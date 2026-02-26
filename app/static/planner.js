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
        const wrap = document.createElement("div");
        wrap.innerHTML = html;
        const metaText = (wrap.textContent || "").replace(/\s+/g, " ");
        const hasReturnDateField = metaText.includes("\uBCF5\uADC0\uC77C:");
        const isRoundTrip = hasReturnDateField && !metaText.includes("\uBCF5\uADC0\uC77C: -");
        const table = wrap.querySelector("table");
        if (!table) return [];
        const cards = [];
        const rows = Array.from(table.querySelectorAll("tr"));
        rows.forEach((tr, idx) => {
            const tds = Array.from(tr.querySelectorAll("td"));
            if (tds.length !== 6) return;
            const cells = tds.map((td) => (td.textContent || "").trim()).filter(Boolean);
            if (cells.length < 6) return;
            const [airline, dep, arr, routeInfo, duration, price] = cells;
            const detailRow = rows[idx + 1];
            const detailDiv = detailRow?.querySelector("details div");
            const segmentDetails = (detailDiv?.textContent || "")
                .replace(/\s+/g, " ")
                .trim();
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
                segmentDetails,
                isRoundTrip,
            });
        });
        return cards.slice(0, 8);
    }

    function formatFlightSegmentDetailsHtml(segmentDetails) {
        const raw = String(segmentDetails || "").trim();
        if (!raw) return "";
        const parts = raw.match(/\d+\)\s[\s\S]*?(?=(?:\s\d+\)\s)|$)/g) || [raw];
        return parts
            .map((p) => {
                const normalized = p
                    .trim()
                    .replace(/\s*\|\s*/g, " · ")
                    .replace(/\s+/g, " ");
                return `<div class="ai-flight-card__segment-line">${escapeHtml(normalized)}</div>`;
            })
            .join("");
    }

    function getAirlineLogoUrlByCode(code) {
        const c = String(code || "").trim().toUpperCase();
        if (!c || c === "-") return "";
        return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(c)}.png`;
    }

    function splitMmddHm(value) {
        const txt = String(value || "").trim();
        const m = txt.match(/(\d{2}-\d{2})\s+(\d{2}:\d{2})/);
        if (m) return { date: m[1], time: m[2] };
        return { date: "", time: txt || "-" };
    }

    function parseFlightSegmentEntries(segmentDetails) {
        const txt = String(segmentDetails || "").trim();
        if (!txt) return [];
        const normalized = txt.replace(/\s+/g, " ");
        const re = /(\d+)\)\s*([A-Z0-9]{2,3})\s*\|\s*([A-Z]{3})\s*(\d{2}-\d{2}\s+\d{2}:\d{2})\s*->\s*([A-Z]{3})\s*(\d{2}-\d{2}\s+\d{2}:\d{2})\s*\|\s*(PT(?:\d+H)?(?:\d+M)?)/g;
        const out = [];
        let m;
        while ((m = re.exec(normalized)) !== null) {
            out.push({
                idx: Number(m[1]),
                airline: m[2],
                depCode: m[3],
                depAt: m[4],
                arrCode: m[5],
                arrAt: m[6],
                duration: m[7],
            });
        }
        return out;
    }

    function parseListCards(rawHtml) {
        const html = String(rawHtml || "");
        const isHotel = /호텔|숙소|렌터카|렌트카|rental|hotel/i.test(html);
        if (!isHotel) return [];
        const distanceBasisSource = html
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/<\/div>/gi, "\n")
            .replace(/<[^>]+>/g, " ")
            .replace(/\u00a0/g, " ");
        const distanceBasisMatch = distanceBasisSource.match(/^\s*거리\s*기준\s*:\s*([^\n]+)$/im);
        const distanceBasis = distanceBasisMatch ? distanceBasisMatch[1].trim() : "";
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
            const fields = {};
            for (const p of parts.slice(1)) {
                const kv = p.match(/^([^:]+):\s*(.+)$/);
                if (!kv) continue;
                fields[kv[1].trim()] = kv[2].trim();
            }
            cards.push({
                type,
                name,
                meta: parts.slice(1).filter((p) => !/^사진\s*:/i.test(p)).join(" | "),
                price: fields["가격"] || "",
                rating: fields["평점"] || "",
                stars: fields["성급"] || "",
                photo: fields["사진"] || "",
                distanceBasis,
            });
        }
        return cards.slice(0, 8);
    }

    function parsePlaceRecommendationCards(rawHtml) {
        const html = String(rawHtml || "");
        if (!/(맛집|명소|놀거리|카페|쇼핑).*(추천)|출처:/i.test(html)) return null;

        const wrap = document.createElement("div");
        wrap.innerHTML = html;
        const rootText = (wrap.textContent || "").replace(/\s+/g, " ").trim();
        if (!rootText) return null;

        const titleNode = wrap.querySelector("b");
        const title = (titleNode?.textContent || "").trim() || "추천";

        const blocks = [];
        // Parse only outer recommendation cards (backend wraps each item with a bordered div).
        // This avoids picking nested title divs again and creating duplicate/empty cards.
        const candidateBlocks = Array.from(wrap.querySelectorAll("div[style*='border-radius']")).filter((el) => {
            const b = el.querySelector("b");
            return b && /^\s*\d+\./.test((b.textContent || "").trim());
        });

        for (const el of candidateBlocks) {
            const nameLine = (el.querySelector("b")?.textContent || "").trim();
            const name = nameLine.replace(/^\s*\d+\.\s*/, "").trim();
            if (!name) continue;

            const imgs = Array.from(el.querySelectorAll("img"))
                .map((img) => img.getAttribute("src") || "")
                .filter(Boolean)
                .slice(0, 3);

            const textLines = Array.from(el.querySelectorAll("div"))
                .map((d) => (d.textContent || "").trim())
                .filter(Boolean)
                .filter((t) => !/^\d+\./.test(t));

            const address = textLines.find((t) => /^주소[:\s]/.test(t)) || "";
            const source = textLines.find((t) => /^출처[:\s]/.test(t)) || "";
            const metaLines = textLines.filter((t) => t !== address && t !== source);
            const summary = metaLines[0] || "";
            const extra = metaLines.slice(1, 3);

            const mapsAnchor = Array.from(el.querySelectorAll("a")).find((a) => /지도|maps/i.test(a.textContent || ""));
            const mapsUrl = mapsAnchor?.getAttribute("href") || "";

            // Skip thin/duplicate parses that only captured the nested title line.
            if (!imgs.length && !summary && !address && !source) continue;

            blocks.push({ name, imgs, summary, extra, address, source, mapsUrl });
        }

        if (!blocks.length) {
            // Fallback: parse plain LLM numbered recommendations like
            // "1. ...", "2. ..." without structured HTML blocks.
            const plain = (wrap.textContent || "")
                .replace(/\r/g, "")
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean);
            const items = [];
            let current = null;
            for (const line of plain) {
                const m = line.match(/^(\d+)\.\s+(.+)$/);
                if (m) {
                    if (current) items.push(current);
                    current = {
                        name: m[2].trim(),
                        imgs: [],
                        summary: "",
                        extra: [],
                        address: "",
                        source: "출처: AI 추천",
                        mapsUrl: "",
                    };
                    continue;
                }
                if (!current) continue;
                if (!current.summary) current.summary = line;
                else current.extra.push(line);
            }
            if (current) items.push(current);
            if (items.length) {
                return {
                    title,
                    subtitle: "추천 후보를 보기 쉽게 정리했어요.",
                    items: items.slice(0, 5),
                };
            }
            return null;
        }

        return {
            title,
            subtitle: "후보별 핵심 정보와 이미지를 보기 쉽게 정리했어요.",
            items: blocks.slice(0, 5),
        };
    }

    function enhancePlaceRecommendationCards(botBubble, rawHtml) {
        const parsed = parsePlaceRecommendationCards(rawHtml);
        if (!parsed) return false;

        const content = botBubble.querySelector(".ai-msg__content");
        if (!content) return false;

        const section = document.createElement("section");
        section.className = "ai-place-reco";

        const itemsHtml = parsed.items.map((item, idx) => {
            const imagesHtml = item.imgs.length
                ? `<div class="ai-place-reco__images">${
                    item.imgs.map((src) => `<img src="${escapeHtml(src)}" alt="${escapeHtml(item.name)}">`).join("")
                }</div>`
                : "";
            const bulletLines = [];
            if (item.summary) bulletLines.push(item.summary);
            item.extra.forEach((t) => bulletLines.push(t));
            if (item.address) bulletLines.push(item.address);
            if (item.source) bulletLines.push(item.source);
            const bulletsHtml = bulletLines.length
                ? `<ul class="ai-place-reco__bullets">${
                    bulletLines.map((t) => `<li>${escapeHtml(t)}</li>`).join("")
                }</ul>`
                : "";
            const actionsHtml = item.mapsUrl
                ? `<div class="ai-place-reco__actions"><a href="${escapeHtml(item.mapsUrl)}" target="_blank" rel="noopener">지도 보기</a></div>`
                : "";
            return `
                <article class="ai-place-reco__card">
                    <div class="ai-place-reco__head">
                        <span class="ai-place-reco__rank">${idx + 1}</span>
                        <h4 class="ai-place-reco__name">${escapeHtml(item.name)}</h4>
                    </div>
                    ${imagesHtml}
                    <div class="ai-place-reco__body">
                        ${bulletsHtml}
                        ${actionsHtml}
                    </div>
                </article>
            `;
        }).join("");

        section.innerHTML = `
            <div class="ai-place-reco__top">
                <div class="ai-place-reco__badge">추천</div>
                <div>
                    <div class="ai-place-reco__title">${escapeHtml(parsed.title)}</div>
                    <div class="ai-place-reco__subtitle">${escapeHtml(parsed.subtitle)}</div>
                </div>
            </div>
            <div class="ai-place-reco__list">${itemsHtml}</div>
        `;

        content.innerHTML = "";
        content.appendChild(section);
        return true;
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
                const airlineCode = String(cardData.airline || "").trim().toUpperCase() || "-";
                const airlineLogoUrl = getAirlineLogoUrlByCode(airlineCode);
                const isRoundTrip = Boolean(cardData.isRoundTrip);
                const isDirect = /직항/.test(routeInfo);
                const durationLabel = isRoundTrip ? "왕복 여정" : (isDirect ? "비행시간" : "총 여정");
                const segs = parseFlightSegmentEntries(cardData.segmentDetails);
                const outSeg = segs[0];
                const inSeg = segs[1];
                const isRoundDirect = Boolean(isRoundTrip && outSeg && inSeg && segs.length === 2);
                const routeInfoLabel = isRoundTrip
                    ? (isRoundDirect ? "출국/귀국 직항" : "왕복 여정")
                    : routeInfo;
                const fareLabel = isRoundTrip ? "왕복 총액" : "가격";

                card.innerHTML = `
                    <div class="ai-flight-card__brand">
                        <div class="ai-flight-card__logo-wrap">
                            ${airlineLogoUrl ? `<img class="ai-flight-card__logo-img" src="${airlineLogoUrl}" alt="${escapeHtml(airlineCode)} 로고" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ""}
                            <div class="ai-flight-card__logo${airlineLogoUrl ? '" style="display:none;' : ''}">${escapeHtml(airlineCode || airline)}</div>
                        </div>
                        <div class="ai-flight-card__airline">${escapeHtml(airlineCode || airline)}</div>
                    </div>
                    ${isRoundTrip && outSeg && inSeg ? (() => {
                        const oDep = splitMmddHm(outSeg.depAt);
                        const oArr = splitMmddHm(outSeg.arrAt);
                        const iDep = splitMmddHm(inSeg.depAt);
                        const iArr = splitMmddHm(inSeg.arrAt);
                        const legBadge = isRoundDirect ? "직항" : "구간 확인";
                        return `
                        <div class="ai-flight-card__schedule ai-flight-card__schedule--round">
                            <div class="ai-flight-card__rt-list">
                                <div class="ai-flight-card__rt-row">
                                    <div class="ai-flight-card__rt-tag">출국</div>
                                    <div class="ai-flight-card__point">
                                    <div class="ai-flight-card__time">${escapeHtml(oDep.time)}</div>
                                    <div class="ai-flight-card__date">${escapeHtml(oDep.date)}</div>
                                    <div class="ai-flight-card__code">${escapeHtml(outSeg.depCode)}</div>
                                    </div>
                                    <div class="ai-flight-card__route ai-flight-card__route--rt">
                                        <div class="ai-flight-card__duration-wrap">
                                        <span class="ai-flight-card__duration">${escapeHtml(outSeg.duration)}</span>
                                        <span class="ai-flight-card__duration-label">&nbsp;</span>
                                        </div>
                                        <div class="ai-flight-card__line"></div>
                                        <div class="ai-flight-card__routeinfo">${escapeHtml(legBadge)}</div>
                                    </div>
                                    <div class="ai-flight-card__point ai-flight-card__point--arr">
                                    <div class="ai-flight-card__time">${escapeHtml(oArr.time)}</div>
                                    <div class="ai-flight-card__date">${escapeHtml(oArr.date)}</div>
                                    <div class="ai-flight-card__code">${escapeHtml(outSeg.arrCode)}</div>
                                    </div>
                                </div>
                                <div class="ai-flight-card__rt-row">
                                    <div class="ai-flight-card__rt-tag">귀국</div>
                                    <div class="ai-flight-card__point">
                                        <div class="ai-flight-card__time">${escapeHtml(iDep.time)}</div>
                                        <div class="ai-flight-card__date">${escapeHtml(iDep.date)}</div>
                                        <div class="ai-flight-card__code">${escapeHtml(inSeg.depCode)}</div>
                                    </div>
                                    <div class="ai-flight-card__route ai-flight-card__route--rt">
                                        <div class="ai-flight-card__duration-wrap">
                                            <span class="ai-flight-card__duration">${escapeHtml(inSeg.duration)}</span>
                                            <span class="ai-flight-card__duration-label">&nbsp;</span>
                                        </div>
                                        <div class="ai-flight-card__line"></div>
                                        <div class="ai-flight-card__routeinfo">${escapeHtml(legBadge)}</div>
                                    </div>
                                    <div class="ai-flight-card__point ai-flight-card__point--arr">
                                        <div class="ai-flight-card__time">${escapeHtml(iArr.time)}</div>
                                        <div class="ai-flight-card__date">${escapeHtml(iArr.date)}</div>
                                        <div class="ai-flight-card__code">${escapeHtml(inSeg.arrCode)}</div>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                    })() : `
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
                            <div class="ai-flight-card__routeinfo">${escapeHtml(routeInfoLabel)}</div>
                        </div>
                        <div class="ai-flight-card__point">
                            <div class="ai-flight-card__time">${escapeHtml(arrTime)}</div>
                            <div class="ai-flight-card__date">${escapeHtml(arrDate)}</div>
                            <div class="ai-flight-card__code">도착</div>
                        </div>
                    </div>`}
                    <div class="ai-flight-card__fare">
                        <div class="ai-flight-card__fare-label">${escapeHtml(fareLabel)}</div>
                        <div class="ai-flight-card__fare-value">${escapeHtml(price)}</div>
                        <button type="button" class="ai-commerce-card__add">장바구니 담기</button>
                    </div>
                `;
            } else if (cardData.type === "호텔") {
                const metaBits = [];
                if (cardData.rating) metaBits.push(`평점 ${cardData.rating}`);
                if (cardData.stars) metaBits.push(`${cardData.stars}성급`);
                const priceText = cardData.price || "";
                card.classList.add("ai-commerce-card--hotel");
                card.innerHTML = `
                    ${cardData.photo ? `<div class="ai-hotel-card__thumb-wrap"><img class="ai-hotel-card__thumb" src="${escapeHtml(cardData.photo)}" alt="${escapeHtml(cardData.name)}" loading="lazy"></div>` : `<div class="ai-hotel-card__thumb-wrap ai-hotel-card__thumb-wrap--placeholder"><div class="ai-hotel-card__thumb-fallback">HOTEL</div></div>`}
                    <div class="ai-hotel-card__body">
                        <div class="ai-commerce-card__type">${escapeHtml(cardData.type)}</div>
                        <div class="ai-commerce-card__name">${escapeHtml(cardData.name)}</div>
                        ${metaBits.length ? `<div class="ai-hotel-card__chips">${metaBits.map((t) => `<span class="ai-hotel-card__chip">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
                    </div>
                    <div class="ai-hotel-card__fare">
                        <div class="ai-flight-card__fare-label">1박 기준가(참고)</div>
                        <div class="ai-hotel-card__price">${escapeHtml(priceText || "-")}</div>
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
        content.innerHTML = "";
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
            const renderedReco = enhancePlaceRecommendationCards(loadingItem, html);
            if (!renderedReco) enhanceCommerceCards(loadingItem, html);
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
