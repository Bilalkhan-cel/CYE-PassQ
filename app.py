import traceback as _tb

from flask import Flask, request, render_template, redirect, url_for,session,flash,jsonify,abort
import uuid
from flask_sqlalchemy import SQLAlchemy 
from sqlalchemy import Column, Integer, String ,CheckConstraint
from flask import send_file
# from werkzeug.security import generate_password_hash, check_password_hash     #for security and for making password appear in hask not in simple words
import io
from datetime import datetime , date, timedelta
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import mpdf 
import json
from chat import get_response
import pytesseract
from office import check_location , reset, branch_has_space
from admin import check_passport_data
from locations import LOCATIONS, PROVINCES, BRANCHES, ICT
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

import pandas as pd
import re
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_UR")# fallback
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
    dob=db.Column(db.Date,nullable=False)
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

                                                                
    __table_args__=(CheckConstraint('token<=800','token_max'),) 
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
    if datetime.now().time() >= datetime.strptime(CLOSING_TIME, '%H:%M').time():
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

@app.route("/voice")
@login_required
def voice_agent():
    # The browser talks to OpenHome directly, so it needs the key; only signed-in
    # users get this page, and it must never be cached by the browser or a proxy.
    resp = app.make_response(render_template(
        "voice_agent.html",
        openhome_api_key=os.getenv("OPENHOME_API_KEY"),
        openhome_agent_id=os.getenv("OPENHOME_AGENT_ID"),
    ))
    resp.headers["Cache-Control"] = "no-store, private"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp

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
    today=date.today()         #aj ki date return kry ga


    count_today=Passport.query.filter(
        db.func.date(Passport.created_date)==today
    ).count()                                               

    if count_today ==0:
        reset()
   
    


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

     get_token_number()
     daily_token=check_location(clean['branch'])       # ye aj ki date ki base pe total token number count kry ga agr 800 log pury hogye to next user pe koi token generate ni hoga

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

     db.session.add(passport_app)
     db.session.commit()
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
    submission_date=date.today()
    
    return render_template("thankyou.html", name=name, token=token,id=id,submission_date=submission_date) 
# passed id and token and name so that in thankyou.html we can use it to generate pdf and we can also see our name and token on screen
@app.route("/error")
def erro_r():
    name = request.args.get("name", "User",)
    error = request.args.get("error", "",)
    
    submission_date=date.today()
    
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
        with open("branches.json", encoding="utf-8") as f:
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


