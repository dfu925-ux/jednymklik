"""
╔══════════════════════════════════════════════════════════════╗
║         JEDNYMKLIK.PL — Backend API                          ║
║         Withdrawal Button SaaS — art. 11a Dyrektywy UE       ║
║                                                              ║
║  Stack: FastAPI + Supabase + SMTP + Railway                  ║
╚══════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import os
import uuid
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jednymklik")

app = FastAPI(title="JednymKlik.pl API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WIDGET_DIR = os.path.join(os.path.dirname(__file__), "..", "widget")
if os.path.isdir(WIDGET_DIR):
    app.mount("/static", StaticFiles(directory=WIDGET_DIR), name="static")

@app.get("/widget.js")
def serve_widget():
    path = os.path.join(os.path.dirname(__file__), "..", "widget", "widget.js")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="widget.js nie znaleziony")

@app.get("/demo.html")
def serve_demo():
    path = os.path.join(os.path.dirname(__file__), "..", "widget", "demo.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    raise HTTPException(status_code=404, detail="demo.html nie znaleziony")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")
FROM_EMAIL   = os.getenv("FROM_EMAIL", "noreply@jednymklik.pl")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

async def sb_insert(table: str, data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=data, timeout=10)
        r.raise_for_status()
        result = r.json()
        return result[0] if result else data

async def sb_update(table: str, filters: dict, data: dict) -> dict:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    async with httpx.AsyncClient() as client:
        r = await client.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), params=params, json=data, timeout=10)
        r.raise_for_status()
        result = r.json()
        return result[0] if result else data

async def sb_select(table: str, filters: dict, limit: int = 50) -> list:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    params["limit"] = limit
    params["order"] = "timestamp_initiated.desc"
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), params=params, timeout=10)
        r.raise_for_status()
        return r.json()

async def sb_select_one(table: str, filters: dict) -> Optional[dict]:
    results = await sb_select(table, filters, limit=1)
    return results[0] if results else None

class WithdrawalRequest(BaseModel):
    shop_id: str
    order_id: str
    customer_email: EmailStr
    customer_name: Optional[str] = None
    order_date: Optional[str] = None
    order_value: Optional[float] = None
    products: Optional[list] = None

class WithdrawalConfirm(BaseModel):
    withdrawal_id: str
    reason: Optional[str] = None

class ShopRegister(BaseModel):
    shop_name: str
    shop_url: str
    owner_email: EmailStr
    owner_name: str
    plan: str = "free"

def get_timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"

def send_email(to: str, subject: str, html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        log.info(f"Email wysłany do {to}")
        return True
    except Exception as e:
        log.error(f"Błąd wysyłki emaila: {e}")
        return False

def generate_confirmation_email(withdrawal_id, order_id, customer_name, shop_name, timestamp, deadline):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>body{{font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto}}
    .header{{background:#2563eb;color:white;padding:20px;text-align:center}}
    .content{{padding:30px}}.info-box{{background:#f3f4f6;padding:15px;border-radius:8px;margin:15px 0}}
    .footer{{background:#f9fafb;padding:15px;text-align:center;font-size:12px;color:#666}}
    .id{{font-family:monospace;background:#e5e7eb;padding:4px 8px;border-radius:4px}}</style>
    </head><body>
    <div class="header"><h1>✅ Potwierdzenie odstąpienia od umowy</h1></div>
    <div class="content">
    <p>Szanowny/a <strong>{customer_name}</strong>,</p>
    <p>Potwierdzamy przyjęcie Twojego oświadczenia o odstąpieniu od umowy.</p>
    <div class="info-box">
    <p><strong>Numer zamówienia:</strong> {order_id}</p>
    <p><strong>Sklep:</strong> {shop_name}</p>
    <p><strong>Data i godzina:</strong> {timestamp}</p>
    <p><strong>Nr referencyjny:</strong> <span class="id">{withdrawal_id}</span></p>
    </div>
    <h3>Co dalej?</h3>
    <ol><li>Zwróć towar w ciągu <strong>14 dni</strong></li>
    <li>Termin zwrotu środków: <strong>do {deadline}</strong></li>
    <li>Zwrot tą samą metodą płatności</li></ol>
    <p style="color:#dc2626;font-weight:bold">⚠️ Zachowaj ten email jako dowód odstąpienia.</p>
    <p>Podstawa prawna: art. 11a Dyrektywy 2011/83/UE (Dyrektywa 2023/2673).</p>
    </div>
    <div class="footer">Obsługiwane przez <a href="https://jednymklik.pl">JednymKlik.pl</a></div>
    </body></html>"""

@app.get("/")
def root():
    return {"service": "JednymKlik.pl API", "version": "1.0.0", "status": "online", "storage": "Supabase"}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": get_timestamp()}

