/*
  File: services/viewer-service-py/app/static/app.js
  Purpose: SaaS dashboard UI and smooth 2D fleet map renderer.
*/

const canvas = document.getElementById("fleet-canvas");
const ctx = canvas.getContext("2d");

const dom = {
  navButtons: Array.from(document.querySelectorAll(".nav-btn")),
  pages: {
    dashboard: document.getElementById("page-dashboard"),
    runs: document.getElementById("page-runs"),
    robots: document.getElementById("page-robots"),
    jobs: document.getElementById("page-jobs"),
  },
  pageTitle: document.getElementById("page-title"),
  connStatus: document.getElementById("conn-status"),
  clock: document.getElementById("clock"),

  defaultScale: document.getElementById("default-scale"),
  defaultSeed: document.getElementById("default-seed"),
  defaultMode: document.getElementById("default-mode"),
  defaultReplan: document.getElementById("default-replan"),

  modeSelect: document.getElementById("mode-select"),
  seedInput: document.getElementById("seed-input"),
  scaleSelect: document.getElementById("scale-select"),
  robotsInput: document.getElementById("robots-input"),
  jobsInput: document.getElementById("jobs-input"),

  runSelectedBtn: document.getElementById("run-selected"),
  runBaselineBtn: document.getElementById("run-baseline"),
  runGaBtn: document.getElementById("run-ga"),
  refreshCompareBtn: document.getElementById("refresh-compare"),
  refreshRunsBtn: document.getElementById("refresh-runs"),

  activeRunId: document.getElementById("active-run-id"),
  runStatus: document.getElementById("run-status"),

  kpiOnTime: document.getElementById("kpi-on-time"),
  kpiDistance: document.getElementById("kpi-distance"),
  kpiAvg: document.getElementById("kpi-avg"),
  kpiLate: document.getElementById("kpi-late"),

  simTime: document.getElementById("sim-time"),
  mapScale: document.getElementById("map-scale"),

  toggleZones: document.getElementById("toggle-zones"),
  toggleJobs: document.getElementById("toggle-jobs"),
  toggleAssignments: document.getElementById("toggle-assignments"),
  toggleTrails: document.getElementById("toggle-trails"),
  toggleFollow: document.getElementById("toggle-follow"),
  followRobotSelect: document.getElementById("follow-robot-select"),

  fitWorldBtn: document.getElementById("fit-world"),
  zoomInBtn: document.getElementById("zoom-in"),
  zoomOutBtn: document.getElementById("zoom-out"),

  compareBody: document.getElementById("compare-body"),
  runsBody: document.getElementById("runs-body"),
  robotsBody: document.getElementById("robots-body"),
  jobsBody: document.getElementById("jobs-body"),
  activityList: document.getElementById("activity-list"),

  robotFilter: document.getElementById("robot-filter"),
  jobFilter: document.getElementById("job-filter"),
};

const PAGE_TITLES = {
  dashboard: "Dashboard",
  runs: "Runs",
  robots: "Robots",
  jobs: "Jobs",
};

const STATE_COLORS = {
  idle: [15, 138, 120],
  moving_to_pickup: [47, 109, 216],
  moving_to_dropoff: [47, 109, 216],
  charging: [127, 86, 217],
};

const appState = {
  config: null,
  activePage: "dashboard",
  connection: "connecting",
  ws: null,
  wsHeartbeat: null,

  activeRunId: null,
  activeRunStatus: "idle",
  metricsPollHandle: null,

  latestSnapshot: null,
  latestRunId: null,
  latestJobs: [],
  simTimeS: 0,

  runHistory: [],
  metricsByRunId: new Map(),
  compareData: null,

  robotTracks: new Map(),
  lastSnapshotAtMs: null,
  lastTableRenderMs: 0,

  activity: [],

  map: {
    worldSize: 100,
    width: 0,
    height: 0,
    baseScale: 1,
    worldCenterX: 50,
    worldCenterY: 50,
    zoom: 1,
    panX: 0,
    panY: 0,
    isPanning: false,
    panLastX: 0,
    panLastY: 0,
  },

  render: {
    frameHandle: null,
    lastFrameMs: 0,
  },
};

function clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function smoothStep(t) {
  const v = clamp(t, 0, 1);
  return v * v * (3 - 2 * v);
}

function formatNum(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(digits);
}

function formatTimestamp(raw) {
  if (!raw) {
    return "-";
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return String(raw);
  }
  return date.toLocaleTimeString();
}

function addActivity(message, level = "info") {
  const entry = {
    message,
    level,
    ts: new Date().toISOString(),
  };
  appState.activity.unshift(entry);
  if (appState.activity.length > 60) {
    appState.activity = appState.activity.slice(0, 60);
  }
  renderActivityFeed();
}

