// =======================
// Cold Room Manage (Django + API)
// 需要后端接口：
//  - GET    /api/coldrooms/stats
//  - GET    /api/coldrooms?page=1&pageSize=10&status=&keyword=&region=&tempRange=
//  - POST   /api/coldrooms
//  - PUT    /api/coldrooms/<id>
//  - DELETE /api/coldrooms/<id>
//
// 列表返回建议：{ total, page, pageSize, rows: [...] }
// rows字段建议：
// { id, name, code, location, temp_min, temp_max, temp_current, status, device_count, updated_at }
// stats返回建议：{ total, normal, alarm, offline, ts }
// =======================

const API = {
  stats: "/api/coldrooms/stats",
  list: "/api/coldrooms",
  detail: (id) => `/api/coldrooms/${id}`,
};

const state = {
  page: 1,
  pageSize: 10,
  filters: { status: "", keyword: "", region: "", tempRange: "" },
  lastPageRows: [], // 用于导出CSV（当前页）
};

let modal = null;
let toast = null;

function $(id){ return document.getElementById(id); }

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      // 如果你启用 CSRF，可在这里加 X-CSRFToken
    },
    ...opts
  });

  if (!r.ok) {
    const text = await r.text().catch(()=> "");
    throw new Error(`${r.status} ${r.statusText} :: ${url} :: ${text.slice(0, 200)}`);
  }
  // 204 No Content
  if (r.status === 204) return null;
  return r.json();
}

function setLastUpdated(ts){
  const el = $("lastUpdated");
  if(!el) return;
  const s = ts ? new Date(ts).toLocaleString() : new Date().toLocaleString();
  el.textContent = `最后更新：${s}`;
}

function showToast(msg){
  $("toastBody").textContent = msg;
  toast.show();
}

function setFormError(msg){
  const el = $("formError");
  if(!msg){
    el.classList.add("d-none");
    el.textContent = "";
    return;
  }
  el.classList.remove("d-none");
  el.textContent = msg;
}

function chip(status){
  if(status === "normal") return `<span class="chip normal"><span class="dot"></span>正常</span>`;
  if(status === "offline") return `<span class="chip offline"><span class="dot"></span>离线</span>`;
  return `<span class="chip alarm"><span class="dot"></span>告警</span>`;
}

function tempRangeText(min, max){
  const hasMin = (min !== null && min !== undefined && min !== "");
  const hasMax = (max !== null && max !== undefined && max !== "");
  if(!hasMin && !hasMax) return `<span class="muted">-</span>`;
  if(hasMin && hasMax) return `${min} ~ ${max}℃`;
  if(hasMin) return `≥ ${min}℃`;
  return `≤ ${max}℃`;
}

function safe(v){ return (v === null || v === undefined) ? "" : String(v); }

// ---------- render ----------
function renderStats(stats){
  $("kpiTotal").textContent = stats.total ?? "-";
  $("kpiNormal").textContent = stats.normal ?? "-";
  $("kpiAlarm").textContent = stats.alarm ?? "-";
  $("kpiOffline").textContent = stats.offline ?? "-";
  setLastUpdated(stats.ts);
}

function renderTable(data){
  const tbody = $("tableBody");
  tbody.innerHTML = "";

  const rows = data.rows || [];
  state.lastPageRows = rows;

  if(!rows.length){
    tbody.innerHTML = `<tr><td colspan="9" class="text-center muted py-4">暂无数据</td></tr>`;
  }else{
    for(const r of rows){
      const nameLine = `<b>${safe(r.name)}</b> <span class="muted">(${safe(r.code)})</span>`;
      const tempCurrent = (r.temp_current === null || r.temp_current === undefined || r.temp_current === "")
        ? `<span class="muted">-</span>`
        : `<span class="badge-soft">${safe(r.temp_current)}℃</span>`;

      tbody.insertAdjacentHTML("beforeend", `
        <tr>
          <td>${safe(r.id)}</td>
          <td>${nameLine}</td>
          <td>${safe(r.location) || `<span class="muted">-</span>`}</td>
          <td>${tempRangeText(r.temp_min, r.temp_max)}</td>
          <td>${tempCurrent}</td>
          <td>${chip(r.status || "normal")}</td>
          <td>${safe(r.device_count ?? 0)}</td>
          <td class="muted">${safe(r.updated_at) || ""}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary op-btn" data-action="edit" data-id="${r.id}">
              <i class="fa-regular fa-pen-to-square"></i> 编辑
            </button>
            <button class="btn btn-sm btn-outline-secondary op-btn" data-action="devices" data-id="${r.id}">
              <i class="fa-solid fa-microchip"></i> 设备
            </button>
            <button class="btn btn-sm btn-outline-danger op-btn" data-action="delete" data-id="${r.id}">
              <i class="fa-regular fa-trash-can"></i> 删除
            </button>
          </td>
        </tr>
      `);
    }
  }

  const total = Number(data.total || 0);
  const page = Number(data.page || 1);
  const pageSize = Number(data.pageSize || state.pageSize);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  $("pageInfo").textContent = `共 ${total} 条｜第 ${page} / ${totalPages} 页`;
  $("btnPrev").disabled = (page <= 1);
  $("btnNext").disabled = (page >= totalPages);
}

