/**
 * DESTINO - 여행 공동예매 통합 스크립트
 */

const RECOMMENDED_COUNTRIES = [
    "일본",
    "베트남",
    "프랑스",
    "태국",
    "미국",
    "이탈리아",
    "스페인",
    "영국",
];
const COUNTRY_CITIES = {
    일본: ["도쿄", "오사카", "교토", "후쿠오카", "삿포로"],
    베트남: ["다낭", "나트랑", "하노이", "호치민", "푸꾸옥"],
    프랑스: ["파리", "니스", "리옹", "마르세유"],
    태국: ["방콕", "푸켓", "치앙마이", "파타야"],
    미국: ["뉴욕", "LA", "라스베이거스", "시카고", "샌프란시스코"],
    이탈리아: ["로마", "피렌체", "베네치아", "밀라노"],
    스페인: ["바르셀로나", "마드리드", "세비야"],
    영국: ["런던", "에든버러", "맨체스터"],
};

let posts = [
    {
        id: 1,
        country: "일본",
        title: "오사카 3박 4일 벚꽃 투어 멤버 구함!",
        start: "2025-03",
        departure: "인천",
        budget: "60만원",
        current: 2,
        max: '명 참여 중',
        status: "open",
        desc: "벚꽃 시즌에 맞춰 오사카 주요 명소를 함께 둘러볼 분들을 찾습니다. 숙소 공동예약으로 경비를 절감해요!",
    },
    {
        id: 2,
        country: "베트남",
        title: "다낭 풀빌라 같이 예약하실 분? (여성만)",
        start: "2025-04",
        departure: "인천",
        budget: "80만원",
        current: 3,
        max: '명 참여 중',
        status: "open",
        desc: "럭셔리 풀빌라 4인실을 예약하려고 합니다. 현재 3명 확정이며 마지막 한 분 모셔요.",
    },
    {
        id: 3,
        country: "태국",
        title: "방콕 미식 탐방 5일차 조인하실 분",
        start: "2025-03",
        departure: "김해",
        budget: "45만원",
        current: 4,
        max: '명 참여 중',
        status: "closed",
        desc: "방콕의 맛집들을 도장깨기 할 동행자들을 모집했습니다. 모집이 마감되었습니다.",
    },
    {
        id: 4,
        country: "프랑스",
        title: "파리 에펠탑 뷰 숙소 공동예매해요",
        start: "2025-05",
        departure: "인천",
        budget: "150만원",
        current: 1,
        max: '명 참여 중',
        status: "open",
        desc: "에펠탑이 보이는 숙소를 혼자 예약하기 부담스러워 동행을 구합니다. 깔끔하신 분 환영합니다.",
    },
    {
        id: 5,
        country: "미국",
        title: "뉴욕 뮤지컬 데이 티켓 공동구매",
        start: "2025-03",
        departure: "뉴욕현지",
        budget: "20만원",
        current: 2,
        max: '명 참여 중',
        status: "open",
        desc: "브로드웨이 뮤지컬 단체 할인을 위해 인원을 모으고 있습니다. 현지 합류도 가능합니다.",
    },
];

// 페이지당 보여줄 게시글 개수 설정
const itemsPerPage = 5; 
// 필터링된 포스트를 담을 변수 (페이지네이션에서 사용)
let filteredPosts = [...posts];

document.addEventListener("DOMContentLoaded", () => {
    initPage();
});

function initPage() {
    renderPosts(); // 게시글 목록 그리기
    setupInteractions(); // 기존 검색바 클릭 이벤트
    initPopovers(); // ★ 글쓰기 모달 내 나라/도시 클릭 이벤트 (중요)
    populateRecommendations(); // ★ 글쓰기 모달 내 추천 나라 리스트 생성 (중요)
    initDateConstraints(); // 날짜 120일 제한
    lucide.createIcons();
    // 시작 날짜 변경 시 종료 날짜 최소값 자동 업데이트 이벤트 연결
    const startInput = document.getElementById("formDateStart");
    if (startInput) {
        startInput.addEventListener("change", updateMinEndDate);
    }
}

/**
 * 게시글 목록 렌더링
 */
