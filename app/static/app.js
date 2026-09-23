const $ = (sel) => document.querySelector(sel);

const form = $("#shorten-form");
const urlInput = $("#url");
const aliasInput = $("#alias");
const expiresInput = $("#expires");
const submitBtn = $("#submit-btn");
const formError = $("#form-error");
const result = $("#result");
const linksList = $("#links-list");
const linksEmpty = $("#links-empty");
const modal = $("#stats-modal");

let currentLink = null;
let statsTimer = null;
let dayChart = null;

$("#host-prefix").textContent = `${location.host}/`;

// ---------- helpers ----------
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(extractError(data) || `Ошибка ${res.status}`);
  return data;
}

function extractError(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length) {
    const first = data.detail[0];
    if (first.loc?.includes("url")) return "Введите корректную ссылку (http:// или https://)";
    return (first.msg || "").replace(/^Value error, /, "");
  }
  return null;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 2200);
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Скопировано ✓");
  } catch {
    toast("Не удалось скопировать");
  }
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
}

function isExpired(link) {
  return link.expires_at && new Date(link.expires_at) <= new Date();
}

// ---------- create ----------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.textContent = "";
  submitBtn.disabled = true;

  const payload = { url: urlInput.value.trim() };
  if (aliasInput.value.trim()) payload.custom_alias = aliasInput.value.trim();
  if (expiresInput.value) payload.expires_in_days = Number(expiresInput.value);

  try {
    const link = await api("/api/links", { method: "POST", body: JSON.stringify(payload) });
    showResult(link);
    form.reset();
    loadLinks();
  } catch (err) {
    formError.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
  }
});

function showResult(link) {
  currentLink = link;
  const a = $("#result-link");
  a.href = link.short_url;
  a.textContent = link.short_url.replace(/^https?:\/\//, "");
  const qrUrl = `/api/links/${encodeURIComponent(link.code)}/qr`;
  $("#qr-img").src = qrUrl;
  $("#qr-download").href = qrUrl;
  $("#qr-download").setAttribute("download", `qr-${link.code}.svg`);
  result.classList.remove("hidden");
}

$("#copy-btn").addEventListener("click", () => currentLink && copy(currentLink.short_url));
$("#result-stats-btn").addEventListener("click", () => currentLink && openStats(currentLink));

// ---------- list ----------
async function loadLinks() {
  try {
    const links = await api("/api/links");
    renderLinks(links);
  } catch (err) {
    toast(err.message);
  }
}

function renderLinks(links) {
  linksList.replaceChildren();
  linksEmpty.classList.toggle("hidden", links.length > 0);

  for (const link of links) {
    const meta = el("div", { class: "link-meta" }, [el("span", { class: "tag", text: formatDate(link.created_at) })]);
    if (link.expires_at) {
      meta.append(
        el("span", {
          class: isExpired(link) ? "tag tag-warn" : "tag",
          text: isExpired(link) ? "истекла" : `до ${formatDate(link.expires_at)}`,
        })
      );
    }

    const row = el("div", { class: "link-row glass" }, [
      el("div", { class: "link-main" }, [
        el("a", { class: "link-short", href: link.short_url, target: "_blank", rel: "noopener", text: `/${link.code}` }),
        el("div", { class: "link-original", title: link.original_url, text: link.original_url }),
        meta,
      ]),
      el("div", { class: "clicks" }, [
        el("span", { class: "clicks-value", text: String(link.clicks_count) }),
        el("span", { class: "clicks-label", text: "кликов" }),
      ]),
      el("div", { class: "row-actions" }, [
        el("button", { class: "icon-btn", title: "Копировать", "aria-label": "Копировать", text: "⧉", onclick: () => copy(link.short_url) }),
        el("button", { class: "icon-btn", title: "Статистика", "aria-label": "Статистика", text: "📊", onclick: () => openStats(link) }),
        el("button", { class: "icon-btn danger", title: "Удалить", "aria-label": "Удалить", text: "🗑", onclick: () => removeLink(link) }),
      ]),
    ]);
    linksList.append(row);
  }
}

async function removeLink(link) {
  if (!confirm(`Удалить /${link.code}? Статистика тоже удалится.`)) return;
  try {
    await api(`/api/links/${encodeURIComponent(link.code)}`, { method: "DELETE" });
    if (currentLink?.code === link.code) result.classList.add("hidden");
    toast("Ссылка удалена");
    loadLinks();
  } catch (err) {
    toast(err.message);
  }
}

$("#refresh-btn").addEventListener("click", loadLinks);

// ---------- stats ----------
function openStats(link) {
  $("#stats-title").textContent = `/${link.code}`;
  const orig = $("#stats-original");
  orig.textContent = link.original_url;
  orig.href = link.original_url;
  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  loadStats(link.code);
  clearInterval(statsTimer);
  statsTimer = setInterval(() => loadStats(link.code), 5000);
}

function closeStats() {
  modal.classList.add("hidden");
  document.body.style.overflow = "";
  clearInterval(statsTimer);
  loadLinks();
}

modal.addEventListener("click", (e) => {
  if (e.target.closest("[data-close]")) closeStats();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !modal.classList.contains("hidden")) closeStats();
});

async function loadStats(code) {
  try {
    const stats = await api(`/api/links/${encodeURIComponent(code)}/stats`);
    renderStats(stats);
  } catch (err) {
    toast(err.message);
    closeStats();
  }
}

function renderStats(stats) {
  const days = stats.clicks_by_day;
  $("#kpi-total").textContent = stats.total_clicks;
  $("#kpi-today").textContent = days.length ? days[days.length - 1].count : 0;
  $("#kpi-top-device").textContent = stats.devices[0]?.label ?? "—";

  renderBars("#bd-devices", stats.devices);
  renderBars("#bd-browsers", stats.browsers);
  renderBars("#bd-os", stats.os);
  renderBars("#bd-referrers", stats.referrers);
  renderDayChart(days);
}

function renderBars(selector, items) {
  const box = $(selector);
  box.replaceChildren();
  if (!items.length) {
    box.append(el("div", { class: "none", text: "Нет данных" }));
    return;
  }
  const max = Math.max(...items.map((i) => i.count));
  for (const item of items) {
    const fill = el("div", { class: "bar-fill" });
    box.append(
      el("div", { class: "bar-row" }, [
        el("div", { class: "bar-top" }, [el("span", { text: item.label }), el("span", { text: String(item.count) })]),
        el("div", { class: "bar-track" }, [fill]),
      ])
    );
    requestAnimationFrame(() => (fill.style.width = `${(item.count / max) * 100}%`));
  }
}

function renderDayChart(days) {
  if (typeof Chart === "undefined") return;
  const labels = days.map((d) => new Date(d.label).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }));
  const values = days.map((d) => d.count);

  if (dayChart) {
    dayChart.data.labels = labels;
    dayChart.data.datasets[0].data = values;
    dayChart.update();
    return;
  }

  dayChart = new Chart($("#chart-days"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: "#2563eb", borderRadius: 3, maxBarThickness: 18 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { displayColors: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#6b7280", maxTicksLimit: 8 } },
        y: { beginAtZero: true, grid: { color: "#eef0f3" }, ticks: { color: "#6b7280", precision: 0 } },
      },
    },
  });
}

loadLinks();
