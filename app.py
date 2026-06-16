import os
import json
import requests
import random
from datetime import datetime
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

# ---------- Create tables on startup ----------
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