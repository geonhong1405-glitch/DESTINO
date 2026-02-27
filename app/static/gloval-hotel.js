document.addEventListener('DOMContentLoaded', function () {
    if (window.lucide && lucide.createIcons) {
        lucide.createIcons();
    }

    const regionsData = {
        일본: ['도쿄', '오사카', '후쿠오카', '삿포로', '오키나와', '나고야', '교토', '고베'],
        동남아: ['방콕', '다낭', '나트랑', '세부', '발리', '싱가포르', '푸껫', '코타키나발루', '마닐라'],
        '홍콩/마카오/중국': ['홍콩', '마카오', '상하이', '베이징', '칭다오', '광저우'],
        남태평양: ['괌', '사이판', '시드니', '오클랜드', '멜버른', '골드코스트'],
        미주: ['하와이', '뉴욕', '로스앤젤레스', '라스베이거스', '샌프란시스코', '밴쿠버'],
        유럽: ['파리', '런던', '로마', '바르셀로나', '프라하', '인터라켄', '베네치아', '피렌체'],
        '중동/아프리카': ['두바이', '카이로', '케이프타운', '아부다비'],
    };

    const regionTabs = document.getElementById('regionTabs');
    const cityGrid = document.getElementById('cityGrid');
    const regionTitle = document.getElementById('selectedRegionTitle');
    const destInput = document.getElementById('destInput');

    function renderCities(region) {
        if (!regionTitle || !cityGrid) return;
        regionTitle.textContent = `${region} 주요 도시`;
        cityGrid.innerHTML = '';
        regionsData[region].forEach((city) => {
            const btn = document.createElement('button');
            btn.className = 'city-btn';
            btn.textContent = city;
            btn.onclick = function (e) {
                e.stopPropagation();
                if (destInput) destInput.value = `${city}, ${region}`;
                closeAllPopovers();
            };
            cityGrid.appendChild(btn);
        });
    }

    function initDestinations() {
        if (!regionTabs) return;
        let isFirst = true;
        for (const region in regionsData) {
            const btn = document.createElement('button');
            btn.className = `dest-tab ${isFirst ? 'active' : ''}`;
            btn.textContent = region;
            btn.onclick = function (e) {
                e.stopPropagation();
                document.querySelectorAll('.dest-tab').forEach((t) => t.classList.remove('active'));
                btn.classList.add('active');
                renderCities(region);
            };
            regionTabs.appendChild(btn);
            if (isFirst) {
                renderCities(region);
                isFirst = false;
            }
        }
    }

    const checkinInput = document.getElementById('checkinDate');
    const checkoutInput = document.getElementById('checkoutDate');
    const params = new URLSearchParams(window.location.search);
    const queryCity = (params.get('city') || '').trim();
    const queryCountry = (params.get('country') || '').trim();
    const queryCheckin = (params.get('checkin') || '').trim();
    const queryCheckout = (params.get('checkout') || '').trim();

    if (destInput && (queryCity || queryCountry)) {
        destInput.value = queryCountry ? `${queryCity}, ${queryCountry}` : queryCity;
    }

    if (checkinInput && checkoutInput) {
        if (queryCheckin) {
            checkinInput.value = queryCheckin;
        } else {
            const today = new Date();
            checkinInput.valueAsDate = today;
        }

        if (queryCheckout) {
            checkoutInput.value = queryCheckout;
        } else {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            checkoutInput.valueAsDate = tomorrow;
        }
    }

    let guests = { adult: 2, child: 0, room: 1 };

    function capitalize(s) {
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    function updateGuest(type, change) {
        if (window.event) window.event.stopPropagation();
        let newVal = guests[type] + change;
        if (type === 'adult' && newVal < 1) newVal = 1;
        if (type === 'child' && newVal < 0) newVal = 0;
        if (type === 'room' && newVal < 1) newVal = 1;
        guests[type] = newVal;

        const valElem = document.getElementById(`val${capitalize(type)}`);
        if (valElem) valElem.textContent = newVal;

        const guestInput = document.getElementById('guestInput');
        if (guestInput) guestInput.value = `성인 ${guests.adult}명, 아동 ${guests.child}명, 객실 ${guests.room}개`;

        const btnAdultMinus = document.getElementById('btnAdultMinus');
        const btnChildMinus = document.getElementById('btnChildMinus');
        const btnRoomMinus = document.getElementById('btnRoomMinus');
        if (btnAdultMinus) btnAdultMinus.disabled = guests.adult <= 1;
        if (btnChildMinus) btnChildMinus.disabled = guests.child <= 0;
        if (btnRoomMinus) btnRoomMinus.disabled = guests.room <= 1;
    }

    function openPopover(id) {
        closeAllPopovers();
        const popover = document.getElementById(id);
        const overlay = document.getElementById('widgetOverlay');
        if (popover) popover.classList.add('active');
        if (overlay) overlay.classList.add('active');
    }

    function closeAllPopovers() {
        document.querySelectorAll('.popover').forEach((p) => p.classList.remove('active'));
        const overlay = document.getElementById('widgetOverlay');
        if (overlay) overlay.classList.remove('active');
    }

    const searchBtn = document.querySelector('.btn-search');
    if (searchBtn) {
        searchBtn.addEventListener('click', function () {
            const dest = (document.getElementById('destInput')?.value || '').trim();
            let city = '';
            let country = '';
            if (dest.includes(',')) {
                const parts = dest.split(',');
                city = parts[0].trim();
                country = parts[1].trim();
            } else {
                city = dest;
            }

            const checkin = document.getElementById('checkinDate')?.value;
            const checkout = document.getElementById('checkoutDate')?.value;
            if (checkin && checkout) {
                const inDate = new Date(checkin);
                const outDate = new Date(checkout);
                if (!Number.isNaN(inDate.getTime()) && !Number.isNaN(outDate.getTime()) && outDate < inDate) {
                    alert('체크아웃 날짜는 체크인 이후여야 합니다.');
                    return;
                }
            }
            const params = new URLSearchParams();
            if (city) params.append('city', city);
            if (country) params.append('country', country);
            if (checkin) params.append('checkin', checkin);
            if (checkout) params.append('checkout', checkout);
            window.location.href = '/gloval-hotel?' + params.toString();
        });
    }

    initDestinations();
    window.updateGuest = updateGuest;
    window.openPopover = openPopover;
    window.closeAllPopovers = closeAllPopovers;
});


let hotelSavedState = { cart: [], wishlist: [] };
let hotelAlertState = [];
let hotelSavedTab = 'cart';
let hotelAuthState = { checkedAt: 0, loggedIn: false };

function hotelEscapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function parseHotelPayload(attr) {
    try {
        const row = JSON.parse(attr || '{}');
        return row && typeof row === 'object' ? row : null;
    } catch (_e) {
        return null;
    }
}

function hotelPayloadKey(payload) {
    const p = payload || {};
    const hotelId = String(p.hotel_id || '').trim();
    if (hotelId) return `hotel:${hotelId}|${String(p.checkin || '')}|${String(p.checkout || '')}`;
    return [
        String(p.name || '').trim().toLowerCase(),
        String(p.address || '').trim().toLowerCase(),
        String(p.checkin || '').trim(),
        String(p.checkout || '').trim(),
        String(p.price ?? '').trim(),
    ].join('|');
}

function hotelSavedRowKey(row) {
    if (!row) return '';
    const payload = row.payload && typeof row.payload === 'object' ? row.payload : {};
    if (String(row.item_type || '').toLowerCase() === 'hotel') return hotelPayloadKey(payload);
    return `${String(row.name || '').toLowerCase()}|${String(row.meta || '').toLowerCase()}`;
}

function formatHotelPriceText(payload) {
    const p = payload || {};
    const num = Number(p.price);
    const cur = String(p.currency || 'KRW').trim();
    if (Number.isFinite(num) && num > 0) return `${num.toLocaleString()} ${cur}`;
    const raw = String(p.price ?? '').trim();
    return raw ? `${raw} ${cur}` : '';
}

function buildHotelSavedPayload(raw, listType) {
    const payload = raw && typeof raw === 'object' ? raw : null;
    if (!payload || !payload.name) return null;
    const priceText = formatHotelPriceText(payload);
    const meta = [
        priceText,
        [payload.city, payload.country].filter(Boolean).join(', '),
        payload.checkin && payload.checkout ? `${payload.checkin} ~ ${payload.checkout}` : '',
    ].filter(Boolean).join(' | ');
    return {
        list_type: listType,
        item_type: 'hotel',
        name: String(payload.name || '').trim(),
        meta,
        source: String(payload.source || 'hotel'),
        payload,
    };
}

async function hotelSavedApi(path = '/api/saved-items', options = {}) {
    const res = await fetch(path, {
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    });
    if (res.status === 401) {
        const e = new Error('LOGIN_REQUIRED');
        e.code = 'LOGIN_REQUIRED';
        throw e;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
    return data;
}

async function loadHotelSavedState() {
    try {
        const data = await hotelSavedApi('/api/saved-items', { method: 'GET', headers: {} });
        hotelSavedState = {
            cart: Array.isArray(data?.cart) ? data.cart : [],
            wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
        };
    } catch (e) {
        if (e?.code !== 'LOGIN_REQUIRED') console.warn('hotel saved-items load failed', e);
        hotelSavedState = { cart: [], wishlist: [] };
    }
}

async function loadHotelAlerts() {
    try {
        const res = await fetch('/api/group-buy/join-requests/inbox', { credentials: 'include' });
        if (res.status === 401) {
            hotelAlertState = [];
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        hotelAlertState = Array.isArray(data) ? data : [];
    } catch (_e) {
        hotelAlertState = [];
    }
}

async function isHotelLoggedIn(force = false) {
    const now = Date.now();
    if (!force && now - Number(hotelAuthState.checkedAt || 0) < 5000) return !!hotelAuthState.loggedIn;
    try {
        const res = await fetch('/api/me', { credentials: 'include' });
        hotelAuthState = { checkedAt: now, loggedIn: res.ok };
        return res.ok;
    } catch (_e) {
        hotelAuthState = { checkedAt: now, loggedIn: false };
        return false;
    }
}

async function ensureHotelLoggedIn() {
    const ok = await isHotelLoggedIn(false);
    if (ok) return true;
    alert('로그인 후 이용 가능합니다.\\n확인을 누르면 로그인 페이지로 이동합니다.');
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?next=${next}`;
    return false;
}

function setHotelSavedDrawer(open) {
    const drawer = document.getElementById('hotelSavedDrawer');
    const fab = document.getElementById('hotelSavedFab');
    if (!drawer || !fab) return;
    drawer.classList.toggle('is-open', !!open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function updateHotelActionButtons() {
    const wishKeys = new Set((hotelSavedState.wishlist || []).map((row) => hotelSavedRowKey(row)));
    const cartKeys = new Set((hotelSavedState.cart || []).map((row) => hotelSavedRowKey(row)));

    document.querySelectorAll('[data-hotel-wish]').forEach((btn) => {
        const payload = parseHotelPayload(btn.getAttribute('data-hotel-wish'));
        const active = !!payload && wishKeys.has(hotelPayloadKey(payload));
        btn.classList.toggle('is-active', active);
    });
    document.querySelectorAll('[data-hotel-cart]').forEach((btn) => {
        const payload = parseHotelPayload(btn.getAttribute('data-hotel-cart'));
        const active = !!payload && cartKeys.has(hotelPayloadKey(payload));
        btn.classList.toggle('is-active', active);
    });
}

function renderHotelSavedDrawer() {
    const listEl = document.getElementById('hotelSavedList');
    const emptyEl = document.getElementById('hotelSavedEmpty');
    const countEl = document.getElementById('hotelSavedFabCount');
    const tabs = Array.from(document.querySelectorAll('[data-hotel-saved-tab]'));
    if (!listEl || !emptyEl) return;

    const total = (hotelSavedState.cart?.length || 0) + (hotelSavedState.wishlist?.length || 0) + (hotelAlertState?.length || 0);
    if (countEl) {
        countEl.hidden = total === 0;
        countEl.textContent = String(total || 0);
    }
    tabs.forEach((btn) => {
        const active = btn.getAttribute('data-hotel-saved-tab') === hotelSavedTab;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    if (hotelSavedTab === 'alerts') {
        if (!hotelAlertState.length) {
            listEl.innerHTML = '';
            emptyEl.style.display = 'block';
            emptyEl.textContent = '알림이 없습니다.';
            return;
        }
        emptyEl.style.display = 'none';
        listEl.innerHTML = hotelAlertState.map((item) => {
            const status = String(item.status || 'pending');
            const statusLabel = status === 'accepted' ? '수락됨' : (status === 'rejected' ? '거절됨' : '대기중');
            return `
                <li class="hotel-saved-item" style="grid-template-columns:1fr;">
                    <div>
                        <div class="hotel-saved-item__type">공동구매 · 참여요청</div>
                        <div class="hotel-saved-item__name">${hotelEscapeHtml(item.post_title || '-')}</div>
                        <div class="hotel-saved-item__meta">${hotelEscapeHtml(item.requester_name || '-')}님의 요청<br>${item.requester_email ? `이메일: ${hotelEscapeHtml(item.requester_email)}<br>` : ''}${hotelEscapeHtml(statusLabel)}${item.message ? `<br>${hotelEscapeHtml(item.message)}` : ''}</div>
                        ${status === 'pending'
                            ? `<div style="margin-top:8px;display:flex;gap:6px;">
                                <button type="button" data-hotel-alert-action="accept" data-hotel-alert-id="${Number(item.id)}" class="hotel-detail-action-btn" style="min-height:32px;padding:0 10px;">수락</button>
                                <button type="button" data-hotel-alert-action="reject" data-hotel-alert-id="${Number(item.id)}" class="hotel-detail-action-btn" style="min-height:32px;padding:0 10px;">거절</button>
                               </div>`
                            : `<div style="margin-top:8px;">
                                <button type="button" data-hotel-alert-remove="${Number(item.id)}" class="hotel-detail-action-btn" style="min-height:32px;padding:0 10px;">알림 삭제</button>
                               </div>`
                        }
                    </div>
                </li>
            `;
        }).join('');
        return;
    }

    const items = Array.isArray(hotelSavedState[hotelSavedTab]) ? hotelSavedState[hotelSavedTab] : [];
    listEl.innerHTML = '';
    emptyEl.style.display = items.length ? 'none' : 'block';
    emptyEl.textContent = hotelSavedTab === 'wishlist' ? '위시리스트 항목이 없습니다.' : '장바구니 항목이 없습니다.';

    items.forEach((item) => {
        const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
        const imageUrl = String(payload?.image || '');
        const li = document.createElement('li');
        li.className = 'hotel-saved-item';
        li.innerHTML = `
            <div class="hotel-saved-item__thumb">${imageUrl ? `<img src="${hotelEscapeHtml(imageUrl)}" alt="">` : ''}</div>
            <div>
                <div class="hotel-saved-item__type">${hotelEscapeHtml((item?.item_type || 'item').toUpperCase())} · ${hotelEscapeHtml(item?.source || 'hotel')}</div>
                <div class="hotel-saved-item__name">${hotelEscapeHtml(item?.name || '-')}</div>
                ${item?.meta ? `<div class="hotel-saved-item__meta">${hotelEscapeHtml(item.meta).replace(/\|/g, '<br>')}</div>` : ''}
            </div>
            <button type="button" class="hotel-saved-item__remove" data-hotel-saved-remove="${Number(item.id)}" title="삭제">×</button>
        `;
        listEl.appendChild(li);
    });
}

async function toggleHotelSaved(rawPayload, listType) {
    const payload = buildHotelSavedPayload(rawPayload, listType);
    if (!payload) return false;
    const targetList = Array.isArray(hotelSavedState[listType]) ? hotelSavedState[listType] : [];
    const key = hotelPayloadKey(payload.payload);
    const existing = targetList.find((row) => hotelSavedRowKey(row) === key);
    try {
        if (existing) {
            await hotelSavedApi(`/api/saved-items/${Number(existing.id)}`, { method: 'DELETE', headers: {} });
        } else {
            await hotelSavedApi('/api/saved-items', { method: 'POST', body: JSON.stringify(payload) });
        }
        await loadHotelSavedState();
        renderHotelSavedDrawer();
        updateHotelActionButtons();
        return true;
    } catch (e) {
        if (e?.code === 'LOGIN_REQUIRED') {
            await ensureHotelLoggedIn();
            return false;
        }
        alert(e?.message || '저장 처리 중 오류가 발생했습니다.');
        return false;
    }
}

async function sendHotelAlertDecision(requestId, action) {
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

async function removeHotelAlert(requestId) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}`, {
        method: 'DELETE',
        credentials: 'include',
    });
    if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d?.detail || `HTTP ${res.status}`);
    }
}

