let tripType = 'round';
let currentDate = new Date();
let displayYear = currentDate.getFullYear();
let displayMonth = currentDate.getMonth();
let selectedStartDate = null;
let selectedEndDate = null;
let pax = { adult: 1, child: 0, infant: 0 };

// 페이지 로드 시 초기화
window.addEventListener('load', () => {
    renderCalendar();
    loadRecentSearch();
    updateDateDisplay();
});

// 여정 타입 변경 (왕복/편도 등)
function setTripType(type) {
    tripType = type;
    document.querySelectorAll('.search-tab').forEach((el) => el.classList.remove('active'));
    document.getElementById(`tab-${type}`).classList.add('active');

    // 편도로 바꿀 때 종료일 초기화
    if (type === 'one') selectedEndDate = null;

    renderCalendar();
    updateDateDisplay();
}

// 공항 검색 모달 열기
function openSearchModal(type) {
    closeAllModals();
    document.getElementById(`${type}-modal`).classList.remove('hidden');
}

// 특정 모달 토글
function toggleModal(id) {
    const el = document.getElementById(id);
    const isHidden = el.classList.contains('hidden');
    if (isHidden) {
        closeAllModals();
        el.classList.remove('hidden');
    } else {
        el.classList.add('hidden');
    }
}

// 모든 모달 닫기
function closeAllModals() {
    ['dep-modal', 'arr-modal', 'date-pax-modal'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
}

// 달력 월 변경
function changeMonth(delta, event) {
    if (event) event.stopPropagation(); // 모달 닫힘 방지
    displayMonth += delta;
    if (displayMonth > 11) {
        displayMonth = 0;
        displayYear++;
    } else if (displayMonth < 0) {
        displayMonth = 11;
        displayYear--;
    }
    renderCalendar();
}

// 달력 그리기 로직
function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    const monthYearTitle = document.getElementById('cal-month-year');
    if (!grid || !monthYearTitle) return;

    monthYearTitle.innerText = `${displayYear}년 ${displayMonth + 1}월`;
    grid.innerHTML = '';

    const firstDay = new Date(displayYear, displayMonth, 1).getDay();
    const daysInMonth = new Date(displayYear, displayMonth + 1, 0).getDate();
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // 공백 채우기
    for (let i = 0; i < firstDay; i++) {
        grid.appendChild(document.createElement('div'));
    }

    // 날짜 채우기
    for (let day = 1; day <= daysInMonth; day++) {
        const cellDate = new Date(displayYear, displayMonth, day);
        const cell = document.createElement('div');
        cell.className = 'calendar-day';
        cell.innerText = day;

        if (cellDate < today) {
            cell.classList.add('disabled');
        } else {
            cell.onclick = (e) => {
                e.stopPropagation(); // 날짜 클릭 시 모달이 닫히지 않도록 방지
                handleDateClick(cellDate);
            };
        }

        // 선택 및 범위 표시 스타일 적용
        const time = cellDate.getTime();
        const start = selectedStartDate ? selectedStartDate.getTime() : null;
        const end = selectedEndDate ? selectedEndDate.getTime() : null;

        if (start && time === start) {
            if (end) cell.classList.add('range-start');
            else cell.classList.add('selected');
        }
        if (end && time === end) cell.classList.add('range-end');
        if (start && end && time > start && time < end) cell.classList.add('in-range');

        grid.appendChild(cell);
    }
}

// 날짜 클릭 처리
function handleDateClick(date) {
    if (tripType === 'one') {
        selectedStartDate = date;
        selectedEndDate = null;
    } else {
        // 왕복인 경우
        if (!selectedStartDate || (selectedStartDate && selectedEndDate)) {
            selectedStartDate = date;
            selectedEndDate = null;
        } else if (date < selectedStartDate) {
            selectedStartDate = date;
        } else if (date.getTime() !== selectedStartDate.getTime()) {
            selectedEndDate = date;
        }
    }
    renderCalendar();
    updateDateDisplay();
}

