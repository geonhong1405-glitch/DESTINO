// ========== airport drawer logic 1:1 (DB 연동) ========== //

// ====== Toast 메시지 함수 ======
function showToast(message, duration = 2000) {
    let toast = document.getElementById('customToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'customToast';
        toast.style.position = 'fixed';
        toast.style.bottom = '40px';
        toast.style.left = '50%';
        toast.style.transform = 'translateX(-50%)';
        toast.style.background = 'rgba(30,30,30,0.95)';
        toast.style.color = '#fff';
        toast.style.padding = '12px 24px';
        toast.style.borderRadius = '24px';
        toast.style.fontSize = '1rem';
        toast.style.zIndex = '9999';
        toast.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.opacity = '1';
    toast.style.pointerEvents = 'auto';
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.pointerEvents = 'none';
    }, duration);
}
let savedItemState = { wishlist: [], cart: [] };
let tourSavedDrawerTab = 'cart';

// DB에서 장바구니/위시리스트 동기화
async function loadSavedItems() {
    try {
        const res = await fetch('/api/saved-items', { credentials: 'same-origin' });
        if (res.status === 401) {
            savedItemState = { wishlist: [], cart: [] };
            renderFlightSavedDrawer();
            return;
        }
        const data = await res.json();
        savedItemState = {
            wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
            cart: Array.isArray(data?.cart) ? data.cart : [],
        };
        renderFlightSavedDrawer();
    } catch (e) {
        savedItemState = { wishlist: [], cart: [] };
        renderFlightSavedDrawer();
    }
}

function getCurrentProductInfo() {
    const params = new URLSearchParams(window.location.search);
    const category = params.get('category') || 'package';
    const id = params.get('id');
    if (!id) return {};
    const title = document.querySelector('h2.text-2xl.font-black')?.innerText || '';
    const loc = document.querySelector('.fa-location-dot')?.parentElement?.innerText?.trim() || '';
    const price = document.getElementById('productPrice')?.innerText || '';
    const img = document.getElementById('productImg')?.src || '';
    return {
        item_type: category,
        name: title,
        meta: loc,
        price,
        image: img,
        id: id
    };
}

function getSavedItemKey(item) {
    return `${String(item?.item_type || '').toLowerCase()}__${String(item?.name || '').toLowerCase()}__${String(item?.meta || '').toLowerCase()}__${String(item?.price || '').toLowerCase()}`;
}

function hasSavedItem(listType, item) {
    // payload.id(프론트 상품 id)와 비교
    if (item.id) {
        return (savedItemState[listType] || []).some((x) => {
            if (x.payload && x.payload.id) {
                return String(x.payload.id) === String(item.id);
            }
            return false;
        });
    } else {
        const key = getSavedItemKey(item);
        return (savedItemState[listType] || []).some((x) => getSavedItemKey(x) === key);
    }
}

