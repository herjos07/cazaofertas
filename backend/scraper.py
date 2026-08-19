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
from affiliates.mercadolibre import fetch_mercadolibre_deals

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
    """
    Aplica el filtro de descuento mínimo y arma la URL de afiliado final.

    Amazon: su API arma el link de afiliado automáticamente (affiliate_ready=True).
    Mercado Libre: NO existe una forma automática de generar el link de afiliado
    (el programa actual exige generarlo a mano por producto). Por eso estas ofertas
    se guardan con affiliate_url = link plano del producto y affiliate_ready=False,
    hasta que tú lo reemplaces manualmente en Supabase con el link real generado
    en la Central de Afiliados. El frontend NUNCA muestra ofertas con
    affiliate_ready=False, así que no hay riesgo de publicar un link sin comisión.
    """
    processed = []

    for deal in raw_deals:
        discount = compute_discount_percent(deal["original_price"], deal["sale_price"])

        if discount < MIN_DISCOUNT_PERCENT:
            continue

        if deal["source"] == "amazon":
            affiliate_url = amazon_affiliate_url(deal["product_url"])
            affiliate_ready = True
        elif deal["source"] == "mercadolibre":
            affiliate_url = deal["product_url"]  # link plano, temporal
            affiliate_ready = False
        else:
            affiliate_url = deal["product_url"]
            affiliate_ready = False

        processed.append({
            "external_id": deal["external_id"],
            "source": deal["source"],
            "title": deal["title"],
            "original_price": deal["original_price"],
            "sale_price": deal["sale_price"],
            "discount_percent": discount,
            "affiliate_url": affiliate_url,
            "affiliate_ready": affiliate_ready,
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
    Para cada oferta:
    - Si el producto ya existe (mismo source + external_id): actualiza SOLO precio,
      descuento, título, imagen y last_seen_at. NO toca affiliate_url ni
      affiliate_ready, para no borrar un link que hayas pegado a mano.
    - Si es nuevo: lo inserta completo (incluyendo affiliate_url/affiliate_ready
      calculados en filter_and_build).
    """
    if not offers:
        logger.info("No hay ofertas nuevas que cumplan el filtro en esta corrida.")
        return

    inserted, updated = 0, 0

    for offer in offers:
        try:
            existing = (
                supabase.table("offers")
                .select("id")
                .eq("source", offer["source"])
                .eq("external_id", offer["external_id"])
                .execute()
            )

            if existing.data:
                row_id = existing.data[0]["id"]
                supabase.table("offers").update({
                    "title": offer["title"],
                    "original_price": offer["original_price"],
                    "sale_price": offer["sale_price"],
                    "discount_percent": offer["discount_percent"],
                    "image_url": offer["image_url"],
                    "is_active": offer["is_active"],
                    "last_seen_at": offer["last_seen_at"],
                }).eq("id", row_id).execute()
                updated += 1
            else:
                supabase.table("offers").insert(offer).execute()
                inserted += 1
        except Exception as exc:
            logger.error("Error al sincronizar '%s': %s", offer.get("title"), exc)

    logger.info("Sincronización completada: %d nuevas, %d actualizadas.", inserted, updated)


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
