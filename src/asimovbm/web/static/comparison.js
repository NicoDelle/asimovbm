let comparisonDesign = null;

async function loadComparisonDesign() {
  const response = await fetch("/api/survey/design");
  comparisonDesign = await response.json();
  const select = document.getElementById("comparison-weight");
  select.innerHTML = "";
  const presets = comparisonDesign.weight_presets || {};
  for (const presetId of Object.keys(presets)) {
    const option = document.createElement("option");
    option.value = presetId;
    option.textContent = presetId.replaceAll("_", " ");
    select.appendChild(option);
  }
  select.value = comparisonDesign.default_weight_preset || "equal";
  select.addEventListener("change", loadComparison);
  await loadComparison();
}

async function loadComparison() {
  const select = document.getElementById("comparison-weight");
  const weightPreset = select?.value || "equal";
  const response = await fetch(`/api/survey/comparison?weight_preset=${encodeURIComponent(weightPreset)}`);
  const payload = await response.json();
  const status = document.getElementById("comparison-status");
  if (!response.ok) {
    status.textContent = payload.error || "Unable to load comparison.";
    clearComparison();
    return;
  }
  const comparison = payload.comparison || {};
  const videos = Object.values(comparison.videos || {});
  const compared = videos.filter((video) => video.status === "compared");
  status.textContent = `${compared.length}/${videos.length} videos have both predictions and survey responses.`;
  renderComparisonSummary(comparison, compared);
  renderComparisonGroups(comparison.groups || {});
  renderComparisonTable(videos);
}

function clearComparison() {
  document.getElementById("comparison-summary").innerHTML = "";
  document.getElementById("comparison-groups").innerHTML = "";
  document.getElementById("comparison-table").innerHTML = "";
}

function renderComparisonSummary(comparison, compared) {
  const summary = document.getElementById("comparison-summary");
  summary.innerHTML = "";
  const averageError = mean(compared.map((item) => item.global_absolute_error));
  const items = [
    ["Compared", `${compared.length}`],
    ["Rank correlation", formatScore(comparison.rank_order_correlation, 2)],
    ["Distribution distance", formatScore(comparison.distribution_distance, 2)],
    ["Mean global error", formatScore(averageError, 1)]
  ];
  for (const [label, value] of items) {
    const node = document.createElement("article");
    node.className = "summary-item";
    node.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    summary.appendChild(node);
  }
}

function renderComparisonGroups(groups) {
  const container = document.getElementById("comparison-groups");
  container.innerHTML = "";
  for (const [groupId, group] of Object.entries(groups)) {
    const node = document.createElement("article");
    node.className = "summary-item";
    node.innerHTML = `
      <span>${groupId.replaceAll("_", " ")}</span>
      <strong>${formatScore(group.global_absolute_error_mean, 1)}</strong>
      <div class="muted">${group.compared_count}/${group.video_count} compared · survey ${formatScore(group.survey_global_mean, 1)} · predicted ${formatScore(group.prediction_global_mean, 1)}</div>
    `;
    container.appendChild(node);
  }
}

function renderComparisonTable(videos) {
  const container = document.getElementById("comparison-table");
  if (videos.length === 0) {
    container.textContent = "No manifest videos available for comparison.";
    return;
  }
  const rows = videos
    .sort((left, right) => (left.video?.episode_order || 0) - (right.video?.episode_order || 0))
    .map((item) => {
      const video = item.video || {};
      const statusClass = item.status === "compared" ? "" : " warning";
      return `
        <tr>
          <td>
            <strong>${escapeHtml(video.title || video.video_id || item.video_id)}</strong>
            <div class="muted">${escapeHtml(video.episode_id || "")}</div>
          </td>
          <td>${escapeHtml(video.policy_id || "")}<div class="muted">${escapeHtml(video.viewpoint || "")} · ${escapeHtml(video.robot_id || "")}</div></td>
          <td>${formatScore(item.prediction_global, 1)}</td>
          <td>${formatScore(item.survey_global, 1)}<div class="muted">${item.survey_response_count || 0} responses</div></td>
          <td>${formatScore(item.global_absolute_error, 1)}</td>
          <td>${axisErrorText(item.axis_absolute_errors || {})}</td>
          <td><span class="status-pill${statusClass}">${item.status}</span></td>
        </tr>
      `;
    })
    .join("");
  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Video</th>
          <th>Cell</th>
          <th>Prediction</th>
          <th>Survey</th>
          <th>Error</th>
          <th>Axis errors</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function axisErrorText(errors) {
  const entries = Object.entries(errors);
  if (entries.length === 0) {
    return "n/a";
  }
  return entries
    .map(([axisId, value]) => `${axisId.replace("perceived_", "")}: ${formatScore(value, 1)}`)
    .join(" · ");
}

function mean(values) {
  const numeric = values.filter((value) => Number.isFinite(value));
  if (numeric.length === 0) {
    return null;
  }
  return numeric.reduce((total, value) => total + value, 0) / numeric.length;
}

function formatScore(value, digits) {
  if (!Number.isFinite(value)) {
    return "n/a";
  }
  return Number(value).toFixed(digits);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadComparisonDesign();
