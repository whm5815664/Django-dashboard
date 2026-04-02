// storageSystem/static/storageSystem/js/dashboard.js
(() => {
  const API = {
    deviceNames: "/storage/api/device-names/",
    trend: "/storage/api/dashboard/trend/",
    deviceList: "/storage/api/dashboard/devices/",
    deviceUpdate: "/storage/api/dashboard/device-update/",
    deviceDelete: "/storage/api/dashboard/device-delete/",
  };

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

  const MEDIA_BASE_URL = "http://47.99.61.189:8175/media/";

  const state = {
    range: "30d",

    // 趋势图选中的设备
    selectedDeviceId: "",
    selectedDeviceName: "",

    chart: null,
    inFlightTrend: false,
    timer: null,
    refreshMs: 5000,

    // 明细表分页
    tablePage: 1,
    tablePageSize: 10,
    tableTotal: 0,
    inFlightTable: false,

    // 表格数据索引：id -> item
    tableIndex: new Map(),

    // Modals
    editModal: null,
    deleteModal: null,

    inFlightSave: false,
    inFlightDelete: false,

    // URL 注入的过滤条件
    filterDeviceCode: "",
    filterBaseId: "",
  };

  // ✅ 从模板注入（dashboard.html 里设置的 window.__FILTER_*__）
  state.filterDeviceCode = window.__FILTER_DEVICE_CODE__ || "";
  state.filterBaseId = window.__FILTER_BASE_ID__ || ""; // ✅ 关键：base_id = environment_data.pigsty_id

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

  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function pick(obj, keys, defVal = "-") {
    if (!obj) return defVal;
    for (const k of keys) {
      if (!(k in obj)) continue;
      const v = obj[k];
      if (v === 0) return 0;
      if (v === undefined || v === null) continue;
      const s = String(v).trim();
      if (s !== "") return v;
    }
    return defVal;
  }

  function fmtTime(v) {
    if (!v || v === "-") return "-";
    return escapeHtml(String(v));
  }

  // ---------- CSRF + fetch ----------
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const m = meta?.getAttribute("content") || "";
    if (m && m !== "NOTPROVIDED") return m;

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

  // ---------- Modals ----------
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

  function openEditModalByItem(item) {
    const modal = ensureEditModal();
    if (!modal) return;

    showEditError("");

    const id = pick(item, ["id"], "");
    const name = pick(item, ["name"], "-");
    const deviceCode = pick(item, ["device_code"], "");
    const description = pick(item, ["description"], "");
    const collectInterval = pick(item, ["collect_interval"], "");
    const createdAt = pick(item, ["created_at"], "");
    const updatedAt = pick(item, ["updated_at"], "");

    const elId = document.getElementById("editDeviceId");
    const elName = document.getElementById("editDeviceName");
    const elCode = document.getElementById("editDeviceCode");
    const elDesc = document.getElementById("editDescription");
    const elCI = document.getElementById("editCollectInterval");
    const elCreatedAt = document.getElementById("editCreatedAt");
    const elUpdatedAt = document.getElementById("editUpdatedAt");

    if (elId) elId.value = String(id ?? "");
    if (elName) elName.value = String(name ?? "");
    if (elCode) elCode.value = deviceCode === "-" ? "" : String(deviceCode ?? "");
    if (elDesc) elDesc.value = description === "-" ? "" : String(description ?? "");
    if (elCI) elCI.value = collectInterval === "-" ? "" : String(collectInterval ?? "");
    if (elCreatedAt) elCreatedAt.value = createdAt === "-" ? "" : String(createdAt ?? "");
    if (elUpdatedAt) elUpdatedAt.value = updatedAt === "-" ? "" : String(updatedAt ?? "");

    modal.show();
  }

  function openDeleteModalByItem(item) {
    const modal = ensureDeleteModal();
    if (!modal) return;

    showDeleteError("");

    const id = pick(item, ["id"], "");
    const name = pick(item, ["name"], "-");

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

  function openReadingsPageByItem(item) {
    if (!item) return;

    const id = pick(item, ["id"], "");
    if (!id) return;

    const sp = new URLSearchParams();
    if (state.filterBaseId) sp.set("base_id", state.filterBaseId);

    const q = sp.toString() ? `?${sp.toString()}` : "";
    window.location.href = `/storage/device/${id}/readings/${q}`;
  }

  // ---------- table ----------
  function getTableFilters() {
    const deviceCode = document.getElementById("filterDeviceCode")?.value || state.filterDeviceCode || "";
    const keyword = document.getElementById("keyword")?.value || "";
    const dateFrom = document.getElementById("dateFrom")?.value || "";
    const dateTo = document.getElementById("dateTo")?.value || "";
    return { deviceCode, keyword, dateFrom, dateTo };
  }

  function fillDeviceCodeSelectFromItems(items) {
    const sel = document.getElementById("filterDeviceCode");
    if (!sel) return;

    if (sel.options && sel.options.length > 1) return;

    const current = sel.value || state.filterDeviceCode || "";
    const codes = new Set();
    for (const it of items || []) {
      const c = String(pick(it, ["device_code"], "") || "").trim();
      if (c) codes.add(c);
    }

    const arr = Array.from(codes).sort((a, b) => a.localeCompare(b));

    sel.innerHTML = "";
    const optAll = document.createElement("option");
    optAll.value = "";
    optAll.textContent = "全部";
    sel.appendChild(optAll);

    for (const c of arr) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    }

    if (current) sel.value = current;
  }

  function renderTableRows(items) {
    const tbody = document.getElementById("tableBody");
    if (!tbody) return;

    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

    if (!items || items.length === 0) {
      tbody.insertAdjacentHTML(
        "beforeend",
        `<tr><td colspan="8" class="text-center muted py-4">暂无数据</td></tr>`
      );
      return;
    }

    const rowsHtml = items
      .map((it) => {
        const idRaw = pick(it, ["id"], "");
        const idKey = String(idRaw ?? "");
        const idShow = escapeHtml(idRaw || "-");

        const nameRaw = pick(it, ["name"], "-");
        const nameShow = escapeHtml(String(nameRaw));

        const deviceCodeRaw = pick(it, ["device_code"], "-");
        const deviceCodeShow = escapeHtml(String(deviceCodeRaw));

        const descRaw = pick(it, ["description"], "-");
        const descShow = escapeHtml(String(descRaw));

        const createdAt = fmtTime(pick(it, ["created_at"], "-"));
        const updatedAt = fmtTime(pick(it, ["updated_at"], "-"));
        const imagePathRaw = pick(it, ["image_path"], "");
        const imagePathStr = String(imagePathRaw ?? "").trim();
        const imageTd = imagePathStr
          ? `<img
              src="${MEDIA_BASE_URL}${escapeHtml(imagePathStr)}"
              alt="device image"
              style="width:90px;height:70px;object-fit:cover;border-radius:8px;"
              onerror="this.style.display='none';"
            />`
          : "-";

        return `
          <tr class="js-row-edit" data-id="${escapeHtml(idKey)}">
            <td>${idShow}</td>
            <td>${nameShow}</td>
            <td>${deviceCodeShow}</td>
            <td>${descShow}</td>
            <td>${createdAt}</td>
            <td>${updatedAt}</td>
            <td>${imageTd}</td>
            <td>
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-sm btn-outline-primary js-view-trend"
                        data-device-id="${escapeHtml(idKey)}"
                        data-device-name="${escapeHtml(String(nameRaw))}">
                  <i class="fa-solid fa-chart-line me-1"></i>趋势
                </button>

                <button class="btn btn-sm btn-outline-info js-read-device" data-id="${escapeHtml(idKey)}">
                  <i class="fa-solid fa-database me-1"></i>读取
                </button>

                <button class="btn btn-sm btn-outline-success js-edit-device" data-id="${escapeHtml(idKey)}">
                  <i class="fa-solid fa-pen-to-square me-1"></i>编辑
                </button>

                <button class="btn btn-sm btn-outline-danger js-delete-device" data-id="${escapeHtml(idKey)}">
                  <i class="fa-solid fa-trash-can me-1"></i>删除
                </button>
              </div>
            </td>
          </tr>
        `;
      })
      .join("");

    tbody.insertAdjacentHTML("beforeend", rowsHtml);

    // 趋势联动
    tbody.querySelectorAll(".js-view-trend").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.deviceId || "";
        if (!id) return;

        state.selectedDeviceId = id;
        state.selectedDeviceName = btn.dataset.deviceName || "";

        const selKpi = document.getElementById("kpiDeviceSelect");
        if (selKpi) selKpi.value = id;

        await loadTrend();
      });
    });

    // 读取按钮
    tbody.querySelectorAll(".js-read-device").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id || "";
        const item = getItemById(id);
        if (!item) return;
        openReadingsPageByItem(item);
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

        // 二次确认：避免误触导致频繁弹出删除弹窗
        const name = pick(item, ["name"], "-");
        const ok = window.confirm(`确定要删除设备：${String(name)} 吗？删除后无法恢复。`);
        if (!ok) return;

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

  // ---------- device select ----------
  function fillDeviceSelect(selectEl, devices, placeholder = "全部设备") {
    selectEl.innerHTML = "";
    const optAll = document.createElement("option");
    optAll.value = "";
    optAll.textContent = placeholder;
    selectEl.appendChild(optAll);

    for (const d of devices) {
      const opt = document.createElement("option");
      opt.value = String(d.id);
      opt.textContent = d.name || `设备#${d.id}`;
      selectEl.appendChild(opt);
    }
  }

  // ---------- load APIs ----------
  async function loadDeviceNames() {
    const selKpi = document.getElementById("kpiDeviceSelect");
    if (selKpi) selKpi.innerHTML = '<option value="">加载中...</option>';

    // ✅ 带 base_id：只取这个基地有数据的设备
    const q = buildQuery({ base_id: state.filterBaseId });
    const data = await fetchJson(API.deviceNames + q);
    const devices = data.devices || [];

    // 默认选中：如果有上次选中并且仍存在，就用它；否则取第一台；否则为空
    let finalId = "";
    if (state.selectedDeviceId && devices.some((d) => String(d.id) === String(state.selectedDeviceId))) {
      finalId = String(state.selectedDeviceId);
    } else if (devices.length) {
      finalId = String(devices[0].id);
    }

    if (selKpi) {
      fillDeviceSelect(selKpi, devices, "全部设备");
      selKpi.value = finalId;
    }

    state.selectedDeviceId = finalId;
    state.selectedDeviceName = devices.find((d) => String(d.id) === finalId)?.name || "";

    setText("lastUpdated", `最后更新：${formatNow()}`);
  }

  async function loadDeviceTable({ resetPage = false } = {}) {
    if (document.hidden) return;
    if (state.inFlightTable) return;

    state.inFlightTable = true;
    if (resetPage) state.tablePage = 1;

    try {
      const filters = getTableFilters();
      const q = buildQuery({
        page: state.tablePage,
        page_size: state.tablePageSize,

        // ✅ 带 base_id：只展示该基地相关设备
        base_id: state.filterBaseId,

        device_code: filters.deviceCode,
        keyword: filters.keyword,
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
      });

      const data = await fetchJson(API.deviceList + q);
      const items = data.items || data.devices || [];
      const total = data.total ?? data.count ?? (Array.isArray(items) ? items.length : 0);

      state.tableIndex.clear();
      for (const it of items) {
        const idRaw = pick(it, ["id"], "");
        const key = String(idRaw ?? "");
        if (key) state.tableIndex.set(key, it);
      }

      state.tableTotal = Number(total) || 0;
      fillDeviceCodeSelectFromItems(items);

      // URL 注入 device_code
      const selCode = document.getElementById("filterDeviceCode");
      if (selCode && state.filterDeviceCode && !selCode.value) {
        selCode.value = state.filterDeviceCode;
      }

      renderTableRows(items);
      renderPageInfo();
      setText("lastUpdated", `最后更新：${formatNow()}`);
    } catch (e) {
      console.error(e);

      const tbody = document.getElementById("tableBody");
      if (tbody) {
        while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
        tbody.insertAdjacentHTML(
          "beforeend",
          `<tr><td colspan="8" class="text-center text-danger py-4">表格加载失败：${escapeHtml(e.message)}</td></tr>`
        );
      }

      state.tableTotal = 0;
      renderPageInfo();
    } finally {
      state.inFlightTable = false;
    }
  }

  async function loadTrend() {
    if (document.hidden) return;
    if (state.inFlightTrend) return;

    state.inFlightTrend = true;

    try {
      if (!state.selectedDeviceId) {
        showChartMessage("请选择设备后查看趋势");
        return;
      }

      const q = buildQuery({
        range: state.range,
        device_id: state.selectedDeviceId,

        // ✅ 带 base_id：趋势只画该基地 pigsty_id 的记录
        base_id: state.filterBaseId,

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
    state.timer = setInterval(() => loadTrend(), state.refreshMs);
  }

  function stopPolling() {
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
    }
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

      const deviceCode = (document.getElementById("editDeviceCode")?.value || "").trim();
      const description = (document.getElementById("editDescription")?.value || "").trim();
      const ciStr = (document.getElementById("editCollectInterval")?.value || "").trim();

      let collect_interval = null;
      if (ciStr !== "") {
        const n = Number(ciStr);
        if (!Number.isFinite(n)) throw new Error("collect_interval 必须是数字");
        collect_interval = n;
      }

      const payload = {
        id,
        device_code: deviceCode,
        description,
        collect_interval,
      };

      await fetchJson(API.deviceUpdate, { method: "POST", body: payload });

      ensureEditModal()?.hide();
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
      if (!id) throw new Error("缺少设备 ID");

      await fetchJson(API.deviceDelete, { method: "POST", body: { id } });

      ensureDeleteModal()?.hide();

      if (state.selectedDeviceId === String(id)) {
        state.selectedDeviceId = "";
        state.selectedDeviceName = "";
        const selKpi = document.getElementById("kpiDeviceSelect");
        if (selKpi) selKpi.value = "";
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

  // ---------- quick search / panels（保留原逻辑，若页面没这些元素会自动跳过） ----------
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
      if (!P || typeof P.pinyin !== "function") return { py: "", ini: "" };
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

  // ---------- events ----------
  function bindEvents() {
    const selKpi = document.getElementById("kpiDeviceSelect");
    if (selKpi) {
      selKpi.addEventListener("change", async () => {
        state.selectedDeviceId = selKpi.value || "";
        state.selectedDeviceName = selKpi.options[selKpi.selectedIndex]?.textContent || "";
        await loadTrend();
      });
    }

    document.querySelectorAll("[data-range]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        state.range = btn.dataset.range || "30d";
        await loadTrend();
      });
    });

    const btnRefreshAll = document.getElementById("btnRefreshAll");
    if (btnRefreshAll) {
      btnRefreshAll.addEventListener("click", async () => {
        await loadDeviceNames();
        await loadTrend();
        await loadDeviceTable({ resetPage: true });
      });
    }

    const btnSearch = document.getElementById("btnSearch");
    if (btnSearch) {
      btnSearch.addEventListener("click", async () => {
        await loadDeviceTable({ resetPage: true });
      });
    }

    const btnReset = document.getElementById("btnReset");
    if (btnReset) {
      btnReset.addEventListener("click", async () => {
        const codeSel = document.getElementById("filterDeviceCode");
        const keyword = document.getElementById("keyword");
        const dateFrom = document.getElementById("dateFrom");
        const dateTo = document.getElementById("dateTo");

        if (codeSel) codeSel.value = "";
        if (keyword) keyword.value = "";
        if (dateFrom) dateFrom.value = "";
        if (dateTo) dateTo.value = "";

        state.filterDeviceCode = "";
        await loadDeviceTable({ resetPage: true });
      });
    }

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

    const btnSaveDeviceEdit = document.getElementById("btnSaveDeviceEdit");
    if (btnSaveDeviceEdit) btnSaveDeviceEdit.addEventListener("click", saveDeviceEdit);

    const btnConfirmDelete = document.getElementById("btnConfirmDelete");
    if (btnConfirmDelete) btnConfirmDelete.addEventListener("click", confirmDeleteDevice);

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopPolling();
      else {
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

      const selCode = document.getElementById("filterDeviceCode");
      if (selCode && state.filterDeviceCode) selCode.value = state.filterDeviceCode;

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