function renderActivityFeed() {
  dom.activityList.innerHTML = "";
  if (appState.activity.length === 0) {
    const li = document.createElement("li");
    li.className = "text-soft";
    li.textContent = "No events yet.";
    dom.activityList.appendChild(li);
    return;
  }
  for (const item of appState.activity.slice(0, 20)) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${formatTimestamp(item.ts)}</strong> ${item.message}`;
    if (item.level === "warn") {
      li.classList.add("text-warn");
    }
    if (item.level === "ok") {
      li.classList.add("text-ok");
    }
    dom.activityList.appendChild(li);
  }
}

function setConnectionStatus(status, label) {
  appState.connection = status;
  dom.connStatus.className = `conn-badge ${status}`;
  dom.connStatus.textContent = label;
}

function updateClock() {
  dom.clock.textContent = new Date().toLocaleTimeString();
}

function switchPage(page) {
  appState.activePage = page;
  dom.pageTitle.textContent = PAGE_TITLES[page] || "Dashboard";
  for (const [name, element] of Object.entries(dom.pages)) {
    if (name === page) {
      element.classList.add("active");
    } else {
      element.classList.remove("active");
    }
  }
  for (const btn of dom.navButtons) {
    if (btn.dataset.page === page) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  }
}

function selectedCounts() {
  const robotsRaw = Number.parseInt(dom.robotsInput.value, 10);
  const jobsRaw = Number.parseInt(dom.jobsInput.value, 10);
  if (Number.isNaN(robotsRaw) && Number.isNaN(jobsRaw)) {
    return { robots: null, jobs: null };
  }
  if (Number.isNaN(robotsRaw) || Number.isNaN(jobsRaw) || robotsRaw <= 0 || jobsRaw <= 0) {
    return { robots: null, jobs: null, error: "Robots and jobs must both be positive integers." };
  }
  return { robots: robotsRaw, jobs: jobsRaw };
}

function inferredWorldSize(snapshot, robots, jobs) {
  const rawWorldSize = Number(snapshot.world_size);
  if (Number.isFinite(rawWorldSize) && rawWorldSize > 0) {
    return Math.ceil(rawWorldSize);
  }

  let maxCoord = 0;
  for (const robot of robots) {
    maxCoord = Math.max(maxCoord, Number(robot.x || 0), Number(robot.y || 0));
  }
  for (const job of jobs) {
    maxCoord = Math.max(
      maxCoord,
      Number(job.pickup_x || 0),
      Number(job.pickup_y || 0),
      Number(job.dropoff_x || 0),
      Number(job.dropoff_y || 0),
    );
  }

  const inferred = Math.ceil(maxCoord + 8);
  return clamp(inferred, 40, 1000);
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    ...options,
  });
  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { error: text };
    }
  }
  return {
    ok: response.ok,
    status: response.status,
    body,
  };
}

function stateColorTriplet(state) {
  if (STATE_COLORS[state]) {
    return STATE_COLORS[state];
  }
  return [18, 33, 45];
}

function rgbaFromTriplet(triplet, alpha = 1) {
  return `rgba(${triplet[0]}, ${triplet[1]}, ${triplet[2]}, ${alpha})`;
}

function ensureTrack(robot, nowMs, interpWindowMs) {
  const robotId = Number(robot.id);
  let track = appState.robotTracks.get(robotId);
  const colorTarget = stateColorTriplet(robot.state);

  if (!track) {
    track = {
      id: robotId,
      fromX: Number(robot.x),
      fromY: Number(robot.y),
      toX: Number(robot.x),
      toY: Number(robot.y),
      startMs: nowMs,
      endMs: nowMs + interpWindowMs,
      prevRenderX: Number(robot.x),
      prevRenderY: Number(robot.y),
      heading: 0,
      state: String(robot.state || "idle"),
      battery: Number(robot.battery || 0),
      speed: Number(robot.speed || 1),
      currentJobId: robot.current_job_id || null,
      trail: [{ x: Number(robot.x), y: Number(robot.y), ms: nowMs }],
      lastTrailMs: nowMs,
      colorTriplet: [...colorTarget],
      colorTarget: [...colorTarget],
      stateChangedAtMs: nowMs,
      pulseOffset: (robotId * 1.61803398875) % (Math.PI * 2),
      lastSeenMs: nowMs,
    };
    appState.robotTracks.set(robotId, track);
    return track;
  }

  const current = getInterpolatedPosition(track, nowMs);
  track.fromX = current.x;
  track.fromY = current.y;
  track.toX = Number(robot.x);
  track.toY = Number(robot.y);
  track.startMs = nowMs;
  track.endMs = nowMs + interpWindowMs;

  if (track.state !== String(robot.state || "idle")) {
    track.stateChangedAtMs = nowMs;
    addActivity(`Robot ${robotId} state ${track.state} -> ${robot.state}`);
  }

  track.state = String(robot.state || "idle");
  track.battery = Number(robot.battery || 0);
  track.speed = Number(robot.speed || 1);
  track.currentJobId = robot.current_job_id || null;
  track.colorTarget = [...colorTarget];
  track.lastSeenMs = nowMs;

  return track;
}

function getInterpolatedPosition(track, nowMs) {
  const duration = Math.max(1, track.endMs - track.startMs);
  const ratio = smoothStep((nowMs - track.startMs) / duration);
  return {
    x: lerp(track.fromX, track.toX, ratio),
    y: lerp(track.fromY, track.toY, ratio),
  };
}

function updateTrackDynamics(track, nowMs) {
  const pos = getInterpolatedPosition(track, nowMs);

  const dx = pos.x - track.prevRenderX;
  const dy = pos.y - track.prevRenderY;
  const distance = Math.hypot(dx, dy);
  if (distance > 0.0001) {
    track.heading = Math.atan2(dy, dx);
  }

  if (distance > 0.1 && nowMs - track.lastTrailMs > 80) {
    track.trail.push({ x: pos.x, y: pos.y, ms: nowMs });
    track.lastTrailMs = nowMs;
    if (track.trail.length > 60) {
      track.trail = track.trail.slice(track.trail.length - 60);
    }
  }

  for (let i = 0; i < 3; i += 1) {
    track.colorTriplet[i] = lerp(track.colorTriplet[i], track.colorTarget[i], 0.15);
  }

  track.prevRenderX = pos.x;
  track.prevRenderY = pos.y;

  return pos;
}

function worldToScreen(x, y) {
  const map = appState.map;
  const scale = map.baseScale * map.zoom;
  return {
    x: (x - map.worldCenterX) * scale + map.width / 2 + map.panX,
    y: map.height / 2 - (y - map.worldCenterY) * scale + map.panY,
  };
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * dpr);
  canvas.height = Math.floor(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  appState.map.width = rect.width;
  appState.map.height = rect.height;
  appState.map.baseScale = Math.max(1, Math.min(rect.width, rect.height) / (appState.map.worldSize + 10));
}

function resetMapView() {
  appState.map.zoom = 1;
  appState.map.panX = 0;
  appState.map.panY = 0;
}

function drawMapBackground() {
  const gradient = ctx.createLinearGradient(0, 0, 0, appState.map.height);
  gradient.addColorStop(0, "#f8fbff");
  gradient.addColorStop(1, "#edf3fb");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, appState.map.width, appState.map.height);
}

function drawGrid() {
  const step = 10;
  ctx.strokeStyle = "rgba(118, 141, 164, 0.25)";
  ctx.lineWidth = 1;

  for (let x = 0; x <= appState.map.worldSize; x += step) {
    const p1 = worldToScreen(x, 0);
    const p2 = worldToScreen(x, appState.map.worldSize);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  }

  for (let y = 0; y <= appState.map.worldSize; y += step) {
    const p1 = worldToScreen(0, y);
    const p2 = worldToScreen(appState.map.worldSize, y);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  }
}

function drawZones() {
  const zones = [
    { name: "Receiving", x: 4, y: 70, w: 25, h: 24, color: "rgba(56, 189, 248, 0.12)" },
    { name: "Storage", x: 68, y: 62, w: 28, h: 30, color: "rgba(52, 211, 153, 0.12)" },
    { name: "Charging", x: 70, y: 6, w: 24, h: 18, color: "rgba(127, 86, 217, 0.14)" },
  ];

  for (const zone of zones) {
    const topLeft = worldToScreen(zone.x, zone.y + zone.h);
    const bottomRight = worldToScreen(zone.x + zone.w, zone.y);
    const width = bottomRight.x - topLeft.x;
    const height = bottomRight.y - topLeft.y;

    ctx.fillStyle = zone.color;
    ctx.fillRect(topLeft.x, topLeft.y, width, height);
    ctx.strokeStyle = "rgba(77, 90, 104, 0.5)";
    ctx.strokeRect(topLeft.x, topLeft.y, width, height);
    ctx.fillStyle = "rgba(31, 47, 62, 0.9)";
    ctx.font = "11px Segoe UI";
    ctx.fillText(zone.name, topLeft.x + 6, topLeft.y + 14);
  }
}

function drawJobs() {
  for (const job of appState.latestJobs) {
    const pickup = worldToScreen(Number(job.pickup_x || 0), Number(job.pickup_y || 0));
    const dropoff = worldToScreen(Number(job.dropoff_x || 0), Number(job.dropoff_y || 0));

    let pickupColor = "#c36f20";
    if (job.state === "completed") {
      pickupColor = "#12805d";
    } else if (job.state === "failed") {
      pickupColor = "#d84a3c";
    }

    ctx.fillStyle = pickupColor;
    ctx.fillRect(pickup.x - 4, pickup.y - 4, 8, 8);

    ctx.strokeStyle = "#4d5a68";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(dropoff.x - 5, dropoff.y - 5);
    ctx.lineTo(dropoff.x + 5, dropoff.y + 5);
    ctx.moveTo(dropoff.x + 5, dropoff.y - 5);
    ctx.lineTo(dropoff.x - 5, dropoff.y + 5);
    ctx.stroke();
  }
}

function drawAssignmentLines(nowMs) {
  const jobsById = new Map(appState.latestJobs.map((job) => [String(job.id), job]));

  for (const track of appState.robotTracks.values()) {
    if (!track.currentJobId) {
      continue;
    }
    const job = jobsById.get(String(track.currentJobId));
    if (!job) {
      continue;
    }

    const pos = getInterpolatedPosition(track, nowMs);
    const robotPoint = worldToScreen(pos.x, pos.y);
    const pickup = worldToScreen(Number(job.pickup_x || 0), Number(job.pickup_y || 0));
    const dropoff = worldToScreen(Number(job.dropoff_x || 0), Number(job.dropoff_y || 0));

    ctx.strokeStyle = "rgba(52, 88, 128, 0.55)";
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    ctx.moveTo(robotPoint.x, robotPoint.y);
    ctx.lineTo(pickup.x, pickup.y);
    ctx.lineTo(dropoff.x, dropoff.y);
    ctx.stroke();
    ctx.setLineDash([]);

    const arrowX = lerp(pickup.x, dropoff.x, 0.55);
    const arrowY = lerp(pickup.y, dropoff.y, 0.55);
    const heading = Math.atan2(dropoff.y - pickup.y, dropoff.x - pickup.x);
    ctx.save();
    ctx.translate(arrowX, arrowY);
    ctx.rotate(heading);
    ctx.fillStyle = "rgba(52, 88, 128, 0.8)";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-7, 3.5);
    ctx.lineTo(-7, -3.5);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }
}

function drawTrails(nowMs) {
  for (const track of appState.robotTracks.values()) {
    if (track.trail.length < 2) {
      continue;
    }
    for (let i = 1; i < track.trail.length; i += 1) {
      const prev = track.trail[i - 1];
      const curr = track.trail[i];
      const ageMs = nowMs - curr.ms;
      const alpha = clamp(1 - ageMs / 5000, 0.05, 0.65);
      const p1 = worldToScreen(prev.x, prev.y);
      const p2 = worldToScreen(curr.x, curr.y);
      ctx.strokeStyle = `rgba(47, 109, 216, ${alpha})`;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }
  }
}

function drawRobots(nowMs) {
  for (const track of appState.robotTracks.values()) {
    const pos = updateTrackDynamics(track, nowMs);
    const screen = worldToScreen(pos.x, pos.y);

    const color = rgbaFromTriplet(track.colorTriplet, 1);
    const moving = track.state === "moving_to_pickup" || track.state === "moving_to_dropoff";

    const pulse = 0.5 + 0.5 * Math.sin(nowMs / 230 + track.pulseOffset);
    if (moving) {
      ctx.fillStyle = `rgba(47, 109, 216, ${0.13 + pulse * 0.13})`;
      ctx.beginPath();
      ctx.arc(screen.x, screen.y, 15 + pulse * 4, 0, Math.PI * 2);
      ctx.fill();
    }

    if (track.state === "charging") {
      ctx.strokeStyle = `rgba(127, 86, 217, ${0.2 + pulse * 0.6})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(screen.x, screen.y, 18 + pulse * 2, 0, Math.PI * 2);
      ctx.stroke();
    }

    const screenHeading = -track.heading;
    ctx.save();
    ctx.translate(screen.x, screen.y);
    ctx.rotate(screenHeading);

    ctx.fillStyle = color;
    ctx.strokeStyle = "rgba(20, 35, 51, 0.7)";
    ctx.lineWidth = 1;

    ctx.beginPath();
    ctx.moveTo(12, 0);
    ctx.lineTo(-8, 7);
    ctx.lineTo(-8, -7);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.restore();

    ctx.fillStyle = "#1f3142";
    ctx.font = "11px Segoe UI";
    ctx.fillText(`R${track.id}`, screen.x - 9, screen.y - 14);

    ctx.fillStyle = "rgba(230, 237, 243, 0.9)";
    ctx.fillRect(screen.x - 12, screen.y + 10, 24, 4);
    ctx.fillStyle = track.battery >= 20 ? "#138a61" : "#d84a3c";
    ctx.fillRect(screen.x - 12, screen.y + 10, 24 * clamp(track.battery / 100, 0, 1), 4);

    if (track.state === "charging") {
      ctx.fillStyle = "#7f56d9";
      ctx.font = "10px Segoe UI";
      ctx.fillText("CHG", screen.x - 11, screen.y + 24);
    }
  }
}

