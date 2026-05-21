(function () {
  var KEY = "agentFactoryBrain";
  var DEFAULT_BRAIN = "claude";
  var THEMES = {
    claude: { label: "Claude", accent: "#D97757", soft: "rgba(217, 119, 87, 0.18)" },
    codex: { label: "Codex", accent: "#10A37F", soft: "rgba(16, 163, 127, 0.18)" },
    gemini: { label: "Gemini", accent: "#4796E3", soft: "rgba(145, 119, 199, 0.18)" },
    fake: { label: "Fake", accent: "#858585", soft: "rgba(133, 133, 133, 0.18)" },
  };

  function normalize(value) {
    return THEMES[value] ? value : DEFAULT_BRAIN;
  }

  function getBrain() {
    try { return normalize(localStorage.getItem(KEY)); } catch (e) { return DEFAULT_BRAIN; }
  }

  function applyBrain(value) {
    var brain = normalize(value);
    var theme = THEMES[brain];
    var root = document.documentElement;
    root.dataset.brain = brain;
    root.style.setProperty("--brain-accent", theme.accent);
    root.style.setProperty("--brain-accent-soft", theme.soft);
    root.style.setProperty("--af-primary", theme.accent);
    root.style.setProperty("--af-primary-soft", theme.soft);
    root.style.setProperty("--accent", theme.accent);
    if (document.body) document.body.dataset.brain = brain;
    return brain;
  }

  function broadcast(brain) {
    var message = { type: "agent-factory-brain", brain: brain };
    try {
      document.querySelectorAll("iframe").forEach(function (frame) {
        if (frame.contentWindow) frame.contentWindow.postMessage(message, "*");
      });
    } catch (e) {}
    try {
      if (window.parent && window.parent !== window) window.parent.postMessage(message, "*");
    } catch (e) {}
  }

  function setBrain(value) {
    var brain = normalize(value);
    try { localStorage.setItem(KEY, brain); } catch (e) {}
    applyBrain(brain);
    broadcast(brain);
    return brain;
  }

  window.addEventListener("storage", function (event) {
    if (event.key === KEY) applyBrain(event.newValue);
  });

  window.addEventListener("message", function (event) {
    if (event.data && event.data.type === "agent-factory-brain") {
      applyBrain(event.data.brain);
    }
  });

  window.AgentFactoryBrain = {
    themes: THEMES,
    getBrain: getBrain,
    setBrain: setBrain,
    applyBrain: applyBrain,
  };

  applyBrain(getBrain());
})();
