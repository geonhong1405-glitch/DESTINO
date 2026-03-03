/* ==========================================
1. 전역 변수 및 데이터 설정
   ========================================== */
let PRICES = { adult: 0, child: 0 };
let quantities = { adult: 1, child: 0 };
let currentRating = 0;

// 모든 상품 정보 및 가격 정보 통합 맵
const PRODUCT_MAP = {
  "디즈니랜드 파리 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2017/04/30/13/36/disneyland-paris-2272907_1280.jpg",
    adult: 92000,
    child: 86000,
    location: "프랑스 · 파리",
    desc: "파리 여행의 하이라이트! 환상적인 불꽃놀이와 디즈니 캐릭터들이 여러분을 기다립니다.",
  },
  "노르웨이 피오르드 럭셔리 크루즈 원데이 투어": {
    image:
      "https://cdn.pixabay.com/photo/2020/08/12/11/16/norway-5482384_1280.jpg",
    adult: 240000,
    child: 180000,
    location: "노르웨이 · 베르겐",
    desc: "하루 동안 피오르드의 아름다움을 만끽할 수 있는 원데이 투어! 현지 가이드와 함께 안전하게 즐기세요.",
  },
  "암스테르담 큐켄호프 튤립 축제 입장권 & 셔틀": {
    image:
      "https://media.istockphoto.com/id/1129048899/ko/%EC%82%AC%EC%A7%84/%EB%84%A4%EB%8D%9C%EB%9E%80%EB%93%9C-%EC%95%94%EC%8A%A4%ED%85%8C%EB%A5%B4%EB%8B%B4-%EB%B4%84-%ED%8A%A4%EB%A6%BD-%EA%BD%83%EA%B3%BC-%EC%9A%B4%ED%95%98-%EB%AC%BC%EA%B0%80%EC%97%90%EC%84%9C-%EB%8F%84%EC%8B%9C-%EC%8A%A4%EC%B9%B4%EC%9D%B4-%EB%9D%BC%EC%9D%B8-%EB%84%A4%EB%8D%9C%EB%9E%80%EB%93%9C-%EC%A7%91.jpg?b=1&s=1024x1024&w=0&k=20&c=GYqfDlR2ZMuvVLjIzIIjJTp1JWCEyhNyHKlBmsqXl_0=",
    adult: 65000,
    child: 50000,
    location: "네덜란드 • 암스테르담",
    desc: "세계 최대의 튤립 축제, 큐켄호프! 셔틀과 함께 편하게 방문하고, 형형색색의 꽃밭을 감상하세요.",
  },
  "프라하 올드타운 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2015/08/05/12/38/prague-castle-876467_1280.jpg",
    adult: 35000,
    child: 25000,
    location: "체코 • 프라하",
    desc: "프라하의 고풍스러운 올드타운을 자유롭게 둘러보세요. 역사와 낭만이 가득한 여행을 경험할 수 있습니다.",
  },
  "브뤼헤 운하 프라이빗 보트 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2022/02/23/17/05/belgium-7031044_1280.jpg",
    adult: 85000,
    child: 60000,
    location: "벨기에 • 브뤼헤",
    desc: "브뤼헤의 아름다운 운하를 프라이빗 보트로 여유롭게 즐겨보세요. 로맨틱한 분위기를 만끽할 수 있습니다.",
  },
  "퀸즈타운 상공 15,000ft 탠덤 스카이다이빙 입장권": {
    image:
      "https://media.istockphoto.com/id/885511008/ko/%EC%82%AC%EC%A7%84/%ED%80%B8-%EC%8A%A4-%ED%83%80%EC%9A%B4-%EB%B0%8F-%ED%98%B8%EC%88%98-wakaitipu-%EB%89%B4%EC%A7%88%EB%9E%9C%EB%93%9C-%ED%8C%A8%EB%9F%AC%EA%B8%80%EB%9D%BC%EC%9D%B4%EB%94%A9.webp?b=1&s=612x612&w=0&k=20&c=qR3D7Eb8T4b_R0XdXC4hheFCd6-HkFrzSY5erDoYfgM=",
    adult: 380000,
    child: 0,
    location: "뉴질랜드 • 퀸스타운",
    desc: "아드레날린이 폭발하는 스카이다이빙! 뉴질랜드의 대자연을 하늘에서 만끽하세요.",
  },
  "라플란드 순록 썰매 입장권": {
    image:
      "https://media.istockphoto.com/id/1995062084/ko/%EC%82%AC%EC%A7%84/%ED%95%80%EB%9E%80%EB%93%9C-%EB%9D%BC%ED%94%8C%EB%9E%80%EB%93%9C%EC%9D%98-%ED%99%94%EB%A0%A4%ED%95%9C-%EC%A1%B0%EB%AA%85.jpg?b=1&s=1024x1024&w=0&k=20&c=U51OLwSRQryF5Jq-38FWNMl71cEw5YDYIBvGvAv4bus=",
    adult: 195000,
    child: 120000,
    location: "핀란드 • 로바니에미",
    desc: "산타마을 라플란드에서 순록 썰매를 타고 겨울왕국을 체험해보세요!",
  },
  "유니버셜 스튜디오 재팬 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2016/12/18/03/12/usj-1914942_1280.jpg",
    adult: 110000,
    child: 90000,
    location: "일본 · 오사카",
    desc: "마리오와 함께 점프! 게임과 영화 속 세상을 그대로 옮겨놓은 짜릿한 모험의 세계입니다.",
  },
  "발리 우붓 정글 스윙 입장권": {
    image:
      "https://media.istockphoto.com/id/1167728454/ko/%EC%82%AC%EC%A7%84/%ED%85%8C%EA%B0%88%EB%9E%91-%EC%9A%B0%EB%B6%93%EC%97%90%EC%84%9C-%EB%B0%9C%EB%A6%AC-%EB%85%BC%EC%9D%84-%EB%B0%A9%EB%AC%B8-%ED%95%98%EB%8A%94-%EC%95%84%EB%A6%84-%EB%8B%A4%EC%9A%B4-%EC%86%8C%EB%85%80-%EC%A0%95%EA%B8%80%EC%9D%84-%ED%86%B5%ED%95%B4-%EC%8A%A4%EC%9C%99%EC%9D%84-%EC%82%AC%EC%9A%A9%ED%95%98%EC%97%AC-%EC%82%AC%EB%9E%8C-%EB%B0%A9%EB%9E%91%EC%9E%90-%EC%97%AC%ED%96%89-%EB%B0%8F-%EA%B4%80%EA%B4%91-%EB%9D%BC%EC%9D%B4%ED%94%84-%EC%8A%A4%ED%83%80%EC%9D%BC%EC%97%90-%EB%8C%80%ED%95%9C-%EA%B0%9C%EB%85%90.jpg?b=1&s=1024x1024&w=0&k=20&c=clhfvqAfw2I0bhAIXVt3OZRLRKXNHqeeW14CzIWZyd0=",
    adult: 45000,
    child: 30000,
    location: "인도네시아 · 발리",
    desc: "우붓의 정글에서 스윙을 타며 인생샷을 남겨보세요! 발리 여행의 필수 코스.",
  },
  "아이슬란드 남부 해안 빙하 하이킹 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2019/08/31/00/24/glacier-hike-4442543_1280.jpg",
    adult: 215000,
    child: 150000,
    location: "아이슬란드 · 레이캬비크",
    desc: "빙하 위를 걷는 특별한 경험! 전문 가이드와 함께 안전하게 하이킹을 즐기세요.",
  },
  "두바이 사막 사파리 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2014/07/24/10/28/desert-400881_1280.jpg",
    adult: 78000,
    child: 60000,
    location: "UAE · 두바이",
    desc: "두바이의 광활한 사막에서 사파리와 바비큐, 전통 공연까지! 이색 체험을 원한다면 추천.",
  },
  "인터라켄 시티뷰 패러글라이딩 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2023/06/19/15/45/paraglider-8074916_1280.jpg",
    adult: 195000,
    child: 0,
    location: "스위스 · 인터라켄",
    desc: "알프스의 절경을 하늘에서! 인터라켄에서 패러글라이딩으로 짜릿한 추억을 만들어보세요.",
  },
  "카파도키아 선라이즈 열기구 탑승권": {
    image:
      "https://media.istockphoto.com/id/1340007371/ko/%EC%82%AC%EC%A7%84/%EA%B3%A0%EC%96%B4%EB%A9%94%EC%9D%98-%EC%9D%BC%EC%B6%9C.jpg?b=1&s=1024x1024&w=0&k=20&c=wWL56oWS5IGaz6GVa-6DrKd-0g-MSWW2WU-WKLoqhX0=",
    adult: 320000,
    child: 250000,
    location: "터키 · 카파도키아",
    desc: "해 뜨는 아침, 열기구를 타고 카파도키아의 신비로운 풍경을 감상하세요.",
  },
  "교토 기온 지구 기모노 대여 & 스냅 촬영 입장권": {
    image:
      "https://media.istockphoto.com/id/1194071526/ko/%EC%82%AC%EC%A7%84/%EC%9D%BC%EB%B3%B8-%EC%86%8C%EB%85%80%EB%8A%94-%EA%B2%A8%EC%9A%B8%EC%B2%A0%EC%97%90-%EC%A0%84%ED%86%B5-%EA%B8%B0%EB%AA%A8%EB%85%B8-%EB%93%9C%EB%A0%88%EC%8A%A4%EB%A5%BC-%EC%9E%85%EA%B3%A0-%EA%B1%B7%EA%B3%A0-%EA%B5%90%ED%86%A0%EC%8B%9C%EC%9D%98-%EB%88%88%EC%9D%84-%EB%B3%B4%ED%98%B8%ED%95%A8.jpg",
    adult: 55000,
    child: 40000,
    location: "일본 · 교토",
    desc: "기모노를 입고 교토의 전통 거리를 산책하며 스냅 촬영까지! 특별한 추억을 남기세요.",
  },
  "워너 브라더스 해리포터 스튜디오": {
    image:
      "https://cdn.pixabay.com/photo/2017/03/28/16/36/hogwarts-2182636_1280.jpg",
    adult: 155000,
    child: 120000,
    location: "영국 · 런던",
    desc: "머글 출입 금지! 다이애건 앨리를 걷고 버터맥주를 마시며 진짜 마법사가 되어보세요.",
  },
  "호주 그레이트 배리어 리프 스노클링 입장권": {
    image:
      "https://cdn.pixabay.com/photo/2022/10/30/14/03/underwater-7557528_1280.jpg",
    adult: 185000,
    child: 120000,
    location: "호주 · 케언즈",
    desc: "세계 최대 산호초에서 스노클링을 즐기며 바다의 신비를 느껴보세요.",
  },
};

