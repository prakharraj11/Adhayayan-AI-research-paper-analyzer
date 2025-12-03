# app.py - AI Research Chatbot with PostgreSQL support
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import requests
from dotenv import load_dotenv
from database import (
    init_db, create_user, get_user_by_email, get_user_by_google_id,
    add_chat_message, get_chat_history, add_uploaded_pdf, get_user_pdfs,
    get_pdf_by_id, delete_pdf, clear_chat_history
)
from paper_search import search_papers_from_pdf
from ingest import ingest_pdf_to_text
from retrieval import retrieve_from_pdf_texts
from llm_agent import answer_with_context

load_dotenv()

PORT = int(os.getenv("PORT", 10000))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:10000")

app = FastAPI(title="AI Research Chatbot")

# Initialize database
init_db()

# === SESSION STORAGE ===
sessions = {}  # session_id -> user_data

# === GOOGLE OAUTH ===
def get_google_login_url():
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": f"{RENDER_EXTERNAL_URL}/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent"
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base_url}?{query}"

def verify_google_token(code: str):
    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{RENDER_EXTERNAL_URL}/callback"
        }
        token_resp = requests.post(token_url, data=data, timeout=10)
        if token_resp.status_code != 200:
            return None
        access_token = token_resp.json().get("access_token")
        user_resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        return user_resp.json() if user_resp.status_code == 200 else None
    except:
        return None

def get_session_user(request: Request):
    sid = request.cookies.get("session_id")
    return sessions.get(sid) if sid and sid in sessions else None

