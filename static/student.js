const APP_SERVER_URL = "http://127.0.0.1:8790/student";

const state = {
  material: null,
  session: null,
  chatbotOn: false,
  recognition: null,
  recognitionSupported: false,
  recognitionActive: false,
  restartRecognition: false,
  singleListen: false,
  micReady: false,
  isSpeaking: false,
  turnInFlight: false,
  system1Mode: "video",
  pendingSpeechText: "",
  speechSendTimer: null,
  lastSpeechActivityAt: 0,
  currentSpeechWaitMs: 1700,
  interruptionTurnActive: false,
  currentAudio: null,
  currentUtterance: null,
  currentAiText: "",
  lastAiText: "",
  lastAiEndedAt: 0,
  recentAiTexts: [],
  recentSpeechWordCounts: [],
  speechPlaybackId: 0,
  turnRequestId: 0,
  speechLangCandidates: [],
  speechLangIndex: 0,
  languageRetryPending: false,
  voiceLoadPromise: null,
};

const els = {
  connectionStatus: document.querySelector("#connectionStatus"),
  settingsToggle: document.querySelector("#settingsToggle"),
  settingsPanel: document.querySelector("#settingsPanel"),
  modeVideo: document.querySelector("#modeVideo"),
  modeTopic: document.querySelector("#modeTopic"),
  system1VideoForm: document.querySelector("#system1VideoForm"),
  system1TopicForm: document.querySelector("#system1TopicForm"),
  system1VideoFile: document.querySelector("#system1VideoFile"),
  selectedVideoName: document.querySelector("#selectedVideoName"),
  sourceTopic: document.querySelector("#sourceTopic"),
  sourceLanguage: document.querySelector("#sourceLanguage"),
  manualTranscript: document.querySelector("#manualTranscript"),
  system1VideoLevel: document.querySelector("#system1VideoLevel"),
  system1VideoSubtitles: document.querySelector("#system1VideoSubtitles"),
  system1VideoStatus: document.querySelector("#system1VideoStatus"),
  maskTop: document.querySelector("#maskTop"),
  maskBottom: document.querySelector("#maskBottom"),
  customMask: document.querySelector("#customMask"),
  topicInput: document.querySelector("#topicInput"),
  system1TopicLevel: document.querySelector("#system1TopicLevel"),
  system1TopicSubtitles: document.querySelector("#system1TopicSubtitles"),
  system1TopicStatus: document.querySelector("#system1TopicStatus"),
  system1Ready: document.querySelector("#system1Ready"),
  materialTitle: document.querySelector("#materialTitle"),
  materialMeta: document.querySelector("#materialMeta"),
  playbackSubtitles: document.querySelector("#playbackSubtitles"),
  videoFrame: document.querySelector("#videoFrame"),
  studentTask: document.querySelector("#studentTask"),
  startForm: document.querySelector("#startForm"),
  participantCode: document.querySelector("#participantCode"),
  registerStudent: document.querySelector("#registerStudent"),
  accountStatus: document.querySelector("#accountStatus"),
  stopChatbot: document.querySelector("#stopChatbot"),
  voiceStyle: document.querySelector("#voiceStyle"),
  chatbotState: document.querySelector("#chatbotState"),
  sessionLine: document.querySelector("#sessionLine"),
  speechNotice: document.querySelector("#speechNotice"),
  liveTranscript: document.querySelector("#liveTranscript"),
  requestMic: document.querySelector("#requestMic"),
  continuousVoiceState: document.querySelector("#continuousVoiceState"),
  chatLog: document.querySelector("#chatLog"),
  studentText: document.querySelector("#studentText"),
  sendTextTurn: document.querySelector("#sendTextTurn"),
};

function setConnection(text) {
  els.connectionStatus.textContent = text;
}

function setChatbotState(on) {
  state.chatbotOn = on;
  els.chatbotState.textContent = on ? "Listening" : "Closed";
  els.chatbotState.classList.toggle("live", on);
  els.chatbotState.classList.toggle("closed", !on);
  els.continuousVoiceState.textContent = on ? "Live voice on" : "Voice off";
}

