from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

from app.services.receipt_parser import ParsedItem


class RepositoryNotFoundError(LookupError):
    """Raised when a required row is not found."""


class RepositoryConflictError(ValueError):
    """Raised when a write conflicts with existing data."""


@dataclass(frozen=True)
class ReceiptItemRecord:
    id: str
    description: str
    price_cents: int


@dataclass(frozen=True)
class BillPreviewRecord:
    receipt_image_id: str
    bill_description: str
    entered_at: datetime
    has_image: bool


@dataclass(frozen=True)
class ReceiptImageRecord:
    image_blob: bytes | None
    image_path: str | None


@dataclass(frozen=True)
class BillSplitParticipantLine:
    receipt_item_id: str
    item_description: str
    amount_cents: int


@dataclass(frozen=True)
class BillSplitParticipantRecord:
    participant_id: str
    participant_name: str
    participant_total_cents: int
    lines: list[BillSplitParticipantLine]


@dataclass(frozen=True)
class BillSplitDetailRecord:
    receipt_image_id: str
    bill_description: str
    entered_at: datetime
    bill_total_cents: int
    has_image: bool
    participants: list[BillSplitParticipantRecord]


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
class RunningBalanceTransactionEvent:
    event_id: str
    event_at: datetime
    amount_cents: int
    reference_details: str


@dataclass(frozen=True)
class RunningBalanceParticipant:
    participant_id: str
    participant_name: str
    lines: list[RunningBalanceLine]
    settlement_events: list[RunningBalanceTransactionEvent]
    repayment_events: list[RunningBalanceTransactionEvent]


@dataclass(frozen=True)
class FolioSummaryRecord:
    participant_id: str
    display_name: str
    total_charged_cents: int
    total_settled_cents: int
    total_repaid_cents: int
    net_balance_cents: int
    status: str
    overpayment_cents: int


@dataclass(frozen=True)
class FolioEventRecord:
    event_id: str
    event_at: datetime
    event_type: str
    amount_cents: int
    previous_net_balance_cents: int
    new_net_balance_cents: int
    reference_details: str
    receipt_image_id: str | None
    receipt_item_id: str | None


@dataclass(frozen=True)
class FolioDetailRecord:
    summary: FolioSummaryRecord
    charge_events: list[FolioEventRecord]
    settlement_events: list[FolioEventRecord]
    repayment_events: list[FolioEventRecord]


@dataclass(frozen=True)
class SettlementCreateResult:
    settlement_id: str
    previous_net_balance_cents: int
    settlement_amount_cents: int
    new_net_balance_cents: int
    status: str
    overpayment_cents: int
    idempotency_replayed: bool


@dataclass(frozen=True)
class SettlementReverseResult:
    settlement_id: str
    previous_net_balance_cents: int
    reversed_settlement_amount_cents: int
    new_net_balance_cents: int
    status: str
    overpayment_cents: int
    reversal_applied: bool


@dataclass(frozen=True)
class RepaymentCreateResult:
    repayment_id: str
    previous_net_balance_cents: int
    repayment_amount_cents: int
    new_net_balance_cents: int
    status: str
    overpayment_cents: int
    idempotency_replayed: bool


@dataclass(frozen=True)
class RepaymentReverseResult:
    repayment_id: str
    previous_net_balance_cents: int
    reversed_repayment_amount_cents: int
    new_net_balance_cents: int
    status: str
    overpayment_cents: int
    reversal_applied: bool


@dataclass(frozen=True)
class RunningTotalMismatchRecord:
    participant_id: str
    display_name: str
    cached_net_balance_cents: int
    computed_net_balance_cents: int
    delta_cents: int


def folio_status_from_net_balance(net_balance_cents: int) -> str:
    if net_balance_cents > 0:
        return "owes_you"
    if net_balance_cents < 0:
        return "you_owe_them"
    return "settled"


