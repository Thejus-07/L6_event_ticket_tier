import pytest
from event_ticket_tier import process_ticket_manifest, monitor_gate_flow


def build(tier, orders, confirmed=True, lounge=False):
    return {
        "is_confirmed": confirmed,
        "tier": tier,
        "exclusive_lounge": lounge,
        "orders": orders,
    }


def test_manifests_not_a_list():
    with pytest.raises(ValueError):
        process_ticket_manifest("abc", 0.1)


def test_negative_tax():
    with pytest.raises(ValueError):
        process_ticket_manifest([], -0.1)


def test_unconfirmed_manifest_skipped():
    r = process_ticket_manifest([build("vip", [{"qty": 2, "promo": ""}], confirmed=False)], 0.0)
    assert r == {"total_revenue": 0.0, "status": "ZERO_SALES"}


def test_vip_single_ticket():
    r = process_ticket_manifest([build("vip", [{"qty": 1, "promo": ""}])], 0.0)
    assert r == {"total_revenue": 150.0, "status": "COMPLETED"}


def test_premium_with_tax():
    r = process_ticket_manifest([build("premium", [{"qty": 2, "promo": ""}])], 0.1)
    assert r == {"total_revenue": 198.0, "status": "COMPLETED"}


def test_unknown_tier_rejected():
    r = process_ticket_manifest([build("gold", [{"qty": 1, "promo": ""}])], 0.0)
    assert r == {"total_revenue": 0.0, "status": "ZERO_SALES"}


def test_zero_quantity_rejected():
    r = process_ticket_manifest([build("general", [{"qty": 0, "promo": ""}])], 0.0)
    assert r == {"total_revenue": 0.0, "status": "ZERO_SALES"}


def test_earlybird_discount():
    r = process_ticket_manifest([build("general", [{"qty": 2, "promo": "EARLYBIRD"}])], 0.0)
    assert r == {"total_revenue": 72.0, "status": "COMPLETED"}


def test_bulk_discount():
    r = process_ticket_manifest([build("general", [{"qty": 5, "promo": ""}])], 0.0)
    assert r == {"total_revenue": 205.0, "status": "COMPLETED"}


def test_fraud_on_vip_zeroes_manifest():
    orders = [{"qty": 1, "promo": ""}, {"qty": 1, "promo": "FRAUD_RISK"}, {"qty": 1, "promo": ""}]
    r = process_ticket_manifest([build("vip", orders)], 0.0)
    assert r == {"total_revenue": 0.0, "status": "ZERO_SALES"}


def test_fraud_on_non_vip_still_counted():
    orders = [{"qty": 1, "promo": "FRAUD_RISK"}, {"qty": 2, "promo": ""}]
    r = process_ticket_manifest([build("general", orders)], 0.0)
    assert r == {"total_revenue": 135.0, "status": "COMPLETED"}


def test_lounge_surcharge():
    r = process_ticket_manifest([build("general", [{"qty": 1, "promo": ""}], lounge=True)], 0.0)
    assert r == {"total_revenue": 120.0, "status": "COMPLETED"}


def test_audit_rejected():
    orders = [{"qty": 0, "promo": ""}] * 5
    r = process_ticket_manifest([build("general", orders)], 0.1)
    assert r == {"total_revenue": 0.0, "status": "AUDIT_REJECTED"}


def test_gate_no_data():
    assert monitor_gate_flow([]) == "NO_DATA"


def test_gate_overflow():
    assert monitor_gate_flow([[10, 60, 70]]) == "OVERFLOW"


def test_gate_flow_normal_streak_resets():
    assert monitor_gate_flow([[60, 10, 60]]) == "FLOW_NORMAL"