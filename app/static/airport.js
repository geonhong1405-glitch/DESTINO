/**
 * DESTINO 항공권 검색 스크립트
 */

function initIcons() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

const airportData = {
    '한국/일본': [
        { name: '인천', code: 'ICN', country: '대한민국' },
        { name: '김포', code: 'GMP', country: '대한민국' },
        { name: '도쿄(나리타)', code: 'NRT', country: '일본' },
        { name: '도쿄(하네다)', code: 'HND', country: '일본' },
        { name: '오사카(간사이)', code: 'KIX', country: '일본' },
    ],
    '동남아': [
        { name: '방콕(수완나폼)', code: 'BKK', country: '태국' },
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
let activeInputId = null;

let passengerState = {
    adult: 1,
    child: 0,
    infant: 0,
    cabin: 'ECONOMY',
};

document.addEventListener('DOMContentLoaded', () => {
    renderForm();
    initAirportPopover();
    initIcons();
});

function setTripType(type) {
    closeAllPopovers();
    activeInputId = null;
    currentTripType = type;
    document.querySelectorAll('.flight-tab-btn').forEach((btn) => {
        btn.classList.remove('active');
        if ((btn.getAttribute('onclick') || '').includes(type)) btn.classList.add('active');
    });
    const addBtn = document.getElementById('addSegmentBtn');
    if (addBtn) addBtn.style.display = type === 'multi' ? 'flex' : 'none';
    renderForm();
}

function renderForm() {
    const container = document.getElementById('flightForm');
    if (!container) return;
    container.innerHTML = '';

    const cabinReverseMap = {
        ECONOMY: '일반석',
        BUSINESS: '프레스티지',
        FIRST: '일등석',
    };
    const passValue = `성인 ${passengerState.adult}${passengerState.child > 0 ? `, 소아 ${passengerState.child}` : ''}${passengerState.infant > 0 ? `, 유아 ${passengerState.infant}` : ''}, ${cabinReverseMap[passengerState.cabin] || passengerState.cabin}`;

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
                <div class="input-group" style="flex: 0.6;"><label>날짜</label><input type="date" id="seg-${index}-date" value="${seg.date || ''}"></div>
                ${segments.length > 2 ? `<button type="button" class="remove-segment-btn" onclick="removeSegment(${index})">&times;</button>` : ''}
            `;
            container.appendChild(row);
        });

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
            <div class="input-group"><label>출발일</label><input type="date" id="main-dep-date"></div>
            ${currentTripType === 'round' ? '<div class="input-group"><label>오는 날</label><input type="date" id="main-return-date"></div>' : ''}
            <div class="input-group" onclick="openPassengerPopover()">
                <label>인원 및 좌석</label>
                <input type="text" id="pass-input" value="${passValue}" readonly>
            </div>
        `;
        container.appendChild(row);
    }
    initIcons();
}

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

function updateCount(type, delta) {
    const newVal = passengerState[type] + delta;
    if (type === 'adult' && newVal < 1) return;
    if (newVal < 0) return;
    if (passengerState.adult + passengerState.child + passengerState.infant + delta > 9) {
        alert('최대 9명까지 선택 가능합니다.');
        return;
    }

    passengerState[type] = newVal;
    const el = document.getElementById(`count-${type}`);
    if (el) el.textContent = newVal;
    updatePassInput();
}

function updateCabin(val) {
    const cabinMap = {
        '일반석': 'ECONOMY',
        '프레스티지': 'BUSINESS',
        '일등석': 'FIRST',
    };
    passengerState.cabin = cabinMap[val] || val;
    updatePassInput();
}

function updatePassInput() {
    const input = document.getElementById('pass-input');
    if (!input) return;
    let text = `성인 ${passengerState.adult}`;
    if (passengerState.child > 0) text += `, 소아 ${passengerState.child}`;
    if (passengerState.infant > 0) text += `, 유아 ${passengerState.infant}`;
    const cabinReverseMap = {
        ECONOMY: '일반석',
        BUSINESS: '프레스티지',
        FIRST: '일등석',
    };
    text += `, ${cabinReverseMap[passengerState.cabin] || passengerState.cabin}`;
    input.value = text;
}

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
    if (!list || !airportData[region]) return;
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

function filterAirports() {
    const input = document.getElementById('airportSearchInput');
    const list = document.getElementById('airportList');
    if (!input || !list) return;
    const keyword = (input.value || '').toLowerCase();
    list.querySelectorAll('.airport-item').forEach((item) => {
        item.style.display = item.textContent.toLowerCase().includes(keyword) ? '' : 'none';
    });
}

function swapMainLocations(e) {
    e.stopPropagation();
    const d = document.getElementById('main-dep');
    const a = document.getElementById('main-arr');
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

function extractIata(value) {
    if (!value) return '';
    return value.match(/\((\w{3})\)/)?.[1] || value.trim();
}

async function fetchFlightSearch({ origin, destination, departure_date, return_date = '' }) {
    const adults = passengerState.adult;
    const child = passengerState.child;
    const infant = passengerState.infant;
    const cabin = passengerState.cabin;

    const params = new URLSearchParams({
        origin,
        destination,
        departure_date,
        adults: String(adults),
        child: String(child),
        infant: String(infant),
        cabin,
    });
    if (return_date) params.set('return_date', return_date);

    const res = await fetch(`/api/flight-search?${params.toString()}`);
    if (!res.ok) {
        const body = await res.text();
        throw new Error(body || '검색 실패');
    }
    return res.json();
}

async function performSearch() {
    closeAllPopovers();

    let resultDiv = document.getElementById('flightResultArea');
    if (resultDiv) resultDiv.innerHTML = '';
    showFlightLoading();

    try {
        if (currentTripType === 'multi') {
            const legs = [];
            for (let i = 0; i < segments.length; i += 1) {
                const depVal = document.getElementById(`seg-${i}-dep`)?.value || '';
                const arrVal = document.getElementById(`seg-${i}-arr`)?.value || '';
                const dateVal = document.getElementById(`seg-${i}-date`)?.value || '';
                const origin = extractIata(depVal);
                const destination = extractIata(arrVal);
                if (!origin || !destination || !dateVal) {
                    alert(`${i + 1}구간의 출발지/도착지/날짜를 모두 입력해 주세요.`);
                    return;
                }
                legs.push({ origin, destination, departure_date: dateVal });
            }

            const responses = await Promise.all(
                legs.map((leg) =>
                    fetchFlightSearch({
                        origin: leg.origin,
                        destination: leg.destination,
                        departure_date: leg.departure_date,
                    }),
                ),
            );
            renderMultiFlightResults(responses, legs);
            return;
        }

        const origin = extractIata(document.getElementById('main-dep')?.value || '');
        const destination = extractIata(document.getElementById('main-arr')?.value || '');
        const departure_date = document.getElementById('main-dep-date')?.value || '';
        const return_date = currentTripType === 'round' ? (document.getElementById('main-return-date')?.value || '') : '';
        if (!origin || !destination || !departure_date) {
            alert('출발지, 도착지, 날짜를 모두 입력해 주세요.');
            return;
        }
        if (currentTripType === 'round' && !return_date) {
            alert('왕복 검색은 오는 날을 입력해 주세요.');
            return;
        }

        const data = await fetchFlightSearch({
            origin,
            destination,
            departure_date,
            return_date: currentTripType === 'round' ? return_date : '',
        });
        renderFlightResults(data);
    } catch (e) {
        renderFlightError(e.message);
    }
}

function showFlightLoading() {
    let resultDiv = document.getElementById('flightResultArea');
    if (!resultDiv) {
        resultDiv = document.createElement('div');
        resultDiv.id = 'flightResultArea';
        document.querySelector('.search-widget').appendChild(resultDiv);
    }
    resultDiv.innerHTML = '<div class="flight-loading">항공편을 검색 중입니다...</div>';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatKrw(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    return `₩${new Intl.NumberFormat('ko-KR').format(Math.round(Number(value)))}`;
}

function formatTime(isoString) {
    if (!isoString) return '-';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return '-';
    return d.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function formatDuration(duration) {
    if (!duration || typeof duration !== 'string') return '-';
    const m = duration.match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
    if (!m) return duration;
    const h = Number(m[1] || 0);
    const min = Number(m[2] || 0);
    if (h && min) return `${h}시간 ${min}분`;
    if (h) return `${h}시간`;
    return `${min}분`;
}

function buildStopLabel(itinerary) {
    const segs = itinerary?.segments || [];
    const stops = Math.max(segs.length - 1, 0);
    if (stops === 0) return '직항';
    if (stops === 1) return '1회 경유';
    return `${stops}회 경유`;
}

const AIRLINE_NAMES = {
    KE: '대한항공',
    OZ: '아시아나항공',
    JL: '일본항공',
    NH: '전일본공수',
    '7C': '제주항공',
    TW: '티웨이항공',
    BX: '에어부산',
    LJ: '진에어',
    RS: '에어서울',
    ZE: '이스타항공',
    SQ: '싱가포르항공',
    CX: '캐세이퍼시픽',
    TG: '타이항공',
    MU: '중국동방항공',
    FM: '상하이항공',
};

function getCarrierDict(data) {
    return data?.raw?.dictionaries?.carriers || {};
}

function getAirlineLogoUrl(code) {
    if (!code) return '';
    return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(code)}.png`;
}

function getAirlineDisplay(offer, carriers = {}) {
    const code =
        (offer?.validatingAirlineCodes && offer.validatingAirlineCodes[0]) ||
        offer?.itineraries?.[0]?.segments?.[0]?.carrierCode ||
        '-';
    const name = carriers[code] || AIRLINE_NAMES[code] || code;
    return { code, name };
}

function getDisplayPrice(offer) {
    if (offer?.price?.krwTotal) return formatKrw(offer.price.krwTotal);
    const amount = Number(offer?.price?.total);
    const cur = offer?.price?.currency || '';
    if (!Number.isNaN(amount) && cur === 'KRW') return formatKrw(amount);
    if (!Number.isNaN(amount)) return `${new Intl.NumberFormat('ko-KR').format(Math.round(amount))} ${cur}`;
    return '-';
}

function buildFlightCardsHtml(data) {
    const results = data && (data.results || data.data);
    if (!results || results.length === 0) {
        return '<div class="flight-no-result">검색 결과가 없습니다.</div>';
    }
    const carriers = getCarrierDict(data);
    const sorted = [...results].sort((a, b) => {
        const aPrice = Number(a?.price?.krwTotal || a?.price?.total || Number.MAX_SAFE_INTEGER);
        const bPrice = Number(b?.price?.krwTotal || b?.price?.total || Number.MAX_SAFE_INTEGER);
        return aPrice - bPrice;
    });

    let html = '<div class="flight-result-list">';
    sorted.forEach((f) => {
        const itineraries = Array.isArray(f.itineraries) ? f.itineraries : [];
        const airline = getAirlineDisplay(f, carriers);
        html += `
            <article class="flight-card">
                <div class="flight-card-main">
                    <div class="flight-airline">
                        <div class="flight-airline-mark">
                            <img
                                class="flight-airline-logo"
                                src="${getAirlineLogoUrl(airline.code)}"
                                alt="${escapeHtml(airline.name)} 로고"
                                loading="lazy"
                                onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                            >
                            <div class="flight-airline-badge" style="display:none;">${escapeHtml(airline.code)}</div>
                        </div>
                        <div class="flight-airline-name">${escapeHtml(airline.name)}</div>
                    </div>
                    <div class="flight-leg-list">
                        ${itineraries.map((it) => renderItineraryLine(it)).join('')}
                    </div>
                </div>
                <aside class="flight-card-price">
                    <div class="flight-offer-count">총 ${itineraries.length}구간</div>
                    <div class="flight-price-main">${getDisplayPrice(f)}</div>
                    <div class="flight-price-sub">${escapeHtml(f?.price?.currency || '')} ${escapeHtml(f?.price?.total || '')}</div>
                    <button type="button" class="flight-select-btn">선택하기</button>
                </aside>
            </article>
        `;
    });
    html += '</div>';

    if (data.booking_reference && Array.isArray(data.booking_reference) && data.booking_reference.length > 0) {
        html += '<div class="flight-booking-ref"><h4>Booking.com 참고 항공권</h4>';
        data.booking_reference.forEach((f) => {
            const rawPrice = Number(f.price);
            const krwPrice = f.price_krw
                ? formatKrw(f.price_krw)
                : (!Number.isNaN(rawPrice) && f.currency === 'KRW' ? formatKrw(rawPrice) : null);
            html += `<div class="flight-result-item booking-ref">
                <div><b>${escapeHtml(f.validating_airline || '-')}</b> ${escapeHtml(f.flight_number || '')}</div>
                <div>${escapeHtml(f.origin || '')} → ${escapeHtml(f.destination || '')}</div>
                <div>출발: ${escapeHtml(f.departure_time || '')}</div>
                <div>도착: ${escapeHtml(f.arrival_time || '')}</div>
                <div>가격: <b>${krwPrice || `${escapeHtml(f.price || '')} ${escapeHtml(f.currency || '')}`}</b></div>
            </div>`;
        });
        html += '</div>';
    }

    return html;
}

function renderItineraryLine(itinerary) {
    const segs = itinerary?.segments || [];
    const first = segs[0] || {};
    const last = segs[segs.length - 1] || {};
    const depAt = first?.departure?.at;
    const arrAt = last?.arrival?.at;
    const depCode = first?.departure?.iataCode || '-';
    const arrCode = last?.arrival?.iataCode || '-';
    const viaCode = segs.length > 1 ? (segs[0]?.arrival?.iataCode || '') : '';
    const stopDetail = segs.length > 1 && viaCode ? `${buildStopLabel(itinerary)} ${viaCode}` : buildStopLabel(itinerary);
    return `
        <div class="flight-leg">
            <div class="flight-leg-time">
                <div class="flight-leg-clock">${formatTime(depAt)}</div>
                <div class="flight-leg-code">${escapeHtml(depCode)}</div>
            </div>
            <div class="flight-leg-middle">
                <div class="flight-leg-duration">${formatDuration(itinerary?.duration)}</div>
                <div class="flight-leg-line"></div>
                <div class="flight-leg-stop">${escapeHtml(stopDetail)}</div>
            </div>
            <div class="flight-leg-time">
                <div class="flight-leg-clock">${formatTime(arrAt)}</div>
                <div class="flight-leg-code">${escapeHtml(arrCode)}</div>
            </div>
        </div>
    `;
}

function renderFlightResults(data) {
    let resultDiv = document.getElementById('flightResultArea');
    if (!resultDiv) {
        resultDiv = document.createElement('div');
        resultDiv.id = 'flightResultArea';
        document.querySelector('.search-widget').appendChild(resultDiv);
    }
    resultDiv.innerHTML = buildFlightCardsHtml(data);
}

function renderMultiFlightResults(dataList, legs) {
    let resultDiv = document.getElementById('flightResultArea');
    if (!resultDiv) {
        resultDiv = document.createElement('div');
        resultDiv.id = 'flightResultArea';
        document.querySelector('.search-widget').appendChild(resultDiv);
    }
    let html = '<div class="flight-multi-result">';
    dataList.forEach((data, idx) => {
        const leg = legs[idx];
        html += `
            <section class="flight-multi-section">
                <h4 class="flight-multi-title">${idx + 1}구간: ${escapeHtml(leg.origin)} → ${escapeHtml(leg.destination)} (${escapeHtml(leg.departure_date)})</h4>
                ${buildFlightCardsHtml(data)}
            </section>
        `;
    });
    html += '</div>';
    resultDiv.innerHTML = html;
}

function renderFlightError(msg) {
    let resultDiv = document.getElementById('flightResultArea');
    if (!resultDiv) {
        resultDiv = document.createElement('div');
        resultDiv.id = 'flightResultArea';
        document.querySelector('.search-widget').appendChild(resultDiv);
    }
    resultDiv.innerHTML = `<div class="flight-error">오류: ${escapeHtml(msg)}</div>`;
}
