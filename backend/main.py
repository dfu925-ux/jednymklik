"""
╔══════════════════════════════════════════════════════════════╗
║         JEDNYMKLIK.PL — Backend API                          ║
║         Withdrawal Button SaaS — art. 11a Dyrektywy UE       ║
║                                                              ║
║  Stack: FastAPI + Supabase + SendGrid/SMTP + Railway         ║
║  Uruchomienie: uvicorn main:app --reload                     ║
╚══════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import os
import uuid
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jednymklik")

app = FastAPI(
    title="JednymKlik.pl API",
    description="Withdrawal Button SaaS — art. 11a Dyrektywy UE 2023/2673",
    version="1.0.0"
)

# CORS — pozwala na wywołania z dowolnej domeny sklepu
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# SERWOWANIE PLIKÓW STATYCZNYCH
# widget.js i demo.html są w katalogu ./widget/
# Dostęp: http://localhost:8000/widget.js
#         http://localhost:8000/demo.html
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# KONFIGURACJA — zmienne środowiskowe
# ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@jednymklik.pl")

# ─────────────────────────────────────────────
# MODELE DANYCH
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
# IN-MEMORY STORAGE (testy lokalne)
# ─────────────────────────────────────────────
withdrawals_db = {}
shops_db = {}

# ─────────────────────────────────────────────
# FUNKCJE POMOCNICZE
# ─────────────────────────────────────────────

def generate_id() -> str:
    return str(uuid.uuid4())

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
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; }}
            .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; }}
            .info-box {{ background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .important {{ color: #dc2626; font-weight: bold; }}
            .footer {{ background: #f9fafb; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
            .id {{ font-family: monospace; background: #e5e7eb; padding: 4px 8px; border-radius: 4px; }}
        </style>
    </head>
    <body>
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
            <ol>
                <li>Zwróć towar w ciągu <strong>14 dni</strong></li>
                <li>Termin zwrotu środków: <strong>do {deadline}</strong></li>
                <li>Zwrot tą samą metodą płatności</li>
            </ol>
            <p class="important">⚠️ Zachowaj ten email jako dowód odstąpienia.</p>
            <p>Podstawa prawna: art. 11a Dyrektywy 2011/83/UE (Dyrektywa 2023/2673).</p>
        </div>
        <div class="footer">
            Obsługiwane przez <a href="https://jednymklik.pl">JednymKlik.pl</a>
        </div>
    </body>
    </html>
    """

# ─────────────────────────────────────────────
# ENDPOINTY API
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "JednymKlik.pl API",
        "version": "1.0.0",
        "status": "online",
        "compliance": "art. 11a Dyrektywy UE 2023/2673",
        "docs": "/docs",
        "demo": "/demo.html",
        "widget": "/widget.js",
    }

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": get_timestamp()}


@app.post("/api/v1/withdrawal/initiate")
async def initiate_withdrawal(
    data: WithdrawalRequest,
    request: Request,
    x_shop_token: Optional[str] = Header(None)
):
    if not x_shop_token:
        raise HTTPException(status_code=401, detail="Brak tokenu sklepu")

    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")

    withdrawal_id = generate_id()
    timestamp = get_timestamp()
    deadline = (datetime.utcnow() + timedelta(days=14)).strftime("%d.%m.%Y")

    withdrawal_record = {
        "id": withdrawal_id,
        "shop_id": data.shop_id,
        "shop_token": x_shop_token,
        "order_id": data.order_id,
        "customer_email": data.customer_email,
        "customer_name": data.customer_name or "Klient",
        "order_date": data.order_date,
        "order_value": data.order_value,
        "products": data.products or [],
        "status": "initiated",
        "step": 1,
        "timestamp_initiated": timestamp,
        "timestamp_confirmed": None,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "deadline_return": deadline,
        "reason": None,
        "email_sent": False,
    }

    withdrawals_db[withdrawal_id] = withdrawal_record
    log.info(f"Withdrawal initiated: {withdrawal_id} | Order: {data.order_id}")

    return {
        "success": True,
        "withdrawal_id": withdrawal_id,
        "message": "Krok 1 z 2. Potwierdź odstąpienie.",
        "order_id": data.order_id,
        "deadline_return": deadline,
    }


