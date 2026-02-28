import email
import imaplib
import os
import re
import time
import html
from html.parser import HTMLParser

import requests


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_data(self, data):
        if data:
            self._chunks.append(data)

    def get_text(self):
        return "".join(self._chunks)


def html_to_text(html):
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def decode_part(part):
    charset = part.get_content_charset() or "utf-8"
    payload = part.get_payload(decode=True) or b""
    return payload.decode(charset, errors="replace")


def extract_body(message):
    if message.is_multipart():
        text_part = None
        html_part = None
        for part in message.walk():
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition.lower():
                continue
            if content_type == "text/plain" and text_part is None:
                text_part = part
            elif content_type == "text/html" and html_part is None:
                html_part = part
        if text_part is not None:
            return decode_part(text_part)
        if html_part is not None:
            return html_to_text(decode_part(html_part))
        return ""
    content_type = message.get_content_type()
    if content_type == "text/html":
        return html_to_text(decode_part(message))
    return decode_part(message)


def find_otp(text):
    match = re.search(r"\b(\d{6})\b", text)
    return match.group(1) if match else None


def send_telegram(bot_token, chat_ids, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for chat_id in chat_ids:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if not response.ok:
            raise RuntimeError(
                f"Telegram error {response.status_code}: {response.text}"
            )


def process_inbox(settings):
    imap = imaplib.IMAP4_SSL(settings["imap_host"])
    imap.login(settings["gmail_user"], settings["gmail_password"])
    imap.select(settings["imap_folder"])

    if settings["bank_from"]:
        criteria = f'(UNSEEN FROM "{settings["bank_from"]}")'
    else:
        criteria = "(UNSEEN)"

    status, data = imap.search(None, criteria)
    if status != "OK":
        imap.logout()
        raise RuntimeError("IMAP search failed")

    message_ids = data[0].split()
    for msg_id in message_ids:
        status, msg_data = imap.fetch(msg_id, "(RFC822)")
        if status != "OK":
            continue
        raw_bytes = msg_data[0][1]
        message = email.message_from_bytes(raw_bytes)

        body = extract_body(message)
        otp = find_otp(body)
        if not otp:
            continue

        subject = message.get("Subject", "")
        safe_subject = html.escape(subject)
        text = f"<code>{otp}</code>\n\n{safe_subject}"

        send_telegram(settings["telegram_token"], settings["telegram_chat_ids"], text)
        imap.store(msg_id, "+FLAGS", "\\Seen")

    imap.logout()


def main():
    load_env_file(".env")

    settings = {
        "gmail_user": require_env("GMAIL_USER"),
        "gmail_password": require_env("GMAIL_APP_PASSWORD"),
        "imap_host": os.getenv("IMAP_HOST", "imap.gmail.com"),
        "imap_folder": os.getenv("IMAP_FOLDER", "INBOX"),
        "bank_from": os.getenv("BANK_FROM", ""),
        "poll_seconds": int(os.getenv("POLL_SECONDS", "15")),
        "telegram_token": require_env("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_ids": [
            chat_id.strip()
            for chat_id in require_env("TELEGRAM_CHAT_IDS").split(",")
            if chat_id.strip()
        ],
    }

    if not settings["telegram_chat_ids"]:
        raise ValueError("TELEGRAM_CHAT_IDS is empty")

    print("OTP forwarder started")
    while True:
        try:
            process_inbox(settings)
        except Exception as exc:
            print(f"Error: {exc}")
        time.sleep(settings["poll_seconds"])


if __name__ == "__main__":
    main()
