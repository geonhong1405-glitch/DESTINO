/**
 * DESTINO 공동구매 페이지 스크립트
 */

const RECOMMENDED_COUNTRIES = ['일본', '베트남', '태국', '프랑스', '미국', '이탈리아', '스페인', '영국'];
const COUNTRY_CITIES = {
    일본: ['오사카', '도쿄', '교토', '후쿠오카', '삿포로'],
    베트남: ['다낭', '나트랑', '하노이', '호치민', '푸꾸옥'],
    태국: ['방콕', '푸켓', '치앙마이', '파타야'],
    프랑스: ['파리', '니스', '리옹', '마르세유'],
    미국: ['뉴욕', '로스앤젤레스', '라스베이거스', '샌프란시스코'],
    이탈리아: ['로마', '밀라노', '베네치아', '피렌체'],
    스페인: ['바르셀로나', '마드리드', '세비야'],
    영국: ['런던', '에든버러', '맨체스터'],
};

const GROUPBUY_IMAGE_BY_COUNTRY = {
    japan: 'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=800&q=80',
    vietnam: 'https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=800&q=80',
    thailand: 'https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=800&q=80',
    france: 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=800&q=80',
    usa: 'https://images.unsplash.com/photo-1485738422979-f5c462d49f74?auto=format&fit=crop&w=800&q=80',
    italy: 'https://images.unsplash.com/photo-1525874684015-58379d421a52?auto=format&fit=crop&w=800&q=80',
    spain: 'https://images.unsplash.com/photo-1543783207-ec64e4d95325?auto=format&fit=crop&w=800&q=80',
    uk: 'https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=800&q=80',
    default: 'https://images.unsplash.com/photo-1488085061387-422e29b40080?auto=format&fit=crop&w=800&q=80',
};

let posts = [
    {
        id: 1,
        country: '일본',
        city: '오사카',
        title: '오사카 3박 4일 벚꽃 투어 멤버 구함!',
        start: '2026-03',
        departure: '인천',
        budget: '600,000원',
        current: 2,
        max: 4,
        status: 'open',
        desc: '항공+숙소 함께 예약하실 분 모집합니다.',
    },
    {
        id: 2,
        country: '베트남',
        city: '다낭',
        title: '다낭 풀빌라 같이 예약하실 분?',
        start: '2026-04',
        departure: '인천',
        budget: '800,000원',
        current: 3,
        max: 4,
        status: 'open',
        desc: '가족형 풀빌라 공동구매 인원 모집입니다.',
    },
    {
        id: 3,
        country: '태국',
        city: '방콕',
        title: '방콕 미식 탐방 5일 조인하실 분',
        start: '2026-03',
        departure: '김해',
        budget: '450,000원',
        current: 4,
        max: 4,
        status: 'closed',
        desc: '미식 위주 일정이며 모집은 마감되었습니다.',
    },
];

const itemsPerPage = 5;
let currentPage = 1;
let currentDetailPostId = null;
let currentUserProfile = { nickname: '', email: '' };

let savedItemsState = { wishlist: [], cart: [] };
let groupSavedTab = 'cart';
let groupAlertState = [];
let writeAttachSource = 'cart';
let selectedLinkedItemKeys = new Set();
let groupAlertInitialized = false;
let seenGroupDecisionKeys = new Set();

function isLoggedIn() {
    return !!(window.__AUTH__ && window.__AUTH__.nickname);
}

async function loadCurrentUserProfile() {
    if (!isLoggedIn()) return;
    try {
        const res = await fetch('/api/me', { credentials: 'include', cache: 'no-store' });
        if (!res.ok) return;
        const data = await res.json();
        const u = data?.user || {};
        currentUserProfile.nickname = String(u.nickname || window.__AUTH?.nickname || '').trim();
        currentUserProfile.email = String(u.email || '').trim();
    } catch (_e) {
        currentUserProfile.nickname = String(window.__AUTH?.nickname || '').trim();
    }
}

