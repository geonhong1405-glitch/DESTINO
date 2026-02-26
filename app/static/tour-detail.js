/**
 * DESTINO 투어 상세페이지 동적 콘텐츠 렌더링
 */

// 1. 투어 코스 데이터
const courseData = [
    {
        time: "09:00",
        title: "호텔 픽업 및 미팅",
        desc: "숙박하시는 호텔 로비에서 가이드와 미팅 후 전용 차량으로 이동합니다.",
        icon: "fa-car-side"
    },
    {
        time: "10:30",
        title: "구시가지 도보 투어",
        desc: "역사와 전통이 살아있는 구시가지의 주요 랜드마크를 전문가의 해설과 함께 탐방합니다.",
        icon: "fa-walking"
    },
    {
        time: "12:30",
        title: "현지 로컬 맛집 중식",
        desc: "관광객 위주의 식당이 아닌, 현지인들이 사랑하는 숨은 맛집에서 정통 요리를 즐깁니다.",
        icon: "fa-utensils"
    },
    {
        time: "14:00",
        title: "랜드마크 집중 관람",
        desc: "이 지역의 하이라이트인 명소를 내부 관람하며 자유 시간을 가집니다.",
        icon: "fa-camera"
    },
    {
        time: "17:00",
        title: "투어 종료 및 호텔 드랍",
        desc: "모든 일정을 마치고 안전하게 투숙하시는 호텔로 모셔다 드립니다.",
        icon: "fa-hotel"
    }
];

// 2. 이용 및 유의사항 데이터
const infoSections = [
    {
        title: "포함 사항",
        items: [
            "한국인 전문 가이드 비",
            "전용 차량 및 유류비",
            "관광지 입장료 (일부 제외)",
            "여행자 보험"
        ]
    },
    {
        title: "불포함 사항",
        items: [
            "개인 매너팁 (자율 선택)",
            "점심 식사 비용 (현지 지불)",
            "개인 쇼핑 비용"
        ]
    },
    {
        title: "유의 사항",
        items: [
            "투어 시작 10분 전까지 미팅 장소에 도착해주세요.",
            "걷기 편한 신발과 복장을 권장합니다.",
            "천재지변으로 인해 투어가 취소될 경우 100% 환불됩니다.",
            "개인 소지품 분실 시 당사는 책임을 지지 않습니다."
        ]
    }
];

// 3. 생생후기 데이터
const reviews = [
    {
        user: "김*나",
        rating: 5,
        date: "2024.01.15",
        content: "가이드님의 해설이 너무 전문적이라서 좋았어요! 사진도 인생샷으로 엄청 많이 찍어주셨습니다. 부모님 모시고 갔는데 대만족이에요.",
        tags: ["친절함", "알찬구성", "사진맛집"]
    },
    {
        user: "Lee***",
        rating: 4,
        date: "2023.12.28",
        content: "차량이 깨끗해서 이동할 때 정말 편했습니다. 다만 점심때 갔던 식당에 사람이 좀 많아서 대기가 있었던 점은 아쉬워요. 그래도 맛은 최고!",
        tags: ["차량쾌적", "맛집탐방"]
    },
    {
        user: "박*수",
        rating: 5,
        date: "2023.12.10",
        content: "혼자 여행와서 신청했는데 가이드님이 잘 챙겨주셔서 외롭지 않게 투어했습니다. 다음에 다른 도시에서도 DESTINO 이용할게요!",
        tags: ["혼자여행", "가이드최고"]
    }
];