function renderFlightSavedDrawer() {
    const listEl = document.getElementById('flightSavedList');
    const emptyEl = document.getElementById('flightSavedEmpty');
    const countEl = document.getElementById('flightSavedFabCount');
    const tabs = Array.from(document.querySelectorAll('[data-flight-saved-tab]'));
    if (!listEl || !emptyEl) return;
    const total = (savedItemState.cart?.length || 0) + (savedItemState.wishlist?.length || 0);
    if (countEl) {
        countEl.hidden = false;
        countEl.textContent = String(total || 0);
    }
    tabs.forEach((btn) => {
        const active = btn.getAttribute('data-flight-saved-tab') === tourSavedDrawerTab;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    if (tourSavedDrawerTab === 'alerts') {
        listEl.innerHTML = '';
        emptyEl.style.display = 'block';
        emptyEl.textContent = '알림 기능은 미지원입니다.';
        return;
    }
    const items = Array.isArray(savedItemState[tourSavedDrawerTab]) ? savedItemState[tourSavedDrawerTab] : [];
    listEl.innerHTML = '';
    emptyEl.style.display = items.length ? 'none' : 'block';
    emptyEl.textContent = tourSavedDrawerTab === 'wishlist' ? '위시리스트 항목이 없습니다.' : '장바구니 항목이 없습니다.';
    items.forEach((item) => {
        const li = document.createElement('li');
        li.className = 'flight-saved-item';
        li.innerHTML = `
            <div class="flight-saved-item__type">${item.item_type === 'tour' ? '투어' : (item.item_type || 'item')}</div>
            <div class="flight-saved-item__name">${item.name || '-'}</div>
            <div class="flight-saved-item__meta">${item.meta || ''}${item.price ? `<br><b>${item.price}원</b>` : ''}</div>
            <button type="button" class="flight-saved-item__remove" data-flight-saved-remove="${item.id}" title="삭제">×</button>
            ${item.image ? `<img src="${item.image}" alt="${item.name}" style="width:38px;height:38px;object-fit:cover;position:absolute;top:10px;left:10px;border-radius:8px;">` : ''}
        `;
        listEl.appendChild(li);
    });
}

function setFlightSavedDrawer(open) {
    const drawer = document.getElementById('flightSavedDrawer');
    const fab = document.getElementById('flightSavedFab');
    if (!drawer || !fab) return;
    drawer.classList.toggle('is-open', !!open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
}


function initFlightSavedDrawer() {
    const fab = document.getElementById('flightSavedFab');
    const drawer = document.getElementById('flightSavedDrawer');
    const listEl = document.getElementById('flightSavedList');
    if (!fab || !drawer) return;
    fab.addEventListener('click', () => {
        setFlightSavedDrawer(!drawer.classList.contains('is-open'));
        if (drawer.classList.contains('is-open')) loadSavedItems();
    });
    document.querySelectorAll('[data-flight-saved-close]').forEach((el) => {
        el.addEventListener('click', () => setFlightSavedDrawer(false));
    });
    document.querySelectorAll('[data-flight-saved-tab]').forEach((btn) => {
        btn.addEventListener('click', () => {
            tourSavedDrawerTab = btn.getAttribute('data-flight-saved-tab') || 'cart';
            loadSavedItems();
        });
    });
    listEl?.addEventListener('click', async (e) => {
        const btn = e.target.closest('[data-flight-saved-remove]');
        if (!btn) return;
        const itemId = Number(btn.getAttribute('data-flight-saved-remove'));
        if (Number.isNaN(itemId)) return;
        // 서버에 id로 삭제 요청
        try {
            await fetch(`/api/saved-items/${itemId}`, { method: 'DELETE', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' } });
            // 클라이언트 상태에서도 제거
            savedItemState[tourSavedDrawerTab] = (savedItemState[tourSavedDrawerTab] || []).filter((x) => Number(x.id) !== itemId);
            renderFlightSavedDrawer();
        } catch (err) {
            alert('삭제 중 오류가 발생했습니다.');
        }
    });
    renderFlightSavedDrawer();
}


// 로그인 체크 함수 (템플릿에서 window.isLoggedIn = true/false로 세팅 필요)
function requireLoginMessage() {
    if (confirm('로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?')) {
        location.href = '/login';
    }
}

function isUserLoggedIn() {
    return typeof window.isLoggedIn !== 'undefined' && window.isLoggedIn === true;
}

// 찜/장바구니 버튼에서 호출
function toggleWish() {
    if (!isUserLoggedIn()) return requireLoginMessage();
    const product = getCurrentProductInfo();
    const wishBtn = document.getElementById('wishBtn');
    const exists = hasSavedItem('wishlist', product);
    // 즉시 UI 반영
    if (wishBtn) {
        if (!exists) {
            wishBtn.classList.add('text-red-500', 'bg-red-50', 'border-red-100');
            wishBtn.classList.remove('text-gray-400');
        } else {
            wishBtn.classList.remove('text-red-500', 'bg-red-50', 'border-red-100');
            wishBtn.classList.add('text-gray-400');
        }
    }
    if (!exists) {
        // 추가: POST
        const payload = {
            ...product,
            list_type: 'wishlist',
            item_type: 'package',
            source: 'package',
            meta: product.meta,
            name: product.name,
            payload: {
                id: product.id,
                image: product.image,
                image_url: product.image,
                price: product.price,
                price_text: product.price,
                name: product.name,
                meta: product.meta,
                location: product.meta
            }
        };
        fetch('/api/saved-items', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(async (res) => {
            if (res.status === 401) return requireLoginMessage();
            await loadSavedItems();
            showToast('찜 목록에 추가되었습니다! ❤️');
        });
    } else {
        // 삭제: DELETE /api/saved-items/{db_id}
        const saved = (savedItemState['wishlist'] || []).find(
            (x) => x.payload && String(x.payload.id) === String(product.id)
        );
        if (!saved) return;
        fetch(`/api/saved-items/${saved.id}`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(async (res) => {
            if (res.status === 401) return requireLoginMessage();
            await loadSavedItems();
            showToast('찜 목록에서 제외되었습니다.');
        });
    }
}

function addToCart() {
    if (!isUserLoggedIn()) return requireLoginMessage();
    const product = getCurrentProductInfo();
    const cartBtn = document.getElementById('cartBtn');
    const exists = hasSavedItem('cart', product);
    // 즉시 UI 반영
    if (cartBtn) {
        if (!exists) {
            cartBtn.classList.add('text-blue-600', 'bg-blue-50', 'border-blue-100');
            cartBtn.classList.remove('text-gray-400');
        } else {
            cartBtn.classList.remove('text-blue-600', 'bg-blue-50', 'border-blue-100');
            cartBtn.classList.add('text-gray-400');
        }
    }
    if (!exists) {
        // 추가: POST
        const payload = {
            ...product,
            list_type: 'cart',
            item_type: 'package',
            source: 'package',
            meta: product.meta,
            name: product.name,
            payload: {
                id: product.id,
                image: product.image,
                image_url: product.image,
                price: product.price,
                price_text: product.price,
                name: product.name,
                meta: product.meta,
                location: product.meta
            }
        };
        fetch('/api/saved-items', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(async (res) => {
            if (res.status === 401) return requireLoginMessage();
            await loadSavedItems();
            showToast('장바구니에 상품을 담았습니다. 🛒');
        });
    } else {
        // 삭제: DELETE /api/saved-items/{db_id}
        const saved = (savedItemState['cart'] || []).find(
            (x) => x.payload && String(x.payload.id) === String(product.id)
        );
        if (!saved) return;
        fetch(`/api/saved-items/${saved.id}`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(async (res) => {
            if (res.status === 401) return requireLoginMessage();
            await loadSavedItems();
            showToast('장바구니에서 상품을 뺐습니다.');
        });
    }
}

window.addEventListener('DOMContentLoaded', () => {
    // 1. URL 파라미터 추출 및 화면 데이터 업데이트 (상품명, 가격, 이미지 등)
    const params = new URLSearchParams(window.location.search);
    const title = params.get('title') || '패키지 상품';
    const priceText = params.get('price') || '0';
    const img = params.get('img');
    const loc = params.get('loc') || '전세계';
    const id = params.get('id') || '';

    // 상품 제목 (h2) 및 브레드크럼
    const titleEl = document.querySelector('h2.text-2xl.font-black');
    if (titleEl) titleEl.innerText = title;
    const breadcrumbEl = document.querySelector('nav span.text-gray-900');
    if (breadcrumbEl) breadcrumbEl.innerText = title;

    // 이미지 및 위치
    const imgEl = document.getElementById('productImg');
    if (imgEl && img) imgEl.src = img;
    const locEl = document.querySelector('.fa-location-dot')?.parentElement;
    if (locEl) locEl.innerHTML = `<i class="fa-solid fa-location-dot"></i> ${loc}`;

    // 가격 로직 통합 (아동 70% 계산)
    const purePrice = parseInt(priceText.replace(/,/g, '')) || 0;
    PRICES.adult = purePrice;
    PRICES.child = Math.floor(purePrice * 0.7); // 70% 계산 및 소수점 절사
    document.getElementById('productPrice').innerText = purePrice.toLocaleString();
    const adultPriceText = document.querySelector('#adultQty')?.parentElement?.previousElementSibling?.querySelector('p.text-gray-400');
    const childPriceText = document.querySelector('#childQty')?.parentElement?.previousElementSibling?.querySelector('p.text-gray-400');
    if (adultPriceText) adultPriceText.innerText = `${PRICES.adult.toLocaleString()}원`;
    if (childPriceText) childPriceText.innerText = `${PRICES.child.toLocaleString()}원`;

    // 상세 설명 매칭
    updateProductInfo(title, id);

    // 리뷰 렌더링
    let matchedKey = "";
    for (const key in PRODUCT_DETAILS) {
        if (title.includes(key)) {
            matchedKey = key;
            break;
        }
    }
    renderInitialReviews(matchedKey);

    // 초기 합계 계산
    updateTotalPrice();

    // [중요] 상품 정보가 모두 세팅된 뒤에만 장바구니/위시리스트 동기화
    loadSavedItems();
    initFlightSavedDrawer();
});
/**
 * Destino Tour Detail Integration
 * 1. URL 파라미터 기반 실시간 데이터 로드
 * 2. 아동 가격 자동 계산 (성인의 70%)
 * 3. 상품별 상세 설명 매칭 (PRODUCT_DETAILS)
 */

// 전역 상태 관리
const PRICES = { adult: 0, child: 0 };
let quantities = { adult: 1, child: 0 };
let currentRating = 0;

// 상품별 카테고리 및 상세 설명 데이터베이스
const PRODUCT_DETAILS = {
    "다낭/호이안 5일 #미케비치 #리조트 #야시장": {
        category: "동남아 패키지",
        desc: "경기도 다낭시라 불릴 만큼 친숙하고 완벽한 휴양지! 세계 6대 해변인 미케비치 앞 5성급 리조트 숙박과 호이안 올드타운 투어가 포함되어 있습니다. 전 일정 노쇼핑/노옵션으로 진정한 휴식을 선사합니다.",
        reviews: [
            { author: "다낭조아", rating: 5, date: "2024-05-20", text: "가족들과 다녀왔는데 리조트 수영장이 정말 좋았어요." },
            { author: "망고귀신", rating: 5, date: "2024-05-15", text: "호이안 야경은 정말 예술입니다. 사진 1000장 찍었네요." },
            { author: "휴양중독", rating: 4, date: "2024-04-30", text: "음식이 입에 잘 맞아서 부모님도 만족해하셨습니다." },
            { author: "베트남러버", rating: 5, date: "2024-04-12", text: "가이드분이 너무 친절해서 이동하는 내내 즐거웠어요." },
            { author: "미케비치팬", rating: 5, date: "2024-03-25", text: "조식이 정말 맛있습니다. 리조트 선택이 신의 한 수!" },
            { author: "리얼후기", rating: 4, date: "2024-02-10", text: "습하긴 했지만 마사지가 포함되어 있어 피로가 싹 풀렸어요." }
        ]
    },
    "교토 감성 4일 #가이세키 #온천 료칸": {
        category: "일본 패키지",
        desc: "일본의 전통이 살아있는 교토에서 즐기는 힐링 여정. 정통 료칸에서의 1박과 장인이 정성껏 준비한 가이세키 요리가 포함되어 있습니다. 청수사, 아라시야마 등 교토의 핵심 명소를 여유롭게 둘러봅니다.",
        reviews: [
            { author: "교토여행자", rating: 5, date: "2024-05-18", text: "료칸 온천이 너무 깨끗하고 가이세키가 정말 고급스러웠어요." },
            { author: "온천마니아", rating: 5, date: "2024-05-02", text: "부모님 효도 관광으로 최고입니다. 조용하고 한적해서 좋았어요." },
            { author: "가을감성", rating: 4, date: "2024-04-20", text: "아라시야마 대나무숲 산책이 기억에 많이 남네요." },
            { author: "맛객", rating: 5, date: "2024-03-15", text: "일본 음식을 제대로 경험할 수 있는 구성이었습니다." },
            { author: "뚜벅이탈출", rating: 5, date: "2024-02-28", text: "교토는 이동이 힘든데 패키지로 오니 몸이 너무 편해요." }
        ]
    },
    "런던 완전정복 9일 #뮤지컬 #시내호텔": {
        category: "유럽 패키지",
        desc: "클래식한 매력의 런던을 깊이 있게 여행합니다. 시내 중심 호텔 숙박으로 저녁 자유시간 활용이 용이하며, 웨스트엔드 뮤지컬 1회 관람권이 포함되어 있습니다. 영국 박물관 공식 가이드 투어로 지식까지 채워보세요.",
        reviews: [
            { author: "런던아일", rating: 5, date: "2024-05-11", text: "호텔 위치가 너무 좋아서 저녁마다 야경 보러 나갔어요." },
            { author: "뮤지컬덕후", rating: 5, date: "2024-04-25", text: "위키드 공연 봤는데 좌석도 좋고 소름 돋는 무대였습니다." },
            { author: "박물관덕이", rating: 4, date: "2024-04-10", text: "가이드님 설명 없었으면 그냥 돌덩이만 보고 올 뻔했네요." },
            { author: "영국신사", rating: 5, date: "2024-03-22", text: "런던 아이에서 본 풍경은 잊을 수 없는 추억입니다." },
            { author: "티타임", rating: 5, date: "2024-03-05", text: "애프터눈 티 세트 체험도 정말 우아하고 좋았어요." },
            { author: "유럽여행", rating: 4, date: "2024-02-18", text: "물가가 비싸지만 패키지 포함 사항이 많아 가성비 좋았습니다." }
        ]
    },
    "방콕/파타야 5일 #5성급호텔 #전신마사지": {
        category: "동남아 패키지",
        desc: "관광과 휴양의 황금 비율! 방콕 시내의 5성급 호텔과 파타야의 에메랄드빛 바다를 한 번에 즐깁니다. 1일 1마사지가 포함되어 여행의 피로를 매일매일 날려버릴 수 있는 힐링 패키지입니다.",
        reviews: [
            { author: "마사지최고", rating: 5, date: "2024-05-14", text: "매일 받는 전신 마사지 덕분에 부모님이 정말 행복해하셨어요." },
            { author: "태국요리사", rating: 5, date: "2024-04-30", text: "푸드코트 투어랑 야시장 방문이 정말 재밌었습니다." },
            { author: "파타야해변", rating: 4, date: "2024-04-15", text: "해양 스포츠 옵션도 다양해서 친구들이랑 신나게 놀았네요." },
            { author: "호캉스족", rating: 5, date: "2024-03-28", text: "호텔 수영장이 넓고 조식 종류가 엄청 많아서 좋았습니다." },
            { author: "코끼리", rating: 5, date: "2024-02-20", text: "방콕 왕궁의 화려함에 압도당했습니다. 꼭 가보세요!" }
        ]
    },
    "허니문 럭셔리 5일 #프라이빗 빌라": {
        category: "몰디브 패키지",
        desc: "생애 가장 로맨틱한 순간을 몰디브에서. 바다 위에 떠 있는 프라빗 워터 빌라와 올 인클루시브 서비스로 식사부터 주류까지 무제한으로 즐기세요. 둘만의 스노클링 투어와 선셋 크루즈가 포함되어 있습니다.",
        reviews: [
            { author: "신혼부부", rating: 5, date: "2024-05-22", text: "말 그대로 천국입니다. 서비스가 너무 세심해서 감동했어요." },
            { author: "물치광이", rating: 5, date: "2024-05-08", text: "방 바로 밑에 상어랑 물고기들이 지나다녀요. 환상적입니다." },
            { author: "허니문러버", rating: 5, date: "2024-04-18", text: "선셋 크루즈에서 마신 샴페인 맛을 잊을 수가 없네요." },
            { author: "올인클루시브", rating: 4, date: "2024-04-02", text: "삼시세끼 다 맛있고 칵테일도 마음껏 마셨습니다." },
            { author: "바다의왕자", rating: 5, date: "2024-03-15", text: "프라이빗 빌라라 누구의 방해도 받지 않고 쉬었습니다." }
        ]
    },
    "오로라 투어 8일 #빙하트레킹 #블루라군": {
        category: "북유럽 패키지",
        desc: "비현실적인 대자연, 아이슬란드로의 초대. 밤하늘을 수놓는 오로라 헌팅 투어와 신비로운 푸른 빛의 블루라군 온천 체험이 포함되어 있습니다. 인터스텔라의 촬영지 빙하 트레킹까지 일생일대의 경험을 선사합니다.",
        reviews: [
            { author: "오로라헌터", rating: 5, date: "2024-05-10", text: "오로라 지수가 높아서 정말 선명하게 보고 왔습니다. 감동!" },
            { author: "얼음왕국", rating: 5, date: "2024-04-20", text: "빙하 트레킹은 힘들었지만 위에서 본 풍경은 경이로웠어요." },
            { author: "블루라군", rating: 4, date: "2024-04-05", text: "따뜻한 온천물에 몸을 녹이니 피로가 싹 가시더라고요." },
            { author: "아이슬러", rating: 5, date: "2024-03-12", text: "지구가 아닌 다른 행성에 와 있는 기분이었습니다." },
            { author: "꿈의여행", rating: 5, date: "2024-02-25", text: "비용은 비싸지만 그만큼 가치가 충분한 여행이었습니다." }
        ]
    },
    "리스본 골목 감성 7일 #트램 #미식투어": {
        category: "유럽 패키지",
        desc: "시간이 멈춘 듯한 도시 리스본의 낭만을 만끽하세요. 노란색 28번 트램 탑승과 에그타르트 원조 맛집 방문이 포함되어 있습니다. 파두 공연 투어로 포르투갈의 영혼을 느끼는 감성 충만한 일정입니다.",
        reviews: [
            { author: "나타팬", rating: 5, date: "2024-05-16", text: "에그타르트 진짜 맛있어요. 1인 5개는 먹어야 합니다." },
            { author: "트램중독", rating: 5, date: "2024-05-01", text: "좁은 골목을 올라가는 트램 안에서 본 리스본은 최고였어요." },
            { author: "감성사진가", rating: 4, date: "2024-04-14", text: "타일 벽들이 너무 예뻐서 셔터를 쉴 수가 없었습니다." },
            { author: "파두공연", rating: 5, date: "2024-03-28", text: "파두 공연 보는데 왜 눈물이 나죠? 정말 뭉클한 경험이었어요." },
            { author: "대항해시대", rating: 5, date: "2024-03-02", text: "벨렘탑과 발견기념비에서 본 노을이 아주 멋집니다." }
        ]
    },
    "고대문명 탐험 9일 #피라미드 #나일강 크루즈": {
        category: "특수지 패키지",
        desc: "교과서에서 보던 피라미드와 스핑크스를 눈앞에서! 5성급 나일강 크루즈에서 3박을 머물며 룩소르, 아부심벨 신전 등 고대 이집트의 정수를 탐험합니다. 전문 역사 가이드가 동행하여 깊이 있는 해설을 제공합니다.",
        reviews: [
            { author: "파라오", rating: 5, date: "2024-05-13", text: "피라미드 크기에 압도당했습니다. 직접 봐야 알아요." },
            { author: "크루즈여행", rating: 5, date: "2024-04-29", text: "나일강 위에서 보는 일출과 일몰은 정말 비현실적입니다." },
            { author: "역사덕후", rating: 5, date: "2024-04-12", text: "가이드님 설명이 너무 좋아서 지루할 틈이 없었네요." },
            { author: "이집트왕", rating: 4, date: "2024-03-25", text: "모래바람은 힘들었지만 신전들의 웅장함이 압승입니다." },
            { author: "아부심벨", rating: 5, date: "2024-03-01", text: "아부심벨 신전은 꼭 가야 합니다. 패키지 동선이 좋았어요." }
        ]
    },
    "이탈리아 완전일주 9일 #베네치아 #피렌체 #로마": {
        category: "유럽 패키지",
        desc: "이탈리아의 핵심 3대 도시를 완벽하게 정복하는 정통 코스입니다. 베네치아 곤돌라 체험, 피렌체 우피치 미술관 내부 관람, 로마 바티칸 박물관 하이패스 입장권이 포함되어 이동과 관광의 효율성을 극대화했습니다.",
        reviews: [
            { author: "피렌체팬", rating: 5, date: "2024-05-19", text: "우피치 미술관 가이드 투어 덕분에 르네상스를 이해하게 됐어요." },
            { author: "바티칸", rating: 5, date: "2024-05-04", text: "줄 안 서고 바티칸 들어가는 게 얼마나 큰 행복인지 알았습니다." },
            { author: "젤라또", rating: 4, date: "2024-04-22", text: "로마 시내 투어 때 먹은 젤라또 맛이 아직도 생각나요." },
            { author: "물의도시", rating: 5, date: "2024-04-10", text: "곤돌라 타고 운하를 지나는데 영화 속 한 장면 같았습니다." },
            { author: "정통코스", rating: 5, date: "2024-03-18", text: "이동 수단이 편해서 부모님도 지치지 않고 즐거워하셨어요." }
        ]
    },
    "열정의 스페인 9일 #가우디투어 #플라멩코": {
        category: "유럽 패키지",
        desc: "태양과 열정의 나라 스페인! 바르셀로나 가우디 투어로 시작해 세비야의 강렬한 플라멩코 공연 감상, 마드리드 프라도 미술관 관람이 포함되어 있습니다. 스페인 전통 음식 타파스와 빠에야 미식 체험이 포함된 알찬 구성입니다.",
        reviews: [
            { author: "가우디러브", rating: 5, date: "2024-05-17", text: "사그라다 파밀리아 성당은 정말 전율이 돋는 건축물이었습니다." },
            { author: "빠에야", rating: 5, date: "2024-05-02", text: "음식이 다 너무 맛있어요! 특히 츄러스랑 빠에야는 최고." },
            { author: "세비야", rating: 4, date: "2024-04-18", text: "플라멩코 공연의 에너지가 대단했습니다. 꼭 관람하세요." },
            { author: "스페인여행", rating: 5, date: "2024-04-01", text: "가이드분이 현지 맛집을 많이 알려주셔서 자유시간도 알찼어요." },
            { author: "태양의나라", rating: 5, date: "2024-03-12", text: "그라나다 알람브라 궁전의 정원이 너무 평화롭고 좋았습니다." }
        ]
    },
    "타이베이 먹방 4일 #지우펀 #야시장": {
        category: "동아시아 패키지",
        desc: "먹으러 떠나는 짧고 굵은 대만 여행! 센과 치히로의 모티브가 된 지우펀 홍등 거리와 타이베이 최대 규모의 스린 야시장 투어가 포함되어 있습니다. 딤섬 맛집 딘타이펑 식사권과 대만 대표 간식 펑리수 만들기 체험이 포함됩니다.",
        reviews: [
            { author: "먹방러", rating: 5, date: "2024-05-21", text: "야시장에서 지파이랑 망고빙수 먹은 게 제일 기억에 남아요." },
            { author: "지우펀홍등", rating: 5, date: "2024-05-06", text: "밤에 켜진 홍등이 너무 예뻐요. 사람이 많지만 꼭 가보세요." },
            { author: "딤섬매니아", rating: 4, date: "2024-04-24", text: "딘타이펑 샤오롱바오는 한국에서 먹는 거랑 차원이 다릅니다." },
            { author: "대만친구", rating: 5, date: "2024-04-11", text: "가이드분이 재밌으셔서 이동하는 버스 안이 항상 화기애애했어요." },
            { author: "짧은휴가", rating: 5, date: "2024-03-29", text: "주말 끼고 다녀오기 딱 좋은 코스입니다. 가성비 최고!" }
        ]
    },
    "하와이 휴양 6일 #와이키키 #스노클링": {
        category: "미주 패키지",
        desc: "영원한 휴양의 파라다이스 하와이! 와이키키 해변 중심가의 호텔 숙박과 하나우마 베이 스노클링 투어가 포함되어 있습니다. 오아후 섬의 핵심 명소를 둘러보는 섬 일주 투어와 로컬 맛집 투어로 하와이의 매력을 100% 느껴보세요.",
        reviews: [
            { author: "알로하", rating: 5, date: "2024-05-15", text: "하나우마 베이에서 본 거북이가 아직도 눈에 선합니다." },
            { author: "와이키키", rating: 5, date: "2024-04-28", text: "쇼핑몰도 가깝고 바다도 가까워서 호텔 위치가 정말 환상이었어요." },
            { author: "하와이안", rating: 4, date: "2024-04-12", text: "새우 트럭 갈릭 새우 꼭 드세요. 두 번 드세요!" },
            { author: "신혼느낌", rating: 5, date: "2024-03-25", text: "결혼 10주년으로 갔는데 다시 신혼으로 돌아간 기분이었습니다." },
            { author: "쇼핑왕", rating: 5, date: "2024-03-08", text: "아울렛 투어 시간이 넉넉해서 득템 많이 하고 왔습니다." },
            { author: "서핑러", rating: 5, date: "2023-12-15", text: "서핑 강습도 연결해주셔서 버킷리스트 하나 이뤘네요." }
        ]
    }
};

window.addEventListener('DOMContentLoaded', () => {
    // 오늘 날짜를 yyyy-mm-dd로 구해 date input min에 적용
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const minDate = `${yyyy}-${mm}-${dd}`;
    const bookingDateInput = document.getElementById('bookingDate');
    if (bookingDateInput) {
        bookingDateInput.setAttribute('min', minDate);
        // 기본값이 과거일 경우 오늘로 맞춤
        if (bookingDateInput.value < minDate) bookingDateInput.value = minDate;
    }
    // 1. URL 파라미터 추출
    const params = new URLSearchParams(window.location.search);
    const title = params.get('title') || '패키지 상품';
    const priceText = params.get('price') || '0';
    const img = params.get('img');
    const loc = params.get('loc') || '전세계';
    const id = params.get('id') || '';

    // 2. 화면 데이터 업데이트 (UI Mapping)
    
    // 상품 제목 (h2) 및 브레드크럼
    const titleEl = document.querySelector('h2.text-2xl.font-black');
    if (titleEl) titleEl.innerText = title;
    const breadcrumbEl = document.querySelector('nav span.text-gray-900');
    if (breadcrumbEl) breadcrumbEl.innerText = title;

    // 이미지 및 위치
    const imgEl = document.getElementById('productImg');
    if (imgEl && img) imgEl.src = img;
    const locEl = document.querySelector('.fa-location-dot')?.parentElement;
    if (locEl) locEl.innerHTML = `<i class="fa-solid fa-location-dot"></i> ${loc}`;

    // 3. 가격 로직 통합 (아동 70% 계산)
    const purePrice = parseInt(priceText.replace(/,/g, '')) || 0;
    PRICES.adult = purePrice;
    PRICES.child = Math.floor(purePrice * 0.7); // 70% 계산 및 소수점 절사

    // 화면상의 단가 텍스트 업데이트 (수량 선택 영역)
    document.getElementById('productPrice').innerText = purePrice.toLocaleString();
    const adultPriceText = document.querySelector('#adultQty')?.parentElement?.previousElementSibling?.querySelector('p.text-gray-400');
    const childPriceText = document.querySelector('#childQty')?.parentElement?.previousElementSibling?.querySelector('p.text-gray-400');
    
    if (adultPriceText) adultPriceText.innerText = `${PRICES.adult.toLocaleString()}원`;
    if (childPriceText) childPriceText.innerText = `${PRICES.child.toLocaleString()}원`;

    // 4. 상세 설명 매칭
    updateProductInfo(title, id);

    // [중요] 상품명에 맞는 리뷰를 화면에 그려줍니다.
    let matchedKey = "";
    for (const key in PRODUCT_DETAILS) {
        if (title.includes(key)) {
            matchedKey = key;
            break;
        }
    }
    renderInitialReviews(matchedKey);

    // 초기 합계 계산
    updateTotalPrice();
});

/**
 * 상품명 키워드 매칭을 통한 상세 정보 업데이트
 */
function updateProductInfo(title, id) {
    const descEl = document.getElementById('productDesc');
    const categoryEl = document.querySelector('p.text-blue-600.uppercase'); // 'Most Popular' 부분 활용 가능
    const childQtyRow = document.getElementById('childQty')?.closest('.flex.items-center.justify-between.pt-5');
    if (!descEl) return;

    // 공백을 제거하고 비교하여 매칭 확률 극대화
    const cleanTitle = title.replace(/\s/g, ''); 
    const cleanId = id.replace(/\s/g, '');

    let found = false;
    let isSkydiving = false;
    for (const key in PRODUCT_DETAILS) {
        const cleanKey = key.replace(/\s/g, ''); // 키값의 공백도 제거
        if (cleanTitle.includes(cleanKey) || cleanId.includes(cleanKey)) {
            descEl.innerText = PRODUCT_DETAILS[key].desc;
            if (categoryEl) categoryEl.innerText = PRODUCT_DETAILS[key].category;
            found = true;
            if (key === '스카이다이빙') isSkydiving = true;
            break;
        }
    }

    // 스카이다이빙 상품이면 아동 수량 선택 숨김, 아니면 보이기
    if (childQtyRow) {
        if (isSkydiving) {
            childQtyRow.style.display = 'none';
            // 아동 수량 0으로 초기화
            quantities.child = 0;
            const qtyDisplay = document.getElementById('childQty');
            if (qtyDisplay) qtyDisplay.innerText = '0';
            updateTotalPrice();
        } else {
            childQtyRow.style.display = '';
        }
    }

    if (!found) {
        descEl.innerText = "이 패키지 상품의 상세 정보는 준비 중입니다. 현지 파트너와의 실시간 연동을 통해 곧 상세 내용을 안내해 드리겠습니다.";
    }
}

/**
 * 수량 변경 및 가격 합계 로직
 */
function changeQty(type, diff) {
    const newQty = quantities[type] + diff;
    if (newQty < 0) return;
    
    // Validation: 아동 동반 시 성인 1명 필수
    if (type === 'adult' && newQty === 0 && quantities.child > 0) {
        showToast('아동 동반 시 성인 1명 이상은 필수입니다.');
        return;
    }
    
    quantities[type] = newQty;
    const qtyDisplay = document.getElementById(`${type}Qty`);
    if (qtyDisplay) qtyDisplay.innerText = newQty;
    updateTotalPrice();
}

function updateTotalPrice() {
    const total = (quantities.adult * PRICES.adult) + (quantities.child * PRICES.child);
    const display = document.getElementById('totalPriceDisplay');
    if (display) display.innerText = total.toLocaleString() + '원';
}

function handleBooking() {
        // Toss 결제 모듈 및 예약 모달 (tour-detail.js와 100% 동일)
        function loadTossPaymentsScript() {
                if (window.TossPayments) return Promise.resolve(window.TossPayments);
                return new Promise((resolve, reject) => {
                        const existing = document.querySelector('script[data-toss-sdk="1"]');
                        if (existing) {
                                existing.addEventListener("load", () => resolve(window.TossPayments));
                                existing.addEventListener("error", reject);
                                return;
                        }
                        const s = document.createElement("script");
                        s.src = "https://js.tosspayments.com/v1/payment";
                        s.async = true;
                        s.dataset.tossSdk = "1";
                        s.onload = () => resolve(window.TossPayments);
                        s.onerror = reject;
                        document.head.appendChild(s);
                });
        }

        function getBookingSnapshot() {
                return {
                        date: document.getElementById("bookingDate")?.value || "",
                        totalText: document.getElementById("totalPriceDisplay")?.innerText || "0원",
                        product: getCurrentProductInfo(),
                        adult: Number(quantities.adult || 0),
                        child: Number(quantities.child || 0),
                };
        }

        function ensureCheckoutStyle() {
                if (document.getElementById("tourCheckoutStyle")) return;
                const style = document.createElement("style");
                style.id = "tourCheckoutStyle";
                style.textContent = `
                    .tour-checkout-modal{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;padding:16px}
                    .tour-checkout-backdrop{position:absolute;inset:0;background:rgba(0,0,0,.45)}
                    .tour-checkout-panel{position:relative;width:min(700px,96vw);max-height:92vh;overflow:auto;background:#fff;border-radius:18px;padding:20px;box-shadow:0 20px 48px rgba(0,0,0,.24)}
                    .tour-checkout-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
                    .tour-checkout-grid input,.tour-checkout-grid textarea{width:100%;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;font-size:14px}
                    .tour-checkout-grid textarea[name="memo"]{height:80px;min-height:80px;max-height:80px;resize:none;}
                    .tour-checkout-grid label{font-size:12px;font-weight:700;color:#374151;display:block}
                    .tour-checkout-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
                    .tour-checkout-btn{height:40px;padding:0 14px;border-radius:10px;border:1px solid transparent;font-weight:700;cursor:pointer}
                    .tour-checkout-btn.cancel{background:#fff;border-color:#d1d5db;color:#374151}
                    .tour-checkout-btn.primary{background:#2563eb;color:#fff}
                    @media (max-width:640px){.tour-checkout-grid{grid-template-columns:1fr}}
                `;
                document.head.appendChild(style);
        }

        function closeCheckoutModal() {
                const modal = document.getElementById("tourCheckoutModal");
                if (modal) modal.remove();
        }

        function openPaymentStep(snapshot, traveler) {
                const modal = document.getElementById("tourCheckoutModal");
                const panel = modal?.querySelector(".tour-checkout-panel");
                if (!panel) return;

                panel.innerHTML = `
                    <h3 style="font-size:22px;font-weight:800;margin:0 0 8px;">결제 진행</h3>
                    <p style="font-size:13px;color:#6b7280;margin:0 0 14px;">예약 정보를 확인하고 결제를 진행하세요.</p>
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:12px;">
                        <div><b>상품</b>: ${snapshot.product.name}</div>
                        <div><b>방문일</b>: ${snapshot.date}</div>
                        <div><b>인원</b>: 성인 ${snapshot.adult} / 아동 ${snapshot.child}</div>
                        <div><b>예약자</b>: ${traveler.name_kr} (${traveler.name_en})</div>
                        <div><b>연락처</b>: ${traveler.phone} / ${traveler.email}</div>
                        <div style="margin-top:6px;font-size:18px;font-weight:800;color:#1d4ed8;">총 결제금액: ${snapshot.totalText}</div>
                    </div>
                    <div class="tour-checkout-actions">
                        <button type="button" class="tour-checkout-btn cancel" data-tour-checkout-close>닫기</button>
                        <button type="button" class="tour-checkout-btn primary" id="tourPayNowBtn">결제하기</button>
                    </div>
                `;

                panel.querySelector("[data-tour-checkout-close]")?.addEventListener("click", closeCheckoutModal);
                panel.querySelector("#tourPayNowBtn")?.addEventListener("click", async function () {
                    const btn = this;
                    btn.disabled = true;
                    btn.textContent = "결제 준비 중...";

                    try {
                        const amount = Number(String(snapshot.totalText || "0").replace(/[^\d]/g, "")) || 0;
                        const payload = {
                            tour: {
                                name: snapshot.product.name,
                                meta: snapshot.product.meta,
                                price: amount,
                                payload: snapshot.product.payload,
                                date: snapshot.date,
                                adult: snapshot.adult,
                                child: snapshot.child,
                            },
                            traveler,
                        };

                        const res = await fetch("/api/pack/checkout", {
                            method: "POST",
                            credentials: "same-origin",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload),
                        });

                        if (res.status === 401) {
                            requireLoginMessage();
                            return;
                        }

                        const checkout = await res.json().catch(() => ({}));
                        if (!res.ok) {
                            throw new Error(checkout?.detail || `HTTP ${res.status}`);
                        }

                        if (checkout.payment_mode !== "toss" || !checkout.toss_client_key) {
                            throw new Error("토스 결제 설정이 없습니다. 운영자에게 TOSS 키 설정을 요청해주세요.");
                        }

                        const TossPayments = await loadTossPaymentsScript();
                        const toss = TossPayments(checkout.toss_client_key);
                        await toss.requestPayment("카드", {
                            amount: Number(checkout.amount || 0),
                            orderId: String(checkout.order_id || ""),
                            orderName: String(checkout.order_name || snapshot.product.name || "패키지 예약"),
                            customerName: String(traveler.name_kr || traveler.name_en || "").trim(),
                            customerEmail: String(traveler.email || "").trim(),
                            successUrl: String(checkout.success_url || `${location.origin}/payment/pack/success`),
                            failUrl: String(checkout.fail_url || `${location.origin}/payment/pack/fail`),
                        });
                    } catch (err) {
                        alert(err?.message || "결제 준비 중 오류가 발생했습니다.");
                    } finally {
                        btn.disabled = false;
                        btn.textContent = "결제하기";
                    }
                });
        }

        function openCheckoutModal(snapshot) {
                ensureCheckoutStyle();
                closeCheckoutModal();

                const modal = document.createElement("div");
                modal.id = "tourCheckoutModal";
                modal.className = "tour-checkout-modal";
                modal.innerHTML = `
                    <div class="tour-checkout-backdrop" data-tour-checkout-close></div>
                    <section class="tour-checkout-panel">
                        <h3 style="font-size:22px;font-weight:800;margin:0 0 8px;">예약자 기본정보</h3>
                        <p style="font-size:13px;color:#6b7280;margin:0 0 14px;">티켓 예약에 필요한 기본정보를 입력해 주세요.</p>
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:12px;margin-bottom:14px;">
                            <div><b>상품</b>: ${snapshot.product.name}</div>
                            <div><b>위치</b>: ${snapshot.product.meta || "-"}</div>
                            <div><b>방문일</b>: ${snapshot.date}</div>
                            <div><b>인원</b>: 성인 ${snapshot.adult} / 아동 ${snapshot.child}</div>
                            <div style="margin-top:6px;font-size:16px;font-weight:800;color:#1d4ed8;">총 결제금액: ${snapshot.totalText}</div>
                        </div>
                        <form id="tourCheckoutForm">
                            <div class="tour-checkout-grid">
                                <label>한글 이름*<input name="name_kr" required placeholder="홍길동"></label>
                                <label>영문 이름(여권)*<input name="name_en" required placeholder="HONG GILDONG"></label>
                                <label>생년월일*<input type="date" name="birth" required></label>
                                <label>국적*<input name="nationality" required placeholder="KOR"></label>
                                <label>여권번호*<input name="passport_no" required placeholder="M12345678"></label>
                                <label>연락처*<input name="phone" required placeholder="010-0000-0000"></label>
                                <label style="grid-column:1 / -1">이메일*<input type="email" name="email" required placeholder="you@example.com"></label>
                                <label style="grid-column:1 / -1">요청사항<textarea name="memo" rows="2" placeholder="선택 입력"></textarea></label>
                            </div>
                            <div class="tour-checkout-actions">
                                <button type="button" class="tour-checkout-btn cancel" data-tour-checkout-close>취소</button>
                                <button type="submit" class="tour-checkout-btn primary">결제창으로 이동</button>
                            </div>
                        </form>
                    </section>
                `;

                document.body.appendChild(modal);
                modal.querySelectorAll("[data-tour-checkout-close]").forEach((el) => el.addEventListener("click", closeCheckoutModal));
                modal.querySelector("#tourCheckoutForm")?.addEventListener("submit", (e) => {
                    e.preventDefault();
                    const traveler = Object.fromEntries(new FormData(e.currentTarget).entries());
                    openPaymentStep(snapshot, traveler);
                });
        }

        const snapshot = getBookingSnapshot();
        if (!snapshot.date) return showToast("방문 날짜를 선택해주세요.");
        if (snapshot.adult === 0 && snapshot.child === 0) return showToast("인원을 선택해주세요.");
        openCheckoutModal(snapshot);
}

/**
 * 리뷰 정렬 로직
 */
// 초기 리뷰 렌더링 함수
function renderInitialReviews(productKey) {
    const reviewList = document.getElementById('reviewList');
    const reviewCountEl = document.getElementById('reviewCount');
    if (!reviewList) return;

    const productData = PRODUCT_DETAILS[productKey];
    let reviews = productData?.reviews || [];
    // localStorage에서 내 리뷰 불러오기 (상품 id별로 저장)
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id') || '';
    let myReviews = [];
    if (id) {
        myReviews = JSON.parse(localStorage.getItem('myReviews_' + id) || '[]');
    }
    reviews = [...myReviews, ...reviews];

    reviewList.innerHTML = '';

    if (reviews.length === 0) {
        reviewList.innerHTML = '<p class="text-center text-gray-400 py-10">아직 작성된 리뷰가 없습니다.</p>';
        if (reviewCountEl) reviewCountEl.textContent = '0';
        return;
    }

    // 4개씩 보여주고, 더보기/접기 버튼 구현
    const maxShow = 4;
    let currentShow = maxShow;

    function renderReviewsChunk() {
        reviewList.innerHTML = '';
        const toShow = reviews.slice(0, currentShow);
        toShow.forEach((rev, idx) => {
            const stars = '<i class="fa-solid fa-star text-yellow-400"></i>'.repeat(rev.rating) +
                '<i class="fa-solid fa-star text-gray-200"></i>'.repeat(5 - rev.rating);
            const reviewHtml = `
                <div class="p-6 bg-white border border-gray-100 rounded-2xl shadow-sm mb-4" data-rating="${rev.rating}" data-date="${rev.date}">
                    <div class="flex justify-between items-start mb-4">
                        <div class="flex items-center gap-3">
                            <div>
                                <p class="text-sm font-bold text-gray-800">${rev.author}</p>
                                <div class="flex text-[10px] mt-0.5">${stars}</div>
                            </div>
                        </div>
                        <span class="text-[11px] text-gray-400">${rev.date}</span>
                    </div>
                    <p class="text-sm text-gray-600 leading-relaxed">${rev.text}</p>
                </div>
            `;
            reviewList.insertAdjacentHTML('beforeend', reviewHtml);
        });

        // 버튼 영역: 항상 리뷰 리스트의 맨 아래에 고정
        if (reviews.length > maxShow) {
            // 마지막 리뷰와 버튼 사이에 충분한 여백 추가
            if (toShow.length > 0) {
                const spacer = document.createElement('div');
                spacer.style.height = '16px';
                reviewList.appendChild(spacer);
            }
            const btn = document.createElement('button');
            btn.style.width = '100%';
            btn.style.display = 'block';
            btn.style.margin = '0 auto 16px auto';
            btn.style.background = '#efefef';
            btn.style.color = '#333';
            btn.style.fontWeight = '700';
            btn.style.fontSize = '15px';
            btn.style.border = 'none';
            btn.style.borderRadius = '12px';
            btn.style.padding = '16px 0';
            btn.style.cursor = 'pointer';

            if (currentShow < reviews.length) {
                // 더보기
                const remain = Math.min(maxShow, reviews.length - currentShow);
                btn.textContent = `더보기`;
                btn.onclick = function() {
                    currentShow = Math.min(currentShow + maxShow, reviews.length);
                    renderReviewsChunk();
                };
            } else if (reviews.length > maxShow) {
                // 접기
                btn.textContent = '접기';
                btn.onclick = function() {
                    currentShow = maxShow;
                    renderReviewsChunk();
                };
            }
            reviewList.appendChild(btn);
        }
    }

    renderReviewsChunk();
    if (reviewCountEl) reviewCountEl.textContent = String(reviews.length);
}

function sortReviews(criteria) {
    const reviewList = document.getElementById('reviewList');
    const reviews = Array.from(reviewList.children);
    const sortText = document.getElementById('currentSortText');
    
    document.querySelectorAll('.sort-item').forEach(item => {
        item.classList.remove('text-blue-600', 'font-bold');
        item.classList.add('text-gray-700');
    });

    const activeItem = document.getElementById(`sort-${criteria}`);
    if (activeItem) {
        activeItem.classList.add('text-blue-600', 'font-bold');
        activeItem.classList.remove('text-gray-700');
        sortText.innerText = activeItem.innerText.replace(' ', '');
    }

    reviews.sort((a, b) => {
        const rA = parseInt(a.dataset.rating) || 0;
        const rB = parseInt(b.dataset.rating) || 0;
        const dA = new Date(a.dataset.date);
        const dB = new Date(b.dataset.date);

        if (criteria === 'high') return rB - rA;
        if (criteria === 'low') return rA - rB;
        return dB - dA; // recent
    });

    reviewList.innerHTML = '';
    reviews.forEach(r => reviewList.appendChild(r));
    toggleSortDropdown(); // 드롭다운 닫기
}

/**
 * 리뷰 모달 및 기타 UI 인터랙션
 */
function toggleSortDropdown() {
    document.getElementById('sortDropdown').classList.toggle('show');
}

function openReviewModal() {
    if (!isUserLoggedIn()) {
        requireLoginMessage();
        return;
    }
    document.getElementById('reviewModal').style.display = 'flex';
    document.body.classList.add('modal-active');
    // header z-index 낮추기
    const header = document.querySelector('header.header');
    if (header) header.style.zIndex = '1';
}

function closeReviewModal() {
    document.getElementById('reviewModal').style.display = 'none';
    document.body.classList.remove('modal-active');
    // header z-index 원복
    const header = document.querySelector('header.header');
    if (header) header.style.zIndex = '';
    setStar(0);
    document.getElementById('reviewText').value = '';
}

function setStar(num) {
    currentRating = num;
    document.querySelectorAll('.star-rating i').forEach((s, idx) => {
        s.classList.toggle('active', idx < num);
    });
}

function submitReview() {
    const text = document.getElementById('reviewText').value;
    if (currentRating === 0) return showToast('별점을 선택해주세요.');
    if (!text.trim()) return showToast('후기 내용을 작성해주세요.');

    const reviewList = document.getElementById('reviewList');
    const newReview = document.createElement('div');
    const dateStr = new Date().toISOString().split('T')[0];
    newReview.className = 'p-6 bg-blue-50/20 border border-blue-100 rounded-2xl shadow-sm';
    newReview.dataset.rating = currentRating;
    newReview.dataset.date = dateStr;
    const stars = '<i class="fa-solid fa-star"></i>'.repeat(currentRating) + 
                  '<i class="fa-solid fa-star text-gray-200"></i>'.repeat(5 - currentRating);
    const myNickname = window.nickname || '본인';
    newReview.innerHTML = `
        <div class="flex justify-between items-start mb-4">
            <div class="flex items-center gap-3">
                <div>
                    <p class="text-sm font-bold text-gray-800">${myNickname}</p>
                    <div class="flex text-[10px] text-yellow-400 mt-0.5">${stars}</div>
                </div>
            </div>
            <span class="text-[11px] text-gray-400">방금 전</span>
        </div>
        <p class="text-sm text-gray-600 leading-relaxed">${text}</p>
    `;
    // localStorage에 저장 (상품 id별로)
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id') || '';
    if (id) {
        let myReviews = JSON.parse(localStorage.getItem('myReviews_' + id) || '[]');
        myReviews.unshift({ author: myNickname, rating: currentRating, date: dateStr, text });
        localStorage.setItem('myReviews_' + id, JSON.stringify(myReviews));
    }
    reviewList.prepend(newReview);
    // 리뷰 카운트 증가
    const reviewCountEl = document.getElementById('reviewCount');
    if (reviewCountEl) {
        const current = parseInt(reviewCountEl.textContent.replace(/[^0-9]/g, '')) || 0;
        reviewCountEl.textContent = String(current + 1);
    }
    closeReviewModal();
    showToast('소중한 후기가 등록되었습니다! ✨');
}

function updateWishCartButtonState() {
    const wishBtn = document.getElementById('wishBtn');
    const cartBtn = document.getElementById('cartBtn');
    const product = getCurrentProductInfo();
    if (!product.id) return; // id 없으면 동기화하지 않음
    // 위시리스트 버튼 색상 (장바구니와 독립)
    if (wishBtn) {
        if (hasSavedItem('wishlist', product)) {
            wishBtn.classList.add('text-red-500', 'bg-red-50', 'border-red-100');
            wishBtn.classList.remove('text-gray-400');
        } else {
            wishBtn.classList.remove('text-red-500', 'bg-red-50', 'border-red-100');
            wishBtn.classList.add('text-gray-400');
        }
    }
    // 장바구니 버튼 색상 (위시리스트와 독립)
    if (cartBtn) {
        if (hasSavedItem('cart', product)) {
            cartBtn.classList.add('text-blue-600', 'bg-blue-50', 'border-blue-100');
            cartBtn.classList.remove('text-gray-400');
        } else {
            cartBtn.classList.remove('text-blue-600', 'bg-blue-50', 'border-blue-100');
            cartBtn.classList.add('text-gray-400');
        }
    }
}

// loadSavedItems, renderFlightSavedDrawer에서 상태 동기화
const _origLoadSavedItems = loadSavedItems;
loadSavedItems = async function(...args) {
    await _origLoadSavedItems.apply(this, args);
    updateWishCartButtonState();
};
const _origRenderFlightSavedDrawer = renderFlightSavedDrawer;
renderFlightSavedDrawer = function(...args) {
    _origRenderFlightSavedDrawer.apply(this, args);
    updateWishCartButtonState();
};