from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request

from app.db.repository import ItemAllocation, ParsedItem, SplitItRepository
from app.domain.split_logic import SplitLogicError, split_cents_fair_remainder
from app.services.receipt_parser import (
    ReceiptParseError,
    extract_items_from_ocr_text,
)

# OCR service should provide: run_ocr(image_bytes: bytes) -> str
# In tests we monkeypatch this so it doesn't require OCR deps.
from app.services import ocr_service

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _json_error(message: str, *, status: int = 400, code: str = "bad_request"):
    return jsonify({"error": {"code": code, "message": message}}), status


def _repo() -> SplitItRepository:
    return SplitItRepository(current_app.config.get("DATABASE_URL", ""))


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@api_bp.post("/ocr")
def ocr_endpoint():
    """
    multipart/form-data:
      - image: file (png/jpg)
      - description: string
    Response:
      - items: [{id, description, price_cents}]
      - receipt_image_id: uuid | null
    """
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

    try:
        ocr_text = ocr_service.run_ocr(image_bytes)
    except Exception:
        return _json_error("OCR failed.", status=500, code="ocr_failed")

    try:
        parsed = extract_items_from_ocr_text(ocr_text)
    except ReceiptParseError:
        return _json_error("Failed to parse receipt text.", status=422, code="parse_failed")

    receipt_image_id = None
    item_ids = [f"i{idx}" for idx in range(len(parsed))]

    repo = _repo()
    if repo.enabled:
        try:
            receipt_image_id, item_ids = repo.create_receipt_with_items(
                owner_id=current_app.config.get("RECEIPT_OWNER_ID", "mvp-owner"),
                description=description,
                image_bytes=image_bytes,
                items=[ParsedItem(description=it.description, price_cents=it.price_cents) for it in parsed],
            )
        except Exception:
            return _json_error("Failed to persist receipt to database.", status=500, code="db_error")

    items = [
        {"id": item_ids[idx], "description": it.description, "price_cents": it.price_cents}
        for idx, it in enumerate(parsed)
    ]
    return jsonify({"items": items, "currency": "USD", "receipt_image_id": receipt_image_id}), 200




@api_bp.post("/participants")
def participants_endpoint():
    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    participants = data.get("participants")
    if not isinstance(participants, list) or not participants:
        return _json_error("'participants' must be a non-empty list.", status=400)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_name in participants:
        if not isinstance(raw_name, str):
            return _json_error("Each participant must be a string name.", status=400)

        name = raw_name.strip()
        if not name:
            return _json_error("Participant names must be non-empty.", status=400)

        key = name.casefold()
        if key in seen:
            return _json_error("Participant names must be unique.", status=400)

        seen.add(key)
        normalized.append(name)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        created = repo.create_participants(participant_names=normalized)
    except Exception:
        return _json_error("Failed to persist participants.", status=500, code="db_error")

    return jsonify({"participants": [{"id": row.id, "name": row.name} for row in created]}), 200


