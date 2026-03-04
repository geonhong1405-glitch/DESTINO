// ========== airport drawer logic 1:1 (DB 연동) ========== //
let savedItemState = { wishlist: [], cart: [] };
let tourSavedDrawerTab = 'cart';

// 상품명/위치 전역 변수(초기 1회만 세팅, 이후 불변)
let FIXED_PRODUCT_NAME = '';
let FIXED_PRODUCT_META = '';

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
        // name, meta, source를 소문자+trim으로 변환해서 저장
        function normalizeList(list) {
            return (Array.isArray(list) ? list : []).map(item => ({
                ...item,
                name: String(item.name || '').trim().toLowerCase(),
                meta: String(item.meta || '').trim().toLowerCase(),
                source: String(item.source || '').trim().toLowerCase(),
            }));
        }
        savedItemState = {
            wishlist: normalizeList(data?.wishlist),
            cart: normalizeList(data?.cart),
        };
        renderFlightSavedDrawer();
    } catch (e) {
        savedItemState = { wishlist: [], cart: [] };
        renderFlightSavedDrawer();
    }
}

function getCurrentProductInfo() {
    // 티켓(목록)페이지처럼, 버튼 클릭 시점에 화면에서 직접 상품명/위치/가격을 읽어옴
    const name = (document.querySelector('h2.text-2xl.font-black')?.innerText || '').trim().toLowerCase();
    // 위치(메타)는 .fa-location-dot 기준으로 추출 (나라+지역 전체)
    const meta = (document.querySelector('.fa-location-dot')?.parentElement?.innerText || '').trim().toLowerCase();
    const price = document.getElementById('productPrice')?.innerText || '';
    const img = document.getElementById('productImg')?.src || '';
    return { item_type: 'tour', name, meta, price, image: img };
}


// price를 비교에서 제외 (name, meta, item_type만 비교)
function getSavedItemKey(item) {
    // name, meta 모두 trim() 후 소문자 변환
    const clean = (v) => String(v || '').trim().toLowerCase();
    return `${clean(item?.item_type)}__${clean(item?.name)}__${clean(item?.meta)}`;
}

