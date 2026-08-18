"""
Cazador de Ofertas Automatizado — Bot principal (Módulo A).

Se ejecuta vía GitHub Actions cada 60 minutos (ver .github/workflows/scraper.yml).

Flujo:
1. Consulta cada proveedor de afiliados configurado (Amazon, Mercado Libre).
2. Filtra: descarta productos con descuento < 40%.
3. Inyecta el link de afiliado en cada producto.
4. Upsert en Supabase (actualiza si existe, inserta si es nuevo).
5. Marca como inactivas las ofertas con más de 48h sin actualizarse.
"""

import os
import sys
import logging
from datetime import datetime, timezone

from supabase import create_client, Client

from affiliates.amazon import fetch_amazon_deals, build_affiliate_url as amazon_affiliate_url
from affiliates.mercadolibre import fetch_mercadolibre_deals, build_affiliate_url as ml_affiliate_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cazador.bot")

MIN_DISCOUNT_PERCENT = float(os.environ.get("MIN_DISCOUNT_PERCENT", "40"))
STALE_HOURS = 48

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")  # service_role key, NUNCA la anon key aquí


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en el entorno.")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def compute_discount_percent(original_price: float, sale_price: float) -> float:
    if not original_price or original_price <= 0:
        return 0.0
    return round((1 - (sale_price / original_price)) * 100, 2)


def collect_raw_deals():
    """Junta las ofertas crudas de todos los proveedores disponibles."""
    raw = []

    try:
        raw.extend(fetch_amazon_deals())
    except Exception as exc:
        logger.error("Fallo al obtener ofertas de Amazon: %s", exc)

    try:
        raw.extend(fetch_mercadolibre_deals())
    except Exception as exc:
        logger.error("Fallo al obtener ofertas de Mercado Libre: %s", exc)

    logger.info("Ofertas crudas obtenidas: %d", len(raw))
    return raw


def filter_and_build(raw_deals):
    """Aplica el filtro de descuento mínimo y arma la URL de afiliado final."""
    processed = []

    for deal in raw_deals:
        discount = compute_discount_percent(deal["original_price"], deal["sale_price"])

        if discount < MIN_DISCOUNT_PERCENT:
            continue

        if deal["source"] == "amazon":
            affiliate_url = amazon_affiliate_url(deal["product_url"])
        elif deal["source"] == "mercadolibre":
            affiliate_url = ml_affiliate_url(deal["product_url"])
        else:
            affiliate_url = deal["product_url"]

        processed.append({
            "external_id": deal["external_id"],
            "source": deal["source"],
            "title": deal["title"],
            "original_price": deal["original_price"],
            "sale_price": deal["sale_price"],
            "discount_percent": discount,
            "affiliate_url": affiliate_url,
            "image_url": deal.get("image_url"),
            "is_active": True,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        })

    logger.info(
        "Ofertas que pasan el filtro de >= %.0f%% de descuento: %d",
        MIN_DISCOUNT_PERCENT, len(processed),
    )
    return processed


def sync_with_supabase(supabase: Client, offers):
    """
    Upsert por (source, external_id) — ver el UNIQUE constraint en schema.sql.
    Supabase/PostgREST soporta upsert nativo con on_conflict.
    """
    if not offers:
        logger.info("No hay ofertas nuevas que cumplan el filtro en esta corrida.")
        return

    try:
        response = (
            supabase.table("offers")
            .upsert(offers, on_conflict="source,external_id")
            .execute()
        )
        logger.info("Upsert completado: %d registros procesados.", len(response.data or []))
    except Exception as exc:
        logger.error("Error al hacer upsert en Supabase: %s", exc)


def deactivate_stale_offers(supabase: Client):
    """Marca como inactivas las ofertas con más de 48h sin refrescarse."""
    try:
        supabase.rpc("deactivate_stale_offers").execute()
        logger.info("Limpieza de ofertas con más de %dh de antigüedad ejecutada.", STALE_HOURS)
    except Exception as exc:
        logger.error("Error ejecutando la limpieza de ofertas viejas: %s", exc)


def main():
    logger.info("=== Iniciando corrida del Cazador de Ofertas ===")

    supabase = get_supabase_client()

    raw_deals = collect_raw_deals()
    offers = filter_and_build(raw_deals)
    sync_with_supabase(supabase, offers)
    deactivate_stale_offers(supabase)

    logger.info("=== Corrida finalizada ===")


if __name__ == "__main__":
    main()
