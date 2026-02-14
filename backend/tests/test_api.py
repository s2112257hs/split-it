import io

import pytest
from flask import Flask

from app.api.routes import api_bp


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_ocr_missing_file(client):
    r = client.post("/api/ocr", data={})
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "bad_request"


def test_ocr_empty_file(client, monkeypatch):
    # Patch OCR so it would work if bytes existed
    monkeypatch.setattr("app.services.ocr_service.run_ocr", lambda b: "Coke 3.50")

    data = {
        "image": (io.BytesIO(b""), "receipt.png"),
    }
    r = client.post("/api/ocr", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "empty" in r.get_json()["error"]["message"].lower()


def test_ocr_happy_path_parses_items(client, monkeypatch):
    # Make OCR deterministic
    monkeypatch.setattr(
        "app.services.ocr_service.run_ocr",
        lambda b: "Chicken Burger 12.99\nCoke 3.50\nTOTAL 16.49\n",
    )

    data = {"image": (io.BytesIO(b"fake-image-bytes"), "receipt.png")}
    r = client.post("/api/ocr", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["currency"] == "USD"
    assert body["items"] == [
        {"id": "i0", "description": "Chicken Burger", "price_cents": 1299},
        {"id": "i1", "description": "Coke", "price_cents": 350},
    ]


def test_calculate_happy_path_penny_perfect(client):
    payload = {
        "participants": [{"id": "p1", "name": "Ali"}, {"id": "p2", "name": "Sara"}],
        "items": [
            {"id": "i1", "description": "Coke", "price_cents": 350},
            {"id": "i2", "description": "Burger", "price_cents": 101},
        ],
        "assignments": {
            "i1": ["p1", "p2"],  # 350 -> 175/175
            "i2": ["p1", "p2"],  # 101 -> 51/50 (p1 gets extra cent because first)
        },
    }

    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["grand_total_cents"] == 451
    assert body["totals_by_participant_id"] == {"p1": 226, "p2": 225}
    assert sum(body["totals_by_participant_id"].values()) == body["grand_total_cents"]


def test_calculate_rejects_unknown_participant_in_assignment(client):
    payload = {
        "participants": [{"id": "p1", "name": "Ali"}],
        "items": [{"id": "i1", "description": "Coke", "price_cents": 350}],
        "assignments": {"i1": ["p2"]},  # p2 not defined
    }
    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 400
    assert "unknown participant" in r.get_json()["error"]["message"].lower()


def test_calculate_rejects_unknown_item_in_assignment(client):
    payload = {
        "participants": [{"id": "p1", "name": "Ali"}],
        "items": [{"id": "i1", "description": "Coke", "price_cents": 350}],
        "assignments": {"i2": ["p1"]},  # i2 not defined
    }
    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 400
    assert "unknown item" in r.get_json()["error"]["message"].lower()


def test_calculate_rejects_non_json(client):
    r = client.post("/api/calculate", data="not-json", content_type="text/plain")
    assert r.status_code == 400
    assert "must be json" in r.get_json()["error"]["message"].lower()
