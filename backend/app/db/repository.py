from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

from app.services.receipt_parser import ParsedItem
@dataclass(frozen=True)
class ReceiptItemRecord:
    id: str
    description: str
    price_cents: int


@dataclass(frozen=True)
class ParticipantRecord:
    id: str
    display_name: str
    running_total_cents: int


@dataclass(frozen=True)
class ItemAllocation:
    participant_id: str
    receipt_item_id: str
    amount_cents: int


@dataclass(frozen=True)
class ParticipantLedgerLine:
    receipt_image_id: str
    bill_description: str
    receipt_item_id: str
    item_description: str
    amount_cents: int


class SplitItRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.database_url)

    def _connect(self):
        if not self.enabled:
            raise RuntimeError("DATABASE_URL not configured")
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        return psycopg.connect(self.database_url)

    def create_receipt_image(self, *, owner_id: str, description: str, image_bytes: bytes) -> str:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO receipt_images (owner_id, description, image_blob)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (owner_id, description, image_bytes),
            )
            receipt_id = cur.fetchone()[0]
            conn.commit()
            return str(receipt_id)

    def replace_receipt_items(self, *, receipt_image_id: str, items: Sequence[ParsedItem]) -> list[ReceiptItemRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM receipt_items
                WHERE receipt_image_id = %s
                """,
                (receipt_image_id,),
            )

            inserted: list[ReceiptItemRecord] = []
            for item in items:
                cur.execute(
                    """
                    INSERT INTO receipt_items (receipt_image_id, description, item_price_cents)
                    VALUES (%s, %s, %s)
                    RETURNING id, description, item_price_cents
                    """,
                    (receipt_image_id, item.description, item.price_cents),
                )
                row = cur.fetchone()
                inserted.append(ReceiptItemRecord(id=str(row[0]), description=str(row[1]), price_cents=int(row[2])))

            conn.commit()
            return inserted

    def get_receipt_items(self, *, receipt_image_id: str) -> list[ReceiptItemRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, description, item_price_cents
                FROM receipt_items
                WHERE receipt_image_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (receipt_image_id,),
            )
            return [ReceiptItemRecord(id=row[0], description=row[1], price_cents=int(row[2])) for row in cur.fetchall()]

    def list_participants(self) -> list[ParticipantRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, display_name, running_total_cents
                FROM participants
                ORDER BY created_at ASC, display_name ASC
                """
            )
            return [
                ParticipantRecord(id=row[0], display_name=row[1], running_total_cents=int(row[2]))
                for row in cur.fetchall()
            ]

    def get_participants_by_ids(self, *, participant_ids: Sequence[str]) -> list[ParticipantRecord]:
        if not participant_ids:
            return []

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, display_name, running_total_cents
                FROM participants
                WHERE id = ANY(%s::uuid[])
                """,
                (list(participant_ids),),
            )
            return [
                ParticipantRecord(id=row[0], display_name=row[1], running_total_cents=int(row[2]))
                for row in cur.fetchall()
            ]

    def create_or_get_participant(self, *, display_name: str) -> ParticipantRecord:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO participants (display_name, running_total_cents)
                VALUES (%s, 0)
                ON CONFLICT (display_name)
                DO UPDATE SET display_name = EXCLUDED.display_name
                RETURNING id::text, display_name, running_total_cents
                """,
                (display_name,),
            )
            row = cur.fetchone()
            conn.commit()
            return ParticipantRecord(id=row[0], display_name=row[1], running_total_cents=int(row[2]))

    def participant_has_allocations(self, *, participant_id: str) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM participant_item_allocations
                    WHERE participant_id = %s
                )
                """,
                (participant_id,),
            )
            return bool(cur.fetchone()[0])

    def delete_participant(self, *, participant_id: str) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM participants
                WHERE id = %s
                """,
                (participant_id,),
            )
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted

    def replace_allocations_for_receipt(self, *, receipt_image_id: str, allocations: Iterable[ItemAllocation]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text
                FROM receipt_items
                WHERE receipt_image_id = %s
                """,
                (receipt_image_id,),
            )
            item_ids = [row[0] for row in cur.fetchall()]

            if item_ids:
                cur.execute(
                    """
                    DELETE FROM participant_item_allocations
                    WHERE receipt_item_id = ANY(%s::uuid[])
                    """,
                    (item_ids,),
                )

            for alloc in allocations:
                cur.execute(
                    """
                    INSERT INTO participant_item_allocations (participant_id, receipt_item_id, amount_cents)
                    VALUES (%s, %s, %s)
                    """,
                    (alloc.participant_id, alloc.receipt_item_id, alloc.amount_cents),
                )

            conn.commit()

    def get_participant_ledger_lines(self, *, participant_id: str) -> list[ParticipantLedgerLine]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ri.id::text AS receipt_image_id,
                    ri.description AS bill_description,
                    ritem.id::text AS receipt_item_id,
                    ritem.description AS item_description,
                    pia.amount_cents
                FROM participant_item_allocations pia
                JOIN receipt_items ritem ON ritem.id = pia.receipt_item_id
                JOIN receipt_images ri ON ri.id = ritem.receipt_image_id
                WHERE pia.participant_id = %s
                ORDER BY ri.created_at DESC, ri.id DESC, ritem.id ASC
                """,
                (participant_id,),
            )
            return [
                ParticipantLedgerLine(
                    receipt_image_id=row[0],
                    bill_description=row[1],
                    receipt_item_id=row[2],
                    item_description=row[3],
                    amount_cents=int(row[4]),
                )
                for row in cur.fetchall()
            ]
