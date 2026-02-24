/**
 * DESTINO - 여행 공동예매 인터랙션 및 필터링 스크립트
 */

// 1. 게시글 예시 데이터
const posts = [
    {
        id: 1,
        country: '일본',
        title: '오사카 3박 4일 벚꽃 투어 멤버 구함!',
        start: '2025-03-20',
        end: '2025-03-24',
        current: 2,
        max: 4,
        status: 'open',
    },
    {
        id: 2,
        country: '베트남',
        title: '다낭 풀빌라 같이 예약하실 분? (여성만)',
        start: '2025-04-10',
        end: '2025-04-15',
        current: 3,
        max: 4,
        status: 'open',
    },
    {
        id: 3,
        country: '태국',
        title: '방콕 미식 탐방 5일차 조인하실 분',
        start: '2025-03-15',
        end: '2025-03-20',
        current: 4,
        max: 4,
        status: 'closed',
    },
    {
        id: 4,
        country: '프랑스',
        title: '파리 에펠탑 뷰 숙소 공동예매해요',
        start: '2025-05-01',
        end: '2025-05-07',
        current: 1,
        max: 2,
        status: 'open',
    },
    {
        id: 5,
        country: '미국',
        title: '뉴욕 뮤지컬 데이 티켓 공동구매',
        start: '2025-03-25',
        end: '2025-03-30',
        current: 2,
        max: 6,
        status: 'open',
    },
    {
        id: 6,
        country: '일본',
        title: '후쿠오카 온천 여행 2박 3일',
        start: '2025-03-10',
        end: '2025-03-12',
        current: 2,
        max: 2,
        status: 'closed',
    },
    {
        id: 7,
        country: '이탈리아',
        title: '로마-피렌체 기차 패스 공구!',
        start: '2025-04-05',
        end: '2025-04-12',
        current: 3,
        max: 5,
        status: 'open',
    },
    {
        id: 8,
        country: '스페인',
        title: '바르셀로나 사그라다 파밀리아 가이드 투어',
        start: '2025-04-20',
        end: '2025-04-25',
        current: 8,
        max: 10,
        status: 'open',
    },
    {
        id: 9,
        country: '영국',
        title: '런던 해리포터 스튜디오 셔틀 공동예매',
        start: '2025-06-15',
        end: '2025-06-15',
        current: 1,
        max: 4,
        status: 'open',
    },
    {
        id: 10,
        country: '대만',
        title: '타이베이 근교 예스진지 택시 투어 같이가요',
        start: '2025-02-28',
        end: '2025-03-03',
        current: 2,
        max: 4,
        status: 'open',
    },
];

let filteredPosts = [...posts];
const itemsPerPage = 5;

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initPage();
});

function initPage() {
    renderPosts(1);
    setupInteractions();
}

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

    // 배경 클릭 시 팝오버 닫기
    overlay.addEventListener('click', () => {
        countryPopover.classList.remove('active');
        overlay.classList.remove('active');
        countrySearch.value = '';
        filterCountryItems('');
    });

    // 나라 이름 검색 필터
    countrySearch.addEventListener('input', (e) => {
        filterCountryItems(e.target.value);
    });

    // 나라 항목 선택
    document.querySelectorAll('.popover-item').forEach((item) => {
        item.addEventListener('click', (e) => {
            document.getElementById('countryDisplay').innerText = e.target.dataset.val;
            countryPopover.classList.remove('active');
            overlay.classList.remove('active');
            e.stopPropagation();
        });
    });

    // 검색 버튼 클릭 이벤트
    searchBtn.addEventListener('click', () => {
        filterPosts(1);
    });
}

// 팝오버 내부 나라 필터링
function filterCountryItems(keyword) {
    const items = document.querySelectorAll('.popover-item');
    items.forEach((item) => {
        if (item.dataset.val.includes(keyword)) {
            item.classList.remove('hidden');
        } else {
            item.classList.add('hidden');
        }
    });
}

