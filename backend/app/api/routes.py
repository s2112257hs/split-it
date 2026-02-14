from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from app.domain.split_logic import SplitLogicError, split_cents_penny_perfect
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


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@api_bp.post("/ocr")
def ocr_endpoint():
    """
    multipart/form-data:
      - image: file (png/jpg)
    Response:
      - items: [{id, description, price_cents}]
    """
    if "image" not in request.files:
        return _json_error("Missing file field 'image'.", status=400)

    f = request.files["image"]
    if not f or not getattr(f, "filename", ""):
        return _json_error("No file provided in 'image'.", status=400)

    # Read bytes
    image_bytes = f.read()
    if not image_bytes:
        return _json_error("Uploaded file is empty.", status=400)

    try:
        ocr_text = ocr_service.run_ocr(image_bytes)
    except Exception:
        # Avoid leaking internals; log in real app
        return _json_error("OCR failed.", status=500, code="ocr_failed")

    try:
        parsed = extract_items_from_ocr_text(ocr_text)
    except ReceiptParseError:
        return _json_error("Failed to parse receipt text.", status=422, code="parse_failed")

    # Add simple deterministic ids: i0, i1, ...
    items = [
        {"id": f"i{idx}", "description": it.description, "price_cents": it.price_cents}
        for idx, it in enumerate(parsed)
    ]
    return jsonify({"items": items, "currency": "USD"}), 200


@api_bp.post("/calculate")
def calculate_endpoint():
    """
    JSON body:
      {
        "participants": [{"id": "p1", "name": "Ali"}, ...],
        "items": [{"id": "i1", "description":"Coke", "price_cents": 350}, ...],
        "assignments": {"i1": ["p1","p2"], ...}
      }

    Response:
      {
        "totals_by_participant_id": {"p1": 175, "p2": 175},
        "grand_total_cents": 350
      }
    """
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

    # Collect valid participant IDs
    participant_ids: List[str] = []
    for p in participants:
        if not isinstance(p, dict) or "id" not in p:
            return _json_error("Each participant must be an object with an 'id'.", status=400)
        pid = p["id"]
        if not isinstance(pid, str) or not pid.strip():
            return _json_error("Participant 'id' must be a non-empty string.", status=400)
        participant_ids.append(pid)

    # Map items by id
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
        items_by_id[iid] = it

    totals: Dict[str, int] = {pid: 0 for pid in participant_ids}
    grand_total = 0

    # For each assigned item: split among listed participants
    for item_id, pids in assignments.items():
        if item_id not in items_by_id:
            return _json_error(f"Assignment references unknown item id: {item_id}", status=400)
        if not isinstance(pids, list) or not pids:
            return _json_error(f"Assignment for item {item_id} must be a non-empty list of participant ids.", status=400)

        # Validate assigned pids exist
        for pid in pids:
            if pid not in totals:
                return _json_error(f"Assignment references unknown participant id: {pid}", status=400)

        item_total = items_by_id[item_id]["price_cents"]
        grand_total += item_total

        try:
            alloc = split_cents_penny_perfect(item_total, pids)
        except SplitLogicError as e:
            return _json_error(str(e), status=422, code="split_failed")

        for pid, cents in zip(alloc.participants, alloc.amounts_cents, strict=True):
            totals[pid] += cents

    # Sanity: totals sum must match grand_total exactly
    if sum(totals.values()) != grand_total:
        return _json_error("Internal error: totals do not sum to grand total.", status=500, code="internal_mismatch")

    return jsonify(
        {
            "totals_by_participant_id": totals,
            "grand_total_cents": grand_total,
        }
    ), 200
