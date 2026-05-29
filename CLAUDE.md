# CLAUDE.md — ŁatwyZwrot.pl

## Kontekst projektu
SaaS widget JavaScript dla sklepów e-commerce. Wdraża formularz odstąpienia od umowy zgodny z Art. 11a Dyrektywy UE 2023/2673. Deadline zgodności: 19 czerwca 2026.

**Właściciel:** Dariusz Śliwa  
**Kontakt:** kontakt@latwyzwrot.pl  
**Status:** MVP live, pierwsze sprzedaże w toku

---

## Stack techniczny

| Warstwa | Technologia |
|---|---|
| Frontend (landing) | HTML + CSS + JS (vanilla, zero frameworków) |
| Backend API | Python FastAPI |
| Baza danych | Supabase (PostgreSQL) |
| Hosting frontend | Netlify (astounding-biscuit-2f6faa) |
| Hosting backend | Railway |
| Płatności | Stripe (webhooks) |
| Email | Resend API |
| Widget | JavaScript snippet osadzany na sklepach klientów |

---

## Repozytoria

| Repo | URL |
|---|---|
| Frontend | https://github.com/dfu925-ux/latwyzwrot |
| Backend | https://github.com/dfu925-ux/jednymklik |

---

## Struktura projektu

### Frontend (latwyzwrot repo)
```
index.html          — landing page (główna strona sprzedażowa)
panel.html          — panel klienta (dashboard)
regulamin.html      — regulamin usługi
dpa.html            — Data Processing Agreement
polityka-prywatnosci.html
subprocessors.html
rejestracja.html    — formularz waitlist / rejestracja
robots.txt
sitemap.xml
favicon.svg
og-image.png        — Open Graph image
_redirects          — Netlify pretty URLs i przekierowania 301
```

### Backend (jednymklik repo)
```
backend/
  main.py           — FastAPI app, wszystkie endpointy
  widget.js         — JavaScript widget osadzany u klientów
  demo.html         — demo widgetu
```

---

## Endpointy API

**Base URL:** `https://jednymklik-production.up.railway.app`

| Metoda | Endpoint | Opis |
|---|---|---|
| GET | `/` | Health check podstawowy |
| GET | `/health` | Health check z timestampem |
| GET | `/widget.js` | Serwuje widget JavaScript |
| GET | `/demo.html` | Demo widgetu |
| POST | `/api/v1/withdrawal/initiate` | Inicjuje odstąpienie (wymaga X-Shop-Token header) |
| POST | `/api/v1/withdrawal/confirm` | Potwierdza odstąpienie (krok 2) |
| GET | `/api/v1/withdrawals/{shop_id}` | Lista odstąpień sklepu |
| GET | `/api/v1/withdrawal/{withdrawal_id}/status` | Status odstąpienia |
| POST | `/api/v1/shops/register` | Rejestracja sklepu |
| POST | `/api/v1/webhook/stripe` | Webhook Stripe (onboarding + dezaktywacja) |
| POST | `/api/v1/waitlist` | Zapis na listę oczekujących |

### Autoryzacja widgetu
- Header: `X-Shop-Token: {shop_token}`
- Token generowany przy rejestracji sklepu (UUID)
- Przechowywany w tabeli `shops` w Supabase

---

## Baza danych Supabase

**Project ID:** `jwzmxrvqfdftbbntqquc`

### Tabele

**shops**
```
shop_id           UUID PK
shop_name         TEXT
shop_url          TEXT
owner_email       TEXT
owner_name        TEXT
plan              TEXT (starter/pro/business)
active            BOOLEAN
shop_token        TEXT UNIQUE
stripe_customer_id TEXT
created_at        TIMESTAMPTZ
```

**withdrawals**
```
id                UUID PK
shop_id           TEXT (FK → shops.shop_id)
order_id          TEXT
customer_email    TEXT
customer_name     TEXT
order_date        TEXT
order_value       FLOAT
status            TEXT (initiated/confirmed)
timestamp_initiated TIMESTAMPTZ
timestamp_confirmed TIMESTAMPTZ
deadline_return   TEXT (14 dni od odstąpienia)
reason            TEXT
email_sent        BOOLEAN
ip_address        TEXT
```