// 4. 렌더링 함수들
function renderCourse() {
    const section = document.getElementById('section-course');
    section.innerHTML = `
        <h2 class="text-2xl font-black text-gray-900 mb-8 flex items-center gap-3">
            <span class="w-1.5 h-8 bg-brand-blue rounded-full"></span> 코스안내
        </h2>
        <div class="space-y-0">
            ${courseData.map((item, index) => `
                <div class="timeline-item flex gap-6 relative pb-12">
                    <div class="timeline-line shrink-0 relative z-10">
                        <div class="w-6 h-6 bg-brand-blue rounded-full flex items-center justify-center border-4 border-blue-100">
                            <i class="fa-solid ${item.icon} text-[8px] text-white"></i>
                        </div>
                    </div>
                    <div>
                        <span class="text-xs font-black text-brand-blue uppercase tracking-tighter">${item.time}</span>
                        <h4 class="text-lg font-bold text-gray-900 mt-1">${item.title}</h4>
                        <p class="text-sm text-gray-500 mt-2 leading-relaxed">${item.desc}</p>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderInfo() {
    const section = document.getElementById('section-info');
    section.innerHTML = `
        <h2 class="text-2xl font-black text-gray-900 mb-8 flex items-center gap-3">
            <span class="w-1.5 h-8 bg-brand-blue rounded-full"></span> 이용/유의사항
        </h2>
        <div class="grid md:grid-cols-3 gap-6">
            ${infoSections.map(info => `
                <div class="bg-gray-50 rounded-3xl p-8 border border-gray-100">
                    <h4 class="font-black text-gray-900 mb-6 text-sm uppercase tracking-widest">${info.title}</h4>
                    <ul class="space-y-4">
                        ${info.items.map(item => `
                            <li class="flex items-start gap-3 text-sm text-gray-600">
                                <i class="fa-solid fa-check text-brand-blue text-[10px] mt-1"></i>
                                <span>${item}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `).join('')}
        </div>
    `;
}

function renderReviews() {
    const section = document.getElementById('section-reviews');
    section.innerHTML = `
        <div class="flex items-end justify-between mb-8">
            <h2 class="text-2xl font-black text-gray-900 flex items-center gap-3">
                <span class="w-1.5 h-8 bg-brand-blue rounded-full"></span> 생생후기
            </h2>
            <div class="text-sm font-bold text-gray-400">전체 후기 ${reviews.length}개</div>
        </div>
        <div class="space-y-6">
            ${reviews.map(review => `
                <div class="p-8 border border-gray-100 rounded-[32px] hover:shadow-xl transition-shadow bg-white">
                    <div class="flex justify-between items-start mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center font-bold text-gray-400 text-xs">
                                ${review.user[0]}
                            </div>
                            <div>
                                <div class="text-sm font-bold text-gray-900">${review.user}</div>
                                <div class="text-[10px] text-gray-400">${review.date}</div>
                            </div>
                        </div>
                        <div class="flex text-yellow-400 text-[10px] gap-0.5">
                            ${Array(5).fill().map((_, i) => `<i class="fa-solid fa-star ${i >= review.rating ? 'text-gray-200' : ''}"></i>`).join('')}
                        </div>
                    </div>
                    <p class="text-sm text-gray-600 leading-relaxed mb-4">${review.content}</p>
                    <div class="flex gap-2">
                        ${review.tags.map(tag => `<span class="text-[10px] font-bold text-brand-blue bg-blue-50 px-3 py-1 rounded-full">#${tag}</span>`).join('')}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// 5. 수량 및 가격 계산 로직
let quantity = 1;
const pricePerPerson = 4590000; // 예시 가격

function updatePrice() {
    const display = document.getElementById('qtyDisplay');
    const totalDisplay = document.getElementById('totalPriceDisplay');
    const baseDisplay = document.getElementById('basePrice');
    
    display.innerText = quantity;
    baseDisplay.innerText = pricePerPerson.toLocaleString();
    totalDisplay.innerText = (pricePerPerson * quantity).toLocaleString() + '원';
}

// 6. 초기화
window.onload = () => {
    // 텍스트 및 기본 정보 설정
    document.getElementById('detailTitle').innerText = "[품격] 서유럽 3국 10일 #파리/융프라우/로마";
    document.getElementById('breadcrumbLoc').innerText = "프랑스/스위스/이탈리아";
    document.getElementById('mainImage').src = "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?q=80&w=1000";
    document.getElementById('contentImage').src = "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?q=80&w=1000";

    // 동적 섹션 렌더링
    renderCourse();
    renderInfo();
    renderReviews();
    updatePrice();

    // 이벤트 리스너
    document.getElementById('plusQty').onclick = () => { quantity++; updatePrice(); };
    document.getElementById('minusQty').onclick = () => { if(quantity > 1) { quantity--; updatePrice(); } };

    // 탭 내비게이션 활성화 처리
    const tabLinks = document.querySelectorAll('.tab-link');
    tabLinks.forEach(link => {
        link.onclick = (e) => {
            tabLinks.forEach(l => l.classList.remove('tab-active'));
            link.classList.add('tab-active');
        };
    });
};