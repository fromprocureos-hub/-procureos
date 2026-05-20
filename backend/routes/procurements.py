"""
ProcureOS v2 — Procurement Routes
"""
import secrets
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Vendor, Procurement, ProcurementVendor, Activity, Company
from agents.scorer import score_vendors, get_recommendation_reason
from agents.email_agent import EmailAgent
import os

procurements_bp = Blueprint('procurements', __name__)
email_agent = EmailAgent()


def log_activity(company_id, user_id, actor, action, detail='', procurement_id=None):
    db.session.add(Activity(
        company_id=company_id,
        procurement_id=procurement_id,
        user_id=user_id,
        actor=actor,
        action=action,
        detail=detail
    ))


def current_user():
    return User.query.get(get_jwt_identity())


# ── LIST PROCUREMENTS ─────────────────────────────────────────────────────────

@procurements_bp.route('', methods=['GET'])
@jwt_required()
def list_procurements():
    user   = current_user()
    status = request.args.get('status', '')
    page   = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    query = Procurement.query.filter_by(company_id=user.company_id)
    if status:
        query = query.filter_by(status=status)

    total = query.count()
    items = query.order_by(Procurement.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return jsonify({
        'procurements': [p.to_dict() for p in items],
        'total': total,
        'page': page,
        'pages': -(-total // per_page)
    })


# ── CREATE PROCUREMENT ────────────────────────────────────────────────────────

@procurements_bp.route('', methods=['POST'])
@jwt_required()
def create_procurement():
    user    = current_user()
    company = Company.query.get(user.company_id)
    data    = request.get_json()

    required = ['title', 'item_name', 'quantity']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    deadline = None
    if data.get('deadline'):
        try:
            deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
        except Exception:
            return jsonify({'error': 'Invalid deadline format'}), 400

    required_by = None
    if data.get('required_by'):
        try:
            required_by = datetime.fromisoformat(data['required_by'].replace('Z', '+00:00'))
        except Exception:
            pass

    proc = Procurement(
        company_id=user.company_id,
        created_by=user.id,
        title=data['title'].strip(),
        item_name=data['item_name'].strip(),
        quantity=int(data['quantity']),
        unit=data.get('unit', 'units'),
        category_tag=data.get('category_tag', ''),
        notes=data.get('notes', ''),
        required_by=required_by,
        deadline=deadline,
        rfq_template=data.get('rfq_template', company.default_template or 'Standard'),
        price_weight=data.get('price_weight', company.price_weight),
        delivery_weight=data.get('delivery_weight', company.delivery_weight),
        quality_weight=data.get('quality_weight', company.quality_weight),
        compliance_weight=data.get('compliance_weight', company.compliance_weight),
        status='draft'
    )
    db.session.add(proc)
    db.session.flush()

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Procurement created',
        detail=proc.title,
        procurement_id=proc.id
    )

    db.session.commit()
    return jsonify({'procurement': proc.to_dict()}), 201


# ── GET PROCUREMENT DETAIL ────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>', methods=['GET'])
@jwt_required()
def get_procurement(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    pv_list = ProcurementVendor.query.filter_by(procurement_id=proc_id).all()
    activities = Activity.query.filter_by(
        procurement_id=proc_id
    ).order_by(Activity.timestamp.desc()).limit(20).all()

    return jsonify({
        'procurement': proc.to_dict(),
        'vendors': [pv.to_dict() for pv in pv_list],
        'activities': [a.to_dict() for a in activities]
    })


# ── UPDATE PROCUREMENT ────────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>', methods=['PUT'])
@jwt_required()
def update_procurement(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    if proc.status not in ('draft',):
        return jsonify({'error': 'Can only edit draft procurements'}), 400

    data = request.get_json()
    fields = ['title', 'item_name', 'quantity', 'unit', 'category_tag',
              'notes', 'rfq_template', 'price_weight', 'delivery_weight',
              'quality_weight', 'compliance_weight']
    for f in fields:
        if f in data:
            setattr(proc, f, data[f])

    if 'deadline' in data and data['deadline']:
        try:
            proc.deadline = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))
        except Exception:
            pass

    db.session.commit()
    return jsonify({'procurement': proc.to_dict()})


# ── FIND & RANK SUPPLIERS ─────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/find-suppliers', methods=['GET'])
@jwt_required()
def find_suppliers(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    category = (proc.category_tag or '').lower()
    vendors  = Vendor.query.filter_by(
        company_id=user.company_id,
        is_active=True
    ).all()

    # Score all vendors using procurement weights
    vendor_dicts = []
    for v in vendors:
        vendor_dicts.append({
            'vendor_id': v.id,
            'vendor_name': v.company_name,
            'vendor_email': v.contact_email,
            'price': None,
            'delivery_days': None,
            'reliability_score': float(v.reliability_score or 80),
            'certifications': '',
            'availability': 'yes',
        })

    weights = {
        'price_weight': proc.price_weight,
        'delivery_weight': proc.delivery_weight,
        'quality_weight': proc.quality_weight,
        'compliance_weight': proc.compliance_weight,
    }

    scored = score_vendors(vendor_dicts, weights)

    # Mark top 3 as pre-selected
    for i, v in enumerate(scored):
        v['pre_selected'] = i < 3

    return jsonify({'vendors': scored, 'total': len(scored)})


# ── SELECT VENDORS & SAVE ─────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/select-vendors', methods=['POST'])
@jwt_required()
def select_vendors(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    data       = request.get_json()
    vendor_ids = data.get('vendor_ids', [])

    if not vendor_ids:
        return jsonify({'error': 'Select at least one vendor'}), 400

    # Remove previously selected vendors
    ProcurementVendor.query.filter_by(procurement_id=proc_id).delete()

    for vid in vendor_ids:
        vendor = Vendor.query.filter_by(
            id=vid, company_id=user.company_id
        ).first()
        if not vendor:
            continue
        pv = ProcurementVendor(
            procurement_id=proc_id,
            vendor_id=vid,
            status='pending'
        )
        db.session.add(pv)

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Vendors selected',
        detail=f'{len(vendor_ids)} vendors selected for RFQ',
        procurement_id=proc_id
    )

    db.session.commit()
    return jsonify({'message': f'{len(vendor_ids)} vendors selected'})


# ── SEND RFQ EMAILS (human clicks this) ──────────────────────────────────────

@procurements_bp.route('/<proc_id>/send-rfq', methods=['POST'])
@jwt_required()
def send_rfq(proc_id):
    user    = current_user()
    proc    = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    company  = Company.query.get(user.company_id)
    pv_list  = ProcurementVendor.query.filter_by(
        procurement_id=proc_id
    ).all()

    if not pv_list:
        return jsonify({'error': 'No vendors selected'}), 400

    base_url     = os.environ.get('BASE_URL', 'http://localhost:5000')
    deadline_str = proc.deadline.strftime('%B %d, %Y') if proc.deadline else 'As soon as possible'
    sent         = 0
    skipped      = 0

    for pv in pv_list:
        vendor = pv.vendor
        if not vendor or not vendor.contact_email:
            skipped += 1
            continue

        # Generate unique token
        token            = secrets.token_urlsafe(32)
        pv.token         = token
        pv.token_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        portal_url       = f'{base_url}/quote/{token}'

        ok = email_agent.send_rfq(
            to=vendor.contact_email,
            vendor_name=vendor.company_name,
            company_name=company.name,
            item_name=proc.item_name,
            quantity=proc.quantity,
            unit=proc.unit or 'units',
            deadline_str=deadline_str,
            portal_url=portal_url,
            template_type=proc.rfq_template,
            notes=proc.notes or ''
        )

        if ok:
            pv.email_sent_at = datetime.now(timezone.utc)
            pv.status        = 'emailed'
            sent += 1
        else:
            skipped += 1

    proc.status = 'pending_quotes'

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='RFQ emails sent',
        detail=f'{sent} emails sent, {skipped} skipped',
        procurement_id=proc_id
    )

    db.session.commit()
    return jsonify({
        'sent': sent,
        'skipped': skipped,
        'message': f'RFQ sent to {sent} vendor(s).'
    })


# ── GET QUOTE COMPARISON ──────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/quotes', methods=['GET'])
@jwt_required()
def get_quotes(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    pv_list = ProcurementVendor.query.filter_by(
        procurement_id=proc_id
    ).all()

    # Build scoreable list from received quotes
    quoted = [pv for pv in pv_list if pv.quote_price]
    vendor_dicts = []
    for pv in quoted:
        vendor_dicts.append({
            'pv_id': pv.id,
            'vendor_id': pv.vendor_id,
            'vendor_name': pv.vendor.company_name if pv.vendor else 'Unknown',
            'vendor_email': pv.vendor.contact_email if pv.vendor else '',
            'price': float(pv.quote_price),
            'delivery_days': pv.quote_delivery_days,
            'reliability_score': float(pv.vendor.reliability_score or 80) if pv.vendor else 80,
            'certifications': pv.quote_certifications or '',
            'availability': pv.quote_availability or 'yes',
            'payment_terms': pv.quote_payment_terms or '',
            'notes': pv.quote_notes or '',
            'total_value': float(pv.quote_price) * proc.quantity,
        })

    weights = {
        'price_weight': proc.price_weight,
        'delivery_weight': proc.delivery_weight,
        'quality_weight': proc.quality_weight,
        'compliance_weight': proc.compliance_weight,
    }

    scored = score_vendors(vendor_dicts, weights)

    # Add recommendation reason to top vendor
    if scored:
        scored[0]['recommendation_reason'] = get_recommendation_reason(scored[0], scored)

    # Also return pending vendors
    pending = [pv.to_dict() for pv in pv_list if not pv.quote_price]

    return jsonify({
        'quoted': scored,
        'pending': pending,
        'total_vendors': len(pv_list),
        'quotes_received': len(quoted),
    })


# ── SELECT WINNER (human clicks) ─────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/select-winner', methods=['POST'])
@jwt_required()
def select_winner(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    data  = request.get_json()
    pv_id = data.get('pv_id')
    if not pv_id:
        return jsonify({'error': 'pv_id required'}), 400

    pv = ProcurementVendor.query.filter_by(
        id=pv_id, procurement_id=proc_id
    ).first()
    if not pv or not pv.quote_price:
        return jsonify({'error': 'Quote not found'}), 404

    proc.selected_vendor_id = pv.vendor_id
    proc.total_value        = float(pv.quote_price) * proc.quantity
    proc.delivery_days      = pv.quote_delivery_days
    proc.payment_terms      = pv.quote_payment_terms

    # Check if approval needed
    company = Company.query.get(user.company_id)
    needs_approval = (
        user.role == 'requester' and
        float(user.spend_limit or 0) > 0 and
        float(proc.total_value) > float(user.spend_limit)
    )

    if needs_approval:
        proc.status = 'pending_approval'
        # Notify approvers
        approvers = User.query.filter_by(
            company_id=user.company_id,
            role='approver',
            is_active=True
        ).all()
        base_url     = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
        approval_url = f'{base_url}/procurements/{proc_id}'
        for approver in approvers:
            email_agent.send_approval_request(
                to=approver.email,
                approver_name=approver.full_name or approver.email,
                requester_name=user.full_name or user.email,
                item_name=proc.item_name,
                total_value=float(proc.total_value),
                approval_url=approval_url
            )
    else:
        proc.status = 'pending_approval'

    pv.status = 'selected'

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Winner selected',
        detail=f'{pv.vendor.company_name if pv.vendor else "?"} at ${float(pv.quote_price):,.2f}',
        procurement_id=proc_id
    )

    db.session.commit()
    return jsonify({
        'procurement': proc.to_dict(),
        'needs_approval': needs_approval,
        'message': 'Winner selected. Ready for approval.' if needs_approval else 'Winner selected. Ready to generate PO.'
    })


# ── APPROVE ───────────────────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/approve', methods=['POST'])
@jwt_required()
def approve(proc_id):
    user = current_user()
    if user.role not in ('admin', 'approver'):
        return jsonify({'error': 'Approver access required'}), 403

    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    if proc.status not in ('pending_approval',):
        return jsonify({'error': f'Cannot approve. Status: {proc.status}'}), 400

    proc.status = 'approved'

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Procurement approved',
        procurement_id=proc_id
    )

    db.session.commit()
    return jsonify({'procurement': proc.to_dict(), 'message': 'Approved. Ready to generate PO.'})


# ── REJECT ────────────────────────────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/reject', methods=['POST'])
@jwt_required()
def reject(proc_id):
    user = current_user()
    if user.role not in ('admin', 'approver'):
        return jsonify({'error': 'Approver access required'}), 403

    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    data   = request.get_json() or {}
    reason = data.get('reason', '')
    proc.status = 'rejected'

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Procurement rejected',
        detail=reason,
        procurement_id=proc_id
    )

    db.session.commit()
    return jsonify({'procurement': proc.to_dict()})


