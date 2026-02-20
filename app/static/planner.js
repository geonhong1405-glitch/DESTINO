document.addEventListener("DOMContentLoaded", function () {
    const promptInput = document.getElementById("ai-prompt");
    if (!promptInput) return;

    const sendBtn = promptInput.parentElement?.querySelector("button.bg-brand");
    if (!sendBtn) return;

    const chatBox = document.createElement("div");
    chatBox.id = "ai-chat-box";
    chatBox.className = "mt-6 space-y-3 text-left overflow-y-auto max-h-[45vh] pr-1";
    chatBox.style.scrollBehavior = "smooth";
    promptInput.parentElement.appendChild(chatBox);

    const sessionKey = "flight_chat_session_id";
    let sessionId = sessionStorage.getItem(sessionKey);
    if (!sessionId) {
        sessionId = globalThis.crypto?.randomUUID?.() || String(Date.now());
        sessionStorage.setItem(sessionKey, sessionId);
    }

    function isNearBottom() {
        const threshold = 80;
        return chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < threshold;
    }

    function scrollToBottom(force = false) {
        if (force || isNearBottom()) {
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }

    function appendUserMessage(text) {
        const item = document.createElement("div");
        item.className = "rounded-xl bg-white border border-gray-200 px-4 py-3";
        item.innerHTML = `<b>나:</b> ${text}`;
        chatBox.appendChild(item);
        scrollToBottom(true);
    }

    function appendLoadingMessage() {
        const item = document.createElement("div");
        item.className = "rounded-xl bg-blue-50 border border-blue-200 px-4 py-3";
        item.innerHTML = "<b>AI:</b> 응답 생성 중...";
        chatBox.appendChild(item);
        scrollToBottom(true);
        return item;
    }

    async function sendMessage() {
        const message = promptInput.value.trim();
        if (!message) return;

        appendUserMessage(message);
        promptInput.value = "";

        const loadingItem = appendLoadingMessage();
        try {
            const res = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                    session_id: sessionId,
                }),
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const data = await res.json();
            const html = data?.response || "응답을 받지 못했습니다.";
            loadingItem.innerHTML = `<b>AI:</b><div class="mt-2">${html}</div>`;
            scrollToBottom(true);
        } catch (error) {
            loadingItem.innerHTML = "<b>AI:</b> 요청 중 오류가 발생했습니다.";
            scrollToBottom(true);
        }
    }

    sendBtn.addEventListener("click", sendMessage);
    promptInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });
});
