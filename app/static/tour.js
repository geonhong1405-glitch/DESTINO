let tourSavedState = { cart: [], wishlist: [] };
let tourSavedDrawerTab = 'cart';
window.addTourToCart = addTourToCart;
window.payTourProduct = payTourProduct;

// 장바구니/위시리스트 기능
loadTourSavedItems();
initTourSavedDrawer();
initTourSavedItemActions();

// 카드 클릭 방지 함수
function preventCardClick(e) {
    e.preventDefault();
    e.stopPropagation();
}

// 상세페이지 이동 완전 차단 및 버튼 기능 보장
function setupTourCardClicks() {
    document.querySelectorAll('.tour-card').forEach((card, index) => {
        card.addEventListener('click', function(e) {
            // 버튼 클릭 시 상세페이지 이동 완전 차단
            if (
                e.target.classList.contains('tour-cart-text-btn') ||
                e.target.classList.contains('tour-pay-text-btn') ||
                e.target.tagName === 'BUTTON'
            ) {
                e.stopPropagation();
                e.preventDefault();
                return;
            }
            const tourData = extractTourData(card, index);
            localStorage.setItem('selectedTour', JSON.stringify(tourData));
            window.location.href = '/tdetail';
        });
    });
}
window.addEventListener('DOMContentLoaded', setupTourCardClicks);

// Toast message utility
function showTourToast(msg) {
    let toast = document.getElementById('tourToastMsg');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'tourToastMsg';
        toast.style.position = 'fixed';
        toast.style.top = '32px';
        toast.style.left = '50%';
        toast.style.transform = 'translateX(-50%)';
        toast.style.background = 'rgba(34,34,34,0.92)';
        toast.style.color = '#fff';
        toast.style.padding = '12px 28px';
        toast.style.borderRadius = '24px';
        toast.style.fontSize = '16px';
        toast.style.zIndex = '9999';
        toast.style.boxShadow = '0 2px 8px rgba(0,0,0,0.18)';
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.2s';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 1400);
}

// Tour Card Wishlist Heart Button Handler
window.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tour-wishlist-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            if (!isLoggedIn) {
                requireLoginMessage();
                return;
            }
            // Find card index
            const card = btn.closest('.tour-card');
            const index = Array.from(document.querySelectorAll('.tour-card')).indexOf(card);
            // Toggle wishlist
            if (index !== -1) {
                const tourData = extractTourData(card, index);
                const wishIdx = tourSavedState.wishlist.findIndex(item => item.name === tourData.name);
                if (wishIdx === -1) {
                    tourSavedState.wishlist.push(tourData);
                    btn.querySelector('i').classList.remove('fa-regular');
                    btn.querySelector('i').classList.add('fa-solid');
                    alert(`'${tourData.name || tourData.title || ''}' 상품이 위시리스트에 담겼습니다.`);
                } else {
                    tourSavedState.wishlist.splice(wishIdx, 1);
                    btn.querySelector('i').classList.remove('fa-solid');
                    btn.querySelector('i').classList.add('fa-regular');
                    alert(`'${tourData.name || tourData.title || ''}' 상품이 위시리스트에서 빠졌습니다.`);
                }
                saveTourItems();
                tourSavedDrawerTab = 'wishlist';
                setTourSavedDrawer(true);
            }
        });
    });
});

// Wishlist Floating Button Click Handler
window.addEventListener('DOMContentLoaded', function() {
    const wishlistFab = document.getElementById('tourWishlistFab');
    if (wishlistFab) {
        wishlistFab.addEventListener('click', function() {
            tourSavedDrawerTab = 'wishlist';
            setTourSavedDrawer(true);
        });
    }
});