function drawMapOverlay() {
  ctx.fillStyle = "rgba(15, 32, 47, 0.95)";
  ctx.font = "12px Segoe UI";
  ctx.fillText(`Sim Time: ${appState.simTimeS}s`, 12, 18);
  ctx.fillText(`Robots: ${appState.robotTracks.size}`, 12, 34);
  ctx.fillText(`Jobs: ${appState.latestJobs.length}`, 12, 50);
}

function maybeFollowRobot() {
  if (!dom.toggleFollow.checked) {
    return;
  }
  const selectedRaw = dom.followRobotSelect.value;
  const selectedId = Number.parseInt(selectedRaw, 10);
  if (Number.isNaN(selectedId)) {
    return;
  }
  const track = appState.robotTracks.get(selectedId);
  if (!track) {
    return;
  }

  const pos = getInterpolatedPosition(track, performance.now());
  const scale = appState.map.baseScale * appState.map.zoom;
  const targetPanX = -((pos.x - appState.map.worldCenterX) * scale);
  const targetPanY = (pos.y - appState.map.worldCenterY) * scale;

  appState.map.panX = lerp(appState.map.panX, targetPanX, 0.08);
  appState.map.panY = lerp(appState.map.panY, targetPanY, 0.08);
}

function drawFrame(nowMs) {
  if (!appState.render.lastFrameMs) {
    appState.render.lastFrameMs = nowMs;
  }

  maybeFollowRobot();
  drawMapBackground();

  drawGrid();
  if (dom.toggleZones.checked) {
    drawZones();
  }
  if (dom.toggleJobs.checked) {
    drawJobs();
  }
  if (dom.toggleAssignments.checked) {
    drawAssignmentLines(nowMs);
  }
  if (dom.toggleTrails.checked) {
    drawTrails(nowMs);
  }
  drawRobots(nowMs);
  drawMapOverlay();

  dom.simTime.textContent = `Sim ${appState.simTimeS}s`;
  dom.mapScale.textContent = `Zoom ${appState.map.zoom.toFixed(2)}x`;

  appState.render.lastFrameMs = nowMs;
  appState.render.frameHandle = requestAnimationFrame(drawFrame);
}

