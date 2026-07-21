from dotenv import load_dotenv
load_dotenv()

import os
import json
import requests
import random
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlencode
from werkzeug.utils import secure_filename
import pytz
import cloudinary
import cloudinary.uploader

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, inspect, text

from config import Config
from models import db, User, Service, GalleryImage, ScopeRequest, Booking, Review, UserRole, BookingStatus, ScopeStatus
from models import format_datetime, format_date, get_sast_time
from models import Notification, ChatMessage

app = Flask(__name__)
app.instance_path = '/tmp'          # 👈 Fix for Vercel read‑only filesystem
app.config.from_object(Config)

# Cloudinary configuration
cloudinary.config(
    cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
    api_key=app.config['CLOUDINARY_API_KEY'],
    api_secret=app.config['CLOUDINARY_API_SECRET']
)

# No need to create UPLOAD_FOLDER – Cloudinary handles uploads.
# If you need a temp folder for any reason, use /tmp.
# os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

# ---------- Helper for notifications ----------
def create_notification(user_id, type, title, message, link=None):
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link=link
    )
    db.session.add(notif)
    db.session.commit()
    return notif

def get_admin_user():
    """Return the admin user (by email)."""
    return User.query.filter_by(email='admin@quickscope.com').first()

# ---------- Helper for database schema updates ----------
def ensure_schema():
    """Add any missing columns to the bookings and users tables."""
    try:
        inspector = inspect(db.engine)

        # Check for bookings.started_at
        columns_bookings = [col['name'] for col in inspector.get_columns('bookings')]
        if 'started_at' not in columns_bookings:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE bookings ADD COLUMN started_at TIMESTAMP'))
                conn.commit()
                print("✅ Added column started_at to bookings table.")

        # Check for users.whatsapp_number
        columns_users = [col['name'] for col in inspector.get_columns('users')]
        if 'whatsapp_number' not in columns_users:
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE users ADD COLUMN whatsapp_number VARCHAR(20)'))
                conn.commit()
                print("✅ Added column whatsapp_number to users table.")

        # You can add other missing columns here in the future.

    except Exception as e:
        print(f"⚠️ Schema update warning: {e}")

# ---------- Helper functions for seeding ----------
def random_phone():
    prefixes = ['082', '083', '084', '071', '072', '073', '074', '076', '078', '079']
    return random.choice(prefixes) + ''.join(str(random.randint(0, 9)) for _ in range(7))

def random_date(start, end):
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

