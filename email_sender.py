import logging
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)


def build_message(
    subject: str,
    body: str,
    attachment_path: Optional[Path] = None,
    to: Optional[str] = None,
    cc: Optional[str] = None,
) -> MIMEMultipart:
    to = to or settings.email_to
    cc = cc or settings.email_cc

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_username
    msg["To"] = to
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = cc

    msg.attach(MIMEText(body, "plain"))

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
    attachment_path: Optional[Path] = None,
    to: Optional[str] = None,
    cc: Optional[str] = None,
) -> bool:
    to = to or settings.email_to
    cc = cc or settings.email_cc

    msg = build_message(subject, body, attachment_path, to, cc)
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
    subject = f"Top 20 Expired Domains - {today}"
    body = (
        f"Top 20 Expired Domains Report\n"
        f"{'=' * 40}\n\n"
        f"Date: {today}\n"
        f"Total domains analyzed: {total_analyzed}\n"
        f"Top Score: {top_score:.1f}\n"
        f"Best Domain: {best_domain}\n\n"
        f"The Excel report is attached.\n\n"
        f"---\nExpired Domain Agent"
    )
    return send_email(
        subject=subject,
        body=body,
        attachment_path=attachment_path,
        to=to,
        cc=cc,
    )
