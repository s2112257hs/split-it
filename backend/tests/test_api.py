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


def test_create_receipt_requires_db(client, monkeypatch):
    monkeypatch.setattr("app.services.ocr_service.run_ocr", lambda b: "Coffee 3.50")
    data = {"description": "Lunch", "image": (io.BytesIO(b"img"), "receipt.png")}

    r = client.post("/api/receipts", data=data, content_type="multipart/form-data")

    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "db_unavailable"


def test_create_receipt_returns_preview_items_and_persisted_image_id(client, monkeypatch):
    class FakeRepo:
        enabled = True

        def create_receipt_image(self, *, owner_id, description, image_bytes):
            assert owner_id == "mvp-owner"
            assert description == "Team dinner"
            assert image_bytes == b"fake-image"
            return "11111111-1111-1111-1111-111111111111"

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())
    monkeypatch.setattr("app.services.ocr_service.run_ocr", lambda b: "Coffee 3.50\nBurger 8.25")

    r = client.post(
        "/api/receipts",
        data={"description": "Team dinner", "image": (io.BytesIO(b"fake-image"), "receipt.png")},
        content_type="multipart/form-data",
    )

    assert r.status_code == 200
    assert r.get_json() == {
        "receipt_image_id": "11111111-1111-1111-1111-111111111111",
        "currency": "USD",
        "items": [
            {"temp_id": "t0", "description": "Coffee", "price_cents": 350},
            {"temp_id": "t1", "description": "Burger", "price_cents": 825},
        ],
    }


def test_replace_receipt_items_validates_payload(client):
    r = client.put("/api/receipts/11111111-1111-1111-1111-111111111111/items", json={"items": [{"description": "", "price_cents": 100}]})
    assert r.status_code == 400
    assert "description" in r.get_json()["error"]["message"].lower()


def test_replace_receipt_items_persists_and_returns_ids(client, monkeypatch):
    class Row:
        def __init__(self, item_id, description, price_cents):
            self.id = item_id
            self.description = description
            self.price_cents = price_cents

    class FakeRepo:
        enabled = True

        def replace_receipt_items(self, *, receipt_image_id, items):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            assert [(i.description, i.price_cents) for i in items] == [("Coffee", 350)]
            return [Row("22222222-2222-2222-2222-222222222222", "Coffee", 350)]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.put(
        "/api/receipts/11111111-1111-1111-1111-111111111111/items",
        json={"items": [{"id": None, "description": "Coffee", "price_cents": 350}]},
    )

    assert r.status_code == 200
    assert r.get_json() == {
        "receipt_image_id": "11111111-1111-1111-1111-111111111111",
        "items": [{"id": "22222222-2222-2222-2222-222222222222", "description": "Coffee", "price_cents": 350}],
    }


def test_list_participants(client, monkeypatch):
    class Row:
        def __init__(self, participant_id, display_name, running_total_cents):
            self.id = participant_id
            self.display_name = display_name
            self.running_total_cents = running_total_cents

    class FakeRepo:
        enabled = True

        def list_participants(self):
            return [Row("p1", "Alice", 1000), Row("p2", "Bob", 175)]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/participants")
    assert r.status_code == 200
    assert r.get_json() == {
        "participants": [
            {"id": "p1", "display_name": "Alice", "running_total_cents": 1000},
            {"id": "p2", "display_name": "Bob", "running_total_cents": 175},
        ]
    }


def test_create_participant_returns_existing_or_new(client, monkeypatch):
    class Row:
        id = "22222222-2222-2222-2222-222222222222"
        display_name = "Charlie"
        running_total_cents = 0

    class FakeRepo:
        enabled = True

        def create_or_get_participant(self, *, display_name):
            assert display_name == "Charlie"
            return Row()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post("/api/participants", json={"display_name": "Charlie"})
    assert r.status_code == 200
    assert r.get_json() == {
        "id": "22222222-2222-2222-2222-222222222222",
        "display_name": "Charlie",
        "running_total_cents": 0,
    }


def test_delete_participant_blocked_when_allocations_exist(client, monkeypatch):
    class FakeRepo:
        enabled = True

        def participant_has_allocations(self, *, participant_id):
            assert participant_id == "11111111-1111-1111-1111-111111111111"
            return True

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.delete("/api/participants/11111111-1111-1111-1111-111111111111")
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "participant_has_allocations"


def test_split_replaces_allocations_for_receipt(client, monkeypatch):
    class Item:
        def __init__(self, item_id, description, price_cents):
            self.id = item_id
            self.description = description
            self.price_cents = price_cents

    class Participant:
        def __init__(self, participant_id):
            self.id = participant_id

    captured = {}

    class FakeRepo:
        enabled = True

        def get_receipt_items(self, *, receipt_image_id):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            return [
                Item("aaaaaaa1-1111-1111-1111-111111111111", "Coffee", 350),
                Item("aaaaaaa2-1111-1111-1111-111111111111", "Sandwich", 825),
            ]

        def get_participants_by_ids(self, *, participant_ids):
            assert participant_ids == [
                "22222222-2222-2222-2222-222222222222",
                "33333333-3333-3333-3333-333333333333",
            ]
            return [Participant(pid) for pid in participant_ids]

        def replace_allocations_for_receipt(self, *, receipt_image_id, allocations):
            captured["receipt_image_id"] = receipt_image_id
            captured["allocations"] = list(allocations)

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    payload = {
        "participants": [
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ],
        "assignments": {
            "aaaaaaa1-1111-1111-1111-111111111111": [
                "22222222-2222-2222-2222-222222222222",
                "33333333-3333-3333-3333-333333333333",
            ],
            "aaaaaaa2-1111-1111-1111-111111111111": ["22222222-2222-2222-2222-222222222222"],
        },
    }

    r = client.post("/api/receipts/11111111-1111-1111-1111-111111111111/split", json=payload)

    assert r.status_code == 200
    body = r.get_json()
    assert body["grand_total_cents"] == 1175
    assert body["totals_by_participant_id"] == {
        "22222222-2222-2222-2222-222222222222": 1000,
        "33333333-3333-3333-3333-333333333333": 175,
    }
    assert captured["receipt_image_id"] == "11111111-1111-1111-1111-111111111111"
    assert len(captured["allocations"]) == 3


def test_split_rejects_assignment_for_foreign_item(client, monkeypatch):
    class Item:
        id = "aaaaaaa1-1111-1111-1111-111111111111"
        description = "Coffee"
        price_cents = 350

    class FakeRepo:
        enabled = True

        def get_receipt_items(self, *, receipt_image_id):
            return [Item()]

        def get_participants_by_ids(self, *, participant_ids):
            return []

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    payload = {
        "participants": ["22222222-2222-2222-2222-222222222222"],
        "assignments": {
            "aaaaaaa9-1111-1111-1111-111111111111": ["22222222-2222-2222-2222-222222222222"],
        },
    }

    r = client.post("/api/receipts/11111111-1111-1111-1111-111111111111/split", json=payload)
    assert r.status_code == 400
    assert "unknown item" in r.get_json()["error"]["message"].lower()
