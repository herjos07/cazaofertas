"""
Proveedor de ofertas: Mercado Libre.

IMPORTANTE — léelo antes de conectar credenciales reales:
La API pública de Mercado Libre (api.mercadolibre.com) sirve principalmente
para catálogo/búsqueda de productos, no expone un feed nativo de "ofertas
del día" con % de descuento ya calculado en todos los países.

El Programa de Afiliados de Mercado Libre entrega, por separado, un feed
de campañas (CSV/JSON) con los productos en promoción vigentes y tu link
de afiliado ya armado. Si ya tienes acceso a ese feed, cambia
`fetch_mercadolibre_deals()` para leerlo directamente en vez de usar
el buscador público + mock.

Mientras tanto, este módulo:
1. Intenta usar la API pública de búsqueda para traer precios reales.
2. Si no puede armar un precio "original" confiable (ML no siempre lo da),
   cae en datos MOCK para no romper el pipeline.
"""

import os
import logging
import requests

logger = logging.getLogger("cazador.mercadolibre")

ML_SITE_ID = os.environ.get("ML_SITE_ID", "MLM")            # MLM = México
ML_AFFILIATE_ID = os.environ.get("ML_AFFILIATE_ID")          # tu ID de afiliado
SEARCH_TERMS = ["celulares", "electrodomesticos", "computadoras", "audio"]

SEARCH_URL = f"https://api.mercadolibre.com/sites/{ML_SITE_ID}/search"


def _mock_mercadolibre_deals():
    return [
        {
            "external_id": "MLMMOCK001",
            "source": "mercadolibre",
            "title": "Freidora de aire 5.5L (ejemplo)",
            "original_price": 2199.00,
            "sale_price": 1099.00,
            "image_url": "https://via.placeholder.com/300x300.png?text=Freidora",
            "product_url": "https://www.mercadolibre.com.mx/p/MLMMOCK001",
        },
        {
            "external_id": "MLMMOCK002",
            "source": "mercadolibre",
            "title": "Smartwatch deportivo (ejemplo)",
            "original_price": 1899.00,
            "sale_price": 999.00,
            "image_url": "https://via.placeholder.com/300x300.png?text=Smartwatch",
            "product_url": "https://www.mercadolibre.com.mx/p/MLMMOCK002",
        },
    ]


def fetch_mercadolibre_deals():
    """
    Devuelve una lista de dicts crudos:
    external_id, source, title, original_price, sale_price, image_url, product_url
    """
    raw_deals = []

    for term in SEARCH_TERMS:
        try:
            resp = requests.get(
                SEARCH_URL,
                params={"q": term, "limit": 20},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                sale_price = item.get("price")
                original_price = item.get("original_price")  # puede venir null si no hay descuento activo

                if sale_price is None or original_price is None:
                    continue  # sin descuento visible en el buscador público, se descarta aquí

                raw_deals.append({
                    "external_id": item["id"],
                    "source": "mercadolibre",
                    "title": item.get("title", ""),
                    "original_price": float(original_price),
                    "sale_price": float(sale_price),
                    "image_url": item.get("thumbnail"),
                    "product_url": item.get("permalink"),
                })
        except Exception as exc:
            logger.error("Error consultando Mercado Libre para '%s': %s", term, exc)

    if not raw_deals:
        logger.warning("No se obtuvieron ofertas reales de Mercado Libre. Usando datos MOCK.")
        return _mock_mercadolibre_deals()

    return raw_deals


def build_affiliate_url(product_url: str) -> str:
    """
    Inyecta el parámetro de afiliado de Mercado Libre.
    Ajusta 'matt_word' / el parámetro exacto según lo que te indique tu
    panel de Afiliados de Mercado Libre al generar tus links (varía por país/programa).
    """
    if ML_AFFILIATE_ID:
        separator = "&" if "?" in product_url else "?"
        return f"{product_url}{separator}matt_word={ML_AFFILIATE_ID}"
    return product_url
