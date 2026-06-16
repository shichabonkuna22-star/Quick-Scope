import os
import sys
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Service, GalleryImage, ScopeRequest, Booking, Review, UserRole, BookingStatus, ScopeStatus

# ---------- Helper functions ----------
def random_phone():
    prefixes = ['082', '083', '084', '071', '072', '073', '074', '076', '078', '079']
    return random.choice(prefixes) + ''.join(str(random.randint(0, 9)) for _ in range(7))

def random_date(start, end):
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

# ---------- Data ----------
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

# ---------- Seed function ----------
def seed_data():
    with app.app_context():
        print("🌱 Seeding database (incremental)...")
        db.create_all()
        
        # Keep track of newly created users for login summary
        new_customers = []
        new_providers = []
        
        # ----- Create customers (if not exist) -----
        for cust in customers:
            user = User.query.filter_by(email=cust['email']).first()
            if not user:
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
                new_customers.append(cust)
                print(f"✅ Created customer: {cust['first_name']} {cust['last_name']} ({cust['email']})")
            else:
                print(f"ℹ️ Customer already exists: {cust['email']}")
        db.session.commit()
        
        # ----- Create providers, services, gallery -----
        provider_objs = []
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
                new_providers.append(prov)
                print(f"✅ Created provider: {prov['first_name']} {prov['last_name']} ({prov['email']})")
            else:
                print(f"ℹ️ Provider already exists: {prov['email']}")
            provider_objs.append(user)  # always add to list for later use
            
            # Create services for this provider (skip if title already exists for that provider)
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
                    print(f"  └─ Added service: {svc['title']}")
                else:
                    print(f"  └─ Service already exists: {svc['title']}")
            
            # Gallery images
            for img in prov['gallery']:
                existing = GalleryImage.query.filter_by(provider_id=user.id, caption=img['caption']).first()
                if not existing:
                    gallery_img = GalleryImage(
                        provider_id=user.id,
                        image_filename=f"https://picsum.photos/seed/{img['seed']}/400/300",
                        caption=img['caption']
                    )
                    db.session.add(gallery_img)
                    print(f"  └─ Added gallery: {img['caption']}")
                else:
                    print(f"  └─ Gallery already exists: {img['caption']}")
        
        db.session.commit()
        print("✅ Providers, services, and gallery created/updated.")
        
        # ----- Create bookings and scope requests for all users (new and existing) -----
        all_customers = User.query.filter_by(role=UserRole.CUSTOMER).all()
        all_providers = User.query.filter_by(role=UserRole.PROVIDER).all()
        all_services = Service.query.all()
        
        if not all_services:
            print("⚠️ No services found. Can't create bookings.")
            return
        
        # For each customer, create 1-2 new bookings if they have fewer than 3 bookings
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
                    print(f"  └─ Booking added for {customer.first_name} from {provider.business_name} - {status.value}")
        
        # ----- Create scope requests (some for each customer) -----
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
                print(f"✅ Scope request for {customer.first_name} on {service.title}")
        
        db.session.commit()
        print("✅ Bookings and scope requests created/updated.")
        
        # ----- Create reviews for completed bookings that don't have reviews -----
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
                print(f"✅ Review for booking #{booking.id} - {rating} stars")
        
        db.session.commit()
        print("✅ Reviews and responses created/updated.")
        
        # Print login details summary (only newly created users)
        print("\n🔐 LOGIN DETAILS (NEWLY ADDED USERS):")
        print("=" * 50)
        if new_customers:
            print("CUSTOMERS:")
            for cust in new_customers:
                print(f"  {cust['first_name']} {cust['last_name']} | {cust['email']} | password: {cust['password']}")
        if new_providers:
            print("\nPROVIDERS:")
            for prov in new_providers:
                print(f"  {prov['first_name']} {prov['last_name']} | {prov['email']} | password: {prov['password']}")
        if not new_customers and not new_providers:
            print("No new users created. All users already existed.")
        print("\n✅ Seeding complete!")

if __name__ == "__main__":
    seed_data()