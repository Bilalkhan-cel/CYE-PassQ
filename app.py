import traceback as _tb

from flask import Flask, request, render_template, redirect, url_for,session,flash,jsonify,abort
import uuid
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import Column, Integer, String ,CheckConstraint
from sqlalchemy.exc import IntegrityError
from flask import send_file
# from werkzeug.security import generate_password_hash, check_password_hash     #for security and for making password appear in hask not in simple words
import io
from datetime import datetime , date, timedelta
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import mpdf 
import json
from chat import get_response
from office import check_location , reset, branch_has_space, sync_counter, pk_now, pk_today
from voice_data import province_ur, place_ur, branch_ur
import speech
from timeslot import slot_window, time_slot
from admin import check_passport_data
from locations import LOCATIONS, PROVINCES, BRANCHES, ICT, allowed_branch_provinces
from collections import defaultdict, deque
from functools import wraps
from mail_sender import send_passport_email, send_otp_email
from mail_config import mail
import security as sec
from flask_mail import Mail
import os
from dotenv import load_dotenv
# Note: values are read once at start-up — after editing .env (mail, database, secret
# key), stop and restart the server; debug auto-reload does NOT pick up .env changes.
# (The chatbot settings are the exception: chat.py re-reads .env on every message.)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import re
import os

# The folder is "Templates" (capital T). Windows doesn't care, but Linux servers
# such as Vercel are case-sensitive, so name it explicitly.
#application configuration and initialization
app = Flask(__name__, template_folder="Templates")
_db_url = os.getenv("SQLALCHEMY_DATABASE_UR") or ""
if _db_url.startswith("postgres://"):           # Heroku/Supabase style; SQLAlchemy wants postgresql://
    _db_url = "postgresql://" + _db_url[len("postgres://"):]
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}   # hosted DBs drop idle connections
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'passport.regional.office100@gmail.com'
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWOR")   # NOT your Gmail password
app.config['MAIL_DEFAULT_SENDER'] = (
    'Regional Passport Office',
    'passport.regional.office100@gmail.com'
)
mail.init_app(app)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Signs login cookies and API tokens. Must be a long random value kept in .env —
# anyone who knows it can log in as any user.
_secret = os.getenv("SECRET_KEY", "")
if len(_secret) < 32:
    raise RuntimeError(
        "SECRET_KEY missing or too short. Add a line to .env like:\n"
        "  SECRET_KEY=<output of: python -c \"import secrets; print(secrets.token_hex(32))\">")
app.config['SECRET_KEY'] = _secret
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
db = SQLAlchemy(app)
vpdf=None
api_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt="api-token")
API_TOKEN_MAX_AGE = 3600  # 1 hour, matches a normal voice-session length

def require_api_auth(f):
    """Decorator for /api/* routes that need a logged-in user.
    Expects header: Authorization: Bearer <token from /api/signin>"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "missing_token",
                             "message": "Authorization header missing or malformed"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            user_id = api_serializer.loads(token, max_age=API_TOKEN_MAX_AGE)
        except SignatureExpired:
            return jsonify({"success": False, "error": "token_expired",
                             "message": "Session expired, please sign in again"}), 401
        except BadSignature:
            return jsonify({"success": False, "error": "invalid_token",
                             "message": "Invalid session token"}), 401
        request.api_user_id = user_id
        return f(*args, **kwargs)
    return wrapper

def login_required(f):
    """Decorator for web pages that need a signed-in user."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.method == "GET":
                session["next_url"] = request.path      # return here after signing in
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("signin"))
        return f(*args, **kwargs)
    return wrapper


