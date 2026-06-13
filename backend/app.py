"""
ProcureOS v2 — Main Flask App
"""
import os
import atexit
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / '.env', override=True)

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from models import db
from routes.auth import auth_bp
from routes.vendor_lists import vendor_lists_bp
from routes.upload import upload_bp
from routes.vendors import vendors_bp
from routes.procurements import procurements_bp
from routes.spec_intelligence import spec_bp
from routes.quotes import quotes_bp
from routes.po import po_bp
from routes.reminders import reminders_bp

# ── CREATE APP ────────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)

    # Config
    app.config['SECRET_KEY']                    = os.environ.get('SECRET_KEY', 'dev-secret')
    app.config['JWT_SECRET_KEY']                = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-secret')
    app.config['JWT_ACCESS_TOKEN_EXPIRES']      = timedelta(days=7)
    app.config['SQLALCHEMY_DATABASE_URI']       = os.environ.get('DATABASE_URL', 'sqlite:///procureos.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS']     = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

    # Fix Railway postgres:// → postgresql://
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config[
            'SQLALCHEMY_DATABASE_URI'
        ].replace('postgres://', 'postgresql://', 1)

    # Extensions
    db.init_app(app)
    JWTManager(app)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    @app.after_request
    def cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        return response

    @app.before_request
    def handle_preflight():
        from flask import request, Response
        if request.method == 'OPTIONS':
            return Response('', 204, {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
            })

    # Blueprints
    # Blueprints
    app.register_blueprint(auth_bp,          url_prefix='/auth')
    app.register_blueprint(vendors_bp,       url_prefix='/vendors')
    app.register_blueprint(spec_bp, url_prefix='/api')
    app.register_blueprint(procurements_bp,  url_prefix='/procurements')
    app.register_blueprint(quotes_bp,        url_prefix='/api/quote')
    app.register_blueprint(po_bp,            url_prefix='/po')
    app.register_blueprint(reminders_bp,     url_prefix='/api')
    app.register_blueprint(vendor_lists_bp)
    app.register_blueprint(upload_bp)

    # Health check
    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'version': '2.0'})
  
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        from flask import send_from_directory
        static_folder = os.path.join(os.path.dirname(__file__), 'static')
        api_prefixes = ['auth/', 'vendors/', 'quote-submit', 'vendor-lists', 'upload', 'po/', 'api/']
        if any(path.startswith(p) for p in api_prefixes):
            from flask import abort
            abort(404)
        if path and os.path.exists(os.path.join(static_folder, path)):
            return send_from_directory(static_folder, path)
        return send_from_directory(static_folder, 'index.html')

    # Init DB + seed industries
    with app.app_context():
        db.create_all()
        _seed_industries()
        print('[DB] Tables ready.')

    # Scheduler
    _start_scheduler(app)

    return app


# ── SEED INDUSTRIES ───────────────────────────────────────────────────────────

