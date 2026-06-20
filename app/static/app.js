/* Calibrate day-view interactions: search, barcode scan, recent/favorites,
   one-tap logging, add/delete entries, energy edit. */
const DATE = window.CALIBRATE_DATE;
const $ = (sel) => document.querySelector(sel);

let currentMeal = "snack";
let picked = null; // selected Product (per-100g)
let activeTab = "recent";

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

// ---- add-food sheet ----------------------------------------------------------
const sheet = $("#sheet");

function openSheet(meal) {
  currentMeal = meal;
  $("#sheet-meal").textContent = "Add to " + meal;
  $("#form-meal").textContent = meal;
  $("#results").innerHTML = "";
  $("#food-q").value = "";
  $("#entry-form").hidden = true;
  $("#save-fav").checked = false;
  showQuick(true);
  loadQuick(activeTab);
  sheet.hidden = false;
}
function closeSheet() {
  sheet.hidden = true;
  stopScanner();
}

document.querySelectorAll(".add-btn").forEach((b) =>
  b.addEventListener("click", () => openSheet(b.dataset.meal))
);
$("#sheet-close").addEventListener("click", closeSheet);
sheet.addEventListener("click", (e) => { if (e.target === sheet) closeSheet(); });

function showQuick(show) {
  $("#quick-tabs").hidden = !show;
  $("#quick-list").hidden = !show;
}

// ---- recent / favorites tabs -------------------------------------------------
document.querySelectorAll("#quick-tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    activeTab = b.dataset.tab;
    document.querySelectorAll("#quick-tabs button").forEach((x) =>
      x.classList.toggle("active", x === b));
    loadQuick(activeTab);
  })
);

async function loadQuick(tab) {
  const ul = $("#quick-list");
  ul.innerHTML = `<li class="r-loading">Loading…</li>`;
  try {
    const url = tab === "favorites" ? "/api/favorites" : "/api/recent";
    const items = await (await fetch(url)).json();
    renderQuick(items, tab);
  } catch {
    ul.innerHTML = `<li>Could not load.</li>`;
  }
}

function renderQuick(items, tab) {
  const ul = $("#quick-list");
  if (!items.length) {
    ul.innerHTML = `<li class="empty-quick">${tab === "favorites"
      ? "No favorites yet. Tick “Save to favorites” when adding a food."
      : "No recent foods yet."}</li>`;
    return;
  }
  ul.innerHTML = "";
  items.forEach((it) => {
    const qty = tab === "favorites" ? (it.default_qty_g || 100) : (it.serving_size_g || 100);
    const li = document.createElement("li");
    li.className = "quick-item";
    li.innerHTML =
      `<div class="qi-main"><div class="r-name">${escapeHtml(it.name)}</div>` +
      `<div class="r-sub">${it.brand ? escapeHtml(it.brand) + " · " : ""}` +
      `${Math.round(qty)} g · ${Math.round((it.calories || 0) * qty / 100)} kcal</div></div>` +
      (tab === "favorites"
        ? `<button class="qi-act remove" title="Remove favorite">✕</button>`
        : `<button class="qi-act star" title="Save as favorite">☆</button>`);
    li.querySelector(".qi-main").addEventListener("click", () => quickAdd(it, qty));
    const act = li.querySelector(".qi-act");
    act.addEventListener("click", (e) => {
      e.stopPropagation();
      if (tab === "favorites") removeFavorite(it.id);
      else saveFavorite(it, qty);
    });
    ul.appendChild(li);
  });
}

async function quickAdd(it, qty) {
  const res = await fetch("/api/entries", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      log_date: DATE, meal: currentMeal, name: it.name, brand: it.brand,
      quantity_g: qty, calories: it.calories, protein: it.protein,
      carbs: it.carbs, fat: it.fat, source: it.source, source_id: it.source_id,
    }),
  });
  if (res.ok) location.reload(); else toast("Could not add.");
}

