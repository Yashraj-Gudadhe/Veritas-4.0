"""
Chats router:
  POST   /api/chats                          — create a new conversation
  GET    /api/chats                          — list user's conversations
  GET    /api/chats/{chat_id}                — get conversation + messages
  DELETE /api/chats/{chat_id}                — delete conversation
  PATCH  /api/chats/{chat_id}                — rename conversation
  POST   /api/chats/{chat_id}/messages       — send a message, invoke RAG, save + return response

The existing RAG pipeline (veritas_graph) is called unmodified inside the message endpoint.
"""
import json
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import shutil

from app.database import get_db
from app.models import User, Conversation, Message, Attachment
from app.auth import get_current_user
from app.utils.logger import logger
from app.config import settings
from app.ingestion.pdf_parser import PDFParser
from app.llm.gemini_client import GeminiClient

# Import the FROZEN RAG pipeline — call only, never modify
from app.graph.workflow import veritas_graph

router = APIRouter(prefix="/api/chats", tags=["chats"])


# --- Pydantic schemas -------------------------------------------------------

class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"


class RenameConversationRequest(BaseModel):
    title: str


class SendMessageRequest(BaseModel):
    content: str
    attachment_id: Optional[str] = None
    document_text: Optional[str] = ""
    document_id: Optional[str] = None
    document_name: Optional[str] = "document.pdf"

class AttachmentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    mime_type: str
    file_size: int

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    has_veritas_result: bool = False
    attachment: Optional[AttachmentOut] = None


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetailOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[MessageOut]


# --- Helper: generate a short title from first message ----------------------

def _generate_title(text: str) -> str:
    """
    Lightweight deterministic title generation from the user's first message.
    Does NOT call the LLM — just trims and truncates.
    """
    stripped = text.strip()
    # Take first sentence or first 60 chars
    for sep in ["?", ".", "!"]:
        idx = stripped.find(sep)
        if 0 < idx < 80:
            stripped = stripped[: idx + 1]
            break
    return stripped[:72].strip() or "New Conversation"


# --- Helper: verify ownership -----------------------------------------------

