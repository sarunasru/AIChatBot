(function () {
    "use strict";

    const STORAGE_KEY = "faq_assistant_history";
    const SESSION_KEY = "faq_assistant_session_id";

    // Matches plain-text URLs (with or without http/https). Declared up here so
    // it's initialised before the history re-render loop below calls linkify().
    const URL_RE = /((?:https?:\/\/)?(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:lt|com|org|net|eu|io|dev)(?:\/[^\s<]*)?)/gi;

    // A random id, stable for this browser session, so the server can group the
    // messages of one conversation together in the chat logs.
    const sessionId = loadSessionId();

    function loadSessionId() {
        try {
            let id = sessionStorage.getItem(SESSION_KEY);
            if (!id) {
                id = (crypto.randomUUID && crypto.randomUUID()) ||
                    `${Date.now()}-${Math.random().toString(16).slice(2)}`;
                sessionStorage.setItem(SESSION_KEY, id);
            }
            return id;
        } catch {
            return "";
        }
    }

    const messagesEl = document.getElementById("messages");
    const inputEl = document.getElementById("message-input");
    const sendBtn = document.getElementById("send-btn");
    const clearBtn = document.getElementById("clear-btn");
    const contactBtn = document.getElementById("contact-btn");
    const loadingEl = document.getElementById("loading-indicator");
    const chatAppEl = document.querySelector(".chat-app");

    /** @type {{role: "user" | "assistant", content: string}[]} */
    let history = loadHistory();

    // Re-render any history restored from this browser session.
    for (const entry of history) {
        renderMessage(entry.role, entry.content);
    }

    function loadHistory() {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch {
            return [];
        }
    }

    function saveHistory() {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history));
        } catch {
            // Ignore storage failures (e.g. private browsing quota).
        }
    }

    function scrollToBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // Turn plain-text URLs into clickable links. Input is HTML-escaped first,
    // so this is safe against injection. (URL_RE is declared at the top.)
    function linkify(content) {
        return escapeHtml(content).replace(URL_RE, (match) => {
            // Keep trailing sentence punctuation outside the link.
            const trail = (match.match(/[.,;:!?)]+$/) || [""])[0];
            const url = trail ? match.slice(0, -trail.length) : match;
            const href = /^https?:\/\//i.test(url) ? url : `https://${url}`;
            return `<a href="${href}" target="_blank" rel="noopener noreferrer">${url}</a>${trail}`;
        });
    }

    function renderMessage(role, content) {
        const wrapper = document.createElement("div");
        wrapper.className = `message ${role}`;

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.innerHTML = linkify(content);

        wrapper.appendChild(bubble);
        messagesEl.appendChild(wrapper);
        scrollToBottom();
        return wrapper;
    }

    function renderError(content) {
        const wrapper = document.createElement("div");
        wrapper.className = "message error";

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.textContent = content;

        wrapper.appendChild(bubble);
        messagesEl.appendChild(wrapper);
        scrollToBottom();
    }

    function setLoading(isLoading) {
        loadingEl.classList.toggle("hidden", !isLoading);
        sendBtn.disabled = isLoading;
        if (isLoading) {
            scrollToBottom();
        }
    }

    function autoResizeInput() {
        inputEl.style.height = "auto";
        inputEl.style.height = `${Math.min(inputEl.scrollHeight, 140)}px`;
    }

    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text) {
            return;
        }

        inputEl.value = "";
        autoResizeInput();

        renderMessage("user", text);
        history.push({ role: "user", content: text });
        saveHistory();

        setLoading(true);

        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    history: history.slice(0, -1),
                    session_id: sessionId,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                const errorMessage = data.error || "Kažkas nutiko ne taip. Bandykite dar kartą.";
                renderError(errorMessage);
                return;
            }

            renderMessage("assistant", data.reply);
            history.push({ role: "assistant", content: data.reply });
            saveHistory();
        } catch {
            renderError("Nepavyko pasiekti serverio. Patikrinkite interneto ryšį ir bandykite dar kartą.");
        } finally {
            setLoading(false);
        }
    }

    function clearChat() {
        history = [];
        saveHistory();
        messagesEl.innerHTML = "";
        renderMessage(
            "assistant",
            "Sveiki! Klauskite manęs bet ko apie mūsų biblioteka ir jos paslaugas – mielai padėsiu."
        );
    }

    // --- Contact form ------------------------------------------------------
    let contactOverlay = null;

    function buildContactForm() {
        const overlay = document.createElement("div");
        overlay.className = "contact-overlay hidden";
        overlay.innerHTML = `
            <div class="contact-panel">
                <div class="contact-header">
                    <h2>Susisiekti su darbuotoju</h2>
                    <button type="button" class="contact-close" aria-label="Uždaryti">&#10005;</button>
                </div>
                <p class="contact-intro">
                    Jei asistentas neatsakė į jūsų klausimą, palikite savo el. paštą ir žinutę –
                    ją kartu su pokalbio istorija persiųsime bibliotekos darbuotojui.
                </p>
                <label class="contact-field">
                    <span>Jūsų el. paštas *</span>
                    <input type="email" class="contact-email" required maxlength="254" autocomplete="email">
                </label>
                <label class="contact-field">
                    <span>Vardas</span>
                    <input type="text" class="contact-name" maxlength="120" autocomplete="name">
                </label>
                <label class="contact-field">
                    <span>Žinutė *</span>
                    <textarea class="contact-message" rows="4" required maxlength="4000"></textarea>
                </label>
                <label class="contact-consent">
                    <input type="checkbox" class="contact-consent-box">
                    <span>Sutinku, kad mano žinutė ir pokalbio istorija būtų persiųsti bibliotekos darbuotojui.</span>
                </label>
                <div class="contact-status" role="alert"></div>
                <div class="contact-actions">
                    <button type="button" class="contact-cancel">Atšaukti</button>
                    <button type="button" class="contact-submit">Siųsti</button>
                </div>
            </div>
        `;
        chatAppEl.appendChild(overlay);

        overlay.querySelector(".contact-close").addEventListener("click", closeContactForm);
        overlay.querySelector(".contact-cancel").addEventListener("click", closeContactForm);
        overlay.querySelector(".contact-submit").addEventListener("click", submitContactForm);
        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                closeContactForm();
            }
        });

        return overlay;
    }

    function openContactForm() {
        if (!contactOverlay) {
            contactOverlay = buildContactForm();
        }
        // Prefill the message with the visitor's last question, if any.
        const lastUser = [...history].reverse().find((entry) => entry.role === "user");
        const messageEl = contactOverlay.querySelector(".contact-message");
        if (lastUser && !messageEl.value) {
            messageEl.value = lastUser.content;
        }
        const statusEl = contactOverlay.querySelector(".contact-status");
        statusEl.textContent = "";
        statusEl.classList.remove("success");
        contactOverlay.classList.remove("hidden");
        contactOverlay.querySelector(".contact-email").focus();
    }

    function closeContactForm() {
        if (contactOverlay) {
            contactOverlay.classList.add("hidden");
        }
    }

    async function submitContactForm() {
        const email = contactOverlay.querySelector(".contact-email").value.trim();
        const name = contactOverlay.querySelector(".contact-name").value.trim();
        const message = contactOverlay.querySelector(".contact-message").value.trim();
        const consent = contactOverlay.querySelector(".contact-consent-box").checked;
        const statusEl = contactOverlay.querySelector(".contact-status");
        const submitEl = contactOverlay.querySelector(".contact-submit");

        statusEl.classList.remove("success");

        if (!email || !message) {
            statusEl.textContent = "Užpildykite el. paštą ir žinutę.";
            return;
        }
        if (!consent) {
            statusEl.textContent = "Turite sutikti, kad žinutė būtų persiųsta.";
            return;
        }

        submitEl.disabled = true;
        statusEl.textContent = "Siunčiama...";

        try {
            const response = await fetch("/contact", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, name, message, consent, history }),
            });
            const data = await response.json();

            if (!response.ok) {
                statusEl.textContent = data.error || "Nepavyko išsiųsti. Bandykite dar kartą.";
                return;
            }

            statusEl.classList.add("success");
            statusEl.textContent = "Žinutė išsiųsta! Su jumis susisieksime el. paštu.";
            contactOverlay.querySelector(".contact-message").value = "";
            contactOverlay.querySelector(".contact-consent-box").checked = false;
            setTimeout(closeContactForm, 1800);
        } catch {
            statusEl.textContent = "Nepavyko pasiekti serverio. Bandykite dar kartą.";
        } finally {
            submitEl.disabled = false;
        }
    }

    if (contactBtn) {
        contactBtn.addEventListener("click", openContactForm);
    }

    sendBtn.addEventListener("click", sendMessage);

    inputEl.addEventListener("input", autoResizeInput);

    inputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });

    clearBtn.addEventListener("click", clearChat);
})();
