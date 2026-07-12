(function () {
    "use strict";

    const DISMISS_KEY = "simas_widget_dismissed";

    const launcherWrap = document.getElementById("launcher-wrap");
    const launcherBtn = document.getElementById("launcher-btn");
    const dismissBtn = document.getElementById("dismiss-btn");
    const panel = document.getElementById("widget-panel");
    const minimizeBtn = document.getElementById("minimize-btn");
    const inputEl = document.getElementById("message-input");

    function notifyParent(state) {
        window.parent.postMessage({ source: "simas-widget", state: state }, "*");
    }

    function openPanel() {
        launcherWrap.classList.add("hidden");
        panel.classList.remove("hidden");
        notifyParent("expanded");
        if (inputEl) {
            inputEl.focus();
        }
    }

    function closePanel() {
        panel.classList.add("hidden");
        launcherWrap.classList.remove("hidden");
        notifyParent("collapsed");
    }

    function dismissWidget() {
        try {
            sessionStorage.setItem(DISMISS_KEY, "1");
        } catch {
            // Ignore storage failures (e.g. private browsing quota).
        }
        launcherWrap.classList.add("hidden");
        notifyParent("dismissed");
    }

    let dismissed = false;
    try {
        dismissed = sessionStorage.getItem(DISMISS_KEY) === "1";
    } catch {
        dismissed = false;
    }

    if (dismissed) {
        launcherWrap.classList.add("hidden");
        notifyParent("dismissed");
    } else {
        launcherBtn.addEventListener("click", openPanel);
        dismissBtn.addEventListener("click", dismissWidget);
        minimizeBtn.addEventListener("click", closePanel);

        // Let the parent page size the iframe correctly from the start.
        notifyParent("collapsed");
    }
})();
