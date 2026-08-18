// =========================================================
// Cazador de Ofertas — Frontend (Módulo B)
// Consulta Supabase directamente desde el navegador usando
// la ANON KEY (pública, de solo lectura gracias a RLS).
// =========================================================

// TODO: reemplaza estos dos valores con los de tu proyecto Supabase
// (Project Settings > API). La anon key es PÚBLICA por diseño,
// no es un secreto — la protección real la da la política RLS
// "Lectura pública de ofertas activas" definida en schema.sql.
const SUPABASE_URL = "https://nmpagbhpifbgyfebxaws.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tcGFnYmhwaWZiZ3lmZWJ4YXdzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcwODIzNTQsImV4cCI6MjEwMjY1ODM1NH0.pODGCIwxTQ0EjRD0_cJOOPR835oUoBSZWYqwQ5UGHdo";

const statusEl = document.getElementById("status");
const gridEl = document.getElementById("offers-grid");

const SOURCE_LABELS = {
  amazon: "Amazon",
  mercadolibre: "Mercado Libre",
};

function formatPrice(value) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 0,
  }).format(value);
}

function offerCardHTML(offer) {
  const sourceLabel = SOURCE_LABELS[offer.source] || offer.source;
  const image = offer.image_url || "https://via.placeholder.com/300x300.png?text=Sin+imagen";

  return `
    <article class="offer-card">
      <div class="offer-image-wrap">
        <span class="discount-badge">-${Math.round(offer.discount_percent)}%</span>
        <span class="source-badge">${sourceLabel}</span>
        <img src="${image}" alt="${offer.title}" loading="lazy" />
      </div>
      <div class="offer-body">
        <h2 class="offer-title">${offer.title}</h2>
        <div class="price-row">
          <span class="price-original">${formatPrice(offer.original_price)}</span>
          <span class="price-sale">${formatPrice(offer.sale_price)}</span>
        </div>
        <a class="cta-button" href="${offer.affiliate_url}" target="_blank" rel="nofollow sponsored noopener">
          Ver oferta
        </a>
      </div>
    </article>
  `;
}

async function loadOffers() {
  statusEl.textContent = "Cargando ofertas…";
  statusEl.classList.remove("error");

  try {
    const response = await fetch(
      `${SUPABASE_URL}/rest/v1/offers?is_active=eq.true&order=last_seen_at.desc&limit=100`,
      {
        headers: {
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Error ${response.status} al consultar Supabase`);
    }

    const offers = await response.json();

    if (!offers.length) {
      statusEl.textContent = "No hay ofertas activas en este momento. Vuelve más tarde.";
      gridEl.innerHTML = "";
      return;
    }

    statusEl.textContent = "";
    gridEl.innerHTML = offers.map(offerCardHTML).join("");
  } catch (err) {
    console.error(err);
    statusEl.textContent = "No se pudieron cargar las ofertas. Intenta de nuevo más tarde.";
    statusEl.classList.add("error");
  }
}

loadOffers();