async function saveFavorite(it, qty) {
  const res = await fetch("/api/favorites", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: it.name, brand: it.brand, serving_size_g: it.serving_size_g,
      default_qty_g: qty, calories: it.calories, protein: it.protein,
      carbs: it.carbs, fat: it.fat, source: it.source, source_id: it.source_id,
    }),
  });
  toast(res.ok ? "Saved to favorites ★" : "Could not save.");
}

async function removeFavorite(id) {
  const res = await fetch(`/api/favorites/${id}`, { method: "DELETE" });
  if (res.ok) loadQuick("favorites");
}

// ---- search ------------------------------------------------------------------
let searchTimer = null;
$("#food-q").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (q.length < 2) { $("#results").innerHTML = ""; showQuick(true); return; }
  showQuick(false);
  searchTimer = setTimeout(() => runSearch(q), 350);
});

async function runSearch(q) {
  $("#results").innerHTML = `<li class="r-loading">Searching…</li>`;
  try {
    const res = await fetch(`/api/foods/search?q=${encodeURIComponent(q)}`);
    renderResults(await res.json());
  } catch {
    $("#results").innerHTML = `<li>Search failed. Check connection.</li>`;
  }
}

function renderResults(products) {
  const ul = $("#results");
  if (!products.length) { ul.innerHTML = `<li>No matches.</li>`; return; }
  ul.innerHTML = "";
  products.forEach((p) => {
    const li = document.createElement("li");
    li.innerHTML =
      `<div class="r-name">${escapeHtml(p.name)}</div>` +
      `<div class="r-sub">${p.brand ? escapeHtml(p.brand) + " · " : ""}` +
      `${Math.round(p.calories)} kcal / 100g</div>`;
    li.addEventListener("click", () => pickProduct(p));
    ul.appendChild(li);
  });
}

// ---- pick + quantity ---------------------------------------------------------
function pickProduct(p) {
  picked = p;
  $("#results").innerHTML = "";
  $("#food-q").value = "";
  showQuick(false);
  $("#picked-name").textContent = p.name + (p.brand ? ` · ${p.brand}` : "");
  $("#picked-per100").textContent =
    `${Math.round(p.calories)} kcal · P${round1(p.protein)} C${round1(p.carbs)} F${round1(p.fat)} per 100g`;
  $("#qty").value = p.serving_size_g ? Math.round(p.serving_size_g) : 100;
  $("#save-fav").checked = false;
  $("#entry-form").hidden = false;
  updateLiveMacros();
}

$("#qty").addEventListener("input", updateLiveMacros);
function updateLiveMacros() {
  if (!picked) return;
  const f = (Number($("#qty").value) || 0) / 100;
  $("#live-macros").textContent =
    `= ${Math.round(picked.calories * f)} kcal · P${round1(picked.protein * f)} ` +
    `C${round1(picked.carbs * f)} F${round1(picked.fat * f)}`;
}
$("#pick-back").addEventListener("click", () => {
  $("#entry-form").hidden = true;
  showQuick(true);
  $("#food-q").focus();
});

$("#entry-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!picked) return;
  const qty = Number($("#qty").value);
  if (!qty || qty <= 0) return;
  if ($("#save-fav").checked) {
    await saveFavorite(picked, qty);
  }
  const res = await fetch("/api/entries", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      log_date: DATE, meal: currentMeal, name: picked.name, brand: picked.brand,
      quantity_g: qty, calories: picked.calories, protein: picked.protein,
      carbs: picked.carbs, fat: picked.fat,
      source: picked.source, source_id: picked.source_id,
    }),
  });
  if (res.ok) { location.reload(); } else { toast("Could not add entry."); }
});

// ---- delete ------------------------------------------------------------------
document.querySelectorAll(".del-btn").forEach((b) =>
  b.addEventListener("click", async () => {
    const res = await fetch(`/api/entries/${b.dataset.id}`, { method: "DELETE" });
    if (res.ok) location.reload();
  })
);

