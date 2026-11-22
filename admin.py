"""
Pakistan Passport Office — Data Validity Checker (strict, rule-based only).

No AI / network calls: every check below is a deterministic rule, so
validation is instant and gives the same answer every time.

Input : dict with keys
          name, age, dob (YYYY-MM-DD), cnic, email, phone, country_code,
          address, province, district, city, domicile, branch,
          father_cnic, mother_cnic, consent (minors only)
Output: {
          "is_valid": bool,
          "reason":   str,               # one-line summary
          "errors":   {form_field_name: msg}, # e.g. {"cnic": "..."}
          "labelled": {field_label: msg},     # same, with readable labels
          "cleaned":  {...}              # normalised values to store
        }
"""

import re
from datetime import date, datetime
from office import pk_today

from locations import (
    LOCATIONS, BRANCHES, normalize_province, allowed_branch_provinces,
)

CNIC_RE = re.compile(r"^(\d{5})-(\d{7})-(\d)$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")
EMAIL_RE = re.compile(
    r"^(?=.{6,120}$)"                         # overall length
    r"[A-Za-z0-9](?:[A-Za-z0-9._%+\-]{0,62}[A-Za-z0-9])?"   # local part
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+"  # domain labels
    r"[A-Za-z]{2,24}$"                        # TLD
)
ADDRESS_RE = re.compile(r"^[A-Za-z0-9\s,./#\-()':]+$")
# Pakistani mobile numbers: 3 + network code (30x–34x, or 355 for SCO) + 7 digits.
PK_MOBILE_RE = re.compile(r"^3(?:[0-4]\d|55)\d{7}$")

# Placeholder / throw-away email domains.
BLOCKED_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "domain.com",
    "mailinator.com", "yopmail.com", "10minutemail.com", "guerrillamail.com",
    "tempmail.com", "temp-mail.org", "trashmail.com", "sharklasers.com",
    "getnada.com", "dispostable.com", "maildrop.cc", "throwawaymail.com",
    "fakeinbox.com",
}

MAX_AGE = 120

# Form input name -> label shown to the user.
FIELD_LABELS = {
    "name": "Full Name", "age": "Age", "dob": "Date of Birth", "cnic": "CNIC",
    "fcnic": "Father's CNIC", "mcnic": "Mother's CNIC", "terms": "Parental Consent",
    "email": "Email", "phone": "Phone Number", "address": "Address",
    "province": "Province", "district": "District", "city": "City",
    "domicile": "Domicile", "branch": "Branch",
}


def _s(data, key):
    value = data.get(key)
    return "" if value is None else str(value).strip()


def _repeats(text, n):
    """True if any character repeats n or more times in a row."""
    return re.search(r"(.)\1{%d,}" % (n - 1), text.lower()) is not None


def _check_cnic(value, label, errors):
    """Validate a CNIC / B-Form number. Returns the match or None."""
    m = CNIC_RE.match(value)
    if not m:
        errors[label] = "Format must be XXXXX-XXXXXXX-X (e.g. 35202-1234567-3)."
        return None
    digits = value.replace("-", "")
    if digits[0] not in "12345678":
        errors[label] = "First digit must be a valid NADRA region code (1–8)."
        return None
    if len(set(digits)) == 1 or m.group(2) == "0000000":
        errors[label] = "This is not a real CNIC number."
        return None
    return m


def _normalize_phone(raw):
    """Accept 3XXXXXXXXX, 03XXXXXXXXX, 923XXXXXXXXX or +923XXXXXXXXX."""
    digits = re.sub(r"[\s\-()]", "", raw)
    if digits.startswith("+92"):
        digits = digits[3:]
    elif digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits


