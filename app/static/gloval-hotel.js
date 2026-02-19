document.addEventListener('DOMContentLoaded', function () {
    // 디버깅용 콘솔 로그
    console.log('gloval-hotel.js loaded');

    // Lucide 아이콘 초기화
    if (window.lucide && lucide.createIcons) {
        lucide.createIcons();
    }

    /* ================= 목적지 데이터 및 모달 로직 ================= */
    const regionsData = {
        일본: ['도쿄', '오사카', '후쿠오카', '삿포로', '오키나와', '나고야', '교토', '고베'],
        동남아: ['방콕', '다낭', '나트랑', '세부', '발리', '싱가포르', '푸껫', '코타키나발루', '마닐라'],
        '홍콩/마카오/중국': ['홍콩', '마카오', '상하이', '베이징', '칭다오', '광저우'],
        남태평양: ['괌', '사이판', '시드니', '오클랜드', '멜버른', '골드코스트'],
        미주: ['하와이', '뉴욕', '로스앤젤레스', '라스베이거스', '샌프란시스코', '밴쿠버'],
        유럽: ['파리', '런던', '로마', '바르셀로나', '프라하', '인터라켄', '베네치아', '피렌체'],
        '중동/아프리카': ['두바이', '카이로', '케이프타운', '아부다비'],
    };

    const regionTabs = document.getElementById('regionTabs');
    const cityGrid = document.getElementById('cityGrid');
    const regionTitle = document.getElementById('selectedRegionTitle');
    const destInput = document.getElementById('destInput');

    // 지역 탭 렌더링
    function initDestinations() {
        let isFirst = true;
        for (const region in regionsData) {
            const btn = document.createElement('button');
            btn.className = `dest-tab ${isFirst ? 'active' : ''}`;
            btn.textContent = region;
            btn.onclick = (e) => {
                e.stopPropagation();
                document.querySelectorAll('.dest-tab').forEach((t) => t.classList.remove('active'));
                btn.classList.add('active');
                renderCities(region);
            };
            regionTabs.appendChild(btn);

            if (isFirst) {
                renderCities(region);
                isFirst = false;
            }
        }
    }

    // 선택된 지역의 도시 렌더링
    function renderCities(region) {
        regionTitle.textContent = `${region} 주요 도시`;
        cityGrid.innerHTML = '';
        regionsData[region].forEach((city) => {
            const btn = document.createElement('button');
            btn.className = 'city-btn';
            btn.textContent = city;
            btn.onclick = (e) => {
                e.stopPropagation();
                destInput.value = `${city}, ${region}`;
                // 국가명 자동 입력 (region이 국가명인 경우만)
                const countryInput = document.getElementById('countryInput');
                if (countryInput) {
                    countryInput.value = region;
                }
                closeAllPopovers();
            };
            cityGrid.appendChild(btn);
        });
    }
    initDestinations();

    /* ================= 날짜 초기화 (오늘/내일) ================= */
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const checkinInput = document.getElementById('checkinDate');
    const checkoutInput = document.getElementById('checkoutDate');

    if (checkinInput && checkoutInput) {
        checkinInput.valueAsDate = today;
        checkoutInput.valueAsDate = tomorrow;
    }

    /* ================= 인원 및 객실 로직 ================= */
    let guests = { adult: 2, child: 0, room: 1 };

    function updateGuest(type, change) {
        if (window.event) window.event.stopPropagation();
        let newVal = guests[type] + change;
        if (type === 'adult' && newVal < 1) newVal = 1;
        if (type === 'child' && newVal < 0) newVal = 0;
        if (type === 'room' && newVal < 1) newVal = 1;
        guests[type] = newVal;
        const valElem = document.getElementById(`val${capitalize(type)}`);
        if (valElem) valElem.textContent = newVal;
        const guestInput = document.getElementById('guestInput');
        if (guestInput) guestInput.value = `성인 ${guests.adult}명, 아동 ${guests.child}명, 객실 ${guests.room}개`;
        const btnAdultMinus = document.getElementById('btnAdultMinus');
        const btnChildMinus = document.getElementById('btnChildMinus');
        const btnRoomMinus = document.getElementById('btnRoomMinus');
        if (btnAdultMinus) btnAdultMinus.disabled = guests.adult <= 1;
        if (btnChildMinus) btnChildMinus.disabled = guests.child <= 0;
        if (btnRoomMinus) btnRoomMinus.disabled = guests.room <= 1;
    }

    function capitalize(s) {
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    /* ================= Popover 제어 로직 ================= */
    function openPopover(id) {
        closeAllPopovers();
        const popover = document.getElementById(id);
        const overlay = document.getElementById('widgetOverlay');
        if (popover) popover.classList.add('active');
        if (overlay) overlay.classList.add('active');
    }

    function closeAllPopovers() {
        document.querySelectorAll('.popover').forEach((p) => p.classList.remove('active'));
        const overlay = document.getElementById('widgetOverlay');
        if (overlay) overlay.classList.remove('active');
    }

    // ================= 검색 버튼 동작 =================
    const searchBtn = document.querySelector('.btn-search');
    console.log('searchBtn:', searchBtn);
    if (searchBtn) {
        searchBtn.addEventListener('click', function () {
            console.log('검색 버튼 클릭됨');
            const dest = document.getElementById('destInput').value.trim();
            let city = '',
                country = '';
            if (dest.includes(',')) {
                const parts = dest.split(',');
                city = parts[0].trim();
                country = parts[1].trim();
            } else {
                city = dest;
            }
            const checkin = document.getElementById('checkinDate').value;
            const checkout = document.getElementById('checkoutDate').value;
            const params = new URLSearchParams();
            if (city) params.append('city', city);
            if (country) params.append('country', country);
            if (checkin) params.append('checkin', checkin);
            if (checkout) params.append('checkout', checkout);
            window.location.href = '/gloval-hotel?' + params.toString();
        });
    }

    window.openPopover = openPopover;
    window.closeAllPopovers = closeAllPopovers;
});
