"""
Standalone Gmail SMTP test - run this directly with:
    python test_smtp.py
It does NOT touch Flask, Flask-Mail, or your app at all. If this fails,
the problem is 100% your Gmail account / App Password / network - not
your Flask code. If this succeeds, the problem is somewhere in how
Flask-Mail is being invoked (mail_config.py / app context / pdf buffer).
"""
import smtplib
from email.mime.text import MIMEText

MAIL_USERNAME = "passport.regional.office100@gmail.com"
MAIL_PASSWORD = ""   # the App Password from app.py
TO_ADDRESS = "bilalahmedkhan6002@gmail.com"  # <-- change this

msg = MIMEText("This is a plain test email from a standalone script.")
msg["Subject"] = "SMTP test"
msg["From"] = MAIL_USERNAME
msg["To"] = TO_ADDRESS

try:
    print("Connecting to smtp.gmail.com:587 ...")
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
    server.set_debuglevel(1)   # prints the full SMTP conversation
    server.starttls()
    print("Logging in ...")
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    print("Sending ...")
    server.sendmail(MAIL_USERNAME, [TO_ADDRESS], msg.as_string())
    server.quit()
    print("SUCCESS - email sent.")
except Exception as e:
    import traceback
    print("FAILED:")
    traceback.print_exc()