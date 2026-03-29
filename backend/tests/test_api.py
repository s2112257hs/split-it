import io
from datetime import datetime, timezone

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


def test_list_bills_returns_preview_cards(client, monkeypatch):
    class BillPreview:
        def __init__(self, receipt_image_id, bill_description, entered_at, has_image):
            self.receipt_image_id = receipt_image_id
            self.bill_description = bill_description
            self.entered_at = entered_at
            self.has_image = has_image

    class FakeRepo:
        enabled = True

        def list_bill_previews(self):
            return [
                BillPreview(
                    "11111111-1111-1111-1111-111111111111",
                    "Uber from airport",
                    datetime(2026, 3, 2, 9, 15, tzinfo=timezone.utc),
                    True,
                ),
                BillPreview(
                    "22222222-2222-2222-2222-222222222222",
                    "Grocery run",
                    datetime(2026, 3, 1, 19, 0, tzinfo=timezone.utc),
                    False,
                ),
            ]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/bills")
    assert r.status_code == 200
    assert r.get_json() == {
        "bills": [
            {
                "receipt_image_id": "11111111-1111-1111-1111-111111111111",
                "bill_description": "Uber from airport",
                "entered_at": "2026-03-02T09:15:00+00:00",
                "has_image": True,
                "preview_image_url": "/api/receipts/11111111-1111-1111-1111-111111111111/image",
            },
            {
                "receipt_image_id": "22222222-2222-2222-2222-222222222222",
                "bill_description": "Grocery run",
                "entered_at": "2026-03-01T19:00:00+00:00",
                "has_image": False,
                "preview_image_url": "/api/receipts/22222222-2222-2222-2222-222222222222/image",
            },
        ]
    }


def test_get_receipt_image_streams_blob(client, monkeypatch):
    class Image:
        image_blob = b"\x89PNG\r\n\x1a\nfakepng"
        image_path = None

    class FakeRepo:
        enabled = True

        def get_receipt_image(self, *, receipt_image_id):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            return Image()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/receipts/11111111-1111-1111-1111-111111111111/image")
    assert r.status_code == 200
    assert r.mimetype == "image/png"
    assert r.data.startswith(b"\x89PNG\r\n\x1a\n")


def test_get_receipt_image_not_found(client, monkeypatch):
    class FakeRepo:
        enabled = True

        def get_receipt_image(self, *, receipt_image_id):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            return None

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/receipts/11111111-1111-1111-1111-111111111111/image")
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"


def test_get_bill_split_details(client, monkeypatch):
    class Line:
        def __init__(self, receipt_item_id, item_description, amount_cents):
            self.receipt_item_id = receipt_item_id
            self.item_description = item_description
            self.amount_cents = amount_cents

    class Participant:
        def __init__(self, participant_id, participant_name, participant_total_cents, lines):
            self.participant_id = participant_id
            self.participant_name = participant_name
            self.participant_total_cents = participant_total_cents
            self.lines = lines

    class Details:
        receipt_image_id = "11111111-1111-1111-1111-111111111111"
        bill_description = "Lidl Wembley"
        entered_at = datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)
        bill_total_cents = 247
        has_image = True
        participants = [
            Participant(
                "p1",
                "Ifham",
                180,
                [
                    Line("i1", "Milk", 30),
                    Line("i2", "Eggs", 150),
                ],
            ),
            Participant(
                "p2",
                "Alice",
                67,
                [
                    Line("i3", "Croissant", 67),
                ],
            ),
        ]

    class FakeRepo:
        enabled = True

        def get_bill_split_detail(self, *, receipt_image_id):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            return Details()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/bills/11111111-1111-1111-1111-111111111111/details")
    assert r.status_code == 200
    assert r.get_json() == {
        "receipt_image_id": "11111111-1111-1111-1111-111111111111",
        "bill_description": "Lidl Wembley",
        "entered_at": "2026-03-03T12:00:00+00:00",
        "bill_total_cents": 247,
        "has_image": True,
        "show_bill_image_url": "/api/receipts/11111111-1111-1111-1111-111111111111/image",
        "participants": [
            {
                "participant_id": "p1",
                "participant_name": "Ifham",
                "participant_total_cents": 180,
                "lines": [
                    {
                        "receipt_item_id": "i1",
                        "item_description": "Milk",
                        "amount_cents": 30,
                    },
                    {
                        "receipt_item_id": "i2",
                        "item_description": "Eggs",
                        "amount_cents": 150,
                    },
                ],
            },
            {
                "participant_id": "p2",
                "participant_name": "Alice",
                "participant_total_cents": 67,
                "lines": [
                    {
                        "receipt_item_id": "i3",
                        "item_description": "Croissant",
                        "amount_cents": 67,
                    },
                ],
            },
        ],
    }


