/**
 * DESTINO 항공권 검색 스크립트
 */

function initIcons() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

const airportData = {
    '한국/일본': [
        { name: '인천', code: 'ICN', country: '대한민국' },
        { name: '김포', code: 'GMP', country: '대한민국' },
        { name: '도쿄(나리타)', code: 'NRT', country: '일본' },
        { name: '도쿄(하네다)', code: 'HND', country: '일본' },
        { name: '오사카(간사이)', code: 'KIX', country: '일본' },
    ],
    '동남아': [
        { name: '방콕(수완나폼)', code: 'BKK', country: '태국' },
        { name: '다낭', code: 'DAD', country: '베트남' },
    ],
    '미주/유럽': [
        { name: '로스앤젤레스', code: 'LAX', country: '미국' },
        { name: '파리(샤를드골)', code: 'CDG', country: '프랑스' },
    ],
};

let currentTripType = 'round';
let mainSearchState = {
    dep: '인천 (ICN)',
    arr: '',
    departureDate: '',
    returnDate: '',
};
let segments = [
    { id: 1, dep: '인천 (ICN)', arr: '', date: '' },
    { id: 2, dep: '', arr: '인천 (ICN)', date: '' },
];
let activeInputId = null;

let passengerState = {
    adult: 1,
    child: 0,
    infant: 0,
    cabin: 'ECONOMY',
};
let flightSortState = 'price';
let savedItemState = { wishlist: [], cart: [] };
let flightSavedDrawerTab = 'cart';
let flightAlertState = [];

document.addEventListener('DOMContentLoaded', () => {
    renderForm();
    initAirportPopover();
    initFlightSortControls();
    initFlightSavedDrawer();
    initFlightSavedItemActions();
    loadSavedItems().catch(() => {});
    initIcons();
});

function getSavedItemKey(item) {
    return `${String(item?.item_type || '').toLowerCase()}__${String(item?.name || '').toLowerCase()}__${String(item?.meta || '').toLowerCase()}`;
}

function hasSavedItem(listType, item) {
    const key = getSavedItemKey(item);
    return (savedItemState[listType] || []).some((x) => getSavedItemKey(x) === key);
}

function getSavedItemTypeLabel(itemType) {
    const type = String(itemType || '').toLowerCase();
    if (type === 'flight') return '항공';
    if (type === 'hotel' || type === 'stay' || type === 'accommodation') return '숙박';
    if (type === 'groupbuy' || type === 'travel-group') return '공동구매';
    return type || 'item';
}

async function savedItemsApi(path = '/api/saved-items', options = {}) {
    const res = await fetch(path, {
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    });
    if (res.status === 401) {
        const err = new Error('LOGIN_REQUIRED');
        err.code = 'LOGIN_REQUIRED';
        throw err;
    }
    let data = null;
    try { data = await res.json(); } catch (_e) {}
    if (!res.ok) {
        const err = new Error((data && (data.detail || data.error)) || `HTTP ${res.status}`);
        err.code = 'API_ERROR';
        err.payload = data;
        throw err;
    }
    return data;
}

function requireLoginMessage() {
    if (confirm('로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?')) {
        location.href = '/login';
    }
}

function loadTossPaymentsScript() {
    if (window.TossPayments) return Promise.resolve(window.TossPayments);
    return new Promise((resolve, reject) => {
        const existing = document.querySelector('script[data-toss-sdk="1"]');
        if (existing) {
            existing.addEventListener('load', () => resolve(window.TossPayments));
            existing.addEventListener('error', () => reject(new Error('토스 스크립트 로드 실패')));
            return;
        }
        const s = document.createElement('script');
        s.src = 'https://js.tosspayments.com/v1/payment';
        s.async = true;
        s.dataset.tossSdk = '1';
        s.onload = () => resolve(window.TossPayments);
        s.onerror = () => reject(new Error('토스 스크립트 로드 실패'));
        document.head.appendChild(s);
    });
}

function ensureFlightCheckoutModal() {
    let root = document.getElementById('flightCheckoutModal');
    if (root) return root;
    root = document.createElement('div');
    root.id = 'flightCheckoutModal';
    root.className = 'flight-checkout-modal';
    root.innerHTML = `
        <div class="flight-checkout-modal__backdrop" data-flight-checkout-close></div>
        <section class="flight-checkout-modal__panel">
            <h3>예약자/탑승자 정보 입력</h3>
            <p class="flight-checkout-modal__sub">여권 정보 입력 후 결제를 진행합니다.</p>
            <div id="flightCheckoutSummary" class="flight-checkout-summary"></div>
            <form id="flightCheckoutForm" class="flight-checkout-form">
                <div class="flight-checkout-grid">
                    <input name="customer_name" placeholder="예약자 이름" required>
                    <input name="customer_email" type="email" placeholder="예약자 이메일" required>
                    <input name="customer_phone" placeholder="예약자 연락처(선택)">
                </div>
                <div id="flightPassengerFields"></div>
                <div class="flight-checkout-actions">
                    <button type="button" class="flight-checkout-cancel" data-flight-checkout-close>취소</button>
                    <button type="submit" class="flight-checkout-submit">결제 진행</button>
                </div>
            </form>
        </section>
    `;
    document.body.appendChild(root);
    root.querySelectorAll('[data-flight-checkout-close]').forEach((el) => {
        el.addEventListener('click', () => root.classList.remove('is-open'));
    });
    return root;
}

function getPassengerCountForCheckout() {
    const total = Number(passengerState?.adult || 0) + Number(passengerState?.child || 0) + Number(passengerState?.infant || 0);
    return Math.max(1, total);
}

function renderPassengerFields(count) {
    const mount = document.getElementById('flightPassengerFields');
    if (!mount) return;
    let html = '';
    for (let i = 0; i < count; i += 1) {
        html += `
        <fieldset class="flight-passenger-fieldset">
            <legend>탑승자 ${i + 1}</legend>
            <div class="flight-checkout-grid">
                <input name="p_${i}_last_name" placeholder="성(영문)" required>
                <input name="p_${i}_first_name" placeholder="이름(영문)" required>
                <input name="p_${i}_birth_date" type="date" required>
                <input name="p_${i}_nationality" placeholder="국적(예: KR)" required>
                <input name="p_${i}_passport_number" placeholder="여권번호" required>
                <input name="p_${i}_passport_expiry" type="date" required>
            </div>
        </fieldset>`;
    }
    mount.innerHTML = html;
}

