# -*- coding: utf-8 -*-
"""
대본 데이터 자동 수집기  —  주식 지식 없이도 쓸 수 있게 만든 도구

사용법
    python collect.py 삼성전자
    python collect.py 000660
    python collect.py 삼성전자 > brief.md      (파일로 저장)
    python collect.py --doctor                 (인터넷 연결 점검 — 중국 등에서 먼저 실행)

하는 일
    1. 종목명 -> 종목코드 자동 변환
    2. 현재가/등락률/거래량  (장중이면 실시간, 마감 후면 종가)
    3. 코스피/코스닥/코스피200 등락률
    4. 코스피 상승/하락 종목 수
    5. 시장 전체 외국인/기관/개인 순매매 (조 단위)
    6. 종목별 외국인/기관 순매매 (주 단위)
    7. 일봉 좌표 (고점, 저점, 매물대, 이동평균)
    8. RSI 계산
    9. 지금 시각에 맞는 대본 프리셋과 제목 태그 추천
   10. 위 전부를 대본용 브리프로 출력

외부 패키지 필요 없음. Python 3.7+
"""

import sys, json, re, time, argparse
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KST = timezone(timedelta(hours=9))
UA_M = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"}
UA_D = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 20


# ────────────────────────────── 네트워크 ──────────────────────────────

def find_insane_search():
    """insane-search 엔진이 설치돼 있으면 경로를 돌려준다. 없으면 None."""
    import os, glob as _g
    cands = []
    if os.environ.get("INSANE_SEARCH_PATH"):
        cands.append(os.environ["INSANE_SEARCH_PATH"])
    home = os.path.expanduser("~")
    cands += _g.glob(os.path.join(home, ".claude", "plugins", "cache", "*", "insane-search", "*", "skills", "insane-search"))
    cands += _g.glob(os.path.join(home, ".codex", "**", "insane-search"), recursive=True)
    cands += _g.glob(os.path.join(home, "insane-search"))
    for base in cands:
        if os.path.isdir(os.path.join(base, "engine")):
            return base
    return None


def _insane_fetch(url):
    """3차 폴백 — insane-search 엔진 (선택 설치).

    WAF·봇탐지·외국 IP 차단은 뚫습니다.
    다만 국가 단위 네트워크 차단은 뚫지 못합니다. 그 경우엔 VPN이 답입니다.
    VPN을 한국으로 켜면 애초에 막힐 일이 없어 이 폴백은 거의 쓰이지 않습니다.
    """
    base = find_insane_search()
    if not base:
        return None
    if base not in sys.path:
        sys.path.insert(0, base)
    try:
        from engine import fetch as _f          # noqa
        r = _f(url, device_class="auto", timeout=25)
        if getattr(r, "ok", False):
            return r.content
    except Exception:
        pass
    return None


