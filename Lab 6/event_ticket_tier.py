def process_ticket_manifest(manifests, service_tax_rate):
    if not isinstance(manifests, list) or service_tax_rate < 0:
        raise ValueError("Invalid manifests list or tax rate")

    total_revenue = 0.0
    rejected_orders = 0

    for manifest in manifests:
        if not manifest.get("is_confirmed", False):
            continue

        tier = manifest.get("tier", "general")
        orders = manifest.get("orders", [])

        if tier == "vip":
            base_seat_price = 150.0
        elif tier == "premium":
            base_seat_price = 90.0
        elif tier == "general":
            base_seat_price = 45.0
        else:
            rejected_orders += 1
            continue

        manifest_total = 0.0

        for order in orders:
            qty = order.get("qty", 0)
            promo_code = order.get("promo", "")

            if qty <= 0:
                rejected_orders += 1
                continue

            order_price = qty * base_seat_price

            if promo_code == "FRAUD_RISK":
                rejected_orders += 1
                if tier == "vip":
                    manifest_total = 0.0
                    break
            elif promo_code == "EARLYBIRD":
                order_price *= 0.80
            else:
                if qty >= 5:
                    order_price -= 20.0

            manifest_total += order_price

        if manifest.get("exclusive_lounge", False):
            manifest_total += 75.0

        total_revenue += manifest_total

    final_billed = total_revenue * (1 + service_tax_rate)

    if rejected_orders > 4:
        return {"total_revenue": round(final_billed, 2), "status": "AUDIT_REJECTED"}
    if total_revenue == 0.0:
        return {"total_revenue": 0.0, "status": "ZERO_SALES"}
    return {"total_revenue": round(final_billed, 2), "status": "COMPLETED"}


def monitor_gate_flow(turnstile_streams):
    if not turnstile_streams:
        return "NO_DATA"

    for stream in turnstile_streams:
        congestion_streak = 0
        for rate in stream:
            if rate > 50:
                congestion_streak += 1
                if congestion_streak >= 2:
                    return "OVERFLOW"
            else:
                congestion_streak = 0
    return "FLOW_NORMAL"