document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  initRentalApp();
  initRentalSavedUi();
});

const DESTINATION_REGIONS = [
  { key: 'jp', label: '일본', countryCode: 'JP', cities: ['도쿄', '오사카', '후쿠오카', '삿포로', '오키나와', '나고야', '교토', '고베'] },
  { key: 'sea', label: '동남아', countryCode: 'TH', cities: ['방콕', '푸켓', '치앙마이', '파타야', '다낭', '하노이', '호치민', '싱가포르'] },
  { key: 'cn', label: '홍콩/마카오/중국', countryCode: 'CN', cities: ['타이베이', '타이중', '가오슝', '홍콩', '마카오', '상하이'] },
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
    const localizedPickup = localizeLocationName(initial.pickupName);
    els.pickupDisplay.textContent = localizedPickup;
    els.pickupSearchInput.value = localizedPickup;
  }
  if (initial.dropoffName) {
    const localizedDropoff = localizeLocationName(initial.dropoffName);
    els.dropoffDisplay.textContent = localizedDropoff;
    els.dropoffSearchInput.value = localizedDropoff;
  }
  renderLocationList(els, 'pickup', []);
  renderLocationList(els, 'dropoff', []);

  // Signal that the main rental UI bindings are healthy.
  window.__RENTAL_MAIN_BOUND = true;
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
    <button type="button" class="destination-city-btn" data-country="${inferDestinationCountryCode(city, region.countryCode)}" data-city="${escapeHtml(city)}">${escapeHtml(city)}</button>
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
        countryCode: (item.country_code || inferDestinationCountryCode(item.name || '', getDestinationRegionCountryCode(state))),
      });
    });
  });
}

function getDestinationRegionCountryCode(state) {
  const region = DESTINATION_REGIONS.find((r) => r.key === state.destinationRegionKey) || DESTINATION_REGIONS[0];
  // Mixed-country regions should not hard-lock country filter during search.
  const mixedRegionKeys = new Set(['sea', 'cn', 'eu', 'mea']);
  if (mixedRegionKeys.has(String(region?.key || ''))) return '';
  return region?.countryCode || 'JP';
}

async function fetchRentalLocations({ q, category = 'all', countryCode = '' }) {
  const cc = String(countryCode || '').trim().toUpperCase();
  const base = `/api/rental/location-search?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`;
  const url = cc ? `${base}&country_code=${encodeURIComponent(cc)}` : base;
  const resp = await fetch(url, { headers: { Accept: 'application/json' } });
  const data = await resp.json();
  return Array.isArray(data?.items) ? data.items : [];
}