// ---- barcode scan ------------------------------------------------------------
// One camera pipeline; only the decoder differs by platform:
//   • BarcodeDetector — native, hardware-accelerated (Android Chrome)
//   • ZBar (WASM)     — fast 1D decoder for browsers without it (iOS Safari)
// ZBar is lazy-loaded the first time you scan so it costs nothing otherwise.
$("#scan-btn").addEventListener("click", startScanner);
$("#scan-stop").addEventListener("click", stopScanner);

let scanStream = null;     // active MediaStream
let scanning = false;
let scanHandled = false;   // guards against a barcode firing twice
let decodeFrame = null;    // (video) => Promise<string|null>
let zbarModule = null;     // cached WASM module

const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "itf", "codabar"];
// Inlined ESM build: real `export`s + the WASM embedded as base64, so there's no
// second cross-origin fetch (the plain dist/index.js is NOT an ES module).
const ZBAR_URL = "https://cdn.jsdelivr.net/npm/@undecaf/zbar-wasm@0.11.0/dist/inlined/index.mjs";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startScanner() {
  $("#scanner").hidden = false;
  showQuick(false);
  resetScan();
  try {
    decodeFrame = await buildDecoder();
  } catch (_) {
    toast("Scanner failed to load."); stopScanner(); return;
  }
  try {
    scanStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
    });
  } catch (_) {
    toast("Camera access denied."); stopScanner(); return;
  }
  const video = $("#scan-video");
  video.srcObject = scanStream;
  await video.play();
  scanning = true;
  scanLoop(video);
}

async function buildDecoder() {
  if ("BarcodeDetector" in window) {
    const supported = await window.BarcodeDetector.getSupportedFormats();
    const formats = BARCODE_FORMATS.filter((f) => supported.includes(f));
    const detector = new window.BarcodeDetector(formats.length ? { formats } : undefined);
    return async (video) => {
      const codes = await detector.detect(video);
      return codes && codes.length ? codes[0].rawValue : null;
    };
  }
  // ZBar WASM fallback — decode a downscaled frame off a canvas.
  zbarModule = zbarModule || (await import(ZBAR_URL));
  if (typeof zbarModule.scanImageData !== "function") {
    throw new Error("ZBar module did not load correctly");
  }
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  return async (video) => {
    if (!video.videoWidth) return null;
    const w = 640;
    const h = Math.round((video.videoHeight * w) / video.videoWidth);
    canvas.width = w; canvas.height = h;
    ctx.drawImage(video, 0, 0, w, h);
    const symbols = await zbarModule.scanImageData(ctx.getImageData(0, 0, w, h));
    return symbols && symbols.length ? symbols[0].decode() : null;
  };
}

async function scanLoop(video) {
  while (scanning) {
    try {
      const code = await decodeFrame(video);
      if (code) { onGoodScan(code); return; }
    } catch (_) { /* ignore transient decode errors */ }
    await sleep(80);  // ~12 fps — plenty, and keeps the CPU/battery in check
  }
}

function onGoodScan(code) {
  if (scanHandled) return;
  scanHandled = true;
  navigator.vibrate?.(60);                 // a short buzz confirms the read (Android)
  $("#scan-box").classList.add("good");    // light the targeting box green
  $("#scanner").classList.add("scanned");
  $("#scan-hint").textContent = "Got it!";
  // brief green flash so the read is visible, then look the product up
  setTimeout(async () => {
    await stopScanner();
    lookupScanned(code);
  }, 400);
}

async function stopScanner() {
  scanning = false;
  if (scanStream) { scanStream.getTracks().forEach((t) => t.stop()); scanStream = null; }
  const video = $("#scan-video");
  if (video) video.srcObject = null;
  $("#scanner").hidden = true;
  resetScan();
}

function resetScan() {
  scanHandled = false;
  $("#scan-box").classList.remove("good");
  $("#scanner").classList.remove("scanned");
  $("#scan-hint").textContent = "Point the camera at a barcode";
}

