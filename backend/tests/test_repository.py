from app.repositories.repository import compute_folio_metrics, folio_status_from_net_balance


def test_compute_folio_metrics_partial_paydown():
    net_balance_cents, status, overpayment_cents = compute_folio_metrics(1000, 400, 0)
    assert net_balance_cents == 600
    assert status == "owes_you"
    assert overpayment_cents == 0


def test_compute_folio_metrics_exact_paydown():
    net_balance_cents, status, overpayment_cents = compute_folio_metrics(1000, 1000, 0)
    assert net_balance_cents == 0
    assert status == "settled"
    assert overpayment_cents == 0


def test_compute_folio_metrics_overpayment_negative_balance():
    net_balance_cents, status, overpayment_cents = compute_folio_metrics(1000, 1300, 0)
    assert net_balance_cents == -300
    assert status == "you_owe_them"
    assert overpayment_cents == 300


def test_compute_folio_metrics_after_repayment():
    net_balance_cents, status, overpayment_cents = compute_folio_metrics(1000, 1300, 200)
    assert net_balance_cents == -100
    assert status == "you_owe_them"
    assert overpayment_cents == 100


def test_folio_status_from_net_balance():
    assert folio_status_from_net_balance(1) == "owes_you"
    assert folio_status_from_net_balance(0) == "settled"
    assert folio_status_from_net_balance(-1) == "you_owe_them"
