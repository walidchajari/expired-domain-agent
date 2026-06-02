import logging
import smtplib
import uuid
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from pathlib import Path
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)


def build_message(
    subject: str,
    body: str,
    html_body: str = "",
    attachment_path: Optional[Path] = None,
    to: Optional[str] = None,
    cc: Optional[str] = None,
) -> MIMEMultipart:
    to = to or settings.email_to
    cc = cc or settings.email_cc

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr(("Domain Agent", settings.smtp_username))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@{settings.smtp_username.split('@')[1]}>"
    msg["Date"] = formatdate(localtime=True)
    msg["X-Mailer"] = "DomainAgent/1.0"
    msg["X-Priority"] = "3"

    if cc:
        msg["Cc"] = cc

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "plain", "utf-8"))
    if html_body:
        alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if attachment_path and attachment_path.exists():
        with open(attachment_path, "rb") as f:
            part = MIMEApplication(f.read(), Name=attachment_path.name)
            part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
            msg.attach(part)

    return msg


def get_recipients(to: str, cc: str) -> list[str]:
    recipients = [to]
    if cc:
        recipients.extend([addr.strip() for addr in cc.split(",") if addr.strip()])
    return recipients


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=30),
)
def send_email(
    subject: str,
    body: str,
    html_body: str = "",
    attachment_path: Optional[Path] = None,
    to: Optional[str] = None,
    cc: Optional[str] = None,
) -> bool:
    to = to or settings.email_to
    cc = cc or settings.email_cc

    msg = build_message(subject, body, html_body, attachment_path, to, cc)
    recipients = get_recipients(to, cc)

    try:
        logger.info("Connecting to SMTP %s:%d", settings.smtp_server, settings.smtp_port)
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_username, recipients, msg.as_string())
        logger.info("Email sent successfully to %s", to)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed. "
            "Use an App Password (not your regular Gmail password). "
            "See: https://support.google.com/accounts/answer/185833"
        )
        raise
    except Exception:
        logger.exception("Failed to send email")
        raise


def send_daily_report(
    attachment_path: Path,
    total_analyzed: int,
    top_score: float,
    best_domain: str,
    to: Optional[str] = None,
    cc: Optional[str] = None,
) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    name = to.split("@")[0].capitalize() if to else "there"
    subject = f"Daily Report - {today}"

    body = (
        f"Hi {name},\n\n"
        f"Here is today's domain report.\n\n"
        f"Total analyzed: {total_analyzed}\n"
        f"Top score: {top_score:.1f}\n"
        f"Best: {best_domain}\n\n"
        f"The Excel file is attached.\n\n"
        f"Best,\nDomain Agent"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Helvetica,Arial,sans-serif;color:#444;max-width:560px;margin:0 auto;padding:24px;">
<div style="text-align:center;padding:8px 0;">
  <span style="font-size:20px;font-weight:bold;color:#1a1a1a;">Daily Report</span>
</div>
<div style="border:1px solid #e0e0e0;border-radius:8px;padding:20px;margin:12px 0;">
  <p style="margin:0 0 12px;">Hi {name},</p>
  <p style="margin:0 0 16px;">Your daily domain report is ready.</p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <tr><td style="padding:8px 4px;color:#888;">Analyzed</td><td style="padding:8px 4px;font-weight:600;">{total_analyzed}</td></tr>
    <tr><td style="padding:8px 4px;color:#888;border-top:1px solid #eee;">Top Score</td><td style="padding:8px 4px;font-weight:600;border-top:1px solid #eee;">{top_score:.1f}</td></tr>
    <tr><td style="padding:8px 4px;color:#888;border-top:1px solid #eee;">Best</td><td style="padding:8px 4px;font-weight:600;border-top:1px solid #eee;">{best_domain}</td></tr>
  </table>
  <p style="margin:16px 0 0;">The Excel report is attached.</p>
</div>
<div style="text-align:center;font-size:12px;color:#aaa;padding:12px 0;">
  <p style="margin:0;">Domain Agent &mdash; {today}</p>
</div>
</body>
</html>"""

    return send_email(
        subject=subject,
        body=body,
        html_body=html_body,
        attachment_path=attachment_path,
        to=to,
        cc=cc,
    )