/* ==========================================
2. 초기화 및 상세 정보 세팅
   ========================================== */
window.addEventListener("DOMContentLoaded", () => {
  // 1. 리뷰 모달 초기 상태 강제 숨김 (문제의 핵심 해결)
  const modal = document.getElementById("reviewModal");
  if (modal) {
    modal.classList.remove("active");
    modal.style.display = "none"; // CSS display 강제 적용
    document.body.classList.remove("modal-active");
  }

  // 2. 상품 상세 정보 로드
  setProductDetailFromParams();

  // 3. 기타 UI 초기화
  setDateMin();
  setupReviewShowMore();
});

// URL 파라미터 추출 함수 (중복 제거)
function getQueryParams() {
  const params = {};
  window.location.search.replace(
    /[?&]+([^=&]+)=([^&]*)/gi,
    function (str, key, value) {
      params[key] = decodeURIComponent(value);
    },
  );
  return params;
}

// 상품 정보 반영 함수 (title만 일치하면 이미지/설명 반영)
function setProductDetailFromParams() {
  const params = getQueryParams();
  if (!params.tour_id) return;
  const [rawTitle, location, price] = params.tour_id.split("__");
  // Normalize title for robust matching
  function normalize(str) {
    return (str || "")
      .replace(/[·•]/g, ".")
      .replace(/\s+/g, " ")
      .replace(/&/g, "&")
      .replace(/,/g, "")
      .trim();
  }
  const title = normalize(rawTitle);
  const loc = normalize(location);
  const priceNorm = normalize(price);
  // title+location+price 모두 normalize해서 robust하게 매칭
  let prodKey = Object.keys(PRODUCT_MAP).find((k) => {
    const mapTitle = normalize(k);
    const mapLoc = normalize(PRODUCT_MAP[k].location);
    const mapAdult = String(PRODUCT_MAP[k].adult);
    const mapChild = String(PRODUCT_MAP[k].child);
    return (
      mapTitle === title &&
      mapLoc === loc &&
      (mapAdult === priceNorm || mapChild === priceNorm)
    );
  });
  let prod = prodKey ? PRODUCT_MAP[prodKey] : undefined;
  if (!prod) {
    // title+location만 일치하는 fallback
    prodKey = Object.keys(PRODUCT_MAP).find((k) => {
      const mapTitle = normalize(k);
      const mapLoc = normalize(PRODUCT_MAP[k].location);
      return mapTitle === title && mapLoc === loc;
    });
    if (prodKey) prod = PRODUCT_MAP[prodKey];
  }
  if (!prod) {
    // title만 일치하는 fallback
    prodKey = Object.keys(PRODUCT_MAP).find((k) => normalize(k) === title);
    if (prodKey) prod = PRODUCT_MAP[prodKey];
  }
  if (title && prod) {
    if (document.getElementById("productTitle"))
      document.getElementById("productTitle").innerText = title;
    if (document.getElementById("productLoc"))
      document.getElementById("productLoc").innerHTML = location
        ? `<i class='fa-solid fa-location-dot'></i> ${location}`
        : "";
    if (document.getElementById("productDesc"))
      document.getElementById("productDesc").innerText = prod.desc;
    const imgEl = document.getElementById("productImg");
    if (imgEl) {
      imgEl.src = prod.image;
      imgEl.alt = title;
    }
    PRICES = { adult: prod.adult, child: prod.child };
    // 클릭한 가격(adult/child)에 따라 메인 가격 반영
    let mainPriceType = "";
    if (String(prod.adult) === priceNorm) mainPriceType = "adult";
    else if (String(prod.child) === priceNorm) mainPriceType = "child";
    // 메인 가격 표시
    if (document.getElementById("productPrice") && mainPriceType) {
      document.getElementById("productPrice").innerText =
        prod[mainPriceType].toLocaleString();
    }
    // 나머지 가격도 표시
    const adultPriceDisplay = document.getElementById("adultPriceDisplay");
    const childPriceDisplay = document.getElementById("childPriceDisplay");
    if (adultPriceDisplay)
      adultPriceDisplay.innerText = prod.adult.toLocaleString() + "원";
    if (childPriceDisplay)
      childPriceDisplay.innerText =
        prod.child > 0 ? prod.child.toLocaleString() + "원" : "예약 불가";
    updateTotalPrice();
  } else {
    // 매칭 실패 시 기본값
    if (document.getElementById("productTitle"))
      document.getElementById("productTitle").innerText = title || "";
    if (document.getElementById("productLoc"))
      document.getElementById("productLoc").innerHTML = location
        ? `<i class='fa-solid fa-location-dot'></i> ${location}`
        : "";
    if (document.getElementById("productDesc"))
      document.getElementById("productDesc").innerText =
        "상품 정보를 찾을 수 없습니다.";
    const imgEl = document.getElementById("productImg");
    if (imgEl) {
      imgEl.src =
        "https://images.unsplash.com/photo-1511739001486-6bfe10ce785f?auto=format&fit=crop&q=80&w=1200";
      imgEl.alt = title || "";
    }
    PRICES = { adult: 0, child: 0 };
    if (document.getElementById("adultPriceDisplay"))
      document.getElementById("adultPriceDisplay").innerText = "-";
    if (document.getElementById("childPriceDisplay"))
      document.getElementById("childPriceDisplay").innerText = "-";
    updateTotalPrice();
  }
}