async function startFlightCheckout(savePayload) {
    const modal = ensureFlightCheckoutModal();
    const summary = modal.querySelector('#flightCheckoutSummary');
    const form = modal.querySelector('#flightCheckoutForm');
    const count = getPassengerCountForCheckout();
    renderPassengerFields(count);
    const priceLabel = String(savePayload?.meta || '').split('|')[0] || '';
    summary.textContent = `${savePayload?.name || '항공권'} ${priceLabel ? `· ${priceLabel}` : ''}`;
    modal.classList.add('is-open');

    form.onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const passengers = [];
        for (let i = 0; i < count; i += 1) {
            passengers.push({
                last_name: String(fd.get(`p_${i}_last_name`) || '').trim(),
                first_name: String(fd.get(`p_${i}_first_name`) || '').trim(),
                birth_date: String(fd.get(`p_${i}_birth_date`) || '').trim(),
                nationality: String(fd.get(`p_${i}_nationality`) || '').trim().toUpperCase(),
                passport_number: String(fd.get(`p_${i}_passport_number`) || '').trim().toUpperCase(),
                passport_expiry: String(fd.get(`p_${i}_passport_expiry`) || '').trim(),
            });
        }
        const body = {
            offer: savePayload?.payload || {},
            customer_name: String(fd.get('customer_name') || '').trim(),
            customer_email: String(fd.get('customer_email') || '').trim(),
            customer_phone: String(fd.get('customer_phone') || '').trim(),
            passengers,
        };
        try {
            const checkout = await savedItemsApi('/api/flight/checkout', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            if (checkout.payment_mode !== 'toss' || !checkout.toss_client_key) {
                modal.classList.remove('is-open');
                alert(`[모의 결제] 주문번호: ${checkout.order_id}\n결제금액: ${checkout.amount.toLocaleString('ko-KR')}원`);
                const oid = encodeURIComponent(String(checkout.order_id || ''));
                location.href = `/payment/flight/confirmed?orderId=${oid}`;
                return;
            }
            const TossPayments = await loadTossPaymentsScript();
            const toss = TossPayments(checkout.toss_client_key);
            await toss.requestPayment('카드', {
                amount: checkout.amount,
                orderId: checkout.order_id,
                orderName: checkout.order_name,
                customerName: body.customer_name,
                customerEmail: body.customer_email,
                successUrl: checkout.success_url,
                failUrl: checkout.fail_url,
            });
        } catch (err) {
            if (err?.code === 'LOGIN_REQUIRED') {
                alert('로그인이 필요합니다. 같은 주소(127.0.0.1 또는 localhost)로 로그인했는지 확인해 주세요.');
                return requireLoginMessage();
            }
            alert(err?.message || '결제 준비 중 오류가 발생했습니다.');
        }
    };
}

async function loadSavedItems() {
    try {
        const data = await savedItemsApi('/api/saved-items', { method: 'GET', headers: {} });
        savedItemState = {
            wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
            cart: Array.isArray(data?.cart) ? data.cart : [],
        };
        rerenderCurrentFlightResults();
        renderFlightSavedDrawer();
    } catch (e) {
        if (e?.code === 'LOGIN_REQUIRED') {
            savedItemState = { wishlist: [], cart: [] };
            renderFlightSavedDrawer();
            return;
        }
        console.warn('saved-items load failed', e);
    }
}

