let activeWorkspace = "topic";

const STORAGE_KEYS = {
  theme: "aiWriterTheme",
  actions: "aiWriterActions",
  recents: "aiWriterRecentOutputs"
};

document.addEventListener("DOMContentLoaded", function () {
  applySavedTheme();
  showTopic();
  updateWordCount();
  updateDashboardStats();
  renderRecentOutputs();
});

/* ========== THEME ========== */

function applySavedTheme() {
  const savedTheme = localStorage.getItem(STORAGE_KEYS.theme) || "dark";

  document.body.classList.toggle("light-theme", savedTheme === "light");

  updateThemeButton();
}

function toggleTheme() {
  const isLight = document.body.classList.toggle("light-theme");

  localStorage.setItem(STORAGE_KEYS.theme, isLight ? "light" : "dark");

  updateThemeButton();

  showToast(isLight ? "Light theme enabled" : "Dark theme enabled");
}

function updateThemeButton() {
  const btn = document.getElementById("themeToggle");

  if (!btn) return;

  btn.innerText = document.body.classList.contains("light-theme")
    ? "🌙 Dark"
    : "☀️ Light";
}

/* ========== SECTION SWITCH ========== */

function showTopic() {
  activeWorkspace = "topic";

  document.getElementById("topicSection").classList.add("active-section");
  document.getElementById("improveSection").classList.remove("active-section");

  document.getElementById("topicTab").classList.add("active");
  document.getElementById("improveTab").classList.remove("active");
}

function showImprove() {
  activeWorkspace = "improve";

  document.getElementById("improveSection").classList.add("active-section");
  document.getElementById("topicSection").classList.remove("active-section");

  document.getElementById("improveTab").classList.add("active");
  document.getElementById("topicTab").classList.remove("active");
}

function logoutUser() {
  window.location.href = "/logout";
}

/* ========== COMMON HELPERS ========== */

function setLoading(loaderId, statusId, isLoading, loadingText) {
  const loader = document.getElementById(loaderId);
  const status = document.getElementById(statusId);

  if (loader) {
    loader.style.display = isLoading ? "block" : "none";
  }

  if (status) {
    status.innerText = isLoading ? loadingText || "Generating..." : "Ready";
    status.classList.toggle("loading", isLoading);
  }
}

function setOutput(elementId, text) {
  const el = document.getElementById(elementId);

  if (!el) return;

  el.innerText = text || "";
  el.classList.remove("empty-state");
}

function getCleanOutput(elementId) {
  const el = document.getElementById(elementId);

  if (!el) return "";

  const text = el.innerText.trim();

  if (
    text === "Your generated description will appear here." ||
    text === "Your AI improved text will appear here."
  ) {
    return "";
  }

  return text;
}

function clearOutput(elementId) {
  const el = document.getElementById(elementId);

  if (!el) return;

  if (elementId === "topicOutput") {
    el.innerText = "Your generated description will appear here.";
  } else {
    el.innerText = "Your AI improved text will appear here.";
  }

  el.classList.add("empty-state");

  showToast("Output cleared");
}

function showToast(message) {
  const toast = document.getElementById("toast");

  if (!toast) return;

  toast.innerText = message;
  toast.classList.add("show");

  setTimeout(function () {
    toast.classList.remove("show");
  }, 2200);
}

function incrementActions() {
  const total = Number(localStorage.getItem(STORAGE_KEYS.actions) || "0") + 1;

  localStorage.setItem(STORAGE_KEYS.actions, String(total));

  updateDashboardStats();
}

function updateDashboardStats() {
  const totalActions = document.getElementById("totalActions");

  if (totalActions) {
    totalActions.innerText = localStorage.getItem(STORAGE_KEYS.actions) || "0";
  }
}

function requireText(value, message) {
  if (!value || value.trim() === "") {
    showToast(message || "Please enter text first");
    return false;
  }

  return true;
}

/* ========== TOPIC GENERATOR ========== */

