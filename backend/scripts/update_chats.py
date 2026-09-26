import re

with open('backend/app/routers/chats.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
imports = '''from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
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
from app.llm.gemini_client import GeminiClient'''

content = re.sub(r'from fastapi import APIRouter.*?logger', imports, content, flags=re.DOTALL)

# 2. Update Schemas
schemas_update = '''class SendMessageRequest(BaseModel):
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
    attachment: Optional[AttachmentOut] = None'''

content = re.sub(r'class SendMessageRequest\(BaseModel\):.*?has_veritas_result: bool = False', schemas_update, content, flags=re.DOTALL)

# 3. Add Attachments Endpoint
attachment_endpoint = '''
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
'''

content = content.replace('@router.post("/{chat_id}/messages")', attachment_endpoint + '\n@router.post("/{chat_id}/messages")')

# 4. Modify get_conversation to include attachments
get_conv = '''    msgs = []
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
        ))'''

content = re.sub(r'    msgs = \[\n.*?for m in conv.messages\n    \]', get_conv, content, flags=re.DOTALL)

# 5. Modify send_message to process attachment before RAG
send_message_updates = '''
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
        user_msg.content = f"[Attached: {attachment.filename}]\\n" + user_msg.content

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
'''

content = re.sub(r'    db\.add\(user_msg\)\n    db\.commit\(\)\n    db\.refresh\(user_msg\)\n\n    # --- Call the FROZEN RAG pipeline.*?\"raw_text\": req\.document_text or \"\",', send_message_updates, content, flags=re.DOTALL)


# Write updated content
with open('backend/app/routers/chats.py', 'w', encoding='utf-8') as f:
    f.write(content)