def _safe_next(url):
    """Only allow redirects back to a page on this site (no //evil.com, no http://)."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None

# Identity documents are private: keep them OUT of /static (which anyone can
# download) — instance/ is not served by Flask and is git-ignored.
app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, "uploads")
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except OSError:
    # Read-only filesystem (e.g. Vercel): only /tmp is writable there.
    app.config['UPLOAD_FOLDER'] = os.path.join("/tmp", "uploads")
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 40 * 1024 * 1024    # whole request (7 files x 5 MB + form)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024                     # per file



#New database table for user accounts
class User(db.Model):
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    cnic = db.Column(db.String(50), unique=True, nullable=False)   
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hashed password
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=sec.utcnow)

#One-time e-mail codes for sign-up verification and password reset.
#Only a hash of the code is stored; the sign-up payload holds an already-hashed password.
class EmailOTP(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    purpose = db.Column(db.String(20), nullable=False)          # "signup" | "reset"
    email = db.Column(db.String(120), nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=True)              # set for "reset"
    code_hash = db.Column(db.String(255), nullable=False)
    payload = db.Column(db.Text, nullable=True)                 # JSON for "signup"
    attempts = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_sent_at = db.Column(db.DateTime, nullable=False, default=sec.utcnow)

#Log of codes sent / wrong codes per account, used to cap guessing across
#new codes. subject is "user:<id>" (reset) or "email:<address>" (sign-up).
class AuthEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kind = db.Column(db.String(20), nullable=False)             # "otp_sent" | "otp_fail"
    subject = db.Column(db.String(140), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=sec.utcnow, index=True)

#For form application
class Passport(db.Model):
   
    id=db.Column(db.Integer,primary_key=True,autoincrement=True)
    user_id=db.Column(db.Integer, nullable=True, index=True)   # account that filed it
    token=db.Column(db.Integer,nullable=False,default=0)
    name=db.Column(db.String(100),nullable=False)
    age=db.Column(db.String(100),nullable=False)
    dob=db.Column(db.Date,nullable=True)    # the voice agent does not ask for it (web form still does)
    email = db.Column(db.String(120), unique=False, nullable=False)
    phone = db.Column(db.String(20), nullable=True)   # +923XXXXXXXXX
    cnic=db.Column(db.String(50),nullable=False)
    address=db.Column(db.String(250),nullable=False)
    province=db.Column(db.String(100))
    city=db.Column(db.String(100))
    district=db.Column(db.String(100))
    domicile=db.Column(db.String(100))
    branch=db.Column(db.String(100))
    
    # only for users under 18
    father_cnic=db.Column(db.String(50), nullable=True)
    mother_cnic=db.Column(db.String(50), nullable=True)

    created_date=db.Column(db.DateTime, default=sec.utcnow)    # new column banaya hai jab koi new user aye ga from submit kry ga to us din ka date time automatically save ho jae ga database me 

    # Day the token number belongs to. With the unique index below, the database
    # itself refuses a second "token 5 at branch X today", even across servers.
    token_day=db.Column(db.Date, nullable=True)

    __table_args__=(CheckConstraint('token<=800','token_max'),
                    db.Index('uq_passport_branch_day_token', 'branch', 'token_day', 'token', unique=True))
# Add this route to your app.py file

@app.route('/')
@app.route('/home')
def home():
    """Home page - landing page for the passport token system"""
    return render_template('home.html')


# SignIn Page
@app.route("/", methods=['POST','GET'])
def index():
    return redirect(url_for('signin'))   # always send users to login first

# =====================================================================
# ACCOUNTS: sign-up with e-mail OTP, sign-in, forgot / reset password
# =====================================================================

def _send_otp(otp, name, code):
    """E-mail the code. Returns True on success (failure is logged, not shown)."""
    try:
        send_otp_email(otp.email, name, code, otp.purpose,
                       minutes_valid=int(sec.OTP_TTL.total_seconds() // 60))
        return True
    except Exception:
        print("=== OTP EMAIL FAILED ===\n", _tb.format_exc())
        return False


def _active_otp(session_key, purpose):
    """The OTP row this browser is working on, or None."""
    otp_id = session.get(session_key)
    if not isinstance(otp_id, int):
        return None
    return EmailOTP.query.filter_by(id=otp_id, purpose=purpose).first()


def _otp_subject(otp):
    return f"user:{otp.user_id}" if otp.purpose == "reset" else f"email:{otp.email}"


def _recent_events(kind, subject):
    since = sec.utcnow() - sec.OTP_WINDOW
    return AuthEvent.query.filter(AuthEvent.kind == kind, AuthEvent.subject == subject,
                                  AuthEvent.created_at >= since).count()


def _log_event(kind, subject):
    db.session.add(AuthEvent(kind=kind, subject=subject))
    # keep the table small: drop entries older than a day
    AuthEvent.query.filter(AuthEvent.created_at < sec.utcnow() - timedelta(days=1)).delete()
    db.session.commit()


def _send_blocked(subject, last_sent_at=None):
    """Return a message if another code may not be sent to this account yet, else None."""
    if last_sent_at is not None:
        wait = (last_sent_at + sec.OTP_RESEND_COOLDOWN) - sec.utcnow()
        if wait.total_seconds() > 0:
            return f"Please wait {int(wait.total_seconds()) + 1} seconds before requesting another code."
    if _recent_events("otp_sent", subject) >= sec.OTP_SENDS_PER_WINDOW:
        return "Too many codes requested. Please try again in an hour."
    return None


def _check_otp(otp, code):
    """Return None if the code is right, else an error message.

    Two limits apply: 5 tries per code (claimed atomically, so parallel requests
    can't exceed it) and 10 wrong codes per account per hour (kept even when a
    new code is issued)."""
    if otp is None or sec.utcnow() > otp.expires_at:
        return "This code has expired. Please request a new one."
    subject = _otp_subject(otp)
    if _recent_events("otp_fail", subject) >= sec.OTP_FAILS_PER_WINDOW:
        return "Too many wrong codes. Please wait an hour and try again."

    # Atomically use up one try: only succeeds while attempts < max.
    claimed = db.session.execute(
        db.update(EmailOTP)
          .where(EmailOTP.id == otp.id, EmailOTP.attempts < sec.OTP_MAX_ATTEMPTS)
          .values(attempts=EmailOTP.attempts + 1)
    ).rowcount
    db.session.commit()
    if not claimed:
        return "Too many wrong attempts. Please request a new code."
    db.session.refresh(otp)

    if not sec.otp_matches(otp.code_hash, code):
        _log_event("otp_fail", subject)
        left = sec.OTP_MAX_ATTEMPTS - otp.attempts
        return (f"Incorrect code. {left} attempt{'s' if left != 1 else ''} left."
                if left > 0 else "Too many wrong attempts. Please request a new code.")
    return None


#Sign-Up Page — step 1: details, then a code is e-mailed
@app.route("/signup",methods=['GET','POST'])
def signup():
    if request.method == "POST":
        f = request.form
        errors, clean = sec.validate_signup(f.get("name", ""), f.get("cnic", ""), f.get("email", ""),
                                            f.get("phone", ""), f.get("password", ""),
                                            f.get("confirm_password", ""))
        if not errors:
            if User.query.filter_by(cnic=clean["cnic"]).first():
                errors.append("An account with this CNIC already exists. Please sign in or reset your password.")
            if User.query.filter(db.func.lower(User.email) == clean["email"]).first():
                errors.append("An account with this email already exists. Please sign in or reset your password.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("signup.html", form=f), 400

        subject = f"email:{clean['email']}"
        blocked = _send_blocked(subject)
        if blocked:
            flash(blocked, "error")
            return render_template("signup.html", form=f), 429

        # Replace any earlier unfinished sign-up for this email.
        EmailOTP.query.filter_by(purpose="signup", email=clean["email"]).delete()
        code, code_hash = sec.new_otp()
        payload = dict(clean, password=sec.hash_password(f.get("password", "")))
        otp = EmailOTP(purpose="signup", email=clean["email"], code_hash=code_hash,
                       payload=json.dumps(payload), expires_at=sec.otp_expiry(),
                       last_sent_at=sec.utcnow())
        db.session.add(otp)
        db.session.commit()

        if not _send_otp(otp, clean["name"], code):
            db.session.delete(otp)
            db.session.commit()
            flash("We could not send the verification email. Please check the address and try again.", "error")
            return render_template("signup.html", form=f), 502

        _log_event("otp_sent", subject)
        session["signup_otp_id"] = otp.id
        flash(f"We sent a 6-digit code to {sec.mask_email(otp.email)}.", "success")
        return redirect(url_for("verify_email"))

    return render_template("signup.html", form={})


#Sign-Up Page — step 2: enter the e-mailed code, account is created
@app.route("/verify_email", methods=["GET", "POST"])
def verify_email():
    otp = _active_otp("signup_otp_id", "signup")
    if otp is None:
        flash("Your sign-up session has expired. Please register again.", "error")
        return redirect(url_for("signup"))

    if request.method == "POST":
        error = _check_otp(otp, request.form.get("code", ""))
        if error:
            flash(error, "error")
            return render_template("verify_otp.html", purpose="signup",
                                   masked_email=sec.mask_email(otp.email)), 400

        data = json.loads(otp.payload)
        if (User.query.filter_by(cnic=data["cnic"]).first() or
                User.query.filter(db.func.lower(User.email) == data["email"]).first()):
            db.session.delete(otp)
            db.session.commit()
            session.pop("signup_otp_id", None)
            flash("An account with this CNIC or email already exists. Please sign in.", "error")
            return redirect(url_for("signin"))

        user = User(name=data["name"], cnic=data["cnic"], email=data["email"],
                    password=data["password"], phone=data.get("phone"))
        try:
            db.session.add(user)
            db.session.delete(otp)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error creating account. Please try again.", "error")
            return redirect(url_for("signup"))
        session.pop("signup_otp_id", None)
        flash("Email verified and account created! You can now sign in.", "success")
        return redirect(url_for("signin"))

    return render_template("verify_otp.html", purpose="signup", masked_email=sec.mask_email(otp.email))


@app.route("/resend_otp/<purpose>", methods=["POST"])
def resend_otp(purpose):
    if purpose not in ("signup", "reset"):
        return redirect(url_for("signin"))
    key = "signup_otp_id" if purpose == "signup" else "reset_otp_id"
    target = "verify_email" if purpose == "signup" else "reset_password"
    otp = _active_otp(key, purpose)
    if otp is None:
        # For reset this is also the "no such account" case: answer exactly the same way.
        if purpose == "reset":
            flash(RESET_SENT_MESSAGE, "success")
            return redirect(url_for("reset_password"))
        flash("Your sign-up session has expired. Please register again.", "error")
        return redirect(url_for("signup"))

    blocked = _send_blocked(_otp_subject(otp), otp.last_sent_at)
    if blocked:
        if purpose == "reset":
            # Don't reveal (via a different message) that this account exists.
            flash(RESET_SENT_MESSAGE, "success")
        else:
            flash(blocked, "error")
        return redirect(url_for(target))

    if purpose == "signup":
        name = json.loads(otp.payload).get("name", "Applicant")
    else:
        user = db.session.get(User, otp.user_id)
        name = user.name if user else "Applicant"
    code, otp.code_hash = sec.new_otp()
    otp.attempts = 0
    otp.expires_at = sec.otp_expiry()
    otp.last_sent_at = sec.utcnow()
    db.session.commit()
    if _send_otp(otp, name, code):
        _log_event("otp_sent", _otp_subject(otp))
    flash("A new code has been sent." if purpose == "signup" else RESET_SENT_MESSAGE, "success")
    return redirect(url_for(target))


RESET_SENT_MESSAGE = ("If an account matches, a 6-digit code has been sent to its registered email. "
                      "Codes can be requested once a minute, up to 5 per hour.")


@app.route("/signin",methods=['GET','POST'])
def signin():
    if request.method == 'POST':
        cnic = re.sub(r'\D', '', request.form.get("cnic", ""))
        password = request.form.get("password", "")

        if not all([cnic, password]):
            flash("Please enter both CNIC and Password", "error")
            return render_template("signin.html")

        user = User.query.filter_by(cnic=cnic).first()
        # Old accounts were saved in plain text (and stripped); new ones are hashed.
        attempt = password if (user and sec.is_hashed(user.password)) else password.strip()

        if user and sec.verify_password(user.password, attempt):
            if not sec.is_hashed(user.password):          # upgrade old plain-text password
                user.password = sec.hash_password(attempt)
                db.session.commit()
            next_url = _safe_next(session.get("next_url"))
            session.clear()                               # fresh session on login
            session['user_id'] = user.id
            session['user_cnic'] = user.cnic
            session['user_name'] = user.name
            session['user_email'] = user.email

            flash(f"Welcome {user.name}! Signed in successfully.", "success")
            return redirect(next_url or url_for('dashboard'))

        flash("Invalid CNIC or Password", "error")
    return render_template("signin.html")


#Forgot password — step 1: CNIC or email, a code goes to the registered email
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip()
        if not ident:
            flash("Enter your CNIC number or email address.", "error")
            return render_template("forgot_password.html"), 400

        if "@" in ident:
            user = User.query.filter(db.func.lower(User.email) == ident.lower()).first()
        else:
            digits = re.sub(r"\D", "", ident)
            user = User.query.filter_by(cnic=digits).first() if len(digits) == 13 else None

        session.pop("reset_otp_id", None)
        if user:
            subject = f"user:{user.id}"
            current = EmailOTP.query.filter_by(purpose="reset", user_id=user.id) \
                                    .order_by(EmailOTP.id.desc()).first()
            if _send_blocked(subject, current.last_sent_at if current else None):
                # Too soon / too many: no new code. Keep the one already sent usable.
                if current and sec.utcnow() <= current.expires_at:
                    session["reset_otp_id"] = current.id
            else:
                EmailOTP.query.filter_by(purpose="reset", user_id=user.id).delete()
                code, code_hash = sec.new_otp()
                otp = EmailOTP(purpose="reset", email=user.email, user_id=user.id,
                               code_hash=code_hash, expires_at=sec.otp_expiry(),
                               last_sent_at=sec.utcnow())
                db.session.add(otp)
                db.session.commit()
                if _send_otp(otp, user.name, code):
                    _log_event("otp_sent", subject)
                session["reset_otp_id"] = otp.id

        # Same answer whether or not the account exists, or is throttled (no account fishing).
        flash(RESET_SENT_MESSAGE, "success")
        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")


#Forgot password — step 2: code + new password
@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        code = request.form.get("code", "")
        otp = _active_otp("reset_otp_id", "reset")
        user = db.session.get(User, otp.user_id) if otp else None
        if not user:
            flash("Incorrect or expired code. Please request a new one.", "error")
            return render_template("reset_password.html"), 400

        # Check the new password first, so a weak password doesn't use up a code try.
        password = request.form.get("password", "")
        if password != request.form.get("confirm_password", ""):
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", code=code), 400
        problems = sec.password_problems(password, user.name, user.cnic, user.email)
        if problems:
            flash(sec.password_error_message(problems), "error")
            return render_template("reset_password.html", code=code), 400

        error = _check_otp(otp, code)
        if error:
            flash(error, "error")
            return render_template("reset_password.html"), 400

        user.password = sec.hash_password(password)
        EmailOTP.query.filter_by(purpose="reset", user_id=user.id).delete()
        db.session.commit()
        session.pop("reset_otp_id", None)
        flash("Your password has been reset. Please sign in with your new password.", "success")
        return redirect(url_for("signin"))

    return render_template("reset_password.html")


def _own_applications_filter():
    """Applications the signed-in user may see: the ones they filed, plus old rows
    (from before user_id existed) whose CNIC matches their account."""
    legacy = db.and_(Passport.user_id.is_(None),
                     db.func.replace(Passport.cnic, "-", "") == session.get("user_cnic", ""))
    return db.or_(Passport.user_id == session.get("user_id"), legacy)


def _clock(dt):
    return dt.strftime("%I:%M").lstrip("0")


@app.template_filter("arrival")
def arrival_window(token):
    """The 20-minute arrival window for a token, in English and Urdu (same rule as timeslot.py)."""
    try:
        start, end = slot_window(int(token))
    except (TypeError, ValueError):
        return None
    ap = end.strftime("%p")
    en = f"{_clock(start)} – {_clock(end)} {ap}" if start.strftime("%p") == ap \
        else f"{_clock(start)} {start.strftime('%p')} – {_clock(end)} {ap}"
    h = start.hour
    part = "صبح" if h < 12 else ("دوپہر" if h < 15 else "سہ پہر")
    return {"en": en, "ur": f"{part} {_clock(start)} – {_clock(end)}"}


@app.template_filter("branch_ur")
def _branch_ur_filter(name):
    return branch_ur(name) if name else ""


@app.context_processor
def _pk_today():
    return {"pk_today": pk_now().date()}


@app.route("/dashboard", methods=['GET'])
@login_required
def dashboard():
    tokens = Passport.query.filter(_own_applications_filter()) \
                           .order_by(Passport.created_date.desc()).all()
    return render_template("dashboard.html",tokens=tokens)   # passport form

@app.route("/token_form" , methods=['GET','POST'])
@login_required
def token_form():
    try:
     return render_form()
    except Exception as e:
       return f"{str(e)}"


CLOSING_TIME = "19:00"

def office_closed_message():
    """Tokens are only issued before 7 PM."""
    if pk_now().time() >= datetime.strptime(CLOSING_TIME, '%H:%M').time():   # Pakistan time
        return "Tokens are issued only before 7:00 PM. Please apply again tomorrow."
    return None


def render_form(values=None, errors=None, form_error=None, status=200):
    """Show the application form. On a failed submit, `values` refills what the
    user typed and `errors` marks the wrong fields, so nothing has to be re-entered."""
    values = dict(values or {})
    # Files can't be refilled by the browser; never echo them back.
    return render_template("form.html",
                           provinces=PROVINCES,
                           locations=LOCATIONS,
                           branches=BRANCHES,
                           ict=ICT,
                           values=values,
                           errors=errors or {},
                           form_error=form_error or office_closed_message()), status


def collect_form(form):
    """Map the HTML form fields to the validator's input dict."""
    g = lambda k, d="": (form.get(k, d) or "").strip()
    return {
        "name": g("name"), "age": g("age"), "dob": g("dob"), "cnic": g("cnic"),
        "email": g("email"), "phone": g("phone"), "country_code": g("country_code", "+92"),
        "address": g("address"), "province": g("province"), "city": g("city"),
        "district": g("district"), "domicile": g("domicile"), "branch": g("branch"),
        "father_cnic": g("fcnic"), "mother_cnic": g("mcnic"), "consent": g("terms"),
    }


