from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import enum
import pytz
from flask import current_app

db = SQLAlchemy()

def get_sast_time():
    """Return current datetime in SAST (UTC+2)"""
    tz = pytz.timezone(current_app.config['TIMEZONE'])
    return datetime.now(tz)

def format_datetime(dt):
    if dt is None:
        return ''
    tz = pytz.timezone(current_app.config['TIMEZONE'])
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime(current_app.config['DATETIME_FORMAT'])

def format_date(dt):
    if dt is None:
        return ''
    tz = pytz.timezone(current_app.config['TIMEZONE'])
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime(current_app.config['DATE_FORMAT'])

class UserRole(enum.Enum):
    CUSTOMER = "customer"
    PROVIDER = "provider"
    ADMIN = "admin"

class BookingStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ScopeStatus(enum.Enum):
    REQUESTED = "requested"
    RESPONDED = "responded"
    ACCEPTED = "accepted"
    DECLINED = "declined"

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    whatsapp_number = db.Column(db.String(20))
    avatar_url = db.Column(db.String(500))
    role = db.Column(db.Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_oauth = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Provider specific
    business_name = db.Column(db.String(100))
    business_description = db.Column(db.Text)
    location = db.Column(db.String(200))
    
    # Relationships
    services = db.relationship('Service', backref='provider', lazy='dynamic', cascade='all, delete-orphan')
    gallery = db.relationship('GalleryImage', backref='provider', lazy='dynamic', cascade='all, delete-orphan')
    bookings_as_customer = db.relationship('Booking', foreign_keys='Booking.customer_id', backref='customer', lazy='dynamic')
    bookings_as_provider = db.relationship('Booking', foreign_keys='Booking.provider_id', backref='provider_booking', lazy='dynamic')
    reviews_given = db.relationship('Review', foreign_keys='Review.customer_id', backref='reviewer', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.provider_id', backref='reviewed_provider', lazy='dynamic')
    scope_requests = db.relationship('ScopeRequest', foreign_keys='ScopeRequest.customer_id', backref='scope_customer', lazy='dynamic')
    scope_responses = db.relationship('ScopeRequest', foreign_keys='ScopeRequest.provider_id', backref='scope_provider', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def average_rating(self):
        reviews = self.reviews_received.all()
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)
    
    @property
    def review_count(self):
        return self.reviews_received.count()

class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    price_min = db.Column(db.Float)
    price_max = db.Column(db.Float)
    price_type = db.Column(db.String(20), default='fixed')
    location = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    image_filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    bookings = db.relationship('Booking', backref='service', lazy='dynamic', cascade='all, delete-orphan')
    scope_requests = db.relationship('ScopeRequest', backref='service', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='service', lazy='dynamic', cascade='all, delete-orphan')

class GalleryImage(db.Model):
    __tablename__ = 'gallery_images'
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    image_filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScopeRequest(db.Model):
    __tablename__ = 'scope_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200))
    preferred_date = db.Column(db.DateTime)
    status = db.Column(db.Enum(ScopeStatus), default=ScopeStatus.REQUESTED)
    
    estimated_cost = db.Column(db.Float)
    estimated_hours = db.Column(db.Float)
    response_message = db.Column(db.Text)
    responded_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    scope_request_id = db.Column(db.Integer, db.ForeignKey('scope_requests.id'))
    
    scheduled_date = db.Column(db.DateTime)
    address = db.Column(db.String(300))
    notes = db.Column(db.Text)
    agreed_price = db.Column(db.Float)
    status = db.Column(db.Enum(BookingStatus), default=BookingStatus.PENDING)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    cancellation_reason = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False, unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    provider_response = db.Column(db.Text)
    response_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    booking = db.relationship('Booking', backref='review')