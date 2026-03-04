from datetime import datetime
from typing import Any, Optional


def flight_html_intro(state: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>조건에 맞는 항공편을 찾지 못했어요.</p><p>출발/도착/날짜를 다시 확인해 주세요.</p>"
    top = rows[0]
    s0 = top["segments"][0] if top.get("segments") else {}
    top_price = (
        f"{int(top.get('price_krw')):,} KRW"
        if isinstance(top.get("price_krw"), (int, float))
        else f"{top.get('price')} {top.get('currency')}"
    )
    return (
        "<div style='margin-bottom:10px;padding:10px;border:1px solid #dbeafe;background:#eff6ff;'>"
        f"<b>검색 조건</b>: {state.get('origin')} -> {state.get('destination')} 기준 결과입니다.<br>"
        f"<b>추천 1건</b>: {s0.get('departure','-')} 출발 / {s0.get('arrival','-')} 도착 / "
        f"{top.get('itinerary_duration') or s0.get('duration','-')} / {top_price}"
        "</div>"
    )


def flight_html_table(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    if not rows:
        return "<p>조건에 맞는 항공편이 없습니다.</p>"

    def _fmt_dt(v: Optional[str]) -> str:
        if not v:
            return "-"
        try:
            return datetime.fromisoformat(v).strftime("%m-%d %H:%M")
        except Exception:
            return str(v)

    def _last_arrival(row: dict[str, Any]) -> Optional[str]:
        segs = row.get("segments") or []
        return (segs[-1] or {}).get("arrival") if segs else None

    def _segment_summary(row: dict[str, Any]) -> str:
        parts = []
        itin_legs = row.get("itinerary_segments")
        if isinstance(itin_legs, list) and itin_legs:
            for leg in itin_legs:
                for i, seg in enumerate(leg or [], 1):
                    dep_code = seg.get("departure_iata", "-")
                    arr_code = seg.get("arrival_iata", "-")
                    parts.append(
                        f"{i}) {seg.get('airline','-')} | {dep_code} {_fmt_dt(seg.get('departure'))} -> {arr_code} {_fmt_dt(seg.get('arrival'))} | {seg.get('duration','-')}"
                    )
        else:
            for i, seg in enumerate(row.get("segments") or [], 1):
                dep_code = seg.get("departure_iata", "-")
                arr_code = seg.get("arrival_iata", "-")
                parts.append(
                    f"{i}) {seg.get('airline','-')} | {dep_code} {_fmt_dt(seg.get('departure'))} -> {arr_code} {_fmt_dt(seg.get('arrival'))} | {seg.get('duration','-')}"
                )
        return "<br>".join(parts) if parts else "-"

    def _price_label(row: dict[str, Any]) -> str:
        krw = row.get("price_krw")
        if isinstance(krw, (int, float)):
            return f"{int(krw):,} KRW"
        return f"{row.get('price')} {row.get('currency')}"

    html = (
        "<div style='margin-bottom:10px;padding:8px;background:#f7f7f7;border:1px solid #ddd;'>"
        f"<b>API 조회 조건</b> | 출발: {meta.get('origin')} / 도착: {meta.get('destination')} / "
        f"가는날: {meta.get('departure_date')} / 오는날: {meta.get('return_date') or '-'} / "
        f"인원: 성인 {meta.get('adults', 1)} / 아동 {meta.get('children', 0)} / 유아 {meta.get('infants', 0)} / 최대가: {meta.get('max_price') or '-'}"
        "</div>"
    )
    html += "<table border='1' style='border-collapse:collapse; width:100%; font-size:14px;'>"
    html += "<tr><th>항공사</th><th>출발 시간</th><th>도착 시간</th><th>구분</th><th>총 소요</th><th>요금</th></tr>"
    for row in rows:
        stops = int(row.get("stops") or 0)
        route_badge = "직항" if stops == 0 else f"경유 {stops}회"
        html += (
            "<tr>"
            f"<td>{row.get('primary_airline','-')}</td>"
            f"<td>{_fmt_dt(row.get('first_departure'))}</td>"
            f"<td>{_fmt_dt(_last_arrival(row))}</td>"
            f"<td>{route_badge}</td>"
            f"<td>{row.get('itinerary_duration') or '-'}</td>"
            f"<td>{_price_label(row)}</td>"
            "</tr>"
        )
        html += (
            "<tr>"
            "<td colspan='6' style='background:#fafafa;padding:6px 8px;'>"
            "<details><summary style='cursor:pointer;'>구간 상세 보기</summary>"
            f"<div style='margin-top:6px;line-height:1.5;'>{_segment_summary(row)}</div>"
            "</details></td></tr>"
        )
    html += "</table>"
    html += "<div style='margin-top:8px;color:#666;font-size:12px;'>실시간 요금은 변동될 수 있어 결제 직전 다시 확인됩니다.</div>"
    return html


def product_html_list(items: list[dict[str, Any]], title: str = "상품 추천") -> str:
    if not items:
        return "<div>추천할 상품을 찾지 못했어요. 다른 키워드로 다시 시도해 주세요.</div>"

    lines: list[str] = []
    for i, it in enumerate(items[:8], 1):
        item_type = str(it.get("type") or "상품")
        name = str(it.get("name") or "추천 상품")
        price = it.get("price")
        currency = str(it.get("currency") or "KRW")
        location = str(it.get("location") or "")
        rating = it.get("rating")
        meta = str(it.get("meta") or "")
        photo = str(it.get("photo") or "")

        price_text = f"{int(price):,} {currency}" if isinstance(price, (int, float)) else "-"
        parts = [
            f"{i}) {name}",
            f"타입: {item_type}",
            f"가격: {price_text}",
        ]
        if rating is not None:
            try:
                parts.append(f"평점: {float(rating):.1f}")
            except Exception:
                parts.append(f"평점: {rating}")
        if location:
            parts.append(f"위치: {location}")
        if meta:
            parts.append(f"설명: {meta}")
        if photo:
            parts.append(f"사진: {photo}")

        lines.append(" | ".join(parts))

    return f"<div><b>{title}</b><br>{'<br>'.join(lines)}</div>"