@app.route("/validate_form", methods=["POST"])
@login_required
def validate_form():
    """Live validation used by the form while the user types. Same rules as /submit."""
    result = check_passport_data(collect_form(request.form))
    errors = dict(result["errors"])
    branch = result["cleaned"].get("branch")
    if "branch" not in errors and branch:
        get_token_number()
        if not branch_has_space(branch):
            errors["branch"] = "This branch has issued all of today's tokens. Please choose another branch."
    return jsonify({"valid": not errors, "errors": errors, "form_error": office_closed_message()})


@app.route("/signout")
def signout():
    # Clear the session so the user is no longer logged in
    session.clear()

    # Flash a message to confirm logout
    flash("You have been signed out.", "info")

    # Redirect to home
    return redirect(url_for("signin"))


@app.route("/chats")
@login_required
def chbot():
    return render_template("chat.html")

# =====================================================================
# PUBLIC VOICE AGENT (no login) - for citizens without an account.
# Signed-in users can still use the web form; both share one token counter
# (issue_branch_token) and the same validation rules.
# =====================================================================
_rate_hits = defaultdict(deque)


def _client_ip():
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "?").split(",")[0].strip()


def _rate_limited(bucket, limit, window_seconds):
    """Small in-memory limiter for the public voice endpoints (per server instance)."""
    now = datetime.now().timestamp()
    hits = _rate_hits[(bucket, _client_ip())]
    while hits and hits[0] <= now - window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        return True
    hits.append(now)
    return False


