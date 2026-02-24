/**
 * DESTINO - 여행 공동예매 스크립트
 */

// 초기 데이터
const posts = [
    {
        id: 1,
        country: '일본',
        title: '오사카 3박 4일 벚꽃 투어 멤버 구함!',
        start: '2025-03',
        departure: '인천',
        budget: '60만원',
        current: 2,
        max: 4,
        status: 'open',
        desc: '벚꽃 시즌에 맞춰 오사카 주요 명소를 함께 둘러볼 분들을 찾습니다. 숙소 공동예약으로 경비를 절감해요!',
    },
    {
        id: 2,
        country: '베트남',
        title: '다낭 풀빌라 같이 예약하실 분? (여성만)',
        start: '2025-04',
        departure: '인천',
        budget: '80만원',
        current: 3,
        max: 4,
        status: 'open',
        desc: '럭셔리 풀빌라 4인실을 예약하려고 합니다. 현재 3명 확정이며 마지막 한 분 모셔요.',
    },
    {
        id: 3,
        country: '태국',
        title: '방콕 미식 탐방 5일차 조인하실 분',
        start: '2025-03',
        departure: '김해',
        budget: '45만원',
        current: 4,
        max: 4,
        status: 'closed',
        desc: '방콕의 맛집들을 도장깨기 할 동행자들을 모집했습니다. 모집이 마감되었습니다.',
    },
    {
        id: 4,
        country: '프랑스',
        title: '파리 에펠탑 뷰 숙소 공동예매해요',
        start: '2025-05',
        departure: '인천',
        budget: '150만원',
        current: 1,
        max: 2,
        status: 'open',
        desc: '에펠탑이 보이는 숙소를 혼자 예약하기 부담스러워 동행을 구합니다. 깔끔하신 분 환영합니다.',
    },
    {
        id: 5,
        country: '미국',
        title: '뉴욕 뮤지컬 데이 티켓 공동구매',
        start: '2025-03',
        departure: '뉴욕현지',
        budget: '20만원',
        current: 2,
        max: 6,
        status: 'open',
        desc: '브로드웨이 뮤지컬 단체 할인을 위해 인원을 모으고 있습니다. 현지 합류도 가능합니다.',
    },
];

let filteredPosts = [...posts];
const itemsPerPage = 5;

// DOM 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initPage();
});

function initPage() {
    renderPosts(1);
    setupInteractions();
}

/**
 * 인터랙션 이벤트 바인딩
 */
function setupInteractions() {
    const countryGroup = document.getElementById('countryInputGroup');
    const countryPopover = document.getElementById('countryPopover');
    const countrySearch = document.getElementById('countrySearch');
    const overlay = document.getElementById('overlay');
    const searchBtn = document.getElementById('searchBtn');

    // 나라 선택 팝오버 열기
    countryGroup.addEventListener('click', () => {
        countryPopover.classList.add('active');
        overlay.classList.add('active');
    });

    // 오버레이 클릭 시 닫기
    overlay.addEventListener('click', () => {
        countryPopover.classList.remove('active');
        overlay.classList.remove('active');
        countrySearch.value = '';
        filterCountryItems('');
    });

    // 팝오버 내부 검색
    countrySearch.addEventListener('input', (e) => filterCountryItems(e.target.value));

    // 나라 아이템 선택
    document.querySelectorAll('.popover-item').forEach((item) => {
        item.addEventListener('click', (e) => {
            document.getElementById('countryDisplay').innerText = e.target.dataset.val;
            countryPopover.classList.remove('active');
            overlay.classList.remove('active');
            e.stopPropagation();
        });
    });

    // 검색 실행
    searchBtn.addEventListener('click', () => filterPosts(1));
}

/**
 * 팝오버 내 국가 필터링
 */
function filterCountryItems(keyword) {
    const items = document.querySelectorAll('.popover-item');
    items.forEach((item) => {
        if (item.dataset.val.includes(keyword)) item.classList.remove('hidden');
        else item.classList.add('hidden');
    });
}

/**
 * 메인 보드 포스트 필터링
 */
function filterPosts(page = 1) {
    const selectedCountry = document.getElementById('countryDisplay').innerText;
    const startMonthVal = document.getElementById('startMonth').value;

    filteredPosts = posts.filter((post) => {
        const matchCountry = selectedCountry === '나라 선택' || post.country === selectedCountry;
        const matchDate = !startMonthVal || post.start === startMonthVal;
        return matchCountry && matchDate;
    });

    renderPosts(page);
}

