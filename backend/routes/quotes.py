"""
ProcureOS v2 — Vendor Quote Portal Routes
GET  /quote/<token>       — get RFQ info
POST /quote/<token>/submit — vendor submits quote
"""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from models import db, ProcurementVendor, Procurement, Vendor, Company, Activity

quotes_bp = Blueprint('quotes', __name__)


# ── GET QUOTE INFO ────────────────────────────────────────────────────────────

@quotes_bp.route('/<token>', methods=['GET'])
def get_quote_info(token):
    pv = ProcurementVendor.query.filter_by(token=token).first()
    if not pv:
        return jsonify({'error': 'Invalid or expired link'}), 404

    # Check expiry
    if pv.token_expires_at:
        expires = pv.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return jsonify({'error': 'This quote link has expired'}), 410

    if pv.status in ('quoted', 'declined'):
        return jsonify({'error': 'You have already submitted a quote for this request'}), 409

    proc    = Procurement.query.get(pv.procurement_id)
    vendor  = Vendor.query.get(pv.vendor_id)
    company = Company.query.get(proc.company_id) if proc else None

    if not proc or not vendor:
        return jsonify({'error': 'Not found'}), 404

    return jsonify({
        'procurement_id': proc.id,
        'item_name': proc.item_name,
        'quantity': proc.quantity,
        'unit': proc.unit or 'units',
        'notes': proc.notes or '',
        'deadline': proc.deadline.isoformat() if proc.deadline else None,
        'rfq_template': proc.rfq_template,
        'vendor_name': vendor.company_name,
        'buyer_name': company.name if company else 'Buyer',
    })


# ── SUBMIT QUOTE ──────────────────────────────────────────────────────────────

@quotes_bp.route('/<token>/submit', methods=['POST'])
def submit_quote(token):
    pv = ProcurementVendor.query.filter_by(token=token).first()
    if not pv:
        return jsonify({'error': 'Invalid or expired link'}), 404

    if pv.token_expires_at:
        expires = pv.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return jsonify({'error': 'This quote link has expired'}), 410

    if pv.status in ('quoted', 'declined'):
        return jsonify({'error': 'Quote already submitted'}), 409

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    price = data.get('price')
    if not price or float(price) <= 0:
        return jsonify({'error': 'Valid price is required'}), 400

    availability = data.get('availability', 'yes')
    if availability not in ('yes', 'no', 'partial'):
        return jsonify({'error': 'Availability must be yes, no, or partial'}), 400

    pv.quote_price         = float(price)
    pv.quote_delivery_days = data.get('delivery_days')
    pv.quote_payment_terms = data.get('payment_terms', '')
    pv.quote_notes         = data.get('notes', '')
    pv.quote_availability  = availability
    pv.quote_capacity      = data.get('capacity', '')
    pv.quote_certifications = data.get('certifications', '')
    pv.quote_experience    = data.get('experience', '')
    pv.quote_received_at   = datetime.now(timezone.utc)
    pv.status              = 'quoted'

    proc   = Procurement.query.get(pv.procurement_id)
    vendor = Vendor.query.get(pv.vendor_id)

    db.session.add(Activity(
        company_id=proc.company_id if proc else '',
        procurement_id=pv.procurement_id,
        actor=vendor.company_name if vendor else 'Vendor',
        action='Quote received',
        detail=f'${float(price):,.2f}'
    ))

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Your quote has been submitted successfully.'
    })


# ── DECLINE QUOTE ─────────────────────────────────────────────────────────────

@quotes_bp.route('/<token>/decline', methods=['POST'])
def decline_quote(token):
    pv = ProcurementVendor.query.filter_by(token=token).first()
    if not pv:
        return jsonify({'error': 'Invalid link'}), 404

    pv.status = 'declined'
    db.session.commit()
    return jsonify({'success': True, 'message': 'You have declined this quote request.'})