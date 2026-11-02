import pytest
from event_ticket_tier import process_ticket_manifest, monitor_gate_flow
 
 
def build(tier="general", orders=None, confirmed=True, lounge=False):
    return {
        "is_confirmed": confirmed,
        "tier": tier,
        "exclusive_lounge": lounge,
        "orders": orders if orders is not None else [{"qty": 1, "promo": ""}],
    }
 
 
# ---- Input validation (line 2): each side of the "or" ----
def test_not_a_list_raises():
    with pytest.raises(ValueError):
        process_ticket_manifest("abc", 0.1)
 
 
def test_negative_tax_raises():
    with pytest.raises(ValueError):
        process_ticket_manifest([], -0.5)
 
 
def test_valid_input_does_not_raise():
    assert process_ticket_manifest([], 0.0)["status"] == "ZERO_SALES"
 
 
# ---- Manifest loop (line 8): empty list vs non-empty ----
def test_empty_manifest_list():
    assert process_ticket_manifest([], 0.2) == {"total_revenue": 0.0, "status": "ZERO_SALES"}
 
 
# ---- Confirmed check (line 9): both outcomes ----
def test_unconfirmed_skipped():
    r = process_ticket_manifest([build(confirmed=False)], 0.0)
    assert r["status"] == "ZERO_SALES"
 
 
def test_confirmed_processed():
    r = process_ticket_manifest([build(confirmed=True)], 0.0)
    assert r == {"total_revenue": 45.0, "status": "COMPLETED"}
 
 
# ---- Tier chain (lines 15-23): every arm ----
@pytest.mark.parametrize("tier,expected", [("vip", 150.0), ("premium", 90.0), ("general", 45.0)])
def test_each_valid_tier(tier, expected):
    r = process_ticket_manifest([build(tier=tier)], 0.0)
    assert r == {"total_revenue": expected, "status": "COMPLETED"}
 
 
def test_unknown_tier_goes_to_else():
    r = process_ticket_manifest([build(tier="gold")], 0.0)
    assert r["status"] == "ZERO_SALES"
 
 
# ---- Order loop (line 27): no orders vs some orders ----
def test_manifest_with_no_orders():
    r = process_ticket_manifest([build(orders=[])], 0.0)
    assert r["status"] == "ZERO_SALES"
 
 
# ---- Quantity check (line 31): both outcomes ----
def test_zero_qty_rejected():
    r = process_ticket_manifest([build(orders=[{"qty": 0, "promo": ""}])], 0.0)
    assert r["status"] == "ZERO_SALES"
 
 
def test_negative_qty_rejected():
    r = process_ticket_manifest([build(orders=[{"qty": -3, "promo": ""}])], 0.0)
    assert r["status"] == "ZERO_SALES"
 
 
def test_positive_qty_accepted():
    r = process_ticket_manifest([build(orders=[{"qty": 2, "promo": ""}])], 0.0)
    assert r["total_revenue"] == 90.0
 
 
# ---- Promo chain (lines 37-45): FRAUD (vip / non-vip), EARLYBIRD, else ----
def test_fraud_vip_breaks_and_zeroes():
    orders = [{"qty": 1, "promo": ""}, {"qty": 1, "promo": "FRAUD_RISK"}, {"qty": 1, "promo": ""}]
    r = process_ticket_manifest([build(tier="vip", orders=orders)], 0.0)
    assert r["status"] == "ZERO_SALES"
 
 
def test_fraud_non_vip_continues():
    orders = [{"qty": 1, "promo": "FRAUD_RISK"}, {"qty": 1, "promo": ""}]
    r = process_ticket_manifest([build(tier="premium", orders=orders)], 0.0)
    assert r == {"total_revenue": 180.0, "status": "COMPLETED"}
 
 
def test_earlybird():
    r = process_ticket_manifest([build(orders=[{"qty": 1, "promo": "EARLYBIRD"}])], 0.0)
    assert r["total_revenue"] == 36.0
 
 
def test_other_promo_is_ignored():
    r = process_ticket_manifest([build(orders=[{"qty": 1, "promo": "SOMETHING"}])], 0.0)
    assert r["total_revenue"] == 45.0
 
 
# ---- Bulk discount (line 45): qty boundary 4 / 5 ----
def test_qty_four_no_bulk_discount():
    r = process_ticket_manifest([build(orders=[{"qty": 4, "promo": ""}])], 0.0)
    assert r["total_revenue"] == 180.0
 
 
def test_qty_five_bulk_discount():
    r = process_ticket_manifest([build(orders=[{"qty": 5, "promo": ""}])], 0.0)
    assert r["total_revenue"] == 205.0
 
 
# ---- Lounge (line 50): both outcomes ----
def test_lounge_true():
    r = process_ticket_manifest([build(lounge=True)], 0.0)
    assert r["total_revenue"] == 120.0
 
 
def test_lounge_false():
    r = process_ticket_manifest([build(lounge=False)], 0.0)
    assert r["total_revenue"] == 45.0
 
 
# ---- Final status (lines 57-61): audit boundary 4 / 5 rejections ----
def test_four_rejections_not_audited():
    orders = [{"qty": 0, "promo": ""}] * 4 + [{"qty": 1, "promo": ""}]
    r = process_ticket_manifest([build(orders=orders)], 0.0)
    assert r["status"] == "COMPLETED"
 
 
def test_five_rejections_audited():
    orders = [{"qty": 0, "promo": ""}] * 5
    r = process_ticket_manifest([build(orders=orders)], 0.1)
    assert r == {"total_revenue": 0.0, "status": "AUDIT_REJECTED"}
 
 
def test_tax_applied_and_rounded():
    r = process_ticket_manifest([build()], 0.1)
    assert r == {"total_revenue": 49.5, "status": "COMPLETED"}
 
 
# ---- Gate flow ----
def test_gate_empty_list():
    assert monitor_gate_flow([]) == "NO_DATA"
 
 
def test_gate_empty_stream():
    assert monitor_gate_flow([[]]) == "FLOW_NORMAL"
 
 
def test_gate_all_low():
    assert monitor_gate_flow([[10, 20, 30]]) == "FLOW_NORMAL"
 
 
def test_gate_single_spike_no_overflow():
    assert monitor_gate_flow([[10, 60, 10]]) == "FLOW_NORMAL"
 
 
def test_gate_streak_resets_between_spikes():
    assert monitor_gate_flow([[60, 10, 60]]) == "FLOW_NORMAL"
 
 
def test_gate_two_in_a_row_overflow():
    assert monitor_gate_flow([[60, 60]]) == "OVERFLOW"
 
 
def test_gate_second_stream_overflows():
    assert monitor_gate_flow([[10, 10], [70, 80]]) == "OVERFLOW"
 
 
def test_gate_streak_does_not_carry_across_streams():
    assert monitor_gate_flow([[10, 60], [60, 10]]) == "FLOW_NORMAL"
 