**waitlist**
```
id                UUID PK
email             TEXT UNIQUE
source            TEXT DEFAULT 'rejestracja.html'
ip                TEXT
created_at        TIMESTAMPTZ
notified_at       TIMESTAMPTZ
```

---

## Zmienne środowiskowe (Railway)

```
SUPABASE_URL=https://jwzmxrvqfdftbbntqquc.supabase.co
SUPABASE_KEY={service_role_key}
RESEND_API_KEY={klucz_resend}
FROM_EMAIL=kontakt@latwyzwrot.pl
STRIPE_WEBHOOK_SECRET={webhook_secret}
STRIPE_SECRET_KEY={stripe_secret}
```

---

## Stripe — linki płatności (live)

| Plan | Cena | Link |
|---|---|---|
| Starter | 19 zł/mc | https://buy.stripe.com/cNi7sL2SQ2ejgE00y0bV609 |
| Pro | 49 zł/mc | https://buy.stripe.com/6oU5kD1OMf1587u0y0bV60a |
| Business | 99 zł/mc | https://buy.stripe.com/eVqfZh8daf151J6fsUbV60b |
| Kupon | LAUNCH9 | 10 zł zniżki, 100 użyć |

---

## Flow onboardingu (Stripe Webhook)

1. Klient płaci przez Stripe → event `customer.subscription.created`
2. Backend pobiera email klienta z Stripe API
3. Tworzy rekord w tabeli `shops` (UUID shop_id + shop_token)
4. Wysyła email przez Resend z snippetem JS do wklejenia
5. Klient wkleja snippet w sklep → widget działa

---

## Netlify

**Site:** astounding-biscuit-2f6faa  
**Domena:** latwyzwrot.pl  
**Auto-deploy:** z GitHub (main branch)  
**Status:** ⚠️ Paused do 1 czerwca 2026 (exceeded credit limits — free plan)

Pretty URLs w `_redirects`:
```
/regulamin → /regulamin.html
/dpa → /dpa.html
/polityka-prywatnosci → /polityka-prywatnosci.html
/subprocessors → /subprocessors.html
/rejestracja → /rejestracja.html
/panel → /panel.html
```

---

## CORS

Widget osadzany na zewnętrznych sklepach → `allow_origins=["*"]`  
Autoryzacja przez `X-Shop-Token` header (nie ciasteczka)  
TODO: Osobny CORS dla endpointów /admin/* ograniczony do latwyzwrot.pl

---

## Co działa

- ✅ Landing page z płatnościami Stripe (7-dniowy trial)
- ✅ Webhook Stripe → automatyczny onboarding → email z tokenem
- ✅ Widget JS z dwuetapowym flow i konfetti
- ✅ Panel klienta z listą odstąpień, eksport CSV
- ✅ Waitlist z Supabase + powiadomienia Resend
- ✅ Audit trail z timestampem
- ✅ Email potwierdzający dla konsumenta

## Co nie działa / TODO

- ⚠️ Netlify paused do 1 czerwca 2026
- ⚠️ CORS dla /admin/* do zrobienia
- ⚠️ shop_name w onboardingu to email klienta (powinno być pobrane ze Stripe)
- 🔲 Strona na certyfikat zgodności (PDF)
- 🔲 Integracja z Allegro/WooCommerce plugin

---

## Zasady kodowania

- Zero frameworków frontend (vanilla HTML/CSS/JS)
- Python FastAPI backend — async wszędzie
- Supabase przez REST API (httpx), nie przez SDK
- Błędy logowane przez `logging` (nie print)
- Każdy endpoint zwraca `{"success": True/False, ...}`
- Timeout httpx: 8 sekund
- UUID dla wszystkich ID
- Daty w UTC (datetime.utcnow())

---

## Kontekst biznesowy

- **Cel:** 100 000 PLN/mc net profit z portfolio SaaS
- **Model:** subskrypcja miesięczna 19/49/99 PLN + Lifetime Deal 199 PLN (pierwsze 100 klientów)
- **Rynek:** polskie sklepy e-commerce (WooCommerce, Shoper, Shoplo)
- **Deadline rynkowy:** 19 czerwca 2026 (Art. 11a wchodzi w życie)
- **Dystrybucja:** LinkedIn outreach, Facebook grupy e-commerce, cold mail