function setContinuousVoice(text) {
  els.continuousVoiceState.textContent = text;
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function buildSpeechLanguageCandidates() {
  const languages = [navigator.language, ...(navigator.languages || [])]
    .filter(Boolean)
    .map((language) => language.trim())
    .filter(Boolean);
  const preferred = languages.filter((language) => language.toLowerCase().startsWith("en"));
  const fallback = ["en-NZ", "en-GB", "en-AU", "en-US", "en"];
  return [...new Set([...preferred, ...fallback])];
}

function currentSpeechLanguage() {
  return state.speechLangCandidates[state.speechLangIndex] || "en";
}

function learnerOpeningPrompt(session) {
  const title = session?.material_title || state.material?.title || "the English video";
  const variants = [
    `You are in charge of this talk. Think for a moment, then choose one idea from ${title} that you want to explore first.`,
    `Start with your own thinking. What did you notice in ${title}, and what would you like to talk about first?`,
    `Take a moment to choose your path. You can begin with one detail, one question, or one feeling from ${title}.`,
    `This is your discussion. Pick one idea from ${title}, and I will help you build it in English.`,
  ];
  const seed = Array.from(String(session?.participant_code || "student")).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return variants[seed % variants.length];
}

async function getJson(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error(`Local server is not responding. Open ${APP_SERVER_URL} and make sure server.py is running.`);
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed: ${response.status}`);
  return data;
}

function setVideoSource(videoUrl, subtitleUrl = "", subtitleLabel = "Subtitles") {
  const track = subtitleUrl
    ? `<track kind="subtitles" src="${subtitleUrl}" srclang="en" label="${escapeHtml(subtitleLabel)}" default />`
    : "";
  els.videoFrame.innerHTML = `<video controls playsinline preload="metadata" src="${videoUrl}">${track}</video>`;
  const video = els.videoFrame.querySelector("video");
  if (video && subtitleUrl) {
    const showTracks = () => {
      for (const textTrack of video.textTracks) {
        textTrack.mode = "showing";
      }
    };
    video.addEventListener("loadedmetadata", showTracks, { once: true });
    window.setTimeout(showTracks, 250);
  }
}

function subtitleUrlForMode(material, mode) {
  if (!material?.artifacts || material.artifacts.subtitles_burned_into_video || mode === "off") return "";
  const subtitles = material.artifacts.subtitles || {};
  if (mode === "bilingual") return subtitles.bilingual || material.artifacts.subtitles_vtt || "";
  return subtitles.english || material.artifacts.subtitles_vtt || "";
}

function applyPlaybackSubtitles() {
  if (!state.material?.artifacts?.video) return;
  const mode = els.playbackSubtitles.value || "english";
  const label = mode === "bilingual" ? "English + Chinese" : "English";
  setVideoSource(state.material.artifacts.video, subtitleUrlForMode(state.material, mode), label);
}

function renderMaterial(material = state.material) {
  if (!material) {
    els.materialTitle.textContent = "English Video";
    els.materialMeta.textContent = "";
    els.videoFrame.innerHTML = "";
    els.system1Ready.textContent = "Waiting";
    els.system1Ready.classList.remove("live");
    return;
  }
  state.material = material;
  const mode = material.system1?.mode || "teacher_selected_material";
  els.materialTitle.textContent = material.title;
  els.materialMeta.textContent = `${mode.replaceAll("_", " ")} · ${material.level} · ${Math.round(material.artifacts?.duration || 0)}s`;
  els.system1Ready.textContent = "Ready";
  els.system1Ready.classList.add("live");
  const preferredSubtitleMode = material.subtitle_mode === "bilingual" ? "bilingual" : "english";
  els.playbackSubtitles.value = preferredSubtitleMode;
  applyPlaybackSubtitles();
  if (!els.studentTask.value.trim()) {
    els.studentTask.value = `I want to discuss the English video about ${material.title}.`;
  }
}

async function loadMaterial() {
  const data = await getJson("/api/materials/current");
  state.material = data.material;
  renderMaterial();
}

function switchSystem1Mode(mode) {
  state.system1Mode = mode;
  els.modeVideo.classList.toggle("active", mode === "video");
  els.modeTopic.classList.toggle("active", mode === "topic");
  els.system1VideoForm.classList.toggle("hidden", mode !== "video");
  els.system1TopicForm.classList.toggle("hidden", mode !== "topic");
}

async function generateFromVideo(event) {
  event.preventDefault();
  const file = els.system1VideoFile.files?.[0];
  if (!file) {
    els.system1VideoStatus.textContent = "Choose a video first.";
    return;
  }
  els.system1VideoStatus.textContent = "Making English video. A 4-5 minute video may take several minutes.";
  els.system1Ready.textContent = "Generating";
  const formData = new FormData();
  formData.append("video", file);
  formData.append("source_topic", els.sourceTopic.value);
  formData.append("source_language", els.sourceLanguage.value);
  formData.append("manual_transcript", els.manualTranscript.value);
  formData.append("level", els.system1VideoLevel.value);
  formData.append("subtitle_mode", els.system1VideoSubtitles.value);
  formData.append("voice_style", els.voiceStyle.value);
  formData.append("mask_top", els.maskTop.checked ? "true" : "false");
  formData.append("mask_bottom", els.maskBottom.checked ? "true" : "false");
  formData.append("custom_mask", els.customMask.value.trim());
  const response = await fetch("/api/student/system1/video", { method: "POST", body: formData });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "System 1 video generation failed.");
  state.session = null;
  renderMaterial(data.material);
  els.system1VideoStatus.textContent = "Done. Watch it, then start the chatbot.";
}

async function generateFromTopic(event) {
  event.preventDefault();
  const topic = els.topicInput.value.trim();
  if (!topic) {
    els.system1TopicStatus.textContent = "Type a topic first.";
    return;
  }
  els.system1TopicStatus.textContent = "Making English video...";
  els.system1Ready.textContent = "Generating";
  const data = await getJson("/api/student/system1/topic", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic,
      level: els.system1TopicLevel.value,
      subtitle_mode: els.system1TopicSubtitles.value,
    }),
  });
  state.session = null;
  renderMaterial(data.material);
  els.system1TopicStatus.textContent = "Done. Watch it, then start the chatbot.";
}

function renderChat() {
  const turns = state.session?.turns || [];
  if (!state.session) {
    els.chatLog.innerHTML = `
      <div class="message ai">
        <strong>AI</strong>
        <p>Watch the System 1 English video first. Then start the chatbot when you are ready.</p>
      </div>
    `;
    return;
  }
  if (!turns.length) {
    els.chatLog.innerHTML = `
      <div class="message ai">
        <strong>AI</strong>
        <p>Hello. I watched the same English video with you. What idea would you like to talk about first?</p>
        <span class="move-chip">IBI · Invitation to build on ideas</span>
      </div>
    `;
    return;
  }
  els.chatLog.innerHTML = turns
    .map(
      (turn) => `
        <div class="message student">
          <strong>Student · ${escapeHtml(turn.input_mode)}</strong>
          <p>${escapeHtml(turn.student_text)}</p>
        </div>
        <div class="message ai">
          <strong>AI</strong>
          <p>${escapeHtml(turn.ai_response)}</p>
          <span class="move-chip">${escapeHtml(turn.move)} · ${escapeHtml(turn.move_name)}</span>
        </div>
      `,
    )
    .join("");
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

async function requestMicrophoneAccess(showSuccess = true) {
  if (!navigator.mediaDevices?.getUserMedia) {
    els.speechNotice.textContent = "This browser cannot use the microphone. Use text in Settings.";
    return false;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    state.micReady = true;
    if (showSuccess) {
      els.speechNotice.textContent = state.recognitionSupported
        ? "Mic is ready. Start the chatbot and speak."
        : "Mic works, but speech recognition is not available. Use text in Settings.";
    }
    return true;
  } catch {
    state.micReady = false;
    els.speechNotice.textContent = "Mic is blocked. Allow microphone access in system and browser settings.";
    return false;
  }
}

async function registerStudentAccount() {
  const participantCode = els.participantCode.value.trim() || "ANON-STUDENT-001";
  els.participantCode.value = participantCode;
  const level = state.material?.level || els.system1VideoLevel.value || "A2";
  const data = await getJson("/api/student/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ participant_code: participantCode, level }),
  });
  els.accountStatus.textContent = `Connected: ${data.account.participant_code} · ${data.account.level}`;
  return data.account;
}

function wordsIn(text = "") {
  return (String(text).toLowerCase().match(/[a-z][a-z'-]*/g) || []).length;
}

function adaptiveSpeechWaitMs() {
  const recent = state.recentSpeechWordCounts.slice(-5);
  if (!recent.length) return 1700;
  const average = recent.reduce((sum, value) => sum + value, 0) / recent.length;
  if (average <= 4) return 1450;
  if (average >= 16) return 2400;
  return Math.round(1450 + ((average - 4) / 12) * 950);
}

function adaptiveInterruptionWaitMs() {
  const recent = state.recentSpeechWordCounts.slice(-4);
  if (!recent.length) return 1300;
  const average = recent.reduce((sum, value) => sum + value, 0) / recent.length;
  if (average <= 4) return 1050;
  if (average >= 14) return 1700;
  return Math.round(1050 + ((average - 4) / 10) * 650);
}

function scheduleSpeechFlush(waitMs) {
  state.currentSpeechWaitMs = waitMs;
  if (state.speechSendTimer) window.clearTimeout(state.speechSendTimer);
  state.speechSendTimer = window.setTimeout(() => {
    const quietFor = Date.now() - state.lastSpeechActivityAt;
    if (quietFor < state.currentSpeechWaitMs) {
      scheduleSpeechFlush(state.currentSpeechWaitMs - quietFor);
      return;
    }
    flushPendingSpeechTurn();
  }, waitMs);
}

function normaliseSpeech(text = "") {
  return String(text).replace(/\s+/g, " ").trim();
}

function speechWordSet(text = "") {
  const stop = new Set([
    "the",
    "a",
    "an",
    "to",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "it",
    "this",
    "that",
    "you",
    "your",
    "can",
    "could",
    "what",
    "why",
    "how",
    "with",
    "from",
    "about",
  ]);
  return new Set((text.toLowerCase().match(/[a-z][a-z'-]*/g) || []).filter((word) => !stop.has(word)));
}

function compactSpeech(text = "") {
  return normaliseSpeech(text).toLowerCase().replace(/[^a-z0-9' ]/g, "").replace(/\s+/g, " ").trim();
}

function rememberAiSpeech(text = "") {
  const clean = normaliseSpeech(text);
  if (!clean) return;
  const now = Date.now();
  state.lastAiText = clean;
  state.lastAiEndedAt = now;
  state.recentAiTexts = [...state.recentAiTexts.filter((item) => now - item.at < 9000), { text: clean, at: now }].slice(-5);
}

function isEchoAgainst(text = "", reference = "") {
  const heardClean = compactSpeech(text);
  const aiClean = compactSpeech(reference);
  if (!heardClean || !aiClean) return false;
  const heardWordCount = wordsIn(heardClean);
  if (heardWordCount < 3 && heardClean.length < 16) return false;
  if (heardClean.length >= 16 && (aiClean.includes(heardClean) || heardClean.includes(aiClean))) return true;
  const heard = speechWordSet(text);
  const ai = speechWordSet(reference);
  if (!heard.size || !ai.size) return false;
  let overlap = 0;
  for (const word of heard) {
    if (ai.has(word)) overlap += 1;
  }
  return overlap / heard.size >= 0.58 && heard.size >= 3;
}

function isProbablyAiEcho(text = "") {
  const now = Date.now();
  state.recentAiTexts = state.recentAiTexts.filter((item) => now - item.at < 9000);
  const candidates = [];
  if (state.currentAiText) candidates.push(state.currentAiText);
  if (state.lastAiText && now - state.lastAiEndedAt < 6500) candidates.push(state.lastAiText);
  candidates.push(...state.recentAiTexts.map((item) => item.text));
  return candidates.some((candidate) => isEchoAgainst(text, candidate));
}

function isFillerSpeech(text = "") {
  const cleaned = normaliseSpeech(text).toLowerCase();
  if (!cleaned) return true;
  const fillerOnly = /^(um+|uh+|er+|ah+|hmm+|okay|ok|yes|yeah|no|wait|sorry|hello|hi)[ .,!]*$/i;
  return fillerOnly.test(cleaned);
}

function stopCurrentAiAudio() {
  if (state.currentAiText) rememberAiSpeech(state.currentAiText);
  state.speechPlaybackId += 1;
  if (state.currentAudio) {
    try {
      state.currentAudio.pause();
      state.currentAudio.currentTime = 0;
      state.currentAudio.src = "";
    } catch {}
  }
  state.currentAudio = null;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  state.currentUtterance = null;
  state.currentAiText = "";
  state.isSpeaking = false;
}

function finishAiSpeaking() {
  if (state.currentAiText) rememberAiSpeech(state.currentAiText);
  state.isSpeaking = false;
  state.currentAudio = null;
  state.currentUtterance = null;
  state.currentAiText = "";
  els.speechNotice.textContent = state.recognitionSupported ? "Listening again. Speak one idea." : "AI finished. Use text in Settings.";
  setContinuousVoice(state.recognitionSupported ? "Listening" : "Text backup only");
  startRecognition(false);
}

function handleAiInterruption(text, isFinal) {
  const clean = normaliseSpeech(text);
  if (!clean || isProbablyAiEcho(clean)) return;
  if (isFillerSpeech(clean)) {
    setContinuousVoice("AI speaking");
    return;
  }
  if (!isFinal && wordsIn(clean) < 3) return;
  stopCurrentAiAudio();
  state.interruptionTurnActive = true;
  state.lastSpeechActivityAt = Date.now();
  state.pendingSpeechText = clean;
  state.recentSpeechWordCounts.push(wordsIn(clean));
  state.recentSpeechWordCounts = state.recentSpeechWordCounts.slice(-8);
  els.liveTranscript.textContent = clean;
  setContinuousVoice("Heard you");
  els.speechNotice.textContent = "I stopped. Go ahead.";
  scheduleSpeechFlush(adaptiveInterruptionWaitMs());
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    state.recognitionSupported = false;
    els.speechNotice.textContent = "Speech recognition is not available. Use text in Settings.";
    setContinuousVoice("Text backup only");
    return;
  }

  state.recognitionSupported = true;
  state.speechLangCandidates = buildSpeechLanguageCandidates();
  state.speechLangIndex = 0;
  state.recognition = new SpeechRecognition();
  state.recognition.lang = currentSpeechLanguage();
  state.recognition.continuous = true;
  state.recognition.interimResults = true;
  state.recognition.maxAlternatives = 1;

  state.recognition.onstart = () => {
    state.recognitionActive = true;
    if (state.chatbotOn) {
      els.speechNotice.textContent = `Listening in ${state.recognition.lang}. Speak one idea.`;
      setContinuousVoice("Listening");
    }
  };

  state.recognition.onresult = (event) => {
    if (!state.chatbotOn) return;
    let interim = "";
    let finalText = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const transcript = result[0]?.transcript?.trim() || "";
      if (result.isFinal) finalText += ` ${transcript}`;
      else interim += ` ${transcript}`;
    }
    if (state.isSpeaking) {
      const heard = normaliseSpeech(finalText || interim);
      if (heard) handleAiInterruption(heard, Boolean(finalText.trim()));
      return;
    }
    const heardNow = normaliseSpeech(`${finalText} ${interim}`);
    if (heardNow) state.lastSpeechActivityAt = Date.now();
    if (heardNow && isProbablyAiEcho(heardNow)) {
      if (!state.pendingSpeechText) els.liveTranscript.textContent = "Listening.";
      setContinuousVoice("Listening");
      return;
    }
    if (finalText.trim()) {
      state.pendingSpeechText = `${state.pendingSpeechText} ${finalText}`.replace(/\s+/g, " ").trim();
      state.recentSpeechWordCounts.push(wordsIn(finalText));
      state.recentSpeechWordCounts = state.recentSpeechWordCounts.slice(-8);
    }
    const visibleSpeech = `${state.pendingSpeechText} ${interim}`.replace(/\s+/g, " ").trim();
    if (visibleSpeech) {
      els.liveTranscript.textContent = visibleSpeech;
      if (interim.trim()) setContinuousVoice("Hearing words");
    }
    if (interim.trim() && state.pendingSpeechText) {
      scheduleSpeechFlush(state.interruptionTurnActive ? adaptiveInterruptionWaitMs() : adaptiveSpeechWaitMs());
    }
    const cleanFinal = finalText.trim();
    if (cleanFinal) {
      setContinuousVoice("Heard you");
      scheduleSpeechFlush(state.interruptionTurnActive ? adaptiveInterruptionWaitMs() : adaptiveSpeechWaitMs());
    }
  };

  state.recognition.onerror = (event) => {
    if (event.error === "language-not-supported") {
      state.speechLangIndex += 1;
      if (state.speechLangIndex < state.speechLangCandidates.length) {
        state.recognition.lang = currentSpeechLanguage();
        state.languageRetryPending = true;
        els.speechNotice.textContent = `Switching speech language to ${state.recognition.lang}.`;
        try {
          state.recognition.abort();
        } catch {}
        return;
      }
    }
    const message = {
      "not-allowed": "Mic is blocked. Please allow microphone access.",
      "audio-capture": "No microphone found. Check the device or use text in Settings.",
      "no-speech": "I did not hear clearly. Try one short sentence.",
      "language-not-supported": "This browser cannot use English speech recognition here. Try Safari or Chrome, or use text in Settings.",
      network: "Speech recognition is not available now. Use text in Settings.",
    }[event.error] || `Voice problem: ${event.error}. Use text in Settings.`;
    els.speechNotice.textContent = message;
  };

  state.recognition.onend = () => {
    state.recognitionActive = false;
    if (state.languageRetryPending) {
      state.languageRetryPending = false;
      if (state.chatbotOn) window.setTimeout(() => startRecognition(false), 300);
      return;
    }
    if (state.singleListen) {
      state.singleListen = false;
      state.restartRecognition = false;
      return;
    }
    if (state.chatbotOn && state.restartRecognition) {
      window.setTimeout(() => startRecognition(false), 450);
    }
  };
}

function flushPendingSpeechTurn() {
  if (state.speechSendTimer) {
    window.clearTimeout(state.speechSendTimer);
    state.speechSendTimer = null;
  }
  const cleanFinal = state.pendingSpeechText.trim();
  state.pendingSpeechText = "";
  if (!cleanFinal || !state.chatbotOn || state.isSpeaking || state.turnInFlight) return;
  state.interruptionTurnActive = false;
  if (isProbablyAiEcho(cleanFinal)) {
    els.liveTranscript.textContent = "Listening.";
    setContinuousVoice("Listening");
    startRecognition(false);
    return;
  }
  els.liveTranscript.textContent = cleanFinal;
  setContinuousVoice("Thinking");
  stopRecognition(false);
  sendTurn(cleanFinal, "speech").catch(handleError);
}

function startRecognition(single = false, allowDuringSpeaking = false) {
  if (!state.recognitionSupported || !state.recognition || !state.chatbotOn || (state.isSpeaking && !allowDuringSpeaking)) return;
  state.singleListen = single;
  state.restartRecognition = !single;
  state.recognition.continuous = !single;
  state.recognition.interimResults = true;
  try {
    state.recognition.start();
  } catch (error) {
    if (error.name !== "InvalidStateError") {
      els.speechNotice.textContent = `Voice start failed: ${error.name || error.message}`;
    }
  }
}

function stopRecognition(allowRestart) {
  state.restartRecognition = Boolean(allowRestart);
  if (state.recognition && state.recognitionActive) {
    try {
      state.recognition.stop();
    } catch {}
  }
}

function speechChunks(text) {
  const chunks = String(text)
    .split(/(?<=[.!?])\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);
  return chunks.length ? chunks : [text];
}

function englishVoices() {
  if (!("speechSynthesis" in window)) return null;
  return window.speechSynthesis.getVoices().filter((voice) => voice.lang?.toLowerCase().startsWith("en"));
}

function voiceScore(voice, style) {
  const name = `${voice.name || ""} ${voice.voiceURI || ""}`.toLowerCase();
  let score = voice.localService ? 25 : 0;
  const premium = [
    "ava",
    "samantha",
    "allison",
    "susan",
    "zoe",
    "karen",
    "moira",
    "tessa",
    "serena",
    "jamie",
    "evan",
    "nathan",
    "daniel",
    "arthur",
    "oliver",
    "microsoft aria",
    "microsoft jenny",
    "microsoft sonia",
    "microsoft libby",
    "google us english",
    "google uk english",
  ];
  premium.forEach((candidate, index) => {
    if (name.includes(candidate)) score += 80 - index;
  });
  if (style === "bright" && /(ava|samantha|zoe|aria|jenny|google us)/.test(name)) score += 18;
  if (style === "calm" && /(daniel|karen|moira|serena|libby|google uk)/.test(name)) score += 18;
  if (style === "expressive" && /(ava|samantha|allison|aria|jenny)/.test(name)) score += 22;
  if (/compact|novelty|whisper|bad news|bubbles|cellos|zarvox|trinoids|pipe organ|organ/.test(name)) score -= 100;
  return score;
}

function preferredVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = englishVoices();
  const style = els.voiceStyle.value;
  return [...voices].sort((a, b) => voiceScore(b, style) - voiceScore(a, style))[0] || null;
}

function waitForEnglishVoices(timeoutMs = 1800) {
  if (!("speechSynthesis" in window)) return Promise.resolve([]);
  const ready = englishVoices();
  if (ready?.length) return Promise.resolve(ready);
  if (state.voiceLoadPromise) return state.voiceLoadPromise;
  state.voiceLoadPromise = new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve(englishVoices() || []);
    };
    if (window.speechSynthesis.addEventListener) {
      window.speechSynthesis.addEventListener("voiceschanged", finish, { once: true });
    } else {
      const oldHandler = window.speechSynthesis.onvoiceschanged;
      window.speechSynthesis.onvoiceschanged = (event) => {
        if (typeof oldHandler === "function") oldHandler.call(window.speechSynthesis, event);
        finish();
      };
    }
    window.setTimeout(finish, timeoutMs);
  });
  return state.voiceLoadPromise;
}

function speechSettings() {
  const style = els.voiceStyle.value;
  if (style === "calm") return { rate: state.session?.level === "A1" ? 0.78 : 0.84, pitch: 0.95 };
  if (style === "bright") return { rate: state.session?.level === "B1" ? 1.02 : 0.94, pitch: 1.12 };
  return { rate: state.session?.level === "A1" ? 0.82 : state.session?.level === "B1" ? 0.98 : 0.9, pitch: 1.04 };
}

async function speakWithBrowser(text, playbackId = null) {
  if (!state.chatbotOn || !("speechSynthesis" in window)) {
    startRecognition(false);
    return;
  }
  const token = playbackId ?? state.speechPlaybackId;
  await waitForEnglishVoices();
  if (!state.chatbotOn || token !== state.speechPlaybackId) return;
  window.speechSynthesis.cancel();
  state.isSpeaking = true;
  state.currentAiText = text;
  els.speechNotice.textContent = "AI is speaking. You can interrupt with your voice.";
  setContinuousVoice("AI speaking");
  const chunks = speechChunks(text);
  const settings = speechSettings();
  const voice = preferredVoice();
  let index = 0;
  const speakNext = () => {
    if (!state.chatbotOn || token !== state.speechPlaybackId) {
      state.isSpeaking = false;
      return;
    }
    if (index >= chunks.length) {
      finishAiSpeaking();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(chunks[index]);
    state.currentUtterance = utterance;
    utterance.lang = voice?.lang || "en-US";
    utterance.rate = settings.rate;
    utterance.pitch = settings.pitch;
    if (voice) utterance.voice = voice;
    utterance.onstart = () => startRecognition(false, true);
    utterance.onend = () => {
      if (!state.isSpeaking || state.currentUtterance !== utterance || token !== state.speechPlaybackId) return;
      index += 1;
      window.setTimeout(speakNext, 140);
    };
    utterance.onerror = utterance.onend;
    window.speechSynthesis.speak(utterance);
  };
  speakNext();
}

async function speak(text) {
  if (!state.chatbotOn) return;
  stopCurrentAiAudio();
  const token = state.speechPlaybackId;
  if ("speechSynthesis" in window) {
    await speakWithBrowser(text, token);
    return;
  }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  state.isSpeaking = true;
  state.currentAiText = text;
  els.speechNotice.textContent = "AI is speaking. You can interrupt with your voice.";
  setContinuousVoice("AI speaking");
  try {
    const data = await getJson("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, style: els.voiceStyle.value, level: state.session?.level || "A2" }),
    });
    if (!state.chatbotOn || token !== state.speechPlaybackId) return;
    const audio = new Audio(data.audio_url);
    state.currentAudio = audio;
    audio.onplay = () => startRecognition(false, true);
    audio.onended = () => {
      if (state.currentAudio === audio && token === state.speechPlaybackId) finishAiSpeaking();
    };
    audio.onerror = () => {
      if (state.currentAudio !== audio || token !== state.speechPlaybackId) return;
      state.isSpeaking = false;
      speakWithBrowser(text, token);
    };
    await audio.play();
  } catch {
    if (!state.chatbotOn || token !== state.speechPlaybackId) return;
    state.isSpeaking = false;
    speakWithBrowser(text, token);
  }
}

function stopVoiceCompletely() {
  state.chatbotOn = false;
  state.turnRequestId += 1;
  state.restartRecognition = false;
  state.singleListen = false;
  state.interruptionTurnActive = false;
  stopCurrentAiAudio();
  state.pendingSpeechText = "";
  if (state.speechSendTimer) {
    window.clearTimeout(state.speechSendTimer);
    state.speechSendTimer = null;
  }
  stopRecognition(false);
  if (state.recognition) {
    try {
      state.recognition.abort();
    } catch {}
  }
  setChatbotState(false);
  els.speechNotice.textContent = "Chatbot is closed. It is not listening.";
  setContinuousVoice("Voice off");
}

async function startChatbot(event) {
  event.preventDefault();
  if (!state.material) {
    els.speechNotice.textContent = "Make an English video first.";
    return;
  }
  await registerStudentAccount();
  if (!state.micReady) await requestMicrophoneAccess(false);
  if (!state.session || state.session.material_id !== state.material.id) {
    const data = await getJson("/api/student/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        participant_code: els.participantCode.value,
        level: state.material.level || els.system1VideoLevel.value,
        material_id: state.material.id,
        chatbot_listening: true,
        student_task: els.studentTask.value,
        voice_profile: els.voiceStyle.value,
      }),
    });
    state.session = data.session;
  } else {
    const data = await getJson(`/api/sessions/${state.session.id}/student-control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chatbot_listening: true }),
    });
    state.session = data.session;
  }
  setChatbotState(true);
  els.sessionLine.textContent = `${state.session.participant_code} · ${state.session.level} · ${state.session.material_title}`;
  els.liveTranscript.textContent = "Waiting for voice.";
  renderChat();
  if (state.recognitionSupported && state.micReady) startRecognition(false);
  else if (!state.recognitionSupported) els.speechNotice.textContent = "Speech recognition is not available. Use text in Settings.";
  else els.speechNotice.textContent = "Mic is not ready. Test mic or use text in Settings.";
  const openingPrompt = learnerOpeningPrompt(state.session);
  window.setTimeout(() => {
    const studentJustStarted = state.lastSpeechActivityAt && Date.now() - state.lastSpeechActivityAt < 900;
    if (state.chatbotOn && !state.pendingSpeechText && !state.isSpeaking && !state.turnInFlight && !studentJustStarted) {
      speak(openingPrompt);
    }
  }, 700);
}

