// storageSystem/static/storageSystem/js/dashboard.js
(() => {
  const API = {
    deviceNames: "/storage/api/device-names/",
    trend: "/storage/api/dashboard/trend",
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

  const state = {
    range: "30d",
    selectedDevice: "",
    chart: null,

    inFlightTrend: false,
    timer: null,
    refreshMs: 5000, // 每5秒查询一次
  };

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

  async function fetchJson(url) {
    const resp = await fetch(url, { credentials: "same-origin" });

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

  // ---------- API ----------
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

  // ---------- quick search (pinyin/initial) ----------
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

  // ---------- ✅ in-page mini page (Modal) ----------
  function initQuickPanels() {
    const modalEl = document.getElementById("quickModal");
    const titleEl = document.getElementById("quickModalTitle");
    const bodyEl = document.getElementById("quickModalBody");
    const linkEl = document.getElementById("quickModalLink");
    if (!modalEl || !titleEl || !bodyEl || !window.bootstrap?.Modal) return;

    const modal = new bootstrap.Modal(modalEl);

    // 你可以在这里随时改内容（支持 HTML）
    const PANELS = {
      docs: {
        title: "文档示例",
        linkText: "打开完整页面",
        html: `
          <div class="mb-2"><b>这里是页内文档示例</b></div>
          <div class="muted small mb-3">你可以放：系统说明、接口文档、字段含义、操作指南等。</div>

          <div class="card border-0 bg-light p-3 mb-3">
            <div class="fw-semibold mb-1">常用字段映射</div>
            <ul class="mb-0">
              <li>temperature → 温度</li>
              <li>humidity → 湿度</li>
              <li>co2_ppm → CO₂</li>
              <li>h2_ppm → H2</li>
              <li>co_ppm → CO</li>
              <li>c2h5oh → C₂H₅OH</li>
              <li>voc → VOC</li>
              <li>o2 → O₂</li>
              <li>c2h4 → C₂H₄</li>
            </ul>
          </div>

          <div class="fw-semibold mb-2">使用建议</div>
          <ol class="mb-0">
            <li>在“设备选择”下拉框选择设备，趋势图自动刷新。</li>
            <li>趋势图每 5 秒刷新一次，切到后台会暂停，回到前台会恢复。</li>
            <li>快捷入口支持拼音/首字母搜索。</li>
          </ol>
        `,
      },
      help: {
        title: "帮助",
        linkText: "打开完整页面",
        html: `
          <div class="mb-2"><b>这里是页内帮助中心</b></div>
          <div class="muted small mb-3">常见问题可以直接写在这里，不必跳转页面。</div>

          <div class="accordion" id="helpAcc">
            <div class="accordion-item">
              <h2 class="accordion-header" id="h1">
                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#c1">
                  1) 为什么趋势图不显示？
                </button>
              </h2>
              <div id="c1" class="accordion-collapse collapse show" data-bs-parent="#helpAcc">
                <div class="accordion-body">
                  <ul class="mb-0">
                    <li>确认页面已引入 ECharts，并且在 dashboard.js 之前。</li>
                    <li>确认 trendChart 容器高度不为 0（JS 已做兜底）。</li>
                    <li>打开控制台看是否有接口报错或 JS 报错。</li>
                  </ul>
                </div>
              </div>
            </div>

            <div class="accordion-item">
              <h2 class="accordion-header" id="h2">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#c2">
                  2) 为什么我切换设备后数据还是旧的？
                </button>
              </h2>
              <div id="c2" class="accordion-collapse collapse" data-bs-parent="#helpAcc">
                <div class="accordion-body">
                  选择设备会立即请求后端刷新趋势；如果后端缓存或数据写入延迟，请检查接口返回是否更新。
                </div>
              </div>
            </div>
          </div>
        `,
      },
    };

    document.querySelectorAll(".js-open-panel").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();

        const key = a.dataset.panel || "";
        const cfg = PANELS[key];
        if (!cfg) return;

        titleEl.textContent = cfg.title;
        bodyEl.innerHTML = cfg.html;

        // footer link：默认展示“打开完整页面”
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

    const btnRefreshAll = document.getElementById("btnRefreshAll");
    if (btnRefreshAll) {
      btnRefreshAll.addEventListener("click", async () => {
        await loadDeviceNames();
        await loadTrend();
      });
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
    } catch (e) {
      console.error(e);
      setText("lastUpdated", `最后更新：失败（${formatNow()}）`);
      showChartMessage(`初始化失败：${e.message}`);
      startPolling();
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
