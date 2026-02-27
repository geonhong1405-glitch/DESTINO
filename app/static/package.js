// 위시리스트 버튼 상태 업데이트
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
    // 하트 아이콘만 표시 (airport 스타일)
    // 기본 회색, in-wishlist일 때만 빨간색
    let color = btn.classList.contains("in-wishlist") ? "#ff5252" : "#bbb";
    btn.innerHTML = `<span class='wishlist-icon' style='font-size:22px;color:${color};'>♥</span>`;
    // 마우스 오버 시 빨간색, 아니면 원래 색상
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
      confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const wishlistNames = packageSavedState.wishlist.map((item) => item.name);
  if (wishlistNames.includes(name)) {
    alert("이미 위시리스트에 있습니다.");
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
        confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateWishlistButtons();
    packageSavedDrawerTab = "wishlist";
    setPackageSavedDrawer(true);
    renderPackageSavedDrawer();
    alert("위시리스트에 저장했습니다!");
  } catch (e) {
    alert("저장 실패");
  }
}

async function removeFromWishlist(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
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
    alert("위시리스트에 없습니다.");
    return;
  }
  try {
    const res = await fetch(`/api/saved-items/${wishlistItem.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.status === 401) {
      if (
        confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateWishlistButtons();
    alert("위시리스트에서 제거했습니다.");
  } catch (e) {
    alert("제거 실패");
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
            "로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?",
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
// 오른쪽 하단 drawer 기능 (airport와 동일하게)
let packageSavedDrawerTab = "cart"; // 'cart' 또는 'wishlist'
let packageSavedState = { cart: [], wishlist: [] };
// ...existing code...

// 상품 카드 장바구니 버튼 기능 복구
function updateCartButtons() {
  // packageSavedState가 undefined일 경우 방지
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
      btn.textContent = "장바구니";
      btn.classList.remove("in-cart");
    } else if (isInCart) {
      btn.textContent = "담김";
      btn.classList.add("in-cart");
    } else {
      btn.textContent = "장바구니";
      btn.classList.remove("in-cart");
    }
  });
}

async function addToCart(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const cartNames = packageSavedState.cart.map((item) => item.name);
  if (cartNames.includes(name)) {
    alert("이미 장바구니에 있습니다.");
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
        confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateCartButtons();
    alert("장바구니에 담았습니다!");
  } catch (e) {
    alert("담기 실패");
  }
}

async function removeFromCart(payload) {
  if (!isLoggedIn()) {
    if (
      confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
    ) {
      location.href = "/login";
    }
    return;
  }
  let name = typeof payload === "object" ? payload.name : payload;
  const cartItem = packageSavedState.cart.find((item) => item.name === name);
  if (!cartItem) {
    alert("장바구니에 없습니다.");
    return;
  }
  try {
    const res = await fetch(`/api/saved-items/${cartItem.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.status === 401) {
      if (
        confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
      ) {
        location.href = "/login";
      }
      return;
    }
    await loadPackageSavedItems();
    updateCartButtons();
    alert("장바구니에서 제거했습니다.");
  } catch (e) {
    alert("제거 실패");
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
            "로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?",
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

// 오른쪽 하단 drawer 기능 (airport와 동일하게)
// ...existing code...

function bindCartButtonEvents() {
  document.querySelectorAll(".package-cart-btn").forEach((btn) => {
    btn.onclick = async function (e) {
      e.preventDefault();
      if (!isLoggedIn()) {
        alert("로그인 후 이용 가능합니다.");
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
    confirm("로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?")
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
  // 탭 활성화
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
  // 아이템 렌더링
  // FAB count: 장바구니+위시리스트 전체 합계
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
  // 현재 탭 아이템만 렌더링
  const items = Array.isArray(packageSavedState[packageSavedDrawerTab])
    ? packageSavedState[packageSavedDrawerTab]
    : [];
  listEl.innerHTML = "";
  emptyEl.style.display = items.length ? "none" : "block";
  emptyEl.textContent =
    packageSavedDrawerTab === "cart"
      ? "장바구니 항목이 없습니다."
      : "위시리스트 항목이 없습니다.";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = "flight-saved-item";
    li.innerHTML = `
                <div class="flight-saved-item__type">${item.item_type || (packageSavedDrawerTab === "cart" ? "패키지" : "위시리스트")}</div>
                <div class="flight-saved-item__name">${item.name || "-"}</div>
                ${item.meta ? `<div class="flight-saved-item__meta">${item.meta}</div>` : ""}
                <button type="button" class="flight-saved-item__remove" data-package-saved-remove="${item.id}" title="삭제">×</button>
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
  // 탭 클릭 이벤트
  cartTab?.addEventListener("click", () => {
    packageSavedDrawerTab = "cart";
    renderPackageSavedDrawer();
  });
  wishlistTab?.addEventListener("click", () => {
    packageSavedDrawerTab = "wishlist";
    renderPackageSavedDrawer();
  });
  // 아이템 삭제
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
      alert("삭제 중 오류가 발생했습니다.");
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
