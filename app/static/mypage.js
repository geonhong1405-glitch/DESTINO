/**
 * DESTINO 마이페이지 동적 로직
 * (로그인 유지 및 찜/장바구니/고객센터 탭 포함)
 */

// --- 초기 기본 데이터 설정 ---
// Server-provided user (from data attributes on <body>)
const SERVER_USER = (() => {
    const d = (document.body && document.body.dataset) || {};
    return {
        id: d.userId || d.userName || '',
        name: d.userName || '',
        nickname: d.userNickname || '',
        email: d.userEmail || '',
        phone: d.userPhone || '',
        isLoggedIn: Boolean(d.userName || d.userNickname || d.userEmail || d.userPhone),
    };
})();
const DEFAULT_USER = {
    id: '',
    name: '',
    nickname: '',
    email: '',
    phone: '',
    isLoggedIn: false,
};

// 브라우저 저장소(localStorage)에서 사용자 정보를 불러오거나 없으면 기본값 사용
let user = (SERVER_USER.isLoggedIn ? SERVER_USER : { ...(JSON.parse(localStorage.getItem('destino_user')) || DEFAULT_USER), isLoggedIn: false });

// 예약 데이터 (빈 배열로 초기화)
const bookings = [];

// DB 저장 항목 (위시리스트/장바구니)
let savedItemsState = {
    wishlist: [],
    cart: [],
};
let joinRequestInboxState = [];
let cartSubTab = 'cart';
let myTripPostsState = [];
let joinAlertInitialized = false;
let seenJoinDecisionKeys = new Set();
let chatPassState = [];

function showMypageToast(message) {
    let toast = document.getElementById('mypageToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'mypageToast';
        toast.style.position = 'fixed';
        toast.style.bottom = '24px';
        toast.style.right = '24px';
        toast.style.zIndex = '9999';
        toast.style.maxWidth = '360px';
        toast.style.padding = '12px 14px';
        toast.style.borderRadius = '12px';
        toast.style.background = 'rgba(15,23,42,0.95)';
        toast.style.color = '#fff';
        toast.style.fontSize = '13px';
        toast.style.fontWeight = '700';
        toast.style.boxShadow = '0 8px 30px rgba(0,0,0,.22)';
        toast.style.display = 'none';
        document.body.appendChild(toast);
    }
    toast.textContent = String(message || '').trim();
    toast.style.display = 'block';
    clearTimeout(window.__mypageToastTimer);
    window.__mypageToastTimer = setTimeout(() => {
        toast.style.display = 'none';
    }, 2800);
}

/**
 * 탭 전환 함수
 */
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach((content) => {
        content.classList.remove('active');
    });

    const targetContent = document.getElementById('content-' + tabId);
    if (targetContent) targetContent.classList.add('active');

    document.querySelectorAll('.sidebar-item').forEach((btn) => {
        btn.classList.remove('active');
    });
    const activeBtn = document.getElementById('tab-btn-' + tabId);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    if (tabId !== 'settings') toggleEditMode(false);
    if (tabId === 'cart') {
        renderCartSubTab();
        loadJoinRequestInbox();
    }
    if (tabId === 'post') {
        loadMyTripPosts();
    }
    if (tabId === 'vouchers') {
        loadChatPasses();
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (window.innerWidth < 1024) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && !sidebar.classList.contains('hidden')) {
            toggleMobileMenu();
        }
    }
}

/**
 * 모바일 사이드바 토글
 */
/* function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const menuIcon = document.getElementById('menu-icon');
    if (!sidebar) return;

    const isMobileHidden = sidebar.classList.contains('hidden');

    if (isMobileHidden) {
        sidebar.classList.remove('hidden');
        sidebar.classList.add('fixed', 'inset-0', 'top-16', 'bg-white', 'z-40', 'p-4', 'block');
        if (menuIcon) menuIcon.setAttribute('data-lucide', 'x');
    } else {
        sidebar.classList.add('hidden');
        sidebar.classList.remove('fixed', 'inset-0', 'top-16', 'bg-white', 'z-40', 'p-4', 'block');
        if (menuIcon) menuIcon.setAttribute('data-lucide', 'menu');
    }
    lucide.createIcons();
} */

/**
 * 회원정보 수정 모드 전환
 */
function toggleEditMode(isEditing) {
    const editBtnContainer = document.getElementById('edit-toggle-container');
    const editActions = document.getElementById('edit-actions');
    const footer = document.getElementById('view-info-footer');

    if (isEditing) {
        if (editBtnContainer) editBtnContainer.classList.add('hidden');
        if (editActions) {
            editActions.classList.remove('hidden-actions');
            editActions.classList.add('active');
        }
        if (footer) footer.classList.add('hidden');

        renderInputField('nickname-field-container', 'input-nickname', user.nickname);
        renderInputField('email-field-container', 'input-email', user.email, 'email');
        renderPhoneField();
        renderPasswordCheckField();
    } else {
        if (editBtnContainer) editBtnContainer.classList.remove('hidden');
        if (editActions) {
            editActions.classList.add('hidden-actions');
            editActions.classList.remove('active');
        }
        if (footer) footer.classList.remove('hidden');

        document.getElementById('nickname-field-container').innerHTML = `<p class="static-field">${user.nickname}</p>`;
        document.getElementById('email-field-container').innerHTML = `<p class="static-field">${user.email}</p>`;
        document.getElementById('phone-field-container').innerHTML = `<p class=\"static-field\">${user.phone}</p>`;
        const pwContainer = document.getElementById('password-check-container');
        if (pwContainer) {
            pwContainer.innerHTML = `<label class="label-default">비밀번호 확인</label><p class="static-field">저장을 위해 비밀번호 확인이 필요합니다.</p>`;
        }
    }
}

