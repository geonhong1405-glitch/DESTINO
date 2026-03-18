(function () {
  const root = document.getElementById("fdRoot");
  if (!root) return;

  const byId = (id) => document.getElementById(id);

  const toNum = (v) => {
    const n = Number(String(v ?? "").replace(/[^\d.]/g, ""));
    return Number.isFinite(n) ? n : 0;
  };

  const parseJsonSafe = (s, fallback) => {
    try {
      const v = JSON.parse(String(s || ""));
      return v ?? fallback;
    } catch (_e) {
      return fallback;
    }
  };

  const splitAt = (txt) => {
    const s = String(txt || "").trim();
    if (!s) return { time: "-", date: "-" };
    if (s.includes("T")) {
      const d = new Date(s);
      if (!Number.isNaN(d.getTime())) {
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const dd = String(d.getDate()).padStart(2, "0");
        const hh = String(d.getHours()).padStart(2, "0");
        const mi = String(d.getMinutes()).padStart(2, "0");
        return { time: `${hh}:${mi}`, date: `${mm}-${dd}` };
      }
    }
    const m = s.match(/(\d{2}:\d{2})/);
    const d = s.match(/(\d{2}-\d{2})/);
    return { time: m ? m[1] : "-", date: d ? d[1] : "-" };
  };

  const ccy = String(root.dataset.currency || "KRW").toUpperCase();
  const fmtMoney = (v) => `${ccy} ${Math.round(v || 0).toLocaleString()}`;

  const data = {
    dep: String(root.dataset.dep || "-"),
    arr: String(root.dataset.arr || "-"),
    route: String(root.dataset.route || "-"),
    duration: String(root.dataset.duration || "-"),
    priceMain: toNum(root.dataset.price || ""),
    priceTotal: toNum(root.dataset.priceTotal || ""),
    priceGrand: toNum(root.dataset.priceGrand || ""),
    priceBase: toNum(root.dataset.priceBase || ""),
    baggage: String(root.dataset.baggage || "").trim(),
    baggageOpts: parseJsonSafe(root.dataset.baggageOpts || "[]", []),
    depAt: String(root.dataset.depAt || "").trim(),
    arrAt: String(root.dataset.arrAt || "").trim(),
    depTerminal: String(root.dataset.depTerminal || "").trim(),
    arrTerminal: String(root.dataset.arrTerminal || "").trim(),
    flightNo: String(root.dataset.flightNo || "").trim(),
    aircraft: String(root.dataset.aircraft || "").trim(),
    cabin: String(root.dataset.cabin || "").trim(),
    retDep: String(root.dataset.retDep || "").trim(),
    retArr: String(root.dataset.retArr || "").trim(),
    retRoute: String(root.dataset.retRoute || "").trim(),
    retDuration: String(root.dataset.retDuration || "").trim(),
    retDepAt: String(root.dataset.retDepAt || "").trim(),
    retArrAt: String(root.dataset.retArrAt || "").trim(),
    retDepTerminal: String(root.dataset.retDepTerminal || "").trim(),
    retArrTerminal: String(root.dataset.retArrTerminal || "").trim(),
    retFlightNo: String(root.dataset.retFlightNo || "").trim(),
    retAircraft: String(root.dataset.retAircraft || "").trim(),
    retCabin: String(root.dataset.retCabin || "").trim(),
    checkoutRef: String(root.dataset.checkoutRef || "").trim(),
    isRound: String(root.dataset.round || "") === "1",
  };

  const baseFare = data.priceTotal || data.priceMain || data.priceGrand || data.priceBase || 0;
  byId("fdChosen").textContent = data.cabin || "API 요금";

  const outRoute = data.route && data.route !== "-" ? data.route : `${data.dep} → ${data.arr}`;
  byId("fdJourneyRoute").textContent = outRoute;
  byId("fdJourneyDur").textContent = data.duration ? `총 ${data.duration} 소요` : "-";
  const outDep = splitAt(data.depAt);
  const outArr = splitAt(data.arrAt);
  byId("fdDepTime").textContent = outDep.time;
  byId("fdDepDate").textContent = outDep.date;
  byId("fdArrTime").textContent = outArr.time;
  byId("fdArrDate").textContent = outArr.date;
  byId("fdDepLabel").textContent = `${data.dep || "-"} 출발`;
  byId("fdArrLabel").textContent = `${data.arr || "-"} 도착`;
  byId("fdDepNote").textContent = `${data.dep || "-"} 터미널 ${data.depTerminal || "-"}`;
  byId("fdArrNote").textContent = `${data.arr || "-"} 터미널 ${data.arrTerminal || "-"}`;

  const outChips = [];
  if (data.flightNo) outChips.push(`편명 ${data.flightNo}`);
  if (data.aircraft) outChips.push(`기종 ${data.aircraft}`);
  if (data.cabin) outChips.push(`좌석 ${data.cabin}`);
  if (data.baggage) outChips.push(data.baggage);
  byId("fdJourneyMeta").innerHTML = outChips.map((x) => `<div class="fd-j-chip">${x}</div>`).join("");

  const retCard = byId("fdReturnCard");
  const hasReturn = data.isRound && (data.retRoute || data.retDep || data.retArr || data.retDepAt || data.retArrAt);
  if (retCard) retCard.hidden = !hasReturn;
  if (hasReturn) {
    const retRoute = data.retRoute && data.retRoute !== "-" ? data.retRoute : `${data.retDep} → ${data.retArr}`;
    byId("fdRetJourneyRoute").textContent = retRoute;
    byId("fdRetJourneyDur").textContent = data.retDuration ? `총 ${data.retDuration} 소요` : "-";
    const retDep = splitAt(data.retDepAt);
    const retArr = splitAt(data.retArrAt);
    byId("fdRetDepTime").textContent = retDep.time;
    byId("fdRetDepDate").textContent = retDep.date;
    byId("fdRetArrTime").textContent = retArr.time;
    byId("fdRetArrDate").textContent = retArr.date;
    byId("fdRetDepLabel").textContent = `${data.retDep || "-"} 출발`;
    byId("fdRetArrLabel").textContent = `${data.retArr || "-"} 도착`;
    byId("fdRetDepNote").textContent = `${data.retDep || "-"} 터미널 ${data.retDepTerminal || "-"}`;
    byId("fdRetArrNote").textContent = `${data.retArr || "-"} 터미널 ${data.retArrTerminal || "-"}`;

    const retChips = [];
    if (data.retFlightNo) retChips.push(`편명 ${data.retFlightNo}`);
    if (data.retAircraft) retChips.push(`기종 ${data.retAircraft}`);
    if (data.retCabin) retChips.push(`좌석 ${data.retCabin}`);
    if (data.baggage) retChips.push(data.baggage);
    byId("fdRetJourneyMeta").innerHTML = retChips.map((x) => `<div class="fd-j-chip">${x}</div>`).join("");
  }

  const nav = byId("fdJourneyNav");
  const prevBtn = byId("fdJourneyPrev");
  const nextBtn = byId("fdJourneyNext");
  const idxEl = byId("fdJourneyIdx");
  const outCard = document.querySelector(".fd-journey-card:not(#fdReturnCard)");
  const cards = [outCard, retCard].filter((x) => x && !x.hidden);
  let idx = 0;
  const applyNav = () => {
    cards.forEach((c, i) => {
      c.style.display = i === idx ? "" : "none";
    });
    if (idxEl) idxEl.textContent = `${idx + 1} / ${cards.length}`;
  };
  if (cards.length > 1) {
    if (nav) nav.hidden = false;
    prevBtn?.addEventListener("click", () => {
      idx = (idx - 1 + cards.length) % cards.length;
      applyNav();
    });
    nextBtn?.addEventListener("click", () => {
      idx = (idx + 1) % cards.length;
      applyNav();
    });
  } else if (nav) {
    nav.hidden = true;
  }
  applyNav();

  const addonWrap = byId("fdAddonWrap");
  const bagSelect = byId("fdBagSelect");
  const bagHint = byId("fdBagHint");
  const options = (Array.isArray(data.baggageOpts) ? data.baggageOpts : [])
    .map((x) => ({ label: String(x?.label || "").trim(), price: toNum(x?.price) }))
    .filter((x) => x.label && x.price > 0);

  if (addonWrap && bagSelect && options.length > 0) {
    addonWrap.hidden = false;
    options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = String(opt.price);
      o.textContent = `${opt.label} (+${Math.round(opt.price).toLocaleString()} ${ccy})`;
      bagSelect.appendChild(o);
    });
    if (bagHint) bagHint.textContent = "API 제공 수하물 추가 옵션";
  } else if (addonWrap) {
    addonWrap.hidden = true;
  }

  const totalEl = byId("fdTotal");
  let bagAddPrice = 0;
  const renderTotal = () => {
    totalEl.textContent = fmtMoney(baseFare + bagAddPrice);
  };
  bagSelect?.addEventListener("change", () => {
    bagAddPrice = toNum(bagSelect.value || "0");
    renderTotal();
  });
  renderTotal();

  function loadTossPaymentsScript() {
    if (window.TossPayments) return Promise.resolve(window.TossPayments);
    return new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-toss-sdk="1"]');
      if (existing) {
        existing.addEventListener("load", () => resolve(window.TossPayments));
        existing.addEventListener("error", () => reject(new Error("토스 스크립트 로드 실패")));
        return;
      }
      const s = document.createElement("script");
      s.src = "https://js.tosspayments.com/v1/payment";
      s.async = true;
      s.dataset.tossSdk = "1";
      s.onload = () => resolve(window.TossPayments);
      s.onerror = () => reject(new Error("토스 스크립트 로드 실패"));
      document.head.appendChild(s);
    });
  }

  function readCheckoutPayload() {
    if (!data.checkoutRef) return null;
    try {
      const raw = sessionStorage.getItem(`flight_checkout_${data.checkoutRef}`);
      if (!raw) return null;
      return parseJsonSafe(raw, null);
    } catch (_e) {
      return null;
    }
  }

  function buildFallbackOffer() {
    const amount = baseFare + bagAddPrice;
    if (!amount || !data.dep || !data.arr) return null;

    const outboundSeg = {
      carrierCode: (data.flightNo.match(/^[A-Z0-9]{2}/) || [""])[0],
      number: (data.flightNo.match(/(\d+)/) || ["", ""])[1],
      aircraft: data.aircraft ? { code: data.aircraft } : undefined,
      departure: { iataCode: data.dep, at: data.depAt || undefined, terminal: data.depTerminal || undefined },
      arrival: { iataCode: data.arr, at: data.arrAt || undefined, terminal: data.arrTerminal || undefined },
    };
    const itineraries = [{ duration: data.duration || undefined, segments: [outboundSeg] }];

    if (hasReturn) {
      const inboundSeg = {
        carrierCode: (data.retFlightNo.match(/^[A-Z0-9]{2}/) || [""])[0],
        number: (data.retFlightNo.match(/(\d+)/) || ["", ""])[1],
        aircraft: data.retAircraft ? { code: data.retAircraft } : undefined,
        departure: { iataCode: data.retDep || undefined, at: data.retDepAt || undefined, terminal: data.retDepTerminal || undefined },
        arrival: { iataCode: data.retArr || undefined, at: data.retArrAt || undefined, terminal: data.retArrTerminal || undefined },
      };
      itineraries.push({ duration: data.retDuration || undefined, segments: [inboundSeg] });
    }

    return {
      airline: root.dataset.airline || "",
      airline_code: (outboundSeg.carrierCode || "").trim(),
      price: {
        currency: "KRW",
        total: String(Math.round(amount)),
        krwTotal: Math.round(amount),
      },
      itineraries,
    };
  }

  function getCheckoutOffer() {
    const stored = readCheckoutPayload();
    const inner = stored?.payload && typeof stored.payload === "object" ? stored.payload : null;
    if (inner?.price && Array.isArray(inner?.itineraries) && inner.itineraries.length) {
      const cloned = JSON.parse(JSON.stringify(inner));
      const total = Math.round((toNum(cloned?.price?.krwTotal || cloned?.price?.total) || baseFare) + bagAddPrice);
      if (!cloned.price || typeof cloned.price !== "object") cloned.price = {};
      cloned.price.krwTotal = total;
      if (String(cloned.price.currency || "").toUpperCase() === "KRW" || !cloned.price.currency) {
        cloned.price.currency = "KRW";
        cloned.price.total = String(total);
      }
      return cloned;
    }
    return buildFallbackOffer();
  }

  const form = byId("fdForm");
  const submitBtn = form?.querySelector('button[type="submit"]');

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!submitBtn) return;

    const offer = getCheckoutOffer();
    if (!offer || !offer.price || !Array.isArray(offer.itineraries) || !offer.itineraries.length) {
      alert("결제용 항공권 데이터가 없습니다. 항공 검색 결과에서 다시 선택해 주세요.");
      return;
    }

    const fd = new FormData(form);
    const fullName = String(fd.get("fullName") || "").trim();
    const parts = fullName.split(/\s+/).filter(Boolean);
    const firstName = parts.length > 1 ? parts.slice(1).join(" ") : (parts[0] || "GILDONG");
    const lastName = parts.length > 1 ? parts[0] : "HONG";
    const birthDate = String(fd.get("birth") || "").trim();
    const passport = String(fd.get("passport") || "").trim().toUpperCase();
    const nationality = String(fd.get("nationality") || "").trim().toUpperCase();
    const email = String(fd.get("email") || "").trim();
    const phone = String(fd.get("phone") || "").trim();

    if (!fullName || !birthDate || !passport || !nationality || !email) {
      alert("탑승객 정보를 모두 입력해 주세요.");
      return;
    }

    const body = {
      offer,
      customer_name: fullName,
      customer_email: email,
      customer_phone: phone,
      passengers: [
        {
          last_name: lastName,
          first_name: firstName,
          birth_date: birthDate,
          nationality,
          passport_number: passport,
          passport_expiry: "2035-12-31",
        },
      ],
    };

    const prevText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "결제 준비 중...";

    try {
      const res = await fetch("/api/flight/checkout", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const checkout = await res.json().catch(() => ({}));
      if (res.status === 401) {
        alert("로그인이 필요합니다.");
        location.href = "/login";
        return;
      }
      if (!res.ok) {
        throw new Error(checkout?.detail || checkout?.message || "결제 준비에 실패했습니다.");
      }

      if (checkout.payment_mode !== "toss" || !checkout.toss_client_key) {
        alert(`[모의 결제]\n주문번호: ${checkout.order_id}\n결제금액: ${Number(checkout.amount || 0).toLocaleString("ko-KR")}원`);
        const oid = encodeURIComponent(String(checkout.order_id || ""));
        location.href = `/payment/flight/confirmed?orderId=${oid}`;
        return;
      }

      const TossPayments = await loadTossPaymentsScript();
      const toss = TossPayments(checkout.toss_client_key);
      await toss.requestPayment("카드", {
        amount: Number(checkout.amount || 0),
        orderId: String(checkout.order_id || ""),
        orderName: String(checkout.order_name || "항공권"),
        customerName: fullName,
        customerEmail: email,
        successUrl: String(checkout.success_url || `${location.origin}/payment/flight/success`),
        failUrl: String(checkout.fail_url || `${location.origin}/payment/flight/fail`),
      });
    } catch (err) {
      alert(err?.message || "결제 진행 중 오류가 발생했습니다.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = prevText;
    }
  });
})();
