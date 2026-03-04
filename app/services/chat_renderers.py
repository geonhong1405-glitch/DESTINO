from datetime import datetime
from typing import Any, Optional


def flight_html_intro(state: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>??? ?? ???? ?? ????.</p><p>??? ?? ??? ??? ?? ??????</p>"
    top = rows[0]
    s0 = top["segments"][0] if top.get("segments") else {}
    top_price = (
        f"{int(top.get('price_krw')):,} KRW"
        if isinstance(top.get("price_krw"), (int, float))
        else f"{top.get('price')} {top.get('currency')}"
    )
    return (
        "<div style='margin-bottom:10px;padding:10px;border:1px solid #dbeafe;background:#eff6ff;'>"
        f"<b>?? ??</b>: {state.get('origin')} ? {state.get('destination')} ???? ????.<br>"
        f"<b>?? 1??</b>: {s0.get('departure','-')} ?? / {s0.get('arrival','-')} ?? / "
        f"{top.get('itinerary_duration') or s0.get('duration','-')} / {top_price}"
        "</div>"
    )


def flight_html_table(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    if not rows:
        return "<p>??? ?? ???? ?? ?????.</p>"

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
        f"<b>API ????</b> | ??: {meta.get('origin')} / ??: {meta.get('destination')} / "
        f"???: {meta.get('departure_date')} / ???: {meta.get('return_date') or '-'} / "
        f"??: ?? {meta.get('adults', 1)} / ?? {meta.get('children', 0)} / ?? {meta.get('infants', 0)} / ????: {meta.get('max_price') or '-'}"
        "</div>"
    )
    html += "<table border='1' style='border-collapse:collapse; width:100%; font-size:14px;'>"
    html += "<tr><th>?????</th><th>? ??</th><th>?? ??</th><th>??</th><th>? ????</th><th>??</th></tr>"
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
            "<details><summary style='cursor:pointer;'>?? ?? ??</summary>"
            f"<div style='margin-top:6px;line-height:1.5;'>{_segment_summary(row)}</div>"
            "</details></td></tr>"
        )
    html += "</table>"
    html += "<div style='margin-top:8px;color:#666;font-size:12px;'>? ????? ?? ?? ??? ??? ?? ?? ?????.</div>"
    return html


def product_html_list(items: list[dict[str, Any]], title: str = "\uC0C1\uD488 \uCD94\uCC9C") -> str:
    if not items:
        return "<div>\uCD94\uCC9C\uD560 \uC0C1\uD488\uC744 \uCC3E\uC9C0 \uBABB\uD588\uC5B4\uC694. \uB2E4\uB978 \uD0A4\uC6CC\uB4DC\uB85C \uB2E4\uC2DC \uC2DC\uB3C4\uD574 \uC8FC\uC138\uC694.</div>"

    lines: list[str] = []
    for i, it in enumerate(items[:8], 1):
        item_type = str(it.get("type") or "\uC0C1\uD488")
        name = str(it.get("name") or "\uCD94\uCC9C \uC0C1\uD488")
        price = it.get("price")
        currency = str(it.get("currency") or "KRW")
        location = str(it.get("location") or "")
        rating = it.get("rating")
        meta = str(it.get("meta") or "")
        photo = str(it.get("photo") or "")

        price_text = f"{int(price):,} {currency}" if isinstance(price, (int, float)) else "-"
        parts = [
            f"{i}) {name}",
            f"\uD0C0\uC785: {item_type}",
            f"\uAC00\uACA9: {price_text}",
        ]
        if rating is not None:
            try:
                parts.append(f"\uD3C9\uC810: {float(rating):.1f}")
            except Exception:
                parts.append(f"\uD3C9\uC810: {rating}")
        if location:
            parts.append(f"\uC704\uCE58: {location}")
        if meta:
            parts.append(f"\uC124\uBA85: {meta}")
        if photo:
            parts.append(f"\uC0AC\uC9C4: {photo}")

        lines.append(" | ".join(parts))

    return f"<div><b>{title}</b><br>{'<br>'.join(lines)}</div>"