function renderKpis(metrics) {
  if (!metrics) {
    dom.kpiOnTime.textContent = "-";
    dom.kpiDistance.textContent = "-";
    dom.kpiAvg.textContent = "-";
    dom.kpiLate.textContent = "-";
    return;
  }

  dom.kpiOnTime.textContent = `${formatNum(metrics.on_time_rate, 1)}%`;
  dom.kpiDistance.textContent = formatNum(metrics.total_distance, 2);
  dom.kpiAvg.textContent = `${formatNum(metrics.avg_completion_time, 2)}s`;
  dom.kpiLate.textContent = `${formatNum(metrics.max_lateness, 2)}s`;
}

function upsertRunHistory(item) {
  if (!item || !item.run_id) {
    return;
  }
  appState.runHistory = appState.runHistory.filter((run) => run.run_id !== item.run_id);
  appState.runHistory.unshift(item);
  appState.runHistory = appState.runHistory.slice(0, 50);
}

function updateRunStatus(runId, status) {
  appState.runHistory = appState.runHistory.map((run) => {
    if (run.run_id === runId) {
      return {
        ...run,
        status,
      };
    }
    return run;
  });
}

function renderRunsTable() {
  dom.runsBody.innerHTML = "";
  if (appState.runHistory.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = "<td colspan='6' class='text-soft'>No runs yet.</td>";
    dom.runsBody.appendChild(row);
    return;
  }

  for (const run of appState.runHistory) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><code>${run.run_id.slice(0, 12)}</code></td>
      <td>${run.mode || "-"}</td>
      <td>${run.scale || "-"}</td>
      <td>${run.seed ?? "-"}</td>
      <td>${run.status || "-"}</td>
      <td>${formatTimestamp(run.ts_utc || run.completed_at || run.created_at)}</td>
    `;
    dom.runsBody.appendChild(row);
  }
}

function renderCompare(compare) {
  appState.compareData = compare;
  dom.compareBody.innerHTML = "";

  if (!compare || compare.error) {
    const row = document.createElement("tr");
    row.innerHTML = "<td colspan='3' class='text-soft'>Comparison unavailable.</td>";
    dom.compareBody.appendChild(row);
    return;
  }

  const keys = ["on_time_rate", "total_distance", "avg_completion_time", "max_lateness"];
  for (const key of keys) {
    const baseline = compare.baseline ? compare.baseline[key] : "-";
    const ga = compare.ga ? compare.ga[key] : "-";
    const row = document.createElement("tr");
    row.innerHTML = `<td>${key}</td><td>${baseline}</td><td>${ga}</td>`;
    dom.compareBody.appendChild(row);
  }
}

function renderRobotsTable() {
  dom.robotsBody.innerHTML = "";
  const filter = dom.robotFilter.value;

  const robots = Array.from(appState.robotTracks.values())
    .map((track) => ({
      id: track.id,
      state: track.state,
      battery: track.battery,
      currentJobId: track.currentJobId,
      x: track.prevRenderX,
      y: track.prevRenderY,
    }))
    .sort((a, b) => a.id - b.id)
    .filter((robot) => filter === "all" || robot.state === filter);

  if (robots.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = "<td colspan='6' class='text-soft'>No robot rows to display.</td>";
    dom.robotsBody.appendChild(row);
    return;
  }

  for (const robot of robots) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>R${robot.id}</td>
      <td>${robot.state}</td>
      <td>${formatNum(robot.battery, 1)}%</td>
      <td>${robot.currentJobId || "-"}</td>
      <td>${formatNum(robot.x, 2)}</td>
      <td>${formatNum(robot.y, 2)}</td>
    `;
    dom.robotsBody.appendChild(row);
  }
}