// 장바구니/결제 버튼에만 이벤트 위임
function addTourToCart(btn, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!isLoggedIn) {
        requireLoginMessage();
        return;
    }
    // 상품 정보 추출
    const card = btn.closest('.tour-card');
    const name = card.querySelector('.tour-name')?.innerText || '';
    const loc = card.querySelector('.tour-loc')?.innerText || '';
    const price = card.querySelector('.price-val')?.innerText || '';
    const item = { title: name, location: loc, price };
    // 기존 cart 배열에 push
    let cart = JSON.parse(localStorage.getItem('tourCart') || '[]');
    cart.push(item);
    localStorage.setItem('tourCart', JSON.stringify(cart));
    // 메모리 상태도 갱신
    tourSavedState.cart = cart;
    saveTourItems();
    renderTourSavedDrawer();
    setTourSavedDrawer(true);
    alert(`'${name}' 상품이 장바구니에 담겼습니다.`);
}

function payTourProduct(btn, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!isLoggedIn) {
        requireLoginMessage();
        return;
    }
    const card = btn.closest('.tour-card');
    const name = card.querySelector('.tour-name')?.innerText || '';
    alert(`'${name}' 상품 결제 페이지로 이동합니다.`);
}

// 외부에서 호출 가능하도록 window에 등록 (중복 없이 한 번만)
window.addTourToCart = addTourToCart;
window.payTourProduct = payTourProduct;

// (중복 함수 정의 제거) 위의 setupTourCardClicks, addTourToCart, payTourProduct만 사용
/**
 * Destino Tour Booking Interactions
 */

window.onload = function () {
    // Lucide 아이콘 초기화
    lucide.createIcons();

    const destInput = document.getElementById('dest-input');
    const tourPopover = document.getElementById('tourPopover');
    const defaultSugg = document.getElementById('default-suggestions');
    const searchResults = document.getElementById('search-results');
    const resultsList = document.getElementById('results-list');
    const searchWidget = document.getElementById('searchWidget');

    /**
     * 입력창 클릭 시 팝업 활성화
     */
    destInput.addEventListener('click', (e) => {
        e.stopPropagation();
        tourPopover.classList.add('active');
    });

    /**
     * 입력어에 따른 실시간 제안 리스트 업데이트
     */
    destInput.addEventListener('input', (e) => {
        const val = e.target.value;

        if (val.trim().length > 0) {
            // 인기 여행지 숨기고 검색 결과 표시
            defaultSugg.style.display = 'none';
            searchResults.style.display = 'block';

            // 검색 제안 템플릿 업데이트
            resultsList.innerHTML = `
                <div class="search-suggestion-item" onclick="selectDest('${val}')">
                    <i data-lucide="map-pin" size="16"></i>
                    <span><strong>'${val}'</strong> 검색 결과 보기</span>
                </div>
                <div class="search-suggestion-item" onclick="selectDest('${val} 인기 명소')">
                    <i data-lucide="star" size="16"></i>
                    <span>${val} 인기 명소/어트랙션 찾기</span>
                </div>
            `;
            // 새로 생성된 아이콘 렌더링
            lucide.createIcons();
        } else {
            // 입력창이 비었을 때 초기 상태로 복구
            defaultSugg.style.display = 'block';
            searchResults.style.display = 'none';
        }
    });

    /**
     * 검색 위젯 외부 클릭 시 팝업 닫기
     */
    document.addEventListener('click', (e) => {
        if (!searchWidget.contains(e.target)) {
            tourPopover.classList.remove('active');
        }
    });
};

/**
 * 제안된 여행지 선택 함수
 * @param {string} name 선택된 지명
 */
function selectDest(name) {
    const destInput = document.getElementById('dest-input');
    const tourPopover = document.getElementById('tourPopover');

    destInput.value = name;
    tourPopover.classList.remove('active');
}

/**
 * 검색 버튼 클릭 핸들러
 */
function handleSearch() {
    const destInput = document.getElementById('dest-input');
    const query = destInput.value;

    if (!query) {
        alert('여행지 또는 어트랙션을 입력해주세요.');
        return;
    }

    // 실제 서비스에서는 검색 결과 페이지로 이동 로직이 들어갑니다.
    alert(`'${query}' 상품 정보를 불러오고 있습니다.`);
}

