from pydantic import BaseModel, EmailStr


class ContactMessageCreate(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str


class NewsletterSubscribe(BaseModel):
    email: EmailStr