/**
 * 게시글 필터링 로직 (연도-월 기반)
 */
function filterPosts(page = 1) {
    const selectedCountry = document.getElementById('countryDisplay').innerText;
    const startMonthVal = document.getElementById('startMonth').value;
    const endMonthVal = document.getElementById('endMonth').value;

    filteredPosts = posts.filter((post) => {
        // 1. 나라 필터
        const matchCountry = selectedCountry === '나라 선택' || post.country === selectedCountry;

        // 2. 날짜 필터 (연도/월 기반 교차 검증)
        let matchDate = true;
        if (startMonthVal || endMonthVal) {
            // 검색 시작 범위: 선택한 월의 1일 00:00:00
            const searchStart = startMonthVal ? new Date(startMonthVal + '-01T00:00:00') : new Date('1900-01-01');

            // 검색 종료 범위: 선택한 월의 마지막 날 23:59:59
            let searchEnd;
            if (endMonthVal) {
                const [year, month] = endMonthVal.split('-').map(Number);
                searchEnd = new Date(year, month, 0, 23, 59, 59);
            } else {
                searchEnd = new Date('2100-12-31T23:59:59');
            }

            const postStart = new Date(post.start + 'T00:00:00');
            const postEnd = new Date(post.end + 'T23:59:59');

            // 게시글 기간과 검색 월 범위가 겹치는지 확인
            matchDate = postStart <= searchEnd && postEnd >= searchStart;
        }

        return matchCountry && matchDate;
    });

    renderPosts(page);
    document.getElementById('boardList').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// 게시글 렌더링
function renderPosts(page) {
    const listContainer = document.getElementById('boardList');
    listContainer.innerHTML = '';

    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageData = filteredPosts.slice(startIndex, endIndex);

    if (pageData.length === 0) {
        listContainer.innerHTML =
            '<div style="text-align:center; padding:100px 0; color:#999;">조건에 맞는 공동예매 게시글이 없습니다.</div>';
        renderPagination(0, 0);
        return;
    }

    pageData.forEach((post) => {
        const card = document.createElement('div');
        card.className = 'board-card';
        card.innerHTML = `
            <div class="board-country">${post.country}</div>
            <div class="board-info">
                <div class="board-title">${post.title}</div>
                <div class="board-date">
                    <i data-lucide="calendar" width="14"></i> ${post.start} ~ ${post.end}
                </div>
            </div>
            <div class="board-participants">
                참여 인원 <strong>${post.current}/${post.max}</strong>
            </div>
            <div class="status-badge ${post.status === 'open' ? 'status-open' : 'status-closed'}">
                ${post.status === 'open' ? '모집 중' : '모집 마감'}
            </div>
        `;
        listContainer.appendChild(card);
    });

    renderPagination(filteredPosts.length, page);
    lucide.createIcons(); // 동적 생성 아이콘 반영
}

// 페이지네이션 렌더링
function renderPagination(totalItems, currentPage) {
    const paginationContainer = document.getElementById('pagination');
    paginationContainer.innerHTML = '';

    const totalPages = Math.ceil(totalItems / itemsPerPage);
    if (totalPages <= 1) return;

    // 이전 버튼
    const prev = document.createElement('div');
    prev.className = 'page-nav';
    prev.innerHTML = '<i data-lucide="chevron-left"></i>';
    prev.onclick = () => {
        if (currentPage > 1) renderPosts(currentPage - 1);
    };
    paginationContainer.appendChild(prev);

    // 페이지 번호 버튼
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === currentPage ? 'active' : ''}`;
        btn.innerText = i;
        btn.onclick = () => renderPosts(i);
        paginationContainer.appendChild(btn);
    }

    // 다음 버튼
    const next = document.createElement('div');
    next.className = 'page-nav';
    next.innerHTML = '<i data-lucide="chevron-right"></i>';
    next.onclick = () => {
        if (currentPage < totalPages) renderPosts(currentPage + 1);
    };
    paginationContainer.appendChild(next);

    lucide.createIcons();
}