function renderJobsTable() {
  dom.jobsBody.innerHTML = "";
  const filter = dom.jobFilter.value;

  const jobs = [...appState.latestJobs]
    .sort((a, b) => {
      const dlA = Number(a.deadline_ts || 0);
      const dlB = Number(b.deadline_ts || 0);
      if (dlA !== dlB) {
        return dlA - dlB;
      }
      return String(a.id).localeCompare(String(b.id));
    })
    .filter((job) => filter === "all" || String(job.state) === filter);

  if (jobs.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = "<td colspan='6' class='text-soft'>No job rows to display.</td>";
    dom.jobsBody.appendChild(row);
    return;
  }

  for (const job of jobs) {
    const lateness = Number(job.lateness_s ?? Math.max(0, appState.simTimeS - Number(job.deadline_ts || 0)));
    const assignedRobot = job.assigned_robot_id || job.assigned_robot || "-";
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${job.id}</td>
      <td>${job.state}</td>
      <td>${job.priority}</td>
      <td>${job.deadline_ts}</td>
      <td>${formatNum(lateness, 2)}</td>
      <td>${assignedRobot}</td>
    `;
    dom.jobsBody.appendChild(row);
  }
}

function refreshFollowRobotOptions() {
  const selected = dom.followRobotSelect.value;
  const robotIds = Array.from(appState.robotTracks.keys()).sort((a, b) => a - b);

  dom.followRobotSelect.innerHTML = "<option value=''>None</option>";
  for (const id of robotIds) {
    const option = document.createElement("option");
    option.value = String(id);
    option.textContent = `R${id}`;
    dom.followRobotSelect.appendChild(option);
  }

  if (selected && robotIds.includes(Number(selected))) {
    dom.followRobotSelect.value = selected;
  }
}

function resetVisualRunState() {
  appState.robotTracks.clear();
  appState.latestJobs = [];
  appState.simTimeS = 0;
  appState.lastSnapshotAtMs = null;
  refreshFollowRobotOptions();
  renderRobotsTable();
  renderJobsTable();
}

function handleSnapshotEvent(event) {
  const snapshot = event.snapshot || {};
  const robots = Array.isArray(snapshot.robots) ? snapshot.robots : [];
  const jobs = Array.isArray(snapshot.jobs) ? snapshot.jobs : [];
  const nextWorldSize = inferredWorldSize(snapshot, robots, jobs);
  if (nextWorldSize !== appState.map.worldSize) {
    appState.map.worldSize = nextWorldSize;
    appState.map.worldCenterX = nextWorldSize / 2;
    appState.map.worldCenterY = nextWorldSize / 2;
    resizeCanvas();
  }

  const runId = String(event.run_id || "");
  if (runId && appState.latestRunId && appState.latestRunId !== runId) {
    resetVisualRunState();
  }
  if (runId) {
    appState.latestRunId = runId;
  }

  appState.latestSnapshot = snapshot;
  appState.latestJobs = jobs;
  appState.simTimeS = Number(event.sim_time_s ?? snapshot.sim_time_s ?? appState.simTimeS);

  const nowMs = performance.now();
  const deltaMs = appState.lastSnapshotAtMs ? nowMs - appState.lastSnapshotAtMs : 220;
  const interpMs = clamp(deltaMs * 0.95, 120, 700);
  appState.lastSnapshotAtMs = nowMs;

  const seen = new Set();
  const sortedRobots = [...robots].sort((a, b) => Number(a.id) - Number(b.id));
  for (const robot of sortedRobots) {
    const robotId = Number(robot.id);
    seen.add(robotId);
    ensureTrack(robot, nowMs, interpMs);
  }

  for (const [robotId] of appState.robotTracks) {
    if (!seen.has(robotId)) {
      appState.robotTracks.delete(robotId);
    }
  }

  refreshFollowRobotOptions();

  const shouldRenderTables = nowMs - appState.lastTableRenderMs > 250;
  if (shouldRenderTables) {
    appState.lastTableRenderMs = nowMs;
    renderRobotsTable();
    renderJobsTable();
  }
}

async function startRun(modeOverride = null) {
  const mode = modeOverride || dom.modeSelect.value;
  const seed = Number.parseInt(dom.seedInput.value, 10);
  const scale = dom.scaleSelect.value;
  const counts = selectedCounts();

  if (!mode || Number.isNaN(seed) || !scale) {
    addActivity("Run input is invalid. Check mode/seed/scale.", "warn");
    return;
  }
  if (counts.error) {
    addActivity(counts.error, "warn");
    return;
  }

  const payload = { mode, seed, scale };
  if (counts.robots !== null && counts.jobs !== null) {
    payload.robots = counts.robots;
    payload.jobs = counts.jobs;
  }

  const { ok, body } = await fetchJSON("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!ok) {
    addActivity(`Run start failed: ${body.error || "unknown error"}`, "warn");
    return;
  }

  const runId = String(body.run_id || body.id || "");
  if (!runId) {
    addActivity("Run start failed: missing run_id", "warn");
    return;
  }

  appState.activeRunId = runId;
  appState.activeRunStatus = "started";
  dom.activeRunId.textContent = runId;
  dom.runStatus.textContent = appState.activeRunStatus;

  upsertRunHistory({
    run_id: runId,
    mode,
    seed,
    scale,
    status: "started",
    ts_utc: new Date().toISOString(),
  });
  renderRunsTable();

  addActivity(`Run started (${mode}) id=${runId.slice(0, 8)}`, "ok");
  startMetricsPolling(runId);
  switchPage("dashboard");
}

function startMetricsPolling(runId) {
  if (appState.metricsPollHandle !== null) {
    clearInterval(appState.metricsPollHandle);
    appState.metricsPollHandle = null;
  }

  appState.metricsPollHandle = setInterval(async () => {
    const metricsResp = await fetchJSON(`/api/runs/${runId}/metrics`);
    if (metricsResp.ok) {
      const metrics = metricsResp.body;
      appState.metricsByRunId.set(runId, metrics);
      renderKpis(metrics);
      updateRunStatus(runId, "completed");
      renderRunsTable();

      if (appState.activeRunId === runId) {
        appState.activeRunStatus = "completed";
        dom.runStatus.textContent = "completed";
      }

      addActivity(`Run completed id=${runId.slice(0, 8)} (metrics persisted)`, "ok");
      clearInterval(appState.metricsPollHandle);
      appState.metricsPollHandle = null;
      await refreshCompare();
      return;
    }

    const runResp = await fetchJSON(`/api/runs/${runId}`);
    if (runResp.ok && runResp.body.status) {
      const status = String(runResp.body.status);
      updateRunStatus(runId, status);
      renderRunsTable();
      if (appState.activeRunId === runId) {
        appState.activeRunStatus = status;
        dom.runStatus.textContent = status;
      }
      if (status === "failed" || status === "stopped") {
        clearInterval(appState.metricsPollHandle);
        appState.metricsPollHandle = null;
        addActivity(`Run ${status} id=${runId.slice(0, 8)}`, "warn");
      }
    }
  }, 1500);
}

async function refreshCompare() {
  if (!appState.config) {
    return;
  }
  const seed = Number.parseInt(dom.seedInput.value, 10);
  const scale = dom.scaleSelect.value;
  const counts = selectedCounts();
  const params = new URLSearchParams({
    seed: String(Number.isNaN(seed) ? appState.config.defaults.seed : seed),
    scale: scale || appState.config.defaults.scale,
  });
  if (!counts.error && counts.robots !== null && counts.jobs !== null) {
    params.set("robots", String(counts.robots));
    params.set("jobs", String(counts.jobs));
  }

  const { body } = await fetchJSON(`/api/runs/compare?${params.toString()}`);
  renderCompare(body);
}

async function refreshRecentRuns() {
  const { ok, body } = await fetchJSON("/api/runs/recent?limit=25");
  if (!ok || !body.items) {
    renderRunsTable();
    return;
  }

  const recentItems = Array.isArray(body.items) ? body.items : [];
  for (const item of recentItems) {
    upsertRunHistory({
      run_id: String(item.run_id || ""),
      mode: item.mode || "-",
      seed: item.seed,
      scale: item.scale,
      status: item.status || "completed",
      ts_utc: item.ts_utc,
    });
    if (item.metrics && item.run_id) {
      appState.metricsByRunId.set(String(item.run_id), item.metrics);
    }
  }

  renderRunsTable();
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${protocol}://${window.location.host}/ws`;

  setConnectionStatus("connecting", "Connecting");
  const ws = new WebSocket(url);
  appState.ws = ws;

  ws.onopen = () => {
    setConnectionStatus("connected", "Connected");
    addActivity("WebSocket connected", "ok");

    if (appState.wsHeartbeat !== null) {
      clearInterval(appState.wsHeartbeat);
    }
    appState.wsHeartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 5000);
  };

  ws.onmessage = async (event) => {
    let data = null;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }

    if (!data || !data.event_type) {
      return;
    }

    if (data.event_type === "snapshot.tick") {
      handleSnapshotEvent(data);
      return;
    }

    if (data.event_type === "run.completed") {
      const runId = String(data.run_id || "");
      const status = String(data.status || "completed");

      if (runId) {
        updateRunStatus(runId, status);
        upsertRunHistory({
          run_id: runId,
          mode: data.mode || "-",
          seed: data.seed,
          scale: data.scale,
          status,
          ts_utc: data.ts_utc,
        });
        renderRunsTable();
      }

      if (data.metrics && runId) {
        appState.metricsByRunId.set(runId, data.metrics);
        renderKpis(data.metrics);
      }

      if (runId && appState.activeRunId === runId) {
        appState.activeRunStatus = status;
        dom.runStatus.textContent = status;
      }

      addActivity(`run.completed id=${runId.slice(0, 8)} status=${status}`, status === "completed" ? "ok" : "warn");
      await refreshCompare();
    }
  };

  ws.onclose = () => {
    if (appState.wsHeartbeat !== null) {
      clearInterval(appState.wsHeartbeat);
      appState.wsHeartbeat = null;
    }
    setConnectionStatus("disconnected", "Reconnecting");
    setTimeout(connectWebSocket, 1200);
  };
}

