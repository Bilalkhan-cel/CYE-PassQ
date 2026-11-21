"""
Account security helpers: password policy, password hashing, e-mail OTP codes,
and sign-up field checks. Used by the sign-up, sign-in and forgot-password routes.
"""

import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone


def utcnow():
    """Current UTC time without tzinfo (same form as the times already stored in the DB).
    Replaces the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from werkzeug.security import generate_password_hash, check_password_hash

from admin import EMAIL_RE, BLOCKED_EMAIL_DOMAINS, NAME_RE, PK_MOBILE_RE, _normalize_phone

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=10)        # code is valid for 10 minutes
OTP_MAX_ATTEMPTS = 5                   # wrong guesses before the code is burned
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
# Per-account limits that survive asking for a new code, so the 5-try cap
# can't be reset by requesting code after code:
OTP_WINDOW = timedelta(hours=1)
OTP_SENDS_PER_WINDOW = 5               # codes e-mailed per account per hour
OTP_FAILS_PER_WINDOW = 10              # wrong guesses per account per hour

PASSWORD_MIN = 8
PASSWORD_MAX = 64

COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "12345678", "123456789",
    "1234567890", "qwerty123", "qwertyuiop", "iloveyou", "pakistan", "pakistan123",
    "pakistan@123", "admin123", "welcome1", "welcome123", "abc12345", "abcd1234",
    "11111111", "00000000", "letmein1", "asdf1234", "zxcvbnm1",
}

_HASH_PREFIXES = ("scrypt:", "pbkdf2:")


# ── Passwords ────────────────────────────────────────────────────────────────

def password_problems(password, name="", cnic="", email=""):
    """Return a list of rules the password breaks (empty list = strong enough)."""
    problems = []
    if len(password) < PASSWORD_MIN:
        problems.append(f"at least {PASSWORD_MIN} characters")
    if len(password) > PASSWORD_MAX:
        problems.append(f"no more than {PASSWORD_MAX} characters")
    if not re.search(r"[A-Z]", password):
        problems.append("an uppercase letter (A-Z)")
    if not re.search(r"[a-z]", password):
        problems.append("a lowercase letter (a-z)")
    if not re.search(r"\d", password):
        problems.append("a number (0-9)")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("a special character (e.g. ! @ # $ %)")

    low = password.lower()
    if low in COMMON_PASSWORDS:
        problems.append("not be a commonly used password")
    cnic_digits = re.sub(r"\D", "", cnic or "")
    if cnic_digits and (cnic_digits in re.sub(r"\D", "", password) and len(cnic_digits) >= 5):
        problems.append("not contain your CNIC number")
    for part in (name or "").lower().split():
        if len(part) >= 3 and part in low:
            problems.append("not contain your name")
            break
    local = (email or "").lower().split("@")[0]
    if len(local) >= 3 and local in low:
        problems.append("not contain your email name")
    return problems


def password_error_message(problems):
    return "Password must have " + ", ".join(problems) + "."


def hash_password(password):
    return generate_password_hash(password)          # scrypt with a random salt


def is_hashed(stored):
    return bool(stored) and stored.startswith(_HASH_PREFIXES)


def verify_password(stored, password):
    """Check a password. Also accepts old plain-text rows (created before hashing)
    so existing users can still log in; the caller should then re-hash them."""
    if not stored or not password:
        return False
    if is_hashed(stored):
        return check_password_hash(stored, password)
    return hmac.compare_digest(stored.encode(), password.encode())


# ── One-time codes ───────────────────────────────────────────────────────────

def new_otp():
    """Return (code, code_hash). Only the hash is stored in the database."""
    code = f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"
    return code, generate_password_hash(code)


def otp_matches(code_hash, code):
    code = (code or "").strip()
    return bool(re.fullmatch(rf"\d{{{OTP_LENGTH}}}", code)) and check_password_hash(code_hash, code)


def otp_expiry():
    return utcnow() + OTP_TTL


def mask_email(email):
    """ali.khan@gmail.com -> al*****@gmail.com"""
    local, _, domain = email.partition("@")
    keep = local[:2] if len(local) > 2 else local[:1]
    return f"{keep}{'*' * max(len(local) - len(keep), 3)}@{domain}"


# ── Sign-up fields ───────────────────────────────────────────────────────────

def validate_signup(name, cnic, email, phone, password, confirm):
    """Return (errors: list[str], cleaned: dict)."""
    errors = []
    name = re.sub(r"\s+", " ", name or "").strip()
    if not name:
        errors.append("Full name is required.")
    elif len(name) > 100 or not NAME_RE.match(name) or len(name.split()) < 2:
        errors.append("Enter your full name in English letters (first and last name).")

    cnic_digits = re.sub(r"\D", "", cnic or "")
    if len(cnic_digits) != 13 or cnic_digits[0] not in "12345678" or len(set(cnic_digits)) == 1:
        errors.append("Enter a valid 13-digit CNIC number.")

    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or ".." in email:
        errors.append("Enter a valid email address.")
    elif email.split("@", 1)[1] in BLOCKED_EMAIL_DOMAINS:
        errors.append("Temporary or placeholder email addresses are not accepted.")

    clean_phone = None
    if phone and phone.strip():
        digits = _normalize_phone(phone)
        if not PK_MOBILE_RE.match(digits):
            errors.append("Enter a valid Pakistani mobile number, e.g. 0300-1234567.")
        else:
            clean_phone = "+92" + digits

    if password != confirm:
        errors.append("Passwords do not match.")
    problems = password_problems(password or "", name, cnic_digits, email)
    if problems:
        errors.append(password_error_message(problems))

    return errors, {"name": name, "cnic": cnic_digits, "email": email, "phone": clean_phone}