function requireLoginMessage() {
    if (confirm('로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?')) {
        location.href = '/login';
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

function getPostById(id) {
    return posts.find((p) => Number(p.id) === Number(id));
}

function normalizeCountryKey(country) {
    const c = String(country || '').toLowerCase();
    if (c.includes('일본') || c.includes('japan')) return 'japan';
    if (c.includes('베트남') || c.includes('vietnam')) return 'vietnam';
    if (c.includes('태국') || c.includes('thailand')) return 'thailand';
    if (c.includes('프랑스') || c.includes('france')) return 'france';
    if (c.includes('미국') || c.includes('usa') || c.includes('united states')) return 'usa';
    if (c.includes('이탈리아') || c.includes('italy')) return 'italy';
    if (c.includes('스페인') || c.includes('spain')) return 'spain';
    if (c.includes('영국') || c.includes('uk') || c.includes('united kingdom')) return 'uk';
    return 'default';
}

function getDefaultGroupbuyImage(country) {
    const key = normalizeCountryKey(country);
    return GROUPBUY_IMAGE_BY_COUNTRY[key] || GROUPBUY_IMAGE_BY_COUNTRY.default;
}

function getSavedItemTypeLabel(itemType) {
    const type = String(itemType || '').toLowerCase();
    if (type === 'flight') return '항공';
    if (type === 'hotel' || type === 'stay' || type === 'accommodation') return '숙박';
    if (type === 'rental' || type === 'rentcar' || type === 'rentalcar') return '렌터카';
    if (type === 'groupbuy' || type === 'travel-group') return '공동구매';
    return type ? type.toUpperCase() : 'ITEM';
}

function isAttachableType(itemType) {
    const t = String(itemType || '').toLowerCase();
    return ['flight', 'hotel', 'rental', 'rentcar', 'rentalcar', 'package', 'tour', 'ticket'].includes(t);
}

function buildLinkedKey(row) {
    return `${String(row?.list_type || '')}:${Number(row?.id || 0)}`;
}

function normalizeLinkedFromSaved(row) {
    return {
        item_type: String(row?.item_type || '').toLowerCase(),
        name: String(row?.name || ''),
        meta: String(row?.meta || ''),
        source: String(row?.source || ''),
        payload: row?.payload ?? null,
    };
}

function getGroupSavedImageUrl(item) {
    const payload = item?.payload || {};
    if (payload?.thumb_url) return String(payload.thumb_url);
    if (payload?.image_url) return String(payload.image_url);
    if (payload?.image) return String(payload.image);
    if (item?.image_url) return String(item.image_url);
    if (item?.image) return String(item.image);
    if (payload?.country) return getDefaultGroupbuyImage(payload.country);
    return '';
}

function getStatusLabel(post) {
    if (post.status === 'closed') return '모집 마감';
    if ((post.max - post.current) <= 1) return '마감 임박';
    return '모집 중';
}

function buildGroupbuyPayload(post) {
    const name = post.title;
    const meta = [post.budget, `${post.start} 출발`, `${post.departure} 출발`].filter(Boolean).join(' | ');
    return {
        list_type: 'wishlist',
        item_type: 'groupbuy',
        name,
        meta,
        source: 'travel-group',
        payload: {
            post_id: post.id,
            country: post.country,
            city: post.city || '',
            start: post.start,
            departure: post.departure,
            budget: post.budget,
            image_url: getDefaultGroupbuyImage(post.country),
            status: post.status,
            current: post.current,
            max: post.max,
            desc: post.desc,
        },
    };
}

function getGroupbuyKey(itemLike) {
    const itemType = String(itemLike?.item_type || '').toLowerCase();
    const name = String(itemLike?.name || '').toLowerCase();
    const meta = String(itemLike?.meta || '').toLowerCase();
    const source = String(itemLike?.source || '').toLowerCase();
    return `${itemType}__${name}__${meta}__${source}`;
}

function isPostWished(post) {
    const payload = buildGroupbuyPayload(post);
    const key = getGroupbuyKey(payload);
    return (savedItemsState.wishlist || []).some((item) => getGroupbuyKey(item) === key);
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
    let data = null;
    try { data = await res.json(); } catch (_e) {}

    if (res.status === 401) {
        const err = new Error('LOGIN_REQUIRED');
        err.code = 'LOGIN_REQUIRED';
        throw err;
    }
    if (!res.ok) {
        const err = new Error((data && (data.detail || data.error)) || `HTTP ${res.status}`);
        err.code = 'API_ERROR';
        throw err;
    }
    return data;
}

async function groupBuyApi(path = '/api/group-buy/posts', options = {}) {
    const res = await fetch(path, {
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    });
    let data = null;
    try { data = await res.json(); } catch (_e) {}
    if (res.status === 401) {
        const err = new Error('LOGIN_REQUIRED');
        err.code = 'LOGIN_REQUIRED';
        throw err;
    }
    if (!res.ok) {
        const err = new Error((data && (data.detail || data.error)) || `HTTP ${res.status}`);
        err.code = 'API_ERROR';
        throw err;
    }
    return data;
}

async function loadGroupBuyPosts() {
    try {
        const rows = await groupBuyApi('/api/group-buy/posts', { method: 'GET', headers: {} });
        posts = (Array.isArray(rows) ? rows : []).map((row) => ({
            id: row.id,
            country: row.country,
            city: row.city || '',
            title: row.title,
            start: String(row.start_date || '').slice(0, 7),
            departure: row.departure || '인천',
            budget: row.budget || '',
            current: Number(row.current_people || 1),
            max: Number(row.max_people || 4),
            status: row.status || 'open',
            desc: row.description || '',
            ownerUserId: Number(row.owner_user_id || 0),
            ownerNickname: row.owner_nickname || '',
            isMine: !!row.is_mine,
            rawStartDate: row.start_date || '',
            rawEndDate: row.end_date || '',
            linkedItems: Array.isArray(row.linked_items) ? row.linked_items : [],
        }));
    } catch (_e) {
        posts = [];
    }
    renderPosts(1);
}

async function loadSavedItems() {
    if (!isLoggedIn()) {
        savedItemsState = { wishlist: [], cart: [] };
        renderPosts(currentPage);
        renderGroupSavedDrawer();
        return;
    }

    try {
        const data = await savedItemsApi('/api/saved-items', { method: 'GET', headers: {} });
        savedItemsState = {
            wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
            cart: Array.isArray(data?.cart) ? data.cart : [],
        };
    } catch (_e) {
        savedItemsState = { wishlist: [], cart: [] };
    }

    renderPosts(currentPage);
    renderGroupSavedDrawer();
    renderWriteLinkedItems();
}

function getAttachableSavedRows(source = writeAttachSource) {
    const rows = Array.isArray(savedItemsState[source]) ? savedItemsState[source] : [];
    return rows.filter((row) => isAttachableType(row?.item_type));
}

function updateLinkedCountText() {
    const el = document.getElementById('formLinkedItemsCount');
    if (!el) return;
    el.textContent = `${selectedLinkedItemKeys.size}개 선택`;
}

function renderWriteLinkedItems() {
    const list = document.getElementById('formLinkedItemsList');
    if (!list) return;
    const rows = getAttachableSavedRows(writeAttachSource);
    if (!rows.length) {
        list.innerHTML = '<div class="linked-items-empty">선택 가능한 항목이 없습니다. 먼저 항공/숙박/렌터카를 장바구니 또는 위시에 담아주세요.</div>';
        updateLinkedCountText();
        return;
    }
    list.innerHTML = rows.map((row) => {
        const key = buildLinkedKey(row);
        const checked = selectedLinkedItemKeys.has(key) ? 'checked' : '';
        return `
            <label class="linked-item-row">
                <input type="checkbox" data-linked-item-key="${escapeHtml(key)}" ${checked} />
                <div>
                    <div class="linked-item-row__name">[${escapeHtml(getSavedItemTypeLabel(row.item_type))}] ${escapeHtml(row.name || '-')}</div>
                    <div class="linked-item-row__meta">${escapeHtml(row.meta || '')}</div>
                </div>
            </label>
        `;
    }).join('');
    updateLinkedCountText();
}

function getSelectedLinkedItemsForSubmit() {
    const allRows = [...(savedItemsState.cart || []), ...(savedItemsState.wishlist || [])].filter((row) => isAttachableType(row?.item_type));
    const selected = allRows.filter((row) => selectedLinkedItemKeys.has(buildLinkedKey(row)));
    return selected.map((row) => normalizeLinkedFromSaved(row));
}

async function loadGroupAlerts() {
    try {
        const res = await fetch('/api/group-buy/join-requests/inbox', { credentials: 'include' });
        if (res.status === 401) {
            groupAlertState = [];
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const rows = Array.isArray(data) ? data : [];
        const mineDone = rows.filter((x) => String(x?.direction || '') === 'mine' && ['accepted', 'rejected'].includes(String(x?.status || '')));
        if (!groupAlertInitialized) {
            seenGroupDecisionKeys = new Set(mineDone.map((x) => `${Number(x?.id)}:${String(x?.status || '')}`));
            groupAlertInitialized = true;
        } else {
            const newly = mineDone.filter((x) => {
                const key = `${Number(x?.id)}:${String(x?.status || '')}`;
                if (seenGroupDecisionKeys.has(key)) return false;
                seenGroupDecisionKeys.add(key);
                return true;
            });
            if (newly.length) {
                const msg = newly
                    .map((x) => String(x?.message || '').trim())
                    .filter(Boolean)
                    .join(' / ');
                showToast(msg || '참여요청 결과가 도착했습니다. 장바구니/알림을 확인해 주세요.');
                await loadSavedItems();
            }
        }
        groupAlertState = rows;
    } catch (_e) {
        groupAlertState = [];
    }
}

async function decideGroupAlert(requestId, action) {
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

function renderPosts(page = 1) {
    currentPage = page;
    const listContainer = document.getElementById('boardList');
    const pagination = document.getElementById('pagination');
    if (!listContainer || !pagination) return;

    const totalPages = Math.ceil(posts.length / itemsPerPage) || 1;
    const safePage = Math.min(Math.max(page, 1), totalPages);
    const startIndex = (safePage - 1) * itemsPerPage;
    const pageData = posts.slice(startIndex, startIndex + itemsPerPage);

    listContainer.innerHTML = pageData.map((post) => {
        const wished = isPostWished(post);
        const statusClass = post.status === 'closed' ? 'status-closed' : ((post.max - post.current) <= 1 ? 'status-imminent' : 'status-open');
        return `
            <article class="board-card" data-post-id="${Number(post.id)}">
                <div class="card-left">
                    <div class="card-meta"><span class="badge-country">${escapeHtml(post.country)}</span></div>
                    <div class="board-title">${escapeHtml(post.title)}</div>
                    <div class="board-date"><i data-lucide="calendar" width="14"></i>${escapeHtml(post.start)} 출발 예정 · ${escapeHtml(post.departure || '인천')} 출발${Array.isArray(post.linkedItems) && post.linkedItems.length ? ` · 연결상품 ${post.linkedItems.length}개` : ''}</div>
                </div>
                <div class="card-right">
                    <div class="progress-label">
                        <span><i data-lucide="users" width="14" style="vertical-align:middle"></i> 인원 현황</span>
                        <span class="pax-text"><span class="current-pax">${post.current}</span> / <span class="max-pax">${post.max}명</span></span>
                    </div>
                    <div class="card-footer">
                        <div class="budget-text">${escapeHtml(post.budget)}</div>
                        <div class="status-badge ${statusClass}">${getStatusLabel(post)}</div>
                    </div>
                </div>
                <button class="card-wish-btn ${wished ? 'active' : ''}" type="button" data-wish-post-id="${Number(post.id)}" aria-label="위시리스트">
                    <i data-lucide="heart" width="20" ${wished ? 'fill="currentColor"' : 'fill="none"'}></i>
                </button>
            </article>
        `;
    }).join('');

    pagination.innerHTML = '';
    if (totalPages > 1) {
        for (let i = 1; i <= totalPages; i += 1) {
            const btn = document.createElement('button');
            btn.className = `page-btn ${i === safePage ? 'active' : ''}`;
            btn.type = 'button';
            btn.textContent = String(i);
            btn.addEventListener('click', () => renderPosts(i));
            pagination.appendChild(btn);
        }
    }

    lucide.createIcons();
}

function showDetail(id) {
    const post = getPostById(id);
    if (!post) return;
    currentDetailPostId = Number(post.id);
    const linkedItems = Array.isArray(post.linkedItems) ? post.linkedItems : [];
    const linkedItemsHtml = linkedItems.length
        ? `
            <div class="linked-refs">
                <div style="font-weight:700; font-size:15px;">연결된 상품 정보</div>
                ${linkedItems.map((item) => `
                    <div class="linked-ref-card">
                        <div class="linked-ref-type">${escapeHtml(getSavedItemTypeLabel(item?.item_type))}</div>
                        <div class="linked-ref-name">${escapeHtml(item?.name || '-')}</div>
                        <div class="linked-ref-meta">${escapeHtml(item?.meta || '')}</div>
                    </div>
                `).join('')}
            </div>
        `
        : '';

    const wished = isPostWished(post);
    const header = document.getElementById('detailHeader');
    const body = document.getElementById('detailBody');
    const actions = document.getElementById('detailActions');
    const privacyCheck = document.getElementById('privacyCheck');
    const privacyBox = privacyCheck?.closest('.privacy-box');

    if (privacyCheck) privacyCheck.checked = false;

    if (header) {
        header.innerHTML = `
            <div style="font-size:13px; color:var(--primary-color); font-weight:700; margin-bottom:4px;">공동구매</div>
            <h2 style="font-size:22px;">${escapeHtml(post.title)}</h2>
        `;
    }

    if (body) {
        body.innerHTML = `
            <div style="display:grid; grid-template-columns: 1fr 1.5fr; gap: 15px; margin-bottom:20px;">
                <div style="background:#f0faff; padding:15px; border-radius:12px;">
                    <div style="font-size:11px; color:#0088cc; font-weight:700; margin-bottom:4px;">여행지</div>
                    <div style="font-size:15px; font-weight:700;">${escapeHtml(post.country)} (${escapeHtml(post.city || '미정')})</div>
                </div>
                <div style="background:#f8f9fa; padding:15px; border-radius:12px;">
                    <div style="font-size:11px; color:#666; font-weight:700; margin-bottom:4px;">일정</div>
                    <div style="font-size:15px; font-weight:700;">${escapeHtml(post.start)} 출발</div>
                </div>
            </div>
            <div style="margin-bottom:20px; font-size:14px; color:#333; font-weight:700;">모집 인원: ${Number(post.current || 1)} / ${Number(post.max || 4)}명</div>
            <div style="border-top:1px solid #f0f0f0; padding-top:20px;">
                <div style="font-weight:700; margin-bottom:10px; font-size:15px;">상세 설명</div>
                <p style="white-space:pre-wrap; color:#555; font-size:14px; line-height:1.7;">${escapeHtml(post.desc || '')}</p>
            </div>
            ${linkedItemsHtml}
            <div id="joinRequestFormWrap" style="display:none; margin-top:18px; padding:14px; border:1px solid #e5e7eb; border-radius:12px; background:#fafcff;">
                <div style="font-size:13px; font-weight:700; margin-bottom:10px;">참여 요청 양식</div>
                <div style="display:grid; gap:8px;">
                    <label style="font-size:12px; color:#666;">닉네임</label>
                    <input id="joinReqNickname" type="text" readonly style="padding:10px; border:1px solid #e5e7eb; border-radius:8px; background:#f3f4f6;" />
                    <label style="font-size:12px; color:#666;">이메일</label>
                    <input id="joinReqEmail" type="email" placeholder="연락 가능한 이메일" style="padding:10px; border:1px solid #e5e7eb; border-radius:8px;" />
                    <label style="font-size:12px; color:#666;">세부사항</label>
                    <textarea id="joinReqDetail" rows="3" placeholder="자기소개, 동행 희망사항 등을 적어주세요." style="padding:10px; border:1px solid #e5e7eb; border-radius:8px; resize:vertical;"></textarea>
                </div>
            </div>
        `;
    }

    if (actions) {
        const canApply = !post.isMine && post.status !== 'closed';
        if (privacyBox) {
            privacyBox.style.display = canApply ? 'flex' : 'none';
        }
        actions.innerHTML = `
            <button id="detailWishBtn" class="btn-detail-wish ${wished ? 'active' : ''}" type="button" data-detail-wish-id="${Number(post.id)}">
                <i data-lucide="heart" width="24" ${wished ? 'fill="currentColor"' : 'fill="none"'}></i>
            </button>
            ${post.isMine
                ? '<button class="btn-detail-apply" type="button" disabled style="opacity:.7;cursor:not-allowed;">내 게시글</button><button class="btn-detail-apply" type="button" id="detailDeleteBtn" style="background:#ef4444;">게시글 삭제</button>'
                : (canApply
                    ? '<button class="btn-detail-apply" type="button" id="detailApplyBtn">참여요청</button>'
                    : '<button class="btn-detail-apply" type="button" disabled style="opacity:.7;cursor:not-allowed;">모집 마감</button>')
            }
        `;

        document.getElementById('detailWishBtn')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleWish(post.id);
        });
        document.getElementById('detailApplyBtn')?.addEventListener('click', () => {
            const wrap = document.getElementById('joinRequestFormWrap');
            if (!wrap) return;
            if (wrap.style.display !== 'block') {
                wrap.style.display = 'block';
                const nickInput = document.getElementById('joinReqNickname');
                const emailInput = document.getElementById('joinReqEmail');
                if (nickInput) nickInput.value = currentUserProfile.nickname || String(window.__AUTH?.nickname || '');
                if (emailInput && !emailInput.value) emailInput.value = currentUserProfile.email || '';
                wrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            handleApply();
        });
        document.getElementById('detailDeleteBtn')?.addEventListener('click', () => deleteMyPost(post.id));
    }

    openModal('detailModal');
    lucide.createIcons();
}

async function deleteMyPost(postId) {
    if (!isLoggedIn()) {
        requireLoginMessage();
        return;
    }
    if (!confirm('내 게시글을 삭제할까요?')) return;
    try {
        await groupBuyApi(`/api/group-buy/posts/${Number(postId)}`, { method: 'DELETE', headers: {} });
        closeModal('detailModal');
        await loadGroupBuyPosts();
        await loadGroupAlerts();
        renderGroupSavedDrawer();
        showToast('게시글을 삭제했습니다.');
    } catch (e) {
        if (e?.code === 'LOGIN_REQUIRED') return requireLoginMessage();
        alert(e?.message || '게시글 삭제 중 오류가 발생했습니다.');
    }
}

async function toggleWish(id) {
    const post = getPostById(id);
    if (!post) return;

    if (!isLoggedIn()) {
        requireLoginMessage();
        return;
    }

    const payload = buildGroupbuyPayload(post);
    const key = getGroupbuyKey(payload);
    const existing = (savedItemsState.wishlist || []).find((item) => getGroupbuyKey(item) === key);

    try {
        if (existing) {
            await savedItemsApi(`/api/saved-items/${Number(existing.id)}`, { method: 'DELETE', headers: {} });
            showToast('위시리스트에서 제거했습니다.');
        } else {
            await savedItemsApi('/api/saved-items', { method: 'POST', body: JSON.stringify(payload) });
            showToast('공동구매를 위시리스트에 추가했습니다.');
        }
        await loadSavedItems();
        if (document.getElementById('detailModal')?.style.display === 'flex') {
            showDetail(id);
        }
    } catch (e) {
        if (e?.code === 'LOGIN_REQUIRED') return requireLoginMessage();
        alert(e?.message || '저장 중 오류가 발생했습니다.');
    }
}

function setupPostInteractions() {
    const boardList = document.getElementById('boardList');
    if (!boardList || boardList.dataset.bound === '1') return;
    boardList.dataset.bound = '1';

    boardList.addEventListener('click', (e) => {
        const wishBtn = e.target.closest('[data-wish-post-id]');
        if (wishBtn) {
            e.preventDefault();
            e.stopPropagation();
            const postId = Number(wishBtn.getAttribute('data-wish-post-id'));
            if (!Number.isNaN(postId)) toggleWish(postId);
            return;
        }

        const card = e.target.closest('.board-card[data-post-id]');
        if (!card) return;
        const postId = Number(card.getAttribute('data-post-id'));
        if (!Number.isNaN(postId)) showDetail(postId);
    });
}

async function handleApply() {
    const checked = document.getElementById('privacyCheck')?.checked;
    if (!checked) return alert('개인정보 수집 및 이용 동의가 필요합니다.');
    if (!isLoggedIn()) {
        requireLoginMessage();
        return;
    }
    if (!currentDetailPostId) return;
    try {
        const email = String(document.getElementById('joinReqEmail')?.value || '').trim();
        const detail = String(document.getElementById('joinReqDetail')?.value || '').trim();
        if (!email) return alert('이메일을 입력해주세요.');
        const res = await groupBuyApi(`/api/group-buy/posts/${Number(currentDetailPostId)}/join-requests`, {
            method: 'POST',
            body: JSON.stringify({ email, detail }),
        });
        if (res?.created === false) {
            showToast('이미 요청을 보냈습니다.');
        } else {
            showToast('참여 요청이 접수되었습니다.');
        }
        closeModal('detailModal');
    } catch (e) {
        if (e?.code === 'LOGIN_REQUIRED') return requireLoginMessage();
        alert(e?.message || '요청 처리 중 오류가 발생했습니다.');
    }
}

function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.style.display = 'flex';
    document.body.classList.add('modal-open');
    if (id === 'writeModal') {
        writeAttachSource = 'cart';
        document.querySelectorAll('.attach-source-tab[data-attach-source]').forEach((el) => {
            el.classList.toggle('is-active', el.getAttribute('data-attach-source') === 'cart');
        });
        renderWriteLinkedItems();
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.style.display = 'none';
    document.body.classList.remove('modal-open');

    if (id === 'writeModal') {
        document.getElementById('writeForm')?.reset();
        selectedLinkedItemKeys = new Set();
        const countryDisplay = document.getElementById('formCountryDisplay');
        const cityDisplay = document.getElementById('formCityDisplay');
        if (countryDisplay) countryDisplay.innerText = '나라 선택';
        if (cityDisplay) cityDisplay.innerText = '도시 입력';
        document.getElementById('formCityTrigger')?.classList.add('disabled');
        const list = document.getElementById('formCityList');
        if (list) list.innerHTML = '';
        document.querySelectorAll('.popover-container.active').forEach((el) => el.classList.remove('active'));
        document.getElementById('overlay')?.classList.remove('active');
        renderWriteLinkedItems();
    }
}

function initPopovers() {
    const overlay = document.getElementById('overlay');
    const setup = (triggerId, popId, doneId) => {
        const trigger = document.getElementById(triggerId);
        const pop = document.getElementById(popId);
        const done = document.getElementById(doneId);
        if (!trigger || !pop || !done || !overlay) return;

        trigger.addEventListener('click', (e) => {
            if (trigger.classList.contains('disabled')) return;
            if (pop.contains(e.target)) return;
            e.stopPropagation();
            pop.classList.add('active');
            overlay.classList.add('active');
        });

        pop.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        done.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (triggerId === 'formCountryTrigger') {
                const typed = String(document.getElementById('formCountryInput')?.value || '').trim();
                if (typed) {
                    document.getElementById('formCountryDisplay').innerText = typed;
                    updateFormCities(typed);
                }
            } else if (triggerId === 'formCityTrigger') {
                const typed = String(document.getElementById('formCityInput')?.value || '').trim();
                if (typed) {
                    document.getElementById('formCityDisplay').innerText = typed;
                }
            }

            pop.classList.remove('active');
            overlay.classList.remove('active');
        });
    };

    setup('formCountryTrigger', 'formCountryPopover', 'formCountryDoneBtn');
    setup('formCityTrigger', 'formCityPopover', 'formCityDoneBtn');

    overlay?.addEventListener('click', () => {
        document.querySelectorAll('.popover-container.active').forEach((el) => el.classList.remove('active'));
        overlay.classList.remove('active');
    });
}

function populateRecommendations() {
    const list = document.getElementById('formCountryList');
    if (!list) return;
    list.innerHTML = '';

    RECOMMENDED_COUNTRIES.forEach((country) => {
        const item = document.createElement('div');
        item.className = 'recommend-item';
        item.innerHTML = `<i data-lucide="globe" width="14"></i>${escapeHtml(country)}`;
        item.addEventListener('click', () => {
            document.getElementById('formCountryInput').value = country;
            document.getElementById('formCountryDisplay').innerText = country;
            updateFormCities(country);
        });
        list.appendChild(item);
    });

    lucide.createIcons();
}

function updateFormCities(country) {
    const trigger = document.getElementById('formCityTrigger');
    const display = document.getElementById('formCityDisplay');
    const list = document.getElementById('formCityList');
    if (!trigger || !display || !list) return;

    trigger.classList.remove('disabled');
    display.innerText = '도시 선택';
    list.innerHTML = '';

    (COUNTRY_CITIES[country] || []).forEach((city) => {
        const item = document.createElement('div');
        item.className = 'recommend-item';
        item.innerHTML = `<i data-lucide="map-pin" width="14"></i>${escapeHtml(city)}`;
        item.addEventListener('click', () => {
            document.getElementById('formCityInput').value = city;
            display.innerText = city;
        });
        list.appendChild(item);
    });

    lucide.createIcons();
}

function initDateConstraints() {
    const startInput = document.getElementById('formDateStart');
    const categorySelect = document.getElementById('formCategory');
    if (!startInput) return;

    const now = new Date();
    if (categorySelect?.value !== 'flight') {
        now.setDate(now.getDate() + 120);
    }

    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    startInput.setAttribute('min', `${y}-${m}-${d}`);
}

function updateMinEndDate() {
    const startInput = document.getElementById('formDateStart');
    const endInput = document.getElementById('formDateEnd');
    if (!startInput || !endInput || !startInput.value) return;
    endInput.setAttribute('min', startInput.value);
    if (endInput.value && endInput.value < startInput.value) endInput.value = '';
}

function toggleFormDates() {
    const categorySelect = document.getElementById('formCategory');
    const endDateWrapper = document.getElementById('formEndDateWrapper');
    const endDateInput = document.getElementById('formDateEnd');
    if (!categorySelect || !endDateWrapper || !endDateInput) return;

    if (categorySelect.value === 'flight') {
        endDateWrapper.style.display = 'none';
        endDateInput.removeAttribute('required');
        endDateInput.value = '';
    } else {
        endDateWrapper.style.display = 'block';
        endDateInput.setAttribute('required', 'required');
    }

    initDateConstraints();
}

function formatCurrency(input) {
    const raw = String(input.value || '').replace(/[^0-9]/g, '');
    input.value = raw ? new Intl.NumberFormat('ko-KR').format(Number(raw)) : '';
}

async function handleFormSubmit(e) {
    e.preventDefault();

    const title = document.getElementById('formTitle')?.value?.trim() || '';
    const country = document.getElementById('formCountryDisplay')?.innerText || '나라 선택';
    const city = document.getElementById('formCityDisplay')?.innerText || '도시 입력';
    const maxPeopleRaw = String(document.getElementById('formMaxPeople')?.value || '').trim();
    const maxPeople = Number(maxPeopleRaw);
    const start = document.getElementById('formDateStart')?.value || '';
    const budgetRaw = document.getElementById('formBudget')?.value || '';
    const desc = document.getElementById('formDesc')?.value?.trim() || '';
    const linkedItems = getSelectedLinkedItemsForSubmit();

    if (!title) return alert('제목을 입력해주세요.');
    if (country === '나라 선택') return alert('나라를 선택해주세요.');
    if (!maxPeopleRaw || !Number.isFinite(maxPeople) || maxPeople < 2 || !Number.isInteger(maxPeople)) {
        return alert('모집 인원은 2명 이상 정수로 입력해주세요.');
    }
    if (!start) return alert('출발일을 선택해주세요.');
    if (!linkedItems.length) return alert('장바구니/위시리스트에서 연결할 항공·숙박·렌터카 상품을 최소 1개 선택해주세요.');

    const cityValue = (city === '도시 입력' || city === '도시 선택') ? '' : city;
    const budget = budgetRaw ? `${budgetRaw}원` : '예산 미정';
    if (!isLoggedIn()) {
        requireLoginMessage();
        return;
    }
    try {
        await groupBuyApi('/api/group-buy/posts', {
            method: 'POST',
            body: JSON.stringify({
                category: document.getElementById('formCategory')?.value || 'package',
                title,
                country,
                city: cityValue,
                max_people: maxPeople,
                start_date: start,
                end_date: document.getElementById('formDateEnd')?.value || '',
                departure: '인천',
                budget,
                description: desc,
                linked_items: linkedItems,
            }),
        });
        closeModal('writeModal');
        await loadGroupBuyPosts();
        showToast('모집 글이 등록되었습니다.');
    } catch (err) {
        if (err?.code === 'LOGIN_REQUIRED') return requireLoginMessage();
        alert(err?.message || '게시글 등록에 실패했습니다.');
    }
}

function showToast(msg) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.display = 'flex';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 1800);
}

