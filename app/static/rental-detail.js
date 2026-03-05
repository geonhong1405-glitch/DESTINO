function loadTossPaymentsScript() {
  if (window.TossPayments) return Promise.resolve(window.TossPayments);
  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-toss-sdk="1"]');
    if (existing) {
      existing.addEventListener('load', () => resolve(window.TossPayments));
      existing.addEventListener('error', reject);
      return;
    }
    const s = document.createElement('script');
    s.src = 'https://js.tosspayments.com/v1/payment';
    s.async = true;
    s.dataset.tossSdk = '1';
    s.onload = () => resolve(window.TossPayments);
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const state = window.__RENTAL_DETAIL__ || {};
  const modal = document.getElementById('driverModal');
  const reserveBtn = document.getElementById('rentalReserveBtn');
  const form = document.getElementById('rentalCheckoutForm');
  const premiumInsurance = document.getElementById('premiumInsurance');
  const agreeTerms = document.getElementById('agreeTerms');
  const addonPriceText = document.getElementById('addonPriceText');
  const totalPriceText = document.getElementById('totalPriceText');
  if (!modal || !reserveBtn || !form) return;

  const basePrice = Number(state?.car?.price || 0);
  const rentalDays = Math.max(1, Number(state?.car?.rental_days || 1));
  const insurancePerDay = 44000;

  const renderPrice = () => {
    const addon = premiumInsurance?.checked ? insurancePerDay * rentalDays : 0;
    const total = Math.max(0, basePrice + addon);
    if (addonPriceText) addonPriceText.textContent = `+ ${addon.toLocaleString('ko-KR')} KRW`;
    if (totalPriceText) totalPriceText.textContent = `${total.toLocaleString('ko-KR')} KRW`;
  };
  premiumInsurance?.addEventListener('change', renderPrice);
  renderPrice();

  const close = () => {
    modal.classList.remove('is-open');
    modal.setAttribute('aria-hidden', 'true');
  };
  const open = () => {
    modal.classList.add('is-open');
    modal.setAttribute('aria-hidden', 'false');
  };

  async function ensureLoggedInForRentalDetail() {
    try {
      const res = await fetch('/api/me', { credentials: 'include' });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data?.ok && data?.user && data.user.id) return true;
    } catch (_e) {}
    if (confirm('로그인이 필요합니다. 로그인 페이지로 이동할까요?')) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      location.href = `/login?next=${next}`;
    }
    return false;
  }

  reserveBtn.addEventListener('click', async () => {
    if (!(await ensureLoggedInForRentalDetail())) return;
    open();
  });
  modal.querySelectorAll('[data-close-modal]').forEach((el) => el.addEventListener('click', close));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) close();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!agreeTerms?.checked) {
      alert('필수 약관에 동의해 주세요.');
      return;
    }
    const fd = new FormData(form);
    const addon = premiumInsurance?.checked ? insurancePerDay * rentalDays : 0;
    const total = Math.max(0, basePrice + addon);
    const carPayload = {
      ...(state.car || {}),
      insurance: {
        premium: !!premiumInsurance?.checked,
        insurance_per_day: insurancePerDay,
        rental_days: rentalDays,
        insurance_total: addon,
      },
      price: total,
      base_price: basePrice,
    };
    const body = {
      car: carPayload,
      driver: {
        last_name: String(fd.get('last_name') || '').trim(),
        first_name: String(fd.get('first_name') || '').trim(),
        birth_date: String(fd.get('birth_date') || '').trim(),
        email: String(fd.get('email') || '').trim(),
        phone: String(fd.get('phone') || '').trim(),
        license_country: String(fd.get('license_country') || '').trim().toUpperCase(),
        license_number: String(fd.get('license_number') || '').trim(),
      },
    };

    try {
      const doCheckout = () => fetch('/api/rental/checkout', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      let res = await doCheckout();
      if (res.status === 401) {
        try {
          const me = await fetch('/api/me', { credentials: 'include', cache: 'no-store' });
          const meData = await me.json().catch(() => ({}));
          if (me.ok && meData?.ok && meData?.user?.id) {
            res = await doCheckout();
          }
        } catch (_e) {}
        if (res.status === 401) {
          if (confirm('로그인이 필요합니다. 로그인 페이지로 이동할까요?')) {
            const next = encodeURIComponent(window.location.pathname + window.location.search);
            location.href = `/login?next=${next}`;
          }
          return;
        }
      }

      const checkout = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(checkout?.detail || `HTTP ${res.status}`);
      }

      if (checkout.payment_mode !== 'toss' || !checkout.toss_client_key) {
        close();
        alert(`[모의 결제] 주문번호: ${checkout.order_id}\n결제금액: ${Number(checkout.amount || 0).toLocaleString('ko-KR')}원`);
        return;
      }

      const TossPayments = await loadTossPaymentsScript();
      const toss = TossPayments(checkout.toss_client_key);
      await toss.requestPayment('카드', {
        amount: checkout.amount,
        orderId: checkout.order_id,
        orderName: checkout.order_name,
        customerName: `${body.driver.last_name} ${body.driver.first_name}`.trim(),
        customerEmail: body.driver.email,
        successUrl: checkout.success_url,
        failUrl: checkout.fail_url,
      });
    } catch (err) {
      alert(err?.message || '결제 준비 중 오류가 발생했습니다.');
    }
  });
});
