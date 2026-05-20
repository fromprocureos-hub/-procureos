from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64
import os
import json
import io
from groq import Groq

upload_bp = Blueprint('upload', __name__)
client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',  # images
    'pdf',                                          # pdf
    'csv',                                          # csv
    'xlsx', 'xls',                                  # excel
    'docx', 'doc'                                   # word
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_vendors_with_ai(text):
    prompt = f"""You are a procurement assistant. Extract all vendor/supplier information from this text.

Return ONLY a valid JSON object, nothing else:
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

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return json.loads(raw.strip())

def extract_vendors_from_image(image_data, mime_type):
    base64_image = base64.b64encode(image_data).decode('utf-8')
    prompt = """Extract all vendor/supplier information from this image (WhatsApp screenshot, invoice, quote, business card, handwritten note, etc).

Return ONLY valid JSON:
{
  "vendors": [
    {
      "name": "vendor name",
      "phone": "phone or empty",
      "email": "email or empty",
      "category": "category or empty",
      "products": [
        {
          "name": "product name",
          "quantity": "qty or empty",
          "unit": "unit or empty",
          "price": 0,
          "currency": "PKR or empty",
          "notes": "terms or empty"
        }
      ]
    }
  ],
  "confidence": 0.9,
  "raw_text": "text you read from image"
}"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}},
                {"type": "text", "text": prompt}
            ]
        }],
        max_tokens=2000,
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return json.loads(raw.strip())

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
        # --- IMAGES ---
        if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}:
            mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
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
                # scanned PDF — convert first page to image
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

    except json.JSONDecodeError:
        return jsonify({'error': 'AI could not parse the file. Try a clearer file.'}), 422
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def build_summary(vendors, filename):
    if not vendors:
        return f"I couldn't find any vendor information in '{filename}'. Try a different file."
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

    summary = f"I found {len(vendors)} vendor{'s' if len(vendors) > 1 else ''}: "
    summary += '; '.join(parts[:5])
    if len(vendors) > 5:
        summary += f' and {len(vendors) - 5} more'
    summary += '. What would you like to do with them?'
    return summary