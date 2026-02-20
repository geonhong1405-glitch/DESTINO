// planner.js: planner.html에서 AI 챗봇과 대화형으로 연동

document.addEventListener("DOMContentLoaded", function () {
    const promptInput = document.getElementById("ai-prompt");
    const sendBtn = document.querySelector("button.bg-brand");
    const chatBox = document.createElement("div");
    chatBox.id = "ai-chat-box";
    chatBox.style.marginTop = "2rem";
    promptInput.parentNode.appendChild(chatBox);

    sendBtn.addEventListener("click", async function () {
        const question = promptInput.value.trim();
        if (!question) return;
        chatBox.innerHTML += `<div class='user-msg'><b>나:</b> ${question}</div>`;
        promptInput.value = "";
        chatBox.innerHTML += `<div class='ai-msg'><b>AI:</b> <span class='loading'>답변 생성 중...</span></div>`;
        const aiMsgDiv = chatBox.querySelector(".ai-msg:last-child span");
        try {
            const res = await fetch("/rag/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question }),
            });
            const data = await res.json();
            aiMsgDiv.textContent = data.answer || "오류가 발생했습니다.";
        } catch (e) {
            aiMsgDiv.textContent = "서버 오류";
        }
    });
});
