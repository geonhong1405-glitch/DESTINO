(() => {
  const LOGIN_CONFIRM_MESSAGE = "로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?";
  const CART_LABEL = "장바구니";
  const CART_IN_LABEL = "담김";
  const ALERT_EMPTY_LABEL = "도착한 참여 요청 알림이 없습니다.";

  let tourSavedState = { cart: [], wishlist: [] };
  let tourSavedDrawerTab = "cart";
  let tourAlertState = [];

  function isLoggedIn() {
    return typeof window.nickname !== "undefined" && window.nickname !== null && window.nickname !== "";
  }

  function requireLoginMessage() {
    if (confirm(LOGIN_CONFIRM_MESSAGE)) {
      location.href = "/login";
    }
  }

  function parseBackgroundImageUrl(value) {
    const s = String(value || "");
    const m = s.match(/url\((['\"]?)(.*?)\1\)/i);
    return m && m[2] ? m[2] : "";
  }

  function normalizeText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[•·]/g, ".")
      .replace(/\s+/g, "")
      .replace(/[^0-9a-zA-Z가-힣.]/g, "");
  }

  function normalizePrice(value) {
    const digits = String(value || "").replace(/\D/g, "");
    return digits || normalizeText(value);
  }

  function getTourSavedKey(item) {
    const title = normalizeText(item?.title || item?.name || item?.payload?.title || item?.payload?.name || "");
    const location = normalizeText(item?.location || item?.payload?.location || "");
    const price = normalizePrice(item?.price || item?.payload?.price_text || item?.meta || "");
    return `${title}__${location}__${price}`;
  }

  function getTourIdentity(item) {
    const title = normalizeText(item?.title || item?.name || item?.payload?.title || item?.payload?.name || "");
    const location = normalizeText(item?.location || item?.payload?.location || "");
    return `${title}__${location}`;
  }

  function extractTourData(card, idx) {
    const location = (card.querySelector(".tour-loc")?.innerText || "").trim();
    const title = (card.querySelector(".tour-name")?.innerText || "").trim();
    let price = (card.querySelector(".price-val")?.innerText || "").trim();
    if (price && !price.includes(",")) {
      const n = Number(price.replace(/,/g, ""));
      if (!Number.isNaN(n)) price = n.toLocaleString();
    }

    const imageWrap = card.querySelector(".tour-image");
    const inlineBg = parseBackgroundImageUrl(imageWrap?.style?.backgroundImage || "");
    const computedBg = parseBackgroundImageUrl(window.getComputedStyle(imageWrap || card).backgroundImage || "");
    const imageTag = imageWrap?.querySelector("img")?.getAttribute("src") || "";

    return {
      id: `${title}_${location}_${price}_${idx}`,
      image: inlineBg || computedBg || imageTag || "",
      location,
      title,
      price,
      badge: (card.querySelector(".badge")?.innerText || "").trim(),
    };
  }

  function updateTourCardButtons() {
    const wishlistKeys = new Set((tourSavedState.wishlist || []).map((row) => getTourIdentity(row?.payload || row)));
    const cartKeys = new Set((tourSavedState.cart || []).map((row) => getTourIdentity(row?.payload || row)));

    document.querySelectorAll(".tour-card").forEach((card, index) => {
      const data = extractTourData(card, index);
      const key = getTourIdentity(data);
      const inWishlist = wishlistKeys.has(key);
      const inCart = cartKeys.has(key);

      const wishBtn = card.querySelector(".tour-wishlist-btn");
      const wishIcon = wishBtn?.querySelector("i");
      if (wishBtn) {
        wishBtn.classList.toggle("is-active", inWishlist);
        wishBtn.setAttribute("aria-pressed", inWishlist ? "true" : "false");
      }
      if (wishIcon) {
        wishIcon.className = inWishlist ? "fa-solid fa-heart" : "fa-regular fa-heart";
      }

      const cartBtn = card.querySelector(".tour-cart-text-btn");
      if (cartBtn) {
        cartBtn.textContent = inCart ? CART_IN_LABEL : CART_LABEL;
        cartBtn.classList.toggle("is-active", inCart);
      }
    });
  }

  async function savedItemsApi(path = "/api/saved-items", options = {}) {
    const res = await fetch(path, {
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });

    if (res.status === 401) {
      const err = new Error("LOGIN_REQUIRED");
      err.code = "LOGIN_REQUIRED";
      throw err;
    }

    let data = null;
    try {
      data = await res.json();
    } catch (_e) {}

    if (!res.ok) {
      const err = new Error((data && (data.detail || data.error)) || `HTTP ${res.status}`);
      err.code = "API_ERROR";
      err.payload = data;
      throw err;
    }

    return data;
  }

  async function loadTourSavedItems() {
    if (!isLoggedIn()) {
      tourSavedState = { cart: [], wishlist: [] };
      renderTourSavedDrawer();
      updateTourCardButtons();
      return;
    }

    try {
      const data = await savedItemsApi("/api/saved-items", { method: "GET", headers: {} });
      tourSavedState = {
        cart: Array.isArray(data?.cart) ? data.cart : [],
        wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
      };
    } catch (_e) {
      tourSavedState = { cart: [], wishlist: [] };
    }

    renderTourSavedDrawer();
    updateTourCardButtons();
  }

  async function loadTourAlerts() {
    if (!isLoggedIn()) {
      tourAlertState = [];
      return;
    }
    try {
      const res = await fetch("/api/group-buy/join-requests/inbox", { credentials: "include" });
      if (res.status === 401) {
        tourAlertState = [];
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      tourAlertState = Array.isArray(data) ? data : [];
    } catch (_e) {
      tourAlertState = [];
    }
  }

  async function decideTourAlert(requestId, action) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}/decision`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadTourAlerts();
  }

  async function removeTourAlert(requestId) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    tourAlertState = (tourAlertState || []).filter((x) => Number(x?.id) !== Number(requestId));
  }

  function ensureTourAlertsTab() {
    const tabsWrap = document.querySelector(".tour-saved-tabs");
    if (!tabsWrap) return null;
    let alertTab = tabsWrap.querySelector('[data-tour-saved-tab="alerts"]');
    if (!alertTab) {
      alertTab = document.createElement("button");
      alertTab.type = "button";
      alertTab.className = "tour-saved-tab";
      alertTab.setAttribute("data-tour-saved-tab", "alerts");
      alertTab.setAttribute("aria-selected", "false");
      alertTab.textContent = "알림";
      tabsWrap.appendChild(alertTab);
    }
    return alertTab;
  }

  function buildSavePayload(tourData, listType) {
    const title = String(tourData?.title || "").trim();
    if (!title) return null;

    const meta = [tourData.location, tourData.price].filter(Boolean).join(" | ");
    return {
      list_type: listType,
      item_type: "ticket",
      source: "tour",
      name: title,
      meta,
      payload: {
        id: tourData.id,
        title,
        name: title,
        location: tourData.location || "",
        price_text: tourData.price || "",
        image: tourData.image || "",
        image_url: tourData.image || "",
        badge: tourData.badge || "",
        detail_url: "",
      },
    };
  }

  function findSavedRow(listType, tourData) {
    const targetKey = getTourIdentity(tourData);
    return (tourSavedState[listType] || []).find((row) => getTourIdentity(row?.payload || row) === targetKey);
  }

  async function toggleTourSaved(tourData, listType) {
    if (!isLoggedIn()) {
      requireLoginMessage();
      return;
    }

    const existing = findSavedRow(listType, tourData);

    try {
      if (existing?.id) {
        await savedItemsApi(`/api/saved-items/${existing.id}`, { method: "DELETE", headers: {} });
      } else {
        const payload = buildSavePayload(tourData, listType);
        if (!payload) return;
        await savedItemsApi("/api/saved-items", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      await loadTourSavedItems();
      tourSavedDrawerTab = listType;
      renderTourSavedDrawer();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  async function toggleHeartSaved(tourData) {
    if (!isLoggedIn()) {
      requireLoginMessage();
      return;
    }

    const wishRow = findSavedRow("wishlist", tourData);
    const isSaved = !!wishRow;

    try {
      if (isSaved) {
        if (wishRow?.id) {
          await savedItemsApi(`/api/saved-items/${wishRow.id}`, { method: "DELETE", headers: {} });
        }
      } else {
        const payload = buildSavePayload(tourData, "wishlist");
        if (!payload) return;
        await savedItemsApi("/api/saved-items", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      await loadTourSavedItems();
      renderTourSavedDrawer();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  function setTourSavedDrawer(open) {
    const drawer = document.getElementById("tourSavedDrawer");
    const fab = document.getElementById("tourSavedFab");
    if (!drawer || !fab) return;
    drawer.classList.toggle("is-open", !!open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    fab.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function renderTourSavedDrawer() {
    const listEl = document.getElementById("tourSavedList");
    const emptyEl = document.getElementById("tourSavedEmpty");
    const countEl = document.getElementById("tourSavedFabCount");
    const alertsTab = ensureTourAlertsTab();
    const tabs = Array.from(document.querySelectorAll("[data-tour-saved-tab]"));
    if (!listEl || !emptyEl) return;

    const items = Array.isArray(tourSavedState[tourSavedDrawerTab]) ? tourSavedState[tourSavedDrawerTab] : [];
    const total =
      (tourSavedState.cart?.length || 0) +
      (tourSavedState.wishlist?.length || 0) +
      (tourAlertState?.length || 0);

    if (countEl) {
      countEl.hidden = total === 0;
      countEl.textContent = String(total || 0);
    }

    tabs.forEach((btn) => {
      const active = btn.getAttribute("data-tour-saved-tab") === tourSavedDrawerTab;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    if (tourSavedDrawerTab === "alerts") {
      listEl.innerHTML = "";
      emptyEl.style.display = tourAlertState.length ? "none" : "block";
      emptyEl.textContent = ALERT_EMPTY_LABEL;

      tourAlertState.forEach((alert) => {
        const li = document.createElement("li");
        li.className = "tour-saved-item";
        const status = String(alert?.status || "pending");
        const statusLabel = status === "accepted" ? "수락됨" : status === "rejected" ? "거절됨" : "대기중";
        const incoming = String(alert?.direction || "incoming") !== "mine";
        li.innerHTML = `
          <div class="tour-saved-item__type">알림</div>
          <div class="tour-saved-item__name">${alert?.post_title || "공동구매 참여 요청"}</div>
          <div class="tour-saved-item__meta">${alert?.requester_name || "사용자"} | ${statusLabel}</div>
          ${alert?.message ? `<div class="tour-saved-item__meta">${alert.message}</div>` : ""}
          ${
            incoming && status === "pending"
              ? `
                <div style="display:flex;gap:6px;margin-top:8px;">
                  <button type="button" data-tour-alert-decision="accept" data-tour-alert-id="${Number(alert?.id)}" style="padding:4px 8px;border-radius:8px;border:1px solid #a7f3d0;background:#ecfdf5;color:#065f46;font-size:12px;font-weight:700;">수락</button>
                  <button type="button" data-tour-alert-decision="reject" data-tour-alert-id="${Number(alert?.id)}" style="padding:4px 8px;border-radius:8px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;font-size:12px;font-weight:700;">거절</button>
                </div>
              `
              : ""
          }
          ${status !== "pending" ? `<button type="button" class="tour-saved-item__remove" data-tour-alert-remove="${Number(alert?.id)}" title="삭제">&times;</button>` : ""}
        `;
        listEl.appendChild(li);
      });
      return;
    }

    listEl.innerHTML = "";
    emptyEl.style.display = items.length ? "none" : "block";
    emptyEl.textContent = tourSavedDrawerTab === "wishlist" ? "위시리스트 항목이 없습니다." : "장바구니 항목이 없습니다.";

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "tour-saved-item";
      li.innerHTML = `
        <div class="tour-saved-item__type">${item.item_type || (tourSavedDrawerTab === "cart" ? "ticket" : "wishlist")}</div>
        <div class="tour-saved-item__name">${item.name || item?.payload?.title || "-"}</div>
        <div class="tour-saved-item__meta">${item.meta || ""}</div>
        <button type="button" class="tour-saved-item__remove" data-tour-saved-remove="${Number(item.id)}" title="remove">&times;</button>
      `;
      listEl.appendChild(li);
    });
  }

  function initTourSavedDrawer() {
    const fab = document.getElementById("tourSavedFab");
    const drawer = document.getElementById("tourSavedDrawer");
    const listEl = document.getElementById("tourSavedList");
    ensureTourAlertsTab();
    if (!fab || !drawer) return;

    fab.addEventListener("click", () => {
      setTourSavedDrawer(!drawer.classList.contains("is-open"));
    });

    document.querySelectorAll("[data-tour-saved-close]").forEach((el) => {
      el.addEventListener("click", () => setTourSavedDrawer(false));
    });

    document.querySelectorAll("[data-tour-saved-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        tourSavedDrawerTab = btn.getAttribute("data-tour-saved-tab") || "cart";
        if (tourSavedDrawerTab === "alerts") {
          loadTourAlerts().then(renderTourSavedDrawer);
          return;
        }
        renderTourSavedDrawer();
      });
    });

    listEl?.addEventListener("click", async (e) => {
      const decisionBtn = e.target.closest("[data-tour-alert-decision]");
      if (decisionBtn) {
        const requestId = Number(decisionBtn.getAttribute("data-tour-alert-id"));
        const action = decisionBtn.getAttribute("data-tour-alert-decision");
        if (!requestId || !action) return;
        try {
          await decideTourAlert(requestId, action);
          renderTourSavedDrawer();
        } catch (_err) {}
        return;
      }

      const removeAlertBtn = e.target.closest("[data-tour-alert-remove]");
      if (removeAlertBtn) {
        const requestId = Number(removeAlertBtn.getAttribute("data-tour-alert-remove"));
        if (!requestId) return;
        try {
          await removeTourAlert(requestId);
          renderTourSavedDrawer();
        } catch (_err) {}
        return;
      }

      const btn = e.target.closest("[data-tour-saved-remove]");
      if (!btn) return;
      const itemId = Number(btn.getAttribute("data-tour-saved-remove"));
      if (Number.isNaN(itemId) || itemId <= 0) return;

      if (!isLoggedIn()) {
        requireLoginMessage();
        return;
      }

      try {
        await savedItemsApi(`/api/saved-items/${itemId}`, { method: "DELETE", headers: {} });
        await loadTourSavedItems();
      } catch (err) {
        if (err?.code === "LOGIN_REQUIRED") requireLoginMessage();
      }
    });

    renderTourSavedDrawer();
  }

  function setupTourCardNavigation() {
    document.addEventListener("click", function (e) {
      const card = e.target.closest(".tour-card");
      if (!card) return;
      if (e.target.closest(".tour-wishlist-btn") || e.target.closest(".tour-cart-text-btn") || e.target.closest(".tour-pay-text-btn")) {
        return;
      }

      const index = Array.from(document.querySelectorAll(".tour-card")).indexOf(card);
      if (index === -1) return;
      const tourData = extractTourData(card, index);

      const params = new URLSearchParams();
      params.append("id", tourData.id);
      params.append("title", tourData.title);
      params.append("price", tourData.price);
      params.append("img", tourData.image);
      params.append("loc", tourData.location);
      window.location.href = `/tour-detail?${params.toString()}`;
    });
  }

  function setupWishlistButtonEvents() {
    document.addEventListener("click", async function (e) {
      const btn = e.target.closest(".tour-wishlist-btn");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();

      const card = btn.closest(".tour-card");
      const index = Array.from(document.querySelectorAll(".tour-card")).indexOf(card);
      if (index === -1) return;
      const tourData = extractTourData(card, index);
      const icon = btn.querySelector("i");
      const exists = !!findSavedRow("wishlist", tourData);

      // Optimistic UI: fill/unfill heart immediately, then reconcile from server state.
      if (icon) icon.className = exists ? "fa-regular fa-heart" : "fa-solid fa-heart";
      btn.classList.toggle("is-active", !exists);
      btn.setAttribute("aria-pressed", exists ? "false" : "true");

      await toggleHeartSaved(tourData);
    });
  }

  async function addTourToCart(btn, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    const card = btn?.closest?.(".tour-card");
    if (!card) return;

    const index = Array.from(document.querySelectorAll(".tour-card")).indexOf(card);
    if (index === -1) return;
    const tourData = extractTourData(card, index);

    await toggleTourSaved(tourData, "cart");
  }

  function payTourProduct(btn, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    if (!isLoggedIn()) {
      requireLoginMessage();
      return;
    }

    const card = btn?.closest?.(".tour-card");
    if (!card) return;
    const index = Array.from(document.querySelectorAll(".tour-card")).indexOf(card);
    if (index === -1) return;

    const tourData = extractTourData(card, index);
    toggleTourSaved(tourData, "cart");
    alert("결제 기능은 준비 중입니다. 우선 장바구니에 담아두었습니다.");
  }

  function initSearchWidget() {
    const destInput = document.getElementById("dest-input");
    const tourPopover = document.getElementById("tourPopover");
    const defaultSugg = document.getElementById("default-suggestions");
    const searchResults = document.getElementById("search-results");
    const resultsList = document.getElementById("results-list");
    const searchWidget = document.getElementById("searchWidget");

    if (window.lucide && lucide.createIcons) {
      lucide.createIcons();
    }

    if (destInput && tourPopover) {
      destInput.addEventListener("click", (e) => {
        e.stopPropagation();
        tourPopover.classList.add("active");
      });
    }

    if (destInput && defaultSugg && searchResults && resultsList) {
      destInput.addEventListener("input", (e) => {
        const val = e.target.value;
        if (val.trim().length > 0) {
          defaultSugg.style.display = "none";
          searchResults.style.display = "block";
          resultsList.innerHTML = `
            <div class="search-suggestion-item" onclick="selectDest('${val}')">
              <i data-lucide="map-pin" size="16"></i>
              <span><strong>'${val}'</strong> results</span>
            </div>
            <div class="search-suggestion-item" onclick="selectDest('${val} attractions')">
              <i data-lucide="star" size="16"></i>
              <span>${val} attractions</span>
            </div>
          `;
          if (window.lucide && lucide.createIcons) {
            lucide.createIcons();
          }
        } else {
          defaultSugg.style.display = "block";
          searchResults.style.display = "none";
        }
      });
    }

    if (searchWidget && tourPopover) {
      document.addEventListener("click", (e) => {
        if (!searchWidget.contains(e.target)) {
          tourPopover.classList.remove("active");
        }
      });
    }
  }

  function selectDest(name) {
    const destInput = document.getElementById("dest-input");
    const tourPopover = document.getElementById("tourPopover");
    if (destInput) destInput.value = name;
    if (tourPopover) tourPopover.classList.remove("active");
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTourSavedDrawer();
    setupTourCardNavigation();
    setupWishlistButtonEvents();
    Promise.all([loadTourSavedItems(), loadTourAlerts()]).then(renderTourSavedDrawer);
    initSearchWidget();

    window.addEventListener("authchange", () => {
      Promise.all([loadTourSavedItems(), loadTourAlerts()]).then(renderTourSavedDrawer);
    });
  });

  window.selectDest = selectDest;
  window.addTourToCart = addTourToCart;
  window.payTourProduct = payTourProduct;
})();
