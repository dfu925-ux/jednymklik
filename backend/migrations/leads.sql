-- ─────────────────────────────────────────────
-- JEDNYMKLIK.PL — tabela `leads`
-- Leady z widgetu / chatbota. Uruchom w Supabase SQL Editor.
-- ─────────────────────────────────────────────

create extension if not exists "pgcrypto";

create table if not exists public.leads (
    id          uuid primary key default gen_random_uuid(),
    name        text,
    email       text not null,
    phone       text,
    message     text,
    source      text default 'chatbot',
    shop_id     text,
    ip          text,
    created_at  timestamptz not null default now()
);

-- Szybkie wyszukiwanie i deduplikacja
create index if not exists idx_leads_email      on public.leads (email);
create index if not exists idx_leads_shop_id    on public.leads (shop_id);
create index if not exists idx_leads_created_at on public.leads (created_at desc);

-- ─────────────────────────────────────────────
-- RLS — blokuje publiczny dostęp przez anon key.
-- Backend używa SERVICE_ROLE key, który omija RLS, więc insert z API działa.
-- Bez tej polityki ktokolwiek z anon key mógłby czytać Twoje leady.
-- ─────────────────────────────────────────────
alter table public.leads enable row level security;

-- Brak polityk = brak dostępu dla anon/authenticated. Service role i tak omija RLS.
-- (Jeśli świadomie chcesz odczyt z panelu na anon key — dodaj policy ręcznie.)