async function loadFlightAlerts() {
    try {
        const res = await fetch('/api/group-buy/join-requests/inbox', { credentials: 'include' });
        if (res.status === 401) {
            flightAlertState = [];
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        flightAlertState = Array.isArray(data) ? data : [];
    } catch (_e) {
        flightAlertState = [];
    }
}

async function decideFlightAlert(requestId, action) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}/decision`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
    });
    if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d?.detail || `HTTP ${res.status}`);
    }
}

function setFlightSavedDrawer(open) {
    const drawer = document.getElementById('flightSavedDrawer');
    const fab = document.getElementById('flightSavedFab');
    if (!drawer || !fab) return;
    drawer.classList.toggle('is-open', !!open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    // 드로어 열림/닫힘에 따라 버튼에 is-open 클래스 토글
    fab.classList.toggle('is-open', !!open);
}

function renderFlightSavedDrawer() {
    const listEl = document.getElementById('flightSavedList');
    const emptyEl = document.getElementById('flightSavedEmpty');
    const countEl = document.getElementById('flightSavedFabCount');
    const tabs = Array.from(document.querySelectorAll('[data-flight-saved-tab]'));
    if (!listEl || !emptyEl) return;
    const total = (savedItemState.cart?.length || 0) + (savedItemState.wishlist?.length || 0) + (flightAlertState?.length || 0);
    if (countEl) {
        countEl.hidden = total === 0;
        countEl.textContent = String(total || 0);
    }
    tabs.forEach((btn) => {
        const active = btn.getAttribute('data-flight-saved-tab') === flightSavedDrawerTab;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    if (flightSavedDrawerTab === 'alerts') {
        // travel-group 구조를 따르되, 클래스명은 airport 스타일로 유지
        listEl.className = 'flight-saved-alert-list';
        emptyEl.style.display = flightAlertState.length ? 'none' : 'block';
        emptyEl.textContent = '도착한 참여 요청 알림이 없습니다.';
        if (!flightAlertState.length) {
            listEl.innerHTML = '';
            return;
        }
        listEl.innerHTML = flightAlertState.map((item) => {
            const status = String(item.status || 'pending');
            const statusLabel = status === 'accepted' ? '수락됨' : (status === 'rejected' ? '거절됨' : '대기중');
            const statusChipStyle = status === 'accepted'
                ? 'display:inline-block;padding:2px 8px;border-radius:999px;background:#dcfce7;color:#166534;font-weight:800;'
                : (status === 'rejected'
                    ? 'display:inline-block;padding:2px 8px;border-radius:999px;background:#fee2e2;color:#991b1b;font-weight:800;'
                    : 'display:inline-block;padding:2px 8px;border-radius:999px;background:#fef3c7;color:#92400e;font-weight:800;');
            const incoming = String(item.direction || 'mine') !== 'mine';
            const reqTitle = incoming
                ? `${escapeHtml(item.requester_name || '-')}` + '님이 요청했습니다'
                : `${escapeHtml(item.requester_name || '작성자')}` + '님의 응답';
            return `
                <li class="flight-saved-alert-item" style="grid-template-columns:1fr;">
                    <div class="flight-saved-alert-meta">
                        <div class="flight-saved-alert-title">공동구매 · 참여요청</div>
                        <div class="flight-saved-alert-desc">${escapeHtml(item.post_title || '-')}</div>
                        <div class="flight-saved-alert-desc">${reqTitle}<br>${item.requester_email ? `이메일: ${escapeHtml(item.requester_email)}<br>` : ''}<span style="${statusChipStyle}">${statusLabel}</span>${item.message ? `<br>${escapeHtml(item.message || '')}` : ''}</div>
                        ${
                            incoming && status === 'pending'
                                ? `<div class="flight-saved-alert-actions">
                                    <button type="button" data-flight-alert-action="accept" data-flight-alert-id="${Number(item.id)}" style="margin-right:6px;padding:4px 8px;border:1px solid #dbeafe;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:700;">수락</button>
                                    <button type="button" data-flight-alert-action="reject" data-flight-alert-id="${Number(item.id)}" style="padding:4px 8px;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:12px;font-weight:700;">거절</button>
                                </div>`
                                : ''
                        }
                        ${
                            status !== 'pending' && !incoming
                                ? `<div class="flight-saved-alert-actions" style="margin-top:8px;">
                                    <button type="button" data-flight-alert-remove="${Number(item.id)}" style="padding:4px 8px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;color:#475569;font-size:12px;font-weight:700;">알림 삭제</button>
                                </div>`
                                : ''
                        }
                    </div>
                </li>
            `;
        }).join('');
        return;
    }

    /* 여기 부분 썸네일, 가격 수정함 */
    const items = Array.isArray(savedItemState[flightSavedDrawerTab]) ? savedItemState[flightSavedDrawerTab] : [];
    listEl.innerHTML = '';
    emptyEl.style.display = items.length ? 'none' : 'block';
    emptyEl.textContent = flightSavedDrawerTab === 'wishlist' ? '위시리스트 항목이 없습니다.' : '장바구니 항목이 없습니다.';
    items.forEach((item) => {
        // home.js의 homeSavedItemHtml 구조 참고
        const itemType = String(item?.item_type || '').toLowerCase();
        let thumb =
            item?.payload?.thumb_url ||
            item?.payload?.image_url ||
            item?.payload?.image ||
            item?.payload?.photo_url ||
            item?.payload?.photo ||
            item?.payload?.thumbnail ||
            item?.image_url ||
            item?.image ||
            '';
        if (!thumb) {
            if (itemType === 'flight') {
                thumb = getAirlineLogoUrl(item?.payload?.airline_code || '');
            } else {
                thumb = '/static/image/noimg.png';
            }
        }
        const kind = `${getSavedItemTypeLabel(item?.item_type)} · ${item?.source || 'saved-item'}`;
        // meta: '₩123,000 | 출발 ...' 또는 '35,000~ | 체코 · 프라하' 형태 지원
        const normalizeKrwPriceText = (raw) => {
            const txt = String(raw || '').trim();
            if (!txt) return '';
            const m = txt.match(/([\d,]+(?:\.\d+)?)/);
            if (!m) return '';
            const n = Number(String(m[1]).replace(/,/g, ''));
            if (!Number.isFinite(n) || n <= 0) return '';
            return `₩${Math.floor(n).toLocaleString('ko-KR')}`;
        };
        let normalizedPrice = '';
        let lines = [];
        if (item.meta) {
            const parts = String(item.meta).split('|').map((x) => x.trim()).filter(Boolean);
            const detected = parts.find((p) => normalizeKrwPriceText(p));
            normalizedPrice = normalizeKrwPriceText(detected || '');
            lines = parts.filter((p) => p !== detected).slice(0, 3);
        }
        if (!normalizedPrice) {
            normalizedPrice = normalizeKrwPriceText(
                item?.price ||
                item?.payload?.price_text ||
                item?.payload?.price ||
                item?.payload?.amount ||
                item?.payload?.total_price ||
                ''
            );
        }
        const li = document.createElement('li');
        li.className = 'flight-saved-item';
        li.innerHTML = `
            <div class="flight-saved-thumb">
                ${thumb ? `<img src="${escapeHtml(thumb)}" alt="썸네일" loading="lazy">` : ''}
            </div>
            <div class="flight-saved-item__meta">
                <div class="flight-saved-item__type">${escapeHtml(kind)}</div>
                <div class="flight-saved-item__name">${escapeHtml(item.name || '-')}</div>
                ${normalizedPrice ? `<div class="flight-saved-line flight-saved-price">${escapeHtml(normalizedPrice)}</div>` : ''}
                ${lines.map(line => `<div class="flight-saved-line">${escapeHtml(line)}</div>`).join('')}
            </div>
            <button type="button" class="flight-saved-item__remove" data-flight-saved-remove="${item.id}" title="삭제">×</button>
        `;
        listEl.appendChild(li);
    });
}

function initFlightSavedDrawer() {
    const fab = document.getElementById('flightSavedFab');
    const drawer = document.getElementById('flightSavedDrawer');
    const listEl = document.getElementById('flightSavedList');
    if (!fab || !drawer) return;
    fab.addEventListener('click', () => {
        setFlightSavedDrawer(!drawer.classList.contains('is-open'));
        if (drawer.classList.contains('is-open')) {
            loadFlightAlerts().then(renderFlightSavedDrawer);
        }
    });
    document.querySelectorAll('[data-flight-saved-close]').forEach((el) => {
        el.addEventListener('click', () => setFlightSavedDrawer(false));
    });
    document.querySelectorAll('[data-flight-saved-tab]').forEach((btn) => {
        btn.addEventListener('click', () => {
            flightSavedDrawerTab = btn.getAttribute('data-flight-saved-tab') || 'cart';
            if (flightSavedDrawerTab === 'alerts') {
                loadFlightAlerts().then(renderFlightSavedDrawer);
                return;
            }
            renderFlightSavedDrawer();
        });
    });
    listEl?.addEventListener('click', async (e) => {
        const alertBtn = e.target.closest('[data-flight-alert-action]');
        if (alertBtn) {
            const requestId = Number(alertBtn.getAttribute('data-flight-alert-id'));
            const action = String(alertBtn.getAttribute('data-flight-alert-action') || '');
            if (!requestId || !action) return;
            try {
                await decideFlightAlert(requestId, action);
                await loadFlightAlerts();
                renderFlightSavedDrawer();
            } catch (err) {
                alert(err?.message || '요청 처리 중 오류가 발생했습니다.');
            }
            return;
        }
        const alertRemoveBtn = e.target.closest('[data-flight-alert-remove]');
        if (alertRemoveBtn) {
            const requestId = Number(alertRemoveBtn.getAttribute('data-flight-alert-remove'));
            if (!requestId) return;
            try {
                const res = await fetch(`/api/group-buy/join-requests/${requestId}`, { method: 'DELETE', credentials: 'include' });
                if (!res.ok) {
                    const d = await res.json().catch(() => ({}));
                    throw new Error(d?.detail || `HTTP ${res.status}`);
                }
                await loadFlightAlerts();
                renderFlightSavedDrawer();
            } catch (err) {
                alert(err?.message || '알림 삭제 중 오류가 발생했습니다.');
            }
            return;
        }
        const btn = e.target.closest('[data-flight-saved-remove]');
        if (!btn) return;
        const itemId = Number(btn.getAttribute('data-flight-saved-remove'));
        if (Number.isNaN(itemId)) return;
        try {
            await savedItemsApi(`/api/saved-items/${itemId}`, { method: 'DELETE', headers: {} });
            savedItemState[flightSavedDrawerTab] = (savedItemState[flightSavedDrawerTab] || []).filter((x) => Number(x.id) !== itemId);
            renderFlightSavedDrawer();
            rerenderCurrentFlightResults();
        } catch (err) {
            if (err?.code === 'LOGIN_REQUIRED') return requireLoginMessage();
            alert(err?.message || '삭제 중 오류가 발생했습니다.');
        }
    });
    window.addEventListener('focus', () => {
        if (drawer.classList.contains('is-open')) {
            loadFlightAlerts().then(renderFlightSavedDrawer);
        }
    });
    renderFlightSavedDrawer();
}

function buildFlightSavedItemPayload(offer, airline) {
    const itineraries = Array.isArray(offer?.itineraries) ? offer.itineraries : [];
    const firstSeg = itineraries?.[0]?.segments?.[0] || {};
    const outboundItin = itineraries?.[0] || {};
    const outboundSegs = Array.isArray(outboundItin?.segments) ? outboundItin.segments : [];
    const outboundLastSeg = outboundSegs[outboundSegs.length - 1] || {};
    const depCode = firstSeg?.departure?.iataCode || '';
    const arrCode = outboundLastSeg?.arrival?.iataCode || '';
    const depAt = firstSeg?.departure?.at || '';
    const arrAt = outboundLastSeg?.arrival?.at || '';
    const priceLabel = getDisplayPrice(offer);
    const routeLabel = `${depCode} → ${arrCode}`.trim();
    const name = `${airline?.name || '항공권'} ${routeLabel}`.trim();
    const meta = [priceLabel, depAt ? `출발 ${depAt.replace('T', ' ')}` : '', arrAt ? `도착 ${arrAt.replace('T', ' ')}` : '']
        .filter(Boolean)
        .join(' | ');
    // 썸네일(항공사 로고) URL 추가
    const thumb_url = getAirlineLogoUrl(airline.code);
    return {
        item_type: 'flight',
        name,
        meta,
        source: 'airport-search',
        payload: {
            airline: airline?.name || '',
            airline_code: airline?.code || '',
            price: offer?.price || {},
            itineraries,
            travelerPricings: offer?.travelerPricings || [],
            baggage_summary: extractBaggageSummary(offer),
            baggage_options: extractChargeableBaggageOptions(offer),
            thumb_url, // 추가
        },
    };
}

function extractBaggageSummary(offer) {
    const tps = Array.isArray(offer?.travelerPricings) ? offer.travelerPricings : [];
    let maxQty = 0;
    let maxWeight = 0;
    let weightUnit = '';
    tps.forEach((tp) => {
        const fds = Array.isArray(tp?.fareDetailsBySegment) ? tp.fareDetailsBySegment : [];
        fds.forEach((fd) => {
            const bag = fd?.includedCheckedBags || {};
            const qty = Number(bag?.quantity || 0);
            if (Number.isFinite(qty) && qty > maxQty) maxQty = qty;
            const weight = Number(bag?.weight || 0);
            const unit = String(bag?.weightUnit || '').toUpperCase();
            if (Number.isFinite(weight) && weight > maxWeight) {
                maxWeight = weight;
                weightUnit = unit || weightUnit;
            }
        });
    });
    if (maxWeight > 0) {
        return `위탁수하물 ${maxWeight}${weightUnit || 'KG'}${maxQty > 0 ? ` ${maxQty}개` : ''}`;
    }
    if (maxQty > 0) {
        return `위탁수하물 ${maxQty}개`;
    }
    return '';
}

function extractChargeableBaggageOptions(offer) {
    const out = [];
    const seen = new Set();

    const toNum = (v) => {
        const n = Number(String(v ?? '').replace(/[^\d.]/g, ''));
        return Number.isFinite(n) ? n : null;
    };

    const pickPrice = (node) => {
        if (!node || typeof node !== 'object') return null;
        const direct = toNum(node.amount ?? node.total ?? node.price ?? node.value);
        if (direct !== null) return direct;
        if (node.price && typeof node.price === 'object') {
            const nested = toNum(node.price.amount ?? node.price.total ?? node.price.value);
            if (nested !== null) return nested;
        }
        return null;
    };

    const pushOpt = (qty, price, weight, unit) => {
        const q = Number(qty || 0);
        const p = Number(price || 0);
        if (!Number.isFinite(q) || q <= 0 || !Number.isFinite(p) || p <= 0) return;
        const uw = Number(weight || 0);
        const uu = String(unit || '').toUpperCase();
        const weightText = uw > 0 ? ` · ${uw}${uu || 'KG'}` : '';
        const label = `${q}개 추가${weightText}`;
        const key = `${q}|${p}|${uw}|${uu}`;
        if (seen.has(key)) return;
        seen.add(key);
        out.push({ label, price: Math.round(p) });
    };

    const tps = Array.isArray(offer?.travelerPricings) ? offer.travelerPricings : [];
    tps.forEach((tp) => {
        const as = tp?.additionalServices || {};
        const ccb = as?.chargeableCheckedBags;
        const ccbList = Array.isArray(ccb) ? ccb : (ccb ? [ccb] : []);
        ccbList.forEach((x) => {
            pushOpt(x?.quantity, pickPrice(x), x?.weight, x?.weightUnit);
        });

        const fds = Array.isArray(tp?.fareDetailsBySegment) ? tp.fareDetailsBySegment : [];
        fds.forEach((fd) => {
            const cb = fd?.chargeableCheckedBags;
            const cbList = Array.isArray(cb) ? cb : (cb ? [cb] : []);
            cbList.forEach((x) => {
                pushOpt(x?.quantity, pickPrice(x), x?.weight, x?.weightUnit);
            });
        });
    });

    out.sort((a, b) => (a.price || 0) - (b.price || 0));
    return out;
}

function goFlightDetailFromSavedPayload(savedPayload) {
    const payload = savedPayload?.payload || {};
    const itineraries = Array.isArray(payload?.itineraries) ? payload.itineraries : [];
    const out = itineraries?.[0] || {};
    const inn = itineraries?.[1] || {};
    const outSegs = Array.isArray(out?.segments) ? out.segments : [];
    const inSegs = Array.isArray(inn?.segments) ? inn.segments : [];
    const first = outSegs[0] || {};
    const last = outSegs[outSegs.length - 1] || {};
    const rfirst = inSegs[0] || {};
    const rlast = inSegs[inSegs.length - 1] || {};
    const depCode = first?.departure?.iataCode || '';
    const arrCode = last?.arrival?.iataCode || '';
    const routeText = `${depCode} → ${arrCode}`.trim();
    const durationText = out?.duration || '';
    const depAt = String(first?.departure?.at || '');
    const arrAt = String(last?.arrival?.at || '');
    const depTerminal = String(first?.departure?.terminal || '');
    const arrTerminal = String(last?.arrival?.terminal || '');
    const flightNo = `${String(first?.carrierCode || '')}${String(first?.number || '')}`.trim();
    const aircraft = String(first?.aircraft?.code || '');
    const retDepCode = rfirst?.departure?.iataCode || '';
    const retArrCode = rlast?.arrival?.iataCode || '';
    const retRouteText = `${retDepCode} → ${retArrCode}`.trim();
    const retDurationText = inn?.duration || '';
    const retDepAt = String(rfirst?.departure?.at || '');
    const retArrAt = String(rlast?.arrival?.at || '');
    const retDepTerminal = String(rfirst?.departure?.terminal || '');
    const retArrTerminal = String(rlast?.arrival?.terminal || '');
    const retFlightNo = `${String(rfirst?.carrierCode || '')}${String(rfirst?.number || '')}`.trim();
    const retAircraft = String(rfirst?.aircraft?.code || '');
    const tps = Array.isArray(payload?.travelerPricings) ? payload.travelerPricings : [];
    let cabin = '';
    let retCabin = '';
    for (const tp of tps) {
        const fds = Array.isArray(tp?.fareDetailsBySegment) ? tp.fareDetailsBySegment : [];
        if (fds[0]?.cabin && !cabin) cabin = String(fds[0].cabin);
        if (fds[1]?.cabin && !retCabin) retCabin = String(fds[1].cabin);
        if (cabin && retCabin) break;
    }
    if (!retCabin) {
        for (const tp of tps) {
            const fds = Array.isArray(tp?.fareDetailsBySegment) ? tp.fareDetailsBySegment : [];
            for (const fd of fds) {
                if (fd?.cabin) {
                    retCabin = String(fd.cabin);
                    break;
                }
            }
            if (retCabin) break;
        }
    }
    const priceObj = payload?.price || {};
    const priceText = String(priceObj?.krwTotal || priceObj?.total || '');
    const priceBase = String(priceObj?.base || '');
    const priceTotal = String(priceObj?.total || '');
    const priceGrand = String(priceObj?.grandTotal || '');
    const currency = String(priceObj?.currency || (priceObj?.krwTotal ? 'KRW' : '')).toUpperCase();
    const baggage = String(payload?.baggage_summary || '');
    const baggageOpts = Array.isArray(payload?.baggage_options) ? payload.baggage_options : [];

    const checkoutRef = `flt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    try {
        sessionStorage.setItem(`flight_checkout_${checkoutRef}`, JSON.stringify(savedPayload || {}));
    } catch (_e) {}

    const qs = new URLSearchParams({
        airline: String(payload?.airline || ''),
        dep: depCode,
        arr: arrCode,
        route: routeText,
        duration: durationText,
        price: priceText,
        price_base: priceBase,
        price_total: priceTotal,
        price_grand: priceGrand,
        currency,
        baggage,
        baggage_opts: JSON.stringify(baggageOpts),
        dep_at: depAt,
        arr_at: arrAt,
        dep_terminal: depTerminal,
        arr_terminal: arrTerminal,
        flight_no: flightNo,
        aircraft,
        cabin,
        ret_route: retRouteText,
        ret_duration: retDurationText,
        ret_dep: retDepCode,
        ret_arr: retArrCode,
        ret_dep_at: retDepAt,
        ret_arr_at: retArrAt,
        ret_dep_terminal: retDepTerminal,
        ret_arr_terminal: retArrTerminal,
        ret_flight_no: retFlightNo,
        ret_aircraft: retAircraft,
        ret_cabin: retCabin,
        checkout_ref: checkoutRef,
        round: itineraries.length > 1 ? '1' : '0',
    });
    window.location.href = `/flight-detail?${qs.toString()}`;
}

