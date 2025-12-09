import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# Use override=True to ensure .env values override any system environment variables
load_dotenv(os.path.join(basedir, '.env'), override=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = False

    # Session Security Configuration
    # Note: Set SESSION_COOKIE_SECURE = True in production with HTTPS
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
    PERMANENT_SESSION_LIFETIME = 43200  # 12 hours (absolute timeout)
    SESSION_INACTIVITY_TIMEOUT = 43200  # 12 hours of inactivity before logout

    # Remember Me Cookie Configuration
    # Must match session timeout - otherwise users can bypass session expiry via remember cookie
    from datetime import timedelta
    REMEMBER_COOKIE_DURATION = timedelta(seconds=43200)  # 12 hours - match session timeout
    REMEMBER_COOKIE_HTTPONLY = True  # Prevent JavaScript access
    REMEMBER_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'

    # Security Headers Configuration
    # These headers protect against common web vulnerabilities
    SECURITY_HEADERS = {
        # Prevent MIME type sniffing
        'X-Content-Type-Options': 'nosniff',

        # Prevent clickjacking - only allow framing from same origin
        'X-Frame-Options': 'SAMEORIGIN',

        # Enable browser XSS protection (legacy, but still useful)
        'X-XSS-Protection': '1; mode=block',

        # Force HTTPS for 1 year (only applies if site is served over HTTPS)
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',

        # Control referrer information sent with requests
        'Referrer-Policy': 'strict-origin-when-cross-origin',

        # Restrict browser features and APIs
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()',

        # Prevent cross-origin information leaks (modern security header)
        'Cross-Origin-Opener-Policy': 'same-origin',

        # Control cross-origin resource loading
        'Cross-Origin-Resource-Policy': 'same-origin',

        # Prevent embedding in cross-origin contexts
        # Use 'credentialless' to allow cross-origin images (IPFS gateways) without CORP headers
        'Cross-Origin-Embedder-Policy': 'credentialless',
    }

    # Content Security Policy Configuration
    # WARNING: 'unsafe-inline' is used for scripts/styles due to Bootstrap and inline event handlers
    # For better security in production, consider:
    # 1. Using nonces for inline scripts/styles
    # 2. Moving inline event handlers to separate JS files
    # 3. Implementing a build process to hash static assets
    CONTENT_SECURITY_POLICY = {
        # Default fallback for all resource types
        'default-src': ["'self'"],

        # Scripts: Allow self, inline (needed for Bootstrap/templates), and CDNs
        # TODO: Replace 'unsafe-inline' with nonce-based approach for better security
        'script-src': [
            "'self'",
            "'unsafe-inline'",  # Required for inline <script> tags and onclick handlers
            "'wasm-unsafe-eval'",  # Required for WebAssembly (ZK proof generation with snarkjs)
            "https://cdn.jsdelivr.net",  # Bootstrap, Font Awesome CDN, snarkjs
            "https://unpkg.com",  # Additional libraries
            "https://code.jquery.com",  # jQuery CDN
            "https://cdnjs.cloudflare.com"  # Cloudflare CDN
        ],

        # Workers: Allow blob/data URLs for Web Workers (snarkjs uses these for parallel proof computation)
        'worker-src': [
            "'self'",
            "blob:",
            "data:"
        ],

        # Styles: Allow self, inline (needed for Bootstrap), and CDNs
        # TODO: Replace 'unsafe-inline' with nonce-based approach for better security
        'style-src': [
            "'self'",
            "'unsafe-inline'",  # Required for inline styles and style attributes
            "https://cdn.jsdelivr.net",  # Bootstrap CSS
            "https://unpkg.com",
            "https://fonts.googleapis.com",  # Google Fonts CSS
            "https://cdnjs.cloudflare.com"  # Cloudflare CDN
        ],

        # Fonts: Allow self and Google Fonts
        'font-src': [
            "'self'",
            "https://fonts.gstatic.com",  # Google Fonts hosting
            "https://cdn.jsdelivr.net",  # Font Awesome fonts
            "https://cdnjs.cloudflare.com"  # Cloudflare CDN fonts
        ],

        # Images: Allow self, data URIs, HTTPS images, and blobs
        'img-src': [
            "'self'",
            "data:",  # Data URIs for inline images
            "https:",  # Allow all HTTPS images (for external content)
            "blob:"  # Blob URLs (for file uploads preview)
        ],

        # AJAX/WebSocket connections: Allow same origin and CDN source maps
        'connect-src': [
            "'self'",
            "https://cdn.jsdelivr.net"  # Source maps for debugging
        ],

        # Frames: Disallow all frame embedding
        'frame-src': ["'none'"],

        # Plugins: Disallow all plugins (Flash, Java, etc.)
        'object-src': ["'none'"],

        # Base tag: Only allow same origin
        'base-uri': ["'self'"],

        # Form submissions: Only allow same origin
        'form-action': ["'self'"],

        # Frame ancestors: Prevent site from being framed (clickjacking protection)
        'frame-ancestors': ["'none'"],

        # Automatically upgrade HTTP requests to HTTPS
        'upgrade-insecure-requests': [],

        # Block mixed content (HTTP resources on HTTPS pages)
        'block-all-mixed-content': [],
    }

    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_HEADERS_ENABLED = True

    # Default rate limits for general endpoints
    RATELIMIT_DEFAULT = "200 per day, 50 per hour"

    # Authentication (strict - prevents brute force)
    RATELIMIT_LOGIN = "10 per minute"
    RATELIMIT_REGISTER = "5 per hour"
    RATELIMIT_PASSWORD_RESET = "3 per hour"

    # Market/Trading (generous - prevents bot trading)
    RATELIMIT_MARKET_BUY = "30 per minute"
    RATELIMIT_MARKET_SELL = "30 per minute"
    RATELIMIT_GOLD_TRADE = "20 per minute"

    # Gameplay (very generous - won't affect normal players)
    RATELIMIT_WORK = "100 per hour"
    RATELIMIT_TRAIN = "100 per hour"
    RATELIMIT_STUDY = "100 per hour"
    RATELIMIT_TRAVEL = "50 per hour"
    RATELIMIT_EAT_DRINK = "60 per hour"

    # Social (reasonable - prevents spam)
    RATELIMIT_SEND_MESSAGE = "20 per minute"
    RATELIMIT_FRIEND_REQUEST = "15 per hour"

    # Profile/Settings (reasonable)
    RATELIMIT_PROFILE_UPDATE = "10 per hour"
    RATELIMIT_AVATAR_UPLOAD = "5 per hour"

    # Company/Business (generous)
    RATELIMIT_COMPANY_CREATE = "10 per hour"
    RATELIMIT_COMPANY_ACTION = "50 per hour"

    # Admin (reasonable for admin actions)
    RATELIMIT_ADMIN_ACTION = "100 per hour"

    # Starter Protection - prevents attacking countries with only 1 region
    # Set to False to disable protection and allow full conquest
    STARTER_PROTECTION_ENABLED = os.environ.get('STARTER_PROTECTION_ENABLED', 'true').lower() == 'true'

    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache')
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_KEY_PREFIX = 'tactizen_'

    CACHE_REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    CACHE_REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    CACHE_REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    CACHE_REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')

    CACHE_TIMEOUT_COUNTRIES = 3600
    CACHE_TIMEOUT_RESOURCES = 1800
    CACHE_TIMEOUT_MARKET = 60
    CACHE_TIMEOUT_USER_STATS = 300
    CACHE_TIMEOUT_LEADERBOARD = 600

    DB_USER = os.environ.get('DATABASE_USER')
    DB_PASSWORD = os.environ.get('DATABASE_PASSWORD')
    DB_HOST = os.environ.get('DATABASE_HOST')
    DB_NAME = os.environ.get('DATABASE_NAME')

    if not all([DB_USER, DB_HOST, DB_NAME]):
        raise ValueError("Database configuration is incomplete. Check .env file.")

    if DB_PASSWORD:
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
    else:
        SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}@{DB_HOST}/{DB_NAME}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database Connection Pool Configuration
    # These settings optimize database connection handling for better performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,           # Number of persistent connections to maintain
        'max_overflow': 20,        # Additional connections allowed when pool is full
        'pool_timeout': 30,        # Seconds to wait for a connection before error
        'pool_recycle': 1800,      # Recycle connections after 30 minutes (avoid stale connections)
        'pool_pre_ping': True,     # Check connection health before use
    }

    UPLOAD_FOLDER = os.path.join(basedir, 'app/static/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB (images will be compressed on server)

    # Error Handling Configuration
    # Control error detail exposure
    PROPAGATE_EXCEPTIONS = None  # Let Flask decide based on DEBUG
    TRAP_HTTP_EXCEPTIONS = False  # Don't trap HTTP exceptions in production
    TRAP_BAD_REQUEST_ERRORS = None  # Let Flask decide based on DEBUG

    # API Configuration
    # Set to True to enable API endpoints
    API_ENABLED = os.environ.get('API_ENABLED', 'False').lower() == 'true'
    # API rate limits (stricter than web interface)
    RATELIMIT_API_DEFAULT = "100 per hour"
    RATELIMIT_API_READ = "200 per hour"
    RATELIMIT_API_WRITE = "50 per hour"
    RATELIMIT_API_ADMIN = "500 per hour"

    # Blockchain Configuration (for election results and NFT operations)
    WEB3_RPC_URL = os.environ.get('WEB3_RPC_URL', 'https://rpc.zerion.io/v1/base-sepolia')
    WEB3_PRIVATE_KEY = os.environ.get('WEB3_PRIVATE_KEY')  # Server wallet for publishing results
    NFT_CONTRACT_ADDRESS = os.environ.get('NFT_CONTRACT_ADDRESS')
    ELECTION_RESULTS_CONTRACT_ADDRESS = os.environ.get('ELECTION_RESULTS_CONTRACT_ADDRESS')


class DevelopmentConfig(Config):
    """Development environment configuration with relaxed security for debugging."""
    DEBUG = True
    TESTING = False

    # Development: Allow HTTP cookies for local testing
    SESSION_COOKIE_SECURE = False

    # Development: Longer session timeouts for easier testing (12 hours)
    PERMANENT_SESSION_LIFETIME = 43200  # 12 hours absolute timeout
    SESSION_INACTIVITY_TIMEOUT = 43200  # 12 hours inactivity timeout

    # Development: Less strict CSP for easier debugging
    # You can add 'unsafe-eval' here if needed for debugging tools

    # Development: Show detailed errors for debugging
    PROPAGATE_EXCEPTIONS = False  # Use Flask's error handlers
    TRAP_BAD_REQUEST_ERRORS = True  # Show details for bad requests


class ProductionConfig(Config):
    """Production environment configuration with maximum security."""
    DEBUG = False
    TESTING = False

    # Production: Larger connection pool for handling more concurrent users
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,           # More persistent connections for production load
        'max_overflow': 40,        # Allow up to 60 total connections under heavy load
        'pool_timeout': 30,        # Seconds to wait for a connection
        'pool_recycle': 1800,      # Recycle connections after 30 minutes
        'pool_pre_ping': True,     # Check connection health before use
    }

    # Production: Force HTTPS for session cookies
    SESSION_COOKIE_SECURE = True

    # Production: Stricter CSRF protection
    WTF_CSRF_SSL_STRICT = True

    # Production: Session timeouts
    PERMANENT_SESSION_LIFETIME = 43200  # 12 hours absolute timeout
    SESSION_INACTIVITY_TIMEOUT = 43200  # 12 hours inactivity timeout

    # Production: Remember cookie must also have short duration
    from datetime import timedelta
    REMEMBER_COOKIE_DURATION = timedelta(seconds=43200)  # 12 hours
    REMEMBER_COOKIE_SECURE = True  # HTTPS only

    # Production: More restrictive rate limits
    RATELIMIT_LOGIN = "5 per minute"
    RATELIMIT_REGISTER = "3 per hour"
    RATELIMIT_PASSWORD_RESET = "2 per hour"

    # Production: Use Redis for rate limiting (better performance and persistence)
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', "redis://localhost:6379/1")

    # Production: Never expose error details
    PROPAGATE_EXCEPTIONS = False  # Use custom error handlers
    TRAP_HTTP_EXCEPTIONS = False  # Handle HTTP exceptions gracefully
    TRAP_BAD_REQUEST_ERRORS = False  # Don't expose bad request details


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True

    # Testing: Use in-memory database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # Testing: Disable CSRF for easier testing
    WTF_CSRF_ENABLED = False

    # Testing: Disable rate limiting
    RATELIMIT_ENABLED = False

    # Testing: Disable security headers that might interfere with tests
    SECURITY_HEADERS = {}
    CONTENT_SECURITY_POLICY = {}


# Configuration dictionary for easy selection
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}