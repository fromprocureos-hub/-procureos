"""
ProcureOS v2 — Vendor Routes
GET    /vendors
POST   /vendors
PUT    /vendors/<id>
DELETE /vendors/<id>
POST   /vendors/import-csv
"""
import io
import math
import pandas as pd
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Vendor, Activity

vendors_bp = Blueprint('vendors', __name__)


def log_activity(company_id, user_id, actor, action, detail=''):
    db.session.add(Activity(
        company_id=company_id,
        user_id=user_id,
        actor=actor,
        action=action,
        detail=detail
    ))


def current_user():
    return User.query.get(get_jwt_identity())


# ── GET ALL VENDORS ───────────────────────────────────────────────────────────

@vendors_bp.route('', methods=['GET'])
@jwt_required()
def get_vendors():
    user = current_user()
    if not user:
        return jsonify({'error': 'Not found'}), 404

    search   = request.args.get('search', '').strip().lower()
    category = request.args.get('category', '').strip().lower()
    page     = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    query = Vendor.query.filter_by(
        company_id=user.company_id,
        is_active=True
    )

    if search:
        query = query.filter(
            Vendor.company_name.ilike(f'%{search}%') |
            Vendor.contact_email.ilike(f'%{search}%') |
            Vendor.categories.ilike(f'%{search}%')
        )

    if category:
        query = query.filter(Vendor.categories.ilike(f'%{category}%'))

    total   = query.count()
    vendors = query.order_by(Vendor.company_name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return jsonify({
        'vendors': [v.to_dict() for v in vendors],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': math.ceil(total / per_page)
    })


# ── CREATE VENDOR ─────────────────────────────────────────────────────────────

@vendors_bp.route('', methods=['POST'])
@jwt_required()
def create_vendor():
    user = current_user()
    data = request.get_json()

    if not data or not data.get('company_name'):
        return jsonify({'error': 'Company name is required'}), 400

    # Deduplicate by email within company
    email = (data.get('contact_email') or '').strip().lower()
    if email:
        existing = Vendor.query.filter_by(
            company_id=user.company_id,
            contact_email=email
        ).first()
        if existing:
            return jsonify({'error': f'Vendor with email {email} already exists', 'vendor_id': existing.id}), 409
    cats = data.get('categories', [])
    if isinstance(cats, list):
        cats = ','.join(cats)

    vendor = Vendor(
        company_id=user.company_id,
        company_name=data['company_name'].strip(),
        contact_email=email or None,
        phone=data.get('phone', '').strip() or None,
        categories=cats,
        reliability_score=data.get('reliability_score', 80),
        notes=data.get('notes', '').strip() or None,
    )
    db.session.add(vendor)

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Vendor added',
        detail=vendor.company_name
    )

    db.session.commit()
    return jsonify({'vendor': vendor.to_dict()}), 201


# ── UPDATE VENDOR ─────────────────────────────────────────────────────────────

@vendors_bp.route('/<vendor_id>', methods=['PUT'])
@jwt_required()
def update_vendor(vendor_id):
    user   = current_user()
    vendor = Vendor.query.filter_by(
        id=vendor_id,
        company_id=user.company_id
    ).first()

    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404

    data = request.get_json()

    if 'company_name' in data:
        vendor.company_name = data['company_name'].strip()
    if 'contact_email' in data:
        vendor.contact_email = data['contact_email'].strip().lower() or None
    if 'phone' in data:
        vendor.phone = data['phone'].strip() or None
    if 'categories' in data:
        cats = data['categories']
        vendor.categories = ','.join(cats) if isinstance(cats, list) else cats
    if 'reliability_score' in data:
        vendor.reliability_score = data['reliability_score']
    if 'notes' in data:
        vendor.notes = data['notes'].strip() or None

    db.session.commit()
    return jsonify({'vendor': vendor.to_dict()})


# ── DELETE VENDOR (soft delete) ───────────────────────────────────────────────

@vendors_bp.route('/<vendor_id>', methods=['DELETE'])
@jwt_required()
def delete_vendor(vendor_id):
    user   = current_user()
    vendor = Vendor.query.filter_by(
        id=vendor_id,
        company_id=user.company_id
    ).first()

    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404

    vendor.is_active = False

    log_activity(
        company_id=user.company_id,
        user_id=user.id,
        actor=user.full_name,
        action='Vendor removed',
        detail=vendor.company_name
    )

    db.session.commit()
    return jsonify({'message': 'Vendor removed'})