function inferDestinationCountryCode(cityName, fallbackCode = 'JP') {
  const n = String(cityName || '').trim().toLowerCase();
  const map = {
    '도쿄': 'JP',
    'tokyo': 'JP',
    '오사카': 'JP',
    'osaka': 'JP',
    '후쿠오카': 'JP',
    'fukuoka': 'JP',
    '삿포로': 'JP',
    'sapporo': 'JP',
    '오키나와': 'JP',
    'okinawa': 'JP',
    '나고야': 'JP',
    'nagoya': 'JP',
    '교토': 'JP',
    'kyoto': 'JP',
    '고베': 'JP',
    'kobe': 'JP',
    '방콕': 'TH',
    'bangkok': 'TH',
    '푸켓': 'TH',
    'phuket': 'TH',
    '치앙마이': 'TH',
    'chiang mai': 'TH',
    '파타야': 'TH',
    'pattaya': 'TH',
    '다낭': 'VN',
    'da nang': 'VN',
    'danang': 'VN',
    '하노이': 'VN',
    'hanoi': 'VN',
    '호치민': 'VN',
    'ho chi minh': 'VN',
    'hochiminh': 'VN',
    '싱가포르': 'SG',
    'singapore': 'SG',
    '홍콩': 'HK',
    'hong kong': 'HK',
    'hongkong': 'HK',
    'hkg': 'HK',
    '마카오': 'MO',
    'macau': 'MO',
    'macao': 'MO',
    'mfm': 'MO',
    '상하이': 'CN',
    'shanghai': 'CN',
    '베이징': 'CN',
    'beijing': 'CN',
    '광저우': 'CN',
    'guangzhou': 'CN',
    '칭다오': 'CN',
    'qingdao': 'CN',
    '타이베이': 'TW',
    'taipei': 'TW',
    '타이중': 'TW',
    'taichung': 'TW',
    '가오슝': 'TW',
    'kaohsiung': 'TW',
    '하와이': 'US',
    'hawaii': 'US',
    '괌': 'US',
    'guam': 'US',
    '사이판': 'US',
    'saipan': 'US',
    '뉴욕': 'US',
    'new york': 'US',
    '로스앤젤레스': 'US',
    'los angeles': 'US',
    '라스베이거스': 'US',
    'las vegas': 'US',
    '샌프란시스코': 'US',
    'san francisco': 'US',
    '파리': 'FR',
    'paris': 'FR',
    '로마': 'IT',
    'rome': 'IT',
    '런던': 'GB',
    'london': 'GB',
    '바르셀로나': 'ES',
    'barcelona': 'ES',
    '두바이': 'AE',
    'dubai': 'AE',
    '아부다비': 'AE',
    'abu dhabi': 'AE',
    '도하': 'QA',
    'doha': 'QA',
  };
  const fallback = String(fallbackCode || '').trim().toUpperCase();
  return map[n] || (/^[A-Z]{2}$/.test(fallback) ? fallback : 'US');
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
    let items = await fetchRentalLocations({ q: searchQ, category: 'city', countryCode });
    if (!items.length) {
      items = await fetchRentalLocations({ q: searchQ, category: 'city', countryCode: '' });
    }
    if (seq !== state.destinationSearchSeq) return;
    const dedup = [];
    const seen = new Set();
    for (const item of items) {
      const name = String(item?.name || '').trim();
      if (!name) continue;
      if (seen.has(name)) continue;
      seen.add(name);
      dedup.push(item);
    }
    if (!dedup.length) {
      dedup.push({
        name: q,
        sub: '입력한 도시로 계속 진행',
        category: 'city',
        country_code: inferDestinationCountryCode(q, countryCode || els.countryCodeHidden?.value || 'US'),
      });
    }
    state.destinationSearchItems = dedup;
  } catch (_e) {
    if (seq !== state.destinationSearchSeq) return;
    state.destinationSearchItems = [{
      name: q,
      sub: '입력한 도시로 계속 진행',
      category: 'city',
      country_code: inferDestinationCountryCode(q, els.countryCodeHidden?.value || 'US'),
    }];
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
    ['북해도', '삿포로'],
    ['beppu', '벳푸'],
    ['벳부', '벳푸'],
    ['벳푸', '벳푸'],
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
  // 목적지 선택 시에는 검색 입력창만 비우고, 추천 목록은 자동 조회로 유도
  if (els.pickupSearchInput) els.pickupSearchInput.value = '';
  if (els.dropoffSearchInput) els.dropoffSearchInput.value = '';
  closeAllPopovers(els);

  if (!city) return;
  await triggerLocationSearch(els, state, 'pickup', city);
  await triggerLocationSearch(els, state, 'dropoff', city);
  // Auto-apply first suggested locations so stale previous airport does not remain.
  const pickupFirst = Array.isArray(state.pickup?.items) && state.pickup.items.length ? state.pickup.items[0] : null;
  const dropoffFirst = Array.isArray(state.dropoff?.items) && state.dropoff.items.length ? state.dropoff.items[0] : null;
  const cityFallback = fallbackLocationForCity(city, countryCode);
  if (pickupFirst) {
    selectLocation(els, 'pickup', pickupFirst, { manual: false, syncDropoff: true });
  } else if (cityFallback) {
    selectLocation(els, 'pickup', cityFallback, { manual: false, syncDropoff: true });
  }
  if (dropoffFirst) {
    selectLocation(els, 'dropoff', dropoffFirst, { manual: false });
  } else if (cityFallback) {
    selectLocation(els, 'dropoff', cityFallback, { manual: false });
  }
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
  const startDefault = new Date(now);
  startDefault.setHours(10, 0, 0, 0);
  const endDefault = new Date(startDefault);
  endDefault.setDate(endDefault.getDate() + 1);
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
    if (!els[id]) return;
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
      const q = getLocationSearchQuery(els, target, searchInput.value.trim());
      triggerLocationSearch(els, state, target, q);
    });
  });

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim();
    clearTimeout(state[target].timer);
    state[target].timer = setTimeout(() => triggerLocationSearch(els, state, target, q), 220);
  });

  const group = target === 'pickup' ? els.pickupGroup : els.dropoffGroup;
  group.addEventListener('click', () => {
    const fallbackQ = getLocationSearchQuery(els, target, searchInput.value.trim());
    if (fallbackQ) {
      triggerLocationSearch(els, state, target, fallbackQ);
    }
  });
}

function getLocationSearchQuery(els, target, typed) {
  return String(typed || '').trim()
    || (target === 'dropoff' ? String(els.pickupNameHidden?.value || '').trim() : '')
    || String(els.cityHintHidden?.value || '').trim()
    || String(els.destinationDisplay?.textContent || '').trim();
}