def _seed_industries():
    from models import IndustryConfig
    if IndustryConfig.query.count() > 0:
        return

    industries = [
        ("Restaurants & Cloud Kitchens",    70, 95, 60, 40, "Standard",  "Produce,Protein,Dairy,Packaging,Cleaning,Beverages"),
        ("Cafes & Bakeries",                75, 90, 70, 40, "Standard",  "Coffee Beans,Flour,Sugar,Packaging,Equipment"),
        ("Bars & Nightclubs",               70, 80, 50, 40, "Standard",  "Liquor,Mixers,Glassware,Cleaning,Ice"),
        ("Food Processing & Packaging",     65, 85, 90, 80, "Advanced",  "Raw Materials,Packaging Film,Labels,Machinery Parts"),
        ("Grocery & Convenience Stores",    90, 75, 60, 50, "Standard",  "Dry Goods,Frozen,Beverages,Household,Snacks"),
        ("Clothing & Fashion Retail",       85, 70, 75, 40, "Standard",  "Fabric,Garments,Hangers,Packaging,Tags"),
        ("E-commerce / DTC Brands",         80, 75, 70, 50, "Standard",  "Packaging,Shipping Supplies,Labels,Inventory"),
        ("Electronics & Mobile Retail",     75, 70, 85, 60, "Advanced",  "Devices,Accessories,Cables,Display Units"),
        ("Furniture & Home Goods",          80, 65, 85, 40, "Standard",  "Wood,Upholstery,Hardware,Foam,Finishing"),
        ("Jewelry & Accessories",           70, 60, 95, 50, "Advanced",  "Precious Metals,Stones,Packaging,Display"),
        ("Auto Repair & Service",           75, 85, 90, 60, "Standard",  "Parts,Fluids,Tires,Tools,Cleaning"),
        ("Auto Parts Distributors",         80, 80, 85, 60, "Standard",  "OEM Parts,Aftermarket,Lubricants,Batteries"),
        ("Car Wash & Detailing",            85, 70, 60, 40, "Standard",  "Chemicals,Towels,Machines,Water Systems"),
        ("Tire Manufacturing & Dealers",    70, 80, 90, 70, "Advanced",  "Rubber,Steel Wire,Chemicals,Molds"),
        ("Light Manufacturing (General)",   75, 80, 85, 70, "Advanced",  "Raw Materials,MRO,Packaging,Components"),
        ("Metal Fabrication & Welding",     70, 85, 90, 80, "Advanced",  "Steel,Aluminum,Gas,Electrodes,Tools"),
        ("Plastic & Rubber Manufacturing",  75, 80, 85, 70, "Advanced",  "Resin,Additives,Molds,Colorants"),
        ("Textile & Apparel Manufacturing", 80, 75, 85, 60, "Standard",  "Yarn,Dyes,Fabric,Buttons,Zippers"),
        ("Woodworking & Carpentry",         80, 70, 85, 50, "Standard",  "Lumber,Plywood,Hardware,Varnish,Glue"),
        ("Printing & Signage",              85, 75, 80, 50, "Standard",  "Paper,Ink,Vinyl,Boards,Machines"),
        ("General Construction",            70, 95, 85, 80, "Advanced",  "Cement,Steel,Lumber,Tools,Safety Gear"),
        ("Electrical Contractors",          75, 90, 90, 90, "Advanced",  "Wire,Panels,Conduit,Fixtures,PPE"),
        ("Plumbing & HVAC",                 75, 90, 90, 85, "Advanced",  "Pipes,Fittings,Units,Sheet Metal,Tools"),
        ("Roofing & Waterproofing",         75, 85, 90, 80, "Advanced",  "Shingles,Membrane,Sealant,Nails,Safety"),
        ("Landscaping & Lawn Care",         85, 70, 60, 40, "Standard",  "Plants,Fertilizer,Tools,Mulch,Equipment"),
        ("Painting & Drywall",              85, 75, 75, 50, "Standard",  "Paint,Primer,Tape,Tools,Drop Cloths"),
        ("Flooring & Tiling",               80, 80, 90, 60, "Standard",  "Tile,Adhesive,Grout,Underlayment,Tools"),
        ("Medical Clinics & Urgent Care",   60, 85, 95, 95, "Advanced",  "Disposables,Devices,Sterilization,Pharma"),
        ("Dental Practices",                60, 80, 95, 95, "Advanced",  "Chairs,Tools,Consumables,X-ray Film"),
        ("Veterinary Clinics",              65, 80, 90, 90, "Advanced",  "Medicine,Food,Surgical Tools,Kennels"),
        ("Pharmacies & Drugstores",         70, 85, 95, 95, "Advanced",  "Medicines,OTC,Cosmetics,Packaging"),
        ("Medical Labs & Diagnostics",      60, 80, 95, 95, "Advanced",  "Reagents,Equipment,Tubes,Calibration"),
        ("Physical Therapy & Rehab",        70, 75, 90, 80, "Advanced",  "Equipment,Bands,Tables,Disposables"),
        ("Hotels & Motels",                 75, 80, 85, 60, "Standard",  "Linens,Toiletries,F&B,Cleaning,Maintenance"),
        ("Short-Term Rentals / Airbnb",     85, 70, 70, 40, "Standard",  "Linens,Toiletries,Cleaning,Decor,Repairs"),
        ("Event Venues & Catering",         75, 90, 80, 60, "Standard",  "Chairs,Tables,Linens,Decor,F&B"),
        ("Travel Agencies & Tourism",       80, 70, 75, 50, "Standard",  "Packaging,Printing,Office,Promotional"),
        ("Salons & Barbershops",            80, 70, 85, 50, "Standard",  "Color,Shampoo,Tools,Towels,Chairs"),
        ("Spas & Wellness Centers",         75, 70, 90, 60, "Standard",  "Oils,Stones,Linens,Creams,Equipment"),
        ("Gyms & Fitness Centers",          80, 70, 85, 60, "Standard",  "Equipment,Mats,Supplements,Towels,Cleaning"),
        ("Nail & Beauty Salons",            85, 65, 80, 50, "Standard",  "Polish,Tools,Chairs,Disposables,Lamps"),
        ("IT Services & MSPs",              75, 70, 90, 70, "Advanced",  "Hardware,Licenses,Cloud,Tools,Cables"),
        ("Software & SaaS Companies",       70, 60, 85, 60, "Standard",  "Cloud,Tools,Hardware,Office,Swag"),
        ("Marketing & Ad Agencies",         80, 70, 75, 50, "Standard",  "Printing,Software,Freelancers,Office"),
        ("Law Firms & Legal Services",      70, 65, 90, 70, "Standard",  "Office,Software,Printing,Research"),
        ("Accounting & Bookkeeping",        80, 65, 85, 60, "Standard",  "Software,Office,Printing,Storage"),
        ("Consulting & Coaching",           80, 60, 80, 50, "Standard",  "Office,Software,Travel,Materials"),
        ("Architecture & Design",           75, 70, 90, 60, "Standard",  "Software,Materials,Printing,Models"),
        ("Engineering Services",            70, 75, 90, 80, "Advanced",  "Software,Prototyping,Testing,Components"),
        ("Research & Development",          60, 75, 95, 90, "Advanced",  "Chemicals,Equipment,Prototypes,Sensors"),
        ("Private Schools & Tutoring",      75, 70, 85, 60, "Standard",  "Books,Furniture,Tech,Supplies,Food"),
        ("Vocational & Trade Schools",      70, 75, 90, 70, "Advanced",  "Tools,Materials,Safety,Equipment"),
        ("Daycare & Childcare",             75, 70, 90, 70, "Standard",  "Toys,Food,Furniture,Cleaning,Supplies"),
        ("Agriculture & Farming",           80, 75, 75, 50, "Standard",  "Seed,Fertilizer,Equipment,Feed,Fuel"),
        ("Nurseries & Greenhouses",         85, 70, 80, 40, "Standard",  "Soil,Pots,Plants,Fertilizer,Tools"),
        ("Animal Husbandry / Livestock",    75, 80, 75, 50, "Standard",  "Feed,Medicine,Fencing,Equipment,Bedding"),
        ("Fishing & Aquaculture",           75, 80, 75, 50, "Standard",  "Feed,Nets,Equipment,Ice,Packaging"),
        ("Food Processing / Meat / Dairy",  70, 85, 90, 85, "Advanced",  "Raw Material,Packaging,Cold Storage,Chemicals"),
        ("Wine, Brewery & Distillery",      70, 75, 90, 70, "Advanced",  "Grapes/Grain,Yeast,Barrels,Bottles,Labels"),
        ("Trucking & Freight",              75, 90, 85, 70, "Standard",  "Fuel,Tires,Parts,Insurance,Permits"),
        ("Courier & Last-Mile Delivery",    80, 95, 75, 50, "Standard",  "Packaging,Fuel,Bikes/Vans,Labels,Uniforms"),
        ("Warehousing & Storage",           80, 75, 80, 60, "Standard",  "Racking,Pallets,Forklifts,Packaging,Safety"),
        ("Moving & Relocation",             85, 80, 75, 50, "Standard",  "Boxes,Tape,Trucks,Labor,Insurance"),
        ("Waste Management & Recycling",    75, 75, 70, 60, "Standard",  "Bins,Trucks,Sorting,Processing,Safety"),
        ("Solar & Renewable Energy",        65, 80, 90, 85, "Advanced",  "Panels,Inverters,Batteries,Mounting,Cable"),
        ("Oil & Gas Services",              60, 85, 95, 90, "Advanced",  "Pipe,Valves,Safety,Chemicals,Tools"),
        ("Mining & Quarrying",              65, 85, 95, 85, "Advanced",  "Explosives,Equipment,Safety,Vehicles"),
        ("Security Services",               75, 70, 90, 70, "Standard",  "Uniforms,Gear,Vehicles,Tech,Training"),
        ("Cleaning & Janitorial",           85, 70, 75, 50, "Standard",  "Chemicals,Equipment,Uniforms,Bags,Mops"),
        ("Pest Control",                    80, 75, 85, 60, "Standard",  "Chemicals,Traps,Vehicles,Safety,Uniforms"),
        ("Property Management",             80, 80, 75, 60, "Standard",  "Maintenance,Cleaning,Landscaping,Paint"),
        ("Real Estate Development",         70, 90, 85, 70, "Advanced",  "Materials,Labor,Fixtures,Landscaping"),
        ("Facility Management",             75, 85, 80, 60, "Standard",  "MRO,HVAC,Cleaning,Security,Lighting"),
        ("Call Centers & BPO",              80, 65, 75, 50, "Standard",  "Headsets,Chairs,Tech,Office,Refreshments"),
        ("Religious Organizations",         80, 60, 70, 40, "Standard",  "Office,Events,Food,Maintenance,Printing"),
        ("Non-Profits & NGOs",              90, 70, 75, 50, "Standard",  "Office,Events,Food,Transport,Printing"),
        ("Government Contractors",          60, 85, 90, 95, "Advanced",  "Everything,Compliance Tracking"),
        ("Arts, Crafts & Hobbies",          85, 60, 80, 40, "Standard",  "Supplies,Tools,Packaging,Display"),
        ("Music & Recording Studios",       75, 65, 90, 50, "Standard",  "Instruments,Cables,Software,Foam,Storage"),
        ("Film & Video Production",         70, 70, 90, 60, "Standard",  "Cameras,Lights,Props,Catering,Transport"),
        ("Photography",                     80, 65, 90, 50, "Standard",  "Cameras,Lenses,Printing,Frames,Props"),
        ("Pet Stores & Grooming",           80, 70, 85, 50, "Standard",  "Food,Toys,Grooming,Cages,Medicine"),
        ("Veterinary Supplies Distributor", 70, 80, 90, 85, "Advanced",  "Medicine,Equipment,Food,Surgical,Lab"),
        ("Aquarium & Fish Supply",          80, 70, 85, 50, "Standard",  "Tanks,Food,Filters,Chemicals,Decor"),
        ("Laundromats & Dry Cleaning",      85, 75, 80, 50, "Standard",  "Machines,Chemicals,Hangers,Bags,Tags"),
        ("Tailoring & Alterations",         85, 60, 85, 40, "Standard",  "Fabric,Thread,Buttons,Zippers,Machines"),
        ("Shoe Repair & Retail",            80, 65, 85, 50, "Standard",  "Leather,Soles,Glue,Polish,Laces"),
        ("Electronics Repair",              75, 70, 90, 60, "Standard",  "Screens,Chips,Tools,Solder,Adhesive"),
        ("Appliance Repair",                75, 80, 90, 60, "Standard",  "Parts,Tools,Testing,Chemicals,Uniforms"),
        ("Pool & Spa Services",             80, 75, 80, 50, "Standard",  "Chemicals,Pumps,Filters,Covers,Tools"),
        ("Boat & Marine Services",          70, 80, 90, 70, "Advanced",  "Paint,Parts,Safety,Rope,Electronics"),
        ("Aircraft Maintenance (Small)",    60, 85, 95, 95, "Advanced",  "Parts,Fluids,Tools,Documentation,Testing"),
        ("Rail & Transport Maintenance",    65, 85, 95, 90, "Advanced",  "Parts,Steel,Safety,Tools,Lubricants"),
        ("Cemetery & Funeral Services",     75, 70, 85, 60, "Standard",  "Caskets,Flowers,Urns,Vehicles,Printing"),
        ("Wedding & Event Planning",        75, 85, 80, 50, "Standard",  "Decor,Flowers,Catering,Rentals,Printing"),
        ("Catering & Food Trucks",          75, 90, 80, 60, "Standard",  "Food,Packaging,Equipment,Fuel,Permits"),
        ("Ice Cream & Dessert Shops",       80, 75, 75, 50, "Standard",  "Dairy,Flavoring,Cones,Cups,Machines"),
        ("Tobacco & Vape Shops",            85, 65, 70, 50, "Standard",  "Product,Packaging,Displays,Accessories"),
        ("Stationery & Office Supply",      85, 70, 75, 50, "Standard",  "Paper,Pens,Furniture,Tech,Coffee"),
        ("Other / General SMB",             80, 75, 80, 50, "Standard",  "Generic defaults"),
    ]

    for row in industries:
        name, pw, dw, qw, cw, tmpl, cats = row
        db.session.add(IndustryConfig(
            name=name,
            price_weight=pw,
            delivery_weight=dw,
            quality_weight=qw,
            compliance_weight=cw,
            default_template=tmpl,
            typical_categories=cats
        ))

    db.session.commit()
    print(f'[DB] Seeded {len(industries)} industries.')


