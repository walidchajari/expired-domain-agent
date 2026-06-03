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
    attachment_paths: Optional[list[Path]] = None,
    total_analyzed: int = 0,
    top_score: float = 0,
    best_domain: str = "",
    top_domains: Optional[list[dict]] = None,
    to: Optional[str] = None,
    cc: Optional[str] = None,
) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    to = to or settings.email_to
    cc = cc or settings.email_cc
    name = to.split("@")[0].capitalize() if to else "there"
    subject = f"Daily Expired Domains Report - {today}"

    # Build top 20 text table for plain text
    table_txt = ""
    if top_domains:
        table_txt = "\nTop 20:\n" + "-" * 60 + "\n"
        for i, d in enumerate(top_domains[:20], 1):
            cat = d.get("category", "")
            score = d.get("final_score", 0)
            prob = d.get("probability_of_sale", 0)
            table_txt += f"  {i:2d}. {d['domain']:25s} {cat:20s} {score:5.1f}  ({prob:.0f}%)\n"

    attachment_names = [p.name for p in (attachment_paths or [])]
    attachments_line = f"Attachments: {', '.join(attachment_names)}" if attachment_names else ""

    body = (
        f"Hi {name},\n\n"
        f"Today's expired domain reports are ready.\n\n"
        f"Total Domains Scraped: {total_analyzed}\n"
        f"Domains Passing Filter: {len(top_domains) if top_domains else 0}\n"
        f"Best Domain: {best_domain}\n"
        f"Highest Score: {top_score:.1f}\n"
        f"{table_txt}\n"
        f"{attachments_line}\n\n"
        f"Best,\nDomain Agent"
    )

    # Build HTML body
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;color:#333;margin:0;padding:0; }}
  .container {{ max-width:680px;margin:20px auto;background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);overflow:hidden; }}
  .header {{ background:linear-gradient(135deg,#1F4E79,#2A6BA0);color:#fff;padding:24px 32px; }}
  .header h1 {{ margin:0;font-size:22px;font-weight:600; }}
  .header p {{ margin:4px 0 0;font-size:14px;opacity:.85; }}
  .stats {{ display:flex;gap:20px;padding:20px 32px;background:#fafbfc;border-bottom:1px solid #e8ecf0;flex-wrap:wrap; }}
  .stat-item {{ flex:1;min-width:100px; }}
  .stat-value {{ font-size:26px;font-weight:700;color:#1F4E79; }}
  .stat-label {{ font-size:12px;color:#888;text-transform:uppercase;letter-spacing:.5px; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>Daily Expired Domains Report</h1>
  <p>{today} — {total_analyzed} domains analyzed</p>
</div>
<div class="stats">
  <div class="stat-item">
    <div class="stat-value">{total_analyzed}</div>
    <div class="stat-label">Scraped</div>
  </div>
  <div class="stat-item">
    <div class="stat-value">{len(top_domains) if top_domains else 0}</div>
    <div class="stat-label">Investor Picks</div>
  </div>
  <div class="stat-item">
    <div class="stat-value">{top_score:.1f}</div>
    <div class="stat-label">Top Score</div>
  </div>
  <div class="stat-item">
    <div class="stat-value" style="font-size:18px;">{best_domain}</div>
    <div class="stat-label">Best Domain</div>
  </div>
</div>"""

    # Build top 10 HTML table
    html_rows = ""
    if top_domains:
        for i, d in enumerate(top_domains[:10], 1):
            cat = d.get("category", "")
            score = d.get("final_score", 0)
            prob = d.get("probability_of_sale", 0)
            ai_rec = d.get("ai_recommendation", "")
            bg = "#f9f9f9" if i % 2 == 0 else "#fff"
            html_rows += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:6px 4px;text-align:center;color:#888;">{i}</td>'
                f'<td style="padding:6px 4px;font-weight:600;">{d["domain"]}</td>'
                f'<td style="padding:6px 4px;color:#666;">{cat}</td>'
                f'<td style="padding:6px 4px;text-align:center;">{score:.1f}</td>'
                f'<td style="padding:6px 4px;text-align:center;color:#666;">{prob:.0f}%</td>'
                f'<td style="padding:6px 4px;text-align:center;font-weight:600;">{ai_rec}</td>'
                f"</tr>\n"
            )

    html_body += f"""<div style="border:1px solid #e0e0e0;border-radius:8px;padding:4px 20px 12px;margin:12px 0;">
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="border-bottom:2px solid #1F4E79;">
        <th style="padding:8px 4px;text-align:center;color:#1F4E79;">#</th>
        <th style="padding:8px 4px;text-align:left;color:#1F4E79;">Domain</th>
        <th style="padding:8px 4px;text-align:left;color:#1F4E79;">Category</th>
        <th style="padding:8px 4px;text-align:center;color:#1F4E79;">Score</th>
        <th style="padding:8px 4px;text-align:center;color:#1F4E79;">Sale %</th>
        <th style="padding:8px 4px;text-align:center;color:#1F4E79;">AI</th>
      </tr>
    </thead>
    <tbody>
{html_rows}
    </tbody>
  </table>
</div>"""

    html_body += """<div style="text-align:center;font-size:12px;color:#aaa;padding:12px 0;">
  <p style="margin:0;">Domain Agent</p>
</div>
</body>
</html>"""

    # Attach multiple files
    if attachment_paths:
        msg = build_message(subject, body, html_body, to=to, cc=cc)
        for ap in attachment_paths:
            if ap.exists():
                with open(ap, "rb") as f:
                    part = MIMEApplication(f.read(), Name=ap.name)
                    part["Content-Disposition"] = f'attachment; filename="{ap.name}"'
                    msg.attach(part)
    else:
        msg = build_message(subject, body, html_body, to=to, cc=cc)

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
