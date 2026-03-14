ACCESS_TOKEN_TTL = 3600  # 1 hour
REFRESH_TOKEN_TTL = 2592000  # 30 days
MAX_ACTIVE_SESSIONS = 5

# Rate limiting
LOGIN_RATE_LIMIT = 10  # per minute
API_RATE_LIMIT = 1000  # per minute per user

# Supported auth providers
OAUTH_PROVIDERS = ['google', 'github', 'microsoft']
MFA_METHODS = ['totp', 'sms', 'email']

# Password requirements
MIN_PASSWORD_LENGTH = 12
REQUIRE_SPECIAL_CHAR = True
REQUIRE_NUMBER = True
PASSWORD_HISTORY_COUNT = 5

def validate_password(password: str) -> bool:
    if len(password) < MIN_PASSWORD_LENGTH:
        return False
    has_special = any(c in '!@#$%^&*()_+-=' for c in password)
    has_number = any(c.isdigit() for c in password)
    return has_special and has_number
