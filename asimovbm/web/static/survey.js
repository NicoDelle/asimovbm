let surveyDesign = null;
let currentVideos = [];
let currentParticipant = null;
let currentVideoIndex = 0;
let activeGroupId = "";
let videoEnded = false;

async function loadSurveyDesign() {
  const response = await fetch("/api/survey/design");
  surveyDesign = await response.json();
  renderStartScreen();
}

function renderStartScreen() {
  const status = document.getElementById("survey-status");
  const videos = document.getElementById("survey-videos");
  const form = document.getElementById("survey-form");
  videos.innerHTML = "";
  status.textContent = "";
  form.innerHTML = `
    <section class="start-screen" aria-labelledby="survey-start-title">
      <h3 id="survey-start-title">Start anonymous survey</h3>
      <p>
        Your answers are used only for research on robot behavior. The survey does not ask for
        name, surname, or email. You will be assigned one robot, one policy, and one viewpoint,
        then rate three scenario videos.
      </p>
      <p>
        Each video must be watched to the end before the four questions unlock.
      </p>
      <button id="start-survey" type="button">Start test</button>
    </section>
  `;
  document.getElementById("start-survey")?.addEventListener("click", startSurvey);
}

async function startSurvey() {
  const status = document.getElementById("survey-status");
  status.textContent = "Assigning survey cell...";
  const response = await fetch("/api/survey/participants", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({})
  });
  const payload = await response.json();
  if (!response.ok) {
    status.textContent = payload.error || "Unable to start survey.";
    return;
  }
  currentParticipant = payload.participant;
  currentVideos = payload.videos || [];
  activeGroupId = currentParticipant.group_id;
  currentVideoIndex = 0;
  renderAssignedVideos();
  renderSurveyEpisode();
}

function renderAssignedVideos() {
  const videos = document.getElementById("survey-videos");
  const videoLabel = currentVideos.length === 1 ? "video" : "videos";
  document.getElementById("survey-status").textContent =
    `${currentVideos.length} ${videoLabel} assigned to ${activeGroupId}`;
  videos.innerHTML = "";
  for (const video of currentVideos) {
    const card = document.createElement("article");
    card.className = "video-card";
    card.innerHTML = `<h3>${escapeHtml(video.title || video.video_id)}</h3><p>${escapeHtml(video.policy_id)} · ${escapeHtml(video.viewpoint)} · ${escapeHtml(video.robot_id)}</p>`;
    videos.appendChild(card);
  }
}

function renderSurveyEpisode() {
  const form = document.getElementById("survey-form");
  if (currentVideos.length === 0 || !surveyDesign || !currentParticipant) {
    return;
  }
  if (currentVideoIndex >= currentVideos.length) {
    form.innerHTML = `
      <h3>Survey complete</h3>
      <p>Thank you. Your anonymous participant id is ${escapeHtml(currentParticipant.participant_id)}.</p>
    `;
    document.getElementById("survey-status").textContent = "Survey complete.";
    return;
  }
  videoEnded = false;
  const video = currentVideos[currentVideoIndex];
  form.innerHTML = `
    <h3>Episode ${currentVideoIndex + 1} of ${currentVideos.length}</h3>
    <p>${escapeHtml(video.title || video.video_id)}</p>
    <video class="episode-player" controls preload="metadata" src="${videoUrl(video.path)}"></video>
    <p id="watch-status" class="watch-status">Watch the full video to unlock the questions.</p>
    <div id="question-region" class="question-region" aria-live="polite"></div>
  `;
  const player = form.querySelector("video");
  player.addEventListener("ended", () => unlockQuestions(video));
  if (player.ended) {
    unlockQuestions(video);
  } else {
    renderQuestions(video, true);
  }
}

function unlockQuestions(video) {
  videoEnded = true;
  document.getElementById("watch-status").textContent = "Questions unlocked.";
  renderQuestions(video, false);
}

function renderQuestions(video, locked) {
  const region = document.getElementById("question-region");
  region.innerHTML = "";
  for (const question of surveyDesign.questions || []) {
    const block = document.createElement("fieldset");
    block.className = "question";
    block.disabled = locked;
    block.innerHTML = `<legend>${escapeHtml(question.text)}</legend>`;
    const likert = document.createElement("div");
    likert.className = "likert";
    for (let value = 1; value <= 7; value += 1) {
      const id = `${question.id}-${currentVideoIndex}-${value}`;
      const label = document.createElement("label");
      label.innerHTML = `<input id="${id}" type="radio" name="${question.id}" value="${value}">${value}`;
      likert.appendChild(label);
    }
    block.appendChild(likert);
    region.appendChild(block);
  }
  const submit = document.createElement("button");
  submit.type = "button";
  submit.disabled = true;
  submit.textContent = "Submit episode";
  submit.addEventListener("click", () => submitSurveyResponse(video));
  region.appendChild(submit);
  if (!locked) {
    region.addEventListener("change", () => {
      submit.disabled = !allQuestionsAnswered();
    });
    submit.disabled = !allQuestionsAnswered();
  }
}

async function submitSurveyResponse(video) {
  if (!videoEnded) {
    document.getElementById("survey-status").textContent = "Watch the full video before answering.";
    return;
  }
  const form = document.getElementById("survey-form");
  const data = new FormData(form);
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
      participant_id: currentParticipant.participant_id,
      group_id: activeGroupId,
      video_id: video.video_id,
      episode_order: video.episode_order,
      video_completed: true,
      answers
    })
  });
  const payload = await response.json();
  if (response.ok) {
    currentVideoIndex += 1;
    document.getElementById("survey-status").textContent = "Response saved.";
    renderSurveyEpisode();
  } else {
    document.getElementById("survey-status").textContent = payload.error || "Response was not saved.";
  }
}

function videoUrl(path) {
  return `/videos/${String(path || "").split("/").map(encodeURIComponent).join("/")}`;
}

function allQuestionsAnswered() {
  const form = document.getElementById("survey-form");
  const data = new FormData(form);
  return (surveyDesign.questions || []).every((question) => Boolean(data.get(question.id)));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadSurveyDesign();
