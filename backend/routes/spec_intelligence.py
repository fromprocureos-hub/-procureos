from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import os
import json
import requests
from models import db, User
from context import build_company_context, get_item_history

spec_bp = Blueprint('spec', __name__)


def groq(messages, max_tokens=400):
    r = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {os.getenv("GROQ_API_KEY")}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'llama-3.3-70b-versatile',
            'messages': messages,
            'temperature': 0.1,
            'max_tokens': max_tokens,
            'response_format': {'type': 'json_object'}
        },
        timeout=15
    )
    result = r.json()
    if 'error' in result:
        raise Exception(result['error']['message'])
    return json.loads(result['choices'][0]['message']['content'])


def get_company_id():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    return user.company_id if user else None


@spec_bp.route('/spec-check', methods=['POST'])
@jwt_required()
def check_spec():
    d = request.get_json()
    company_id = get_company_id()
    ctx = build_company_context(company_id)
    item_history = get_item_history(company_id, d.get('item_name', ''))
    prompt = (
        f"{ctx}\n{item_history}\n\n"
        f"Analyze this RFQ for real procurement issues only. "
        f'Return {{"warnings":[{{"type":"vague|missing_info|quantity|deadline",'
        f'"severity":"high|medium","message":"issue","impact":"consequence","fix":"fix"}}]}}. '
        f"Max 3. Empty array if fine.\n"
        f"IGNORE: unit naming style, minor wording. "
        f"Only flag industry mismatch if item could cause serious legal or safety risk. "
        f"Never flag office supplies, IT equipment, or general business items.\n"
        f"Item:{d.get('item_name')} Qty:{d.get('quantity')} {d.get('unit')} "
        f"Deadline:{d.get('deadline')} Notes:{d.get('notes','')}"
    )
    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=400)
        warnings = parsed.get('warnings', [])
        if not isinstance(warnings, list):
            warnings = next((v for v in parsed.values() if isinstance(v, list)), [])
        return jsonify({'warnings': warnings})
    except Exception as e:
        print(f'[GROQ ERROR] spec-check: {e}')
        return jsonify({'warnings': []})


@spec_bp.route('/rfq-rewrite', methods=['POST'])
@jwt_required()
def rfq_rewrite():
    d = request.get_json()
    company_id = get_company_id()
    ctx = build_company_context(company_id)
    item_history = get_item_history(company_id, d.get('item_name', ''))
    warnings = d.get('warnings', [])
    fixes = '; '.join([w['fix'] for w in warnings])
    auto_deadline = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
    prompt = (
        f"{ctx}\n{item_history}\n\n"
        f"Fix this RFQ. Use company history to suggest realistic quantity and specs.\n"
        f'Return {{"item_name":"...","quantity":"number","unit":"...","notes":"detailed specs","changes_summary":"one sentence"}}.\n'
        f"Original - Item:{d.get('item_name')} Qty:{d.get('quantity')} {d.get('unit')} Notes:{d.get('notes','')}\n"
        f"Fixes: {fixes}"
    )
    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=300)
        parsed['deadline'] = auto_deadline
        return jsonify({'rewritten': parsed})
    except Exception as e:
        print(f'[GROQ ERROR] rfq-rewrite: {e}')
        return jsonify({'error': str(e)}), 500


@spec_bp.route('/vendor-warning', methods=['POST'])
@jwt_required()
def vendor_warning():
    d = request.get_json()
    vendor_name = d.get('vendor_name', '')
    company_id = get_company_id()
    ctx = build_company_context(company_id)
    prompt = (
        f"{ctx}\n\n"
        f'Single vendor risk warning. Return {{"warning":"2 sentences","risk_level":"high|medium|low"}}.\n'
        f"Vendor:{vendor_name} Reliability:{d.get('vendor_reliability')}% "
        f"Item:{d.get('item_name')} Category:{d.get('category')} "
        f"Deadline:{d.get('deadline')} Other vendors:{len(d.get('available_vendors', []))}"
    )
    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=150)
        return jsonify(parsed)
    except Exception as e:
        print(f'[GROQ ERROR] vendor-warning: {e}')
        return jsonify({
            'warning': f'{vendor_name} is your only option. Adding 2 more vendors protects your deadline.',
            'risk_level': 'medium'
        })