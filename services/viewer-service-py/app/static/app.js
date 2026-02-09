/*
  File: services/viewer-service-py/app/static/app.js
  Purpose: Client-side renderer + controls for the fleet demo.
  Key responsibilities:
  - Render snapshots to Canvas
  - Trigger baseline/GA runs
  - Stream updates via WebSocket
*/

const canvas = document.getElementById("fleet-canvas");
const ctx = canvas.getContext("2d");

const scaleEl = document.getElementById("scale-value");
const seedEl = document.getElementById("seed-value");
const replanEl = document.getElementById("replan-value");
const runIdEl = document.getElementById("run-id");
const metricsBody = document.getElementById("metrics-body");
const compareBody = document.getElementById("compare-body");
const robotsInput = document.getElementById("robots-input");
const jobsInput = document.getElementById("jobs-input");

let config = null;
let currentSnapshot = null;
let currentRunId = null;

function selectedCounts() {
  const robotsRaw = Number.parseInt(robotsInput.value, 10);
  const jobsRaw = Number.parseInt(jobsInput.value, 10);
  if (Number.isNaN(robotsRaw) && Number.isNaN(jobsRaw)) {
    return { robots: null, jobs: null };
  }
  if (Number.isNaN(robotsRaw) || Number.isNaN(jobsRaw) || robotsRaw <= 0 || jobsRaw <= 0) {
    return { robots: null, jobs: null, error: "Robots and jobs must both be positive integers." };
  }
  return { robots: robotsRaw, jobs: jobsRaw };
}