def seed_database():
    with app.app_context():
        if Service.query.count() > 0:
            print("✅ Database already has services – skipping seed.")
            return

        print("🌱 Seeding database with sample data...")
        db.create_all()

        # Customers
        customers = [
            {'first_name': 'Thabo', 'last_name': 'Mokoena', 'email': 'thabo.m@example.com', 'password': 'password123', 'phone': random_phone(), 'location': 'Johannesburg, Gauteng'},
            {'first_name': 'Lindiwe', 'last_name': 'Nkosi', 'email': 'lindiwe.n@example.com', 'password': 'password123', 'phone': random_phone(), 'location': 'Cape Town, Western Cape'},
            {'first_name': 'Sipho', 'last_name': 'Zulu', 'email': 'sipho.z@example.com', 'password': 'password123', 'phone': random_phone(), 'location': 'Durban, KwaZulu-Natal'},
            {'first_name': 'Zanele', 'last_name': 'Mthembu', 'email': 'zanele.m@example.com', 'password': 'password123', 'phone': random_phone(), 'location': 'Pretoria, Gauteng'},
            {'first_name': 'Kagiso', 'last_name': 'Mabaso', 'email': 'kagiso.m@example.com', 'password': 'password123', 'phone': random_phone(), 'location': 'Port Elizabeth, Eastern Cape'}
        ]

        providers = [
            {
                'first_name': 'Nomsa', 'last_name': 'Mthembu', 'email': 'nomsa.m@example.com', 'password': 'password123',
                'phone': random_phone(), 'business_name': 'Clean & Shine Services',
                'business_description': 'Professional cleaning services...', 'location': 'Johannesburg, Gauteng',
                'services': [
                    {'title': 'Deep House Cleaning', 'category': 'Cleaning', 'description': 'Thorough cleaning...', 'price_min': 450, 'price_max': 850, 'price_type': 'fixed', 'image_seed': 'clean1'},
                    {'title': 'Office Cleaning (Weekly)', 'category': 'Cleaning', 'description': 'Regular office cleaning...', 'price_min': 600, 'price_max': 1200, 'price_type': 'fixed', 'image_seed': 'clean2'}
                ],
                'gallery': [{'caption': 'After a deep clean', 'seed': 'gallery1'}, {'caption': 'Kitchen sparkling clean', 'seed': 'gallery2'}, {'caption': 'Office refresh', 'seed': 'gallery3'}]
            },
            {
                'first_name': 'Bongani', 'last_name': 'Mkhize', 'email': 'bongani.m@example.com', 'password': 'password123',
                'phone': random_phone(), 'business_name': 'Handyman Bongani',
                'business_description': 'Reliable handyman services...', 'location': 'Cape Town, Western Cape',
                'services': [
                    {'title': 'Plumbing Repairs', 'category': 'Repairs', 'description': 'Fix leaks...', 'price_min': 350, 'price_max': 800, 'price_type': 'quote', 'image_seed': 'plumb1'},
                    {'title': 'Electrical Fixes', 'category': 'Repairs', 'description': 'Install lights...', 'price_min': 400, 'price_max': 900, 'price_type': 'quote', 'image_seed': 'elec1'},
                    {'title': 'General Handyman', 'category': 'Repairs', 'description': 'Painting...', 'price_min': 300, 'price_max': 700, 'price_type': 'hourly', 'image_seed': 'handy1'}
                ],
                'gallery': [{'caption': 'New bathroom faucet', 'seed': 'gallery4'}, {'caption': 'Rewired kitchen', 'seed': 'gallery5'}, {'caption': 'Painted living room', 'seed': 'gallery6'}]
            },
            {
                'first_name': 'Precious', 'last_name': 'Singh', 'email': 'precious.s@example.com', 'password': 'password123',
                'phone': random_phone(), 'business_name': 'Green Thumb Gardening',
                'business_description': 'Professional gardening...', 'location': 'Durban, KwaZulu-Natal',
                'services': [
                    {'title': 'Garden Design & Installation', 'category': 'Gardening', 'description': 'Full garden design...', 'price_min': 1500, 'price_max': 5000, 'price_type': 'quote', 'image_seed': 'garden1'},
                    {'title': 'Lawn Maintenance', 'category': 'Gardening', 'description': 'Weekly or bi‑weekly lawn mowing...', 'price_min': 250, 'price_max': 450, 'price_type': 'fixed', 'image_seed': 'garden2'}
                ],
                'gallery': [{'caption': 'New garden installation', 'seed': 'gallery7'}, {'caption': 'Before and after', 'seed': 'gallery8'}, {'caption': 'Irrigation system', 'seed': 'gallery9'}]
            },
            {
                'first_name': 'Ayanda', 'last_name': 'Naidoo', 'email': 'ayanda.n@example.com', 'password': 'password123',
                'phone': random_phone(), 'business_name': 'Ayanda Tutoring',
                'business_description': 'Experienced tutor...', 'location': 'Pretoria, Gauteng',
                'services': [
                    {'title': 'Mathematics Tutoring (Grades 8-12)', 'category': 'Tutoring', 'description': 'One-on-one tutoring...', 'price_min': 200, 'price_max': 350, 'price_type': 'hourly', 'image_seed': 'math1'},
                    {'title': 'English & Literature', 'category': 'Tutoring', 'description': 'Help with reading...', 'price_min': 180, 'price_max': 300, 'price_type': 'hourly', 'image_seed': 'eng1'}
                ],
                'gallery': [{'caption': 'Lesson in progress', 'seed': 'gallery10'}, {'caption': 'Student resources', 'seed': 'gallery11'}]
            },
            {
                'first_name': 'Sibusiso', 'last_name': 'Mthethwa', 'email': 'sibusiso.m@example.com', 'password': 'password123',
                'phone': random_phone(), 'business_name': 'Sibusiso Photography',
                'business_description': 'Professional photography...', 'location': 'Johannesburg, Gauteng',
                'services': [
                    {'title': 'Wedding Photography', 'category': 'Photography', 'description': 'Full-day coverage...', 'price_min': 5000, 'price_max': 12000, 'price_type': 'quote', 'image_seed': 'wedding1'},
                    {'title': 'Portrait Sessions', 'category': 'Photography', 'description': 'Personal or family portraits...', 'price_min': 800, 'price_max': 1800, 'price_type': 'fixed', 'image_seed': 'portrait1'}
                ],
                'gallery': [{'caption': 'Wedding couple', 'seed': 'gallery12'}, {'caption': 'Family portrait', 'seed': 'gallery13'}, {'caption': 'Event coverage', 'seed': 'gallery14'}]
            }
        ]

        for cust in customers:
            if not User.query.filter_by(email=cust['email']).first():
                user = User(
                    email=cust['email'],
                    password_hash=generate_password_hash(cust['password']),
                    first_name=cust['first_name'],
                    last_name=cust['last_name'],
                    phone=cust['phone'],
                    location=cust['location'],
                    role=UserRole.CUSTOMER,
                    avatar_url=f"https://i.pravatar.cc/150?img={random.randint(1,70)}"
                )
                db.session.add(user)
        db.session.commit()

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
                    avatar_url=f"https://i.pravatar.cc/150?img={random.randint(1,70)}"
                )
                db.session.add(user)
                db.session.commit()

            for svc in prov['services']:
                if not Service.query.filter_by(provider_id=user.id, title=svc['title']).first():
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

            for img in prov['gallery']:
                if not GalleryImage.query.filter_by(provider_id=user.id, caption=img['caption']).first():
                    gallery_img = GalleryImage(
                        provider_id=user.id,
                        image_filename=f"https://picsum.photos/seed/{img['seed']}/400/300",
                        caption=img['caption']
                    )
                    db.session.add(gallery_img)

        db.session.commit()

        # Bookings & scopes
        all_customers = User.query.filter_by(role=UserRole.CUSTOMER).all()
        all_providers = User.query.filter_by(role=UserRole.PROVIDER).all()
        all_services = Service.query.all()

        if all_services:
            for customer in all_customers:
                if Booking.query.filter_by(customer_id=customer.id).count() < 3:
                    for _ in range(random.randint(1,2)):
                        provider = random.choice(all_providers)
                        provider_services = [s for s in all_services if s.provider_id == provider.id]
                        if not provider_services:
                            continue
                        service = random.choice(provider_services)
                        status = random.choices(
                            [BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS, BookingStatus.COMPLETED, BookingStatus.CANCELLED],
                            weights=[0.2, 0.2, 0.2, 0.3, 0.1], k=1
                        )[0]
                        created = random_date(datetime.now() - timedelta(days=90), datetime.now())
                        confirmed_at = created + timedelta(days=1) if status in [BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS, BookingStatus.COMPLETED] else None
                        started_at = created + timedelta(days=2) if status in [BookingStatus.IN_PROGRESS, BookingStatus.COMPLETED] else None
                        completed_at = created + timedelta(days=5) if status == BookingStatus.COMPLETED else None
                        booking = Booking(
                            customer_id=customer.id,
                            provider_id=provider.id,
                            service_id=service.id,
                            scheduled_date=created + timedelta(days=random.randint(1,10)),
                            address=customer.location,
                            agreed_price=service.price_min or 300,
                            status=status,
                            created_at=created,
                            confirmed_at=confirmed_at,
                            started_at=started_at,
                            completed_at=completed_at,
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
                        description=f"I need help with {service.title.lower()}. Can you provide a quote?",
                        location=customer.location,
                        preferred_date=datetime.now() + timedelta(days=random.randint(3,10)),
                        status=random.choice([ScopeStatus.REQUESTED, ScopeStatus.RESPONDED, ScopeStatus.ACCEPTED]),
                        estimated_cost=random.choice([None, round(random.uniform(300,1200),2)]),
                        estimated_hours=random.choice([None, round(random.uniform(1,8),1)]),
                        response_message=random.choice([None, "Sure, I can do that. Here's my estimate."]),
                        responded_at=datetime.now() - timedelta(days=random.randint(1,5)) if random.choice([True,False]) else None,
                        created_at=datetime.now() - timedelta(days=random.randint(1,15))
                    )
                    db.session.add(scope)

            db.session.commit()

            # Reviews
            for booking in Booking.query.filter_by(status=BookingStatus.COMPLETED).all():
                if not booking.review and random.random() < 0.7:
                    review = Review(
                        booking_id=booking.id,
                        customer_id=booking.customer_id,
                        provider_id=booking.provider_id,
                        service_id=booking.service_id,
                        rating=random.randint(3,5),
                        comment=random.choice(["Excellent service!", "Great job!", "Good quality.", "Satisfied.", "Amazing experience."]),
                        created_at=booking.completed_at + timedelta(days=random.randint(1,3))
                    )
                    db.session.add(review)
            db.session.commit()

        print("🎉 Database seeding complete.")

