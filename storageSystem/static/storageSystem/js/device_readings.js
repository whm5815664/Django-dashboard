// storageSystem/static/storageSystem/js/device_readings.js
(() => {
  const API = {
    list: (deviceId, query = "") => `/storage/api/device/${deviceId}/readings/${query}`,
    update: (readingId) => `/storage/api/readings/${readingId}/update/`,
    delete: (readingId) => `/storage/api/readings/${readingId}/delete/`,
  };

  const state = {
    deviceId: window.__DEVICE_ID__ || "",
    baseId: window.__BASE_ID__ || "",
    page: 1,
    pageSize: 10,
    total: 0,
    sortBy: "collected_time",
    sortDir: "desc",
    rowIndex: new Map(),
    editModal: null,
    deleteModal: null,
    inFlight: false,
  };

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function buildQuery(params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      const s = String(v).trim();
      if (!s) return;
      sp.set(k, s);
    });
    const q = sp.toString();
    return q ? `?${q}` : "";
  }

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

  function ensureEditModal() {
    const el = document.getElementById("editReadingModal");
    if (!el || !window.bootstrap?.Modal) return null;
    if (!state.editModal) state.editModal = new bootstrap.Modal(el);
    return state.editModal;
  }

  function ensureDeleteModal() {
    const el = document.getElementById("deleteReadingModal");
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

  function getFilters() {
    return {
      page: state.page,
      page_size: state.pageSize,
      base_id: state.baseId,
      keyword: document.getElementById("keyword")?.value || "",
      date_from: document.getElementById("dateFrom")?.value || "",
      date_to: document.getElementById("dateTo")?.value || "",
      sort_by: state.sortBy,
      sort_dir: state.sortDir,
    };
  }

  function imgTd(url) {
    if (!url) return "-";
    return `
      <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">
        <img src="${escapeHtml(url)}"
             alt="reading image"
             class="reading-img"
             onerror="this.style.display='none'; this.parentNode.innerHTML='-'">
      </a>
    `;
  }

  function renderRows(rows) {
    const tbody = document.getElementById("readingTableBody");
    if (!tbody) return;

    while (tbody.firstChild) tbody.removeChild(tbody.firstChild);

    if (!rows || rows.length === 0) {
      tbody.insertAdjacentHTML(
        "beforeend",
        `<tr><td colspan="13" class="text-center muted py-4">暂无数据</td></tr>`
      );
      return;
    }

    const html = rows.map((row) => {
      return `
        <tr data-id="${escapeHtml(row.id)}">
          <td>${escapeHtml(row.id)}</td>
          <td>${escapeHtml(row.CO2 ?? "-")}</td>
          <td>${escapeHtml(row.temperature ?? "-")}</td>
          <td>${escapeHtml(row.humidity ?? "-")}</td>
          <td>${escapeHtml(row.collected_time ?? "-")}</td>
          <td>${imgTd(row.image)}</td>
          <td>${escapeHtml(row.C2H4 ?? "-")}</td>
          <td>${escapeHtml(row.C2H5OH ?? "-")}</td>
          <td>${escapeHtml(row.CO ?? "-")}</td>
          <td>${escapeHtml(row.H2 ?? "-")}</td>
          <td>${escapeHtml(row.O2 ?? "-")}</td>
          <td>${escapeHtml(row.VOC ?? "-")}</td>
          <td>
            <div class="d-flex flex-wrap gap-2">
              <button class="btn btn-sm btn-outline-success js-edit-reading" data-id="${escapeHtml(row.id)}">
                <i class="fa-solid fa-pen-to-square me-1"></i>编辑
              </button>
              <button class="btn btn-sm btn-outline-danger js-delete-reading" data-id="${escapeHtml(row.id)}">
                <i class="fa-solid fa-trash-can me-1"></i>删除
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    tbody.insertAdjacentHTML("beforeend", html);

    tbody.querySelectorAll(".js-edit-reading").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id || "";
        const row = state.rowIndex.get(String(id));
        if (!row) return;
        openEditModal(row);
      });
    });

    tbody.querySelectorAll(".js-delete-reading").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id || "";
        const row = state.rowIndex.get(String(id));
        if (!row) return;
        openDeleteModal(row);
      });
    });
  }

  function renderPageInfo() {
    const total = state.total || 0;
    const page = state.page || 1;
    const ps = state.pageSize || 10;
    const start = total === 0 ? 0 : (page - 1) * ps + 1;
    const end = Math.min(page * ps, total);
    setText("pageInfo", `第 ${page} 页，显示 ${start}-${end} / 共 ${total} 条`);
  }

  function renderSortIndicators() {
    document.querySelectorAll("th.sortable").forEach((th) => {
      const sortKey = th.dataset.sort;
      const indicator = th.querySelector(".sort-indicator");
      if (!indicator) return;

      if (sortKey === state.sortBy) {
        indicator.textContent = state.sortDir === "asc" ? "▲" : "▼";
      } else {
        indicator.textContent = "";
      }
    });
  }

  function formatNow() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  function toDatetimeLocalString(v) {
    if (!v) return "";
    const text = String(v).trim();
    if (!text) return "";

    const normalized = text.replace(" ", "T");
    const d = new Date(normalized);
    if (Number.isNaN(d.getTime())) return "";

    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function openEditModal(row) {
    showEditError("");

    document.getElementById("editId").value = row.id ?? "";
    document.getElementById("editCO2").value = row.CO2 ?? "";
    document.getElementById("editTemperature").value = row.temperature ?? "";
    document.getElementById("editHumidity").value = row.humidity ?? "";
    document.getElementById("editCollectedTime").value = toDatetimeLocalString(row.collected_time);
    document.getElementById("editC2H4").value = row.C2H4 ?? "";
    document.getElementById("editC2H5OH").value = row.C2H5OH ?? "";
    document.getElementById("editCO").value = row.CO ?? "";
    document.getElementById("editH2").value = row.H2 ?? "";
    document.getElementById("editO2").value = row.O2 ?? "";
    document.getElementById("editVOC").value = row.VOC ?? "";
    document.getElementById("editImage").value = row.image ?? "";

    ensureEditModal()?.show();
  }

  function openDeleteModal(row) {
    showDeleteError("");

    document.getElementById("deleteId").value = row.id ?? "";
    document.getElementById("deleteSummary").textContent =
      `ID=${row.id} | collected_time=${row.collected_time || "-"} | temperature=${row.temperature ?? "-"}`;

    ensureDeleteModal()?.show();
  }

  async function loadReadings({ resetPage = false } = {}) {
    if (!state.deviceId || state.inFlight) return;
    if (resetPage) state.page = 1;

    state.inFlight = true;

    try {
      const query = buildQuery(getFilters());
      const data = await fetchJson(API.list(state.deviceId, query));

      const rows = data.results || [];
      state.total = Number(data.total || 0);
      state.rowIndex.clear();
      rows.forEach((row) => state.rowIndex.set(String(row.id), row));

      if (data.sort_by) state.sortBy = data.sort_by;
      if (data.sort_dir) state.sortDir = data.sort_dir;

      renderRows(rows);
      renderPageInfo();
      renderSortIndicators();
      setText("lastUpdated", `最后更新：${formatNow()}`);
    } catch (e) {
      console.error(e);
      const tbody = document.getElementById("readingTableBody");
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="13" class="text-center text-danger py-4">加载失败：${escapeHtml(e.message)}</td></tr>`;
      }
      state.total = 0;
      renderPageInfo();
      renderSortIndicators();
      setText("lastUpdated", `最后更新：失败（${formatNow()}）`);
    } finally {
      state.inFlight = false;
    }
  }

  async function saveEdit() {
    const id = document.getElementById("editId")?.value || "";
    if (!id) return;

    try {
      showEditError("");

      const payload = {
        CO2: document.getElementById("editCO2")?.value ?? "",
        temperature: document.getElementById("editTemperature")?.value ?? "",
        humidity: document.getElementById("editHumidity")?.value ?? "",
        collected_time: document.getElementById("editCollectedTime")?.value ?? "",
        C2H4: document.getElementById("editC2H4")?.value ?? "",
        C2H5OH: document.getElementById("editC2H5OH")?.value ?? "",
        CO: document.getElementById("editCO")?.value ?? "",
        H2: document.getElementById("editH2")?.value ?? "",
        O2: document.getElementById("editO2")?.value ?? "",
        VOC: document.getElementById("editVOC")?.value ?? "",
        image: document.getElementById("editImage")?.value ?? "",
      };

      await fetchJson(API.update(id), {
        method: "POST",
        body: payload,
      });

      ensureEditModal()?.hide();
      await loadReadings({ resetPage: false });
    } catch (e) {
      console.error(e);
      showEditError(e.message || "保存失败");
    }
  }

  async function confirmDelete() {
    const id = document.getElementById("deleteId")?.value || "";
    if (!id) return;

    try {
      showDeleteError("");

      await fetchJson(API.delete(id), {
        method: "POST",
        body: {},
      });

      ensureDeleteModal()?.hide();

      const maxPageBefore = Math.max(1, Math.ceil(Math.max(0, state.total - 1) / state.pageSize));
      if (state.page > maxPageBefore) {
        state.page = maxPageBefore;
      }

      await loadReadings({ resetPage: false });
    } catch (e) {
      console.error(e);
      showDeleteError(e.message || "删除失败");
    }
  }

  function bindEvents() {
    document.getElementById("btnSearch")?.addEventListener("click", async () => {
      await loadReadings({ resetPage: true });
    });

    document.getElementById("btnReset")?.addEventListener("click", async () => {
      document.getElementById("keyword").value = "";
      document.getElementById("dateFrom").value = "";
      document.getElementById("dateTo").value = "";
      state.sortBy = "collected_time";
      state.sortDir = "desc";
      renderSortIndicators();
      await loadReadings({ resetPage: true });
    });

    document.getElementById("btnPrev")?.addEventListener("click", async () => {
      if (state.page <= 1) return;
      state.page -= 1;
      await loadReadings({ resetPage: false });
    });

    document.getElementById("btnNext")?.addEventListener("click", async () => {
      const maxPage = Math.max(1, Math.ceil((state.total || 0) / state.pageSize));
      if (state.page >= maxPage) return;
      state.page += 1;
      await loadReadings({ resetPage: false });
    });

    document.getElementById("btnSaveEdit")?.addEventListener("click", saveEdit);
    document.getElementById("btnConfirmDelete")?.addEventListener("click", confirmDelete);

    document.querySelectorAll("th.sortable").forEach((th) => {
      th.addEventListener("click", async () => {
        const sortKey = th.dataset.sort;
        if (!sortKey) return;

        if (state.sortBy === sortKey) {
          state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        } else {
          state.sortBy = sortKey;
          state.sortDir = "asc";
        }

        state.page = 1;
        renderSortIndicators();
        await loadReadings({ resetPage: true });
      });
    });
  }

  async function init() {
    bindEvents();
    ensureEditModal();
    ensureDeleteModal();
    renderSortIndicators();
    await loadReadings({ resetPage: true });
  }

  document.addEventListener("DOMContentLoaded", init);
})();