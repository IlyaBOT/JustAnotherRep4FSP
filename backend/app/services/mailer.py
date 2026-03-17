from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..config import settings


class Mailer:
    def is_configured(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_username and settings.smtp_password and settings.mail_to)

    def send_contact_request(self, full_name: str, phone: str, message: str | None) -> bool:
        if not self.is_configured():
            return False

        email = EmailMessage()
        email["Subject"] = "Новая заявка из чат-бота «СВОй»"
        email["From"] = settings.smtp_username
        email["To"] = settings.mail_to
        email.set_content(
            f"Новая заявка из веб-чата\n\n"
            f"ФИО: {full_name}\n"
            f"Телефон: {phone}\n"
            f"Комментарий: {message or '-'}\n"
        )

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(email)
        return True