function renderPosts(page = 1) {
    const listContainer = document.getElementById('boardList');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    // 현재 코드의 filteredPosts를 사용하여 페이지네이션 적용
    const startIndex = (page - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageData = filteredPosts.slice(startIndex, endIndex);

    if (pageData.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:100px 0; color:#999;">조건에 맞는 게시글이 없습니다.</div>';
        renderPagination(0, 0);
        return;
    }

    pageData.forEach((post) => {
        // 기존의 인원 현황 계산 및 마감 임박 로직
        const maxPax = post.max || 4;
        const progress = (post.current / maxPax) * 100;
        const isImminent = post.status === 'open' && (maxPax - post.current <= 1);
        
        const card = document.createElement('div');
        card.className = 'board-card';
        
        // 클릭 시 현재의 발전된 상세 모달(showDetail) 호출
        card.onclick = () => showDetail(post.id); 
        
        card.innerHTML = `
            <div class="card-left">
                <div class="card-meta">
                    <span class="badge-country">${post.country}</span>
                </div>
                <div class="board-title">${post.title}</div>
                <div class="board-date">
                    <i data-lucide="calendar" width="14"></i> ${post.start} 출발 예정 · ${post.departure || '인천'} 출발
                </div>
            </div>
            
            <div class="card-right">
                <div class="progress-container">
                    <div class="progress-label">
                        <span><i data-lucide="users" width="14" style="vertical-align:middle"></i> 인원 현황</span>
                        <span class="pax-text">
                            <span class="current-pax">${post.current}</span>
                            <span class="max-pax">  ${maxPax}</span>
                        </span>
                    </div>
                </div>
                
                <div class="card-footer">
                    <div class="budget-text">${post.budget}</div>
                    <div class="status-badge ${post.status === 'closed' ? 'status-closed' : (isImminent ? 'status-imminent' : 'status-open')}">
                        ${post.status === 'closed' ? '모집 마감' : (isImminent ? '마감 임박' : '모집 중')}
                    </div>
                </div>
            </div>

            <button class="card-wish-btn ${post.wish ? 'active' : ''}" onclick="toggleWish(event, ${post.id})">
                <i data-lucide="heart" width="20" ${post.wish ? 'fill="currentColor"' : 'fill="none"'}></i>
            </button>
        `;
        listContainer.appendChild(card);
    });

    renderPagination(filteredPosts.length, page);
    lucide.createIcons();
}

/**
 * 페이지네이션 렌더링 함수
 */
function renderPagination(totalItems, currentPage) {
    const container = document.getElementById('pagination');
    if (!container) return; // HTML에 pagination 아이디를 가진 요소가 없으면 중단
    
    container.innerHTML = '';
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    
    // 페이지가 1개 이하라면 페이지네이션을 표시하지 않음
    if (totalPages <= 1) return;

    // [이전] 버튼
    const prev = document.createElement('div');
    prev.className = 'page-nav';
    prev.innerHTML = '<i data-lucide="chevron-left"></i>';
    prev.style.cursor = 'pointer';
    prev.onclick = () => {
        if (currentPage > 1) renderPosts(currentPage - 1);
    };
    container.appendChild(prev);

    // [번호] 버튼들
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === currentPage ? 'active' : ''}`;
        btn.innerText = i;
        btn.onclick = () => renderPosts(i);
        container.appendChild(btn);
    }

    // [다음] 버튼
    const next = document.createElement('div');
    next.className = 'page-nav';
    next.innerHTML = '<i data-lucide="chevron-right"></i>';
    next.style.cursor = 'pointer';
    next.onclick = () => {
        if (currentPage < totalPages) renderPosts(currentPage + 1);
    };
    container.appendChild(next);
    
    // 루사이드 아이콘 렌더링
    lucide.createIcons();
}

/**
 * 상세 페이지 표시 (디자인 및 버튼 반영)
 */
function showDetail(id) {
    const p = posts.find((post) => post.id === id);
    if (!p) return;

    // 개인정보 동의 체크박스 초기화 (항상 해제된 상태로 시작)
    const privacyCheck = document.getElementById("privacyCheck");
    if (privacyCheck) privacyCheck.checked = false;

  // 헤더 반영
    document.getElementById("detailHeader").innerHTML = `
        <div style="font-size:13px; color:var(--primary-color); font-weight:700; margin-bottom:4px;">${p.cat || "공동예매"}</div>
        <h2 style="font-size:22px;">${p.title}</h2>
    `;

  // 바디 그리드 반영
    document.getElementById("detailBody").innerHTML = `
        <div style="display:grid; grid-template-columns: 1fr 1.5fr; gap: 15px; margin-bottom:20px;">
            <div style="background:#f0faff; padding:15px; border-radius:12px;">
                <div style="font-size:11px; color:#0088cc; font-weight:700; margin-bottom:4px;">여행지</div>
                <div style="font-size:15px; font-weight:700;">${p.country} (${p.city || "전체"})</div>
            </div>
            <div style="background:#f8f9fa; padding:15px; border-radius:12px;">
                <div style="font-size:11px; color:#666; font-weight:700; margin-bottom:4px;">일정</div>
                <div style="font-size:15px; font-weight:700;">${p.start} 출발</div>
            </div>
        </div>
        <div style="border-top:1px solid #f0f0f0; padding-top:20px;">
            <div style="font-weight:700; margin-bottom:10px; font-size:15px;">상세 설명</div>
            <p style="white-space:pre-wrap; color:#555; font-size:14px; line-height:1.7;">${p.desc}</p>
        </div>
    `;

  // 하단 버튼 영역 (찜하기 + 신청하기)
    const actions = document.getElementById("detailActions");
    actions.innerHTML = `
        <button class="btn-detail-wish ${p.wish ? "active" : ""}" onclick="toggleWish(event, ${p.id})">
            <i data-lucide="heart" width="24" ${p.wish ? 'fill="currentColor"' : 'fill="none"'}></i>
        </button>
        <button class="btn-detail-apply" onclick="handleApply()">지금 신청하기</button>
    `;

    lucide.createIcons();
    openModal("detailModal");
}

function toggleWish(e, id) {
  // 카드 클릭 이벤트(상세보기)가 발생하는 것을 방지
    if (e) e.stopPropagation();

    const post = posts.find((p) => p.id === id);
    if (!post) return;

  // 찜 상태 반전
    post.wish = !post.wish;

  // 목록 다시 그리기 (하트 색상 반영)
    renderPosts();

  // 만약 상세 모달이 열려있다면 모달 안의 하트도 업데이트
    const detailModal = document.getElementById("detailModal");
    const detailWishBtn = document.getElementById("detailWishBtn");
    if (
        detailWishBtn &&
        document.getElementById("detailModal").style.display === "flex"
    ) {
        detailWishBtn.classList.toggle("active", post.wish);
        detailWishBtn.innerHTML = `<i data-lucide="heart" width="24" ${post.wish ? 'fill="currentColor"' : 'fill="none"'}></i>`;
        lucide.createIcons();
    }

  // 토스트 알림 (기존에 showToast 함수가 있다면 실행)
    if (typeof showToast === "function") {
        showToast(
            post.wish
            ? "찜한 목록에 추가되었습니다."
            : "찜한 목록에서 삭제되었습니다.",
        );
    } else {
        console.log(post.wish ? "찜 추가" : "찜 해제");
    }
}

/**
 * 팝업(Popover) 초기화 - 글쓰기 나라/도시 클릭의 핵심
 */
function initPopovers() {
    const globalOverlay =
        document.getElementById("globalOverlay") ||
        document.getElementById("overlay");

    const setup = (triggerId, popId, doneId) => {
        const trigger = document.getElementById(triggerId);
        const pop = document.getElementById(popId);

        if (!trigger || !pop) return;

        trigger.onclick = (e) => {
            if (trigger.classList.contains("disabled")) return;
            e.stopPropagation();
            pop.classList.toggle("active");
            globalOverlay.classList.toggle("active");
        };

        const doneBtn = document.getElementById(doneId);
        if (doneBtn) {
                doneBtn.onclick = () => {
                pop.classList.remove("active");
                globalOverlay.classList.remove("active");
            };
        }
    };

  // 글쓰기 모달 내 팝오버 연결
    setup("formCountryTrigger", "formCountryPopover", "formCountryDoneBtn");
    setup("formCityTrigger", "formCityPopover", "formCityDoneBtn");
}

/**
 * 시작 날짜를 선택하면 종료 날짜의 최소값을 해당 날짜로 고정
 */
function updateMinEndDate() {
    const startInput = document.getElementById('formDateStart');
    const endInput = document.getElementById('formDateEnd');
    
    if (startInput && endInput && startInput.value) {
        // 종료 날짜는 시작 날짜 이후여야 하므로 min 속성을 업데이트
        endInput.setAttribute('min', startInput.value);
        
        // 만약 기존에 선택된 종료 날짜가 새 시작 날짜보다 빠르면 초기화
        if (endInput.value && endInput.value < startInput.value) {
            endInput.value = '';
        }
    }
}

/**
 * 추천 나라 목록 생성 (글쓰기 모달 내부)
 */
function populateRecommendations() {
    const formList = document.getElementById("formCountryList");
    if (!formList) return;
    formList.innerHTML = "";

    RECOMMENDED_COUNTRIES.forEach((c) => {
        const item = document.createElement("div");
        item.className = "recommend-item";
        item.innerHTML = `<i data-lucide="globe" width="14"></i>${c}`;

        item.onclick = () => {
            document.getElementById("formCountryInput").value = c;
            document.getElementById("formCountryDisplay").innerText = c;
            updateFormCities(c); // 나라 선택 시 도시 목록 갱신 호출
        };
        formList.appendChild(item);
    });
}

/**
 * 도시 목록 업데이트
 */
function updateFormCities(country) {
    const trigger = document.getElementById("formCityTrigger");
    const display = document.getElementById("formCityDisplay");
    const list = document.getElementById("formCityList");

    trigger.classList.remove("disabled");
    display.innerText = "도시 선택";
    list.innerHTML = "";

    const cities = COUNTRY_CITIES[country] || [];
    cities.forEach((city) => {
        const div = document.createElement("div");
        div.className = "recommend-item";
        div.innerHTML = `<i data-lucide="map-pin" width="14"></i>${city}`;
        div.onclick = () => {
            document.getElementById("formCityInput").value = city;
            display.innerText = city;
        };
        list.appendChild(div);
    });
    lucide.createIcons();
}

/**
 * 신청 처리
 */
function handleApply() {
    const checked = document.getElementById("privacyCheck").checked;
    if (!checked) return alert("개인정보 수집 및 이용에 동의해주세요.");
    alert("신청이 완료되었습니다! 담당자가 확인 후 연락드릴 예정입니다.");
    closeModal("detailModal");
}

// 나머지 모달 제어 및 기본 인터랙션은 유지
function openModal(id) {
    document.getElementById(id).style.display = "flex";
}
function closeModal(id) {
    document.getElementById(id).style.display = "none";
}
function showToast(msg) {
  /* 토스트 로직 */
}
function initDateConstraints() {
  /* 날짜 제한 로직 */
}

function setupInteractions() {
  // 메인 페이지 검색바 나라 선택 로직 (필요시 유지)
    const countryGroup = document.getElementById("countryInputGroup");
    if (countryGroup) {
        countryGroup.onclick = () => {
            document.getElementById("countryPopover").classList.add("active");
            document.getElementById("overlay").classList.add("active");
        };
    }
}

/**
 * 카테고리 선택에 따라 종료 날짜 입력란 표시/숨김 및 필수 속성 제어
 */
function toggleFormDates() {
    const categorySelect = document.getElementById('formCategory');
    const endDateWrapper = document.getElementById('formEndDateWrapper');
    const endDateInput = document.getElementById('formDateEnd'); // 입력창 직접 선택
    
    if (!categorySelect || !endDateWrapper || !endDateInput) return;

    if (categorySelect.value === 'flight') {
        // 항공권일 때: 숨기고 필수 입력 해제
        endDateWrapper.style.display = 'none';
        endDateInput.removeAttribute('required'); 
        endDateInput.value = ''; // 값도 비워줌
    } else {
        // 그 외(호텔, 패키지 등): 보이고 필수 입력 설정
        endDateWrapper.style.display = 'block';
        endDateInput.setAttribute('required', 'required');
    }
}

/**
 * 새 글 등록 처리 (마이페이지 연동 포함)
 */
function handleFormSubmit(e) {
    e.preventDefault();

    // 폼 데이터 가져오기
    const title = document.getElementById('formTitle').value;
    const country = document.getElementById('formCountryDisplay').innerText;
    const city = document.getElementById('formCityDisplay').innerText;
    const start = document.getElementById('formDateStart').value;
    const budget = document.getElementById('formBudget').value;
    const desc = document.getElementById('formDesc').value;

    if (country === "나라 선택") return alert("나라를 선택해주세요.");

    const newPost = {
        id: Date.now(),
        title: title,
        country: country,
        city: city,
        start: start,
        departure: "인천", // 기본값
        budget: budget,
        desc: desc,
        current: 1,
        max: 4,
        status: 'open',
        wish: false,
        isMine: true // 내가 쓴 글 표시
    };

    // 1. 전체 목록 맨 앞에 추가
    posts.unshift(newPost);
    filteredPosts = [...posts];

    // 2. 로컬 스토리지 저장 (마이페이지 연동용)
    saveToLocalStorage(newPost);

    // 3. 화면 갱신 및 모달 닫기
    renderPosts(1);
    closeModal('writeModal');
    e.target.reset(); // 폼 초기화
    
    // 선택 디스플레이 초기화
    document.getElementById('formCountryDisplay').innerText = "나라 선택";
    document.getElementById('formCityDisplay').innerText = "도시 선택";
}

/**
 * 로컬 스토리지 저장 함수
 */
function saveToLocalStorage(post) {
    try {
        const myPosts = JSON.parse(localStorage.getItem('myTripPosts')) || [];
        myPosts.unshift(post);
        localStorage.setItem('myTripPosts', JSON.stringify(myPosts));
        alert('성공적으로 등록되었습니다!');
    } catch (e) {
        console.error("저장 실패:", e);
    }
}