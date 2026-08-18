from backend.app.core.config import Settings
from backend.app.services.email_service import EmailService


def test_email_service_skips_delivery_when_disabled(monkeypatch) -> None:
    settings = Settings(email_enabled=False, smtp_host="smtp.example.com", email_from_address="shop@example.com")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("SMTP should not be opened when email is disabled")

    monkeypatch.setattr("backend.app.services.email_service.smtplib.SMTP", fail_if_called)
    assert EmailService(settings).send("customer@example.com", "Subject", "Body") is False


def test_email_service_sends_multipart_message(monkeypatch) -> None:
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.com", 587, 5.0)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def starttls(self):
            return None

        def login(self, username, password):
            assert (username, password) == ("mailer", "app-password")

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr("backend.app.services.email_service.smtplib.SMTP", FakeSMTP)
    settings = Settings(
        email_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="mailer",
        smtp_password="app-password",
        smtp_use_tls=True,
        smtp_timeout_seconds=5,
        email_from_address="shop@example.com",
        email_from_name="DukaanHub",
    )

    assert EmailService(settings).send("customer@example.com", "Welcome", "Plain body", "<p>HTML body</p>") is True
    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "customer@example.com"
    assert sent_messages[0]["Subject"] == "Welcome"
    assert sent_messages[0].is_multipart()
