let researcherVideos = null;

async function loadRuns() {
  const response = await fetch("/api/runs");
  const payload = await response.json();
  const list = document.getElementById("run-list");
  list.innerHTML = "";
  for (const run of payload.runs || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run-card";
    button.innerHTML = `<strong>${run.run_id}</strong><span>${run.status} · ${run.viewer_mode || "unknown"}</span>`;
    button.addEventListener("click", () => loadRun(run.run_id));
    list.appendChild(button);
  }
  if ((payload.runs || []).length === 0) {
    list.textContent = "No local validation runs found.";
  }
}

async function loadRun(runId) {
  const [response, videos] = await Promise.all([
    fetch(`/api/runs/${encodeURIComponent(runId)}`),
    loadResearcherVideos()
  ]);
  const payload = await response.json();
  const detail = document.getElementById("run-detail");
  if (!response.ok) {
    detail.textContent = payload.error || "Unable to load run.";
    return;
  }
  const reliability = payload.report?.technical_reliability || {};
  const records = payload.records || [];
  detail.innerHTML = `
    <h3>${payload.run_id}</h3>
    <p>${payload.status} · ${reliability.technical_valid_episode_runs || 0}/${reliability.total_episode_runs || 0} technically valid</p>
    <div class="metric-grid"></div>
    <div id="episode-inspector" class="episode-inspector"></div>
  `;
  const grid = detail.querySelector(".metric-grid");
  for (const record of records) {
    const axes = record.metrics?.behavioral_metrics?.axes || {};
    const card = document.createElement("button");
    card.type = "button";
    card.className = "metric-card metric-card-button";
    card.innerHTML = `<h3>${record.episode_id}</h3>`;
    for (const [axisId, axis] of Object.entries(axes)) {
      const row = document.createElement("div");
      row.className = "score-row";
      const score = axis.score == null ? "n/a" : Math.round(axis.score * 100);
      row.innerHTML = `<span>${axisId}</span><strong>${score}</strong>`;
      card.appendChild(row);
    }
    card.addEventListener("click", () => renderEpisodeInspector(record, videos));
    grid.appendChild(card);
  }
  if (records[0]) {
    renderEpisodeInspector(records[0], videos);
  }
}

async function loadResearcherVideos() {
  if (researcherVideos !== null) {
    return researcherVideos;
  }
  try {
    const response = await fetch("/api/survey/videos");
    const payload = await response.json();
    researcherVideos = response.ok ? payload.videos || [] : [];
  } catch {
    researcherVideos = [];
  }
  return researcherVideos;
}

function renderEpisodeInspector(record, videos) {
  const inspector = document.getElementById("episode-inspector");
  if (!inspector) {
    return;
  }
  const matches = matchingVideos(record, videos);
  const axes = record.metrics?.behavioral_metrics?.axes || {};
  const axisRows = Object.entries(axes)
    .map(([axisId, axis]) => {
      const score = axis.score == null ? "n/a" : Math.round(axis.score * 100);
      return `<div class="score-row"><span>${escapeHtml(axisId)}</span><strong>${score}</strong></div>`;
    })
    .join("");
  const media = matches.length === 0
    ? `<p class="muted">No survey video matched this episode id.</p>`
    : matches
      .map((video) => `
        <article class="research-video">
          <video class="research-player" controls preload="metadata" src="${videoUrl(video.path)}"></video>
          <strong>${escapeHtml(video.title || video.video_id)}</strong>
          <span class="muted">${escapeHtml(video.policy_id)} · ${escapeHtml(video.viewpoint)} · ${escapeHtml(video.episode_id)}</span>
        </article>
      `)
      .join("");
  inspector.innerHTML = `
    <div class="inspector-heading">
      <div>
        <h3>${escapeHtml(record.episode_id || "Episode")}</h3>
        <p>${escapeHtml(record.terminal_status || "unknown")} · iteration ${escapeHtml(record.iteration ?? "")}</p>
      </div>
      <span class="status-pill">${record.technical_valid ? "technical valid" : "technical issue"}</span>
    </div>
    <div class="media-score-layout">
      <div class="research-video-grid">${media}</div>
      <div class="metric-card compact-card">${axisRows}</div>
    </div>
  `;
}

function matchingVideos(record, videos) {
  const ids = episodeAliases(record.episode_id || "");
  return (videos || []).filter((video) => {
    const metrics = video.metrics || {};
    return ids.has(video.episode_id) || ids.has(metrics.source_episode_id);
  });
}

function episodeAliases(episodeId) {
  const aliases = new Set([episodeId]);
  const suffix = String(episodeId).replace(/^(g1|go2)_/, "");
  aliases.add(suffix);
  const map = {
    approach_user: "point_to_point_open",
    lateral_open: "point_to_point_static_obstacles",
    lateral_static_dynamic_obstacles: "point_to_point_dynamic_npcs",
    point_to_point_open: "approach_user",
    point_to_point_static_obstacles: "lateral_open",
    point_to_point_dynamic_npcs: "lateral_static_dynamic_obstacles"
  };
  if (map[suffix]) {
    aliases.add(map[suffix]);
    aliases.add(`g1_${map[suffix]}`);
    aliases.add(`go2_${map[suffix]}`);
  }
  return aliases;
}

function videoUrl(path) {
  return `/videos/${String(path || "").split("/").map(encodeURIComponent).join("/")}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.getElementById("refresh-runs")?.addEventListener("click", loadRuns);
loadRuns();
