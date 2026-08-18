# Cazador de Ofertas Automatizado

Sistema de agregación de ofertas de afiliados con costo $0 USD:
GitHub Pages (frontend) + GitHub Actions (bot) + Supabase (base de datos).

## Estructura del proyecto

```
cazador-ofertas/
├── schema.sql                          # Ejecutar en Supabase SQL Editor
├── backend/
│   ├── scraper.py                      # Bot principal
│   ├── requirements.txt
│   └── affiliates/
│       ├── amazon.py                   # Proveedor Amazon PA-API
│       └── mercadolibre.py             # Proveedor Mercado Libre
├── .github/workflows/scraper.yml       # Cron job (cada 60 min)
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Puesta en marcha

### 1. Supabase
1. Crea un proyecto gratuito en https://supabase.com.
2. Ve a **SQL Editor** y ejecuta el contenido de `schema.sql`.
3. En **Project Settings > API** copia:
   - `Project URL` → lo usarás como `SUPABASE_URL`
   - `anon public` key → la usarás en `frontend/script.js`
   - `service_role` key → la usarás como `SUPABASE_SERVICE_KEY` (¡nunca la publiques en el frontend!)

### 2. Repositorio en GitHub
1. Sube esta carpeta a un repo nuevo.
2. Ve a **Settings > Secrets and variables > Actions** y crea estos secrets:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `AMAZON_ACCESS_KEY`, `AMAZON_SECRET_KEY`, `AMAZON_PARTNER_TAG`, `AMAZON_COUNTRY` (opcionales mientras no tengas aprobación de Amazon)
   - `ML_SITE_ID` (ej. `MLM` para México), `ML_AFFILIATE_ID`
3. Ve a **Actions** y habilita los workflows si te lo pide. Puedes correr el bot manualmente la primera vez con "Run workflow".

### 3. GitHub Pages
1. Ve a **Settings > Pages**.
2. En "Build and deployment", elige **Deploy from a branch**, rama `main`, carpeta `/frontend`.
   - Alternativa: mueve el contenido de `frontend/` a la raíz del repo si prefieres no usar subcarpeta.
3. Antes de publicar, edita `frontend/script.js` y reemplaza `SUPABASE_URL` y `SUPABASE_ANON_KEY` con tus valores reales.

## Notas importantes sobre las APIs de afiliados

- **Amazon PA-API**: necesitas que tu cuenta de Afiliados tenga al menos 3 ventas calificadas
  en tu periodo de prueba para que la API te dé acceso. Sin eso, las llamadas fallan aunque
  el código esté bien. Mientras tanto, `amazon.py` usa datos de ejemplo (MOCK) para que puedas
  probar el resto del sistema.
- **Mercado Libre**: la API pública de búsqueda no siempre expone `original_price` (solo cuando
  el producto tiene un descuento activo visible en catálogo). Si tienes acceso al feed del
  Programa de Afiliados de Mercado Libre (CSV/JSON de campañas), es más confiable — solo necesitas
  reemplazar `fetch_mercadolibre_deals()` en `mercadolibre.py` para leer ese feed en vez del buscador.
- El disclaimer de afiliación del footer usa el texto estándar exigido por el Programa de
  Afiliados de Amazon; revísalo también contra los términos vigentes de cada programa que uses.

## Ajustar el umbral de descuento

El mínimo de 40% está centralizado en `MIN_DISCOUNT_PERCENT`
(variable de entorno en el workflow, con default en `scraper.py`). Para cambiarlo,
edita el valor `"40"` en `.github/workflows/scraper.yml`.

## Probar el bot en local

```bash
cd backend
pip install -r requirements.txt
export SUPABASE_URL="https://tu-proyecto.supabase.co"
export SUPABASE_SERVICE_KEY="tu-service-role-key"
python scraper.py
```

Sin credenciales de Amazon/Mercado Libre configuradas, correrá igual usando
datos MOCK, así puedes verificar que el filtro, el upsert y la limpieza
funcionan antes de conectar las APIs reales.