def check_passport_data(data: dict) -> dict:
    errors = {}
    cleaned = {}

    name = _s(data, "name")
    age_raw = _s(data, "age")
    dob_raw = _s(data, "dob")
    cnic = _s(data, "cnic")
    email = _s(data, "email")
    phone_raw = _s(data, "phone")
    country_code = _s(data, "country_code")
    address = _s(data, "address")
    province_raw = _s(data, "province")
    district = _s(data, "district")
    city = _s(data, "city")
    domicile_raw = _s(data, "domicile")
    branch = _s(data, "branch")
    father_cnic = _s(data, "father_cnic")
    mother_cnic = _s(data, "mother_cnic")
    consent = _s(data, "consent").lower()

    # ── NAME ────────────────────────────────────────────────────────────────
    name = re.sub(r"\s+", " ", name)
    words = name.split(" ") if name else []
    if not name:
        errors["name"] = "Name is required."
    elif len(name) > 100:
        errors["name"] = "Name must be 100 characters or fewer."
    elif not NAME_RE.match(name):
        errors["name"] = "Name may contain only English letters, spaces, dots, hyphens or apostrophes."
    elif len(words) < 2:
        errors["name"] = "Enter your full name (at least first and last name)."
    elif sum(c.isalpha() for c in name) < 4:
        errors["name"] = "Name is too short."
    elif _repeats(name, 3):
        errors["name"] = "Name contains the same letter repeated; please enter your real name."
    cleaned["name"] = name

    # ── DATE OF BIRTH ───────────────────────────────────────────────────────
    dob = None
    today = pk_today()
    if not dob_raw:
        errors["dob"] = "Date of birth is required."
    else:
        try:
            dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
        except ValueError:
            errors["dob"] = "Date of birth must be a valid date (YYYY-MM-DD)."
        else:
            if dob > today:
                errors["dob"] = "Date of birth cannot be in the future."
                dob = None
            elif dob.year < today.year - MAX_AGE:
                errors["dob"] = f"Date of birth cannot be more than {MAX_AGE} years ago."
                dob = None

    # ── AGE ─────────────────────────────────────────────────────────────────
    age = None
    if not age_raw:
        errors["age"] = "Age is required."
    elif not age_raw.isdigit():
        errors["age"] = "Age must be a whole number (digits only)."
    else:
        age = int(age_raw)
        if age > MAX_AGE:
            errors["age"] = f"Age must be between 0 and {MAX_AGE}."
            age = None

    if age is not None and dob is not None:
        real_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age != real_age:
            errors["age"] = f"Age ({age}) does not match date of birth (age should be {real_age})."
    is_minor = age is not None and age < 18

    # ── APPLICANT CNIC / B-FORM ─────────────────────────────────────────────
    if not cnic:
        errors["cnic"] = "CNIC / B-Form number is required."
    else:
        _check_cnic(cnic, "cnic", errors)

    # ── PARENTS (minors only) ───────────────────────────────────────────────
    if is_minor:
        if not father_cnic:
            errors["fcnic"] = "Father's CNIC is required for applicants under 18."
        elif _check_cnic(father_cnic, "fcnic", errors):
            if int(father_cnic[-1]) % 2 == 0:
                errors["fcnic"] = "Father's CNIC must end in an odd digit (male CNIC)."
            elif father_cnic == cnic:
                errors["fcnic"] = "Father's CNIC cannot be the same as the applicant's."

        if not mother_cnic:
            errors["mcnic"] = "Mother's CNIC is required for applicants under 18."
        elif _check_cnic(mother_cnic, "mcnic", errors):
            if int(mother_cnic[-1]) % 2 == 1:
                errors["mcnic"] = "Mother's CNIC must end in an even digit (female CNIC)."
            elif mother_cnic == cnic:
                errors["mcnic"] = "Mother's CNIC cannot be the same as the applicant's."
            elif mother_cnic == father_cnic:
                errors["mcnic"] = "Mother's and father's CNIC cannot be the same."

        if consent not in ("on", "true", "yes", "1"):
            errors["terms"] = "Parental consent must be ticked for applicants under 18."
    else:
        # Adults: parent CNICs are not collected.
        father_cnic = mother_cnic = ""
    cleaned["father_cnic"] = father_cnic or None
    cleaned["mother_cnic"] = mother_cnic or None

    # ── EMAIL ───────────────────────────────────────────────────────────────
    email = email.lower()
    if not email:
        errors["email"] = "Email is required."
    elif not EMAIL_RE.match(email) or ".." in email:
        errors["email"] = "Enter a valid email address (e.g. name@gmail.com)."
    elif email.split("@", 1)[1] in BLOCKED_EMAIL_DOMAINS:
        errors["email"] = "Temporary or placeholder email addresses are not accepted."
    cleaned["email"] = email

    # ── PHONE ───────────────────────────────────────────────────────────────
    cleaned["phone"] = None
    if country_code and country_code != "+92":
        errors["phone"] = "Only Pakistani mobile numbers (+92) are accepted."
    elif not phone_raw:
        errors["phone"] = "Phone number is required."
    else:
        phone = _normalize_phone(phone_raw)
        if not PK_MOBILE_RE.match(phone):
            errors["phone"] = "Enter a valid Pakistani mobile number, e.g. 3001234567 (+92 3XX XXXXXXX)."
        elif _repeats(phone[3:], 7):
            errors["phone"] = "This is not a real phone number."
        else:
            cleaned["phone"] = "+92" + phone

    # ── ADDRESS ─────────────────────────────────────────────────────────────
    address = re.sub(r"\s+", " ", address)
    if not address:
        errors["address"] = "Address is required."
    elif len(address) < 10:
        errors["address"] = "Address is too short (minimum 10 characters)."
    elif len(address) > 250:
        errors["address"] = "Address must be 250 characters or fewer."
    elif not ADDRESS_RE.match(address):
        errors["address"] = "Address contains characters that are not allowed."
    elif sum(c.isalpha() for c in address) < 5:
        errors["address"] = "Address must include street / area names, not just numbers."
    elif _repeats(address, 5):
        errors["address"] = "Address looks invalid (repeated characters)."
    cleaned["address"] = address

    # ── PROVINCE → DISTRICT → CITY ──────────────────────────────────────────
    province = normalize_province(province_raw)
    if not province_raw:
        errors["province"] = "Province is required."
    elif not province:
        errors["province"] = f"'{province_raw}' is not a province or territory of Pakistan."

    if not district:
        errors["district"] = "District is required."
    elif province and district not in LOCATIONS[province]:
        errors["district"] = f"District '{district}' is not in {province}."

    if not city:
        errors["city"] = "City is required."
    elif province and district in LOCATIONS.get(province, {}):
        if city not in LOCATIONS[province][district]:
            errors["city"] = f"City '{city}' is not in {district} district, {province}."
    elif province:
        in_province = any(city in cities for cities in LOCATIONS[province].values())
        if not in_province:
            errors["city"] = f"City '{city}' is not in {province}."
    cleaned["province"] = province
    cleaned["district"] = district
    cleaned["city"] = city

    # ── DOMICILE (any valid province/territory) ─────────────────────────────
    domicile = normalize_province(domicile_raw)
    if not domicile_raw:
        errors["domicile"] = "Domicile is required."
    elif not domicile:
        errors["domicile"] = f"'{domicile_raw}' is not a valid domicile province or territory."
    cleaned["domicile"] = domicile

    # ── BRANCH (own province or Islamabad) ──────────────────────────────────
    if not branch:
        errors["branch"] = "Passport office branch is required."
    elif branch not in BRANCHES:
        errors["branch"] = "Selected branch does not exist."
    elif province and BRANCHES[branch]["province"] not in allowed_branch_provinces(province):
        errors["branch"] = (
            f"This branch is in {BRANCHES[branch]['province']}. "
            f"Applicants from {province} can choose a branch in {province} or Islamabad."
        )
    cleaned["branch"] = branch

    # ── RESULT ──────────────────────────────────────────────────────────────
    if errors:
        n = len(errors)
        return {
            "is_valid": False,
            "reason": f"{n} field{'s' if n > 1 else ''} failed validation. Please correct and resubmit.",
            "errors": errors,
            "labelled": {FIELD_LABELS.get(k, k): v for k, v in errors.items()},
            "cleaned": cleaned,
        }
    return {
        "is_valid": True,
        "reason": "All checks passed.",
        "errors": {},
        "labelled": {},
        "cleaned": cleaned,
    }
