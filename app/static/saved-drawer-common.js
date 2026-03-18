(() => {
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalizeKrwPriceText(text) {
    const raw = String(text || "").trim();
    if (!raw) return "";
    const match = raw.match(/([\d,]+(?:\.\d+)?)/);
    if (!match) return "";
    const amount = Number(String(match[1]).replace(/,/g, ""));
    if (!Number.isFinite(amount) || amount <= 0) return "";
    return `₩${Math.floor(amount).toLocaleString("ko-KR")}`;
  }

  function isLikelyPriceMetaLine(text) {
    const raw = String(text || "").trim();
    if (!raw) return false;
    if (/^(출발|도착|오는편\s*출발|오는편\s*도착)\b/.test(raw)) return false;
    if (!/[\d,]+/.test(raw)) return false;
    return /(₩|원|krw|KRW|~)/.test(raw) || /^[\d,\.\s]+$/.test(raw);
  }

  function getTypeLabel(itemType) {
    const type = String(itemType || "").toLowerCase();
    if (type === "flight") return "항공";
    if (type === "hotel" || type === "stay" || type === "accommodation") return "숙박";
    if (type === "rental" || type === "rentcar" || type === "rentalcar") return "렌터카";
    if (type === "ticket" || type === "tour") return "티켓";
    if (type === "package" || type === "flight_hotel") return "패키지";
    if (type === "groupbuy" || type === "travel-group") return "공동구매";
    return type ? type.toUpperCase() : "ITEM";
  }

  function countryKey(country) {
    const c = String(country || "").toLowerCase();
    if (c.includes("일본") || c.includes("japan")) return "japan";
    if (c.includes("베트남") || c.includes("vietnam")) return "vietnam";
    if (c.includes("태국") || c.includes("thailand")) return "thailand";
    if (c.includes("프랑스") || c.includes("france")) return "france";
    if (c.includes("미국") || c.includes("usa") || c.includes("united states")) return "usa";
    if (c.includes("이탈리아") || c.includes("italy")) return "italy";
    if (c.includes("스페인") || c.includes("spain")) return "spain";
    if (c.includes("영국") || c.includes("uk") || c.includes("united kingdom")) return "uk";
    return "default";
  }

  const countryImageMap = {
    japan: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=800&q=80",
    vietnam: "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=800&q=80",
    thailand: "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=800&q=80",
    france: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=800&q=80",
    usa: "https://images.unsplash.com/photo-1485738422979-f5c462d49f74?auto=format&fit=crop&w=800&q=80",
    italy: "https://images.unsplash.com/photo-1525874684015-58379d421a52?auto=format&fit=crop&w=800&q=80",
    spain: "https://images.unsplash.com/photo-1543783207-ec64e4d95325?auto=format&fit=crop&w=800&q=80",
    uk: "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=800&q=80",
    default: "https://images.unsplash.com/photo-1488085061387-422e29b40080?auto=format&fit=crop&w=800&q=80",
  };

  function getAirlineLogoUrl(code) {
    if (!code) return "";
    return `https://images.kiwi.com/airlines/64x64/${encodeURIComponent(String(code).toUpperCase())}.png`;
  }

  function getItemImage(item, options = {}) {
    const payload = item?.payload || {};
    const direct =
      payload?.thumb_url ||
      payload?.image_url ||
      payload?.image ||
      payload?.photo_url ||
      payload?.photo ||
      payload?.thumbnail ||
      item?.image_url ||
      item?.image ||
      "";
    if (direct) return String(direct);
    if (String(item?.item_type || "").toLowerCase() === "flight") {
      return getAirlineLogoUrl(payload?.airline_code || "");
    }
    if (String(item?.item_type || "").toLowerCase() === "groupbuy" || String(item?.item_type || "").toLowerCase() === "travel-group") {
      return countryImageMap[countryKey(payload?.country)] || countryImageMap.default;
    }
    return String(options.fallbackImage || "");
  }

  function getMetaInfo(item) {
    const metaParts = String(item?.meta || "")
      .split("|")
      .map((x) => x.trim())
      .filter(Boolean);
    const detectedPriceMeta =
      metaParts.find((part) => isLikelyPriceMetaLine(part)) ||
      metaParts.find((part) => normalizeKrwPriceText(part));
    let price = normalizeKrwPriceText(detectedPriceMeta || "");
    if (!price) {
      price = normalizeKrwPriceText(
        item?.price ||
          item?.payload?.price_text ||
          item?.payload?.price ||
          item?.payload?.amount ||
          item?.payload?.total_price ||
          "",
      );
    }
    return {
      price,
      lines: metaParts.filter((part) => part && part !== detectedPriceMeta).slice(0, 3),
    };
  }

  function renderSavedItem(item, options = {}) {
    const imageUrl = getItemImage(item, options);
    const meta = getMetaInfo(item);
    const typeLabel = options.typeLabelFn
      ? options.typeLabelFn(item?.item_type, item)
      : getTypeLabel(item?.item_type);
    const source = String(item?.source || "saved-item");
    const kind = `${typeLabel} · ${source}`;
    const lines = meta.lines
      .map((line) => `<div class="${options.lineClass}">${escapeHtml(line)}</div>`)
      .join("");
    return `
      <${options.tagName || "li"} class="${options.itemClass}" data-saved-id="${Number(item?.id || 0)}">
        <div class="${options.thumbClass}">
          ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(item?.name || "")}" loading="lazy" onerror="this.remove()">` : ""}
        </div>
        <div class="${options.metaClass}">
          <div class="${options.typeClass}">${escapeHtml(kind)}</div>
          <div class="${options.nameClass}">${escapeHtml(item?.name || "-")}</div>
          ${meta.price ? `<div class="${options.priceClass}">${escapeHtml(meta.price)}</div>` : ""}
          ${lines}
        </div>
        <button type="button" class="${options.removeClass}" ${options.removeAttrName}="${Number(item?.id || 0)}" aria-label="삭제" title="삭제">×</button>
      </${options.tagName || "li"}>
    `;
  }

  function renderAlertItem(item, options = {}) {
    const status = String(item?.status || "pending");
    const statusLabel = status === "accepted" ? "수락됨" : status === "rejected" ? "거절됨" : "대기중";
    const statusClass = status === "accepted" ? "is-accepted" : status === "rejected" ? "is-rejected" : "is-pending";
    const incoming = String(item?.direction || "incoming") !== "mine";
    const requester = incoming
      ? `${escapeHtml(item?.requester_name || "-")}님이 요청했습니다`
      : `${escapeHtml(item?.requester_name || "작성자")}님의 응답`;
    const actions = options.actionHtml
      ? options.actionHtml(item, { incoming, status, statusClass, statusLabel })
      : "";
    const closeHtml = options.closeHtml ? options.closeHtml(item, { incoming, status, statusClass, statusLabel }) : "";
    return `
      <${options.tagName || "li"} class="${options.itemClass} saved-alert-card" data-alert-id="${Number(item?.id || 0)}">
        <div class="${options.metaClass}">
          <div class="${options.typeClass}">공동구매 · 참여요청</div>
          <div class="${options.nameClass}">${escapeHtml(item?.post_title || "-")}</div>
          <div class="${options.lineClass}">${requester}</div>
          ${item?.requester_email ? `<div class="${options.lineClass}">이메일: ${escapeHtml(item.requester_email)}</div>` : ""}
          ${item?.message ? `<div class="${options.lineClass}">${escapeHtml(item.message)}</div>` : ""}
          <div class="${options.lineClass}"><span class="saved-alert-status ${statusClass}">${statusLabel}</span></div>
          ${actions}
        </div>
        ${closeHtml}
      </${options.tagName || "li"}>
    `;
  }

  window.SavedDrawerCommon = {
    escapeHtml,
    normalizeKrwPriceText,
    isLikelyPriceMetaLine,
    getTypeLabel,
    getAirlineLogoUrl,
    getItemImage,
    getMetaInfo,
    renderSavedItem,
    renderAlertItem,
  };
})();
