/* Calibrate day-view interactions: search, barcode scan, add/delete entries, energy edit. */
const DATE = window.CALIBRATE_DATE;
const $ = (sel) => document.querySelector(sel);

let currentMeal = "snack";
let picked = null; // selected Product (per-100g)
let scanner = null;

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
  sheet.hidden = false;
  $("#food-q").focus();
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

// ---- search ------------------------------------------------------------------
let searchTimer = null;
$("#food-q").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (q.length < 2) { $("#results").innerHTML = ""; return; }
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
  $("#picked-name").textContent = p.name + (p.brand ? ` · ${p.brand}` : "");
  $("#picked-per100").textContent =
    `${Math.round(p.calories)} kcal · P${round1(p.protein)} C${round1(p.carbs)} F${round1(p.fat)} per 100g`;
  $("#qty").value = p.serving_size_g ? Math.round(p.serving_size_g) : 100;
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
  $("#food-q").focus();
});

$("#entry-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!picked) return;
  const qty = Number($("#qty").value);
  if (!qty || qty <= 0) return;
  const body = {
    log_date: DATE, meal: currentMeal, name: picked.name, brand: picked.brand,
    quantity_g: qty, calories: picked.calories, protein: picked.protein,
    carbs: picked.carbs, fat: picked.fat,
    food_item_id: picked.food_item_id || null,
  };
  const res = await fetch("/api/entries", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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
$("#scan-btn").addEventListener("click", startScanner);
$("#scan-stop").addEventListener("click", stopScanner);

async function startScanner() {
  if (typeof Html5Qrcode === "undefined") { toast("Scanner unavailable offline."); return; }
  $("#scanner").hidden = false;
  scanner = new Html5Qrcode("reader");
  try {
    await scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 250, height: 150 } },
      onScan,
      () => {}
    );
  } catch {
    toast("Camera access denied.");
    stopScanner();
  }
}

async function stopScanner() {
  $("#scanner").hidden = true;
  if (scanner) {
    try { await scanner.stop(); scanner.clear(); } catch {}
    scanner = null;
  }
}

async function onScan(code) {
  await stopScanner();
  $("#results").innerHTML = `<li class="r-loading">Looking up ${escapeHtml(code)}…</li>`;
  try {
    const res = await fetch(`/api/foods/barcode/${encodeURIComponent(code)}`);
    if (res.ok) { pickProduct(await res.json()); }
    else { $("#results").innerHTML = `<li>No product for barcode ${escapeHtml(code)}.</li>`; }
  } catch {
    $("#results").innerHTML = `<li>Lookup failed.</li>`;
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

// ---- utils -------------------------------------------------------------------
function round1(n) { return Math.round((n || 0) * 10) / 10; }
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
