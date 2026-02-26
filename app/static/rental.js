document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  initRentalApp();
});

const DESTINATION_REGIONS = [
  { key: 'jp', label: '일본', countryCode: 'JP', cities: ['도쿄', '오사카', '후쿠오카', '삿포로', '오키나와', '나고야', '교토', '고베'] },
  { key: 'sea', label: '동남아', countryCode: 'TH', cities: ['방콕', '푸켓', '치앙마이', '파타야', '다낭', '하노이', '호치민', '싱가포르'] },
  { key: 'cn', label: '홍콩/마카오/중국', countryCode: 'TW', cities: ['타이베이', '타이중', '가오슝', '홍콩', '마카오', '상하이'] },
  { key: 'pac', label: '남태평양', countryCode: 'US', cities: ['하와이', '괌', '사이판'] },
  { key: 'us', label: '미주', countryCode: 'US', cities: ['뉴욕', '로스앤젤레스', '라스베이거스', '샌프란시스코'] },
  { key: 'eu', label: '유럽', countryCode: 'FR', cities: ['파리', '로마', '런던', '바르셀로나'] },
  { key: 'mea', label: '중동/아프리카', countryCode: 'AE', cities: ['두바이', '아부다비', '도하'] },
];

function initRentalApp() {
  const initial = window.__RENTAL_INITIAL__ || {};
  const els = {
    overlay: document.getElementById('overlay'),
    form: document.getElementById('rentalSearchForm'),

    destinationGroup: document.getElementById('destinationInputGroup'),
    destinationPopover: document.getElementById('destinationPopover'),
    destinationDisplay: document.getElementById('destinationDisplay'),
    destinationRegionList: document.getElementById('destinationRegionList'),
    destinationCityGrid: document.getElementById('destinationCityGrid'),
    destinationPanelTitle: document.getElementById('destinationPanelTitle'),
    destinationSearchInput: document.getElementById('destinationSearchInput'),
    destinationSearchBtn: document.getElementById('destinationSearchBtn'),
    destinationSearchMeta: document.getElementById('destinationSearchMeta'),
    destinationSearchList: document.getElementById('destinationSearchList'),
    countryCodeHidden: document.getElementById('countryCodeHidden'),
    cityHintHidden: document.getElementById('cityHintHidden'),

    pickupGroup: document.getElementById('pickupLocInputGroup'),
    dropoffGroup: document.getElementById('dropoffLocInputGroup'),
    pickupPopover: document.getElementById('pickupLocPopover'),
    dropoffPopover: document.getElementById('dropoffLocPopover'),
    startGroup: document.getElementById('startInputGroup'),
    endGroup: document.getElementById('endInputGroup'),
    startPopover: document.getElementById('startDtPopover'),
    endPopover: document.getElementById('endDtPopover'),

    pickupDisplay: document.getElementById('pickupLocDisplay'),
    dropoffDisplay: document.getElementById('dropoffLocDisplay'),
    pickupSearchInput: document.getElementById('pickupLocSearchInput'),
    dropoffSearchInput: document.getElementById('dropoffLocSearchInput'),
    pickupLocationList: document.getElementById('pickupLocationList'),
    dropoffLocationList: document.getElementById('dropoffLocationList'),

    pickupNameHidden: document.getElementById('pickupNameHidden'),
    pickupLatHidden: document.getElementById('pickupLatHidden'),
    pickupLonHidden: document.getElementById('pickupLonHidden'),
    dropoffNameHidden: document.getElementById('dropoffNameHidden'),
    dropoffLatHidden: document.getElementById('dropoffLatHidden'),
    dropoffLonHidden: document.getElementById('dropoffLonHidden'),

    startDate: document.getElementById('startDate'),
    startTime: document.getElementById('startTime'),
    endDate: document.getElementById('endDate'),
    endTime: document.getElementById('endTime'),
    startDtDisplay: document.getElementById('startDtDisplay'),
    endDtDisplay: document.getElementById('endDtDisplay'),
    dtError: document.getElementById('dtError'),
    pickupAtHidden: document.getElementById('pickupAtHidden'),
    dropoffAtHidden: document.getElementById('dropoffAtHidden'),
  };

  const state = {
    pickup: { category: 'all', items: [], timer: null },
    dropoff: { category: 'all', items: [], timer: null },
    destinationRegionKey: 'jp',
    destinationSearching: false,
    destinationSearchItems: [],
    destinationSearchTried: false,
    destinationSearchSeq: 0,
  };

  initDestinationPicker(els, state, initial);
  initDates(els, initial);
  bindPopoverToggles(els);
  bindDateHandlers(els);
  bindLocationSearch(els, state, 'pickup');
  bindLocationSearch(els, state, 'dropoff');
  bindFormSubmit(els);

  if (initial.pickupName) {
    els.pickupDisplay.textContent = initial.pickupName;
    els.pickupSearchInput.value = initial.pickupName;
  }
  if (initial.dropoffName) {
    els.dropoffDisplay.textContent = initial.dropoffName;
    els.dropoffSearchInput.value = initial.dropoffName;
  }
  renderLocationList(els, 'pickup', []);
  renderLocationList(els, 'dropoff', []);
}