// ---------- API calls ----------
async function apiGetStats(){
  return fetchJSON(API.stats);
}

async function apiGetList(){
  const qs = new URLSearchParams({
    page: String(state.page),
    pageSize: String(state.pageSize),
    status: state.filters.status || "",
    keyword: state.filters.keyword || "",
    region: state.filters.region || "",
    tempRange: state.filters.tempRange || "",
  }).toString();
  return fetchJSON(`${API.list}?${qs}`);
}

async function apiCreate(payload){
  return fetchJSON(API.list, { method: "POST", body: JSON.stringify(payload) });
}

async function apiUpdate(id, payload){
  return fetchJSON(API.detail(id), { method: "PUT", body: JSON.stringify(payload) });
}

async function apiDelete(id){
  return fetchJSON(API.detail(id), { method: "DELETE" });
}

// ---------- modal helpers ----------
function openCreate(){
  $("modalTitle").textContent = "新增冷库";
  $("crId").value = "";
  $("crName").value = "";
  $("crCode").value = "";
  $("crLocation").value = "";
  $("crTempMin").value = "";
  $("crTempMax").value = "";
  $("crStatus").value = "normal";
  $("crNote").value = "";
  setFormError(null);
  modal.show();
}

function openEdit(row){
  $("modalTitle").textContent = "编辑冷库";
  $("crId").value = row.id ?? "";
  $("crName").value = row.name ?? "";
  $("crCode").value = row.code ?? "";
  $("crLocation").value = row.location ?? "";
  $("crTempMin").value = (row.temp_min ?? "");
  $("crTempMax").value = (row.temp_max ?? "");
  $("crStatus").value = row.status ?? "normal";
  $("crNote").value = row.note ?? "";
  setFormError(null);
  modal.show();
}

function collectFormPayload(){
  const name = $("crName").value.trim();
  const code = $("crCode").value.trim();
  const location = $("crLocation").value.trim();
  const status = $("crStatus").value;
  const note = $("crNote").value.trim();

  const temp_min_raw = $("crTempMin").value;
  const temp_max_raw = $("crTempMax").value;
  const temp_min = temp_min_raw === "" ? null : Number(temp_min_raw);
  const temp_max = temp_max_raw === "" ? null : Number(temp_max_raw);

  if(!name) return { error: "请填写冷库名称" };
  if(!code) return { error: "请填写冷库编号" };
  if((temp_min !== null && Number.isNaN(temp_min)) || (temp_max !== null && Number.isNaN(temp_max))){
    return { error: "温度输入格式不正确" };
  }
  if(temp_min !== null && temp_max !== null && temp_min > temp_max){
    return { error: "最低温不能高于最高温" };
  }

  return {
    payload: {
      name, code, location, status, note,
      temp_min, temp_max
    }
  };
}