async function lookupScanned(code) {
  $("#results").innerHTML = `<li class="r-loading">Looking up ${escapeHtml(code)}…</li>`;
  try {
    const res = await fetch(`/api/foods/barcode/${encodeURIComponent(code)}`);
    if (res.ok) {
      pickProduct(await res.json());
    } else {
      $("#results").innerHTML =
        `<li>Scanned <b>${escapeHtml(code)}</b> — not in the food database. Try searching by name.</li>`;
    }
  } catch {
    $("#results").innerHTML = `<li>Lookup failed. Check your connection.</li>`;
  }
}

// ---- energy edit -------------------------------------------------------------
const energySheet = $("#energy-sheet");
$("#edit-energy").addEventListener("click", () => {
  const b = $("#edit-energy");
  $("#active").value = Math.round(Number(b.dataset.active) || 0);
  $("#resting").value = Math.round(Number(b.dataset.resting) || 0);
  energySheet.hidden = false;
});
$("#energy-close").addEventListener("click", () => (energySheet.hidden = true));
energySheet.addEventListener("click", (e) => { if (e.target === energySheet) energySheet.hidden = true; });

$("#energy-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const res = await fetch("/api/energy", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      record_date: DATE,
      active_kcal: Number($("#active").value) || 0,
      resting_kcal: Number($("#resting").value) || 0,
    }),
  });
  if (res.ok) location.reload(); else toast("Could not save energy.");
});

// ---- edit a logged entry -----------------------------------------------------
const editSheet = $("#edit-sheet");
let editing = null; // { id, cal100, pro100, carb100, fat100 }

document.querySelectorAll(".entry").forEach((li) =>
  li.querySelector(".entry-main").addEventListener("click", () => openEdit(li.dataset))
);

function openEdit(d) {
  editing = {
    id: d.id,
    cal100: Number(d.cal100), pro100: Number(d.pro100),
    carb100: Number(d.carb100), fat100: Number(d.fat100),
  };
  $("#edit-title").textContent = d.name;
  $("#edit-qty").value = Math.round(Number(d.qty));
  editSheet.hidden = false;
  updateEditMacros();
}

$("#edit-qty").addEventListener("input", updateEditMacros);
function updateEditMacros() {
  if (!editing) return;
  const f = (Number($("#edit-qty").value) || 0) / 100;
  $("#edit-live").textContent =
    `= ${Math.round(editing.cal100 * f)} kcal · P${round1(editing.pro100 * f)} ` +
    `C${round1(editing.carb100 * f)} F${round1(editing.fat100 * f)}`;
}

$("#edit-close").addEventListener("click", () => (editSheet.hidden = true));
editSheet.addEventListener("click", (e) => { if (e.target === editSheet) editSheet.hidden = true; });

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const qty = Number($("#edit-qty").value);
  if (!editing || !qty || qty <= 0) return;
  const res = await fetch(`/api/entries/${editing.id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity_g: qty }),
  });
  if (res.ok) location.reload(); else toast("Could not save changes.");
});

$("#edit-delete").addEventListener("click", async () => {
  if (!editing) return;
  const res = await fetch(`/api/entries/${editing.id}`, { method: "DELETE" });
  if (res.ok) location.reload(); else toast("Could not delete.");
});

// ---- global sheet behaviour: Escape closes, lock background scroll -----------
function syncScrollLock() {
  document.body.classList.toggle(
    "sheet-open", !sheet.hidden || !energySheet.hidden || !editSheet.hidden
  );
}
// Keep the scroll lock in sync however a sheet was opened or closed.
const sheetObserver = new MutationObserver(syncScrollLock);
[sheet, energySheet, editSheet].forEach((el) =>
  sheetObserver.observe(el, { attributes: true, attributeFilter: ["hidden"] }));

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!editSheet.hidden) editSheet.hidden = true;
  else if (!energySheet.hidden) energySheet.hidden = true;
  else if (!sheet.hidden) closeSheet();
});

// ---- utils -------------------------------------------------------------------
function round1(n) { return Math.round((n || 0) * 10) / 10; }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