function renderInputField(containerId, inputId, value, type = 'text') {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = `
        <input 
            id="${inputId}"
            type="${type}" 
            value="${value}" 
            class="w-full px-4 py-3 rounded-2xl bg-white border border-[#00AEEF] focus:ring-2 focus:ring-[#00AEEF]/20 outline-none transition-all text-sm font-semibold"
        />
    `;
}

function renderPhoneField() {
    const container = document.getElementById('phone-field-container');
    if (!container) return;
    container.innerHTML = `
        <div class="flex flex-col sm:flex-row gap-2">
            <input 
                id="input-phone"
                type="tel" 
                value="${user.phone}" 
                class="flex-grow px-4 py-3 rounded-2xl bg-white border border-[#00AEEF] focus:ring-2 focus:ring-[#00AEEF]/20 outline-none transition-all text-sm font-semibold"
            />
        </div>
    `;
}

/**
 * 사용자 정보 저장
 */

function renderPasswordCheckField() {
    const container = document.getElementById('password-check-container');
    if (!container) return;
    container.innerHTML = `
        <label class="label-default">비밀번호 확인</label>
        <input 
            id="input-password-check"
            type="password" 
            placeholder="저장을 위해 비밀번호를 입력하세요"
            class="w-full px-4 py-3 rounded-2xl bg-white border border-[#00AEEF] focus:ring-2 focus:ring-[#00AEEF]/20 outline-none transition-all text-sm font-semibold"
        />
    `;
}
function saveUserInfo() {
    const nickVal = document.getElementById('input-nickname')?.value;
    const emailVal = document.getElementById('input-email')?.value;
    const phoneVal = document.getElementById('input-phone')?.value;
    const pwCheckVal = document.getElementById('input-password-check')?.value;

    if (!pwCheckVal) {
        alert('저장을 위해 비밀번호를 입력해 주세요.');
        return;
    }

    fetch('/api/update-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            password: pwCheckVal,
            nickname: nickVal,
            email: emailVal,
            phone: phoneVal,
        }),
    })
        .then((r) => r.json())
        .then((d) => {
            if (!d || !d.ok) {
                const code = d?.error_code || '';
                const msgMap = {
                    NOT_LOGGED_IN: '로그인이 필요합니다.',
                    USER_NOT_FOUND: '사용자를 찾을 수 없습니다.',
                    PASSWORD_INVALID: '비밀번호가 올바르지 않습니다.',
                    EMAIL_EXISTS: '이미 사용 중인 이메일입니다.',
                    PHONE_EXISTS: '이미 사용 중인 전화번호입니다.',
                };
                alert(msgMap[code] || '저장에 실패했습니다.');
                return;
            }
            const u = d.user || {};
            user.nickname = u.nickname || user.nickname;
            user.email = u.email || user.email;
            user.phone = u.phone || user.phone;
            // keep id/name
            if (u.name) user.name = u.name;
            localStorage.setItem('destino_user', JSON.stringify(user));
            updateDisplay();
            toggleEditMode(false);
        })
        .catch(() => {
            alert('저장되었습니다.');
        });
}


/**
 * 로그아웃 처리
 */
function handleLogout() {
    if (confirm('로그아웃 하시겠습니까?')) {
        localStorage.removeItem('destino_user');
        fetch('/logout', { method: 'GET', credentials: 'include' })
            .catch(() => {})
            .finally(() => {
                window.location.href = '/';
            });
    }
}

/**
 * 저장 항목 삭제 함수 (위시리스트/장바구니 공통)
 */
