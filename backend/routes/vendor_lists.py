from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, VendorList, VendorListMember, Vendor, User
import uuid

vendor_lists_bp = Blueprint('vendor_lists', __name__)

def get_company_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get('company_id')
    user = User.query.get(identity)
    return user.company_id if user else None

@vendor_lists_bp.route('/vendor-lists', methods=['GET'])
@jwt_required()
def get_lists():
    company_id = get_company_id()
    lists = VendorList.query.filter_by(company_id=company_id).order_by(VendorList.created_at.desc()).all()
    result = []
    for l in lists:
        members = VendorListMember.query.filter_by(list_id=l.id).all()
        vendor_ids = [m.vendor_id for m in members]
        vendors = Vendor.query.filter(Vendor.id.in_(vendor_ids)).all() if vendor_ids else []
        result.append({
            'id': l.id,
            'name': l.name,
            'description': l.description,
            'vendor_count': len(vendors),
            'vendors': [{'id': v.id, 'company_name': v.company_name, 'contact_email': v.contact_email, 'reliability_score': float(v.reliability_score)} for v in vendors]
        })
    return jsonify({'lists': result})

@vendor_lists_bp.route('/vendor-lists', methods=['POST'])
@jwt_required()
def create_list():
    company_id = get_company_id()
    if not company_id:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    vl = VendorList(id=str(uuid.uuid4()), company_id=company_id, name=data['name'], description=data.get('description', ''))
    db.session.add(vl)
    db.session.commit()
    return jsonify({'id': vl.id, 'name': vl.name, 'message': 'Created'})

@vendor_lists_bp.route('/vendor-lists/<list_id>', methods=['DELETE'])
@jwt_required()
def delete_list(list_id):
    company_id = get_company_id()
    vl = VendorList.query.filter_by(id=list_id, company_id=company_id).first_or_404()
    db.session.delete(vl)
    db.session.commit()
    return jsonify({'message': 'Deleted'})

@vendor_lists_bp.route('/vendor-lists/<list_id>/members', methods=['POST'])
@jwt_required()
def add_member(list_id):
    company_id = get_company_id()
    vl = VendorList.query.filter_by(id=list_id, company_id=company_id).first_or_404()
    data = request.get_json()
    vendor_id = data.get('vendor_id')
    existing = VendorListMember.query.filter_by(list_id=list_id, vendor_id=vendor_id).first()
    if existing:
        return jsonify({'message': 'Already in list'})
    member = VendorListMember(id=str(uuid.uuid4()), list_id=list_id, vendor_id=vendor_id)
    db.session.add(member)
    db.session.commit()
    return jsonify({'message': 'Added'})

@vendor_lists_bp.route('/vendor-lists/<list_id>/members/<vendor_id>', methods=['DELETE'])
@jwt_required()
def remove_member(list_id, vendor_id):
    company_id = get_company_id()
    vl = VendorList.query.filter_by(id=list_id, company_id=company_id).first_or_404()
    member = VendorListMember.query.filter_by(list_id=list_id, vendor_id=vendor_id).first_or_404()
    db.session.delete(member)
    db.session.commit()
    return jsonify({'message': 'Removed'})

@vendor_lists_bp.route('/vendor-lists/<list_id>/top-vendors', methods=['GET'])
@jwt_required()
def get_top_vendors(list_id):
    company_id = get_company_id()
    vl = VendorList.query.filter_by(id=list_id, company_id=company_id).first_or_404()
    members = VendorListMember.query.filter_by(list_id=list_id).all()
    vendor_ids = [m.vendor_id for m in members]
    vendors = Vendor.query.filter(Vendor.id.in_(vendor_ids)).order_by(Vendor.reliability_score.desc()).all() if vendor_ids else []
    top3 = vendors[:3]
    return jsonify({
        'all_vendors': [{'id': v.id, 'company_name': v.company_name, 'contact_email': v.contact_email, 'reliability_score': float(v.reliability_score)} for v in vendors],
        'top3': [v.id for v in top3]
    })