def test_get_bill_split_details_not_found(client, monkeypatch):
    class FakeRepo:
        enabled = True

        def get_bill_split_detail(self, *, receipt_image_id):
            assert receipt_image_id == "11111111-1111-1111-1111-111111111111"
            return None

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/bills/11111111-1111-1111-1111-111111111111/details")
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"


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




def test_get_running_balances_groups_bills_and_totals(client, monkeypatch):
    class ParticipantRow:
        def __init__(self, participant_id, participant_name, lines, settlement_events, repayment_events):
            self.participant_id = participant_id
            self.participant_name = participant_name
            self.lines = lines
            self.settlement_events = settlement_events
            self.repayment_events = repayment_events

    class Line:
        def __init__(self, receipt_id, bill_description, receipt_item_id, item_name, contribution_cents):
            self.receipt_id = receipt_id
            self.bill_description = bill_description
            self.receipt_item_id = receipt_item_id
            self.item_name = item_name
            self.contribution_cents = contribution_cents

    class Event:
        def __init__(self, event_id, event_at, amount_cents, reference_details):
            self.event_id = event_id
            self.event_at = event_at
            self.amount_cents = amount_cents
            self.reference_details = reference_details

    class FakeRepo:
        enabled = True

        def list_running_balance_participants(self):
            return [
                ParticipantRow(
                    "p-alice",
                    "Alice",
                    [
                        Line("r2", "Dinner", "i2", "Steak", 1500),
                        Line("r2", "Dinner", "i3", "Soda", 300),
                        Line("r1", "Lunch", "i1", "Soup", 700),
                    ],
                    [
                        Event(
                            "settlement:s-1",
                            datetime(2026, 1, 2, 11, 30, tzinfo=timezone.utc),
                            200,
                            "Bank transfer",
                        )
                    ],
                    [],
                ),
                ParticipantRow("p-bob", "Bob", [], [], []),
            ]

        def list_participant_folios(self):
            class Summary:
                def __init__(
                    self,
                    participant_id,
                    total_charged_cents,
                    total_settled_cents,
                    total_repaid_cents,
                    net_balance_cents,
                    status,
                ):
                    self.participant_id = participant_id
                    self.total_charged_cents = total_charged_cents
                    self.total_settled_cents = total_settled_cents
                    self.total_repaid_cents = total_repaid_cents
                    self.net_balance_cents = net_balance_cents
                    self.status = status

            return [
                Summary("p-alice", 2500, 200, 0, 2300, "owes_you"),
                Summary("p-bob", 0, 0, 0, 0, "settled"),
            ]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/running-balances")

    assert r.status_code == 200
    assert r.get_json() == {
        "participants": [
            {
                "participant_id": "p-alice",
                "participant_name": "Alice",
                "participant_total_cents": 2300,
                "total_charged_cents": 2500,
                "total_settled_cents": 200,
                "total_repaid_cents": 0,
                "net_balance_cents": 2300,
                "status": "owes_you",
                "bills": [
                    {
                        "receipt_id": "r2",
                        "bill_description": "Dinner",
                        "bill_total_cents": 1800,
                        "lines": [
                            {"receipt_item_id": "i2", "item_name": "Steak", "contribution_cents": 1500},
                            {"receipt_item_id": "i3", "item_name": "Soda", "contribution_cents": 300},
                        ],
                    },
                    {
                        "receipt_id": "r1",
                        "bill_description": "Lunch",
                        "bill_total_cents": 700,
                        "lines": [
                            {"receipt_item_id": "i1", "item_name": "Soup", "contribution_cents": 700},
                        ],
                    },
                ],
                "settlement_events": [
                    {
                        "event_id": "settlement:s-1",
                        "event_at": "2026-01-02T11:30:00+00:00",
                        "amount_cents": 200,
                        "reference_details": "Bank transfer",
                    }
                ],
                "repayment_events": [],
            },
            {
                "participant_id": "p-bob",
                "participant_name": "Bob",
                "participant_total_cents": 0,
                "total_charged_cents": 0,
                "total_settled_cents": 0,
                "total_repaid_cents": 0,
                "net_balance_cents": 0,
                "status": "settled",
                "bills": [],
                "settlement_events": [],
                "repayment_events": [],
            },
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
    assert body["receipt_items"] == [
        {"id": "aaaaaaa1-1111-1111-1111-111111111111", "description": "Coffee"},
        {"id": "aaaaaaa2-1111-1111-1111-111111111111", "description": "Sandwich"},
    ]
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


def test_get_participant_ledger_groups_lines_and_computes_total(client, monkeypatch):
    class Participant:
        id = "22222222-2222-2222-2222-222222222222"

    class LedgerLine:
        def __init__(self, receipt_image_id, bill_description, receipt_item_id, item_description, amount_cents):
            self.receipt_image_id = receipt_image_id
            self.bill_description = bill_description
            self.receipt_item_id = receipt_item_id
            self.item_description = item_description
            self.amount_cents = amount_cents

    class FakeRepo:
        enabled = True

        def get_participants_by_ids(self, *, participant_ids):
            assert participant_ids == ["22222222-2222-2222-2222-222222222222"]
            return [Participant()]

        def get_participant_ledger_lines(self, *, participant_id):
            assert participant_id == "22222222-2222-2222-2222-222222222222"
            return [
                LedgerLine("r2", "Dinner", "i2", "Steak", 1500),
                LedgerLine("r2", "Dinner", "i3", "Soda", 300),
                LedgerLine("r1", "Lunch", "i1", "Soup", 700),
            ]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/participants/22222222-2222-2222-2222-222222222222/ledger")
    assert r.status_code == 200
    assert r.get_json() == {
        "participant_id": "22222222-2222-2222-2222-222222222222",
        "computed_total_cents": 2500,
        "bills": [
            {
                "receipt_image_id": "r2",
                "bill_description": "Dinner",
                "lines": [
                    {"receipt_item_id": "i2", "item_description": "Steak", "amount_cents": 1500},
                    {"receipt_item_id": "i3", "item_description": "Soda", "amount_cents": 300},
                ],
            },
            {
                "receipt_image_id": "r1",
                "bill_description": "Lunch",
                "lines": [{"receipt_item_id": "i1", "item_description": "Soup", "amount_cents": 700}],
            },
        ],
    }


def test_list_participant_folios(client, monkeypatch):
    class Summary:
        def __init__(self, participant_id, display_name, charged, settled, repaid, net, status, overpayment):
            self.participant_id = participant_id
            self.display_name = display_name
            self.total_charged_cents = charged
            self.total_settled_cents = settled
            self.total_repaid_cents = repaid
            self.net_balance_cents = net
            self.status = status
            self.overpayment_cents = overpayment

    class FakeRepo:
        enabled = True

        def list_participant_folios(self):
            return [
                Summary("p1", "Alice", 1000, 400, 0, 600, "owes_you", 0),
                Summary("p2", "Bob", 1000, 1300, 200, -100, "you_owe_them", 100),
            ]

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/participants/folios")
    assert r.status_code == 200
    assert r.get_json() == {
        "folios": [
            {
                "participant_id": "p1",
                "display_name": "Alice",
                "total_charged_cents": 1000,
                "total_settled_cents": 400,
                "total_repaid_cents": 0,
                "net_balance_cents": 600,
                "status": "owes_you",
                "overpayment_cents": 0,
            },
            {
                "participant_id": "p2",
                "display_name": "Bob",
                "total_charged_cents": 1000,
                "total_settled_cents": 1300,
                "total_repaid_cents": 200,
                "net_balance_cents": -100,
                "status": "you_owe_them",
                "overpayment_cents": 100,
            },
        ]
    }


def test_get_participant_folio_returns_event_history(client, monkeypatch):
    class Summary:
        participant_id = "22222222-2222-2222-2222-222222222222"
        display_name = "Alice"
        total_charged_cents = 1000
        total_settled_cents = 400
        total_repaid_cents = 0
        net_balance_cents = 600
        status = "owes_you"
        overpayment_cents = 0

    class Event:
        def __init__(self, event_id, event_at, event_type, amount_cents, prev_net, new_net, ref):
            self.event_id = event_id
            self.event_at = event_at
            self.event_type = event_type
            self.amount_cents = amount_cents
            self.previous_net_balance_cents = prev_net
            self.new_net_balance_cents = new_net
            self.reference_details = ref
            self.receipt_image_id = "r1" if event_type == "charge" else None
            self.receipt_item_id = "i1" if event_type == "charge" else None

    class Folio:
        summary = Summary()
        charge_events = [
            Event(
                "evt-charge-1",
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                "charge",
                1000,
                0,
                1000,
                "Dinner | Pasta",
            )
        ]
        settlement_events = [
            Event(
                "evt-settle-1",
                datetime(2026, 1, 2, 11, 30, tzinfo=timezone.utc),
                "settlement",
                400,
                1000,
                600,
                "Bank transfer",
            )
        ]
        repayment_events = []

    class FakeRepo:
        enabled = True

        def get_participant_folio(self, *, participant_id, max_events):
            assert participant_id == "22222222-2222-2222-2222-222222222222"
            assert max_events == 100
            return Folio()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.get("/api/participants/22222222-2222-2222-2222-222222222222/folio")
    assert r.status_code == 200
    assert r.get_json() == {
        "participant_id": "22222222-2222-2222-2222-222222222222",
        "display_name": "Alice",
        "total_charged_cents": 1000,
        "total_settled_cents": 400,
        "total_repaid_cents": 0,
        "net_balance_cents": 600,
        "status": "owes_you",
        "overpayment_cents": 0,
        "charge_events": [
            {
                "event_id": "evt-charge-1",
                "event_at": "2026-01-01T10:00:00+00:00",
                "type": "charge",
                "amount_cents": 1000,
                "previous_net_balance_cents": 0,
                "new_net_balance_cents": 1000,
                "previous_owed_cents": 0,
                "new_owed_cents": 1000,
                "reference_details": "Dinner | Pasta",
                "receipt_image_id": "r1",
                "receipt_item_id": "i1",
            }
        ],
        "settlement_events": [
            {
                "event_id": "evt-settle-1",
                "event_at": "2026-01-02T11:30:00+00:00",
                "type": "settlement",
                "amount_cents": 400,
                "previous_net_balance_cents": 1000,
                "new_net_balance_cents": 600,
                "previous_owed_cents": 1000,
                "new_owed_cents": 600,
                "reference_details": "Bank transfer",
                "receipt_image_id": None,
                "receipt_item_id": None,
            }
        ],
        "repayment_events": [],
    }


def test_create_settlement_exact_paydown(client, monkeypatch):
    class Result:
        settlement_id = "s1"
        previous_net_balance_cents = 1000
        settlement_amount_cents = 1000
        new_net_balance_cents = 0
        status = "settled"
        overpayment_cents = 0
        idempotency_replayed = False

    class FakeRepo:
        enabled = True

        def create_participant_settlement(self, **kwargs):
            assert kwargs["amount_cents"] == 1000
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/settlements",
        json={"amount_cents": 1000, "note": "Exact paydown"},
    )
    assert r.status_code == 200
    assert r.get_json()["new_net_balance_cents"] == 0
    assert r.get_json()["status"] == "settled"
    assert r.get_json()["overpayment_happened"] is False


def test_create_settlement_partial_paydown(client, monkeypatch):
    class Result:
        settlement_id = "s2"
        previous_net_balance_cents = 1000
        settlement_amount_cents = 400
        new_net_balance_cents = 600
        status = "owes_you"
        overpayment_cents = 0
        idempotency_replayed = False

    class FakeRepo:
        enabled = True

        def create_participant_settlement(self, **kwargs):
            assert kwargs["amount_cents"] == 400
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/settlements",
        json={"amount_cents": 400},
    )
    assert r.status_code == 200
    assert r.get_json()["previous_net_balance_cents"] == 1000
    assert r.get_json()["new_net_balance_cents"] == 600
    assert r.get_json()["status"] == "owes_you"


