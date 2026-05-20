"""
ProcureOS v2 — Email Agent
Brevo SMTP (primary)
"""
import os
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailAgent:
    def __init__(self):
        self.smtp_server   = os.environ.get('SMTP_SERVER', 'smtp-relay.brevo.com')
        self.smtp_port     = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_user     = os.environ.get('SMTP_USER', '').strip()
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '').strip()
        self.from_email    = os.environ.get('FROM_EMAIL', self.smtp_user)
        self.from_name     = os.environ.get('FROM_NAME', 'ProcureOS')

    def _html_to_text(self, html):
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        text = re.sub(r'</(div|p|h[1-6]|li|tr|td)>', '\n', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def send(self, to, subject, html):
        if not to or '@' not in to:
            print(f'[EMAIL] Invalid address: {to}')
            return False
        try:
            import requests
            response = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'accept': 'application/json',
                    'api-key': os.environ.get('BREVO_API_KEY', ''),
                    'content-type': 'application/json'
                },
                json={
                    'sender': {'name': self.from_name, 'email': self.from_email},
                    'to': [{'email': to}],
                    'subject': subject,
                    'htmlContent': html
                },
                timeout=15
            )
            if response.status_code == 201:
                print(f'[BREVO] Sent to {to}')
                return True
            else:
                print(f'[BREVO] Failed: {response.text}')
                return False
        except Exception as e:
            print(f'[BREVO] Failed: {e}')
            return False

    def send_rfq(self, to, vendor_name, company_name, item_name,
                 quantity, unit, deadline_str, portal_url,
                 template_type='Standard', notes=''):

        advanced_fields = ''
        if template_type == 'Advanced':
            advanced_fields = """
            <li>Your monthly production capacity for this item</li>
            <li>Relevant certifications (ISO, CE, etc.)</li>
            <li>Years of experience supplying this category</li>
            <li>Preferred payment terms</li>
            """

        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f9fafb">
        <div style="background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e7eb">
          <div style="margin-bottom:24px">
            <h1 style="font-size:22px;font-weight:700;color:#111;margin:0">Request for Quotation</h1>
            <p style="color:#6b7280;font-size:14px;margin:4px 0 0 0">from {company_name}</p>
          </div>
          <p style="font-size:15px">Dear <strong>{vendor_name}</strong>,</p>
          <p style="color:#374151">{company_name} is requesting a quote for the following:</p>
          <div style="background:#eef2ff;border-left:4px solid #6366f1;padding:16px;border-radius:0 8px 8px 0;margin:20px 0">
            <div style="font-size:20px;font-weight:700;color:#1e1b4b">{item_name}</div>
            <div style="color:#6b7280;margin-top:4px">Quantity: <strong>{quantity} {unit}</strong></div>
            {f'<div style="color:#6b7280;margin-top:4px">Notes: {notes}</div>' if notes else ''}
          </div>
          <p style="font-size:14px;color:#374151"><strong>Please provide:</strong></p>
          <ul style="color:#374151;line-height:2;font-size:14px">
            <li>Unit price and currency</li>
            <li>Delivery timeline (days)</li>
            <li>Product availability</li>
            {advanced_fields}
          </ul>
          <p style="font-size:13px;color:#374151;margin-top:16px">
            <strong>Deadline:</strong> {deadline_str}
          </p>
          <div style="text-align:center;margin:32px 0">
            <a href="{portal_url}" style="background:#6366f1;color:#fff;padding:14px 36px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;display:inline-block">
              Submit Your Quote →
            </a>
          </div>
          <p style="font-size:12px;color:#9ca3af;border-top:1px solid #e5e7eb;padding-top:16px">
            This link is unique to your company. Do not share it.
          </p>
        </div>
        </body></html>
        """
        return self.send(to, f'{company_name} — Quote Request for {item_name}', html)

    def send_po(self, to, vendor_name, po_number, company_name,
            item_name, quantity, unit_price, total,
            delivery_days, payment_terms, unit='units', currency='USD'):
        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px">
        <div style="background:#1e40af;color:#fff;padding:28px;border-radius:8px 8px 0 0;text-align:center">
          <h1 style="margin:0;font-size:26px">PURCHASE ORDER</h1>
          <div style="font-size:18px;font-weight:600;margin-top:8px;opacity:0.9">{po_number}</div>
        </div>
        <div style="border:1px solid #e5e7eb;padding:20px">
          <table width="100%" style="border-collapse:collapse">
            <tr>
              <td style="padding:8px 0"><strong>From:</strong> {company_name}</td>
              <td style="padding:8px 0"><strong>To:</strong> {vendor_name}</td>
            </tr>
          </table>
        </div>
        <div style="border:1px solid #e5e7eb;border-top:none;padding:20px">
          <table width="100%" cellpadding="10" style="border-collapse:collapse">
            <thead>
              <tr style="background:#f3f4f6">
                <th style="text-align:left;border-bottom:2px solid #e5e7eb">Item</th>
                <th style="text-align:center;border-bottom:2px solid #e5e7eb">Qty</th>
                <th style="text-align:right;border-bottom:2px solid #e5e7eb">Unit Price</th>
                <th style="text-align:right;border-bottom:2px solid #e5e7eb">Total</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="border-bottom:1px solid #e5e7eb">{item_name}</td>
                <td style="text-align:center;border-bottom:1px solid #e5e7eb">{quantity} {unit}</td>
                <td style="text-align:right;border-bottom:1px solid #e5e7eb">{currency} {unit_price:,.2f}</td>
                <td style="text-align:right;border-bottom:1px solid #e5e7eb"><strong>{currency} {total:,.2f}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="border:1px solid #e5e7eb;border-top:none;padding:20px;border-radius:0 0 8px 8px">
          <p style="margin:4px 0"><strong>Delivery:</strong> {delivery_days} business days</p>
          <p style="margin:4px 0"><strong>Payment Terms:</strong> {payment_terms}</p>
        </div>
        <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:16px">
          This is an official purchase order from {company_name}.
        </p>
        </body></html>
        """
        return self.send(to, f'{company_name} — Purchase Order {po_number}', html)

    def send_reminder(self, to, vendor_name, item_name, deadline_str, portal_url):
        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
        <div style="background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e7eb">
          <h2 style="color:#d97706">⏰ Quote Deadline Reminder</h2>
          <p>Dear <strong>{vendor_name}</strong>,</p>
          <p>This is a reminder that your quote for <strong>{item_name}</strong> is due by <strong>{deadline_str}</strong>.</p>
          <div style="text-align:center;margin:24px 0">
            <a href="{portal_url}" style="background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600">
              Submit Quote Now →
            </a>
          </div>
        </div>
        </body></html>
        """
        return self.send(to, f'Reminder: Quote due for {item_name}', html)

    def send_approval_request(self, to, approver_name, requester_name,
                               item_name, total_value, approval_url):
        html = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
        <div style="background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e7eb">
          <h2 style="color:#1e40af">Approval Required</h2>
          <p>Dear <strong>{approver_name}</strong>,</p>
          <p><strong>{requester_name}</strong> has requested approval for:</p>
          <div style="background:#f3f4f6;padding:16px;border-radius:8px;margin:16px 0">
            <p style="margin:0;font-size:16px;font-weight:600">{item_name}</p>
            <p style="margin:4px 0;color:#6b7280">Total Value: <strong>${total_value:,.2f}</strong></p>
          </div>
          <div style="text-align:center;margin:24px 0">
            <a href="{approval_url}" style="background:#059669;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600">
              Review & Approve →
            </a>
          </div>
        </div>
        </body></html>
        """
        return self.send(to, f'Approval Needed: {item_name}', html)