async function stopChatbot() {
  if (state.session) {
    try {
      const data = await getJson(`/api/sessions/${state.session.id}/student-control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chatbot_listening: false }),
      });
      state.session = data.session;
    } catch {}
  }
  stopVoiceCompletely();
}

async function sendTurn(text, inputMode = "typed") {
  if (!state.session || !state.chatbotOn) {
    els.speechNotice.textContent = "Start the chatbot first.";
    return;
  }
  if (inputMode === "speech" && isProbablyAiEcho(text)) {
    els.liveTranscript.textContent = "Listening.";
    setContinuousVoice("Listening");
    startRecognition(false);
    return;
  }
  if (state.turnInFlight) return;
  state.turnInFlight = true;
  const requestId = (state.turnRequestId += 1);
  els.speechNotice.textContent = "AI is thinking.";
  try {
    const data = await getJson(`/api/sessions/${state.session.id}/turns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_text: text, input_mode: inputMode }),
    });
    if (!state.chatbotOn || requestId !== state.turnRequestId) return;
    state.session = data.session;
    renderChat();
    const last = state.session.turns[state.session.turns.length - 1];
    if (last?.ai_response) speak(last.ai_response);
  } finally {
    state.turnInFlight = false;
  }
}

function bindEvents() {
  els.settingsToggle.addEventListener("click", () => {
    const open = els.settingsPanel.classList.toggle("hidden") === false;
    els.settingsToggle.setAttribute("aria-expanded", String(open));
  });
  els.modeVideo.addEventListener("click", () => switchSystem1Mode("video"));
  els.modeTopic.addEventListener("click", () => switchSystem1Mode("topic"));
  els.system1VideoFile.addEventListener("change", () => {
    const file = els.system1VideoFile.files?.[0];
    els.selectedVideoName.textContent = file ? file.name : "No file selected";
  });
  els.system1VideoForm.addEventListener("submit", (event) => generateFromVideo(event).catch(handleError));
  els.system1TopicForm.addEventListener("submit", (event) => generateFromTopic(event).catch(handleError));
  els.playbackSubtitles.addEventListener("change", applyPlaybackSubtitles);
  els.registerStudent.addEventListener("click", () => registerStudentAccount().catch(handleError));
  els.startForm.addEventListener("submit", (event) => startChatbot(event).catch(handleError));
  els.stopChatbot.addEventListener("click", () => stopChatbot().catch(handleError));
  els.requestMic.addEventListener("click", () => requestMicrophoneAccess(true).catch(handleError));
  els.sendTextTurn.addEventListener("click", () => {
    const text = els.studentText.value.trim();
    if (!text) return;
    els.studentText.value = "";
    els.liveTranscript.textContent = text;
    sendTurn(text, "typed").catch(handleError);
  });
  if ("speechSynthesis" in window) window.speechSynthesis.onvoiceschanged = () => preferredVoice();
}

function handleError(error) {
  console.error(error);
  const message = error.message || "Something went wrong.";
  els.system1VideoStatus.textContent = message;
  els.system1TopicStatus.textContent = message;
  els.speechNotice.textContent = message;
  setConnection("Issue");
}

async function boot() {
  bindEvents();
  setupSpeechRecognition();
  setChatbotState(false);
  renderChat();
  await loadMaterial();
  setConnection("Ready");
}

boot().catch((error) => {
  setConnection("Error");
  handleError(error);
});