def test_create_settlement_overpayment(client, monkeypatch):
    class Result:
        settlement_id = "s3"
        previous_net_balance_cents = 1000
        settlement_amount_cents = 1300
        new_net_balance_cents = -300
        status = "you_owe_them"
        overpayment_cents = 300
        idempotency_replayed = False

    class FakeRepo:
        enabled = True

        def create_participant_settlement(self, **kwargs):
            assert kwargs["amount_cents"] == 1300
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/settlements",
        json={"amount_cents": 1300},
    )
    assert r.status_code == 200
    assert r.get_json()["new_net_balance_cents"] == -300
    assert r.get_json()["status"] == "you_owe_them"
    assert r.get_json()["overpayment_cents"] == 300
    assert r.get_json()["overpayment_happened"] is True


def test_create_settlement_duplicate_idempotency_key_is_replayed(client, monkeypatch):
    class Result:
        settlement_id = "s4"
        previous_net_balance_cents = 1000
        settlement_amount_cents = 400
        new_net_balance_cents = 600
        status = "owes_you"
        overpayment_cents = 0
        idempotency_replayed = True

    class FakeRepo:
        enabled = True

        def create_participant_settlement(self, **kwargs):
            assert kwargs["idempotency_key"] == "idem-abc"
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/settlements",
        json={"amount_cents": 400, "idempotency_key": "idem-abc"},
    )
    assert r.status_code == 200
    assert r.get_json()["idempotency_replayed"] is True
    assert r.get_json()["settlement_amount_cents"] == 400