async function generateTopic() {
  const topic = document.getElementById("topicInput").value;
  const length = document.getElementById("lengthSelect").value;

  if (!requireText(topic, "Please enter a topic first")) return;

  setLoading("loaderTopic", "topicStatus", true, "Generating...");
  setOutput("topicOutput", "");

  try {
    const res = await fetch("/topic", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        topic: topic,
        length: length
      })
    });

    const data = await res.json();

    const result = data.result || "AI did not return a result.";

    setOutput("topicOutput", result);

    saveRecentOutput("Topic", topic, result);

    incrementActions();

    showToast("Description generated");
  } catch (error) {
    setOutput(
      "topicOutput",
      "Something went wrong. Please check backend/API key and try again."
    );

    showToast("Generation failed");
  } finally {
    setLoading("loaderTopic", "topicStatus", false);
  }
}

async function regenerateTopic() {
  const original = getCleanOutput("topicOutput");
  const feedback = document.getElementById("topicFeedback").value;

  if (!requireText(original, "Generate a description first")) return;
  if (!requireText(feedback, "Write feedback first")) return;

  setLoading("loaderTopic", "topicStatus", true, "Regenerating...");

  try {
    const res = await fetch("/regenerate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        original: original,
        feedback: feedback
      })
    });

    const data = await res.json();

    const result = data.result || "AI did not return a result.";

    setOutput("topicOutput", result);

    saveRecentOutput("Topic Feedback", feedback, result);

    incrementActions();

    showToast("Updated with feedback");
  } catch (error) {
    showToast("Regeneration failed");
  } finally {
    setLoading("loaderTopic", "topicStatus", false);
  }
}

/* ========== TEXT IMPROVER ========== */

function updateWordCount() {
  const input = document.getElementById("userText");

  const text = input ? input.value : "";

  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const chars = text.length;

  const wordCount = document.getElementById("wordCount");
  const charCount = document.getElementById("charCount");
  const miniWordCount = document.getElementById("miniWordCount");
  const miniCharCount = document.getElementById("miniCharCount");

  if (wordCount) wordCount.innerText = words;
  if (charCount) charCount.innerText = chars;
  if (miniWordCount) miniWordCount.innerText = words;
  if (miniCharCount) miniCharCount.innerText = chars;
}

async function generateText() {
  await runTextAction("/generate", "Generate", "Generating...");
}

async function correctText() {
  await runTextAction("/correct", "Correction", "Correcting...");
}

async function enhanceText() {
  await runTextAction("/enhance", "AI Enhanced", "Enhancing...");
}

async function runTextAction(endpoint, actionName, loadingText) {
  const text = document.getElementById("userText").value;

  if (!requireText(text, "Please enter text first")) return;

  setLoading("loaderText", "textStatus", true, loadingText);
  setOutput("textOutput", "");

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: text
      })
    });

    const data = await res.json();

    const result = data.result || "AI did not return a result.";

    setOutput("textOutput", result);

    saveRecentOutput(actionName, text, result);

    incrementActions();

    showToast(actionName + " completed");

    checkProfessionalAuto();

  } catch (error) {
    setOutput(
      "textOutput",
      "Something went wrong. Please check backend/API key and try again."
    );

    showToast("AI action failed");
  } finally {
    setLoading("loaderText", "textStatus", false);
  }
}

async function wordCount() {
  const text = document.getElementById("userText").value;

  updateWordCount();

  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const chars = text.length;

  setOutput("textOutput", "Words: " + words + " | Characters: " + chars);

  showToast("Word count updated");
}

async function checkProfessional() {
  const text = document.getElementById("userText").value;

  if (!requireText(text, "Please enter text first")) return;

  setLoading("loaderText", "textStatus", true, "Checking...");

  try {
    const res = await fetch("/professional", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: text
      })
    });

    const data = await res.json();

    setOutput("textOutput", data.result || "No analysis received.");

    updateProfessionalScore(data.result || "");

    incrementActions();

    showToast("Professionalism checked");
  } catch (error) {
    showToast("Professionalism check failed");
  } finally {
    setLoading("loaderText", "textStatus", false);
  }
}

