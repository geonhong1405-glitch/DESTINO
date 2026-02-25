/**
 * 여행사 메인 비주얼 슬라이더 스크립트
 */

const sliderData = [
    {
        sub: '공동구매',
        title: '항공+숙소 공동구매 OPEN',
        desc: '지금 이 순간에도 인원이 차고 있어요.<br>마지막 티켓의 주인공은?',
        img: 'https://cdn.pixabay.com/photo/2023/10/11/13/41/ship-8308680_1280.jpg',
    },
    {
        sub: 'Tour',
        title: '대만 투어&티켓 할인 혜택',
        desc: '타이베이 101부터 지우펀 홍등까지,<br>가장 똑똑하게 예약하는 방법',
        img: 'https://media.istockphoto.com/id/479711387/ko/%EC%82%AC%EC%A7%84/taipei-taiwan.jpg?b=1&s=1024x1024&w=0&k=20&c=xsLCTGo6uqq_lGoReEoVyleyoIj-bOFE5LPlE94hKcc=',
    },
    {
        sub: '2026 EVENT',
        title: '상하이 예원 등불 축제',
        desc: '1월 26일 그랜드 오픈!<br>붉은 등불 아래 인생샷을 남겨보세요.',
        img: 'https://cdn.pixabay.com/photo/2020/09/04/08/02/cityscape-5543224_1280.jpg',
    },
    {
        sub: 'SPRING EDITION',
        title: '일본 벚꽃 개화 시기 확정!',
        desc: '핑크빛 꽃길이 열리는 순간,<br>가장 가까운 곳에서 봄을 맞이하세요.',
        img: 'https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1600&q=80',
    },
    {
        sub: 'GLOBAL PASS',
        title: '유레일패스 25% OFF',
        desc: '낭만 가득한 유럽 배낭여행,<br>교통비 고민은 미리 해결하고 떠나세요.',
        img: 'https://images.unsplash.com/photo-1467269204594-9661b134dd2b?auto=format&fit=crop&w=1600&q=80',
    },
    {
        sub: 'STAY FOCUS',
        title: '제주 독채 자쿠지 단독 예약',
        desc: '돌담 너머 파도 소리와 풍경까지,<br>여유를 즐기는 프라이빗한 휴식의 정석.',
        img: 'https://cdn.pixabay.com/photo/2020/03/23/02/52/pension-4959272_1280.jpg',
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

// 초기 실행
document.addEventListener('DOMContentLoaded', initSlider);

/* 공동구매 */
// 가상의 공동구매 데이터
const bookings = [
    {
        id: 1,
        status: 'recruiting',
        category: 'flight_hotel',
        destination: '오사카',
        title: '3박 4일 벚꽃투어 항공+호텔 특가 모여라!',
        startDate: '2026-03-25',
        endDate: '2026-03-28',
        currentPax: 5,
        maxPax: '명 참여 중',
    },
    {
        id: 2,
        status: 'imminent',
        category: 'flight',
        destination: '다낭',
        title: '왕복 특가 항공권 4인 이상 모이면 반값!',
        startDate: '2026-04-10',
        endDate: '2026-04-14',
        currentPax: 3,
        maxPax: '명 참여 중',
    },
    {
        id: 3,
        status: 'closed',
        category: 'hotel',
        destination: '서귀포',
        title: '5성급 오션뷰 호텔 풀빌라 쉐어하실 분',
        startDate: '2026-05-01',
        endDate: '2026-05-03',
        currentPax: 6,
        maxPax: '명 참여 중',
    },
    {
        id: 4,
        status: 'recruiting',
        category: 'hotel',
        destination: '방콕',
        title: '시내 중심가 레지던스 장기 투숙 모집',
        startDate: '2026-06-15',
        endDate: '2026-06-20',
        currentPax: 1,
        maxPax: '명 참여 중',
    },
];

// 설정 도우미 함수들
const getCategoryLabel = (cat) => ({ flight: '항공', hotel: '호텔', flight_hotel: '항공+호텔' }[cat] || '기타');

const getStatusConfig = (status) => {
    const configs = {
        recruiting: { label: '모집중', className: 'status-recruiting' },
        imminent: { label: '마감임박', className: 'status-imminent' },
        closed: { label: '모집완료', className: 'status-closed' }
    };
    return configs[status] || { label: '미상', className: 'status-closed' };
};

const formatDate = (dateString) => dateString.substring(5).replace('-', '.');

// 렌더링 함수
function renderBookings() {
    const listContainer = document.getElementById('booking-list');
    
    listContainer.innerHTML = bookings.map(booking => {
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
                        ${formatDate(booking.startDate)} — ${formatDate(booking.endDate)}
                    </div>
                </div>
                <div class="pax-area">
                    <div class="pax-count">
                        <span class="pax-current ${isClosed ? 'is-closed' : ''}">${booking.currentPax}</span>
                        <span class="pax-max"> ${booking.maxPax}</span>
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
document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('#tab-menu li');
    const cards = document.querySelectorAll('.ai-card');

    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            // 클릭된 탭의 카테고리 값 가져오기
            const category = tab.getAttribute('data-category');

            // 1. 모든 탭에서 'active' 클래스 제거 후 현재 탭에만 추가
            tabs.forEach((t) => t.classList.remove('active'));
            tab.classList.add('active');

            // 2. 카드 필터링 처리
            cards.forEach((card) => {
                const cardType = card.getAttribute('data-type');

                // 선택한 카테고리와 일치하는 카드만 클래스 'show' 부여
                if (cardType === category) {
                    card.classList.add('show');
                } else {
                    card.classList.remove('show');
                }
            });
        });
    });
});
