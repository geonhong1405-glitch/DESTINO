(() => {
  const LOGIN_CONFIRM_MESSAGE =
    "로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?";
  const CART_LABEL = "장바구니";
  const CART_IN_LABEL = "담김";
  const CART_EMPTY_LABEL = "장바구니 항목이 없습니다.";
  const WISHLIST_EMPTY_LABEL = "위시리스트 항목이 없습니다.";
  const ALERT_EMPTY_LABEL = "도착한 참여 요청 알림이 없습니다.";

  let packageSavedDrawerTab = "cart";
  let packageSavedState = { cart: [], wishlist: [] };
  let packageAlertState = [];

  function isLoggedIn() {
    return (
      typeof window.__AUTH__ !== "undefined" &&
      window.__AUTH__ !== null &&
      window.__AUTH__ !== ""
    );
  }

  function requireLoginMessage() {
    if (confirm(LOGIN_CONFIRM_MESSAGE)) {
      location.href = "/login";
    }
  }

  function parsePayload(raw) {
    if (!raw) return null;
    if (typeof raw === "object") return raw;
    try {
      const p = JSON.parse(raw);
      return p && typeof p === "object" ? p : null;
    } catch (_e) {
      const name = String(raw).trim();
      if (!name) return null;
      return { name, source: "package", payload: {} };
    }
  }

  function normalizeKrwPriceText(text) {
    const raw = String(text || "").trim();
    if (!raw) return "";
    const m = raw.match(/([\d,]+(?:\.\d+)?)\s*(krw|KRW|원|₩)?/);
    if (!m) return "";
    const n = Number(String(m[1]).replace(/,/g, ""));
    if (!Number.isFinite(n) || n <= 0) return "";
    return `₩${Math.floor(n).toLocaleString("ko-KR")}`;
  }

  function savedTypeLabel(itemType) {
    const type = String(itemType || "").toLowerCase();
    if (type === "flight") return "FLIGHT";
    if (type === "hotel" || type === "stay" || type === "accommodation")
      return "HOTEL";
    if (type === "ticket" || type === "tour") return "TICKET";
    if (type === "package") return "PACKAGE";
    if (type === "groupbuy" || type === "travel-group") return "GROUPBUY";
    return type ? type.toUpperCase() : "ITEM";
  }

  function parseBackgroundImageUrl(value) {
    const s = String(value || "");
    const m = s.match(/url\((['"]?)(.*?)\1\)/i);
    return m && m[2] ? m[2] : "";
  }

  function getCardContext(buttonEl) {
    const card = buttonEl?.closest?.(".package-card");
    if (!card) return {};
    const title = (
      card.querySelector(".package-name")?.textContent || ""
    ).trim();
    const location = (
      card.querySelector(".package-loc")?.textContent || ""
    ).trim();
    const priceText = (
      card.querySelector(".price-val")?.textContent || ""
    ).trim();
    const imageWrap = card.querySelector(".package-image");
    let image = "";
    if (imageWrap) {
      const inlineBg = parseBackgroundImageUrl(
        imageWrap.style?.backgroundImage || "",
      );
      const computedBg = parseBackgroundImageUrl(
        window.getComputedStyle(imageWrap).backgroundImage || "",
      );
      const imageTag =
        imageWrap.querySelector("img")?.getAttribute("src") || "";
      image = inlineBg || computedBg || imageTag || "";
    }
    const href = card.getAttribute("href") || "";
    return { title, location, priceText, image, href };
  }

  function payloadName(payload) {
    const p = parsePayload(payload);
    return String(p?.name || "").trim();
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
      const err = new Error(
        (data && (data.detail || data.error)) || `HTTP ${res.status}`,
      );
      err.code = "API_ERROR";
      err.payload = data;
      throw err;
    }

    return data;
  }

  async function loadPackageSavedItems() {
    try {
      const data = await savedItemsApi("/api/saved-items", {
        method: "GET",
        headers: {},
      });
      packageSavedState = {
        cart: Array.isArray(data?.cart) ? data.cart : [],
        wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
      };
    } catch (_e) {
      packageSavedState = { cart: [], wishlist: [] };
    }
    renderPackageSavedDrawer();
  }

  async function loadPackageAlerts() {
    try {
      const res = await fetch("/api/group-buy/join-requests/inbox", {
        credentials: "include",
      });
      if (res.status === 401) {
        packageAlertState = [];
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      packageAlertState = Array.isArray(data) ? data : [];
    } catch (_e) {
      packageAlertState = [];
    }
  }

  async function decidePackageAlert(requestId, action) {
    const res = await fetch(
      `/api/group-buy/join-requests/${Number(requestId)}/decision`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadPackageAlerts();
  }

  async function removePackageAlert(requestId) {
    const res = await fetch(
      `/api/group-buy/join-requests/${Number(requestId)}`,
      {
        method: "DELETE",
        credentials: "include",
      },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    packageAlertState = (packageAlertState || []).filter(
      (x) => Number(x?.id) !== Number(requestId),
    );
  }

  function ensurePackageAlertsTab() {
    const tabsWrap = document.querySelector(".package-saved-tabs");
    if (!tabsWrap) return null;
    let alertTab = tabsWrap.querySelector('[data-package-saved-tab="alerts"]');
    if (!alertTab) {
      alertTab = document.createElement("button");
      alertTab.type = "button";
      alertTab.id = "packageSavedTabAlerts";
      alertTab.className = "package-saved-tab";
      alertTab.setAttribute("data-package-saved-tab", "alerts");
      alertTab.setAttribute("aria-selected", "false");
      alertTab.textContent = "알림";
      tabsWrap.appendChild(alertTab);
    }
    return alertTab;
  }

  function updateWishlistButtons() {
    const wishlistNames = new Set(
      (packageSavedState.wishlist || []).map((item) => item?.name),
    );
    document.querySelectorAll(".package-wishlist-btn").forEach((btn) => {
      const payload = parsePayload(btn.dataset.savePayload);
      const inWishlist = !!payload && wishlistNames.has(payload.name);
      const color = inWishlist ? "#ff5252" : "#bbb";
      btn.innerHTML = `<span class='wishlist-icon' style='font-size:22px;color:${color};'>&hearts;</span>`;
      btn.classList.toggle("in-wishlist", inWishlist);

      btn.onmouseenter = function () {
        const icon = btn.querySelector(".wishlist-icon");
        if (icon) icon.style.color = "#ff5252";
      };
      btn.onmouseleave = function () {
        const icon = btn.querySelector(".wishlist-icon");
        if (icon)
          icon.style.color = btn.classList.contains("in-wishlist")
            ? "#ff5252"
            : "#bbb";
      };
    });
  }

  function updateCartButtons() {
    const cartNames = new Set(
      (packageSavedState.cart || []).map((item) => item?.name),
    );
    document.querySelectorAll(".package-cart-btn").forEach((btn) => {
      const payload = parsePayload(btn.dataset.savePayload);
      const inCart = !!payload && cartNames.has(payload.name);
      btn.textContent = inCart ? CART_IN_LABEL : CART_LABEL;
      btn.classList.toggle("in-cart", inCart);
    });
  }

  function buildSavePayload(rawPayload, listType, buttonEl = null) {
    const payload = parsePayload(rawPayload);
    const ctx = getCardContext(buttonEl);
    const name = String(payload?.name || ctx.title || "").trim();
    if (!name) return null;

    const payloadBody =
      payload?.payload && typeof payload.payload === "object"
        ? payload.payload
        : {};
    const meta = [ctx.location, ctx.priceText].filter(Boolean).join(" | ");
    const normalizedPayload = {
      ...payloadBody,
      name,
      image: String(
        payloadBody?.image || payload?.image || ctx.image || "",
      ).trim(),
      image_url: String(
        payloadBody?.image_url || payload?.image_url || ctx.image || "",
      ).trim(),
      location: String(
        payloadBody?.location || payload?.location || ctx.location || "",
      ).trim(),
      price_text: String(
        payloadBody?.price_text || payload?.price_text || ctx.priceText || "",
      ).trim(),
      detail_url: String(
        payloadBody?.detail_url || payload?.detail_url || ctx.href || "",
      ).trim(),
    };

    return {
      ...(typeof payload === "object" ? payload : {}),
      list_type: listType,
      item_type: "package",
      source: payload?.source || "package",
      meta: payload?.meta || meta,
      payload: normalizedPayload,
      name,
    };
  }

  async function addToWishlist(rawPayload, buttonEl = null) {
    if (!isLoggedIn()) return requireLoginMessage();
    const payload = buildSavePayload(rawPayload, "wishlist", buttonEl);
    if (!payload) return;

    const exists = (packageSavedState.wishlist || []).some(
      (item) => item?.name === payload.name,
    );
    if (exists) return;

    try {
      await savedItemsApi("/api/saved-items", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadPackageSavedItems();
      updateWishlistButtons();
      renderPackageSavedDrawer();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  async function removeFromWishlist(rawPayload) {
    if (!isLoggedIn()) return requireLoginMessage();
    const name = payloadName(rawPayload);
    const row = (packageSavedState.wishlist || []).find(
      (item) => item?.name === name,
    );
    if (!row) return;

    try {
      await savedItemsApi(`/api/saved-items/${row.id}`, {
        method: "DELETE",
        headers: {},
      });
      await loadPackageSavedItems();
      updateWishlistButtons();
      renderPackageSavedDrawer();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  async function addToCart(rawPayload, buttonEl = null) {
    if (!isLoggedIn()) return requireLoginMessage();
    const payload = buildSavePayload(rawPayload, "cart", buttonEl);
    if (!payload) return;

    const exists = (packageSavedState.cart || []).some(
      (item) => item?.name === payload.name,
    );
    if (exists) return;

    try {
      await savedItemsApi("/api/saved-items", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadPackageSavedItems();
      updateCartButtons();
      renderPackageSavedDrawer();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  async function removeFromCart(rawPayload) {
    if (!isLoggedIn()) return requireLoginMessage();
    const name = payloadName(rawPayload);
    const row = (packageSavedState.cart || []).find(
      (item) => item?.name === name,
    );
    if (!row) return;

    try {
      await savedItemsApi(`/api/saved-items/${row.id}`, {
        method: "DELETE",
        headers: {},
      });
      await loadPackageSavedItems();
      updateCartButtons();
      renderPackageSavedDrawer();
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  function bindWishlistButtonEvents() {
    document.querySelectorAll(".package-wishlist-btn").forEach((btn) => {
      btn.onclick = async function (e) {
        e.preventDefault();
        const payload = parsePayload(btn.dataset.savePayload);
        if (!payload) return;
        const inWishlist = (packageSavedState.wishlist || []).some(
          (item) => item?.name === payload.name,
        );
        if (inWishlist) await removeFromWishlist(payload);
        else await addToWishlist(payload, btn);
      };
    });
  }

  function bindCartButtonEvents() {
    document.querySelectorAll(".package-cart-btn").forEach((btn) => {
      btn.onclick = async function (e) {
        e.preventDefault();
        const payload = parsePayload(btn.dataset.savePayload);
        if (!payload) return;
        const inCart = (packageSavedState.cart || []).some(
          (item) => item?.name === payload.name,
        );
        if (inCart) await removeFromCart(payload);
        else await addToCart(payload, btn);
      };
    });
  }

  function setPackageSavedDrawer(open) {
    const drawer = document.getElementById("packageSavedDrawer");
    const fab = document.getElementById("packageSavedFab");
    if (!drawer || !fab) return;
    drawer.classList.toggle("is-open", !!open);
    fab.classList.toggle("is-open", !!open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    fab.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function renderPackageSavedDrawer() {
    const listEl = document.getElementById("packageSavedList");
    const emptyEl = document.getElementById("packageSavedEmpty");
    const countEl = document.getElementById("packageSavedFabCount");
    const cartTab = document.getElementById("packageSavedTabCart");
    const wishlistTab = document.getElementById("packageSavedTabWishlist");
    const alertsTab = ensurePackageAlertsTab();
    if (!listEl || !emptyEl) return;

    [cartTab, wishlistTab, alertsTab].forEach((tab) => {
      if (!tab) return;
      const active =
        tab.getAttribute("data-package-saved-tab") === packageSavedDrawerTab;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });

    const total =
      (packageSavedState.cart?.length || 0) +
      (packageSavedState.wishlist?.length || 0) +
      (packageAlertState?.length || 0);
    if (countEl) {
      countEl.hidden = total === 0;
      countEl.textContent = String(total || 0);
    }

    if (packageSavedDrawerTab === "alerts") {
      listEl.innerHTML = "";
      emptyEl.style.display = packageAlertState.length ? "none" : "block";
      emptyEl.textContent = ALERT_EMPTY_LABEL;

      packageAlertState.forEach((alert) => {
        const li = document.createElement("li");
        li.className = "package-saved-item";
        const status = String(alert?.status || "pending");
        const statusLabel =
          status === "accepted"
            ? "수락됨"
            : status === "rejected"
              ? "거절됨"
              : "대기중";
        const incoming = String(alert?.direction || "incoming") !== "mine";
        li.innerHTML = `
          <div class="package-saved-item__type">알림</div>
          <div class="package-saved-item__name">${alert?.post_title || "공동구매 참여 요청"}</div>
          <div class="package-saved-item__meta">${alert?.requester_name || "사용자"} · ${statusLabel}</div>
          ${alert?.message ? `<div class="package-saved-item__meta">${alert.message}</div>` : ""}
          ${
            incoming && status === "pending"
              ? `
            <div style="display:flex;gap:6px;margin-top:8px;">
              <button type="button" data-package-alert-decision="accept" data-package-alert-id="${Number(alert?.id)}" style="padding:4px 8px;border-radius:8px;border:1px solid #a7f3d0;background:#ecfdf5;color:#065f46;font-size:12px;font-weight:700;">수락</button>
              <button type="button" data-package-alert-decision="reject" data-package-alert-id="${Number(alert?.id)}" style="padding:4px 8px;border-radius:8px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;font-size:12px;font-weight:700;">거절</button>
            </div>
          `
              : ""
          }
          ${status !== "pending" ? `<button type="button" class="package-saved-item__remove" data-package-alert-remove="${Number(alert?.id)}" title="삭제">×</button>` : ""}
        `;
        listEl.appendChild(li);
      });
      return;
    }

    const items = Array.isArray(packageSavedState[packageSavedDrawerTab])
      ? packageSavedState[packageSavedDrawerTab]
      : [];

    listEl.innerHTML = "";
    emptyEl.style.display = items.length ? "none" : "block";
    emptyEl.textContent =
      packageSavedDrawerTab === "cart"
        ? CART_EMPTY_LABEL
        : WISHLIST_EMPTY_LABEL;

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "package-saved-item";
      const thumb =
        item?.payload?.thumb_url ||
        item?.payload?.image_url ||
        item?.payload?.image ||
        item?.image_url ||
        item?.image ||
        "";
      let price = "";
      const metaLines = [];
      if (item.meta) {
        const parts = String(item.meta)
          .split("|")
          .map((x) => x.trim())
          .filter(Boolean);
        const detected = parts.find((p) => normalizeKrwPriceText(p));
        price = normalizeKrwPriceText(detected || "");
        metaLines.push(
          ...parts.filter(
            (p) =>
              p !== detected &&
              !/[\d,]+(?:\.\d+)?\s*(krw|KRW|원|₩)?/.test(p),
          ),
        );
      }
      if (!price) {
        price = normalizeKrwPriceText(
          item?.price ||
          item?.payload?.price_text ||
          item?.payload?.price ||
          item?.payload?.amount ||
          item?.payload?.total_price ||
          ""
        );
      }
      const typeText = `${savedTypeLabel(item.item_type)} · ${item?.source || "saved-item"}`;
      li.innerHTML = `
        <div class="package-saved-thumb">
          ${thumb ? `<img src="${thumb.replace(/"/g, "&quot;")}" alt="썸네일" loading="lazy" onerror="this.remove()">` : ""}
        </div>
        <div class="package-saved-content">
          <div class="package-saved-item__type">${typeText}</div>
          <div class="package-saved-item__name">${item.name || "-"}</div>
          ${price ? `<div class="package-saved-line package-saved-price">${price}</div>` : ""}
          ${metaLines.map((line) => `<div class="package-saved-item__meta">${line}</div>`).join("")}
        </div>
        <button type="button" class="package-saved-item__remove" data-package-saved-remove="${item.id}" title="삭제">×</button>
      `;
      listEl.appendChild(li);
    });
  }

  function initPackageSavedDrawer() {
    const fab = document.getElementById("packageSavedFab");
    const drawer = document.getElementById("packageSavedDrawer");
    const listEl = document.getElementById("packageSavedList");
    const cartTab = document.getElementById("packageSavedTabCart");
    const wishlistTab = document.getElementById("packageSavedTabWishlist");
    const alertsTab = ensurePackageAlertsTab();
    if (!fab || !drawer) return;

    fab.addEventListener("click", () => {
      setPackageSavedDrawer(!drawer.classList.contains("is-open"));
    });

    document.querySelectorAll("[data-package-saved-close]").forEach((el) => {
      el.addEventListener("click", () => setPackageSavedDrawer(false));
    });

    cartTab?.addEventListener("click", () => {
      packageSavedDrawerTab = "cart";
      renderPackageSavedDrawer();
    });
    wishlistTab?.addEventListener("click", () => {
      packageSavedDrawerTab = "wishlist";
      renderPackageSavedDrawer();
    });
    alertsTab?.addEventListener("click", async () => {
      packageSavedDrawerTab = "alerts";
      await loadPackageAlerts();
      renderPackageSavedDrawer();
    });

    listEl?.addEventListener("click", async (e) => {
      const decisionBtn = e.target.closest("[data-package-alert-decision]");
      if (decisionBtn) {
        const requestId = Number(
          decisionBtn.getAttribute("data-package-alert-id"),
        );
        const action = decisionBtn.getAttribute("data-package-alert-decision");
        if (!requestId || !action) return;
        try {
          await decidePackageAlert(requestId, action);
          renderPackageSavedDrawer();
        } catch (_err) {}
        return;
      }

      const removeAlertBtn = e.target.closest("[data-package-alert-remove]");
      if (removeAlertBtn) {
        const requestId = Number(
          removeAlertBtn.getAttribute("data-package-alert-remove"),
        );
        if (!requestId) return;
        try {
          await removePackageAlert(requestId);
          renderPackageSavedDrawer();
        } catch (_err) {}
        return;
      }

      const btn = e.target.closest("[data-package-saved-remove]");
      if (!btn) return;
      const itemId = Number(btn.getAttribute("data-package-saved-remove"));
      if (Number.isNaN(itemId)) return;

      try {
        await savedItemsApi(`/api/saved-items/${itemId}`, {
          method: "DELETE",
          headers: {},
        });
        await loadPackageSavedItems();
        updateCartButtons();
        updateWishlistButtons();
      } catch (_err) {}
    });

    renderPackageSavedDrawer();
  }

  document.addEventListener("DOMContentLoaded", () => {
    initPackageSavedDrawer();
    Promise.all([loadPackageSavedItems(), loadPackageAlerts()]).then(() => {
      bindCartButtonEvents();
      updateCartButtons();
      bindWishlistButtonEvents();
      updateWishlistButtons();
      renderPackageSavedDrawer();
    });

    window.addEventListener("authchange", () => {
      Promise.all([loadPackageSavedItems(), loadPackageAlerts()]).then(() => {
        bindCartButtonEvents();
        updateCartButtons();
        bindWishlistButtonEvents();
        updateWishlistButtons();
        renderPackageSavedDrawer();
      });
    });

    if (window.lucide && lucide.createIcons) {
      lucide.createIcons();
    }
  });
})();

// package.js 하단 혹은 적절한 위치에 추가
document.addEventListener("DOMContentLoaded", () => {
  // 모든 패키지 카드를 찾습니다.
  const cards = document.querySelectorAll(".package-card");

  function extractProduct(card, index) {
    return {
      id: `pack_${index + 1}`,
      name: card.querySelector(".package-name").innerText,
      price: card.querySelector(".price-val").innerText.replace(/[^0-9]/g, ""),
      location: card.querySelector(".package-loc").innerText,
      image: getComputedStyle(card.querySelector(".package-image")).backgroundImage.replace(
        /url\(['"]?(.*?)['"]?\)/i,
        "$1",
      ),
    };
  }

  cards.forEach((card, index) => {
    card.addEventListener("click", function (e) {
      // 장바구니나 찜 버튼을 눌렀을 때는 상세페이지로 이동하지 않도록 방지
      if (e.target.closest("button")) return;

      // 기본 <a> 태그 이동을 막고 JS로 제어
      e.preventDefault();
      goToDetail(extractProduct(this, index));
    });

    // 예약하기 버튼도 동일 파라미터로 상세 이동
    const payBtn = card.querySelector(".package-pay-btn");
    if (payBtn) {
      payBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        goToDetail(extractProduct(card, index));
      });
    }
  });
});

// 기존에 작성하신 함수 (그대로 유지)
function goToDetail(product) {
  const params = new URLSearchParams({
    id: product.id,
    title: product.name,
    price: product.price,
    img: product.image,
    loc: product.location,
    category: "package",
  });
  // .html 확장자가 붙어있는지 확인하세요 (파일 구조에 따라 수정)
  location.href = `/pack-detail?${params.toString()}`;
}
