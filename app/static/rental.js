// Lucide 아이콘 초기화
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initApp();
});

function initApp() {
    // 기본 날짜 설정
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const threeDaysLater = new Date(Date.now() + 86400000 * 3).toISOString().split('T')[0];

    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');

    startDateInput.value = today;
    endDateInput.value = threeDaysLater;

    // 최소 선택 가능 날짜 제한
    startDateInput.min = today;
    endDateInput.min = today;

    updateDtDisplay('start');
    updateDtDisplay('end');

    // 이벤트 리스너 등록
    setupEventListeners();
}

function setupEventListeners() {
    const overlay = document.getElementById('overlay');

    // 오버레이 클릭 시 모든 팝오버 닫기
    overlay.addEventListener('click', closeAllPopovers);

    // 입력 그룹 클릭 시 팝오버 토글
    document.getElementById('locInputGroup').addEventListener('click', () => handleTogglePopover('locPopover'));
    document.getElementById('startInputGroup').addEventListener('click', () => handleTogglePopover('startDtPopover'));
    document.getElementById('endInputGroup').addEventListener('click', () => handleTogglePopover('endDtPopover'));

    // 팝오버 내부 클릭 시 닫힘 방지
    document.querySelectorAll('.popover-container').forEach((p) => {
        p.addEventListener('click', (e) => e.stopPropagation());
    });

    // 장소 검색 및 필터
    const locSearchInput = document.getElementById('locSearchInput');
    locSearchInput.addEventListener('keyup', (e) => searchLoc(e.target.value));

    const sidebarBtns = document.querySelectorAll('.sidebar-btn');
    sidebarBtns.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            filterCategory(e.target.dataset.category, e.target);
        });
    });

    // 장소 아이템 선택
    const locItems = document.querySelectorAll('.location-item');
    locItems.forEach((item) => {
        item.addEventListener('click', () => selectLoc(item.dataset.name));
    });

    // 날짜 변경 감지
    ['startDate', 'startTime', 'endDate', 'endTime'].forEach((id) => {
        document.getElementById(id).addEventListener('change', () => {
            validateDates(id.startsWith('start') ? 'start' : 'end');
        });
    });

    // 확인 버튼들
    document.querySelectorAll('.btn-confirm').forEach((btn) => {
        btn.addEventListener('click', closeAllPopovers);
    });
}

function handleTogglePopover(id) {
    const popover = document.getElementById(id);
    const overlay = document.getElementById('overlay');
    const isActive = popover.classList.contains('active');

    closeAllPopovers();
    if (!isActive) {
        popover.classList.add('active');
        overlay.classList.add('active');
    }
}

function closeAllPopovers() {
    document.querySelectorAll('.popover-container').forEach((p) => p.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
}

function selectLoc(name) {
    document.getElementById('locDisplay').innerText = name;
    closeAllPopovers();
}

function filterCategory(cat, btn) {
    document.querySelectorAll('.sidebar-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');

    const items = document.querySelectorAll('.location-item');
    items.forEach((item) => {
        if (cat === 'all' || item.dataset.cat === cat) item.style.display = 'flex';
        else item.style.display = 'none';
    });
}

function searchLoc(val) {
    const items = document.querySelectorAll('.location-item');
    items.forEach((item) => {
        const name = item.dataset.name;
        if (name.includes(val)) item.style.display = 'flex';
        else item.style.display = 'none';
    });
}

function validateDates(type) {
    const startD = document.getElementById('startDate').value;
    const startT = document.getElementById('startTime').value;
    const endD = document.getElementById('endDate').value;
    const endT = document.getElementById('endTime').value;
    const errorMsg = document.getElementById('dtError');

    const startFull = new Date(`${startD}T${startT}`);
    const endFull = new Date(`${endD}T${endT}`);

    if (endFull <= startFull) {
        errorMsg.style.display = 'block';
        if (type === 'end') {
            // 반납 일시가 대여 일시보다 빠를 경우 대여 일시로 맞춤
            document.getElementById('endDate').value = startD;
        }
    } else {
        errorMsg.style.display = 'none';
    }

    updateDtDisplay('start');
    updateDtDisplay('end');
}

function updateDtDisplay(type) {
    const date = document.getElementById(type + 'Date').value;
    const time = document.getElementById(type + 'Time').value;
    if (date) {
        document.getElementById(type + 'DtDisplay').innerText = `${date} ${time}`;
    }
}