# ---------- Create tables, seed, and ensure schema ----------
with app.app_context():
    db.create_all()
    ensure_schema()  # ✅ This will add missing columns like whatsapp_number

    admin_email = "admin@quickscope.com"
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
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
        if admin.role != UserRole.ADMIN:
            admin.role = UserRole.ADMIN
            db.session.commit()
            print("Admin role updated to ADMIN.")
        print("Admin user already exists (role confirmed).")

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
    if not filename:
        return None
    if filename.startswith(('http://', 'https://')):
        return filename
    return url_for('static', filename='uploads/' + filename)

@app.context_processor
def inject_globals():
    categories = db.session.query(Service.category).distinct().all()
    unread_count = 0
    chat_unread = 0
    if current_user.is_authenticated:
        unread_count = current_user.unread_notification_count
        chat_unread = ChatMessage.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return dict(
        categories=[c[0] for c in categories if c[0]],
        currency=app.config['CURRENCY'],
        format_datetime=format_datetime,
        format_date=format_date,
        get_image_url=get_image_url,
        unread_notifications=unread_count,
        chat_unread=chat_unread
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
    category = request.args.get('category')
    location = request.args.get('location')
    search = request.args.get('q')
    page = request.args.get('page', 1, type=int)
    per_page = 6
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
    paginated = query.order_by(Service.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    services = paginated.items
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
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(file)
                image_filename = upload_result['secure_url']

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

        admin = get_admin_user()
        if admin:
            create_notification(
                user_id=admin.id,
                type='new_service_listed',
                title='New Service Listed',
                message=f'{current_user.full_name} listed a new service: "{service.title}"',
                link=url_for('admin_services')
            )

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
                upload_result = cloudinary.uploader.upload(file)
                service.image_filename = upload_result['secure_url']

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
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(file)
        filename = upload_result['secure_url']
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
    # No need to delete from Cloudinary here; just remove the DB record.
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
        create_notification(
            user_id=service.provider_id,
            type='scope_requested',
            title='New Scope Request',
            message=f'{current_user.full_name} requested a scope for "{service.title}".',
            link=url_for('my_bookings')
        )
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
    create_notification(
        user_id=scope.customer_id,
        type='scope_responded',
        title='Scope Response',
        message=f'{current_user.full_name} responded to your scope request for "{scope.service.title}".',
        link=url_for('my_bookings')
    )
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
    create_notification(
        user_id=scope.provider_id,
        type='booking_created',
        title='New Booking',
        message=f'{current_user.full_name} accepted your scope and created a booking for "{scope.service.title}".',
        link=url_for('my_bookings')
    )
    flash('Scope accepted and booking created!', 'success')
    return redirect(url_for('my_bookings'))

# ==================== BOOKINGS ====================
@app.route('/bookings')
@login_required
def my_bookings():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [5, 10, 15]:
        per_page = 10

    scope_page = request.args.get('scope_page', 1, type=int)
    scope_per_page = request.args.get('scope_per_page', 10, type=int)
    if scope_per_page not in [5, 10, 15]:
        scope_per_page = 10

    if current_user.role == UserRole.CUSTOMER:
        bookings_query = Booking.query.filter_by(customer_id=current_user.id).order_by(Booking.created_at.desc())
        bookings_pagination = bookings_query.paginate(page=page, per_page=per_page, error_out=False)
        bookings = bookings_pagination.items

        scopes_query = ScopeRequest.query.filter_by(customer_id=current_user.id).order_by(ScopeRequest.created_at.desc())
        scopes_pagination = scopes_query.paginate(page=scope_page, per_page=scope_per_page, error_out=False)
        scopes = scopes_pagination.items
    else:
        bookings_query = Booking.query.filter_by(provider_id=current_user.id).order_by(Booking.created_at.desc())
        bookings_pagination = bookings_query.paginate(page=page, per_page=per_page, error_out=False)
        bookings = bookings_pagination.items

        scopes_query = ScopeRequest.query.filter_by(provider_id=current_user.id).order_by(ScopeRequest.created_at.desc())
        scopes_pagination = scopes_query.paginate(page=scope_page, per_page=scope_per_page, error_out=False)
        scopes = scopes_pagination.items

    return render_template('bookings.html',
                           bookings=bookings,
                           bookings_pagination=bookings_pagination,
                           scopes=scopes,
                           scopes_pagination=scopes_pagination,
                           per_page=per_page,
                           scope_per_page=scope_per_page)

@app.route('/booking/<int:booking_id>/status', methods=['POST'])
@login_required
def update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    action = request.form.get('action')
    if current_user.role == UserRole.CUSTOMER and booking.customer_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if current_user.role == UserRole.PROVIDER and booking.provider_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    if action == 'confirm' and current_user.role == UserRole.PROVIDER:
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = datetime.utcnow()
        create_notification(
            user_id=booking.customer_id,
            type='booking_confirmed',
            title='Booking Confirmed',
            message=f'Your booking for "{booking.service.title}" has been confirmed by {current_user.full_name}.',
            link=url_for('my_bookings')
        )
        create_notification(
            user_id=booking.provider_id,
            type='booking_confirmed',
            title='Booking Confirmed',
            message=f'You confirmed booking for "{booking.service.title}" with {booking.customer.full_name}.',
            link=url_for('my_bookings')
        )
    elif action == 'start' and current_user.role == UserRole.PROVIDER:
        booking.status = BookingStatus.IN_PROGRESS
        booking.started_at = datetime.utcnow()
        create_notification(
            user_id=booking.customer_id,
            type='booking_started',
            title='Work Started',
            message=f'{current_user.full_name} has started working on "{booking.service.title}".',
            link=url_for('my_bookings')
        )
    elif action == 'complete' and current_user.role == UserRole.PROVIDER:
        booking.status = BookingStatus.COMPLETED
        booking.completed_at = datetime.utcnow()
        create_notification(
            user_id=booking.customer_id,
            type='booking_completed',
            title='Job Completed',
            message=f'Your service "{booking.service.title}" has been marked as complete. Please leave a review!',
            link=url_for('my_bookings')
        )
        create_notification(
            user_id=booking.provider_id,
            type='booking_completed',
            title='Job Completed',
            message=f'You marked "{booking.service.title}" as complete.',
            link=url_for('my_bookings')
        )
    elif action == 'cancel':
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = datetime.utcnow()
        booking.cancellation_reason = request.form.get('reason', '')
        other_id = booking.provider_id if current_user.id == booking.customer_id else booking.customer_id
        create_notification(
            user_id=other_id,
            type='booking_cancelled',
            title='Booking Cancelled',
            message=f'Your booking for "{booking.service.title}" has been cancelled by {current_user.full_name}. Reason: {booking.cancellation_reason}',
            link=url_for('my_bookings')
        )
        create_notification(
            user_id=current_user.id,
            type='booking_cancelled',
            title='Booking Cancelled',
            message=f'You cancelled booking for "{booking.service.title}".',
            link=url_for('my_bookings')
        )
    else:
        flash('Invalid action.', 'error')
        return redirect(url_for('my_bookings'))

    db.session.commit()
    flash(f'Booking {action}d!', 'success')
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
    create_notification(
        user_id=service.provider_id,
        type='booking_created',
        title='New Booking',
        message=f'{current_user.full_name} booked your service "{service.title}".',
        link=url_for('my_bookings')
    )
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

# ==================== NOTIFICATIONS ====================
@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [5, 10, 15]:
        per_page = 10
    query = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    notifications = paginated.items
    return render_template('notifications.html', 
                           notifications=notifications,
                           pagination=paginated,
                           per_page=per_page)

@app.route('/notification/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notif = Notification.query.get_or_404(notification_id)
    if notif.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notif.read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/notification/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    return jsonify({'success': True})

# ==================== CHAT ====================
@app.route('/chat/conversations')
@login_required
def chat_conversations():
    sent_ids = db.session.query(ChatMessage.receiver_id).filter(ChatMessage.sender_id == current_user.id).distinct().all()
    received_ids = db.session.query(ChatMessage.sender_id).filter(ChatMessage.receiver_id == current_user.id).distinct().all()
    user_ids = set([id[0] for id in sent_ids] + [id[0] for id in received_ids])
    if current_user.id in user_ids:
        user_ids.remove(current_user.id)
    users = User.query.filter(User.id.in_(user_ids)).all()
    conversation_data = []
    for user in users:
        latest = ChatMessage.query.filter(
            ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == user.id)) |
            ((ChatMessage.sender_id == user.id) & (ChatMessage.receiver_id == current_user.id))
        ).order_by(ChatMessage.created_at.desc()).first()
        unread = ChatMessage.query.filter(
            ChatMessage.sender_id == user.id,
            ChatMessage.receiver_id == current_user.id,
            ChatMessage.is_read == False
        ).count()
        conversation_data.append({
            'user': user,
            'latest': latest,
            'unread': unread
        })
    conversation_data.sort(key=lambda x: x['latest'].created_at if x['latest'] else datetime.min, reverse=True)
    return render_template('chat/conversations.html', conversations=conversation_data)

@app.route('/contact-admin')
@login_required
def contact_admin():
    admin = get_admin_user()
    if not admin:
        flash('Admin not found. Please contact support.', 'error')
        return redirect(url_for('index'))
    return redirect(url_for('chat_with_user', user_id=admin.id))

@app.route('/chat/user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def chat_with_user(user_id):
    other_user = User.query.get_or_404(user_id)
    if other_user.id == current_user.id:
        flash('You cannot chat with yourself.', 'error')
        return redirect(url_for('chat_conversations'))

    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if message:
            chat_msg = ChatMessage(
                sender_id=current_user.id,
                receiver_id=other_user.id,
                message=message
            )
            db.session.add(chat_msg)
            db.session.commit()
            create_notification(
                user_id=other_user.id,
                type='chat_message',
                title=f'New message from {current_user.full_name}',
                message=message[:200],
                link=url_for('chat_with_user', user_id=current_user.id)
            )
            flash('Message sent.', 'success')
        return redirect(url_for('chat_with_user', user_id=other_user.id))

    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == other_user.id)) |
        ((ChatMessage.sender_id == other_user.id) & (ChatMessage.receiver_id == current_user.id))
    ).order_by(ChatMessage.created_at.asc()).all()
    for msg in messages:
        if msg.sender_id == other_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    return render_template('chat/chat_user.html', other_user=other_user, messages=messages)