def test_reverse_settlement_behavior(client, monkeypatch):
    class Result:
        settlement_id = "44444444-4444-4444-4444-444444444444"
        previous_net_balance_cents = -300
        reversed_settlement_amount_cents = 1300
        new_net_balance_cents = 1000
        status = "owes_you"
        overpayment_cents = 0
        reversal_applied = True

    class FakeRepo:
        enabled = True

        def reverse_participant_settlement(self, **kwargs):
            assert kwargs["participant_id"] == "22222222-2222-2222-2222-222222222222"
            assert kwargs["settlement_id"] == "44444444-4444-4444-4444-444444444444"
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/settlements/44444444-4444-4444-4444-444444444444/reverse",
        json={"note": "Correction"},
    )
    assert r.status_code == 200
    assert r.get_json() == {
        "transaction_type": "settlement_reversal",
        "settlement_id": "44444444-4444-4444-4444-444444444444",
        "previous_net_balance_cents": -300,
        "reversed_settlement_amount_cents": 1300,
        "new_net_balance_cents": 1000,
        "status": "owes_you",
        "overpayment_cents": 0,
        "reversal_applied": True,
    }


def test_create_settlement_invalid_payload_returns_400(client):
    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/settlements",
        json={"amount_cents": 0, "paid_at": "not-a-time"},
    )
    assert r.status_code == 400
    assert "amount_cents" in r.get_json()["error"]["message"]