function initFlightSavedItemActions() {
    const mount = document.getElementById('flightResultsMount');
    if (!mount || mount.dataset.savedActionsBound === '1') return;
    mount.dataset.savedActionsBound = '1';
    mount.addEventListener('click', async (e) => {
        const heartBtn = e.target.closest('.flight-heart-btn');
        const cartBtn = e.target.closest('.flight-select-btn[data-save-payload]');
        const payBtn = e.target.closest('.flight-pay-btn[data-save-payload]');
        const btn = heartBtn || cartBtn || payBtn;
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();

        let payload;
        try {
            payload = JSON.parse(decodeURIComponent(btn.getAttribute('data-save-payload') || ''));
        } catch (_err) {
            alert('항목 정보를 읽지 못했습니다.');
            return;
        }
        if (payBtn) {
            goFlightDetailFromSavedPayload(payload);
            return;
        }
        const listType = heartBtn ? 'wishlist' : 'cart';
        try {
            await savedItemsApi('/api/saved-items', {
                method: 'POST',
                body: JSON.stringify({ ...payload, list_type: listType }),
            });
            await loadSavedItems();
            renderFlightSavedDrawer();
            if (cartBtn) {
                btn.textContent = '담김';
                setFlightSavedDrawer(true);
            }
        } catch (err) {
            if (err?.code === 'LOGIN_REQUIRED') {
                requireLoginMessage();
                return;
            }
            alert(err?.message || '저장 중 오류가 발생했습니다.');
        }
    });
}

