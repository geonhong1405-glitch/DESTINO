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
            <span class="ai-cart-fab__label">장바구니</span>
            <span id="ai-cart-count" class="ai-cart-fab__count" hidden>0</span>
        </button>
        <div id="ai-cart-drawer" class="ai-cart-drawer" aria-hidden="true">
            <div class="ai-cart-drawer__backdrop" data-cart-close></div>
            <section class="ai-cart-drawer__panel">
                <div class="ai-cart-drawer__grab"></div>
                <div class="ai-cart-drawer__header">
                    <div class="ai-cart-tabs" role="tablist" aria-label="저장 항목 탭">
                        <button type="button" class="ai-cart-tab is-active" data-cart-tab="cart" role="tab" aria-selected="true">장바구니</button>
                        <button type="button" class="ai-cart-tab" data-cart-tab="wishlist" role="tab" aria-selected="false">위시리스트</button>
                        <button type="button" class="ai-cart-tab" data-cart-tab="alerts" role="tab" aria-selected="false">알림</button>
                    </div>
                    <button type="button" class="ai-cart-drawer__close" data-cart-close>닫기</button>
                </div>
                <ul id="ai-cart-list" class="ai-cart-list"></ul>
                <div id="ai-cart-empty" class="ai-cart-empty">저장된 항목이 없습니다.</div>
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
    const cartTabs = Array.from(shell.querySelectorAll("[data-cart-tab]"));
    chatBox.style.scrollBehavior = "smooth";

    const sessionKey = "flight_chat_session_id";
    let sessionId = sessionStorage.getItem(sessionKey);
    if (!sessionId) {
        sessionId = globalThis.crypto?.randomUUID?.() || String(Date.now());
        sessionStorage.setItem(sessionKey, sessionId);
    }
    let cartTab = "cart";
    let savedItems = { cart: [], wishlist: [] };
    let alertItems = [];

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

    function isIsoDateString(value) {
        const v = String(value || "").trim();
        if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false;
        const d = new Date(`${v}T00:00:00`);
        return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v;
    }

    function addDaysIso(value, days) {
        const d = new Date(`${String(value || "").trim()}T00:00:00`);
        if (Number.isNaN(d.getTime())) return "";
        d.setDate(d.getDate() + Number(days || 0));
        return d.toISOString().slice(0, 10);
    }

    function resolveHotelStayDates(cardData) {
        let checkin = String(cardData?.checkin || "").trim();
        let checkout = String(cardData?.checkout || "").trim();
        const meta = String(cardData?.meta || "");
        const dates = meta.match(/\b20\d{2}-\d{2}-\d{2}\b/g) || [];

        if (!isIsoDateString(checkin) && dates[0]) checkin = dates[0];
        if (!isIsoDateString(checkout) && dates[1]) checkout = dates[1];

        if (!isIsoDateString(checkin) && isIsoDateString(checkout)) checkin = addDaysIso(checkout, -1);
        if (!isIsoDateString(checkout) && isIsoDateString(checkin)) checkout = addDaysIso(checkin, 1);

        if (!isIsoDateString(checkin) || !isIsoDateString(checkout)) {
            const today = new Date();
            const inDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
            const outDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 2);
            checkin = isIsoDateString(checkin) ? checkin : inDate.toISOString().slice(0, 10);
            checkout = isIsoDateString(checkout) ? checkout : outDate.toISOString().slice(0, 10);
        }

        if (checkout <= checkin) checkout = addDaysIso(checkin, 1);
        return { checkin, checkout };
    }

    const hotelPhotoCache = new Map();

    function looksLikeHotelName(text) {
        const t = String(text || "").toLowerCase();
        if (!t) return false;
        return /(호텔|숙소|hotel|inn|ryokan|resort|hostel|guesthouse|mystays|toyoko|apa|hilton|marriott|hyatt|sheraton)/i.test(t);
    }

    function looksLikeHotelCard(cardData) {
        const name = String(cardData?.name || "");
        const meta = String(cardData?.meta || "");
        const hasHotelField = Boolean(
            String(cardData?.hotel_id || "").trim() ||
            String(cardData?.checkin || "").trim() ||
            String(cardData?.checkout || "").trim() ||
            String(cardData?.address || "").trim() ||
            String(cardData?.area || "").trim() ||
            String(cardData?.stars || "").trim() ||
            String(cardData?.distance || "").trim()
        );
        const hasHotelMeta = /(거리\s*[:：]|등급\s*[:：]|성급\s*[:：]|체크인\s*[:：]|체크아웃\s*[:：])/i.test(meta);
        return hasHotelField || hasHotelMeta || looksLikeHotelName(name);
    }

    async function fetchHotelPhotoFromApi(name, address) {
        const nm = String(name || "").trim();
        const addr = String(address || "").trim();
        const key = `${nm}||${addr}`;
        if (!nm) return "";
        if (hotelPhotoCache.has(key)) return hotelPhotoCache.get(key) || "";
        try {
            const qs = new URLSearchParams({ name: nm });
            if (addr) qs.set("address", addr);
            const resp = await fetch(`/api/hotel/photo?${qs.toString()}`);
            const data = await resp.json().catch(() => ({}));
            const photo = String(data?.photo_url || "").trim();
            hotelPhotoCache.set(key, photo);
            return photo;
        } catch (_) {
            hotelPhotoCache.set(key, "");
            return "";
        }
    }

    async function hydrateHotelCardPhoto(card, cardData) {
        if (!card || !cardData) return;
        if (String(cardData.photo || "").trim()) return;
        const wrap = card.querySelector(".ai-hotel-card__thumb-wrap");
        if (!wrap) return;
        const address = String(cardData.address || cardData.area || cardData.name || "").trim();
        const photoUrl = await fetchHotelPhotoFromApi(cardData.name, address);
        if (!photoUrl) return;
        cardData.photo = photoUrl;
        wrap.classList.remove("ai-hotel-card__thumb-wrap--placeholder");
        wrap.innerHTML = `<img class="ai-hotel-card__thumb" src="${escapeHtml(photoUrl)}" alt="${escapeHtml(cardData.name || "Hotel")}" loading="lazy" onerror="this.onerror=null; const w=this.closest('.ai-hotel-card__thumb-wrap'); if(w){w.classList.add('ai-hotel-card__thumb-wrap--placeholder'); w.innerHTML='<div class=\\'ai-hotel-card__thumb-fallback\\'>HOTEL</div>'; }">`;
    }

    const SAVED_COUNTRY_IMAGE = {
        japan: "https://images.unsplash.com/photo-1492571350019-22de08371fd3?auto=format&fit=crop&w=400&q=80",
        vietnam: "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=400&q=80",
        thailand: "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=400&q=80",
        france: "https://images.unsplash.com/photo-1499856871958-5b9357976b82?auto=format&fit=crop&w=400&q=80",
        usa: "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=400&q=80",
        italy: "https://images.unsplash.com/photo-1529260830199-42c24126f198?auto=format&fit=crop&w=400&q=80",
        spain: "https://images.unsplash.com/photo-1543783207-ec64e4d95325?auto=format&fit=crop&w=400&q=80",
        uk: "https://images.unsplash.com/photo-1486299267070-83823f5448dd?auto=format&fit=crop&w=400&q=80",
        default: "https://images.unsplash.com/photo-1488085061387-422e29b40080?auto=format&fit=crop&w=400&q=80",
    };
    const FLIGHT_AIRLINE_EN = {
        KE: "KOREAN AIR",
        OZ: "ASIANA AIR",
        TW: "TWAY AIR",
        "7C": "JEJU AIR",
        BX: "AIR BUSAN",
        LJ: "JINAIR",
        RS: "AIR SEOUL",
        ZE: "EASTAR JET",
        AC: "AIR CANADA",
        JL: "JAPAN AIRLINES",
        NH: "ANA",
    };
    const RENTAL_FALLBACK_IMAGES = {
        suv: [
            "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=800&q=80",
        ],
        van: [
            "https://images.unsplash.com/photo-1502877338535-766e1452684a?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1549399542-7e8f2e9380f6?auto=format&fit=crop&w=800&q=80",
        ],
        sedan: [
            "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1549924231-f129b911e442?auto=format&fit=crop&w=800&q=80",
        ],
        default: [
            "https://images.unsplash.com/photo-1493238792000-8113da705763?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?auto=format&fit=crop&w=800&q=80",
        ],
    };
    const TOUR_PAGE_IMAGE_FALLBACK = {
        disney: "https://cdn.pixabay.com/photo/2017/04/30/13/36/disneyland-paris-2272907_1280.jpg",
        skytree: "https://media.istockphoto.com/id/1194071526/ko/%EC%82%AC%EC%A7%84/%EC%9D%BC%EB%B3%B8-%EC%86%8C%EB%85%80%EB%8A%94-%EA%B2%A8%EC%9A%B8%EC%B2%A0%EC%97%90-%EC%A0%84%ED%86%B5-%EA%B8%B0%EB%AA%A8%EB%85%B8-%EB%93%9C%EB%A0%88%EC%8A%A4%EB%A5%BC-%EC%9E%85%EA%B3%A0-%EA%B1%B7%EA%B3%A0-%EA%B5%90%ED%86%A0%EC%8B%9C%EC%9D%98-%EB%88%88%EC%9D%84-%EB%B3%B4%ED%98%B8%ED%95%98%EA%B8%B0-%EC%9C%84%ED%95%B4-%EC%9A%B0%EC%82%B0%EC%9D%84-%EC%82%AC%EC%9A%A9%ED%95%A9%EB%8B%88%EB%8B%A4.jpg?b=1&s=1024x1024&w=0&k=20&c=IfqDhqA2K88H3WwAMSEg0xTAysz27ffoELdX2gLLf48=",
        usj: "https://cdn.pixabay.com/photo/2016/12/18/03/12/usj-1914942_1280.jpg",
        ny: "https://cdn.pixabay.com/photo/2015/08/05/12/38/prague-castle-876467_1280.jpg",
        liberty: "https://cdn.pixabay.com/photo/2020/08/12/11/16/norway-5482384_1280.jpg",
    };

    function savedTypeLabel(itemType) {
        const type = String(itemType || "").toLowerCase();
        if (type === "flight") return "항공";
        if (type === "hotel" || type === "stay" || type === "accommodation") return "숙박";
        if (type === "groupbuy" || type === "travel-group") return "공동구매";
        return type ? type.toUpperCase() : "ITEM";
    }

    function savedCountryKey(country) {
        const c = String(country || "").toLowerCase();
        if (c.includes("일본") || c.includes("japan")) return "japan";
        if (c.includes("베트남") || c.includes("vietnam")) return "vietnam";
        if (c.includes("태국") || c.includes("thailand")) return "thailand";
        if (c.includes("프랑스") || c.includes("france")) return "france";
        if (c.includes("미국") || c.includes("usa") || c.includes("united states")) return "usa";
        if (c.includes("이탈리아") || c.includes("italy")) return "italy";
        if (c.includes("스페인") || c.includes("spain")) return "spain";
        if (c.includes("영국") || c.includes("uk") || c.includes("united kingdom")) return "uk";
        return "default";
    }

    function savedAirlineLogo(code) {
        if (!code) return "";
        return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(String(code).toUpperCase())}.png`;
    }

    function savedImageUrl(item) {
        const payload = item?.payload || {};
        const type = String(item?.item_type || item?.type || "").toLowerCase();
        if (type === "flight") {
            return payload?.thumb_url || payload?.image_url || payload?.image || savedAirlineLogo(payload?.airline_code || payload?.airline || "");
        }
        const direct =
            payload?.thumb_url ||
            payload?.image_url ||
            payload?.image ||
            payload?.thumbnail ||
            payload?.photo ||
            item?.image_url ||
            item?.image ||
            (Array.isArray(payload?.images) ? payload.images[0] : "");
        if (direct) return direct;
        if (type === "groupbuy" || type === "travel-group") {
            return SAVED_COUNTRY_IMAGE[savedCountryKey(payload?.country)] || SAVED_COUNTRY_IMAGE.default;
        }
        return "";
    }

    function looksLikeLogoImage(url) {
        const u = String(url || "").toLowerCase();
        if (!u) return false;
        return [
            "logo",
            "vendor",
            "supplier",
            "brand",
            "icon",
            "64x64",
            "128x128",
            "airlines/",
        ].some((k) => u.includes(k));
    }

    function normalizeRentalPhotoUrl(url) {
        const u = String(url || "").trim();
        if (!u) return "";
        return looksLikeLogoImage(u) ? "" : u;
    }

    function productFallbackImageFromTour(name, type) {
        const n = String(name || "").toLowerCase();
        const t = String(type || "").toLowerCase();
        if (!(t.includes("티켓") || t.includes("ticket"))) return "";
        if (n.includes("디즈니")) return TOUR_PAGE_IMAGE_FALLBACK.disney;
        if (n.includes("스카이트리") || n.includes("skytree")) return TOUR_PAGE_IMAGE_FALLBACK.skytree;
        if (n.includes("유니버셜") || n.includes("universal") || n.includes("usj")) return TOUR_PAGE_IMAGE_FALLBACK.usj;
        if (n.includes("자유의 여신상") || n.includes("liberty")) return TOUR_PAGE_IMAGE_FALLBACK.liberty;
        if (n.includes("타임스퀘어") || n.includes("times square") || n.includes("뉴욕")) return TOUR_PAGE_IMAGE_FALLBACK.ny;
        return "";
    }

    function normalizeRentalName(name, supplier) {
        const n = String(name || "").trim();
        const s = String(supplier || "").trim();
        if (!n) return "차종 정보 없음";
        const nl = n.toLowerCase();
        if (["rental car", "rental", "렌터카", "렌터카 옵션", "car"].includes(nl)) return "차종 정보 없음";
        if (/렌터카$|rental car$| rental$/i.test(nl)) {
            const core = nl.replace(/렌터카$|rental car$| rental$/i, "").trim();
            if (!core || (s && core === s.toLowerCase())) return "차종 정보 없음";
        }
        return n;
    }

    function formatRentalRating(rating) {
        const n = Number(rating);
        if (!Number.isFinite(n)) return "";
        return n.toFixed(1);
    }

    function summarizeRentalSpecs(specsText) {
        const raw = String(specsText || "");
        if (!raw) return "옵션 정보 없음";
        const tokens = raw
            .split(/[|·,/]/)
            .map((s) => s.trim())
            .filter(Boolean);
        const out = [];
        for (const t of tokens) {
            const l = t.toLowerCase();
            const seatM = t.match(/(\d+)\s*(?:인승|seats?|pax|명)/i);
            if (seatM) {
                out.push(`${seatM[1]}인승`);
                continue;
            }
            const bagM = t.match(/(\d+)\s*(?:bags?|bag|가방)/i);
            if (bagM) {
                out.push(`가방 ${bagM[1]}`);
                continue;
            }
            if (/automatic|auto|오토/i.test(l)) {
                out.push("자동");
                continue;
            }
            if (/manual|수동/i.test(l)) {
                out.push("수동");
                continue;
            }
            if (/air.?con|a\/c|에어컨/i.test(l)) {
                out.push("에어컨");
                continue;
            }
            if (/full[_\-\s]?to[_\-\s]?full|만땅|연료/i.test(l)) {
                out.push("연료 정책");
                continue;
            }
        }
        const uniq = Array.from(new Set(out));
        return uniq.length ? uniq.slice(0, 4).join(" · ") : "옵션 정보 없음";
    }

    function savedMetaParts(item) {
        const raw = String(item?.meta || "").trim();
        const parts = raw.split("|").map((x) => x.trim()).filter(Boolean);
        const detectedPrice = parts.find((p) => normalizeSavedPrice(p));
        const price = normalizeSavedPrice(detectedPrice || "");
        return {
            price,
            lines: parts
                .filter((p) => p && p !== detectedPrice && !normalizeSavedPrice(p))
                .slice(0, 3),
        };
    }

    function parseSavedFlightMeta(item) {
        const payload = (item && typeof item.payload === "object") ? item.payload : {};
        const rawMeta = String(item?.meta || payload?.meta || "").trim();
        const parts = rawMeta ? rawMeta.split("|").map((x) => x.trim()).filter(Boolean) : [];

        const looksLikePrice = (text) => /\d/.test(String(text || "")) && /(krw|usd|eur|jpy|원|₩|\$|€|¥)/i.test(String(text || ""));
        const price = normalizeSavedPrice(looksLikePrice(parts[0]) ? parts[0] : (String(payload?.price || "").trim() || ""));
        const itineraries = Array.isArray(payload?.itineraries) ? payload.itineraries : [];
        const outItinerary = itineraries[0] || {};
        const inItinerary = itineraries[1] || {};
        const outSegments = Array.isArray(outItinerary?.segments) ? outItinerary.segments : [];
        const inSegments = Array.isArray(inItinerary?.segments) ? inItinerary.segments : [];
        const outFirstSeg = outSegments[0] || null;
        const outLastSeg = outSegments[outSegments.length - 1] || null;
        const inFirstSeg = inSegments[0] || null;
        const inLastSeg = inSegments[inSegments.length - 1] || null;
        const segs = parseFlightSegmentEntries(payload?.segmentDetails || "");
        const legSummaries = summarizeLegs(segs);
        const outLeg = legSummaries[0] || null;
        const inLeg = legSummaries[1] || null;
        const dep = normalizeSavedDateTime(String(
            payload?.outboundDep ||
            outFirstSeg?.departure?.at ||
            outLeg?.depAt ||
            payload?.dep ||
            ""
        ).trim());
        const arr = normalizeSavedDateTime(String(
            payload?.outboundArr ||
            outLastSeg?.arrival?.at ||
            outLeg?.arrAt ||
            payload?.arr ||
            ""
        ).trim());
        const route = String(
            payload?.outboundRoute ||
            (outFirstSeg?.departure?.iataCode && outLastSeg?.arrival?.iataCode
                ? `${outFirstSeg.departure.iataCode} → ${outLastSeg.arrival.iataCode}`
                : "") ||
            outLeg?.routeText ||
            payload?.routeInfo ||
            ""
        ).trim();
        const retDep = normalizeSavedDateTime(String(
            payload?.returnDep ||
            inFirstSeg?.departure?.at ||
            inLeg?.depAt ||
            ""
        ).trim());
        const retArr = normalizeSavedDateTime(String(
            payload?.returnArr ||
            inLastSeg?.arrival?.at ||
            inLeg?.arrAt ||
            ""
        ).trim());
        const retRoute = String(
            payload?.returnRoute ||
            (inFirstSeg?.departure?.iataCode && inLastSeg?.arrival?.iataCode
                ? `${inFirstSeg.departure.iataCode} → ${inLastSeg.arrival.iataCode}`
                : "") ||
            inLeg?.routeText ||
            ""
        ).trim();
        const isRound = Boolean(payload?.isRoundTrip || inSegments.length || inLeg || (retDep && retArr));
        const name = String(item?.name || payload?.name || "-").trim();
        const airlineCode = String(payload?.airline_code || outFirstSeg?.carrierCode || "").trim().toUpperCase();
        const depCode = String(payload?.dep_code || outFirstSeg?.departure?.iataCode || "").trim().toUpperCase();
        const arrCode = String(payload?.arr_code || outLastSeg?.arrival?.iataCode || "").trim().toUpperCase();
        const airlineName = String(payload?.airline_name || FLIGHT_AIRLINE_EN[airlineCode] || airlineCode || "").trim();
        const routeTitle = (depCode && arrCode) ? `${depCode} -> ${arrCode}` : "";
        const displayTitle = airlineName && routeTitle ? `${airlineName} ${routeTitle}` : (routeTitle || name);

        return {
            name,
            displayTitle,
            price,
            dep,
            arr,
            route,
            retDep,
            retArr,
            retRoute,
            isRound,
            airlineCode,
            airlineName,
        };
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

    async function savedItemsApi(path = "/api/saved-items", options = {}) {
        const res = await fetch(path, {
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {}),
            },
            ...options,
        });
        let data = null;
        try { data = await res.json(); } catch (_e) {}
        if (res.status === 401) {
            const err = new Error("로그인이 필요합니다.");
            err.code = "LOGIN_REQUIRED";
            throw err;
        }
        if (!res.ok) {
            const err = new Error((data && (data.detail || data.error)) || `HTTP ${res.status}`);
            err.code = "API_ERROR";
            throw err;
        }
        return data;
    }

    function savedKey(item) {
        return `${String(item?.item_type || item?.type || "").toLowerCase()}__${String(item?.name || "").toLowerCase()}__${String(item?.meta || "").toLowerCase()}`;
    }

    function promptLoginForSavedItems() {
        if (confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")) {
            location.href = "/login";
        }
    }

    async function ensureLoggedInForChat() {
        try {
            const res = await fetch("/api/me", { credentials: "same-origin", cache: "no-store" });
            if (!res.ok) {
                return false;
            }
            const data = await res.json().catch(() => ({}));
            return !!(data && data.ok && data.user);
        } catch (_e) {
            return false;
        }
    }

    function promptLoginForChat() {
        if (confirm("채팅은 로그인 후 이용 가능합니다. 로그인 페이지로 이동할까요?")) {
            const next = encodeURIComponent(location.pathname + location.search + location.hash);
            location.href = `/login?next=${next}`;
        }
    }

    function promptChatPassPurchase(code) {
        const reasonMap = {
            NO_PASS: "챗봇 이용권이 없습니다. 이용권 구매 페이지로 이동할까요?",
            PASS_EXPIRED: "이용권이 만료되었습니다. 새 이용권을 구매할까요?",
            PASS_EXHAUSTED: "이용권 사용 횟수를 모두 소진했습니다. 새 이용권을 구매할까요?",
            PASS_REQUIRED: "챗봇 이용권이 필요합니다. 구매 페이지로 이동할까요?",
        };
        const msg = reasonMap[String(code || "PASS_REQUIRED")] || reasonMap.PASS_REQUIRED;
        if (confirm(msg)) {
            const next = encodeURIComponent(location.pathname + location.search + location.hash);
            location.href = `/chat-pass/purchase?next=${next}`;
        }
    }

    async function refreshSavedItems() {
        try {
            const data = await savedItemsApi("/api/saved-items", { method: "GET", headers: {} });
            savedItems = {
                cart: Array.isArray(data?.cart) ? data.cart : [],
                wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
            };
        } catch (e) {
            if (e?.code !== "LOGIN_REQUIRED") {
                console.warn("saved-items refresh failed", e);
            }
            savedItems = { cart: [], wishlist: [] };
        }
        renderCart();
    }

    async function refreshAlertItems() {
        try {
            const res = await fetch("/api/group-buy/join-requests/inbox", { credentials: "same-origin" });
            if (res.status === 401) {
                alertItems = [];
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            alertItems = Array.isArray(data) ? data : [];
        } catch (_e) {
            alertItems = [];
        }
    }

    async function decideAlertItem(requestId, action) {
        const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}/decision`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action }),
        });
        if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d?.detail || `HTTP ${res.status}`);
        }
    }

    function setCartDrawer(open) {
        if (!cartDrawer || !cartFab) return;
        cartDrawer.classList.toggle("is-open", !!open);
        cartDrawer.setAttribute("aria-hidden", open ? "false" : "true");
        cartFab.setAttribute("aria-expanded", open ? "true" : "false");
        // 버튼에 is-open 클래스 토글 (배경 이미지 변경)
        cartFab.classList.toggle("is-open", !!open);
    }

    function renderCart() {
        if (!cartList || !cartEmpty) return;
        // 탭 디자인 토글은 항상 실행
        cartTabs.forEach((btn) => {
            const active = btn.getAttribute("data-cart-tab") === cartTab;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-selected", active ? "true" : "false");
        });

        if (cartTab === "alerts") {
            cartList.innerHTML = "";
            cartEmpty.style.display = alertItems.length ? "none" : "block";
            cartEmpty.textContent = "도착한 참여 요청 알림이 없습니다.";
            alertItems.forEach((item) => {
                const status = String(item.status || "pending");
                const statusLabel = status === "accepted" ? "수락됨" : (status === "rejected" ? "거절됨" : "대기중");
                const incoming = String(item.direction || "incoming") !== "mine";
                const reqTitle = incoming
                    ? `${escapeHtml(item.requester_name || "-")}님이 요청했습니다`
                    : `${escapeHtml(item.requester_name || "작성자")}님의 응답`;
                const statusClass = status === "accepted" ? "is-accepted" : (status === "rejected" ? "is-rejected" : "is-pending");
                const li = document.createElement("li");
                li.className = "ai-cart-item saved-alert-card";
                li.setAttribute("data-alert-id", String(Number(item.id)));
                li.innerHTML = `
                    <div class="ai-cart-item__content">
                        <div class="ai-cart-item__type">공동구매 · 참여요청</div>
                        <div class="ai-cart-item__name">${escapeHtml(item.post_title || "-")}</div>
                        <div class="ai-cart-item__line">${reqTitle}</div>
                        ${item.requester_email ? `<div class="ai-cart-item__line">이메일: ${escapeHtml(item.requester_email || "")}</div>` : ""}
                        <div class="ai-cart-item__line"><span class="saved-alert-status ${statusClass}">${statusLabel}</span></div>
                        ${item.message ? `<div class="ai-cart-item__line">${escapeHtml(item.message || "")}</div>` : ""}
                        ${
                            incoming && status === "pending"
                                ? `<div class="saved-alert-actions">
                                    <button type="button" data-alert-action="accept" data-alert-id="${Number(item.id)}" class="saved-alert-btn">수락</button>
                                    <button type="button" data-alert-action="reject" data-alert-id="${Number(item.id)}" class="saved-alert-btn is-reject">거절</button>
                                </div>`
                                  : ""
                          }
                      </div>
                      <button type="button" class="ai-cart-item__remove" data-alert-remove="${Number(item.id)}" title="삭제" aria-label="삭제">×</button>
                  `;
                cartList.appendChild(li);
            });
            return;
        }

        const items = Array.isArray(savedItems[cartTab]) ? savedItems[cartTab] : [];
        cartList.innerHTML = "";
        cartEmpty.style.display = items.length ? "none" : "block";
        cartEmpty.textContent = cartTab === "wishlist" ? "위시리스트 항목이 없습니다." : "장바구니 항목이 없습니다.";
        if (cartCount) {
            const totalCount = (savedItems.cart?.length || 0) + (savedItems.wishlist?.length || 0) + (alertItems?.length || 0);
            cartCount.hidden = false; // 항상 표시
            cartCount.textContent = String(totalCount || 0);
        }
        items.forEach((item) => {
            const li = document.createElement("li");
            li.className = "ai-cart-item";
            const imageUrl = savedImageUrl(item);
            const meta = savedMetaParts(item);
            const itemTypeRaw = String(item?.item_type || item?.type || item?.payload?.item_type || "").toLowerCase();
            const isFlightItem = itemTypeRaw === "flight" || itemTypeRaw === "항공편";
            const kind = `${savedTypeLabel(item.item_type || item.type || item?.payload?.item_type)} · ${item.source || "saved-item"}`;
            const lines = (meta.lines || []).map((line) => `<div class="ai-cart-item__line">${escapeHtml(line)}</div>`).join("");
            let priceHtml = meta.price ? `<div class="ai-cart-item__line ai-cart-item__price">${escapeHtml(meta.price)}</div>` : "";
            let extraHtml = "";
            if (isFlightItem) {
                const f = parseSavedFlightMeta(item);
                const depLine = f.dep ? `<div class=\"ai-cart-item__line\">출발 ${escapeHtml(f.dep)}</div>` : "";
                const arrLine = f.arr ? `<div class=\"ai-cart-item__line\">도착 ${escapeHtml(f.arr)}</div>` : "";
                priceHtml = f.price ? `<div class=\"ai-cart-item__line ai-cart-item__price\">${escapeHtml(f.price)}</div>` : priceHtml;
                extraHtml = `${depLine}${arrLine}`;
            }
            li.innerHTML = `
                <div class="ai-cart-item__thumb">
                    ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(item.name || "")}" loading="lazy" onerror="this.remove()">` : ""}
                </div>
                <div class="ai-cart-item__content">
                    <div class="ai-cart-item__type">${escapeHtml(kind)}</div>
                    <div class="ai-cart-item__name">${escapeHtml(item.name || "-")}</div>
                    ${priceHtml}
                    ${lines}
                    ${extraHtml}
                </div>
                <button type="button" class="ai-cart-item__remove" data-cart-remove="${item.id}" title="삭제">×</button>
            `;
            cartList.appendChild(li);
        });
        syncCommerceCardStates();
    }

    function hasSavedItem(listType, item) {
        return (savedItems[listType] || []).some((x) => savedKey(x) === savedKey(item));
    }

    function syncCommerceCardStates() {
        const cards = Array.from(shell.querySelectorAll(".ai-commerce-card"));
        cards.forEach((card) => {
            const item = card.__savedItemData;
            if (!item) return;
            const inCart = hasSavedItem("cart", item);
            const inWishlist = hasSavedItem("wishlist", item);
            const addBtn = card.querySelector(".ai-commerce-card__add");
            const wishBtn = card.querySelector(".ai-commerce-card__wish");
            if (addBtn) {
                addBtn.textContent = inCart ? "담김" : "장바구니";
                addBtn.classList.toggle("is-active", inCart);
            }
            if (wishBtn) {
                wishBtn.textContent = inWishlist ? "♥" : "♡";
                wishBtn.classList.toggle("is-active", inWishlist);
                wishBtn.setAttribute("aria-pressed", inWishlist ? "true" : "false");
                wishBtn.setAttribute("title", inWishlist ? "위시리스트에 저장됨" : "위시리스트 저장");
            }
            card.classList.toggle("is-added", inCart || inWishlist);
        });
    }

    async function addSavedItem(listType, item) {
        const savePayload = {
            list_type: listType,
            item_type: item.item_type || item.type || "item",
            name: item.name || "-",
            meta: item.meta || "",
            source: "planner-chat",
            payload: item,
        };
        try {
            const resp = await savedItemsApi("/api/saved-items", {
                method: "POST",
                body: JSON.stringify(savePayload),
            });
            const row = resp?.item;
            if (row) {
                const exists = (savedItems[listType] || []).some((x) => savedKey(x) === savedKey(row));
                if (!exists) savedItems[listType].unshift(row);
            } else {
                await refreshSavedItems();
            }
            renderCart();
            return !!resp?.created;
        } catch (e) {
            if (e?.code === "LOGIN_REQUIRED") {
                promptLoginForSavedItems();
                return false;
            }
            const label = listType === "wishlist" ? "위시리스트" : "장바구니";
            alert(e?.message || `${label} 저장 중 오류가 발생했습니다.`);
            return false;
        }
    }

    cartFab?.addEventListener("click", () => {
        setCartDrawer(!cartDrawer?.classList.contains("is-open"));
        if (cartDrawer?.classList.contains("is-open")) {
            refreshAlertItems().then(renderCart);
        }
    });
    shell.querySelectorAll("[data-cart-close]").forEach((el) => el.addEventListener("click", () => setCartDrawer(false)));
    cartTabs.forEach((btn) => btn.addEventListener("click", () => {
        cartTab = btn.getAttribute("data-cart-tab") || "cart";
        if (cartTab === "alerts") {
            refreshAlertItems().then(renderCart);
            return;
        }
        renderCart();
    }));
    cartList?.addEventListener("click", (e) => {
        const alertBtn = e.target.closest("[data-alert-action]");
        if (alertBtn) {
            const requestId = Number(alertBtn.getAttribute("data-alert-id"));
            const action = String(alertBtn.getAttribute("data-alert-action") || "");
            if (!requestId || !action) return;
            (async () => {
                try {
                    await decideAlertItem(requestId, action);
                    await refreshAlertItems();
                    renderCart();
                } catch (err) {
                    alert(err?.message || "요청 처리 중 오류가 발생했습니다.");
                }
            })();
            return;
        }
        const alertRemoveBtn = e.target.closest("[data-alert-remove]");
        if (alertRemoveBtn) {
            const requestId = Number(alertRemoveBtn.getAttribute("data-alert-remove"));
            if (!requestId) return;
            (async () => {
                try {
                    const res = await fetch(`/api/group-buy/join-requests/${requestId}`, { method: "DELETE", credentials: "same-origin" });
                    if (!res.ok) {
                        const d = await res.json().catch(() => ({}));
                        throw new Error(d?.detail || `HTTP ${res.status}`);
                    }
                    await refreshAlertItems();
                    renderCart();
                } catch (err) {
                    alert(err?.message || "알림 삭제 중 오류가 발생했습니다.");
                }
            })();
            return;
        }
        const btn = e.target.closest("[data-cart-remove]");
        if (!btn) return;
        const itemId = Number(btn.getAttribute("data-cart-remove"));
        if (Number.isNaN(itemId)) return;
        (async () => {
            try {
                await savedItemsApi(`/api/saved-items/${itemId}`, { method: "DELETE", headers: {} });
                savedItems[cartTab] = (savedItems[cartTab] || []).filter((x) => Number(x.id) !== itemId);
                renderCart();
            } catch (err) {
                if (err?.code === "LOGIN_REQUIRED") {
                    promptLoginForSavedItems();
                    return;
                }
                alert(err?.message || "삭제 중 오류가 발생했습니다.");
            }
        })();
    });
    refreshSavedItems();
    refreshAlertItems().then(renderCart);

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
        const seen = new Set();
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
            const segs = parseFlightSegmentEntries(segmentDetails);
            const legSummaries = summarizeLegs(segs);
            const outLeg = legSummaries[0] || null;
            const inLeg = legSummaries[1] || null;
            const outboundDep = outLeg?.depAt || dep || "";
            const outboundArr = outLeg?.arrAt || arr || "";
            const outboundRoute = outLeg?.routeText || routeInfo || "";
            const returnDep = inLeg?.depAt || "";
            const returnArr = inLeg?.arrAt || "";
            const returnRoute = inLeg?.routeText || "";
            const inferredRoundTrip = Boolean(isRoundTrip || inLeg);
            const depArrCodes = extractRouteCodesFromSegments(segmentDetails);
            const depCode = String(outLeg?.depCode || depArrCodes.dep || "").toUpperCase();
            const arrCode = String(outLeg?.arrCode || depArrCodes.arr || "").toUpperCase();
            const airlineCode = String(airline || "").trim().toUpperCase();
            const airlineName = FLIGHT_AIRLINE_EN[airlineCode] || airlineCode || "FLIGHT";
            const routeTitle = (depCode && arrCode) ? `${depCode} -> ${arrCode}` : String(outboundRoute || "").replace(/→/g, "->");
            const card = {
                type: "항공편",
                item_type: "flight",
                name: `${airlineName} ${routeTitle}`.trim(),
                meta: [
                    normalizeSavedPrice(price || ""),
                    outboundDep ? `출발 ${normalizeSavedDateTime(outboundDep)}` : "",
                    outboundArr ? `도착 ${normalizeSavedDateTime(outboundArr)}` : "",
                    outboundRoute || "",
                    inferredRoundTrip && returnDep ? `오는편 출발 ${normalizeSavedDateTime(returnDep)}` : "",
                    inferredRoundTrip && returnArr ? `오는편 도착 ${normalizeSavedDateTime(returnArr)}` : "",
                    inferredRoundTrip && returnRoute ? returnRoute : "",
                    duration ? `소요 ${duration}` : "",
                ]
                    .filter(Boolean)
                    .join(" | "),
                airline,
                airline_code: airlineCode,
                airline_name: airlineName,
                dep_code: depCode,
                arr_code: arrCode,
                dep: outboundDep || dep,
                arr: outboundArr || arr,
                routeInfo,
                duration,
                price: normalizeSavedPrice(price || ""),
                segmentDetails,
                isRoundTrip: inferredRoundTrip,
                outboundDep,
                outboundArr,
                outboundRoute,
                returnDep,
                returnArr,
                returnRoute,
            };
            const dedupeKey = [
                card.airline,
                card.dep,
                card.arr,
                card.routeInfo,
                card.duration,
                card.price,
                card.segmentDetails,
            ].join("||");
            if (seen.has(dedupeKey)) return;
            seen.add(dedupeKey);
            cards.push(card);
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

    function normalizeSavedDateTime(value) {
        const txt = String(value || "").trim();
        if (!txt) return "";
        const iso = txt.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})(?::\d{2})?/);
        if (iso) return `${iso[1]} ${iso[2]}:00`;
        const mdhm = txt.match(/^(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/);
        if (mdhm) {
            const y = new Date().getFullYear();
            return `${y}-${mdhm[1]}-${mdhm[2]} ${mdhm[3]}:${mdhm[4]}:00`;
        }
        return txt;
    }

    function normalizeSavedPrice(value) {
        const txt = String(value || "").trim();
        if (!txt) return "";
        const m = txt.match(/([\d,]+(?:\.\d+)?)\s*(KRW|krw|원|₩)?/);
        if (!m) return "";
        const n = Number(String(m[1]).replace(/,/g, ""));
        if (!Number.isFinite(n) || n <= 0) return "";
        return `₩${Math.floor(n).toLocaleString("ko-KR")}`;
    }

    function formatKoreanMeridiemTime(hhmm) {
        const m = String(hhmm || "").match(/^(\d{2}):(\d{2})$/);
        if (!m) return String(hhmm || "-");
        const h24 = Number(m[1]);
        const mm = m[2];
        const meridiem = h24 < 12 ? "오전" : "오후";
        const h12 = (h24 % 12) || 12;
        return `${meridiem} ${h12}:${mm}`;
    }

    function formatPtDurationKo(value) {
        const m = String(value || "").toUpperCase().match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
        if (!m) return String(value || "-");
        const h = Number(m[1] || 0);
        const mm = Number(m[2] || 0);
        if (h && mm) return `${h}시간 ${mm}분`;
        if (h) return `${h}시간`;
        if (mm) return `${mm}분`;
        return "-";
    }

    function isUnknownText(value) {
        const s = String(value || "").trim();
        if (!s) return true;
        return /^[?？\-\s]+$/.test(s);
    }

    function ptDurationMinutes(value) {
        const m = String(value || "").toUpperCase().match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
        if (!m) return 0;
        return Number(m[1] || 0) * 60 + Number(m[2] || 0);
    }

    function formatMinutesKo(totalMinutes) {
        const m = Math.max(0, Number(totalMinutes || 0));
        const h = Math.floor(m / 60);
        const mm = m % 60;
        if (h && mm) return `${h}시간 ${mm}분`;
        if (h) return `${h}시간`;
        if (mm) return `${mm}분`;
        return "-";
    }

    function parseFareDisplay(priceText) {
        const txt = String(priceText || "").trim();
        const mKrw = txt.match(/([\d,]+)\s*KRW/i);
        if (mKrw) {
            return { primary: `₩${mKrw[1]}`, secondary: "" };
        }
        const mFx = txt.match(/([\d,]+(?:\.\d+)?)\s*(USD|EUR|JPY|CNY|GBP)/i) || txt.match(/(USD|EUR|JPY|CNY|GBP)\s*([\d,]+(?:\.\d+)?)/i);
        if (mFx) {
            const code = (mFx[2] || mFx[1] || "").toUpperCase();
            const amount = mFx[1] && /^[\d,.]+$/.test(mFx[1]) ? mFx[1] : mFx[2];
            return { primary: `${code} ${amount}`, secondary: "" };
        }
        return { primary: txt || "-", secondary: "" };
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
        // If backend prints itinerary legs separately, numbering restarts from 1 per leg.
        // Convert that reset pattern into explicit leg index for roundtrip rendering.
        let prev = 0;
        let legNo = 1;
        out.forEach((seg) => {
            if (prev && seg.idx <= prev) legNo += 1;
            seg.leg = legNo;
            prev = seg.idx;
        });
        return out;
    }

    function extractRouteCodesFromSegments(segmentDetails) {
        const txt = String(segmentDetails || "").toUpperCase();
        if (!txt) return { dep: "", arr: "" };
        const codes = txt.match(/\b[A-Z]{3}\b/g) || [];
        if (!codes.length) return { dep: "", arr: "" };
        return { dep: codes[0] || "", arr: codes[codes.length - 1] || "" };
    }

    function summarizeLegs(segs) {
        const groups = new Map();
        segs.forEach((s) => {
            const key = Number(s.leg || 1);
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(s);
        });
        return Array.from(groups.keys()).sort((a, b) => a - b).map((k) => {
            const arr = groups.get(k) || [];
            const first = arr[0] || {};
            const last = arr[arr.length - 1] || {};
            const path = arr.length
                ? [arr[0].depCode, ...arr.map((x) => x.arrCode)].filter(Boolean)
                : [];
            const via = path.length > 2 ? path.slice(1, -1) : [];
            const totalMinutes = arr.reduce((acc, x) => acc + ptDurationMinutes(x.duration), 0);
            return {
                depCode: first.depCode || "-",
                depAt: first.depAt || "-",
                arrCode: last.arrCode || "-",
                arrAt: last.arrAt || "-",
                duration: formatMinutesKo(totalMinutes),
                isDirect: arr.length <= 1,
                stops: Math.max(arr.length - 1, 0),
                routeText: via.length
                    ? `${path[0]} → ${path[path.length - 1]} (경유: ${via.join(", ")})`
                    : `${path[0] || "-"} → ${path[path.length - 1] || "-"}`,
            };
        });
    }

    function inferHotelArea(text) {
        const t = String(text || "").toLowerCase();
        if (!t) return "";
        const areaMap = [
            ["shinjuku", "신주쿠"], ["신주쿠", "신주쿠"],
            ["shibuya", "시부야"], ["시부야", "시부야"],
            ["ginza", "긴자"], ["긴자", "긴자"],
            ["ueno", "우에노"], ["우에노", "우에노"],
            ["asakusa", "아사쿠사"], ["아사쿠사", "아사쿠사"],
            ["ikebukuro", "이케부쿠로"], ["이케부쿠로", "이케부쿠로"],
            ["roppongi", "롯폰기"], ["롯폰기", "롯폰기"],
        ];
        for (const [k, v] of areaMap) {
            if (t.includes(k)) return v;
        }
        return "";
    }

    function parseListCards(rawHtml) {
        const html = String(rawHtml || "");
        const commerceRx = /(호텔|숙소|렌터카|렌트카|rental|hotel|패키지|공동구매|group\s*buy|groupbuy|티켓|ticket)/i;
        if (!commerceRx.test(html)) return [];

        const distanceBasisSource = html
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/<\/div>/gi, "\n")
            .replace(/<[^>]+>/g, " ")
            .replace(/ /g, " ");
        const distanceBasisMatch = distanceBasisSource.match(/^\s*거리\s*기준\s*:\s*([^\n]+)$/im);
        const distanceBasis = distanceBasisMatch ? distanceBasisMatch[1].trim() : "";

        const normalized = html
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/<\/div>/gi, "\n")
            .replace(/<[^>]+>/g, "")
            .replace(/ /g, " ");
        const lines = normalized.split("\n").map((s) => s.trim()).filter(Boolean);
        const cards = [];

        const normKey = (k) => String(k || "").toLowerCase().replace(/\s+/g, "");
        const aliasMap = {
            type: ["타입", "유형", "분류", "type", "category"],
            price: ["가격", "요금", "금액", "price", "fare", "cost", "total"],
            rating: ["평점", "rating", "score"],
            stars: ["성급", "stars", "star"],
            supplier: ["업체", "공급사", "vendor", "supplier", "provider", "company"],
            specs: ["옵션", "사양", "spec", "specs", "features"],
            pickup: ["픽업", "대여", "pickup", "pickupdate"],
            dropoff: ["반납", "dropoff", "returndate"],
            photo: ["사진", "이미지", "photo", "image", "imageurl", "thumbnail"],
            address: ["주소", "위치", "address", "location"],
            area: ["지역", "구역", "district", "area", "neighborhood"],
            distance: ["거리", "distance", "dist"],
            checkin: ["체크인", "checkin"],
            checkout: ["체크아웃", "checkout"],
            maps: ["지도", "maps", "map"],
            hotelId: ["호텔id", "hotel_id", "hotelid", "id"],
            snapshot: ["스냅샷", "snapshot", "detail_snapshot"],
        };

        const pickField = (fields, canonical) => {
            const keys = aliasMap[canonical] || [];
            for (const k of keys) {
                const v = fields[normKey(k)];
                if (v) return v;
            }
            return "";
        };

        const detectDefaultType = (lineText, fields) => {
            const line = String(lineText || "");
            const hasRentalField = Boolean(
                pickField(fields, "pickup") ||
                pickField(fields, "dropoff") ||
                pickField(fields, "supplier") ||
                pickField(fields, "specs")
            );
            const hasHotelField = Boolean(
                pickField(fields, "checkin") ||
                pickField(fields, "checkout") ||
                pickField(fields, "hotelId") ||
                pickField(fields, "maps") ||
                pickField(fields, "stars") ||
                pickField(fields, "distance") ||
                pickField(fields, "area")
            );
            if (hasRentalField || /(렌터카|렌트카|rental)/i.test(line)) return "렌터카";
            if (hasHotelField || /(호텔|숙소|hotel|inn|ryokan|resort|hostel|guesthouse|mystays|toyoko|apa)/i.test(line)) return "호텔";
            return "상품";
        };

        for (const line of lines) {
            const m = line.match(/^(\d+)[\)\.]\s*(.+)$/);
            if (!m) continue;
            const body = m[2];
            const parts = body.split("|").map((x) => x.trim()).filter(Boolean);
            const name = parts[0];
            if (!name) continue;

            const fields = {};
            for (const p of parts.slice(1)) {
                let key = "";
                let value = "";
                let kv = p.match(/^([^:：]+)\s*[:：]\s*(.+)$/);
                if (!kv) kv = p.match(/^([가-힣A-Za-z ]{1,20})\s+(.+)$/);
                if (kv) {
                    key = normKey(kv[1]);
                    value = kv[2].trim();
                }
                if (!key || !value) continue;
                fields[key] = value;
            }

            const supplier = pickField(fields, "supplier");
            let displayName = name;
            if (/^(렌터카|rental car|rental)$/i.test(displayName) && supplier) {
                displayName = `${supplier} 렌터카`;
            }

            const rawType = String(pickField(fields, "type") || "").toLowerCase();
            let resolvedType = detectDefaultType(line, fields);
            if (/(패키지|package)/i.test(rawType)) resolvedType = "패키지";
            else if (/(공동구매|group\s*buy|groupbuy)/i.test(rawType)) resolvedType = "공동구매";
            else if (/(티켓|ticket)/i.test(rawType)) resolvedType = "티켓";

            const hasKnownField = Boolean(
                rawType ||
                pickField(fields, "price") ||
                pickField(fields, "rating") ||
                pickField(fields, "address") ||
                pickField(fields, "checkin") ||
                pickField(fields, "checkout") ||
                pickField(fields, "pickup") ||
                pickField(fields, "dropoff") ||
                pickField(fields, "supplier") ||
                pickField(fields, "hotelId") ||
                pickField(fields, "photo")
            );
            if (!hasKnownField) continue;
            if (/^(항공권\s*추천|숙소\s*추천|여행\s*초안\s*추천)$/i.test(name)) continue;
            if (/(booking\s*실시간\s*검색|주변\s*호텔\s*지도)/i.test(name)) continue;
            const priceField = String(pickField(fields, "price") || "").trim();
            if (/(Booking에서 확인|지도에서 확인)/i.test(priceField)) continue;

            cards.push({
                type: resolvedType,
                name: displayName,
                meta: parts.slice(1).filter((p) => !/^사진\s*[:：]/i.test(p)).join(" | "),
                price: priceField,
                rating: pickField(fields, "rating"),
                stars: pickField(fields, "stars"),
                supplier,
                specs: pickField(fields, "specs"),
                pickup: pickField(fields, "pickup"),
                dropoff: pickField(fields, "dropoff"),
                photo: pickField(fields, "photo"),
                address: pickField(fields, "address"),
                area: pickField(fields, "area"),
                distance: pickField(fields, "distance"),
                checkin: pickField(fields, "checkin"),
                checkout: pickField(fields, "checkout"),
                maps: pickField(fields, "maps"),
                hotel_id: pickField(fields, "hotelId"),
                snapshot: pickField(fields, "snapshot"),
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
                    items: items.slice(0, 9),
                };
            }
            return null;
        }

        return {
            title,
            subtitle: "후보별 핵심 정보와 이미지를 보기 쉽게 정리했어요.",
            items: blocks.slice(0, 9),
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

        const prevPlaceSection = content.querySelector(".ai-place-reco");
        if (prevPlaceSection) prevPlaceSection.remove();
        content.appendChild(section);
        return true;
    }

    function enhanceCommerceCards(botBubble, rawHtml) {
        const flightCards = parseFlightTableCards(rawHtml);
        const listCards = parseListCards(rawHtml);
        const htmlText = String(rawHtml || "");
        const merged = [];
        const seen = new Set();
        [...flightCards, ...listCards].forEach((c) => {
            const key = [
                String(c?.type || ""),
                String(c?.name || ""),
                String(c?.price || ""),
                String(c?.dep || ""),
                String(c?.arr || ""),
                String(c?.checkin || ""),
                String(c?.checkout || ""),
            ].join("||");
            if (seen.has(key)) return;
            seen.add(key);
            merged.push(c);
        });
        const cards = merged;
        if (!cards.length) return;

        const content = botBubble.querySelector(".ai-msg__content");
        if (!content) return;

        // Keep itinerary narrative, but remove verbose API dump section once cards are available.
        content.innerHTML = String(content.innerHTML || "").replace(
            /<div[^>]*>\s*<b>\s*실제\s*API\s*추천\s*<\/b>\s*<\/div>[\s\S]*$/i,
            ""
        );
        // Also remove raw flight table/condition dumps when card UI is rendered.
        Array.from(content.querySelectorAll("table")).forEach((el) => el.remove());
        Array.from(content.querySelectorAll("div")).forEach((el) => {
            const txt = String(el.textContent || "").replace(/\s+/g, " ").trim();
            if (/검색\s*조건\s*:|API\s*조회\s*조건|추천\s*\d+\s*건\s*:|구간\s*상세\s*보기/i.test(txt)) {
                el.remove();
            }
        });

        const section = document.createElement("section");
        section.className = "ai-commerce-cards";
        const title = cards[0].type === "항공편" ? "항공편 카드" : `${cards[0].type} 카드`;
        section.innerHTML = `<div class="ai-commerce-cards__title">${escapeHtml(title)}</div>`;
        if (!flightCards.length && /(항공편을 찾지 못했|조건에 맞는 항공편이 없습니다)/i.test(htmlText)) {
            const warn = document.createElement("div");
            warn.style.cssText = "margin:8px 0 12px;padding:8px 10px;border:1px solid #fde68a;background:#fffbeb;border-radius:8px;color:#92400e;font-size:13px;";
            warn.textContent = "항공권은 현재 조건에서 결과가 없어 숙소만 표시했어요. 날짜/예산을 조정해 보세요.";
            section.appendChild(warn);
        }

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
                const rawDuration = String(cardData.duration || "").trim();
                const price = cardData.price || "-";
                const airline = cardData.airline || "항공사";
                const airlineCode = String(cardData.airline || "").trim().toUpperCase() || "-";
                const airlineLogoUrl = getAirlineLogoUrlByCode(airlineCode);
                const segs = parseFlightSegmentEntries(cardData.segmentDetails);
                const legSummaries = summarizeLegs(segs);
                const outSeg = legSummaries[0] || segs[0];
                const inSeg = legSummaries[1] || segs[1];
                const inferredCodes = extractRouteCodesFromSegments(cardData?.segmentDetails || "");
                const isRoundTrip = Boolean(cardData.isRoundTrip || legSummaries.length >= 2);
                const isDirect = /직항/.test(routeInfo);
                const fallbackDuration = outSeg?.duration ? formatPtDurationKo(outSeg.duration) : "-";
                const duration = isUnknownText(rawDuration) ? fallbackDuration : formatPtDurationKo(rawDuration);
                const durationLabel = isRoundTrip ? "왕복 여정" : (isDirect ? "비행시간" : "총 여정");
                const canRenderRoundPairs = Boolean(
                    isRoundTrip &&
                    outSeg &&
                    inSeg &&
                    legSummaries.length >= 2
                );
                const outRouteCode = `${String(outSeg?.depCode || "-")} → ${String(outSeg?.arrCode || "-")}`;
                const inRouteCode = `${String(inSeg?.depCode || "-")} → ${String(inSeg?.arrCode || "-")}`;
                const inferredStops = Number(outSeg?.stops ?? Math.max(segs.length - 1, 0));
                const inferredRouteInfo = inferredStops <= 0 ? "직항" : `경유 ${inferredStops}회`;
                const safeRouteInfo = isUnknownText(routeInfo) ? inferredRouteInfo : routeInfo;
                const routeInfoLabel = isRoundTrip ? "왕복 여정" : safeRouteInfo;
                const singleRouteCode = `${String(outSeg?.depCode || inferredCodes.dep || "-")} → ${String(outSeg?.arrCode || inferredCodes.arr || "-")}`;
                const totalLegs = Math.max(legSummaries.length, isRoundTrip ? 2 : 1);
                const fareDisplay = parseFareDisplay(price);

                card.innerHTML = `
                    <div class="ai-flight-card__brand">
                        <div class="ai-flight-card__logo-wrap">
                            ${airlineLogoUrl ? `<img class="ai-flight-card__logo-img" src="${airlineLogoUrl}" alt="${escapeHtml(airlineCode)} 로고" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ""}
                            <div class="ai-flight-card__logo${airlineLogoUrl ? '" style="display:none;' : ''}">${escapeHtml(airlineCode || airline)}</div>
                        </div>
                        <div class="ai-flight-card__airline">${escapeHtml(airlineCode || airline)}</div>
                    </div>
                    ${canRenderRoundPairs ? (() => {
                        const oDep = splitMmddHm(outSeg.depAt);
                        const oArr = splitMmddHm(outSeg.arrAt);
                        const iDep = splitMmddHm(inSeg.depAt);
                        const iArr = splitMmddHm(inSeg.arrAt);
                        return `
                        <div class="ai-flight-card__schedule ai-flight-card__schedule--round">
                            <div class="ai-flight-card__v2-list">
                                <div class="ai-flight-card__v2-row">
                                    <div class="ai-flight-card__point">
                                    <div class="ai-flight-card__time">${escapeHtml(formatKoreanMeridiemTime(oDep.time))}</div>
                                    <div class="ai-flight-card__date">${escapeHtml(oDep.date || "-")}</div>
                                    <div class="ai-flight-card__code">${escapeHtml(outSeg.depCode)}</div>
                                    </div>
                                    <div class="ai-flight-card__v2-route">
                                        <div class="ai-flight-card__duration">${escapeHtml(formatPtDurationKo(outSeg.duration))}</div>
                                        <div class="ai-flight-card__v2-routecode">${escapeHtml(outRouteCode)}</div>
                                        <div class="ai-flight-card__line" data-dots="${'.'.repeat(Math.max(0, Number(outSeg.stops || 0)))}"></div>
                                        <div class="ai-flight-card__routeinfo">${escapeHtml(outSeg.isDirect ? "직항" : `경유 ${outSeg.stops}회`)}</div>
                                    </div>
                                    <div class="ai-flight-card__point ai-flight-card__point--arr">
                                    <div class="ai-flight-card__time">${escapeHtml(formatKoreanMeridiemTime(oArr.time))}</div>
                                    <div class="ai-flight-card__date">${escapeHtml(oArr.date || "-")}</div>
                                    <div class="ai-flight-card__code">${escapeHtml(outSeg.arrCode)}</div>
                                    </div>
                                </div>
                                <div class="ai-flight-card__v2-row">
                                    <div class="ai-flight-card__point">
                                        <div class="ai-flight-card__time">${escapeHtml(formatKoreanMeridiemTime(iDep.time))}</div>
                                        <div class="ai-flight-card__date">${escapeHtml(iDep.date || "-")}</div>
                                        <div class="ai-flight-card__code">${escapeHtml(inSeg.depCode)}</div>
                                    </div>
                                    <div class="ai-flight-card__v2-route">
                                        <div class="ai-flight-card__duration">${escapeHtml(formatPtDurationKo(inSeg.duration))}</div>
                                        <div class="ai-flight-card__v2-routecode">${escapeHtml(inRouteCode)}</div>
                                        <div class="ai-flight-card__line" data-dots="${'.'.repeat(Math.max(0, Number(inSeg.stops || 0)))}"></div>
                                        <div class="ai-flight-card__routeinfo">${escapeHtml(inSeg.isDirect ? "직항" : `경유 ${inSeg.stops}회`)}</div>
                                    </div>
                                    <div class="ai-flight-card__point ai-flight-card__point--arr">
                                        <div class="ai-flight-card__time">${escapeHtml(formatKoreanMeridiemTime(iArr.time))}</div>
                                        <div class="ai-flight-card__date">${escapeHtml(iArr.date || "-")}</div>
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
                            <div class="ai-flight-card__v2-routecode">${escapeHtml(singleRouteCode)}</div>
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
                        <button type="button" class="ai-commerce-card__wish" aria-pressed="false" title="위시리스트 저장">♡</button>
                        <div class="ai-flight-card__fare-label">총 ${escapeHtml(String(totalLegs))}구간</div>
                        <div class="ai-flight-card__fare-value">${escapeHtml(fareDisplay.primary)}</div>
                        <div class="ai-commerce-card__actions">
                            <button type="button" class="ai-commerce-card__add">장바구니</button>
                            <button type="button" class="ai-commerce-card__pay">예약하기</button>
                        </div>
                    </div>
                `;
            } else if (cardData.type === "호텔" || (cardData.type === "상품" && looksLikeHotelCard(cardData))) {
                const metaBits = [];
                if (cardData.rating) metaBits.push(`평점 ${cardData.rating}`);
                if (cardData.stars) metaBits.push(`${cardData.stars}성급`);
                if (cardData.distance) metaBits.push(`거리 ${cardData.distance}`);
                const priceText = cardData.price || "";
                const stayText = [cardData.checkin ? `체크인 ${cardData.checkin}` : "", cardData.checkout ? `체크아웃 ${cardData.checkout}` : ""]
                    .filter(Boolean)
                    .join(" · ");
                const locationText = cardData.address || "";
                const areaText = String(cardData.area || inferHotelArea(`${cardData.name || ""} ${locationText}`) || "").trim();
                const locationLine = [locationText, areaText].filter(Boolean).join(" · ");
                card.classList.add("ai-commerce-card--hotel");
                card.innerHTML = `
                    ${cardData.photo ? `<div class="ai-hotel-card__thumb-wrap"><img class="ai-hotel-card__thumb" src="${escapeHtml(cardData.photo)}" alt="${escapeHtml(cardData.name)}" loading="lazy" onerror="this.onerror=null; const w=this.closest('.ai-hotel-card__thumb-wrap'); if(w){w.classList.add('ai-hotel-card__thumb-wrap--placeholder'); w.innerHTML='<div class=\\'ai-hotel-card__thumb-fallback\\'>HOTEL</div>'; }"></div>` : `<div class="ai-hotel-card__thumb-wrap ai-hotel-card__thumb-wrap--placeholder"><div class="ai-hotel-card__thumb-fallback">HOTEL</div></div>`}
                    <div class="ai-hotel-card__body">
                        <div class="ai-commerce-card__type">호텔</div>
                        <div class="ai-commerce-card__name">${escapeHtml(cardData.name)}</div>
                        ${metaBits.length ? `<div class="ai-hotel-card__chips">${metaBits.map((t) => `<span class="ai-hotel-card__chip">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
                        ${stayText ? `<div class="ai-hotel-card__note">${escapeHtml(stayText)}</div>` : ""}
                        ${locationLine ? `<div class="ai-hotel-card__note">${escapeHtml(locationLine)}</div>` : ""}
                    </div>
                    <div class="ai-hotel-card__fare">
                        <button type="button" class="ai-commerce-card__wish" aria-pressed="false" title="위시리스트 저장">♡</button>
                        <div class="ai-flight-card__fare-label">숙박 총액(참고)</div>
                        <div class="ai-hotel-card__price">${escapeHtml(priceText || "-")}</div>
                        <div class="ai-commerce-card__actions">
                            <button type="button" class="ai-commerce-card__add">장바구니</button>
                            <button type="button" class="ai-commerce-card__pay">예약하기</button>
                        </div>
                    </div>
                `;
                hydrateHotelCardPhoto(card, cardData);
            } else if (["패키지", "공동구매", "티켓"].includes(cardData.type)) {
                const priceText = cardData.price || "";
                const metaText = String(cardData.meta || "");
                const ratingFromMeta = (metaText.match(/평점\s*[:：]\s*([0-9.]+)/i) || [])[1] || "";
                const locationFromMeta = (metaText.match(/위치\s*[:：]\s*([^|]+)/i) || [])[1] || "";
                const descFromMeta = (metaText.match(/설명\s*[:：]\s*([^|]+)/i) || [])[1] || "";
                const ratingText = String(cardData.rating || ratingFromMeta || "").trim();
                const locationText = String(cardData.address || locationFromMeta || "").trim();
                const descText = String(descFromMeta || "").trim();
                const typeLabel = String(cardData.type || "상품");
                const thumbLabel = typeLabel === "티켓" ? "TICKET" : (typeLabel === "공동구매" ? "GROUP" : "PACKAGE");
                const fallbackPhoto = productFallbackImageFromTour(cardData.name, typeLabel);

                const chips = [];
                if (ratingText) chips.push(`평점 ${ratingText}`);
                if (locationText) chips.push(locationText);

                card.classList.add("ai-commerce-card--hotel", "ai-commerce-card--product");
                card.innerHTML = `
                    ${cardData.photo ? `<div class="ai-hotel-card__thumb-wrap"><img class="ai-hotel-card__thumb" src="${escapeHtml(cardData.photo)}" data-fallback-src="${escapeHtml(fallbackPhoto)}" alt="${escapeHtml(cardData.name)}" loading="lazy" onerror="this.onerror=null; const fb=this.getAttribute('data-fallback-src'); if(fb && this.src!==fb){ this.src=fb; this.removeAttribute('data-fallback-src'); return; } const w=this.closest('.ai-hotel-card__thumb-wrap'); if(w){w.classList.add('ai-hotel-card__thumb-wrap--placeholder'); w.innerHTML='<div class=\'ai-hotel-card__thumb-fallback\'>${thumbLabel}</div>'; }"></div>` : `<div class="ai-hotel-card__thumb-wrap ai-hotel-card__thumb-wrap--placeholder"><div class="ai-hotel-card__thumb-fallback">${thumbLabel}</div></div>`}
                    <div class="ai-hotel-card__body">
                        <div class="ai-commerce-card__type">${escapeHtml(typeLabel)}</div>
                        <div class="ai-commerce-card__name">${escapeHtml(cardData.name)}</div>
                        ${chips.length ? `<div class="ai-hotel-card__chips">${chips.map((x) => `<span class="ai-hotel-card__chip">${escapeHtml(x)}</span>`).join("")}</div>` : ""}
                        ${descText ? `<div class="ai-hotel-card__note">${escapeHtml(descText)}</div>` : ""}
                    </div>
                    <div class="ai-hotel-card__fare">
                        <button type="button" class="ai-commerce-card__wish" aria-pressed="false" title="위시리스트 저장">♡</button>
                        <div class="ai-flight-card__fare-label">${escapeHtml(typeLabel === "공동구매" ? "예상 금액(참고)" : "상품가(참고)")}</div>
                        <div class="ai-hotel-card__price">${escapeHtml(priceText || "-")}</div>
                        <div class="ai-commerce-card__actions">
                            <button type="button" class="ai-commerce-card__add">장바구니</button>
                            <button type="button" class="ai-commerce-card__pay">예약하기</button>
                        </div>
                    </div>
                `;
            } else if (cardData.type === "렌터카") {
                const priceText = cardData.price || "";
                const displayName = normalizeRentalName(cardData.name, cardData.supplier);
                const normalizedSpecs = summarizeRentalSpecs(cardData.specs);
                const ratingText = formatRentalRating(cardData.rating);
                const metaBits = [];
                if (cardData.supplier) metaBits.push(`업체 ${cardData.supplier}`);
                if (ratingText) metaBits.push(`평점 ${ratingText}`);
                if (normalizedSpecs) metaBits.push(normalizedSpecs);
                const rentalPhoto = normalizeRentalPhotoUrl(cardData.photo);
                const rentalPeriod = [cardData.pickup ? `픽업 ${cardData.pickup}` : "", cardData.dropoff ? `반납 ${cardData.dropoff}` : ""]
                    .filter(Boolean)
                    .join(" · ");
                card.classList.add("ai-commerce-card--hotel");
                card.innerHTML = `
                    ${rentalPhoto ? `<div class="ai-hotel-card__thumb-wrap"><img class="ai-hotel-card__thumb" src="${escapeHtml(rentalPhoto)}" alt="${escapeHtml(displayName)}" loading="lazy" onerror="this.onerror=null; const w=this.closest('.ai-hotel-card__thumb-wrap'); if(w){w.classList.add('ai-hotel-card__thumb-wrap--placeholder'); w.innerHTML='<div class=\\'ai-hotel-card__thumb-fallback\\'>RENTAL</div>'; }"></div></div>` : `<div class="ai-hotel-card__thumb-wrap ai-hotel-card__thumb-wrap--placeholder"><div class="ai-hotel-card__thumb-fallback">RENTAL</div></div>`}
                    <div class="ai-hotel-card__body">
                        <div class="ai-commerce-card__name">${escapeHtml(displayName)}</div>
                        ${metaBits.length ? `<div class="ai-hotel-card__chips">${metaBits.map((t) => `<span class="ai-hotel-card__chip">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
                        ${rentalPeriod ? `<div class="ai-hotel-card__note">${escapeHtml(rentalPeriod)}</div>` : ""}
                    </div>
                    <div class="ai-hotel-card__fare">
                        <button type="button" class="ai-commerce-card__wish" aria-pressed="false" title="위시리스트 저장">♡</button>
                        <div class="ai-flight-card__fare-label">대여 총액(참고)</div>
                        <div class="ai-hotel-card__price">${escapeHtml(priceText || "-")}</div>
                        <div class="ai-commerce-card__actions">
                            <button type="button" class="ai-commerce-card__add">장바구니</button>
                            <button type="button" class="ai-commerce-card__pay">예약하기</button>
                        </div>
                    </div>
                `;
            } else {
                card.innerHTML = `
                    <div class="ai-commerce-card__type">${escapeHtml(cardData.type)}</div>
                    <div class="ai-commerce-card__name">${escapeHtml(cardData.name)}</div>
                    ${cardData.meta ? `<div class="ai-commerce-card__meta">${escapeHtml(cardData.meta)}</div>` : ""}
                    <div class="ai-commerce-card__actions">
                        <button type="button" class="ai-commerce-card__add">장바구니</button>
                        <button type="button" class="ai-commerce-card__wish" aria-pressed="false" title="위시리스트 저장">♡</button>
                    </div>
                `;
            }
            card.__savedItemData = cardData;
            const addBtn = card.querySelector(".ai-commerce-card__add");
            const wishBtn = card.querySelector(".ai-commerce-card__wish");
            const payBtn = card.querySelector(".ai-commerce-card__pay");
            addBtn?.addEventListener("click", async () => {
                await addSavedItem("cart", cardData);
                cartTab = "cart";
                setCartDrawer(true);
            });
            payBtn?.addEventListener("click", () => {
                const t = String(cardData?.type || "").toLowerCase();
                const isFlight = t === "항공편" || t === "flight";
                const isHotel = t === "호텔" || t === "hotel" || t === "숙소" || t === "stay" || t === "accommodation";
                const isTicket = t === "티켓" || t === "ticket" || t === "activity";
                const isRental = t === "렌터카" || t === "rental" || t === "car rental" || t === "rentcar" || t === "car";
                const isTourLikeProduct = isTicket || t === "패키지" || t === "package" || t === "공동구매" || t === "groupbuy" || t === "group buy";
                if (isFlight) {
                    const priceRaw = String(cardData?.price || "");
                    const digitsOnly = priceRaw.replace(/[^\d.]/g, "");
                    const legsForPay = summarizeLegs(parseFlightSegmentEntries(cardData?.segmentDetails || ""));
                    const inferredRoundTrip = Boolean(cardData?.isRoundTrip || legsForPay.length >= 2);
                    const qs = new URLSearchParams({
                        airline: String(cardData?.airline || ""),
                        dep: String(cardData?.dep || ""),
                        arr: String(cardData?.arr || ""),
                        route: String(cardData?.routeInfo || ""),
                        duration: String(cardData?.duration || ""),
                        price: priceRaw,
                        price_total: digitsOnly,
                        currency: "KRW",
                        dep_at: String(cardData?.dep || ""),
                        arr_at: String(cardData?.arr || ""),
                        round: inferredRoundTrip ? "1" : "0",
                    });
                    window.location.href = `/flight-detail?${qs.toString()}`;
                    return;
                }
                if (isHotel) {
                    let hotelId = String(cardData?.hotel_id || cardData?.hotelId || "").trim();
                    const { checkin, checkout } = resolveHotelStayDates(cardData);
                    const city = String(cardData?.address || cardData?.name || "").trim();
                    if (!hotelId) {
                        const base = `${String(cardData?.name || "hotel")}|${city}|${checkin}|${checkout}`;
                        hotelId = `chat_${encodeURIComponent(base).replace(/%/g, "").slice(0, 48)}`;
                    }
                    const priceNum = Number(String(cardData?.price || "").replace(/[^\d.]/g, ""));
                    const ratingNum = Number(String(cardData?.rating || "").replace(/[^\d.]/g, ""));
                    const snapshotObj = {
                        hotel_id: hotelId,
                        name: String(cardData?.name || "Hotel"),
                        name_ko: String(cardData?.name || "Hotel"),
                        address: city,
                        city,
                        checkin,
                        checkout,
                        image: String(cardData?.photo || ""),
                        review_score: Number.isFinite(ratingNum) ? ratingNum : null,
                        review_word: "",
                        price: Number.isFinite(priceNum) && priceNum > 0 ? priceNum : null,
                        price_original: null,
                        currency: "KRW",
                        source: "chat-hotel-card",
                    };
                    const snapshot = encodeURIComponent(JSON.stringify(snapshotObj));
                    const detailQs = new URLSearchParams({
                        hotel_id: hotelId,
                        city,
                        checkin,
                        checkout,
                        snapshot,
                    });
                    window.location.href = `/gloval-hotel/detail?${detailQs.toString()}`;
                    return;
                }
                if (isRental) {
                    const priceRaw = String(cardData?.price || "").trim();
                    const priceNumber = Number(priceRaw.replace(/[^\d.]/g, ""));
                    const ratingRaw = String(cardData?.rating || "").trim();
                    const ratingNumber = Number(ratingRaw.replace(/[^\d.]/g, ""));
                    const specsText = String(cardData?.specs || "").trim();
                    const specs = specsText
                        ? specsText.split(/[|,/]/).map((s) => s.trim()).filter(Boolean)
                        : [];
                    const carPayload = {
                        name: String(cardData?.name || "렌터카 상품"),
                        supplier: String(cardData?.company || cardData?.supplier || ""),
                        price: Number.isFinite(priceNumber) ? priceNumber : 0,
                        currency: "KRW",
                        image: String(cardData?.photo || ""),
                        specs,
                        pickup_name: String(cardData?.pickup_name || cardData?.pickup || ""),
                        dropoff_name: String(cardData?.dropoff_name || cardData?.dropoff || ""),
                        pickup_at: String(cardData?.pickup_at || cardData?.pickup || ""),
                        dropoff_at: String(cardData?.dropoff_at || cardData?.dropoff || ""),
                    };
                    if (Number.isFinite(ratingNumber) && ratingNumber > 0) {
                        carPayload.rating = ratingNumber;
                    }
                    const encoded = encodeURIComponent(JSON.stringify(carPayload));
                    window.location.href = `/rental/detail?car=${encoded}`;
                    return;
                }
                if (isTourLikeProduct) {
                    const title = String(cardData?.name || "").trim() || "투어 상품";
                    const locText = String(cardData?.address || cardData?.location || "").trim() || "전세계";
                    const priceText = String(cardData?.price || "").trim() || "0";
                    const img = String(cardData?.photo || "").trim();
                    const qs = new URLSearchParams({
                        title,
                        price: priceText,
                        loc: locText,
                    });
                    if (img) qs.set("img", img);
                    window.location.href = `/tour-detail?${qs.toString()}`;
                    return;
                }
                alert("결제 기능은 준비 중입니다. 우선 장바구니에 담아두었습니다.");
            });
            wishBtn?.addEventListener("click", async () => {
                await addSavedItem("wishlist", cardData);
                cartTab = "wishlist";
                setCartDrawer(true);
            });
            grid.appendChild(card);
        });
        section.appendChild(grid);
        const prevCommerceSection = content.querySelector(".ai-commerce-cards");
        if (prevCommerceSection) prevCommerceSection.remove();
        content.appendChild(section);
        syncCommerceCardStates();
    }

    async function sendMessage() {
        const message = promptInput.value.trim();
        if (!message) return;

        const canChat = await ensureLoggedInForChat();
        if (!canChat) {
            promptLoginForChat();
            return;
        }

        collapseHeroForChat();
        appendUserMessage(message);
        promptInput.value = "";

        const loadingItem = appendLoadingMessage();
        try {
            const res = await fetch("/chat", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                    session_id: sessionId,
                }),
            });

            if (res.status === 401) {
                loadingItem.remove();
                promptLoginForChat();
                return;
            }
            if (res.status === 402) {
                const errData = await res.json().catch(() => ({}));
                const code = errData?.detail?.code || "PASS_REQUIRED";
                loadingItem.remove();
                promptChatPassPurchase(code);
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();
            const html = data?.response || "응답을 받지 못했어요.";
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
                <div class="ai-msg__bubble ai-msg__bubble--error">요청 중 오류가 발생했어요.</div>
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
