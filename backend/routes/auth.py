"""
ProcureOS v2 — Auth Routes
POST /auth/register
POST /auth/login
GET  /auth/me
POST /auth/invite (admin only)
"""
import secrets
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from models import db, User, Company, IndustryConfig, Activity

auth_bp = Blueprint('auth', __name__)


def log_activity(company_id, user_id, actor, action, detail='', procurement_id=None):
    db.session.add(Activity(
        company_id=company_id,
        procurement_id=procurement_id,
        user_id=user_id,
        actor=actor,
        action=action,
        detail=detail
    ))


# ── REGISTER ──────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required = ['company_name', 'email', 'password', 'full_name', 'industry_id']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    email = data['email'].strip().lower()

    # Check email not already used
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    # Validate industry
    industry = IndustryConfig.query.get(data['industry_id'])
    if not industry:
        return jsonify({'error': 'Invalid industry selected'}), 400

    # Validate password length
    if len(data['password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    # Create company — copy industry defaults
    company = Company(
        name=data['company_name'].strip(),
        industry_id=industry.id,
        price_weight=industry.price_weight,
        delivery_weight=industry.delivery_weight,
        quality_weight=industry.quality_weight,
        compliance_weight=industry.compliance_weight,
        default_template=industry.default_template,
    )
    db.session.add(company)
    db.session.flush()  # get company.id

    # Create first user as admin
    user = User(
        company_id=company.id,
        email=email,
        full_name=data['full_name'].strip(),
        role='admin',
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.flush()

    log_activity(
        company_id=company.id,
        user_id=user.id,
        actor=user.full_name,
        action='Company registered',
        detail=f'Industry: {industry.name}'
    )

    db.session.commit()

    token = create_access_token(identity=user.id)
    return jsonify({
        'token': token,
        'user': user.to_dict(),
        'company': company.to_dict()
    }), 201


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email    = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403

    company = Company.query.get(user.company_id)

    token = create_access_token(identity=user.id)
    return jsonify({
        'token': token,
        'user': user.to_dict(),
        'company': company.to_dict() if company else None
    })


# ── ME ────────────────────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    company = Company.query.get(user.company_id)
    return jsonify({
        'user': user.to_dict(),
        'company': company.to_dict() if company else None
    })


# ── INVITE TEAM MEMBER (admin only) ──────────────────────────────────────────

@auth_bp.route('/invite', methods=['POST'])
@jwt_required()
def invite():
    user_id = get_jwt_identity()
    admin   = User.query.get(user_id)
    if not admin or admin.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    required = ['email', 'full_name', 'role']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    email = data['email'].strip().lower()
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    if data['role'] not in ('admin', 'approver', 'requester'):
        return jsonify({'error': 'Invalid role'}), 400

    # Generate temporary password
    temp_password = secrets.token_urlsafe(10)

    new_user = User(
        company_id=admin.company_id,
        email=email,
        full_name=data['full_name'].strip(),
        role=data['role'],
        spend_limit=data.get('spend_limit', 0),
    )
    new_user.set_password(temp_password)
    db.session.add(new_user)

    log_activity(
        company_id=admin.company_id,
        user_id=admin.id,
        actor=admin.full_name,
        action='Team member invited',
        detail=f'{email} as {data["role"]}'
    )

    db.session.commit()

    return jsonify({
        'user': new_user.to_dict(),
        'temp_password': temp_password,
        'message': f'User created. Share this temporary password: {temp_password}'
    }), 201


# ── UPDATE PASSWORD ───────────────────────────────────────────────────────────

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    data    = request.get_json()

    if not user.check_password(data.get('current_password', '')):
        return jsonify({'error': 'Current password is incorrect'}), 400

    new_pw = data.get('new_password', '')
    if len(new_pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    user.set_password(new_pw)
    db.session.commit()
    return jsonify({'message': 'Password updated successfully'})


# ── GET ALL INDUSTRIES (public — used for registration dropdown) ──────────────

@auth_bp.route('/industries', methods=['GET'])
def get_industries():
    industries = IndustryConfig.query.order_by(IndustryConfig.name).all()
    return jsonify({'industries': [i.to_dict() for i in industries]})


# ── GET TEAM MEMBERS (admin only) ────────────────────────────────────────────

@auth_bp.route('/team', methods=['GET'])
@jwt_required()
def get_team():
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Not found'}), 404
    members = User.query.filter_by(company_id=user.company_id).all()
    return jsonify({'team': [m.to_dict() for m in members]})


# ── UPDATE TEAM MEMBER (admin only) ──────────────────────────────────────────

@auth_bp.route('/team/<member_id>', methods=['PUT'])
@jwt_required()
def update_member(member_id):
    user_id = get_jwt_identity()
    admin   = User.query.get(user_id)
    if not admin or admin.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    member = User.query.get(member_id)
    if not member or member.company_id != admin.company_id:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json()
    if 'role' in data:
        if data['role'] not in ('admin', 'approver', 'requester'):
            return jsonify({'error': 'Invalid role'}), 400
        member.role = data['role']
    if 'spend_limit' in data:
        member.spend_limit = data['spend_limit']
    if 'is_active' in data:
        member.is_active = data['is_active']
    if 'full_name' in data:
        member.full_name = data['full_name']

    db.session.commit()
    return jsonify({'user': member.to_dict()})