def _same_site():
    """Browsers label cross-site requests; refuse them so other sites can't use our agent."""
    return request.headers.get("Sec-Fetch-Site", "same-origin") in ("same-origin", "none")


def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.route("/voice")
def voice_agent():
    """The voice agent page - open to everyone, no sign-in."""
    return _no_store(app.make_response(render_template(
        "voice_agent.html", stt_server=speech.is_configured(),
        # Sent once after connecting to open the token ability; must be one of
        # the ability's trigger words in the OpenHome dashboard.
        trigger_phrase=os.getenv("VOICE_TRIGGER_PHRASE", "پاسپورٹ ٹوکن"))))


@app.route("/api/voice/session")
def api_voice_session():
    """Gives the page the OpenHome stream address. It is not written into the page
    HTML, is rate-limited, same-site only and never cached. (The browser must
    connect to OpenHome itself: Vercel functions cannot relay WebSockets.)"""
    if not _same_site():
        return jsonify({"success": False, "error": "forbidden"}), 403
    if _rate_limited("session", 20, 3600):
        return jsonify({"success": False, "error": "rate_limited"}), 429
    key, agent = os.getenv("OPENHOME_API_KEY"), os.getenv("OPENHOME_AGENT_ID")
    if not key or not agent:
        return jsonify({"success": False, "error": "not_configured"}), 503
    return _no_store(jsonify({
        "success": True,
        "ws_url": f"wss://app.openhome.com/websocket/voice-stream/{key}/{agent}",
    }))


