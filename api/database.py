"""
SQLite database operations for conversation history.
Simple persistence for page refresh recovery.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
import os


DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/conversations.db")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database schema if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migrate existing conversations table to add token columns if they don't exist
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN input_tokens INTEGER DEFAULT 0")
        except:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN output_tokens INTEGER DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN total_cost REAL DEFAULT 0.0")
        except:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                type TEXT NOT NULL,
                role TEXT,
                content TEXT NOT NULL,
                tool_name TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_created
            ON messages(created_at DESC)
        """)


# Conversation operations

def create_conversation(conversation_id: str, role: str) -> Dict:
    """Create a new conversation."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, role) VALUES (?, ?)",
            (conversation_id, role)
        )
    return {"id": conversation_id, "role": role}


def get_conversation(conversation_id: str) -> Optional[Dict]:
    """Get conversation by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,)
        ).fetchone()

        if row:
            return dict(row)
    return None


def list_conversations(limit: int = 50, offset: int = 0) -> List[Dict]:
    """List all conversations, most recent first."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.*, COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        return [dict(row) for row in rows]


def update_conversation_timestamp(conversation_id: str):
    """Update the updated_at timestamp for a conversation."""
    with get_db() as conn:
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )


def update_conversation_usage(
    conversation_id: str,
    input_tokens: int,
    output_tokens: int,
    cost: float
):
    """Update token usage and cost for a conversation."""
    with get_db() as conn:
        conn.execute("""
            UPDATE conversations
            SET input_tokens = input_tokens + ?,
                output_tokens = output_tokens + ?,
                total_cost = total_cost + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (input_tokens, output_tokens, cost, conversation_id))


def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages."""
    with get_db() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# Message operations

def add_message(
    message_id: str,
    conversation_id: str,
    msg_type: str,
    content: str,
    role: Optional[str] = None,
    tool_name: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Dict:
    """Add a message to a conversation."""
    metadata_json = json.dumps(metadata) if metadata else None

    with get_db() as conn:
        conn.execute("""
            INSERT INTO messages (id, conversation_id, type, role, content, tool_name, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message_id, conversation_id, msg_type, role, content, tool_name, metadata_json))

    # Update conversation timestamp
    update_conversation_timestamp(conversation_id)

    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "type": msg_type,
        "role": role,
        "content": content,
        "tool_name": tool_name,
        "metadata": metadata
    }


def get_messages(conversation_id: str) -> List[Dict]:
    """Get all messages for a conversation."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """, (conversation_id,)).fetchall()

        messages = []
        for row in rows:
            msg = dict(row)
            # Parse metadata JSON
            if msg.get('metadata'):
                msg['metadata'] = json.loads(msg['metadata'])
            messages.append(msg)

        return messages


def delete_message(message_id: str):
    """Delete a specific message."""
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
