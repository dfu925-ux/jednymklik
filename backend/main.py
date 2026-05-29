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
import logging
import asyncio



logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jednymklik")


# ─────────────────────────────────────────────
# RATE-LIMIT (in-memory, sliding window po IP)
# UWAGA: trzymane w pamięci procesu. Wystarczy na 1 instancję (Railway MVP).
# Jeśli wrzucisz >1 replikę, limit liczy się per-instancja — wtedy
# przenieś licznik do Redis/Supabase. Na start to wystarczy.
# ─────────────────────────────────────────────
from collections import defaultdict, deque
import threading

_rate_lock = threading.Lock()
_rate_hits: dict = defaultdict(deque)

def rate_limit(key: str, max_calls: int, window_sec: int) -> bool:
    """Zwraca True jeśli request mieści się w limicie, False jeśli przekroczony."""
    now = datetime.utcnow().timestamp()
    with _rate_lock:
        q = _rate_hits[key]
        while q and q[0] <= now - window_sec:
            q.popleft()
        if len(q) >= max_calls:
            return False
        q.append(now)
        return True

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
    async with httpx.AsyncClient(timeout=8.0) as client:
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
    async with httpx.AsyncClient(timeout=8.0) as client:
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
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.patch(url, json=data, params=params, headers=headers)
        r.raise_for_status()
        return r.json()

# ─────────────────────────────────────────────
# RESEND EMAIL
# ─────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "kontakt@latwyzwrot.pl")

async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    if not RESEND_API_KEY:
        log.warning("Brak RESEND_API_KEY")
        return False
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": "ŁatwyZwrot <kontakt@latwyzwrot.pl>", "to": [to_email], "subject": subject, "html": body_html}
            )
            r.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Resend error: {e}")
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

class WaitlistEntry(BaseModel):
    email: EmailStr

# ─────────────────────────────────────────────
# STRIPE
# ─────────────────────────────────────────────
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

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
    if not shop.get("active", True):
        raise HTTPException(status_code=403, detail="Konto nieaktywne")

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
    if withdrawal.get("customer_email") and RESEND_API_KEY:
        subject = f"Potwierdzenie odstąpienia od umowy — zamówienie {withdrawal['order_id']}"
        body = f"""
        <h2>Potwierdzenie odstąpienia od umowy</h2>
        <p>Twoje odstąpienie zostało zarejestrowane.</p>
        <p><strong>Nr zamówienia:</strong> {withdrawal['order_id']}</p>
        <p><strong>Nr referencyjny:</strong> {data.withdrawal_id}</p>
        <p><strong>Termin zwrotu towaru:</strong> {withdrawal['deadline_return']}</p>
        <p><strong>Powód:</strong> {data.reason or 'Nie podano'}</p>
        <hr>
        <p style="font-size:12px;color:#666">ŁatwyZwrot.pl — zgodność z art. 11a Dyrektywy UE 2023/2673</p>
        """
        asyncio.create_task(send_email(withdrawal["customer_email"], subject, body))
        email_sent = True

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
        "shop_token": shop_token,
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
        "widget_snippet": f'<script src="https://api.latwyzwrot.pl/widget.js" data-shop-id="{shop_id}" data-shop-token="{shop_token}"></script>',
    }

@app.post("/api/v1/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    # Weryfikacja podpisu Stripe
    if STRIPE_WEBHOOK_SECRET:
        import hmac, hashlib, time
        try:
            parts = {k: v for k, v in (p.split("=", 1) for p in sig.split(","))}
            ts = parts.get("t", "")
            v1 = parts.get("v1", "")
            signed = f"{ts}.{payload.decode()}"
            expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), signed.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, v1):
                raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            log.error(f"Webhook signature error: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        event = (await request.json()) if not payload else __import__("json").loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type", "")
    log.info(f"Stripe webhook: {event_type}")

    if event_type == "customer.subscription.created":
        sub = event.get("data", {}).get("object", {})
        customer_id = sub.get("customer")
        plan_name = "starter"

        # Pobierz email klienta z Stripe
        customer_email = ""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                stripe_secret = os.getenv("STRIPE_SECRET_KEY", "")
                r = await client.get(
                    f"https://api.stripe.com/v1/customers/{customer_id}",
                    auth=(stripe_secret, "")
                )
                customer_data = r.json()
                customer_email = customer_data.get("email", "")
        except Exception as e:
            log.error(f"Stripe customer fetch error: {e}")

        if not customer_email:
            log.error("Brak emaila klienta")
            return {"received": True}

        # Utwórz sklep w Supabase
        shop_token = str(uuid.uuid4())
        shop_id = str(uuid.uuid4())
        try:
            await sb_insert("shops", {
                "shop_id": shop_id,
                "shop_name": customer_email,
                "shop_url": "",
                "owner_email": customer_email,
                "plan": plan_name,
                "active": True,
                "shop_token": shop_token,
                "stripe_customer_id": customer_id,
            })
        except Exception as e:
            log.error(f"Supabase shop insert error: {e}")
            return {"received": True}

        # Wyślij email z tokenem
        snippet = f'<script src="https://jednymklik-production.up.railway.app/widget.js" data-shop-id="{shop_id}" data-shop-token="{shop_token}"></script>'
        body = f"""
        <h2>Witaj w ŁatwyZwrot.pl!</h2>
        <p>Twoje konto jest aktywne. Wklej poniższy kod przed tagiem &lt;/body&gt; w swoim sklepie:</p>
        <pre style="background:#f5f5f5;padding:16px;border-radius:8px;font-size:13px;overflow-x:auto">{snippet}</pre>
        <p>Token Twojego sklepu: <strong>{shop_token}</strong></p>
        <p>Jeśli masz pytania — napisz na kontakt@latwyzwrot.pl</p>
        <hr>
        <p style="font-size:12px;color:#666">ŁatwyZwrot.pl — zgodność z art. 11a Dyrektywy UE 2023/2673</p>
        """
        asyncio.create_task(send_email(
            customer_email,
            "Twój widget ŁatwyZwrot.pl jest gotowy — wklej 1 linijkę kodu",
            body
        ))
        log.info(f"Onboarding complete: {customer_email} | shop_id: {shop_id}")

    elif event_type == "customer.subscription.deleted":
        sub = event.get("data", {}).get("object", {})
        customer_id = sub.get("customer")

        # Dezaktywuj sklep w Supabase
        try:
            shop = await sb_select_one("shops", {"stripe_customer_id": customer_id})
            if shop:
                await sb_update("shops", {"stripe_customer_id": customer_id}, {"active": False})
                log.info(f"Shop deactivated: {customer_id}")

                # Powiadom klienta
                owner_email = shop.get("owner_email", "")
                if owner_email:
                    asyncio.create_task(send_email(
                        owner_email,
                        "Twoja subskrypcja ŁatwyZwrot.pl wygasła",
                        """
                        <h2>Subskrypcja wygasła</h2>
                        <p>Twój widget ŁatwyZwrot.pl został dezaktywowany.</p>
                        <p>Aby wznowić dostęp, odnów subskrypcję na <a href="https://latwyzwrot.pl/#cennik">latwyzwrot.pl</a>.</p>
                        <hr>
                        <p style="font-size:12px;color:#666">ŁatwyZwrot.pl — zgodność z art. 11a Dyrektywy UE 2023/2673</p>
                        """
                    ))
        except Exception as e:
            log.error(f"Subscription deleted error: {e}")

    return {"received": True}