function drawGrid() {
  // Background grid for spatial context.
  const step = 50;
  ctx.strokeStyle = "#dfd4be";
  ctx.lineWidth = 1;
  for (let x = 0; x <= canvas.width; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y <= canvas.height; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
}

function transform(x, y, worldSize = 100) {
  // Map world coordinates into canvas pixels with padding.
  const px = (x / worldSize) * (canvas.width - 40) + 20;
  const py = canvas.height - ((y / worldSize) * (canvas.height - 40) + 20);
  return [px, py];
}

function drawSnapshot(snapshot) {
  // Main render routine: jobs, robots, and UI overlays.
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawGrid();

  if (!snapshot) {
    return;
  }

  const jobs = snapshot.jobs || [];
  const robots = snapshot.robots || [];

  for (const job of jobs) {
    // Pickup squares (color by completion) + dropoff X markers.
    const [px, py] = transform(job.pickup_x, job.pickup_y);
    const [dx, dy] = transform(job.dropoff_x, job.dropoff_y);

    ctx.fillStyle = job.state === "completed" ? "#0a8f74" : "#b05c2a";
    ctx.fillRect(px - 4, py - 4, 8, 8);

    ctx.strokeStyle = "#34424a";
    ctx.beginPath();
    ctx.moveTo(dx - 5, dy - 5);
    ctx.lineTo(dx + 5, dy + 5);
    ctx.moveTo(dx + 5, dy - 5);
    ctx.lineTo(dx - 5, dy + 5);
    ctx.stroke();
  }

  for (const robot of robots) {
    // Robot glyph, battery bar, and optional route overlay.
    const [x, y] = transform(robot.x, robot.y);

    ctx.fillStyle = robot.state === "idle" ? "#1b8d7a" : "#244d9d";
    ctx.beginPath();
    ctx.arc(x, y, 10, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#1f2a30";
    ctx.font = "12px sans-serif";
    ctx.fillText(`R${robot.id}`, x - 8, y - 14);

    ctx.fillStyle = "#c8c8c8";
    ctx.fillRect(x - 12, y + 12, 24, 4);
    ctx.fillStyle = robot.battery > 20 ? "#118f53" : "#b13020";
    ctx.fillRect(x - 12, y + 12, 24 * Math.max(0, Math.min(1, robot.battery / 100)), 4);

    if (robot.current_job_id) {
      const job = jobs.find((j) => j.id === robot.current_job_id);
      if (job) {
        const [px, py] = transform(job.pickup_x, job.pickup_y);
        const [dx, dy] = transform(job.dropoff_x, job.dropoff_y);
        ctx.strokeStyle = "rgba(22, 22, 22, 0.4)";
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(px, py);
        ctx.lineTo(dx, dy);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  }

  ctx.fillStyle = "#17262d";
  ctx.font = "bold 13px sans-serif";
  ctx.fillText(`Sim Time: ${snapshot.sim_time_s}s`, 20, 20);
}

function renderMetrics(metrics) {
  // Populate the metrics table once a run completes.
  metricsBody.innerHTML = "";
  if (!metrics || metrics.error) {
    return;
  }
  const items = [
    ["on_time_rate", metrics.on_time_rate],
    ["total_distance", metrics.total_distance],
    ["avg_completion_time", metrics.avg_completion_time],
    ["max_lateness", metrics.max_lateness],
    ["completed_jobs", metrics.completed_jobs],
    ["failed_jobs", metrics.failed_jobs],
    ["total_jobs", metrics.total_jobs],
  ];
  for (const [k, v] of items) {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${k}</td><td>${v}</td>`;
    metricsBody.appendChild(row);
  }
}

function renderCompare(compare) {
  // Baseline vs GA comparison table.
  compareBody.innerHTML = "";
  if (!compare || compare.error) {
    return;
  }
  const keys = ["on_time_rate", "total_distance", "avg_completion_time", "max_lateness"];
  for (const key of keys) {
    const row = document.createElement("tr");
    const baseline = compare.baseline ? compare.baseline[key] : "-";
    const ga = compare.ga ? compare.ga[key] : "-";
    row.innerHTML = `<td>${key}</td><td>${baseline}</td><td>${ga}</td>`;
    compareBody.appendChild(row);
  }
}

async function fetchConfig() {
  // Fetch defaults and scale map from viewer-service.
  const resp = await fetch("/api/config");
  config = await resp.json();
  scaleEl.textContent = config.defaults.scale;
  seedEl.textContent = config.defaults.seed;
  replanEl.textContent = `${config.defaults.ga_replan_interval_s}s`;
  const scaleCfg = config.scale_map[config.defaults.scale];
  if (scaleCfg) {
    robotsInput.value = scaleCfg.robots;
    jobsInput.value = scaleCfg.jobs;
  }
}

async function startRun(mode) {
  // Trigger a run via viewer-service proxy.
  const counts = selectedCounts();
  if (counts.error) {
    alert(counts.error);
    return;
  }
  const payload = {
    mode,
    seed: config.defaults.seed,
    scale: config.defaults.scale,
  };
  if (counts.robots !== null && counts.jobs !== null) {
    payload.robots = counts.robots;
    payload.jobs = counts.jobs;
  }
  const resp = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await resp.json();
  if (!resp.ok) {
    alert(`Run failed to start: ${body.error || resp.statusText}`);
    return;
  }
  currentRunId = body.run_id;
  runIdEl.textContent = currentRunId;
  pollMetrics(currentRunId);
}

async function pollMetrics(runId) {
  // Poll fleet-api for metrics until available.
  const interval = setInterval(async () => {
    const resp = await fetch(`/api/runs/${runId}/metrics`);
    const body = await resp.json();
    if (resp.ok) {
      clearInterval(interval);
      renderMetrics(body);
      await compareRuns();
    }
  }, 2000);
}

async function compareRuns() {
  // Fetch latest baseline vs GA metrics.
  const counts = selectedCounts();
  if (counts.error) {
    alert(counts.error);
    return;
  }
  const params = new URLSearchParams({
    seed: String(config.defaults.seed),
    scale: config.defaults.scale,
  });
  if (counts.robots !== null && counts.jobs !== null) {
    params.set("robots", String(counts.robots));
    params.set("jobs", String(counts.jobs));
  }
  const resp = await fetch(`/api/runs/compare?${params.toString()}`);
  const body = await resp.json();
  renderCompare(body);
}

function connectWS() {
  // WebSocket connection for live snapshot streaming.
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/ws`);

  ws.onopen = () => {
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 5000);
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event_type !== "snapshot.tick") {
      return;
    }
    currentSnapshot = data.snapshot;
    drawSnapshot(currentSnapshot);
  };

  ws.onclose = () => {
    setTimeout(connectWS, 1000);
  };
}

async function init() {
  // Page initialization.
  await fetchConfig();
  connectWS();
  drawSnapshot(null);

  document.getElementById("run-baseline").addEventListener("click", () => startRun("baseline"));
  document.getElementById("run-ga").addEventListener("click", () => startRun("ga"));
  document.getElementById("compare").addEventListener("click", compareRuns);
}

init();