async function triggerLocationSearch(els, state, target, q) {
  renderLocationList(els, target, []);
  if (!q) return;
  try {
    const category = state[target].category || 'all';
    const countryCode = els.countryCodeHidden?.value || 'JP';
    const variants = buildLocationQueryVariants(q);
    let items = [];
    for (const keyword of variants) {
      items = await fetchRentalLocations({ q: keyword, category, countryCode });
      if (items.length) break;
      items = await fetchRentalLocations({ q: keyword, category, countryCode: '' });
      if (items.length) break;
    }
    if (!items.length && category !== 'all') {
      for (const keyword of variants) {
        items = await fetchRentalLocations({ q: keyword, category: 'all', countryCode });
        if (items.length) break;
        items = await fetchRentalLocations({ q: keyword, category: 'all', countryCode: '' });
        if (items.length) break;
      }
    }
    state[target].items = items;
    renderLocationList(els, target, items);
  } catch (_e) {
    renderLocationList(els, target, [], '지역 검색 중 오류가 발생했습니다.');
  }
}

function buildLocationQueryVariants(q) {
  const src = String(q || '').trim();
  if (!src) return [];
  const out = [];
  const push = (v) => {
    const s = String(v || '').trim();
    if (!s) return;
    if (!out.includes(s)) out.push(s);
  };

  push(src);
  const map = new Map([
    ['도쿄', ['Tokyo', 'Narita Airport', 'Haneda Airport', 'NRT', 'HND']],
    ['오키나와', ['Okinawa', 'Naha Airport', 'OKA']],
    ['나고야', ['Nagoya', 'NGO', 'Chubu Centrair Airport']],
    ['교토', ['Kyoto', 'KIX', 'Osaka']],
    ['고베', ['Kobe', 'UKB', 'Osaka']],
    ['방콕', ['Bangkok', 'Suvarnabhumi Airport', 'BKK']],
    ['푸켓', ['Phuket', 'HKT', 'Phuket Airport']],
    ['치앙마이', ['Chiang Mai', 'CNX', 'Chiang Mai Airport']],
    ['파타야', ['Pattaya', 'UTP', 'U-Tapao Airport']],
    ['홍콩', ['Hong Kong', 'Hong Kong Intl Airport', 'HKG']],
    ['두바이', ['Dubai', 'Dubai Airport', 'DXB']],
    ['오사카', ['Osaka', 'Kansai Airport', 'KIX']],
    ['삿포로', ['Sapporo', 'CTS']],
    ['후쿠오카', ['Fukuoka', 'FUK']],
    ['다낭', ['Da Nang', 'DAD', 'Da Nang Airport']],
    ['하노이', ['Hanoi', 'HAN', 'Noi Bai Airport']],
    ['호치민', ['Ho Chi Minh', 'SGN', 'Tan Son Nhat Airport']],
    ['싱가포르', ['Singapore', 'Changi Airport', 'SIN']],
    ['뉴욕', ['New York', 'JFK Airport', 'JFK', 'EWR', 'LGA']],
    ['로스앤젤레스', ['Los Angeles', 'LAX', 'LAX Airport']],
    ['라스베이거스', ['Las Vegas', 'LAS', 'Harry Reid Airport']],
    ['샌프란시스코', ['San Francisco', 'SFO', 'SFO Airport']],
    ['하와이', ['Honolulu', 'HNL', 'Daniel K Inouye Airport']],
    ['괌', ['Guam', 'GUM', 'Antonio B. Won Pat Airport']],
    ['사이판', ['Saipan', 'SPN', 'Saipan Airport']],
    ['런던', ['London', 'Heathrow Airport', 'LHR']],
    ['파리', ['Paris', 'CDG Airport', 'CDG']],
    ['로마', ['Rome', 'Fiumicino Airport', 'FCO']],
    ['바르셀로나', ['Barcelona', 'BCN', 'Barcelona Airport']],
    ['아부다비', ['Abu Dhabi', 'AUH', 'Abu Dhabi Airport']],
    ['도하', ['Doha', 'DOH', 'Hamad International Airport']],
    ['타이베이', ['Taipei', 'Taoyuan Airport', 'TPE']],
    ['타이중', ['Taichung', 'RMQ', 'Taichung Airport']],
    ['가오슝', ['Kaohsiung', 'KHH', 'Kaohsiung Airport']],
    ['상하이', ['Shanghai', 'PVG', 'SHA']],
    ['마카오', ['Macau', 'MFM', 'Macau Airport']],
    ['시드니', ['Sydney', 'Sydney Airport', 'SYD']],
    ['서울', ['Seoul', 'Incheon Airport', 'ICN', 'GMP']],
    ['부산', ['Busan', 'Gimhae Airport', 'PUS']],
  ]);
  const alias = map.get(src);
  if (Array.isArray(alias)) alias.forEach(push);
  return out;
}

