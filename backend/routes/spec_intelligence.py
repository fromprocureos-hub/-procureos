from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import os
import json
import re
import requests

spec_bp = Blueprint('spec', __name__)

@spec_bp.route('/spec-check', methods=['POST'])
@jwt_required()
def check_spec():
    data = request.get_json()
    item_name = data.get('item_name', '')
    quantity = data.get('quantity', '')
    unit = data.get('unit', '')
    deadline = data.get('deadline', '')
    notes = data.get('notes', '')

    system_prompt = f"""You are a procurement intelligence system. Analyze this RFQ and return warnings as JSON.

RFQ DETAILS:
Item: {item_name}
Quantity: {quantity} {unit}
Deadline: {deadline}
Notes: {notes}

Return a JSON array of up to 3 warnings. Each warning must have these exact keys with string values in double quotes:
- "type": one of "deadline", "overspec", "quantity", "missing_info", "vague"
- "severity": one of "high", "medium"
- "message": a single sentence describing the issue
- "impact": the consequence of this issue
- "fix": one actionable sentence on how to fix it

If the RFQ looks fine, return an empty array: []

IMPORTANT: Every value must be a properly quoted JSON string. Do not return any text outside the JSON array."""

    try:
        groq_key = os.getenv("GROQ_API_KEY")
        print(f'[GROQ] spec-check called, key present: {bool(groq_key)}')
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {groq_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a JSON API. You only return valid JSON. Never return unquoted string values. Always wrap all string values in double quotes.'
                    },
                    {
                        'role': 'user',
                        'content': system_prompt
                    }
                ],
                'temperature': 0.1,
                'max_tokens': 800,
                'response_format': {'type': 'json_object'}
            },
            timeout=15
        )
        print(f'[GROQ] spec-check status: {response.status_code}')
        result = response.json()
        text = result['choices'][0]['message']['content'].strip()
        print(f'[GROQ] spec-check raw: {repr(text[:200])}')
        parsed = json.loads(text)
        # response_format returns an object, extract the array
        if isinstance(parsed, dict):
            warnings = parsed.get('warnings', parsed.get('items', parsed.get('results', [])))
            # if still a dict with no known key, try to find any list value
            if not isinstance(warnings, list):
                for v in parsed.values():
                    if isinstance(v, list):
                        warnings = v
                        break
                else:
                    warnings = []
        else:
            warnings = parsed
        return jsonify({'warnings': warnings})
    except Exception as e:
        print(f'[GROQ ERROR] spec-check: {e}')
        return jsonify({'warnings': []})


@spec_bp.route('/vendor-warning', methods=['POST'])
@jwt_required()
def vendor_warning():
    data = request.get_json()
    vendor_name = data.get('vendor_name', '')
    vendor_reliability = data.get('vendor_reliability', 80)
    category = data.get('category', '')
    deadline = data.get('deadline', '')
    available_vendors = data.get('available_vendors', [])
    item_name = data.get('item_name', '')

    prompt = f"""You are a procurement risk analyst. A buyer is about to send an RFQ to only ONE vendor.

SITUATION:
- Selected vendor: {vendor_name}
- Vendor reliability score: {vendor_reliability}%
- Item being purchased: {item_name}
- Item category: {category}
- Deadline: {deadline}
- Other available vendors in their list: {len(available_vendors)}

Write a short 2-sentence warning about the risk of using only this vendor.
Be specific to the reliability score and category.

Return ONLY this JSON object with all string values properly quoted:
{{"warning": "your warning here", "risk_level": "high"}}

risk_level must be one of: high, medium, low"""

    try:
        groq_key = os.getenv("GROQ_API_KEY")
        print(f'[GROQ] vendor-warning called, key present: {bool(groq_key)}')
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {groq_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a JSON API. Return only valid JSON with all string values in double quotes.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.3,
                'max_tokens': 200,
                'response_format': {'type': 'json_object'}
            },
            timeout=15
        )
        print(f'[GROQ] vendor-warning status: {response.status_code}')
        result = response.json()
        text = result['choices'][0]['message']['content'].strip()
        parsed = json.loads(text)
        return jsonify(parsed)
    except Exception as e:
        print(f'[GROQ ERROR] vendor-warning: {e}')
        return jsonify({
            'warning': f'{vendor_name} is your only option if something goes wrong. Adding 2 more vendors takes one click and protects your deadline.',
            'risk_level': 'medium'
        })