"""
Bezalel.AI — SMTP email service.

Sends OTP verification emails using aiosmtplib for async delivery.
Provides a clean HTML template for the one-time code.
"""

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings


def _build_otp_html(otp_code: str) -> str:
    """
    Return a clean HTML email body containing the OTP code.
    Inline styles are used for maximum email-client compatibility.
    """
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:8px;padding:40px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <tr>
            <td style="text-align:center;padding-bottom:24px;">
              <h1 style="margin:0;font-size:24px;color:#1a1a2e;">Bezalel.AI</h1>
            </td>
          </tr>
          <tr>
            <td style="text-align:center;padding-bottom:16px;">
              <p style="margin:0;font-size:16px;color:#4a4a68;">
                Your one-time verification code is:
              </p>
            </td>
          </tr>
          <tr>
            <td style="text-align:center;padding-bottom:24px;">
              <div style="display:inline-block;padding:16px 32px;background:#1a1a2e;
                          border-radius:8px;letter-spacing:8px;font-size:32px;
                          font-weight:bold;color:#ffffff;">
                {otp_code}
              </div>
            </td>
          </tr>
          <tr>
            <td style="text-align:center;padding-bottom:8px;">
              <p style="margin:0;font-size:14px;color:#8888a0;">
                This code expires in <strong>10 minutes</strong>.
              </p>
            </td>
          </tr>
          <tr>
            <td style="text-align:center;">
              <p style="margin:0;font-size:12px;color:#b0b0c0;">
                If you did not request this code, please ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


async def send_otp_email(recipient_email: str, otp_code: str) -> None:
    """
    Send a verification OTP email to the given address.

    Uses aiosmtplib for non-blocking SMTP delivery.  Connection uses
    STARTTLS when ``SMTP_USE_TLS`` is enabled in settings.

    Args:
        recipient_email: The user's email address.
        otp_code:        The 6-digit one-time code.

    Raises:
        aiosmtplib.SMTPException: If the mail server rejects the message.
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = "Bezalel.AI — Your Verification Code"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient_email

    # Plain-text fallback.
    plain = f"Your Bezalel.AI verification code is: {otp_code}\n\nThis code expires in 10 minutes."
    message.attach(MIMEText(plain, "plain"))

    # HTML body.
    html = _build_otp_html(otp_code)
    message.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        start_tls=settings.SMTP_USE_TLS,
    )
