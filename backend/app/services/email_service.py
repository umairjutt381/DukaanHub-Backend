from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Iterable

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger("dukaanhub.email")


class EmailService:
    """Send transactional email without allowing delivery errors to break requests."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.email_enabled
            and self.settings.smtp_host
            and self.settings.email_from_address
        )

    def send(self, recipient: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
        if not self.is_configured:
            logger.info("Email delivery is disabled or SMTP is not configured; skipped %s", subject)
            return False

        message = EmailMessage()
        message["From"] = formataddr((self.settings.email_from_name, self.settings.email_from_address))
        message["To"] = recipient.strip()
        message["Subject"] = subject
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        try:
            smtp_class = smtplib.SMTP_SSL if self.settings.smtp_use_ssl else smtplib.SMTP
            with smtp_class(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as smtp:
                if self.settings.smtp_use_tls and not self.settings.smtp_use_ssl:
                    smtp.starttls()
                if self.settings.smtp_username:
                    # Gmail displays App Passwords in groups separated by spaces.
                    smtp.login(self.settings.smtp_username, "".join(self.settings.smtp_password.split()))
                smtp.send_message(message)
            return True
        except (OSError, smtplib.SMTPException, ValueError):
            logger.exception("Unable to deliver transactional email: %s", subject)
            return False


def send_registration_emails(recipient: str, full_name: str) -> None:
    settings = get_settings()
    mailer = EmailService(settings)
    safe_name = html.escape(full_name or "Customer")
    mailer.send(
        recipient,
        "Welcome to DukaanHub",
        f"Hi {full_name or 'Customer'},\n\nYour DukaanHub account has been created successfully.",
        f"<h2>Welcome to DukaanHub</h2><p>Hi {safe_name},</p><p>Your account has been created successfully.</p>",
    )
    if settings.email_admin_recipient:
        mailer.send(
            settings.email_admin_recipient,
            "New DukaanHub account registered",
            f"A new account was registered for {full_name} ({recipient}).",
        )


def send_password_reset_email(recipient: str, full_name: str, reset_url: str) -> None:
    safe_name = html.escape(full_name or "Customer")
    safe_url = html.escape(reset_url, quote=True)
    EmailService().send(
        recipient,
        "Reset your DukaanHub password",
        f"Hi {full_name or 'Customer'},\n\nUse this link to reset your DukaanHub password:\n{reset_url}\n\nThis link expires in 30 minutes and can only be used once.",
        f"<h2>Reset your password</h2><p>Hi {safe_name},</p><p><a href=\"{safe_url}\">Choose a new password</a></p><p>This link expires in 30 minutes and can only be used once.</p>",
    )


def send_order_emails(
    recipient: str,
    full_name: str,
    order_number: str,
    total_amount: float,
    currency: str,
    items: Iterable[tuple[str, int, float]],
) -> None:
    settings = get_settings()
    mailer = EmailService(settings)
    item_rows = list(items)
    text_items = "\n".join(f"- {name} x{quantity}: {currency} {line_total:,.2f}" for name, quantity, line_total in item_rows)
    html_items = "".join(
        f"<li>{html.escape(name)} × {quantity}: {html.escape(currency)} {line_total:,.2f}</li>"
        for name, quantity, line_total in item_rows
    )
    mailer.send(
        recipient,
        f"Order {order_number} received",
        (
            f"Hi {full_name or 'Customer'},\n\nYour order {order_number} has been received.\n"
            f"{text_items}\n\nTotal: {currency} {total_amount:,.2f}"
        ),
        (
            f"<h2>Order received</h2><p>Hi {html.escape(full_name or 'Customer')},</p>"
            f"<p>Your order <strong>{html.escape(order_number)}</strong> has been received.</p>"
            f"<ul>{html_items}</ul><p><strong>Total: {html.escape(currency)} {total_amount:,.2f}</strong></p>"
        ),
    )
    if settings.email_admin_recipient:
        mailer.send(
            settings.email_admin_recipient,
            f"New order {order_number}",
            f"{full_name} ({recipient}) placed order {order_number} for {currency} {total_amount:,.2f}.",
        )


def send_order_status_email(recipient: str, full_name: str, order_number: str, order_status: str) -> None:
    status_label = order_status.replace("_", " ").title()
    EmailService().send(
        recipient,
        f"Order {order_number}: {status_label}",
        f"Hi {full_name or 'Customer'},\n\nYour order {order_number} is now {status_label}.",
        (
            f"<h2>Order update</h2><p>Hi {html.escape(full_name or 'Customer')},</p>"
            f"<p>Your order <strong>{html.escape(order_number)}</strong> is now "
            f"<strong>{html.escape(status_label)}</strong>.</p>"
        ),
    )