@app.route('/chat/messages')
@login_required
def get_chat_messages_ajax():
    other_id = request.args.get('user_id', type=int)
    last_id = request.args.get('last_id', 0, type=int)
    if not other_id:
        return jsonify([])
    other_user = User.query.get_or_404(other_id)
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == other_user.id)) |
        ((ChatMessage.sender_id == other_user.id) & (ChatMessage.receiver_id == current_user.id)),
        ChatMessage.id > last_id
    ).order_by(ChatMessage.created_at.asc()).all()
    for msg in messages:
        if msg.sender_id == other_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    data = [{
        'id': m.id,
        'sender_name': m.sender.full_name,
        'sender_id': m.sender_id,
        'message': m.message,
        'created_at': format_datetime(m.created_at)
    } for m in messages]
    return jsonify(data)

# ==================== ADMIN CHAT ====================
@app.route('/admin/chat')
@login_required
@admin_required
def admin_chat():
    admin_user = get_admin_user()
    if not admin_user:
        flash('Admin user not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    sent_ids = db.session.query(ChatMessage.sender_id).filter(ChatMessage.receiver_id == admin_user.id).distinct().all()
    received_ids = db.session.query(ChatMessage.receiver_id).filter(ChatMessage.sender_id == admin_user.id).distinct().all()
    user_ids = set([id[0] for id in sent_ids] + [id[0] for id in received_ids])
    users = User.query.filter(User.id.in_(user_ids)).all()
    user_data = []
    for user in users:
        latest = ChatMessage.query.filter(
            ((ChatMessage.sender_id == user.id) & (ChatMessage.receiver_id == admin_user.id)) |
            ((ChatMessage.sender_id == admin_user.id) & (ChatMessage.receiver_id == user.id))
        ).order_by(ChatMessage.created_at.desc()).first()
        unread = ChatMessage.query.filter(
            ChatMessage.sender_id == user.id,
            ChatMessage.receiver_id == admin_user.id,
            ChatMessage.is_read == False
        ).count()
        user_data.append({
            'user': user,
            'latest': latest,
            'unread': unread
        })
    user_data.sort(key=lambda x: x['latest'].created_at if x['latest'] else datetime.min, reverse=True)
    return render_template('admin/chat.html', user_data=user_data)

@app.route('/admin/chat/<int:user_id>')
@login_required
@admin_required
def admin_chat_with_user(user_id):
    admin_user = get_admin_user()
    if not admin_user:
        flash('Admin user not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    user = User.query.get_or_404(user_id)
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == admin_user.id)) |
        ((ChatMessage.sender_id == admin_user.id) & (ChatMessage.receiver_id == user_id))
    ).order_by(ChatMessage.created_at.asc()).all()
    for msg in messages:
        if msg.sender_id == user_id and not msg.is_read:
            msg.is_read = True
    db.session.commit()
    return render_template('admin/chat_user.html', user=user, messages=messages, admin_user=admin_user)