def _get_conversation_for_user(chat_id: str, user: User, db: Session) -> Conversation:
    conv = db.query(Conversation).filter(
        Conversation.id == chat_id,
        Conversation.user_id == user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


# --- Endpoints ---------------------------------------------------------------

@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    req: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = Conversation(
        user_id=current_user.id,
        title=req.title or "New Conversation",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


@router.get("", response_model=List[ConversationOut])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    result = []
    for c in convs:
        msg_count = len(c.messages)
        result.append(ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            message_count=msg_count,
        ))
    return result


@router.get("/{chat_id}", response_model=ConversationDetailOut)
def get_conversation(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_conversation_for_user(chat_id, current_user, db)
    msgs = []
    for m in conv.messages:
        attachment_out = None
        att = db.query(Attachment).filter(Attachment.message_id == m.id).first()
        if att:
            attachment_out = AttachmentOut(
                id=att.id,
                filename=att.filename,
                file_type=att.file_type,
                mime_type=att.mime_type,
                file_size=int(att.file_size)
            )
        msgs.append(MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
            has_veritas_result=bool(m.veritas_result_json),
            attachment=attachment_out
        ))
    return ConversationDetailOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        messages=msgs,
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_conversation_for_user(chat_id, current_user, db)
    db.delete(conv)
    db.commit()


@router.patch("/{chat_id}", response_model=ConversationOut)
def rename_conversation(
    chat_id: str,
    req: RenameConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_conversation_for_user(chat_id, current_user, db)
    conv.title = req.title.strip() or conv.title
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )



MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

@router.post("/{chat_id}/attachments", response_model=AttachmentOut)
async def upload_attachment(
    chat_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_conversation_for_user(chat_id, current_user, db)
    
    content_type = file.content_type
    allowed_types = [
        "application/pdf", "image/jpeg", "image/png", "image/webp",
        "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type")
        
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_SIZE_MB} MB.")
        
    save_dir = settings.DATA_DIR / "attachments"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{file_id}{ext}"
    file_path = save_dir / safe_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    attachment = Attachment(
        id=file_id,
        conversation_id=chat_id,
        filename=file.filename,
        file_type=ext.lstrip('.'),
        mime_type=content_type,
        file_size=str(file_size),
        storage_path=str(file_path)
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return AttachmentOut(
        id=attachment.id,
        filename=attachment.filename,
        file_type=attachment.file_type,
        mime_type=attachment.mime_type,
        file_size=file_size
    )

@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str,
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a user message → invoke the FROZEN VERITAS RAG pipeline → save both messages → return result.
    The veritas_graph.ainvoke() call is identical to what main.py does in /api/analyze.
    """
    if not req.content.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message content cannot be empty")

    conv = _get_conversation_for_user(chat_id, current_user, db)

    # Auto-title: if this is the first message, derive title from content
    existing_msg_count = db.query(Message).filter(Message.conversation_id == chat_id).count()
    if existing_msg_count == 0 and conv.title in ("New Conversation", ""):
        conv.title = _generate_title(req.content)

    # Persist user message
    user_msg = Message(
        conversation_id=chat_id,
        role="user",
        content=req.content,
    )

    # Process attachment if present
    extracted_text = req.document_text or ""
    doc_name = req.document_name or "clinical_document.pdf"
    
    attachment = None
    if req.attachment_id:
        attachment = db.query(Attachment).filter(
            Attachment.id == req.attachment_id,
            Attachment.conversation_id == chat_id
        ).first()
        
        if not attachment:
            raise HTTPException(status_code=400, detail="Attachment not found or does not belong to this conversation")
            
        doc_name = attachment.filename
        file_path = attachment.storage_path
        
        if attachment.mime_type == "application/pdf":
            try:
                pdf_result = PDFParser.parse_pdf(file_path, document_id=attachment.id)
                extracted_text = pdf_result.full_text
            except Exception as e:
                logger.error(f"PDF parsing error: {e}")
                raise HTTPException(status_code=400, detail=f"Could not parse PDF: {str(e)}")
                
        elif attachment.mime_type.startswith("image/"):
            try:
                with open(file_path, "rb") as f:
                    img_bytes = f.read()
                extracted_text = await GeminiClient.extract_image_text(img_bytes, attachment.mime_type)
            except Exception as e:
                logger.error(f"Image Vision error: {e}")
                raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")
                
        elif attachment.mime_type == "text/plain":
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
                
        # Update user message to indicate attachment
        user_msg.content = f"[Attached: {attachment.filename}]\n" + user_msg.content

    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    
    if attachment:
        attachment.message_id = user_msg.id
        db.commit()

    # --- Call the FROZEN RAG pipeline (unchanged from main.py /api/analyze) ---
    req_id = f"REQ-{uuid.uuid4().hex[:8]}"
    doc_id = req.document_id or (attachment.id if attachment else f"DOC-{uuid.uuid4().hex[:6]}")

    initial_state = {
        "request_id": req_id,
        "document_id": doc_id,
        "document_name": doc_name,
        "raw_text": extracted_text,

        "user_query": req.content,
        "file_path": None,
        "observations": [],
        "claims": [],
        "normalized_concepts": [],
        "evidence_requirements": [],
        "local_evidence": [],
        "online_evidence": [],
        "merged_evidence": [],
        "scored_evidence": [],
        "supporting_evidence": [],
        "conflicting_evidence": [],
        "questionable_evidence": [],
        "contradictions": [],
        "missing_information": [],
        "overall_evidence_score": 0.0,
        "score_breakdown": {},
        "decision_status": "NO_RELIABLE_CONCLUSION",
        "human_review_required": True,
        "final_explanation": "",
        "citations": [],
        "audit_log": [],
    }

    try:
        final_state = await veritas_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"RAG pipeline error in chat {chat_id}: {str(e)}")
        # Persist a failure message so the conversation is not left dangling
        err_msg = Message(
            conversation_id=chat_id,
            role="assistant",
            content="I encountered an error processing your request. Please try again.",
        )
        db.add(err_msg)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Pipeline failed: {str(e)}")

    explanation = final_state.get("final_explanation", "No explanation generated.")
    decision_status = final_state.get("decision_status", "NO_RELIABLE_CONCLUSION")
    evidence_score = final_state.get("overall_evidence_score", 0.0)

    # Build a compact, chat-friendly summary of the VERITAS result
    assistant_content = explanation

    # Serialise the full result for potential audit replay
    veritas_result = {
        "request_id": req_id,
        "decision_status": decision_status,
        "evidence_quality_score": evidence_score,
        "score_breakdown": final_state.get("score_breakdown", {}),
        "observations": final_state.get("observations", []),
        "claims": final_state.get("claims", []),
        "supporting_evidence": final_state.get("supporting_evidence", []),
        "conflicting_evidence": final_state.get("conflicting_evidence", []),
        "questionable_evidence": final_state.get("questionable_evidence", []),
        "contradictions": final_state.get("contradictions", []),
        "missing_information": final_state.get("missing_information", []),
        "citations": final_state.get("citations", []),
        "human_review_required": final_state.get("human_review_required", False),
        "final_explanation": explanation,
    }

    # Persist assistant message
    assistant_msg = Message(
        conversation_id=chat_id,
        role="assistant",
        content=assistant_content,
        veritas_result_json=json.dumps(veritas_result),
    )
    db.add(assistant_msg)

    # Update conversation's updated_at timestamp
    from datetime import datetime, timezone
    conv.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(assistant_msg)

    return {
        "message": {
            "id": assistant_msg.id,
            "role": "assistant",
            "content": assistant_content,
            "created_at": assistant_msg.created_at.isoformat(),
        },
        "veritas_result": veritas_result,
        "conversation_title": conv.title,
    }


@router.get("/{chat_id}/messages/{message_id}/veritas")
def get_veritas_result(
    chat_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full VERITAS audit result stored with a specific assistant message."""
    conv = _get_conversation_for_user(chat_id, current_user, db)
    msg = db.query(Message).filter(
        Message.id == message_id,
        Message.conversation_id == chat_id,
    ).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if not msg.veritas_result_json:
        raise HTTPException(status_code=404, detail="No VERITAS result stored for this message")
    return json.loads(msg.veritas_result_json)