# ── CSV IMPORT ────────────────────────────────────────────────────────────────

@vendors_bp.route('/import-csv', methods=['POST'])
@jwt_required()
def import_csv():
    user = current_user()

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    if file.content_length and file.content_length > 5 * 1024 * 1024:
        return jsonify({'error': 'File too large. Max 5MB'}), 400

    try:
        fn = file.filename.lower()
        if fn.endswith('.csv'):
            df = pd.read_csv(file)
        elif fn.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            return jsonify({'error': 'Use .csv or .xlsx files'}), 400

        if df.empty:
            return jsonify({'error': 'File is empty'}), 400

        # Auto-detect columns
        col_map = _detect_columns(df)

        if 'company_name' not in col_map:
            return jsonify({
                'error': 'Could not find a vendor name column.',
                'columns_found': list(df.columns)
            }), 400

        # Preview first 5 rows
        preview = []
        for _, row in df.head(5).iterrows():
            preview.append(_parse_row(row, col_map))

        # If preview_only param set, return preview
        if request.args.get('preview') == '1':
            return jsonify({
                'preview': preview,
                'total_rows': len(df),
                'columns_mapped': col_map
            })

        # Full import
        imported = 0
        skipped  = 0
        errors   = []

        for idx, row in df.iterrows():
            try:
                parsed = _parse_row(row, col_map)
                name   = parsed.get('company_name', '').strip()
                email  = parsed.get('contact_email', '').strip().lower()

                if not name:
                    skipped += 1
                    continue

                # Deduplicate by email
                if email:
                    existing = Vendor.query.filter_by(
                        company_id=user.company_id,
                        contact_email=email
                    ).first()
                    if existing:
                        skipped += 1
                        continue

                cats = parsed.get('categories', '')
                vendor = Vendor(
                    company_id=user.company_id,
                    company_name=name,
                    contact_email=email or None,
                    phone=parsed.get('phone', '').strip() or None,
                    categories=cats,
                    reliability_score=parsed.get('reliability_score', 80),
                )
                db.session.add(vendor)
                imported += 1

            except Exception as e:
                errors.append(f'Row {idx + 2}: {str(e)}')
                continue

        log_activity(
            company_id=user.company_id,
            user_id=user.id,
            actor=user.full_name,
            action='Vendors imported',
            detail=f'{imported} imported, {skipped} skipped'
        )

        db.session.commit()

        return jsonify({
            'imported': imported,
            'skipped': skipped,
            'errors': errors[:10],
            'message': f'Successfully imported {imported} vendors.'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _detect_columns(df):
    """Auto-detect column roles from header names."""
    KEYWORDS = {
        'company_name':      ['company_name', 'company', 'vendor', 'name',
                              'supplier', 'business', 'firm'],
        'contact_email':     ['email', 'contact_email', 'e-mail', 'mail'],
        'phone':             ['phone', 'tel', 'mobile', 'contact_number'],
        'categories':        ['categories', 'category', 'type', 'segment',
                              'industry', 'product_type'],
        'reliability_score': ['reliability', 'reliability_score', 'score',
                              'rating', 'on_time'],
    }
    cols_lower = {str(c).lower().strip(): c for c in df.columns}
    mapping    = {}
    used       = set()

    for role, keywords in KEYWORDS.items():
        for kw in keywords:
            for lc, orig in cols_lower.items():
                if orig in used:
                    continue
                if kw == lc or kw in lc or lc in kw:
                    mapping[role] = orig
                    used.add(orig)
                    break
            if role in mapping:
                break

    return mapping


def _parse_row(row, col_map):
    def ss(val):
        if val is None:
            return ''
        import math as _math
        if isinstance(val, float) and _math.isnan(val):
            return ''
        return str(val).strip()

    def sf(val, default=80):
        try:
            return float(ss(val))
        except Exception:
            return default

    result = {}
    if 'company_name' in col_map:
        result['company_name'] = ss(row[col_map['company_name']])
    if 'contact_email' in col_map:
        result['contact_email'] = ss(row[col_map['contact_email']]).lower()
    if 'phone' in col_map:
        result['phone'] = ss(row[col_map['phone']])
    if 'categories' in col_map:
        result['categories'] = ss(row[col_map['categories']])
    if 'reliability_score' in col_map:
        result['reliability_score'] = sf(row[col_map['reliability_score']])

    return result