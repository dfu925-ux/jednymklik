"""
╔══════════════════════════════════════════════════════════════╗
║         JEDNYMKLIK.PL — Backend API                         ║
║         Withdrawal Button SaaS — art. 11a Dyrektywy UE      ║
║                                                             ║
║  Stack: FastAPI + Supabase + SMTP + Railway                 ║
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
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jednymklik")

app = FastAPI(title="JednymKlik.pl API", version="1.0.0")

# ─────────────────────────────────────────────
# CORS
# Widget jest osadzany na dowolnym sklepie klienta — Origin nieznany z góry,
# więc allow_origins="*" jest tu uzasadnione dla endpointów widgetowych.
# Uwaga: spec CORS zabrania jednocześnie "*" + allow_credentials=True,
# więc credentials wyłączone — autoryzacja idzie przez shop_token w body/headerze,
# nie przez ciasteczka.
#
# TODO (przed pierwszą sprzedażą): przenieść endpointy administracyjne
# (rejestracja sklepu, panel, statystyki) na osobny prefix /admin/*
# z osobnym CORS-em ograniczonym do https://latwyzwrot.pl + https://app.latwyzwrot.pl.
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=86400,
)

WIDGET_DIR = os.path.dirname(__file__)
if os.path.isdir(WIDGET_DIR):
    app.mount("/static", StaticFiles(directory=WIDGET_DIR), name="static")

@app.get("/widget.js")
def serve_widget():
    path = os.path.join(os.path.dirname(__file__), "widget.js")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="widget.js nie znaleziony")

@app.get("/demo.html")
def serve_demo():
    # Szukaj demo.html w tym samym folderze co main.py (backend/)
    path = os.path.join(os.path.dirname(__file__), "demo.html")
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    # Fallback: folder widget/
    path2 = os.path.join(os.path.dirname(__file__), "..", "widget", "demo.html")
    if os.path.exists(path2):
        return FileResponse(path2, media_type="text/html")
    raise HTTPException(status_code=404, detail="demo.html nie znaleziony")

# ─────────────────────────────────────────────
# SUPABASE CONFIG
# ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

async def sb_insert(table: str, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=data, headers=headers)
        r.raise_for_status()
        return r.json()[0] if r.json() else {}

async def sb_select(table: str, filters: dict, limit: int = 50):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"limit": limit}
    for k, v in filters.items():
        params[k] = f"eq.{v}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, headers=headers)
        r.raise_for_status()
        return r.json()

async def sb_select_one(table: str, filters: dict):
    results = await sb_select(table, filters, limit=1)
    return results[0] if results else None

async def sb_update(table: str, filters: dict, data: dict):
    params = {}
    for k, v in filters.items():
        params[k] = f"eq.{v}"
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient() as client:
        r = await client.patch(url, json=data, params=params, headers=headers)
        r.raise_for_status()
        return r.json()

# ─────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@jednymklik.pl")

def send_email(to_email: str, subject: str, body_html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        log.error(f"Email error: {e}")
        return False

# ─────────────────────────────────────────────
# MODELE
# ─────────────────────────────────────────────
class WithdrawalInitiate(BaseModel):
    shop_id: str
    order_id: str
    customer_email: str
    customer_name: Optional[str] = None
    order_date: Optional[str] = None
    order_value: Optional[float] = None

class WithdrawalConfirm(BaseModel):
    withdrawal_id: str
    reason: Optional[str] = None

class ShopRegister(BaseModel):
    shop_name: str
    shop_url: str
    owner_email: str
    owner_name: Optional[str] = None
    plan: Optional[str] = "free"

# ─────────────────────────────────────────────
# ENDPOINTY
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "JednymKlik.pl API", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/withdrawal/initiate")
async def initiate_withdrawal(data: WithdrawalInitiate, x_shop_token: Optional[str] = Header(None)):
    if not x_shop_token:
        raise HTTPException(status_code=401, detail="Brak tokenu sklepu")
    try:
        shop = await sb_select_one("shops", {"shop_token": x_shop_token})
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd odczytu z bazy")
    if not shop:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token sklepu")

    withdrawal_id = str(uuid.uuid4())
    deadline = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")

    record = {
        "id": withdrawal_id,
        "shop_id": data.shop_id,
        "order_id": data.order_id,
        "customer_email": data.customer_email,
        "customer_name": data.customer_name,
        "order_date": data.order_date,
        "order_value": data.order_value,
        "status": "initiated",
        "deadline_return": deadline,
        "timestamp_initiated": datetime.utcnow().isoformat(),
        "email_sent": False,
    }

    try:
        await sb_insert("withdrawals", record)
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd zapisu do bazy")

    log.info(f"Withdrawal initiated: {withdrawal_id} | Order: {data.order_id}")
    return {
        "success": True,
        "withdrawal_id": withdrawal_id,
        "status": "initiated",
        "deadline_return": deadline,
    }

@app.post("/api/v1/withdrawal/confirm")
async def confirm_withdrawal(data: WithdrawalConfirm, x_shop_token: Optional[str] = Header(None)):
    if not x_shop_token:
        raise HTTPException(status_code=401, detail="Brak tokenu sklepu")

    try:
        withdrawal = await sb_select_one("withdrawals", {"id": data.withdrawal_id})
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd odczytu z bazy")

    if not withdrawal:
        raise HTTPException(status_code=404, detail="Nie znaleziono odstąpienia")
    if withdrawal["status"] == "confirmed":
        raise HTTPException(status_code=400, detail="Odstąpienie już potwierdzone")

    timestamp_confirmed = datetime.utcnow().isoformat()

    email_sent = False
    if withdrawal.get("customer_email") and SMTP_HOST:
        subject = f"Potwierdzenie odstąpienia od umowy — zamówienie {withdrawal['order_id']}"
        body = f"""
        <h2>Potwierdzenie odstąpienia od umowy</h2>
        <p>Twoje odstąpienie zostało zarejestrowane.</p>
        <p><strong>Nr zamówienia:</strong> {withdrawal['order_id']}</p>
        <p><strong>Nr referencyjny:</strong> {data.withdrawal_id}</p>
        <p><strong>Termin zwrotu towaru:</strong> {withdrawal['deadline_return']}</p>
        <p><strong>Powód:</strong> {data.reason or 'Nie podano'}</p>
        <hr>
        <p style="font-size:12px;color:#666">JednymKlik.pl — zgodność z art. 11a Dyrektywy UE 2023/2673</p>
        """
        email_sent = send_email(withdrawal["customer_email"], subject, body)

    try:
        await sb_update("withdrawals", {"id": data.withdrawal_id}, {
            "status": "confirmed",
            "reason": data.reason,
            "timestamp_confirmed": timestamp_confirmed,
            "email_sent": email_sent,
        })
    except Exception:
        pass

    log.info(f"Withdrawal confirmed: {data.withdrawal_id} | Email: {email_sent}")
    return {
        "success": True,
        "withdrawal_id": data.withdrawal_id,
        "status": "confirmed",
        "timestamp": timestamp_confirmed,
        "email_sent": email_sent,
        "message": "Odstąpienie zarejestrowane.",
        "deadline_return": withdrawal["deadline_return"],
    }

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
    record = {
        "shop_name": data.shop_name,
        "shop_url": data.shop_url,
        "owner_email": data.owner_email,
        "owner_name": data.owner_name,
        "plan": data.plan,
        "active": True,
    }
    try:
        inserted = await sb_insert("shops", record)
        shop_id = str(inserted.get("shop_id", uuid.uuid4()))
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd zapisu do bazy")
    return {
        "success": True,
        "shop_id": shop_id,
        "shop_token": shop_token,
        "widget_snippet": f'<script src="https://jednymklik-production.up.railway.app/widget.js" data-shop-id="{shop_id}" data-shop-token="{shop_token}"></script>',
    }

@app.get("/api/v1/withdrawal/{withdrawal_id}/status")
async def get_withdrawal_status(withdrawal_id: str):
    try:
        w = await sb_select_one("withdrawals", {"id": withdrawal_id})
    except Exception as e:
        log.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Błąd odczytu z bazy")
    if not w:
        raise HTTPException(status_code=404, detail="Nie znaleziono odstąpienia")
    return {
        "withdrawal_id": withdrawal_id,
        "status": w["status"],
        "order_id": w["order_id"],
        "timestamp_initiated": w["timestamp_initiated"],
        "timestamp_confirmed": w.get("timestamp_confirmed"),
        "deadline_return": w["deadline_return"],
        "email_sent": w["email_sent"],
    }
