// ?„ì‹œë¦¬ìŠ¤??ë²„íŠ¼ ?íƒœ ?…ë°?´íŠ¸
function updateWishlistButtons() {
  if (!packageSavedState || !packageSavedState.wishlist) return;
  const wishlistNames = packageSavedState.wishlist.map((item) => item.name);
  document.querySelectorAll(".package-wishlist-btn").forEach((btn) => {
    let payload;
    try {
      payload = JSON.parse(btn.dataset.savePayload);
    } catch {
      payload = btn.dataset.savePayload;
    }
    const isInWishlist =
      typeof payload === "object"
        ? wishlistNames.includes(payload.name)
        : wishlistNames.includes(payload);
    // ?˜íŠ¸ ?„ì´ì½˜ë§Œ ?œì‹œ (airport ?¤í???
    // ê¸°ë³¸ ?Œìƒ‰, in-wishlist???Œë§Œ ë¹¨ê°„??    let color = btn.classList.contains("in-wishlist") ? "#ff5252" : "#bbb";
    btn.innerHTML = `<span class='wishlist-icon' style='font-size:22px;color:${color};'>??/span>`;
    // ë§ˆìš°???¤ë²„ ??ë¹¨ê°„?? ?„ë‹ˆë©??ë˜ ?‰ìƒ
    btn.onmouseenter = function () {
      btn.querySelector(".wishlist-icon").style.color = "#ff5252";
    };
    btn.onmouseleave = function () {
      let leaveColor = btn.classList.contains("in-wishlist")
        ? "#ff5252"
        : "#bbb";
      btn.querySelector(".wishlist-icon").style.color = leaveColor;
    };
    if (!isLoggedIn()) {
      btn.classList.remove("in-wishlist");
    } else if (isInWishlist) {
      btn.classList.add("in-wishlist");
    } else {
      btn.classList.remove("in-wishlist");
    }
  });
}

async function addToWishlist(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const wishlistNames = packageSavedState.wishlist.map((item) => item.name);
  if (wishlistNames.includes(name)) {
    return;
  }
  try {
    const res = await fetch("/api/saved-items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(
        typeof payload === "object"
          ? { ...payload, list_type: "wishlist", item_type: "package" }
          : {
              list_type: "wishlist",
              item_type: "package",
              name: payload,
              meta: "",
              source: "",
              payload: {},
            },
      ),
    });
    if (res.status === 401) {
      if (
        confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateWishlistButtons();
    packageSavedDrawerTab = "wishlist";
    // keep drawer closed on add/remove
    renderPackageSavedDrawer();
  } catch (e) {
  }
}