function initDestinationPicker(els, state, initial) {
  const cityHint = (initial.cityHint || '').trim();
  const countryCode = String(initial.countryCode || els.countryCodeHidden?.value || 'JP').toUpperCase();
  const region = DESTINATION_REGIONS.find((r) => r.countryCode === countryCode) || DESTINATION_REGIONS[0];
  state.destinationRegionKey = region.key;
  state.destinationSearchItems = [];
  state.destinationSearchTried = false;
  state.destinationSearching = false;

  if (els.countryCodeHidden) els.countryCodeHidden.value = countryCode;
  if (els.cityHintHidden && cityHint) els.cityHintHidden.value = cityHint;
  if (els.destinationDisplay) {
    els.destinationDisplay.textContent = cityHint || '\uC5EC\uD589\uC9C0 \uC120\uD0DD';
  }

  renderDestinationRegions(els, state);
  renderDestinationCities(els, state);
  bindDestinationSearch(els, state);

  if (els.destinationGroup) {
    els.destinationGroup.addEventListener('click', () => {
      if (els.destinationPopover?.classList.contains('active')) return;
      closeAllPopovers(els);
      els.destinationPopover?.classList.add('active');
      els.overlay?.classList.add('active');
    });
  }
}

function renderDestinationRegions(els, state) {
  if (!els.destinationRegionList) return;
  els.destinationRegionList.innerHTML = DESTINATION_REGIONS.map((r) => `
    <button type="button" class="destination-region-btn ${state.destinationRegionKey === r.key ? 'active' : ''}" data-region="${r.key}">
      ${escapeHtml(r.label)}
    </button>
  `).join('');

  els.destinationRegionList.querySelectorAll('.destination-region-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      state.destinationRegionKey = btn.dataset.region || state.destinationRegionKey;
      state.destinationSearchItems = [];
      state.destinationSearchTried = false;
      state.destinationSearching = false;
      if (els.destinationSearchInput) els.destinationSearchInput.value = '';
      renderDestinationRegions(els, state);
      renderDestinationCities(els, state);
    });
  });
}

function renderDestinationCities(els, state) {
  const region = DESTINATION_REGIONS.find((r) => r.key === state.destinationRegionKey) || DESTINATION_REGIONS[0];
  if (els.destinationPanelTitle) {
    els.destinationPanelTitle.textContent = `${region.label} 주요 도시`;
  }
  renderDestinationSearchArea(els, state);
  if (!els.destinationCityGrid) return;
  const hasSearchOverlay = state.destinationSearching || state.destinationSearchTried;
  const showGrid = !hasSearchOverlay;
  if (!showGrid) {
    els.destinationCityGrid.style.display = 'none';
    els.destinationCityGrid.innerHTML = '';
    return;
  }
  els.destinationCityGrid.style.display = '';
  els.destinationCityGrid.innerHTML = region.cities.map((city) => `
    <button type="button" class="destination-city-btn" data-country="${region.countryCode}" data-city="${escapeHtml(city)}">${escapeHtml(city)}</button>
  `).join('');

  els.destinationCityGrid.querySelectorAll('.destination-city-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const countryCode = btn.dataset.country || 'JP';
      const city = btn.dataset.city || '';
      await selectDestinationCity(els, state, { countryCode, city });
    });
  });
}

function bindDestinationSearch(els, state) {
  if (els.destinationSearchInput?.dataset.bound === '1') return;
  if (els.destinationSearchInput) els.destinationSearchInput.dataset.bound = '1';

  els.destinationSearchBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    triggerDestinationSearch(els, state);
  });

  els.destinationSearchInput?.addEventListener('click', (e) => e.stopPropagation());
  els.destinationSearchInput?.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    e.stopPropagation();
    triggerDestinationSearch(els, state);
  });

  els.destinationSearchInput?.addEventListener('input', () => {
    state.destinationSearchItems = [];
    state.destinationSearchTried = false;
    state.destinationSearching = false;
    renderDestinationCities(els, state);
  });
}

