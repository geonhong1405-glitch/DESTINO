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
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        joinRequestInboxState = Array.isArray(data) ? data : [];
    } catch (_e) {
        joinRequestInboxState = [];
    }
    renderJoinRequestInbox();
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
                        status !== 'pending'
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

    return `
        <div class="wish-item">
            <div class="wish-img-placeholder ${colorClass} ${imageUrl ? '' : 'no-image'}">${imageHtml}</div>
            <div class="wish-info">
                <p class="wish-category">${escapeHtml(category)}</p>
                <h5 class="wish-name">${escapeHtml(title)}</h5>
                <p class="wish-price">${escapeHtml(metaData.price || '저장된 항목')}</p>
                ${detailLines}
            </div>
            <button class="wish-remove-btn" onclick="removeSavedItem(${Number(item.id)})" title="삭제">
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
    }
    lucide.createIcons();
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

/*페이지 로드 시 실행*/
window.onload = () => {
    if (!SERVER_USER.isLoggedIn) {
        alert('로그인 세션이 만료되었거나 로그인이 필요합니다. 다시 로그인해주세요.');
        window.location.href = '/login';
        return;
    }
    updateDisplay();
    renderBookings();
    loadSavedItems();
    loadMyTripPosts();
    loadJoinRequestInbox();
    renderCartSubTab();

    const logoutBtn = document.querySelector('.logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = (e) => {
            e.preventDefault();
            handleLogout();
        };
    }

    lucide.createIcons();
};

window.addEventListener('focus', () => {
    loadSavedItems();
    loadMyTripPosts();
    loadJoinRequestInbox();
});