function updateDefaultsUI() {
  if (!appState.config) {
    return;
  }
  dom.defaultScale.textContent = appState.config.defaults.scale;
  dom.defaultSeed.textContent = appState.config.defaults.seed;
  dom.defaultMode.textContent = appState.config.defaults.mode;
  dom.defaultReplan.textContent = `${appState.config.defaults.ga_replan_interval_s}s`;
}

function applyScalePreset(scaleKey) {
  if (!appState.config || !appState.config.scale_map) {
    return;
  }
  const preset = appState.config.scale_map[scaleKey];
  if (!preset) {
    return;
  }
  dom.robotsInput.value = String(preset.robots);
  dom.jobsInput.value = String(preset.jobs);
}

async function fetchConfig() {
  const { ok, body } = await fetchJSON("/api/config");
  if (!ok) {
    addActivity("Unable to load /api/config", "warn");
    return;
  }

  appState.config = body;

  dom.modeSelect.value = body.defaults.mode;
  dom.seedInput.value = String(body.defaults.seed);

  dom.scaleSelect.innerHTML = "";
  for (const scaleKey of Object.keys(body.scale_map || {})) {
    const option = document.createElement("option");
    option.value = scaleKey;
    option.textContent = scaleKey;
    dom.scaleSelect.appendChild(option);
  }

  dom.scaleSelect.value = body.defaults.scale;
  applyScalePreset(body.defaults.scale);
  updateDefaultsUI();
}