async function initHotelSavedUi() {
    const hasActionButtons = !!document.querySelector('[data-hotel-wish], [data-hotel-cart], [data-hotel-reserve]');
    const fab = document.getElementById('hotelSavedFab');
    const drawer = document.getElementById('hotelSavedDrawer');
    if (!hasActionButtons && (!fab || !drawer)) return;

    if (fab && drawer) {
        fab.addEventListener('click', () => {
            const nextOpen = !drawer.classList.contains('is-open');
            setHotelSavedDrawer(nextOpen);
            if (nextOpen && hotelSavedTab === 'alerts') loadHotelAlerts().then(renderHotelSavedDrawer);
        });
        document.querySelectorAll('[data-hotel-saved-close]').forEach((el) => {
            el.addEventListener('click', () => setHotelSavedDrawer(false));
        });
        document.querySelectorAll('[data-hotel-saved-tab]').forEach((btn) => {
            btn.addEventListener('click', () => {
                hotelSavedTab = btn.getAttribute('data-hotel-saved-tab') || 'cart';
                if (hotelSavedTab === 'alerts') {
                    loadHotelAlerts().then(renderHotelSavedDrawer);
                    return;
                }
                renderHotelSavedDrawer();
            });
        });
    }

    document.addEventListener('click', async (e) => {
        const wishBtn = e.target.closest('[data-hotel-wish]');
        if (wishBtn) {
            e.preventDefault();
            e.stopPropagation();
            if (!(await ensureHotelLoggedIn())) return;
            const payload = parseHotelPayload(wishBtn.getAttribute('data-hotel-wish'));
            await toggleHotelSaved(payload, 'wishlist');
            return;
        }

        const cartBtn = e.target.closest('[data-hotel-cart]');
        if (cartBtn) {
            e.preventDefault();
            e.stopPropagation();
            if (!(await ensureHotelLoggedIn())) return;
            const payload = parseHotelPayload(cartBtn.getAttribute('data-hotel-cart'));
            await toggleHotelSaved(payload, 'cart');
            return;
        }

        const reserveBtn = e.target.closest('[data-hotel-reserve]');
        if (reserveBtn) {
            e.preventDefault();
            e.stopPropagation();
            if (!(await ensureHotelLoggedIn())) return;
            const payload = parseHotelPayload(reserveBtn.getAttribute('data-hotel-reserve'));
            if (payload) await toggleHotelSaved(payload, 'cart');
            const bookingUrl = String(payload?.hotel_url || '').trim();
            if (bookingUrl) window.open(bookingUrl, '_blank', 'noopener,noreferrer');
            else alert('예약 링크가 없습니다.');
            return;
        }

        const removeBtn = e.target.closest('[data-hotel-saved-remove]');
        if (removeBtn) {
            const itemId = Number(removeBtn.getAttribute('data-hotel-saved-remove'));
            if (!itemId) return;
            try {
                await hotelSavedApi(`/api/saved-items/${itemId}`, { method: 'DELETE', headers: {} });
                hotelSavedState.cart = (hotelSavedState.cart || []).filter((x) => Number(x.id) !== itemId);
                hotelSavedState.wishlist = (hotelSavedState.wishlist || []).filter((x) => Number(x.id) !== itemId);
                renderHotelSavedDrawer();
                updateHotelActionButtons();
            } catch (err) {
                alert(err?.message || '삭제 중 오류가 발생했습니다.');
            }
            return;
        }

        const alertActBtn = e.target.closest('[data-hotel-alert-action]');
        if (alertActBtn) {
            const requestId = Number(alertActBtn.getAttribute('data-hotel-alert-id'));
            const action = String(alertActBtn.getAttribute('data-hotel-alert-action') || '');
            try {
                await sendHotelAlertDecision(requestId, action);
                await loadHotelAlerts();
                await loadHotelSavedState();
                renderHotelSavedDrawer();
            } catch (err) {
                alert(err?.message || '요청 처리 중 오류가 발생했습니다.');
            }
            return;
        }

        const alertRemoveBtn = e.target.closest('[data-hotel-alert-remove]');
        if (alertRemoveBtn) {
            const requestId = Number(alertRemoveBtn.getAttribute('data-hotel-alert-remove'));
            try {
                await removeHotelAlert(requestId);
                await loadHotelAlerts();
                renderHotelSavedDrawer();
            } catch (err) {
                alert(err?.message || '알림 삭제 중 오류가 발생했습니다.');
            }
        }
    });

    await loadHotelSavedState();
    await loadHotelAlerts();
    renderHotelSavedDrawer();
    updateHotelActionButtons();
    if (window.lucide && lucide.createIcons) lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', () => {
    initHotelSavedUi();
});
