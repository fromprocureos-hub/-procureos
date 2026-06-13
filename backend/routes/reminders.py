from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone, timedelta
import os
import requests
from models import db, User, Procurement, ProcurementVendor, Activity

reminders_bp = Blueprint('reminders', __name__)

BREVO_KEY = os.getenv('BREVO_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@procureos.com')
FROM_NAME = os.getenv('FROM_NAME', 'ProcureOS')
APP_URL = os.getenv('APP_URL', 'https://procureos-production.up.railway.app')


def send_brevo(to_email, to_name, subject, html):
    r = requests.post(
        'https://api.brevo.com/v3/smtp/email',
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json'},
        json={
            'sender': {'name': FROM_NAME, 'email': FROM_EMAIL},
            'to': [{'email': to_email, 'name': to_name}],
            'subject': subject,
            'htmlContent': html,
        },
        timeout=10
    )
    return r.status_code < 300


def get_company_id():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    return user.company_id if user else None


def get_user(uid):
    return User.query.get(uid)


@reminders_bp.route('/procurements/<pid>/reminder-status', methods=['GET'])
@jwt_required()
def reminder_status(pid):
    company_id = get_company_id()
    proc = Procurement.query.filter_by(id=pid, company_id=company_id).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    pvs = ProcurementVendor.query.filter_by(procurement_id=pid).all()
    now = datetime.now(timezone.utc)

    vendors = []
    for pv in pvs:
        v = pv.vendor
        if not v:
            continue

        # determine status
        if pv.quote_received_at:
            vstatus = 'replied'
        elif pv.email_sent_at:
            vstatus = 'opened'  # we treat emailed = opened (no pixel tracking yet)
        else:
            vstatus = 'not_opened'

        # smart reminder flags
        hours_since_sent = None
        if pv.email_sent_at:
            sent = pv.email_sent_at
            if sent.tzinfo is None:
                sent = sent.replace(tzinfo=timezone.utc)
            hours_since_sent = (now - sent).total_seconds() / 3600

        suggest_reminder = (
            vstatus != 'replied' and
            hours_since_sent is not None and
            hours_since_sent >= 48
        )

        deadline_hours = None
        urgent = False
        if proc.deadline:
            dl = proc.deadline
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            deadline_hours = (dl - now).total_seconds() / 3600
            urgent = deadline_hours < 24 and vstatus != 'replied'

        vendors.append({
            'pv_id': pv.id,
            'vendor_id': v.id,
            'vendor_name': v.company_name,
            'vendor_email': v.contact_email,
            'status': vstatus,
            'email_sent_at': pv.email_sent_at.isoformat() if pv.email_sent_at else None,
            'quote_received_at': pv.quote_received_at.isoformat() if pv.quote_received_at else None,
            'last_reminder_at': pv.last_reminder_at.isoformat() if hasattr(pv, 'last_reminder_at') and pv.last_reminder_at else None,
            'suggest_reminder': suggest_reminder,
            'urgent': urgent,
        })

    return jsonify({
        'procurement_title': proc.title,
        'procurement_deadline': proc.deadline.isoformat() if proc.deadline else None,
        'vendors': vendors,
    })


@reminders_bp.route('/procurements/<pid>/send-reminders', methods=['POST'])
@jwt_required()
def send_reminders(pid):
    uid = get_jwt_identity()
    company_id = get_company_id()
    user = get_user(uid)

    proc = Procurement.query.filter_by(id=pid, company_id=company_id).first()
    if not proc:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json()
    pv_ids = data.get('pv_ids', [])  # list of procurement_vendor ids to remind

    if not pv_ids:
        return jsonify({'error': 'No vendors selected'}), 400

    sent = []
    failed = []

    for pv_id in pv_ids:
        pv = ProcurementVendor.query.filter_by(id=pv_id, procurement_id=pid).first()
        if not pv or not pv.vendor:
            continue

        v = pv.vendor
        if not v.contact_email:
            failed.append(v.company_name)
            continue

        # build quote link
        quote_link = f"{APP_URL}/quote/{pv.token}" if pv.token else APP_URL

        deadline_str = ''
        if proc.deadline:
            deadline_str = proc.deadline.strftime('%d %B %Y')

        subject = f"Reminder: RFQ Response Required – {proc.title}"

        html = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:32px;background:#f9fafb">
  <div style="background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e7eb">
    <div style="margin-bottom:24px">
      <img src="{APP_URL}/icons.svg" style="height:32px" alt="ProcureOS" onerror="this.style.display='none'"/>
    </div>
    <h2 style="color:#1e3a5f;margin:0 0 8px">Reminder: Quote Still Required</h2>
    <p style="color:#6b7280;margin:0 0 24px">Dear {v.company_name},</p>
    <p style="color:#374151">We sent you an RFQ and are still awaiting your response. Please submit your quote at your earliest convenience.</p>

    <div style="background:#f0f4ff;border-radius:8px;padding:20px;margin:24px 0">
      <p style="margin:0 0 8px;font-weight:600;color:#1e3a5f">RFQ Details</p>
      <table style="width:100%;font-size:14px;color:#374151">
        <tr><td style="padding:4px 0;color:#6b7280">Item</td><td style="padding:4px 0;font-weight:500">{proc.item_name}</td></tr>
        <tr><td style="padding:4px 0;color:#6b7280">Quantity</td><td style="padding:4px 0;font-weight:500">{proc.quantity} {proc.unit}</td></tr>
        {'<tr><td style="padding:4px 0;color:#6b7280">Deadline</td><td style="padding:4px 0;font-weight:500;color:#dc2626">' + deadline_str + '</td></tr>' if deadline_str else ''}
        {'<tr><td style="padding:4px 0;color:#6b7280">Notes</td><td style="padding:4px 0">' + proc.notes + '</td></tr>' if proc.notes else ''}
      </table>
    </div>

    <a href="{quote_link}" style="display:inline-block;background:#1e3a5f;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px">
      Submit Your Quote
    </a>

    <p style="color:#9ca3af;font-size:12px;margin-top:32px">
      Reply with your quote or use the button above. If you have questions, simply reply to this email.
    </p>
  </div>
</div>
"""

        ok = send_brevo(v.contact_email, v.company_name, subject, html)
        if ok:
            sent.append(v.company_name)
            # log activity
            act = Activity(
                company_id=company_id,
                procurement_id=pid,
                user_id=uid,
                actor=user.full_name if user else 'User',
                action='Reminder sent',
                detail=f'Reminder email sent to {v.company_name} ({v.contact_email})',
            )
            db.session.add(act)
        else:
            failed.append(v.company_name)

    db.session.commit()

    return jsonify({
        'sent': sent,
        'failed': failed,
        'message': f'Reminders sent to {len(sent)} vendor(s)' + (f', failed for {len(failed)}' if failed else '')
    })