/**
 * DESTINO 항공권 예약 시스템 스크립트
 */

function initIcons() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

/* ================= 데이터 & 상태 ================= */
const airportData = {
    '한국/동북아': [
        { name: '인천', code: 'ICN', country: '대한민국' },
        { name: '김포', code: 'GMP', country: '대한민국' },
        { name: '도쿄(나리타)', code: 'NRT', country: '일본' },
        { name: '도쿄(하네다)', code: 'HND', country: '일본' },
        { name: '오사카(간사이)', code: 'KIX', country: '일본' },
    ],
    동남아: [
        { name: '방콕(수완나품)', code: 'BKK', country: '태국' },
        { name: '다낭', code: 'DAD', country: '베트남' },
    ],
    '미주/유럽': [
        { name: '로스앤젤레스', code: 'LAX', country: '미국' },
        { name: '파리(샤를드골)', code: 'CDG', country: '프랑스' },
    ],
};

let currentTripType = 'round';
let segments = [
    { id: 1, dep: '인천 (ICN)', arr: '', date: '' },
    { id: 2, dep: '', arr: '인천 (ICN)', date: '' },
];

// 인원 및 좌석 상태
let passengerState = {
    adult: 1,
    child: 0,
    infant: 0,
    cabin: '일반석',
};

/* ================= 초기화 ================= */
document.addEventListener('DOMContentLoaded', () => {
    renderForm();
    initAirportPopover();
    initIcons();
});

function setTripType(type) {
    currentTripType = type;
    document.querySelectorAll('.flight-tab-btn').forEach((btn) => {
        btn.classList.remove('active');
        if (btn.getAttribute('onclick').includes(type)) btn.classList.add('active');
    });
    const addBtn = document.getElementById('addSegmentBtn');
    if (addBtn) addBtn.style.display = type === 'multi' ? 'flex' : 'none';
    renderForm();
}

function renderForm() {
    const container = document.getElementById('flightForm');
    if (!container) return;
    container.innerHTML = '';

    const passValue = `성인 ${passengerState.adult}${passengerState.child > 0 ? ', 소아 ' + passengerState.child : ''}, ${passengerState.cabin}`;

    if (currentTripType === 'multi') {
        segments.forEach((seg, index) => {
            const row = document.createElement('div');
            row.className = 'flight-row';
            row.innerHTML = `
                <div class="input-group" onclick="openAirportPopover('seg-${index}-dep')">
                    <label>출발지</label>
                    <input type="text" id="seg-${index}-dep" value="${seg.dep}" readonly placeholder="도시/공항">
                </div>
                <div class="swap-btn" style="transform: rotate(90deg); border:none;"><i data-lucide="plane" width="18"></i></div>
                <div class="input-group" onclick="openAirportPopover('seg-${index}-arr')">
                    <label>도착지</label>
                    <input type="text" id="seg-${index}-arr" value="${seg.arr}" readonly placeholder="도시/공항">
                </div>
                <div class="input-group" style="flex: 0.6;"><label>가는 날</label><input type="date"></div>
                ${segments.length > 2 ? `<button type="button" class="remove-segment-btn" onclick="removeSegment(${index})">&times;</button>` : ''}
            `;
            container.appendChild(row);
        });
        // 다구간일 때 하단에 인원 선택 바 추가 (구조상 별도 행)
        const bottomRow = document.createElement('div');
        bottomRow.className = 'flight-row';
        bottomRow.innerHTML = `
            <div class="input-group" onclick="openPassengerPopover()" style="width:100%">
                <label>인원 및 좌석</label>
                <input type="text" id="pass-input" value="${passValue}" readonly>
            </div>
        `;
        container.appendChild(bottomRow);
    } else {
        const row = document.createElement('div');
        row.className = 'flight-row';
        row.innerHTML = `
            <div class="input-group" onclick="openAirportPopover('main-dep')">
                <label>출발지</label>
                <input type="text" id="main-dep" value="인천 (ICN)" readonly>
            </div>
            <button type="button" class="swap-btn" onclick="swapMainLocations(event)"><i data-lucide="arrow-right-left" width="16"></i></button>
            <div class="input-group" onclick="openAirportPopover('main-arr')">
                <label>도착지</label>
                <input type="text" id="main-arr" value="" readonly placeholder="어디로 떠나시나요?">
            </div>
            <div class="input-group"><label>가는 날</label><input type="date"></div>
            ${currentTripType === 'round' ? '<div class="input-group"><label>오는 날</label><input type="date"></div>' : ''}
            <div class="input-group" onclick="openPassengerPopover()">
                <label>인원 및 좌석</label>
                <input type="text" id="pass-input" value="${passValue}" readonly>
            </div>
        `;
        container.appendChild(row);
    }
    initIcons();
}

