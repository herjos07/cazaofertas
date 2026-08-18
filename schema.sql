-- =========================================================
-- Cazador de Ofertas Automatizado — Esquema de Base de Datos
-- Motor: Supabase (PostgreSQL)
-- Ejecutar esto en: Supabase Dashboard > SQL Editor > New query
-- =========================================================

create table if not exists public.offers (
    id                bigint generated always as identity primary key,
    external_id       text not null,               -- ID único del producto en la tienda (ASIN, ID de ML, etc.)
    source            text not null,                -- 'amazon' | 'mercadolibre' | etc.
    title             text not null,
    original_price    numeric(12,2) not null,
    sale_price        numeric(12,2) not null,
    discount_percent   numeric(5,2) not null,
    affiliate_url      text not null,
    image_url          text,
    is_active          boolean not null default true,
    first_seen_at      timestamptz not null default now(),
    last_seen_at       timestamptz not null default now(),

    -- Un mismo producto no se duplica por tienda
    constraint offers_source_external_id_unique unique (source, external_id)
);

-- Índices para las consultas más comunes del frontend y del bot
create index if not exists idx_offers_active_recent
    on public.offers (is_active, last_seen_at desc);

create index if not exists idx_offers_discount
    on public.offers (discount_percent desc);

-- =========================================================
-- Row Level Security (RLS)
-- El frontend usa la ANON KEY (pública), así que solo debe
-- poder LEER ofertas activas. El bot usa la SERVICE ROLE KEY
-- desde GitHub Actions, que se salta RLS por completo.
-- =========================================================
alter table public.offers enable row level security;

create policy "Lectura pública de ofertas activas"
    on public.offers
    for select
    using (is_active = true);

-- No se crean políticas de insert/update/delete para el rol anon:
-- por defecto quedan bloqueadas, y el bot escribe con la service key.

-- =========================================================
-- Función de mantenimiento: marca como inactivas las ofertas
-- con más de 48 horas sin haber sido vistas de nuevo por el bot.
-- El script de Python también puede hacer esto, pero tenerlo
-- como función SQL permite llamarla directo si algún día se
-- quiere programar dentro de Supabase (pg_cron) en vez de Actions.
-- =========================================================
create or replace function public.deactivate_stale_offers()
returns void
language sql
as $$
    update public.offers
    set is_active = false
    where is_active = true
      and last_seen_at < now() - interval '48 hours';
$$;
