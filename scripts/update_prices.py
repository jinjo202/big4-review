#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
리포트의 '실시간 시세' 블록만 갱신한다.

설계 원칙 (중요):
  - 분석 본문은 2026-07-31 종가 기준으로 고정한다. 절대 건드리지 않는다.
    지수화 주가 SVG는 좌표가 하드코딩이고, 본문 서술("7/31 KOSPI +18%" 등)은
    특정 시점 분석이라 매일 갱신하면 논지와 숫자가 어긋난다.
  - 이 스크립트는 <!--LIVE:START--> ~ <!--LIVE:END--> 사이만 다시 쓴다.
  - 시총은 '7/31 시총 x (현재가 / 7/31 종가)' 스케일링이다. 발행주식수를 쓰지 않으므로
    리포트 기준선과 항상 내적 정합하며, 자사주 소각·증자 등은 반영되지 않는다.
"""
import json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
BASE_DATE = "2026-07-31"

# key: (표시명, 야후심볼, 7/31 종가, 7/31 시총, 시총통화, 표시통화기호, 색토큰)
T = [
    ("마이크로소프트", "MSFT",      464.72,   3450.0, "USD", "$",  "--msft"),
    ("아마존",         "AMZN",      271.58,   2930.0, "USD", "$",  "--amzn"),
    ("알파벳",         "GOOGL",     356.13,   4360.0, "USD", "$",  "--googl"),
    ("메타",           "META",      556.71,   1420.0, "USD", "$",  "--meta"),
    ("엔비디아",       "NVDA",      200.75,   4860.0, "USD", "$",  "--googl"),
    ("TSMC",          "2330.TW",   2425.0,   1950.0, "USD", "NT$", "--baseline"),
    ("마이크론",       "MU",        823.03,    929.5, "USD", "$",  "--amzn"),
    ("ASML",          "ASML",     1629.0,     633.6, "USD", "$",  "--meta"),
    ("샌디스크",       "SNDK",     1214.83,    179.9, "USD", "$",  "--up"),
    ("키옥시아",       "285A.T",  46500.0,     161.9, "USD", "¥",  "--down"),
    ("삼성전자",       "005930.KS", 262500.0, 1511.0, "KRW", "₩",  "--msft"),
    ("SK하이닉스",     "000660.KS", 1718000.0, 1255.0, "KRW", "₩", "--accent"),
]
FX = {"KRW": ("KRW=X", 1420.60)}


def fetch(sym):
    u = ("https://query1.finance.yahoo.com/v8/finance/chart/"
         + urllib.parse.quote(sym) + "?interval=1d&range=5d")
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            m = json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]["meta"]
            p = m.get("regularMarketPrice")
            if p:
                return float(p)
        except Exception as e:
            if attempt == 2:
                print("  WARN %s: %s" % (sym, str(e)[:70]), file=sys.stderr)
            time.sleep(2)
    return None


def fmt_price(v, cur):
    if v is None:
        return "—"
    if cur in ("₩", "¥"):
        return "{:,.0f}".format(v)
    return "{:,.2f}".format(v)


def fmt_cap(v, cur):
    if cur == "KRW":
        return "₩{:,.0f}조".format(v)
    return "${:,.0f}B".format(v) if v < 1000 else "${:,.2f}T".format(v / 1000)


def main():
    krw = fetch(FX["KRW"][0]) or FX["KRW"][1]
    rows, missing = [], 0
    for name, sym, base_px, base_cap, cap_cur, px_cur, tok in T:
        px = fetch(sym)
        if px is None:
            missing += 1
            rows.append((name, sym, tok, "—", None, "—", "—"))
            continue
        chg = (px / base_px - 1) * 100
        cap = base_cap * (px / base_px)
        cap_s = fmt_cap(cap, cap_cur)
        if cap_cur == "USD":
            cap_s += ' <span class="note">(₩{:,.0f}조)</span>'.format(cap * krw / 1000)
        rows.append((name, sym, tok, fmt_price(px, px_cur), chg, cap_s, px_cur))
        time.sleep(0.35)

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    h = ['<!--LIVE:START-->']
    h.append('<figure><figcaption>실시간 시세 — 7월 31일 종가 대비</figcaption>')
    h.append('<p class="figsub">이 블록만 매일 자동 갱신된다. <strong>분석 본문의 수치는 7/31 종가 기준으로 고정</strong>이며 여기 숫자와 다를 수 있다.</p>')
    h.append('<div class="tblwrap"><table><thead><tr><th>종목</th><th>현재가</th><th>7/31 대비</th><th>시총(환산)</th></tr></thead><tbody>')
    for name, sym, tok, px, chg, cap, cur in rows:
        if chg is None:
            cls, chg_s = "note", "조회 실패"
        else:
            cls = "pos" if chg >= 0 else "neg"
            chg_s = "{:+.1f}%".format(chg)
        h.append('<tr><td class="co"><span class="dot" style="background:var({})"></span>{}</td>'
                 '<td>{} {}</td><td class="{}">{}</td><td>{}</td></tr>'
                 .format(tok, name, cur if cur != "—" else "", px, cls, chg_s, cap))
    h.append('</tbody></table></div>')
    h.append('<p class="note">갱신 {} · 출처 야후 파이낸스 · 종가/지연 시세이며 실시간이 아니다. '
             'USD/KRW <b>{:,.1f}</b> 적용. '
             '<b>시총은 발행주식수가 아니라 "7/31 시총 × 주가 변동"으로 환산</b>한 값이라 '
             '자사주 소각·증자 등은 반영되지 않으며, 해외 상장 종목은 환율 변동이 시총 스케일링에 반영되지 않는다. '
             'TSMC는 대만 본토(2330.TW), 키옥시아는 도쿄(285A.T) 기준.</p>'
             .format(now, krw))
    h.append('</figure>')
    h.append('<!--LIVE:END-->')
    block = "\n".join(h)

    pat = re.compile(r"<!--LIVE:START-->.*?<!--LIVE:END-->", re.S)
    changed = 0
    for f in ("big4-semis-q2-2026-review.html", "index.html"):
        s = open(f, encoding="utf-8").read()
        if not pat.search(s):
            print("ERROR: %s 에 LIVE 마커가 없다" % f, file=sys.stderr)
            return 1
        s2 = pat.sub(lambda m: block, s)
        if s2 != s:
            open(f, "w", encoding="utf-8", newline="").write(s2)
            changed += 1
    print("갱신 완료: %d개 파일 · 조회 실패 %d종목 · USD/KRW %.1f" % (changed, missing, krw))
    if missing >= len(T):
        print("ERROR: 전 종목 조회 실패 — 커밋하지 않는다", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