/* ==========================================
3. 예약 및 수량 조절
   ========================================== */
function changeQty(type, diff) {
  const newQty = quantities[type] + diff;
  if (newQty < 0) return;

  if (type === "adult" && newQty === 0 && quantities.child > 0) {
    showToast("아동 동반 시 성인 1명 이상은 필수입니다.");
    return;
  }

  quantities[type] = newQty;
  document.getElementById(`${type}Qty`).innerText = newQty;
  updateTotalPrice();
}

function updateTotalPrice() {
  const total =
    quantities.adult * PRICES.adult + quantities.child * PRICES.child;
  const totalDisplay = document.getElementById("totalPriceDisplay");
  if (totalDisplay) totalDisplay.innerText = total.toLocaleString() + "원";
}

function handleBooking() {
  const date = document.getElementById("bookingDate").value;
  if (!date) return showToast("방문 날짜를 선택해주세요.");
  if (quantities.adult === 0) return showToast("성인 인원을 선택해주세요.");
  alert(`${date} 투어 예약을 진행합니다.`);
}

function getTodayStr() {
  const today = new Date();
  return today.toISOString().split("T")[0];
}

function setDateMin() {
  const dateInput = document.getElementById("bookingDate");
  if (dateInput) {
    dateInput.min = getTodayStr();
  }
}