def _fetch(url, headers=UA_M, decode=None, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            raw = urllib.request.urlopen(req, timeout=TIMEOUT).read()
            if decode:
                return raw.decode(decode, errors="ignore")
            return raw.decode("utf-8", errors="ignore")
        except Exception as e:
            last = e
            if i < retries:
                time.sleep(1.2)
    hard = _insane_fetch(url)                        # 마지막 시도
    if hard:
        return hard
    raise RuntimeError(f"접속 실패: {url}\n  → {last}")


def _json(url, headers=UA_M):
    return json.loads(_fetch(url, headers))


def _num(s):
    """'1,550,000' -> 1550000 / '-14.65' -> -14.65"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return s
    t = re.sub(r"[^\d.\-]", "", str(s))
    if t in ("", "-", "."):
        return None
    return float(t) if "." in t else int(t)


def _man(n):
    """1550000 -> '155만 원' 처럼 TTS가 읽기 좋은 한글 표기"""
    if n is None:
        return "-"
    n = int(n)
    eok, rest = divmod(n, 100_000_000)
    man, won = divmod(rest, 10_000)
    parts = []
    if eok:
        parts.append(f"{eok}억")
    if man:
        parts.append(f"{man:,}만")
    if won:
        parts.append(f"{won:,}")
    return (" ".join(parts) or "0") + " 원"


def _jo(eok):
    """억 단위 숫자 -> '4조 5,009억 원'"""
    if eok is None:
        return "-"
    sign = "-" if eok < 0 else ""
    v = abs(int(eok))
    jo, rest = divmod(v, 10_000)
    if jo:
        return f"{sign}{jo}조 {rest:,}억 원" if rest else f"{sign}{jo}조 원"
    return f"{sign}{v:,}억 원"


# ────────────────────────────── 종목 조회 ──────────────────────────────

FALLBACK_CODES = {
    "삼성전자": "005930", "sk하이닉스": "000660", "하이닉스": "000660",
    "삼성전기": "009150", "삼성sdi": "006400", "lg에너지솔루션": "373220",
    "현대차": "005380", "기아": "000270", "네이버": "035420", "naver": "035420",
    "카카오": "035720", "셀트리온": "068270", "한미반도체": "042700",
    "lg이노텍": "011070", "하이브": "352820", "sk텔레콤": "017670",
    "포스코홀딩스": "005490", "두산에너빌리티": "034020", "한화에어로스페이스": "012450",
    "삼성바이오로직스": "207940", "kb금융": "105560", "신한지주": "055550",
}


def resolve_code(q):
    q = q.strip()
    if re.fullmatch(r"\d{6}", q):
        return q, None
    try:
        d = _json("https://m.stock.naver.com/api/search/all?query=" + urllib.parse.quote(q))
        for bucket in ("stocks", "searchResults", "result"):
            items = d.get(bucket) or []
            for it in items:
                code = it.get("code") or it.get("itemCode") or it.get("reutersCode")
                name = it.get("name") or it.get("stockName")
                if code and re.fullmatch(r"\d{6}", str(code)):
                    return str(code), name
    except Exception:
        pass
    hit = FALLBACK_CODES.get(q.lower().replace(" ", ""))
    if hit:
        return hit, q
    raise SystemExit(
        f"\n[!] '{q}' 종목코드를 못 찾았습니다.\n"
        f"    6자리 숫자 코드로 다시 실행해 주세요.  예)  python collect.py 005930\n"
        f"    코드는 네이버 금융에서 종목 검색하면 주소창에 나옵니다.\n"
    )


# ────────────────────────────── 수집 ──────────────────────────────

def get_quote(code):
    """현재가/등락률/거래량 + 장중 여부. 네이버 실패 시 야후로 폴백."""
    try:
        d = _json(f"https://m.stock.naver.com/api/stock/{code}/basic")
        return {
            "source": "naver",
            "name": d.get("stockName"),
            "price": _num(d.get("closePrice")),
            "diff": _num(d.get("compareToPreviousClosePrice")),
            "rate": _num(d.get("fluctuationsRatio")),
            "volume": _num(d.get("accumulatedTradingVolume")),
            "status": d.get("marketStatus"),
            "traded_at": d.get("localTradedAt"),
        }
    except Exception as e:
        try:
            y = _json(f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.KS?range=5d&interval=1d", UA_D)
            m = y["chart"]["result"][0]["meta"]
            p, pc = m.get("regularMarketPrice"), m.get("previousClose") or m.get("chartPreviousClose")
            return {
                "source": "yahoo(폴백)", "name": m.get("symbol"), "price": p,
                "diff": (p - pc) if (p and pc) else None,
                "rate": round((p / pc - 1) * 100, 2) if (p and pc) else None,
                "volume": m.get("regularMarketVolume"), "status": None, "traded_at": None,
                "warn": f"네이버 접속 실패로 야후 데이터 사용 ({e})",
            }
        except Exception as e2:
            raise RuntimeError(f"시세 수집 실패 (네이버·야후 모두)\n  네이버: {e}\n  야후: {e2}")


def get_ohlcv(code, days=140):
    end = datetime.now(KST).strftime("%Y%m%d")
    start = (datetime.now(KST) - timedelta(days=days * 2)).strftime("%Y%m%d")
    txt = _fetch(f"https://api.finance.naver.com/siseJson.naver?symbol={code}"
                 f"&requestType=1&startTime={start}&endTime={end}&timeframe=day", UA_D)
    rows = re.findall(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*(\d+)', txt)
    return [{"date": r[0], "open": float(r[1]), "high": float(r[2]),
             "low": float(r[3]), "close": float(r[4]), "vol": int(r[5])} for r in rows]


def get_index(sym):
    txt = _fetch(f"https://api.finance.naver.com/siseJson.naver?symbol={sym}&requestType=1"
                 f"&startTime={(datetime.now(KST)-timedelta(days=20)).strftime('%Y%m%d')}"
                 f"&endTime={datetime.now(KST).strftime('%Y%m%d')}&timeframe=day", UA_D)
    rows = re.findall(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', txt)
    if len(rows) < 2:
        return None
    cur, prev = float(rows[-1][4]), float(rows[-2][4])
    return {"date": rows[-1][0], "close": cur, "prev": prev,
            "rate": round((cur / prev - 1) * 100, 2)}


def get_updown(mkt="KOSPI", max_pages=26):
    """상승/하락 종목 수. 페이지를 병렬로 받는다 (VPN 환경에서 순차 요청은 너무 느림)."""
    from concurrent.futures import ThreadPoolExecutor

    def page(p):
        try:
            return _json(f"https://m.stock.naver.com/api/stocks/marketValue/{mkt}?page={p}&pageSize=100").get("stocks", [])
        except Exception:
            return []

    up = down = flat = 0
    seen = set()
    with ThreadPoolExecutor(max_workers=6) as ex:
        for st in ex.map(page, range(1, max_pages + 1)):
            for s in st:
                if s.get("stockEndType") != "stock":
                    continue
                c = s.get("itemCode")
                if not c or c in seen:
                    continue
                seen.add(c)
                r = _num(s.get("fluctuationsRatio"))
                if r is None:
                    continue
                if r > 0:
                    up += 1
                elif r < 0:
                    down += 1
                else:
                    flat += 1
    return {"up": up, "down": down, "flat": flat, "total": len(seen)}


def get_market_flow():
    """시장 전체 투자자별 순매매 (단위: 백만원 -> 억원 변환). bizdate 필수."""
    for back in range(0, 6):                       # 오늘부터 최대 5영업일 거슬러 시도
        d = (datetime.now(KST) - timedelta(days=back)).strftime("%Y%m%d")
        try:
            h = _fetch(f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate={d}&sosok=01",
                       UA_D, decode="euc-kr")
        except Exception:
            continue
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
            cells = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", " ", c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            cells = [c for c in cells if c]
            if len(cells) >= 4 and re.match(r"\d{2}\.\d{2}\.\d{2}", cells[0]):
                # 네이버 표기 단위 = 억원 (페이지 헤더 '단위:억원'), 변환 없이 그대로 사용
                return {"date": cells[0],
                        "person": _num(cells[1]),
                        "foreign": _num(cells[2]),
                        "inst": _num(cells[3])}
    return None


def get_news(code, limit=12):
    """종목 관련 뉴스 헤드라인. 대본의 '재료' 부분에 쓴다."""
    import html as _h
    # Referer 없이 요청하면 목록이 1건만 내려온다 (6KB vs 17KB). 반드시 붙일 것.
    h = _fetch(f"https://finance.naver.com/item/news_news.naver?code={code}&page=1",
               {**UA_D, "Referer": "https://finance.naver.com/"}, decode="euc-kr")
    out, seen = [], set()
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        t = re.search(r"news_read[^>]*>\s*(.*?)\s*</a>", r, re.S)
        if not t:
            continue
        title = _h.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip()
        title = re.sub(r"\.{3,}\s*$", "", title).strip()
        if len(title) < 8:
            continue
        key = re.sub(r"[^가-힣]", "", title)[:14]
        if key in seen:
            continue
        seen.add(key)
        src = re.search(r'class="info"[^>]*>\s*(.*?)\s*<', r, re.S)
        dt = re.search(r'class="date"[^>]*>\s*(.*?)\s*<', r, re.S)
        out.append({"title": title,
                    "src": src.group(1).strip() if src else "",
                    "date": dt.group(1).strip() if dt else ""})
        if len(out) >= limit:
            break
    return out


def get_stock_flow(code):
    """종목별 외국인/기관/개인 순매매 (주 단위). trend API 우선, 실패 시 HTML 스크랩."""
    try:
        d = _json(f"https://m.stock.naver.com/api/stock/{code}/trend")
        out = []
        for r in d[:5]:
            out.append({"date": r.get("bizdate"),
                        "foreign": _num(r.get("foreignerPureBuyQuant")),
                        "inst": _num(r.get("organPureBuyQuant")),
                        "person": _num(r.get("individualPureBuyQuant")),
                        "frate": r.get("foreignerHoldRatio")})
        if out:
            return out
    except Exception:
        pass
    h = _fetch(f"https://finance.naver.com/item/frgn.naver?code={code}", UA_D, decode="euc-kr")
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        cells = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", " ", c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        cells = [c for c in cells if c]
        if len(cells) >= 7 and re.match(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
            out.append({"date": cells[0].replace(".", ""), "inst": _num(cells[5]),
                        "foreign": _num(cells[6]), "person": None,
                        "frate": cells[8] if len(cells) > 8 else None})
        if len(out) >= 5:
            break
    return out


# ────────────────────────────── 계산 ──────────────────────────────

def calc_rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 1)


def calc_levels(bars):
    """고점/저점/매물대/이동평균"""
    if not bars:
        return {}
    recent = bars[-120:] if len(bars) >= 120 else bars
    hi = max(recent, key=lambda b: b["high"])
    lo = min(recent, key=lambda b: b["low"])
    closes = [b["close"] for b in bars]
    ma = {p: round(sum(closes[-p:]) / p) for p in (5, 20, 60, 120) if len(closes) >= p}

    # 매물대: 최근 60봉을 가격 20구간으로 나눠 거래량이 몰린 밴드
    win = bars[-60:] if len(bars) >= 60 else bars
    lo_p = min(b["low"] for b in win); hi_p = max(b["high"] for b in win)
    band = None
    if hi_p > lo_p:
        step = (hi_p - lo_p) / 20
        buckets = {}
        for b in win:
            k = int((b["close"] - lo_p) / step) if step else 0
            k = min(k, 19)
            buckets[k] = buckets.get(k, 0) + b["vol"]
        top = sorted(buckets, key=buckets.get, reverse=True)[:3]
        band = (round(lo_p + min(top) * step), round(lo_p + (max(top) + 1) * step))
    return {"high": {"price": hi["high"], "date": hi["date"]},
            "low": {"price": lo["low"], "date": lo["date"]},
            "ma": ma, "band": band}


def pick_preset():
    """지금 시각(KST)으로 대본 프리셋과 제목 태그를 정한다"""
    now = datetime.now(KST)
    hm = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return ("③ 개장전 검증형", "*새벽 속보*", "날개", "주말 — 다음 거래일 개장전 편으로 씁니다")
    if hm < 9 * 60:
        return ("③ 개장전 검증형", "*새벽 속보*", "날개", "장 시작 전")
    if hm < 15 * 60 + 20:
        return ("② 장중 폭락/급등형", "*5분전 속보*", "힘", "장중 — 실시간 현재가 기준")
    if hm < 16 * 60:
        return ("② 장마감형", "*장마감 속보*", "힘", "장 마감 직후")
    return ("② 시간외형", "*시외 속보*", "힘", "시간외 거래 시간대")


# ────────────────────────────── 점검 모드 ──────────────────────────────

def doctor():
    print("=" * 62)
    print("■ 연결 점검 — 중국 등 해외에서 먼저 실행하세요")
    print("=" * 62)
    tests = [
        ("종목 시세 (필수)",       lambda: _json("https://m.stock.naver.com/api/stock/005930/basic")["stockName"]),
        ("일봉 데이터 (필수)",      lambda: f"{len(get_ohlcv('005930', 30))}봉"),
        ("지수 (필수)",            lambda: f"{get_index('KOSPI')['rate']}%"),
        ("상승/하락 종목수 (선택)", lambda: f"상승 {get_updown('KOSPI', 3)['up']} (일부만 확인)"),
        ("시장 수급 (필수)",       lambda: f"{get_market_flow()['date']}"),
        ("종목 수급 (필수)",       lambda: f"{get_stock_flow('005930')[0]['date']}"),
        ("야후 폴백 (예비)",       lambda: _json("https://query1.finance.yahoo.com/v8/finance/chart/005930.KS?range=5d&interval=1d", UA_D)["chart"]["result"][0]["meta"]["currency"]),
        ("뉴스 (선택)",           lambda: f"{len(get_news('005930', 3))}건"),
    ]
    ok = 0
    for name, fn in tests:
        try:
            r = fn()
            print(f"  [정상] {name:24s} {r}")
            ok += 1
        except Exception as e:
            print(f"  [실패] {name:24s} {str(e)[:70]}")
    print("-" * 62)
    _is = find_insane_search()
    print(f"  [{'설치됨' if _is else '없음  '}] 우회 엔진 (insane-search)  "
          f"{'— 접속이 막힐 때만 씁니다' if _is else '— VPN 한국이면 필요 없습니다'}")
    print("-" * 62)
    if ok == len(tests):
        print("  전부 정상입니다. collect.py 그냥 쓰시면 됩니다.")
    elif ok == 0:
        print("  전부 실패했습니다. 한국 서버 접속이 막혀 있습니다.")
        print("  -> VPN을 한국 또는 일본으로 연결한 뒤 다시 실행하세요.")
    else:
        print("  일부만 됩니다. VPN 연결 후 다시 실행하는 걸 권합니다.")
        print("  '필수' 항목이 하나라도 실패하면 대본 데이터가 불완전해집니다.")
    print()


# ────────────────────────────── 출력 ──────────────────────────────

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("query", nargs="?")
    ap.add_argument("--doctor", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.doctor:
        doctor(); return
    if not a.query:
        print(__doc__); return

    t0 = time.time()
    code, nm = resolve_code(a.query)

    def step(msg, fn, default=None):
        print(f"  … {msg}", end="", file=sys.stderr, flush=True)
        t = time.time()
        try:
            r = fn()
            print(f"\r  [완료] {msg} ({time.time()-t:.1f}초)      ", file=sys.stderr)
            return r
        except Exception as e:
            print(f"\r  [실패] {msg} — {str(e)[:50]}", file=sys.stderr)
            return default

    print(f"[{a.query} ({code})] 수집 시작 — VPN 환경에서는 30초쯤 걸릴 수 있습니다", file=sys.stderr)

    q = step("시세", lambda: get_quote(code))
    if q is None:
        raise RuntimeError("시세를 못 가져왔습니다. python collect.py --doctor 를 먼저 실행하세요.")
    bars = step("일봉 차트", lambda: get_ohlcv(code), [])
    lv = calc_levels(bars)
    rsi = calc_rsi([b["close"] for b in bars]) if bars else None
    preset, tag, keyword, when = pick_preset()

    idx = {}
    def _idx():
        for k, s in (("코스피", "KOSPI"), ("코스닥", "KOSDAQ"), ("코스피200", "KPI200")):
            try: idx[k] = get_index(s)
            except Exception: idx[k] = None
        return idx
    step("지수 3개", _idx, {})
    ud = step("상승/하락 종목수 (오래 걸림)", lambda: get_updown("KOSPI"))
    mf = step("시장 전체 수급", get_market_flow)
    sf = step("종목 수급", lambda: get_stock_flow(code), [])
    nw = step("뉴스 헤드라인", lambda: get_news(code), [])
    print(f"[수집 완료] 총 {time.time()-t0:.1f}초\n", file=sys.stderr)

    name = q.get("name") or nm or a.query
    now = datetime.now(KST)

    if a.json:
        print(json.dumps({"code": code, "name": name, "quote": q, "levels": lv, "rsi": rsi,
                          "index": idx, "updown": ud, "market_flow": mf, "stock_flow": sf,
                          "preset": preset, "tag": tag, "keyword": keyword},
                         ensure_ascii=False, indent=1, default=str))
        return

    P = print
    P(f"# 대본 브리프 — {name} ({code})")
    P("")
    P(f"- 수집 시각 : {now.strftime('%Y년 %m월 %d일 %H시 %M분')} (한국시간)")
    P(f"- 장 상태   : {q.get('status') or '알 수 없음'}   ({when})")
    P(f"- 데이터 출처: {q.get('source')}")
    if q.get("warn"):
        P(f"- ⚠ {q['warn']}")
    P("")
    P("## 1. 대본 설정 (자동 판정)")
    P("")
    P(f"| 항목 | 값 |")
    P(f"|---|---|")
    P(f"| 프리셋 | **{preset}** |")
    P(f"| 제목 태그 | `{tag}` |")
    P(f"| 댓글 키워드 | **{keyword}** |")
    P(f"| 목표 분량 | **4,000자 (약 9분 30초)** |")
    P("")
    P("## 2. 시세")
    P("")
    P(f"- 현재가/종가 : **{_man(q['price'])}**  ({int(q['price']):,}원)")
    P(f"- 전일 대비   : {int(q['diff']):,}원  (**{q['rate']}%**)")
    vol = q.get("volume") or (bars[-1]["vol"] if bars else None)
    P(f"- 거래량      : {int(vol):,}주" if vol else "- 거래량      : -")
    if bars:
        b = bars[-1]
        P(f"- 당일 시/고/저 : {int(b['open']):,} / {int(b['high']):,} / {int(b['low']):,}")
    P("")
    P("## 3. 시장 전체")
    P("")
    for k, v in idx.items():
        P(f"- {k} : **{v['rate']}%**  ({v['close']:,.2f})" if v else f"- {k} : 수집 실패")
    if ud:
        P(f"- **코스피 상승 {ud['up']}개 / 보합 {ud['flat']}개 / 하락 {ud['down']}개**  (전체 {ud['total']}종목)")
    else:
        P("- 상승/하락 종목수 : 수집 실패")
    P("")
    P("## 4. 수급")
    P("")
    today8 = now.strftime("%Y%m%d")
    if mf:
        fresh = mf["date"].replace(".", "") == today8[2:]
        P(f"코스피 전체 ({mf['date']} 기준)")
        P(f"- 외국인 : **{_jo(mf['foreign'])}**")
        P(f"- 개인   : **{_jo(mf['person'])}**")
        P(f"- 기관   : **{_jo(mf['inst'])}**")
        if not fresh:
            P("")
            P(f"> 🚨 **이 수급은 오늘 것이 아니라 {mf['date']} 것입니다.**")
            P("> 대본에서 '지금 외국인이 …' 라고 쓰면 안 됩니다.")
            P("> **이 수치를 아예 빼거나**, '전 거래일 기준' 이라고 명시하세요.")
    else:
        P("- 시장 수급 : 수집 실패 — 이 문단은 대본에서 빼세요")
    P("")
    if sf:
        sfresh = str(sf[0].get("date", "")) == today8
        P(f"{name} 종목별 (최근 3일, 단위: 주)")
        P("")
        P("| 날짜 | 외국인 | 기관 | 개인 | 외국인 비율 |")
        P("|---|---|---|---|---|")
        for r in sf[:3]:
            d8 = str(r.get("date") or "")
            ds = f"{d8[4:6]}.{d8[6:8]}" if len(d8) == 8 else d8
            f = f"{int(r['foreign']):+,}" if r.get("foreign") is not None else "-"
            i = f"{int(r['inst']):+,}" if r.get("inst") is not None else "-"
            p = f"{int(r['person']):+,}" if r.get("person") is not None else "-"
            P(f"| {ds} | {f} | {i} | {p} | {r.get('frate') or '-'} |")
        if not sfresh:
            P("")
            P(f"> 🚨 **종목 수급도 오늘 것이 아닙니다.** 최신 = {sf[0].get('date')}")
    P("")
    P("## 5. 오늘 무슨 일이 있었나 (참고용)")
    P("")
    if nw:
        for r in nw[:8]:
            P(f"- {r['title']}  <sub>{r['src']} · {r['date']}</sub>")
        P("")
        P("> ### ⚠️ 대본에는 최대 1~2문장만 쓰세요")
        P(">")
        P("> 원본 채널은 뉴스를 **편당 평균 1문장**만 언급합니다 (전체 문장의 1.4%).")
        P("> 기사 제목을 읊는 문장은 **원본 53편에 단 한 건도 없습니다.**")
        P(">")
        P("> | | |")
        P("> |---|---|")
        P("> | ❌ | `KBS 보도에 따르면 중국발 반도체 충격으로…` (기사 인용) |")
        P("> | ❌ | 헤드라인 나열 |")
        P("> | ⭕ | `미국 반도체가 먼저 밀렸고 나스닥도 1퍼센트 넘게 빠졌습니다.` |")
        P("> | ⭕ | `오늘 일본 니케이도 4퍼센트 넘게 급락하고 있습니다.` |")
        P(">")
        P("> **위 헤드라인은 '무슨 일인지 파악용'입니다.** 대본에는 그 내용을")
        P("> **숫자가 든 시장 지표 한 줄**로 바꿔서 짚고 바로 넘어가세요.")
        P("> 헤드라인 밖의 사실을 추측해서 쓰면 안 됩니다.")
    else:
        P("- 수집 실패 — 재료 언급 없이 수급·차트만으로 쓰세요")
    P("")
    P("## 6. 차트 좌표")
    P("")
    if lv.get("high"):
        P(f"- 최근 고점 : **{_man(lv['high']['price'])}**  ({lv['high']['date'][:4]}년 {int(lv['high']['date'][4:6])}월 {int(lv['high']['date'][6:])}일)")
        P(f"- 최근 저점 : **{_man(lv['low']['price'])}**  ({lv['low']['date'][:4]}년 {int(lv['low']['date'][4:6])}월 {int(lv['low']['date'][6:])}일)")
    if lv.get("band"):
        P(f"- 매물대    : **{_man(lv['band'][0])} ~ {_man(lv['band'][1])}**  (최근 60일 거래 밀집 구간 — 추정치)")
    if lv.get("ma"):
        P(f"- 이동평균  : " + " / ".join(f"{p}일 {v:,}" for p, v in lv["ma"].items()))
        cur = q["price"]
        below = [f"{p}일선" for p, v in lv["ma"].items() if cur < v]
        P(f"- 현재가는 {', '.join(below)} **아래**에 있습니다." if below else "- 현재가는 모든 이동평균선 **위**에 있습니다.")
    P(f"- RSI(14)   : **{rsi}**  ({'과매도권' if rsi and rsi < 30 else '낮은 구간' if rsi and rsi < 45 else '중립' if rsi and rsi < 60 else '과열권'})")
    P("")
    P("---")
    P("")
    P("## 7. 이 브리프로 대본 만들기")
    P("")
    P("아래 한 줄을 그대로 입력하세요.")
    P("")
    P("```")
    P("이 브리프로 대본 써줘. AGENTS.md 규칙 전부 지켜서.")
    P("대본 + 제목 10개 + 썸네일 문구 + 설명란 + 태그까지 한 번에.")
    P("```")
    P("")
    P("> ⚠️ 매물대는 거래 밀집도로 계산한 **추정치**입니다. 정확한 값이 아닙니다.")
    P("> ⚠️ 수급·지수는 공개 데이터이지만, '세력의 의도'는 데이터가 아니라 해석입니다.")


if __name__ == "__main__":
    import urllib.parse
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n[오류] {e}\n\n연결 문제라면 먼저 이걸 실행하세요:\n    python collect.py --doctor\n", file=sys.stderr)
        sys.exit(1)
