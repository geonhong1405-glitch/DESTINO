// Initialize Lucide Icons
lucide.createIcons();

// State Management
let currentDates = {
    start: new Date(),
    end: new Date(),
};
let selectedDates = {
    start: null,
    end: null,
};

/**
 * Popover Handlers
 */
function openPopover(e, id) {
    e.stopPropagation();
    closeAllPopovers();
    document.getElementById(id).classList.add('active');
    document.getElementById('overlay').classList.add('active');

    if (id.includes('cal')) {
        const type = id.includes('Start') ? 'start' : 'end';
        renderCalendar(type);
    }
}

function closeAllPopovers() {
    document.querySelectorAll('.popover').forEach((p) => p.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
}

/**
 * Selection Handlers
 */
function selectRegion(type, val) {
    const targetSpan = document.getElementById(`text-${type}`);
    if (targetSpan) targetSpan.innerText = val;
    closeAllPopovers();
}

function filterRegion(input) {
    const filter = input.value.toUpperCase();
    const list = input.closest('.popover-main').querySelector('.region-list');
    const items = list.getElementsByTagName('li');
    for (let i = 0; i < items.length; i++) {
        const text = items[i].textContent || items[i].innerText;
        items[i].style.display = text.toUpperCase().indexOf(filter) > -1 ? '' : 'none';
    }
}

/**
 * Calendar Logic
 */
function renderCalendar(type) {
    const date = currentDates[type];
    const year = date.getFullYear();
    const month = date.getMonth();

    // Render Select Boxes in Header
    const titleWrap = document.getElementById(`title-wrap-${type}`);
    if (!titleWrap) return;
    titleWrap.innerHTML = '';

    // Year Select
    const yearSelect = document.createElement('select');
    yearSelect.className = 'calendar-select';
    for (let y = 2024; y <= 2030; y++) {
        const opt = document.createElement('option');
        opt.value = y;
        opt.innerText = `${y}년`;
        if (y === year) opt.selected = true;
        yearSelect.appendChild(opt);
    }
    yearSelect.onchange = (e) => {
        currentDates[type].setFullYear(parseInt(e.target.value));
        renderCalendar(type);
    };

    // Month Select
    const monthSelect = document.createElement('select');
    monthSelect.className = 'calendar-select';
    for (let m = 0; m < 12; m++) {
        const opt = document.createElement('option');
        opt.value = m;
        opt.innerText = `${m + 1}월`;
        if (m === month) opt.selected = true;
        monthSelect.appendChild(opt);
    }
    monthSelect.onchange = (e) => {
        currentDates[type].setMonth(parseInt(e.target.value));
        renderCalendar(type);
    };

    titleWrap.appendChild(yearSelect);
    titleWrap.appendChild(monthSelect);

    const grid = document.getElementById(`grid-${type}`);
    if (!grid) return;
    grid.innerHTML = '';

    // Days Label
    ['일', '월', '화', '수', '목', '금', '토'].forEach((d) => {
        const el = document.createElement('div');
        el.className = 'day-label';
        el.innerText = d;
        grid.appendChild(el);
    });

    const firstDay = new Date(year, month, 1).getDay();
    const lastDate = new Date(year, month + 1, 0).getDate();
    const prevLastDate = new Date(year, month, 0).getDate();

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Previous Month Days
    for (let i = firstDay; i > 0; i--) {
        const el = document.createElement('div');
        el.className = 'calendar-day disabled';
        el.innerText = prevLastDate - i + 1;
        grid.appendChild(el);
    }

    // Current Month Days
    for (let i = 1; i <= lastDate; i++) {
        const el = document.createElement('div');
        const fullDate = new Date(year, month, i);

        el.className = 'calendar-day';
        el.innerText = i;

        if (fullDate < today) el.classList.add('disabled');
        if (fullDate.getTime() === today.getTime()) el.classList.add('today');

        if (selectedDates[type] && fullDate.getTime() === selectedDates[type].getTime()) {
            el.classList.add('selected');
        }

        el.onclick = (e) => {
            e.stopPropagation();
            selectedDates[type] = fullDate;
            const textElement = document.getElementById(`text-${type}`);
            if (textElement) {
                textElement.innerText = `${year}.${String(month + 1).padStart(2, '0')}.${String(i).padStart(2, '0')}`;
            }
            closeAllPopovers();
        };

        grid.appendChild(el);
    }

    // Re-initialize Icons if any were added dynamically
    lucide.createIcons();
}

function changeMonth(delta, type) {
    if (window.event) window.event.stopPropagation();
    currentDates[type].setMonth(currentDates[type].getMonth() + delta);
    renderCalendar(type);
}

/**
 * Global Window Events
 */
window.onclick = (e) => {
    if (!e.target.closest('.search-widget')) {
        closeAllPopovers();
    }
};
