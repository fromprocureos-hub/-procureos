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

    system_prompt = f"""You are an elite procurement intelligence system trained on millions of RFQs across 19 industries. Your job is to protect the buyer from costly mistakes before the RFQ is sent.

BUYER'S RFQ:
Item: {item_name}
Quantity: {quantity} {unit}
Deadline: {deadline}
Additional Notes: {notes}

YOUR JOB:
Analyze this RFQ and identify UP TO 3 real issues that will either:
- Cost the buyer more money
- Reduce the number of suppliers who respond
- Cause confusion or delays

STRICT RULES:
1. QUANTITY: Only flag if genuinely abnormal for that item category.
2. DEADLINE: Only flag if genuinely impossible or expensive for that item.
3. MISSING INFO: Flag only critical missing details suppliers NEED to quote accurately.
4. OVER-SPECIFICATION: Flag requirements that unnecessarily restrict supplier pool.
5. VAGUE DESCRIPTION: Flag only if suppliers genuinely cannot quote without clarification.
6. IF THE RFQ IS FINE: Return empty array. Do not invent problems.

RESPONSE FORMAT:
Return ONLY a valid JSON array. No markdown. No explanation. No extra text.
Maximum 3 objects. Minimum 0.
Each object must have:
- type: "deadline" | "overspec" | "quantity" | "missing_info" | "vague"
- severity: "high" | "medium"
- message: ONE sentence. Direct. Specific to this exact item.
- impact: Real consequence. Include specific numbers or percentages where possible.
- fix: Exactly what to change or add. One sentence. Actionable.

Now analyze the RFQ above and return your JSON response."""

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
                'messages': [{'role': 'user', 'content': system_prompt}],
                'temperature': 0.1,
                'max_tokens': 800
            },
            timeout=15
        )
        print(f'[GROQ] spec-check status: {response.status_code}')
        result = response.json()
        text = result['choices'][0]['message']['content'].strip()
        text = re.sub(r'```json|```', '', text).strip()
        warnings = json.loads(text)
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

YOUR JOB:
Write ONE short, specific, honest warning message (2 sentences max) explaining the real risk of using only this vendor for this specific situation.

RULES:
- Be specific to the vendor reliability score and category
- If reliability is below 75% mention it directly
- If deadline is tight mention the risk of delays
- If category is competitive mention they could get better prices with competition
- Never be generic. Sound like a smart colleague warning them, not a system message

Return ONLY a JSON object:
{{
  "warning": "your 2 sentence warning here",
  "risk_level": "high" | "medium" | "low"
}}

No markdown. No explanation. Just JSON."""

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
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 200
            },
            timeout=15
        )
        print(f'[GROQ] vendor-warning status: {response.status_code}')
        result = response.json()
        text = result['choices'][0]['message']['content'].strip()
        text = re.sub(r'```json|```', '', text).strip()
        parsed = json.loads(text)
        return jsonify(parsed)
    except Exception as e:
        print(f'[GROQ ERROR] vendor-warning: {e}')
        return jsonify({
            'warning': f'{vendor_name} is your only option if something goes wrong. Adding 2 more vendors takes one click and protects your deadline.',
            'risk_level': 'medium'
        })