import pytest
from pydantic import ValidationError
from backend.app.schemas.commerce import AddressCreate
from backend.app.schemas.auth import RegisterRequest
from backend.app.schemas.common import UserBase
from backend.app.schemas.payments import CheckoutRequest

def test_address_phone_validation():
    # Valid
    AddressCreate(
        label="Home",
        full_name="John Doe",
        phone="+923001234567",
        line1="123 Main St",
        city="Anytown",
        postal_code="12345"
    )
    
    # Invalid (letters)
    with pytest.raises(ValidationError):
        AddressCreate(
            label="Home",
            full_name="John Doe",
            phone="123-abc-4567",
            line1="123 Main St",
            city="Anytown",
            postal_code="12345"
        )
        
    # Invalid (too short)
    with pytest.raises(ValidationError):
        AddressCreate(
            label="Home",
            full_name="John Doe",
            phone="123",
            line1="123 Main St",
            city="Anytown",
            postal_code="12345"
        )

def test_user_phone_validation():
    # Valid
    UserBase(full_name="John", email="john@example.com", phone="+923001234567")
    
    # Invalid
    with pytest.raises(ValidationError):
        UserBase(full_name="John", email="john@example.com", phone="123")


def test_registration_and_checkout_reject_invalid_phone_numbers():
    with pytest.raises(ValidationError):
        RegisterRequest(full_name="John Doe", email="john@example.com", password="Password123", phone="0300-abc-123")

    with pytest.raises(ValidationError):
        CheckoutRequest(payment_method="cash_on_delivery", shipping_name="John Doe", shipping_phone="1234567")
