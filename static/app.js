let meta = { categories: [], statuses: [] };

function escapeHtml(s){
  return String(s || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function badgeStatus(status){
  const map = {
    "In Stock": "success",
    "Assigned": "primary",
    "Repair": "warning",
    "Retired": "secondary",
  };
  return `<span class="badge text-bg-${map[status] || "secondary"}">${escapeHtml(status)}</span>`;
}

function badgeWarranty(a){
  if (a.warranty_expired) return `<span class="badge text-bg-danger">Expired</span>`;
  if (a.warranty_expiring_30d) return `<span class="badge text-bg-warning text-dark">Expiring</span>`;
  return `<span class="badge text-bg-success">OK</span>`;
}

async function apiGetReports(){
  const r = await fetch("/api/reports");
  return await r.json();
}

async function apiGetAssets(){
  const category = document.getElementById("filterCategory").value;
  const status = document.getElementById("filterStatus").value;
  const warranty = document.getElementById("filterWarranty").value;
  const search = document.getElementById("filterSearch").value.trim();

  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (status) params.set("status", status);
  if (warranty) params.set("warranty", warranty);
  if (search) params.set("search", search);

  const r = await fetch(`/api/assets?${params.toString()}`);
  const data = await r.json();
  return data.items || [];
}

function renderAssets(items){
  const body = document.getElementById("assetsBody");
  if (!items.length){
    body.innerHTML = `<tr><td colspan="6" class="text-secondary">No assets found.</td></tr>`;
    return;
  }

  body.innerHTML = items.map(a => {
    const details = `${escapeHtml(a.category)} • ${escapeHtml(a.brand)} ${escapeHtml(a.model)}<div class="small text-secondary">SN: ${escapeHtml(a.serial_no || "-")} • Loc: ${escapeHtml(a.location || "-")}</div>`;
    const warranty = `${badgeWarranty(a)} <span class="ms-2 small text-secondary">${escapeHtml(a.warranty_end || "-")}</span>`;
    const assignedTo = a.assigned_to ? escapeHtml(a.assigned_to) : `<span class="text-secondary">-</span>`;

    return `
      <tr>
        <td class="fw-semibold">${escapeHtml(a.asset_tag)}</td>
        <td>${details}</td>
        <td>${warranty}</td>
        <td>${badgeStatus(a.status)}</td>
        <td>${assignedTo}</td>
        <td class="d-flex gap-2 flex-wrap">
          <button class="btn btn-outline-primary btn-sm" onclick="openEdit(${a.id})">Edit</button>
          <button class="btn btn-outline-secondary btn-sm" onclick="openHistory(${a.id})">History</button>
          <button class="btn btn-outline-danger btn-sm" onclick="deleteAsset(${a.id})">Delete</button>
        </td>
      </tr>
    `;
  }).join("");
}

async function refreshAll(){
  const rep = await apiGetReports();

  meta.categories = rep.categories || [];
  meta.statuses = rep.statuses || [];

  // set filters options once
  fillSelectOnce("filterCategory", meta.categories, "All Categories");
  fillSelectOnce("filterStatus", meta.statuses, "All Status");

  document.getElementById("statTotal").textContent = rep.total_assets ?? "-";
  document.getElementById("statAssigned").textContent = rep.assigned_now ?? "-";
  document.getElementById("statExpiring").textContent = rep.warranty_expiring_30d ?? "-";
  document.getElementById("statExpired").textContent = rep.warranty_expired ?? "-";

  const items = await apiGetAssets();
  renderAssets(items);

  document.getElementById("lastUpdated").textContent = "Last updated: " + new Date().toLocaleString();
}

function fillSelectOnce(id, items, firstLabel){
  const sel = document.getElementById(id);
  if (sel.getAttribute("data-filled") === "1") return;

  const keep = sel.value;
  sel.innerHTML = `<option value="">${firstLabel}</option>` + items.map(x => `<option>${escapeHtml(x)}</option>`).join("");
  sel.value = keep || "";
  sel.setAttribute("data-filled", "1");
}

function openAdd(){
  document.getElementById("assetModalTitle").textContent = "Add Asset";
  document.getElementById("aId").value = "";
  document.getElementById("aTag").disabled = false;

  setAssetForm({
    asset_tag: "",
    category: "Laptop",
    status: "In Stock",
    brand: "", model: "", serial_no: "",
    purchase_date: "", warranty_end: "",
    assigned_to: "", location: "", notes: ""
  });

  document.getElementById("assetErr").textContent = "";
}

function setAssetForm(a){
  document.getElementById("aTag").value = a.asset_tag || "";
  document.getElementById("aCategory").value = a.category || "Laptop";
  document.getElementById("aStatus").value = a.status || "In Stock";
  document.getElementById("aBrand").value = a.brand || "";
  document.getElementById("aModel").value = a.model || "";
  document.getElementById("aSerial").value = a.serial_no || "";
  document.getElementById("aPurchase").value = a.purchase_date || "";
  document.getElementById("aWarranty").value = a.warranty_end || "";
  document.getElementById("aAssignedTo").value = a.assigned_to || "";
  document.getElementById("aLocation").value = a.location || "";
  document.getElementById("aNotes").value = a.notes || "";
}

async function openEdit(id){
  const items = await apiGetAssets(); // simple way: re-fetch then find
  const a = items.find(x => x.id === id);
  if (!a) return alert("Asset not found");

  document.getElementById("assetModalTitle").textContent = "Edit Asset";
  document.getElementById("aId").value = a.id;
  document.getElementById("aTag").disabled = false; // allow tag change (with uniqueness check)

  setAssetForm(a);
  document.getElementById("assetErr").textContent = "";

  const modalEl = document.getElementById("assetModal");
  const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
  modal.show();
}

async function saveAsset(){
  const err = document.getElementById("assetErr");
  err.textContent = "";

  const id = document.getElementById("aId").value.trim();
  const payload = {
    asset_tag: document.getElementById("aTag").value.trim(),
    category: document.getElementById("aCategory").value,
    status: document.getElementById("aStatus").value,
    brand: document.getElementById("aBrand").value.trim(),
    model: document.getElementById("aModel").value.trim(),
    serial_no: document.getElementById("aSerial").value.trim(),
    purchase_date: document.getElementById("aPurchase").value,
    warranty_end: document.getElementById("aWarranty").value,
    assigned_to: document.getElementById("aAssignedTo").value.trim(),
    location: document.getElementById("aLocation").value.trim(),
    notes: document.getElementById("aNotes").value.trim(),
  };

  let resp;
  if (!id){
    resp = await fetch("/api/assets", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
  } else {
    resp = await fetch(`/api/assets/${id}`, {
      method: "PATCH",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
  }

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok){
    err.textContent = data.error || "Failed to save asset.";
    return;
  }

  // close modal
  const modalEl = document.getElementById("assetModal");
  const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
  modal.hide();
  await refreshAll();
}

async function deleteAsset(id){
  if (!confirm("Delete this asset? This will also delete its assignment history.")) return;
  await fetch(`/api/assets/${id}`, { method: "DELETE" });
  await refreshAll();
}

async function openHistory(assetId){
  document.getElementById("hAssetId").value = assetId;
  document.getElementById("histErr").textContent = "";
  document.getElementById("histBody").innerHTML = `<tr><td colspan="4" class="text-secondary">Loading...</td></tr>`;

  const r = await fetch(`/api/assets/${assetId}/history`);
  const data = await r.json();

  if (!r.ok){
    document.getElementById("histErr").textContent = data.error || "Failed to load history";
    return;
  }

  const a = data.asset;
  document.getElementById("histAssetTitle").innerHTML =
    `<span class="fw-semibold">${escapeHtml(a.asset_tag)}</span> • ${escapeHtml(a.category)} • ${escapeHtml(a.brand)} ${escapeHtml(a.model)} 
     <span class="ms-2">${badgeStatus(a.status)}</span>`;

  const rows = (data.history || []).map(h => {
    const rOn = h.returned_on ? new Date(h.returned_on).toLocaleString() : `<span class="text-secondary">-</span>`;
    return `
      <tr>
        <td>${escapeHtml(h.assigned_to)}</td>
        <td>${new Date(h.assigned_on).toLocaleString()}</td>
        <td>${rOn}</td>
        <td class="small">${escapeHtml(h.notes || "")}</td>
      </tr>
    `;
  });

  document.getElementById("histBody").innerHTML = rows.length
    ? rows.join("")
    : `<tr><td colspan="4" class="text-secondary">No history yet.</td></tr>`;

  // show modal
  const modalEl = document.getElementById("historyModal");
  const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
  modal.show();
}

async function assignAsset(){
  const assetId = document.getElementById("hAssetId").value;
  const assigned_to = document.getElementById("hAssignTo").value.trim();
  const location = document.getElementById("hLocation").value.trim();
  const notes = document.getElementById("hNotes").value.trim();

  const err = document.getElementById("histErr");
  err.textContent = "";

  const r = await fetch(`/api/assets/${assetId}/assign`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ assigned_to, location, notes })
  });

  const data = await r.json().catch(() => ({}));
  if (!r.ok){
    err.textContent = data.error || "Failed to assign";
    return;
  }

  // clear inputs
  document.getElementById("hAssignTo").value = "";
  document.getElementById("hLocation").value = "";
  document.getElementById("hNotes").value = "";

  await openHistory(Number(assetId));
  await refreshAll();
}

async function returnAsset(){
  const assetId = document.getElementById("hAssetId").value;
  const notes = document.getElementById("hNotes").value.trim();

  const err = document.getElementById("histErr");
  err.textContent = "";

  const r = await fetch(`/api/assets/${assetId}/return`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ notes })
  });

  const data = await r.json().catch(() => ({}));
  if (!r.ok){
    err.textContent = data.error || "Failed to return";
    return;
  }

  document.getElementById("hNotes").value = "";
  await openHistory(Number(assetId));
  await refreshAll();
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btnRefresh").addEventListener("click", refreshAll);

  // export buttons
  document.getElementById("btnExportAssets").addEventListener("click", () => {
    window.location.href = "/api/reports/export/assets";
  });
  document.getElementById("btnExportAssignments").addEventListener("click", () => {
    window.location.href = "/api/reports/export/assignments";
  });

  // open add modal
  const assetModalEl = document.getElementById("assetModal");
  assetModalEl.addEventListener("show.bs.modal", () => {
    // if opened from navbar +Add Asset, we want clean state
    if (!document.getElementById("aId").value) openAdd();
  });

  document.getElementById("btnSaveAsset").addEventListener("click", saveAsset);

  // history actions
  document.getElementById("btnAssign").addEventListener("click", assignAsset);
  document.getElementById("btnReturn").addEventListener("click", returnAsset);

  // filters live refresh
  ["filterCategory","filterStatus","filterWarranty"].forEach(id => {
    document.getElementById(id).addEventListener("change", refreshAll);
  });
  document.getElementById("filterSearch").addEventListener("keyup", () => {
    clearTimeout(window.__srch);
    window.__srch = setTimeout(refreshAll, 250);
  });

  refreshAll();
});