@api_bp.post("/calculate")
def calculate_endpoint():
    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    try:
        participants = data["participants"]
        items = data["items"]
        assignments = data["assignments"]
    except KeyError as e:
        return _json_error(f"Missing field: {e.args[0]}", status=400)

    if not isinstance(participants, list) or not participants:
        return _json_error("'participants' must be a non-empty list.", status=400)
    if not isinstance(items, list):
        return _json_error("'items' must be a list.", status=400)
    if not isinstance(assignments, dict):
        return _json_error("'assignments' must be an object mapping item_id -> participant_ids.", status=400)

    participant_ids: List[str] = []
    participant_names: Dict[str, str] = {}
    for p in participants:
        if not isinstance(p, dict) or "id" not in p:
            return _json_error("Each participant must be an object with an 'id'.", status=400)
        pid = p["id"]
        if not isinstance(pid, str) or not pid.strip():
            return _json_error("Participant 'id' must be a non-empty string.", status=400)
        display_name = p.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            return _json_error("Participant 'name' must be a non-empty string.", status=400)

        if pid in participant_names:
            return _json_error("Participant ids must be unique.", status=400)

        participant_ids.append(pid)
        participant_names[pid] = display_name.strip()

    items_by_id: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            return _json_error("Each item must be an object.", status=400)
        if "id" not in it or "price_cents" not in it:
            return _json_error("Each item must include 'id' and 'price_cents'.", status=400)
        iid = it["id"]
        pc = it["price_cents"]
        if not isinstance(iid, str) or not iid.strip():
            return _json_error("Item 'id' must be a non-empty string.", status=400)
        if not isinstance(pc, int) or pc < 0:
            return _json_error("Item 'price_cents' must be an int >= 0.", status=400)
        if iid in items_by_id:
            return _json_error("Item ids must be unique.", status=400)
        items_by_id[iid] = it

    totals: Dict[str, int] = {pid: 0 for pid in participant_ids}
    grand_total = 0

    participant_order = {pid: idx for idx, pid in enumerate(participant_ids)}

    for item_id in assignments:
        if item_id not in items_by_id:
            return _json_error(f"Assignment references unknown item id: {item_id}", status=400)

    persistable_allocation_rows: list[ItemAllocation] = []

    for item in items:
        item_id = item["id"]
        pids = assignments.get(item_id)
        if pids is None:
            continue
        if not isinstance(pids, list) or not pids:
            return _json_error(f"Assignment for item {item_id} must be a non-empty list of participant ids.", status=400)

        seen_pids: set[str] = set()
        for pid in pids:
            if not isinstance(pid, str) or not pid.strip():
                return _json_error(f"Assignment for item {item_id} must only include non-empty participant ids.", status=400)
            if pid in seen_pids:
                return _json_error(f"Assignment for item {item_id} contains duplicate participant ids.", status=400)
            if pid not in totals:
                return _json_error(f"Assignment references unknown participant id: {pid}", status=400)
            seen_pids.add(pid)

        item_total = items_by_id[item_id]["price_cents"]
        grand_total += item_total

        try:
            alloc = split_cents_fair_remainder(item_total, pids, totals, participant_order)
        except SplitLogicError as e:
            return _json_error(str(e), status=422, code="split_failed")

        for pid, cents in zip(alloc.participants, alloc.amounts_cents, strict=True):
            totals[pid] += cents
            row = ItemAllocation(
                participant_name=participant_names[pid],
                receipt_item_id=item_id,
                amount_cents=cents,
            )
            if _is_uuid(item_id):
                persistable_allocation_rows.append(row)

    if sum(totals.values()) != grand_total:
        return _json_error("Internal error: totals do not sum to grand total.", status=500, code="internal_mismatch")

    repo = _repo()
    if repo.enabled and persistable_allocation_rows:
        try:
            persisted_names = {row.participant_name for row in persistable_allocation_rows}
            repo.add_allocations(participant_names=persisted_names, allocations=persistable_allocation_rows)
        except Exception:
            return _json_error("Failed to persist allocations.", status=500, code="db_error")

    return jsonify(
        {
            "totals_by_participant_id": totals,
            "grand_total_cents": grand_total,
        }
    ), 200


@api_bp.post("/summary")
def summary_endpoint():
    data = request.get_json(silent=True)
    if data is None:
        return _json_error("Request body must be JSON.", status=400)

    receipt_image_id = data.get("receipt_image_id")
    participant_ids = data.get("participant_ids")

    if not isinstance(receipt_image_id, str) or not receipt_image_id.strip() or not _is_uuid(receipt_image_id):
        return _json_error("'receipt_image_id' must be a valid UUID string.", status=400)

    if not isinstance(participant_ids, list) or not participant_ids:
        return _json_error("'participant_ids' must be a non-empty list.", status=400)

    clean_participant_ids: list[str] = []
    seen: set[str] = set()
    for participant_id in participant_ids:
        if not isinstance(participant_id, str) or not participant_id.strip() or not _is_uuid(participant_id):
            return _json_error("'participant_ids' must contain valid UUID strings.", status=400)

        normalized = participant_id.strip()
        if normalized in seen:
            return _json_error("'participant_ids' must be unique.", status=400)

        seen.add(normalized)
        clean_participant_ids.append(normalized)

    repo = _repo()
    if not repo.enabled:
        return _json_error("DATABASE_URL is not configured.", status=503, code="db_unavailable")

    try:
        summary_rows = repo.get_summary(receipt_image_id=receipt_image_id, participant_ids=clean_participant_ids)
    except Exception:
        return _json_error("Failed to load summary.", status=500, code="db_error")

    totals_by_participant_id = {row.participant_id: row.total_cents for row in summary_rows}
    grand_total_cents = sum(totals_by_participant_id.values())

    return jsonify({
        "totals_by_participant_id": totals_by_participant_id,
        "grand_total_cents": grand_total_cents,
    }), 200
