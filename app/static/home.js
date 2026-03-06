/**
 * 여행사 메인 비주얼 슬라이더 스크립트
 */

const sliderData = [
    {
    sub: "공동구매",
    title: "항공+숙소 공동구매 OPEN",
    desc: "지금 이 순간에도 인원이 차고 있어요.<br>마지막 티켓의 주인공은?",
    img: "https://cdn.pixabay.com/photo/2023/10/11/13/41/ship-8308680_1280.jpg",
    },
    {
    sub: "Tour",
    title: "대만 티켓 할인 혜택",
    desc: "타이베이 101부터 지우펀 홍등까지,<br>가장 똑똑하게 예약하는 방법",
    img: "https://media.istockphoto.com/id/479711387/ko/%EC%82%AC%EC%A7%84/taipei-taiwan.jpg?b=1&s=1024x1024&w=0&k=20&c=xsLCTGo6uqq_lGoReEoVyleyoIj-bOFE5LPlE94hKcc=",
    },
    {
    sub: "2026 EVENT",
    title: "상하이 예원 등불 축제",
    desc: "1월 26일 그랜드 오픈!<br>붉은 등불 아래 인생샷을 남겨보세요.",
    img: "https://cdn.pixabay.com/photo/2020/09/04/08/02/cityscape-5543224_1280.jpg",
    },
    {
    sub: "SPRING EDITION",
    title: "일본 벚꽃 개화 시기 확정!",
    desc: "핑크빛 꽃길이 열리는 순간,<br>가장 가까운 곳에서 봄을 맞이하세요.",
    img: "https://images.pexels.com/photos/1440476/pexels-photo-1440476.jpeg?auto=compress&cs=tinysrgb&w=1200",
    },
    {
    sub: "GLOBAL PASS",
    title: "유레일패스 25% OFF",
    desc: "낭만 가득한 유럽 배낭여행,<br>교통비 고민은 미리 해결하고 떠나세요.",
    img: "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?auto=format&fit=crop&w=1600&q=80",
    },
    {
    sub: "STAY FOCUS",
    title: "제주 독채 자쿠지 단독 예약",
    desc: "돌담 너머 파도 소리와 풍경까지,<br>여유를 즐기는 프라이빗한 휴식의 정석.",
    img: "https://cdn.pixabay.com/photo/2020/03/23/02/52/pension-4959272_1280.jpg",
    },
];

const wrapper = document.getElementById('sliderWrapper');
const currentTxt = document.getElementById('currentIdx');
const totalTxt = document.getElementById('totalIdx');
const progressFill = document.getElementById('progressFill');

let currentIndex = 1; // 무한루프용 클론 때문에 1부터 시작
let isTransitioning = false;
const slideCount = sliderData.length;
const slideDuration = 5000; // 5초 자동 전환

/**
 * 슬라이더 초기화 및 클론 생성
 */
function initSlider() {
    const firstClone = sliderData[0];
    const lastClone = sliderData[slideCount - 1];
    const extendedData = [lastClone, ...sliderData, firstClone];

    extendedData.forEach((data) => {
        const slide = document.createElement('div');
        slide.className = 'slide-item';
        slide.style.backgroundImage = `url('${data.img}')`;
        slide.innerHTML = `
            <div class="slide-content">
                <span class="slide-sub">${data.sub}</span>
                <h2 class="slide-title">${data.title}</h2>
                <p class="slide-desc">${data.desc}</p>
                <a href="#" class="btn-event-link">자세히 보기</a>
            </div>
        `;
        wrapper.appendChild(slide);
    });

    totalTxt.innerText = slideCount.toString().padStart(2, '0');
    updateSlider(false);
}

/**
 * 슬라이더 위치 및 상태 업데이트
 */
function updateSlider(withTransition = true) {
    if (withTransition) {
        wrapper.style.transition = 'transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
    } else {
        wrapper.style.transition = 'none';
    }

    wrapper.style.transform = `translateX(-${currentIndex * 100}%)`;

    // 액티브 클래스 관리 (애니메이션 트리거)
    const allSlides = document.querySelectorAll('.slide-item');
    allSlides.forEach((s) => s.classList.remove('active-slide'));

    // UI상 표시될 인덱스 계산
    let displayIdx = currentIndex;
    if (currentIndex === 0) displayIdx = slideCount;
    else if (currentIndex > slideCount) displayIdx = 1;

    allSlides[currentIndex].classList.add('active-slide');
    currentTxt.innerText = displayIdx.toString().padStart(2, '0');

    resetProgressBar();
}

