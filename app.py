import os
import json
import requests
import random
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlencode
from werkzeug.utils import secure_filename
import pytz

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

from config import Config
from models import db, User, Service, GalleryImage, ScopeRequest, Booking, Review, UserRole, BookingStatus, ScopeStatus
from models import format_datetime, format_date, get_sast_time

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

# ---------- Helper functions for seeding ----------
def random_phone():
    prefixes = ['082', '083', '084', '071', '072', '073', '074', '076', '078', '079']
    return random.choice(prefixes) + ''.join(str(random.randint(0, 9)) for _ in range(7))

def random_date(start, end):
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

def seed_database():
    """Seed the database with sample data if it's empty."""
    with app.app_context():
        # Check if any services exist – if yes, skip seeding
        if Service.query.count() > 0:
            print("✅ Database already has services – skipping seed.")
            return

        print("🌱 Seeding database with sample data...")
        db.create_all()

        # ---------- Seed Customers ----------
        customers = [
            {
                'first_name': 'Thabo',
                'last_name': 'Mokoena',
                'email': 'thabo.m@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'location': 'Johannesburg, Gauteng'
            },
            {
                'first_name': 'Lindiwe',
                'last_name': 'Nkosi',
                'email': 'lindiwe.n@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'location': 'Cape Town, Western Cape'
            },
            {
                'first_name': 'Sipho',
                'last_name': 'Zulu',
                'email': 'sipho.z@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'location': 'Durban, KwaZulu-Natal'
            },
            {
                'first_name': 'Zanele',
                'last_name': 'Mthembu',
                'email': 'zanele.m@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'location': 'Pretoria, Gauteng'
            },
            {
                'first_name': 'Kagiso',
                'last_name': 'Mabaso',
                'email': 'kagiso.m@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'location': 'Port Elizabeth, Eastern Cape'
            }
        ]

        # ---------- Seed Providers ----------
        providers = [
            {
                'first_name': 'Nomsa',
                'last_name': 'Mthembu',
                'email': 'nomsa.m@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'business_name': 'Clean & Shine Services',
                'business_description': 'Professional cleaning services for homes and offices. We use eco-friendly products and have a 100% satisfaction guarantee.',
                'location': 'Johannesburg, Gauteng',
                'services': [
                    {
                        'title': 'Deep House Cleaning',
                        'category': 'Cleaning',
                        'description': 'Thorough cleaning of all rooms, including windows, carpets, and appliances. We bring all equipment and supplies.',
                        'price_min': 450.00,
                        'price_max': 850.00,
                        'price_type': 'fixed',
                        'image_seed': 'clean1'
                    },
                    {
                        'title': 'Office Cleaning (Weekly)',
                        'category': 'Cleaning',
                        'description': 'Regular office cleaning for small to medium businesses. Includes dusting, vacuuming, and sanitizing common areas.',
                        'price_min': 600.00,
                        'price_max': 1200.00,
                        'price_type': 'fixed',
                        'image_seed': 'clean2'
                    }
                ],
                'gallery': [
                    {'caption': 'After a deep clean', 'seed': 'gallery1'},
                    {'caption': 'Kitchen sparkling clean', 'seed': 'gallery2'},
                    {'caption': 'Office refresh', 'seed': 'gallery3'}
                ]
            },
            {
                'first_name': 'Bongani',
                'last_name': 'Mkhize',
                'email': 'bongani.m@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'business_name': 'Handyman Bongani',
                'business_description': 'Reliable handyman services for all your home repair needs. Plumbing, electrical, carpentry, and general maintenance.',
                'location': 'Cape Town, Western Cape',
                'services': [
                    {
                        'title': 'Plumbing Repairs',
                        'category': 'Repairs',
                        'description': 'Fix leaks, unblock drains, repair taps and toilets. Fast response and quality workmanship.',
                        'price_min': 350.00,
                        'price_max': 800.00,
                        'price_type': 'quote',
                        'image_seed': 'plumb1'
                    },
                    {
                        'title': 'Electrical Fixes',
                        'category': 'Repairs',
                        'description': 'Install lights, replace switches, fix faulty wiring. Certified electrician with 10 years experience.',
                        'price_min': 400.00,
                        'price_max': 900.00,
                        'price_type': 'quote',
                        'image_seed': 'elec1'
                    },
                    {
                        'title': 'General Handyman',
                        'category': 'Repairs',
                        'description': 'Painting, drywall repair, door fixes, furniture assembly, and more. Call for any small job.',
                        'price_min': 300.00,
                        'price_max': 700.00,
                        'price_type': 'hourly',
                        'image_seed': 'handy1'
                    }
                ],
                'gallery': [
                    {'caption': 'New bathroom faucet', 'seed': 'gallery4'},
                    {'caption': 'Rewired kitchen', 'seed': 'gallery5'},
                    {'caption': 'Painted living room', 'seed': 'gallery6'}
                ]
            },
            {
                'first_name': 'Precious',
                'last_name': 'Singh',
                'email': 'precious.s@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'business_name': 'Green Thumb Gardening',
                'business_description': 'Professional gardening and landscaping services. We transform your outdoor spaces into beautiful, low-maintenance gardens.',
                'location': 'Durban, KwaZulu-Natal',
                'services': [
                    {
                        'title': 'Garden Design & Installation',
                        'category': 'Gardening',
                        'description': 'Full garden design service including planting, paving, and irrigation systems. We create sustainable, water-wise gardens.',
                        'price_min': 1500.00,
                        'price_max': 5000.00,
                        'price_type': 'quote',
                        'image_seed': 'garden1'
                    },
                    {
                        'title': 'Lawn Maintenance',
                        'category': 'Gardening',
                        'description': 'Weekly or bi‑weekly lawn mowing, edging, and weeding. Keep your lawn looking pristine all year round.',
                        'price_min': 250.00,
                        'price_max': 450.00,
                        'price_type': 'fixed',
                        'image_seed': 'garden2'
                    }
                ],
                'gallery': [
                    {'caption': 'New garden installation', 'seed': 'gallery7'},
                    {'caption': 'Before and after', 'seed': 'gallery8'},
                    {'caption': 'Irrigation system', 'seed': 'gallery9'}
                ]
            },
            {
                'first_name': 'Ayanda',
                'last_name': 'Naidoo',
                'email': 'ayanda.n@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'business_name': 'Ayanda Tutoring',
                'business_description': 'Experienced tutor for mathematics, science, and English. Personalized lessons to help students excel.',
                'location': 'Pretoria, Gauteng',
                'services': [
                    {
                        'title': 'Mathematics Tutoring (Grades 8-12)',
                        'category': 'Tutoring',
                        'description': 'One-on-one tutoring focusing on problem-solving and exam preparation. Proven track record of improving grades.',
                        'price_min': 200.00,
                        'price_max': 350.00,
                        'price_type': 'hourly',
                        'image_seed': 'math1'
                    },
                    {
                        'title': 'English & Literature',
                        'category': 'Tutoring',
                        'description': 'Help with reading comprehension, essay writing, and literature analysis. Suitable for all ages.',
                        'price_min': 180.00,
                        'price_max': 300.00,
                        'price_type': 'hourly',
                        'image_seed': 'eng1'
                    }
                ],
                'gallery': [
                    {'caption': 'Lesson in progress', 'seed': 'gallery10'},
                    {'caption': 'Student resources', 'seed': 'gallery11'}
                ]
            },
            {
                'first_name': 'Sibusiso',
                'last_name': 'Mthethwa',
                'email': 'sibusiso.m@example.com',
                'password': 'password123',
                'phone': random_phone(),
                'business_name': 'Sibusiso Photography',
                'business_description': 'Professional photography for weddings, events, portraits, and commercial shoots. We capture moments that last a lifetime.',
                'location': 'Johannesburg, Gauteng',
                'services': [
                    {
                        'title': 'Wedding Photography',
                        'category': 'Photography',
                        'description': 'Full-day coverage of your wedding with a second shooter. Includes digital gallery and print rights.',
                        'price_min': 5000.00,
                        'price_max': 12000.00,
                        'price_type': 'quote',
                        'image_seed': 'wedding1'
                    },
                    {
                        'title': 'Portrait Sessions',
                        'category': 'Photography',
                        'description': 'Personal or family portraits in studio or on location. Perfect for special occasions or professional headshots.',
                        'price_min': 800.00,
                        'price_max': 1800.00,
                        'price_type': 'fixed',
                        'image_seed': 'portrait1'
                    }
                ],
                'gallery': [
                    {'caption': 'Wedding couple', 'seed': 'gallery12'},
                    {'caption': 'Family portrait', 'seed': 'gallery13'},
                    {'caption': 'Event coverage', 'seed': 'gallery14'}
                ]
            }
        ]

        # ----- Create customers -----
        for cust in customers:
            existing = User.query.filter_by(email=cust['email']).first()
            if not existing:
                user = User(
                    email=cust['email'],
                    password_hash=generate_password_hash(cust['password']),
                    first_name=cust['first_name'],
                    last_name=cust['last_name'],
                    phone=cust['phone'],
                    location=cust['location'],
                    role=UserRole.CUSTOMER,
                    is_oauth=False,
                    avatar_url=f"https://i.pravatar.cc/150?img={random.randint(1, 70)}"
                )
                db.session.add(user)
        db.session.commit()
        print("✅ Customers seeded.")

        # ----- Create providers, services, gallery -----
        for prov in providers:
            user = User.query.filter_by(email=prov['email']).first()
            if not user:
                user = User(
                    email=prov['email'],
                    password_hash=generate_password_hash(prov['password']),
                    first_name=prov['first_name'],
                    last_name=prov['last_name'],
                    phone=prov['phone'],
                    business_name=prov['business_name'],
                    business_description=prov['business_description'],
                    location=prov['location'],
                    role=UserRole.PROVIDER,
                    is_oauth=False,
                    avatar_url=f"https://i.pravatar.cc/150?img={random.randint(1, 70)}"
                )
                db.session.add(user)
                db.session.commit()  # flush to get user.id

            # Create services
            for svc in prov['services']:
                existing = Service.query.filter_by(provider_id=user.id, title=svc['title']).first()
                if not existing:
                    service = Service(
                        provider_id=user.id,
                        title=svc['title'],
                        category=svc['category'],
                        description=svc['description'],
                        price_min=svc['price_min'],
                        price_max=svc['price_max'],
                        price_type=svc['price_type'],
                        location=user.location,
                        is_active=True,
                        image_filename=f"https://picsum.photos/seed/{svc['image_seed']}/400/300"
                    )
                    db.session.add(service)

            # Gallery
            for img in prov['gallery']:
                existing = GalleryImage.query.filter_by(provider_id=user.id, caption=img['caption']).first()
                if not existing:
                    gallery_img = GalleryImage(
                        provider_id=user.id,
                        image_filename=f"https://picsum.photos/seed/{img['seed']}/400/300",
                        caption=img['caption']
                    )
                    db.session.add(gallery_img)

        db.session.commit()
        print("✅ Providers, services, and gallery seeded.")

        # ----- Create bookings and scope requests -----
        all_customers = User.query.filter_by(role=UserRole.CUSTOMER).all()
        all_providers = User.query.filter_by(role=UserRole.PROVIDER).all()
        all_services = Service.query.all()

        if not all_services:
            print("⚠️ No services found – skipping bookings.")
        else:
            for customer in all_customers:
                existing_bookings = Booking.query.filter_by(customer_id=customer.id).count()
                if existing_bookings < 3:
                    num_to_add = random.randint(1, 2)
                    for _ in range(num_to_add):
                        provider = random.choice(all_providers)
                        provider_services = [s for s in all_services if s.provider_id == provider.id]
                        if not provider_services:
                            continue
                        service = random.choice(provider_services)
                        status = random.choices(
                            [BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.COMPLETED, BookingStatus.CANCELLED],
                            weights=[0.3, 0.3, 0.3, 0.1],
                            k=1
                        )[0]
                        base_price = service.price_min or 300
                        agreed = round(base_price * random.uniform(0.9, 1.3), 2)
                        created = random_date(datetime.now() - timedelta(days=90), datetime.now())
                        scheduled = created + timedelta(days=random.randint(1, 10))
                        booking = Booking(
                            customer_id=customer.id,
                            provider_id=provider.id,
                            service_id=service.id,
                            scheduled_date=scheduled,
                            address=random.choice([customer.location, "123 Main St, " + customer.location.split(',')[0]]),
                            notes=random.choice(["Please bring your own equipment.", "Call me before coming.", "I'll be home all day."]),
                            agreed_price=agreed,
                            status=status,
                            created_at=created,
                            confirmed_at=created + timedelta(days=1) if status in [BookingStatus.CONFIRMED, BookingStatus.COMPLETED] else None,
                            completed_at=created + timedelta(days=5) if status == BookingStatus.COMPLETED else None,
                            cancelled_at=created + timedelta(days=1) if status == BookingStatus.CANCELLED else None,
                            cancellation_reason="Changed my mind" if status == BookingStatus.CANCELLED else None
                        )
                        db.session.add(booking)

            # Scope requests
            for customer in all_customers[:3]:
                if random.random() < 0.5:
                    provider = random.choice(all_providers)
                    provider_services = [s for s in all_services if s.provider_id == provider.id]
                    if not provider_services:
                        continue
                    service = random.choice(provider_services)
                    scope = ScopeRequest(
                        customer_id=customer.id,
                        provider_id=provider.id,
                        service_id=service.id,
                        description=f"I need help with {service.title.lower()}. Can you provide a quote? I need it done within the next two weeks.",
                        location=customer.location,
                        preferred_date=datetime.now() + timedelta(days=random.randint(3, 10)),
                        status=random.choice([ScopeStatus.REQUESTED, ScopeStatus.RESPONDED, ScopeStatus.ACCEPTED]),
                        estimated_cost=random.choice([None, round(random.uniform(300, 1200), 2)]),
                        estimated_hours=random.choice([None, round(random.uniform(1, 8), 1)]),
                        response_message=random.choice([None, "Sure, I can do that. Here's my estimate."]),
                        responded_at=datetime.now() - timedelta(days=random.randint(1, 5)) if random.choice([True, False]) else None,
                        created_at=datetime.now() - timedelta(days=random.randint(1, 15))
                    )
                    db.session.add(scope)

            db.session.commit()
            print("✅ Bookings and scope requests seeded.")

            # ----- Reviews -----
            completed_bookings = Booking.query.filter_by(status=BookingStatus.COMPLETED).all()
            for booking in completed_bookings:
                existing_review = Review.query.filter_by(booking_id=booking.id).first()
                if existing_review:
                    continue
                if random.random() < 0.7:
                    rating = random.randint(3, 5)
                    comment = random.choice([
                        "Excellent service! Very professional and efficient.",
                        "Great job, highly recommend.",
                        "Good quality, would book again.",
                        "Satisfied with the work.",
                        "Amazing experience, went above and beyond.",
                        "Quick response and good communication."
                    ])
                    review = Review(
                        booking_id=booking.id,
                        customer_id=booking.customer_id,
                        provider_id=booking.provider_id,
                        service_id=booking.service_id,
                        rating=rating,
                        comment=comment,
                        created_at=booking.completed_at + timedelta(days=random.randint(1, 3))
                    )
                    db.session.add(review)
                    if random.random() < 0.5:
                        review.provider_response = random.choice([
                            "Thank you for your kind review!",
                            "We appreciate your feedback.",
                            "Glad you were happy with the service.",
                            "It was a pleasure working with you.",
                            "Thank you, we hope to serve you again."
                        ])
                        review.response_date = review.created_at + timedelta(days=random.randint(1, 2))

            db.session.commit()
            print("✅ Reviews seeded.")

        print("🎉 Database seeding complete.")