async function checkProfessionalAuto() {
  const text = getCleanOutput("textOutput");

  if (text.length < 20) return;

  try {
    const res = await fetch("/professional", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: text
      })
    });

    const data = await res.json();

    updateProfessionalScore(data.result || "");
  } catch (error) {
    const score = document.getElementById("professionalScore");

    if (score) score.innerText = "--";
  }
}

function updateProfessionalScore(result) {
  const score = document.getElementById("professionalScore");

  if (!score) return;

  const match = String(result).match(/(\d+(\.\d+)?)(\s*\/\s*10|\s*out of\s*10)?/i);

  score.innerText = match ? match[1] + "/10" : "Checked";
}

async function checkPlagiarism() {
  const text = document.getElementById("userText").value;

  if (!requireText(text, "Please enter text first")) return;

  setLoading("loaderText", "textStatus", true, "Checking...");

  try {
    const res = await fetch("/plagiarism", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: text
      })
    });

    const data = await res.json();

    document.getElementById("plagiarismResult").innerText =
      data.result || "No analysis received.";

    incrementActions();

    showToast("Plagiarism analysis completed");
  } catch (error) {
    document.getElementById("plagiarismResult").innerText =
      "Unable to check right now.";
  } finally {
    setLoading("loaderText", "textStatus", false);
  }
}

/* ========== COPY + DOWNLOAD ========== */

function copyText(elementId) {
  const text = getCleanOutput(elementId);

  if (!text) {
    showToast("Nothing to copy yet");
    return;
  }

  navigator.clipboard
    .writeText(text)
    .then(function () {
      showToast("Copied to clipboard");
    })
    .catch(function () {
      showToast("Copy failed");
    });
}

function downloadText(elementId, fileName) {
  const text = getCleanOutput(elementId);

  if (!text) {
    showToast("Please generate result first");
    return;
  }

  const blob = new Blob([text], {
    type: "text/plain;charset=utf-8"
  });

  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");

  a.href = url;
  a.download = fileName;

  document.body.appendChild(a);

  a.click();

  document.body.removeChild(a);

  URL.revokeObjectURL(url);

  showToast("Download started");
}

function downloadCurrentResult() {
  if (activeWorkspace === "topic") {
    downloadText("topicOutput", "ai-topic-description.txt");
  } else {
    downloadText("textOutput", "ai-writing-result.txt");
  }
}

/* ========== RECENT OUTPUTS ========== */

function saveRecentOutput(type, input, output) {
  const recents = getRecentOutputs();

  recents.unshift({
    type: type,
    input: String(input).slice(0, 120),
    output: String(output).slice(0, 450),
    time: new Date().toLocaleString()
  });

  localStorage.setItem(
    STORAGE_KEYS.recents,
    JSON.stringify(recents.slice(0, 6))
  );

  renderRecentOutputs();
}

function getRecentOutputs() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.recents) || "[]");
  } catch (error) {
    return [];
  }
}

function renderRecentOutputs() {
  const box = document.getElementById("recentList");

  if (!box) return;

  const recents = getRecentOutputs();

  if (recents.length === 0) {
    box.innerHTML =
      '<p class="empty-recent">No recent outputs yet. Generate something to show it here.</p>';

    return;
  }

  box.innerHTML = recents
    .map(function (item) {
      return `
        <article class="recent-item">
          <div class="recent-head">
            <strong>${escapeHtml(item.type)}</strong>
            <small>${escapeHtml(item.time)}</small>
          </div>

          <p><b>Input:</b> ${escapeHtml(item.input)}</p>
          <p>${escapeHtml(item.output)}</p>
        </article>
      `;
    })
    .join("");
}

function clearRecentOutputs() {
  localStorage.removeItem(STORAGE_KEYS.recents);

  renderRecentOutputs();

  showToast("Recent outputs cleared");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* ========== GOOGLE LOGIN SUPPORT ========== */

function handleCredentialResponse(response) {
  fetch("/google-login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      token: response.credential
    })
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "success") {
        window.location.href = "/index";
      } else {
        alert("Google login failed");
      }
    })
    .catch((error) => {
      console.error("Google login error:", error);
    });
}