// ---------- export ----------
function exportCsvCurrentPage(){
  const rows = state.lastPageRows || [];
  if(!rows.length){
    showToast("当前页无数据可导出");
    return;
  }

  const header = ["ID","冷库名称","冷库编号","位置/区域","最低温","最高温","当前温度","状态","设备数","更新时间"];
  const lines = [header.join(",")];

  for(const r of rows){
    const line = [
      safe(r.id),
      `"${safe(r.name).replaceAll('"','""')}"`,
      `"${safe(r.code).replaceAll('"','""')}"`,
      `"${safe(r.location).replaceAll('"','""')}"`,
      safe(r.temp_min ?? ""),
      safe(r.temp_max ?? ""),
      safe(r.temp_current ?? ""),
      safe(r.status ?? ""),
      safe(r.device_count ?? 0),
      `"${safe(r.updated_at).replaceAll('"','""')}"`,
    ];
    lines.push(line.join(","));
  }

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `coldrooms_page_${state.page}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------- drill ----------
function drillTo(status){
  $("filterStatus").value = (status === "all" ? "" : status);
  state.filters.status = (status === "all" ? "" : status);
  state.page = 1;
  loadList().catch(console.warn);
}

// ---------- load ----------
async function loadStats(){
  const stats = await apiGetStats();
  renderStats(stats);
}

async function loadList(){
  const data = await apiGetList();
  renderTable(data);
}

async function init(){
  try { await loadStats(); } catch(e){ console.warn("stats failed:", e); }
  try { await loadList(); } catch(e){ console.warn("list failed:", e); }
}

// ---------- events ----------
function bindEvents(){
  // KPI 下钻
  document.querySelectorAll(".kpi").forEach(el=>{
    el.addEventListener("click", ()=> drillTo(el.dataset.drill));
  });

  $("btnRefreshAll").addEventListener("click", ()=> init());

  $("btnOpenCreate").addEventListener("click", ()=> openCreate());

  $("btnExportCsv").addEventListener("click", ()=> exportCsvCurrentPage());

  $("btnSearch").addEventListener("click", ()=>{
    state.filters = {
      keyword: $("keyword").value.trim(),
      status: $("filterStatus").value,
      region: $("filterRegion").value.trim(),
      tempRange: $("filterTempRange").value,
    };
    state.page = 1;
    loadList().catch(console.warn);
  });

  $("btnReset").addEventListener("click", ()=>{
    $("keyword").value = "";
    $("filterStatus").value = "";
    $("filterRegion").value = "";
    $("filterTempRange").value = "";
    state.filters = { status:"", keyword:"", region:"", tempRange:"" };
    state.page = 1;
    loadList().catch(console.warn);
  });

  $("btnPrev").addEventListener("click", ()=>{
    state.page = Math.max(1, state.page - 1);
    loadList().catch(console.warn);
  });
  $("btnNext").addEventListener("click", ()=>{
    state.page += 1;
    loadList().catch(console.warn);
  });

  // 表格按钮事件委托
  $("tableBody").addEventListener("click", async (e)=>{
    const btn = e.target.closest("button[data-action]");
    if(!btn) return;

    const action = btn.dataset.action;
    const id = btn.dataset.id;

    if(action === "devices"){
      // 你可以改成跳转：/devices/?coldroom_id=xxx
      location.href = `/devices/?coldroom_id=${encodeURIComponent(id)}`;
      return;
    }

    if(action === "edit"){
      const row = (state.lastPageRows || []).find(x => String(x.id) === String(id));
      if(!row){
        showToast("未找到该行数据，请刷新后重试");
        return;
      }
      openEdit(row);
      return;
    }

    if(action === "delete"){
      if(!confirm("确认删除该冷库？删除后不可恢复。")) return;
      try{
        await apiDelete(id);
        showToast("删除成功");
        await init();
      }catch(err){
        console.warn(err);
        showToast("删除失败（请检查后端接口/权限）");
      }
      return;
    }
  });

  // 保存（新增/编辑）
  $("btnSaveColdroom").addEventListener("click", async ()=>{
    setFormError(null);
    const { payload, error } = collectFormPayload();
    if(error){
      setFormError(error);
      return;
    }

    const id = $("crId").value;
    try{
      if(id){
        await apiUpdate(id, payload);
        showToast("更新成功");
      }else{
        await apiCreate(payload);
        showToast("新增成功");
      }
      modal.hide();
      await init();
    }catch(err){
      console.warn(err);
      setFormError("保存失败：请检查后端接口返回/字段校验/CSRF 设置");
    }
  });

  // 页面重新可见时刷新一次
  document.addEventListener("visibilitychange", ()=>{
    if(!document.hidden) init();
  });
}

// ---------- boot ----------
document.addEventListener("DOMContentLoaded", ()=>{
  modal = new bootstrap.Modal(document.getElementById("coldroomModal"));
  toast = bootstrap.Toast.getOrCreateInstance(document.getElementById("appToast"), { delay: 2500 });

  bindEvents();
  init();
});