function getGroupSavedTabItems() {
    return Array.isArray(savedItemsState[groupSavedTab]) ? savedItemsState[groupSavedTab] : [];
}

function setGroupSavedDrawer(open) {
    const drawer = document.getElementById('groupSavedDrawer');
    const fab = document.getElementById('groupSavedFab');
    if (!drawer || !fab) return;
    drawer.classList.toggle('is-open', !!open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function renderGroupSavedDrawer() {
    const listEl = document.getElementById('groupSavedList');
    const emptyEl = document.getElementById('groupSavedEmpty');
    const countEl = document.getElementById('groupSavedFabCount');
    const tabs = document.querySelectorAll('[data-group-saved-tab]');
    if (!listEl || !emptyEl) return;

    const total = (savedItemsState.cart?.length || 0) + (savedItemsState.wishlist?.length || 0) + (groupAlertState?.length || 0);
    if (countEl) {
        countEl.hidden = total === 0;
        countEl.textContent = String(total);
    }

    tabs.forEach((btn) => {
        const isActive = btn.getAttribute('data-group-saved-tab') === groupSavedTab;
        btn.classList.toggle('is-active', isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        if (btn.getAttribute('data-group-saved-tab') === 'alerts') {
            btn.textContent = `알림 (${groupAlertState.length})`;
        }
    });

    if (groupSavedTab === 'alerts') {
        if (!groupAlertState.length) {
            listEl.innerHTML = '';
            emptyEl.style.display = 'block';
            emptyEl.textContent = '도착한 참여 요청 알림이 없습니다.';
            return;
        }
        emptyEl.style.display = 'none';
        listEl.innerHTML = groupAlertState.map((item) => {
            const status = String(item.status || 'pending');
            const statusLabel = status === 'accepted' ? '수락됨' : (status === 'rejected' ? '거절됨' : '대기중');
            const statusChipStyle = status === 'accepted'
                ? 'display:inline-block;padding:2px 8px;border-radius:999px;background:#dcfce7;color:#166534;font-weight:800;'
                : (status === 'rejected'
                    ? 'display:inline-block;padding:2px 8px;border-radius:999px;background:#fee2e2;color:#991b1b;font-weight:800;'
                    : 'display:inline-block;padding:2px 8px;border-radius:999px;background:#fef3c7;color:#92400e;font-weight:800;');
            const incoming = String(item.direction || 'incoming') !== 'mine';
            const reqTitle = incoming
                ? `${escapeHtml(item.requester_name || '-')}님이 요청했습니다`
                : `${escapeHtml(item.requester_name || '작성자')}님의 응답`;
            return `
                <li class="group-saved-item" style="grid-template-columns:1fr;">
                    <div class="group-saved-item__content">
                        <div class="group-saved-item__type">공동구매 · 참여요청</div>
                        <div class="group-saved-item__name">${escapeHtml(item.post_title || '-')}</div>
                        <div class="group-saved-item__meta">${reqTitle}<br>${item.requester_email ? `이메일: ${escapeHtml(item.requester_email)}<br>` : ''}<span style="${statusChipStyle}">${statusLabel}</span>${item.message ? `<br>${escapeHtml(item.message || '')}` : ''}</div>
                        ${
                            incoming && status === 'pending'
                                ? `<div class="group-saved-item__meta">
                                    <button type="button" data-group-alert-action="accept" data-group-alert-id="${Number(item.id)}" title="수락" style="margin-right:6px;padding:4px 8px;border:1px solid #dbeafe;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:700;">수락</button>
                                    <button type="button" data-group-alert-action="reject" data-group-alert-id="${Number(item.id)}" title="거절" style="padding:4px 8px;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:12px;font-weight:700;">거절</button>
                                </div>`
                                : ''
                        }
                        ${
                            status !== 'pending' && !incoming
                                ? `<div class="group-saved-item__meta" style="margin-top:8px;">
                                    <button type="button" data-group-alert-remove="${Number(item.id)}" title="알림 삭제" style="padding:4px 8px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;color:#475569;font-size:12px;font-weight:700;">알림 삭제</button>
                                </div>`
                                : ''
                        }
                    </div>
                </li>
            `;
        }).join('');
        return;
    }

    const items = getGroupSavedTabItems();
    if (!items.length) {
        listEl.innerHTML = '';
        emptyEl.style.display = 'block';
        emptyEl.textContent = groupSavedTab === 'cart' ? '장바구니 항목이 없습니다.' : '위시리스트 항목이 없습니다.';
        return;
    }

    emptyEl.style.display = 'none';
    listEl.innerHTML = items.map((item) => {
        const imageUrl = getGroupSavedImageUrl(item);
        const source = String(item?.source || 'saved-item');
        const typeLabel = getSavedItemTypeLabel(item.item_type || item.type);
        const parts = String(item?.meta || '').split('|').map((x) => x.trim()).filter(Boolean);
        const normalizeKrwPriceText = (text) => {
            const raw = String(text || '').trim();
            if (!raw) return '';
            const m = raw.match(/([\d,]+(?:\.\d+)?)/);
            if (!m) return '';
            const n = Number(String(m[1]).replace(/,/g, ''));
            if (!Number.isFinite(n) || n <= 0) return '';
            return `₩${Math.floor(n).toLocaleString('ko-KR')}`;
        };
        const detectedPriceMeta = parts.find((p) => /[\d,]+(?:\.\d+)?\s*(krw|KRW|원|₩)?/.test(String(p)));
        let priceText = normalizeKrwPriceText(detectedPriceMeta || '');
        if (!priceText) {
            priceText = normalizeKrwPriceText(
                item?.price ||
                item?.payload?.price_text ||
                item?.payload?.price ||
                item?.payload?.amount ||
                item?.payload?.total_price ||
                ''
            );
        }
        const metaLines = parts.filter((p) => p && p !== detectedPriceMeta && !/[\d,]+(?:\.\d+)?\s*(krw|KRW|원|₩)?/.test(String(p)));
        return `
            <li class="group-saved-item">
                <div class="group-saved-item__thumb ${imageUrl ? '' : 'no-image'}">
                    ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(item.name || '')}" loading="lazy" onerror="this.style.display='none';this.parentElement.classList.add('no-image')">` : ''}
                </div>
                <div class="group-saved-item__content">
                    <div class="group-saved-item__type">${escapeHtml(typeLabel)} · ${escapeHtml(source)}</div>
                    <div class="group-saved-item__name">${escapeHtml(item.name || '-')}</div>
                    ${priceText ? `<div class="group-saved-item__meta group-saved-price">${escapeHtml(priceText)}</div>` : ''}
                    ${metaLines.map((line) => `<div class="group-saved-item__meta">${escapeHtml(line)}</div>`).join('')}
                </div>
                <button type="button" class="group-saved-item__remove" data-group-saved-remove="${Number(item.id)}" title="삭제">×</button>
            </li>
        `;
    }).join('');
}

function initGroupSavedDrawer() {
    const fab = document.getElementById('groupSavedFab');
    const drawer = document.getElementById('groupSavedDrawer');
    const listEl = document.getElementById('groupSavedList');
    if (!fab || !drawer || !listEl) return;

    fab.addEventListener('click', () => {
        setGroupSavedDrawer(!drawer.classList.contains('is-open'));
        if (drawer.classList.contains('is-open')) {
            loadGroupAlerts().then(renderGroupSavedDrawer);
        }
    });

    document.querySelectorAll('[data-group-saved-close]').forEach((el) => {
        el.addEventListener('click', () => setGroupSavedDrawer(false));
    });

    document.querySelectorAll('[data-group-saved-tab]').forEach((btn) => {
        btn.addEventListener('click', () => {
            groupSavedTab = btn.getAttribute('data-group-saved-tab') || 'cart';
            if (groupSavedTab === 'alerts') {
                loadGroupAlerts().then(renderGroupSavedDrawer);
                return;
            }
            renderGroupSavedDrawer();
        });
    });

    listEl.addEventListener('click', async (e) => {
        const alertBtn = e.target.closest('[data-group-alert-action]');
        if (alertBtn) {
            const requestId = Number(alertBtn.getAttribute('data-group-alert-id'));
            const action = String(alertBtn.getAttribute('data-group-alert-action') || '');
            if (!requestId || !action) return;
            try {
                await decideGroupAlert(requestId, action);
                await loadGroupAlerts();
                await loadGroupBuyPosts();
                renderGroupSavedDrawer();
            } catch (err) {
                alert(err?.message || '요청 처리 중 오류가 발생했습니다.');
            }
            return;
        }
        const alertRemoveBtn = e.target.closest('[data-group-alert-remove]');
        if (alertRemoveBtn) {
            const requestId = Number(alertRemoveBtn.getAttribute('data-group-alert-remove'));
            if (!requestId) return;
            try {
                await groupBuyApi(`/api/group-buy/join-requests/${requestId}`, { method: 'DELETE' });
                await loadGroupAlerts();
                renderGroupSavedDrawer();
            } catch (err) {
                alert(err?.message || '알림 삭제 중 오류가 발생했습니다.');
            }
            return;
        }
        const removeBtn = e.target.closest('[data-group-saved-remove]');
        if (!removeBtn) return;
        const itemId = Number(removeBtn.getAttribute('data-group-saved-remove'));
        if (Number.isNaN(itemId)) return;

        try {
            await savedItemsApi(`/api/saved-items/${itemId}`, { method: 'DELETE', headers: {} });
            await loadSavedItems();
        } catch (err) {
            if (err?.code === 'LOGIN_REQUIRED') return requireLoginMessage();
            alert(err?.message || '삭제 중 오류가 발생했습니다.');
        }
    });

    window.addEventListener('focus', () => {
        if (drawer.classList.contains('is-open')) {
            loadGroupAlerts().then(renderGroupSavedDrawer);
        }
    });

    renderGroupSavedDrawer();
}

function initWriteButtonGuard() {
    const writeBtn = document.querySelector('.btn-write');
    if (!writeBtn) return;
    writeBtn.onclick = null;
    writeBtn.addEventListener('click', (e) => {
        if (!isLoggedIn()) {
            e.preventDefault();
            requireLoginMessage();
            return;
        }
        openModal('writeModal');
    });
}

function initWriteLinkedItemsUi() {
    document.querySelectorAll('.attach-source-tab[data-attach-source]').forEach((btn) => {
        btn.addEventListener('click', () => {
            writeAttachSource = btn.getAttribute('data-attach-source') || 'cart';
            document.querySelectorAll('.attach-source-tab[data-attach-source]').forEach((el) => {
                const active = el === btn;
                el.classList.toggle('is-active', active);
            });
            renderWriteLinkedItems();
        });
    });

    document.getElementById('formLinkedItemsList')?.addEventListener('change', (e) => {
        const target = e.target;
        if (!(target instanceof HTMLInputElement)) return;
        if (target.type !== 'checkbox') return;
        const key = String(target.getAttribute('data-linked-item-key') || '');
        if (!key) return;
        if (target.checked) selectedLinkedItemKeys.add(key);
        else selectedLinkedItemKeys.delete(key);
        updateLinkedCountText();
    });

    document.getElementById('formLinkedItemsSelectAll')?.addEventListener('click', () => {
        const rows = getAttachableSavedRows(writeAttachSource);
        const keys = rows.map((row) => buildLinkedKey(row));
        const allSelected = keys.length > 0 && keys.every((k) => selectedLinkedItemKeys.has(k));
        keys.forEach((k) => {
            if (allSelected) selectedLinkedItemKeys.delete(k);
            else selectedLinkedItemKeys.add(k);
        });
        renderWriteLinkedItems();
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    setupPostInteractions();
    initPopovers();
    initWriteLinkedItemsUi();
    populateRecommendations();
    initDateConstraints();
    initGroupSavedDrawer();
    initWriteButtonGuard();
    await loadCurrentUserProfile();
    await loadGroupBuyPosts();
    await loadSavedItems();
    await loadGroupAlerts();
    renderGroupSavedDrawer();
    setInterval(async () => {
        await loadGroupAlerts();
        renderGroupSavedDrawer();
    }, 15000);
    lucide.createIcons();
});

window.addEventListener('focus', () => {
    loadGroupBuyPosts();
    loadSavedItems();
});
