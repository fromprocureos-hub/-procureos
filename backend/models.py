"""
ProcureOS v2 — Database Models
Multi-tenant: all data scoped to company_id
"""
import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def new_id():
    return str(uuid.uuid4())

def now():
    return datetime.now(timezone.utc)


# ── INDUSTRY CONFIG ─────────────────────────────────────────────────────────

class IndustryConfig(db.Model):
    __tablename__ = 'industry_configs'
    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(120), unique=True, nullable=False)
    price_weight       = db.Column(db.Integer, default=80)
    delivery_weight    = db.Column(db.Integer, default=80)
    quality_weight     = db.Column(db.Integer, default=80)
    compliance_weight  = db.Column(db.Integer, default=50)
    default_template   = db.Column(db.String(20), default='Standard')
    typical_categories = db.Column(db.Text, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price_weight': self.price_weight,
            'delivery_weight': self.delivery_weight,
            'quality_weight': self.quality_weight,
            'compliance_weight': self.compliance_weight,
            'default_template': self.default_template,
            'typical_categories': self.typical_categories.split(',') if self.typical_categories else []
        }


# ── COMPANY (TENANT) ────────────────────────────────────────────────────────

class Company(db.Model):
    __tablename__ = 'companies'
    id                  = db.Column(db.String(36), primary_key=True, default=new_id)
    name                = db.Column(db.String(255), nullable=False)
    industry_id         = db.Column(db.Integer, db.ForeignKey('industry_configs.id'))
    logo_url            = db.Column(db.Text)
    default_payment_terms = db.Column(db.String(100), default='Net 30')
    price_weight        = db.Column(db.Integer, default=80)
    delivery_weight     = db.Column(db.Integer, default=80)
    quality_weight      = db.Column(db.Integer, default=80)
    compliance_weight   = db.Column(db.Integer, default=50)
    default_template    = db.Column(db.String(20), default='Standard')
    is_active           = db.Column(db.Boolean, default=True)
    created_at          = db.Column(db.DateTime, default=now)

    industry  = db.relationship('IndustryConfig', foreign_keys=[industry_id])
    users     = db.relationship('User', backref='company', lazy='dynamic')
    vendors   = db.relationship('Vendor', backref='company', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'industry_id': self.industry_id,
            'industry_name': self.industry.name if self.industry else None,
            'logo_url': self.logo_url,
            'default_payment_terms': self.default_payment_terms,
            'price_weight': self.price_weight,
            'delivery_weight': self.delivery_weight,
            'quality_weight': self.quality_weight,
            'compliance_weight': self.compliance_weight,
            'default_template': self.default_template,
        }


# ── USER ─────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.String(36), primary_key=True, default=new_id)
    company_id    = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    full_name     = db.Column(db.String(255))
    role          = db.Column(db.String(20), default='requester')  # admin | approver | requester
    spend_limit   = db.Column(db.Numeric(15, 2), default=0)        # 0 = no limit
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'spend_limit': float(self.spend_limit) if self.spend_limit else 0,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ── VENDOR ───────────────────────────────────────────────────────────────────

class Vendor(db.Model):
    __tablename__ = 'vendors'
    id                = db.Column(db.String(36), primary_key=True, default=new_id)
    company_id        = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    company_name      = db.Column(db.String(255), nullable=False)
    contact_email     = db.Column(db.String(255))
    phone             = db.Column(db.String(50))
    categories        = db.Column(db.Text)       # comma-separated
    reliability_score = db.Column(db.Numeric(5,2), default=80)
    notes             = db.Column(db.Text)
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'company_name': self.company_name,
            'contact_email': self.contact_email,
            'phone': self.phone,
            'categories': self.categories.split(',') if self.categories else [],
            'reliability_score': float(self.reliability_score) if self.reliability_score else 80,
            'notes': self.notes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

# ── VENDOR LISTS ──────────────────────────────────────────────────────────────

class VendorList(db.Model):
    __tablename__ = 'vendor_lists'
    id         = db.Column(db.String(36), primary_key=True, default=new_id)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    created_at  = db.Column(db.DateTime, default=now)
    members     = db.relationship('VendorListMember', backref='vendor_list', lazy=True, cascade='all, delete-orphan')

class VendorListMember(db.Model):
    __tablename__ = 'vendor_list_members'
    id         = db.Column(db.String(36), primary_key=True, default=new_id)
    list_id    = db.Column(db.String(36), db.ForeignKey('vendor_lists.id'), nullable=False)
    vendor_id  = db.Column(db.String(36), db.ForeignKey('vendors.id'), nullable=False)
    added_at   = db.Column(db.DateTime, default=now)

# ── PROCUREMENT ───────────────────────────────────────────────────────────────