async function removeFromWishlist(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const wishlistItem = packageSavedState.wishlist.find(
    (item) => item.name === name,
  );
  if (!wishlistItem) {
    return;
  }
  try {
    const res = await fetch(`/api/saved-items/${wishlistItem.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.status === 401) {
      if (
        confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateWishlistButtons();
  } catch (e) {
  }
}

function bindWishlistButtonEvents() {
  document.querySelectorAll(".package-wishlist-btn").forEach((btn) => {
    btn.onclick = async function (e) {
      e.preventDefault();
      let payload;
      try {
        payload = JSON.parse(btn.dataset.savePayload);
      } catch {
        payload = btn.dataset.savePayload;
      }
      if (!isLoggedIn()) {
        if (
          confirm(
            "ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??",
          )
        ) {
          location.href = "/login";
        }
        return;
      }
      const wishlistNames = packageSavedState.wishlist.map((item) => item.name);
      const isInWishlist =
        typeof payload === "object"
          ? wishlistNames.includes(payload.name)
          : wishlistNames.includes(payload);
      if (isInWishlist) {
        await removeFromWishlist(payload);
      } else {
        await addToWishlist(payload);
      }
      updateWishlistButtons();
    };
  });
}
// ?¤ë¥¸ìª??˜ë‹¨ drawer ê¸°ëŠ¥ (airport?€ ?™ì¼?˜ê²Œ)
let packageSavedDrawerTab = "cart"; // 'cart' ?ëŠ” 'wishlist'
let packageSavedState = { cart: [], wishlist: [] };
// ...existing code...

// ?í’ˆ ì¹´ë“œ ?¥ë°”êµ¬ë‹ˆ ë²„íŠ¼ ê¸°ëŠ¥ ë³µêµ¬
function updateCartButtons() {
  // packageSavedStateê°€ undefined??ê²½ìš° ë°©ì?
  if (!packageSavedState || !packageSavedState.cart) return;
  const cartNames = packageSavedState.cart.map((item) => item.name);
  document.querySelectorAll(".package-cart-btn").forEach((btn) => {
    let payload;
    try {
      payload = JSON.parse(btn.dataset.savePayload);
    } catch {
      payload = btn.dataset.savePayload;
    }
    const isInCart =
      typeof payload === "object"
        ? cartNames.includes(payload.name)
        : cartNames.includes(payload);
    if (!isLoggedIn()) {
      btn.textContent = "?¥ë°”êµ¬ë‹ˆ";
      btn.classList.remove("in-cart");
    } else if (isInCart) {
      btn.textContent = "?´ê?";
      btn.classList.add("in-cart");
    } else {
      btn.textContent = "?¥ë°”êµ¬ë‹ˆ";
      btn.classList.remove("in-cart");
    }
  });
}

async function addToCart(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const cartNames = packageSavedState.cart.map((item) => item.name);
  if (cartNames.includes(name)) {
    return;
  }
  try {
    const res = await fetch("/api/saved-items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(
        typeof payload === "object"
          ? { ...payload, list_type: "cart", item_type: "package" }
          : {
              list_type: "cart",
              item_type: "package",
              name: payload,
              meta: "",
              source: "",
              payload: {},
            },
      ),
    });
    if (res.status === 401) {
      if (
        confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateCartButtons();
  } catch (e) {
  }
}

async function removeFromCart(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const cartItem = packageSavedState.cart.find((item) => item.name === name);
  if (!cartItem) {
    return;
  }
  try {
    const res = await fetch(`/api/saved-items/${cartItem.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.status === 401) {
      if (
        confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateCartButtons();
  } catch (e) {
  }
}
function bindCartButtonEvents() {
  document.querySelectorAll(".package-cart-btn").forEach((btn) => {
    btn.onclick = async function (e) {
      e.preventDefault();
      let payload;
      try {
        payload = JSON.parse(btn.dataset.savePayload);
      } catch {
        payload = btn.dataset.savePayload;
      }
      if (!isLoggedIn()) {
        if (
          confirm(
            "ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??",
          )
        ) {
          location.href = "/login";
        }
        return;
      }
      const cartNames = packageSavedState.cart.map((item) => item.name);
      const isInCart =
        typeof payload === "object"
          ? cartNames.includes(payload.name)
          : cartNames.includes(payload);
      if (isInCart) {
        await removeFromCart(payload);
      } else {
        await addToCart(payload);
      }
      updateCartButtons();
    };
  });
}
document.addEventListener("DOMContentLoaded", () => {
  bindCartButtonEvents();
  updateCartButtons();
});
window.addEventListener("authchange", () => {
  loadPackageSavedItems().then(() => {
    bindCartButtonEvents();
    updateCartButtons();
  });
});
updateCartButtons();

// ?¤ë¥¸ìª??˜ë‹¨ drawer ê¸°ëŠ¥ (airport?€ ?™ì¼?˜ê²Œ)
// ...existing code...

function bindCartButtonEvents() {
  document.querySelectorAll(".package-cart-btn").forEach((btn) => {
    btn.onclick = async function (e) {
      e.preventDefault();
      if (!isLoggedIn()) {
        return;
      }
      const payload = btn.dataset.savePayload;
      const cartNames = packageSavedState.cart.map((item) => item.name);
      if (cartNames.includes(payload)) {
        await removeFromCart(payload);
      } else {
        await addToCart(payload);
      }
      updateCartButtons();
    };
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindCartButtonEvents();
  updateCartButtons();
});

window.addEventListener("authchange", () => {
  loadPackageSavedItems();
  bindCartButtonEvents();
  updateCartButtons();
});

function isLoggedIn() {
  return (
    typeof window.__AUTH__ !== "undefined" &&
    window.__AUTH__ !== null &&
    window.__AUTH__ !== ""
  );
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

function requireLoginMessage() {
  if (
    confirm("ë¡œê·¸?????´ìš© ê°€?¥í•œ ê¸°ëŠ¥?…ë‹ˆ?? ë¡œê·¸???˜ì´ì§€ë¡??´ë™? ê¹Œ??")
  ) {
    location.href = "/login";
  }
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
  } catch (e) {
    packageSavedState = { cart: [], wishlist: [] };
  }
  renderPackageSavedDrawer();
}

function setPackageSavedDrawer(open) {
  const drawer = document.getElementById("packageSavedDrawer");
  const fab = document.getElementById("packageSavedFab");
  if (!drawer || !fab) return;
  drawer.classList.toggle("is-open", !!open);
  drawer.setAttribute("aria-hidden", open ? "false" : "true");
  fab.setAttribute("aria-expanded", open ? "true" : "false");
}

function renderPackageSavedDrawer() {
  const listEl = document.getElementById("packageSavedList");
  const emptyEl = document.getElementById("packageSavedEmpty");
  const countEl = document.getElementById("packageSavedFabCount");
  const cartTab = document.getElementById("packageSavedTabCart");
  const wishlistTab = document.getElementById("packageSavedTabWishlist");
  if (!listEl || !emptyEl) return;
  // tab state
  // tab state
  if (cartTab) {
    if (packageSavedDrawerTab === "cart") {
      cartTab.classList.add("is-active");
      cartTab.setAttribute("aria-selected", "true");
    } else {
      cartTab.classList.remove("is-active");
      cartTab.setAttribute("aria-selected", "false");
    }
  }
  if (wishlistTab) {
    if (packageSavedDrawerTab === "wishlist") {
      wishlistTab.classList.add("is-active");
      wishlistTab.setAttribute("aria-selected", "true");
    } else {
      wishlistTab.classList.remove("is-active");
      wishlistTab.setAttribute("aria-selected", "false");
    }
  }
  // ?„ì´???Œë”ë§?  // FAB count: ?¥ë°”êµ¬ë‹ˆ+?„ì‹œë¦¬ìŠ¤???„ì²´ ?©ê³„
  const cartCount = Array.isArray(packageSavedState.cart)
    ? packageSavedState.cart.length
    : 0;
  const wishlistCount = Array.isArray(packageSavedState.wishlist)
    ? packageSavedState.wishlist.length
    : 0;
  const total = cartCount + wishlistCount;
  if (countEl) {
    countEl.hidden = total === 0;
    countEl.textContent = String(total || 0);
  }
  // current tab items
  const items = Array.isArray(packageSavedState[packageSavedDrawerTab])
    ? packageSavedState[packageSavedDrawerTab]
    : [];
  listEl.innerHTML = "";
  emptyEl.style.display = items.length ? "none" : "block";
  emptyEl.textContent =
    packageSavedDrawerTab === "cart"
      ? "?¥ë°”êµ¬ë‹ˆ ??ª©???†ìŠµ?ˆë‹¤."
      : "?„ì‹œë¦¬ìŠ¤????ª©???†ìŠµ?ˆë‹¤.";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "flight-saved-item";
    const typeText = item.item_type || (packageSavedDrawerTab === "cart" ? "package" : "wishlist");
    const metaHtml = item.meta ? `<div class="flight-saved-item__meta">${item.meta}</div>` : "";
    li.innerHTML = `
                <div class="flight-saved-item__type">${typeText}</div>
                <div class="flight-saved-item__name">${item.name || "-"}</div>
                ${metaHtml}
                <button type="button" class="flight-saved-item__remove" data-package-saved-remove="${item.id}" title="remove">x</button>
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
  if (!fab || !drawer) return;
  fab.addEventListener("click", () => {
    setPackageSavedDrawer(!drawer.classList.contains("is-open"));
  });
  document.querySelectorAll("[data-package-saved-close]").forEach((el) => {
    el.addEventListener("click", () => setPackageSavedDrawer(false));
  });
  // tab click events
  cartTab?.addEventListener("click", () => {
    renderPackageSavedDrawer();
  });
  wishlistTab?.addEventListener("click", () => {
    packageSavedDrawerTab = "wishlist";
    renderPackageSavedDrawer();
  });
  // ?„ì´???? œ
  listEl?.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-package-saved-remove]");
    if (!btn) return;
    const itemId = Number(btn.getAttribute("data-package-saved-remove"));
    if (Number.isNaN(itemId)) return;
    try {
      await fetch(`/api/saved-items/${itemId}`, {
        method: "DELETE",
        credentials: "include",
      });
      await loadPackageSavedItems();
      updateCartButtons();
      updateWishlistButtons();
    } catch (err) {
    }
  });
  renderPackageSavedDrawer();
}

document.addEventListener("DOMContentLoaded", () => {
  initPackageSavedDrawer();
  loadPackageSavedItems().then(() => {
    bindCartButtonEvents();
    updateCartButtons();
    bindWishlistButtonEvents();
    updateWishlistButtons();
  });
  window.addEventListener("authchange", () => {
    loadPackageSavedItems().then(() => {
      bindCartButtonEvents();
      updateCartButtons();
      bindWishlistButtonEvents();
      updateWishlistButtons();
    });
  });
});
lucide.createIcons();

// ...existing code...
