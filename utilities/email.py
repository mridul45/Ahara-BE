import logging
import resend
from django.conf import settings

logger = logging.getLogger(__name__)

def send_otp_email(to_email: str, otp: str) -> bool:
    """
    Sends an OTP to the user's email using Resend.
    Returns True if successful, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        logger.error("Resend API key is not set.")
        return False

    resend.api_key = settings.RESEND_API_KEY
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #f7f9fc; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #f7f9fc; padding: 40px 0;">
            <tr>
                <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);">
                        <!-- Header -->
                        <tr>
                            <td align="center" style="padding: 40px 40px 20px 40px;">
                                <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #1e293b; letter-spacing: -0.5px;">Welcome to Ahara</h1>
                            </td>
                        </tr>
                        <!-- Body -->
                        <tr>
                            <td align="center" style="padding: 0 40px;">
                                <p style="margin: 0; font-size: 16px; line-height: 24px; color: #475569;">
                                    We're thrilled to have you here. Please securely enter the verification code below to seamlessly access your account.
                                </p>
                            </td>
                        </tr>
                        <!-- OTP Box -->
                        <tr>
                            <td align="center" style="padding: 40px;">
                                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 25px 40px; display: inline-block;">
                                    <h2 style="margin: 0; font-size: 42px; font-weight: 800; letter-spacing: 12px; color: #0f172a;">{otp}</h2>
                                </div>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td align="center" style="padding: 0 40px 40px 40px;">
                                <p style="margin: 0; font-size: 14px; color: #94a3b8;">
                                    This unique code will safely expire in exactly <strong>10 minutes</strong>.
                                </p>
                                <p style="margin: 20px 0 0 0; font-size: 12px; color: #cbd5e1;">
                                    &copy; {{{{ year|default:"2026" }}}} Ahara App. All rights reserved.
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

    try:
        r = resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": to_email,
            "subject": "Ahara - Your Verification Code",
            "html": html_content
        })
        
        logger.info(f"OTP email successfully sent to {to_email}. Resend ID: {r.get('id', 'Unknown')}")
        return True
    except Exception as e:
        logger.exception("Exception occurred while sending OTP via Resend")
        return False
