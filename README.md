# JednymKlik.pl — MVP Setup

## Struktura projektu

```
jednymklik/
├── backend/
│   ├── main.py          ← FastAPI backend (API + audit trail + email)
│   ├── requirements.txt ← Zależności Python
│   └── railway.toml     ← Konfiguracja Railway
└── widget/
    ├── widget.js        ← Widget JS (embed do sklepu)
    └── demo.html        ← Strona testowa
```

---

## Uruchomienie lokalne (test)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# API dostępne na: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Widget (demo)

```bash
cd widget
# Otwórz demo.html w przeglądarce
# Zmień API_BASE w widget.js na http://localhost:8000
```

---

## Deploy na Railway

1. Wrzuć folder `backend/` na GitHub
2. Zaloguj się na Railway → New Project → Deploy from GitHub
3. Dodaj zmienne środowiskowe:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=twoj@gmail.com
SMTP_PASS=haslo_aplikacji
FROM_EMAIL=noreply@jednymklik.pl
```

4. Railway automatycznie wykryje `railway.toml` i uruchomi serwer
5. Skopiuj URL Railway (np. `https://jednymklik-api.railway.app`)
6. Zmień `API_BASE` w `widget.js` na ten URL

---

## Jak używać widgetu w sklepie klienta

Wklej ten kod do strony z detalami zamówienia:

```html
<div id="jednymklik-widget"></div>
<script src="https://api.jednymklik.pl/widget.js"
        data-shop-id="TWOJ_SHOP_ID"
        data-shop-token="TWOJ_TOKEN"
        data-order-id="{{ order.id }}"
        data-customer-email="{{ customer.email }}"
        data-customer-name="{{ customer.name }}"
        data-order-date="{{ order.date }}"
        data-order-value="{{ order.total }}"
        data-container-id="jednymklik-widget"
        data-lang="pl">
</script>
```

---

## API Endpoints

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/health` | Healthcheck |
| POST | `/api/v1/shops/register` | Rejestracja sklepu |
| POST | `/api/v1/withdrawal/initiate` | Krok 1 — inicjacja |
| POST | `/api/v1/withdrawal/confirm` | Krok 2 — potwierdzenie |
| GET | `/api/v1/withdrawals/{shop_id}` | Lista odstąpień (dashboard) |
| GET | `/api/v1/withdrawal/{id}/status` | Status odstąpienia |

Pełna dokumentacja: `http://localhost:8000/docs`

---

## TODO (następne kroki)

- [ ] Podłączyć Supabase (zastąpić in-memory storage)
- [ ] Plugin WooCommerce (PHP)
- [ ] Dashboard dla właściciela sklepu (HTML)
- [ ] Landing page jednymklik.pl
- [ ] Stripe dla płatności subskrypcji
- [ ] Plugin PrestaShop

---

## Zgodność prawna

Widget implementuje wymagania art. 11a Dyrektywy 2011/83/UE
wprowadzonego Dyrektywą (UE) 2023/2673:

✅ Łatwo dostępny przycisk
✅ Dwuetapowe potwierdzenie (krok 1 + krok 2)
✅ Automatyczne potwierdzenie email
✅ Audit trail (timestamp, IP, user-agent)
✅ Dostępny przez 14 dni od zamówienia
✅ Wyraźne oznaczenie "Odstąp od umowy"