def compute_folio_metrics(
    total_charged_cents: int,
    total_settled_cents: int,
    total_repaid_cents: int = 0,
) -> tuple[int, str, int]:
    net_balance_cents = total_charged_cents - total_settled_cents + total_repaid_cents
    overpayment_cents = max(-net_balance_cents, 0)
    return net_balance_cents, folio_status_from_net_balance(net_balance_cents), overpayment_cents


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

    @staticmethod
    def _map_folio_summary_row(row: tuple[str, str, int, int, int]) -> FolioSummaryRecord:
        total_charged_cents = int(row[2])
        total_settled_cents = int(row[3])
        total_repaid_cents = int(row[4])
        net_balance_cents, status, overpayment_cents = compute_folio_metrics(
            total_charged_cents,
            total_settled_cents,
            total_repaid_cents,
        )
        return FolioSummaryRecord(
            participant_id=row[0],
            display_name=row[1],
            total_charged_cents=total_charged_cents,
            total_settled_cents=total_settled_cents,
            total_repaid_cents=total_repaid_cents,
            net_balance_cents=net_balance_cents,
            status=status,
            overpayment_cents=overpayment_cents,
        )

    def _fetch_folio_summary_rows(self, *, cur, participant_id: str | None = None) -> list[FolioSummaryRecord]:
        query = """
            SELECT
                p.id::text AS participant_id,
                p.display_name,
                COALESCE(ch.total_charged_cents, 0)::int AS total_charged_cents,
                COALESCE(st.total_settled_cents, 0)::int AS total_settled_cents,
                COALESCE(rp.total_repaid_cents, 0)::int AS total_repaid_cents
            FROM participants p
            LEFT JOIN (
                SELECT
                    participant_id,
                    SUM(amount_cents)::bigint AS total_charged_cents
                FROM participant_item_allocations
                GROUP BY participant_id
            ) ch ON ch.participant_id = p.id
            LEFT JOIN (
                SELECT
                    participant_id,
                    SUM(amount_cents)::bigint AS total_settled_cents
                FROM participant_settlements
                WHERE reversed_at IS NULL
                GROUP BY participant_id
            ) st ON st.participant_id = p.id
            LEFT JOIN (
                SELECT
                    participant_id,
                    SUM(amount_cents)::bigint AS total_repaid_cents
                FROM participant_repayments
                WHERE reversed_at IS NULL
                GROUP BY participant_id
            ) rp ON rp.participant_id = p.id
        """

        params: tuple[str, ...] = ()
        if participant_id is not None:
            query += " WHERE p.id = %s"
            params = (participant_id,)

        query += " ORDER BY p.created_at ASC, p.display_name ASC"
        cur.execute(query, params)
        return [self._map_folio_summary_row(row) for row in cur.fetchall()]

    def create_receipt_image(self, *, owner_id: str, description: str, image_bytes: bytes) -> str:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO receipt_images (owner_id, description, image_blob, status, finalized_at)
                VALUES (%s, %s, %s, 'draft', NULL)
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

            # Editing items re-opens the bill as draft until splits are submitted again.
            cur.execute(
                """
                UPDATE receipt_images
                SET
                    status = 'draft',
                    finalized_at = NULL
                WHERE id = %s
                """,
                (receipt_image_id,),
            )

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

    def list_bill_previews(self) -> list[BillPreviewRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id::text AS receipt_image_id,
                    description AS bill_description,
                    created_at AS entered_at,
                    (image_blob IS NOT NULL OR image_path IS NOT NULL) AS has_image
                FROM receipt_images
                WHERE status = 'finalized'
                ORDER BY created_at DESC, id DESC
                """
            )
            return [
                BillPreviewRecord(
                    receipt_image_id=row[0],
                    bill_description=row[1],
                    entered_at=row[2],
                    has_image=bool(row[3]),
                )
                for row in cur.fetchall()
            ]

    def get_receipt_image(self, *, receipt_image_id: str) -> ReceiptImageRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT image_blob, image_path
                FROM receipt_images
                WHERE id = %s
                """,
                (receipt_image_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            image_blob = bytes(row[0]) if row[0] is not None else None
            return ReceiptImageRecord(
                image_blob=image_blob,
                image_path=row[1],
            )

    def get_bill_split_detail(self, *, receipt_image_id: str) -> BillSplitDetailRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ri.id::text AS receipt_image_id,
                    ri.description AS bill_description,
                    ri.created_at AS entered_at,
                    (ri.image_blob IS NOT NULL OR ri.image_path IS NOT NULL) AS has_image,
                    p.id::text AS participant_id,
                    p.display_name AS participant_name,
                    ritem.id::text AS receipt_item_id,
                    ritem.description AS item_description,
                    pia.amount_cents::int AS amount_cents
                FROM receipt_images ri
                LEFT JOIN receipt_items ritem
                    ON ritem.receipt_image_id = ri.id
                LEFT JOIN participant_item_allocations pia
                    ON pia.receipt_item_id = ritem.id
                LEFT JOIN participants p
                    ON p.id = pia.participant_id
                WHERE ri.id = %s
                ORDER BY
                    p.display_name ASC NULLS LAST,
                    p.id ASC NULLS LAST,
                    ritem.created_at ASC NULLS LAST,
                    ritem.id ASC NULLS LAST
                """,
                (receipt_image_id,),
            )
            rows = cur.fetchall()

        if not rows:
            return None

        receipt_id = rows[0][0]
        bill_description = rows[0][1]
        entered_at = rows[0][2]
        has_image = bool(rows[0][3])

        participants_map: dict[str, dict] = {}

        for row in rows:
            participant_id = row[4]
            if participant_id is None:
                continue

            if participant_id not in participants_map:
                participants_map[participant_id] = {
                    "participant_name": row[5],
                    "participant_total_cents": 0,
                    "lines": [],
                }

            if row[6] is None:
                continue

            amount_cents = int(row[8])
            participants_map[participant_id]["lines"].append(
                BillSplitParticipantLine(
                    receipt_item_id=row[6],
                    item_description=row[7],
                    amount_cents=amount_cents,
                )
            )
            participants_map[participant_id]["participant_total_cents"] += amount_cents

        participants = [
            BillSplitParticipantRecord(
                participant_id=participant_id,
                participant_name=data["participant_name"],
                participant_total_cents=data["participant_total_cents"],
                lines=data["lines"],
            )
            for participant_id, data in participants_map.items()
        ]

        bill_total_cents = sum(participant.participant_total_cents for participant in participants)

        return BillSplitDetailRecord(
            receipt_image_id=receipt_id,
            bill_description=bill_description,
            entered_at=entered_at,
            bill_total_cents=bill_total_cents,
            has_image=has_image,
            participants=participants,
        )

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

            cur.execute(
                """
                UPDATE receipt_images
                SET
                    status = 'finalized',
                    finalized_at = NOW()
                WHERE id = %s
                """,
                (receipt_image_id,),
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

    def list_participant_folios(self) -> list[FolioSummaryRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            return self._fetch_folio_summary_rows(cur=cur)

    def get_participant_folio(self, *, participant_id: str, max_events: int = 100) -> FolioDetailRecord:
        with self._connect() as conn, conn.cursor() as cur:
            summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
            if not summaries:
                raise RepositoryNotFoundError("Participant not found.")

            cur.execute(
                """
                WITH charge_events AS (
                    SELECT
                        pia.id::text AS event_id,
                        pia.created_at AS event_at,
                        'charge'::text AS event_type,
                        1::int AS event_sort_order,
                        pia.amount_cents::int AS amount_cents,
                        pia.amount_cents::int AS net_delta,
                        ri.id::text AS receipt_image_id,
                        ritem.id::text AS receipt_item_id,
                        CONCAT_WS(' | ', ri.description, ritem.description) AS reference_details
                    FROM participant_item_allocations pia
                    JOIN receipt_items ritem ON ritem.id = pia.receipt_item_id
                    JOIN receipt_images ri ON ri.id = ritem.receipt_image_id
                    WHERE pia.participant_id = %s
                ),
                settlement_events AS (
                    SELECT
                        ps.id::text AS event_id,
                        COALESCE(ps.paid_at, ps.recorded_at) AS event_at,
                        'settlement'::text AS event_type,
                        2::int AS event_sort_order,
                        ps.amount_cents::int AS amount_cents,
                        (-ps.amount_cents)::int AS net_delta,
                        NULL::text AS receipt_image_id,
                        NULL::text AS receipt_item_id,
                        COALESCE(ps.note, 'Settlement') AS reference_details
                    FROM participant_settlements ps
                    WHERE ps.participant_id = %s
                      AND ps.reversed_at IS NULL
                ),
                repayment_events AS (
                    SELECT
                        pr.id::text AS event_id,
                        COALESCE(pr.paid_at, pr.recorded_at) AS event_at,
                        'repayment'::text AS event_type,
                        3::int AS event_sort_order,
                        pr.amount_cents::int AS amount_cents,
                        pr.amount_cents::int AS net_delta,
                        NULL::text AS receipt_image_id,
                        NULL::text AS receipt_item_id,
                        COALESCE(pr.note, 'Repayment') AS reference_details
                    FROM participant_repayments pr
                    WHERE pr.participant_id = %s
                      AND pr.reversed_at IS NULL
                ),
                events AS (
                    SELECT * FROM charge_events
                    UNION ALL
                    SELECT * FROM settlement_events
                    UNION ALL
                    SELECT * FROM repayment_events
                ),
                ordered AS (
                    SELECT
                        event_id,
                        event_at,
                        event_type,
                        event_sort_order,
                        amount_cents,
                        net_delta,
                        receipt_image_id,
                        receipt_item_id,
                        reference_details,
                        SUM(net_delta) OVER (
                            ORDER BY event_at ASC, event_sort_order ASC, event_id ASC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        )::int AS cumulative_net
                    FROM events
                )
                SELECT
                    event_id,
                    event_at,
                    event_type,
                    amount_cents,
                    (cumulative_net - net_delta)::int AS previous_net_balance_cents,
                    cumulative_net::int AS new_net_balance_cents,
                    reference_details,
                    receipt_image_id,
                    receipt_item_id
                FROM ordered
                ORDER BY event_at DESC, event_sort_order DESC, event_id DESC
                LIMIT %s
                """,
                (participant_id, participant_id, participant_id, max_events),
            )
            event_rows = cur.fetchall()

        events = [
            FolioEventRecord(
                event_id=row[0],
                event_at=row[1],
                event_type=row[2],
                amount_cents=int(row[3]),
                previous_net_balance_cents=int(row[4]),
                new_net_balance_cents=int(row[5]),
                reference_details=row[6] or "",
                receipt_image_id=row[7],
                receipt_item_id=row[8],
            )
            for row in event_rows
        ]

        return FolioDetailRecord(
            summary=summaries[0],
            charge_events=[event for event in events if event.event_type == "charge"],
            settlement_events=[event for event in events if event.event_type == "settlement"],
            repayment_events=[event for event in events if event.event_type == "repayment"],
        )

    def create_participant_settlement(
        self,
        *,
        participant_id: str,
        amount_cents: int,
        paid_at: datetime | None,
        note: str | None,
        idempotency_key: str | None,
        created_by: str | None,
    ) -> SettlementCreateResult:
        with self._connect() as conn, conn.cursor() as cur:
            if idempotency_key:
                cur.execute(
                    """
                    SELECT
                        id::text,
                        participant_id::text,
                        amount_cents,
                        previous_net_balance_cents,
                        new_net_balance_cents
                    FROM participant_settlements
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    if existing[1] != participant_id:
                        raise RepositoryConflictError(
                            "Idempotency key already exists for a different participant."
                        )

                    summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
                    if not summaries:
                        raise RepositoryNotFoundError("Participant not found.")

                    return SettlementCreateResult(
                        settlement_id=existing[0],
                        previous_net_balance_cents=int(existing[3]),
                        settlement_amount_cents=int(existing[2]),
                        new_net_balance_cents=int(existing[4]),
                        status=summaries[0].status,
                        overpayment_cents=summaries[0].overpayment_cents,
                        idempotency_replayed=True,
                    )

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                FOR UPDATE
                """,
                (participant_id,),
            )
            participant_row = cur.fetchone()
            if participant_row is None:
                raise RepositoryNotFoundError("Participant not found.")

            previous_net_balance_cents = int(participant_row[0])
            expected_new_net_balance_cents = previous_net_balance_cents - amount_cents

            cur.execute(
                """
                INSERT INTO participant_settlements (
                    participant_id,
                    amount_cents,
                    paid_at,
                    note,
                    idempotency_key,
                    created_by,
                    previous_net_balance_cents,
                    new_net_balance_cents
                )
                VALUES (
                    %s,
                    %s,
                    COALESCE(%s, NOW()),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id::text
                """,
                (
                    participant_id,
                    amount_cents,
                    paid_at,
                    note,
                    idempotency_key,
                    created_by,
                    previous_net_balance_cents,
                    expected_new_net_balance_cents,
                ),
            )
            settlement_id = str(cur.fetchone()[0])

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                """,
                (participant_id,),
            )
            current_net_balance_cents = int(cur.fetchone()[0])

            summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
            if not summaries:
                raise RepositoryNotFoundError("Participant not found.")

            conn.commit()
            return SettlementCreateResult(
                settlement_id=settlement_id,
                previous_net_balance_cents=previous_net_balance_cents,
                settlement_amount_cents=amount_cents,
                new_net_balance_cents=current_net_balance_cents,
                status=summaries[0].status,
                overpayment_cents=summaries[0].overpayment_cents,
                idempotency_replayed=False,
            )

    def reverse_participant_settlement(
        self,
        *,
        participant_id: str,
        settlement_id: str,
        reversed_by: str | None,
        reversal_note: str | None,
    ) -> SettlementReverseResult:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT amount_cents, reversed_at IS NOT NULL
                FROM participant_settlements
                WHERE id = %s
                  AND participant_id = %s
                FOR UPDATE
                """,
                (settlement_id, participant_id),
            )
            settlement_row = cur.fetchone()
            if settlement_row is None:
                raise RepositoryNotFoundError("Settlement not found.")

            amount_cents = int(settlement_row[0])
            already_reversed = bool(settlement_row[1])

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                FOR UPDATE
                """,
                (participant_id,),
            )
            participant_row = cur.fetchone()
            if participant_row is None:
                raise RepositoryNotFoundError("Participant not found.")

            previous_net_balance_cents = int(participant_row[0])

            if not already_reversed:
                cur.execute(
                    """
                    UPDATE participant_settlements
                    SET
                        reversed_at = NOW(),
                        reversed_by = %s,
                        reversal_note = %s
                    WHERE id = %s
                      AND participant_id = %s
                    """,
                    (reversed_by, reversal_note, settlement_id, participant_id),
                )

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                """,
                (participant_id,),
            )
            new_net_balance_cents = int(cur.fetchone()[0])

            summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
            if not summaries:
                raise RepositoryNotFoundError("Participant not found.")

            conn.commit()
            return SettlementReverseResult(
                settlement_id=settlement_id,
                previous_net_balance_cents=previous_net_balance_cents,
                reversed_settlement_amount_cents=amount_cents,
                new_net_balance_cents=new_net_balance_cents,
                status=summaries[0].status,
                overpayment_cents=summaries[0].overpayment_cents,
                reversal_applied=not already_reversed,
            )

    def create_participant_repayment(
        self,
        *,
        participant_id: str,
        amount_cents: int,
        paid_at: datetime | None,
        note: str | None,
        idempotency_key: str | None,
        created_by: str | None,
    ) -> RepaymentCreateResult:
        with self._connect() as conn, conn.cursor() as cur:
            if idempotency_key:
                cur.execute(
                    """
                    SELECT
                        id::text,
                        participant_id::text,
                        amount_cents,
                        previous_net_balance_cents,
                        new_net_balance_cents
                    FROM participant_repayments
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    if existing[1] != participant_id:
                        raise RepositoryConflictError(
                            "Idempotency key already exists for a different participant."
                        )

                    summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
                    if not summaries:
                        raise RepositoryNotFoundError("Participant not found.")

                    return RepaymentCreateResult(
                        repayment_id=existing[0],
                        previous_net_balance_cents=int(existing[3]),
                        repayment_amount_cents=int(existing[2]),
                        new_net_balance_cents=int(existing[4]),
                        status=summaries[0].status,
                        overpayment_cents=summaries[0].overpayment_cents,
                        idempotency_replayed=True,
                    )

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                FOR UPDATE
                """,
                (participant_id,),
            )
            participant_row = cur.fetchone()
            if participant_row is None:
                raise RepositoryNotFoundError("Participant not found.")

            previous_net_balance_cents = int(participant_row[0])
            expected_new_net_balance_cents = previous_net_balance_cents + amount_cents

            cur.execute(
                """
                INSERT INTO participant_repayments (
                    participant_id,
                    amount_cents,
                    paid_at,
                    note,
                    idempotency_key,
                    created_by,
                    previous_net_balance_cents,
                    new_net_balance_cents
                )
                VALUES (
                    %s,
                    %s,
                    COALESCE(%s, NOW()),
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id::text
                """,
                (
                    participant_id,
                    amount_cents,
                    paid_at,
                    note,
                    idempotency_key,
                    created_by,
                    previous_net_balance_cents,
                    expected_new_net_balance_cents,
                ),
            )
            repayment_id = str(cur.fetchone()[0])

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                """,
                (participant_id,),
            )
            current_net_balance_cents = int(cur.fetchone()[0])

            summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
            if not summaries:
                raise RepositoryNotFoundError("Participant not found.")

            conn.commit()
            return RepaymentCreateResult(
                repayment_id=repayment_id,
                previous_net_balance_cents=previous_net_balance_cents,
                repayment_amount_cents=amount_cents,
                new_net_balance_cents=current_net_balance_cents,
                status=summaries[0].status,
                overpayment_cents=summaries[0].overpayment_cents,
                idempotency_replayed=False,
            )

    def reverse_participant_repayment(
        self,
        *,
        participant_id: str,
        repayment_id: str,
        reversed_by: str | None,
        reversal_note: str | None,
    ) -> RepaymentReverseResult:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT amount_cents, reversed_at IS NOT NULL
                FROM participant_repayments
                WHERE id = %s
                  AND participant_id = %s
                FOR UPDATE
                """,
                (repayment_id, participant_id),
            )
            repayment_row = cur.fetchone()
            if repayment_row is None:
                raise RepositoryNotFoundError("Repayment not found.")

            amount_cents = int(repayment_row[0])
            already_reversed = bool(repayment_row[1])

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                FOR UPDATE
                """,
                (participant_id,),
            )
            participant_row = cur.fetchone()
            if participant_row is None:
                raise RepositoryNotFoundError("Participant not found.")

            previous_net_balance_cents = int(participant_row[0])

            if not already_reversed:
                cur.execute(
                    """
                    UPDATE participant_repayments
                    SET
                        reversed_at = NOW(),
                        reversed_by = %s,
                        reversal_note = %s
                    WHERE id = %s
                      AND participant_id = %s
                    """,
                    (reversed_by, reversal_note, repayment_id, participant_id),
                )

            cur.execute(
                """
                SELECT running_total_cents
                FROM participants
                WHERE id = %s
                """,
                (participant_id,),
            )
            new_net_balance_cents = int(cur.fetchone()[0])

            summaries = self._fetch_folio_summary_rows(cur=cur, participant_id=participant_id)
            if not summaries:
                raise RepositoryNotFoundError("Participant not found.")

            conn.commit()
            return RepaymentReverseResult(
                repayment_id=repayment_id,
                previous_net_balance_cents=previous_net_balance_cents,
                reversed_repayment_amount_cents=amount_cents,
                new_net_balance_cents=new_net_balance_cents,
                status=summaries[0].status,
                overpayment_cents=summaries[0].overpayment_cents,
                reversal_applied=not already_reversed,
            )

    def list_running_balance_participants(self) -> list[RunningBalanceParticipant]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH charge_events AS (
                    SELECT
                        pia.participant_id,
                        CONCAT('charge:', pia.id::text) AS event_id,
                        pia.created_at AS event_at,
                        1::int AS event_sort_order,
                        pia.amount_cents::int AS net_delta,
                        'charge'::text AS event_type,
                        ri.id::text AS receipt_id,
                        ri.description AS bill_description,
                        ritem.id::text AS receipt_item_id,
                        ritem.description AS item_name,
                        pia.amount_cents::int AS amount_cents,
                        CONCAT_WS(' | ', ri.description, ritem.description) AS reference_details
                    FROM participant_item_allocations pia
                    JOIN receipt_items ritem ON ritem.id = pia.receipt_item_id
                    JOIN receipt_images ri ON ri.id = ritem.receipt_image_id
                ),
                settlement_events AS (
                    SELECT
                        ps.participant_id,
                        CONCAT('settlement:', ps.id::text) AS event_id,
                        COALESCE(ps.paid_at, ps.recorded_at) AS event_at,
                        2::int AS event_sort_order,
                        (-ps.amount_cents)::int AS net_delta,
                        'settlement'::text AS event_type,
                        NULL::text AS receipt_id,
                        NULL::text AS bill_description,
                        NULL::text AS receipt_item_id,
                        NULL::text AS item_name,
                        ps.amount_cents::int AS amount_cents,
                        COALESCE(ps.note, 'Settlement') AS reference_details
                    FROM participant_settlements ps
                    WHERE ps.reversed_at IS NULL
                ),
                repayment_events AS (
                    SELECT
                        pr.participant_id,
                        CONCAT('repayment:', pr.id::text) AS event_id,
                        COALESCE(pr.paid_at, pr.recorded_at) AS event_at,
                        3::int AS event_sort_order,
                        pr.amount_cents::int AS net_delta,
                        'repayment'::text AS event_type,
                        NULL::text AS receipt_id,
                        NULL::text AS bill_description,
                        NULL::text AS receipt_item_id,
                        NULL::text AS item_name,
                        pr.amount_cents::int AS amount_cents,
                        COALESCE(pr.note, 'Repayment') AS reference_details
                    FROM participant_repayments pr
                    WHERE pr.reversed_at IS NULL
                ),
                events AS (
                    SELECT * FROM charge_events
                    UNION ALL
                    SELECT * FROM settlement_events
                    UNION ALL
                    SELECT * FROM repayment_events
                ),
                ordered AS (
                    SELECT
                        e.participant_id,
                        e.event_id,
                        e.event_at,
                        e.event_sort_order,
                        e.event_type,
                        e.receipt_id,
                        e.bill_description,
                        e.receipt_item_id,
                        e.item_name,
                        e.amount_cents,
                        e.reference_details,
                        ROW_NUMBER() OVER (
                            PARTITION BY e.participant_id
                            ORDER BY e.event_at ASC, e.event_sort_order ASC, e.event_id ASC
                        ) AS event_rank,
                        SUM(e.net_delta) OVER (
                            PARTITION BY e.participant_id
                            ORDER BY e.event_at ASC, e.event_sort_order ASC, e.event_id ASC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        )::int AS cumulative_net
                    FROM events e
                ),
                last_zero AS (
                    SELECT
                        participant_id,
                        MAX(event_rank) AS last_zero_rank
                    FROM ordered
                    WHERE cumulative_net = 0
                    GROUP BY participant_id
                ),
                active_charge_events AS (
                    SELECT
                        o.participant_id,
                        o.event_id,
                        o.event_type,
                        o.receipt_id,
                        o.bill_description,
                        o.receipt_item_id,
                        o.item_name,
                        o.amount_cents,
                        o.reference_details,
                        o.event_at,
                        o.event_sort_order
                    FROM ordered o
                    LEFT JOIN last_zero lz ON lz.participant_id = o.participant_id
                    WHERE o.event_rank > COALESCE(lz.last_zero_rank, 0)
                )
                SELECT
                    p.id::text AS participant_id,
                    p.display_name AS participant_name,
                    ae.event_id,
                    ae.event_at,
                    ae.event_type,
                    ae.receipt_id,
                    ae.bill_description,
                    ae.receipt_item_id,
                    ae.item_name,
                    ae.amount_cents,
                    ae.reference_details
                FROM participants p
                LEFT JOIN active_charge_events ae ON ae.participant_id = p.id
                ORDER BY
                    p.display_name ASC,
                    ae.event_at DESC NULLS LAST,
                    ae.event_sort_order DESC NULLS LAST,
                    ae.event_id DESC NULLS LAST
                """
            )
            rows = cur.fetchall()

        participants: list[RunningBalanceParticipant] = []
        current_participant_id: str | None = None
        current_lines: list[RunningBalanceLine] = []
        current_settlement_events: list[RunningBalanceTransactionEvent] = []
        current_repayment_events: list[RunningBalanceTransactionEvent] = []
        current_participant_name = ""

        for row in rows:
            participant_id = row[0]
            participant_name = row[1]
            event_id = row[2]

            if participant_id != current_participant_id:
                if current_participant_id is not None:
                    participants.append(
                        RunningBalanceParticipant(
                            participant_id=current_participant_id,
                            participant_name=current_participant_name,
                            lines=current_lines,
                            settlement_events=current_settlement_events,
                            repayment_events=current_repayment_events,
                        )
                    )
                current_participant_id = participant_id
                current_participant_name = participant_name
                current_lines = []
                current_settlement_events = []
                current_repayment_events = []

            if event_id is None:
                continue

            event_at = row[3]
            event_type = row[4]
            if event_type == "charge":
                if row[5] is None:
                    continue
                current_lines.append(
                    RunningBalanceLine(
                        receipt_id=row[5],
                        bill_description=row[6],
                        receipt_item_id=row[7],
                        item_name=row[8],
                        contribution_cents=int(row[9]),
                    )
                )
                continue

            transaction_event = RunningBalanceTransactionEvent(
                event_id=event_id,
                event_at=event_at,
                amount_cents=int(row[9]),
                reference_details=row[10] or "",
            )
            if event_type == "settlement":
                current_settlement_events.append(transaction_event)
            elif event_type == "repayment":
                current_repayment_events.append(transaction_event)

        if current_participant_id is not None:
            participants.append(
                RunningBalanceParticipant(
                    participant_id=current_participant_id,
                    participant_name=current_participant_name,
                    lines=current_lines,
                    settlement_events=current_settlement_events,
                    repayment_events=current_repayment_events,
                )
            )

        return participants

    def list_running_total_mismatches(self) -> list[RunningTotalMismatchRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id::text AS participant_id,
                    p.display_name,
                    p.running_total_cents::int AS cached_net_balance_cents,
                    (
                        COALESCE(ch.total_charged_cents, 0)
                        - COALESCE(st.total_settled_cents, 0)
                        + COALESCE(rp.total_repaid_cents, 0)
                    )::int AS computed_net_balance_cents
                FROM participants p
                LEFT JOIN (
                    SELECT
                        participant_id,
                        SUM(amount_cents)::bigint AS total_charged_cents
                    FROM participant_item_allocations
                    GROUP BY participant_id
                ) ch ON ch.participant_id = p.id
                LEFT JOIN (
                    SELECT
                        participant_id,
                        SUM(amount_cents)::bigint AS total_settled_cents
                    FROM participant_settlements
                    WHERE reversed_at IS NULL
                    GROUP BY participant_id
                ) st ON st.participant_id = p.id
                LEFT JOIN (
                    SELECT
                        participant_id,
                        SUM(amount_cents)::bigint AS total_repaid_cents
                    FROM participant_repayments
                    WHERE reversed_at IS NULL
                    GROUP BY participant_id
                ) rp ON rp.participant_id = p.id
                WHERE p.running_total_cents <> (
                    COALESCE(ch.total_charged_cents, 0)
                    - COALESCE(st.total_settled_cents, 0)
                    + COALESCE(rp.total_repaid_cents, 0)
                )
                ORDER BY p.display_name ASC
                """
            )
            rows = cur.fetchall()

        return [
            RunningTotalMismatchRecord(
                participant_id=row[0],
                display_name=row[1],
                cached_net_balance_cents=int(row[2]),
                computed_net_balance_cents=int(row[3]),
                delta_cents=int(row[2]) - int(row[3]),
            )
            for row in rows
        ]
