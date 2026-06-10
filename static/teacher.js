const state = {
  token: localStorage.getItem("integrated_token") || "",
  role: localStorage.getItem("integrated_role") || "",
  sessions: [],
  accounts: [],
  summary: null,
  research: null,
  researchSummary: null,
  materials: [],
  selected: null,
  pollTimer: null,
  query: "",
};

const els = {
  appStatus: document.querySelector("#appStatus"),
  overviewStamp: document.querySelector("#overviewStamp"),
  overviewGrid: document.querySelector("#overviewGrid"),
  researchStamp: document.querySelector("#researchStamp"),
  researchSummary: document.querySelector("#researchSummary"),
  loginForm: document.querySelector("#loginForm"),
  materialForm: document.querySelector("#materialForm"),
  classForm: document.querySelector("#classForm"),
  researchStudentForm: document.querySelector("#researchStudentForm"),
  lessonForm: document.querySelector("#lessonForm"),
  assessmentForm: document.querySelector("#assessmentForm"),
  fidelityForm: document.querySelector("#fidelityForm"),
  comparisonForm: document.querySelector("#comparisonForm"),
  codingForm: document.querySelector("#codingForm"),
  imiForm: document.querySelector("#imiForm"),
  reflectionForm: document.querySelector("#reflectionForm"),
  safeguardingForm: document.querySelector("#safeguardingForm"),
  approvalForm: document.querySelector("#approvalForm"),
  exportEna: document.querySelector("#exportEna"),
  refreshState: document.querySelector("#refreshState"),
  sessionSearch: document.querySelector("#sessionSearch"),
  accountList: document.querySelector("#accountList"),
  sessionList: document.querySelector("#sessionList"),
  selectedStatus: document.querySelector("#selectedStatus"),
  metricsGrid: document.querySelector("#metricsGrid"),
  patternList: document.querySelector("#patternList"),
  profileGrid: document.querySelector("#profileGrid"),
  loadRecord: document.querySelector("#loadRecord"),
  teacherNote: document.querySelector("#teacherNote"),
  saveTeacherNote: document.querySelector("#saveTeacherNote"),
  noteList: document.querySelector("#noteList"),
  transcript: document.querySelector("#transcript"),
  auditList: document.querySelector("#auditList"),
  pauseSession: document.querySelector("#pauseSession"),
  resumeSession: document.querySelector("#resumeSession"),
  flagSession: document.querySelector("#flagSession"),
  terminateSession: document.querySelector("#terminateSession"),
  loadAudit: document.querySelector("#loadAudit"),
  exportDataset: document.querySelector("#exportDataset"),
  exportAllDataset: document.querySelector("#exportAllDataset"),
};