# ── SCHEDULER ─────────────────────────────────────────────────────────────────

def _start_scheduler(app):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()

        def deadline_check():
            with app.app_context():
                from models import ProcurementVendor, Procurement
                from agents.email_agent import EmailAgent
                import os

                now      = datetime.now(timezone.utc)
                tomorrow = now + timedelta(hours=24)
                ea       = EmailAgent()
                base_url = os.environ.get('BASE_URL', 'http://localhost:5000')

                # Remind vendors 24h before deadline
                pending = ProcurementVendor.query.filter_by(status='emailed').all()
                for pv in pending:
                    proc = Procurement.query.get(pv.procurement_id)
                    if not proc or not proc.deadline:
                        continue
                    deadline = proc.deadline
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    if now < deadline <= tomorrow:
                        vendor = pv.vendor
                        if vendor and vendor.contact_email and pv.token:
                            portal_url   = f'{base_url}/quote/{pv.token}'
                            deadline_str = deadline.strftime('%B %d, %Y')
                            ea.send_reminder(
                                to=vendor.contact_email,
                                vendor_name=vendor.company_name,
                                item_name=proc.item_name,
                                deadline_str=deadline_str,
                                portal_url=portal_url
                            )
                            print(f'[SCHEDULER] Reminder sent to {vendor.contact_email}')

                # Auto-close overdue RFQs
                overdue = Procurement.query.filter(
                    Procurement.status == 'pending_quotes',
                    Procurement.deadline < now
                ).all()
                for proc in overdue:
                    proc.status = 'draft'
                    print(f'[SCHEDULER] Closed overdue RFQ: {proc.title}')

                db.session.commit()

        scheduler.add_job(deadline_check, 'interval', hours=1)
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())
        print('[SCHEDULER] Started.')
    except ImportError:
        print('[SCHEDULER] apscheduler not installed. pip install apscheduler')


# ── RUN ───────────────────────────────────────────────────────────────────────

app = create_app()

if __name__ == '__main__':
    import socket
    port = int(os.environ.get('PORT', 5000))
    def port_in_use(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', p)) == 0
    if port_in_use(port):
        port = 5001
    print(f'\n[SERVER] http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)