@app.route("/api/voice/status")
def api_voice_status():
    """Is the office issuing tokens right now? (Checked before any questions.)"""
    closed = office_closed_message()
    return jsonify({"success": True, "open": not closed, "now": pk_now().strftime("%H:%M"),
                    "closing": CLOSING_TIME, "message": closed or ""})


@app.route("/api/voice/options")
def api_voice_options():
    """Option bubbles for the voice funnel: Urdu label shown, English value stored.

    level=province | domicile
    level=district & province=
    level=city     & province= & district=
    level=branch   & province= (& district= & city= to put nearby branches first)
    Branches follow the web form's rule: own province or Islamabad.
    """
    level = request.args.get("level", "")
    province = request.args.get("province", "")
    district = request.args.get("district", "")
    city = request.args.get("city", "")

    if level in ("province", "domicile"):
        options = [{"value": p, "label": province_ur(p)} for p in LOCATIONS]
    elif level == "district":
        if province not in LOCATIONS:
            return jsonify({"success": False, "error": "unknown_province"}), 400
        # Districts with a passport office first (where most people are), then the rest.
        branch_cities = {b["city"] for b in BRANCHES.values() if b["province"] == province}
        has_branch = lambda d: d in branch_cities or bool(branch_cities & set(LOCATIONS[province][d]))
        options = [{"value": d, "label": place_ur(d)}
                   for d in sorted(LOCATIONS[province], key=lambda d: (not has_branch(d), place_ur(d)))]
    elif level == "city":
        cities = LOCATIONS.get(province, {}).get(district)
        if cities is None:
            return jsonify({"success": False, "error": "unknown_district"}), 400
        options = [{"value": c, "label": place_ur(c)} for c in cities]
    elif level == "branch":
        if province not in LOCATIONS:
            return jsonify({"success": False, "error": "unknown_province"}), 400
        get_token_number()
        allowed = allowed_branch_provinces(province)
        options = []
        for name, info in BRANCHES.items():
            if info["province"] not in allowed:
                continue
            options.append({
                "value": name, "label": branch_ur(name),
                "near": info["city"] in (city, district),
                "own_province": info["province"] == province,
                "full": not branch_has_space(name),
            })
        options.sort(key=lambda o: (not o["near"], not o["own_province"]))
    else:
        return jsonify({"success": False, "error": "unknown_level"}), 400
    return jsonify({"success": True, "level": level, "options": options})


@app.route("/api/stt", methods=["POST"])
def api_stt():
    """Urdu speech -> text (free Whisper large-v3 on Groq). 503 = use the browser's own."""
    if not _same_site():
        return jsonify({"success": False, "error": "forbidden"}), 403
    if _rate_limited("stt", 60, 600):
        return jsonify({"success": False, "error": "rate_limited"}), 429
    upload = request.files.get("audio")
    if not upload:
        return jsonify({"success": False, "error": "no_audio"}), 400
    audio = upload.read(speech.MAX_AUDIO_BYTES + 1)
    if len(audio) > speech.MAX_AUDIO_BYTES:
        return jsonify({"success": False, "error": "too_large"}), 413
    if len(audio) < 1000:                       # a click, not speech
        return jsonify({"success": True, "text": ""})
    try:
        text = speech.transcribe_urdu(audio, upload.filename or "speech.webm", upload.mimetype)
    except speech.SpeechUnavailable as exc:
        print("=== STT UNAVAILABLE ===", exc)
        return jsonify({"success": False, "error": "stt_unavailable"}), 503
    return jsonify({"success": True, "text": text})

CHAT_LIMIT = 20                         # messages per user ...
CHAT_WINDOW = timedelta(minutes=10)     # ... per 10 minutes (each message costs API credit)

@app.route("/chats", methods=["POST"])
@login_required
def chats():
    data = request.get_json(silent=True) or {}
    user_msg = data.get("message")
    if not isinstance(user_msg, str) or not user_msg.strip():
        return jsonify({"reply": "Please type your passport question."}), 400

    subject = f"user:{session['user_id']}"
    recent = AuthEvent.query.filter(AuthEvent.kind == "chat", AuthEvent.subject == subject,
                                    AuthEvent.created_at >= sec.utcnow() - CHAT_WINDOW).count()
    if recent >= CHAT_LIMIT:
        return jsonify({"reply": "You have sent many messages in a short time. "
                                 "Please wait a few minutes and try again."}), 429
    _log_event("chat", subject)

    bot_reply = get_response(user_msg, data.get("history"))
    return jsonify({"reply": bot_reply})


def get_token_number():
    today=pk_today()           #aj ki date (Pakistan time; Vercel servers run on UTC)


    count_today=Passport.query.filter(
        Passport.token_day==today
    ).count()                                               

    if count_today ==0:
        reset()


def issue_branch_token(branch):
    """The single token-number rule for BOTH the web form and the voice agent.

    Takes the branch's next number from branches.json, then double-checks it
    against today's saved applications for that branch, so a token number is
    never handed out twice (e.g. when two server instances share one database).
    Returns the number, None (unknown branch), 0 (closed) or >800 (full today).
    """
    get_token_number()
    number = check_location(branch)
    if not number or number > 800:
        return number
    issued_today = Passport.query.filter(
        Passport.branch == branch,
        Passport.token_day == pk_today(),
    ).count()
    if issued_today >= number:
        number = issued_today + 1
        if number > 800:
            return 801
        sync_counter(branch, number)
    return number


def save_with_unique_token(passport_app):
    """Save a new application (web form and voice agent).

    If another server gave out the same token number a moment earlier, the
    unique index refuses this save; we take the next number and try again.
    Returns the saved token number, or None if the branch filled up meanwhile.
    """
    passport_app.token_day = pk_today()
    for _ in range(5):
        db.session.add(passport_app)
        try:
            db.session.commit()
            return passport_app.token
        except IntegrityError as exc:
            db.session.rollback()
            if "uq_passport_branch_day_token" not in str(exc) and "token_day" not in str(exc):
                raise                                   # some other problem: not ours to fix here
            number = issue_branch_token(passport_app.branch)
            if not number or number > 800:
                return None
            passport_app.token = number
    raise RuntimeError("Could not find a free token number after 5 tries.")

    


UPLOAD_FIELDS_ADULT = ["cnic_front", "cnic_back"]
UPLOAD_FIELDS_MINOR = ["bform", "father_cnic_front", "father_cnic_back",
                       "mother_cnic_front", "mother_cnic_back"]