class Procurement(db.Model):
    __tablename__ = 'procurements'
    id                 = db.Column(db.String(36), primary_key=True, default=new_id)
    company_id         = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    created_by         = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title              = db.Column(db.String(255), nullable=False)
    item_name          = db.Column(db.String(255), nullable=False)
    quantity           = db.Column(db.Integer, default=1)
    unit               = db.Column(db.String(50), default='units')
    category_tag       = db.Column(db.String(100))
    notes              = db.Column(db.Text)
    required_by        = db.Column(db.DateTime)
    deadline           = db.Column(db.DateTime)
    rfq_template       = db.Column(db.String(20), default='Standard')  # Standard | Advanced
    price_weight       = db.Column(db.Integer, default=80)
    delivery_weight    = db.Column(db.Integer, default=80)
    quality_weight     = db.Column(db.Integer, default=80)
    compliance_weight  = db.Column(db.Integer, default=50)
    status             = db.Column(db.String(50), default='draft')
    # draft | pending_quotes | pending_approval | approved | rejected | completed
    selected_vendor_id = db.Column(db.String(36), db.ForeignKey('vendors.id'), nullable=True)
    total_value        = db.Column(db.Numeric(15, 2))
    delivery_days      = db.Column(db.Integer)
    payment_terms      = db.Column(db.String(100))
    created_at         = db.Column(db.DateTime, default=now)
    updated_at         = db.Column(db.DateTime, default=now, onupdate=now)

    creator          = db.relationship('User', foreign_keys=[created_by])
    selected_vendor  = db.relationship('Vendor', foreign_keys=[selected_vendor_id])
    procurement_vendors = db.relationship('ProcurementVendor', backref='procurement', lazy='dynamic', cascade='all, delete-orphan')
    activities       = db.relationship('Activity', backref='procurement', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'title': self.title,
            'item_name': self.item_name,
            'quantity': self.quantity,
            'unit': self.unit,
            'category_tag': self.category_tag,
            'notes': self.notes,
            'required_by': self.required_by.isoformat() if self.required_by else None,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'rfq_template': self.rfq_template,
            'price_weight': self.price_weight,
            'delivery_weight': self.delivery_weight,
            'quality_weight': self.quality_weight,
            'compliance_weight': self.compliance_weight,
            'status': self.status,
            'selected_vendor_id': self.selected_vendor_id,
            'selected_vendor_name': self.selected_vendor.company_name if self.selected_vendor else None,
            'total_value': float(self.total_value) if self.total_value else None,
            'delivery_days': self.delivery_days,
            'payment_terms': self.payment_terms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ── PROCUREMENT VENDOR (join table with quote data) ───────────────────────────

class ProcurementVendor(db.Model):
    __tablename__ = 'procurement_vendors'
    id                   = db.Column(db.String(36), primary_key=True, default=new_id)
    procurement_id       = db.Column(db.String(36), db.ForeignKey('procurements.id'), nullable=False)
    vendor_id            = db.Column(db.String(36), db.ForeignKey('vendors.id'), nullable=False)
    rank_score           = db.Column(db.Numeric(5, 2))
    token                = db.Column(db.String(64), unique=True)
    token_expires_at     = db.Column(db.DateTime)
    email_sent_at        = db.Column(db.DateTime)
    quote_received_at    = db.Column(db.DateTime)
    quote_price          = db.Column(db.Numeric(15, 2))
    quote_delivery_days  = db.Column(db.Integer)
    quote_payment_terms  = db.Column(db.String(100))
    quote_notes          = db.Column(db.Text)
    quote_availability   = db.Column(db.String(20))  # yes | no | partial
    quote_capacity       = db.Column(db.String(255))
    quote_certifications = db.Column(db.String(255))
    quote_experience     = db.Column(db.Text)
    status               = db.Column(db.String(20), default='pending')
    # pending | emailed | quoted | declined | selected

    vendor = db.relationship('Vendor', foreign_keys=[vendor_id])

    def to_dict(self):
        return {
            'id': self.id,
            'procurement_id': self.procurement_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.company_name if self.vendor else None,
            'vendor_email': self.vendor.contact_email if self.vendor else None,
            'rank_score': float(self.rank_score) if self.rank_score else None,
            'email_sent_at': self.email_sent_at.isoformat() if self.email_sent_at else None,
            'quote_received_at': self.quote_received_at.isoformat() if self.quote_received_at else None,
            'quote_price': float(self.quote_price) if self.quote_price else None,
            'quote_delivery_days': self.quote_delivery_days,
            'quote_payment_terms': self.quote_payment_terms,
            'quote_notes': self.quote_notes,
            'quote_availability': self.quote_availability,
            'quote_capacity': self.quote_capacity,
            'quote_certifications': self.quote_certifications,
            'quote_experience': self.quote_experience,
            'status': self.status,
        }


# ── PURCHASE ORDER ────────────────────────────────────────────────────────────

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id             = db.Column(db.String(36), primary_key=True, default=new_id)
    company_id     = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    procurement_id = db.Column(db.String(36), db.ForeignKey('procurements.id'), nullable=False)
    vendor_id      = db.Column(db.String(36), db.ForeignKey('vendors.id'), nullable=False)
    po_number      = db.Column(db.String(50), unique=True, nullable=False)
    total_amount   = db.Column(db.Numeric(15, 2))
    pdf_data       = db.Column(db.Text)   # base64 encoded PDF
    sent_at        = db.Column(db.DateTime)
    created_at     = db.Column(db.DateTime, default=now)

    procurement = db.relationship('Procurement', foreign_keys=[procurement_id])
    vendor      = db.relationship('Vendor', foreign_keys=[vendor_id])

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'procurement_id': self.procurement_id,
            'vendor_id': self.vendor_id,
            'vendor_name': self.vendor.company_name if self.vendor else None,
            'po_number': self.po_number,
            'total_amount': float(self.total_amount) if self.total_amount else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ── ACTIVITY LOG ──────────────────────────────────────────────────────────────

class Activity(db.Model):
    __tablename__ = 'activities'
    id             = db.Column(db.String(36), primary_key=True, default=new_id)
    company_id     = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    procurement_id = db.Column(db.String(36), db.ForeignKey('procurements.id'), nullable=True)
    user_id        = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    actor          = db.Column(db.String(255))   # user name or "System"
    action         = db.Column(db.String(255), nullable=False)
    detail         = db.Column(db.Text)
    timestamp      = db.Column(db.DateTime, default=now)

    user = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'procurement_id': self.procurement_id,
            'actor': self.actor,
            'action': self.action,
            'detail': self.detail,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }