const demoHours = [
  { h: "00", in: 0.08, out: 0.07 },
  { h: "01", in: 0.05, out: 0.04 },
  { h: "02", in: 0.04, out: 0.04 },
  { h: "03", in: 0.03, out: 0.03 },
  { h: "04", in: 0.02, out: 0.02 },
  { h: "05", in: 0.03, out: 0.03 },
  { h: "06", in: 0.05, out: 0.04 },
  { h: "07", in: 0.16, out: 0.14 },
  { h: "08", in: 0.32, out: 0.30 },
  { h: "09", in: 0.55, out: 0.52 },
  { h: "10", in: 0.88, out: 0.84 },
  { h: "11", in: 0.36, out: 0.34 },
  { h: "12", in: 0.18, out: 0.17 },
  { h: "13", in: 0.12, out: 0.11 },
  { h: "14", in: 0.20, out: 0.18 },
  { h: "15", in: 0.24, out: 0.22 },
  { h: "16", in: 0.09, out: 0.08 },
  { h: "17", in: 0.10, out: 0.09 },
  { h: "18", in: 0.14, out: 0.13 },
  { h: "19", in: 0.12, out: 0.11 },
  { h: "20", in: 0.22, out: 0.20 },
  { h: "21", in: 0.18, out: 0.16 },
  { h: "22", in: 0.11, out: 0.10 },
  { h: "23", in: 0.07, out: 0.06 },
];

const fallbackServers = [
  {
    akileId: 12345,
    index: 1,
    account: "Akile",
    flag: "🇲🇴",
    flagLabel: "Macau",
    flagSrc: "/flags/mo.svg",
    name: "Demo Macau VPS",
    node: "Macau / Demo Node",
    status: "Running",
    remaining: "742.00 GiB",
    used: "258.00 GiB",
    total: "1000 GiB",
    usedRatio: 25.8,
    usedPercent: "25.80%",
    forecast: "约 76.8 天",
    resetAt: "2026-06-12 15:40",
    expiresAt: "2027-06-12 15:40",
    uptime: "16天 18小时",
    hourly: demoHours,
  },
  {
    akileId: 67890,
    index: 2,
    account: "Akile",
    flag: "🇺🇸",
    flagLabel: "United States",
    flagSrc: "/flags/us.svg",
    name: "Demo US VPS",
    node: "United States / Demo Node",
    status: "Running",
    remaining: "1659.00 GiB",
    used: "29.00 GiB",
    total: "1688 GiB",
    usedRatio: 1.72,
    usedPercent: "1.72%",
    forecast: "约 5300.0 天",
    resetAt: "2026-06-12 14:36",
    expiresAt: "2027-05-12 14:36",
    uptime: "13天 1小时",
    hourly: demoHours.map((item) => ({ h: item.h, in: item.in * 0.08, out: item.out * 0.08 })),
  },
];

let servers = fallbackServers;

function formatMax(value) {
  if (value < 1) return `${value.toFixed(1)} GiB`;
  return `${value.toFixed(0)} GiB`;
}

function makeChart(server) {
  const width = 960;
  const height = 276;
  const padding = { top: 24, right: 24, bottom: 40, left: 58 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const totals = server.hourly.map((d) => d.in + d.out);
  const max = server.placeholder ? 0.5 : Math.max(0.5, ...totals) * 1.12;
  const step = plotW / server.hourly.length;
  const barW = Math.max(12, step * 0.58);
  const grid = [0, 0.25, 0.5, 0.75, 1];

  const gridLines = grid
    .map((ratio) => {
      const y = padding.top + plotH - plotH * ratio;
      const label = formatMax(max * ratio);
      return `
        <line class="grid-line" x1="${padding.left}" x2="${width - padding.right}" y1="${y}" y2="${y}" />
        <text class="axis-label" x="12" y="${y + 5}">${label}</text>
      `;
    })
    .join("");

  const bars = server.hourly
    .map((d, i) => {
      const totalH = ((d.in + d.out) / max) * plotH;
      const inH = (d.in / max) * plotH;
      const outH = (d.out / max) * plotH;
      const x = padding.left + i * step + (step - barW) / 2;
      const yOut = padding.top + plotH - totalH;
      const yIn = padding.top + plotH - inH;
      const tick = i % 3 === 0
        ? `<text class="axis-label" x="${x + barW / 2}" y="${height - 13}" text-anchor="middle">${d.h}</text>`
        : "";

      if (server.placeholder) {
        const fakeH = totalH * (0.72 + (i % 4) * 0.06);
        const fakeY = padding.top + plotH - fakeH;
        return `
          <rect class="placeholder-bar" x="${x}" y="${fakeY}" width="${barW}" height="${fakeH}" />
          ${tick}
        `;
      }

      return `
        <rect class="bar-out" x="${x}" y="${yOut}" width="${barW}" height="${outH}" />
        <rect class="bar-in" x="${x}" y="${yIn}" width="${barW}" height="${inH}" />
        ${tick}
      `;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${server.name} hourly traffic chart">
      ${gridLines}
      ${bars}
    </svg>
  `;
}

function makeServerCard(server) {
  const placeholderNote = server.placeholder
    ? `<div class="placeholder-note"><span>第二台服务器数据接入后，这里会替换成真实 24 小时柱状图。</span><span>Placeholder</span></div>`
    : "";

  return `
    <article class="server-card ${server.placeholder ? "placeholder" : ""}">
      <div class="server-top">
        <div class="server-title">
          <span class="server-index">${server.index}</span>
          <div class="server-name">
            <h2><img class="emoji-flag" src="${server.flagSrc}" alt="${server.flag}" title="${server.flagLabel}" />${server.name}</h2>
            <p>${server.node}</p>
          </div>
        </div>
        <div class="status-pill">${server.status}</div>
      </div>

      <div class="traffic-panel" aria-label="${server.name} traffic summary">
        <div class="usage-row">
          <div class="usage-track" aria-label="traffic usage">
            <span style="width: ${Math.max(0, Math.min(100, server.usedRatio))}%"></span>
          </div>
          <strong>${server.used} / ${server.total}</strong>
        </div>
        <div class="detail-table">
          <div><span>剩余流量</span><strong>${server.remaining}</strong></div>
          <div><span>已用比例</span><strong>${server.usedPercent}</strong></div>
          <div><span>预计可用天数</span><strong>${server.forecast}</strong></div>
          <div><span>运行时长</span><strong>${server.uptime}</strong></div>
          <div><span>流量重置日期</span><strong>${server.resetAt}</strong></div>
          <div><span>VPS 到期日期</span><strong>${server.expiresAt}</strong></div>
        </div>
      </div>

      <div class="chart-block">
        <div class="chart-heading">
          <h3>Hourly Traffic (GiB)</h3>
          <div class="legend">
            <span><i class="in"></i>In</span>
            <span><i class="out"></i>Out</span>
          </div>
        </div>
        <div class="chart">${makeChart(server)}</div>
        ${placeholderNote}
      </div>
    </article>
  `;
}

function renderServers() {
  document.getElementById("servers").innerHTML = servers.map(makeServerCard).join("");
  document.querySelector(".report")?.classList.add("ready");
}

function updateTimestamp(data) {
  const timeNode = document.querySelector(".timestamp span");
  const dateNode = document.querySelector(".timestamp strong");
  if (timeNode && data.generatedTime) {
    timeNode.textContent = data.generatedTime;
  }
  if (dateNode && data.generatedAt) {
    dateNode.textContent = data.generatedAt.slice(0, 10);
  }
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

async function loadServers() {
  try {
    const [latest, history] = await Promise.all([
      fetchJson("/api/latest"),
      fetchJson("/api/history?hours=24"),
    ]);
    if (!Array.isArray(latest.servers) || latest.servers.length === 0) {
      throw new Error("No server data returned");
    }
    const hourlyById = new Map(
      (history.servers || []).map((server) => [server.akileId, server.hourly || []]),
    );
    servers = latest.servers.map((server) => ({
      ...server,
      hourly: hourlyById.get(server.akileId) || [],
    }));
    updateTimestamp(latest);
  } catch (error) {
    console.warn("Using bundled fallback server data:", error);
    servers = fallbackServers;
  }
  renderServers();
}

loadServers();