# Recognise files by their first bytes, not by the name or the browser's claim.
_FILE_SIGNATURES = [(b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"), (b"%PDF-", "pdf")]


def check_uploads(files, is_minor):
    """Return (errors, accepted) where accepted = [(field, file, extension)]."""
    errors, accepted = {}, []
    for field in (UPLOAD_FIELDS_MINOR if is_minor else UPLOAD_FIELDS_ADULT):
        f = files.get(field)
        if not f or not f.filename:
            errors[field] = "Please upload this document."
            continue
        head = f.stream.read(8)
        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        ext = next((e for sig, e in _FILE_SIGNATURES if head.startswith(sig)), None)
        if ext is None:
            errors[field] = "Only JPG, PNG or PDF files are allowed."
        elif size > MAX_UPLOAD_BYTES:
            errors[field] = "File must be 5 MB or smaller."
        else:
            accepted.append((field, f, ext))
    return errors, accepted


def save_uploads(passport_id, accepted):
    """Store files privately under instance/uploads/<id>/ with unguessable names."""
    folder = os.path.join(app.config['UPLOAD_FOLDER'], str(int(passport_id)))
    os.makedirs(folder, exist_ok=True)
    for field, f, ext in accepted:
        f.save(os.path.join(folder, f"{field}_{uuid.uuid4().hex}.{ext}"))


@app.route("/submit", methods=["POST"])
@login_required
def submit():
    
    if request.method=='POST':
    
     data_val = collect_form(request.form)
     age, dob, cnic = data_val["age"], data_val["dob"], data_val["cnic"]

     # 1) Strict rule-based validation FIRST, so a rejected form never uses up a token.
     #    (The form already validates live via /validate_form; this is the safety net.)
     validation_result = check_passport_data(data_val)

     if not validation_result['is_valid']:
            return render_form(request.form, validation_result['errors'], status=400)

     clean = validation_result['cleaned']

     upload_errors, uploads = check_uploads(request.files, is_minor=int(age) < 18)
     if upload_errors:
            return render_form(request.form, upload_errors, status=400)

     # 2) Office hours check, then allocate the branch token.
     closed = office_closed_message()
     if closed:
            reset()
            return render_form(request.form, form_error=closed, status=400)

     daily_token=issue_branch_token(clean['branch'])   # ye aj ki date ki base pe total token number count kry ga agr 800 log pury hogye to next user pe koi token generate ni hoga (same rule as the voice agent)

     if daily_token is None or daily_token == 0 or daily_token > 800:
            return render_form(request.form,
                               {"branch": "This branch has issued all of today's tokens. Please choose another branch."},
                               status=400)

     dob=datetime.strptime(dob, '%Y-%m-%d')
     father_cnic = clean['father_cnic'] or ""
     mother_cnic = clean['mother_cnic'] or ""

     passport_app = Passport(         #daily reset ho k token number de ga
            user_id=session['user_id'],
            token=daily_token,
            name=clean['name'],
            age=age,
            dob=dob,
            cnic=cnic,
            email=clean['email'],
            phone=clean['phone'],
            address=clean['address'],
            province=clean['province'],
            city=clean['city'],
            district=clean['district'],
            domicile=clean['domicile'],
            branch=clean['branch'],
            father_cnic=clean['father_cnic'],
            mother_cnic=clean['mother_cnic']
        )
     name, email, address = clean['name'], clean['email'], clean['address']
     province, city, district = clean['province'], clean['city'], clean['district']
     domicile, branch = clean['domicile'], clean['branch']

     daily_token = save_with_unique_token(passport_app)   # same safe save as the voice agent
     if daily_token is None:
            return render_form(request.form,
                               {"branch": "This branch has issued all of today's tokens. Please choose another branch."},
                               status=400)
     pdf_data=mpdf.makepdf(
         daily_token, name, dob, age,
         cnic,email, address, city,
         domicile, province, district,branch,
         father_cnic=father_cnic,
         mother_cnic=mother_cnic,
         parent_cnic=father_cnic  # Primary guardian CNIC
         )
     send_passport_email(daily_token,name,cnic,email,branch,pdf_data)

     save_uploads(passport_app.id, uploads)

    return redirect(url_for("thank_you",
                                    name=passport_app.name,
                                    token=passport_app.token,
                                    id=passport_app.id)) 

@app.route("/thankyou")
def thank_you():
    name = request.args.get("name", "User",)
    token = request.args.get("token", "",)
    id = request.args.get("id", "",)
    submission_date=pk_today()
    # The citizen's own application (never someone else's guessed id) supplies the
    # office and arrival window shown on the ticket.
    app_row = None
    if "user_id" in session and str(id).isdigit():
        app_row = Passport.query.filter(Passport.id == int(id), _own_applications_filter()).first()
    if app_row is not None:
        name, token = app_row.name, app_row.token
    return render_template("thankyou.html", name=name, token=token,id=id,submission_date=submission_date,
                           branch=app_row.branch if app_row else None)
# passed id and token and name so that in thankyou.html we can use it to generate pdf and we can also see our name and token on screen
@app.route("/error")
def erro_r():
    name = request.args.get("name", "User",)
    error = request.args.get("error", "",)
    
    submission_date=pk_today()
    
    return render_template("error.html", name=name, reason=error,submission_date=submission_date)    # passed id and token and name so that in thankyou.html we can use it to generate pdf and we can also see our name and token on screen


@app.route("/view/<int:id>")
@login_required
def view(id):
    # Only the account that filed the application may open it. Anyone else
    # (or a guessed id) gets the same 404 as a missing record.
    pass_app = Passport.query.filter(Passport.id == id, _own_applications_filter()).first()
    if pass_app is None:
        abort(404)
    try:
        # Call PDF function with all parameters including minor fields

        pdf_data=mpdf.makepdf(
                pass_app.token, pass_app.name, pass_app.dob, pass_app.age,
                pass_app.cnic,pass_app.email, pass_app.address, pass_app.city,
                pass_app.domicile, pass_app.province, pass_app.district,pass_app.branch,
                father_cnic=pass_app.father_cnic,
                mother_cnic=pass_app.mother_cnic,
                parent_cnic=pass_app.father_cnic  # Primary guardian CNIC
                )
        
        return send_file(pdf_data, as_attachment=False, download_name="passport_token.pdf", mimetype='application/pdf')
          # send file is flask method to send file to user without saving it locally as we have pdf in bytes so we can use send_file
     # as_attachment=False it will open in browser if true it will download directly
     # download_name is for flask 2.0 and above if below use attachment_filename


    except Exception:
        print("=== PDF GENERATION FAILED ===\n", _tb.format_exc())
        return "Could not generate the PDF right now. Please try again.", 500
    

# =====================================================================
# API ROUTES - used by the OpenHome voice Ability (JSON in/out, not HTML)
# =====================================================================

def safe_str(data, key, default=""):
    """Like str(data.get(key, default)).strip(), but treats JSON null (None)
    the same as a missing key - avoids the value literally becoming 'None'."""
    value = data.get(key, default)
    if value is None:
        value = default
    return str(value).strip()


def is_valid_email(value: str) -> bool:
    """Very loose sanity check - good enough to catch STT/LLM leftovers
    like a missing '@' without pretending to be a full RFC validator."""
    return bool(value) and "@" in value and "." in value.split("@")[-1]


@app.route("/api/branches", methods=["GET"])
def api_branches():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "branches.json"), encoding="utf-8") as f:
            branches_data = json.load(f)
        return jsonify({"success": True, "branches": list(branches_data.keys())}), 200
    except Exception as e:
        return jsonify({"success": False, "error": "server_error", "message": str(e)}), 500


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or {}

    name = safe_str(data, "name", "")
    cnic = safe_str(data, "cnic", "")
    email = safe_str(data, "email", "")
    password = safe_str(data, "password", "")
    confirm_password = safe_str(data, "confirm_password", password)
    phone = safe_str(data, "phone", "")

    if not all([name, cnic, email, password]):
        return jsonify({"success": False, "error": "missing_fields",
                         "message": "Name, CNIC, Email and Password are required"}), 400

    if password != confirm_password:
        return jsonify({"success": False, "error": "password_mismatch",
                         "message": "Passwords do not match"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "weak_password",
                         "message": "Password must be at least 6 characters"}), 400

    if User.query.filter_by(cnic=cnic).first():
        return jsonify({"success": False, "error": "cnic_exists",
                         "message": "CNIC already exists"}), 400

    try:
        new_user = User(
            name=name, cnic=cnic, email=email,
            password=sec.hash_password(password), phone=phone
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"success": True, "message": "Account created successfully",
                         "user_id": new_user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "server_error",
                         "message": f"Could not create account: {str(e)}"}), 500


