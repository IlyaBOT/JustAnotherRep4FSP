from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
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


def _build_message_out(row: ChatMessage) -> MessageOut:
    return MessageOut(role=row.role, text=row.text, buttons=row.buttons, meta=row.meta, created_at=row.created_at)


def _get_session_or_404(db: Session, session_id: str) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _persist_assistant_messages(db: Session, session_id: str, messages: list) -> None:
    for item in messages:
        db.add(ChatMessage(session_id=session_id, role="assistant", text=item.text, buttons=item.buttons, meta=item.meta))


def _chat_response(db: Session, session_id: str) -> ChatResponse:
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.asc())).all()
    return ChatResponse(session_id=session_id, messages=[_build_message_out(row) for row in rows])


def _handle_post_chat_side_effects(db: Session, session: ChatSession, new_state: dict) -> None:
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


def _build_uploaded_files_message_text(comment: str | None, uploaded_files: list[dict]) -> str:
    uploaded_list = "\n".join(f"• {item['name']}" for item in uploaded_files)
    if comment:
        return f"{comment}\n\nЗагружены файлы:\n{uploaded_list}"
    return f"Загружены файлы:\n{uploaded_list}"


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
        message = ChatMessage(session_id=session.id, role="assistant", text=item.text, buttons=item.buttons, meta=item.meta)
        db.add(message)
        messages_out.append(MessageOut(role="assistant", text=item.text, buttons=item.buttons, meta=item.meta))

    db.commit()
    return StartChatResponse(session_id=session.id, messages=messages_out)


@app.get("/api/chat/history/{session_id}", response_model=ChatResponse)
def chat_history(session_id: str, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
    return _chat_response(db, session_id)


@app.post("/api/chat/message", response_model=ChatResponse)
def chat_message(payload: ChatIn, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, payload.session_id)

    user_message_text = payload.display_text.strip() if payload.display_text else payload.text
    db.add(ChatMessage(session_id=session.id, role="user", text=user_message_text))

    responses, new_state = bot.handle(payload.text, session.state)
    session.state = new_state

    _handle_post_chat_side_effects(db, session, new_state)
    _persist_assistant_messages(db, session.id, responses)

    db.commit()
    return _chat_response(db, session.id)


@app.post("/api/chat/message-with-files", response_model=ChatResponse)
async def chat_message_with_files(
    session_id: str = Form(...),
    text: str = Form(default=""),
    db: Session = Depends(get_db),
    files: list[UploadFile] = File(default=[]),
):
    session = _get_session_or_404(db, session_id)

    uploaded_files: list[dict] = []
    for item in files:
        content = await item.read()
        uploaded_files.append(
            {
                "name": item.filename or "Файл без названия",
                "content_type": item.content_type or "application/octet-stream",
                "size": len(content),
            }
        )
        await item.close()

    if not uploaded_files:
        raise HTTPException(status_code=400, detail="Files are required")

    comment = text.strip() or None
    db.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            text=_build_uploaded_files_message_text(comment, uploaded_files),
            meta={"files": uploaded_files},
        )
    )

    responses, new_state = bot.handle_uploaded_documents(uploaded_files, session.state, comment)
    session.state = new_state
    _persist_assistant_messages(db, session.id, responses)
    db.commit()
    return _chat_response(db, session.id)


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
