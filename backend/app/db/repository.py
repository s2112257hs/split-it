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


@dataclass(frozen=True)
class RunningBalanceLine:
    receipt_id: str
    bill_description: str
    receipt_item_id: str
    item_name: str
    contribution_cents: int


@dataclass(frozen=True)
class RunningBalanceParticipant:
    participant_id: str
    participant_name: str
    lines: list[RunningBalanceLine]


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

    def list_running_balance_participants(self) -> list[RunningBalanceParticipant]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id::text AS participant_id,
                    p.display_name AS participant_name,
                    ri.id::text AS receipt_id,
                    ri.description AS bill_description,
                    ritem.id::text AS receipt_item_id,
                    ritem.description AS item_name,
                    SUM(pia.amount_cents)::int AS contribution_cents,
                    ri.created_at AS receipt_created_at
                FROM participants p
                LEFT JOIN participant_item_allocations pia ON pia.participant_id = p.id
                LEFT JOIN receipt_items ritem ON ritem.id = pia.receipt_item_id
                LEFT JOIN receipt_images ri ON ri.id = ritem.receipt_image_id
                GROUP BY p.id, p.display_name, ri.id, ri.description, ritem.id, ritem.description, ri.created_at
                ORDER BY p.display_name ASC, ri.created_at DESC NULLS LAST, ri.id DESC NULLS LAST, ritem.id ASC NULLS LAST
                """
            )
            rows = cur.fetchall()

        participants: list[RunningBalanceParticipant] = []
        current_participant_id: str | None = None
        current_lines: list[RunningBalanceLine] = []
        current_participant_name = ""

        for row in rows:
            participant_id = row[0]
            participant_name = row[1]
            receipt_id = row[2]

            if participant_id != current_participant_id:
                if current_participant_id is not None:
                    participants.append(
                        RunningBalanceParticipant(
                            participant_id=current_participant_id,
                            participant_name=current_participant_name,
                            lines=current_lines,
                        )
                    )
                current_participant_id = participant_id
                current_participant_name = participant_name
                current_lines = []

            if receipt_id is None:
                continue

            current_lines.append(
                RunningBalanceLine(
                    receipt_id=receipt_id,
                    bill_description=row[3],
                    receipt_item_id=row[4],
                    item_name=row[5],
                    contribution_cents=int(row[6]),
                )
            )

        if current_participant_id is not None:
            participants.append(
                RunningBalanceParticipant(
                    participant_id=current_participant_id,
                    participant_name=current_participant_name,
                    lines=current_lines,
                )
            )

        return participants
