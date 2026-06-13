from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import json
import requests
from models import db, User
from context import build_company_context, get_item_history

spec_bp = Blueprint('spec', __name__)

def groq(messages, max_tokens=400):
    r = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization': f'Bearer {os.getenv("GROQ_API_KEY")}', 'Content-Type': 'application/json'},
        json={'model': 'llama-3.3-70b-versatile', 'messages': messages, 'temperature': 0.1,
              'max_tokens': max_tokens, 'response_format': {'type': 'json_object'}},
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

    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""{ctx}
{item_history}

Analyze this RFQ for real procurement issues only. Return {{"warnings":[{{"type":"vague|missing_info|quantity|deadline","severity":"high|medium","message":"issue","impact":"consequence","fix":"fix"}}]}}. Max 3. Empty array if fine.
IGNORE: unit naming style, minor wording. Only flag industry mismatch if item could cause serious legal or safety risk (e.g. medical supplies for a construction company). Never flag office supplies, IT equipment, or general business items.
Only flag if it will genuinely cost money or reduce supplier responses.
Item:{d.get('item_name')} Qty:{d.get('quantity')} {d.get('unit')} Deadline:{d.get('deadline')} Notes:{d.get('notes','')}"""}
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
    from datetime import datetime, timedelta
    auto_deadline = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')

    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""{ctx}
{item_history}

from datetime import datetime, timedelta
auto_deadline = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')

        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""Fix this RFQ. Use company history to suggest realistic quantity and specs.
Return {{"item_name":"...","quantity":"number","unit":"...","notes":"detailed specs","changes_summary":"one sentence"}}.

Original — Item:{d.get('item_name')} Qty:{d.get('quantity')} {d.get('unit')} Notes:{d.get('notes','')}
Fixes: {fixes}"""}
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

    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""{ctx}

Single vendor risk warning. Return {{"warning":"2 sentences","risk_level":"high|medium|low"}}.
Vendor:{vendor_name} Reliability:{d.get('vendor_reliability')}% Item:{d.get('item_name')} Category:{d.get('category')} Deadline:{d.get('deadline')} Other vendors:{len(d.get('available_vendors',[]))}"""}
        ], max_tokens=150)
        return jsonify(parsed)
    except Exception as e:
        print(f'[GROQ ERROR] vendor-warning: {e}')
        return jsonify({'warning': f'{vendor_name} is your only option. Adding 2 more vendors protects your deadline.', 'risk_level': 'medium'})