function setTripType(type) {
    closeAllPopovers();
    activeInputId = null;
    currentTripType = type;
    document.querySelectorAll('.flight-tab-btn').forEach((btn) => {
        btn.classList.remove('active');
        if ((btn.getAttribute('onclick') || '').includes(type)) btn.classList.add('active');
    });
    const addBtn = document.getElementById('addSegmentBtn');
    if (addBtn) addBtn.style.display = type === 'multi' ? 'flex' : 'none';
    renderForm();
}

function initFlightSortControls() {
    const sortBar = document.getElementById('flightSortBar');
    if (!sortBar) return;
    sortBar.addEventListener('click', (e) => {
        const btn = e.target.closest('.flight-sort-btn');
        if (!btn) return;
        const nextSort = btn.getAttribute('data-sort') || 'price';
        setFlightSort(nextSort);
    });
    updateFlightSortButtons();
}

function setFlightSort(sortKey) {
    flightSortState = ['price', 'duration', 'departure'].includes(sortKey) ? sortKey : 'price';
    updateFlightSortButtons();
    rerenderCurrentFlightResults();
}

function updateFlightSortButtons() {
    document.querySelectorAll('.flight-sort-btn').forEach((btn) => {
        btn.classList.toggle('is-active', btn.getAttribute('data-sort') === flightSortState);
    });
}

function rerenderCurrentFlightResults() {
    const resultDiv = document.getElementById('flightResultArea');
    const payload = resultDiv?._flightRenderPayload;
    if (!resultDiv || !payload) return;
    if (payload.type === 'multi') {
        renderMultiFlightResults(payload.dataList, payload.legs);
        return;
    }
    if (payload.type === 'single') {
        renderFlightResults(payload.data);
    }
}

function renderForm() {
    const container = document.getElementById('flightForm');
    if (!container) return;
    container.innerHTML = '';

    const cabinReverseMap = {
        ECONOMY: '일반석',
        BUSINESS: '프레스티지',
        FIRST: '일등석',
    };
    const passValue = `성인 ${passengerState.adult}${passengerState.child > 0 ? `, 소아 ${passengerState.child}` : ''}${passengerState.infant > 0 ? `, 유아 ${passengerState.infant}` : ''}, ${cabinReverseMap[passengerState.cabin] || passengerState.cabin}`;

    if (currentTripType === 'multi') {
        segments.forEach((seg, index) => {
            const row = document.createElement('div');
            row.className = 'flight-row';
            row.innerHTML = `
                <div class="input-group" onclick="openAirportPopover('seg-${index}-dep')">
                    <label>출발지</label>
                    <input type="text" id="seg-${index}-dep" value="${seg.dep}" readonly placeholder="도시/공항">
                </div>
                <div class="swap-btn" style="transform: rotate(90deg); border:none;"><i data-lucide="plane" width="18"></i></div>
                <div class="input-group" onclick="openAirportPopover('seg-${index}-arr')">
                    <label>도착지</label>
                    <input type="text" id="seg-${index}-arr" value="${seg.arr}" readonly placeholder="도시/공항">
                </div>
                <div class="input-group" style="flex: 0.6;"><label>날짜</label><input type="date" id="seg-${index}-date" value="${seg.date || ''}"></div>
                ${segments.length > 2 ? `<button type="button" class="remove-segment-btn" onclick="removeSegment(${index})">&times;</button>` : ''}
            `;
            container.appendChild(row);
            const dateInput = row.querySelector(`#seg-${index}-date`);
            if (dateInput) {
                dateInput.addEventListener('change', (e) => {
                    segments[index].date = e.target.value || '';
                });
                dateInput.addEventListener('input', (e) => {
                    segments[index].date = e.target.value || '';
                });
            }
        });

        const bottomRow = document.createElement('div');
        bottomRow.className = 'flight-row';
        bottomRow.innerHTML = `
            <div class="input-group" onclick="openPassengerPopover()" style="width:100%">
                <label>인원 및 좌석</label>
                <input type="text" id="pass-input" value="${passValue}" readonly>
            </div>
        `;
        container.appendChild(bottomRow);
    } else {
        const row = document.createElement('div');
        row.className = 'flight-row';
        row.innerHTML = `
            <div class="input-group" onclick="openAirportPopover('main-dep')">
                <label>출발지</label>
                <input type="text" id="main-dep" value="${mainSearchState.dep || ''}" readonly>
            </div>
            <button type="button" class="swap-btn" onclick="swapMainLocations(event)"><i data-lucide="arrow-right-left" width="16"></i></button>
            <div class="input-group" onclick="openAirportPopover('main-arr')">
                <label>도착지</label>
                <input type="text" id="main-arr" value="${mainSearchState.arr || ''}" readonly placeholder="어디로 떠나시나요?">
            </div>
            <div class="input-group"><label>출발일</label><input type="date" id="main-dep-date" value="${mainSearchState.departureDate || ''}"></div>
            ${currentTripType === 'round' ? `<div class="input-group"><label>오는 날</label><input type="date" id="main-return-date" value="${mainSearchState.returnDate || ''}"></div>` : ''}
            <div class="input-group" onclick="openPassengerPopover()">
                <label>인원 및 좌석</label>
                <input type="text" id="pass-input" value="${passValue}" readonly>
            </div>
        `;
        container.appendChild(row);
        const depDateInput = row.querySelector('#main-dep-date');
        if (depDateInput) {
            depDateInput.addEventListener('change', (e) => {
                mainSearchState.departureDate = e.target.value || '';
            });
            depDateInput.addEventListener('input', (e) => {
                mainSearchState.departureDate = e.target.value || '';
            });
        }
        const returnDateInput = row.querySelector('#main-return-date');
        if (returnDateInput) {
            returnDateInput.addEventListener('change', (e) => {
                mainSearchState.returnDate = e.target.value || '';
            });
            returnDateInput.addEventListener('input', (e) => {
                mainSearchState.returnDate = e.target.value || '';
            });
        }
    }
    initIcons();
}

