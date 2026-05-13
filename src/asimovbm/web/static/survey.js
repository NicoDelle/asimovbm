let surveyDesign = null;
let currentVideos = [];
let currentParticipant = null;
let currentVideoIndex = 0;

async function loadSurveyDesign() {
  const response = await fetch("/api/survey/design");
  surveyDesign = await response.json();
  const select = document.getElementById("survey-group");
  select.innerHTML = "";
  for (const cell of surveyDesign.study_cells || []) {
    const option = document.createElement("option");
    option.value = cell.id;
    option.textContent = cell.label;
    select.appendChild(option);
  }
  select.addEventListener("change", () => loadSurveyVideos(select.value));
  if (select.value) {
    await loadSurveyVideos(select.value);
  }
}

async function loadSurveyVideos(groupId) {
  const response = await fetch(`/api/survey/videos?group=${encodeURIComponent(groupId)}`);
  const payload = await response.json();
  const status = document.getElementById("survey-status");
  const videos = document.getElementById("survey-videos");
  const form = document.getElementById("survey-form");
  videos.innerHTML = "";
  form.innerHTML = "";
  if (!response.ok) {
    status.textContent = payload.error || "Unable to load videos.";
    return;
  }
  currentVideos = payload.videos || [];
  status.textContent = `${currentVideos.length} videos assigned to ${groupId}`;
  for (const video of currentVideos) {
    const card = document.createElement("article");
    card.className = "video-card";
    card.innerHTML = `<h3>${video.title || video.video_id}</h3><p>${video.policy_id} · ${video.viewpoint} · ${video.robot_id}</p>`;
    videos.appendChild(card);
  }
  currentParticipant = null;
  currentVideoIndex = 0;
  renderSurveyForm(groupId);
}

function renderSurveyForm(groupId) {
  const form = document.getElementById("survey-form");
  if (currentVideos.length === 0 || !surveyDesign) {
    return;
  }
  if (currentVideoIndex >= currentVideos.length) {
    form.innerHTML = `
      <h3>Survey complete</h3>
      <p>${currentParticipant?.participant_id || "Participant"} completed ${currentVideos.length} videos.</p>
      <p><a href="/api/survey/participants.csv">Export participants.csv</a></p>
    `;
    return;
  }
  const video = currentVideos[currentVideoIndex];
  form.innerHTML = `
    <h3>Episode ${currentVideoIndex + 1} of ${currentVideos.length}</h3>
    <p>${video.title || video.video_id}</p>
    <input name="participant_id" placeholder="Participant/session id" value="${currentParticipant?.participant_id || ""}">
    <input type="hidden" name="group_id" value="${groupId}">
    <input type="hidden" name="video_id" value="${video.video_id}">
  `;
  if (!currentParticipant) {
    for (const field of surveyDesign.participant_fields || []) {
      const wrapper = document.createElement("label");
      wrapper.className = "question";
      const select = document.createElement("select");
      select.name = `meta:${field.id}`;
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = field.label;
      select.appendChild(empty);
      for (const optionValue of field.options || []) {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;
        select.appendChild(option);
      }
      wrapper.appendChild(select);
      form.appendChild(wrapper);
    }
  }
  for (const question of surveyDesign.questions || []) {
    const block = document.createElement("fieldset");
    block.className = "question";
    block.innerHTML = `<legend>${question.text}</legend>`;
    const likert = document.createElement("div");
    likert.className = "likert";
    for (let value = 1; value <= 7; value += 1) {
      const id = `${question.id}-${value}`;
      const label = document.createElement("label");
      label.innerHTML = `<input id="${id}" type="radio" name="${question.id}" value="${value}">${value}`;
      likert.appendChild(label);
    }
    block.appendChild(likert);
    form.appendChild(block);
  }
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Submit episode";
  form.appendChild(submit);
  form.onsubmit = (event) => submitSurveyResponse(event, video);
}

async function submitSurveyResponse(event, video) {
  event.preventDefault();
  const data = new FormData(event.target);
  const participantId = data.get("participant_id") || currentParticipant?.participant_id;
  const groupId = data.get("group_id");
  if (!currentParticipant) {
    const metadata = {};
    for (const field of surveyDesign.participant_fields || []) {
      const value = data.get(`meta:${field.id}`);
      if (value) {
        metadata[field.id] = value;
      }
    }
    const participantResponse = await fetch("/api/survey/participants", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({participant_id: participantId, group_id: groupId, metadata})
    });
    const participantPayload = await participantResponse.json();
    currentParticipant = participantPayload.participant;
  }
  const activeParticipantId = currentParticipant?.participant_id || participantId;
  const answers = {};
  for (const question of surveyDesign.questions || []) {
    const value = data.get(question.id);
    if (value) {
      answers[question.id] = Number(value);
    }
  }
  const response = await fetch("/api/survey/responses", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      participant_id: activeParticipantId,
      group_id: groupId,
      video_id: video.video_id,
      episode_order: video.episode_order,
      answers
    })
  });
  if (response.ok) {
    currentVideoIndex += 1;
    document.getElementById("survey-status").textContent = "Response saved.";
    renderSurveyForm(groupId);
  } else {
    document.getElementById("survey-status").textContent = "Response was not saved.";
  }
}

loadSurveyDesign();