/**
 * 포스트 리스트 렌더링
 */
function renderPosts(page) {
    const listContainer = document.getElementById('boardList');
    listContainer.innerHTML = '';

    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageData = filteredPosts.slice(startIndex, endIndex);

    if (pageData.length === 0) {
        listContainer.innerHTML =
            '<div style="text-align:center; padding:100px 0; color:#999;">조건에 맞는 게시글이 없습니다.</div>';
        renderPagination(0, 0);
        return;
    }

    pageData.forEach((post) => {
        const card = document.createElement('div');
        card.className = 'board-card';
        card.onclick = () => showPostDetail(post.id);
        card.innerHTML = `
            <div class="board-country">${post.country}</div>
            <div class="board-info">
                <div class="board-title">${post.title}</div>
                <div class="board-date">
                    <i data-lucide="calendar" width="14"></i> ${post.start} 출발 예정
                </div>
            </div>
            <div class="board-participants">
                모집 금액 <strong>${post.budget}</strong>
            </div>
            <div class="status-badge ${post.status === 'open' ? 'status-open' : 'status-closed'}">
                ${post.status === 'open' ? '모집 중' : '모집 마감'}
            </div>
        `;
        listContainer.appendChild(card);
    });

    renderPagination(filteredPosts.length, page);
    lucide.createIcons();
}

/**
 * 모달 제어
 */
function openModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

/**
 * 새 글 등록 처리
 */
function handleFormSubmit(e) {
    e.preventDefault();

    const newPost = {
        id: Date.now(), // 고유 ID 생성
        title: document.getElementById('formTitle').value,
        start: document.getElementById('formMonth').value,
        country: document.getElementById('formCountry').value,
        departure: document.getElementById('formDeparture').value,
        budget: document.getElementById('formBudget').value,
        desc: document.getElementById('formDesc').value,
        current: 1,
        max: 4,
        status: 'open',
    };

    posts.unshift(newPost); // 최신글을 가장 앞에 추가
    filteredPosts = [...posts];

    renderPosts(1);
    closeModal('writeModal');
    e.target.reset();
}

/**
 * 상세 보기 렌더링 및 모달 노출
 */
function showPostDetail(postId) {
    const post = posts.find((p) => p.id === postId);
    if (!post) return;

    const detailView = document.getElementById('detailView');
    detailView.innerHTML = `
        <div class="detail-header">
            <div class="detail-title">${post.title}</div>
            <div class="detail-meta">
                <span>${post.country}</span>
                <span>•</span>
                <span>모집 상태: ${post.status === 'open' ? '모집 중' : '마감'}</span>
            </div>
        </div>
        <div class="detail-info-grid">
            <div class="info-item">
                <label>여행 예정 월</label>
                <span>${post.start}</span>
            </div>
            <div class="info-item">
                <label>출발지</label>
                <span>${post.departure}</span>
            </div>
            <div class="info-item">
                <label>예상 금액</label>
                <span>${post.budget}</span>
            </div>
            <div class="info-item">
                <label>목적지</label>
                <span>${post.country}</span>
            </div>
        </div>
        <div class="form-group">
            <label style="margin-top:20px;">상세 내용</label>
            <div class="detail-description">${post.desc}</div>
        </div>
        <div class="modal-notice" style="margin-top: 20px;">
            💡 참여 신청은 해당 작성자와의 일정을 꼭 확인하신 후 진행해주세요.
        </div>
    `;

    openModal('detailModal');
}

/**
 * 페이지네이션 렌더링
 */
function renderPagination(totalItems, currentPage) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    if (totalPages <= 1) return;

    const prev = document.createElement('div');
    prev.className = 'page-nav';
    prev.innerHTML = '<i data-lucide="chevron-left"></i>';
    prev.onclick = () => currentPage > 1 && renderPosts(currentPage - 1);
    container.appendChild(prev);

    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === currentPage ? 'active' : ''}`;
        btn.innerText = i;
        btn.onclick = () => renderPosts(i);
        container.appendChild(btn);
    }

    const next = document.createElement('div');
    next.className = 'page-nav';
    next.innerHTML = '<i data-lucide="chevron-right"></i>';
    next.onclick = () => currentPage < totalPages && renderPosts(currentPage + 1);
    container.appendChild(next);
    lucide.createIcons();
}
