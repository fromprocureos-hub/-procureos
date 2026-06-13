from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import os
import json
import requests

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


@spec_bp.route('/spec-check', methods=['POST'])
@jwt_required()
def check_spec():
    d = request.get_json()
    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""Analyze this RFQ for issues. Return {{"warnings":[{{"type":"vague|missing_info|quantity|deadline","severity":"high|medium","message":"issue","impact":"consequence","fix":"fix"}}]}}. Max 3 warnings. Empty array if fine.

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
    warnings = d.get('warnings', [])
    fixes = '; '.join([w['fix'] for w in warnings])
    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""Fix this RFQ based on the issues. Return {{"item_name":"...","quantity":"...","unit":"...","deadline":"...","notes":"...","changes_summary":"one sentence"}}.

Original — Item:{d.get('item_name')} Qty:{d.get('quantity')} {d.get('unit')} Deadline:{d.get('deadline')} Notes:{d.get('notes','')}
Fixes to apply: {fixes}"""}
        ], max_tokens=300)
        return jsonify({'rewritten': parsed})
    except Exception as e:
        print(f'[GROQ ERROR] rfq-rewrite: {e}')
        return jsonify({'error': str(e)}), 500


@spec_bp.route('/vendor-warning', methods=['POST'])
@jwt_required()
def vendor_warning():
    d = request.get_json()
    vendor_name = d.get('vendor_name', '')
    try:
        parsed = groq([
            {'role': 'system', 'content': 'Return only valid JSON.'},
            {'role': 'user', 'content': f"""Single vendor risk warning. Return {{"warning":"2 sentences","risk_level":"high|medium|low"}}.

Vendor:{vendor_name} Reliability:{d.get('vendor_reliability')}% Item:{d.get('item_name')} Category:{d.get('category')} Deadline:{d.get('deadline')} Other vendors available:{len(d.get('available_vendors',[]))}"""}
        ], max_tokens=150)
        return jsonify(parsed)
    except Exception as e:
        print(f'[GROQ ERROR] vendor-warning: {e}')
        return jsonify({'warning': f'{vendor_name} is your only option. Adding 2 more vendors protects your deadline.', 'risk_level': 'medium'})