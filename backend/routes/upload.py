from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64
import os
import json
import re
import io
import requests

upload_bp = Blueprint('upload', __name__)

GROQ_API_KEY = lambda: os.environ.get('GROQ_API_KEY')
TEXT_MODEL = 'llama-3.3-70b-versatile'
VISION_MODEL = 'meta-llama/llama-4-maverick-17b-128e-instruct'  # Groq vision model

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
    'pdf', 'csv', 'xlsx', 'xls', 'docx', 'doc'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def call_groq(messages, model, max_tokens=2000):
    response = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {GROQ_API_KEY()}',
            'Content-Type': 'application/json'
        },
        json={
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': 0.1
        },
        timeout=30
    )
    print(f'[UPLOAD] Groq status: {response.status_code}, model: {model}')
    result = response.json()
    if 'error' in result:
        print(f'[UPLOAD] Groq error: {result["error"]}')
        raise Exception(result['error'].get('message', 'Groq error'))
    return result['choices'][0]['message']['content'].strip()

def parse_json_response(raw):
    # Remove markdown fences
    text = re.sub(r'```json|```', '', raw).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try extracting JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f'Could not parse JSON from: {text[:200]}')

def extract_vendors_with_ai(text):
    prompt = f"""You are a procurement assistant. Extract all vendor/supplier information from this text.

Return ONLY a valid JSON object:
{{
  "vendors": [
    {{
      "name": "vendor company name",
      "phone": "phone number or empty string",
      "email": "email or empty string",
      "category": "product category or empty string",
      "products": [
        {{
          "name": "product name",
          "quantity": "quantity as string or empty",
          "unit": "unit or empty",
          "price": 0,
          "currency": "PKR or USD or empty",
          "notes": "any terms or empty"
        }}
      ]
    }}
  ],
  "confidence": 0.9
}}

Text to extract from:
{text[:4000]}

Rules:
- If no vendors found, return empty vendors array
- Always return valid JSON only
- No markdown, no explanation"""

    raw = call_groq([{"role": "user", "content": prompt}], TEXT_MODEL)
    return parse_json_response(raw)

def extract_vendors_from_image(image_data, mime_type):
    base64_image = base64.b64encode(image_data).decode('utf-8')
    prompt = """You are a procurement assistant. Look at this image carefully — it could be a WhatsApp screenshot, invoice, quote, business card, or handwritten note.

Extract ALL vendor/supplier information visible in the image.

Return ONLY this valid JSON object:
{
  "vendors": [
    {
      "name": "vendor name",
      "phone": "phone or empty string",
      "email": "email or empty string",
      "category": "category or empty string",
      "products": [
        {
          "name": "product name",
          "quantity": "qty or empty string",
          "unit": "unit or empty string",
          "price": 0,
          "currency": "PKR or empty string",
          "notes": "terms or empty string"
        }
      ]
    }
  ],
  "confidence": 0.9,
  "raw_text": "all text you can read from the image"
}

No markdown. No explanation. Just JSON."""

    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
            },
            {
                "type": "text",
                "text": prompt
            }
        ]
    }]

    raw = call_groq(messages, VISION_MODEL)
    print(f'[UPLOAD] vision raw: {repr(raw[:300])}')
    return parse_json_response(raw)

@upload_bp.route('/upload/file', methods=['POST'])
@jwt_required()
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file type'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    file_data = file.read()
    extracted = None

    try:
        # --- IMAGES (WhatsApp screenshots etc) ---
        if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}:
            mime_type = 'image/jpeg' if ext == 'jpg' else f'image/{ext}'
            extracted = extract_vendors_from_image(file_data, mime_type)

        # --- PDF ---
        elif ext == 'pdf':
            import pdfplumber
            text = ''
            with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or '') + '\n'
            if text.strip():
                extracted = extract_vendors_with_ai(text)
            else:
                extracted = extract_vendors_from_image(file_data, 'application/pdf')

        # --- CSV ---
        elif ext == 'csv':
            import pandas as pd
            df = pd.read_csv(io.BytesIO(file_data))
            text = df.to_string(index=False)
            extracted = extract_vendors_with_ai(text)

        # --- EXCEL ---
        elif ext in {'xlsx', 'xls'}:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_data))
            text = df.to_string(index=False)
            extracted = extract_vendors_with_ai(text)

        # --- WORD ---
        elif ext in {'docx', 'doc'}:
            from docx import Document
            doc = Document(io.BytesIO(file_data))
            text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
            extracted = extract_vendors_with_ai(text)

        if not extracted:
            return jsonify({'error': 'Could not extract data from file'}), 422

        vendors = extracted.get('vendors', [])
        summary = build_summary(vendors, file.filename)

        return jsonify({
            'success': True,
            'extracted': extracted,
            'vendors': vendors,
            'message': summary,
            'file_type': ext
        })

    except json.JSONDecodeError as e:
        print(f'[UPLOAD] JSON error: {e}')
        return jsonify({'error': 'AI could not parse the file. Try a clearer image.'}), 422
    except Exception as e:
        print(f'[UPLOAD] Error: {e}')
        return jsonify({'error': str(e)}), 500


def build_summary(vendors, filename):
    if not vendors:
        return f"I couldn't find any vendor information in '{filename}'. Try a clearer image."
    parts = []
    for v in vendors:
        name = v.get('name', 'Unknown vendor')
        products = v.get('products', [])
        if products:
            lines = []
            for p in products:
                price = p.get('price', 0)
                pname = p.get('name', 'item')
                currency = p.get('currency', 'Rs.')
                if price:
                    lines.append(f"{pname} at {currency} {price}")
                else:
                    lines.append(pname)
            parts.append(f"{name} ({', '.join(lines[:2])})")
        else:
            parts.append(name)

    summary = f"Found {len(vendors)} vendor{'s' if len(vendors) > 1 else ''}: "
    summary += '; '.join(parts[:5])
    if len(vendors) > 5:
        summary += f' and {len(vendors) - 5} more'
    summary += '. What would you like to do with them?'
    return summary