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
// { id, name, code, location, longitude, latitude, temp_min, temp_max, temp_current, status, device_count, updated_at }
// stats返回建议：{ total, normal, alarm, offline, ts }
//
// 可选（高德逆地理）：
//  - POST /api/amap/regeo/   body: { lng, lat }  -> { ok:true, address:"xxx" }
// =======================

const API = {
  stats: "/api/coldrooms/stats",
  list: "/api/coldrooms",
  detail: (id) => `/api/coldrooms/${id}`,

  // ✅ 可选：你后端封装的高德逆地理接口（如果路径不同改这里）
  amapRegeo: "/api/amap/regeo/",
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

// ✅ 可选：如果你开启了 CSRF，这个用于取 csrftoken
function getCookie(name) {
  const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return m ? m.pop() : "";
}

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      // 如果你启用 CSRF，可在这里加 X-CSRFToken
      // "X-CSRFToken": getCookie("csrftoken"),
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

function coordText(v){
  if(v === null || v === undefined || v === "") return `<span class="muted">-</span>`;
  return safe(v);
}

function to3(val){
  // ✅ 保留 3 位小数，空值返回 null
  if(val === null || val === undefined) return null;
  const s = String(val).trim();
  if(s === "") return null;
  const num = Number(s);
  if(Number.isNaN(num)) return null;
  return Number(num.toFixed(3));
}

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

  // ✅ 现在表格是 11 列（加了经纬度），所以空行 colspan=11
  if(!rows.length){
    tbody.innerHTML = `<tr><td colspan="11" class="text-center muted py-4">暂无数据</td></tr>`;
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

          <td>${coordText(r.longitude)}</td>
          <td>${coordText(r.latitude)}</td>

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

// ✅ 可选：调用你后端封装的高德逆地理接口（经纬度 -> 地址）
async function apiAmapRegeo(lng, lat){
  // 如果你启用 CSRF，就把 X-CSRFToken 打开
  return fetchJSON(API.amapRegeo, {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      // "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ lng, lat }),
  });
}

// ---------- modal helpers ----------
function openCreate(){
  $("modalTitle").textContent = "新增冷库";
  $("crId").value = "";
  $("crName").value = "";
  $("crCode").value = "";
  $("crLocation").value = "";

  // ✅ 新增字段清空
  $("crLng").value = "";
  $("crLat").value = "";

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

  // ✅ 回填经纬度
  $("crLng").value = (row.longitude ?? "");
  $("crLat").value = (row.latitude ?? "");

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

  // ✅ 经度/纬度：保留 3 位小数
  const longitude = to3($("crLng").value);
  const latitude  = to3($("crLat").value);

  if(!name) return { error: "请填写冷库名称" };
  if(!code) return { error: "请填写冷库编号" };

  if((temp_min !== null && Number.isNaN(temp_min)) || (temp_max !== null && Number.isNaN(temp_max))){
    return { error: "温度输入格式不正确" };
  }
  if(temp_min !== null && temp_max !== null && temp_min > temp_max){
    return { error: "最低温不能高于最高温" };
  }

  // ✅ 经纬度格式校验（可选：你不填也允许）
  if(longitude !== null && (longitude < -180 || longitude > 180)){
    return { error: "经度范围应为 -180 ~ 180" };
  }
  if(latitude !== null && (latitude < -90 || latitude > 90)){
    return { error: "纬度范围应为 -90 ~ 90" };
  }

  return {
    payload: {
      name, code, location, status, note,
      temp_min, temp_max,

      // ✅ 提交给后端保存
      longitude,
      latitude
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

  // ✅ CSV 增加经纬度
  const header = ["ID","冷库名称","冷库编号","位置/区域","经度","纬度","最低温","最高温","当前温度","状态","设备数","更新时间"];
  const lines = [header.join(",")];

  for(const r of rows){
    const line = [
      safe(r.id),
      `"${safe(r.name).replaceAll('"','""')}"`,
      `"${safe(r.code).replaceAll('"','""')}"`,
      `"${safe(r.location).replaceAll('"','""')}"`,
      safe(r.longitude ?? ""),
      safe(r.latitude ?? ""),
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

// ---------- 可选：经纬度变化 -> 自动调用高德逆地理 -> 自动填地址 ----------
let _regeoTimer = null;
function debounceRegeo(){
  if(_regeoTimer) clearTimeout(_regeoTimer);
  _regeoTimer = setTimeout(async ()=>{
    try{
      const lng = to3($("crLng").value);
      const lat = to3($("crLat").value);
      if(lng === null || lat === null) return;

      // ✅ 只在“地址为空”时自动填（避免覆盖你手动输入）
      const loc = $("crLocation").value.trim();
      if(loc) return;

      const data = await apiAmapRegeo(lng, lat);
      if(data && data.ok && data.address){
        $("crLocation").value = data.address;
      }
    }catch(err){
      // 不影响主流程，只打印
      console.warn("amap regeo failed:", err);
    }
  }, 400); // 0.4s 防抖
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

  // ✅ 可选：经纬度输入框变化时自动填地址（高德逆地理）
  // 注意：输入框在弹窗里，所以页面加载后就能绑定到 DOM
  $("crLng")?.addEventListener("input", debounceRegeo);
  $("crLat")?.addEventListener("input", debounceRegeo);

  // 表格按钮事件委托
  $("tableBody").addEventListener("click", async (e)=>{
    const btn = e.target.closest("button[data-action]");
    if(!btn) return;

    const action = btn.dataset.action;
    const id = btn.dataset.id;

    if(action === "devices"){
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