function hasSavedItem(listType, item) {
    const key = getSavedItemKey(item);
    return (savedItemState[listType] || []).some((x) => getSavedItemKey(x) === key);
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
            <div class="flight-saved-item__type">${item.item_type === 'tour' ? 'ticket' : (item.item_type || 'item')}</div>
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
        // filter로 제거하기 전에 삭제 대상 아이템을 미리 저장
        let removedItem = null;
        if (tourSavedDrawerTab === 'cart') {
            removedItem = (savedItemState.cart || []).find(x => Number(x.id) === itemId);
        } else if (tourSavedDrawerTab === 'wishlist') {
            removedItem = (savedItemState.wishlist || []).find(x => Number(x.id) === itemId);
        }
        try {
            await fetch(`/api/saved-items/${itemId}`, { method: 'DELETE', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' } });
            // 클라이언트 상태에서도 제거
            savedItemState[tourSavedDrawerTab] = (savedItemState[tourSavedDrawerTab] || []).filter((x) => Number(x.id) !== itemId);
            renderFlightSavedDrawer();

            // 현재 상세페이지 상품과 일치하는 경우, 해당 버튼만 색상 해제
            const currentProduct = getCurrentProductInfo();
            if (removedItem && getSavedItemKey(removedItem) === getSavedItemKey(currentProduct)) {
                if (tourSavedDrawerTab === 'cart') {
                    // 장바구니 버튼 색상 해제
                    const cartBtn = document.getElementById('cartBtn');
                    if (cartBtn) {
                        cartBtn.classList.remove('text-blue-600', 'bg-blue-50', 'border-blue-100');
                    }
                } else if (tourSavedDrawerTab === 'wishlist') {
                    // 찜 버튼 색상 해제
                    const wishBtn = document.getElementById('wishBtn');
                    if (wishBtn) {
                        wishBtn.classList.remove('text-red-500', 'bg-red-50', 'border-red-100');
                    }
                }
            }
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
    const btn = document.getElementById('wishBtn');
    if (!btn) return;
    btn.disabled = true;
    const product = getCurrentProductInfo();
    const exists = hasSavedItem('wishlist', product);
    const wishKey = getSavedItemKey(product);
    const wishRow = (savedItemState.wishlist || []).find(x => getSavedItemKey(x) === wishKey);
    const finish = () => { btn.disabled = false; };
    if (exists && wishRow?.id) {
        // 이미 담겨있으면 삭제
        fetch(`/api/saved-items/${wishRow.id}`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
        }).then(async (res) => {
            if (res.status === 401) {
                window.isLoggedIn = false;
                finish();
                return requireLoginMessage();
            }
            await loadSavedItems();
            // 티켓페이지처럼: 상태 동기화 후 버튼 색상도 동기화
            const stillExists = hasSavedItem('wishlist', product);
            if (!stillExists) {
                btn.classList.remove('text-red-500', 'bg-red-50', 'border-red-100');
            }
            showToast('찜 목록에서 제외되었습니다.');
        }).catch(() => {}).finally(finish);
    } else {
        // 없으면 추가
        const payload = {
            ...product,
            list_type: 'wishlist',
            name: String(product.name || '').trim().toLowerCase(),
            meta: String(product.meta || '').trim().toLowerCase(),
            source: String(product.source || '').trim().toLowerCase(),
        };
        fetch('/api/saved-items', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }).then(async (res) => {
            if (res.status === 401) { finish(); return requireLoginMessage(); }
            await loadSavedItems();
            // 티켓페이지처럼: 상태 동기화 후 버튼 색상도 동기화
            const nowExists = hasSavedItem('wishlist', product);
            if (nowExists) {
                btn.classList.add('text-red-500', 'bg-red-50', 'border-red-100');
            }
            showToast('찜 목록에 추가되었습니다! ❤️');
        }).catch(() => {}).finally(finish);
    }
}

function addToCart() {
    if (!isUserLoggedIn()) return requireLoginMessage();
    const btn = document.getElementById('cartBtn');
    if (!btn) return;
    btn.disabled = true;
    const product = getCurrentProductInfo();
    const exists = hasSavedItem('cart', product);
    const cartKey = getSavedItemKey(product);
    const cartRow = (savedItemState.cart || []).find(x => getSavedItemKey(x) === cartKey);
    const finish = () => { btn.disabled = false; };
    if (exists && cartRow?.id) {
        // 이미 담겨있으면 삭제
        fetch(`/api/saved-items/${cartRow.id}`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
        }).then(async (res) => {
            if (res.status === 401) {
                window.isLoggedIn = false;
                finish();
                return requireLoginMessage();
            }
            await loadSavedItems();
            // 티켓페이지처럼: 상태 동기화 후 버튼 색상도 동기화
            const stillExists = hasSavedItem('cart', product);
            if (!stillExists) {
                btn.classList.remove('text-blue-600', 'bg-blue-50', 'border-blue-100');
            }
            showToast('장바구니에서 상품을 뺐습니다.');
        }).catch(() => {}).finally(finish);
    } else {
        // 없으면 추가
        const payload = {
            ...product,
            list_type: 'cart',
            name: String(product.name || '').trim().toLowerCase(),
            meta: String(product.meta || '').trim().toLowerCase(),
            source: String(product.source || '').trim().toLowerCase(),
        };
        fetch('/api/saved-items', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }).then(async (res) => {
            if (res.status === 401) { finish(); return requireLoginMessage(); }
            await loadSavedItems();
            // 티켓페이지처럼: 상태 동기화 후 버튼 색상도 동기화
            const nowExists = hasSavedItem('cart', product);
            if (nowExists) {
                btn.classList.add('text-blue-600', 'bg-blue-50', 'border-blue-100');
            }
            showToast('장바구니에 상품을 담았습니다. 🛒');
        }).catch(() => {}).finally(finish);
    }
}

