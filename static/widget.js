/**
 * Embeddable loader for the "Simas" chat widget.
 *
 * Usage on any VU website:
 *   <script src="https://YOUR-DOMAIN/static/widget.js" async></script>
 *
 * Injects a fixed-position iframe that loads the widget from this same
 * server, so all styling is isolated from the host page's CSS and the
 * chat UI looks identical everywhere it's embedded.
 */
(function () {
    "use strict";

    const currentScript = document.currentScript;
    if (!currentScript) {
        return;
    }

    const origin = new URL(currentScript.src).origin;

    // static/Simas.png + label bar, plus a small row above for the dismiss "x", both transparent.
    const COLLAPSED = { width: "220px", height: "234px", borderRadius: "0" };

    function getExpandedSize() {
        if (window.innerWidth <= 480 || window.innerHeight <= 500) {
            return { width: "100vw", height: "100vh", borderRadius: "0", bottom: "0", right: "0" };
        }
        return { width: "380px", height: "620px", borderRadius: "16px", bottom: "20px", right: "20px" };
    }

    const iframe = document.createElement("iframe");
    iframe.src = origin + "/widget";
    iframe.title = "Virtualus DI asistentas Simas";
    iframe.setAttribute("allowtransparency", "true");
    iframe.setAttribute("scrolling", "no");
    iframe.style.position = "fixed";
    iframe.style.bottom = "20px";
    iframe.style.right = "20px";
    iframe.style.border = "none";
    iframe.style.background = "transparent";
    iframe.style.zIndex = "2147483000";
    iframe.style.boxShadow = "none";
    iframe.style.colorScheme = "light";
    applySize(COLLAPSED);

    function applySize(size) {
        iframe.style.width = size.width;
        iframe.style.height = size.height;
        iframe.style.borderRadius = size.borderRadius;
        if (size.bottom !== undefined) iframe.style.bottom = size.bottom;
        if (size.right !== undefined) iframe.style.right = size.right;
    }

    window.addEventListener("message", function (event) {
        if (event.origin !== origin) {
            return;
        }
        const data = event.data;
        if (!data || data.source !== "simas-widget") {
            return;
        }

        if (data.state === "expanded") {
            applySize(getExpandedSize());
        } else if (data.state === "dismissed") {
            iframe.style.display = "none";
        } else {
            iframe.style.display = "";
            iframe.style.bottom = "20px";
            iframe.style.right = "20px";
            applySize(COLLAPSED);
        }
    });

    function mount() {
        document.body.appendChild(iframe);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", mount);
    } else {
        mount();
    }
})();