# === HTML TEMPLATES ===
def get_login_html():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>अध्ययन - Research AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body {
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e0e0e0;
        }
        .login-box {
            background: rgba(20, 20, 35, 0.9);
            padding: 50px 60px;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            text-align: center;
            max-width: 450px;
            border: 1px solid rgba(100, 100, 150, 0.2);
        }
        h1 {
            font-size: 36px;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #a78bfa, #c4b5fd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        p { color: #9ca3af; margin-bottom: 30px; font-size: 15px; }
        .login-btn {
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            color: white;
            padding: 14px 40px;
            border-radius: 12px;
            text-decoration: none;
            display: inline-block;
            font-weight: 600;
            font-size: 16px;
            transition: transform 0.2s, box-shadow 0.2s;
            border: none;
            cursor: pointer;
        }
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(124, 58, 237, 0.4);
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🔬 अध्ययन</h1>
        <p>AI-Powered Research Paper Analyzer</p>
        <a href="/login" class="login-btn">Continue with Google</a>
    </div>
</body>
</html>
"""

def get_registration_html(google_email, google_name):
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Complete Registration</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }}
        body {{
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .reg-box {{
            background: rgba(20, 20, 35, 0.95);
            padding: 40px 50px;
            border-radius: 24px;
            max-width: 550px;
            width: 100%;
            border: 1px solid rgba(100, 100, 150, 0.2);
        }}
        h2 {{
            color: #a78bfa;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        p {{ color: #9ca3af; margin-bottom: 25px; font-size: 14px; }}
        label {{
            display: block;
            color: #d1d5db;
            margin-bottom: 8px;
            font-size: 14px;
            font-weight: 500;
        }}
        input, textarea {{
            width: 100%;
            padding: 12px 16px;
            margin-bottom: 20px;
            background: rgba(30, 30, 45, 0.8);
            border: 1px solid rgba(100, 100, 150, 0.3);
            border-radius: 10px;
            color: #e0e0e0;
            font-size: 14px;
        }}
        input:focus, textarea:focus {{
            outline: none;
            border-color: #7c3aed;
        }}
        textarea {{ resize: vertical; min-height: 80px; }}
        button {{
            width: 100%;
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            color: white;
            padding: 14px;
            border-radius: 12px;
            border: none;
            font-weight: 600;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        button:hover {{ transform: translateY(-2px); }}
        .optional {{ color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="reg-box">
        <h2>Welcome! Complete Your Profile</h2>
        <p>We need a few more details to get you started</p>
        <form action="/register" method="post">
            <label>Full Name *</label>
            <input type="text" name="name" value="{google_name}" required>
            
            <label>Email *</label>
            <input type="email" name="email" value="{google_email}" readonly>
            
            <label>Username *</label>
            <input type="text" name="username" placeholder="Choose a unique username" required>
            
            <label>Organization/University *</label>
            <input type="text" name="organization" placeholder="e.g., Stanford University" required>
            
            <label>Research Interests <span class="optional">(optional)</span></label>
            <textarea name="research_interests" placeholder="e.g., Machine Learning, NLP, Computer Vision"></textarea>
            
            <button type="submit">Create Account</button>
        </form>
    </div>
</body>
</html>
"""

def get_chat_html(user, chat_history, pdfs):
    messages_html = ""
    for msg in chat_history:
        role = msg['role']
        content = msg['content']
        citations = msg.get('citations', '')
        
        if role == 'user':
            messages_html += f"""
            <div class="message user-message">
                <div class="avatar">👤</div>
                <div class="text">{content}</div>
            </div>
            """
        else:
            messages_html += f"""
            <div class="message ai-message">
                <div class="avatar">🤖</div>
                <div class="text">
                    {content}
                    {f'<details class="citations"><summary>📚 View Citations & Related Papers</summary><div class="citation-content">{citations}</div></details>' if citations else ''}
                </div>
            </div>
            """
    
    pdfs_html = ""
    if pdfs:
        for pdf in pdfs:
            pdfs_html += f"""
            <div class="pdf-item">
                <span class="pdf-icon">📄</span>
                <span class="pdf-name">{pdf['filename']}</span>
                <span class="pdf-pages">{pdf['pages']} pages</span>
                <button class="pdf-delete" onclick="if(confirm('Delete this PDF?')) window.location.href='/delete-pdf/{pdf['id']}'">×</button>
            </div>
            """
    else:
        pdfs_html = "<p class='no-pdfs'>No documents uploaded yet. Upload PDFs to start analyzing!</p>"

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Research AI - Chat</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }}
        body {{
            background: #0a0a0f;
            color: #e0e0e0;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        .sidebar {{
            width: 280px;
            background: rgba(15, 15, 25, 0.95);
            border-right: 1px solid rgba(100, 100, 150, 0.15);
            display: flex;
            flex-direction: column;
            padding: 20px;
        }}
        .sidebar-header {{
            margin-bottom: 30px;
        }}
        .sidebar-header h1 {{
            font-size: 24px;
            background: linear-gradient(135deg, #a78bfa, #c4b5fd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }}
        .user-info {{
            display: flex;
            align-items: center;
            padding: 12px;
            background: rgba(30, 30, 45, 0.5);
            border-radius: 12px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .user-avatar {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
            font-size: 18px;
        }}
        .pdfs-section {{
            flex: 1;
            overflow-y: auto;
            margin-bottom: 20px;
        }}
        .pdfs-section h3 {{
            font-size: 14px;
            color: #9ca3af;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .pdf-item {{
            background: rgba(30, 30, 45, 0.5);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            font-size: 13px;
            position: relative;
        }}
        .pdf-item:hover {{
            background: rgba(30, 30, 45, 0.7);
        }}
        .pdf-delete {{
            position: absolute;
            right: 8px;
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        .pdf-item:hover .pdf-delete {{
            opacity: 1;
        }}
        .pdf-delete:hover {{
            background: rgba(239, 68, 68, 0.4);
        }}
        .pdf-icon {{ margin-right: 8px; }}
        .pdf-name {{ flex: 1; color: #d1d5db; }}
        .pdf-pages {{ color: #6b7280; font-size: 11px; }}
        .no-pdfs {{ color: #6b7280; font-size: 13px; text-align: center; padding: 20px 0; }}
        .upload-label {{
            cursor: pointer;
            padding: 10px;
            border-radius: 10px;
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            color: white;
            font-size: 14px;
            font-weight: 600;
            text-align: center;
            display: block;
            margin-bottom: 10px;
            border: none;
        }}
        .upload-label:hover {{ opacity: 0.9; }}
        input[type="file"] {{ display: none; }}
        .logout-btn {{
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            padding: 8px;
            border-radius: 8px;
            text-align: center;
            cursor: pointer;
            font-size: 13px;
            border: 1px solid rgba(239, 68, 68, 0.3);
            width: 100%;
            margin-top: 10px;
        }}
        .logout-btn:hover {{ background: rgba(239, 68, 68, 0.3); }}
        .clear-chat-btn {{
            background: rgba(255, 159, 64, 0.2);
            color: #fbbf24;
            padding: 8px;
            border-radius: 8px;
            text-align: center;
            cursor: pointer;
            font-size: 13px;
            border: 1px solid rgba(255, 159, 64, 0.3);
            width: 100%;
            margin-top: 8px;
        }}
        .clear-chat-btn:hover {{ background: rgba(255, 159, 64, 0.3); }}
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
        }}
        .chat-area {{
            flex: 1;
            overflow-y: auto;
            padding: 40px 20px 20px 20px;
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
        }}
        .message {{
            display: flex;
            margin-bottom: 30px;
            align-items: flex-start;
        }}
        .avatar {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            font-size: 20px;
            flex-shrink: 0;
        }}
        .user-message .avatar {{
            background: linear-gradient(135deg, #3b82f6, #60a5fa);
        }}
        .ai-message .avatar {{
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
        }}
        .text {{
            flex: 1;
            padding: 14px 18px;
            border-radius: 16px;
            line-height: 1.6;
            font-size: 15px;
        }}
        .user-message .text {{
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}
        .ai-message .text {{
            background: rgba(30, 30, 45, 0.6);
            border: 1px solid rgba(100, 100, 150, 0.2);
        }}
        .citations {{
            margin-top: 15px;
            padding: 12px;
            background: rgba(20, 20, 30, 0.8);
            border-radius: 10px;
            border-left: 3px solid #a78bfa;
        }}
        .citations summary {{
            cursor: pointer;
            color: #a78bfa;
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .citation-content {{
            color: #d1d5db;
            font-size: 13px;
            line-height: 1.8;
            margin-top: 10px;
        }}
        .input-area {{
            border-top: 1px solid rgba(100, 100, 150, 0.15);
            padding: 20px;
            background: rgba(15, 15, 25, 0.95);
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
        }}
        .input-form {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        textarea {{
            flex: 1;
            padding: 14px 18px;
            background: rgba(30, 30, 45, 0.8);
            border: 1px solid rgba(100, 100, 150, 0.3);
            border-radius: 16px;
            color: #e0e0e0;
            font-size: 15px;
            resize: none;
            font-family: 'Inter', sans-serif;
        }}
        textarea:focus {{
            outline: none;
            border-color: #7c3aed;
        }}
        .send-btn {{
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            color: white;
            padding: 14px 24px;
            border-radius: 16px;
            border: none;
            cursor: pointer;
            font-weight: 600;
            font-size: 15px;
            white-space: nowrap;
        }}
        .send-btn:hover {{ opacity: 0.9; }}
        .send-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        input[type="file"] {{ display: none; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h1>🔬 अध्ययन</h1>
            <p style="font-size: 11px; color: #6b7280; margin-top: 5px;">Research AI</p>
        </div>
        <div class="user-info">
            <div class="user-avatar">{user['name'][0].upper()}</div>
            <div>
                <div style="font-weight: 600;">{user['name']}</div>
                <div style="font-size: 12px; color: #6b7280;">@{user['username']}</div>
            </div>
        </div>
        <div class="pdfs-section">
            <h3>Uploaded Documents</h3>
            {pdfs_html}
        </div>
        <form action="/upload" method="post" enctype="multipart/form-data" style="margin-bottom: 10px;">
            <input type="file" name="files" id="fileInput" multiple accept=".pdf" onchange="this.form.submit()">
            <label for="fileInput" class="upload-label">📤 Upload PDFs</label>
        </form>
        <button class="clear-chat-btn" onclick="if(confirm('Clear all chat history and documents?')) window.location.href='/clear-chat'">🗑️ Clear Chat</button>
        <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    </div>
    <div class="main-content">
        <div class="chat-area" id="chatArea">
            {messages_html if messages_html else '<div style="text-align: center; color: #6b7280; margin-top: 100px; font-size: 16px;">👋 Upload a PDF and start asking questions!</div>'}
        </div>
        <div class="input-area">
            <form action="/chat" method="post" class="input-form" id="chatForm">
                <textarea name="message" rows="1" placeholder="Ask about your research papers..." required id="messageInput"></textarea>
                <button type="submit" class="send-btn" id="sendBtn">Send</button>
            </form>
        </div>
    </div>
    <script>
        const chatArea = document.getElementById('chatArea');
        chatArea.scrollTop = chatArea.scrollHeight;
        
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', function() {{
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        }});
        
        document.getElementById('chatForm').addEventListener('submit', function() {{
            document.getElementById('sendBtn').disabled = true;
        }});
    </script>
</body>
</html>
"""

# === ROUTES ===
@app.get("/")
async def home(request: Request):
    user = get_session_user(request)
    return RedirectResponse("/chat") if user else HTMLResponse(get_login_html())

@app.get("/login")
async def login():
    return RedirectResponse(get_google_login_url())

@app.get("/callback")
async def callback(request: Request, code: str = None):
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    
    google_user = verify_google_token(code)
    if not google_user:
        raise HTTPException(status_code=400, detail="Invalid token")
    
    # Check if user exists
    user = get_user_by_google_id(google_user.get('sub'))
    
    if not user:
        # New user - show registration form
        sid = str(uuid.uuid4())
        sessions[sid] = {"pending_registration": True, "google_data": google_user}
        resp = HTMLResponse(get_registration_html(
            google_user.get('email', ''),
            google_user.get('name', '')
        ))
        resp.set_cookie(key="session_id", value=sid, httponly=True)
        return resp
    
    # Existing user - log them in
    sid = str(uuid.uuid4())
    sessions[sid] = user
    resp = RedirectResponse("/chat")
    resp.set_cookie(key="session_id", value=sid, httponly=True)
    return resp

@app.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    organization: str = Form(...),
    research_interests: str = Form("")
):
    sid = request.cookies.get("session_id")
    if not sid or sid not in sessions:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    session_data = sessions[sid]
    if not session_data.get("pending_registration"):
        raise HTTPException(status_code=400, detail="Not in registration flow")
    
    google_data = session_data["google_data"]
    
    # Create user
    user = create_user(
        google_id=google_data.get('sub'),
        email=email,
        name=name,
        username=username,
        organization=organization,
        research_interests=research_interests
    )
    
    if not user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Update session
    sessions[sid] = user
    return RedirectResponse("/chat", status_code=303)

@app.get("/chat")
async def chat_page(request: Request):
    user = get_session_user(request)
    if not user:
        return RedirectResponse("/")
    
    chat_history = get_chat_history(user['id'])
    pdfs = get_user_pdfs(user['id'])
    
    return HTMLResponse(get_chat_html(user, chat_history, pdfs))

@app.post("/upload")
async def upload_pdfs(request: Request, files: list[UploadFile] = File(...)):
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check current PDF count
    current_pdfs = get_user_pdfs(user['id'])
    
    # Limit to 5 total PDFs to avoid token issues
    if len(current_pdfs) + len(files) > 5:
        raise HTTPException(
            status_code=400, 
            detail=f"Maximum 5 PDFs allowed. You have {len(current_pdfs)} PDFs. Please delete some before uploading more."
        )
    
    for file in files:
        try:
            # Process PDF and extract text
            pdf_text, pages, summary, pdf_name = ingest_pdf_to_text(file)
            
            # Store in database (text stored in DB, no file storage needed!)
            add_uploaded_pdf(
                user_id=user['id'],
                filename=pdf_name,
                pdf_text=pdf_text,
                pages=pages,
                chunks=len(pdf_text.split('\n\n')),  # Rough chunk estimate
                summary=summary
            )
        except Exception as e:
            print(f"Error uploading {file.filename}: {e}")
            continue
    
    return RedirectResponse("/chat", status_code=303)

@app.post("/chat")
async def chat_message(request: Request, message: str = Form(...)):
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get all user's PDFs
    pdfs = get_user_pdfs(user['id'])
    
    if not pdfs:
        response_text = "Please upload at least one PDF document before asking questions."
        citations = ""
    else:
        try:
            # Retrieve context from PDF texts stored in database
            chunks = retrieve_from_pdf_texts(message, pdfs)
            
            # Get answer from LLM
            response_text = answer_with_context(message, chunks)
            
            # Extract citations and generate related papers
            citations = search_papers_from_pdf(pdfs, response_text)
        except Exception as e:
            print(f"❌ Error processing chat: {e}")
            response_text = "I encountered an error while processing your question. Please try again."
            citations = ""
    
    # Save to chat history
    add_chat_message(user['id'], 'user', message)
    add_chat_message(user['id'], 'assistant', response_text, citations)
    
    return RedirectResponse("/chat", status_code=303)

@app.get("/delete-pdf/{pdf_id}")
async def delete_pdf_route(request: Request, pdf_id: int):
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Verify PDF belongs to user and delete it
    pdf = get_pdf_by_id(pdf_id)
    if pdf and pdf['user_id'] == user['id']:
        delete_pdf(pdf_id)
    
    return RedirectResponse("/chat", status_code=303)

@app.get("/clear-chat")
async def clear_chat_route(request: Request):
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Clear all chat history and PDFs for this user
    clear_chat_history(user['id'])
    
    # Delete all PDFs
    pdfs = get_user_pdfs(user['id'])
    for pdf in pdfs:
        delete_pdf(pdf['id'])
    
    return RedirectResponse("/chat", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    sid = request.cookies.get("session_id")
    if sid and sid in sessions:
        del sessions[sid]
    
    resp = RedirectResponse("/")
    resp.delete_cookie("session_id")
    return resp

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