window.addEventListener('DOMContentLoaded', () => {
    // 상품명/위치 전역 변수 최초 1회만 세팅 (불변)
    FIXED_PRODUCT_NAME = (document.querySelector('h2.text-2xl.font-black')?.innerText || '').trim().toLowerCase();
    FIXED_PRODUCT_META = (document.querySelector('.fa-location-dot')?.parentElement?.innerText?.replace(/^\s*\S+\s*/, '') || '').trim().toLowerCase();
    // [리뷰] localStorage에서 내 리뷰 불러와서 PRODUCT_DETAILS에 병합
    try {
        const localReviewsRaw = localStorage.getItem('destino_my_reviews');
        if (localReviewsRaw) {
            const localReviews = JSON.parse(localReviewsRaw);
            Object.keys(localReviews).forEach(key => {
                if (!PRODUCT_DETAILS[key]) return;
                PRODUCT_DETAILS[key].reviews = [
                    ...(localReviews[key] || []),
                    ...(PRODUCT_DETAILS[key].reviews || []).filter(r => !(localReviews[key] || []).some(lr => lr.text === r.text && lr.date === r.date && lr.author === r.author))
                ];
            });
        }
    } catch(e) {}
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
// tour.html의 모든 상품(tImg1 ~ tImg16) 완벽 반영
const PRODUCT_DETAILS = {
    "디즈니랜드": {
        category: "테마파크",
        desc: "환상적인 마법의 세계, 파리 디즈니랜드에서 잊지 못할 추억을 만드세요. 패스트패스로 인기 어트랙션을 정복하세요!",
        reviews: [
            { author: "미키마니아", rating: 5, date: "2024-02-15", text: "아이들이 너무 좋아했어요! 패스트패스 꼭 사세요." },
            { author: "퍼레이드홀릭", rating: 4, date: "2024-01-20", text: "사람은 많지만 퍼레이드가 환상적입니다." },
            { author: "동심소환", rating: 5, date: "2023-12-25", text: "크리스마스 시즌에 갔는데 정말 꿈만 같았어요." },
            { author: "테마파크러버", rating: 5, date: "2023-11-10", text: "어트랙션 퀄리티가 대박이에요. 일찍 가는 걸 추천!" },
            { author: "파리여행자", rating: 4, date: "2023-10-05", text: "음식값은 좀 비싸지만 분위기가 다 했습니다." },
            { author: "꿈꾸는어른이", rating: 5, date: "2023-09-12", text: "파리 여행 중 가장 행복했던 하루였어요." }
        ]
    },
    "피오르드": {
        category: "자연/풍경",
        desc: "노르웨이의 거대한 대자연, 투명한 피오르드 해안을 탐험하는 럭셔리 크루즈 투어입니다.",
        reviews: [
            { author: "대자연예찬", rating: 5, date: "2024-02-28", text: "자연의 위대함에 압도당했습니다. 크루즈가 너무 쾌적해요." },
            { author: "북유럽감성", rating: 5, date: "2024-01-15", text: "공기가 너무 맑고 풍경이 비현실적입니다." },
            { author: "노르웨이숲", rating: 4, date: "2023-12-01", text: "조금 추웠지만 가이드 설명이 친절해서 좋았어요." },
            { author: "풍경수집가", rating: 5, date: "2023-11-20", text: "베르겐 여행 필수 코스! 사진만 찍어도 화보입니다." },
            { author: "효도여행성공", rating: 5, date: "2023-10-15", text: "부모님 모시고 갔는데 정말 만족해하셨어요." },
            { author: "힐링마스터", rating: 4, date: "2023-09-05", text: "평화로운 분위기에서 힐링하기 최고입니다." }
        ]
    },
    "큐켄호프": {
        category: "축제/꽃",
        desc: "네덜란드 암스테르담의 상징, 큐켄호프 튤립 축제!",
        reviews: [
            { author: "꽃길만걷자", rating: 5, date: "2024-03-01", text: "꽃향기가 가득해서 행복했어요. 셔틀이 정말 편합니다." },
            { author: "튤립홀릭", rating: 5, date: "2024-02-20", text: "태어나서 볼 튤립을 여기서 다 본 것 같아요. 최고!" },
            { author: "암스테르담러버", rating: 4, date: "2024-01-10", text: "사람이 많긴 하지만 공원이 워낙 넓어 괜찮아요." },
            { author: "봄의요정", rating: 5, date: "2023-12-15", text: "입장권 따로 안 사도 돼서 편하게 다녀왔습니다." },
            { author: "사진작가망생", rating: 5, date: "2023-11-30", text: "네덜란드 여행 중 가장 예뻤던 장소입니다." },
            { author: "가족여행러", rating: 4, date: "2023-10-25", text: "가족 여행으로 강력 추천합니다. 사진 명당 많아요." }
        ]
    },
    "프라하": {
        category: "랜드마크",
        desc: "중세의 로망이 살아있는 프라하 올드타운 투어.",
        reviews: [
            { author: "중세의로망", rating: 5, date: "2024-03-02", text: "시계탑 위에서 본 프라하 전경은 잊을 수가 없네요." },
            { author: "야경사냥꾼", rating: 4, date: "2024-02-14", text: "로맨틱한 도시 프라하! 투어 구성이 알찹니다." },
            { author: "프라하의연인", rating: 5, date: "2024-01-05", text: "야경 투어까지 연계해서 보니 더 좋았어요." },
            { author: "역사탐험가", rating: 5, date: "2023-12-20", text: "가이드분이 역사를 재미있게 설명해주셔서 감동!" },
            { author: "튼튼한두다리", rating: 4, date: "2023-11-15", text: "돌길이라 발은 좀 아프지만 정말 예쁜 동네입니다." },
            { author: "체코맥주최고", rating: 5, date: "2023-10-10", text: "프라하의 정취를 온전히 느낄 수 있는 투어였어요." }
        ]
    },
    "브뤼헤": {
        category: "이색체험",
        desc: "벨기에의 베니스, 브뤼헤 운하를 프라이빗 보트로 탐험합니다.",
        reviews: [
            { author: "운하의여유", rating: 5, date: "2024-02-25", text: "보트 위에서 보는 마을 모습이 너무 아름다워요." },
            { author: "데이트장인", rating: 5, date: "2024-01-30", text: "조용하고 한적해서 데이트 코스로 딱입니다." },
            { author: "동화속주인공", rating: 4, date: "2023-12-10", text: "마을이 작아서 한 바퀴 돌기 적당하고 좋네요." },
            { author: "와플귀신", rating: 5, date: "2023-11-05", text: "와플 먹으면서 보트 타니까 천국이 따로 없네요." },
            { author: "타임슬립", rating: 5, date: "2023-10-20", text: "중세 시대로 타임머신 타고 온 기분이었어요." },
            { author: "벨기에탐방꾼", rating: 4, date: "2023-09-15", text: "벨기에 가면 브뤼헤는 꼭 들러보세요. 강추!" }
        ]
    },
    "스카이다이빙": {
        category: "익스트림",
        desc: "뉴질랜드 퀸스타운 상공 15,000ft에서 떨어지는 전율!",
        reviews: [
            { author: "강심장보유자", rating: 5, date: "2024-02-10", text: "인생 최고의 경험이었습니다! 하나도 안 무서워요." },
            { author: "버킷리스트달성", rating: 5, date: "2024-01-18", text: "버킷리스트 달성! 풍경이 정말 예술입니다." },
            { author: "아드레날린중독", rating: 5, date: "2023-12-22", text: "전문가와 함께라 믿음직스러웠고 짜릿함 그 자체!" },
            { author: "통장요정", rating: 4, date: "2023-11-30", text: "조금 비싸긴 하지만 그만한 가치가 충분합니다." },
            { author: "퀸스타운날다람쥐", rating: 5, date: "2023-10-25", text: "퀸스타운을 가장 멋지게 보는 방법이에요." },
            { author: "자유를찾아서", rating: 5, date: "2023-09-10", text: "낙하할 때의 그 기분을 잊을 수가 없네요. 또 하고 싶어요!" }
        ]
    },
    "라플란드": {
        category: "이색체험",
        desc: "핀란드 로바니에미에서 즐기는 순록 썰매!",
        reviews: [
            { author: "산타친구", rating: 5, date: "2024-02-15", text: "산타 마을 분위기 실화인가요? 너무 몽환적입니다." },
            { author: "엘사팬클럽", rating: 5, date: "2024-01-10", text: "순록들이 너무 귀여워요! 겨울 왕국에 온 느낌." },
            { author: "추위는싫지만", rating: 4, date: "2023-12-24", text: "진짜 추웠지만 방한복 빌려줘서 다행이었어요." },
            { author: "오로라헌터", rating: 5, date: "2023-11-28", text: "오로라까지 보고 와서 완벽한 여행이었습니다." },
            { author: "좋은아빠", rating: 5, date: "2023-10-20", text: "아이들에게 최고의 추억을 선물한 것 같아요." },
            { author: "눈꽃여행자", rating: 4, date: "2023-09-30", text: "설경이 정말 예뻐서 카메라 쉴 틈이 없었네요." }
        ]
    },
    "유니버셜 스튜디오": {
        category: "테마파크",
        desc: "오사카의 필수 코스!",
        reviews: [
            { author: "마리오덕후", rating: 5, date: "2024-03-01", text: "닌텐도 월드 정리권 성공! 마리오 카트 최고예요." },
            { author: "익스프레스찬스", rating: 4, date: "2024-02-15", text: "사람이 많아서 익스프레스 티켓은 필수인 듯요." },
            { author: "그리핀도르", rating: 5, date: "2024-01-20", text: "해리포터 포비든 저니는 언제 타도 감동입니다." },
            { author: "일본여행자", rating: 5, date: "2023-12-10", text: "직원들이 너무 친절해서 기분 좋게 놀았어요." },
            { author: "먹방투어", rating: 4, date: "2023-11-05", text: "먹거리가 다양해서 하루 종일 배부르게 놀았네요." },
            { author: "오사카정복", rating: 5, date: "2023-10-12", text: "오사카 오면 무조건 가야 하는 곳 1위!" }
        ]
    },
    "발리 우붓": {
        category: "포토존",
        desc: "울창한 정글 위에서 즐기는 공중 그네!",
        reviews: [
            { author: "인생샷장인", rating: 5, date: "2024-02-28", text: "인생샷 건졌습니다! 드레스 대여해서 꼭 찍으세요." },
            { author: "발리한달살기", rating: 5, date: "2024-01-15", text: "사진 기사분이 열정적으로 찍어주셔서 좋았어요." },
            { author: "정글북", rating: 4, date: "2023-12-20", text: "조금 대기가 있지만 기다릴 만한 가치가 있습니다." },
            { author: "그네타는여자", rating: 5, date: "2023-11-10", text: "정글 뷰가 정말 시원하고 공기도 좋네요." },
            { author: "스릴만점", rating: 5, date: "2023-10-05", text: "스윙 탈 때 짜릿하고 뷰가 환상적입니다." },
            { author: "우붓감성", rating: 4, date: "2023-09-12", text: "우붓 여행 중 가장 기억에 남는 코스예요." }
        ]
    },
    "빙하 하이킹": {
        category: "베스트",
        desc: "아이슬란드 남부 해안의 신비로운 파란 빙하 위를 직접 걷는 투어.",
        reviews: [
            { author: "얼음왕국관광객", rating: 5, date: "2024-02-20", text: "파란 빙하가 정말 신비로워요. 가이드가 안전하게 이끌어줍니다." },
            { author: "아이슬란드꿈", rating: 5, date: "2024-01-10", text: "아이슬란드 아니면 절대 못 해볼 경험! 강추합니다." },
            { author: "등산매니아", rating: 4, date: "2023-12-15", text: "조금 힘들었지만 정상에서 본 뷰가 모든 걸 보상해주네요." },
            { author: "풀장착완료", rating: 5, date: "2023-11-25", text: "장비가 다 포함되어 있어서 몸만 가도 됩니다." },
            { author: "인터스텔라팬", rating: 5, date: "2023-10-30", text: "인생 최고의 하이킹! 지구가 아닌 것 같았어요." },
            { author: "용감한도전자", rating: 4, date: "2023-09-20", text: "춥지만 열정적인 가이드 덕분에 즐거웠습니다." }
        ]
    },
    "사막 사파리": {
        category: "익스트림",
        desc: "두바이의 황금빛 사막을 질주하는 듄 베이싱!",
        reviews: [
            { author: "모래바람", rating: 5, date: "2024-03-01", text: "듄 베이싱 진짜 스릴 넘쳐요! 멀미약은 챙기세요 ㅋㅋ" },
            { author: "노을성애자", rating: 5, date: "2024-02-15", text: "사막 노을 아래서 먹는 바베큐 저녁이 환상적입니다." },
            { author: "낙타와나", rating: 4, date: "2024-01-10", text: "낙타 타보는 경험이 신선했어요. 모래 썰매도 재밌음!" },
            { author: "두바이부자망상", rating: 5, date: "2023-12-20", text: "두바이 투어 중 만족도 1위! 공연도 볼만해요." },
            { author: "베스트드라이버", rating: 5, date: "2023-11-12", text: "가이드분이 운전을 너무 잘해서 안전하고 재밌었습니다." },
            { author: "사막의여정", rating: 4, date: "2023-10-05", text: "저녁에 쌀쌀해지니 얇은 겉옷 챙겨가세요." }
        ]
    },
    "패러글라이딩": {
        category: "익스트림",
        desc: "스위스 인터라켄의 융프라우와 튠 호수를 발아래에!",
        reviews: [
            { author: "구름위를걷는자", rating: 5, date: "2024-03-02", text: "하늘에서 본 스위스는 말로 표현이 안 됩니다." },
            { author: "인터라켄신사", rating: 5, date: "2024-02-18", text: "파일럿분이 유머러스해서 긴장이 다 풀렸어요." },
            { author: "고소공포증극복", rating: 4, date: "2024-01-20", text: "착륙할 때 살짝 떨렸지만 전체적으로 너무 완벽!" },
            { author: "추억저장소", rating: 5, date: "2023-12-15", text: "사진이랑 영상 옵션 꼭 추가하세요. 평생 소장각!" },
            { author: "스위스홀릭", rating: 5, date: "2023-11-30", text: "인터라켄 가면 이거 안 하고 오면 손해입니다." },
            { author: "에메랄드호수", rating: 5, date: "2023-10-22", text: "호수 색깔이 위에서 보니까 더 예술이네요." }
        ]
    },
    "카파도키아": {
        category: "이색체험",
        desc: "일출과 함께 떠오르는 수백 개의 열기구!",
        reviews: [
            { author: "열기구여행가", rating: 5, date: "2024-02-25", text: "지구상의 장소가 아닌 것 같아요. 눈물이 날 정도로 예뻐요." },
            { author: "터키커피향", rating: 5, date: "2024-01-30", text: "일출과 열기구의 조화는 인생 최고의 풍경입니다." },
            { author: "운수좋은날", rating: 4, date: "2023-12-20", text: "바람 때문에 취소될 뻔했지만 다행히 탔네요. 감동!" },
            { author: "터키일주중", rating: 5, date: "2023-11-15", text: "조금 비싸지만 터키 오면 무조건 해야 하는 1순위." },
            { author: "카파도키아전경", rating: 5, date: "2023-10-10", text: "카파도키아 지형을 한눈에 볼 수 있어서 너무 좋았어요." },
            { author: "샴페인파티", rating: 5, date: "2023-09-05", text: "안전하게 운전해주시고 샴페인 파티까지 완벽!" }
        ]
    },
    "교토": {
        category: "이색체험",
        desc: "전통이 살아있는 교토 기온 거리에서 기모노 체험!",
        reviews: [
            { author: "기모노소녀", rating: 5, date: "2024-03-01", text: "기모노 종류가 많아서 고르기 좋았어요. 스냅 사진 최고!" },
            { author: "기온거리의추억", rating: 5, date: "2024-02-14", text: "교토 거리랑 기모노가 너무 잘 어울려서 기분 좋았음." },
            { author: "스냅홀릭", rating: 4, date: "2024-01-10", text: "게다가 사진 작가님이 친절해서 포즈 잡기 편했어요." },
            { author: "우정여행성공", rating: 5, date: "2023-12-25", text: "친구랑 같이했는데 평생 기억에 남을 추억이네요." },
            { author: "단아한자태", rating: 4, date: "2023-11-20", text: "기모노 입고 걷는 게 조금 힘들었지만 사진 보니 대만족." },
            { author: "일본감성매니아", rating: 5, date: "2023-10-15", text: "교토 여행의 꽃입니다. 추천드려요!" }
        ]
    },
    "해리포터": {
        category: "랜드마크",
        desc: "런던 워너 브라더스 스튜디오 투어!",
        reviews: [
            { author: "호그와트신입생", rating: 5, date: "2024-02-20", text: "해리포터 덕후라면 여기가 바로 천국입니다." },
            { author: "덤블도어교수팬", rating: 5, date: "2024-01-15", text: "연회장 열리는 순간 소름 돋았어요. 세트장 퀄리티 미쳤음." },
            { author: "버터맥주한잔", rating: 4, date: "2023-12-10", text: "버터 맥주는 호불호가 갈리지만 분위기는 짱!" },
            { author: "기념품샵싹쓸이", rating: 5, date: "2023-11-25", text: "기념품 샵에서 통장 털릴 뻔... 너무 예뻐요." },
            { author: "영화공부생", rating: 5, date: "2023-10-30", text: "영화 제작 과정을 알 수 있어서 더 유익했습니다." },
            { author: "런던의마법", rating: 4, date: "2023-09-18", text: "티켓 구하기 힘들었는데 투어로 오니 편하네요." }
        ]
    },
    "배리어 리프": {
        category: "베스트",
        desc: "호주 케언즈의 보석, 세계 최대의 산호초 지대!",
        reviews: [
            { author: "니모를찾아서", rating: 5, date: "2024-02-28", text: "니모를 직접 봤어요! 바다색이 미쳤습니다." },
            { author: "산호초탐험대", rating: 5, date: "2024-01-20", text: "스노클링 하는데 산호초가 정말 알록달록 예뻐요." },
            { author: "거북이친구", rating: 5, date: "2023-12-15", text: "호주 여행 중 최고의 날이었습니다. 거북이도 봤음!" },
            { author: "멀미극복자", rating: 4, date: "2023-11-10", text: "배 타는 시간이 좀 길었지만 풍경이 다 보상해줌." },
            { author: "안전이최고", rating: 5, date: "2023-10-05", text: "안전요원들이 세심하게 챙겨줘서 초보자도 안심이에요." },
            { author: "바다의왕자", rating: 5, date: "2023-09-12", text: "물고기들이 정말 많아요. 꼭 한번 해보세요!" }
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
    const title = params.get('title') || '투어 상품';
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

    // [추가] 상품명/위치 전역 변수 갱신 (항상 최신 선택값으로)
    window.FIXED_PRODUCT_NAME = (title || '').trim().toLowerCase();
    // 위치(메타)는 .fa-location-dot 기준으로 추출
    const meta = (document.querySelector('.fa-location-dot')?.parentElement?.innerText?.replace(/^\s*\S+\s*/, '') || '').trim().toLowerCase();
    window.FIXED_PRODUCT_META = meta;

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
        descEl.innerText = "이 투어 상품의 상세 정보는 준비 중입니다. 현지 파트너와의 실시간 연동을 통해 곧 상세 내용을 안내해 드리겠습니다.";
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


// ========== TOSS 결제 관련 함수 복구 ========== //
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

function ensureCheckoutStyle() {
        if (document.getElementById("tourCheckoutStyle")) return;
        const style = document.createElement("style");
        style.id = "tourCheckoutStyle";
        style.textContent = `
            .tour-checkout-modal {
                position: fixed;
                inset: 0;
                z-index: 5000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 16px;
                overflow: hidden !important;
            }
            .tour-checkout-backdrop {
                position: absolute;
                inset: 0;
                background: rgba(0,0,0,.45);
            }
            .tour-checkout-panel {
                position: relative;
                width: min(700px, 96vw);
                max-height: 92vh;
                overflow: hidden;
                background: #fff;
                border-radius: 28px;
                box-shadow: 0 20px 48px rgba(0,0,0,.24);
                box-sizing: border-box;
                margin-right: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
            }
            .tour-checkout-panel__scroll {
                flex: 1 1 auto;
                max-height: 92vh;
                overflow-y: auto;
                overflow-x: hidden;
                padding: 20px;
                border-radius: 28px;
                scrollbar-width: thin;
                scrollbar-color: #cbd5e1 #f1f5f9;
                background: transparent;
            }
            .tour-checkout-panel__scroll::-webkit-scrollbar {
                width: 8px;
                background: #f1f5f9;
                border-radius: 8px;
            }
            .tour-checkout-panel__scroll::-webkit-scrollbar-thumb {
                background: #cbd5e1;
                border-radius: 8px;
            }
            .tour-checkout-info-scroll {
                max-height: 220px;
                overflow-y: auto;
                overflow-x: hidden;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 14px;
                scrollbar-width: thin;
                scrollbar-color: #cbd5e1 #f1f5f9;
            }
            .tour-checkout-info-scroll::-webkit-scrollbar {
                width: 8px;
                background: #f1f5f9;
                border-radius: 6px;
            }
            .tour-checkout-info-scroll::-webkit-scrollbar-thumb {
                background: #cbd5e1;
                border-radius: 6px;
            }
            .tour-checkout-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            .tour-checkout-grid input,
            .tour-checkout-grid textarea {
                width: 100%;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 14px;
            }
            .tour-checkout-grid label {
                font-size: 12px;
                font-weight: 700;
                color: #374151;
                display: block;
            }
            .tour-checkout-actions {
                display: flex;
                justify-content: flex-end;
                gap: 8px;
                margin-top: 14px;
            }
            .tour-checkout-btn {
                height: 40px;
                padding: 0 14px;
                border-radius: 10px;
                border: 1px solid transparent;
                font-weight: 700;
                cursor: pointer;
            }
            .tour-checkout-btn.cancel {
                background: #fff;
                border-color: #d1d5db;
                color: #374151;
            }
            .tour-checkout-btn.primary {
                background: #2563eb;
                color: #fff;
            }
            @media (max-width:640px) {
                .tour-checkout-grid {
                    grid-template-columns: 1fr;
                }
            }
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
            <div class="tour-checkout-panel__scroll">
                <h3 style="font-size:22px;font-weight:800;margin:0 0 8px;">결제 진행</h3>
                <p style="font-size:13px;color:#6b7280;margin:0 0 14px;">예약 정보를 확인하고 결제를 진행하세요.</p>
                <div class="tour-checkout-info-scroll">
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

                const res = await fetch("/api/tour/checkout", {
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
                    orderName: String(checkout.order_name || snapshot.product.name || "투어 예약"),
                    customerName: String(traveler.name_kr || traveler.name_en || "").trim(),
                    customerEmail: String(traveler.email || "").trim(),
                    successUrl: String(checkout.success_url || `${location.origin}/payment/tour/success`),
                    failUrl: String(checkout.fail_url || `${location.origin}/payment/tour/fail`),
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
                <div class="tour-checkout-panel__scroll">
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
                            <label style="grid-column:1 / -1">요청사항<textarea name="memo" rows="2" placeholder="선택 입력" style="height:80px;min-height:80px;max-height:80px;resize:none;"></textarea></label>
                        </div>
                        <div class="tour-checkout-actions">
                            <button type="button" class="tour-checkout-btn cancel" data-tour-checkout-close>취소</button>
                            <button type="submit" class="tour-checkout-btn primary">결제창으로 이동</button>
                        </div>
                    </form>
                </div>
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

function getBookingSnapshot() {
        return {
            date: document.getElementById("bookingDate")?.value || "",
            totalText: document.getElementById("totalPriceDisplay")?.innerText || "0원",
            product: getCurrentProductInfo(),
            adult: Number(quantities.adult || 0),
            child: Number(quantities.child || 0),
        };
}

function handleBooking() {
        if (!isUserLoggedIn()) return requireLoginMessage();
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
    if (!reviewList) return;

    const productData = PRODUCT_DETAILS[productKey];
    const reviews = productData?.reviews || [];

    // 리뷰 개수 동적으로 표시
    const reviewCountEl = document.getElementById('reviewCount');
    if (reviewCountEl) {
        reviewCountEl.innerText = reviews.length.toLocaleString();
    }

    reviewList.innerHTML = '';

    // Remove existing show more button if present
    const existingShowMore = document.getElementById('showMoreReviewsBtn');
    if (existingShowMore) existingShowMore.remove();

    if (reviews.length === 0) {
        reviewList.innerHTML = '<p class="text-center text-gray-400 py-10">아직 작성된 리뷰가 없습니다.</p>';
        return;
    }

    // Helper to render reviews (count: how many to show, or all if count === undefined)
    function renderReviews(count) {
        reviewList.innerHTML = '';
        const toShow = typeof count === 'number' ? reviews.slice(0, count) : reviews;
        toShow.forEach(rev => {
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
    }


    if (reviews.length <= 4) {
        renderReviews();
        return;
    }

    // 리뷰가 5개 이상일 때만 4개만 보여주고 '더보기' 버튼 노출
    let expanded = false;
    renderReviews(4);

    const showMoreBtn = document.createElement('button');
    showMoreBtn.id = 'showMoreReviewsBtn';
    showMoreBtn.className = 'block mx-auto mt-2 mb-4 px-6 py-2 rounded-xl bg-gray-100 text-gray-700 font-bold hover:bg-blue-50 hover:text-blue-600 transition-all';
    showMoreBtn.textContent = '더보기';
    showMoreBtn.onclick = function() {
        expanded = !expanded;
        if (expanded) {
            renderReviews();
            showMoreBtn.textContent = '접기';
        } else {
            renderReviews(4);
            showMoreBtn.textContent = '더보기';
        }
        reviewList.parentNode.insertBefore(showMoreBtn, reviewList.nextSibling);
    };
    reviewList.parentNode.insertBefore(showMoreBtn, reviewList.nextSibling);

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
    if (typeof isUserLoggedIn === 'function' ? !isUserLoggedIn() : window.isUserLoggedIn === false) {
        requireLoginMessage();
        return;
    }
    document.getElementById('reviewModal').style.display = 'flex';
    document.body.classList.add('modal-active');
}

function closeReviewModal() {
    document.getElementById('reviewModal').style.display = 'none';
    document.body.classList.remove('modal-active');
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
        if (typeof isUserLoggedIn === 'function' ? !isUserLoggedIn() : window.isUserLoggedIn === false) {
            requireLoginMessage();
            return;
        }
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
    
    const nickname = window.nickname || '나';
    newReview.innerHTML = `
        <div class="flex justify-between items-start mb-4">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center font-bold text-sm text-gray-500">ME</div>
                <div>
                    <p class="text-sm font-bold text-gray-800">${nickname}</p>
                    <div class="flex text-[10px] text-yellow-400 mt-0.5">${stars}</div>
                </div>
            </div>
            <span class="text-[11px] text-gray-400">방금 전</span>
        </div>
        <p class="text-sm text-gray-600 leading-relaxed">${text}</p>
    `;

    // 실제 상품키를 찾아서 PRODUCT_DETAILS에 push
    const title = document.querySelector('h2.text-2xl.font-black')?.innerText || '';
    let matchedKey = '';
    for (const key in PRODUCT_DETAILS) {
        if (title.includes(key)) {
            matchedKey = key;
            break;
        }
    }
    if (matchedKey) {
        PRODUCT_DETAILS[matchedKey].reviews = PRODUCT_DETAILS[matchedKey].reviews || [];
        const myReview = {
            author: nickname,
            rating: currentRating,
            date: new Date().toISOString().split('T')[0],
            text: text
        };
        PRODUCT_DETAILS[matchedKey].reviews.unshift(myReview);
        // [리뷰] localStorage에 저장
        try {
            const localReviewsRaw = localStorage.getItem('destino_my_reviews');
            const localReviews = localReviewsRaw ? JSON.parse(localReviewsRaw) : {};
            localReviews[matchedKey] = [myReview, ...(localReviews[matchedKey] || [])];
            localStorage.setItem('destino_my_reviews', JSON.stringify(localReviews));
        } catch(e) {}
        renderInitialReviews(matchedKey);
    } else {
        reviewList.prepend(newReview);
    }
    closeReviewModal();
    showToast('소중한 후기가 등록되었습니다! ✨');
}


function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.innerText = msg;
    toast.style.opacity = '1';
    setTimeout(() => {
        toast.style.opacity = '0';
    }, 2500);
}