@app.post("/api/v1/withdrawal/initiate")
async def initiate_withdrawal(data: WithdrawalRequest, request: Request, x_shop_token: Optional[str] = Header(None)):
    if not x_shop_token:
        raise HTTPException(status_code=401, detail="Brak tokenu sklepu")
    deadline = (datetime.utcnow() + timedelta(days=14)).strftime("%d.%m.%Y")
    record = {
        "shop_id": data.shop_id, "shop_token": x_shop_token,
        "order_id": data.order_id, "customer_email": data.customer_email,
        "customer_name": data.customer_name or "Klient", "order_date": data.order_date,
        "order_value": data.order_value, "products": data.products or [],
        "status": "initiated", "step": 1,
        "client_ip": request.client.host, "user_agent": request.headers.get("user-agent", ""),
        "deadline_return": deadline, "email_sent": False,
    }
    try:
        inserted = await sb_insert("withdrawals", record)
        withdrawal_id = inserted.get("id", str(uuid.uuid4()))
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd zapisu do bazy")
    log.info(f"Withdrawal initiated: {withdrawal_id} | Order: {data.order_id}")
    return {"success": True, "withdrawal_id": withdrawal_id, "message": "Krok 1 z 2.", "order_id": data.order_id, "deadline_return": deadline}

@app.post("/api/v1/withdrawal/confirm")
async def confirm_withdrawal(data: WithdrawalConfirm, request: Request, x_shop_token: Optional[str] = Header(None)):
    try:
        withdrawal = await sb_select_one("withdrawals", {"id": data.withdrawal_id})
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd odczytu z bazy")
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Nie znaleziono odstąpienia")
    if withdrawal.get("status") == "confirmed":
        raise HTTPException(status_code=400, detail="Odstąpienie już potwierdzone")
    timestamp_confirmed = get_timestamp()
    try:
        await sb_update("withdrawals", {"id": data.withdrawal_id}, {
            "status": "confirmed", "step": 2,
            "timestamp_confirmed": timestamp_confirmed,
            "reason": data.reason, "confirm_ip": request.client.host,
        })
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd aktualizacji w bazie")
    email_html = generate_confirmation_email(
        data.withdrawal_id, withdrawal["order_id"], withdrawal["customer_name"],
        "Sklep internetowy", timestamp_confirmed, withdrawal["deadline_return"]
    )
    email_sent = send_email(withdrawal["customer_email"], f"✅ Potwierdzenie odstąpienia — {withdrawal['order_id']}", email_html)
    try:
        await sb_update("withdrawals", {"id": data.withdrawal_id}, {"email_sent": email_sent})
    except Exception:
        pass
    log.info(f"Withdrawal confirmed: {data.withdrawal_id} | Email: {email_sent}")
    return {"success": True, "withdrawal_id": data.withdrawal_id, "status": "confirmed",
            "timestamp": timestamp_confirmed, "email_sent": email_sent,
            "message": "Odstąpienie zarejestrowane.", "deadline_return": withdrawal["deadline_return"]}

@app.get("/api/v1/withdrawals/{shop_id}")
async def get_withdrawals(shop_id: str, x_shop_token: Optional[str] = Header(None), limit: int = 50):
    if not x_shop_token:
        raise HTTPException(status_code=401, detail="Brak tokenu sklepu")
    try:
        results = await sb_select("withdrawals", {"shop_id": shop_id}, limit=limit)
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd odczytu z bazy")
    return {"success": True, "total": len(results), "withdrawals": results}

@app.post("/api/v1/shops/register")
async def register_shop(data: ShopRegister):
    shop_token = str(uuid.uuid4())
    record = {"shop_name": data.shop_name, "shop_url": data.shop_url,
              "owner_email": data.owner_email, "owner_name": data.owner_name,
              "plan": data.plan, "active": True}
    try:
        inserted = await sb_insert("shops", record)
        shop_id = str(inserted.get("shop_id", uuid.uuid4()))
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd zapisu do bazy")
    return {"success": True, "shop_id": shop_id, "shop_token": shop_token,
            "widget_snippet": f'<script src="https://jednymklik-production.up.railway.app/widget.js" data-shop-id="{shop_id}" data-shop-token="{shop_token}"></script>'}

@app.get("/api/v1/withdrawal/{withdrawal_id}/status")
async def get_withdrawal_status(withdrawal_id: str):
    try:
        w = await sb_select_one("withdrawals", {"id": withdrawal_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Błąd odczytu z bazy")
    if not w:
        raise HTTPException(status_code=404, detail="Nie znaleziono odstąpienia")
    return {"withdrawal_id": withdrawal_id, "status": w["status"], "order_id": w["order_id"],
            "timestamp_initiated": w["timestamp_initiated"], "timestamp_confirmed": w.get("timestamp_confirmed"),
            "deadline_return": w["deadline_return"], "email_sent": w["email_sent"]}