function bindMapControls() {
  dom.fitWorldBtn.addEventListener("click", () => {
    resetMapView();
  });

  dom.zoomInBtn.addEventListener("click", () => {
    appState.map.zoom = clamp(appState.map.zoom * 1.15, 0.35, 5);
  });

  dom.zoomOutBtn.addEventListener("click", () => {
    appState.map.zoom = clamp(appState.map.zoom * 0.87, 0.35, 5);
  });

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.12 : 0.89;
    appState.map.zoom = clamp(appState.map.zoom * factor, 0.35, 5);
  });

  canvas.addEventListener("mousedown", (event) => {
    appState.map.isPanning = true;
    appState.map.panLastX = event.clientX;
    appState.map.panLastY = event.clientY;
    canvas.classList.add("panning");
  });

  window.addEventListener("mousemove", (event) => {
    if (!appState.map.isPanning) {
      return;
    }
    const dx = event.clientX - appState.map.panLastX;
    const dy = event.clientY - appState.map.panLastY;
    appState.map.panX += dx;
    appState.map.panY += dy;
    appState.map.panLastX = event.clientX;
    appState.map.panLastY = event.clientY;
  });

  window.addEventListener("mouseup", () => {
    appState.map.isPanning = false;
    canvas.classList.remove("panning");
  });

  dom.followRobotSelect.addEventListener("change", () => {
    if (!dom.followRobotSelect.value) {
      dom.toggleFollow.checked = false;
    }
  });

  dom.toggleFollow.addEventListener("change", () => {
    if (dom.toggleFollow.checked && !dom.followRobotSelect.value) {
      const firstRobot = appState.robotTracks.keys().next();
      if (!firstRobot.done) {
        dom.followRobotSelect.value = String(firstRobot.value);
      }
    }
  });
}