# ── REQUEST DISCOUNT EMAIL DRAFT ──────────────────────────────────────────────

@procurements_bp.route('/<proc_id>/discount-draft', methods=['POST'])
@jwt_required()
def discount_draft(proc_id):
    user = current_user()
    proc = Procurement.query.filter_by(
        id=proc_id, company_id=user.company_id
    ).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    data    = request.get_json()
    pv_id   = data.get('pv_id')
    pv      = ProcurementVendor.query.get(pv_id)
    company = Company.query.get(user.company_id)

    if not pv or not pv.quote_price:
        return jsonify({'error': 'Quote not found'}), 404

    vendor      = pv.vendor
    target_pct  = data.get('target_discount_pct', 5)
    target_price = float(pv.quote_price) * (1 - target_pct / 100)

    # Return draft for human to review/edit/send
    draft = {
        'to': vendor.contact_email,
        'subject': f'Re: Quote for {proc.item_name} — Discount Request',
        'body': f"""Dear {vendor.company_name},

Thank you for your quote of ${float(pv.quote_price):,.2f} for {proc.item_name} (Qty: {proc.quantity} {proc.unit or 'units'}).

We are reviewing quotes from multiple suppliers and would like to ask if you can offer a better price. We are targeting around ${target_price:,.2f} per unit.

Please let us know if this is possible.

Best regards,
{user.full_name}
{company.name}"""
    }
    return jsonify({'draft': draft})


# ── DASHBOARD STATS ───────────────────────────────────────────────────────────

@procurements_bp.route('/stats/dashboard', methods=['GET'])
@jwt_required()
def dashboard_stats():
    user = current_user()
    cid  = user.company_id

    active    = Procurement.query.filter_by(company_id=cid, status='pending_quotes').count()
    pending   = Procurement.query.filter_by(company_id=cid, status='pending_approval').count()
    approved  = Procurement.query.filter_by(company_id=cid, status='approved').count()
    completed = Procurement.query.filter_by(company_id=cid, status='completed').count()
    vendors   = Vendor.query.filter_by(company_id=cid, is_active=True).count()

    recent = Procurement.query.filter_by(
        company_id=cid
    ).order_by(Procurement.created_at.desc()).limit(5).all()

    return jsonify({
        'active_rfqs': active,
        'pending_approvals': pending,
        'approved': approved,
        'completed': completed,
        'total_vendors': vendors,
        'recent_procurements': [p.to_dict() for p in recent]
    })