def test_create_repayment(client, monkeypatch):
    class Result:
        repayment_id = "repay-1"
        previous_net_balance_cents = -300
        repayment_amount_cents = 300
        new_net_balance_cents = 0
        status = "settled"
        overpayment_cents = 0
        idempotency_replayed = False

    class FakeRepo:
        enabled = True

        def create_participant_repayment(self, **kwargs):
            assert kwargs["amount_cents"] == 300
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/repayments",
        json={"amount_cents": 300, "note": "Returned overpay"},
    )
    assert r.status_code == 200
    assert r.get_json() == {
        "transaction_type": "repayment",
        "repayment_id": "repay-1",
        "previous_net_balance_cents": -300,
        "repayment_amount_cents": 300,
        "new_net_balance_cents": 0,
        "status": "settled",
        "overpayment_cents": 0,
        "idempotency_replayed": False,
    }


def test_reverse_repayment(client, monkeypatch):
    class Result:
        repayment_id = "repay-1"
        previous_net_balance_cents = 0
        reversed_repayment_amount_cents = 300
        new_net_balance_cents = -300
        status = "you_owe_them"
        overpayment_cents = 300
        reversal_applied = True

    class FakeRepo:
        enabled = True

        def reverse_participant_repayment(self, **kwargs):
            assert kwargs["participant_id"] == "22222222-2222-2222-2222-222222222222"
            assert kwargs["repayment_id"] == "55555555-5555-5555-5555-555555555555"
            return Result()

    monkeypatch.setattr("app.api.routes._repo", lambda: FakeRepo())

    r = client.post(
        "/api/participants/22222222-2222-2222-2222-222222222222/repayments/55555555-5555-5555-5555-555555555555/reverse",
        json={"note": "Undo"},
    )
    assert r.status_code == 200
    assert r.get_json() == {
        "transaction_type": "repayment_reversal",
        "repayment_id": "repay-1",
        "previous_net_balance_cents": 0,
        "reversed_repayment_amount_cents": 300,
        "new_net_balance_cents": -300,
        "status": "you_owe_them",
        "overpayment_cents": 300,
        "reversal_applied": True,
    }