function setAirportValue(targetId, value) {
    if (!targetId) return;
    const el = document.getElementById(targetId);
    if (el) el.value = value;

    if (targetId === 'main-dep') {
        mainSearchState.dep = value;
        return;
    }
    if (targetId === 'main-arr') {
        mainSearchState.arr = value;
        return;
    }
    const match = targetId.match(/^seg-(\d+)-(dep|arr)$/);
    if (!match) return;
    const idx = Number(match[1]);
    const key = match[2];
    if (!Number.isNaN(idx) && segments[idx]) {
        segments[idx][key] = value;
    }
}

function syncCurrentFormStateFromDom() {
    if (currentTripType === 'multi') {
        segments.forEach((seg, index) => {
            seg.dep = document.getElementById(`seg-${index}-dep`)?.value || seg.dep || '';
            seg.arr = document.getElementById(`seg-${index}-arr`)?.value || seg.arr || '';
            seg.date = document.getElementById(`seg-${index}-date`)?.value || seg.date || '';
        });
        return;
    }
    mainSearchState.dep = document.getElementById('main-dep')?.value || mainSearchState.dep || '';
    mainSearchState.arr = document.getElementById('main-arr')?.value || mainSearchState.arr || '';
    mainSearchState.departureDate = document.getElementById('main-dep-date')?.value || mainSearchState.departureDate || '';
    mainSearchState.returnDate = document.getElementById('main-return-date')?.value || mainSearchState.returnDate || '';
}