function renderDestinationSearchArea(els, state) {
  const listEl = els.destinationSearchList;
  const metaEl = els.destinationSearchMeta;
  if (!listEl || !metaEl) return;

  listEl.classList.remove('has-results', 'has-message');
  listEl.innerHTML = '';

  if (state.destinationSearching) {
    metaEl.textContent = '\uAC80\uC0C9 \uC911...';
    listEl.innerHTML = `<div class="location-empty">\uAC80\uC0C9 \uC911...</div>`;
    listEl.classList.add('has-message');
    return;
  }

  if (!state.destinationSearchTried) {
    metaEl.textContent = '';
    return;
  }

  const items = Array.isArray(state.destinationSearchItems) ? state.destinationSearchItems : [];
  if (!items.length) {
    metaEl.textContent = '\uAC80\uC0C9 \uACB0\uACFC \uC5C6\uC74C';
    listEl.innerHTML = `<div class="location-empty">\uAC80\uC0C9 \uACB0\uACFC\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4. \uC9C1\uC811 \uC785\uB825\uB85C \uC9C4\uD589\uD574\uB3C4 \uB429\uB2C8\uB2E4.</div>`;
    listEl.classList.add('has-message');
    return;
  }

  metaEl.textContent = `\uAC80\uC0C9 \uACB0\uACFC ${items.length}\uAC1C`;
  listEl.innerHTML = items.map((item, idx) => `
    <button type="button" class="location-item destination-result-item" data-idx="${idx}">
      <i data-lucide="map-pin" width="16"></i>
      <div class="loc-info">
        <span class="loc-name">${escapeHtml(item.name || '')}</span>
        <span class="loc-sub">${escapeHtml(item.sub || '')}</span>
      </div>
    </button>
  `).join('');
  listEl.classList.add('has-results');
  if (window.lucide) lucide.createIcons();

  listEl.querySelectorAll('.destination-result-item').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const idx = Number(btn.dataset.idx);
      const item = items[idx];
      if (!item) return;
      await selectDestinationCity(els, state, {
        city: item.name || '',
        countryCode: getDestinationRegionCountryCode(state),
      });
    });
  });
}

function getDestinationRegionCountryCode(state) {
  const region = DESTINATION_REGIONS.find((r) => r.key === state.destinationRegionKey) || DESTINATION_REGIONS[0];
  return region?.countryCode || 'JP';
}

async function triggerDestinationSearch(els, state) {
  const q = (els.destinationSearchInput?.value || '').trim();
  if (!q) {
    state.destinationSearching = false;
    state.destinationSearchTried = false;
    state.destinationSearchItems = [];
    renderDestinationCities(els, state);
    return;
  }

  const seq = ++state.destinationSearchSeq;
  state.destinationSearching = true;
  state.destinationSearchTried = true;
  state.destinationSearchItems = [];
  renderDestinationCities(els, state);

  try {
    const countryCode = getDestinationRegionCountryCode(state);
    const searchQ = normalizeDestinationKeyword(q);
    const url = `/api/rental/location-search?q=${encodeURIComponent(searchQ)}&category=city&country_code=${encodeURIComponent(countryCode)}`;
    const resp = await fetch(url, { headers: { Accept: 'application/json' } });
    const data = await resp.json();
    if (seq !== state.destinationSearchSeq) return;
    const items = Array.isArray(data.items) ? data.items : [];
    const dedup = [];
    const seen = new Set();
    for (const item of items) {
      const name = String(item?.name || '').trim();
      if (!name) continue;
      if (seen.has(name)) continue;
      seen.add(name);
      dedup.push(item);
    }
    state.destinationSearchItems = dedup;
  } catch (_e) {
    if (seq !== state.destinationSearchSeq) return;
    state.destinationSearchItems = [];
  } finally {
    if (seq !== state.destinationSearchSeq) return;
    state.destinationSearching = false;
    renderDestinationCities(els, state);
  }
}

function normalizeDestinationKeyword(q) {
  const s = String(q || '').trim();
  if (!s) return s;

  const aliasMap = new Map([
    ['훗카이도', '삿포로'],
    ['홋카이도', '삿포로'],
    ['북해도', '삿포로'],
    ['벳부', '벳푸'],
    ['벳푸', '벳푸'],
    ['뱃부', '벳푸'],
    ['뱃푸', '벳푸'],
  ]);

  return aliasMap.get(s) || s;
}

