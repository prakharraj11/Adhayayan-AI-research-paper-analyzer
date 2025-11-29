# database.py - PostgreSQL + SQLite support (auto-detects)
import os
from typing import Optional, List, Dict
from datetime import datetime

# Check if PostgreSQL is available (Render sets DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print("✅ Using PostgreSQL database")
else:
    import sqlite3
    print("✅ Using SQLite database (local development)")

DB_PATH = "research_ai.db"  # SQLite fallback

def get_db():
    """Get database connection (PostgreSQL or SQLite)"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        # PostgreSQL syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                google_id TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                organization TEXT NOT NULL,
                research_interests TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_pdfs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                pdf_text TEXT,
                pages INTEGER NOT NULL,
                chunks INTEGER NOT NULL,
                summary TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
    else:
        # SQLite syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_id TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                organization TEXT NOT NULL,
                research_interests TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_pdfs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                pdf_text TEXT,
                pages INTEGER NOT NULL,
                chunks INTEGER NOT NULL,
                summary TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# === USER OPERATIONS ===

def create_user(google_id: str, email: str, name: str, username: str, 
                organization: str, research_interests: str = "") -> Optional[Dict]:
    """Create a new user"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            cursor.execute("""
                INSERT INTO users (google_id, email, name, username, organization, research_interests)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (google_id, email, name, username, organization, research_interests))
            user_id = cursor.fetchone()['id']
        else:
            cursor.execute("""
                INSERT INTO users (google_id, email, name, username, organization, research_interests)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (google_id, email, name, username, organization, research_interests))
            user_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return get_user_by_id(user_id)
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    else:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    else:
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_google_id(google_id: str) -> Optional[Dict]:
    """Get user by Google ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
    else:
        cursor.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# === CHAT HISTORY OPERATIONS ===

def add_chat_message(user_id: int, role: str, content: str, citations: str = ""):
    """Add a chat message to history"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO chat_history (user_id, role, content, citations)
            VALUES (%s, %s, %s, %s)
        """, (user_id, role, content, citations))
    else:
        cursor.execute("""
            INSERT INTO chat_history (user_id, role, content, citations)
            VALUES (?, ?, ?, ?)
        """, (user_id, role, content, citations))
    
    conn.commit()
    conn.close()

def get_chat_history(user_id: int, limit: int = 50) -> List[Dict]:
    """Get chat history for a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("""
            SELECT role, content, citations, timestamp
            FROM chat_history
            WHERE user_id = %s
            ORDER BY timestamp ASC
            LIMIT %s
        """, (user_id, limit))
    else:
        cursor.execute("""
            SELECT role, content, citations, timestamp
            FROM chat_history
            WHERE user_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (user_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def clear_chat_history(user_id: int):
    """Clear all chat history for a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("DELETE FROM chat_history WHERE user_id = %s", (user_id,))
    else:
        cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()

# === PDF OPERATIONS ===

def add_uploaded_pdf(user_id: int, filename: str, pdf_text: str, 
                     pages: int, chunks: int, summary: str = ""):
    """Add an uploaded PDF to the database (stores text in DB)"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO uploaded_pdfs (user_id, filename, pdf_text, pages, chunks, summary)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, filename, pdf_text, pages, chunks, summary))
    else:
        cursor.execute("""
            INSERT INTO uploaded_pdfs (user_id, filename, pdf_text, pages, chunks, summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, filename, pdf_text, pages, chunks, summary))
    
    conn.commit()
    conn.close()

def get_user_pdfs(user_id: int) -> List[Dict]:
    """Get all PDFs uploaded by a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("""
            SELECT id, filename, pdf_text, pages, chunks, summary, uploaded_at
            FROM uploaded_pdfs
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT id, filename, pdf_text, pages, chunks, summary, uploaded_at
            FROM uploaded_pdfs
            WHERE user_id = ?
            ORDER BY uploaded_at DESC
        """, (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_pdf_by_id(pdf_id: int) -> Optional[Dict]:
    """Get a specific PDF by ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("SELECT * FROM uploaded_pdfs WHERE id = %s", (pdf_id,))
    else:
        cursor.execute("SELECT * FROM uploaded_pdfs WHERE id = ?", (pdf_id,))
    
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_pdf(pdf_id: int):
    """Delete a PDF"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("DELETE FROM uploaded_pdfs WHERE id = %s", (pdf_id,))
    else:
        cursor.execute("DELETE FROM uploaded_pdfs WHERE id = ?", (pdf_id,))
    
    conn.commit()
    conn.close()

# === STATISTICS ===

def get_user_stats(user_id: int) -> Dict:
    """Get user statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    if USE_POSTGRES:
        cursor.execute("SELECT COUNT(*) as count FROM uploaded_pdfs WHERE user_id = %s", (user_id,))
        pdf_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM chat_history WHERE user_id = %s", (user_id,))
        message_count = cursor.fetchone()['count']
    else:
        cursor.execute("SELECT COUNT(*) FROM uploaded_pdfs WHERE user_id = ?", (user_id,))
        pdf_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chat_history WHERE user_id = ?", (user_id,))
        message_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "pdfs_uploaded": pdf_count,
        "messages_sent": message_count
    }
