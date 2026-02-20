
window.onload = () => {
    // Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // Initialize Destination Data
    initDest();

    // Set Default Dates
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 3);
    
    const startInput = document.getElementById('startDate');
    const endInput = document.getElementById('endDate');
    
    if(startInput) startInput.valueAsDate = today;
    if(endInput) endInput.valueAsDate = tomorrow;
};

/* ================= Data ================= */
const regionsData = {
    '일본': ['도쿄', '오사카', '후쿠오카', '삿포로', '오키나와', '나고야', '교토', '고베'],
    '동남아': ['방콕', '다낭', '나트랑', '세부', '발리', '싱가포르', '푸껫', '코타키나발루', '마닐라'],
    '중국/홍콩': ['홍콩', '마카오', '상하이', '베이징', '칭다오', '광저우'],
    '유럽': ['파리', '런던', '로마', '바르셀로나', '프라하', '인터라켄', '베네치아', '피렌체'],
    '미주': ['하와이', '뉴욕', '로스앤젤레스', '라스베이거스', '샌프란시스코', '밴쿠버']
};

let currentRegion = '일본';
let guests = { adult: 2, child: 0, room: 1 };

/* ================= Tab Switching ================= */
function switchTab(el, type) {
    document.querySelectorAll('.search-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    const input = document.getElementById('destInput');
    if(!input) return;

    if(type === 'flight') {
        input.placeholder = "도시 또는 공항 검색";
    } else {
        input.placeholder = "어느 숙소를 찾으시나요?";
    }
}

/* ================= Date Picker Fix ================= */
/**
 * Focuses on the input element. 
 * Prevents SecurityError from automated showPicker() in iframes.
 */
function focusInput(id) {
    const el = document.getElementById(id);
    if (el) {
        el.focus();
    }
}

/* ================= Destination Popover ================= */
function initDest() {
    const tabs = document.getElementById('regionTabs');
    if(!tabs) return;
    tabs.innerHTML = '';
    
    Object.keys(regionsData).forEach(region => {
        const btn = document.createElement('button');
        btn.className = `dest-tab ${region === currentRegion ? 'active' : ''}`;
        btn.textContent = region;
        btn.onclick = (e) => {
            e.stopPropagation();
            currentRegion = region;
            initDest();
            renderCities(regionsData[region]);
        };
        tabs.appendChild(btn);
    });
    renderCities(regionsData[currentRegion]);
}

function renderCities(cities) {
    const grid = document.getElementById('cityGrid');
    if(!grid) return;
    grid.innerHTML = '';
    
    cities.forEach(city => {
        const btn = document.createElement('button');
        btn.className = 'city-btn';
        btn.textContent = city;
        btn.onclick = (e) => {
            e.stopPropagation();
            const destInput = document.getElementById('destInput');
            if(destInput) destInput.value = city;
            closeAllPopovers();
        };
        grid.appendChild(btn);
    });
}

function filterCities() {
    const termInput = document.getElementById('citySearchInput');
    if(!termInput) return;
    
    const term = termInput.value.toLowerCase();
    const allCities = Object.values(regionsData).flat();
    const filtered = allCities.filter(c => c.includes(term));
    
    if(term === '') {
        renderCities(regionsData[currentRegion]);
    } else {
        renderCities(filtered);
    }
}

/* ================= Guest Counter ================= */
function updateCount(type, delta) {
    // Stop propagation if event exists
    if(typeof event !== 'undefined') event.stopPropagation();
    
    let val = guests[type] + delta;
    
    // Limits
    if(type === 'adult' && val < 1) val = 1;
    if(type === 'child' && val < 0) val = 0;
    if(type === 'room' && val < 1) val = 1;
    
    guests[type] = val;
    
    // UI Update
    const valDisplay = document.getElementById(`val-${type}`);
    const minusBtn = document.getElementById(`minus-${type}`);
    if(valDisplay) valDisplay.textContent = val;
    
    if(minusBtn) {
        minusBtn.disabled = (type === 'child' ? val <= 0 : val <= 1);
    }
    
    const guestInput = document.getElementById('guestInput');
    if(guestInput) {
        guestInput.value = `성인 ${guests.adult}, 아동 ${guests.child}, 객실 ${guests.room}`;
    }
}

/* ================= Common UI Logic ================= */
function openPopover(id) {
    closeAllPopovers();
    const pop = document.getElementById(id);
    const overlay = document.getElementById('uiOverlay');
    if(pop) pop.classList.add('active');
    if(overlay) overlay.classList.add('active');
}

function closeAllPopovers() {
    document.querySelectorAll('.popover').forEach(p => p.classList.remove('active'));
    const overlay = document.getElementById('uiOverlay');
    if(overlay) overlay.classList.remove('active');
}



document.addEventListener('DOMContentLoaded', () => {
    const sliderWrapper = document.querySelector('.event-slider-wrapper');
    const sliderTrack = document.querySelector('.grid-33'); // 슬라이드 트랙 역할
    const slides = document.querySelectorAll('.event-c');
    const prevBtn = document.querySelector('.slider-btn.prev');
    const nextBtn = document.querySelector('.slider-btn.next');

    let currentIndex = 0;
    let slideWidth = 0;
    let gap = 20; // CSS의 gap과 동일하게 설정
    let visibleItems = 3; // 기본 3개 보임

    // 초기화 및 반응형 처리
    function updateSliderDimensions() {
        const containerWidth = sliderWrapper.clientWidth;
        
        // 화면 크기에 따른 보이는 아이템 개수 설정 (CSS 미디어 쿼리와 일치)
        if (window.innerWidth <= 600) {
            visibleItems = 1;
        } else if (window.innerWidth <= 992) {
            visibleItems = 2;
        } else {
            visibleItems = 3;
        }

        // 슬라이드 하나의 너비 계산: (전체폭 - (갭 * (보이는개수-1))) / 보이는개수
        // *버튼 영역 확보를 위해 CSS에서 wrapper에 padding이 있다고 가정하거나, 계산에 보정치를 둡니다.
        // 여기서는 grid-3가 wrapper 꽉 차게 있다고 가정합니다.
        
        // grid-3의 너비 기준으로 계산
        const trackWidth = sliderTrack.clientWidth;
        slideWidth = (trackWidth - (gap * (visibleItems - 1))) / visibleItems;

        // 슬라이드들에게 너비 강제 적용 (flex-basis)
        slides.forEach(slide => {
            slide.style.flex = `0 0 ${slideWidth}px`;
            slide.style.maxWidth = `${slideWidth}px`; // 더 커지지 않게 고정
        });

        // 위치 재조정
        updateSlidePosition();
    }

    function updateSlidePosition() {
        // 이동 거리 = 인덱스 * (슬라이드너비 + 갭)
        const moveAmount = currentIndex * (slideWidth + gap);
        sliderTrack.style.transform = `translateX(-${moveAmount}px)`;
        
        // 버튼 활성화/비활성화 상태 관리
        prevBtn.style.opacity = currentIndex === 0 ? '0.5' : '1';
        prevBtn.style.pointerEvents = currentIndex === 0 ? 'none' : 'auto';

        const maxIndex = slides.length - visibleItems;
        nextBtn.style.opacity = currentIndex >= maxIndex ? '0.5' : '1';
        nextBtn.style.pointerEvents = currentIndex >= maxIndex ? 'none' : 'auto';
    }

    // 다음 버튼 클릭
    nextBtn.addEventListener('click', () => {
        const maxIndex = slides.length - visibleItems;
        if (currentIndex < maxIndex) {
            currentIndex++;
            updateSlidePosition();
        }
    });

    // 이전 버튼 클릭
    prevBtn.addEventListener('click', () => {
        if (currentIndex > 0) {
            currentIndex--;
            updateSlidePosition();
        }
    });

    // 창 크기 변경 시 사이즈 재계산
    window.addEventListener('resize', () => {
        updateSliderDimensions();
    });

    // 초기 실행
    updateSliderDimensions();
});
