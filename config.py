import os
import pytz

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-key-change-in-production'
    
    # Database – use Render's DATABASE_URL if set, else local SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///quickscope.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Google OAuth (set these as environment variables on Render)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'your-google-client-id'
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'your-google-client-secret'
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    # South Africa settings
    TIMEZONE = 'Africa/Johannesburg'   # SAST
    CURRENCY = 'R'                     # ZAR

    # Display formats
    DATETIME_FORMAT = '%b %d, %Y at %H:%M'
    DATE_FORMAT = '%b %d, %Y'