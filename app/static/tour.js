(() => {
  const LOGIN_CONFIRM_MESSAGE = "로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?";
  const CART_LABEL = "장바구니";
  const CART_IN_LABEL = "담김";
  const WISHLIST_EMPTY_LABEL = "위시리스트 항목이 없습니다.";
  const CART_EMPTY_LABEL = "장바구니 항목이 없습니다.";

  let tourSavedDrawerTab = "cart";
  let tourSavedState = { cart: [], wishlist: [] };
  let tourAlertState = [];

  const isLoggedIn = () => typeof window.nickname !== "undefined" && window.nickname !== null && window.nickname !== "";

  const requireLoginMessage = () => {
    if (confirm(LOGIN_CONFIRM_MESSAGE)) location.href = "/login";
  };

  const parseBackgroundImageUrl = (value) => {
    const s = String(value || "");
    const m = s.match(/url\((['"]?)(.*?)\1\)/i);
    return m && m[2] ? m[2] : "";
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const normalizePrice = (text) => {
    const raw = String(text || "").trim();
    if (!raw) return "";
    const digits = raw.replace(/[^\d]/g, "");
    if (!digits) return raw;
    return `${Number(digits).toLocaleString()}원~`;
  };

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
    renderTourButtons();
  }

  async function loadTourAlerts() {
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

  const getCardContext = (buttonEl) => {
    const card = buttonEl?.closest?.(".tour-card");
    if (!card) return null;

    const title = (card.querySelector(".tour-name")?.textContent || "").trim();
    const location = (card.querySelector(".tour-loc")?.textContent || "").trim();
    const priceText = normalizePrice(card.querySelector(".price-val")?.textContent || "");
    const badge = (card.querySelector(".badge")?.textContent || "").trim();
    const imageWrap = card.querySelector(".tour-image");

    let image = "";
    if (imageWrap) {
      const inlineBg = parseBackgroundImageUrl(imageWrap.style?.backgroundImage || "");
      const computedBg = parseBackgroundImageUrl(window.getComputedStyle(imageWrap).backgroundImage || "");
      const imageTag = imageWrap.querySelector("img")?.getAttribute("src") || "";
      image = inlineBg || computedBg || imageTag || "";
    }

    return { card, title, location, priceText, badge, image };
  };

  const buildSavePayload = (buttonEl, listType) => {
    const ctx = getCardContext(buttonEl);
    if (!ctx || !ctx.title) return null;

    const meta = [ctx.location, ctx.priceText].filter(Boolean).join(" | ");

    return {
      list_type: listType,
      item_type: "tour",
      source: "tour",
      name: ctx.title,
      meta,
      payload: {
        name: ctx.title,
        title: ctx.title,
        location: ctx.location,
        price_text: ctx.priceText,
        badge: ctx.badge,
        image: ctx.image,
        image_url: ctx.image,
      },
    };
  };

  const findSavedRow = (listType, name) =>
    (tourSavedState[listType] || []).find((row) => String(row?.name || "").trim() === String(name || "").trim());

  async function upsertTourSaved(buttonEl, listType) {
    if (!isLoggedIn()) return requireLoginMessage();

    const payload = buildSavePayload(buttonEl, listType);
    if (!payload) return;

    const existing = findSavedRow(listType, payload.name);
    try {
      if (existing) {
        await savedItemsApi(`/api/saved-items/${Number(existing.id)}`, { method: "DELETE", headers: {} });
      } else {
        await savedItemsApi("/api/saved-items", { method: "POST", body: JSON.stringify(payload) });
      }
      await loadTourSavedItems();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  async function addTourCartOnly(buttonEl) {
    if (!isLoggedIn()) return requireLoginMessage();

    const payload = buildSavePayload(buttonEl, "cart");
    if (!payload) return;

    const existing = findSavedRow("cart", payload.name);
    if (existing) {
      setTourSavedDrawer(true);
      return;
    }

    try {
      await savedItemsApi("/api/saved-items", { method: "POST", body: JSON.stringify(payload) });
      await loadTourSavedItems();
      tourSavedDrawerTab = "cart";
      setTourSavedDrawer(true);
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

  function ensureAlertsTab() {
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

  function renderTourButtons() {
    const wishNames = new Set((tourSavedState.wishlist || []).map((row) => String(row?.name || "").trim()));
    const cartNames = new Set((tourSavedState.cart || []).map((row) => String(row?.name || "").trim()));

    document.querySelectorAll(".tour-card").forEach((card) => {
      const title = (card.querySelector(".tour-name")?.textContent || "").trim();
      if (!title) return;

      const inWish = wishNames.has(title);
      const inCart = cartNames.has(title);

      const wishBtn = card.querySelector(".tour-wishlist-btn");
      if (wishBtn) {
        const icon = wishBtn.querySelector("i");
        if (icon) {
          icon.classList.toggle("fa-solid", inWish);
          icon.classList.toggle("fa-regular", !inWish);
          icon.style.color = inWish ? "#ef4444" : "";
        }
        wishBtn.classList.toggle("in-wishlist", inWish);
      }

      const cartBtn = card.querySelector(".tour-cart-text-btn");
      if (cartBtn) {
        cartBtn.textContent = inCart ? CART_IN_LABEL : CART_LABEL;
      }
    });
  }

  function buildAlertCardHtml(alert) {
    const requestId = Number(alert?.id);
    if (!requestId) return "";

    const status = String(alert?.status || "pending");
    const statusLabel = status === "accepted" ? "수락됨" : status === "rejected" ? "거절됨" : "대기중";
    const statusClass = status === "accepted" ? "#059669" : status === "rejected" ? "#dc2626" : "#d97706";
    const incoming = String(alert?.direction || "incoming") !== "mine";

    const actionHtml = incoming && status === "pending"
      ? `<div style="margin-top:8px;display:flex;gap:6px;">
          <button type="button" data-tour-alert-decision="accept" data-tour-alert-id="${requestId}" style="padding:4px 8px;border-radius:8px;border:1px solid #a7f3d0;background:#ecfdf5;color:#065f46;font-size:12px;font-weight:700;">수락</button>
          <button type="button" data-tour-alert-decision="reject" data-tour-alert-id="${requestId}" style="padding:4px 8px;border-radius:8px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;font-size:12px;font-weight:700;">거절</button>
        </div>`
      : "";

    const removeHtml = status !== "pending"
      ? `<button type="button" data-tour-alert-remove="${requestId}" style="position:absolute;top:8px;right:8px;width:22px;height:22px;border-radius:999px;border:1px solid #e2e8f0;background:#fff;color:#64748b;">×</button>`
      : "";

    return `<li class="tour-saved-item" style="padding-right:10px;">
      ${removeHtml}
      <div class="tour-saved-item__type" style="background:#fff7ed;color:#b45309;">알림</div>
      <div class="tour-saved-item__name">${escapeHtml(alert?.post_title || "공동구매 참여 요청")}</div>
      <div class="tour-saved-item__meta">${escapeHtml(alert?.requester_name || "사용자")} · <span style="color:${statusClass};font-weight:700;">${statusLabel}</span></div>
      ${alert?.message ? `<div class="tour-saved-item__meta">${escapeHtml(alert.message)}</div>` : ""}
      ${actionHtml}
    </li>`;
  }

  function renderTourSavedDrawer() {
    const listEl = document.getElementById("tourSavedList");
    const emptyEl = document.getElementById("tourSavedEmpty");
    const countEl = document.getElementById("tourSavedFabCount");
    const tabs = Array.from(document.querySelectorAll("[data-tour-saved-tab]"));
    if (!listEl || !emptyEl) return;

    ensureAlertsTab();

    const total = (tourSavedState.cart?.length || 0) + (tourSavedState.wishlist?.length || 0) + (tourAlertState?.length || 0);
    if (countEl) {
      countEl.hidden = total === 0;
      countEl.textContent = String(total || 0);
    }

    tabs.forEach((btn) => {
      const active = btn.getAttribute("data-tour-saved-tab") === tourSavedDrawerTab;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    listEl.innerHTML = "";

    if (tourSavedDrawerTab === "alerts") {
      const alerts = Array.isArray(tourAlertState) ? tourAlertState : [];
      emptyEl.style.display = alerts.length ? "none" : "block";
      emptyEl.textContent = "도착한 참여 요청 알림이 없습니다.";
      alerts.forEach((alert) => {
        const html = buildAlertCardHtml(alert);
        if (!html) return;
        const wrap = document.createElement("div");
        wrap.innerHTML = html;
        if (wrap.firstElementChild) listEl.appendChild(wrap.firstElementChild);
      });
      return;
    }

    const items = Array.isArray(tourSavedState[tourSavedDrawerTab]) ? tourSavedState[tourSavedDrawerTab] : [];
    emptyEl.style.display = items.length ? "none" : "block";
    emptyEl.textContent = tourSavedDrawerTab === "wishlist" ? WISHLIST_EMPTY_LABEL : CART_EMPTY_LABEL;

    items.forEach((item) => {
      const payload = item?.payload && typeof item.payload === "object" ? item.payload : {};
      const image = payload?.image_url || payload?.image || "";
      const meta = item?.meta || [payload?.location || "", payload?.price_text || ""].filter(Boolean).join(" | ");

      const li = document.createElement("li");
      li.className = "tour-saved-item";
      li.innerHTML = `
        <div style="display:flex;gap:10px;align-items:flex-start;">
          <div style="width:52px;height:52px;border-radius:10px;overflow:hidden;flex:0 0 52px;background:#e2e8f0;${image ? `background-image:url('${escapeHtml(image)}');background-size:cover;background-position:center;` : ""}"></div>
          <div style="min-width:0;flex:1;">
            <div class="tour-saved-item__type">${escapeHtml(item?.item_type || "tour")}</div>
            <div class="tour-saved-item__name">${escapeHtml(item?.name || "-")}</div>
            ${meta ? `<div class="tour-saved-item__meta">${escapeHtml(meta)}</div>` : ""}
          </div>
        </div>
        <button type="button" class="tour-saved-item__remove" data-tour-saved-remove="${Number(item.id)}" title="삭제">×</button>
      `;
      listEl.appendChild(li);
    });
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
    renderTourSavedDrawer();
  }

  async function removeTourAlert(requestId) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    tourAlertState = (tourAlertState || []).filter((x) => Number(x?.id) !== Number(requestId));
    renderTourSavedDrawer();
  }

  async function removeTourSavedItem(itemId) {
    await savedItemsApi(`/api/saved-items/${Number(itemId)}`, { method: "DELETE", headers: {} });
    tourSavedState.cart = (tourSavedState.cart || []).filter((x) => Number(x?.id) !== Number(itemId));
    tourSavedState.wishlist = (tourSavedState.wishlist || []).filter((x) => Number(x?.id) !== Number(itemId));
    renderTourSavedDrawer();
    renderTourButtons();
  }

  function initTourSavedDrawer() {
    const fab = document.getElementById("tourSavedFab");
    const drawer = document.getElementById("tourSavedDrawer");
    const listEl = document.getElementById("tourSavedList");
    if (!fab || !drawer || !listEl) return;

    ensureAlertsTab();

    fab.addEventListener("click", async () => {
      const nextOpen = !drawer.classList.contains("is-open");
      setTourSavedDrawer(nextOpen);
      if (nextOpen && tourSavedDrawerTab === "alerts") {
        await loadTourAlerts();
        renderTourSavedDrawer();
      }
    });

    document.querySelectorAll("[data-tour-saved-close]").forEach((el) => {
      el.addEventListener("click", () => setTourSavedDrawer(false));
    });

    document.addEventListener("click", async (e) => {
      const tabBtn = e.target.closest("[data-tour-saved-tab]");
      if (tabBtn) {
        tourSavedDrawerTab = tabBtn.getAttribute("data-tour-saved-tab") || "cart";
        if (tourSavedDrawerTab === "alerts") await loadTourAlerts();
        renderTourSavedDrawer();
        return;
      }

      const decisionBtn = e.target.closest("[data-tour-alert-decision]");
      if (decisionBtn) {
        const requestId = Number(decisionBtn.getAttribute("data-tour-alert-id"));
        const action = decisionBtn.getAttribute("data-tour-alert-decision");
        if (!requestId || !action) return;
        try { await decideTourAlert(requestId, action); } catch (_e) {}
        return;
      }

      const removeAlertBtn = e.target.closest("[data-tour-alert-remove]");
      if (removeAlertBtn) {
        const requestId = Number(removeAlertBtn.getAttribute("data-tour-alert-remove"));
        if (!requestId) return;
        try { await removeTourAlert(requestId); } catch (_e) {}
        return;
      }

      const removeBtn = e.target.closest("[data-tour-saved-remove]");
      if (removeBtn) {
        const itemId = Number(removeBtn.getAttribute("data-tour-saved-remove"));
        if (!itemId) return;
        try { await removeTourSavedItem(itemId); } catch (_e) {}
      }
    });

    renderTourSavedDrawer();
  }

  function initTourCardActions() {
    document.addEventListener("click", async (e) => {
      const wishBtn = e.target.closest(".tour-wishlist-btn");
      if (wishBtn) {
        e.preventDefault();
        e.stopPropagation();
        await upsertTourSaved(wishBtn, "wishlist");
        tourSavedDrawerTab = "wishlist";
        setTourSavedDrawer(true);
        return;
      }

      const cartBtn = e.target.closest(".tour-cart-text-btn");
      if (cartBtn) {
        e.preventDefault();
        e.stopPropagation();
        await upsertTourSaved(cartBtn, "cart");
        tourSavedDrawerTab = "cart";
        setTourSavedDrawer(true);
        return;
      }

      const payBtn = e.target.closest(".tour-pay-text-btn");
      if (payBtn) {
        e.preventDefault();
        e.stopPropagation();
        await addTourCartOnly(payBtn);
        return;
      }

      const card = e.target.closest(".tour-card");
      if (!card) return;
      if (e.target.closest("button")) return;

      const title = (card.querySelector(".tour-name")?.textContent || "").trim();
      if (!title) return;
      e.preventDefault();
      location.href = `/tour-detail?tour_id=${encodeURIComponent(title)}`;
    });
  }

  window.addTourToCart = async function addTourToCart(btn, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    await upsertTourSaved(btn, "cart");
    tourSavedDrawerTab = "cart";
    setTourSavedDrawer(true);
  };

  window.payTourProduct = async function payTourProduct(btn, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    await addTourCartOnly(btn);
  };

  document.addEventListener("DOMContentLoaded", async () => {
    initTourSavedDrawer();
    initTourCardActions();
    await loadTourSavedItems();
    await loadTourAlerts();
    renderTourSavedDrawer();

    window.addEventListener("authchange", async () => {
      await loadTourSavedItems();
      await loadTourAlerts();
      renderTourSavedDrawer();
    });

    if (window.lucide && lucide.createIcons) lucide.createIcons();
  });
})();
