
from flask_mail import Message
from mail_config import mail






def send_passport_email(
    token_number: int,
    name: str,
    Cnic: int,
    email: str,
    branch: str,
    pdf_data
    
   
):
    """
    Sends a passport token confirmation email with a PDF attachment.

    Parameters:
        email (str): Recipient's email address.
        name (str): Applicant's name.
        token_number (str): Generated token number.
        branch (str): Passport office branch.
        appointment_date (str): Appointment date.
        appointment_time (str): Appointment time.
        pdf_buffer (BytesIO): PDF buffer returned by your PDF generation function.
    """

    msg = Message(
        subject="Passport Token Confirmation",
        recipients=[email]
    )
    # Escape everything that goes into the HTML, so a value like
    # "<a href=...>" shows as text instead of becoming a link in an official email.
    from markupsafe import escape
    pdf_token = token_number
    name, Cnic, branch, token_number = escape(name), escape(Cnic), escape(branch), escape(token_number)
    msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
            color: #333333;
        }}
        .email-container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }}
        .header-banner {{
            background-color: #005436; /* Pakistan Flag Green */
            color: #ffffff;
            text-align: center;
            padding: 20px;
        }}
        .header-banner h2 {{
            margin: 0;
            font-size: 20px;
            letter-spacing: 1px;
        }}
        .header-banner p {{
            margin: 5px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .email-body {{
            padding: 30px;
        }}
        .success-msg {{
            color: #005436;
            font-weight: bold;
            font-size: 16px;
        }}
        .token-card {{
            background-color: #f9fdfa;
            border-left: 4px solid #005436;
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 4px 4px 0;
        }}
        .token-card table {{
            width: 100%;
        }}
        .token-card td {{
            padding: 8px 0;
            font-size: 15px;
        }}
        .label {{
            font-weight: bold;
            color: #555555;
            width: 40%;
        }}
        .value {{
            color: #111111;
            font-weight: bold;
        }}
        .instructions {{
            background-color: #fff9e6;
            padding: 15px 20px;
            border-radius: 4px;
            margin-top: 20px;
        }}
        .instructions h4 {{
            margin-top: 0;
            color: #856404;
        }}
        .instructions ul {{
            margin: 0;
            padding-left: 20px;
            color: #555555;
        }}
        .instructions li {{
            margin-bottom: 8px;
        }}
        .footer {{
            background-color: #333333;
            color: #ffffff;
            text-align: center;
            padding: 20px;
            font-size: 12px;
        }}
        .footer a {{
            color: #00e676;
            text-decoration: none;
        }}
    </style>
</head>
<body>

<div class="email-container">
    <!-- Header Banner -->
    <div class="header-banner">
        <h2>Directorate General of Immigration & Passports</h2>
        <p>Government of Pakistan</p>
    </div>

    <!-- Email Content -->
    <div class="email-body">
        <p>Dear <strong>{name}</strong>,</p>
        <p class="success-msg">✅ Your passport token has been successfully generated.</p>

        <!-- Token Details Box -->
        <div class="token-card">
            <table>
                <tr>
                    <td class="label">Token Number:</td>
                    <td class="value">{token_number}</td>
                </tr>
                <tr>
                    <td class="label">Branch:</td>
                    <td class="value">{branch}</td>
                </tr>
                <tr>
                    <td class="label">CNIC:</td>
                    <td class="value">{Cnic}</td>
                </tr>
            </table>
        </div>

        <!-- Instructions Box -->
        <div class="instructions">
            <h4>⚠️ Important: Please bring the following on your appointment day:</h4>
            <ul>
                <li>Original CNIC</li>
                <li>Required Supporting Documents</li>
                <li><strong>Attached PDF Token</strong> (Printout or on your phone)</li>
            </ul>
        </div>

        <p style="margin-top: 30px;">Thank you for using our digital service.</p>
        <p>Regards,<br><strong>e-Services Team</strong></p>
    </div>

    <!-- Footer -->
    <div class="footer">
        <p>This is an automated email, please do not reply to this address.</p>
        <p>&copy; 2026 Directorate General of Immigration & Passports, Government of Pakistan. All rights reserved.</p>
        <p><a href="https://dgip.gov.pk">Visit our Official Website</a></p>
    </div>
</div>

</body>
</html>
"""

#     msg.body = f"""
# Dear {name},

# Your passport token has been successfully generated.

# Token Number: {token_number}
# Branch: {branch}
# CNIC: {Cnic}


# Please bring the following on your appointment day:

# • Original CNIC
# • Required Documents
# • Attached PDF Token

# Thank you for using our service.

# Regards,

# Directorate General of Immigration & Passports
# Government of Pakistan
# """

    # Reset buffer position before reading
    pdf_data.seek(0)

    # Attach PDF
    msg.attach(
        filename=f"Passport_Token_{int(pdf_token)}.pdf",
        content_type="application/pdf",
        data=pdf_data.read()
    )

    # Send email
    mail.send(msg)

def send_otp_email(email: str, name: str, code: str, purpose: str, minutes_valid: int = 10):
    """Send a one-time verification code. purpose: 'signup' or 'reset'."""
    from markupsafe import escape
    if purpose == "reset":
        subject = "Password Reset Code – DGIP Portal"
        intro = "We received a request to reset the password of your DGIP portal account."
        ignore = "If you did not ask to reset your password, ignore this email — your password will not change."
    else:
        subject = "Verify Your Email – DGIP Portal"
        intro = "Thank you for registering on the DGIP passport portal. Use the code below to verify your email address."
        ignore = "If you did not try to register, you can safely ignore this email."

    msg = Message(subject=subject, recipients=[email])
    msg.body = (
        f"Dear {name},\n\n{intro}\n\nYour code: {code}\n\n"
        f"This code expires in {minutes_valid} minutes. Never share it with anyone — "
        f"DGIP staff will never ask for it.\n\n{ignore}\n\n"
        "Directorate General of Immigration & Passports"
    )
    msg.html = f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:20px auto;border:1px solid #e3e3e3;border-radius:8px;overflow:hidden;color:#333;">
  <div style="background:#005436;color:#fff;text-align:center;padding:18px;">
    <h2 style="margin:0;font-size:18px;">Directorate General of Immigration &amp; Passports</h2>
    <p style="margin:4px 0 0;font-size:13px;opacity:.9;">Government of Pakistan</p>
  </div>
  <div style="padding:26px;">
    <p>Dear <strong>{escape(name)}</strong>,</p>
    <p>{intro}</p>
    <p style="text-align:center;margin:26px 0;">
      <span style="display:inline-block;font-size:30px;letter-spacing:8px;font-weight:bold;color:#005436;
                   background:#f1f8f4;border:1px dashed #005436;border-radius:6px;padding:12px 22px;">{code}</span>
    </p>
    <p style="font-size:14px;">This code expires in <strong>{minutes_valid} minutes</strong>.
       Never share it with anyone — DGIP staff will never ask for it.</p>
    <p style="font-size:13px;color:#777;">{ignore}</p>
  </div>
  <div style="background:#333;color:#fff;text-align:center;padding:12px;font-size:11px;">
    This is an automated email, please do not reply.
  </div>
</div>
"""
    mail.send(msg)