# ---------- Create tables and seed on startup ----------
with app.app_context():
    db.create_all()
    # Create admin user if it doesn't exist
    admin_email = "admin@quickscope.com"
    if not User.query.filter_by(email=admin_email).first():
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash("admin123"),
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN
        )
        db.session.add(admin)
        db.session.commit()
        print("Default admin created: admin@quickscope.com / admin123")
    else:
        print("Admin user already exists.")

    # Seed the database with sample data if no services exist
    seed_database()

# ---------- Flask extensions ----------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

GOOGLE_CLIENT_ID = app.config['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = app.config['GOOGLE_CLIENT_SECRET']
GOOGLE_DISCOVERY_URL = app.config['GOOGLE_DISCOVERY_URL']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def provider_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.PROVIDER:
            flash('Provider access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.CUSTOMER:
            flash('Customer access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_image_url(filename):
    """Return the correct URL for an image, handling both local and external URLs."""
    if not filename:
        return None
    if filename.startswith(('http://', 'https://')):
        return filename
    return url_for('static', filename='uploads/' + filename)

@app.context_processor
def inject_globals():
    categories = db.session.query(Service.category).distinct().all()
    return dict(
        categories=[c[0] for c in categories if c[0]],
        currency=app.config['CURRENCY'],
        format_datetime=format_datetime,
        format_date=format_date,
        get_image_url=get_image_url
    )

# ==================== PUBLIC ROUTES ====================
@app.route('/')
def index():
    category = request.args.get('category')
    location = request.args.get('location')
    search = request.args.get('q')
    query = Service.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    if location:
        query = query.filter(Service.location.ilike(f'%{location}%'))
    if search:
        query = query.filter(
            or_(
                Service.title.ilike(f'%{search}%'),
                Service.description.ilike(f'%{search}%')
            )
        )
    services = query.order_by(Service.created_at.desc()).all()
    # If no filters, show only 3 random services
    if not (category or location or search):
        if len(services) > 3:
            services = random.sample(services, 3)
    total_services = Service.query.count()
    total_providers = User.query.filter_by(role=UserRole.PROVIDER).count()
    total_bookings = Booking.query.count()
    return render_template('index.html', services=services,
                           total_services=total_services,
                           total_providers=total_providers,
                           total_bookings=total_bookings)

@app.route('/services')
def services_page():
    # Get query parameters
    category = request.args.get('category')
    location = request.args.get('location')
    search = request.args.get('q')
    page = request.args.get('page', 1, type=int)
    per_page = 6

    # Build query
    query = Service.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    if location:
        query = query.filter(Service.location.ilike(f'%{location}%'))
    if search:
        query = query.filter(
            or_(
                Service.title.ilike(f'%{search}%'),
                Service.description.ilike(f'%{search}%')
            )
        )

    # Paginate
    paginated = query.order_by(Service.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    services = paginated.items
    total = paginated.total

    # Get categories for filter dropdown
    categories = db.session.query(Service.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]

    return render_template('services.html',
                           services=services,
                           pagination=paginated,
                           categories=categories,
                           selected_category=category,
                           selected_location=location,
                           search_query=search)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/service/<int:service_id>')
def service_detail(service_id):
    service = Service.query.get_or_404(service_id)
    reviews = Review.query.filter_by(service_id=service_id).order_by(Review.created_at.desc()).all()
    gallery = GalleryImage.query.filter_by(provider_id=service.provider_id).order_by(GalleryImage.created_at.desc()).all()
    can_request = current_user.is_authenticated and current_user.role == UserRole.CUSTOMER
    whatsapp_link = None
    if service.provider.whatsapp_number:
        clean_number = service.provider.whatsapp_number.replace('+', '').replace(' ', '').replace('-', '')
        whatsapp_msg = f"Hi! I'm interested in your service: {service.title} on QuickScope."
        whatsapp_link = f"https://wa.me/{clean_number}?text={requests.utils.quote(whatsapp_msg)}"
    return render_template('service_detail.html',
                         service=service,
                         reviews=reviews,
                         gallery=gallery,
                         can_request=can_request,
                         whatsapp_link=whatsapp_link)

# ==================== SERVICE MANAGEMENT ====================
@app.route('/service/create', methods=['GET', 'POST'])
@login_required
@provider_required
def create_service():
    if request.method == 'POST':
        image_filename = None
        if 'service_image' in request.files:
            file = request.files['service_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

        service = Service(
            provider_id=current_user.id,
            title=request.form['title'],
            category=request.form['category'],
            description=request.form['description'],
            price_min=float(request.form['price_min']) if request.form.get('price_min') else None,
            price_max=float(request.form['price_max']) if request.form.get('price_max') else None,
            price_type=request.form.get('price_type', 'fixed'),
            location=request.form.get('location'),
            image_filename=image_filename
        )
        db.session.add(service)
        db.session.commit()
        flash('Service listed successfully!', 'success')
        return redirect(url_for('provider_dashboard'))
    return render_template('create_service.html')

@app.route('/service/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@provider_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    if service.provider_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'service_image' in request.files:
            file = request.files['service_image']
            if file and allowed_file(file.filename):
                if service.image_filename and not service.image_filename.startswith(('http://', 'https://')):
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], service.image_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                service.image_filename = filename

        service.title = request.form['title']
        service.category = request.form['category']
        service.description = request.form['description']
        service.price_min = float(request.form['price_min']) if request.form.get('price_min') else None
        service.price_max = float(request.form['price_max']) if request.form.get('price_max') else None
        service.price_type = request.form.get('price_type', 'fixed')
        service.location = request.form.get('location')
        service.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('Service updated!', 'success')
        return redirect(url_for('provider_dashboard'))

    return render_template('create_service.html', service=service, edit_mode=True)

# ==================== GALLERY MANAGEMENT ====================
@app.route('/provider/gallery')
@login_required
@provider_required
def manage_gallery():
    images = GalleryImage.query.filter_by(provider_id=current_user.id).order_by(GalleryImage.created_at.desc()).all()
    return render_template('manage_gallery.html', images=images)

@app.route('/provider/gallery/upload', methods=['POST'])
@login_required
@provider_required
def upload_gallery_image():
    if 'gallery_image' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('manage_gallery'))
    file = request.files['gallery_image']
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        caption = request.form.get('caption', '')
        gallery_image = GalleryImage(
            provider_id=current_user.id,
            image_filename=filename,
            caption=caption
        )
        db.session.add(gallery_image)
        db.session.commit()
        flash('Image uploaded to gallery.', 'success')
    else:
        flash('Invalid file type.', 'error')
    return redirect(url_for('manage_gallery'))

@app.route('/provider/gallery/delete/<int:image_id>', methods=['POST'])
@login_required
@provider_required
def delete_gallery_image(image_id):
    image = GalleryImage.query.get_or_404(image_id)
    if image.provider_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('manage_gallery'))
    # Only delete local files
    if not image.image_filename.startswith(('http://', 'https://')):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], image.image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    db.session.delete(image)
    db.session.commit()
    flash('Image deleted.', 'success')
    return redirect(url_for('manage_gallery'))

# ==================== SCOPE REQUESTS ====================
@app.route('/service/<int:service_id>/scope', methods=['GET', 'POST'])
@login_required
@customer_required
def request_scope(service_id):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        preferred_date = None
        if request.form.get('preferred_date'):
            try:
                preferred_date = datetime.strptime(request.form['preferred_date'], '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        scope = ScopeRequest(
            customer_id=current_user.id,
            provider_id=service.provider_id,
            service_id=service.id,
            description=request.form['description'],
            location=request.form.get('location'),
            preferred_date=preferred_date
        )
        db.session.add(scope)
        db.session.commit()
        flash('Scope request sent! The provider will respond soon.', 'success')
        return redirect(url_for('my_bookings'))
    return render_template('scope_request.html', service=service)

@app.route('/scope/<int:scope_id>/respond', methods=['POST'])
@login_required
@provider_required
def respond_scope(scope_id):
    scope = ScopeRequest.query.get_or_404(scope_id)
    if scope.provider_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    scope.estimated_cost = float(request.form['estimated_cost'])
    scope.estimated_hours = float(request.form['estimated_hours']) if request.form.get('estimated_hours') else None
    scope.response_message = request.form.get('response_message', '')
    scope.status = ScopeStatus.RESPONDED
    scope.responded_at = datetime.utcnow()
    db.session.commit()
    flash('Response sent to customer!', 'success')
    return redirect(url_for('provider_dashboard'))

@app.route('/scope/<int:scope_id>/accept', methods=['POST'])
@login_required
@customer_required
def accept_scope(scope_id):
    scope = ScopeRequest.query.get_or_404(scope_id)
    if scope.customer_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    scope.status = ScopeStatus.ACCEPTED
    agreed_price = scope.estimated_cost if scope.estimated_cost is not None else 0.0
    booking = Booking(
        customer_id=current_user.id,
        provider_id=scope.provider_id,
        service_id=scope.service_id,
        scope_request_id=scope.id,
        scheduled_date=scope.preferred_date,
        address=scope.location,
        agreed_price=agreed_price,
        status=BookingStatus.PENDING
    )
    db.session.add(booking)
    db.session.commit()
    flash('Scope accepted and booking created!', 'success')
    return redirect(url_for('my_bookings'))

# ==================== BOOKINGS ====================
@app.route('/bookings')
@login_required
def my_bookings():
    if current_user.role == UserRole.CUSTOMER:
        bookings = Booking.query.filter_by(customer_id=current_user.id).order_by(Booking.created_at.desc()).all()
        scopes = ScopeRequest.query.filter_by(customer_id=current_user.id).order_by(ScopeRequest.created_at.desc()).all()
    else:
        bookings = Booking.query.filter_by(provider_id=current_user.id).order_by(Booking.created_at.desc()).all()
        scopes = ScopeRequest.query.filter_by(provider_id=current_user.id).order_by(ScopeRequest.created_at.desc()).all()
    return render_template('bookings.html', bookings=bookings, scopes=scopes)

@app.route('/booking/<int:booking_id>/status', methods=['POST'])
@login_required
def update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form['status']
    if current_user.role == UserRole.CUSTOMER and booking.customer_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if current_user.role == UserRole.PROVIDER and booking.provider_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    if new_status == 'confirmed' and current_user.role == UserRole.PROVIDER:
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = datetime.utcnow()
    elif new_status == 'completed' and current_user.role == UserRole.PROVIDER:
        booking.status = BookingStatus.COMPLETED
        booking.completed_at = datetime.utcnow()
    elif new_status == 'cancelled':
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = datetime.utcnow()
        booking.cancellation_reason = request.form.get('reason', '')
    else:
        flash('Invalid status update.', 'error')
        return redirect(url_for('my_bookings'))

    db.session.commit()
    flash(f'Booking {new_status}!', 'success')
    return redirect(url_for('my_bookings'))

# ==================== DIRECT BOOKING ====================
@app.route('/service/<int:service_id>/book', methods=['POST'])
@login_required
@customer_required
def direct_booking(service_id):
    service = Service.query.get_or_404(service_id)
    if service.price_type == 'quote' or service.price_min is None:
        flash('This service requires a quote. Please use "Request Scope".', 'error')
        return redirect(url_for('service_detail', service_id=service.id))
    agreed_price = service.price_min if service.price_min else 0.0
    booking = Booking(
        customer_id=current_user.id,
        provider_id=service.provider_id,
        service_id=service.id,
        scheduled_date=None,
        address=current_user.location,
        agreed_price=agreed_price,
        status=BookingStatus.PENDING
    )
    db.session.add(booking)
    db.session.commit()
    flash(f'Booking created for "{service.title}". The provider will confirm your booking soon.', 'success')
    return redirect(url_for('my_bookings'))

# ==================== REVIEWS ====================
@app.route('/booking/<int:booking_id>/review', methods=['GET', 'POST'])
@login_required
@customer_required
def leave_review(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.customer_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('index'))
    if booking.status != BookingStatus.COMPLETED:
        flash('Can only review completed bookings.', 'error')
        return redirect(url_for('my_bookings'))
    if booking.review:
        flash('You already reviewed this booking.', 'error')
        return redirect(url_for('my_bookings'))

    if request.method == 'POST':
        review = Review(
            booking_id=booking.id,
            customer_id=current_user.id,
            provider_id=booking.provider_id,
            service_id=booking.service_id,
            rating=int(request.form['rating']),
            comment=request.form.get('comment', '')
        )
        db.session.add(review)
        db.session.commit()
        flash('Review submitted! Thank you.', 'success')
        return redirect(url_for('service_detail', service_id=booking.service_id))

    return render_template('review.html', booking=booking)

@app.route('/review/<int:review_id>/respond', methods=['POST'])
@login_required
@provider_required
def respond_to_review(review_id):
    review = Review.query.get_or_404(review_id)
    if review.provider_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('index'))
    response_text = request.form.get('response_text', '').strip()
    if response_text:
        review.provider_response = response_text
        review.response_date = datetime.utcnow()
        db.session.commit()
        flash('Your response has been posted.', 'success')
    else:
        flash('Response cannot be empty.', 'error')
    return redirect(url_for('service_detail', service_id=review.service_id))

# ==================== AUTH ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))
        user = User(
            email=email,
            password_hash=generate_password_hash(request.form['password']),
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            phone=request.form.get('phone'),
            whatsapp_number=request.form.get('whatsapp_number'),
            role=UserRole(request.form['role']),
            business_name=request.form.get('business_name'),
            business_description=request.form.get('business_description'),
            location=request.form.get('location')
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Welcome to QuickScope!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user, remember=request.form.get('remember') == 'on')
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(next_page or url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ==================== GOOGLE OAUTH ====================
@app.route('/login/google')
def login_google():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    redirect_uri = url_for('google_callback', _external=True)
    request_uri = authorization_endpoint + "?" + urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": os.urandom(16).hex(),
    })
    session['oauth_state'] = request.args.get('state')
    return redirect(request_uri)

