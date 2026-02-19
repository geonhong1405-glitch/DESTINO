/**
 * DESTINO 항공권 예약 시스템 (flight.js)
 */

// 전역 상태
let tripType = 'round'; // round(왕복), one(편도), multi(다구간)
let currentDate = new Date();
let displayYear = currentDate.getFullYear();
let displayMonth = currentDate.getMonth();
let selectedStartDate = null;
let selectedEndDate = null;
let pax = { adult: 1, child: 0, infant: 0 };

// 초기화
window.addEventListener('DOMContentLoaded', () => {
    renderCalendar();
    updateDateDisplay();
    updatePaxDisplay();
});

// 여정 타입 변경
function setTripType(type) {
    tripType = type;
    document.querySelectorAll('.widget-tab').forEach((el) => el.classList.remove('active'));
    document.getElementById(`tab-${type}`).classList.add('active');

    // 편도 선택 시 도착일 초기화
    if (type === 'one') {
        selectedEndDate = null;
    }

    updateDateDisplay();
    renderCalendar();
}

// 모달 제어
function openSearchModal(type) {
    closeAllModals();
    document.getElementById(`${type}-modal`).classList.remove('hidden');
}

function toggleModal(id) {
    const el = document.getElementById(id);
    const isHidden = el.classList.contains('hidden');
    closeAllModals();
    if (isHidden) el.classList.remove('hidden');
}

function closeAllModals() {
    const modals = ['dep-modal', 'arr-modal', 'date-modal', 'pax-modal'];
    modals.forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
}

// 위치 선택
function selectLocation(type, name, country) {
    document.getElementById(`${type}-input`).value = name;
    document.getElementById(`${type}-sub`).innerText = country;
    closeAllModals();
}

// 출발지 <-> 도착지 교체
function swapLocations() {
    const depInput = document.getElementById('dep-input');
    const depSub = document.getElementById('dep-sub');
    const arrInput = document.getElementById('arr-input');
    const arrSub = document.getElementById('arr-sub');

    // 값이 둘 다 있을 때만 교체 (선택사항)
    // if (!depInput.value || !arrInput.value) return;

    const tempVal = depInput.value;
    const tempSub = depSub.innerText;

    depInput.value = arrInput.value;
    depSub.innerText = arrSub.innerText;
    arrInput.value = tempVal;
    arrSub.innerText = tempSub;
}

// 달력 로직
function changeMonth(delta, event) {
    if (event) event.stopPropagation();
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

function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    if (!grid) return;

    const monthYearTitle = document.getElementById('cal-month-year');
    monthYearTitle.innerText = `${displayYear}년 ${displayMonth + 1}월`;
    grid.innerHTML = '';

    const firstDay = new Date(displayYear, displayMonth, 1).getDay();
    const daysInMonth = new Date(displayYear, displayMonth + 1, 0).getDate();
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let i = 0; i < firstDay; i++) {
        grid.appendChild(document.createElement('div'));
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const cellDate = new Date(displayYear, displayMonth, day);
        const cell = document.createElement('div');
        cell.className = 'calendar-day';
        cell.innerText = day;

        if (cellDate < today) {
            cell.classList.add('disabled');
        } else {
            cell.onclick = (e) => {
                e.stopPropagation();
                handleDateClick(cellDate);
            };
        }

        // 선택 상태 스타일링
        const time = cellDate.getTime();
        const start = selectedStartDate ? selectedStartDate.getTime() : null;
        const end = selectedEndDate ? selectedEndDate.getTime() : null;

        if (start && time === start) cell.classList.add('selected');
        if (end && time === end) cell.classList.add('selected');

        // 범위 표시 (옵션: CSS에 .in-range 스타일 추가 필요)
        // if (start && end && time > start && time < end) cell.classList.add('in-range');

        grid.appendChild(cell);
    }
}

function handleDateClick(date) {
    if (tripType === 'one') {
        selectedStartDate = date;
        selectedEndDate = null;
        // 편도면 선택 후 모달 닫기
        // closeAllModals();
    } else {
        if (!selectedStartDate || (selectedStartDate && selectedEndDate)) {
            selectedStartDate = date;
            selectedEndDate = null;
        } else if (date < selectedStartDate) {
            selectedStartDate = date;
        } else {
            selectedEndDate = date;
            // 왕복 선택 완료 후 모달 닫기 (선택사항)
            // closeAllModals();
        }
    }
    renderCalendar();
    updateDateDisplay();
}

function updateDateDisplay() {
    const startEl = document.getElementById('start-date-display');
    const endEl = document.getElementById('end-date-display');

    if (!startEl || !endEl) return;

    const format = (d) => `${d.getMonth() + 1}월 ${d.getDate()}일`;

    if (!selectedStartDate) {
        startEl.innerText = '날짜 선택';
        startEl.style.color = '';
        startEl.style.fontWeight = '';
    } else {
        startEl.innerText = format(selectedStartDate);
        startEl.style.color = '#111827';
        startEl.style.fontWeight = '700';
    }

    if (tripType === 'one') {
        endEl.innerText = '-';
        endEl.style.color = '#9ca3af';
    } else {
        if (!selectedEndDate) {
            endEl.innerText = '날짜 선택';
            endEl.style.color = '';
            endEl.style.fontWeight = '';
        } else {
            endEl.innerText = format(selectedEndDate);
            endEl.style.color = '#111827';
            endEl.style.fontWeight = '700';
        }
    }
}

// 인원 변경
function changePax(type, delta, event) {
    if (event) event.stopPropagation();
    const newVal = pax[type] + delta;
    if (newVal < 0) return;
    if (type === 'adult' && newVal < 1) return; // 성인은 최소 1명

    pax[type] = newVal;
    document.getElementById(`${type}-count`).innerText = newVal;
    updatePaxDisplay();
}

function updatePaxDisplay() {
    const total = pax.adult + pax.child + pax.infant;
    const el = document.getElementById('pax-display');
    if (el) {
        el.innerText = `성인 ${pax.adult}명, 소아 ${pax.child}명`;
        el.style.color = '#111827';
        el.style.fontWeight = '700';
    }
}

// 리스트 필터링
function filterList(keyword, listId) {
    const list = document.getElementById(listId);
    const items = list.getElementsByTagName('li');
    const lower = keyword.toLowerCase();
    for (let item of items) {
        const text = item.innerText.toLowerCase();
        item.style.display = text.includes(lower) ? 'flex' : 'none';
    }
}

// 검색 실행
function performFlightSearch() {
    const dep = document.getElementById('dep-input').value;
    const arr = document.getElementById('arr-input').value;

    if (!arr) return alert('도착지를 선택해주세요.');
    if (!selectedStartDate) return alert('출발 날짜를 선택해주세요.');

    alert(`[검색 요청]\n출발: ${dep}\n도착: ${arr}\n날짜: ${document.getElementById('start-date-display').innerText}`);
}

// 외부 클릭 닫기
document.addEventListener('click', (e) => {
    if (!e.target.closest('.input-group') && !e.target.closest('.dropdown-modal')) {
        closeAllModals();
    }
});
