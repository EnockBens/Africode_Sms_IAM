import os

# Security configurations
SECRET_KEY = 'lFl76-rspYFn0IihJqEGaRpqKNg7du8gaBo6b6xEshU' 
SECURITY_PASSWORD_SALT = '29620583801938585979065387498578790966'

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'postgres://default:1qDmySO8idHt@ep-fancy-moon-a4vw0v68-pooler.us-east-1.aws.neon.tech:5432/verceldb?sslmode=require')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URI = database_url
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True,}

# Registration configurations
SECURITY_REGISTERABLE = True
SECURITY_CONFIRMABLE = True

# Cookie settings
REMEMBER_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_SAMESITE = 'Strict'

# Mail settings
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'bensonkings81@gmail.com'
MAIL_PASSWORD = 'vsazlawurlxgfpyv'
MAIL_DEFAULT_SENDER = 'enockbenz294@gmail.com'

# Password recovery
SECURITY_RECOVERABLE = True
