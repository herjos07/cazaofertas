"""
Proveedor de ofertas: Amazon.

IMPORTANTE — léelo antes de conectar credenciales reales:
Amazon PA-API 5.0 solo otorga acceso si tu cuenta de Afiliados ya generó
al menos 3 ventas calificadas en tu ventana de prueba (normalmente 180 días).
Hasta entonces, las llamadas a la API devuelven error de autorización.

Este módulo usa la librería no oficial pero muy usada `python-amazon-paapi`
(pip install python-amazon-paapi), que envuelve la firma SigV4 por ti.

Mientras no tengas las credenciales aprobadas, `fetch_amazon_deals()` cae
en datos de ejemplo (MOCK) para que puedas probar todo el pipeline
(filtro, Supabase, frontend) de principio a fin.
"""

import os
import logging

logger = logging.getLogger("cazador.amazon")

AMAZON_ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY")
AMAZON_PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG")   # tu ID de afiliado, ej. "tuweb-20"
AMAZON_COUNTRY = os.environ.get("AMAZON_COUNTRY", "MX")

# Palabras/categorías semilla que se buscan cuando no se tiene acceso a un
# feed directo de "ofertas del día" (Amazon no siempre expone ese feed vía PA-API).
SEARCH_SEEDS = ["electronica", "hogar", "videojuegos", "computo"]


def _mock_amazon_deals():
    """Datos de ejemplo para desarrollo/pruebas sin credenciales reales."""
    return [
        {
            "external_id": "B0MOCKAMZ01",
            "source": "amazon",
            "title": "Audífonos Bluetooth over-ear (ejemplo)",
            "original_price": 1499.00,
            "sale_price": 799.00,
            "image_url": "https://via.placeholder.com/300x300.png?text=Audifonos",
            "product_url": "https://www.amazon.com.mx/dp/B0MOCKAMZ01",
        },
        {
            "external_id": "B0MOCKAMZ02",
            "source": "amazon",
            "title": "Pantalla LED 43'' (ejemplo)",
            "original_price": 6999.00,
            "sale_price": 3999.00,
            "image_url": "https://via.placeholder.com/300x300.png?text=Pantalla",
            "product_url": "https://www.amazon.com.mx/dp/B0MOCKAMZ02",
        },
    ]


def fetch_amazon_deals():
    """
    Devuelve una lista de dicts crudos (sin filtrar por descuento todavía):
    external_id, source, title, original_price, sale_price, image_url, product_url

    Si no hay credenciales configuradas, usa datos MOCK para no romper el pipeline.
    """
    if not (AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY and AMAZON_PARTNER_TAG):
        logger.warning("Credenciales de Amazon PA-API no configuradas. Usando datos MOCK.")
        return _mock_amazon_deals()

    try:
        from amazon_paapi import AmazonApi
    except ImportError:
        logger.error("Falta instalar python-amazon-paapi (revisa requirements.txt). Usando MOCK.")
        return _mock_amazon_deals()

    amazon = AmazonApi(
        AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG, AMAZON_COUNTRY
    )

    raw_deals = []
    for seed in SEARCH_SEEDS:
        try:
            results = amazon.search_items(keywords=seed, item_count=10)
            for item in results.items or []:
                price_info = getattr(item, "offers", None)
                if not price_info or not price_info.listings:
                    continue
                listing = price_info.listings[0]
                sale_price = getattr(listing.price, "amount", None)
                original_price = getattr(
                    getattr(listing, "saving_basis", None), "amount", sale_price
                )
                if sale_price is None or original_price is None:
                    continue

                raw_deals.append({
                    "external_id": item.asin,
                    "source": "amazon",
                    "title": item.item_info.title.display_value,
                    "original_price": float(original_price),
                    "sale_price": float(sale_price),
                    "image_url": item.images.primary.large.url if item.images else None,
                    "product_url": item.detail_page_url,
                })
        except Exception as exc:
            logger.error("Error consultando Amazon PA-API para '%s': %s", seed, exc)

    return raw_deals or _mock_amazon_deals()


def build_affiliate_url(product_url: str) -> str:
    """
    Amazon: el partner tag ya va incrustado en detail_page_url cuando se usa
    AmazonApi con el partner_tag configurado. Esta función queda como punto
    único de inyección por si luego quieres agregar parámetros extra
    (ej. &linkCode=... &camp=... para OneLink).
    """
    if AMAZON_PARTNER_TAG and f"tag={AMAZON_PARTNER_TAG}" not in product_url:
        separator = "&" if "?" in product_url else "?"
        return f"{product_url}{separator}tag={AMAZON_PARTNER_TAG}"
    return product_url
