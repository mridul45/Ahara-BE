import logging
import resend
from django.conf import settings

logger = logging.getLogger(__name__)


class OtpEmailError(Exception):
    """Raised when OTP email delivery fails so callers can surface the error."""
    pass


def send_otp_email(to_email: str, otp: str) -> None:
    """
    Send an OTP to the user's email via Resend.

    Raises:
        OtpEmailError: if the API key is missing or Resend rejects the send.
                       Callers should catch this and return an appropriate HTTP error.
    """
    if not settings.RESEND_API_KEY:
        logger.error("Resend API key is not set.")
        raise OtpEmailError("Email service is not configured.")

    resend.api_key = settings.RESEND_API_KEY

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin: 0; padding: 0; background-color: #f7f9fc; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #f7f9fc; padding: 40px 0;">
            <tr>
                <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);">
                        <tr>
                            <td align="center" style="padding: 40px 40px 20px 40px;">
                                <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #1e293b; letter-spacing: -0.5px;">Welcome to Ahara</h1>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" style="padding: 0 40px;">
                                <p style="margin: 0; font-size: 16px; line-height: 24px; color: #475569;">
                                    Please enter the verification code below to access your account.
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" style="padding: 40px;">
                                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 25px 40px; display: inline-block;">
                                    <h2 style="margin: 0; font-size: 42px; font-weight: 800; letter-spacing: 12px; color: #0f172a;">{otp}</h2>
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" style="padding: 0 40px 40px 40px;">
                                <p style="margin: 0; font-size: 14px; color: #94a3b8;">
                                    This code expires in <strong>10 minutes</strong>.
                                </p>
                                <p style="margin: 20px 0 0 0; font-size: 12px; color: #cbd5e1;">
                                    &copy; 2026 Ahara App. All rights reserved.
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
            "to": [to_email],
            "subject": "Ahara — Your Verification Code",
            "html": html_content,
        })
        email_id = r.get("id") if isinstance(r, dict) else getattr(r, "id", "unknown")
        logger.info("otp_email.sent to=%s id=%s", to_email, email_id)
    except Exception as e:
        logger.exception("otp_email.failed to=%s error=%s", to_email, str(e))
        raise OtpEmailError(str(e)) from e
