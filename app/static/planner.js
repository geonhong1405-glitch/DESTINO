document.addEventListener("DOMContentLoaded", function () {
    const promptInput = document.getElementById("ai-prompt");
    if (!promptInput) return;

    const sendBtn = promptInput.parentElement?.querySelector("button.bg-brand");
    if (!sendBtn) return;
    const promptWrap = promptInput.parentElement;
    const cardWrap = promptWrap?.parentElement;
    const heroRoot = cardWrap?.parentElement;
    if (promptWrap) promptWrap.classList.add("ai-composer-wrap");
    if (cardWrap) cardWrap.classList.add("ai-chat-combined");

    function collapseHeroForChat() {
        if (!heroRoot) return;
        heroRoot.classList.add("ai-chat-mode");
    }

    const shell = document.createElement("section");
    shell.id = "ai-chat-shell";
    shell.className = "mt-6 text-left";
    shell.innerHTML = `
        <div class="ai-chat-panel">
            <div class="ai-chat-panel__header">
                <div class="ai-chat-panel__badge">
                    <span class="ai-chat-panel__dot"></span>
                    여행 플래너와 대화 중
                </div>
                <div class="ai-chat-panel__hint"></div>
            </div>
            <div id="ai-chat-box" class="ai-chat-messages" aria-live="polite"></div>
        </div>
        <button id="ai-cart-fab" class="ai-cart-fab" type="button" aria-expanded="false" aria-controls="ai-cart-drawer" title="장바구니 열기">
            <span class="ai-cart-fab__icon">🧺</span>
            <span class="ai-cart-fab__label">장바구니</span>
            <span id="ai-cart-count" class="ai-cart-fab__count" hidden>0</span>
        </button>
        <div id="ai-cart-drawer" class="ai-cart-drawer" aria-hidden="true">
            <div class="ai-cart-drawer__backdrop" data-cart-close></div>
            <section class="ai-cart-drawer__panel">
                <div class="ai-cart-drawer__grab"></div>
                <div class="ai-cart-drawer__header">
                    <strong>담은 항목</strong>
                    <button type="button" class="ai-cart-drawer__close" data-cart-close>닫기</button>
                </div>
                <ul id="ai-cart-list" class="ai-cart-list"></ul>
                <div id="ai-cart-empty" class="ai-cart-empty">담은 항목이 없습니다.</div>
            </section>
        </div>
    `;
    cardWrap.insertBefore(shell, promptWrap);

    const chatBox = shell.querySelector("#ai-chat-box");
    const cartFab = shell.querySelector("#ai-cart-fab");
    const cartCount = shell.querySelector("#ai-cart-count");
    const cartDrawer = shell.querySelector("#ai-cart-drawer");
    const cartList = shell.querySelector("#ai-cart-list");
    const cartEmpty = shell.querySelector("#ai-cart-empty");
    chatBox.style.scrollBehavior = "smooth";

    const sessionKey = "flight_chat_session_id";
    let sessionId = sessionStorage.getItem(sessionKey);
    if (!sessionId) {
        sessionId = globalThis.crypto?.randomUUID?.() || String(Date.now());
        sessionStorage.setItem(sessionKey, sessionId);
    }
    const cartStorageKey = "planner_cart_items";
    let cartItems = [];
    try {
        cartItems = JSON.parse(sessionStorage.getItem(cartStorageKey) || "[]");
        if (!Array.isArray(cartItems)) cartItems = [];
    } catch {
        cartItems = [];
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

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function appendUserMessage(text) {
        const item = document.createElement("div");
        item.className = "ai-msg ai-msg--user";
        item.innerHTML = `
            <div class="ai-msg__meta">나</div>
            <div class="ai-msg__bubble">${escapeHtml(text)}</div>
        `;
        chatBox.appendChild(item);
        scrollToBottom(true);
    }

    function appendLoadingMessage() {
        const item = document.createElement("div");
        item.className = "ai-msg ai-msg--bot";
        item.innerHTML = `
            <div class="ai-msg__meta">DESTINO AI</div>
            <div class="ai-msg__bubble ai-msg__bubble--loading">
                <span class="ai-dots"><i></i><i></i><i></i></span>
                응답 생성 중...
            </div>
        `;
        chatBox.appendChild(item);
        scrollToBottom(true);
        return item;
    }

    function saveCart() {
        sessionStorage.setItem(cartStorageKey, JSON.stringify(cartItems));
    }

    function setCartDrawer(open) {
        if (!cartDrawer || !cartFab) return;
        cartDrawer.classList.toggle("is-open", !!open);
        cartDrawer.setAttribute("aria-hidden", open ? "false" : "true");
        cartFab.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function renderCart() {
        if (!cartList || !cartEmpty) return;
        cartList.innerHTML = "";
        cartEmpty.style.display = cartItems.length ? "none" : "block";
        if (cartCount) {
            cartCount.hidden = cartItems.length === 0;
            cartCount.textContent = String(cartItems.length || 0);
        }
        cartItems.forEach((item, idx) => {
            const li = document.createElement("li");
            li.className = "ai-cart-item";
            li.innerHTML = `
                <div class="ai-cart-item__type">${escapeHtml(item.type || "항목")}</div>
                <div class="ai-cart-item__name">${escapeHtml(item.name || "-")}</div>
                ${item.meta ? `<div class="ai-cart-item__meta">${escapeHtml(item.meta)}</div>` : ""}
                <button type="button" class="ai-cart-item__remove" data-cart-remove="${idx}" title="삭제">×</button>
            `;
            cartList.appendChild(li);
        });
    }

    function addCartItem(item) {
        const key = `${item.type || ""}__${item.name || ""}__${item.meta || ""}`.toLowerCase();
        const exists = cartItems.some((x) => `${x.type || ""}__${x.name || ""}__${x.meta || ""}`.toLowerCase() === key);
        if (exists) return false;
        cartItems.push(item);
        saveCart();
        renderCart();
        return true;
    }

    cartFab?.addEventListener("click", () => setCartDrawer(!cartDrawer?.classList.contains("is-open")));
    shell.querySelectorAll("[data-cart-close]").forEach((el) => el.addEventListener("click", () => setCartDrawer(false)));
    cartList?.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-cart-remove]");
        if (!btn) return;
        const idx = Number(btn.getAttribute("data-cart-remove"));
        if (Number.isNaN(idx)) return;
        cartItems.splice(idx, 1);
        saveCart();
        renderCart();
    });

    function parseFlightTableCards(rawHtml) {
        const html = String(rawHtml || "");
        if (!html.includes("<table") || !/API/.test(html)) return [];
        const metaText = (wrap.textContent || "").replace(/\s+/g, " ");
        const hasReturnDateField = metaText.includes("\uBCF5\uADC0\uC77C:");
        const isRoundTrip = hasReturnDateField && !metaText.includes("\uBCF5\uADC0\uC77C: -");
        const wrap = document.createElement("div");
        wrap.innerHTML = html;
        const table = wrap.querySelector("table");
        if (!table) return [];
        const cards = [];
        table.querySelectorAll("tr").forEach((tr) => {
            const tds = Array.from(tr.querySelectorAll("td"));
            if (tds.length < 5) return;
            const cells = tds.map((td) => (td.textContent || "").trim()).filter(Boolean);
            if (cells.length < 5) return;
            if (cells[0].includes("-")) return;
            const [airline, dep, arr, routeInfo, duration, price] = cells;
            cards.push({
                type: "항공편",
                name: `${airline} ${dep} 출발`,
                meta: [arr ? `도착 ${arr}` : "", routeInfo || "", duration ? `소요 ${duration}` : "", price || ""]
                    .filter(Boolean)
                    .join(" | "),
                airline,
                dep,
                arr,
                routeInfo,
                duration,
                price,
            });
        });
        return cards.slice(0, 8);
    }

    function parseListCards(rawHtml) {
        const html = String(rawHtml || "");
        const isHotel = /호텔|숙소|렌터카|렌트카|rental|hotel/i.test(html);
        if (!isHotel) return [];
        const normalized = html
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/<\/div>/gi, "\n")
            .replace(/<[^>]+>/g, "")
            .replace(/\u00a0/g, " ");
        const lines = normalized.split("\n").map((s) => s.trim()).filter(Boolean);
        const cards = [];
        for (const line of lines) {
            const m = line.match(/^(\d+)[\)\.]\s*(.+)$/);
            if (!m) continue;
            const body = m[2];
            const parts = body.split("|").map((x) => x.trim()).filter(Boolean);
            const name = parts[0];
            if (!name) continue;
            const type = /렌터카|렌트카|rental/i.test(html) ? "렌터카" : "호텔";
            cards.push({
                type,
                name,
                meta: parts.slice(1).join(" | "),
            });
        }
        return cards.slice(0, 8);
    }

    function enhanceCommerceCards(botBubble, rawHtml) {
        const flightCards = parseFlightTableCards(rawHtml);
        const listCards = parseListCards(rawHtml);
        const cards = flightCards.length ? flightCards : listCards;
        if (!cards.length) return;

        const content = botBubble.querySelector(".ai-msg__content");
        if (!content) return;

        const section = document.createElement("section");
        section.className = "ai-commerce-cards";
        const title = cards[0].type === "항공편" ? "항공편 카드" : `${cards[0].type} 카드`;
        section.innerHTML = `<div class="ai-commerce-cards__title">${escapeHtml(title)}</div>`;

        const grid = document.createElement("div");
        grid.className = "ai-commerce-cards__grid";
        cards.forEach((cardData) => {
            const card = document.createElement("article");
            card.className = `ai-commerce-card ${cardData.type === "항공편" ? "ai-commerce-card--flight" : ""}`;

            if (cardData.type === "항공편") {
                const depText = String(cardData.dep || "").trim();
                const arrText = String(cardData.arr || "").trim();
                const depParts = depText.split(/\s+/);
                const arrParts = arrText.split(/\s+/);
                const depTime = depParts[1] || depParts[0] || "-";
                const arrTime = arrParts[1] || arrParts[0] || "-";
                const depDate = depParts.length > 1 ? depParts[0] : "";
                const arrDate = arrParts.length > 1 ? arrParts[0] : "";
                const routeInfo = cardData.routeInfo || "여정 정보";
                const duration = cardData.duration || "-";
                const price = cardData.price || "-";
                const airline = cardData.airline || "항공사";
                const isDirect = /직항/.test(routeInfo);
                const durationLabel = isDirect ? "비행시간" : "총 여정";

                card.innerHTML = `
                    <div class="ai-flight-card__brand">
                        <div class="ai-flight-card__logo">${escapeHtml(airline)}</div>
                        <div class="ai-flight-card__airline">${escapeHtml(airline)}</div>
                    </div>
                    <div class="ai-flight-card__schedule">
                        <div class="ai-flight-card__point">
                            <div class="ai-flight-card__time">${escapeHtml(depTime)}</div>
                            <div class="ai-flight-card__date">${escapeHtml(depDate)}</div>
                            <div class="ai-flight-card__code">출발</div>
                        </div>
                        <div class="ai-flight-card__route">
                            <div class="ai-flight-card__duration-wrap">
                                <span class="ai-flight-card__duration">${escapeHtml(duration)}</span>
                                <span class="ai-flight-card__duration-label">${escapeHtml(durationLabel)}</span>
                            </div>
                            <div class="ai-flight-card__line"></div>
                            <div class="ai-flight-card__routeinfo">${escapeHtml(routeInfoText)}</div>
                        </div>
                        <div class="ai-flight-card__point">
                            <div class="ai-flight-card__time">${escapeHtml(arrTime)}</div>
                            <div class="ai-flight-card__date">${escapeHtml(arrDate)}</div>
                            <div class="ai-flight-card__code">도착</div>
                        </div>
                    </div>
                    <div class="ai-flight-card__fare">
                        <div class="ai-flight-card__fare-label">가격</div>
                        <div class="ai-flight-card__fare-value">${escapeHtml(price)}</div>
                        <button type="button" class="ai-commerce-card__add">장바구니 담기</button>
                    </div>
                `;
            } else {
                card.innerHTML = `
                    <div class="ai-commerce-card__type">${escapeHtml(cardData.type)}</div>
                    <div class="ai-commerce-card__name">${escapeHtml(cardData.name)}</div>
                    ${cardData.meta ? `<div class="ai-commerce-card__meta">${escapeHtml(cardData.meta)}</div>` : ""}
                    <button type="button" class="ai-commerce-card__add">장바구니 담기</button>
                `;
            }
            const addBtn = card.querySelector(".ai-commerce-card__add");
            addBtn?.addEventListener("click", () => {
                const added = addCartItem(cardData);
                if (added) {
                    card.classList.add("is-added");
                    addBtn.textContent = "담김";
                }
                setCartDrawer(true);
            });
            grid.appendChild(card);
        });
        section.appendChild(grid);
        content.appendChild(section);
    }

    async function sendMessage() {
        const message = promptInput.value.trim();
        if (!message) return;

        collapseHeroForChat();
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

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();
            const html = data?.response || "응답을 받지 못했습니다.";
            loadingItem.innerHTML = `
                <div class="ai-msg__meta">DESTINO AI</div>
                <div class="ai-msg__bubble"><div class="ai-msg__content">${html}</div></div>
            `;
            enhanceCommerceCards(loadingItem, html);
            scrollToBottom(true);
        } catch (error) {
            loadingItem.innerHTML = `
                <div class="ai-msg__meta">DESTINO AI</div>
                <div class="ai-msg__bubble ai-msg__bubble--error">요청 중 오류가 발생했습니다.</div>
            `;
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

    renderCart();
    setCartDrawer(false);
});