@app.post("/api/v1/withdrawal/confirm")
async def confirm_withdrawal(
    data: WithdrawalConfirm,
    request: Request,
    x_shop_token: Optional[str] = Header(None)
):
    withdrawal = withdrawals_db.get(data.withdrawal_id)
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Nie znaleziono odstąpienia")
    if withdrawal["status"] == "confirmed":
        raise HTTPException(status_code=400, detail="Odstąpienie już potwierdzone")

    timestamp_confirmed = get_timestamp()
    shop_name = shops_db.get(withdrawal["shop_id"], {}).get("shop_name", "Sklep internetowy")

    withdrawal["status"] = "confirmed"
    withdrawal["step"] = 2
    withdrawal["timestamp_confirmed"] = timestamp_confirmed
    withdrawal["reason"] = data.reason
    withdrawal["confirm_ip"] = request.client.host

    email_html = generate_confirmation_email(
        withdrawal_id=data.withdrawal_id,
        order_id=withdrawal["order_id"],
        customer_name=withdrawal["customer_name"],
        shop_name=shop_name,
        timestamp=timestamp_confirmed,
        deadline=withdrawal["deadline_return"]
    )

    email_sent = send_email(
        to=withdrawal["customer_email"],
        subject=f"✅ Potwierdzenie odstąpienia — zamówienie {withdrawal['order_id']}",
        html=email_html
    )
    withdrawal["email_sent"] = email_sent

    log.info(f"Withdrawal confirmed: {data.withdrawal_id} | Email sent: {email_sent}")

    return {
        "success": True,
        "withdrawal_id": data.withdrawal_id,
        "status": "confirmed",
        "timestamp": timestamp_confirmed,
        "email_sent": email_sent,
        "message": "Odstąpienie zarejestrowane. Potwierdzenie wysłane na email.",
        "deadline_return": withdrawal["deadline_return"],
    }


@app.get("/api/v1/withdrawals/{shop_id}")
async def get_withdrawals(
    shop_id: str,
    x_shop_token: Optional[str] = Header(None),
    limit: int = 50,
    offset: int = 0
):
    if not x_shop_token:
        raise HTTPException(status_code=401, detail="Brak tokenu sklepu")

    shop_withdrawals = [w for w in withdrawals_db.values() if w["shop_id"] == shop_id]
    shop_withdrawals.sort(key=lambda x: x["timestamp_initiated"], reverse=True)

    return {
        "success": True,
        "total": len(shop_withdrawals),
        "withdrawals": shop_withdrawals[offset:offset + limit]
    }


@app.post("/api/v1/shops/register")
async def register_shop(data: ShopRegister):
    shop_id = generate_id()
    shop_token = generate_id()

    shop_record = {
        "shop_id": shop_id,
        "shop_token": shop_token,
        "shop_name": data.shop_name,
        "shop_url": data.shop_url,
        "owner_email": data.owner_email,
        "owner_name": data.owner_name,
        "plan": data.plan,
        "created_at": get_timestamp(),
        "active": True,
    }

    shops_db[shop_id] = shop_record
    log.info(f"Shop registered: {shop_id} | {data.shop_name}")

    return {
        "success": True,
        "shop_id": shop_id,
        "shop_token": shop_token,
        "message": "Sklep zarejestrowany.",
        "widget_snippet": f"""<!-- JednymKlik.pl Widget -->
<script src="http://localhost:8000/widget.js"
        data-shop-id="{shop_id}"
        data-shop-token="{shop_token}"
        data-order-id="NUMER_ZAMOWIENIA"
        data-customer-email="email@klienta.pl">
</script>"""
    }


@app.get("/api/v1/withdrawal/{withdrawal_id}/status")
async def get_withdrawal_status(withdrawal_id: str):
    withdrawal = withdrawals_db.get(withdrawal_id)
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Nie znaleziono odstąpienia")

    return {
        "withdrawal_id": withdrawal_id,
        "status": withdrawal["status"],
        "order_id": withdrawal["order_id"],
        "timestamp_initiated": withdrawal["timestamp_initiated"],
        "timestamp_confirmed": withdrawal["timestamp_confirmed"],
        "deadline_return": withdrawal["deadline_return"],
        "email_sent": withdrawal["email_sent"],
    }
