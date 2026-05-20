"""
ProcureOS v2 — AI Scorer
Ranks vendors by weighted score. Human always makes final decision.
"""
import math


def score_vendors(vendors, weights):
    """
    vendors: list of dicts with keys:
        vendor_id, vendor_name, price, delivery_days,
        reliability_score, certifications, availability
    weights: dict with keys:
        price_weight, delivery_weight, quality_weight, compliance_weight
    returns: same list sorted by score descending, each item gets 'score' and 'rank'
    """
    if not vendors:
        return []

    # Filter out vendors with no price
    scoreable = [v for v in vendors if v.get('price') and float(v['price']) > 0]
    no_price  = [v for v in vendors if not v.get('price') or float(v.get('price', 0)) <= 0]

    if not scoreable:
        for i, v in enumerate(vendors):
            v['score'] = 0
            v['rank']  = i + 1
        return vendors

    # ── PRICE SCORE (lower is better) ───────────────────────────────────────
    prices = [float(v['price']) for v in scoreable]
    min_p, max_p = min(prices), max(prices)
    for v in scoreable:
        p = float(v['price'])
        v['price_score'] = (
            1.0 - (p - min_p) / (max_p - min_p)
            if max_p > min_p else 1.0
        )

    # ── DELIVERY SCORE (faster is better) ───────────────────────────────────
    deliveries = [v.get('delivery_days') for v in scoreable if v.get('delivery_days')]
    if deliveries:
        min_d, max_d = min(deliveries), max(deliveries)
        for v in scoreable:
            d = v.get('delivery_days')
            if d:
                v['delivery_score'] = (
                    1.0 - (d - min_d) / (max_d - min_d)
                    if max_d > min_d else 1.0
                )
            else:
                v['delivery_score'] = 0.5
    else:
        for v in scoreable:
            v['delivery_score'] = 0.5

    # ── QUALITY SCORE (reliability + availability) ───────────────────────────
    for v in scoreable:
        rel = float(v.get('reliability_score') or 80) / 100.0
        avail_map = {'yes': 1.0, 'partial': 0.6, 'no': 0.0}
        avail = avail_map.get(str(v.get('availability', 'yes')).lower(), 0.8)
        v['quality_score'] = (rel * 0.7) + (avail * 0.3)

    # ── COMPLIANCE SCORE (certifications) ────────────────────────────────────
    for v in scoreable:
        certs = str(v.get('certifications') or '')
        cert_keywords = ['iso', 'ce', 'fda', 'gmp', 'ohsas', 'ansi', 'astm', 'ul']
        found = sum(1 for kw in cert_keywords if kw.lower() in certs.lower())
        v['compliance_score'] = min(1.0, found * 0.25 + 0.25)

    # ── WEIGHTED TOTAL ────────────────────────────────────────────────────────
    pw = float(weights.get('price_weight', 80)) / 100.0
    dw = float(weights.get('delivery_weight', 80)) / 100.0
    qw = float(weights.get('quality_weight', 80)) / 100.0
    cw = float(weights.get('compliance_weight', 50)) / 100.0
    total_w = pw + dw + qw + cw or 1.0

    for v in scoreable:
        raw = (
            v['price_score']      * pw +
            v['delivery_score']   * dw +
            v['quality_score']    * qw +
            v['compliance_score'] * cw
        )
        v['score'] = round((raw / total_w) * 100, 1)

    # ── SORT & RANK ───────────────────────────────────────────────────────────
    scoreable.sort(key=lambda x: x['score'], reverse=True)
    for i, v in enumerate(scoreable):
        v['rank'] = i + 1
        v['is_recommended'] = (i == 0)

    # Append no-price vendors at the bottom
    for i, v in enumerate(no_price):
        v['score'] = 0
        v['rank']  = len(scoreable) + i + 1
        v['is_recommended'] = False

    return scoreable + no_price


def get_recommendation_reason(vendor, all_vendors):
    """
    Returns a short human-readable reason why this vendor is recommended.
    """
    if not vendor or not all_vendors:
        return ''

    parts = []
    price = vendor.get('price')
    if price:
        prices = [float(v['price']) for v in all_vendors if v.get('price')]
        if prices:
            avg = sum(prices) / len(prices)
            min_p = min(prices)
            if float(price) <= min_p * 1.02:
                parts.append(f"lowest price ({price:,.0f})")
            elif float(price) < avg:
                pct = (avg - float(price)) / avg * 100
                parts.append(f"{pct:.0f}% below average price")

    delivery = vendor.get('delivery_days')
    if delivery:
        deliveries = [v['delivery_days'] for v in all_vendors if v.get('delivery_days')]
        if deliveries:
            min_d = min(deliveries)
            if delivery <= min_d + 1:
                parts.append(f"fastest delivery ({delivery} days)")

    rel = vendor.get('reliability_score')
    if rel and float(rel) >= 90:
        parts.append(f"{rel}% reliability score")

    if not parts:
        return f"Best overall score: {vendor.get('score', 0)}/100"

    reason = "Recommended: " + ", ".join(parts)
    reason += f". Score: {vendor.get('score', 0)}/100"
    return reason