// 화면 상단 날짜 텍스트 업데이트
function updateDateDisplay() {
    const displayEl = document.getElementById('date-display');
    if (!displayEl) return;

    if (!selectedStartDate) {
        displayEl.innerText = '날짜를 선택하세요';
        displayEl.style.color = '#9ca3af'; // 가독성을 위한 회색 처리
        return;
    }

    displayEl.style.color = '#111827';
    const format = (d) =>
        `${d.getMonth() + 1}.${d.getDate()}(${['일', '월', '화', '수', '목', '금', '토'][d.getDay()]})`;

    if (tripType === 'one' || !selectedEndDate) {
        displayEl.innerText = format(selectedStartDate);
    } else {
        displayEl.innerText = `${format(selectedStartDate)} - ${format(selectedEndDate)}`;
    }
}

// 인원수 변경
function changePax(type, delta, event) {
    if (event) event.stopPropagation();
    const newVal = pax[type] + delta;
    if (newVal < 0 || (type === 'adult' && newVal < 1)) return;

    pax[type] = newVal;
    const countEl = document.getElementById(`pax-${type}-count`);
    if (countEl) countEl.innerText = newVal;
    updatePaxDisplay();
}

// 화면 인원 텍스트 업데이트
function updatePaxDisplay() {
    let text = `성인 ${pax.adult}`;
    if (pax.child > 0) text += `, 소아 ${pax.child}`;
    if (pax.infant > 0) text += `, 유아 ${pax.infant}`;
    const displayEl = document.getElementById('pax-display');
    if (displayEl) displayEl.innerText = text;
}

// 선택 완료 버튼 (모달 닫기)
function confirmSelection(event) {
    if (event) event.stopPropagation();
    document.getElementById('date-pax-modal').classList.add('hidden');
}

// 장소 선택 처리
function selectLocation(type, name, sub) {
    document.getElementById(`${type}-input`).value = name;
    document.getElementById(`${type}-sub`).innerText = sub;
    document.getElementById(`${type}-modal`).classList.add('hidden');
}

// 출발지/도착지 반전
function swapLocations() {
    const depInput = document.getElementById('dep-input');
    const depSub = document.getElementById('dep-sub');
    const arrInput = document.getElementById('arr-input');
    const arrSub = document.getElementById('arr-sub');

    const tVal = depInput.value;
    const tSub = depSub.innerText;

    depInput.value = arrInput.value;
    depSub.innerText = arrSub.innerText;

    arrInput.value = tVal;
    arrSub.innerText = tSub;
}

// 리스트 필터링 (검색어 입력 시)
function filterList(keyword, listId) {
    const items = document.getElementById(listId).getElementsByTagName('li');
    const lower = keyword.toLowerCase();
    for (let item of items) {
        item.style.display = item.textContent.toLowerCase().includes(lower) ? 'flex' : 'none';
    }
}

// 검색 실행
function performSearch() {
    const arrValue = document.getElementById('arr-input').value;
    if (!arrValue || arrValue === '') return alert('도착지를 선택하세요.');
    if (!selectedStartDate) return alert('날짜를 선택하세요.');

    const data = {
        dep: document.getElementById('dep-input').value,
        arr: arrValue,
    };
    localStorage.setItem('destino_recent', JSON.stringify(data));
    alert('검색을 시작합니다.');
    location.reload();
}

// 최근 검색어 로드
function loadRecentSearch() {
    const saved = localStorage.getItem('destino_recent');
    const area = document.getElementById('recent-search-area');
    const text = document.getElementById('recent-text');
    if (saved && area && text) {
        const data = JSON.parse(saved);
        area.classList.remove('hidden');
        text.innerText = `${data.dep} → ${data.arr}`;
    }
}

// 최근 검색어 삭제
function clearRecent(e) {
    e.stopPropagation();
    localStorage.removeItem('destino_recent');
    location.reload();
}

// 모달 외부 클릭 시 닫기 처리
document.addEventListener('click', (e) => {
    const isClickInside = e.target.closest('.relative') || e.target.closest('.group');
    if (!isClickInside) {
        closeAllModals();
    }
});
