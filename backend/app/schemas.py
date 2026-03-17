from datetime import datetime
from pydantic import BaseModel, Field


class Button(BaseModel):
    label: str
    value: str


class MessageOut(BaseModel):
    role: str
    text: str
    buttons: list[Button] | None = None
    created_at: datetime | None = None


class StartChatResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]


class ChatIn(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=3000)
    display_text: str | None = Field(default=None, max_length=3000)


class ChatResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]


class ContactRequestIn(BaseModel):
    session_id: str | None = None
    full_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=5, max_length=50)
    message: str | None = Field(default=None, max_length=2000)


class ContactRequestOut(BaseModel):
    status: str
    detail: str


class HealthOut(BaseModel):
    status: str
    project: str
