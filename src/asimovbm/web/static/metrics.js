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
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
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
  `;
  const grid = detail.querySelector(".metric-grid");
  for (const record of records) {
    const axes = record.metrics?.behavioral_metrics?.axes || {};
    const card = document.createElement("article");
    card.className = "metric-card";
    card.innerHTML = `<h3>${record.episode_id}</h3>`;
    for (const [axisId, axis] of Object.entries(axes)) {
      const row = document.createElement("div");
      row.className = "score-row";
      const score = axis.score == null ? "n/a" : Math.round(axis.score * 100);
      row.innerHTML = `<span>${axisId}</span><strong>${score}</strong>`;
      card.appendChild(row);
    }
    grid.appendChild(card);
  }
}

document.getElementById("refresh-runs")?.addEventListener("click", loadRuns);
loadRuns();