function fallbackLocationForCity(city, countryCode = 'US') {
  const n = String(city || '').trim().toLowerCase();
  if (!n) return null;
  const map = {
    '도쿄': { name: 'Tokyo', lat: 35.6762, lon: 139.6503, sub: 'Japan', cc: 'JP' },
    '오사카': { name: 'Osaka', lat: 34.6937, lon: 135.5023, sub: 'Japan', cc: 'JP' },
    '후쿠오카': { name: 'Fukuoka', lat: 33.5902, lon: 130.4017, sub: 'Japan', cc: 'JP' },
    '삿포로': { name: 'Sapporo', lat: 43.0618, lon: 141.3545, sub: 'Japan', cc: 'JP' },
    '나고야': { name: 'Nagoya', lat: 35.1815, lon: 136.9066, sub: 'Japan', cc: 'JP' },
    '교토': { name: 'Kyoto', lat: 35.0116, lon: 135.7681, sub: 'Japan', cc: 'JP' },
    '고베': { name: 'Kobe', lat: 34.6901, lon: 135.1955, sub: 'Japan', cc: 'JP' },
    '방콕': { name: 'Bangkok', lat: 13.7563, lon: 100.5018, sub: 'Thailand', cc: 'TH' },
    '다낭': { name: 'Da Nang', lat: 16.0544, lon: 108.2022, sub: 'Vietnam', cc: 'VN' },
    '하노이': { name: 'Hanoi', lat: 21.0278, lon: 105.8342, sub: 'Vietnam', cc: 'VN' },
    '호치민': { name: 'Ho Chi Minh City', lat: 10.8231, lon: 106.6297, sub: 'Vietnam', cc: 'VN' },
    '싱가포르': { name: 'Singapore', lat: 1.3521, lon: 103.8198, sub: 'Singapore', cc: 'SG' },
    '홍콩': { name: 'Hong Kong', lat: 22.3193, lon: 114.1694, sub: 'Hong Kong', cc: 'HK' },
    '마카오': { name: 'Macau', lat: 22.1987, lon: 113.5439, sub: 'Macau', cc: 'MO' },
    '상하이': { name: 'Shanghai', lat: 31.2304, lon: 121.4737, sub: 'China', cc: 'CN' },
    '타이베이': { name: 'Taipei', lat: 25.0330, lon: 121.5654, sub: 'Taiwan', cc: 'TW' },
    '런던': { name: 'London', lat: 51.5072, lon: -0.1276, sub: 'United Kingdom', cc: 'GB' },
    '파리': { name: 'Paris', lat: 48.8566, lon: 2.3522, sub: 'France', cc: 'FR' },
    '로마': { name: 'Rome', lat: 41.9028, lon: 12.4964, sub: 'Italy', cc: 'IT' },
    '바르셀로나': { name: 'Barcelona', lat: 41.3874, lon: 2.1686, sub: 'Spain', cc: 'ES' },
    '뉴욕': { name: 'New York', lat: 40.7128, lon: -74.0060, sub: 'United States', cc: 'US' },
    '로스앤젤레스': { name: 'Los Angeles', lat: 34.0522, lon: -118.2437, sub: 'United States', cc: 'US' },
    '라스베이거스': { name: 'Las Vegas', lat: 36.1699, lon: -115.1398, sub: 'United States', cc: 'US' },
    '샌프란시스코': { name: 'San Francisco', lat: 37.7749, lon: -122.4194, sub: 'United States', cc: 'US' },
    '두바이': { name: 'Dubai', lat: 25.2048, lon: 55.2708, sub: 'United Arab Emirates', cc: 'AE' },
    '아부다비': { name: 'Abu Dhabi', lat: 24.4539, lon: 54.3773, sub: 'United Arab Emirates', cc: 'AE' },
    '도하': { name: 'Doha', lat: 25.2854, lon: 51.5310, sub: 'Qatar', cc: 'QA' },
  };
  const row = map[n];
  if (row) {
    return {
      name: row.name,
      sub: row.sub,
      lat: row.lat,
      lon: row.lon,
      category: 'city',
      country_code: row.cc,
    };
  }
  return {
    name: String(city || '').trim(),
    sub: 'Selected destination city',
    lat: ({ JP: 35.6762, KR: 37.5665, US: 40.7128, FR: 48.8566, GB: 51.5072, IT: 41.9028, ES: 41.3874, TH: 13.7563, VN: 21.0278, SG: 1.3521, HK: 22.3193, MO: 22.1987, CN: 31.2304, TW: 25.0330, AE: 25.2048, QA: 25.2854 }[String(inferDestinationCountryCode(city, countryCode)).toUpperCase()] ?? 35.6762),
    lon: ({ JP: 139.6503, KR: 126.9780, US: -74.0060, FR: 2.3522, GB: -0.1276, IT: 12.4964, ES: 2.1686, TH: 100.5018, VN: 105.8342, SG: 103.8198, HK: 114.1694, MO: 113.5439, CN: 121.4737, TW: 121.5654, AE: 55.2708, QA: 51.5310 }[String(inferDestinationCountryCode(city, countryCode)).toUpperCase()] ?? 139.6503),
    category: 'city',
    country_code: inferDestinationCountryCode(city, countryCode),
  };
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
        <span class="loc-name">${escapeHtml(localizeLocationName(item.name || ''))}</span>
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

function selectLocation(els, target, item, options = {}) {
  if (!item) return;
  const manual = options.manual !== false;
  const syncDropoff = options.syncDropoff === true;
  const isPickup = target === 'pickup';
  const display = isPickup ? els.pickupDisplay : els.dropoffDisplay;
  const nameHidden = isPickup ? els.pickupNameHidden : els.dropoffNameHidden;
  const latHidden = isPickup ? els.pickupLatHidden : els.dropoffLatHidden;
  const lonHidden = isPickup ? els.pickupLonHidden : els.dropoffLonHidden;

  const localizedName = localizeLocationName(item.name || '');
  display.textContent = localizedName || '장소 선택';
  nameHidden.value = localizedName || '';
  latHidden.value = item.lat ?? '';
  lonHidden.value = item.lon ?? '';

  if (!isPickup) {
    if (manual) window.__RENTAL_DROPOFF_MANUAL__ = true;
  }

  const dropoffManual = Boolean(window.__RENTAL_DROPOFF_MANUAL__);
  // Keep classic UX: dropoff follows pickup until user explicitly chooses dropoff.
  if (isPickup && (!dropoffManual || syncDropoff)) {
    els.dropoffDisplay.textContent = localizedName || '장소 선택';
    els.dropoffNameHidden.value = localizedName || '';
    els.dropoffLatHidden.value = item.lat ?? '';
    els.dropoffLonHidden.value = item.lon ?? '';
    if (syncDropoff) window.__RENTAL_DROPOFF_MANUAL__ = false;
  }
  closeAllPopovers(els);
}

function localizeLocationName(name) {
  const src = String(name || '').trim();
  if (!src) return '';

  const iataMatch = src.match(/\(([A-Z]{3})\)/);
  const iata = iataMatch ? iataMatch[1] : '';

  const aliases = new Map([
    ['narita airport', '나리타 공항'],
    ['haneda airport', '하네다 공항'],
    ['incheon intl airport', '인천국제공항'],
    ['incheon airport', '인천국제공항'],
    ['gimhae airport', '김해국제공항'],
    ['kansai airport', '간사이국제공항'],
    ['suvarnabhumi airport', '수완나품공항'],
    ['hong kong intl airport', '홍콩국제공항'],
    ['taoyuan airport', '타오위안공항'],
    ['sydney airport', '시드니공항'],
    ['jfk airport', 'JFK 공항'],
    ['lax airport', 'LAX 공항'],
    ['heathrow airport', '히드로공항'],
    ['fiumicino airport', '피우미치노공항'],
    ['dubai airport', '두바이공항'],
    ['tokyo', '도쿄'],
    ['osaka', '오사카'],
    ['sapporo', '삿포로'],
    ['new york', '뉴욕'],
    ['los angeles', '로스앤젤레스'],
    ['london', '런던'],
    ['paris', '파리'],
    ['rome', '로마'],
    ['dubai', '두바이'],
    ['bangkok', '방콕'],
    ['singapore', '싱가포르'],
    ['hong kong', '홍콩'],
    ['taipei', '타이베이'],
    ['sydney', '시드니'],
    ['seoul', '서울'],
    ['busan', '부산'],
  ]);

  const lower = src.toLowerCase();
  let localized = '';
  for (const [key, value] of aliases.entries()) {
    if (lower === key || lower.startsWith(`${key} (`)) {
      localized = value;
      break;
    }
  }
  if (!localized) return src;
  if (iata) return `${localized} (${iata})`;
  return localized;
}

function resetSelectedLocations(els) {
  window.__RENTAL_DROPOFF_MANUAL__ = false;
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

let rentalSavedState = { cart: [], wishlist: [] };
let rentalSavedTab = 'cart';
let rentalAlertState = [];
let rentalAuthState = { checkedAt: 0, loggedIn: false };

function rentalKeyFromPayload(payload) {
  const p = payload || {};
  return [
    String(p.name || '').trim().toLowerCase(),
    String(p.supplier || '').trim().toLowerCase(),
    String(p.price ?? '').trim(),
    String(p.currency || '').trim().toLowerCase(),
    String(p.pickup_at || '').trim(),
    String(p.dropoff_at || '').trim(),
  ].join('|');
}

function rentalSavedRowKey(row) {
  if (!row) return '';
  const payload = row.payload && typeof row.payload === 'object' ? row.payload : {};
  if (String(row.item_type || '').toLowerCase() === 'rental') return rentalKeyFromPayload(payload);
  return `${String(row.name || '').toLowerCase()}|${String(row.meta || '').toLowerCase()}`;
}

function parseRentalPayload(attrValue) {
  try {
    const row = JSON.parse(attrValue || '{}');
    return row && typeof row === 'object' ? row : null;
  } catch (_e) {
    return null;
  }
}

function buildRentalSavedPayload(raw, listType) {
  const payload = raw && typeof raw === 'object' ? raw : null;
  if (!payload || !payload.name) return null;
  const metaParts = [];
  if (payload.supplier) metaParts.push(String(payload.supplier));
  if (payload.pickup_name) metaParts.push(`픽업 ${payload.pickup_name}`);
  if (payload.dropoff_name) metaParts.push(`반납 ${payload.dropoff_name}`);
  if (payload.pickup_at) metaParts.push(String(payload.pickup_at).slice(0, 10));
  return {
    list_type: listType,
    item_type: 'rental',
    name: String(payload.name || '').trim(),
    meta: metaParts.join(' | '),
    source: 'rental',
    payload,
  };
}

async function rentalSavedApi(path = '/api/saved-items', options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  if (res.status === 401) {
    const e = new Error('LOGIN_REQUIRED');
    e.code = 'LOGIN_REQUIRED';
    throw e;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data;
}

async function loadRentalSavedState() {
  try {
    const data = await rentalSavedApi('/api/saved-items', { method: 'GET', headers: {} });
    rentalSavedState = {
      cart: Array.isArray(data?.cart) ? data.cart : [],
      wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
    };
  } catch (e) {
    if (e?.code !== 'LOGIN_REQUIRED') console.warn('rental saved-items load failed', e);
    rentalSavedState = { cart: [], wishlist: [] };
  }
}

async function loadRentalAlerts() {
  try {
    const res = await fetch('/api/group-buy/join-requests/inbox', { credentials: 'include' });
    if (res.status === 401) {
      rentalAlertState = [];
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    rentalAlertState = Array.isArray(data) ? data : [];
  } catch (_e) {
    rentalAlertState = [];
  }
}

function setRentalSavedDrawer(open) {
  const drawer = document.getElementById('rentalSavedDrawer');
  const fab = document.getElementById('rentalSavedFab');
  if (!drawer || !fab) return;
  drawer.classList.toggle('is-open', !!open);
  drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
  fab.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function updateRentalCardButtons() {
  const wishRows = Array.isArray(rentalSavedState.wishlist) ? rentalSavedState.wishlist : [];
  const cartRows = Array.isArray(rentalSavedState.cart) ? rentalSavedState.cart : [];
  const wishKeys = new Set(wishRows.map((row) => rentalSavedRowKey(row)));
  const cartKeys = new Set(cartRows.map((row) => rentalSavedRowKey(row)));

  document.querySelectorAll('[data-rental-card]').forEach((card) => {
    const wishBtn = card.querySelector('[data-rental-wish]');
    const cartBtn = card.querySelector('[data-rental-cart]');
    const payload = parseRentalPayload(wishBtn?.getAttribute('data-rental-wish') || cartBtn?.getAttribute('data-rental-cart') || '');
    const key = rentalKeyFromPayload(payload);

    const wished = !!key && wishKeys.has(key);
    const inCart = !!key && cartKeys.has(key);

    if (wishBtn) wishBtn.classList.toggle('is-active', wished);
    if (cartBtn) {
      cartBtn.classList.toggle('is-active', inCart);
      cartBtn.textContent = inCart ? '담김' : '장바구니';
    }
  });
}

function renderRentalSavedDrawer() {
  const listEl = document.getElementById('rentalSavedList');
  const emptyEl = document.getElementById('rentalSavedEmpty');
  const countEl = document.getElementById('rentalSavedFabCount');
  const tabs = Array.from(document.querySelectorAll('[data-rental-saved-tab]'));
  if (!listEl || !emptyEl) return;

  const total = (rentalSavedState.cart?.length || 0) + (rentalSavedState.wishlist?.length || 0) + (rentalAlertState?.length || 0);
  if (countEl) {
    countEl.hidden = total === 0;
    countEl.textContent = String(total || 0);
  }

  tabs.forEach((btn) => {
    const active = btn.getAttribute('data-rental-saved-tab') === rentalSavedTab;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });

  if (rentalSavedTab === 'alerts') {
    if (!rentalAlertState.length) {
      listEl.innerHTML = '';
      emptyEl.style.display = 'block';
      emptyEl.textContent = '공동구매 참여 요청 알림이 없습니다.';
      return;
    }
    emptyEl.style.display = 'none';
    listEl.innerHTML = '';
    rentalAlertState.forEach((item) => {
      const status = String(item.status || 'pending');
      const statusLabel = status === 'accepted' ? '수락됨' : (status === 'rejected' ? '거절됨' : '대기중');
      const incoming = String(item.direction || 'incoming') !== 'mine';
      const reqTitle = incoming
        ? `${escapeHtml(item.requester_name || '-')}님의 요청입니다`
        : `${escapeHtml(item.requester_name || '작성자')}님의 응답`;
      const li = document.createElement('li');
      li.className = 'rental-saved-item';
      li.style.gridTemplateColumns = '1fr';
      li.innerHTML = `
        <div>
          <div class="rental-saved-item__type">공동구매 · 참여요청</div>
          <div class="rental-saved-item__name">${escapeHtml(item.post_title || '-')}</div>
          <div class="rental-saved-item__meta">${reqTitle}<br>${item.requester_email ? `이메일: ${escapeHtml(item.requester_email)}<br>` : ''}${statusLabel}${item.message ? `<br>${escapeHtml(item.message || '')}` : ''}</div>
          ${incoming && status === 'pending' ? `
            <div class="rental-saved-item__meta" style="margin-top:8px;">
              <button type="button" data-rental-alert-action="accept" data-rental-alert-id="${Number(item.id)}" style="margin-right:6px;padding:4px 8px;border:1px solid #dbeafe;border-radius:8px;background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:700;">수락</button>
              <button type="button" data-rental-alert-action="reject" data-rental-alert-id="${Number(item.id)}" style="padding:4px 8px;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:12px;font-weight:700;">거절</button>
            </div>` : ''}
          ${status !== 'pending' ? `
            <div class="rental-saved-item__meta" style="margin-top:8px;">
              <button type="button" data-rental-alert-remove="${Number(item.id)}" style="padding:4px 8px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;color:#475569;font-size:12px;font-weight:700;">알림 삭제</button>
            </div>` : ''}
        </div>
      `;
      listEl.appendChild(li);
    });
    return;
  }

  const items = Array.isArray(rentalSavedState[rentalSavedTab]) ? rentalSavedState[rentalSavedTab] : [];
  listEl.innerHTML = '';
  emptyEl.style.display = items.length ? 'none' : 'block';
  emptyEl.textContent = rentalSavedTab === 'wishlist' ? '위시리스트 항목이 없습니다.' : '장바구니 항목이 없습니다.';

  items.forEach((item) => {
    const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
    const imageUrl = String(payload?.image || '');
    const li = document.createElement('li');
    li.className = 'rental-saved-item';
    li.innerHTML = `
      <div class="rental-saved-item__thumb">${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="">` : ''}</div>
      <div>
        <div class="rental-saved-item__type">렌터카 · ${escapeHtml(item?.source || 'rental')}</div>
        <div class="rental-saved-item__name">${escapeHtml(item?.name || '-')}</div>
        ${item?.meta ? `<div class="rental-saved-item__meta">${escapeHtml(item.meta).replace(/\|/g, '<br>')}</div>` : ''}
      </div>
      <button type="button" class="rental-saved-item__remove" data-rental-saved-remove="${Number(item.id)}" title="삭제">X</button>
    `;
    listEl.appendChild(li);
  });
}

async function toggleRentalSaved(rawPayload, listType) {
  const payload = buildRentalSavedPayload(rawPayload, listType);
  if (!payload) return false;
  const targetList = Array.isArray(rentalSavedState[listType]) ? rentalSavedState[listType] : [];
  const key = rentalKeyFromPayload(payload.payload);
  const exists = targetList.find((row) => rentalSavedRowKey(row) === key);
  try {
    if (exists) {
      await rentalSavedApi(`/api/saved-items/${Number(exists.id)}`, { method: 'DELETE', headers: {} });
    } else {
      await rentalSavedApi('/api/saved-items', { method: 'POST', body: JSON.stringify(payload) });
    }
    await loadRentalSavedState();
    renderRentalSavedDrawer();
    updateRentalCardButtons();
    return true;
  } catch (e) {
    if (e?.code === 'LOGIN_REQUIRED') {
      alert('로그인이 필요한 기능입니다.\n확인을 누르면 로그인 페이지로 이동합니다.');
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?next=${next}`;
      return false;
    }
    alert(e?.message || '요청 처리 중 오류가 발생했습니다.');
    return false;
  }
}

async function isRentalLoggedIn(force = false) {
  const now = Date.now();
  if (!force && now - Number(rentalAuthState.checkedAt || 0) < 5000) {
    return !!rentalAuthState.loggedIn;
  }
  try {
    const res = await fetch('/api/me', { credentials: 'include' });
    const data = await res.json().catch(() => ({}));
    const loggedIn = !!(res.ok && data?.ok && data?.user && data.user.id);
    rentalAuthState = { checkedAt: now, loggedIn };
    return loggedIn;
  } catch (_e) {
    rentalAuthState = { checkedAt: now, loggedIn: false };
    return false;
  }
}

async function ensureRentalLoggedIn() {
  if (window.__RENTAL_LOGGED_IN__ === true) return true;
  const ok = await isRentalLoggedIn(false);
  if (ok) return true;
  alert('로그인이 필요한 기능입니다.\n확인을 누르면 로그인 페이지로 이동합니다.');
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/login?next=${next}`;
  return false;
}

async function sendRentalAlertDecision(requestId, action) {
  const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}/decision`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || `HTTP ${res.status}`);
  }
}

function initRentalSavedUi() {
  const fab = document.getElementById('rentalSavedFab');
  const drawer = document.getElementById('rentalSavedDrawer');
  const listEl = document.getElementById('rentalSavedList');
  if (!fab || !drawer || !listEl) return;

  fab.addEventListener('click', () => {
    setRentalSavedDrawer(!drawer.classList.contains('is-open'));
    if (drawer.classList.contains('is-open') && rentalSavedTab === 'alerts') {
      loadRentalAlerts().then(renderRentalSavedDrawer);
    }
  });

  document.querySelectorAll('[data-rental-saved-close]').forEach((el) => {
    el.addEventListener('click', () => setRentalSavedDrawer(false));
  });

  document.querySelectorAll('[data-rental-saved-tab]').forEach((btn) => {
    btn.addEventListener('click', () => {
      rentalSavedTab = btn.getAttribute('data-rental-saved-tab') || 'cart';
      if (rentalSavedTab === 'alerts') {
        loadRentalAlerts().then(renderRentalSavedDrawer);
        return;
      }
      renderRentalSavedDrawer();
    });
  });

  document.addEventListener('click', async (e) => {
    const wishBtn = e.target.closest('[data-rental-wish]');
    if (wishBtn) {
      if (!(await ensureRentalLoggedIn())) return;
      const payload = parseRentalPayload(wishBtn.getAttribute('data-rental-wish'));
      await toggleRentalSaved(payload, 'wishlist');
      return;
    }

    const cartBtn = e.target.closest('[data-rental-cart]');
    if (cartBtn) {
      if (!(await ensureRentalLoggedIn())) return;
      const payload = parseRentalPayload(cartBtn.getAttribute('data-rental-cart'));
      await toggleRentalSaved(payload, 'cart');
      return;
    }

    const reserveBtn = e.target.closest('[data-rental-reserve]');
    if (reserveBtn) {
      if (!(await ensureRentalLoggedIn())) return;
      const payload = parseRentalPayload(reserveBtn.getAttribute('data-rental-reserve'));
      if (!payload) return;
      const encoded = encodeURIComponent(JSON.stringify(payload));
      window.location.href = '/rental/detail?car=' + encoded;
      return;
    }

    const actionBtn = e.target.closest('[data-rental-alert-action]');
    if (actionBtn) {
      const requestId = Number(actionBtn.getAttribute('data-rental-alert-id'));
      const action = actionBtn.getAttribute('data-rental-alert-action');
      sendRentalAlertDecision(requestId, action)
        .then(async () => {
          await loadRentalAlerts();
          renderRentalSavedDrawer();
        })
        .catch((err) => alert(err?.message || '요청 처리 중 오류가 발생했습니다.'));
      return;
    }

    const alertRemoveBtn = e.target.closest('[data-rental-alert-remove]');
    if (alertRemoveBtn) {
      const requestId = Number(alertRemoveBtn.getAttribute('data-rental-alert-remove'));
      fetch(`/api/group-buy/join-requests/${requestId}`, { method: 'DELETE', credentials: 'include' })
        .then(async (res) => {
          if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d?.detail || `HTTP ${res.status}`);
          }
          await loadRentalAlerts();
          renderRentalSavedDrawer();
        })
        .catch((err) => alert(err?.message || '알림 삭제 중 오류가 발생했습니다.'));
      return;
    }

    const removeBtn = e.target.closest('[data-rental-saved-remove]');
    if (removeBtn) {
      const itemId = Number(removeBtn.getAttribute('data-rental-saved-remove'));
      rentalSavedApi(`/api/saved-items/${itemId}`, { method: 'DELETE', headers: {} })
        .then(async () => {
          await loadRentalSavedState();
          renderRentalSavedDrawer();
          updateRentalCardButtons();
        })
        .catch((err) => {
          if (err?.code === 'LOGIN_REQUIRED') return;
          alert(err?.message || '삭제 중 오류가 발생했습니다.');
        });
      return;
    }

    if (!drawer.classList.contains('is-open')) return;
    if (drawer.contains(e.target) || fab.contains(e.target)) return;
    setRentalSavedDrawer(false);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.classList.contains('is-open')) setRentalSavedDrawer(false);
  });

  Promise.all([loadRentalSavedState(), loadRentalAlerts()]).finally(() => {
    renderRentalSavedDrawer();
    updateRentalCardButtons();
    if (window.lucide) lucide.createIcons();
  });
}