function bindEvents() {
  for (const btn of dom.navButtons) {
    btn.addEventListener("click", () => switchPage(btn.dataset.page));
  }

  dom.modeSelect.addEventListener("change", () => {
    addActivity(`Mode selected: ${dom.modeSelect.value}`);
  });

  dom.scaleSelect.addEventListener("change", () => {
    applyScalePreset(dom.scaleSelect.value);
    addActivity(`Scale preset selected: ${dom.scaleSelect.value}`);
  });

  dom.runSelectedBtn.addEventListener("click", () => startRun(null));
  dom.runBaselineBtn.addEventListener("click", () => startRun("baseline"));
  dom.runGaBtn.addEventListener("click", () => startRun("ga"));
  dom.refreshCompareBtn.addEventListener("click", refreshCompare);
  dom.refreshRunsBtn.addEventListener("click", refreshRecentRuns);

  dom.robotFilter.addEventListener("change", renderRobotsTable);
  dom.jobFilter.addEventListener("change", renderJobsTable);

  bindMapControls();
}

async function init() {
  updateClock();
  setInterval(updateClock, 1000);

  renderActivityFeed();
  renderKpis(null);

  bindEvents();
  await fetchConfig();
  await refreshRecentRuns();
  await refreshCompare();

  resetMapView();
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  connectWebSocket();

  if (!appState.render.frameHandle) {
    appState.render.frameHandle = requestAnimationFrame(drawFrame);
  }

  addActivity("Viewer initialized");
}

init();