/**
 * 무한 루프 처리를 위한 트랜지션 엔드 리스너
 */
wrapper.addEventListener('transitionend', () => {
    isTransitioning = false;
    if (currentIndex === 0) {
        currentIndex = slideCount;
        updateSlider(false);
    } else if (currentIndex === slideCount + 1) {
        currentIndex = 1;
        updateSlider(false);
    }
});

function moveNext() {
    if (isTransitioning) return;
    isTransitioning = true;
    currentIndex++;
    updateSlider();
}

function movePrev() {
    if (isTransitioning) return;
    isTransitioning = true;
    currentIndex--;
    updateSlider();
}

/**
 * 하단 프로그레스 바 및 자동 넘김 제어
 */
let progressInterval;
function resetProgressBar() {
    clearInterval(progressInterval);
    let width = 0;
    progressFill.style.width = '0%';

    const step = 100 / (slideDuration / 100);
    progressInterval = setInterval(() => {
        width += step;
        progressFill.style.width = width + '%';
        if (width >= 100) {
            clearInterval(progressInterval);
            moveNext();
        }
    }, 100);
}

// 버튼 클릭 이벤트 리스너
document.getElementById('nextBtn').addEventListener('click', moveNext);
document.getElementById('prevBtn').addEventListener('click', movePrev);