async function removeSavedItem(id) {
    try {
        const res = await fetch(`/api/saved-items/${id}`, {
            method: 'DELETE',
            credentials: 'include',
        });
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        savedItemsState.wishlist = savedItemsState.wishlist.filter((item) => item.id !== id);
        savedItemsState.cart = savedItemsState.cart.filter((item) => item.id !== id);
        renderSavedItems();
        updateDisplay();
    } catch (e) {
        alert('삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.');
    }
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getFlightAirlineLogoUrl(code) {
    if (!code) return '';
    return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(String(code).toUpperCase())}.png`;
}

function getSavedItemImageUrl(item) {
    const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
    const nested = payload?.payload && typeof payload.payload === 'object' ? payload.payload : {};

    if (item?.item_type === 'flight') {
        return getFlightAirlineLogoUrl(payload?.airline_code || nested?.airline_code || '');
    }

    return (
        payload?.image_url ||
        payload?.image ||
        nested?.image_url ||
        nested?.image ||
        payload?.thumbnail ||
        payload?.photo ||
        nested?.thumbnail ||
        nested?.photo ||
        (Array.isArray(payload?.images) ? payload.images[0] : '') ||
        (Array.isArray(payload?.photos) ? payload.photos[0] : '') ||
        (Array.isArray(nested?.images) ? nested.images[0] : '') ||
        (Array.isArray(nested?.photos) ? nested.photos[0] : '') ||
        ''
    );
}

function getItemTypeLabel(itemType) {
    const type = String(itemType || '').toLowerCase();
    if (type === 'flight') return '항공';
    if (type === 'hotel' || type === 'stay' || type === 'accommodation') return '숙박';
    if (type === 'package' || type === 'pkg') return '패키지';
    if (type === 'rental' || type === 'car' || type === 'rentcar') return '렌터카';
    if (type === 'groupbuy' || type === 'travel-group') return '공동구매';
    return type ? type.toUpperCase() : 'ITEM';
}

function formatSavedItemMeta(item) {
    const raw = String(item?.meta || '').trim();
    const parts = raw ? raw.split('|').map((v) => v.trim()).filter(Boolean) : [];
    const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
    const itemType = String(item?.item_type || '').toLowerCase();

    const looksLikePrice = (text) => {
        const s = String(text || '').trim();
        if (!s) return false;
        return /\d/.test(s) && /(krw|jpy|usd|eur|aed|thb|vnd|sgd|twd|원|\$|€|¥)/i.test(s);
    };

    const payloadPriceText = (() => {
        const cur = String(payload?.currency || '').trim();
        const rawPrice = payload?.price;
        const num = Number(rawPrice);
        if (Number.isFinite(num) && num > 0) {
            return `${num.toLocaleString()} ${cur}`.trim();
        }
        const txt = String(rawPrice ?? '').trim();
        if (txt) return `${txt} ${cur}`.trim();
        return '';
    })();

    let price = '';
    let details = [];
    if (parts.length) {
        if (looksLikePrice(parts[0])) {
            price = parts[0];
            details = parts.slice(1, 3);
        } else {
            details = parts.slice(0, 3);
        }
    }

    if (!price && itemType === 'rental') {
        price = payloadPriceText;
    }

    return {
        price,
        details,
    };
}

function getWishlistCategory(item) {
    const type = String(item?.item_type || '').toLowerCase();
    if (type === 'flight') return '항공';
    if (type === 'hotel' || type === 'stay' || type === 'accommodation') return '숙박';
    if (type === 'package' || type === 'pkg') return '패키지';
    if (type === 'rental' || type === 'car' || type === 'rentcar') return '렌터카';
    if (type === 'groupbuy' || type === 'travel-group') return '공동구매';
    return '기타';
}

function findSavedItemById(itemId) {
    const idNum = Number(itemId);
    if (!Number.isFinite(idNum)) return null;
    const rows = [...(savedItemsState.wishlist || []), ...(savedItemsState.cart || [])];
    return rows.find((x) => Number(x?.id) === idNum) || null;
}

function buildFlightDetailUrlFromSaved(item) {
    const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
    const itineraries = Array.isArray(payload?.itineraries) ? payload.itineraries : [];
    if (!itineraries.length) return '/airport';

    const out = itineraries[0] || {};
    const inn = itineraries[1] || {};
    const outSegs = Array.isArray(out?.segments) ? out.segments : [];
    const inSegs = Array.isArray(inn?.segments) ? inn.segments : [];
    const first = outSegs[0] || {};
    const last = outSegs[outSegs.length - 1] || {};
    const rfirst = inSegs[0] || {};
    const rlast = inSegs[inSegs.length - 1] || {};

    const depCode = String(first?.departure?.iataCode || '');
    const arrCode = String(last?.arrival?.iataCode || '');
    const depAt = String(first?.departure?.at || '');
    const arrAt = String(last?.arrival?.at || '');
    const depTerminal = String(first?.departure?.terminal || '');
    const arrTerminal = String(last?.arrival?.terminal || '');
    const flightNo = `${String(first?.carrierCode || '')}${String(first?.number || '')}`.trim();
    const aircraft = String(first?.aircraft?.code || '');

    const retDepCode = String(rfirst?.departure?.iataCode || '');
    const retArrCode = String(rlast?.arrival?.iataCode || '');
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
        if (!cabin && fds[0]?.cabin) cabin = String(fds[0].cabin);
        if (!retCabin && fds[1]?.cabin) retCabin = String(fds[1].cabin);
        if (cabin && retCabin) break;
    }

    const priceObj = payload?.price || {};
    const baggage = String(payload?.baggage_summary || '');
    const baggageOpts = Array.isArray(payload?.baggage_options) ? payload.baggage_options : [];

    const checkoutRef = `flt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    try {
        sessionStorage.setItem(`flight_checkout_${checkoutRef}`, JSON.stringify(item || {}));
    } catch (_e) {}

    const qs = new URLSearchParams({
        airline: String(payload?.airline || ''),
        dep: depCode,
        arr: arrCode,
        route: `${depCode} -> ${arrCode}`.trim(),
        duration: String(out?.duration || ''),
        price: String(priceObj?.krwTotal || priceObj?.total || ''),
        price_base: String(priceObj?.base || ''),
        price_total: String(priceObj?.total || ''),
        price_grand: String(priceObj?.grandTotal || ''),
        currency: String(priceObj?.currency || (priceObj?.krwTotal ? 'KRW' : '')).toUpperCase(),
        baggage,
        baggage_opts: JSON.stringify(baggageOpts),
        dep_at: depAt,
        arr_at: arrAt,
        dep_terminal: depTerminal,
        arr_terminal: arrTerminal,
        flight_no: flightNo,
        aircraft,
        cabin,
        ret_route: `${retDepCode} -> ${retArrCode}`.trim(),
        ret_duration: String(inn?.duration || ''),
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
    return `/flight-detail?${qs.toString()}`;
}

function getSavedItemPurchaseUrl(item) {
    const type = String(item?.item_type || '').toLowerCase();
    const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
    const nested = payload?.payload && typeof payload.payload === 'object' ? payload.payload : {};

    if (type === 'flight') {
        return buildFlightDetailUrlFromSaved(item);
    }

    if (type === 'hotel' || type === 'stay' || type === 'accommodation') {
        const hotelId = String(payload?.hotel_id || nested?.hotel_id || '').trim();
        const params = new URLSearchParams();
        const city = String(payload?.city || nested?.city || '').trim();
        const cityEn = String(payload?.city_en || nested?.city_en || '').trim();
        const country = String(payload?.country || nested?.country || '').trim();
        const checkin = String(payload?.checkin || nested?.checkin || '').trim();
        const checkout = String(payload?.checkout || nested?.checkout || '').trim();
        const snapshot = String(payload?.snapshot || nested?.snapshot || payload?.detail_snapshot || nested?.detail_snapshot || '').trim();
        if (city) params.set('city', city);
        if (cityEn) params.set('city_en', cityEn);
        if (country) params.set('country', country);
        if (checkin) params.set('checkin', checkin);
        if (checkout) params.set('checkout', checkout);
        if (snapshot) params.set('snapshot', snapshot);
        if (hotelId) {
            params.set('hotel_id', hotelId);
            return `/gloval-hotel/detail?${params.toString()}`;
        }
        return `/gloval-hotel?${params.toString()}`;
    }

    if (type === 'rental' || type === 'car' || type === 'rentcar') {
        const carPayload = payload?.name ? payload : nested;
        if (carPayload && typeof carPayload === 'object' && carPayload.name) {
            return `/rental/detail?car=${encodeURIComponent(JSON.stringify(carPayload))}`;
        }
        return '/rental';
    }

    if (type === 'tour' || type === 'ticket') {
        const params = new URLSearchParams();
        params.set('id', String(payload?.id || nested?.id || item?.id || 'saved'));
        params.set('title', String(payload?.title || payload?.name || nested?.title || nested?.name || item?.name || '티켓'));
        params.set('price', String(payload?.price_text || payload?.price || nested?.price_text || nested?.price || ''));
        params.set('img', String(payload?.image_url || payload?.image || nested?.image_url || nested?.image || ''));
        params.set('loc', String(payload?.location || payload?.meta || nested?.location || item?.meta || ''));
        return `/tour-detail?${params.toString()}`;
    }

    if (type === 'package' || type === 'pkg' || type === 'pack') {
        const params = new URLSearchParams();
        params.set('category', 'package');
        params.set('id', String(payload?.id || nested?.id || item?.id || 'saved'));
        params.set('title', String(payload?.title || payload?.name || nested?.title || nested?.name || item?.name || '패키지'));
        params.set('price', String(payload?.price_text || payload?.price || nested?.price_text || nested?.price || ''));
        params.set('img', String(payload?.image_url || payload?.image || nested?.image_url || nested?.image || ''));
        params.set('loc', String(payload?.location || payload?.meta || nested?.location || item?.meta || ''));
        return `/pack-detail?${params.toString()}`;
    }

    if (type === 'groupbuy' || type === 'travel-group') {
        return '/travel-group';
    }

    return '/';
}

function openSavedItem(itemId) {
    const item = findSavedItemById(itemId);
    if (!item) {
        alert('상품 정보를 찾을 수 없습니다.');
        return;
    }
    const target = getSavedItemPurchaseUrl(item);
    if (!target) {
        alert('이 항목은 바로 구매 이동을 지원하지 않습니다.');
        return;
    }
    window.location.href = target;
}

async function loadSavedItems() {
    try {
        const res = await fetch('/api/saved-items', { credentials: 'include' });
        if (res.status === 401) {
            savedItemsState = { wishlist: [], cart: [] };
            renderSavedItems();
            updateDisplay();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        savedItemsState = {
            wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
            cart: Array.isArray(data?.cart) ? data.cart : [],
        };
    } catch (e) {
        savedItemsState = { wishlist: [], cart: [] };
    }
    renderSavedItems();
    updateDisplay();
}

async function loadJoinRequestInbox() {
    try {
        const res = await fetch('/api/group-buy/join-requests/inbox', { credentials: 'include' });
        if (res.status === 401) {
            joinRequestInboxState = [];
            renderJoinRequestInbox();
            renderCartSubTab();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const rows = Array.isArray(data) ? data : [];
        const mineDone = rows.filter((x) => String(x?.direction || '') === 'mine' && ['accepted', 'rejected'].includes(String(x?.status || '')));
        if (!joinAlertInitialized) {
            seenJoinDecisionKeys = new Set(mineDone.map((x) => `${Number(x?.id)}:${String(x?.status || '')}`));
            joinAlertInitialized = true;
        } else {
            const newly = mineDone.filter((x) => {
                const key = `${Number(x?.id)}:${String(x?.status || '')}`;
                if (seenJoinDecisionKeys.has(key)) return false;
                seenJoinDecisionKeys.add(key);
                return true;
            });
            if (newly.length) {
                const joinedMessage = newly
                    .map((x) => String(x?.message || '').trim())
                    .filter(Boolean)
                    .join(' / ');
                showMypageToast(joinedMessage || '참여요청 결과가 도착했습니다. 장바구니/알림을 확인해 주세요.');
                await loadSavedItems();
            }
        }
        joinRequestInboxState = rows;
    } catch (_e) {
        joinRequestInboxState = [];
    }
    renderJoinRequestInbox();
    renderCartSubTab();
}

function switchCartSubTab(tab) {
    cartSubTab = tab === 'alerts' ? 'alerts' : 'cart';
    renderCartSubTab();
}

function renderCartSubTab() {
    const cartBtn = document.getElementById('mypage-cart-subtab-cart');
    const alertsBtn = document.getElementById('mypage-cart-subtab-alerts');
    const cartList = document.getElementById('mypage-cart-list');
    const alertsList = document.getElementById('mypage-cart-alerts-list');
    if (!cartBtn || !alertsBtn || !cartList || !alertsList) return;

    const cartActive = cartSubTab === 'cart';
    cartBtn.classList.toggle('bg-white', cartActive);
    cartBtn.classList.toggle('text-[#00AEEF]', cartActive);
    cartBtn.classList.toggle('text-gray-500', !cartActive);
    alertsBtn.classList.toggle('bg-white', !cartActive);
    alertsBtn.classList.toggle('text-[#00AEEF]', !cartActive);
    alertsBtn.classList.toggle('text-gray-500', cartActive);
    alertsBtn.textContent = `알림 (${joinRequestInboxState.length})`;

    cartList.classList.toggle('hidden', !cartActive);
    alertsList.classList.toggle('hidden', cartActive);
}

async function decideJoinRequest(requestId, action) {
    try {
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
        await loadJoinRequestInbox();
        await loadMyTripPosts();
    } catch (e) {
        alert(e?.message || '요청 처리 중 오류가 발생했습니다.');
    }
}

async function removeJoinAlert(requestId) {
    try {
        const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}`, {
            method: 'DELETE',
            credentials: 'include',
        });
        if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d?.detail || `HTTP ${res.status}`);
        }
        await loadJoinRequestInbox();
    } catch (e) {
        alert(e?.message || '알림 삭제 중 오류가 발생했습니다.');
    }
}

function renderJoinRequestInbox() {
    const container = document.getElementById('mypage-cart-alerts-list');
    if (!container) return;

    if (!joinRequestInboxState.length) {
        container.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-12">
                <p class="text-gray-400 text-sm">도착한 참여 요청 알림이 없습니다.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = joinRequestInboxState
        .map((item) => {
            const status = String(item.status || 'pending');
            const statusLabel = status === 'accepted' ? '수락됨' : (status === 'rejected' ? '거절됨' : '대기중');
            const statusClass = status === 'accepted' ? 'text-emerald-600' : (status === 'rejected' ? 'text-rose-600' : 'text-amber-600');
            const incoming = String(item.direction || 'incoming') !== 'mine';
            const reqTitle = incoming
                ? `${escapeHtml(item.requester_name || '')}님이 요청했습니다`
                : `${escapeHtml(item.requester_name || '작성자')}님의 응답`;
            return `
                <div class="p-4 rounded-2xl border border-gray-100 bg-white shadow-sm">
                    <div class="flex items-start justify-between gap-3">
                        <div>
                            <p class="text-[11px] font-bold text-gray-400">공동구매 참여요청</p>
                            <p class="text-sm font-bold text-gray-800 mt-0.5">${escapeHtml(item.post_title || '')}</p>
                            <p class="text-xs text-gray-500 mt-1">${reqTitle}</p>
                            ${item.requester_email ? `<p class="text-xs text-gray-500 mt-1">이메일: ${escapeHtml(item.requester_email)}</p>` : ''}
                            ${item.message ? `<p class="text-xs text-gray-500 mt-1">${escapeHtml(item.message)}</p>` : ''}
                        </div>
                        <p class="text-xs font-bold ${statusClass}">${statusLabel}</p>
                    </div>
                    ${
                        incoming && status === 'pending'
                            ? `
                        <div class="mt-3 flex gap-2">
                            <button onclick="decideJoinRequest(${Number(item.id)}, 'accept')" class="px-3 py-1.5 rounded-lg bg-emerald-500 text-white text-xs font-bold">수락</button>
                            <button onclick="decideJoinRequest(${Number(item.id)}, 'reject')" class="px-3 py-1.5 rounded-lg bg-rose-500 text-white text-xs font-bold">거절</button>
                        </div>
                    `
                            : ''
                    }
                    ${
                        status !== 'pending' && !incoming
                            ? `
                        <div class="mt-3 flex gap-2">
                            <button onclick="removeJoinAlert(${Number(item.id)})" class="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-xs font-bold">알림 삭제</button>
                        </div>
                    `
                            : ''
                    }
                </div>
            `;
        })
        .join('');
}

function buildSavedItemCard(item, listType) {
    const category = `${getItemTypeLabel(item?.item_type)} · ${item?.source || 'saved-item'}`;
    const title = item?.name || '(이름 없음)';
    const metaData = formatSavedItemMeta(item);
    const iconHtml = listType === 'wishlist'
        ? '<i data-lucide="heart" class="fill-current text-red-500" size="18"></i>'
        : '<i data-lucide="x" size="18"></i>';
    const colorClass = listType === 'cart' ? 'bg-blue-100' : '';
    const imageUrl = getSavedItemImageUrl(item);
    const imageHtml = imageUrl
        ? `<img class="wish-thumb-img" src="${escapeHtml(imageUrl)}" alt="${escapeHtml(title)}" loading="lazy" onerror="this.style.display='none';this.parentElement.classList.add('no-image')">`
        : '';
    const detailLines = (metaData.details || []).map((line) => `<p class="wish-meta-line">${escapeHtml(line)}</p>`).join('');
    const actionLabel = listType === 'cart' ? '결제하기' : '상품 보기';

    return `
        <div class="wish-item" onclick="openSavedItem(${Number(item.id)})" style="cursor:pointer;">
            <div class="wish-img-placeholder ${colorClass} ${imageUrl ? '' : 'no-image'}">${imageHtml}</div>
            <div class="wish-info">
                <p class="wish-category">${escapeHtml(category)}</p>
                <h5 class="wish-name">${escapeHtml(title)}</h5>
                <p class="wish-price">${escapeHtml(metaData.price || '저장된 항목')}</p>
                ${detailLines}
                <button class="mt-2 px-3 py-1.5 rounded-lg bg-[#00AEEF] text-white text-xs font-bold" onclick="event.stopPropagation();openSavedItem(${Number(item.id)})">${actionLabel}</button>
            </div>
            <button class="wish-remove-btn" onclick="event.stopPropagation();removeSavedItem(${Number(item.id)})" title="삭제">
                ${iconHtml}
            </button>
        </div>
    `;
}

function renderSavedItemsList(container, listType, items) {
    if (!container) return;
    if (!items.length) {
        container.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-12">
                <p class="text-gray-400 text-sm">${listType === 'wishlist' ? '위시리스트 내역이 없습니다.' : '장바구니가 비어 있습니다.'}</p>
            </div>
        `;
        return;
    }
    container.innerHTML = items.map((item) => buildSavedItemCard(item, listType)).join('');
}

function renderWishlistGrouped(container, items) {
    if (!container) return;
    const groups = { 항공: [], 숙박: [], 패키지: [], 렌터카: [], 공동구매: [], 기타: [] };
    (items || []).forEach((item) => {
        const key = getWishlistCategory(item);
        if (groups[key]) groups[key].push(item);
    });
    const sections = ['항공', '숙박', '패키지', '렌터카', '공동구매', '기타']
        .map((label) => {
            const rows = groups[label] || [];
            return `
                <section class="col-span-full">
                    <h5 class="text-sm font-bold text-gray-700 mb-3">${label} (${rows.length})</h5>
                    ${
                        rows.length
                            ? `<div class="grid grid-cols-1 md:grid-cols-2 gap-4">${rows.map((item) => buildSavedItemCard(item, 'wishlist')).join('')}</div>`
                            : '<p class="text-xs text-gray-400 mb-4">저장된 항목이 없습니다.</p>'
                    }
                </section>
            `;
        })
        .join('');
    container.innerHTML = sections;
}

function renderSavedItems() {
    const wishContainer = document.getElementById('mypage-wishlist-list');
    const cartContainer = document.getElementById('mypage-cart-list');
    const wishTitle = document.getElementById('mypage-wishlist-title');
    const cartTitle = document.getElementById('mypage-cart-title');

    if (wishTitle) wishTitle.innerText = `위시리스트 (${savedItemsState.wishlist.length})`;
    if (cartTitle) cartTitle.innerText = `장바구니 (${savedItemsState.cart.length})`;

    renderWishlistGrouped(wishContainer, savedItemsState.wishlist || []);
    renderSavedItemsList(cartContainer, 'cart', savedItemsState.cart);
    renderCartSubTab();
    renderRecentCartPreview();
    lucide.createIcons();
}

function renderRecentCartPreview() {
    const container = document.getElementById('recent-cart-list');
    if (!container) return;

    const items = (savedItemsState.cart || []).slice(0, 3);
    if (!items.length) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-10 bg-white rounded-3xl border border-dashed border-gray-200 shadow-sm">
                <p class="text-gray-500 font-medium">장바구니에 담긴 항목이 없습니다.</p>
                <p class="text-gray-400 text-sm mt-1">항공/숙소/렌터카를 담아 비교해보세요.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${items.map((item) => buildSavedItemCard(item, 'cart')).join('')}
        </div>
        <div class="mt-3 text-right">
            <button onclick="switchTab('cart')" class="view-all-btn">장바구니 전체보기 <i data-lucide="chevron-right" size="16"></i></button>
        </div>
    `;
}

/**
 * 화면 데이터 표시 업데이트
 */
function updateDisplay() {
    const displayName = user.nickname || user.name || '';
    document.querySelectorAll('.user-name-display').forEach((el) => (el.innerText = displayName));
    document.querySelectorAll('.user-email-display').forEach((el) => (el.innerText = user.email));

    const emailText = document.querySelector('.user-email-text');
    if (emailText) emailText.innerText = user.email;

    const infoId = document.getElementById('info-id');
    if (infoId) infoId.innerText = user.name || user.id || 'destino_traveler';

    const bookingStat = document.getElementById('mypage-booking-count');
    if (bookingStat) bookingStat.innerText = `${bookings.length}건`;

    const wishStat = document.getElementById('mypage-wishlist-count');
    if (wishStat) wishStat.innerText = `${savedItemsState.wishlist.length}개`;

    const cartStat = document.getElementById('mypage-cart-count');
    if (cartStat) cartStat.innerText = `${savedItemsState.cart.length}개`;
}

/**
 * 예약 내역 렌더링
 */
function renderBookings() {
    const recentList = document.getElementById('recent-bookings-list');
    const allList = document.getElementById('all-bookings-list');

    if (!recentList || !allList) return;

    if (bookings.length === 0) {
        const emptyHtml = `
            <div class="flex flex-col items-center justify-center py-16 bg-white rounded-3xl border border-dashed border-gray-200 shadow-sm">
                <div class="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center text-gray-300 mb-4">
                    <i data-lucide="calendar-x" size="32"></i>
                </div>
                <p class="text-gray-500 font-medium">최근 예약 내역이 없습니다.</p>
                <p class="text-gray-400 text-sm mt-1">DESTINO와 함께 새로운 여행을 계획해보세요!</p>
                <button class="mt-6 px-6 py-3 bg-[#00AEEF] text-white rounded-2xl font-bold text-sm hover:shadow-lg transition-all">여행지 구경하기</button>
            </div>
        `;
        recentList.innerHTML = emptyHtml;
        allList.innerHTML = emptyHtml;
        return;
    }

    const formatWhen = (item) => {
        const raw = String(item?.confirmed_at || item?.created_at || '').trim();
        if (!raw) return '-';
        const d = new Date(raw);
        if (Number.isNaN(d.getTime())) return raw;
        return d.toLocaleString();
    };

    const buildBookingCard = (item) => {
        const amount = Number(item?.amount || 0);
        const cur = String(item?.currency || 'KRW').toUpperCase();
        const status = String(item?.status_label || item?.status || '예약 확정');
        const route = String(item?.route || '').trim();
        const itemType = String(item?.item_type || '').toLowerCase();
        const typeLabelMap = {
            flight: '항공',
            hotel: '호텔',
            rental: '렌터카',
            tour: '티켓',
            pack: '패키지',
        };
        const typeLabel = typeLabelMap[itemType] || '예약';
        return `
            <div class="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all relative border-l-4 border-l-[#00AEEF]">
                <div class="flex justify-between items-start mb-3">
                    <span class="px-2 py-1 bg-blue-50 text-[#00AEEF] text-[10px] font-bold rounded-lg uppercase">${escapeHtml(typeLabel)}</span>
                    <span class="text-xs font-bold text-emerald-600">${escapeHtml(status)}</span>
                </div>
                <h5 class="font-bold text-gray-800 mb-1 truncate">${escapeHtml(String(item?.order_name || '예약 상품'))}</h5>
                <p class="text-sm text-gray-500">${escapeHtml(route || '-')}</p>
                <p class="text-sm font-semibold text-gray-700 mt-2">${escapeHtml(`${cur} ${amount.toLocaleString()}`)}</p>
                <div class="mt-4 pt-3 border-t border-gray-50 flex justify-between items-center">
                    <span class="text-[10px] text-gray-400">주문번호: ${escapeHtml(String(item?.order_id || '-'))}</span>
                    <span class="text-[10px] text-gray-400">${escapeHtml(formatWhen(item))}</span>
                </div>
            </div>
        `;
    };

    const recent = bookings.slice(0, 3);
    recentList.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${recent.map((item) => buildBookingCard(item)).join('')}
        </div>
    `;
    allList.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${bookings.map((item) => buildBookingCard(item)).join('')}
        </div>
    `;
    lucide.createIcons();
}

async function loadFlightBookings() {
    try {
        const res = await fetch('/api/bookings', { credentials: 'include', cache: 'no-store' });
        if (res.status === 401) {
            bookings.splice(0, bookings.length);
            renderBookings();
            updateDisplay();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json().catch(() => ({}));
        const rows = Array.isArray(data?.bookings) ? data.bookings : [];
        bookings.splice(0, bookings.length, ...rows);
    } catch (_e) {
        bookings.splice(0, bookings.length);
    }
    renderBookings();
    updateDisplay();
}

async function loadMyTripPosts() {
    try {
        const res = await fetch('/api/group-buy/my-posts', { credentials: 'include', cache: 'no-store' });
        if (res.status === 401) {
            myTripPostsState = [];
            renderMyTripPosts();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        myTripPostsState = Array.isArray(data) ? data : [];
    } catch (_e) {
        myTripPostsState = [];
    }
    renderMyTripPosts();
}

/* 내가 쓴 공동구매 게시글 렌더링 */
function renderMyTripPosts() {
    const container = document.getElementById('my-trip-posts-list');
    if (!container) return;

    if (myTripPostsState.length === 0) {
        container.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-16 bg-gray-50 rounded-3xl border border-dashed border-gray-200">
                <i data-lucide="file-text" class="text-gray-300 mb-4" size="48"></i>
                <p class="text-gray-500 font-medium">아직 작성한 게시물이 없습니다.</p>
                <p class="text-gray-400 text-xs mt-1">공동구매 게시판에서 첫 모집글을 올려보세요!</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    container.innerHTML = myTripPostsState
        .map(
            (post) => `
        <div class="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all relative border-l-4 border-l-[#00AEEF]">
            <div class="flex justify-between items-start mb-3">
                <span class="px-2 py-1 bg-blue-50 text-[#00AEEF] text-[10px] font-bold rounded-lg uppercase">${post.country}</span>
                <button onclick="deleteMyPost(${post.id})" class="text-gray-300 hover:text-red-500 transition-colors">
                    <i data-lucide="trash-2" size="16"></i>
                </button>
            </div>
            <h5 class="font-bold text-gray-800 mb-2 truncate">${post.title}</h5>
            <div class="space-y-1">
                <div class="flex items-center gap-2 text-xs text-gray-500">
                    <i data-lucide="calendar" size="12"></i>
                    <span>${String(post.start_date || post.start || '').slice(0, 7)} 출발</span>
                </div>
                <div class="flex items-center gap-2 text-xs text-gray-500">
                    <i data-lucide="wallet" size="12"></i>
                    <span class="font-semibold text-gray-700">${post.budget || ''}</span>
                </div>
            </div>
            <div class="mt-4 pt-3 border-t border-gray-50 flex justify-between items-center">
                <span class="text-[10px] text-gray-400">작성일: ${post.created_at ? new Date(post.created_at).toLocaleDateString() : '-'}</span>
                <span class="text-xs font-bold ${post.status === 'closed' ? 'text-gray-400' : 'text-[#00AEEF]'}">${post.status === 'closed' ? '마감' : '모집 중'}</span>
            </div>
        </div>
    `
        )
        .join('');

    lucide.createIcons();
}

/* 내가 쓴 글 삭제 기능 */
async function deleteMyPost(postId) {
    if (!confirm('게시글을 삭제하시겠습니까?')) return;
    try {
        const res = await fetch(`/api/group-buy/posts/${Number(postId)}`, {
            method: 'DELETE',
            credentials: 'include',
        });
        if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d?.detail || `HTTP ${res.status}`);
        }
        await loadMyTripPosts();
        await loadJoinRequestInbox();
    } catch (e) {
        alert(e?.message || '게시글 삭제에 실패했습니다.');
    }
}

async function loadChatPasses() {
    try {
        const res = await fetch('/api/chat-passes', { credentials: 'include', cache: 'no-store' });
        if (res.status === 401) {
            chatPassState = [];
            renderChatPasses();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json().catch(() => ({}));
        chatPassState = Array.isArray(data?.passes) ? data.passes : [];
    } catch (_e) {
        chatPassState = [];
    }
    renderChatPasses();
}

async function removeChatPass(passId) {
    try {
        const res = await fetch(`/api/chat-passes/${Number(passId)}`, { method: 'DELETE', credentials: 'include' });
        if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d?.detail || '삭제 실패');
        }
        await loadChatPasses();
    } catch (e) {
        alert(e?.message || '삭제에 실패했습니다.');
    }
}

function renderChatPasses() {
    const container = document.getElementById('mypage-voucher-list');
    const title = document.getElementById('mypage-voucher-title');
    if (!container) return;
    if (title) title.innerText = `이용권 (${chatPassState.length})`;

    if (!chatPassState.length) {
        container.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-12">
                <p class="text-gray-400 text-sm">보유한 이용권이 없습니다.</p>
            </div>
        `;
        return;
    }

    const statusLabel = (s) => {
        if (s === 'active') return '사용중';
        if (s === 'expired') return '만료';
        if (s === 'used_up') return '횟수 소진';
        return s || '-';
    };
    const statusClass = (s) => {
        if (s === 'active') return 'text-emerald-600';
        if (s === 'expired') return 'text-rose-600';
        if (s === 'used_up') return 'text-amber-600';
        return 'text-gray-500';
    };
    const dateText = (s) => {
        const d = new Date(String(s || ''));
        if (Number.isNaN(d.getTime())) return '-';
        return d.toLocaleDateString();
    };

    container.innerHTML = chatPassState.map((row) => `
        <div class="p-4 rounded-2xl border border-gray-100 bg-white shadow-sm">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <p class="text-[11px] font-bold text-gray-400">챗봇 이용권</p>
                    <p class="text-sm font-bold text-gray-800 mt-0.5">${escapeHtml(row.plan_name || '-')}</p>
                    <p class="text-xs text-gray-500 mt-1">결제금액: ₩${Number(row.amount || 0).toLocaleString('ko-KR')}</p>
                    <p class="text-xs text-gray-500 mt-1">유효기간: ${dateText(row.started_at)} ~ ${dateText(row.expires_at)}</p>
                    <p class="text-xs text-gray-500 mt-1">남은 횟수: ${row.remaining_uses == null ? '무제한' : `${Number(row.remaining_uses)}회`}</p>
                </div>
                <div class="text-right">
                    <p class="text-xs font-bold ${statusClass(row.status)}">${statusLabel(row.status)}</p>
                    ${(row.status === 'expired' || row.status === 'used_up')
                        ? `<button onclick="removeChatPass(${Number(row.id)})" class="mt-2 px-2 py-1 rounded-lg bg-gray-100 text-gray-700 text-xs font-bold">삭제</button>`
                        : ''}
                </div>
            </div>
        </div>
    `).join('');
}

/*페이지 로드 시 실행*/
window.onload = () => {
    if (!SERVER_USER.isLoggedIn) {
        alert('로그인 세션이 만료되었거나 로그인이 필요합니다. 다시 로그인해주세요.');
        window.location.href = '/login';
        return;
    }
    updateDisplay();
    renderBookings();
    loadFlightBookings();
    loadSavedItems();
    loadMyTripPosts();
    loadJoinRequestInbox();
    loadChatPasses();
    renderCartSubTab();
    setInterval(() => {
        loadSavedItems();
        loadJoinRequestInbox();
    }, 15000);

    const logoutBtn = document.querySelector('.logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = (e) => {
            e.preventDefault();
            handleLogout();
        };
    }

    lucide.createIcons();

    const tab = new URLSearchParams(window.location.search).get('tab');
    if (tab && document.getElementById(`content-${tab}`)) {
        switchTab(tab);
    }
};

window.addEventListener('focus', () => {
    loadFlightBookings();
    loadSavedItems();
    loadMyTripPosts();
    loadJoinRequestInbox();
    loadChatPasses();
});
