from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .chatbot import BotEngine
from .config import settings
from .database import Base, engine, get_db
from .models import ChatMessage, ChatSession, ContactRequest
from .schemas import ChatIn, ChatResponse, ContactRequestIn, ContactRequestOut, HealthOut, MessageOut, StartChatResponse
from .services.mailer import Mailer

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.project_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/checklists", StaticFiles(directory=static_dir / "checklists"), name="checklists")

bot = BotEngine()
mailer = Mailer()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/widget")


@app.get("/widget", include_in_schema=False)
def widget():
    return FileResponse(static_dir / "index.html")


@app.get("/api/health", response_model=HealthOut)
def health():
    return HealthOut(status="ok", project=settings.project_name)


@app.post("/api/chat/start", response_model=StartChatResponse)
def start_chat(db: Session = Depends(get_db)):
    session = ChatSession(state={})
    db.add(session)
    db.flush()

    messages_out: list[MessageOut] = []
    for item in bot.welcome_messages():
        message = ChatMessage(session_id=session.id, role="assistant", text=item.text, buttons=item.buttons)
        db.add(message)
        messages_out.append(MessageOut(role="assistant", text=item.text, buttons=item.buttons))

    db.commit()
    return StartChatResponse(session_id=session.id, messages=messages_out)


@app.get("/api/chat/history/{session_id}", response_model=ChatResponse)
def chat_history(session_id: str, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.asc())).all()
    return ChatResponse(
        session_id=session_id,
        messages=[
            MessageOut(role=row.role, text=row.text, buttons=row.buttons, created_at=row.created_at) for row in rows
        ],
    )


@app.post("/api/chat/message", response_model=ChatResponse)
def chat_message(payload: ChatIn, db: Session = Depends(get_db)):
    session = db.get(ChatSession, payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_message_text = payload.display_text.strip() if payload.display_text else payload.text
    db.add(ChatMessage(session_id=session.id, role="user", text=user_message_text))

    responses, new_state = bot.handle(payload.text, session.state)
    session.state = new_state

    if new_state.pop("create_contact_request", False):
        request = ContactRequest(
            session_id=session.id,
            full_name=new_state.get("lead_full_name", "Не указано"),
            phone=new_state.get("lead_phone", "Не указано"),
            message=new_state.get("lead_message"),
        )
        db.add(request)
        try:
            mailer.send_contact_request(request.full_name, request.phone, request.message)
        except Exception:
            pass

    for item in responses:
        db.add(ChatMessage(session_id=session.id, role="assistant", text=item.text, buttons=item.buttons))

    db.commit()

    latest_rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.id.asc())).all()
    return ChatResponse(
        session_id=session.id,
        messages=[
            MessageOut(role=row.role, text=row.text, buttons=row.buttons, created_at=row.created_at)
            for row in latest_rows
        ],
    )


@app.post("/api/contact-request", response_model=ContactRequestOut)
def create_contact_request(payload: ContactRequestIn, db: Session = Depends(get_db)):
    request = ContactRequest(
        session_id=payload.session_id,
        full_name=payload.full_name,
        phone=payload.phone,
        message=payload.message,
    )
    db.add(request)
    db.commit()

    try:
        mailer.send_contact_request(payload.full_name, payload.phone, payload.message)
    except Exception:
        pass

    return ContactRequestOut(status="ok", detail="Заявка сохранена")