// 메인 페이지에서 카드를 클릭했을 때 실행될 함수
document.addEventListener('DOMContentLoaded', () => {
    // 기존 카드 클릭 상세페이지 이동
    const tourCards = document.querySelectorAll('.tour-card');
    tourCards.forEach((card, index) => {
        card.addEventListener('click', (e) => {
            e.preventDefault();
            const tourData = extractTourData(card, index);
            localStorage.setItem('selectedTour', JSON.stringify(tourData));
            window.location.href = '/tdetail';
        });
    });

    // 장바구니/결제 버튼 완전 삭제, 기존 카드 클릭 상세페이지 이동만 유지
});

// 투어 장바구니/위시리스트 상태
// 로그인 상태 체크 (템플릿에서 nickname 변수 전달)
const isLoggedIn = typeof window.nickname !== 'undefined' && window.nickname !== null && window.nickname !== '';

function requireLoginMessage() {
    if (confirm('로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?')) {
        location.href = '/login';
    }
}

function getTourSavedKey(item) {
    return `${String(item?.id || '').toLowerCase()}__${String(item?.title || '').toLowerCase()}`;
}

function hasTourSaved(listType, item) {
    const key = getTourSavedKey(item);
    return (tourSavedState[listType] || []).some((x) => getTourSavedKey(x) === key);
}

function loadTourSavedItems() {
    try {
        const cart = JSON.parse(localStorage.getItem('tourCart') || '[]');
        const wishlist = JSON.parse(localStorage.getItem('tourWishlist') || '[]');
        tourSavedState.cart = cart;
        tourSavedState.wishlist = wishlist;
        renderTourSavedDrawer();
    } catch (e) {
        tourSavedState.cart = [];
        tourSavedState.wishlist = [];
        renderTourSavedDrawer();
    }
}

function saveTourItems() {
    localStorage.setItem('tourCart', JSON.stringify(tourSavedState.cart));
    localStorage.setItem('tourWishlist', JSON.stringify(tourSavedState.wishlist));
}