@app.post("/api/v1/waitlist")
async def join_waitlist(data: WaitlistEntry):
    try:
        await sb_insert("waitlist", {"email": data.email})
    except Exception as e:
        err = str(e)
        if "duplicate" in err.lower() or "unique" in err.lower():
            return {"success": True, "message": "Już jesteś na liście."}
        log.error(f"Waitlist error: {e}")
        raise HTTPException(status_code=500, detail="Błąd zapisu")

    # Powiadomienie dla właściciela
    asyncio.create_task(send_email(
        "kontakt@latwyzwrot.pl",
        f"[ŁatwyZwrot] Nowy zapis: {data.email}",
        f"<p>Nowy email na liście oczekujących: <strong>{data.email}</strong></p>"
    ))

    log.info(f"Waitlist: {data.email}")
    return {"success": True, "message": "Zapisano! Powiadomimy Cię przy starcie."}


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

# ─────────────────────────────────────────────
# WAITLIST — zapis na listę oczekujących
# Endpoint dla /rejestracja.html (przed publicznym launchem)
# Tabela `waitlist`: (id uuid pk, email text unique, created_at timestamptz, source text, ip text)
# ─────────────────────────────────────────────
class WaitlistEntry(BaseModel):
    email: EmailStr

@app.post("/api/v1/waitlist")
async def add_to_waitlist(data: WaitlistEntry, request: Request):
    email = data.email.lower().strip()
    client_ip = request.client.host if request.client else None

    try:
        existing = await sb_select_one("waitlist", {"email": email})
    except Exception as e:
        log.error(f"Waitlist select error: {e}")
        # Nie blokujemy — jeśli nie wiemy czy istnieje, pozwalamy spróbować zapisać.
        existing = None

    if existing:
        # E-mail już zapisany — zwracamy success (klient widzi to samo, nie ujawniamy listy)
        return {"success": True, "message": "Już jesteś na liście."}

    record = {
        "id": str(uuid.uuid4()),
        "email": email,
        "source": "rejestracja.html",
        "ip": client_ip,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        await sb_insert("waitlist", record)
    except Exception as e:
        log.error(f"Waitlist insert error: {e}")
        raise HTTPException(status_code=500, detail="Nie udało się zapisać. Spróbuj ponownie.")

    return {"success": True, "message": "Zapisano. Powiadomimy Cię przy starcie."}

# ─────────────────────────────────────────────
# LEADS — zapis leadów z widgetu chatbota
# Tabela `leads`: (id uuid pk, name text, email text, phone text,
#   message text, source text, shop_id text, ip text, created_at timestamptz)
# ─────────────────────────────────────────────
class Lead(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = "chatbot"
    shop_id: Optional[str] = None

@app.post("/api/v1/leads")
async def create_lead(data: Lead, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    # Rate-limit: max 5 leadów / 10 min / IP
    if not rate_limit(f"leads:{client_ip}", max_calls=5, window_sec=600):
        log.warning(f"Rate limit hit for leads from IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Zbyt wiele zgłoszeń. Spróbuj później.")

    record = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "email": data.email.lower().strip(),
        "phone": data.phone,
        "message": data.message,
        "source": data.source,
        "shop_id": data.shop_id,
        "ip": client_ip,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        inserted = await sb_insert("leads", record)
    except Exception as e:
        log.error(f"Lead insert error: {e}")
        raise HTTPException(status_code=500, detail="Nie udało się zapisać leada.")

    log.info(f"Lead saved: {record['email']} | source: {data.source}")
    return {"success": True, "lead_id": inserted.get("id", record["id"]), "message": "Lead zapisany."}
