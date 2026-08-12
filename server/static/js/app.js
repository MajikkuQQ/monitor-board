(() => {
  const ICONS = {
    ok: `<svg class="ico ok" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 1 0 20a10 10 0 0 1 0-20Zm4.3 7.3a1 1 0 0 0-1.4-1.4L11 11.8l-1.9-1.9a1 1 0 0 0-1.4 1.4l2.6 2.6a1 1 0 0 0 1.4 0l4.6-4.6Z"/></svg>`,
    bad: `<svg class="ico bad" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 1 0 20a10 10 0 0 1 0-20Zm3.7 6.3a1 1 0 0 0-1.4 0L12 10.6L9.7 8.3a1 1 0 0 0-1.4 1.4L10.6 12l-2.3 2.3a1 1 0 1 0 1.4 1.4L12 13.4l2.3 2.3a1 1 0 0 0 1.4-1.4L13.4 12l2.3-2.3a1 1 0 0 0 0-1.4Z"/></svg>`,
    mute: `<svg class="ico mute" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 1 1 0 20a10 10 0 0 1 0-20Zm0 2a8 8 0 1 0 0 16a8 8 0 0 0 0-16Zm0 3a1 1 0 0 1 1 1v5a1 1 0 1 1-2 0V8a1 1 0 0 1 1-1Zm0 9a1.25 1.25 0 1 1 0 2.5A1.25 1.25 0 0 1 12 16Z"/></svg>`,
    monitorOn: `<svg class="ico ok" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-5v2h2a1 1 0 1 1 0 2H8a1 1 0 1 1 0-2h2v-2H5a2 2 0 0 1-2-2V5Zm2 0v10h14V5H5Zm7.7 2.3a1 1 0 0 1 0 1.4L11.4 10l1.3 1.3a1 1 0 0 1-1.4 1.4l-2-2a1 1 0 0 1 0-1.4l2-2a1 1 0 0 1 1.4 0Z"/></svg>`,
    monitorOff: `<svg class="ico bad" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-5v2h2a1 1 0 1 1 0 2H8a1 1 0 1 1 0-2h2v-2H5a2 2 0 0 1-2-2V5Zm2 0v10h14V5H5Zm10.7 2.3a1 1 0 0 1 0 1.4L12.4 10l3.3 3.3a1 1 0 1 1-1.4 1.4L11 11.4l-3.3 3.3a1 1 0 0 1-1.4-1.4L9.6 10L6.3 6.7a1 1 0 0 1 1.4-1.4L11 8.6l3.3-3.3a1 1 0 0 1 1.4 0Z"/></svg>`,
    bell: `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a6 6 0 0 1 6 6v3.1l1.4 2.8A1 1 0 0 1 18.5 16H5.5a1 1 0 0 1-.9-1.5L6 11.1V8a6 6 0 0 1 6-6Zm0 20a3 3 0 0 1-2.8-2h5.6A3 3 0 0 1 12 22Z"/></svg>`,
    trash: `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9 3a1 1 0 0 0-1 1v1H5a1 1 0 0 0 0 2h1v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7h1a1 1 0 1 0 0-2h-3V4a1 1 0 0 0-1-1H9Zm1 2h4v1h-4V5Zm-1 4a1 1 0 0 1 2 0v8a1 1 0 1 1-2 0V9Zm5 0a1 1 0 0 1 2 0v8a1 1 0 1 1-2 0V9Z"/></svg>`,
  };

  const STATUS_UI = {
    ok: { key: "ok", label: "Онлайн", pill: "ok", bar: "ok", icon: ICONS.ok },
    monitor_offline: {
      key: "bad",
      label: "Монитор off",
      pill: "bad",
      bar: "bad",
      icon: ICONS.monitorOff,
    },
    agent_offline: {
      key: "bad",
      label: "Оффлайн",
      pill: "bad",
      bar: "bad",
      icon: ICONS.bad,
    },
    unknown: {
      key: "mute",
      label: "Нет данных",
      pill: "mute",
      bar: "mute",
      icon: ICONS.mute,
    },
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
        const ticks = Array.isArray(e.uptime) ? e.uptime : [];
        const uptimeHtml = ticks.length
          ? `<div class="uptime" aria-hidden="true">
              <div class="uptime-track">
                ${ticks
                  .map(
                    (t, idx) =>
                      `<span class="tick ${t.s}" data-i="${idx}" data-t="${escapeHtml(
                        t.t
                      )}" data-label="${escapeHtml(t.label)}"></span>`
                  )
                  .join("")}
              </div>
              <div class="uptime-tip hidden"></div>
            </div>`
          : `<div class="bar ${s.bar}"></div>`;
        return `
        <button type="button" class="kiosk-card" data-id="${e.id}">
          <div class="stamp ${s.key}">${s.icon}<span>${escapeHtml(e.last_seen_label)}</span></div>
          <h3 class="title">${escapeHtml(e.name)}</h3>
          <p class="sub">${escapeHtml(e.hostname || "—")}</p>
          <p class="meta">мониторы ${e.monitors_on}/${e.monitors_total}${
            e.open_incidents ? ` · открытых ${e.open_incidents}` : ""
          }</p>
          ${uptimeHtml}
        </button>`;
      })
      .join("");

    cardsView.querySelectorAll(".kiosk-card").forEach((btn) => {
      btn.addEventListener("click", () => openDetail(Number(btn.dataset.id)));
      const tip = btn.querySelector(".uptime-tip");
      const track = btn.querySelector(".uptime-track");
      if (!tip || !track) return;
      track.addEventListener("mousemove", (ev) => {
        const tick = ev.target.closest(".tick");
        if (!tick || !track.contains(tick)) return;
        tip.innerHTML = `<strong>${tick.dataset.t}</strong><span class="tip-dot ${
          tick.classList.contains("bad")
            ? "bad"
            : tick.classList.contains("mute")
              ? "mute"
              : "ok"
        }"></span><span>${tick.dataset.label}</span>`;
        tip.classList.remove("hidden");
        const rect = track.getBoundingClientRect();
        const x = ev.clientX - rect.left;
        tip.style.left = `${Math.max(8, Math.min(rect.width - 8, x))}px`;
      });
      track.addEventListener("mouseleave", () => tip.classList.add("hidden"));
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
          <td><span class="pill ${s.pill}">${s.icon}<span>${s.label}</span></span></td>
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

  async function deleteEndpoint(id, name) {
    const ok = window.confirm(
      `Удалить точку «${name}»?\nИстория отключений этой точки тоже будет удалена.`
    );
    if (!ok) return;
    const res = await fetch(`/api/web/endpoints/${id}`, {
      method: "DELETE",
      credentials: "same-origin",
    });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!res.ok) {
      let detail = "";
      try {
        const body = await res.json();
        detail = body.detail ? `\n${body.detail}` : "";
      } catch (_) {
        /* ignore */
      }
      alert(`Не удалось удалить точку (${res.status})${detail}`);
      return;
    }
    closeModal();
    await loadOverview();
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
          <span class="row-with-ico">${m.is_connected ? ICONS.monitorOn : ICONS.monitorOff}<span>${escapeHtml(m.name)}</span></span>
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
          <span class="row-with-ico">${ICONS.monitorOff}<span>${escapeHtml(i.monitor_name)}</span></span>
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
          <span class="row-with-ico">${i.state === "open" ? ICONS.monitorOff : ICONS.mute}<span>${escapeHtml(i.monitor_name)}</span></span>
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
        <div class="head-actions">
          <span class="pill ${s.pill}">${s.icon}<span>${s.label}</span></span>
          <button type="button" class="btn" id="btnAlerts">${ICONS.bell}<span>Алерты: ${
            d.alerts_enabled ? "вкл" : "выкл"
          }</span></button>
          <button type="button" class="btn danger" id="btnDelete">${ICONS.trash}<span>Удалить</span></button>
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

    const delBtn = modalBody.querySelector("#btnDelete");
    if (delBtn) {
      delBtn.addEventListener("click", () => deleteEndpoint(d.id, d.name));
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
