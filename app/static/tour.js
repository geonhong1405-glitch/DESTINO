/**
 * Destino Tour Booking Interactions
 */

window.onload = function () {
    // Lucide 아이콘 초기화
    lucide.createIcons();

    const destInput = document.getElementById('dest-input');
    const tourPopover = document.getElementById('tourPopover');
    const defaultSugg = document.getElementById('default-suggestions');
    const searchResults = document.getElementById('search-results');
    const resultsList = document.getElementById('results-list');
    const searchWidget = document.getElementById('searchWidget');

    /**
     * 입력창 클릭 시 팝업 활성화
     */
    destInput.addEventListener('click', (e) => {
        e.stopPropagation();
        tourPopover.classList.add('active');
    });

    /**
     * 입력어에 따른 실시간 제안 리스트 업데이트
     */
    destInput.addEventListener('input', (e) => {
        const val = e.target.value;

        if (val.trim().length > 0) {
            // 인기 여행지 숨기고 검색 결과 표시
            defaultSugg.style.display = 'none';
            searchResults.style.display = 'block';

            // 검색 제안 템플릿 업데이트
            resultsList.innerHTML = `
                <div class="search-suggestion-item" onclick="selectDest('${val}')">
                    <i data-lucide="map-pin" size="16"></i>
                    <span><strong>'${val}'</strong> 검색 결과 보기</span>
                </div>
                <div class="search-suggestion-item" onclick="selectDest('${val} 인기 명소')">
                    <i data-lucide="star" size="16"></i>
                    <span>${val} 인기 명소/어트랙션 찾기</span>
                </div>
            `;
            // 새로 생성된 아이콘 렌더링
            lucide.createIcons();
        } else {
            // 입력창이 비었을 때 초기 상태로 복구
            defaultSugg.style.display = 'block';
            searchResults.style.display = 'none';
        }
    });

    /**
     * 검색 위젯 외부 클릭 시 팝업 닫기
     */
    document.addEventListener('click', (e) => {
        if (!searchWidget.contains(e.target)) {
            tourPopover.classList.remove('active');
        }
    });
};

/**
 * 제안된 여행지 선택 함수
 * @param {string} name 선택된 지명
 */
function selectDest(name) {
    const destInput = document.getElementById('dest-input');
    const tourPopover = document.getElementById('tourPopover');

    destInput.value = name;
    tourPopover.classList.remove('active');
}

/**
 * 검색 버튼 클릭 핸들러
 */
function handleSearch() {
    const destInput = document.getElementById('dest-input');
    const query = destInput.value;

    if (!query) {
        alert('여행지 또는 어트랙션을 입력해주세요.');
        return;
    }

    // 실제 서비스에서는 검색 결과 페이지로 이동 로직이 들어갑니다.
    alert(`'${query}' 상품 정보를 불러오고 있습니다.`);
}