@app.route('/login/google/callback')
def google_callback():
    code = request.args.get("code")
    if not code:
        flash('Google login failed.', 'error')
        return redirect(url_for('login'))
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    redirect_uri = url_for('google_callback', _external=True)
    token_response = requests.post(
        token_endpoint,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    tokens = token_response.json()
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    userinfo_response = requests.get(
        userinfo_endpoint,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    userinfo = userinfo_response.json()
    if not userinfo.get("email_verified"):
        flash('Google email not verified.', 'error')
        return redirect(url_for('login'))
    email = userinfo["email"]
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            first_name=userinfo.get("given_name", "Google"),
            last_name=userinfo.get("family_name", "User"),
            avatar_url=userinfo.get("picture"),
            is_oauth=True,
            role=UserRole.CUSTOMER
        )
        db.session.add(user)
        db.session.commit()
    login_user(user)
    flash(f'Welcome, {user.first_name}!', 'success')
    return redirect(url_for('index'))

# ==================== PROFILE & DASHBOARD ====================
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form['first_name']
        current_user.last_name = request.form['last_name']
        current_user.phone = request.form.get('phone')
        current_user.whatsapp_number = request.form.get('whatsapp_number')
        current_user.location = request.form.get('location')
        if current_user.role == UserRole.PROVIDER:
            current_user.business_name = request.form.get('business_name')
            current_user.business_description = request.form.get('business_description')
        if request.form.get('password'):
            current_user.password_hash = generate_password_hash(request.form['password'])
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

@app.route('/provider/dashboard')
@login_required
@provider_required
def provider_dashboard():
    services = Service.query.filter_by(provider_id=current_user.id).order_by(Service.created_at.desc()).all()
    pending_scopes = ScopeRequest.query.filter_by(provider_id=current_user.id, status=ScopeStatus.REQUESTED).order_by(ScopeRequest.created_at.desc()).all()
    active_bookings = Booking.query.filter(
        Booking.provider_id == current_user.id,
        Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
    ).order_by(Booking.scheduled_date).all()
    return render_template('provider_dashboard.html',
                         services=services,
                         pending_scopes=pending_scopes,
                         active_bookings=active_bookings)

@app.route('/switch-role', methods=['POST'])
@login_required
def switch_role():
    new_role = request.form.get('role')
    if new_role in ['customer', 'provider']:
        current_user.role = UserRole(new_role)
        db.session.commit()
        flash(f'Switched to {new_role} mode.', 'success')
    return redirect(url_for('index'))

# ==================== ADMIN PANEL ====================
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_services = Service.query.count()
    total_bookings = Booking.query.count()
    total_reviews = Review.query.count()
    pending_scopes = ScopeRequest.query.filter_by(status=ScopeStatus.REQUESTED).count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_services=total_services,
                         total_bookings=total_bookings,
                         total_reviews=total_reviews,
                         pending_scopes=pending_scopes,
                         recent_users=recent_users,
                         recent_bookings=recent_bookings)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def admin_update_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form['role']
    if new_role in ['customer', 'provider', 'admin']:
        user.role = UserRole(new_role)
        db.session.commit()
        flash(f'Updated role for {user.email} to {new_role}.', 'success')
    else:
        flash('Invalid role.', 'error')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete yourself.', 'error')
        return redirect(url_for('admin_users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.email} deleted.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/services')
@login_required
@admin_required
def admin_services():
    services = Service.query.order_by(Service.created_at.desc()).all()
    return render_template('admin/services.html', services=services)

@app.route('/admin/service/<int:service_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_service(service_id):
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    flash(f'Service "{service.title}" {"activated" if service.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin_services'))

@app.route('/admin/service/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash(f'Service "{service.title}" deleted.', 'success')
    return redirect(url_for('admin_services'))

@app.route('/admin/bookings')
@login_required
@admin_required
def admin_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)

@app.route('/admin/booking/<int:booking_id>/status', methods=['POST'])
@login_required
@admin_required
def admin_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form['status']
    if new_status in ['pending', 'confirmed', 'completed', 'cancelled']:
        booking.status = BookingStatus(new_status)
        db.session.commit()
        flash(f'Booking #{booking.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status.', 'error')
    return redirect(url_for('admin_bookings'))

@app.route('/admin/reviews')
@login_required
@admin_required
def admin_reviews():
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=reviews)

@app.route('/admin/review/<int:review_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    flash('Review deleted.', 'success')
    return redirect(url_for('admin_reviews'))

# ==================== API ENDPOINTS ====================
@app.route('/api/services')
def api_services():
    services = Service.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': s.id,
        'title': s.title,
        'category': s.category,
        'price_min': s.price_min,
        'price_max': s.price_max,
        'location': s.location,
        'provider': s.provider.full_name,
        'rating': s.provider.average_rating,
        'image': get_image_url(s.image_filename)
    } for s in services])

@app.route('/api/booking/<int:booking_id>')
@login_required
def api_booking_detail(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.customer_id != current_user.id and booking.provider_id != current_user.id and current_user.role != UserRole.ADMIN:
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({
        'id': booking.id,
        'status': booking.status.value,
        'service': booking.service.title,
        'price': booking.agreed_price,
        'date': booking.scheduled_date.isoformat() if booking.scheduled_date else None
    })

# ==================== MAIN ====================
if __name__ == '__main__':
    app.run(debug=True, port=5000)