async function selectDestinationCity(els, state, payload) {
  const region = DESTINATION_REGIONS.find((r) => r.key === state.destinationRegionKey) || DESTINATION_REGIONS[0];
  const countryCode = payload?.countryCode || region.countryCode || 'JP';
  const city = String(payload?.city || '').trim();

  if (els.countryCodeHidden) els.countryCodeHidden.value = countryCode;
  if (els.cityHintHidden) els.cityHintHidden.value = city;
  if (els.destinationDisplay) els.destinationDisplay.textContent = city || '\uC5EC\uD589\uC9C0 \uC120\uD0DD';
  if (els.destinationSearchInput) els.destinationSearchInput.value = city;

  state.destinationSearchItems = [];
  state.destinationSearchTried = false;
  state.destinationSearching = false;

  resetSelectedLocations(els);
  if (els.pickupSearchInput) els.pickupSearchInput.value = city;
  if (els.dropoffSearchInput) els.dropoffSearchInput.value = city;
  closeAllPopovers(els);

  if (!city) return;
  await triggerLocationSearch(els, state, 'pickup', city);
  if (els.pickupPopover) {
    els.pickupPopover.classList.add('active');
    els.overlay?.classList.add('active');
  }
}

function closeAllPopovers(els) {
  document.querySelectorAll('.popover-container').forEach((p) => p.classList.remove('active'));
  els.overlay?.classList.remove('active');
}

function initDates(els, initial) {
  const now = new Date();
  const startDefault = new Date(now.getTime() + 3600 * 1000);
  const endDefault = new Date(startDefault.getTime() + 3 * 86400 * 1000);
  const s = parseLocalDateTime(initial.pickupAt) || startDefault;
  const e = parseLocalDateTime(initial.dropoffAt) || endDefault;
  const minDate = formatDate(now);
  els.startDate.min = minDate;
  els.endDate.min = minDate;
  els.startDate.value = formatDate(s);
  els.startTime.value = formatTime(s);
  els.endDate.value = formatDate(e);
  els.endTime.value = formatTime(e);
  syncDateDisplays(els);
}

function bindPopoverToggles(els) {
  const pairs = [
    [els.pickupGroup, els.pickupPopover],
    [els.dropoffGroup, els.dropoffPopover],
    [els.startGroup, els.startPopover],
    [els.endGroup, els.endPopover],
  ];

  els.overlay?.addEventListener('click', () => closeAllPopovers(els));
  document.querySelectorAll('.popover-container').forEach((p) => p.addEventListener('click', (e) => e.stopPropagation()));
  document.querySelectorAll('.btn-confirm').forEach((b) => b.addEventListener('click', () => closeAllPopovers(els)));

  pairs.forEach(([group, pop]) => {
    if (!group || !pop) return;
    group.addEventListener('click', () => {
      const active = pop.classList.contains('active');
      closeAllPopovers(els);
      if (!active) {
        pop.classList.add('active');
        els.overlay?.classList.add('active');
      }
    });
  });
}

function bindDateHandlers(els) {
  ['startDate', 'startTime', 'endDate', 'endTime'].forEach((id) => {
    els[id].addEventListener('change', () => {
      validateDates(els);
      syncDateDisplays(els);
    });
  });
}

function bindLocationSearch(els, state, target) {
  const searchInput = target === 'pickup' ? els.pickupSearchInput : els.dropoffSearchInput;
  const popover = target === 'pickup' ? els.pickupPopover : els.dropoffPopover;
  const categoryButtons = Array.from(popover.querySelectorAll('.sidebar-btn'));

  categoryButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      categoryButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state[target].category = btn.dataset.category || 'all';
      triggerLocationSearch(els, state, target, searchInput.value.trim());
    });
  });

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim();
    clearTimeout(state[target].timer);
    state[target].timer = setTimeout(() => triggerLocationSearch(els, state, target, q), 220);
  });

  const group = target === 'pickup' ? els.pickupGroup : els.dropoffGroup;
  group.addEventListener('click', () => {
    const fallbackQ = searchInput.value.trim()
      || (target === 'dropoff' ? (els.pickupNameHidden.value || '') : '')
      || (els.cityHintHidden?.value || '')
      || (els.destinationDisplay?.textContent || '');
    if (fallbackQ) {
      searchInput.value = fallbackQ;
      triggerLocationSearch(els, state, target, fallbackQ);
    }
  });
}

async function triggerLocationSearch(els, state, target, q) {
  renderLocationList(els, target, []);
  if (!q) return;
  try {
    const category = state[target].category || 'all';
    const countryCode = els.countryCodeHidden?.value || 'JP';
    const url = `/api/rental/location-search?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}&country_code=${encodeURIComponent(countryCode)}`;
    const resp = await fetch(url, { headers: { Accept: 'application/json' } });
    const data = await resp.json();
    const items = Array.isArray(data.items) ? data.items : [];
    state[target].items = items;
    renderLocationList(els, target, items);
  } catch (_e) {
    renderLocationList(els, target, [], '지역 검색 중 오류가 발생했습니다.');
  }
}