function setStatus(text) {
  els.appStatus.textContent = text;
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function getJson(url, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed: ${response.status}`);
  return data;
}

function metric(label, value) {
  return `
    <div class="metric-card">
      <strong>${escapeHtml(label)}</strong>
      <span>${escapeHtml(value)}</span>
    </div>
  `;
}

function formObject(form) {
  const data = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    if (element.type === "checkbox") data[element.name] = element.checked;
    else data[element.name] = element.value;
  }
  return data;
}

function renderResearchSummary() {
  const summary = state.researchSummary || {};
  const lesson = summary.current_lesson || {};
  if (els.researchStamp) {
    els.researchStamp.textContent = state.research ? new Date().toLocaleTimeString() : "Not loaded";
  }
  if (!els.researchSummary) return;
  els.researchSummary.innerHTML = [
    ["Classes", summary.classes || 0],
    ["Research students", summary.research_students || 0],
    ["Assessment records", summary.assessment_records || 0],
    ["Fidelity logs", summary.fidelity_logs || 0],
    ["BAU logs", summary.comparison_logs || 0],
    ["Human coding", summary.human_coding || 0],
    ["IMI surveys", summary.imi_surveys || 0],
    ["Teacher reflections", summary.teacher_reflections || 0],
    ["Safeguarding cases", summary.safeguarding_cases || 0],
    ["Dataset approvals", summary.dataset_approvals || 0],
    ["Current unit", lesson.unit || "Unit 1"],
    ["Lesson phase", lesson.phase || "in_class"],
  ]
    .map(([label, value]) => metric(label, value))
    .join("");
}

function renderOverview() {
  const rows = state.sessions;
  const summary = state.summary || {};
  const totalTurns = rows.reduce((sum, row) => sum + (row.monitoring.turn_count || 0), 0);
  const active = rows.filter((row) => row.session.status === "active").length;
  const listening = rows.filter((row) => row.session.chatbot_listening).length;
  const flags = rows.reduce((sum, row) => sum + (row.session.flags?.length || 0), 0);
  const attention = rows.filter((row) => row.monitoring.teacher_attention_required).length;
  const uploads = rows.filter((row) => row.session.student_video_upload).length;
  els.overviewStamp.textContent = rows.length ? new Date().toLocaleTimeString() : "No data";
  els.overviewGrid.innerHTML = [
    ["Registered accounts", summary.registered_accounts ?? state.accounts.length],
    ["Capacity", `${summary.registered_accounts ?? state.accounts.length}/${summary.max_accounts || 500}`],
    ["Connected accounts", summary.connected_accounts || 0],
    ["Sessions", rows.length],
    ["Active", active],
    ["Listening", listening],
    ["Total turns", totalTurns],
    ["Flags", flags],
    ["Uploads", uploads],
    ["Needs attention", attention],
    ["Current videos", state.materials.length],
  ]
    .map(([label, value]) => metric(label, value))
    .join("");
}

function renderAccounts() {
  const accounts = state.accounts || [];
  if (!accounts.length) {
    els.accountList.innerHTML = `<div class="session-card"><strong>No registered accounts</strong><div class="meta-row">Students appear here after Connect account or Start Chatbot.</div></div>`;
    return;
  }
  els.accountList.innerHTML = accounts
    .map((account) => {
      const activeSession = account.active_session;
      const connected = activeSession ? `<span class="chip low">connected</span>` : `<span class="chip">registered</span>`;
      const attention = account.monitoring?.teacher_attention_required ? `<span class="chip high">attention</span>` : "";
      return `
        <div class="account-card">
          <strong>${escapeHtml(account.participant_code)} · ${escapeHtml(account.level || "A2")}</strong>
          <div class="meta-row">
            ${connected} ${attention}
            ${activeSession ? `session ${escapeHtml(activeSession.status)} · turns ${escapeHtml(activeSession.turn_count || 0)} · ${escapeHtml(activeSession.material_title || "English video")}` : "no live session yet"}
          </div>
          <div class="meta-row">Last seen ${escapeHtml(account.last_seen_at || account.created_at || "not yet")}</div>
        </div>
      `;
    })
    .join("");
}

function searchableText(row) {
  const session = row.session;
  return [
    session.participant_code,
    session.level,
    session.status,
    session.material_title,
    session.topic,
    session.student_task,
    session.student_video_upload?.original_filename,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function filteredSessions() {
  const query = state.query.trim().toLowerCase();
  if (!query) return state.sessions;
  return state.sessions.filter((row) => searchableText(row).includes(query));
}

function renderSessions() {
  const rows = filteredSessions();
  if (!rows.length) {
    els.sessionList.innerHTML = `<div class="session-card"><strong>No matching session</strong><div class="meta-row">Students appear here after they start the chatbot.</div></div>`;
    return;
  }
  els.sessionList.innerHTML = rows
    .map(({ session, monitoring }) => {
      const active = state.selected?.session.id === session.id ? "active" : "";
      const attention = monitoring.teacher_attention_required ? `<span class="chip high">attention</span>` : `<span class="chip low">normal</span>`;
      const upload = session.student_video_upload ? `<span class="chip medium">video upload</span>` : "";
      return `
        <button class="session-card ${active}" type="button" data-session-id="${session.id}">
          <strong>${escapeHtml(session.participant_code)} · ${escapeHtml(session.level)} · ${escapeHtml(session.material_title)}</strong>
          <div class="meta-row">
            ${escapeHtml(session.status)} · chatbot ${session.chatbot_listening ? "on" : "off"} · turns ${monitoring.turn_count}
            ${attention} ${upload}
          </div>
        </button>
      `;
    })
    .join("");
  els.sessionList.querySelectorAll("[data-session-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = state.sessions.find((item) => item.session.id === button.dataset.sessionId);
      if (row) selectSession(row);
    });
  });
}

function renderSelected() {
  const row = state.selected;
  if (!row) {
    els.selectedStatus.textContent = "No session";
    els.metricsGrid.innerHTML = "";
    els.patternList.innerHTML = "";
    els.profileGrid.innerHTML = "";
    els.noteList.innerHTML = "";
    els.transcript.innerHTML = `<div class="turn-card"><strong>未选择会话</strong><p>请选择左侧学生会话。</p></div>`;
    return;
  }
  const session = row.session;
  const monitoring = row.monitoring;
  const inputModes = monitoring.input_modes || {};
  els.selectedStatus.textContent = `${session.status} · chatbot ${session.chatbot_listening ? "on" : "off"}`;
  els.metricsGrid.innerHTML = [
    ["Turns", monitoring.turn_count],
    ["Participation", monitoring.participation_level || "not_started"],
    ["Reasoning", monitoring.reasoning_depth || "not_started"],
    ["English ratio", `${Math.round((monitoring.average_english_ratio || 0) * 100)}%`],
    ["Avg words", monitoring.average_words_per_turn || 0],
    ["Speech / typed", `${inputModes.speech || 0} / ${inputModes.typed || 0}`],
    ["Reason markers", monitoring.reasoning_marker_total || 0],
    ["Flags", session.flags?.length || 0],
  ]
    .map(([label, value]) => metric(label, value))
    .join("");

  renderPatterns(monitoring);
  renderProfile(session, monitoring);
  renderTranscript(session);
  renderNotes(session);
}

function renderPatterns(monitoring) {
  const patterns = monitoring.patterns || [];
  const moveCounts = monitoring.move_counts || {};
  const moveSummary = Object.entries(moveCounts)
    .map(([move, count]) => `${move}:${count}`)
    .join(" · ");
  const cards = patterns.length
    ? patterns
        .map(
          (pattern) => `
            <div class="pattern-card">
              <strong>${escapeHtml(pattern.type)} <span class="chip ${escapeHtml(pattern.severity)}">${escapeHtml(pattern.severity)}</span></strong>
              <p>${escapeHtml(pattern.description)}</p>
            </div>
          `,
        )
        .join("")
    : "";
  els.patternList.innerHTML =
    cards ||
    `<div class="pattern-card"><strong>No concerning pattern</strong><p>${escapeHtml((monitoring.move_sequence || []).join(" -> ") || "No moves yet")}</p></div>`;
  if (moveSummary) {
    els.patternList.innerHTML += `<div class="pattern-card"><strong>Tech-SEDA move counts</strong><p>${escapeHtml(moveSummary)}</p></div>`;
  }
}

function profileItem(label, value) {
  return `
    <div class="profile-item">
      <strong>${escapeHtml(label)}</strong>
      <span>${value}</span>
    </div>
  `;
}

function renderProfile(session, monitoring) {
  const upload = session.student_video_upload;
  const system1 = session.system1_material || {};
  const system1Source = system1.source || {};
  const uploadLink = upload
    ? `<a href="${escapeHtml(upload.url)}" target="_blank">${escapeHtml(upload.original_filename)}</a>`
    : "Teacher video";
  const sourceVideoLink = system1Source.source_video
    ? `<a href="${escapeHtml(system1Source.source_video)}" target="_blank">${escapeHtml(system1Source.original_filename || "source video")}</a>`
    : "None";
  els.profileGrid.innerHTML = [
    ["Anonymous ID", escapeHtml(session.participant_code)],
    ["English level", escapeHtml(session.level)],
    ["Session ID", escapeHtml(session.id)],
    ["Current material", escapeHtml(session.material_title)],
    ["System 1 mode", escapeHtml(system1.mode || "teacher_selected_material")],
    ["System 1 source video", sourceVideoLink],
    ["Student video", uploadLink],
    ["Student task", escapeHtml(session.student_task || "not provided")],
    ["Created", escapeHtml(session.created_at)],
    ["Last update", escapeHtml(session.updated_at)],
    ["Teacher interventions", escapeHtml(monitoring.intervention_count || 0)],
    ["Teacher notes", escapeHtml(monitoring.teacher_note_count || 0)],
  ]
    .map(([label, value]) => profileItem(label, value))
    .join("");
}

function renderTranscript(session) {
  els.transcript.innerHTML = session.turns?.length
    ? session.turns
        .map(
          (turn) => `
            <div class="turn-card">
              <strong>Turn ${escapeHtml(turn.turn)} · ${escapeHtml(turn.input_mode)} · ${escapeHtml(turn.move)} · ${escapeHtml(turn.scaffold)}</strong>
              <p><b>Student:</b> ${escapeHtml(turn.student_text)}</p>
              <p><b>AI:</b> ${escapeHtml(turn.ai_response)}</p>
              <p><b>Why:</b> ${escapeHtml((turn.explainability?.decision_reasons || []).join(" "))}</p>
            </div>
          `,
        )
        .join("")
    : `<div class="turn-card"><strong>No turns yet</strong><p>Student has started a session but has not spoken or typed yet.</p></div>`;
}

function renderNotes(session) {
  const notes = session.teacher_notes || [];
  els.noteList.innerHTML = notes.length
    ? notes
        .slice()
        .reverse()
        .map(
          (note) => `
            <div class="note-card">
              <strong>${escapeHtml(note.time)} · ${escapeHtml(note.role)}</strong>
              <p>${escapeHtml(note.note)}</p>
            </div>
          `,
        )
        .join("")
    : `<div class="note-card"><strong>No notes</strong><p>Teacher notes are stored in the local session record.</p></div>`;
}

function selectSession(row) {
  state.selected = row;
  if (document.activeElement !== els.teacherNote) {
    els.teacherNote.value = "";
  }
  renderSessions();
  renderSelected();
}

async function refreshState() {
  if (!state.token) return;
  let data;
  try {
    data = await getJson("/api/teacher/state");
  } catch (error) {
    if ((error.message || "").includes("Unauthorized")) {
      state.token = "";
      state.role = "";
      localStorage.removeItem("integrated_token");
      localStorage.removeItem("integrated_role");
      setStatus("Login required");
      return;
    }
    throw error;
  }
  state.sessions = data.sessions || [];
  state.accounts = data.accounts || [];
  state.summary = data.summary || null;
  state.materials = data.materials || [];
  const researchData = await getJson("/api/research/state");
  state.research = researchData.research || null;
  state.researchSummary = researchData.summary || null;
  if (state.selected) {
    const updated = state.sessions.find((row) => row.session.id === state.selected.session.id);
    if (updated) state.selected = updated;
  } else if (state.sessions.length) {
    state.selected = state.sessions[0];
  }
  renderOverview();
  renderAccounts();
  renderResearchSummary();
  renderSessions();
  renderSelected();
  setStatus(`Logged in: ${state.role}`);
}

async function login(event) {
  event.preventDefault();
  const form = new FormData(els.loginForm);
  const data = await getJson("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: form.get("role"), passcode: form.get("passcode") }),
  });
  state.token = data.token;
  state.role = data.role;
  localStorage.setItem("integrated_token", state.token);
  localStorage.setItem("integrated_role", state.role);
  setStatus(`Logged in: ${state.role}`);
  await refreshState();
  startPolling();
}

async function generateMaterial(event) {
  event.preventDefault();
  if (!state.token) {
    setStatus("Login first");
    return;
  }
  const form = new FormData(els.materialForm);
  const customTopic = form.get("customTopic")?.trim();
  setStatus("Generating video");
  const data = await getJson("/api/materials/topic", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: customTopic || form.get("topic"),
      level: form.get("level"),
      subtitle_mode: form.get("subtitleMode"),
    }),
  });
  setStatus(`Current video: ${data.material.title}`);
  await refreshState();
}

async function submitResearchForm(event, url, statusText, transform = null) {
  event.preventDefault();
  if (!state.token) {
    setStatus("Login first");
    return;
  }
  const form = event.currentTarget;
  const payload = transform ? transform(formObject(form)) : formObject(form);
  await getJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  setStatus(statusText);
  await refreshState();
}

async function exportEna() {
  if (state.role !== "researcher") {
    setStatus("Researcher role required");
    return;
  }
  const data = await getJson("/api/research/export-ena", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  els.auditList.innerHTML = `
    <div class="audit-card">
      <strong>ENA-ready CSV exported</strong>
      <p>${escapeHtml(data.row_count)} rows · <a href="${data.url}" target="_blank">${escapeHtml(data.file)}</a></p>
    </div>
  ` + els.auditList.innerHTML;
  setStatus("ENA-ready CSV exported");
}

async function teacherAction(action) {
  if (!state.selected) return;
  const data = await getJson(`/api/sessions/${state.selected.session.id}/teacher-action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  state.selected.session = data.session;
  await refreshState();
}

async function loadRecord() {
  if (!state.selected) return;
  const data = await getJson(`/api/sessions/${state.selected.session.id}/record`);
  state.selected = { session: data.session, monitoring: data.monitoring };
  renderSessions();
  renderSelected();
  renderAudit(data.audit);
  setStatus(`Loaded record: ${data.session.participant_code}`);
}

function renderAudit(audit) {
  const turns = audit?.turn_audits || [];
  els.auditList.innerHTML = turns.length
    ? turns
        .map(
          (turn) => `
            <div class="audit-card">
              <strong>Turn ${escapeHtml(turn.turn)} · ${escapeHtml(turn.move)} · ${escapeHtml(turn.scaffold)}</strong>
              <p>${escapeHtml((turn.decision_reasons || []).join(" "))}</p>
            </div>
          `,
        )
        .join("")
    : `<div class="audit-card"><strong>No audit yet</strong><p>No student turn has been recorded.</p></div>`;
}

async function loadAudit() {
  if (!state.selected) return;
  const data = await getJson(`/api/sessions/${state.selected.session.id}/audit`);
  renderAudit(data.audit);
}

async function saveTeacherNote() {
  if (!state.selected) return;
  const note = els.teacherNote.value.trim();
  if (!note) {
    setStatus("Teacher note is empty");
    return;
  }
  const data = await getJson(`/api/sessions/${state.selected.session.id}/teacher-note`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  state.selected.session = data.session;
  els.teacherNote.value = "";
  await refreshState();
  setStatus("Teacher note saved");
}

async function exportDataset() {
  if (!state.selected) return;
  if (state.role !== "researcher") {
    setStatus("Researcher role required");
    return;
  }
  const data = await getJson(`/api/sessions/${state.selected.session.id}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  els.auditList.innerHTML = `
    <div class="audit-card">
      <strong>Dataset exported</strong>
      <p><a href="${data.url}" target="_blank">${escapeHtml(data.file)}</a></p>
    </div>
  ` + els.auditList.innerHTML;
}

async function exportAllDataset() {
  if (state.role !== "researcher") {
    setStatus("Researcher role required");
    return;
  }
  const data = await getJson("/api/teacher/export-all", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  els.auditList.innerHTML = `
    <div class="audit-card">
      <strong>All anonymised datasets exported</strong>
      <p><a href="${data.url}" target="_blank">${escapeHtml(data.file)}</a></p>
    </div>
  ` + els.auditList.innerHTML;
  setStatus("All anonymised data exported");
}

function startPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(() => refreshState().catch(console.error), 3000);
}

function bindEvents() {
  els.loginForm.addEventListener("submit", (event) => login(event).catch(handleError));
  els.loginForm.role.addEventListener("change", () => {
    els.loginForm.passcode.value = els.loginForm.role.value === "researcher" ? "researcher-demo" : "teacher-demo";
  });
  els.materialForm.addEventListener("submit", (event) => generateMaterial(event).catch(handleError));
  els.classForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/class", "Class/group saved").catch(handleError));
  els.researchStudentForm.addEventListener("submit", (event) =>
    submitResearchForm(event, "/api/research/student", "Student research status saved").catch(handleError),
  );
  els.lessonForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/lesson", "Current lesson context saved").catch(handleError));
  els.assessmentForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/assessments/import", "Assessment records imported").catch(handleError));
  els.fidelityForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/fidelity", "Treatment fidelity log saved").catch(handleError));
  els.comparisonForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/comparison-log", "BAU comparison log saved").catch(handleError));
  els.codingForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/human-coding", "Human Tech-SEDA coding saved").catch(handleError));
  els.imiForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/imi-survey", "IMI survey record saved").catch(handleError));
  els.reflectionForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/reflection", "Teacher reflection saved").catch(handleError));
  els.safeguardingForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/safeguarding-case", "Safeguarding case saved").catch(handleError));
  els.approvalForm.addEventListener("submit", (event) => submitResearchForm(event, "/api/research/dataset-approval", "Dataset approval saved").catch(handleError));
  els.exportEna.addEventListener("click", () => exportEna().catch(handleError));
  els.refreshState.addEventListener("click", () => refreshState().catch(handleError));
  els.sessionSearch.addEventListener("input", () => {
    state.query = els.sessionSearch.value;
    renderSessions();
  });
  els.pauseSession.addEventListener("click", () => teacherAction("pause").catch(handleError));
  els.resumeSession.addEventListener("click", () => teacherAction("resume").catch(handleError));
  els.flagSession.addEventListener("click", () => teacherAction("flag_review").catch(handleError));
  els.terminateSession.addEventListener("click", () => teacherAction("terminate").catch(handleError));
  els.loadRecord.addEventListener("click", () => loadRecord().catch(handleError));
  els.saveTeacherNote.addEventListener("click", () => saveTeacherNote().catch(handleError));
  els.loadAudit.addEventListener("click", () => loadAudit().catch(handleError));
  els.exportDataset.addEventListener("click", () => exportDataset().catch(handleError));
  els.exportAllDataset.addEventListener("click", () => exportAllDataset().catch(handleError));
}

function handleError(error) {
  console.error(error);
  setStatus(error.message || "Error");
}

async function boot() {
  bindEvents();
  renderOverview();
  renderAccounts();
  renderResearchSummary();
  if (state.token) {
    await refreshState();
    startPolling();
  }
}

boot().catch(handleError);
