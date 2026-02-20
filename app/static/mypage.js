/**
 * DESTINO 마이페이지 동적 로직
 * (HTML 구조 변화에 맞춰 선택자 및 수정 모드 로직 보완)
 */

let user = {
    id: "destino_traveler",
    name: "김데스티노",
    nickname: "여행자김씨",
    email: "traveler@destino.com",
    phone: "010-1234-5678"
};

const bookings = []; 

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const targetContent = document.getElementById('content-' + tabId);
    if (targetContent) targetContent.classList.add('active');

    document.querySelectorAll('.sidebar-item').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeBtn = document.getElementById('tab-btn-' + tabId);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    if (tabId !== 'settings') toggleEditMode(false);

    if (window.innerWidth < 1024) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('fixed')) {
            toggleMobileMenu();
        }
    }
}

function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const menuIcon = document.getElementById('menu-icon');
    if (!sidebar) return;
    
    const isMobileHidden = sidebar.classList.contains('hidden');
    
    if (isMobileHidden) {
        sidebar.classList.remove('hidden');
        sidebar.classList.add('fixed', 'inset-0', 'top-16', 'bg-white', 'z-40', 'p-4', 'block');
        if(menuIcon) menuIcon.setAttribute('data-lucide', 'x');
    } else {
        sidebar.classList.add('hidden');
        sidebar.classList.remove('fixed', 'inset-0', 'top-16', 'bg-white', 'z-40', 'p-4', 'block');
        if(menuIcon) menuIcon.setAttribute('data-lucide', 'menu');
    }
    lucide.createIcons();
}

function toggleEditMode(isEditing) {
    const editBtnContainer = document.getElementById('edit-toggle-container');
    const editActions = document.getElementById('edit-actions');
    const footer = document.getElementById('view-info-footer');

    if (isEditing) {
        if(editBtnContainer) editBtnContainer.classList.add('hidden');
        if(editActions) {
            editActions.classList.remove('hidden-actions');
            editActions.classList.add('active');
        }
        if(footer) footer.classList.add('hidden');

        renderInputField('name-field-container', 'input-name', user.name);
        renderInputField('nickname-field-container', 'input-nickname', user.nickname);
        renderInputField('email-field-container', 'input-email', user.email, 'email');
        renderPhoneField();
    } else {
        if(editBtnContainer) editBtnContainer.classList.remove('hidden');
        if(editActions) {
            editActions.classList.add('hidden-actions');
            editActions.classList.remove('active');
        }
        if(footer) footer.classList.remove('hidden');

        document.getElementById('name-field-container').innerHTML = `<p class="static-field">${user.name}</p>`;
        document.getElementById('nickname-field-container').innerHTML = `<p class="static-field">${user.nickname}</p>`;
        document.getElementById('email-field-container').innerHTML = `<p class="static-field">${user.email}</p>`;
        document.getElementById('phone-field-container').innerHTML = `<p class="static-field">${user.phone}</p>`;
    }
}

function renderInputField(containerId, inputId, value, type = 'text') {
    const container = document.getElementById(containerId);
    if(!container) return;
    container.innerHTML = `
        <input 
            id="${inputId}"
            type="${type}" 
            value="${value}" 
            class="w-full px-4 py-3 rounded-2xl bg-white border border-[#00AEEF] focus:ring-2 focus:ring-[#00AEEF]/20 outline-none transition-all text-sm font-semibold"
        />
    `;
}

function renderPhoneField() {
    const container = document.getElementById('phone-field-container');
    if(!container) return;
    container.innerHTML = `
        <div class="flex flex-col sm:flex-row gap-2">
            <input 
                id="input-phone"
                type="tel" 
                value="${user.phone}" 
                class="flex-grow px-4 py-3 rounded-2xl bg-white border border-[#00AEEF] focus:ring-2 focus:ring-[#00AEEF]/20 outline-none transition-all text-sm font-semibold"
            />
            <button class="px-6 py-3 bg-gray-100 text-gray-600 rounded-2xl text-sm font-bold hover:bg-gray-200 transition-colors">인증번호 발송</button>
        </div>
    `;
}

function saveUserInfo() {
    const nameVal = document.getElementById('input-name')?.value;
    const nickVal = document.getElementById('input-nickname')?.value;
    const emailVal = document.getElementById('input-email')?.value;
    const phoneVal = document.getElementById('input-phone')?.value;

    if(nameVal) user.name = nameVal;
    if(nickVal) user.nickname = nickVal;
    if(emailVal) user.email = emailVal;
    if(phoneVal) user.phone = phoneVal;

    document.querySelectorAll('.user-name-display').forEach(el => el.innerText = user.name);
    document.querySelectorAll('.user-email-display').forEach(el => el.innerText = user.email);

    toggleEditMode(false);
}

function renderBookings() {
    const recentList = document.getElementById('recent-bookings-list');
    const allList = document.getElementById('all-bookings-list');

    if (!recentList || !allList) return;

    if (bookings.length === 0) {
        const emptyHtml = `
            <div class="flex flex-col items-center justify-center py-16 bg-white rounded-3xl border border-dashed border-gray-200 shadow-sm">
                <div class="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center text-gray-300 mb-4">
                    <i data-lucide="calendar-x" size="32"></i>
                </div>
                <p class="text-gray-500 font-medium">최근 예약 내역이 없습니다.</p>
                <p class="text-gray-400 text-sm mt-1">DESTINO와 함께 새로운 여행을 계획해보세요!</p>
                <button class="mt-6 px-6 py-3 bg-[#00AEEF] text-white rounded-2xl font-bold text-sm hover:shadow-lg transition-all">여행지 구경하기</button>
            </div>
        `;
        recentList.innerHTML = emptyHtml;
        allList.innerHTML = emptyHtml;
    } else {
        // 예약 내역이 있을 때의 로직은 이전과 동일하게 유지 가능
    }
    lucide.createIcons();
}

window.onload = () => {
    lucide.createIcons();
    renderBookings();
};