function renderLocationList(els, target, items, errorMsg) {
  const listEl = target === 'pickup' ? els.pickupLocationList : els.dropoffLocationList;
  if (!listEl) return;
  if (errorMsg) {
    listEl.innerHTML = `<div class="location-empty">${escapeHtml(errorMsg)}</div>`;
    return;
  }
  if (!items.length) {
    const hint = els.cityHintHidden?.value || '도시/공항/역';
    listEl.innerHTML = `<div class="location-empty">검색 결과가 없습니다. 예: ${escapeHtml(hint)}</div>`;
    return;
  }

  const iconByCategory = { airport: 'plane', station: 'train', city: 'map-pin', all: 'map-pin' };
  listEl.innerHTML = items.map((item, idx) => `
    <button type="button" class="location-item" data-idx="${idx}">
      <i data-lucide="${iconByCategory[item.category] || 'map-pin'}" width="16"></i>
      <div class="loc-info">
        <span class="loc-name">${escapeHtml(item.name || '')}</span>
        <span class="loc-sub">${escapeHtml(item.sub || '')}</span>
      </div>
    </button>
  `).join('');
  if (window.lucide) lucide.createIcons();
  listEl.querySelectorAll('.location-item').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.dataset.idx);
      selectLocation(els, target, items[idx]);
    });
  });
}

function selectLocation(els, target, item) {
  if (!item) return;
  const isPickup = target === 'pickup';
  const display = isPickup ? els.pickupDisplay : els.dropoffDisplay;
  const nameHidden = isPickup ? els.pickupNameHidden : els.dropoffNameHidden;
  const latHidden = isPickup ? els.pickupLatHidden : els.dropoffLatHidden;
  const lonHidden = isPickup ? els.pickupLonHidden : els.dropoffLonHidden;

  display.textContent = item.name || '장소 선택';
  nameHidden.value = item.name || '';
  latHidden.value = item.lat ?? '';
  lonHidden.value = item.lon ?? '';

  if (isPickup && !els.dropoffNameHidden.value) {
    els.dropoffDisplay.textContent = item.name || '장소 선택';
    els.dropoffNameHidden.value = item.name || '';
    els.dropoffLatHidden.value = item.lat ?? '';
    els.dropoffLonHidden.value = item.lon ?? '';
  }
  closeAllPopovers(els);
}

function resetSelectedLocations(els) {
  els.pickupDisplay.textContent = '대여 장소를 선택하세요';
  els.dropoffDisplay.textContent = '반납 장소를 선택하세요 (기본: 대여 장소)';
  els.pickupNameHidden.value = '';
  els.pickupLatHidden.value = '';
  els.pickupLonHidden.value = '';
  els.dropoffNameHidden.value = '';
  els.dropoffLatHidden.value = '';
  els.dropoffLonHidden.value = '';
}

function bindFormSubmit(els) {
  els.form.addEventListener('submit', (e) => {
    syncDateDisplays(els);
    if (!validateDates(els)) {
      e.preventDefault();
      return;
    }
    if (!els.pickupLatHidden.value || !els.pickupLonHidden.value) {
      e.preventDefault();
      alert('대여 장소를 검색 후 선택해 주세요.');
      return;
    }
    if (!els.dropoffLatHidden.value || !els.dropoffLonHidden.value) {
      els.dropoffNameHidden.value = els.pickupNameHidden.value;
      els.dropoffLatHidden.value = els.pickupLatHidden.value;
      els.dropoffLonHidden.value = els.pickupLonHidden.value;
    }
  });
}

function syncDateDisplays(els) {
  const startVal = `${els.startDate.value || ''} ${els.startTime.value || ''}`.trim();
  const endVal = `${els.endDate.value || ''} ${els.endTime.value || ''}`.trim();
  els.startDtDisplay.textContent = startVal || '날짜와 시간을 선택';
  els.endDtDisplay.textContent = endVal || '날짜와 시간을 선택';
  els.pickupAtHidden.value = startVal;
  els.dropoffAtHidden.value = endVal;
}

function validateDates(els) {
  const s = parseLocalDateTime(`${els.startDate.value} ${els.startTime.value}`);
  const e = parseLocalDateTime(`${els.endDate.value} ${els.endTime.value}`);
  if (!s || !e) return true;
  if (e <= s) {
    els.dtError.style.display = 'block';
    return false;
  }
  els.dtError.style.display = 'none';
  return true;
}

function parseLocalDateTime(text) {
  if (!text) return null;
  const d = new Date(String(text).trim().replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatTime(d) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
