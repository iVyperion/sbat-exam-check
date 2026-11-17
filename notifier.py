"""
Remote notifications via Telegram and email (SMTP over SSL).

Configuration is read from a `.env` file (see `.env.example`), looked up in
the current working directory and next to the script / frozen executable.
Each channel is only used when all of its variables are set.
"""

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv not installed: rely on real env vars only
    load_dotenv = None


def _load_env():
    if load_dotenv is None:
        return
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent
    for path in (Path.cwd() / ".env", app_dir / ".env"):
        if path.is_file():
            load_dotenv(path, override=False)


_load_env()


def _default_log(msg):
    print(msg)


def telegram_configured():
    return bool(os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def email_configured():
    return all(
        os.getenv(k)
        for k in ("EMAIL_SENDER", "EMAIL_PASSWORD", "EMAIL_RECEIVER", "SMTP_SERVER")
    )


def send_telegram(message, log=_default_log):
    """Send a plain-text Telegram message. Returns True on success."""
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=15,
        )
        if response.status_code != 200:
            log(f"Telegram error: {response.status_code} {response.text[:200]}")
            return False
        log("Telegram message sent")
        return True
    except Exception as e:
        log(f"Telegram error: {e}")
        return False


def send_email(subject, message, log=_default_log):
    """Send a plain-text email over SMTP_SSL. Returns True on success."""
    try:
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        receiver = os.getenv("EMAIL_RECEIVER")
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", 465))

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain", "utf-8"))

        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:
            server.login(sender, password)
            server.send_message(msg)

        log("Email sent")
        return True
    except Exception as e:
        log(f"Email error: {e}")
        return False


def notify(subject, message, log=_default_log):
    """
    Send `message` via every configured channel (Telegram and/or email).
    Returns True if at least one channel delivered it.
    """
    sent = False
    if telegram_configured():
        sent = send_telegram(f"{subject}\n\n{message}", log) or sent
    if email_configured():
        sent = send_email(subject, message, log) or sent
    if not telegram_configured() and not email_configured():
        log("No Telegram/email configured in .env — skipping remote notification")
    return sent