function setTourSavedDrawer(open) {
    const drawer = document.getElementById('tourSavedDrawer');
    const fab = document.getElementById('tourSavedFab');
    if (!drawer || !fab) return;
    drawer.classList.toggle('is-open', !!open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function renderTourSavedDrawer() {
    const listEl = document.getElementById('tourSavedList');
    const emptyEl = document.getElementById('tourSavedEmpty');
    const countEl = document.getElementById('tourSavedFabCount');
    const tabs = Array.from(document.querySelectorAll('[data-tour-saved-tab]'));
    if (!listEl || !emptyEl) return;
    const items = Array.isArray(tourSavedState[tourSavedDrawerTab]) ? tourSavedState[tourSavedDrawerTab] : [];
    const total = (tourSavedState.cart?.length || 0) + (tourSavedState.wishlist?.length || 0);
    if (countEl) {
        countEl.hidden = total === 0;
        countEl.textContent = String(total || 0);
    }
    tabs.forEach((btn) => {
        const active = btn.getAttribute('data-tour-saved-tab') === tourSavedDrawerTab;
        btn.classList.toggle('is-active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    listEl.innerHTML = '';
    emptyEl.style.display = items.length ? 'none' : 'block';
    emptyEl.textContent = tourSavedDrawerTab === 'wishlist' ? '위시리스트 항목이 없습니다.' : '장바구니 항목이 없습니다.';
    items.forEach((item, idx) => {
        const li = document.createElement('li');
        li.className = 'tour-saved-item';
        li.innerHTML = `
            <div class="tour-saved-item__type">${tourSavedDrawerTab === 'cart' ? '투어' : '위시리스트'}</div>
            <div class="tour-saved-item__name">${item.title || '-'}</div>
            <div class="tour-saved-item__meta">${item.location || ''} | ${item.price || ''}</div>
            <button type="button" class="tour-saved-item__remove" data-tour-saved-remove="${idx}" title="삭제">×</button>
        `;
        listEl.appendChild(li);
    });
    // 결제 버튼 추가 (장바구니 탭에서만, 항상 맨 아래에 하나만)
    const oldBtn = document.querySelector('.tour-saved-checkout-btn');
    if (oldBtn) oldBtn.remove();
    if (tourSavedDrawerTab === 'cart' && items.length > 0) {
        const checkoutBtn = document.createElement('button');
        checkoutBtn.className = 'tour-saved-checkout-btn';
        checkoutBtn.textContent = '장바구니 결제하기';
        checkoutBtn.style = 'margin-top:18px;width:100%;height:48px;font-size:18px;font-weight:700;background:#2563eb;color:#fff;border-radius:12px;border:none;cursor:pointer;';
        checkoutBtn.onclick = function() {
            alert('장바구니 결제 페이지로 이동합니다.');
        };
        listEl.parentNode.appendChild(checkoutBtn);
    }
}

function initTourSavedDrawer() {
    const fab = document.getElementById('tourSavedFab');
    const drawer = document.getElementById('tourSavedDrawer');
    const listEl = document.getElementById('tourSavedList');
    if (!fab || !drawer) return;
    fab.addEventListener('click', () => {
        setTourSavedDrawer(!drawer.classList.contains('is-open'));
    });
    document.querySelectorAll('[data-tour-saved-close]').forEach((el) => {
        el.addEventListener('click', () => setTourSavedDrawer(false));
    });
    document.querySelectorAll('[data-tour-saved-tab]').forEach((btn) => {
        btn.addEventListener('click', () => {
            tourSavedDrawerTab = btn.getAttribute('data-tour-saved-tab') || 'cart';
            renderTourSavedDrawer();
        });
    });
    listEl?.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-tour-saved-remove]');
        if (!btn) return;
        const idx = Number(btn.getAttribute('data-tour-saved-remove'));
        if (Number.isNaN(idx)) return;
        tourSavedState[tourSavedDrawerTab].splice(idx, 1);
        saveTourItems();
        renderTourSavedDrawer();
    });
    renderTourSavedDrawer();
}

function initTourSavedItemActions() {
    document.querySelectorAll('.tour-heart-btn').forEach((btn, idx) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!isLoggedIn) return requireLoginMessage();
            const card = btn.closest('.tour-card');
            if (!card) return;
            const tourData = extractTourData(card, idx);
            const savedIdx = tourSavedState.wishlist.findIndex(x => getTourSavedKey(x) === getTourSavedKey(tourData));
            if (savedIdx >= 0) {
                tourSavedState.wishlist.splice(savedIdx, 1);
                btn.classList.remove('is-active');
            } else {
                tourSavedState.wishlist.push(tourData);
                btn.classList.add('is-active');
            }
            saveTourItems();
            renderTourSavedDrawer();
        });
    });
    document.querySelectorAll('.tour-cart-btn').forEach((btn, idx) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!isLoggedIn) return requireLoginMessage();
            const card = btn.closest('.tour-card');
            if (!card) return;
            const tourData = extractTourData(card, idx);
            const savedIdx = tourSavedState.cart.findIndex(x => getTourSavedKey(x) === getTourSavedKey(tourData));
            if (savedIdx >= 0) {
                tourSavedState.cart.splice(savedIdx, 1);
                btn.classList.remove('is-active');
            } else {
                tourSavedState.cart.push(tourData);
                btn.classList.add('is-active');
            }
            saveTourItems();
            renderTourSavedDrawer();
        });
    });
}

function extractTourData(card, idx) {
    return {
        id: idx,
        image: getComputedStyle(card.querySelector('.tour-image')).backgroundImage.replace(/url\((['"])?(.*?)\1\)/, '$2'),
        location: card.querySelector('.tour-loc')?.innerText || '',
        title: card.querySelector('.tour-name')?.innerText || '',
        price: card.querySelector('.price-val')?.innerText.replace(/,/g, '') || '',
        badge: card.querySelector('.badge')?.innerText || ''
    };
}

// 위시리스트 플로팅 버튼 클릭 시 drawer 열고 wishlist 탭으로 전환
const wishlistFab = document.getElementById('tourWishlistFab');
if (wishlistFab) {
    wishlistFab.addEventListener('click', function() {
        tourSavedDrawerTab = 'wishlist';
        renderTourSavedDrawer();
        setTourSavedDrawer(true);
    });
}
