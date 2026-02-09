// storageSystem/static/storageSystem/js/dashboard.js
(() => {
  const API = {
    deviceNames: "/storage/api/device-names/",
    trend: "/storage/api/dashboard/trend/",
    deviceList: "/storage/api/dashboard/devices/",

    // 编辑 / 删除
    deviceUpdate: "/storage/api/dashboard/device-update/",
    deviceDelete: "/storage/api/dashboard/device-delete/",
  };

  // 字段名映射：后端 series.name -> 前端 legend
  const METRIC_LABEL_MAP = {
    temperature: "温度",
    humidity: "湿度",
    co2_ppm: "CO₂",
    h2_ppm: "H2",
    co_ppm: "CO",
    c2h5oh: "C₂H₅OH",
    voc: "VOC",
    o2: "O₂",
    c2h4: "C₂H₄",
  };

  // 高德网页 marker 坐标系
  const AMAP_COORD_SYS = "gaode";

  const state = {
    range: "30d",
    selectedDevice: "",
    chart: null,

    inFlightTrend: false,
    timer: null,
    refreshMs: 5000,

    // 明细表分页
    tablePage: 1,
    tablePageSize: 10,
    tableTotal: 0,
    inFlightTable: false,

    // 当前表格数据索引（用于点击行/编辑/删除）
    tableIndex: new Map(), // key: String(id) -> item

    // Modals
    editModal: null,
    deleteModal: null,

    inFlightSave: false,
    inFlightDelete: false,

    // 可选：从 URL 注入的基地编号，用于按 base_id 过滤设备表
    filterBaseId: "",
  };

  // 从全局变量注入 base_id（由 Django 模板在 <head> 中设置）
  state.filterBaseId = window.__FILTER_BASE_ID__ || "";

  // ---------- utils ----------
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function formatNow() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
      d.getHours()
    )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  function buildQuery(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      const s = String(v).trim();
      if (s === "") return;
      sp.set(k, s);
    });
    const q = sp.toString();
    return q ? `?${q}` : "";
  }

  // 防止 XSS
  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // 兼容不同字段名取值
  function pick(obj, keys, defVal = "-") {
    if (!obj) return defVal;
    for (const k of keys) {
      if (!(k in obj)) continue;
      const v = obj[k];
      if (v === 0) return 0; // 0 合法
      if (v === undefined || v === null) continue;
      const s = String(v).trim();
      if (s !== "") return v;
    }
    return defVal;
  }

  function fmtCoord(v) {
    if (v === "-" || v === "" || v === null || v === undefined) return "-";
    const n = Number(v);
    if (Number.isNaN(n)) return escapeHtml(String(v));
    return n.toFixed(6);
  }

  function fmtTime(v) {
    if (!v || v === "-") return "-";
    return escapeHtml(String(v));
  }

  function statusBadge(statusRaw) {
    const s = String(statusRaw || "").toLowerCase().trim();
    if (s === "online") return `<span class="badge text-bg-success">在线</span>`;
    if (s === "offline") return `<span class="badge text-bg-secondary">离线</span>`;
    if (s === "alarm") return `<span class="badge text-bg-danger">告警</span>`;
    if (s === "normal") return `<span class="badge text-bg-success">正常</span>`; // 兼容旧数据
    return `<span class="badge text-bg-light text-dark">${escapeHtml(statusRaw || "-")}</span>`;
  }

  // ---------- CSRF + fetch ----------
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const m = meta?.getAttribute("content") || "";
    if (m && m !== "NOTPROVIDED") return m;

    // 兜底：从 cookie 读 csrftoken
    const name = "csrftoken=";
    const parts = document.cookie ? document.cookie.split(";") : [];
    for (const p of parts) {
      const s = p.trim();
      if (s.startsWith(name)) return decodeURIComponent(s.slice(name.length));
    }
    return "";
  }

  async function fetchJson(url, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");

    const isUnsafe = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);
    if (isUnsafe) {
      const csrf = getCsrfToken();
      if (csrf) headers.set("X-CSRFToken", csrf);
    }

    let body = options.body;
    if (body && typeof body === "object" && !(body instanceof FormData)) {
      headers.set("Content-Type", "application/json; charset=utf-8");
      body = JSON.stringify(body);
    }

    const resp = await fetch(url, {
      credentials: "same-origin",
      ...options,
      method,
      headers,
      body,
    });

    let data = null;
    try {
      data = await resp.json();
    } catch (e) {
      const text = await resp.text().catch(() => "");
      throw new Error(`接口返回非 JSON：${text.slice(0, 200)}`);
    }

    if (!resp.ok) throw new Error(data?.error || `HTTP ${resp.status}`);
    if (!data?.ok) throw new Error(data?.error || "API ok=false");
    return data;
  }

  // ---------- chart ----------
  function ensureChart() {
    const el = document.getElementById("trendChart");
    if (!el) return null;

    if (el.clientHeight === 0) el.style.height = "360px";

    if (!window.echarts) {
      console.error("echarts 未加载：请确认 HTML 在 dashboard.js 之前引入 echarts.min.js");
      return null;
    }

    if (!state.chart) state.chart = echarts.init(el);
    return state.chart;
  }

  function showChartMessage(msg) {
    const chart = ensureChart();
    if (!chart) return;

    chart.clear();
    chart.setOption(
      {
        xAxis: { type: "category", data: [] },
        yAxis: { type: "value" },
        series: [],
        graphic: [
          {
            type: "text",
            left: "center",
            top: "middle",
            style: { text: msg || "请选择设备后查看趋势", fontSize: 14 },
          },
        ],
      },
      true
    );

    setText("kpiTotal", "0");
    setText("kpiTotalSub", "折线数量：0");
  }

  function mapSeriesName(rawName) {
    const k = String(rawName || "").trim();
    return METRIC_LABEL_MAP[k] || k;
  }

  function renderTrend(trend) {
    const chart = ensureChart();
    if (!chart) return;

    const x = trend.x || [];
    const rawSeries = Array.isArray(trend.series) ? trend.series : [];
    const validSeries = rawSeries.filter((s) => Array.isArray(s?.data) && s.data.length > 0);

    const series = validSeries.map((s) => ({
      name: mapSeriesName(s.name),
      type: "line",
      smooth: true,
      showSymbol: false,
      data: s.data,
    }));

    chart.setOption(
      {
        tooltip: { trigger: "axis" },
        legend: { top: 0, type: "scroll" },
        grid: { left: 30, right: 18, top: 40, bottom: 25, containLabel: true },
        xAxis: { type: "category", data: x },
        yAxis: { type: "value" },
        series,
        graphic: [],
      },
      true
    );

    const lineCount = series.length;
    setText("kpiTotal", String(lineCount));
    setText("kpiTotalSub", `折线数量：${lineCount}`);
    setText("lastUpdated", `最后更新：${formatNow()}`);
  }

  // ---------- 高德网页定位 ----------
  function buildAmapMarkerUrl(lng, lat, title = "设备位置", coord = AMAP_COORD_SYS) {
    const ln = Number(lng);
    const lt = Number(lat);
    if (!Number.isFinite(ln) || !Number.isFinite(lt)) return "";
    return (
      `https://uri.amap.com/marker?position=${ln},${lt}` +
      `&name=${encodeURIComponent(String(title || "设备位置"))}` +
      `&coordinate=${encodeURIComponent(coord)}` +
      `&callnative=0`
    );
  }

  function openAmapByLngLat({ lng, lat, name, location }) {
    const url = buildAmapMarkerUrl(lng, lat, name || "设备位置");
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const q = String(location || name || "").trim();
    if (q) {
      window.open(`https://www.amap.com/search?query=${encodeURIComponent(q)}`, "_blank", "noopener,noreferrer");
    } else {
      alert("该设备没有有效经纬度，无法定位。");
    }
  }

  // ---------- Edit/Delete Modals ----------
  function ensureEditModal() {
    const el = document.getElementById("editDeviceModal");
    if (!el || !window.bootstrap?.Modal) return null;
    if (!state.editModal) state.editModal = new bootstrap.Modal(el);
    return state.editModal;
  }

  function ensureDeleteModal() {
    const el = document.getElementById("deleteDeviceModal");
    if (!el || !window.bootstrap?.Modal) return null;
    if (!state.deleteModal) state.deleteModal = new bootstrap.Modal(el);
    return state.deleteModal;
  }

  function showEditError(msg) {
    const el = document.getElementById("editErr");
    if (!el) return;
    if (!msg) {
      el.classList.add("d-none");
      el.textContent = "-";
    } else {
      el.classList.remove("d-none");
      el.textContent = msg;
    }
  }

  function showDeleteError(msg) {
    const el = document.getElementById("deleteErr");
    if (!el) return;
    if (!msg) {
      el.classList.add("d-none");
      el.textContent = "-";
    } else {
      el.classList.remove("d-none");
      el.textContent = msg;
    }
  }

  function toBlankIfDash(v) {
    if (v === "-" || v === null || v === undefined) return "";
    const s = String(v).trim();
    return s === "-" ? "" : s;
  }

  function openEditModalByItem(item) {
    const modal = ensureEditModal();
    if (!modal) return;

    showEditError("");

    const id = pick(item, ["id", "device_id"], "");
    const name = pick(item, ["device_name", "name", "device"], "-");
    // 冷库字段兼容：优先 base_id
    const baseId = pick(item, ["base_id", "cold_room", "coldroom", "cold_room_name", "coldroom_name"], "");
    const status = String(pick(item, ["status", "state"], "") || "").toLowerCase().trim();
    const location = pick(item, ["location", "position", "address"], "");
    const lng = pick(item, ["longitude", "lng", "lon"], "");
    const lat = pick(item, ["latitude", "lat"], "");

    const elId = document.getElementById("editDeviceId");
    const elName = document.getElementById("editDeviceName");
    const elBaseId = document.getElementById("editBaseId"); // 修复：使用正确的ID
    const elStatus = document.getElementById("editStatus");
    const elLoc = document.getElementById("editLocation");
    const elLng = document.getElementById("editLongitude");
    const elLat = document.getElementById("editLatitude");

    if (elId) elId.value = String(id ?? "");
    if (elName) elName.value = String(name ?? "");
    if (elBaseId) elBaseId.value = toBlankIfDash(baseId);
    if (elLoc) elLoc.value = toBlankIfDash(location);
    if (elLng) elLng.value = toBlankIfDash(lng);
    if (elLat) elLat.value = toBlankIfDash(lat);

    // ORM 版本只允许 online/offline/alarm（normal 仅展示兼容）
    const allowed = new Set(["", "online", "offline", "alarm"]);
    if (elStatus) elStatus.value = allowed.has(status) ? status : "";

    modal.show();
  }

  function openDeleteModalByItem(item) {
    const modal = ensureDeleteModal();
    if (!modal) return;

    showDeleteError("");

    const id = pick(item, ["id", "device_id"], "");
    const name = pick(item, ["device_name", "name", "device"], "-");

    const elId = document.getElementById("deleteDeviceId");
    const elName = document.getElementById("deleteDeviceName");

    if (elId) elId.value = String(id ?? "");
    if (elName) elName.textContent = String(name ?? "-");

    modal.show();
  }

  function getItemById(id) {
    const key = String(id ?? "");
    if (!key) return null;
    return state.tableIndex.get(key) || null;
  }

  // ---------- table ----------
  function getTableFilters() {
    // filterColdRoom 实际当作 base_id 过滤值
    const baseId = document.getElementById("filterColdRoom")?.value || "";
    const status = document.getElementById("filterStatus")?.value || "";
    const device = document.getElementById("filterDevice")?.value || "";
    const keyword = document.getElementById("keyword")?.value || "";
    const dateFrom = document.getElementById("dateFrom")?.value || "";
    const dateTo = document.getElementById("dateTo")?.value || "";
    return { baseId, status, device, keyword, dateFrom, dateTo };
  }

  function renderTableRows(items) {
    const tbody = document.getElementById("tableBody");
    if (!tbody) return;

    // ✅ Edge 兼容性修复：先清空所有子节点，然后使用 insertAdjacentHTML
    while (tbody.firstChild) {
      tbody.removeChild(tbody.firstChild);
    }

    if (!items || items.length === 0) {
      // 使用 insertAdjacentHTML 而不是 innerHTML，提高 Edge 兼容性
      tbody.insertAdjacentHTML("beforeend", `
        <tr>
          <td colspan="9" class="text-center muted py-4">暂无数据</td>
        </tr>
      `);
      return;
    }

    // ✅ Edge 兼容性修复：使用 insertAdjacentHTML 逐个添加行
    const rowsHtml = items
      .map((it) => {
        const idRaw = pick(it, ["id", "device_id"], "");
        const idKey = String(idRaw ?? "");
        const idShow = escapeHtml(idRaw || "-");

        const nameRaw = pick(it, ["device_name", "name", "device"], "-");
        const nameShow = escapeHtml(String(nameRaw));

        // 显示 base_id（兼容多种字段名）
        const baseIdShow = escapeHtml(
          String(pick(it, ["base_id", "cold_room", "coldroom", "cold_room_name", "coldroom_name"], "-"))
        );

        const lngRaw = pick(it, ["longitude", "lng", "lon"], "-");
        const latRaw = pick(it, ["latitude", "lat"], "-");
        const lngShow = fmtCoord(lngRaw);
        const latShow = fmtCoord(latRaw);

        const locationRaw = pick(it, ["location", "position", "address"], "-");
        const locationShow = escapeHtml(String(locationRaw));

        const status = pick(it, ["status", "state"], "-");
        const lastSeen = fmtTime(pick(it, ["last_seen", "last_report_time", "updated_at"], "-"));
        const code = escapeHtml(String(pick(it, ["code", "sn", "device_code"], "")));

        return `
          <tr class="js-row-edit" data-id="${escapeHtml(idKey)}">
            <td>${idShow}</td>
            <td>
              <div class="fw-semibold">${nameShow}</div>
              ${code ? `<div class="muted small">${code}</div>` : ``}
            </td>
            <td>${baseIdShow}</td>

            <td>${lngShow}</td>
            <td>${latShow}</td>

            <td>${locationShow}</td>
            <td>${statusBadge(status)}</td>
            <td>${lastSeen}</td>

            <td>
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-sm btn-outline-primary js-view-trend" data-device="${escapeHtml(nameRaw)}">
                  <i class="fa-solid fa-chart-line me-1"></i>趋势
                </button>

                <button
                  class="btn btn-sm btn-outline-secondary js-open-map"
                  data-name="${escapeHtml(nameRaw)}"
                  data-lng="${escapeHtml(lngRaw)}"
                  data-lat="${escapeHtml(latRaw)}"
                  data-location="${escapeHtml(locationRaw)}"
                >
                  <i class="fa-solid fa-location-dot me-1"></i>地图
                </button>

                <button class="btn btn-sm btn-outline-success js-edit-device" data-id="${escapeHtml(idKey)}">
                  <i class="fa-solid fa-pen-to-square me-1"></i>编辑
                </button>

                <button class="btn btn-sm btn-outline-danger js-delete-device" data-id="${escapeHtml(idKey)}">
                  <i class="fa-solid fa-trash-can me-1"></i>删除
                </button>
              </div>

              <div class="muted small mt-1">提示：也可以直接点击整行进入编辑</div>
            </td>
          </tr>
        `;
      })
      .join("");

    // ✅ Edge 兼容性修复：使用 insertAdjacentHTML 一次性插入所有行
    tbody.insertAdjacentHTML("beforeend", rowsHtml);

    // 趋势联动
    tbody.querySelectorAll(".js-view-trend").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const dev = btn.dataset.device || "";
        if (!dev) return;

        state.selectedDevice = dev;

        const selKpi = document.getElementById("kpiDeviceSelect");
        const selFilter = document.getElementById("filterDevice");
        if (selKpi) selKpi.value = dev;
        if (selFilter) selFilter.value = dev;

        await loadTrend();
      });
    });

    // 地图按钮
    tbody.querySelectorAll(".js-open-map").forEach((btn) => {
      btn.addEventListener("click", () => {
        const name = btn.dataset.name || "";
        const lng = btn.dataset.lng || "";
        const lat = btn.dataset.lat || "";
        const location = btn.dataset.location || "";
        openAmapByLngLat({ lng, lat, name, location });
      });
    });

    // 编辑按钮
    tbody.querySelectorAll(".js-edit-device").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id || "";
        const item = getItemById(id);
        if (!item) return;
        openEditModalByItem(item);
      });
    });

    // 删除按钮
    tbody.querySelectorAll(".js-delete-device").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id || "";
        const item = getItemById(id);
        if (!item) return;
        openDeleteModalByItem(item);
      });
    });

    // 点击整行进入编辑（排除按钮/输入控件）
    tbody.querySelectorAll("tr.js-row-edit").forEach((tr) => {
      tr.addEventListener("click", (e) => {
        const t = e.target;
        if (t && (t.closest("button") || t.closest("a") || t.closest("input") || t.closest("select"))) return;
        const id = tr.dataset.id || "";
        const item = getItemById(id);
        if (!item) return;
        openEditModalByItem(item);
      });
    });
  }

  function renderPageInfo() {
    const pageInfo = document.getElementById("pageInfo");
    if (!pageInfo) return;

    const total = state.tableTotal || 0;
    const page = state.tablePage || 1;
    const ps = state.tablePageSize || 10;

    const start = total === 0 ? 0 : (page - 1) * ps + 1;
    const end = Math.min(page * ps, total);

    pageInfo.textContent = `第 ${page} 页，显示 ${start}-${end} / 共 ${total} 条`;
  }

  async function loadDeviceTable({ resetPage = false } = {}) {
    if (document.hidden) return;
    if (state.inFlightTable) return;

    state.inFlightTable = true;
    if (resetPage) state.tablePage = 1;

    try {
      const filters = getTableFilters();

      // ✅ 纯 ORM 版建议后端收 base_id；
      // 同时带上 cold_room 兼容旧后端（可删除）
      const q = buildQuery({
        page: state.tablePage,
        page_size: state.tablePageSize,

        base_id: filters.baseId,
        status: filters.status,
        device_name: filters.device || "",
        keyword: filters.keyword,
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
      });

      const data = await fetchJson(API.deviceList + q);

      const items = data.items || data.devices || [];
      const total = data.total ?? data.count ?? (Array.isArray(items) ? items.length : 0);

      // 建索引：id -> item
      state.tableIndex.clear();
      for (const it of items) {
        const idRaw = pick(it, ["id", "device_id"], "");
        const key = String(idRaw ?? "");
        if (key) state.tableIndex.set(key, it);
      }

      state.tableTotal = Number(total) || 0;
      renderTableRows(items);
      renderPageInfo();

      // 更新 KPI
      const kpi = data.kpi || data.summary || null;
      if (kpi) {
        const online = kpi.online ?? "-";
        const offline = kpi.offline ?? "-";
        const alarm = kpi.alarm ?? "-";

        setText("kpiOnline", String(online));
        setText("kpiOffline", String(offline));

        setText("kpiOnlineMini", String(online));
        setText("kpiOfflineMini", String(offline));
        setText("kpiAlarmMini", String(alarm));
      }

      setText("lastUpdated", `最后更新：${formatNow()}`);
    } catch (e) {
      console.error(e);

      const tbody = document.getElementById("tableBody");
      if (tbody) {
        // Edge 兼容性修复：先清空再使用 insertAdjacentHTML
        while (tbody.firstChild) {
          tbody.removeChild(tbody.firstChild);
        }
        tbody.insertAdjacentHTML("beforeend", `
          <tr>
            <td colspan="9" class="text-center text-danger py-4">
              表格加载失败：${escapeHtml(e.message)}
            </td>
          </tr>
        `);
      }

      state.tableTotal = 0;
      renderPageInfo();
    } finally {
      state.inFlightTable = false;
    }
  }

  // ---------- API ----------
  function fillSelect(selectEl, names, placeholder = "全部设备") {
    selectEl.innerHTML = "";
    const optAll = document.createElement("option");
    optAll.value = "";
    optAll.textContent = placeholder;
    selectEl.appendChild(optAll);

    for (const name of names) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      selectEl.appendChild(opt);
    }
  }

  async function loadDeviceNames() {
    const selKpi = document.getElementById("kpiDeviceSelect");
    const selFilter = document.getElementById("filterDevice");

    if (selKpi) selKpi.innerHTML = '<option value="">加载中...</option>';
    if (selFilter) selFilter.innerHTML = '<option value="">加载中...</option>';

    const data = await fetchJson(API.deviceNames);
    const names = data.device_names || [];

    let finalVal = names.includes(state.selectedDevice) ? state.selectedDevice : "";
    if (!finalVal && names.length) finalVal = names[0];

    if (selKpi) {
      fillSelect(selKpi, names, "全部设备");
      selKpi.value = finalVal;
    }
    if (selFilter) {
      fillSelect(selFilter, names, "全部设备");
      selFilter.value = finalVal;
    }

    state.selectedDevice = finalVal;
    setText("lastUpdated", `最后更新：${formatNow()}`);
  }

  async function loadTrend() {
    if (document.hidden) return;
    if (state.inFlightTrend) return;

    state.inFlightTrend = true;

    try {
      if (!state.selectedDevice) {
        showChartMessage("请选择设备后查看趋势");
        return;
      }

      const q = buildQuery({
        range: state.range,
        device_name: state.selectedDevice,
        limit: 500,
      });

      const data = await fetchJson(API.trend + q);

      if (!data.x || data.x.length === 0) {
        showChartMessage(data.note || "该设备暂无可用趋势数据");
        return;
      }

      renderTrend(data);
    } catch (e) {
      console.error(e);
      showChartMessage(`加载失败：${e.message}`);
      setText("lastUpdated", `最后更新：失败（${formatNow()}）`);
    } finally {
      state.inFlightTrend = false;
    }
  }

  function startPolling() {
    stopPolling();
    state.timer = setInterval(() => {
      loadTrend();
    }, state.refreshMs);
  }

  function stopPolling() {
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
    }
  }

  // ---------- quick search ----------
  function initQuickSearch() {
    const input = document.getElementById("quickSearch");
    const grid = document.getElementById("quickGrid");
    const noMatch = document.getElementById("quickNoMatch");
    const hint = document.getElementById("quickSearchHint");
    if (!input || !grid) return;

    function norm(s) {
      return String(s || "")
        .toLowerCase()
        .trim()
        .replace(/\s+/g, "")
        .replace(/[-_]/g, "");
    }

    function getPinyinTokens(text) {
      const raw = String(text || "");
      const P = window.pinyinPro;
      if (!P || typeof P.pinyin !== "function") {
        return { py: "", ini: "" };
      }
      const py = norm(P.pinyin(raw, { toneType: "none" }));
      const ini = norm(P.pinyin(raw, { pattern: "initial" }));
      return { py, ini };
    }

    const items = Array.from(grid.querySelectorAll(".quick-item"));
    for (const a of items) {
      const text = a.textContent || "";
      const { py, ini } = getPinyinTokens(text);
      a.dataset.qText = norm(text);
      a.dataset.qPinyin = py;
      a.dataset.qInitial = ini;
    }

    function applyFilter() {
      const q = norm(input.value);
      let shown = 0;

      for (const a of items) {
        const t = a.dataset.qText || "";
        const py = a.dataset.qPinyin || "";
        const ini = a.dataset.qInitial || "";
        const ok = !q || t.includes(q) || py.includes(q) || ini.includes(q);
        a.classList.toggle("d-none", !ok);
        if (ok) shown += 1;
      }

      if (noMatch) noMatch.classList.toggle("d-none", shown !== 0);
      if (hint) {
        hint.textContent = q
          ? `匹配到 ${shown} 个快捷入口（支持拼音/首字母）`
          : "输入后将只显示匹配的快捷入口（支持拼音/首字母）";
      }
    }

    input.addEventListener("input", applyFilter);
    applyFilter();
  }

  // ---------- in-page mini page (Modal) ----------
  function initQuickPanels() {
    const modalEl = document.getElementById("quickModal");
    const titleEl = document.getElementById("quickModalTitle");
    const bodyEl = document.getElementById("quickModalBody");
    const linkEl = document.getElementById("quickModalLink");
    if (!modalEl || !titleEl || !bodyEl || !window.bootstrap?.Modal) return;

    const modal = new bootstrap.Modal(modalEl);

    const PANELS = {
      docs: { title: "文档示例", linkText: "打开完整页面", html: `<div class="mb-2"><b>这里是页内文档示例</b></div>` },
      help: { title: "帮助", linkText: "打开完整页面", html: `<div class="mb-2"><b>这里是页内帮助中心</b></div>` },
    };

    document.querySelectorAll(".js-open-panel").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();

        const key = a.dataset.panel || "";
        const cfg = PANELS[key];
        if (!cfg) return;

        titleEl.textContent = cfg.title;
        bodyEl.innerHTML = cfg.html;

        const href = a.getAttribute("href") || "#";
        if (linkEl) {
          if (href && href !== "#") {
            linkEl.classList.remove("d-none");
            linkEl.href = href;
            linkEl.textContent = cfg.linkText || "打开完整页面";
          } else {
            linkEl.classList.add("d-none");
          }
        }

        modal.show();
      });
    });
  }

  // ---------- save edit / delete ----------
  async function saveDeviceEdit() {
    if (state.inFlightSave) return;
    state.inFlightSave = true;

    const btn = document.getElementById("btnSaveDeviceEdit");
    if (btn) btn.disabled = true;

    try {
      showEditError("");

      const id = document.getElementById("editDeviceId")?.value || "";
      if (!id) throw new Error("缺少设备 ID");

      const baseId = (document.getElementById("editBaseId")?.value || "").trim(); // 修复：使用正确的ID
      let status = (document.getElementById("editStatus")?.value || "").trim().toLowerCase();
      const location = document.getElementById("editLocation")?.value || "";
      const lngStr = (document.getElementById("editLongitude")?.value || "").trim();
      const latStr = (document.getElementById("editLatitude")?.value || "").trim();

      let longitude = null;
      let latitude = null;

      if (lngStr !== "") {
        const n = Number(lngStr);
        if (!Number.isFinite(n)) throw new Error("经度必须是数字");
        longitude = n;
      }
      if (latStr !== "") {
        const n = Number(latStr);
        if (!Number.isFinite(n)) throw new Error("纬度必须是数字");
        latitude = n;
      }

      // ORM Device.status 不含 normal
      if (status === "normal") status = "online";
      if (status && !["online", "offline", "alarm"].includes(status)) {
        throw new Error("状态只允许：online / offline / alarm");
      }

      const payload = {
        id: id,
        base_id: baseId,
        status: status,
        location: location,
        longitude: longitude, // null 表示清空（由后端决定）
        latitude: latitude,
      };

      await fetchJson(API.deviceUpdate, { method: "POST", body: payload });

      const modal = ensureEditModal();
      modal?.hide();

      await loadDeviceTable({ resetPage: false });

      setText("lastUpdated", `最后更新：${formatNow()}`);
    } catch (e) {
      console.error(e);
      showEditError(e.message || "保存失败");
    } finally {
      state.inFlightSave = false;
      if (btn) btn.disabled = false;
    }
  }

  async function confirmDeleteDevice() {
    if (state.inFlightDelete) return;
    state.inFlightDelete = true;

    const btn = document.getElementById("btnConfirmDelete");
    if (btn) btn.disabled = true;

    try {
      showDeleteError("");

      const id = document.getElementById("deleteDeviceId")?.value || "";
      const name = document.getElementById("deleteDeviceName")?.textContent || "";

      if (!id) throw new Error("缺少设备 ID");

      await fetchJson(API.deviceDelete, { method: "POST", body: { id } });

      const modal = ensureDeleteModal();
      modal?.hide();

      if (name && state.selectedDevice === name) {
        state.selectedDevice = "";
        const selKpi = document.getElementById("kpiDeviceSelect");
        const selFilter = document.getElementById("filterDevice");
        if (selKpi) selKpi.value = "";
        if (selFilter) selFilter.value = "";
        showChartMessage("设备已删除，请重新选择设备");
      }

      await loadDeviceNames();

      await loadDeviceTable({ resetPage: false });
      const maxPage = Math.max(1, Math.ceil((state.tableTotal || 0) / state.tablePageSize));
      if (state.tablePage > maxPage) {
        state.tablePage = maxPage;
        await loadDeviceTable({ resetPage: false });
      }

      setText("lastUpdated", `最后更新：${formatNow()}`);
    } catch (e) {
      console.error(e);
      showDeleteError(e.message || "删除失败");
    } finally {
      state.inFlightDelete = false;
      if (btn) btn.disabled = false;
    }
  }

  // ---------- events ----------
  function bindEvents() {
    const selKpi = document.getElementById("kpiDeviceSelect");
    const selFilter = document.getElementById("filterDevice");

    if (selKpi && selFilter) {
      selKpi.addEventListener("change", async () => {
        state.selectedDevice = selKpi.value || "";
        selFilter.value = state.selectedDevice;
        await loadTrend();
      });

      selFilter.addEventListener("change", async () => {
        state.selectedDevice = selFilter.value || "";
        selKpi.value = state.selectedDevice;
        await loadTrend();
      });
    }

    document.querySelectorAll("[data-range]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        state.range = btn.dataset.range || "30d";
        await loadTrend();
      });
    });

    // 刷新按钮
    const btnRefreshAll = document.getElementById("btnRefreshAll");
    if (btnRefreshAll) {
      btnRefreshAll.addEventListener("click", async () => {
        await loadDeviceNames();
        await loadTrend();
        await loadDeviceTable({ resetPage: true });
      });
    }

    // 表格查询
    const btnSearch = document.getElementById("btnSearch");
    if (btnSearch) {
      btnSearch.addEventListener("click", async () => {
        await loadDeviceTable({ resetPage: true });
      });
    }

    // 表格重置
    const btnReset = document.getElementById("btnReset");
    if (btnReset) {
      btnReset.addEventListener("click", async () => {
        const coldRoom = document.getElementById("filterColdRoom");
        const status = document.getElementById("filterStatus");
        const device = document.getElementById("filterDevice");
        const keyword = document.getElementById("keyword");
        const dateFrom = document.getElementById("dateFrom");
        const dateTo = document.getElementById("dateTo");

        if (coldRoom) coldRoom.value = "";
        if (status) status.value = "";
        if (device) device.value = "";
        if (keyword) keyword.value = "";
        if (dateFrom) dateFrom.value = "";
        if (dateTo) dateTo.value = "";

        await loadDeviceTable({ resetPage: true });
      });
    }

    // 分页
    const btnPrev = document.getElementById("btnPrev");
    const btnNext = document.getElementById("btnNext");

    if (btnPrev) {
      btnPrev.addEventListener("click", async () => {
        if (state.tablePage <= 1) return;
        state.tablePage -= 1;
        await loadDeviceTable();
      });
    }

    if (btnNext) {
      btnNext.addEventListener("click", async () => {
        const maxPage = Math.max(1, Math.ceil((state.tableTotal || 0) / state.tablePageSize));
        if (state.tablePage >= maxPage) return;
        state.tablePage += 1;
        await loadDeviceTable();
      });
    }

    // 编辑保存按钮
    const btnSaveDeviceEdit = document.getElementById("btnSaveDeviceEdit");
    if (btnSaveDeviceEdit) {
      btnSaveDeviceEdit.addEventListener("click", saveDeviceEdit);
    }

    // 删除确认按钮
    const btnConfirmDelete = document.getElementById("btnConfirmDelete");
    if (btnConfirmDelete) {
      btnConfirmDelete.addEventListener("click", confirmDeleteDevice);
    }

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        stopPolling();
      } else {
        loadTrend();
        startPolling();
      }
    });

    window.addEventListener("resize", () => state.chart && state.chart.resize());
  }

  async function init() {
    bindEvents();
    initQuickSearch();
    initQuickPanels();
    ensureChart();

    try {
      await loadDeviceNames();
      await loadTrend();
      startPolling();
      await loadDeviceTable({ resetPage: true });
    } catch (e) {
      console.error(e);
      setText("lastUpdated", `最后更新：失败（${formatNow()}）`);
      showChartMessage(`初始化失败：${e.message}`);
      startPolling();
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