@app.route("/api/submit", methods=["POST"])
@require_api_auth
def api_submit():
    data = request.get_json(silent=True) or {}
    user = User.query.get(request.api_user_id)
    if not user:
        return jsonify({"success": False, "error": "user_not_found",
                         "message": "Account no longer exists"}), 404

    name = safe_str(data, "name", "")
    age_raw = safe_str(data, "age", "")
    dob_raw = safe_str(data, "dob", "")
    cnic = safe_str(data, "cnic", "")
    address = safe_str(data, "address", "")
    province = safe_str(data, "province", "")
    city = safe_str(data, "city", "")
    district = safe_str(data, "district", "")
    domicile = safe_str(data, "domicile", "")
    branch = safe_str(data, "branch", "")
    father_cnic = safe_str(data, "father_cnic", "")
    mother_cnic = safe_str(data, "mother_cnic", "")

    # CHANGED: the applicant's own email, as collected by the voice agent.
    # The account that's logged in for /api/submit is now always the fixed
    # kiosk/admin account (see the agent's auto-login), so we can't rely on
    # `user.email` to reach the actual applicant anymore - that would just
    # keep emailing the admin inbox for every single token. If the applicant
    # didn't give a usable email, we fall back to the logged-in account's
    # email so the message still goes somewhere and isn't silently dropped.
    applicant_email_raw = safe_str(data, "email", "")
    applicant_email = applicant_email_raw if is_valid_email(applicant_email_raw) else ""
    recipient_email = applicant_email or user.email

    if not all([name, cnic, address]):
        return jsonify({"success": False, "error": "missing_fields",
                         "message": "Name, CNIC and Address are required"}), 400

    if not age_raw.isdigit():
        return jsonify({"success": False, "error": "invalid_age",
                         "message": "Age must be a number"}), 400
    age = int(age_raw)

    if age < 18 and not all([father_cnic, mother_cnic]):
        return jsonify({"success": False, "error": "missing_guardian_cnic",
                         "message": "Father CNIC and Mother CNIC are required for minors"}), 400

    if not branch:
        return jsonify({"success": False, "error": "missing_branch",
                         "message": "Branch is required"}), 400

    try:
        dob = datetime.strptime(dob_raw, '%Y-%m-%d')
    except ValueError:
        return jsonify({"success": False, "error": "invalid_dob",
                         "message": "Date of birth must be in YYYY-MM-DD format"}), 400

    get_token_number()
    daily_token = check_location(branch)

    if daily_token is None:
        return jsonify({"success": False, "error": "invalid_branch",
                         "message": f"Branch '{branch}' was not recognized. Please use the exact branch name."}), 400

    if daily_token > 800:
        return jsonify({"success": False, "error": "daily_limit_reached",
                         "message": "Daily limit of 800 tokens reached. Try tomorrow."}), 400

    if datetime.now().time() >= datetime.strptime('19:00', '%H:%M').time():
        reset()
        return jsonify({"success": False, "error": "time_limit_reached",
                         "message": "Time limit reached for today. Please try again tomorrow."}), 400

    passport_app = Passport(
        user_id=user.id,
        token=daily_token, name=name, age=age_raw, dob=dob, cnic=cnic,
        address=address, province=province, city=city, district=district,
        domicile=domicile, branch=branch,
        email=recipient_email ,
        father_cnic=father_cnic if father_cnic else None,
        mother_cnic=mother_cnic if mother_cnic else None
    )

    try:
        db.session.add(passport_app)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        if "UNIQUE constraint" in str(e):
            return jsonify({"success": False, "error": "cnic_exists",
                             "message": "CNIC already exists in system"}), 400
        return jsonify({"success": False, "error": "server_error",
                         "message": f"Error occurred: {str(e)}"}), 500

    # Generate the PDF - if this fails, the token still exists in DB,
    # we just tell the caller the PDF/email step failed so they can retry /view/<id>
     # ---- PDF generation ----
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
    except Exception as e:
        tb_text = _tb.format_exc()
        print("=== PDF GENERATION FAILED ===\n", tb_text)
        return jsonify({
            "success": True, "token": passport_app.token, "id": passport_app.id,
            "pdf_generated": False, "email_sent": False,
            "message": f"Token generated but PDF creation failed: {str(e)}",
            "debug_traceback": tb_text
        }), 200

    # ---- Email sending ----
    email_sent = False
    email_error = None
    try:
        send_passport_email(
            passport_app.token, passport_app.name, passport_app.cnic,
            recipient_email, passport_app.branch, pdf_buffer
        )
        email_sent = True
    except Exception as e:
        email_error = _tb.format_exc()
        print("=== EMAIL SEND FAILED ===\n", email_error)

    return jsonify({
        "success": True,
        "token": passport_app.token,
        "id": passport_app.id,
        "pdf_generated": True,
        "email_sent": email_sent,
        "email_error": email_error,
        "recipient_email": recipient_email,
        "message": (
            f"Token {passport_app.token} generated. PDF sent to {recipient_email}."
            if email_sent else
            f"Token {passport_app.token} generated, but email could not be sent."
        )
    }), 200


def add_missing_columns():
    """create_all() never alters existing tables, so add new columns by hand.
    This keeps existing applications instead of dropping the database."""
    inspector = db.inspect(db.engine)
    if "passport" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("passport")}
    new_columns = {"phone": "VARCHAR(20)", "user_id": "INTEGER"}   # fixed names, no user input
    for name, sql_type in new_columns.items():
        if name not in existing:
            with db.engine.begin() as conn:
                conn.execute(db.text(f"ALTER TABLE passport ADD COLUMN {name} {sql_type}"))
            print(f"Added '{name}' column to passport table.")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        add_missing_columns()

        # Create tables for passport.d
       
    app.run(debug=True)

    # if the code isnot working in your system please install the following packages in real.txt
    # donot run test.py it is for deleteing and creating database again and again bascicallt for testing purpose onlyfrom flask import Flask, request, render_template, redirect, url_for,session,flash,jsonify
