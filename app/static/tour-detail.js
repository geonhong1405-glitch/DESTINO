(() => {
  const LOGIN_CONFIRM_MESSAGE = "로그인 후 이용 가능한 기능입니다. 로그인 페이지로 이동할까요?";
  const LIST_TYPES = ["cart", "wishlist"];

  let savedItemState = { wishlist: [], cart: [] };
  let alertState = [];
  let drawerTab = "cart";
  let prices = { adult: 0, child: 0 };
  let quantities = { adult: 1, child: 0 };
  let currentRating = 0;

  function isUserLoggedIn() {
    if (typeof window.isLoggedIn === "boolean") return window.isLoggedIn;
    if (typeof window.isLoggedIn === "string") {
      const v = window.isLoggedIn.toLowerCase().trim();
      if (v === "true" || v === "1") return true;
      if (v === "false" || v === "0") return false;
    }
    if (document.querySelector('a[href="/logout"]')) return true;
    if (document.querySelector('a[href="/mypage"] span')) return true;
    return false;
  }

  function requireLoginMessage() {
    if (confirm(LOGIN_CONFIRM_MESSAGE)) {
      location.href = "/login";
    }
  }

  function loadTossPaymentsScript() {
    if (window.TossPayments) return Promise.resolve(window.TossPayments);
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-toss-sdk="1"]');
      if (existing) {
        existing.addEventListener("load", () => resolve(window.TossPayments));
        existing.addEventListener("error", reject);
        return;
      }
      const s = document.createElement("script");
      s.src = "https://js.tosspayments.com/v1/payment";
      s.async = true;
      s.dataset.tossSdk = "1";
      s.onload = () => resolve(window.TossPayments);
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  function normalizeText(v) {
    return String(v || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function getItemKey(item) {
    return `${normalizeText(item?.name)}__${normalizeText(item?.meta)}`;
  }

  function getCurrentProductInfo() {
    const title = (document.querySelector("h2.text-2xl.font-black")?.innerText || "").trim();
    const locRaw = document.querySelector(".fa-location-dot")?.parentElement?.innerText || "";
    const location = locRaw.replace(/\s+/g, " ").replace(/^\s*[^\s]+\s*/g, "").trim();
    const priceText = (document.getElementById("productPrice")?.innerText || "0").replace(/[^\d]/g, "");
    const image = document.getElementById("productImg")?.getAttribute("src") || "";

    return {
      item_type: "ticket",
      source: "tour-detail",
      name: title || "투어 상품",
      meta: location,
      price: Number(priceText || 0),
      image,
      payload: {
        title: title || "투어 상품",
        location,
        price_text: Number(priceText || 0).toLocaleString("ko-KR"),
        image,
      },
    };
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

  async function loadSavedItems() {
    if (!isUserLoggedIn()) {
      savedItemState = { wishlist: [], cart: [] };
      renderSavedDrawer();
      updateActionButtons();
      return;
    }

    try {
      const data = await savedItemsApi("/api/saved-items", { method: "GET", headers: {} });
      savedItemState = {
        wishlist: Array.isArray(data?.wishlist) ? data.wishlist : [],
        cart: Array.isArray(data?.cart) ? data.cart : [],
      };
    } catch (_e) {
      savedItemState = { wishlist: [], cart: [] };
    }

    renderSavedDrawer();
    updateActionButtons();
  }

  async function loadAlerts() {
    if (!isUserLoggedIn()) {
      alertState = [];
      return;
    }
    try {
      const res = await fetch("/api/group-buy/join-requests/inbox", { credentials: "include" });
      if (!res.ok) {
        alertState = [];
        return;
      }
      const data = await res.json();
      alertState = Array.isArray(data) ? data : [];
    } catch (_e) {
      alertState = [];
    }
  }

  async function decideAlert(requestId, action) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}/decision`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadAlerts();
  }

  async function removeAlert(requestId) {
    const res = await fetch(`/api/group-buy/join-requests/${Number(requestId)}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    alertState = (alertState || []).filter((x) => Number(x?.id) !== Number(requestId));
  }

  function updateActionButtons() {
    const wishBtn = document.getElementById("wishBtn");
    const cartBtn = document.getElementById("cartBtn");
    if (!wishBtn || !cartBtn) return;

    const current = getCurrentProductInfo();
    const key = getItemKey(current);

    const inWishlist = (savedItemState.wishlist || []).some((x) => getItemKey(x) === key);
    const inCart = (savedItemState.cart || []).some((x) => getItemKey(x) === key);

    wishBtn.classList.toggle("text-red-500", inWishlist);
    wishBtn.classList.toggle("bg-red-50", inWishlist);
    wishBtn.classList.toggle("border-red-100", inWishlist);

    cartBtn.classList.toggle("text-blue-600", inCart);
    cartBtn.classList.toggle("bg-blue-50", inCart);
    cartBtn.classList.toggle("border-blue-100", inCart);
  }

  function setSavedDrawer(open) {
    const drawer = document.getElementById("flightSavedDrawer");
    const fab = document.getElementById("flightSavedFab");
    if (!drawer || !fab) return;
    drawer.classList.toggle("is-open", !!open);
    drawer.setAttribute("aria-hidden", open ? "false" : "true");
    fab.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function renderSavedDrawer() {
    const listEl = document.getElementById("flightSavedList");
    const emptyEl = document.getElementById("flightSavedEmpty");
    const countEl = document.getElementById("flightSavedFabCount");
    const tabs = Array.from(document.querySelectorAll("[data-flight-saved-tab]"));
    if (!listEl || !emptyEl) return;

    const total =
      (savedItemState.cart?.length || 0) +
      (savedItemState.wishlist?.length || 0) +
      (alertState?.length || 0);

    if (countEl) {
      countEl.hidden = total === 0;
      countEl.textContent = String(total || 0);
    }

    tabs.forEach((btn) => {
      const active = btn.getAttribute("data-flight-saved-tab") === drawerTab;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    if (drawerTab === "alerts") {
      listEl.innerHTML = "";
      emptyEl.style.display = alertState.length ? "none" : "block";
      emptyEl.textContent = "도착한 참여 요청 알림이 없습니다.";

      alertState.forEach((a) => {
        const status = String(a?.status || "pending");
        const statusLabel = status === "accepted" ? "수락됨" : status === "rejected" ? "거절됨" : "대기중";
        const incoming = String(a?.direction || "incoming") !== "mine";

        const li = document.createElement("li");
        li.className = "flight-saved-item";
        li.innerHTML = `
          <div class="flight-saved-item__type">알림</div>
          <div class="flight-saved-item__name">${a?.post_title || "공동구매 참여 요청"}</div>
          <div class="flight-saved-item__meta">${a?.requester_name || "사용자"} | ${statusLabel}</div>
          ${a?.message ? `<div class="flight-saved-item__meta">${a.message}</div>` : ""}
          ${incoming && status === "pending" ? `
            <div style="display:flex;gap:6px;margin-top:8px;">
              <button type="button" data-alert-decision="accept" data-alert-id="${Number(a?.id)}" style="padding:4px 8px;border-radius:8px;border:1px solid #a7f3d0;background:#ecfdf5;color:#065f46;font-size:12px;font-weight:700;">수락</button>
              <button type="button" data-alert-decision="reject" data-alert-id="${Number(a?.id)}" style="padding:4px 8px;border-radius:8px;border:1px solid #fecaca;background:#fef2f2;color:#991b1b;font-size:12px;font-weight:700;">거절</button>
            </div>
          ` : ""}
          ${status !== "pending" ? `<button type="button" class="flight-saved-item__remove" data-alert-remove="${Number(a?.id)}" title="삭제">&times;</button>` : ""}
        `;
        listEl.appendChild(li);
      });
      return;
    }

    const items = Array.isArray(savedItemState[drawerTab]) ? savedItemState[drawerTab] : [];
    listEl.innerHTML = "";
    emptyEl.style.display = items.length ? "none" : "block";
    emptyEl.textContent = drawerTab === "wishlist" ? "위시리스트 항목이 없습니다." : "장바구니 항목이 없습니다.";

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "flight-saved-item";
      li.innerHTML = `
        <div class="flight-saved-item__type">${item.item_type || "ticket"}</div>
        <div class="flight-saved-item__name">${item.name || "-"}</div>
        <div class="flight-saved-item__meta">${item.meta || ""}</div>
        <button type="button" class="flight-saved-item__remove" data-flight-saved-remove="${Number(item.id)}" title="삭제">&times;</button>
      `;
      listEl.appendChild(li);
    });
  }

  function initSavedDrawer() {
    const fab = document.getElementById("flightSavedFab");
    const drawer = document.getElementById("flightSavedDrawer");
    const listEl = document.getElementById("flightSavedList");
    if (!fab || !drawer) return;

    fab.addEventListener("click", async () => {
      const nextOpen = !drawer.classList.contains("is-open");
      setSavedDrawer(nextOpen);
      if (nextOpen) {
        await Promise.all([loadSavedItems(), loadAlerts()]);
        renderSavedDrawer();
      }
    });

    document.querySelectorAll("[data-flight-saved-close]").forEach((el) => {
      el.addEventListener("click", () => setSavedDrawer(false));
    });

    document.querySelectorAll("[data-flight-saved-tab]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        drawerTab = btn.getAttribute("data-flight-saved-tab") || "cart";
        if (drawerTab === "alerts") await loadAlerts();
        renderSavedDrawer();
      });
    });

    listEl?.addEventListener("click", async (e) => {
      const decisionBtn = e.target.closest("[data-alert-decision]");
      if (decisionBtn) {
        const id = Number(decisionBtn.getAttribute("data-alert-id"));
        const action = decisionBtn.getAttribute("data-alert-decision");
        if (!id || !action) return;
        try {
          await decideAlert(id, action);
          renderSavedDrawer();
        } catch (_e) {}
        return;
      }

      const removeAlertBtn = e.target.closest("[data-alert-remove]");
      if (removeAlertBtn) {
        const id = Number(removeAlertBtn.getAttribute("data-alert-remove"));
        if (!id) return;
        try {
          await removeAlert(id);
          renderSavedDrawer();
        } catch (_e) {}
        return;
      }

      const removeBtn = e.target.closest("[data-flight-saved-remove]");
      if (!removeBtn) return;
      const itemId = Number(removeBtn.getAttribute("data-flight-saved-remove"));
      if (!itemId) return;

      try {
        await savedItemsApi(`/api/saved-items/${itemId}`, { method: "DELETE", headers: {} });
        await loadSavedItems();
      } catch (_e) {}
    });

    renderSavedDrawer();
  }

  async function toggleListItem(listType) {
    if (!isUserLoggedIn()) return requireLoginMessage();

    const current = getCurrentProductInfo();
    const key = getItemKey(current);
    const row = (savedItemState[listType] || []).find((x) => getItemKey(x) === key);

    try {
      if (row?.id) {
        await savedItemsApi(`/api/saved-items/${row.id}`, { method: "DELETE", headers: {} });
      } else {
        await savedItemsApi("/api/saved-items", {
          method: "POST",
          body: JSON.stringify({
            list_type: listType,
            item_type: "ticket",
            name: current.name,
            meta: current.meta,
            source: "tour-detail",
            payload: current.payload,
          }),
        });
      }
      await loadSavedItems();
      showToast(listType === "wishlist" ? "위시리스트를 업데이트했습니다." : "장바구니를 업데이트했습니다.");
    } catch (e) {
      if (e?.code === "LOGIN_REQUIRED") requireLoginMessage();
    }
  }

  function toggleWish() {
    toggleListItem("wishlist");
  }

  function addToCart() {
    toggleListItem("cart");
  }

  function initProductFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const title = params.get("title") || "투어 상품";
    const priceText = params.get("price") || "0";
    const img = params.get("img") || "";
    const loc = params.get("loc") || "";

    const titleEl = document.querySelector("h2.text-2xl.font-black");
    if (titleEl) titleEl.innerText = title;

    const breadcrumbEl = document.querySelector("nav span.text-gray-900");
    if (breadcrumbEl) breadcrumbEl.innerText = title;

    const imgEl = document.getElementById("productImg");
    if (imgEl && img) imgEl.src = img;

    const locEl = document.querySelector(".fa-location-dot")?.parentElement;
    if (locEl && loc) locEl.innerHTML = `<i class="fa-solid fa-location-dot"></i> ${loc}`;

    const purePrice = parseInt(String(priceText).replace(/,/g, ""), 10) || 0;
    prices.adult = purePrice;
    prices.child = Math.floor(purePrice * 0.7);

    const productPriceEl = document.getElementById("productPrice");
    if (productPriceEl) productPriceEl.innerText = purePrice.toLocaleString("ko-KR");

    updateTotalPrice();
  }

  function changeQty(type, diff) {
    const next = Number(quantities[type] || 0) + Number(diff || 0);
    if (next < 0) return;
    if (type === "adult" && next === 0 && quantities.child > 0) {
      showToast("아동 동반 시 성인 1명 이상은 필수입니다.");
      return;
    }
    quantities[type] = next;
    const el = document.getElementById(`${type}Qty`);
    if (el) el.innerText = String(next);
    updateTotalPrice();
  }

  function updateTotalPrice() {
    const total = Number(quantities.adult || 0) * Number(prices.adult || 0) + Number(quantities.child || 0) * Number(prices.child || 0);
    const display = document.getElementById("totalPriceDisplay");
    if (display) display.innerText = `${total.toLocaleString("ko-KR")}원`;
  }

  function getBookingSnapshot() {
    return {
      date: document.getElementById("bookingDate")?.value || "",
      totalText: document.getElementById("totalPriceDisplay")?.innerText || "0원",
      product: getCurrentProductInfo(),
      adult: Number(quantities.adult || 0),
      child: Number(quantities.child || 0),
    };
  }

  function ensureCheckoutStyle() {
    if (document.getElementById("tourCheckoutStyle")) return;
    const style = document.createElement("style");
    style.id = "tourCheckoutStyle";
    style.textContent = `
      .tour-checkout-modal{position:fixed;inset:0;z-index:5000;display:flex;align-items:center;justify-content:center;padding:16px}
      .tour-checkout-backdrop{position:absolute;inset:0;background:rgba(0,0,0,.45)}
      .tour-checkout-panel{position:relative;width:min(700px,96vw);max-height:92vh;overflow:auto;background:#fff;border-radius:18px;padding:20px;box-shadow:0 20px 48px rgba(0,0,0,.24)}
      .tour-checkout-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      .tour-checkout-grid input,.tour-checkout-grid textarea{width:100%;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;font-size:14px}
      .tour-checkout-grid label{font-size:12px;font-weight:700;color:#374151;display:block}
      .tour-checkout-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
      .tour-checkout-btn{height:40px;padding:0 14px;border-radius:10px;border:1px solid transparent;font-weight:700;cursor:pointer}
      .tour-checkout-btn.cancel{background:#fff;border-color:#d1d5db;color:#374151}
      .tour-checkout-btn.primary{background:#2563eb;color:#fff}
      @media (max-width:640px){.tour-checkout-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function closeCheckoutModal() {
    const modal = document.getElementById("tourCheckoutModal");
    if (modal) modal.remove();
  }

  function openPaymentStep(snapshot, traveler) {
    const modal = document.getElementById("tourCheckoutModal");
    const panel = modal?.querySelector(".tour-checkout-panel");
    if (!panel) return;

    panel.innerHTML = `
      <h3 style="font-size:22px;font-weight:800;margin:0 0 8px;">결제 진행</h3>
      <p style="font-size:13px;color:#6b7280;margin:0 0 14px;">예약 정보를 확인하고 결제를 진행하세요.</p>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:12px;">
        <div><b>상품</b>: ${snapshot.product.name}</div>
        <div><b>방문일</b>: ${snapshot.date}</div>
        <div><b>인원</b>: 성인 ${snapshot.adult} / 아동 ${snapshot.child}</div>
        <div><b>예약자</b>: ${traveler.name_kr} (${traveler.name_en})</div>
        <div><b>연락처</b>: ${traveler.phone} / ${traveler.email}</div>
        <div style="margin-top:6px;font-size:18px;font-weight:800;color:#1d4ed8;">총 결제금액: ${snapshot.totalText}</div>
      </div>
      <div class="tour-checkout-actions">
        <button type="button" class="tour-checkout-btn cancel" data-tour-checkout-close>닫기</button>
        <button type="button" class="tour-checkout-btn primary" id="tourPayNowBtn">결제하기</button>
      </div>
    `;

    panel.querySelector("[data-tour-checkout-close]")?.addEventListener("click", closeCheckoutModal);
    panel.querySelector("#tourPayNowBtn")?.addEventListener("click", async function () {
      const btn = this;
      btn.disabled = true;
      btn.textContent = "결제 준비 중...";

      try {
        const amount = Number(String(snapshot.totalText || "0").replace(/[^\d]/g, "")) || 0;
        const payload = {
          tour: {
            name: snapshot.product.name,
            meta: snapshot.product.meta,
            price: amount,
            payload: snapshot.product.payload,
            date: snapshot.date,
            adult: snapshot.adult,
            child: snapshot.child,
          },
          traveler,
        };

        const res = await fetch("/api/tour/checkout", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (res.status === 401) {
          requireLoginMessage();
          return;
        }

        const checkout = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(checkout?.detail || `HTTP ${res.status}`);
        }

        if (checkout.payment_mode !== "toss" || !checkout.toss_client_key) {
          throw new Error("토스 결제 설정이 없습니다. 운영자에게 TOSS 키 설정을 요청해주세요.");
        }

        const TossPayments = await loadTossPaymentsScript();
        const toss = TossPayments(checkout.toss_client_key);
        await toss.requestPayment("카드", {
          amount: Number(checkout.amount || 0),
          orderId: String(checkout.order_id || ""),
          orderName: String(checkout.order_name || snapshot.product.name || "투어 예약"),
          customerName: String(traveler.name_kr || traveler.name_en || "").trim(),
          customerEmail: String(traveler.email || "").trim(),
          successUrl: String(checkout.success_url || `${location.origin}/payment/tour/success`),
          failUrl: String(checkout.fail_url || `${location.origin}/payment/tour/fail`),
        });
      } catch (err) {
        alert(err?.message || "결제 준비 중 오류가 발생했습니다.");
      } finally {
        btn.disabled = false;
        btn.textContent = "결제하기";
      }
    });
  }

  function openCheckoutModal(snapshot) {
    ensureCheckoutStyle();
    closeCheckoutModal();

    const modal = document.createElement("div");
    modal.id = "tourCheckoutModal";
    modal.className = "tour-checkout-modal";
    modal.innerHTML = `
      <div class="tour-checkout-backdrop" data-tour-checkout-close></div>
      <section class="tour-checkout-panel">
        <h3 style="font-size:22px;font-weight:800;margin:0 0 8px;">예약자 기본정보</h3>
        <p style="font-size:13px;color:#6b7280;margin:0 0 14px;">티켓 예약에 필요한 기본정보를 입력해 주세요.</p>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:12px;margin-bottom:14px;">
          <div><b>상품</b>: ${snapshot.product.name}</div>
          <div><b>위치</b>: ${snapshot.product.meta || "-"}</div>
          <div><b>방문일</b>: ${snapshot.date}</div>
          <div><b>인원</b>: 성인 ${snapshot.adult} / 아동 ${snapshot.child}</div>
          <div style="margin-top:6px;font-size:16px;font-weight:800;color:#1d4ed8;">총 결제금액: ${snapshot.totalText}</div>
        </div>
        <form id="tourCheckoutForm">
          <div class="tour-checkout-grid">
            <label>한글 이름*<input name="name_kr" required placeholder="홍길동"></label>
            <label>영문 이름(여권)*<input name="name_en" required placeholder="HONG GILDONG"></label>
            <label>생년월일*<input type="date" name="birth" required></label>
            <label>국적*<input name="nationality" required placeholder="KOR"></label>
            <label>여권번호*<input name="passport_no" required placeholder="M12345678"></label>
            <label>연락처*<input name="phone" required placeholder="010-0000-0000"></label>
            <label style="grid-column:1 / -1">이메일*<input type="email" name="email" required placeholder="you@example.com"></label>
            <label style="grid-column:1 / -1">요청사항<textarea name="memo" rows="2" placeholder="선택 입력"></textarea></label>
          </div>
          <div class="tour-checkout-actions">
            <button type="button" class="tour-checkout-btn cancel" data-tour-checkout-close>취소</button>
            <button type="submit" class="tour-checkout-btn primary">결제창으로 이동</button>
          </div>
        </form>
      </section>
    `;

    document.body.appendChild(modal);
    modal.querySelectorAll("[data-tour-checkout-close]").forEach((el) => el.addEventListener("click", closeCheckoutModal));
    modal.querySelector("#tourCheckoutForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      const traveler = Object.fromEntries(new FormData(e.currentTarget).entries());
      openPaymentStep(snapshot, traveler);
    });
  }

  function handleBooking() {
    const snapshot = getBookingSnapshot();
    if (!snapshot.date) return showToast("방문 날짜를 선택해주세요.");
    if (snapshot.adult === 0 && snapshot.child === 0) return showToast("인원을 선택해주세요.");
    openCheckoutModal(snapshot);
  }

  function toggleSortDropdown() {
    document.getElementById("sortDropdown")?.classList.toggle("show");
  }

  function sortReviews(criteria) {
    const reviewList = document.getElementById("reviewList");
    if (!reviewList) return;
    const reviews = Array.from(reviewList.children);
    const sortText = document.getElementById("currentSortText");

    reviews.sort((a, b) => {
      const rA = Number(a.dataset.rating || 0);
      const rB = Number(b.dataset.rating || 0);
      const dA = new Date(a.dataset.date || "1970-01-01").getTime();
      const dB = new Date(b.dataset.date || "1970-01-01").getTime();
      if (criteria === "high") return rB - rA;
      if (criteria === "low") return rA - rB;
      return dB - dA;
    });

    reviewList.innerHTML = "";
    reviews.forEach((x) => reviewList.appendChild(x));

    if (sortText) {
      sortText.innerText = criteria === "high" ? "별점 높은순" : criteria === "low" ? "별점 낮은순" : "최신순";
    }
    toggleSortDropdown();
  }

  function openReviewModal() {
    const modal = document.getElementById("reviewModal");
    if (!modal) return;
    modal.style.display = "flex";
    document.body.classList.add("modal-active");
  }

  function closeReviewModal() {
    const modal = document.getElementById("reviewModal");
    if (!modal) return;
    modal.style.display = "none";
    document.body.classList.remove("modal-active");
    setStar(0);
    const ta = document.getElementById("reviewText");
    if (ta) ta.value = "";
  }

  function setStar(num) {
    currentRating = Number(num || 0);
    document.querySelectorAll(".star-rating i").forEach((s, idx) => {
      s.classList.toggle("active", idx < currentRating);
    });
  }

  function submitReview() {
    const text = document.getElementById("reviewText")?.value || "";
    if (currentRating === 0) return showToast("별점을 선택해주세요.");
    if (!text.trim()) return showToast("후기 내용을 작성해주세요.");

    const reviewList = document.getElementById("reviewList");
    if (!reviewList) return;

    const dateStr = new Date().toISOString().split("T")[0];
    const stars = '<i class="fa-solid fa-star"></i>'.repeat(currentRating) + '<i class="fa-solid fa-star text-gray-200"></i>'.repeat(5 - currentRating);

    const node = document.createElement("div");
    node.className = "p-6 bg-blue-50/20 border border-blue-100 rounded-2xl shadow-sm";
    node.dataset.rating = String(currentRating);
    node.dataset.date = dateStr;
    node.innerHTML = `
      <div class="flex justify-between items-start mb-4">
        <div class="flex items-center gap-3">
          <div>
            <p class="text-sm font-bold text-gray-800">본인</p>
            <div class="flex text-[10px] text-yellow-400 mt-0.5">${stars}</div>
          </div>
        </div>
        <span class="text-[11px] text-gray-400">방금 전</span>
      </div>
      <p class="text-sm text-gray-600 leading-relaxed">${text}</p>
    `;

    reviewList.prepend(node);
    closeReviewModal();
    showToast("후기가 등록되었습니다.");
  }

  function showToast(msg) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.innerText = msg;
    toast.style.opacity = "1";
    setTimeout(() => {
      toast.style.opacity = "0";
    }, 2200);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initProductFromQuery();

    const bookingDateInput = document.getElementById("bookingDate");
    if (bookingDateInput) {
      const today = new Date();
      const yyyy = today.getFullYear();
      const mm = String(today.getMonth() + 1).padStart(2, "0");
      const dd = String(today.getDate()).padStart(2, "0");
      const minDate = `${yyyy}-${mm}-${dd}`;
      bookingDateInput.setAttribute("min", minDate);
      if (!bookingDateInput.value || bookingDateInput.value < minDate) bookingDateInput.value = minDate;
    }

    initSavedDrawer();
    await Promise.all([loadSavedItems(), loadAlerts()]);
    renderSavedDrawer();
  });

  window.toggleWish = toggleWish;
  window.addToCart = addToCart;
  window.changeQty = changeQty;
  window.updateTotalPrice = updateTotalPrice;
  window.handleBooking = handleBooking;
  window.toggleSortDropdown = toggleSortDropdown;
  window.sortReviews = sortReviews;
  window.openReviewModal = openReviewModal;
  window.closeReviewModal = closeReviewModal;
  window.setStar = setStar;
  window.submitReview = submitReview;
  window.showToast = showToast;
})();
