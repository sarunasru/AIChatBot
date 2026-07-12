(function () {
    "use strict";

    const launcherBtn = document.getElementById("launcher-btn");
    const panel = document.getElementById("widget-panel");
    const minimizeBtn = document.getElementById("minimize-btn");
    const inputEl = document.getElementById("message-input");

    function notifyParent(state) {
        window.parent.postMessage({ source: "simas-widget", state: state }, "*");
    }

    function openPanel() {
        launcherBtn.classList.add("hidden");
        panel.classList.remove("hidden");
        notifyParent("expanded");
        if (inputEl) {
            inputEl.focus();
        }
    }

    function closePanel() {
        panel.classList.add("hidden");
        launcherBtn.classList.remove("hidden");
        notifyParent("collapsed");
    }

    launcherBtn.addEventListener("click", openPanel);
    minimizeBtn.addEventListener("click", closePanel);

    // Let the parent page size the iframe correctly from the start.
    notifyParent("collapsed");
})();
