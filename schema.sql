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
    affiliate_url      text not null,               -- Amazon: link de afiliado ya armado. Mercado Libre: link plano hasta que lo reemplaces a mano.
    affiliate_ready     boolean not null default true, -- false = falta pegar el link real de afiliado (típico en Mercado Libre)
    image_url          text,
    is_active          boolean not null default true,
    first_seen_at      timestamptz not null default now(),
    last_seen_at       timestamptz not null default now(),

    -- Un mismo producto no se duplica por tienda
    constraint offers_source_external_id_unique unique (source, external_id)
);

-- Por si la tabla ya existía de una corrida anterior de este script,
-- esto asegura que la columna nueva se agregue de todos modos.
alter table public.offers add column if not exists affiliate_ready boolean not null default true;

-- Índices para las consultas más comunes del frontend y del bot
create index if not exists idx_offers_active_recent
    on public.offers (is_active, affiliate_ready, last_seen_at desc);

create index if not exists idx_offers_discount
    on public.offers (discount_percent desc);

-- =========================================================
-- Row Level Security (RLS)
-- El frontend usa la ANON KEY (pública), así que solo debe
-- poder LEER ofertas activas. El bot usa la SERVICE ROLE KEY
-- desde GitHub Actions, que se salta RLS por completo.
-- =========================================================
alter table public.offers enable row level security;

drop policy if exists "Lectura pública de ofertas activas" on public.offers;
drop policy if exists "Lectura pública de ofertas activas y con link listo" on public.offers;

create policy "Lectura pública de ofertas activas y con link listo"
    on public.offers
    for select
    using (is_active = true and affiliate_ready = true);

-- No se crean políticas de insert/update/delete para el rol anon:
-- por defecto quedan bloqueadas, y el bot escribe con la service key.

-- =========================================================
-- Panel de Administración: activar links de afiliado a mano
-- =========================================================
-- Tabla de configuración interna. Sin ninguna política RLS pública:
-- solo el service_role o funciones "security definer" pueden leerla.
create table if not exists public.app_settings (
    key    text primary key,
    value  text not null
);

alter table public.app_settings enable row level security;
-- (Intencionalmente sin policies: nadie con la anon key puede leer esta tabla directo)

-- CAMBIA 'pon-aqui-tu-clave-secreta' por una clave propia antes de usar el panel.
insert into public.app_settings (key, value)
values ('admin_secret', 'pon-aqui-tu-clave-secreta')
on conflict (key) do nothing;

-- Lista las ofertas pendientes de link real (solo si la clave es correcta)
create or replace function public.admin_list_pending_offers(p_secret text)
returns setof public.offers
language plpgsql
security definer
set search_path = public
as $$
declare
    v_secret text;
begin
    select value into v_secret from public.app_settings where key = 'admin_secret';
    if v_secret is null or p_secret is null or p_secret <> v_secret then
        raise exception 'No autorizado';
    end if;

    return query
        select * from public.offers
        where affiliate_ready = false
        order by last_seen_at desc;
end;
$$;

-- Guarda el link real de afiliado y activa la oferta (solo si la clave es correcta)
create or replace function public.admin_set_affiliate_link(p_secret text, p_offer_id bigint, p_affiliate_url text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_secret text;
begin
    select value into v_secret from public.app_settings where key = 'admin_secret';
    if v_secret is null or p_secret is null or p_secret <> v_secret then
        raise exception 'No autorizado';
    end if;

    update public.offers
    set affiliate_url = p_affiliate_url,
        affiliate_ready = true
    where id = p_offer_id;
end;
$$;

grant execute on function public.admin_list_pending_offers(text) to anon;
grant execute on function public.admin_set_affiliate_link(text, bigint, text) to anon;

-- =========================================================
-- Función de mantenimiento: marca como inactivas las ofertas
-- con más de 48 horas sin haber sido vistas de nuevo por el bot.
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