@app.route('/admin/chat/send', methods=['POST'])
@login_required
@admin_required
def admin_send_chat():
    user_id = request.form.get('user_id', type=int)
    message = request.form.get('message', '').strip()
    if not user_id or not message:
        return jsonify({'error': 'Missing fields'}), 400
    admin_user = get_admin_user()
    if not admin_user:
        return jsonify({'error': 'Admin not found'}), 404
    chat_msg = ChatMessage(
        sender_id=admin_user.id,
        receiver_id=user_id,
        message=message
    )
    db.session.add(chat_msg)
    db.session.commit()
    create_notification(
        user_id=user_id,
        type='chat_message',
        title=f'New reply from Admin',
        message=message[:200],
        link=url_for('chat_with_user', user_id=admin_user.id)
    )
    return jsonify({'success': True, 'message': message, 'created_at': format_datetime(chat_msg.created_at)})

# ==================== AUTH ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    flash('Please use Google Sign‑In to create an account.', 'info')
    return redirect(url_for('login_google'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            if user.role == UserRole.ADMIN:
                login_user(user, remember=request.form.get('remember') == 'on')
                next_page = request.args.get('next')
                flash(f'Welcome back, {user.first_name}!', 'success')
                return redirect(next_page or url_for('index'))
            else:
                flash('Non‑admin users must log in with Google.', 'error')
                return redirect(url_for('login_google'))
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
            role=None
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    if user.role is None:
        return redirect(url_for('choose_role'))

    flash(f'Welcome, {user.first_name}!', 'success')
    return redirect(url_for('index'))

# ==================== ROLE SELECTION ====================
@app.route('/choose-role', methods=['GET', 'POST'])
@login_required
def choose_role():
    if current_user.role is not None:
        return redirect(url_for('index'))

    if request.method == 'POST':
        chosen = request.form.get('role')
        if chosen in ['customer', 'provider']:
            current_user.role = UserRole(chosen)
            db.session.commit()
            flash(f'You are now registered as a {chosen}. Welcome!', 'success')
            return redirect(url_for('index'))
        flash('Please select a valid role.', 'error')
    return render_template('choose_role.html')

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
        Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.IN_PROGRESS])
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
    admin_user = get_admin_user()
    unread_chats = 0
    if admin_user:
        unread_chats = ChatMessage.query.filter_by(receiver_id=admin_user.id, is_read=False).count()
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_services=total_services,
                         total_bookings=total_bookings,
                         total_reviews=total_reviews,
                         pending_scopes=pending_scopes,
                         recent_users=recent_users,
                         recent_bookings=recent_bookings,
                         unread_chats=unread_chats)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [5, 10, 15]:
        per_page = 10

    role_filter = request.args.get('role', '')
    search_query = request.args.get('search', '')

    query = User.query
    if role_filter:
        query = query.filter_by(role=UserRole(role_filter))
    if search_query:
        query = query.filter(
            or_(
                User.first_name.ilike(f'%{search_query}%'),
                User.last_name.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            )
        )
    query = query.order_by(User.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    users = paginated.items
    return render_template('admin/users.html',
                           users=users,
                           pagination=paginated,
                           per_page=per_page,
                           role_filter=role_filter,
                           search_query=search_query)

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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [5, 10, 15]:
        per_page = 10

    category_filter = request.args.get('category', '')
    active_filter = request.args.get('active', '')
    search_query = request.args.get('search', '')

    query = Service.query
    if category_filter:
        query = query.filter_by(category=category_filter)
    if active_filter != '':
        is_active = active_filter.lower() == 'true'
        query = query.filter_by(is_active=is_active)
    if search_query:
        query = query.filter(Service.title.ilike(f'%{search_query}%'))
    query = query.order_by(Service.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    services = paginated.items
    categories = db.session.query(Service.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    return render_template('admin/services.html',
                           services=services,
                           pagination=paginated,
                           per_page=per_page,
                           categories=categories,
                           category_filter=category_filter,
                           active_filter=active_filter,
                           search_query=search_query)

@app.route('/admin/service/<int:service_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_service(service_id):
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    flash(f'Service "{service.title}" {"activated" if service.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin_services'))

@app.route('/admin/service/<int:service_id>/remove', methods=['POST'])
@login_required
@admin_required
def admin_remove_service(service_id):
    service = Service.query.get_or_404(service_id)
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Please provide a reason for removal.', 'error')
        return redirect(url_for('admin_services'))
    create_notification(
        user_id=service.provider_id,
        type='service_removed',
        title='Service Removed',
        message=f'Your service "{service.title}" has been removed by admin. Reason: {reason}',
        link=url_for('provider_dashboard')
    )
    db.session.delete(service)
    db.session.commit()
    flash(f'Service "{service.title}" removed. Provider notified.', 'success')
    return redirect(url_for('admin_services'))

@app.route('/admin/bookings')
@login_required
@admin_required
def admin_bookings():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [5, 10, 15]:
        per_page = 10

    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '')

    query = Booking.query
    if status_filter:
        query = query.filter_by(status=BookingStatus(status_filter))
    if search_query:
        query = query.join(Service).filter(Service.title.ilike(f'%{search_query}%'))
    query = query.order_by(Booking.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    bookings = paginated.items
    return render_template('admin/bookings.html',
                           bookings=bookings,
                           pagination=paginated,
                           per_page=per_page,
                           status_filter=status_filter,
                           search_query=search_query)

@app.route('/admin/booking/<int:booking_id>/status', methods=['POST'])
@login_required
@admin_required
def admin_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form['status']
    if new_status in ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled']:
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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [5, 10, 15]:
        per_page = 10

    rating_filter = request.args.get('rating', type=int)
    search_query = request.args.get('search', '')

    query = Review.query
    if rating_filter:
        query = query.filter(Review.rating >= rating_filter)
    if search_query:
        query = query.join(Service).filter(Service.title.ilike(f'%{search_query}%'))
    query = query.order_by(Review.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    reviews = paginated.items
    return render_template('admin/reviews.html',
                           reviews=reviews,
                           pagination=paginated,
                           per_page=per_page,
                           rating_filter=rating_filter,
                           search_query=search_query)

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