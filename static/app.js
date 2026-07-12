(function () {
    "use strict";

    const STORAGE_KEY = "faq_assistant_history";

    const messagesEl = document.getElementById("messages");
    const inputEl = document.getElementById("message-input");
    const sendBtn = document.getElementById("send-btn");
    const clearBtn = document.getElementById("clear-btn");
    const loadingEl = document.getElementById("loading-indicator");

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

    function renderMessage(role, content) {
        const wrapper = document.createElement("div");
        wrapper.className = `message ${role}`;

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.textContent = content;

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
