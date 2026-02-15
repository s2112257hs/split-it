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


def test_ocr_missing_description(client):
    data = {"image": (io.BytesIO(b"fake-image-bytes"), "receipt.png")}
    r = client.post("/api/ocr", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "description" in r.get_json()["error"]["message"].lower()


def test_ocr_empty_file(client, monkeypatch):
    # Patch OCR so it would work if bytes existed
    monkeypatch.setattr("app.services.ocr_service.run_ocr", lambda b: "Coke 3.50")

    data = {
        "description": "Office lunch",
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

    data = {"description": "Dinner with team", "image": (io.BytesIO(b"fake-image-bytes"), "receipt.png")}
    r = client.post("/api/ocr", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["currency"] == "USD"
    assert body["receipt_image_id"] is None
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




def test_calculate_uses_fair_remainder_and_receipt_order(client):
    payload = {
        "participants": [
            {"id": "p1", "name": "Ali"},
            {"id": "p2", "name": "Sara"},
            {"id": "p3", "name": "Moe"},
        ],
        "items": [
            {"id": "i1", "description": "Steak", "price_cents": 5},
            {"id": "i2", "description": "Fries", "price_cents": 2},
        ],
        "assignments": {
            "i2": ["p1", "p2"],
            "i1": ["p1", "p2", "p3"],
        },
    }

    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 200
    body = r.get_json()

    # i1 first by receipt order: base=1, rem=2 => p1/p2 get extra (totals 2,2,1)
    # i2 next: base=1 each, rem=0 => (3,3,1)
    assert body["totals_by_participant_id"] == {"p1": 3, "p2": 3, "p3": 1}
    assert body["grand_total_cents"] == 7

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


def test_calculate_rejects_duplicate_participant_ids(client):
    payload = {
        "participants": [{"id": "p1", "name": "Ali"}, {"id": "p1", "name": "Alex"}],
        "items": [{"id": "i1", "description": "Coke", "price_cents": 350}],
        "assignments": {"i1": ["p1"]},
    }

    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 400
    assert "unique" in r.get_json()["error"]["message"].lower()


def test_calculate_rejects_duplicate_item_ids(client):
    payload = {
        "participants": [{"id": "p1", "name": "Ali"}],
        "items": [
            {"id": "i1", "description": "Coke", "price_cents": 350},
            {"id": "i1", "description": "Fries", "price_cents": 250},
        ],
        "assignments": {"i1": ["p1"]},
    }

    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 400
    assert "item ids must be unique" in r.get_json()["error"]["message"].lower()


def test_calculate_rejects_duplicate_assignment_participant_ids(client):
    payload = {
        "participants": [{"id": "p1", "name": "Ali"}],
        "items": [{"id": "i1", "description": "Coke", "price_cents": 350}],
        "assignments": {"i1": ["p1", "p1"]},
    }

    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 400
    assert "duplicate" in r.get_json()["error"]["message"].lower()


def test_calculate_skips_persisting_non_uuid_item_allocations(client, monkeypatch):
    captured = {}

    class FakeRepo:
        enabled = True

        def add_allocations(self, *, participant_names, allocations):
            captured["participant_names"] = set(participant_names)
            captured["allocations"] = list(allocations)

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    payload = {
        "participants": [{"id": "p1", "name": "Ali"}],
        "items": [{"id": "item_local", "description": "Added in UI", "price_cents": 350}],
        "assignments": {"item_local": ["p1"]},
    }

    r = client.post("/api/calculate", json=payload)
    assert r.status_code == 200
    assert r.get_json()["totals_by_participant_id"] == {"p1": 350}
    assert "allocations" not in captured


def test_participants_rejects_duplicate_names(client):
    payload = {"participants": ["Ali", "ali"]}
    r = client.post("/api/participants", json=payload)
    assert r.status_code == 400
    assert "unique" in r.get_json()["error"]["message"].lower()


def test_participants_requires_database(client):
    payload = {"participants": ["Ali", "Sara"]}
    r = client.post("/api/participants", json=payload)
    assert r.status_code == 503


def test_summary_returns_backend_totals(client, monkeypatch):
    class Row:
        def __init__(self, participant_id, total_cents):
            self.participant_id = participant_id
            self.total_cents = total_cents

    class FakeRepo:
        enabled = True

        def get_summary(self, *, receipt_image_id, participant_ids):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            assert participant_ids == [
                "22222222-2222-2222-2222-222222222222",
                "33333333-3333-3333-3333-333333333333",
            ]
            return [
                Row("22222222-2222-2222-2222-222222222222", 226),
                Row("33333333-3333-3333-3333-333333333333", 225),
            ]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    payload = {
        "receipt_image_id": "11111111-1111-1111-1111-111111111111",
        "participant_ids": [
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ],
    }

    r = client.post("/api/summary", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["totals_by_participant_id"] == {
        "22222222-2222-2222-2222-222222222222": 226,
        "33333333-3333-3333-3333-333333333333": 225,
    }
    assert body["grand_total_cents"] == 451


def test_participants_persists_and_returns_ids(client, monkeypatch):
    class Row:
        def __init__(self, participant_id, name):
            self.id = participant_id
            self.name = name

    class FakeRepo:
        enabled = True

        def create_participants(self, *, participant_names):
            assert participant_names == ["Ali", "Sara"]
            return [
                Row("22222222-2222-2222-2222-222222222222", "Ali"),
                Row("33333333-3333-3333-3333-333333333333", "Sara"),
            ]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post("/api/participants", json={"participants": ["Ali", "Sara"]})
    assert r.status_code == 200
    assert r.get_json()["participants"] == [
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Ali"},
        {"id": "33333333-3333-3333-3333-333333333333", "name": "Sara"},
    ]
