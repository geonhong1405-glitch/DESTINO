/**
 * DESTINO 마이페이지 동적 로직
 * (로그인 유지 및 찜, 쿠폰, 마일리지, 고객센터 탭 확장 포함)
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
    id: 'destino_traveler',
    name: '김데스티노',
    nickname: '여행자김씨',
    email: 'traveler@destino.com',
    phone: '010-1234-5678',
    isLoggedIn: true,
};

// 브라우저 저장소(localStorage)에서 사용자 정보를 불러오거나 없으면 기본값 사용
let user = (SERVER_USER.isLoggedIn ? SERVER_USER : (JSON.parse(localStorage.getItem('destino_user')) || DEFAULT_USER));

// 예약 데이터 (빈 배열로 초기화)
const bookings = [];

// 찜 데이터 관리 (초기 샘플 데이터)
let wishlist = JSON.parse(localStorage.getItem('destino_wishlist')) || [
    {
        id: 1,
        category: '파리 · 항공/호텔',
        name: '에펠탑 뷰 5성급 호텔 패키지',
        price: '1,250,000원~',
        color: 'bg-gray-200',
    },
    {
        id: 2,
        category: '도쿄 · 투어/티켓',
        name: '시부야 스카이 전망대 입장권',
        price: '22,000원~',
        color: 'bg-blue-100',
    },
];

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
        localStorage.removeItem('destino_wishlist');
        fetch('/logout', { method: 'GET', credentials: 'include' })
            .catch(() => {})
            .finally(() => {
                window.location.href = '/';
            });
    }
}

/**
 * 찜 삭제 함수
 */
function removeWishItem(id) {
    wishlist = wishlist.filter((item) => item.id !== id);
    localStorage.setItem('destino_wishlist', JSON.stringify(wishlist));
    renderWishlist();
    updateDisplay(); // 상단 요약 카드의 찜 개수 업데이트를 위해 호출
}

/**
 * 찜 목록 렌더링
 */
function renderWishlist() {
    const wishContainer = document.querySelector('#content-wishlist .grid');
    const wishTitle = document.querySelector('#content-wishlist .card-title');

    if (!wishContainer) return;

    if (wishTitle) {
        wishTitle.innerText = `찜한 여행지 (${wishlist.length})`;
    }

    if (wishlist.length === 0) {
        wishContainer.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-12">
                <p class="text-gray-400 text-sm">찜한 내역이 없습니다.</p>
            </div>
        `;
        return;
    }

    wishContainer.innerHTML = wishlist
        .map(
            (item) => `
        <div class="wish-item">
            <div class="wish-img-placeholder ${item.color}"></div>
            <div class="wish-info">
                <p class="wish-category">${item.category}</p>
                <h5 class="wish-name">${item.name}</h5>
                <p class="wish-price">${item.price}</p>
            </div>
            <button class="wish-remove-btn" onclick="removeWishItem(${item.id})">
                <i data-lucide="heart" class="fill-current text-red-500" size="18"></i>
            </button>
        </div>
    `
        )
        .join('');

    lucide.createIcons();
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

    // 상단 요약 카드의 찜 개수 실시간 반영
    const wishStat = document.querySelector('.stat-box[onclick*="wishlist"] .stat-value');
    if (wishStat) wishStat.innerText = `${wishlist.length}개`;
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

/* 내가 쓴 공동구매 게시글 렌더링 (추가) */
function renderMyTripPosts() {
    const container = document.getElementById('my-trip-posts-list');
    if (!container) return;

    const myPosts = JSON.parse(localStorage.getItem('myTripPosts')) || [];

    if (myPosts.length === 0) {
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

    container.innerHTML = myPosts
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
                    <span>${post.start} 출발</span>
                </div>
                <div class="flex items-center gap-2 text-xs text-gray-500">
                    <i data-lucide="wallet" size="12"></i>
                    <span class="font-semibold text-gray-700">${post.budget}</span>
                </div>
            </div>
            <div class="mt-4 pt-3 border-t border-gray-50 flex justify-between items-center">
                <span class="text-[10px] text-gray-400">작성일: ${new Date(post.id).toLocaleDateString()}</span>
                <span class="text-xs font-bold text-[#00AEEF]">모집 중</span>
            </div>
        </div>
    `
        )
        .join('');

    lucide.createIcons();
}

/*내가 쓴 글 삭제 기능 (추가 선택사항)*/
function deleteMyPost(postId) {
    if (!confirm('게시글을 삭제하시겠습니까?')) return;
    
    let myPosts = JSON.parse(localStorage.getItem('myTripPosts')) || [];
    myPosts = myPosts.filter(p => p.id !== postId);
    localStorage.setItem('myTripPosts', JSON.stringify(myPosts));
    
    renderMyTripPosts(); // 새로고침 없이 화면 갱신
}

/*페이지 로드 시 실행*/
window.onload = () => {
    updateDisplay();
    renderBookings();
    renderWishlist();
    renderMyTripPosts();

    const logoutBtn = document.querySelector('.logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = (e) => {
            e.preventDefault();
            handleLogout();
        };
    }

    lucide.createIcons();
};





