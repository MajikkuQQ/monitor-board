(() => {
  const STATUS_UI = {
    ok: { key: "ok", label: "Онлайн", pill: "ok", bar: "ok" },
    monitor_offline: { key: "bad", label: "Монитор off", pill: "bad", bar: "bad" },
    agent_offline: { key: "bad", label: "Оффлайн", pill: "bad", bar: "bad" },
    unknown: { key: "mute", label: "Нет данных", pill: "mute", bar: "mute" },
  };

  const cardsView = document.getElementById("cardsView");
  const tableBody = document.getElementById("tableBody");
  const tableView = document.getElementById("tableView");
  const filterEl = document.getElementById("filter");
  const filter2 = document.getElementById("filter2");
  const updatedAt = document.getElementById("updatedAt");
  const modal = document.getElementById("modal");
  const modalBody = document.getElementById("modalBody");

  let endpoints = [];
  let view = "cards";
  let historyDays = 7;
  let selectedId = null;
  let timer = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function ui(status) {
    return STATUS_UI[status] || STATUS_UI.unknown;
  }

  function query() {
    return (filterEl.value || filter2.value || "").trim().toLowerCase();
  }

  function filtered() {
    const q = query();
    if (!q) return endpoints;
    return endpoints.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        (e.hostname || "").toLowerCase().includes(q)
    );
  }

  function syncFilters(source) {
    if (source === filterEl) filter2.value = filterEl.value;
    if (source === filter2) filterEl.value = filter2.value;
    render();
  }

  function renderCards(items) {
    if (!items.length) {
      cardsView.innerHTML = `<p class="muted">Точек нет</p>`;
      return;
    }
    cardsView.innerHTML = items
      .map((e) => {
        const s = ui(e.status);
        return `
        <button type="button" class="kiosk-card" data-id="${e.id}">
          <div class="stamp ${s.key}">${escapeHtml(e.last_seen_label)}</div>
          <h3 class="title">${escapeHtml(e.name)}</h3>
          <p class="sub">${escapeHtml(e.hostname || "—")}</p>
          <p class="meta">мониторы ${e.monitors_on}/${e.monitors_total}${
            e.open_incidents ? ` · открытых ${e.open_incidents}` : ""
          }</p>
          <div class="bar ${s.bar}"></div>
        </button>`;
      })
      .join("");

    cardsView.querySelectorAll(".kiosk-card").forEach((btn) => {
      btn.addEventListener("click", () => openDetail(Number(btn.dataset.id)));
    });
  }

  function renderTable(items) {
    if (!items.length) {
      tableBody.innerHTML = `<tr><td colspan="5" class="muted">Точек нет</td></tr>`;
      return;
    }
    tableBody.innerHTML = items
      .map((e) => {
        const s = ui(e.status);
        return `
        <tr data-id="${e.id}">
          <td><span class="pill ${s.pill}">${s.label}</span></td>
          <td>${escapeHtml(e.name)}</td>
          <td>${escapeHtml(e.hostname || "—")}</td>
          <td>${e.monitors_on}/${e.monitors_total}</td>
          <td>${escapeHtml(e.last_seen_label)}</td>
        </tr>`;
      })
      .join("");

    tableBody.querySelectorAll("tr[data-id]").forEach((row) => {
      row.addEventListener("click", () => openDetail(Number(row.dataset.id)));
    });
  }

  function render() {
    const items = filtered();
    if (view === "cards") {
      cardsView.classList.remove("hidden");
      tableView.classList.add("hidden");
      renderCards(items);
    } else {
      cardsView.classList.add("hidden");
      tableView.classList.remove("hidden");
      renderTable(items);
    }
  }

  function setView(next) {
    view = next;
    document.getElementById("viewCards").classList.toggle("active", view === "cards");
    document.getElementById("viewTable").classList.toggle("active", view === "table");
    render();
  }

  async function loadOverview() {
    const res = await fetch("/api/web/overview", { credentials: "same-origin" });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!res.ok) throw new Error("overview failed");
    const data = await res.json();
    endpoints = data.endpoints || [];

    const online = data.counts.ok || 0;
    const offline =
      (data.counts.monitor_offline || 0) +
      (data.counts.agent_offline || 0) +
      (data.counts.unknown || 0);

    document.getElementById("cOk").textContent = online;
    document.getElementById("cOff").textContent = offline;
    updatedAt.textContent = data.generated_at;
    render();
    if (selectedId && !modal.classList.contains("hidden")) {
      openDetail(selectedId, false);
    }
  }

  function closeModal() {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    selectedId = null;
  }

  async function openDetail(id, showLoading = true) {
    selectedId = id;
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    if (showLoading) {
      modalBody.innerHTML = `<p class="muted">Загрузка…</p>`;
    }

    const res = await fetch(`/api/web/endpoints/${id}?days=${historyDays}`, {
      credentials: "same-origin",
    });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!res.ok) {
      modalBody.innerHTML = `<p class="error">Не удалось загрузить точку</p>`;
      return;
    }
    const d = await res.json();
    const s = ui(d.status);

    const monitorsHtml = d.monitors.length
      ? d.monitors
          .map(
            (m) => `
        <div class="row-line">
          <span>${m.is_connected ? "🟢" : "🔴"} ${escapeHtml(m.name)}</span>
          <span class="muted">${escapeHtml(m.last_seen_label)}</span>
        </div>`
          )
          .join("")
      : `<p class="muted">ещё не было heartbeat</p>`;

    const openHtml = d.open_incidents.length
      ? d.open_incidents
          .map(
            (i) => `
        <div class="row-line">
          <span>🔴 ${escapeHtml(i.monitor_name)}</span>
          <span class="muted">${escapeHtml(i.started_at)} · ${escapeHtml(i.duration)}</span>
        </div>`
          )
          .join("")
      : `<p class="muted">нет открытых отключений</p>`;

    const histHtml = d.history.length
      ? d.history
          .map(
            (i) => `
        <div class="row-line">
          <span>${i.state === "open" ? "🔴" : "⚪"} ${escapeHtml(i.monitor_name)}</span>
          <span class="muted">${escapeHtml(i.started_at)} → ${escapeHtml(i.ended_at)} · ${escapeHtml(i.duration)}</span>
        </div>`
          )
          .join("")
      : `<p class="muted">история пуста</p>`;

    modalBody.innerHTML = `
      <div class="head-row">
        <div>
          <h2>${escapeHtml(d.name)}</h2>
          <p class="muted">${escapeHtml(d.hostname || "—")} · last seen ${escapeHtml(d.last_seen_label)}</p>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <span class="pill ${s.pill}">${s.label}</span>
          <button type="button" class="btn" id="btnAlerts">Алерты: ${
            d.alerts_enabled ? "вкл" : "выкл"
          }</button>
        </div>
      </div>
      ${
        d.agent_offline
          ? `<p class="error">Агент offline с ${escapeHtml(d.agent_offline.started_at)}</p>`
          : ""
      }
      <div class="boxes">
        <div class="box"><h3>Мониторы</h3>${monitorsHtml}</div>
        <div class="box"><h3>Открытые отключения</h3>${openHtml}</div>
      </div>
      <div class="box">
        <h3>История</h3>
        <div class="chips">
          <button type="button" class="chip ${historyDays === 1 ? "active" : ""}" data-days="1">сегодня</button>
          <button type="button" class="chip ${historyDays === 7 ? "active" : ""}" data-days="7">7д</button>
          <button type="button" class="chip ${historyDays === 30 ? "active" : ""}" data-days="30">30д</button>
        </div>
        ${histHtml}
      </div>
    `;

    modalBody.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        historyDays = Number(chip.dataset.days);
        openDetail(selectedId);
      });
    });

    const alertsBtn = modalBody.querySelector("#btnAlerts");
    if (alertsBtn) {
      alertsBtn.addEventListener("click", async () => {
        const r = await fetch(`/api/web/endpoints/${selectedId}/alerts`, {
          method: "POST",
          credentials: "same-origin",
        });
        if (r.ok) openDetail(selectedId);
      });
    }
  }

  async function tick() {
    try {
      await loadOverview();
    } catch (err) {
      console.error(err);
      updatedAt.textContent = "ошибка обновления";
    }
  }

  filterEl.addEventListener("input", () => syncFilters(filterEl));
  filter2.addEventListener("input", () => syncFilters(filter2));
  document.getElementById("btnRefresh").addEventListener("click", tick);
  document.getElementById("viewCards").addEventListener("click", () => setView("cards"));
  document.getElementById("viewTable").addEventListener("click", () => setView("table"));
  modal.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  tick();
  timer = setInterval(tick, 10000);
  window.addEventListener("beforeunload", () => clearInterval(timer));
})();