@app.route("/api/signin", methods=["POST"])
def api_signin():
    data = request.get_json(silent=True) or {}

    cnic = safe_str(data, "cnic", "")
    # cnic = re.sub(r'\D', '', cnic)
    password = safe_str(data, "password", "")

    if not all([cnic, password]):
        return jsonify({"success": False, "error": "missing_fields",
                         "message": "CNIC and Password are required"}), 400

    user = User.query.filter_by(cnic=cnic).first()

    if not user or not sec.verify_password(user.password, password):
        return jsonify({"success": False, "error": "invalid_credentials",
                         "message": "Invalid CNIC or Password"}), 401
    if not sec.is_hashed(user.password):          # upgrade old plain-text password
        user.password = sec.hash_password(password)
        db.session.commit()

    api_token = api_serializer.dumps(user.id)

    return jsonify({
        "success": True,
        "message": f"Welcome {user.name}",
        "api_token": api_token,
        "expires_in": API_TOKEN_MAX_AGE,
        "user": {"id": user.id, "name": user.name, "email": user.email, "cnic": user.cnic}
    }), 200


# The voice agent does not collect these, so their "required" rules are skipped.
VOICE_IGNORED_FIELDS = {"phone", "dob"}
# Validator field names (web form inputs) -> the names the voice agent uses.
VOICE_FIELD_NAMES = {"fcnic": "father_cnic", "mcnic": "mother_cnic", "terms": "consent"}
VOICE_FIELDS = ("name", "age", "dob", "cnic", "email", "address", "province", "district",
                "city", "domicile", "branch", "father_cnic", "mother_cnic", "consent")


def _dashed_cnic(value):
    """'3520212345673' or '35202-1234567-3' -> '35202-1234567-3'; anything else unchanged."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return (value or "").strip()


def _token_issued_today(cnic):
    """Today's application for this CNIC (stored dashed by the form, digits by old API calls)."""
    return Passport.query.filter(
        db.or_(Passport.cnic == cnic, Passport.cnic == cnic.replace("-", "")),
        Passport.token_day == pk_today(),
    ).order_by(Passport.id.desc()).first()


def _slot_info(token):
    start, end = slot_window(token)
    return {"arrival": time_slot(token), "date": pk_today().isoformat(),
            "slot_start": start.strftime("%H:%M"), "slot_end": end.strftime("%H:%M")}