function parseBackgroundImageUrl(value) {
    const s = String(value || '');
    const m = s.match(/url\((['"]?)(.*?)\1\)/i);
    return m && m[2] ? m[2] : '';
}

function parsePriceToDigits(value) {
    const matches = String(value || '').match(/\d[\d,]*/g) || [];
    const last = matches.length ? matches[matches.length - 1] : '0';
    return last.replace(/[^\d]/g, '');
}

function buildDetailUrl(path, params) {
    const qs = new URLSearchParams(params);
    return `${path}?${qs.toString()}`;
}

function initHotDealNavigation() {
    const cards = document.querySelectorAll('.grid-4 .product-card');
    cards.forEach((card, index) => {
        const title = (card.querySelector('.p-title')?.textContent || '').trim();
        const loc = (card.querySelector('.p-subtitle')?.textContent || '').trim();
        const priceText = (card.querySelector('.p-price')?.textContent || '').trim();
        const price = parsePriceToDigits(priceText);
        const imgBox = card.querySelector('.img-box');
        const image = parseBackgroundImageUrl(window.getComputedStyle(imgBox || card).backgroundImage || '');
        const id = `home_pack_${index + 1}`;
        const href = buildDetailUrl('/pack-detail', {
            id,
            title,
            price,
            img: image,
            loc,
            category: 'package',
        });
        card.setAttribute('href', href);
    });
}

function initAiHotplaceNavigation() {
    const typeLabelMap = {
        landmark: '랜드마크',
        activity: '익스트림',
        unique: '이색체험',
        photo: '포토존',
    };

    const cards = document.querySelectorAll('.ai-card');
    cards.forEach((card, index) => {
        const title = (card.querySelector('.product-name')?.textContent || '').trim();
        const type = String(card.getAttribute('data-type') || '').trim();
        const loc = typeLabelMap[type] || '티켓';
        const priceText = (card.querySelector('.price')?.textContent || '').trim();
        const price = parsePriceToDigits(priceText);
        const image = (card.querySelector('img')?.getAttribute('src') || '').trim();
        const id = `home_tour_${index + 1}`;
        const href = buildDetailUrl('/tour-detail', {
            id,
            title,
            price,
            img: image,
            loc,
            category: 'ticket',
        });
        card.setAttribute('href', href);
    });
}

/* 공동구매 */
let bookings = [];

// 설정 도우미 함수들
const getCategoryLabel = (cat) => ({
    flight: '항공',
    roundtrip: '항공',
    hotel: '호텔',
    package: '항공+호텔',
    flight_hotel: '항공+호텔',
}[cat] || '기타');

const getStatusConfig = (status) => {
    const configs = {
        recruiting: { label: '모집중', className: 'status-recruiting' },
        imminent: { label: '마감임박', className: 'status-imminent' },
        closed: { label: '모집완료', className: 'status-closed' },
        open: { label: '모집중', className: 'status-recruiting' },
    };
    return configs[status] || { label: '미상', className: 'status-closed' };
};

const formatDate = (dateString) => {
    const s = String(dateString || '');
    if (s.length >= 10) return s.substring(5, 10).replace('-', '.');
    return s;
};

async function loadLiveGroupBookings() {
    try {
        const res = await fetch('/api/group-buy/posts', { credentials: 'same-origin' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rows = await res.json();
        const list = Array.isArray(rows) ? rows : [];
        bookings = list.slice(0, 6).map((row) => {
            const maxPeople = Number(row?.max_people || 4);
            const currentPeople = Number(row?.current_people || 1);
            const statusRaw = String(row?.status || 'open').toLowerCase();
            const status = statusRaw === 'closed'
                ? 'closed'
                : ((maxPeople - currentPeople) <= 1 ? 'imminent' : 'recruiting');
            return {
                id: Number(row?.id || 0),
                status,
                category: String(row?.category || 'package').toLowerCase(),
                destination: row?.city || row?.country || '여행지',
                title: row?.title || '공동구매 모집글',
                startDate: row?.start_date || '',
                endDate: row?.end_date || '',
                currentPax: currentPeople,
                maxPax: maxPeople,
            };
        });
    } catch (_e) {
        bookings = [];
    }
    renderBookings();
}

// 렌더링 함수
function renderBookings() {
    const listContainer = document.getElementById('booking-list');
    if (!listContainer) return;
    if (!bookings.length) {
        listContainer.innerHTML = `
            <div class="booking-item">
                <div class="content-area">
                    <h3 class="booking-title">진행 중인 공동구매가 없습니다.</h3>
                </div>
            </div>
        `;
        return;
    }
    
    // 최대 4개까지만 노출
    const limitedBookings = bookings.slice(0, 4);
    listContainer.innerHTML = limitedBookings.map(booking => {
        const categoryLabel = getCategoryLabel(booking.category);
        const stat = getStatusConfig(booking.status);
        const isClosed = booking.status === 'closed';

        return `
            <div class="booking-item ${isClosed ? 'closed' : 'active'}">
                <div class="content-area">
                    <div class="badge-row">
                        <span class="status-badge ${stat.className}">${stat.label}</span>
                        <span class="divider"></span>
                        <span class="category-label">${categoryLabel}</span>
                    </div>
                    <h3 class="booking-title">
                        <span class="dest">[${booking.destination}]</span>${booking.title}
                    </h3>
                    <div class="date-info">
                        ${formatDate(booking.startDate)}${booking.endDate ? ` — ${formatDate(booking.endDate)}` : ''}
                    </div>
                </div>
                <div class="pax-area">
                    <div class="pax-count">
                        <span class="pax-current ${isClosed ? 'is-closed' : ''}">${booking.currentPax}</span>
                        <span class="pax-max"> / ${booking.maxPax}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Lucide 아이콘 초기화 (동적 생성 후 실행 필요)
    lucide.createIcons();
}

// 초기 실행
renderBookings();

/*AI 핫플레이스 탭 메뉴 및 필터링 기능*/
function initAiTabs() {
    const tabs = document.querySelectorAll('#tab-menu li');
    const cards = document.querySelectorAll('.ai-card');

    // 탭 메뉴가 실제로 존재하는지 확인
    if (tabs.length === 0) return;

    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            const category = tab.getAttribute('data-category');

            // 1. 활성 탭 교체
            tabs.forEach((t) => t.classList.remove('active'));
            tab.classList.add('active');

            // 2. 카드 필터링
            cards.forEach((card) => {
                const cardType = card.getAttribute('data-type');
                if (cardType === category) {
                    card.classList.add('show');
                } else {
                    card.classList.remove('show');
                }
            });
        });
    });
}

// 모든 초기화 로직을 하나로 합치기
document.addEventListener('DOMContentLoaded', () => {
    initSlider();     // 슬라이더 초기화
    loadLiveGroupBookings(); // 공동구매 리스트 DB 실시간 로드
    initAiTabs();     // AI 탭 초기화 (추가)
    initHotDealNavigation(); // 패키지 핫딜 상세 연결
    initAiHotplaceNavigation(); // 티켓 핫플레이스 상세 연결
    initHomeSavedDrawer(); // 공통 장바구니/위시리스트 드로어
});

window.addEventListener('focus', () => {
    loadLiveGroupBookings();
});

/* 홈 공통 저장목록(장바구니/위시리스트) */
let homeSavedTab = 'cart';
let homeSavedState = { cart: [], wishlist: [] };
let homeAlertState = [];
const HOME_SAVED_COUNTRY_IMAGE = {
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

async function homeSavedApi(path = '/api/saved-items', options = {}) {
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

function homeSavedEscape(v) {
    return String(v ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function homeSavedAirlineLogo(code) {
    if (!code) return '';
    return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(String(code).toUpperCase())}.png`;
}

function homeSavedTypeLabel(itemType) {
    const type = String(itemType || '').toLowerCase();
    if (type === 'flight') return '항공';
    if (type === 'hotel' || type === 'stay' || type === 'accommodation') return '숙박';
    if (type === 'groupbuy' || type === 'travel-group') return '공동구매';
    return type ? type.toUpperCase() : 'ITEM';
}

function homeSavedCountryKey(country) {
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

function homeSavedImageUrl(item) {
    const p = item?.payload || {};
    if (item?.item_type === 'flight') {
        return homeSavedAirlineLogo(p?.airline_code || '');
    }
    const direct = p?.image_url || p?.image || p?.thumbnail || p?.photo || (Array.isArray(p?.images) ? p.images[0] : '');
    if (direct) return direct;
    if (String(item?.item_type || '').toLowerCase() === 'groupbuy' || String(item?.item_type || '').toLowerCase() === 'travel-group') {
        return HOME_SAVED_COUNTRY_IMAGE[homeSavedCountryKey(p?.country)] || HOME_SAVED_COUNTRY_IMAGE.default;
    }
    return '';
}

function homeSavedMetaParts(item) {
    const raw = String(item?.meta || '').trim();
    const parts = raw.split('|').map((x) => x.trim()).filter(Boolean);
    return {
        price: parts[0] || '',
        lines: parts.slice(1, 3),
    };
}

function homeSavedItemHtml(item) {
    const img = homeSavedImageUrl(item);
    const kind = `${homeSavedTypeLabel(item?.item_type)} · ${item?.source || 'saved-item'}`;
    const meta = homeSavedMetaParts(item);
    const lines = (meta.lines || []).map((line) => `<div class="home-saved-line">${homeSavedEscape(line)}</div>`).join('');
    return `
        <div class="home-saved-item" data-saved-id="${Number(item.id)}">
            <div class="home-saved-thumb">
                ${img ? `<img src="${homeSavedEscape(img)}" alt="${homeSavedEscape(item?.name || '')}" loading="lazy" onerror="this.remove()">` : ''}
            </div>
            <div class="home-saved-meta">
                <div class="home-saved-kind">${homeSavedEscape(kind)}</div>
                <div class="home-saved-name">${homeSavedEscape(item?.name || '(이름 없음)')}</div>
                ${meta.price ? `<div class="home-saved-line home-saved-price">${homeSavedEscape(meta.price)}</div>` : ''}
                ${lines}
            </div>
            <button type="button" class="home-saved-remove" data-saved-remove="${Number(item.id)}" aria-label="삭제">×</button>
        </div>
    `;
}

async function loadHomeSavedItems() {
    try {
        const data = await homeSavedApi('/api/saved-items', { method: 'GET', headers: {} });
        homeSavedState = {
            cart: Array.isArray(data?.cart) ? data.cart : [],
            wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
        };
    } catch (e) {
        if (e?.code !== 'LOGIN_REQUIRED') {
            console.warn('home saved-items load failed', e);
        }
        homeSavedState = { cart: [], wishlist: [] };
    }
    renderHomeSavedDrawer();
}

async function loadHomeAlerts() {
    try {
        const res = await fetch('/api/group-buy/join-requests/inbox', { credentials: 'include' });
        if (res.status === 401) {
            homeAlertState = [];
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        homeAlertState = Array.isArray(data) ? data : [];
    } catch (_e) {
        homeAlertState = [];
    }
}

async function decideHomeAlert(requestId, action) {
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

function setHomeSavedDrawer(open) {
    const drawer = document.getElementById('homeSavedDrawer');
    const fab = document.getElementById('homeSavedFab');
    if (!drawer || !fab) return;
    drawer.classList.toggle('is-open', !!open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    // is-open 클래스 토글 (장바구니 버튼 이미지 변경)
    fab.classList.toggle('is-open', !!open);
}

function renderHomeSavedDrawer() {
    const listEl = document.getElementById('homeSavedList');
    const emptyEl = document.getElementById('homeSavedEmpty');
    const countEl = document.getElementById('homeSavedFabCount');
    const tabs = document.querySelectorAll('[data-home-saved-tab]');
    if (!listEl || !emptyEl) return;

    const cartCount = homeSavedState.cart?.length || 0;
    const wishCount = homeSavedState.wishlist?.length || 0;
    const alertCount = homeAlertState?.length || 0;
    const total = cartCount + wishCount + alertCount;
    if (countEl) {
        countEl.hidden = total === 0;
        countEl.textContent = String(total);
    }

    tabs.forEach((btn) => {
        const tab = btn.getAttribute('data-home-saved-tab');
        btn.classList.toggle('is-active', tab === homeSavedTab);
    });

    if (homeSavedTab === 'alerts') {
        if (!homeAlertState.length) {
            listEl.innerHTML = '';
            emptyEl.style.display = 'block';
            emptyEl.textContent = '도착한 참여 요청 알림이 없습니다.';
            return;
        }
        emptyEl.style.display = 'none';
        listEl.innerHTML = homeAlertState.map((item) => {
            const status = String(item.status || 'pending');
            const statusLabel = status === 'accepted' ? '수락됨' : (status === 'rejected' ? '거절됨' : '대기중');
            const incoming = String(item.direction || 'incoming') !== 'mine';
            const reqTitle = incoming
                ? `${homeSavedEscape(item.requester_name || '')}님이 요청했습니다`
                : `${homeSavedEscape(item.requester_name || '작성자')}님의 응답`;
            return `
                <div class="home-saved-item" data-alert-id="${Number(item.id)}" style="grid-template-columns:1fr;">
                    <div class="home-saved-meta">
                        <div class="home-saved-kind">공동구매 · 참여요청</div>
                        <div class="home-saved-name">${homeSavedEscape(item.post_title || '')}</div>
                        <div class="home-saved-line">${reqTitle}</div>
                        ${item.requester_email ? `<div class="home-saved-line">이메일: ${homeSavedEscape(item.requester_email || '')}</div>` : ''}
                        ${item.message ? `<div class="home-saved-line">${homeSavedEscape(item.message || '')}</div>` : ''}
                        <div class="home-saved-line">${statusLabel}</div>
                        ${
                            incoming && status === 'pending'
                                ? `<div class="home-saved-line">
                                    <button type="button" data-alert-action="accept" data-alert-id="${Number(item.id)}" class="home-saved-close">수락</button>
                                    <button type="button" data-alert-action="reject" data-alert-id="${Number(item.id)}" class="home-saved-close">거절</button>
                                </div>`
                                : ''
                        }
                        ${
                            status !== 'pending'
                                ? `<div class="home-saved-line">
                                    <button type="button" data-alert-remove="${Number(item.id)}" class="home-saved-close">알림 삭제</button>
                                </div>`
                                : ''
                        }
                    </div>
                </div>
            `;
        }).join('');
        return;
    }

    const items = Array.isArray(homeSavedState[homeSavedTab]) ? homeSavedState[homeSavedTab] : [];
    if (!items.length) {
        listEl.innerHTML = '';
        emptyEl.style.display = 'block';
        emptyEl.textContent = homeSavedTab === 'wishlist' ? '위시리스트 항목이 없습니다.' : '장바구니 항목이 없습니다.';
        return;
    }

    emptyEl.style.display = 'none';
    listEl.innerHTML = items.map(homeSavedItemHtml).join('');
}

async function removeHomeSavedItem(itemId) {
    try {
        await homeSavedApi(`/api/saved-items/${itemId}`, { method: 'DELETE', headers: {} });
        homeSavedState.cart = (homeSavedState.cart || []).filter((x) => Number(x.id) !== Number(itemId));
        homeSavedState.wishlist = (homeSavedState.wishlist || []).filter((x) => Number(x.id) !== Number(itemId));
        renderHomeSavedDrawer();
    } catch (e) {
        if (e?.code === 'LOGIN_REQUIRED') {
            if (confirm('로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?')) location.href = '/login';
            return;
        }
        alert(e?.message || '삭제 중 오류가 발생했습니다.');
    }
}

function initHomeSavedDrawer() {
    const fab = document.getElementById('homeSavedFab');
    const drawer = document.getElementById('homeSavedDrawer');
    const closeBtn = document.getElementById('homeSavedDrawerClose');
    const listEl = document.getElementById('homeSavedList');
    if (!fab || !drawer || !closeBtn || !listEl) return;

    fab.addEventListener('click', () => {
        const open = !drawer.classList.contains('is-open');
        setHomeSavedDrawer(open);
        if (open) {
            loadHomeSavedItems();
            loadHomeAlerts().then(renderHomeSavedDrawer);
        }
    });
    closeBtn.addEventListener('click', () => setHomeSavedDrawer(false));

    document.querySelectorAll('[data-home-saved-tab]').forEach((btn) => {
        btn.addEventListener('click', () => {
            homeSavedTab = btn.getAttribute('data-home-saved-tab') || 'cart';
            if (homeSavedTab === 'alerts') {
                loadHomeAlerts().then(renderHomeSavedDrawer);
                return;
            }
            renderHomeSavedDrawer();
        });
    });

    listEl.addEventListener('click', (e) => {
        const alertActionBtn = e.target.closest('[data-alert-action]');
        if (alertActionBtn) {
            const alertId = Number(alertActionBtn.getAttribute('data-alert-id'));
            const action = String(alertActionBtn.getAttribute('data-alert-action') || '');
            if (!alertId || !action) return;
            decideHomeAlert(alertId, action)
                .then(async () => {
                    await loadHomeAlerts();
                    await loadLiveGroupBookings();
                    renderHomeSavedDrawer();
                })
                .catch((err) => alert(err?.message || '요청 처리 중 오류가 발생했습니다.'));
            return;
        }
        const alertRemoveBtn = e.target.closest('[data-alert-remove]');
        if (alertRemoveBtn) {
            const alertId = Number(alertRemoveBtn.getAttribute('data-alert-remove'));
            if (!alertId) return;
            fetch(`/api/group-buy/join-requests/${alertId}`, { method: 'DELETE', credentials: 'include' })
                .then(async (res) => {
                    if (!res.ok) {
                        const d = await res.json().catch(() => ({}));
                        throw new Error(d?.detail || `HTTP ${res.status}`);
                    }
                    await loadHomeAlerts();
                    renderHomeSavedDrawer();
                })
                .catch((err) => alert(err?.message || '알림 삭제 중 오류가 발생했습니다.'));
            return;
        }
        const removeBtn = e.target.closest('[data-saved-remove]');
        if (!removeBtn) return;
        const itemId = Number(removeBtn.getAttribute('data-saved-remove'));
        if (!itemId) return;
        removeHomeSavedItem(itemId);
    });

    document.addEventListener('click', (e) => {
        if (!drawer.classList.contains('is-open')) return;
        if (drawer.contains(e.target) || fab.contains(e.target)) return;
        setHomeSavedDrawer(false);
    });

    window.addEventListener('focus', () => {
        if (drawer.classList.contains('is-open')) {
            loadHomeSavedItems();
            loadHomeAlerts().then(renderHomeSavedDrawer);
        }
    });

    loadHomeSavedItems();
    loadHomeAlerts().then(renderHomeSavedDrawer);
}
