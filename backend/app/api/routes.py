from __future__ import annotations

from datetime import datetime
from typing import Dict

from flask import Blueprint, current_app, jsonify, request

from app.repositories.repository import (
    ItemAllocation,
    RepositoryConflictError,
    RepositoryNotFoundError,
    SplitItRepository,
)
from app.domain.split_logic import SplitLogicError, split_cents_fair_remainder
from app.services import ocr_service
from app.services.receipt_parser import ReceiptParseError, extract_items_from_ocr_text
from app.api.validators import (
    ApiValidationError,
    is_uuid,
    parse_optional_iso_datetime,
    parse_optional_string,
    parse_positive_cents,
    parse_receipt_items,
    parse_unique_participant_ids,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _json_error(message: str, *, status: int = 400, code: str = "bad_request"):
    return jsonify({"error": {"code": code, "message": message}}), status


def _repo() -> SplitItRepository:
    return SplitItRepository(current_app.config.get("DATABASE_URL", ""))


def _isoformat(value: datetime) -> str:
    return value.isoformat()


def _folio_summary_payload(summary) -> dict:
    return {
        "participant_id": summary.participant_id,
        "display_name": summary.display_name,
        "total_charged_cents": summary.total_charged_cents,
        "total_settled_cents": summary.total_settled_cents,
        "total_repaid_cents": summary.total_repaid_cents,
        "net_balance_cents": summary.net_balance_cents,
        "status": summary.status,
        "overpayment_cents": summary.overpayment_cents,
    }


def _folio_event_payload(event) -> dict:
    return {
        "event_id": event.event_id,
        "event_at": _isoformat(event.event_at),
        "type": event.event_type,
        "amount_cents": event.amount_cents,
        "previous_net_balance_cents": event.previous_net_balance_cents,
        "new_net_balance_cents": event.new_net_balance_cents,
        "previous_owed_cents": event.previous_net_balance_cents,
        "new_owed_cents": event.new_net_balance_cents,
        "reference_details": event.reference_details,
        "receipt_image_id": event.receipt_image_id,
        "receipt_item_id": event.receipt_item_id,
    }


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@api_bp.post("/receipts")
def create_receipt_from_image():
    if "image" not in request.files:
        return _json_error("Missing file field 'image'.", status=400)

    description = request.form.get("description", "").strip()
    if not description:
        return _json_error("Missing field 'description'.", status=400)

    f = request.files["image"]
    if not f or not getattr(f, "filename", ""):
        return _json_error("No file provided in 'image'.", status=400)

    image_bytes = f.read()
    if not image_bytes:
        return _json_error("Uploaded file is empty.", status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    owner_id = request.form.get("owner_id", "").strip() or current_app.config.get("RECEIPT_OWNER_ID", "mvp-owner")

    try:
        receipt_image_id = repo.create_receipt_image(owner_id=owner_id, description=description, image_bytes=image_bytes)
    except Exception:
        return _json_error("Failed to persist receipt image.", status=500, code="db_error")

    try:
        ocr_text = ocr_service.run_ocr(image_bytes)
        parsed_items = extract_items_from_ocr_text(ocr_text)
    except Exception as exc:
        if isinstance(exc, ReceiptParseError):
            return _json_error("Failed to parse receipt text.", status=422, code="parse_failed")
        return _json_error("OCR failed.", status=500, code="ocr_failed")

    return (
        jsonify(
            {
                "receipt_image_id": receipt_image_id,
                "currency": "USD",
                "items": [
                    {"temp_id": f"t{idx}", "description": item.description, "price_cents": item.price_cents}
                    for idx, item in enumerate(parsed_items)
                ],
            }
        ),
        200,
    )


@api_bp.put("/receipts/<receipt_image_id>/items")
def replace_receipt_items(receipt_image_id: str):
    if not is_uuid(receipt_image_id):
        return _json_error("Invalid receipt_image_id.", status=400)

    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    try:
        parsed_items = parse_receipt_items(data.get("items"))
    except ApiValidationError as exc:
        return _json_error(str(exc), status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        inserted = repo.replace_receipt_items(receipt_image_id=receipt_image_id, items=parsed_items)
    except Exception:
        return _json_error("Failed to persist receipt items.", status=500, code="db_error")

    return (
        jsonify(
            {
                "receipt_image_id": receipt_image_id,
                "items": [
                    {"id": item.id, "description": item.description, "price_cents": item.price_cents}
                    for item in inserted
                ],
            }
        ),
        200,
    )


@api_bp.get("/participants")
def list_participants():
    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        participants = repo.list_participants()
    except Exception:
        return _json_error("Failed to fetch participants.", status=500, code="db_error")

    return (
        jsonify(
            {
                "participants": [
                    {
                        "id": participant.id,
                        "display_name": participant.display_name,
                        "running_total_cents": participant.running_total_cents,
                    }
                    for participant in participants
                ]
            }
        ),
        200,
    )


@api_bp.get("/running-balances")
def get_running_balances():
    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        participants = repo.list_running_balance_participants()
    except Exception:
        current_app.logger.exception("Failed to fetch running balance activity.")
        return _json_error(
            "Failed to fetch running balance activity.",
            status=500,
            code="db_error_running_balance_activity",
        )

    try:
        folio_summaries = repo.list_participant_folios()
    except Exception:
        current_app.logger.exception("Failed to fetch running balance folio summaries.")
        return _json_error(
            "Failed to fetch running balance folio summaries.",
            status=501,
            code="db_error_running_balance_folio_summary",
        )

    summary_by_participant_id = {summary.participant_id: summary for summary in folio_summaries}
    response_participants = []
    for participant in participants:
        bills: Dict[str, dict] = {}
        active_cycle_charged_cents = 0
        summary = summary_by_participant_id.get(participant.participant_id)

        for line in participant.lines:
            if line.receipt_id not in bills:
                bills[line.receipt_id] = {
                    "receipt_id": line.receipt_id,
                    "bill_description": line.bill_description,
                    "bill_total_cents": 0,
                    "lines": [],
                }

            bills[line.receipt_id]["lines"].append(
                {
                    "receipt_item_id": line.receipt_item_id,
                    "item_name": line.item_name,
                    "contribution_cents": line.contribution_cents,
                }
            )
            bills[line.receipt_id]["bill_total_cents"] += line.contribution_cents
            active_cycle_charged_cents += line.contribution_cents

        participant_net_balance_cents = summary.net_balance_cents if summary else active_cycle_charged_cents
        participant_status = (
            summary.status
            if summary
            else ("owes_you" if participant_net_balance_cents > 0 else "you_owe_them" if participant_net_balance_cents < 0 else "settled")
        )

        response_participants.append(
            {
                "participant_id": participant.participant_id,
                "participant_name": participant.participant_name,
                "participant_total_cents": participant_net_balance_cents,
                "total_charged_cents": summary.total_charged_cents if summary else active_cycle_charged_cents,
                "total_settled_cents": summary.total_settled_cents if summary else 0,
                "total_repaid_cents": summary.total_repaid_cents if summary else 0,
                "net_balance_cents": participant_net_balance_cents,
                "status": participant_status,
                "bills": list(bills.values()),
                "settlement_events": [
                    {
                        "event_id": event.event_id,
                        "event_at": _isoformat(event.event_at),
                        "amount_cents": event.amount_cents,
                        "reference_details": event.reference_details,
                    }
                    for event in participant.settlement_events
                ],
                "repayment_events": [
                    {
                        "event_id": event.event_id,
                        "event_at": _isoformat(event.event_at),
                        "amount_cents": event.amount_cents,
                        "reference_details": event.reference_details,
                    }
                    for event in participant.repayment_events
                ],
            }
        )

    return jsonify({"participants": response_participants}), 200


@api_bp.get("/participants/folios")
def list_participant_folios():
    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        summaries = repo.list_participant_folios()
    except Exception:
        return _json_error("Failed to fetch participant folios.", status=500, code="db_error")

    return jsonify({"folios": [_folio_summary_payload(summary) for summary in summaries]}), 200


@api_bp.get("/participants/<participant_id>/folio")
def get_participant_folio(participant_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)

    raw_max_events = request.args.get("max_events", "100")
    try:
        max_events = int(raw_max_events)
    except ValueError:
        return _json_error("'max_events' must be an integer.", status=400)

    if max_events <= 0 or max_events > 500:
        return _json_error("'max_events' must be between 1 and 500.", status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        folio = repo.get_participant_folio(participant_id=participant_id, max_events=max_events)
    except RepositoryNotFoundError:
        return _json_error("Participant not found.", status=404, code="not_found")
    except Exception:
        return _json_error("Failed to fetch participant folio.", status=500, code="db_error")

    return (
        jsonify(
            {
                **_folio_summary_payload(folio.summary),
                "charge_events": [_folio_event_payload(event) for event in folio.charge_events],
                "settlement_events": [_folio_event_payload(event) for event in folio.settlement_events],
                "repayment_events": [_folio_event_payload(event) for event in folio.repayment_events],
            }
        ),
        200,
    )


@api_bp.get("/participants/folios/reconciliation")
def get_folio_reconciliation():
    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        mismatches = repo.list_running_total_mismatches()
    except Exception:
        return _json_error("Failed to run folio reconciliation.", status=500, code="db_error")

    return (
        jsonify(
            {
                "mismatch_count": len(mismatches),
                "mismatches": [
                    {
                        "participant_id": mismatch.participant_id,
                        "display_name": mismatch.display_name,
                        "cached_net_balance_cents": mismatch.cached_net_balance_cents,
                        "computed_net_balance_cents": mismatch.computed_net_balance_cents,
                        "delta_cents": mismatch.delta_cents,
                    }
                    for mismatch in mismatches
                ],
            }
        ),
        200,
    )


@api_bp.post("/participants")
def create_participant():
    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    display_name = data.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip():
        return _json_error("'display_name' must be a non-empty string.", status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        participant = repo.create_or_get_participant(display_name=display_name.strip())
    except Exception:
        return _json_error("Failed to persist participant.", status=500, code="db_error")

    return (
        jsonify(
            {
                "id": participant.id,
                "display_name": participant.display_name,
                "running_total_cents": participant.running_total_cents,
            }
        ),
        200,
    )


@api_bp.delete("/participants/<participant_id>")
def delete_participant(participant_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        if repo.participant_has_allocations(participant_id=participant_id):
            return _json_error(
                "Cannot delete participant because they have existing allocations.",
                status=409,
                code="participant_has_allocations",
            )

        deleted = repo.delete_participant(participant_id=participant_id)
    except Exception:
        return _json_error("Failed to delete participant.", status=500, code="db_error")

    if not deleted:
        return _json_error("Participant not found.", status=404, code="not_found")

    return jsonify({"deleted": True}), 200


@api_bp.post("/participants/<participant_id>/settlements")
def create_participant_settlement(participant_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)

    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    try:
        amount_cents = parse_positive_cents(data.get("amount_cents"), field_name="amount_cents")
        paid_at = parse_optional_iso_datetime(data.get("paid_at"), field_name="paid_at")
        note = parse_optional_string(data.get("note"), field_name="note", max_len=500)
        idempotency_key = parse_optional_string(
            data.get("idempotency_key"),
            field_name="idempotency_key",
            max_len=255,
        )
        created_by = parse_optional_string(data.get("created_by"), field_name="created_by", max_len=255)
    except ApiValidationError as exc:
        return _json_error(str(exc), status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        result = repo.create_participant_settlement(
            participant_id=participant_id,
            amount_cents=amount_cents,
            paid_at=paid_at,
            note=note,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
    except RepositoryNotFoundError:
        return _json_error("Participant not found.", status=404, code="not_found")
    except RepositoryConflictError as exc:
        return _json_error(str(exc), status=409, code="conflict")
    except Exception:
        return _json_error("Failed to create settlement.", status=500, code="db_error")

    return (
        jsonify(
            {
                "transaction_type": "settlement",
                "settlement_id": result.settlement_id,
                "previous_net_balance_cents": result.previous_net_balance_cents,
                "payment_amount_cents": result.settlement_amount_cents,
                "settlement_amount_cents": result.settlement_amount_cents,
                "new_net_balance_cents": result.new_net_balance_cents,
                "status": result.status,
                "overpayment_cents": result.overpayment_cents,
                "overpayment_happened": result.overpayment_cents > 0,
                "idempotency_replayed": result.idempotency_replayed,
            }
        ),
        200,
    )


@api_bp.post("/participants/<participant_id>/repayments")
def create_participant_repayment(participant_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)

    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    try:
        amount_cents = parse_positive_cents(data.get("amount_cents"), field_name="amount_cents")
        paid_at = parse_optional_iso_datetime(data.get("paid_at"), field_name="paid_at")
        note = parse_optional_string(data.get("note"), field_name="note", max_len=500)
        idempotency_key = parse_optional_string(
            data.get("idempotency_key"),
            field_name="idempotency_key",
            max_len=255,
        )
        created_by = parse_optional_string(data.get("created_by"), field_name="created_by", max_len=255)
    except ApiValidationError as exc:
        return _json_error(str(exc), status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        result = repo.create_participant_repayment(
            participant_id=participant_id,
            amount_cents=amount_cents,
            paid_at=paid_at,
            note=note,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
    except RepositoryNotFoundError:
        return _json_error("Participant not found.", status=404, code="not_found")
    except RepositoryConflictError as exc:
        return _json_error(str(exc), status=409, code="conflict")
    except Exception:
        return _json_error("Failed to create repayment.", status=500, code="db_error")

    return (
        jsonify(
            {
                "transaction_type": "repayment",
                "repayment_id": result.repayment_id,
                "previous_net_balance_cents": result.previous_net_balance_cents,
                "repayment_amount_cents": result.repayment_amount_cents,
                "new_net_balance_cents": result.new_net_balance_cents,
                "status": result.status,
                "overpayment_cents": result.overpayment_cents,
                "idempotency_replayed": result.idempotency_replayed,
            }
        ),
        200,
    )


@api_bp.post("/participants/<participant_id>/settlements/<settlement_id>/reverse")
def reverse_participant_settlement(participant_id: str, settlement_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)
    if not is_uuid(settlement_id):
        return _json_error("Invalid settlement_id.", status=400)

    data = request.get_json(silent=True) or {}

    try:
        reversal_note = parse_optional_string(data.get("note"), field_name="note", max_len=500)
        reversed_by = parse_optional_string(data.get("reversed_by"), field_name="reversed_by", max_len=255)
    except ApiValidationError as exc:
        return _json_error(str(exc), status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        result = repo.reverse_participant_settlement(
            participant_id=participant_id,
            settlement_id=settlement_id,
            reversed_by=reversed_by,
            reversal_note=reversal_note,
        )
    except RepositoryNotFoundError:
        return _json_error("Settlement not found.", status=404, code="not_found")
    except Exception:
        return _json_error("Failed to reverse settlement.", status=500, code="db_error")

    return (
        jsonify(
            {
                "transaction_type": "settlement_reversal",
                "settlement_id": result.settlement_id,
                "previous_net_balance_cents": result.previous_net_balance_cents,
                "reversed_settlement_amount_cents": result.reversed_settlement_amount_cents,
                "new_net_balance_cents": result.new_net_balance_cents,
                "status": result.status,
                "overpayment_cents": result.overpayment_cents,
                "reversal_applied": result.reversal_applied,
            }
        ),
        200,
    )


@api_bp.post("/participants/<participant_id>/repayments/<repayment_id>/reverse")
def reverse_participant_repayment(participant_id: str, repayment_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)
    if not is_uuid(repayment_id):
        return _json_error("Invalid repayment_id.", status=400)

    data = request.get_json(silent=True) or {}

    try:
        reversal_note = parse_optional_string(data.get("note"), field_name="note", max_len=500)
        reversed_by = parse_optional_string(data.get("reversed_by"), field_name="reversed_by", max_len=255)
    except ApiValidationError as exc:
        return _json_error(str(exc), status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        result = repo.reverse_participant_repayment(
            participant_id=participant_id,
            repayment_id=repayment_id,
            reversed_by=reversed_by,
            reversal_note=reversal_note,
        )
    except RepositoryNotFoundError:
        return _json_error("Repayment not found.", status=404, code="not_found")
    except Exception:
        return _json_error("Failed to reverse repayment.", status=500, code="db_error")

    return (
        jsonify(
            {
                "transaction_type": "repayment_reversal",
                "repayment_id": result.repayment_id,
                "previous_net_balance_cents": result.previous_net_balance_cents,
                "reversed_repayment_amount_cents": result.reversed_repayment_amount_cents,
                "new_net_balance_cents": result.new_net_balance_cents,
                "status": result.status,
                "overpayment_cents": result.overpayment_cents,
                "reversal_applied": result.reversal_applied,
            }
        ),
        200,
    )


@api_bp.get("/participants/<participant_id>/ledger")
def get_participant_ledger(participant_id: str):
    if not is_uuid(participant_id):
        return _json_error("Invalid participant_id.", status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        participant = repo.get_participants_by_ids(participant_ids=[participant_id])
        if not participant:
            return _json_error("Participant not found.", status=404, code="not_found")

        ledger_lines = repo.get_participant_ledger_lines(participant_id=participant_id)
    except Exception:
        return _json_error("Failed to fetch participant ledger.", status=500, code="db_error")

    bill_groups: Dict[str, dict] = {}
    computed_total_cents = 0

    for line in ledger_lines:
        if line.receipt_image_id not in bill_groups:
            bill_groups[line.receipt_image_id] = {
                "receipt_image_id": line.receipt_image_id,
                "bill_description": line.bill_description,
                "lines": [],
            }

        bill_groups[line.receipt_image_id]["lines"].append(
            {
                "receipt_item_id": line.receipt_item_id,
                "item_description": line.item_description,
                "amount_cents": line.amount_cents,
            }
        )
        computed_total_cents += line.amount_cents

    return (
        jsonify(
            {
                "participant_id": participant_id,
                "computed_total_cents": computed_total_cents,
                "bills": list(bill_groups.values()),
            }
        ),
        200,
    )


@api_bp.post("/receipts/<receipt_image_id>/split")
def split_receipt(receipt_image_id: str):
    if not is_uuid(receipt_image_id):
        return _json_error("Invalid receipt_image_id.", status=400)

    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    assignments = data.get("assignments")
    if not isinstance(assignments, dict):
        return _json_error("'assignments' must be an object mapping receipt_item_id -> participant_ids.", status=400)

    try:
        participant_ids = parse_unique_participant_ids(data.get("participants"))
    except ApiValidationError as exc:
        return _json_error(str(exc), status=400)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        receipt_items = repo.get_receipt_items(receipt_image_id=receipt_image_id)
    except Exception:
        return _json_error("Failed to fetch receipt items.", status=500, code="db_error")

    items_by_id = {item.id: item for item in receipt_items}
    if not items_by_id:
        return _json_error("No persisted receipt items found for this receipt.", status=400)

    for assigned_item_id in assignments:
        if assigned_item_id not in items_by_id:
            return _json_error(f"Assignment references unknown item id for this receipt: {assigned_item_id}", status=400)

    for item_id in items_by_id:
        pids = assignments.get(item_id)
        if not isinstance(pids, list) or not pids:
            return _json_error(f"Assignment for item {item_id} must be a non-empty list.", status=400)

    try:
        db_participants = repo.get_participants_by_ids(participant_ids=participant_ids)
    except Exception:
        return _json_error("Failed to fetch participants.", status=500, code="db_error")

    db_participant_ids = {participant.id for participant in db_participants}
    if db_participant_ids != set(participant_ids):
        return _json_error("One or more participant ids do not exist.", status=400)

    totals_by_participant_id: Dict[str, int] = {pid: 0 for pid in participant_ids}
    participant_order = {pid: idx for idx, pid in enumerate(participant_ids)}
    allocations: list[ItemAllocation] = []
    grand_total_cents = 0

    for item in receipt_items:
        selected = assignments[item.id]
        seen_selected: set[str] = set()
        for selected_pid in selected:
            if not isinstance(selected_pid, str) or not is_uuid(selected_pid):
                return _json_error(f"Assignment for item {item.id} contains invalid participant id.", status=400)
            if selected_pid in seen_selected:
                return _json_error(f"Assignment for item {item.id} contains duplicate participant ids.", status=400)
            if selected_pid not in totals_by_participant_id:
                return _json_error(f"Assignment for item {item.id} references participant not in request 'participants'.", status=400)
            seen_selected.add(selected_pid)

        grand_total_cents += item.price_cents

        try:
            split_result = split_cents_fair_remainder(
                item.price_cents,
                selected,
                totals_by_participant_id,
                participant_order,
            )
        except SplitLogicError as exc:
            return _json_error(str(exc), status=422, code="split_failed")

        item_sum = sum(split_result.amounts_cents)
        if item_sum != item.price_cents:
            return _json_error(
                f"Split allocations for item {item.id} do not sum to item price.",
                status=422,
                code="split_sum_mismatch",
            )

        for selected_pid, amount_cents in zip(split_result.participants, split_result.amounts_cents, strict=True):
            totals_by_participant_id[selected_pid] += amount_cents
            allocations.append(
                ItemAllocation(
                    participant_id=selected_pid,
                    receipt_item_id=item.id,
                    amount_cents=amount_cents,
                )
            )

    if sum(totals_by_participant_id.values()) != grand_total_cents:
        return _json_error("Internal error: totals do not sum to grand total.", status=500, code="internal_mismatch")

    try:
        repo.replace_allocations_for_receipt(receipt_image_id=receipt_image_id, allocations=allocations)
    except Exception:
        return _json_error("Failed to persist allocations.", status=500, code="db_error")

    return (
        jsonify(
            {
                "receipt_image_id": receipt_image_id,
                "grand_total_cents": grand_total_cents,
                "totals_by_participant_id": totals_by_participant_id,
                "receipt_items": [
                    {
                        "id": item.id,
                        "description": item.description,
                    }
                    for item in receipt_items
                ],
                "allocations": [
                    {
                        "participant_id": allocation.participant_id,
                        "receipt_item_id": allocation.receipt_item_id,
                        "amount_cents": allocation.amount_cents,
                    }
                    for allocation in allocations
                ],
            }
        ),
        200,
    )
