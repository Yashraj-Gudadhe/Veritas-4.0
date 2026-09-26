"""
Database inspection script for developers/administrators.
Prints out users, conversations, messages, and attachments from the SQLite database.
Do not expose this via the public web API.
"""
import sys
import os
from pathlib import Path

# Add project root to path so we can import backend modules
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models import User, Conversation, Message, Attachment

def inspect_db():
    db = SessionLocal()
    try:
        print("="*60)
        print("DATABASE INSPECTION UTILITY")
        print("="*60)
        
        users = db.query(User).all()
        print(f"\n[{len(users)} USERS]")
        print("-" * 60)
        print(f"{'ID':<38} | {'EMAIL':<20} | {'NAME'}")
        for u in users:
            print(f"{u.id:<38} | {u.email:<20} | {u.name}")
            
        convs = db.query(Conversation).all()
        print(f"\n[{len(convs)} CONVERSATIONS]")
        print("-" * 60)
        print(f"{'ID':<38} | {'USER_ID':<38} | {'TITLE'}")
        for c in convs:
            title = c.title[:30] + "..." if len(c.title) > 30 else c.title
            print(f"{c.id:<38} | {c.user_id:<38} | {title}")
            
        msgs = db.query(Message).all()
        print(f"\n[{len(msgs)} MESSAGES]")
        print("-" * 60)
        print(f"{'ID':<38} | {'CONV_ID':<38} | {'ROLE'}")
        for m in msgs:
            print(f"{m.id:<38} | {m.conversation_id:<38} | {m.role}")

        atts = db.query(Attachment).all()
        print(f"\n[{len(atts)} ATTACHMENTS]")
        print("-" * 60)
        print(f"{'ID':<38} | {'MSG_ID':<38} | {'FILENAME':<20} | {'SIZE'}")
        for a in atts:
            msg_id = a.message_id or "Unassigned"
            filename = a.filename[:17] + "..." if len(a.filename) > 20 else a.filename
            print(f"{a.id:<38} | {msg_id:<38} | {filename:<20} | {a.file_size}")

        print("\n" + "="*60)
    finally:
        db.close()

if __name__ == "__main__":
    inspect_db()