/* ================= 팝업 제어 ================= */
function openAirportPopover(targetId) {
    activeInputId = targetId;
    document.getElementById('airportPopover').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function openPassengerPopover() {
    document.getElementById('passengerPopover').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function closeAllPopovers() {
    document.querySelectorAll('.popover').forEach((p) => p.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
    updatePassInput();
}

/* ================= 인원 조절 로직 ================= */
function updateCount(type, delta) {
    const newVal = passengerState[type] + delta;
    if (type === 'adult' && newVal < 1) return; // 성인 최소 1명
    if (newVal < 0) return; // 소아, 유아 최소 0명
    if (passengerState.adult + passengerState.child + passengerState.infant + delta > 9) {
        alert('최대 9명까지 선택 가능합니다.');
        return;
    }

    passengerState[type] = newVal;
    document.getElementById(`count-${type}`).textContent = newVal;
    updatePassInput();
}

function updateCabin(val) {
    passengerState.cabin = val;
    updatePassInput();
}

function updatePassInput() {
    const input = document.getElementById('pass-input');
    if (!input) return;
    const total = passengerState.adult + passengerState.child + passengerState.infant;
    let text = `성인 ${passengerState.adult}`;
    if (passengerState.child > 0) text += `, 소아 ${passengerState.child}`;
    if (passengerState.infant > 0) text += `, 유아 ${passengerState.infant}`;
    text += `, ${passengerState.cabin}`;
    input.value = text;
}

/* ================= 공항 선택 (기존 유지) ================= */
function initAirportPopover() {
    const tabs = document.getElementById('airportRegionTabs');
    if (!tabs) return;
    tabs.innerHTML = '';
    Object.keys(airportData).forEach((region, i) => {
        const btn = document.createElement('button');
        btn.className = `popover-tab ${i === 0 ? 'active' : ''}`;
        btn.textContent = region;
        btn.onclick = (e) => {
            document.querySelectorAll('.popover-tab').forEach((t) => t.classList.remove('active'));
            e.target.classList.add('active');
            renderAirportList(region);
        };
        tabs.appendChild(btn);
        if (i === 0) renderAirportList(region);
    });
}

function renderAirportList(region) {
    const list = document.getElementById('airportList');
    list.innerHTML = '';
    airportData[region].forEach((ap) => {
        const div = document.createElement('div');
        div.className = 'airport-item';
        div.innerHTML = `<div><span class="airport-name">${ap.name}</span><span class="airport-country">${ap.country}</span></div><span class="airport-code">${ap.code}</span>`;
        div.onclick = () => {
            if (activeInputId) document.getElementById(activeInputId).value = `${ap.name} (${ap.code})`;
            closeAllPopovers();
        };
        list.appendChild(div);
    });
}

function swapMainLocations(e) {
    e.stopPropagation();
    const d = document.getElementById('main-dep'),
        a = document.getElementById('main-arr');
    const t = d.value;
    d.value = a.value;
    a.value = t;
}

function addMultiCitySegment() {
    segments.push({ id: Date.now(), dep: '', arr: '', date: '' });
    renderForm();
}
function removeSegment(i) {
    segments.splice(i, 1);
    renderForm();
}
function performSearch() {
    alert('검색을 시작합니다.');
}