/* ==========================================
4. 리뷰 리스트 관리 (더보기, 정렬)
   ========================================== */
function setupReviewShowMore() {
  const reviewList = document.querySelectorAll(".review-item");
  const moreBtn = document.getElementById("reviewMoreBtn");
  if (!reviewList.length) return;

  reviewList.forEach((el, idx) => {
    el.style.display = idx < 4 ? "" : "none";
  });

  if (reviewList.length > 4 && moreBtn) {
    moreBtn.style.display = "";
    moreBtn.innerText = "더보기";
    moreBtn.onclick = function () {
      const isOpen = moreBtn.getAttribute("data-open") === "1";
      if (!isOpen) {
        document
          .querySelectorAll(".review-item")
          .forEach((el) => (el.style.display = ""));
        moreBtn.innerText = "접기";
        moreBtn.setAttribute("data-open", "1");
      } else {
        document.querySelectorAll(".review-item").forEach((el, idx) => {
          el.style.display = idx < 4 ? "" : "none";
        });
        moreBtn.innerText = "더보기";
        moreBtn.setAttribute("data-open", "0");
      }
    };
  }
}

function toggleSortDropdown() {
  document.getElementById("sortDropdown").classList.toggle("show");
}

function sortReviews(criteria) {
  const reviewList = document.getElementById("reviewList");
  const reviews = Array.from(reviewList.children);
  const sortText = document.getElementById("currentSortText");

  reviews.sort((a, b) => {
    const rA = parseInt(a.dataset.rating),
      rB = parseInt(b.dataset.rating);
    const dA = new Date(a.dataset.date),
      dB = new Date(b.dataset.date);
    if (criteria === "high") return rB - rA;
    if (criteria === "low") return rA - rB;
    return dB - dA;
  });

  reviewList.innerHTML = "";
  reviews.forEach((r) => reviewList.appendChild(r));
  document.getElementById("sortDropdown").classList.remove("show");
  showToast("정렬이 완료되었습니다.");
}

