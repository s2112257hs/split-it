from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


@dataclass(frozen=True)
class ParsedItem:
    description: str
    price_cents: int


@dataclass(frozen=True)
class ItemAllocation:
    participant_name: str
    receipt_item_id: str
    amount_cents: int


@dataclass(frozen=True)
class ParticipantRecord:
    id: str
    name: str


@dataclass(frozen=True)
class SummaryRecord:
    participant_id: str
    participant_name: str
    total_cents: int


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

    def create_receipt_with_items(self, *, owner_id: str, description: str, image_bytes: bytes, items: Sequence[ParsedItem]) -> tuple[str, list[str]]:
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

            item_ids: list[str] = []
            for item in items:
                cur.execute(
                    """
                    INSERT INTO receipt_items (receipt_image_id, description, item_price_cents)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (receipt_id, item.description, item.price_cents),
                )
                item_ids.append(str(cur.fetchone()[0]))

            conn.commit()
            return str(receipt_id), item_ids

    def add_allocations(self, *, participant_names: Iterable[str], allocations: Iterable[ItemAllocation]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            participant_ids: dict[str, str] = {}
            for participant_name in participant_names:
                cur.execute(
                    """
                    INSERT INTO participants (display_name, running_total_cents)
                    VALUES (%s, 0)
                    ON CONFLICT (display_name)
                    DO UPDATE SET display_name = EXCLUDED.display_name
                    RETURNING id
                    """,
                    (participant_name,),
                )
                participant_ids[participant_name] = str(cur.fetchone()[0])

            for alloc in allocations:
                participant_id = participant_ids[alloc.participant_name]
                cur.execute(
                    """
                    INSERT INTO participant_item_allocations (participant_id, receipt_item_id, amount_cents)
                    VALUES (%s, %s, %s)
                    """,
                    (participant_id, alloc.receipt_item_id, alloc.amount_cents),
                )

            conn.commit()


    def create_participants(self, *, participant_names: Sequence[str]) -> list[ParticipantRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            rows: list[ParticipantRecord] = []
            for participant_name in participant_names:
                cur.execute(
                    """
                    INSERT INTO participants (display_name, running_total_cents)
                    VALUES (%s, 0)
                    ON CONFLICT (display_name)
                    DO UPDATE SET display_name = EXCLUDED.display_name
                    RETURNING id, display_name
                    """,
                    (participant_name,),
                )
                participant_id, display_name = cur.fetchone()
                rows.append(ParticipantRecord(id=str(participant_id), name=str(display_name)))

            conn.commit()
            return rows

    def get_summary(self, *, receipt_image_id: str, participant_ids: Sequence[str]) -> list[SummaryRecord]:
        if not participant_ids:
            return []

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id::text AS participant_id,
                    p.display_name,
                    COALESCE(SUM(CASE WHEN ri.id IS NOT NULL THEN pia.amount_cents ELSE 0 END), 0) AS total_cents
                FROM participants p
                LEFT JOIN participant_item_allocations pia
                    ON pia.participant_id = p.id
                LEFT JOIN receipt_items ri
                    ON ri.id = pia.receipt_item_id
                    AND ri.receipt_image_id = %s
                WHERE p.id = ANY(%s::uuid[])
                GROUP BY p.id, p.display_name
                ORDER BY p.display_name ASC
                """,
                (receipt_image_id, list(participant_ids)),
            )

            return [
                SummaryRecord(
                    participant_id=row[0],
                    participant_name=row[1],
                    total_cents=int(row[2]),
                )
                for row in cur.fetchall()
            ]
