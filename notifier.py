"""
Remote notifications via Telegram and email (SMTP over SSL).

Configuration is read from a `.env` file (see `.env.example`), looked up in
the current working directory and next to the script / frozen executable.
Each channel is only used when all of its variables are set.
"""

import hashlib
import json
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


def _app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _load_env():
    if load_dotenv is None:
        return
    for path in (Path.cwd() / ".env", _app_dir() / ".env"):
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


class QrRelay:
    """
    Relays the itsme login QR code to you while a login is pending, so you can
    scan it with your phone when you can't see the computer's screen.

    - Telegram: one photo message that is edited in place every time the QR
      rotates (itsme replaces it every ~10s), and deleted after login.
    - Email: a single heads-up that a login is needed (a QR in an email would
      already be expired by the time you open it).
    - File: the current QR is also written to `login_qr.png` next to the app.
    """

    CAPTION = (
        "SBAT: itsme login needed\n"
        "Scan this QR code with the itsme app (open this chat on another screen). "
        "It refreshes automatically every few seconds."
    )

    def __init__(self, log=_default_log):
        self._log = log
        self._last_hash = None
        self._message_id = None
        self._emailed = False
        self.file_path = _app_dir() / "login_qr.png"

    def update(self, png_bytes):
        """Send/replace the QR image if it changed since the last update."""
        digest = hashlib.sha1(png_bytes).hexdigest()
        if digest == self._last_hash:
            return
        self._last_hash = digest

        try:
            self.file_path.write_bytes(png_bytes)
        except Exception as e:
            self._log(f"Could not write {self.file_path}: {e}")

        if not self._emailed:
            self._emailed = True
            if email_configured():
                send_email(
                    "SBAT: itsme login needed",
                    "The SBAT checker needs an itsme login.\n"
                    "The live QR code is in your Telegram chat with the bot "
                    f"(and in {self.file_path} on the computer).",
                    self._log,
                )

        if not telegram_configured():
            return
        token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        base = f"https://api.telegram.org/bot{token}"
        try:
            if self._message_id is None:
                r = requests.post(
                    f"{base}/sendPhoto",
                    data={"chat_id": chat_id, "caption": self.CAPTION},
                    files={"photo": ("qr.png", png_bytes, "image/png")},
                    timeout=15,
                )
                if r.ok:
                    self._message_id = r.json()["result"]["message_id"]
                    self._log("Login QR code sent to Telegram.")
                else:
                    self._log(f"Telegram QR error: {r.status_code} {r.text[:200]}")
            else:
                media = {"type": "photo", "media": "attach://qr", "caption": self.CAPTION}
                r = requests.post(
                    f"{base}/editMessageMedia",
                    data={
                        "chat_id": chat_id,
                        "message_id": self._message_id,
                        "media": json.dumps(media),
                    },
                    files={"qr": ("qr.png", png_bytes, "image/png")},
                    timeout=15,
                )
                if not r.ok:
                    self._log(f"Telegram QR update error: {r.status_code} {r.text[:200]}")
        except Exception as e:
            self._log(f"Telegram QR error: {e}")

    def finish(self, success):
        """Remove the (now useless) QR message and file, and report the outcome."""
        if self._last_hash is None:
            return  # No QR was ever shown
        try:
            self.file_path.unlink(missing_ok=True)
        except Exception:
            pass
        if telegram_configured():
            token = os.getenv("TELEGRAM_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            if self._message_id is not None:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/deleteMessage",
                        json={"chat_id": chat_id, "message_id": self._message_id},
                        timeout=15,
                    )
                except Exception:
                    pass
            send_telegram(
                "SBAT: itsme login successful, checking resumes."
                if success
                else "SBAT: itsme login timed out. Restart the login to get a new QR code.",
                self._log,
            )
        self._last_hash = None
        self._message_id = None
        self._emailed = False