/* ==========================================
5. 모달 및 기타 편의 기능
   ========================================== */
function openReviewModal() {
  const modal = document.getElementById("reviewModal");
  modal.style.display = "flex"; // 열 때 flex로 변경
  setTimeout(() => modal.classList.add("active"), 10);
  document.body.classList.add("modal-active");
}

function closeReviewModal() {
  const modal = document.getElementById("reviewModal");
  modal.classList.remove("active");
  setTimeout(() => (modal.style.display = "none"), 300); // 애니메이션 후 숨김
  document.body.classList.remove("modal-active");
  currentRating = 0;
  document
    .querySelectorAll(".star-rating i")
    .forEach((s) => s.classList.remove("active"));
  document.getElementById("reviewText").value = "";
}

function setStar(num) {
  currentRating = num;
  document.querySelectorAll(".star-rating i").forEach((s, idx) => {
    s.classList.toggle("active", idx < num);
  });
}

function submitReview() {
  const text = document.getElementById("reviewText").value;
  if (currentRating === 0) return showToast("별점을 선택해주세요.");
  if (!text.trim()) return showToast("후기 내용을 작성해주세요.");

  // 리뷰 추가 로직 (생략 - 기존 유지)
  closeReviewModal();
  showToast("소중한 후기가 등록되었습니다! ✨");
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.innerText = msg;
  toast.classList.replace("opacity-0", "opacity-100");
  setTimeout(() => toast.classList.replace("opacity-100", "opacity-0"), 2500);
}

// 찜/장바구니 토글 (UI만)
function toggleWish() {
  const btn = document.getElementById("wishBtn");
  const active = btn.classList.toggle("text-red-500");
  showToast(
    active ? "찜 목록에 추가되었습니다!" : "찜 목록에서 제외되었습니다.",
  );
}

function addToCart() {
  const btn = document.getElementById("cartBtn");
  const active = btn.classList.toggle("text-blue-600");
  showToast(active ? "장바구니에 담겼습니다!" : "장바구니에서 뺐습니다.");
}