function openAirportPopover(targetId) {
    activeInputId = targetId;
    document.getElementById('airportPopover').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function openPassengerPopover() {
    document.getElementById('passengerPopover').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function closeAllPopovers() {
    document.querySelectorAll('.popover').forEach((p) => p.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
    updatePassInput();
}

function updateCount(type, delta) {
    const newVal = passengerState[type] + delta;
    if (type === 'adult' && newVal < 1) return;
    if (newVal < 0) return;
    if (passengerState.adult + passengerState.child + passengerState.infant + delta > 9) {
        alert('최대 9명까지 선택 가능합니다.');
        return;
    }

    passengerState[type] = newVal;
    const el = document.getElementById(`count-${type}`);
    if (el) el.textContent = newVal;
    updatePassInput();
}

function updateCabin(val) {
    const cabinMap = {
        '일반석': 'ECONOMY',
        '프레스티지': 'BUSINESS',
        '일등석': 'FIRST',
    };
    passengerState.cabin = cabinMap[val] || val;
    updatePassInput();
}

function updatePassInput() {
    const input = document.getElementById('pass-input');
    if (!input) return;
    let text = `성인 ${passengerState.adult}`;
    if (passengerState.child > 0) text += `, 소아 ${passengerState.child}`;
    if (passengerState.infant > 0) text += `, 유아 ${passengerState.infant}`;
    const cabinReverseMap = {
        ECONOMY: '일반석',
        BUSINESS: '프레스티지',
        FIRST: '일등석',
    };
    text += `, ${cabinReverseMap[passengerState.cabin] || passengerState.cabin}`;
    input.value = text;
}

function initAirportPopover() {
    const tabs = document.getElementById('airportRegionTabs');
    if (!tabs) return;
    tabs.innerHTML = '';
    Object.keys(airportData).forEach((region, i) => {
        const btn = document.createElement('button');
        btn.className = `popover-tab ${i === 0 ? 'active' : ''}`;
        btn.textContent = region;
        btn.onclick = (e) => {
            document.querySelectorAll('.popover-tab').forEach((t) => t.classList.remove('active'));
            e.target.classList.add('active');
            renderAirportList(region);
        };
        tabs.appendChild(btn);
        if (i === 0) renderAirportList(region);
    });
}

function renderAirportList(region) {
    const list = document.getElementById('airportList');
    if (!list || !airportData[region]) return;
    list.innerHTML = '';
    airportData[region].forEach((ap) => {
        const div = document.createElement('div');
        div.className = 'airport-item';
        div.innerHTML = `<div><span class="airport-name">${ap.name}</span><span class="airport-country">${ap.country}</span></div><span class="airport-code">${ap.code}</span>`;
        div.onclick = () => {
            if (activeInputId) setAirportValue(activeInputId, `${ap.name} (${ap.code})`);
            closeAllPopovers();
        };
        list.appendChild(div);
    });
}

function filterAirports() {
    const input = document.getElementById('airportSearchInput');
    const list = document.getElementById('airportList');
    if (!input || !list) return;
    const keyword = (input.value || '').toLowerCase();
    list.querySelectorAll('.airport-item').forEach((item) => {
        item.style.display = item.textContent.toLowerCase().includes(keyword) ? '' : 'none';
    });
}

function swapMainLocations(e) {
    e.stopPropagation();
    const d = document.getElementById('main-dep');
    const a = document.getElementById('main-arr');
    if (!d || !a) return;
    const t = d.value;
    d.value = a.value;
    a.value = t;
    mainSearchState.dep = d.value || '';
    mainSearchState.arr = a.value || '';
}

function addMultiCitySegment() {
    segments.push({ id: Date.now(), dep: '', arr: '', date: '' });
    renderForm();
}

function removeSegment(i) {
    segments.splice(i, 1);
    renderForm();
}

function extractIata(value) {
    if (!value) return '';
    return value.match(/\((\w{3})\)/)?.[1] || value.trim();
}

async function fetchFlightSearch({ origin, destination, departure_date, return_date = '' }) {
    const adults = passengerState.adult;
    const child = passengerState.child;
    const infant = passengerState.infant;
    const cabin = passengerState.cabin;

    const params = new URLSearchParams({
        origin,
        destination,
        departure_date,
        adults: String(adults),
        child: String(child),
        infant: String(infant),
        cabin,
    });
    if (return_date) params.set('return_date', return_date);

    const res = await fetch(`/api/flight-search?${params.toString()}`);
    if (!res.ok) {
        const body = await res.text();
        throw new Error(body || '검색 실패');
    }
    return res.json();
}

async function performSearch() {
    closeAllPopovers();
    syncCurrentFormStateFromDom();

    let resultDiv = document.getElementById('flightResultArea');
    if (resultDiv) resultDiv.innerHTML = '';
    showFlightLoading();

    try {
        if (currentTripType === 'multi') {
            const legs = [];
            for (let i = 0; i < segments.length; i += 1) {
                const depVal = document.getElementById(`seg-${i}-dep`)?.value || '';
                const arrVal = document.getElementById(`seg-${i}-arr`)?.value || '';
                const dateVal = document.getElementById(`seg-${i}-date`)?.value || '';
                const origin = extractIata(depVal);
                const destination = extractIata(arrVal);
                if (!origin || !destination || !dateVal) {
                    alert(`${i + 1}구간의 출발지/도착지/날짜를 모두 입력해 주세요.`);
                    return;
                }
                legs.push({ origin, destination, departure_date: dateVal });
            }

            const responses = await Promise.all(
                legs.map((leg) =>
                    fetchFlightSearch({
                        origin: leg.origin,
                        destination: leg.destination,
                        departure_date: leg.departure_date,
                    }),
                ),
            );
            renderMultiFlightResults(responses, legs);
            return;
        }

        const origin = extractIata(document.getElementById('main-dep')?.value || '');
        const destination = extractIata(document.getElementById('main-arr')?.value || '');
        const departure_date = document.getElementById('main-dep-date')?.value || '';
        const return_date = currentTripType === 'round' ? (document.getElementById('main-return-date')?.value || '') : '';
        if (!origin || !destination || !departure_date) {
            alert('출발지, 도착지, 날짜를 모두 입력해 주세요.');
            return;
        }
        if (currentTripType === 'round' && !return_date) {
            alert('왕복 검색은 오는 날을 입력해 주세요.');
            return;
        }

        const data = await fetchFlightSearch({
            origin,
            destination,
            departure_date,
            return_date: currentTripType === 'round' ? return_date : '',
        });
        renderFlightResults(data);
    } catch (e) {
        renderFlightError(e.message);
    }
}

function showFlightLoading() {
    const resultDiv = ensureFlightResultArea();
    resultDiv._flightRenderPayload = null;
    resultDiv.innerHTML = '<div class="flight-loading">항공편을 검색 중입니다...</div>';
}

function ensureFlightResultArea() {
    let resultDiv = document.getElementById('flightResultArea');
    if (resultDiv) return resultDiv;

    resultDiv = document.createElement('div');
    resultDiv.id = 'flightResultArea';

    const mount = document.getElementById('flightResultsMount');
    if (mount) {
        mount.appendChild(resultDiv);
    } else {
        document.querySelector('.search-widget')?.appendChild(resultDiv);
    }
    return resultDiv;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatKrw(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    return `₩${new Intl.NumberFormat('ko-KR').format(Math.round(Number(value)))}`;
}

function formatTime(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return '-';
    return d.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function formatDuration(duration) {
    if (!duration || typeof duration !== 'string') return '-';
    const m = duration.match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
    if (!m) return duration;
    const h = Number(m[1] || 0);
    const min = Number(m[2] || 0);
    if (h && min) return `${h}시간 ${min}분`;
    if (h) return `${h}시간`;
    return `${min}분`;
}

function durationMinutesFromIso(duration) {
    if (!duration || typeof duration !== 'string') return Number.MAX_SAFE_INTEGER;
    const m = duration.match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
    if (!m) return Number.MAX_SAFE_INTEGER;
    return (Number(m[1] || 0) * 60) + Number(m[2] || 0);
}

function getOfferPriceValue(offer) {
    return Number(offer?.price?.krwTotal || offer?.price?.total || Number.MAX_SAFE_INTEGER);
}

function getOfferDurationValue(offer) {
    const itineraries = Array.isArray(offer?.itineraries) ? offer.itineraries : [];
    if (!itineraries.length) return Number.MAX_SAFE_INTEGER;
    let total = 0;
    let hasValid = false;
    itineraries.forEach((it) => {
        const mins = durationMinutesFromIso(it?.duration);
        if (Number.isFinite(mins) && mins < Number.MAX_SAFE_INTEGER) {
            total += mins;
            hasValid = true;
        }
    });
    return hasValid ? total : Number.MAX_SAFE_INTEGER;
}

function getOfferFirstDepartureValue(offer) {
    const dep = offer?.itineraries?.[0]?.segments?.[0]?.departure?.at;
    const ts = dep ? new Date(dep).getTime() : Number.NaN;
    return Number.isNaN(ts) ? Number.MAX_SAFE_INTEGER : ts;
}

function sortOffersForDisplay(results) {
    const rows = [...(Array.isArray(results) ? results : [])];
    const sortKey = flightSortState || 'price';
    rows.sort((a, b) => {
        const aPrice = getOfferPriceValue(a);
        const bPrice = getOfferPriceValue(b);
        const aDur = getOfferDurationValue(a);
        const bDur = getOfferDurationValue(b);
        const aDep = getOfferFirstDepartureValue(a);
        const bDep = getOfferFirstDepartureValue(b);

        if (sortKey === 'duration') {
            return (aDur - bDur) || (aPrice - bPrice) || (aDep - bDep);
        }
        if (sortKey === 'departure') {
            return (aDep - bDep) || (aPrice - bPrice) || (aDur - bDur);
        }
        // price default
        return (aPrice - bPrice) || (aDur - bDur) || (aDep - bDep);
    });
    return rows;
}

function buildStopLabel(itinerary) {
    const segs = itinerary?.segments || [];
    const stops = Math.max(segs.length - 1, 0);
    if (stops === 0) return '직항';
    if (stops === 1) return '1회 경유';
    return `${stops}회 경유`;
}

const AIRLINE_NAMES = {
    KE: '대한항공',
    OZ: '아시아나항공',
    JL: '일본항공',
    NH: '전일본공수',
    '7C': '제주항공',
    TW: '티웨이항공',
    BX: '에어부산',
    LJ: '진에어',
    RS: '에어서울',
    ZE: '이스타항공',
    SQ: '싱가포르항공',
    CX: '캐세이퍼시픽',
    TG: '타이항공',
    MU: '중국동방항공',
    FM: '상하이항공',
};

function getCarrierDict(data) {
    return data?.raw?.dictionaries?.carriers || {};
}

function getAirlineLogoUrl(code) {
    if (!code) return '';
    return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(code)}.png`;
}

function getAirlineDisplay(offer, carriers = {}) {
    const code =
        (offer?.validatingAirlineCodes && offer.validatingAirlineCodes[0]) ||
        offer?.itineraries?.[0]?.segments?.[0]?.carrierCode ||
        '-';
    const name = carriers[code] || AIRLINE_NAMES[code] || code;
    return { code, name };
}

function getDisplayPrice(offer) {
    if (offer?.price?.krwTotal) return formatKrw(offer.price.krwTotal);
    const amount = Number(offer?.price?.total);
    const cur = offer?.price?.currency || '';
    if (!Number.isNaN(amount) && cur === 'KRW') return formatKrw(amount);
    if (!Number.isNaN(amount)) return `${new Intl.NumberFormat('ko-KR').format(Math.round(amount))} ${cur}`;
    return '-';
}

function buildFlightCardsHtml(data) {
    const results = data && (data.results || data.data);
    if (!results || results.length === 0) {
        const apiErr = String(data?.raw?.amadeus_error || data?.amadeus_error || '').trim();
        if (apiErr) {
            return `<div class="flight-error">검색 결과가 없습니다. (${escapeHtml(apiErr)})</div>`;
        }
        return '<div class="flight-no-result">검색 결과가 없습니다.</div>';
    }
    const carriers = getCarrierDict(data);
    const sorted = sortOffersForDisplay(results);
    const isTestPricing = String(data?.pricing_mode || '').toLowerCase() === 'test';
    const pricingNotice = String(data?.pricing_notice || '').trim() || '테스트 요금(참고용)';

    let html = '';
    if (isTestPricing) {
        html += `<div class="flight-pricing-notice">${escapeHtml(pricingNotice)}: 실제 결제 단계에서 금액이 달라질 수 있습니다.</div>`;
    }
    html += '<div class="flight-result-list">';
    sorted.forEach((f) => {
        const itineraries = Array.isArray(f.itineraries) ? f.itineraries : [];
        const airline = getAirlineDisplay(f, carriers);
        const singleClass = itineraries.length <= 1 ? ' flight-card--single' : '';
        const savePayload = buildFlightSavedItemPayload(f, airline);
        const payloadAttr = escapeHtml(encodeURIComponent(JSON.stringify(savePayload)));
        const inWishlist = hasSavedItem('wishlist', savePayload);
        const inCart = hasSavedItem('cart', savePayload);
        html += `
            <article class="flight-card${singleClass}">
                <div class="flight-card-main">
                    <div class="flight-airline">
                        <div class="flight-airline-mark">
                            <img
                                class="flight-airline-logo"
                                src="${getAirlineLogoUrl(airline.code)}"
                                alt="${escapeHtml(airline.name)} 로고"
                                loading="lazy"
                                onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                            >
                            <div class="flight-airline-badge" style="display:none;">${escapeHtml(airline.code)}</div>
                        </div>
                        <div class="flight-airline-name">${escapeHtml(airline.name)}</div>
                    </div>
                    <div class="flight-leg-list">
                        ${itineraries.map((it) => renderItineraryLine(it)).join("")}
                    </div>
                </div>
                <aside class="flight-card-price">
                    <button
                        type="button"
                        class="flight-heart-btn ${inWishlist ? "is-active" : ""}"
                        data-save-payload="${payloadAttr}"
                        aria-label="위시리스트 담기"
                        title="위시리스트"
                    >♥</button>
                    <div class="flight-offer-count">총 ${itineraries.length}구간</div>
                    ${isTestPricing ? '<div class="flight-test-badge">TEST FARE</div>' : ''}
                    <div class="flight-price-main">${getDisplayPrice(f)}</div>
                    <div class="flight-card-actions">
                        <button type="button" class="flight-select-btn" data-save-payload="${payloadAttr}">${inCart ? "담김" : "장바구니"}</button>
                        <button type="button" class="flight-pay-btn" data-save-payload="${payloadAttr}">예약하기</button>
                    </div>
                </aside>
            </article>
        `;
    });
    html += '</div>';

    if (data.booking_reference && Array.isArray(data.booking_reference) && data.booking_reference.length > 0) {
        html += '<div class="flight-booking-ref"><h4>Booking.com 참고 항공권</h4>';
        data.booking_reference.forEach((f) => {
            const rawPrice = Number(f.price);
            const krwPrice = f.price_krw
                ? formatKrw(f.price_krw)
                : (!Number.isNaN(rawPrice) && f.currency === 'KRW' ? formatKrw(rawPrice) : null);
            html += `<div class="flight-result-item booking-ref">
                <div><b>${escapeHtml(f.validating_airline || '-')}</b> ${escapeHtml(f.flight_number || '')}</div>
                <div>${escapeHtml(f.origin || '')} → ${escapeHtml(f.destination || '')}</div>
                <div>출발: ${escapeHtml(f.departure_time || '')}</div>
                <div>도착: ${escapeHtml(f.arrival_time || '')}</div>
                <div>가격: <b>${krwPrice || `${escapeHtml(f.price || '')} ${escapeHtml(f.currency || '')}`}</b></div>
            </div>`;
        });
        html += '</div>';
    }

    return html;
}

function renderItineraryLine(itinerary) {
    const segs = itinerary?.segments || [];
    const first = segs[0] || {};
    const last = segs[segs.length - 1] || {};
    const stops = Math.max(segs.length - 1, 0);
    const depAt = first?.departure?.at;
    const arrAt = last?.arrival?.at;
    const depCode = first?.departure?.iataCode || '-';
    const arrCode = last?.arrival?.iataCode || '-';
    const viaCode = segs.length > 1 ? (segs[0]?.arrival?.iataCode || '') : '';
    const stopDetail = segs.length > 1 && viaCode ? `${buildStopLabel(itinerary)} ${viaCode}` : buildStopLabel(itinerary);
    const routePathCodes = segs.length
        ? [segs[0]?.departure?.iataCode, ...segs.map((s) => s?.arrival?.iataCode)]
            .filter(Boolean)
            .join(' → ')
        : `${depCode} → ${arrCode}`;
    return `
        <div class="flight-leg">
            <div class="flight-leg-time">
                <div class="flight-leg-clock">${formatTime(depAt)}</div>
                <div class="flight-leg-code">${escapeHtml(depCode)}</div>
            </div>
            <div class="flight-leg-middle">
                <div class="flight-leg-duration">${formatDuration(itinerary?.duration)}</div>
                <div class="flight-leg-line"></div>
                <div class="flight-leg-path">${escapeHtml(routePathCodes)}</div>
                <div class="flight-leg-stop">${escapeHtml(stopDetail)}</div>
            </div>
            <div class="flight-leg-time">
                <div class="flight-leg-clock">${formatTime(arrAt)}</div>
                <div class="flight-leg-code">${escapeHtml(arrCode)}</div>
            </div>
        </div>
    `;
}

function renderFlightResults(data) {
    const resultDiv = ensureFlightResultArea();
    resultDiv._flightRenderPayload = { type: 'single', data };
    resultDiv.innerHTML = buildFlightCardsHtml(data);
    initIcons();
}

function renderMultiFlightResults(dataList, legs) {
    const resultDiv = ensureFlightResultArea();
    resultDiv._flightRenderPayload = { type: 'multi', dataList, legs };
    let html = '<div class="flight-multi-result">';
    dataList.forEach((data, idx) => {
        const leg = legs[idx];
        html += `
            <section class="flight-multi-section">
                <h4 class="flight-multi-title">${idx + 1}구간: ${escapeHtml(leg.origin)} → ${escapeHtml(leg.destination)} (${escapeHtml(leg.departure_date)})</h4>
                ${buildFlightCardsHtml(data)}
            </section>
        `;
    });
    html += '</div>';
    resultDiv.innerHTML = html;
    initIcons();
}

function renderFlightError(msg) {
    const resultDiv = ensureFlightResultArea();
    resultDiv._flightRenderPayload = null;
    resultDiv.innerHTML = `<div class="flight-error">오류: ${escapeHtml(msg)}</div>`;
}