@app.route("/api/submit", methods=["POST"])
@require_api_auth
def api_submit():
    """Token request from the voice agent.

    Same rules as the web form (/submit): office hours first, the same
    field validation (admin.check_passport_data), and the same branch token
    counter (issue_branch_token, max 800 a day). Skipped only because the voice
    agent does not collect them: date of birth, phone number and document
    uploads. Email is optional - people without one may skip it.
    Extra rule for the public, no-login agent: one token per CNIC per day.
    """
    data = request.get_json(silent=True) or {}
    user = db.session.get(User, request.api_user_id)
    if not user:
        return jsonify({"success": False, "error": "user_not_found",
                         "message": "Account no longer exists"}), 404

    # 1) Office hours first, exactly like /submit.
    closed = office_closed_message()
    if closed:
        reset()
        return jsonify({"success": False, "error": "time_limit_reached", "message": closed}), 400

    # 2) Field rules - the same validator the web form uses.
    fields = {key: safe_str(data, key, "") for key in VOICE_FIELDS}
    for key in ("cnic", "father_cnic", "mother_cnic"):
        fields[key] = _dashed_cnic(fields[key])
    fields["country_code"] = "+92"

    result = check_passport_data(fields)
    errors = {k: v for k, v in result["errors"].items() if k not in VOICE_IGNORED_FIELDS}
    if fields["dob"] and "dob" in result["errors"]:
        errors["dob"] = result["errors"]["dob"]           # a date that WAS sent must be valid
    if not fields["email"]:
        errors.pop("email", None)                         # optional for the voice agent
    if errors:
        return jsonify({"success": False, "error": "validation_failed",
                         "fields": {VOICE_FIELD_NAMES.get(k, k): v for k, v in errors.items()},
                         "message": result["reason"]}), 400
    clean = result["cleaned"]
    cnic = fields["cnic"]

    # 3) One token per CNIC per day.
    existing = _token_issued_today(cnic)
    if existing:
        return jsonify({"success": False, "error": "already_issued_today",
                         "token": existing.token, "branch": existing.branch,
                         "branch_ur": branch_ur(existing.branch),
                         **_slot_info(existing.token),
                         "message": "A token has already been issued today for this CNIC."}), 409

    # 4) Branch token number - the exact counter the web form uses.
    daily_token = issue_branch_token(clean["branch"])
    if daily_token is None:
        return jsonify({"success": False, "error": "invalid_branch",
                         "message": "Branch was not recognized."}), 400
    if daily_token == 0:
        return jsonify({"success": False, "error": "time_limit_reached",
                         "message": "Tokens are issued only before 7:00 PM."}), 400
    if daily_token > 800:
        return jsonify({"success": False, "error": "daily_limit_reached",
                         "message": "This branch has issued all of today's tokens."}), 400

    recipient_email = clean["email"] or user.email
    passport_app = Passport(
        user_id=user.id, token=daily_token, name=clean["name"], age=fields["age"],
        dob=datetime.strptime(fields["dob"], "%Y-%m-%d") if fields["dob"] else None,
        cnic=cnic, email=recipient_email, phone=None, address=clean["address"],
        province=clean["province"], city=clean["city"], district=clean["district"],
        domicile=clean["domicile"], branch=clean["branch"],
        father_cnic=clean["father_cnic"], mother_cnic=clean["mother_cnic"],
    )
    try:
        saved = save_with_unique_token(passport_app)
    except Exception:
        db.session.rollback()
        print("=== VOICE TOKEN SAVE FAILED ===\n", _tb.format_exc())
        return jsonify({"success": False, "error": "server_error",
                         "message": "Could not save the application."}), 500
    if saved is None:
        return jsonify({"success": False, "error": "daily_limit_reached",
                         "message": "This branch has issued all of today's tokens."}), 400

    reply = {
        "success": True, "token": passport_app.token, "id": passport_app.id,
        "branch": passport_app.branch, "branch_ur": branch_ur(passport_app.branch),
        "applicant_email": clean["email"] or None, **_slot_info(passport_app.token),
    }

    # PDF + email. If either fails the token still stands; we just say so.
    try:
        pdf_buffer = mpdf.makepdf(
            passport_app.token, passport_app.name, passport_app.dob, passport_app.age,
            passport_app.cnic, passport_app.email, passport_app.address, passport_app.city,
            passport_app.domicile, passport_app.province, passport_app.district,
            passport_app.branch,
            father_cnic=passport_app.father_cnic,
            mother_cnic=passport_app.mother_cnic,
            parent_cnic=passport_app.father_cnic
        )
    except Exception:
        print("=== PDF GENERATION FAILED ===\n", _tb.format_exc())
        return jsonify({**reply, "pdf_generated": False, "email_sent": False,
                        "message": f"Token {passport_app.token} generated, but the PDF could not be created."}), 200

    email_sent = False
    try:
        send_passport_email(
            passport_app.token, passport_app.name, passport_app.cnic,
            recipient_email, passport_app.branch, pdf_buffer
        )
        email_sent = True
    except Exception:
        print("=== EMAIL SEND FAILED ===\n", _tb.format_exc())

    return jsonify({**reply, "pdf_generated": True, "email_sent": email_sent,
                    "message": (f"Token {passport_app.token} generated." if email_sent else
                                f"Token {passport_app.token} generated, but email could not be sent.")}), 200


def add_missing_columns():
    """create_all() never alters existing tables, so add new columns by hand.
    This keeps existing applications instead of dropping the database."""
    inspector = db.inspect(db.engine)
    if "passport" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("passport")}
    new_columns = {"phone": "VARCHAR(20)", "user_id": "INTEGER", "token_day": "DATE"}   # fixed names, no user input
    for name, sql_type in new_columns.items():
        if name not in existing:
            with db.engine.begin() as conn:
                conn.execute(db.text(f"ALTER TABLE passport ADD COLUMN {name} {sql_type}"))
            print(f"Added '{name}' column to passport table.")
    # Old rows keep token_day empty; the database treats empty values as all
    # different, so they never clash with the rule.
    with db.engine.begin() as conn:
        conn.execute(db.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_passport_branch_day_token "
                             "ON passport (branch, token_day, token)"))


def make_dob_optional():
    """Voice-agent tokens have no date of birth. Databases created before that
    have passport.dob NOT NULL, which create_all() never relaxes, so relax it here.
    Existing rows are copied over unchanged."""
    inspector = db.inspect(db.engine)
    if "passport" not in inspector.get_table_names():
        return
    old_cols = {c["name"]: c for c in inspector.get_columns("passport")}
    if "dob" not in old_cols or old_cols["dob"].get("nullable", True):
        return
    with db.engine.begin() as conn:
        if db.engine.dialect.name == "sqlite":
            # SQLite cannot drop NOT NULL in place: rebuild the table from the model.
            conn.execute(db.text("ALTER TABLE passport RENAME TO passport_old"))
            old_indexes = conn.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='passport_old' AND sql IS NOT NULL")).scalars().all()
            for index_name in old_indexes:                  # names come from sqlite itself
                conn.execute(db.text(f'DROP INDEX "{index_name}"'))
            Passport.__table__.create(conn)
            shared = ", ".join(c.name for c in Passport.__table__.columns if c.name in old_cols)
            conn.execute(db.text(f"INSERT INTO passport ({shared}) SELECT {shared} FROM passport_old"))
            conn.execute(db.text("DROP TABLE passport_old"))
        else:
            conn.execute(db.text("ALTER TABLE passport ALTER COLUMN dob DROP NOT NULL"))
    print("passport.dob is now optional (voice agent tokens have no date of birth).")


def init_db():
    """Runs on import too, because serverless hosts (Vercel) never run __main__."""
    try:
        with app.app_context():
            db.create_all()
            add_missing_columns()
            make_dob_optional()
    except Exception:
        print("=== DATABASE INIT FAILED ===\n", _tb.format_exc())


init_db()


if __name__ == '__main__':
    app.run()

    # if the code isnot working in your system please install the following packages in real.txt
    # donot run test.py it is for deleteing and creating database again and again bascicallt for testing purpose onlyfrom flask import Flask, request, render_template, redirect, url_for,session,flash,jsonify
