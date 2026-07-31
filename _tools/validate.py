# -*- coding: utf-8 -*-
"""
대본 최종 검증기 — 통과 못 하면 업로드 금지

사용법
    python _tools/validate.py 대본.txt brief.md

하는 일
    1. 대본에 나온 모든 숫자를 brief.md와 대조   ← AI가 지어낸 숫자를 잡는다
    2. 구조 검사 (후크 위치, 인사 위치, 고정 문구, CTA 배치, 분량)
    3. 말투 검사 (금지 단어, 예고 필러, 어미 비율)
    4. 금지 표현 검사 (목표가, 매수 권유)

결과
    합격  -> 종료 코드 0.  "합격.txt" 생성
    불합격 -> 종료 코드 1.  무엇을 고쳐야 하는지 한국어로 출력

외부 패키지 필요 없음. Python 3.7+
"""

import sys, os, re, json
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RATE = 7.04  # 자/초

# ────────────────────── 채널 설정 ──────────────────────
# ★ 채널마다 여기 두 줄만 바꾸면 됩니다.
PERSONA = "신민석프로"
PHONE   = "01054451634"        # TTS가 숫자로 또박또박 읽도록 하이픈 없이

# ────────────────────── 숫자 파싱 ──────────────────────

UNITS = [("조", 10**12), ("천억", 10**11), ("백억", 10**10), ("십억", 10**9),
         ("억", 10**8), ("천만", 10**7), ("백만", 10**6), ("십만", 10**5),
         ("만", 10**4), ("천", 10**3)]
UNIT_RE = "|".join(u for u, _ in UNITS)
UNIT_MAP = dict(UNITS)

# 한 덩어리 숫자 표현: "4조 5천억", "37만 4,500", "1,550,000", "13.39"
NUM_EXPR = re.compile(
    r"(?:\d[\d,]*(?:\.\d+)?\s*(?:" + UNIT_RE + r")?\s*)+"
)
NUM_PART = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(" + UNIT_RE + r")?")

# 데이터가 아닌 숫자 — 고정 문구·서수·날짜 등
WHITELIST_CTX = [
    r"돈\s*1\s*원", r"한\s*번씩", r"세\s*가지", r"첫째", r"둘째", r"셋째",
    r"하나만", r"한\s*마디", r"한\s*통", r"1위", r"두\s*자릿수",
    re.escape(PHONE),                     # 개인 번호는 데이터가 아니다
]
SMALL_OK = set(range(0, 13))          # 월, 서수 등 작은 정수는 통과


def parse_num(expr):
    """'4조 5천억' -> 4.5e12 / '37만 4,500' -> 374500 / '13.39' -> 13.39"""
    total, found = 0.0, False
    for m in NUM_PART.finditer(expr):
        raw, unit = m.group(1), m.group(2)
        if not raw:
            continue
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        total += v * (UNIT_MAP[unit] if unit else 1)
        found = True
    return total if found else None


def extract_numbers(text):
    """텍스트에서 (원문표기, 숫자값, 앞뒤문맥) 목록"""
    out = []
    for m in NUM_EXPR.finditer(text):
        s = m.group(0).strip()
        if not re.search(r"\d", s):
            continue
        v = parse_num(s)
        if v is None:
            continue
        ctx = text[max(0, m.start() - 25): m.end() + 15].replace("\n", " ")
        out.append((s, v, ctx))
    return out


# ────────────────────── TTS 정제 ──────────────────────

ENG_MAP = [
    ("S&P", "에스앤피"), ("M&A", "엠앤에이"),
    ("HBM", "에이치비엠"), ("RSI", "알에스아이"), ("FOMC", "에프오엠씨"),
    ("ETF", "이티에프"), ("ETN", "이티엔"), ("CEO", "씨이오"), ("GDP", "지디피"),
    ("CPI", "씨피아이"), ("PER", "피이알"), ("PBR", "피비알"), ("IPO", "아이피오"),
    ("SK", "에스케이"), ("LG", "엘지"), ("KB", "케이비"), ("JP", "제이피"),
    ("UBS", "유비에스"), ("KT", "케이티"), ("AI", "에이아이"), ("IT", "아이티"),
]

# TTS가 소리 내어 읽거나 오독하는 문자
TTS_RISK = [
    (r"\[\d{1,2}:\d{2}[^\]]*\]", "타임코드", "지우세요 — TTS가 '영영 콜론 영영'이라고 읽습니다"),
    (r"\*\*?", "마크다운 별표", "지우세요 — '별표'라고 읽거나 끊깁니다"),
    (r"[\[\]{}]", "대괄호·중괄호", "지우세요"),
    (r"[#>|]", "마크다운 기호", "지우세요"),
    (r"→|←|↑|↓", "화살표", "말로 풀어 쓰세요"),
    (r"[「」『』]", "낫표", "지우세요"),
    (r"·", "가운뎃점", "쉼표나 '와/과'로 바꾸세요"),
    (r"%", "퍼센트 기호", "'퍼센트'라고 글자로 쓰세요"),
    (r"~", "물결표", "'에서'로 풀어 쓰세요"),
    (r"[A-Za-z]", "영문 알파벳", "한글 발음으로 바꾸세요 (HBM→에이치비엠)"),
    (r"\d{1,3},\d{3}", "숫자 안 콤마", "콤마를 빼세요 — TTS가 쉼표로 끊어 읽습니다"),
    (r"[\U0001F300-\U0001FAFF☀-➿]", "이모지", "지우세요"),
]


def tts_sanitize(text):
    """TTS에 그대로 넣을 수 있게 정제. (정제본, 바꾼내역) 반환"""
    changes = []
    t = text

    def note(label, before, after):
        if before != after:
            changes.append(label)
        return after

    t = note("타임코드 제거", t, re.sub(r"\[\d{1,2}:\d{2}[^\]]*\]", "", t))
    t = note("마크다운 제거", t, re.sub(r"\*\*?|^#{1,6}\s*|^>\s*", "", t, flags=re.M))
    t = note("대괄호 제거", t, re.sub(r"[\[\]{}「」『』]", "", t))
    t = note("화살표 제거", t, re.sub(r"\s*[→←↑↓]\s*", " ", t))
    t = note("가운뎃점 정리", t, t.replace("·", ", "))
    t = note("퍼센트 기호", t, re.sub(r"\s*%", " 퍼센트", t))
    t = note("물결표", t, re.sub(r"(\d)\s*~\s*(\d)", r"\1에서 \2", t))
    for a, b in ENG_MAP:
        t = note(f"{a}→{b}", t, re.sub(a, b, t))
    t = note("숫자 콤마 제거", t, re.sub(r"(?<=\d),(?=\d{3})", "", t))
    t = note("이모지 제거", t, re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", t))
    t = note("공백 정리", t, re.sub(r"[ \t]{2,}", " ", t))
    # 문단은 유지, 3줄 이상 빈 줄만 정리
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    # 문장 끝 마침표 보강
    lines = []
    for ln in t.split("\n"):
        ls = ln.strip()
        if ls and ls[-1] not in ".?!":
            ls += "."
            if "마침표 보강" not in changes:
                changes.append("마침표 보강")
        lines.append(ls)
    return "\n".join(lines), changes


# ────────────────────── 코퍼스 대조 ──────────────────────
# 금지어 목록으로는 AI 문장을 다 못 잡는다.
# 그래서 원본 14편에 실제로 나오는 말투를 정답지로 삼고, 거기 없는 어미를 잡아낸다.

_CORPUS_CACHE = {}


# 구어 대본에 나오면 안 되는 문어체 종결 — 원본 14편에 단 한 번도 없다.
# 이건 확실한 신호라 '불합격'으로 잡는다.
LITERARY_ENDINGS = [
    (r"것이다\s*[.。]?$", "~라는 겁니다"),
    (r"(?<![가-힣])[가-힣]*한다\s*[.。]?$", "~합니다 / ~해요"),
    (r"(?<![가-힣])[가-힣]*된다\s*[.。]?$", "~됩니다 / ~돼요"),
    (r"[가-힣]*이다\s*[.。]?$", "~입니다 / ~예요"),
    (r"습니다만\s*[.。]?$", "~습니다. 근데"),
    (r"하겠다\s*[.。]?$", "~하겠습니다"),
    (r"라\s*하겠습니다\s*[.。]?$", "~입니다"),
    (r"할\s*수\s*있다\s*[.。]?$", "~할 수 있습니다"),
    (r"바입니다\s*[.。]?$", "~입니다"),
    (r"(?:에|와)\s*다름\s*아니", "그냥 ~입니다"),
    (r"라\s*볼\s*수\s*있겠습니다\s*[.。]?$", "~로 볼 수 있습니다"),
]


def sentence_ending(s):
    """문장 끝 2~5자를 뽑는다 (어미 비교용)"""
    s = s.strip().rstrip(".?!…\"'」』) ")
    m = re.search(r"([가-힣]{2,5})$", s)
    return m.group(1) if m else None


def ending_seen_in_corpus(s, corpus_endings):
    """문장의 끝 2~5자 중 하나라도 원본에 나오면 정상으로 본다"""
    s = s.strip().rstrip(".?!…\"'」』) ")
    for k in (5, 4, 3, 2):
        if len(s) >= k and s[-k:] in corpus_endings:
            return True
    return False


def load_corpus_profile():
    """원본 대본에서 '실제로 쓰이는 어미' 목록과 문장길이 편차 범위를 뽑는다."""
    if _CORPUS_CACHE:
        return _CORPUS_CACHE.get("endings"), _CORPUS_CACHE.get("stats")
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_raw")
    import glob as _g
    files = _g.glob(os.path.join(base, "*.plain.txt"))
    if not files:
        _CORPUS_CACHE["endings"], _CORPUS_CACHE["stats"] = None, None
        return None, None
    endings, sds = set(), []
    for f in files:
        try:
            t = re.sub(r"\s+", " ", open(f, encoding="utf-8").read())
        except Exception:
            continue
        ss = [x for x in re.split(r"(?<=[.?!])\s+", t) if len(x.strip()) > 4]
        if not ss:
            continue
        for x in ss:
            e = sentence_ending(x)
            if e:
                endings.add(e)
                # 어미의 뒷부분(2~4자)도 허용 목록에 넣어 표기 흔들림을 흡수
                for k in (2, 3, 4):
                    if len(e) > k:
                        endings.add(e[-k:])
        lens = [len(x) for x in ss]
        mean = sum(lens) / len(lens)
        sds.append((sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5)
    stats = {"sd_min": min(sds) * 0.75 if sds else 0, "sd_max": max(sds) if sds else 0}
    _CORPUS_CACHE["endings"], _CORPUS_CACHE["stats"] = endings, stats
    return endings, stats


# ────────────────────── 과거 대본과의 중복 검사 ──────────────────────
# 매번 단어만 갈아끼운 대본을 올리면 유튜브가 반복 콘텐츠로 본다.
# 원본 채널의 편간 중복률은 8어절 기준 평균 6.8%, 최대 14.7% 였다.
# 그 수준을 기준으로 삼는다.

# 채널 정체성이라 매편 반복해도 되는 문구 — 중복률 계산에서 제외한다
BRAND_PHRASES = [
    # 우리 채널 시그니처 (B안) — 원본 1개짜리 고정
    "제가 늘 강조드리는 게 수급이거든요",
    "누가 팔고 누가 받았는지부터 보셔야 됩니다",
    "이걸 어떻게 읽어야 되냐면요",
    "여러분 이거 한 번 생각해 보실까요",
    "이 구조가 뭡니까",
    "많이 빠졌다는 사실과 추세가 살아났다는 건 완전히 다른 얘기",
    "제가 늘 말씀드리는 게 이거예요",
    "댓글로",
]

# 10_고정문구_변형.md 의 변형들을 regex로 매칭해 중복률 계산에서 제외
BRAND_PATTERNS = [
    # 01 후크 전환
    r"근데.{2,40}(?:따로 있|핵심은 이게|숨어 있는|끝이 아니|보여드리고 싶은|넘어가면 안|확인해야 되는 건|모르고 있는|더 중요합니다)",
    # 03 긴급 선언
    r"(?:그래서 제가|그래서 오늘|이 흐름을|이런 날이니까|이 구조를 보고|이게 제가|이런 장에서는|이 상황을 보고).{5,60}(?:촬영했|만들었|만든 겁|찍었|정리했|올리는|준비했|들어갔|만들었습니다)",
    # 04 CTA① 구독
    r"(?:들어가기|시작하기|시작|본론|본격|그전에|구독\s*아직\s*안|부탁\s*하나만|구독하고\s*좋아요\s*하나만\s*먼저).{0,50}(?:구독|부탁).{0,80}댓글",
    # 05 차트 진입
    r"자,?\s*(?:그럼\s*)?(?:일봉|차트|바로\s*(?:차트|일봉)).{0,30}",
    # 06 접근성 도입
    r"(?:매번|항상|모두|일하시면서|장 시작하면).{0,40}(?:실시간|챙겨|찾아서|챙기기|확인하시|보시긴|볼\s*수|볼\s*여유).{0,20}(?:어렵|쉽지 않|않잖|없잖|없으시|않은 거)",
    # 07 번호 CTA
    r"\d{10,11}로\s*.{2,10}(?:이?라고\s*)?문자\s*(?:한\s*통|하나|보내|남겨).{0,120}무료",
    # 08 반론 차단+대가 전환
    r"(?:오해|걱정|부담).{0,40}(?:돈\s*(?:받지|안\s*받|한\s*푼|1원)|무료입니다).{0,120}(?:가입비|상담비)",
    # 09 요약 진입
    r"(?:자,?\s*)?(?:오늘\s*(?:내용|핵심)\s*)?(?:핵심만\s*)?(?:마무리\s*)?정리(?:하겠|해\s*드리|하면)",
    # 10 약속 한정
    r"(?:무조건|미래를\s*장담).{0,25}(?:약속|말씀|말\s*못|드릴 수 없|못 드|못 합)",
    # 11 마무리
    r"(?:혼자\s*하면서|혼자서\s*계속|혼자\s*판단).{0,60}(?:손실|잃기|깎이|깎여).{0,200}타점.{0,30}(?:베껴|복사|가져다|퍼지|돌아다니)",
]

# 원본 22편 실측 — 시청자가 둘 다 보는 '같은 종목'일수록 훨씬 다르게 쓴다.
# 원본 53편 실측 (삼성전자 20편 / SK하이닉스 16편 포함)
#   같은 종목 다른 날 : 8어절 평균 1.3% / 최대 16.5%
#   다른 종목끼리     : 8어절 평균 1.5% / 최대 33.4%
# 평균은 거의 같다. 원본은 같은 종목이든 아니든 매번 새로 쓴다.
# 다만 같은 종목은 구독자가 둘 다 보므로 기준을 더 조인다.
DUP_FAIL_SAME = 20.0
DUP_WARN_SAME = 12.0
DUP_FAIL_DIFF = 38.0
DUP_WARN_DIFF = 25.0


def script_stock(text):
    """대본에서 종목명을 뽑는다. 'OOO 주주분들' 패턴 사용."""
    m = re.search(r"([가-힣A-Za-z0-9]{2,12})\s*주주(?:분들|님들)", text)
    return m.group(1) if m else None


def _strip_brand(t):
    for p in BRAND_PHRASES:
        t = t.replace(p, " ")
    for pat in BRAND_PATTERNS:
        t = re.sub(pat, " ", t)
    return re.sub(r"\s+", " ", t)


def _grams(t, n=8):
    w = _strip_brand(t).split()
    return set(" ".join(w[i:i + n]) for i in range(len(w) - n + 1))


def check_duplication(script_path, script_text):
    """이전에 합격한 대본들과 얼마나 겹치는지 (브랜드 문구 제외)"""
    import glob as _g
    store = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_scripts")
    if not os.path.isdir(store):
        return []
    base = os.path.splitext(os.path.basename(script_path))[0]
    ga = _grams(script_text)
    if not ga:
        return []
    out = []
    for f in _g.glob(os.path.join(store, "*.txt")):
        # 같은 대본의 이전 보관본은 비교 대상이 아니다 (재검증 시 자기 자신과 비교됨).
        # 보관본 이름은 "종목명__원본파일명" 이므로 접두사를 떼고 비교한다.
        other_base = os.path.splitext(os.path.basename(f))[0]
        if "__" in other_base:
            other_base = other_base.split("__", 1)[1]
        if other_base == base:
            continue
        try:
            other = re.sub(r"\s+", " ", open(f, encoding="utf-8").read())
        except Exception:
            continue
        gb = _grams(other)
        if not gb:
            continue
        jac = len(ga & gb) / len(ga | gb) * 100
        # 98% 이상이면 같은 대본을 이름만 바꿔 다시 검증한 것 — 비교 대상이 아니다
        if jac >= 98:
            continue
        out.append((os.path.basename(f), jac, script_stock(other)))
    out.sort(key=lambda x: -x[1])
    return out


# ── 어휘 이탈 검사 ──
# 중복을 피하려고 문장을 새로 지어내면 원본에 없는 낯선 말투가 나온다.
# 원본 53편은 서로에 대해 평균 10.1%, 최대 25.6%의 새 어절을 쓴다. 원본을 오탐하지 않는 선으로 잡는다.
NOVEL_WARN = 28.0
NOVEL_FAIL = 35.0

_CORPUS_WORDS = {}
_CORPUS_FLAT = {}


def corpus_flat():
    """원본 전문을 공백 없이 이어붙인 것 — 문장 통째 복제 검사용"""
    if _CORPUS_FLAT:
        return _CORPUS_FLAT.get("t")
    import glob as _g
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_raw")
    parts = []
    for f in _g.glob(os.path.join(base, "*.plain.txt")):
        try:
            parts.append(re.sub(r"[^가-힣0-9]", "", open(f, encoding="utf-8").read()))
        except Exception:
            pass
    _CORPUS_FLAT["t"] = " ".join(parts) if parts else None
    return _CORPUS_FLAT["t"]


def corpus_words():
    if _CORPUS_WORDS:
        return _CORPUS_WORDS.get("w")
    import glob as _g
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_raw")
    w = set()
    for f in _g.glob(os.path.join(base, "*.plain.txt")):
        try:
            w |= set(re.findall(r"[가-힣]{2,}", open(f, encoding="utf-8").read()))
        except Exception:
            pass
    _CORPUS_WORDS["w"] = w or None
    return _CORPUS_WORDS["w"]


def check_novelty(text):
    """원본에 없는 어절 비율. 높으면 AI가 말투를 지어낸 것."""
    cw = corpus_words()
    if not cw:
        return None, []
    mine = set(re.findall(r"[가-힣]{2,}", text))
    if not mine:
        return None, []
    novel = sorted(mine - cw)
    return len(novel) / len(mine) * 100, novel


def archive_script(script_path, script_text):
    """합격한 대본을 보관해서 다음 편의 중복 검사 기준으로 쓴다"""
    store = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_scripts")
    os.makedirs(store, exist_ok=True)
    # 같은 대본을 다시 검증하면 덮어쓴다 (타임스탬프를 붙이면 자기 자신과 100% 중복으로 잡힘)
    st = script_stock(script_text) or "미상"
    dst = os.path.join(store, f"{st}__{os.path.basename(script_path)}")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(script_text)


# ────────────────────── 검사 항목 ──────────────────────

# ★ 우리 채널 시그니처 (B안 — 원본과 다른 우리 문구)
# 원본도 이 자리들을 매편 쓰지 않는다(32~68%). 필수/선택을 나눈다.
# 10_고정문구_변형.md 에 카테고리별 10~15개 변형이 있다. regex로 어느 변형이든 수용한다.
FIXED_PHRASES = [
    ("후크", r"근데.{0,35}(?:따로 있|핵심은 이게|놓칩니다|숨어 있는|끝이 아니거든|보여드리고 싶은|눈에 띈 게|넘어가면 안|분위기가.{0,5}다릅|얘기가 달라|확인해야 되는 건|흐름이 다릅|모르고 있는 게|더 중요합니다)"),
    ("차트 진입", r"자,?\s*(?:그럼\s*)?(?:일봉|차트|바로\s*(?:차트|일봉))"),
    ("CTA① 구독", r"(?:들어가기|시작하기|시작|본론|본격|자,?\s*그전에|구독\s*아직\s*안).{0,20}(?:구독|부탁)"),
    ("접근성 CTA②", r"(?:매번|항상|모두|일하시면서|장 시작하면)\s*.{0,30}(?:실시간|챙겨|찾아서|챙기기|확인하시|보시긴|볼\s*수|볼\s*여유).{0,20}(?:어렵|쉽지 않|않잖|없잖|없으시|않은 거)"),
    ("요약", r"(?:자,?\s*)?(?:오늘\s*(?:내용|핵심)\s*)?(?:핵심만\s*)?(?:마무리\s*)?정리(?:하겠|해\s*드리|하면)"),
    ("마무리", r"타점.{0,30}(?:베껴|복사|가져다\s*쓰|퍼지)"),
]

# 있으면 좋지만 매편 넣을 필요는 없다 (원본 등장률 26~49%)
OPTIONAL_PHRASES = [
    ("수급 시그니처", "늘 강조드리는 게 수급"),
    ("해석 진입", "어떻게 읽어야 되냐면요"),
    ("관점 전환", "여러분 이거 한 번 생각해"),
    ("반론 차단", "오해하시는 분들 계신데요"),
]

# ── 원본 53편에 0회인 '글쓰기 투' ──
# 말이 안 되는 건 아니지만 이 채널 사람은 절대 안 쓰는 표현.
# 어절 이탈률은 조사·활용에 희석돼서 이런 한 문장을 못 잡는다. 그래서 따로 막는다.
# 값을 추가할 때는 반드시 코퍼스 등장 0회를 먼저 확인하고 selftest를 돌릴 것.
NOT_IN_CORPUS = [
    (r"무서운",              "'중요한 건'으로 (원본 53편 0회 / '중요한 건'은 53회)"),
    (r"원\s*어치",           "'억 원을 순매도했고' 형태로 (원본 0회)"),
    (r"짚어\s*드리|짚어\s*드릴", "'정리해 드리겠습니다'로 (원본 0회)"),
    (r"얘기예요",            "'얘기입니다'로 (원본 0회)"),
    (r"키\s*포인트|관건|주목할", "'중요한 건'으로 (원본 0회)"),
    (r"의미합니다|시사합니다|드러납니다", "'~라는 겁니다'로 (원본 0회)"),
    (r"기대하십니다",         "'기대합니다'로 (원본 0회)"),
    (r"하나도\s*안\s*남",      "'모두 이탈했습니다'로 (원본 0회)"),
    (r"자주\s*나오는\s*게\s*아니", "예고 빼고 수급 결론에서 바로 이어가세요 (원본 0회)"),
    (r"내줬",                "'이탈했습니다'로 (원본 0회 / '이탈했습니다'는 7회)"),
    # 이동 평균선은 스스로 무너지지 않는다. 주어는 언제나 '주가'다 (무생물 주어 금지)
    (r"이동\s*평균선(?:이|을)\s*(?:전부\s*|모두\s*)?(?:무너|붕괴)",
     "선이 아니라 주가가 주어입니다 → '주가가 이동 평균선을 모두 이탈했습니다'"),
    (r"이동평균선",           "'이동 평균선'으로 띄어 쓰세요 (원본 40회 전부 띄어쓰기)"),
    # 이동 평균선 가격을 하나씩 나열하지 마라 (원본 53편 0회)
    (r"\d+일선이?\s*\d+만\s*\d*(?:천|백)?\s*원",
     "이동 평균선 값을 하나씩 읊지 마세요 (원본 53편 0회). 단기/중기/장기로 묶어 방향·위치만"),
]

# ── 우리 채널이 다루지 않는 주제 ──
# 주식 채널이다. 코인·가상자산 얘기는 어떤 맥락이든 하지 않는다.
BANNED_TOPICS = [
    (r"비트코인|이더리움|리플|도지코인",
     "주식 채널입니다. 코인 얘기는 하지 마세요"),
    (r"코인(?:까지|이|을|은|도|에|의|시장)",
     "주식 채널입니다. 코인 얘기는 하지 마세요"),
    (r"가상\s*(?:화폐|자산)|암호\s*화폐",
     "주식 채널입니다. 코인 얘기는 하지 마세요"),
]

# ── 페르소나의 개인 사정을 지어내지 말 것 ──
# 원본 채널은 화자가 실제로 겪은 일이라 말할 수 있다. 우리는 그 사실을 모른다.
# 실존 인물 입에 없는 보유 자산·손실·사생활을 넣으면 방송에서 거짓말이 된다.
# ★ 이 목록은 '코퍼스에 있느냐'와 무관하다. 원본에 있어도 우리는 쓰면 안 된다.
FABRICATED_PERSONAL = [
    (r"저도\s*지금\s*[^.?!]{0,20}(가지고|들고|보유)",
     "보유 자산을 지어내지 마세요"),
    (r"제\s*계좌(도|가|는)|저도\s*물렸|제\s*자산이",
     "화자의 손익을 지어내지 마세요"),
    (r"화가\s*(많이\s*)?나|정신이\s*없는\s*게\s*사실",
     "화자의 감정을 지어내지 말고 '감정적으로 대응하면 판단이 더 흔들릴 수 있습니다'로"),
]

# 원본 12편에 단 한 번도 안 나오는 것만 '금지'로 둔다
FILLER = [
    (r"짚고\s*(?:가|갈|넘어)", "예고 빼고 바로 내용"),
    (r"얘기가\s*나왔으니", "삭제, 바로 내용"),
    (r"먼저\s*(?:보겠|살펴|확인해\s*보겠)", "'먼저' 빼고 바로 내용"),
    (r"(?<!다시 )(?<!한 번 더 )말씀드릴게요\s*\.", "삭제, 바로 본론"),
    (r"살펴보겠습니다", "'~을 보면'으로"),
    (r"차례로\s*(?:보|짚|확인)", "삭제, 바로 내용"),
    (r"다음으로\s*(?:넘어|보겠|살펴)", "삭제, 바로 내용"),
    (r"이제부터\s*(?:보겠|살펴|확인해\s*보)", "삭제, 바로 내용"),
]

# 원본이 3/12편 정도로 쓰는 것 — 막지 않고 더 나은 형태만 알려준다
SOFT_FILLER = [
    (r"(?:도|를|을)?\s*같이\s*보겠습니다", "원본은 '~를 보면 [내용]'을 2배 더 많이 씁니다(6회 vs 3회)"),
]

# ★ 원본 12편에 대해 회귀 테스트를 통과한 목록만 남긴다.
#   원본이 쓰는 표현을 금지하면 검증기가 틀린 것이다. (selftest.py로 검증)
#   '하지만' 은 원본 12/12편이 쓰므로 금지에서 제외했다.
BANNED_WORDS = [
    (r"동반\s*(?:하락|상승)", "~하면서 같이 밀렸다/올랐다"),
    (r"변곡", "방향이 바뀌는"),
    (r"괴리", "차이"),
    (r"수렴(?:하|해|한)", "따라 내려가는"), (r"촉발", "시작하게 한"),
    (r"종합하면", "정리하면요"),
    (r"이를\s*통해", "그래서"),
    (r"이러한\s*점에서", "그래서"), (r"뚜렷(?:한|하게)", "확실한"),
    (r"뒷받침(?:하|합|해|된)", "맞아떨어지다"),
    (r"선명해(?:져|지|집니다)", "확실해요"),
    (r"오독(?:이|을|하)", "잘못 읽는 거예요"),
    (r"(?:는|은)\s*사실이다", "한국어 자연어로"),
    (r"에\s*의해\s*(?:되|된|됐)", "능동태로"),
    (r"인정하고\s*들어가", "삭제"),
    (r"숨기지\s*않고", "삭제"), (r"겸허하게", "삭제"),
    (r"처음부터\s*차근차근", "삭제, 바로 시작"),
    (r"하나도\s*빼지\s*않고", "삭제"),
]

# 원본이 드물게(1~2편) 쓰는 것 — 막지 않고 알려만 준다
SOFT_WORDS = [
    (r"분기점", "'갈리는 자리'가 더 쉽게 들립니다"),
    (r"결론적으로", "'그래서 제 결론은요'가 더 자연스럽습니다"),
    (r"(?:위에|위로)\s*안착", "'자리를 잡다'가 더 쉽게 들립니다"),
    (r"따라서\s", "'그래서'가 더 자연스럽습니다"),
    (r"그러나\s", "'근데'가 더 자연스럽습니다"),
    (r"위험\s*회피", "'공포 매도'가 더 쉽게 들립니다"),
    (r"(?<![가-힣])봉(?:을|이|은|의|에서)", "'캔들'이 더 명확합니다"),
    (r"소진", "'다 나왔다'가 더 쉽게 들립니다"),
]

FORBIDDEN = [
    (r"목표\s*주가", "목표가 제시 금지"),
    (r"까지\s*(?:갑니다|간다고|오릅니다|상승합니다)", "목표가 제시 금지"),
    (r"(?:지금|여기서)\s*(?:사|매수)(?:세요|십시오|시면)", "매수 권유 금지"),
    (r"(?:지금|여기서)\s*(?:파|매도)(?:세요|십시오|시면)", "매도 권유 금지"),
    (r"반드시\s*(?:오릅|상승)", "단정 금지"),
    (r"확실히\s*(?:오릅|상승|반등)", "단정 금지"),
]


def run(script_path, brief_path):
    script = open(script_path, encoding="utf-8").read()
    flat = re.sub(r"\s+", " ", script).strip()
    sents = [s for s in re.split(r"(?<=[.?!])\s+", flat) if s.strip()]
    brief = open(brief_path, encoding="utf-8").read() if brief_path and os.path.exists(brief_path) else ""

    fails, warns = [], []

    def fail(name, detail, how):
        fails.append((name, detail, how))

    def warn(name, detail, how):
        warns.append((name, detail, how))

    # ── 1. 숫자 대조 ── (가장 중요)
    if brief:
        # 브리프 숫자 + 사람이 흔히 쓰는 반올림/절삭 표기까지 허용값으로
        allowed_set = set()
        for _, v, _ in extract_numbers(brief):
            if not v:
                continue
            allowed_set.update({v, float(round(v)), float(int(v)), round(v, 1)})
            for d in (10, 100, 1000, 10**4, 10**5, 10**6, 10**7, 10**8, 10**9, 10**10, 10**11):
                if v >= d:
                    allowed_set.add(round(v / d) * d)
                    allowed_set.add(int(v / d) * d)
        allowed_set.discard(0)

        def matches(v):
            for a in allowed_set:
                # 100 미만(퍼센트·지표)은 오차를 거의 안 준다 — 날짜와 뒤섞이는 걸 막기 위해
                tol = abs(a) * 0.01 if abs(a) >= 100 else 0.05
                if abs(v - a) <= tol:
                    return True
            return False

        bad = []
        for s, v, ctx in extract_numbers(script):
            if any(re.search(w, ctx) for w in WHITELIST_CTX):
                continue
            if v in SMALL_OK:
                continue
            if re.search(r"\d\s*(?:월|일|년|시|분)", ctx):   # 날짜·시각은 검사 제외
                continue
            if not matches(v):
                bad.append((s, ctx.strip()))
        if bad:
            for s, ctx in bad[:8]:
                fail("브리프에 없는 숫자", f"「{s}」  …{ctx}…",
                     "brief.md에 없는 숫자입니다. AI가 지어냈을 수 있으니 삭제하거나 브리프 값으로 고치세요")
    else:
        warn("숫자 대조", "brief.md 없이 실행됨", "brief.md를 같이 넘기면 지어낸 숫자를 잡을 수 있습니다")

    # ── 2. 분량 ──
    n = len(flat)
    sec = n / RATE
    if not (3400 <= n <= 4300):
        fail("분량", f"{n:,}자 ({int(sec)//60}분 {int(sec)%60}초)",
             "3,400~4,300자로 맞추세요")

    # ── 3. 후크 / 인사 위치 ──
    hook_pat = r"근데.{0,35}(?:따로 있|핵심은 이게|숨어 있는 게|끝이 아니거든|보여드리고 싶은|넘어가면 안|확인해야 되는 건|모르고 있는 게|더 중요합니다)"
    m = re.search(hook_pat, flat)
    if not m:
        fail("후크 없음", "10_고정문구_변형.md 01번 카테고리 문구가 없습니다", "0:08 부근에 넣으세요")
    elif m.start() / RATE > 20:
        fail("후크 위치", f"{m.start()/RATE:.0f}초", "15초 안에 나와야 합니다. 앞의 시세 설명을 줄이세요")

    m = re.search(r"(?:주주\s*여러분들|주주분들|주주님들)[,·\s]*(?:반갑습니다[.。]?\s*)?" + re.escape(PERSONA) + r"입니다", flat)
    if not m:
        fail("인사", f"'{PERSONA}' 자기소개가 없습니다",
             f"'OOO 주주분들, {PERSONA}입니다' 형태로 25~35초 지점에 넣으세요")
    else:
        t = m.start() / RATE
        if t < 20:
            fail("인사 위치", f"{t:.0f}초", "인사가 너무 빠릅니다. 25~35초로 옮기세요 (첫 30초는 후킹)")
        elif t > 45:
            fail("인사 위치", f"{t:.0f}초", "인사가 너무 늦습니다. 25~35초로 옮기세요")

    # ── 4. 고정 문구 (regex 매칭 — 10_고정문구_변형.md 어느 변형이든 수용) ──
    missing = [name for name, pat in FIXED_PHRASES if not re.search(pat, flat)]
    if missing:
        fail("우리 시그니처 누락", ", ".join(missing), "AGENTS.md 3번의 문장을 토씨 그대로 넣으세요")
    opt = [name for name, p in OPTIONAL_PHRASES if p in flat]
    if len(opt) < 2:
        warn("선택 문구 부족", f"{len(opt)}개 사용", "AGENTS.md 3-2번에서 2개 이상 골라 쓰면 자연스럽습니다")

    # ── 4-1. 개인 번호 — 틀리면 영상 전체가 무의미해진다 ──
    digits = re.findall(r"\d{9,13}", flat.replace(" ", ""))
    if not digits:
        fail("개인 번호 없음", f"번호 {PHONE} 가 대본에 없습니다",
             f"CTA② 자리에 '{PHONE}로 {{종목}}이라고 문자 한 통 남겨 주세요' 형태로 넣으세요")
    else:
        wrong = sorted({d for d in digits if d != PHONE})
        if wrong:
            fail("개인 번호 틀림", "「" + "」「".join(wrong) + "」",
                 f"정확히 {PHONE} 이어야 합니다. 한 자리만 틀려도 문자가 안 옵니다")
        if flat.count(PHONE) < 1:
            fail("개인 번호 없음", "정상 번호가 한 번도 안 나옵니다", f"{PHONE} 를 넣으세요")

    # 원본 시그니처를 그대로 쓰면 안 된다 (B안 — 우리 문구로 교체했음)
    ORIG_SIG = [
        ("후크", "뭐를 놓치고 있는지 아세요"),
        ("수급", "제가 항상 말씀드리죠"),
        ("수급", "외국인들의 움직임을 봐야 한다고요"),
        ("해석", "이게 뭐냐면요"),
        ("차트", "일봉 차트를 먼저 보시게 되면요"),
        ("관점", "여러분들 생각해 보세요"),
        ("CTA①", "본격적으로 시청 전에"),
        ("CTA②", "제 방송을 모두 실시간으로"),
        ("요약", "다시 돌아와서 우리"),
    ]
    for name, p in ORIG_SIG:
        if p in flat:
            fail("원본 시그니처 사용", f"[{name}] 「{p}」",
                 "그 채널의 문구입니다. AGENTS.md 3번의 우리 문구로 바꾸세요")
            break

    # ── 5. 상승/하락 종목 수 ──
    if not re.search(r"(?:상승|오른).{0,12}종목.{0,20}\d|하락.{0,12}종목.{0,20}\d|\d+개(?:뿐|인데)", flat):
        fail("상승/하락 종목 수", "언급 없음", "이 채널의 시그니처입니다. 반드시 넣으세요")

    # ── 6. 수급 3주체 ──
    for who in ("외국인", "개인", "기관"):
        if who not in flat:
            fail("수급 누락", f"'{who}' 언급 없음", "외국인·개인·기관 세 주체를 모두 말해야 합니다")

    # ── 7. CTA 배치 ──
    cta = []
    for pat in (r"(?:들어가기|시작하기|시작|본론|본격|그전에|구독\s*아직\s*안|구독하고\s*좋아요\s*하나만\s*먼저).{0,20}(?:구독|부탁)", r"(?:매번|항상|모두|일하시면서|장 시작하면)\s*.{0,30}(?:실시간|챙겨|찾아서|챙기기|확인하시|보시긴|볼\s*수|볼\s*여유)", r"타점.{0,30}(?:베껴|복사|가져다\s*쓰|퍼지)"):
        mm = re.search(pat, flat)
        cta.append(mm.start() / n * 100 if mm else None)
    if cta[0] is None:
        fail("CTA① 없음", "구독·좋아요·댓글 요청", "본론 들어가기 직전(약 26% 지점)에 넣으세요")
    elif not (15 <= cta[0] <= 40):
        warn("CTA① 위치", f"{cta[0]:.0f}% 지점", "26% 부근이 좋습니다")
    if cta[2] is None:
        fail("마무리 CTA 없음", "마무리 2차 CTA", "맨 끝에 넣으세요")

    # ── 8. 댓글 키워드 ──
    if not re.search(r"댓글로\s*[「\"']?\s*[가-힣\s]{1,6}[」\"']?\s*(?:이?라고|라는)", flat):
        fail("댓글 키워드", "지정 안 됨", "'댓글로 힘이라고 한 마디씩 남겨 주세요' 형태로 넣으세요")

    # ── 9. 단정 차단 문장 ──
    # 원본 53편 실측: 평균 3.6회 ± 1.4. 너무 적어도, 너무 많아도 원본과 달라진다.
    hedge = len(re.findall(r"단정하(?:면|기)|아닙니다|아니거든요|볼 수(?:도)? 없|보기 어렵", flat))
    if hedge < 2:
        fail("단정 차단 부족", f"{hedge}회 (원본 평균 3.6회)",
             "'~라고 단정하면 안 됩니다' 계열을 2~5회 넣으세요")
    elif hedge > 7:
        warn("단정 차단 과다", f"{hedge}회 (원본 평균 3.6회, 최대 6회)",
             "너무 자주 빠져나가면 확신이 없어 보입니다. 2~5회로 줄이세요")

    # ── 10. 금지 표현 ──
    for pat, how in FORBIDDEN:
        for mm in re.finditer(pat, flat):
            ctx = flat[max(0, mm.start()-25):mm.end()+15]
            if "약속은 드릴 수 없" in ctx or "이런 약속" in ctx:
                continue                      # 면책 문장은 통과
            fail("금지 표현", f"…{ctx}…", how)
            break

    # ── 11. 예고 필러 ──
    for pat, how in FILLER:
        mm = re.search(pat, flat)
        if mm:
            fail("예고 필러", f"…{flat[max(0,mm.start()-20):mm.end()+15]}…", how)
    for pat, how in NOT_IN_CORPUS:
        mm = re.search(pat, flat)
        if mm:
            fail("원본에 없는 표현", f"「{mm.group()}」  …{flat[max(0,mm.start()-22):mm.end()+18]}…", how)
    for pat, how in BANNED_TOPICS:
        mm = re.search(pat, flat)
        if mm:
            fail("금지 주제", f"「{mm.group()}」  …{flat[max(0,mm.start()-25):mm.end()+25]}…", how)
    for pat, how in FABRICATED_PERSONAL:
        mm = re.search(pat, flat)
        if mm:
            fail("지어낸 개인 사정", f"「{mm.group()}」  …{flat[max(0,mm.start()-25):mm.end()+25]}…", how)
    for pat, how in SOFT_FILLER:
        mm = re.search(pat, flat)
        if mm:
            warn("전환 표현", f"…{flat[max(0,mm.start()-18):mm.end()+12]}…", how)

    # ── 12. 금지 단어 ──
    for pat, alt in BANNED_WORDS:
        mm = re.search(pat, flat)
        if mm:
            fail("금지 단어", f"…{flat[max(0,mm.start()-15):mm.end()+15]}…", f"'{alt}'로 바꾸세요")
    for pat, how in SOFT_WORDS:
        mm = re.search(pat, flat)
        if mm:
            warn("표현 제안", f"…{flat[max(0,mm.start()-15):mm.end()+12]}…", how)

    # ── 12-b. 문어체 종결 ── (원본에 0회. 확실한 신호라 불합격)
    for x in sents:
        for pat, alt in LITERARY_ENDINGS:
            if re.search(pat, x.strip()):
                fail("문어체 종결", f"…{x.strip()[-44:]}…", f"'{alt}' 형태로 바꾸세요. 말이 아니라 글이 됩니다")
                break
        else:
            continue
        break

    # ── 12-c. 코퍼스 대조 ── (휴리스틱이라 경고만. 막지는 않는다)
    corpus_endings, corpus_stats = load_corpus_profile()
    if corpus_endings:
        odd = {}
        for x in sents:
            if len(x) < 12:
                continue
            if not ending_seen_in_corpus(x, corpus_endings):
                e = sentence_ending(x)
                if e:
                    odd.setdefault(e, x)
        if odd:
            sample = list(odd.items())[:3]
            warn("원본에 없는 말투",
                 " / ".join(f"「{e}」" for e, _ in sample) + (f" 외 {len(odd)-3}개" if len(odd) > 3 else ""),
                 "원본 14편에 없는 종결입니다. 어색하면 바꾸세요 (막지는 않습니다)")
        # 문장 길이가 지나치게 균일하면 AI가 쓴 티가 난다
        lens = [len(x) for x in sents]
        if len(lens) > 20 and corpus_stats["sd_min"]:
            mean = sum(lens) / len(lens)
            sd = (sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5
            if sd < corpus_stats["sd_min"]:
                warn("문장 리듬", f"길이 편차 {sd:.1f} (원본 {corpus_stats['sd_min']:.0f} 이상)",
                     "문장 길이가 너무 고릅니다. 짧은 문장과 긴 문장을 섞으세요")

    # ── 13. 어미 ──
    streak = 1
    for i in range(1, len(sents)):
        a = "습니다" if sents[i-1].rstrip(".?!").endswith("습니다") else ("요" if sents[i-1].rstrip(".?!").endswith("요") else None)
        b = "습니다" if sents[i].rstrip(".?!").endswith("습니다") else ("요" if sents[i].rstrip(".?!").endswith("요") else None)
        streak = streak + 1 if (a and a == b) else 1
        if streak >= 4:
            fail("어미 4연속", f"'{b}' 4문장 연속 — …{sents[i][:30]}…", "중간을 다른 어미로 바꾸세요")
            break
    avg = sum(len(s) for s in sents) / max(len(sents), 1)
    if avg > 50:
        warn("문장 길이", f"평균 {avg:.1f}자", "45자 이하로 쪼개세요")

    # ── 13-b. 과거 대본과의 중복 ── (유튜브 반복 콘텐츠 방지)
    me_stock = script_stock(flat)
    for name, jac, other_stock in check_duplication(script_path, flat):
        is_same = bool(me_stock and other_stock and me_stock == other_stock)
        f_lim, w_lim = (DUP_FAIL_SAME, DUP_WARN_SAME) if is_same else (DUP_FAIL_DIFF, DUP_WARN_DIFF)
        if jac >= f_lim:
            if is_same:
                fail("같은 종목 이전 회차와 너무 비슷함", f"{jac:.0f}% 중복 — {name}",
                     "같은 종목은 구독자가 반드시 둘 다 봅니다. 원본은 같은 종목끼리 평균 1.7%예요. "
                     "09_변형뱅크.md에서 지난 회차와 다른 번호를 고르고, 이번 편의 축도 바꾸세요")
            else:
                fail("다른 대본과 너무 비슷함", f"{jac:.0f}% 중복 — {name}",
                     "단어만 바꾼 대본입니다. 원본은 편간 평균 1.5%예요. 09_변형뱅크.md에서 다른 문장을 고르세요")
            break
        if jac >= w_lim:
            warn("이전 대본과 유사", f"{jac:.0f}% 중복 — {name}" + (" (같은 종목)" if is_same else ""),
                 "표현을 조금 더 바꾸면 좋습니다")
            break

    # ── 13-a2. 구어 비율 ── (기준대본 66%. 뱅크 문장을 그대로 쓰면 격식체로 쏠린다)
    hae = len(re.findall(r"(거든요|어요|에요|예요|거죠|잖아요|고요|게요)", flat))
    gyeok = len(re.findall(r"(습니다|겁니다|입니다)", flat))
    if hae + gyeok >= 30:
        col = hae / (hae + gyeok) * 100
        if col < 40:
            fail("구어 비율 부족", f"{col:.0f}% (기준대본 66%, 목표 55~75%)",
                 "'~습니다'가 너무 많습니다. 일부를 '~거든요/~어요/~라는 거예요'로 바꾸세요. "
                 "변형뱅크 문장은 자막 원문이라 격식체가 많으니 어미만 구어로 고치세요")
        elif col > 82:
            warn("구어 비율 과다", f"{col:.0f}% (목표 55~75%)",
                 "'~습니다'를 몇 개 섞으면 무게가 잡힙니다")

    # ── 13-b2. 원본 문장 복제율 ── (B안: 뱅크를 쓰되 통째로 베끼진 말 것)
    _cw = corpus_flat()
    if _cw:
        _s = [x.strip() for x in sents if len(x.strip()) > 10]
        def _n(x): return re.sub(r"[^가-힣0-9]", "", x)
        _ex = [x for x in _s if len(_n(x)) >= 10 and _n(x) in _cw]
        if _s:
            _rate = len(_ex) / len(_s) * 100
            if _rate >= 30:
                fail("원본 문장 복제 과다", f"{_rate:.0f}% ({len(_ex)}/{len(_s)}문장)",
                     "뱅크 문장을 그대로 너무 많이 썼습니다. 목표는 20% 이하예요. "
                     "어미를 구어체로 바꾸고 어순·표현을 조금씩 손보세요")
            elif _rate >= 20:
                warn("원본 문장 복제", f"{_rate:.0f}% ({len(_ex)}/{len(_s)}문장)",
                     "20% 이하가 목표입니다. 몇 문장만 더 손보면 좋습니다")

    # ── 13-c. 어휘 이탈 ── (지어낸 말투 방지)
    rate, novel = check_novelty(flat)
    if rate is not None:
        if rate >= NOVEL_FAIL:
            fail("원본에 없는 말투가 너무 많음", f"{rate:.0f}% (원본 53편 평균 10%, 최대 26%)",
                 f"문장을 새로 지어냈습니다. 09_변형뱅크.md에서 원본 문장을 골라 쓰세요. "
                 f"예: {', '.join(novel[:8])}")
        elif rate >= NOVEL_WARN:
            warn("원본에 없는 말투", f"{rate:.0f}% (원본 평균 17%)",
                 f"09_변형뱅크.md의 문장으로 바꾸면 자연스러워집니다. 예: {', '.join(novel[:6])}")

    # ── 14. 반문형 최소 7개 (CLAUDE.md §5) ──
    _Q_PATS = [
        r"이해되시죠", r"감\s*오시죠", r"느낌\s*오시죠",
        r"여기까지\s*따라오고\s*계시죠", r"이게\s*뭘\s*뜻하겠어요",
        r"왜\s*그럴까요", r"그럼\s*어떻게\s*되겠어요", r"이거\s*우연일까요",
        r"좀\s*무섭죠", r"이상하지\s*않아요", r"말이\s*되나요\s*이게",
        r"많이\s*어려우신가요", r"뭔가\s*이상하다\s*느끼셨죠",
        r"여러분이라면\s*어떻게\s*하시겠어요", r"눈치채셨어요",
        r"어떠세요", r"여러분도\s*같은\s*생각이시죠",
        r"혹시\s*이\s*숫자\s*보고\s*안심하신\s*분\s*계세요",
    ]
    _q_used = {}
    for i, qp in enumerate(_Q_PATS):
        cnt = len(re.findall(qp, flat))
        if cnt:
            _q_used[i] = cnt
    if len(_q_used) < 7:
        fail("반문형 부족", f"{len(_q_used)}종류 (최소 7종류 필수)",
             "CLAUDE.md §5 반문형 리스트(18개)에서 7개 이상 골라 넣으세요")
    for qi, qc in _q_used.items():
        if qc >= 2:
            sample = re.search(_Q_PATS[qi], flat).group()
            fail("반문형 중복", f"'{sample}' {qc}회 사용",
                 "같은 반문형은 대본 한 편에서 1회만 쓸 수 있습니다")
            break

    # ── 14-b. "자, 이게" 필수 (후크 양자택일 질문) ──
    if not re.search(r"자,?\s*이게", flat):
        fail("'자, 이게' 누락", "양자택일 질문 앞에 '자, 이게'가 없습니다",
             "후크의 A/B 질문 앞에 '자, 이게'를 반드시 붙이세요")

    # ── 14-c. CTA 구조 완결성 ──
    if "무료" not in flat:
        fail("무료 명시 누락", "'무료' 단어가 대본에 없습니다",
             "번호 CTA에서 '무료로 보내 드리겠습니다' 형태로 반드시 넣으세요")
    if not re.search(r"가입비|상담비", flat):
        fail("반론 차단 누락", "'가입비/상담비' 구체 부정이 없습니다",
             "'가입비나 상담비를 요구하는 것도 아닙니다' 형태로 넣으세요")
    if not re.search(r"(?:유튜버|유투버).{0,15}(?:최고|제일)", flat):
        fail("대가 전환 누락", "'주식 유튜버 중에서 최고가 되고 싶다' 문구가 없습니다",
             "반론 차단 뒤에 대가 전환 문구를 넣으세요 (10_고정문구_변형.md 08번)")
    if not re.search(r"(?:고생\s*많으셨|수고\s*(?:많으셨|하셨))", flat):
        fail("마무리 인사 누락", "'고생 많으셨습니다' 계열 마무리 인사가 없습니다",
             "대본 맨 끝에 마무리 인사를 넣으세요")

    # ── 14-c2. 끊어 읽기 — 쉼표·마침표 (AGENTS.md 6-3/6-4) ──
    # TTS는 쉼표에서 숨을 쉰다. 없으면 한 호흡에 몰아쳐 읽는다.
    if "!" in flat or "！" in flat:
        fail("느낌표", "대본에 느낌표가 있습니다",
             "TTS가 과장되게 소리칩니다. 마침표로 바꾸세요")
    if re.search(r"…|\.{2,}", flat):
        fail("말줄임표", "대본에 말줄임표가 있습니다",
             "TTS가 읽지 못하고 멈추거나 점을 세어 읽습니다. 지우세요")
    if ",," in flat.replace(" ", ""):
        fail("쉼표 연속", "쉼표가 두 개 붙어 있습니다", "하나만 남기세요")

    # 조사 앞 쉼표 — 단어가 두 동강 나서 들린다
    # 이/가/의/도/만 은 관형사·명사와 겹쳐 오탐이 난다 (", 이 종목" 은 정상)
    _josa = re.findall(r".{0,8},\s*(?:은|는|을|를)\s", flat)
    if _josa:
        fail("조사 앞 쉼표", f"「{_josa[0].strip()}」",
             "조사 앞에서 끊으면 단어가 두 동강 나서 들립니다. 쉼표를 지우세요")

    # 반문형은 물음표로 끝나야 끝을 올려 읽는다
    _noq = [q for q in ("이해되시죠", "감 오시죠", "느낌 오시죠", "왜 그럴까요",
                        "이상하지 않아요", "좀 무섭죠", "눈치채셨어요", "어떠세요")
            if re.search(re.escape(q) + r"(?!\s*\?)", flat)]
    if _noq:
        fail("반문형 물음표 누락", f"「{_noq[0]}」",
             "반문형은 물음표로 끝내세요. 마침표를 찍으면 끝을 올려 읽지 않아 밋밋해집니다")

    # 쉼표 밀도 — 40자 초과 1개, 70자 초과 2개 (AGENTS.md 6-3)
    _thin = []
    for s in sents:
        L = len(s)
        c = s.count(",")
        if (L > 70 and c < 2) or (40 < L <= 70 and c < 1):
            _thin.append((L, c, s))
    if _thin:
        _thin.sort(key=lambda x: -x[0])
        L, c, s = _thin[0]
        lead = "쉼표 부족" if len(_thin) < 6 else "쉼표 부족 (다수)"
        fail(lead, f"{len(_thin)}문장 — 예: {L}자에 쉼표 {c}개 … {s[:42]}",
             "TTS가 한 호흡에 몰아쳐 읽습니다. 연결어미(~고/~는데/~면) 뒤나 "
             "접속부사(근데/그래서/반대로) 뒤에 쉼표를 넣으세요")

    # 쉼표 과다 — 4개 초과면 문장을 쪼개야 한다
    _fat = [s for s in sents if s.count(",") > 4]
    if _fat:
        warn("쉼표 과다", f"{len(_fat)}문장 — 예: {_fat[0][:42]}",
             "한 문장에 쉼표 4개가 넘으면 뚝뚝 끊깁니다. 문장을 두 개로 쪼개세요")

    # ── 14-d. 숫자 문장 4연속 금지 (CLAUDE.md §3) ──
    _num_streak = 0
    _num_bad_sent = None
    for s in sents:
        if re.search(r"\d", s):
            _num_streak += 1
            if _num_streak >= 4:
                _num_bad_sent = s
                break
        else:
            _num_streak = 0
    if _num_bad_sent:
        fail("숫자 4연속", f"…{_num_bad_sent[:40]}…",
             "숫자 문장이 4개 연속됩니다. 중간에 해석('이게 뭘 뜻하겠어요?')을 끼우세요")

    # ── 14-e. 퍼센트 밀도 (CLAUDE.md §3 — 문단당 2개 이하) ──
    _paras = [p.strip() for p in script.split("\n\n") if p.strip()]
    for _p in _paras:
        _pct_cnt = len(re.findall(r"\d+(?:[.·]\d+)?\s*(?:퍼센트|%)", _p))
        if _pct_cnt > 2:
            fail("퍼센트 과다", f"한 문단에 퍼센트 {_pct_cnt}개",
                 "문단당 퍼센트는 2개 이하. 나머지는 '크게 빠졌어요' 같은 해석으로 바꾸세요")
            break

    # ── 14-f. 무생물 주어 금지 (CLAUDE.md §6) ──
    _INANIMATE = [
        (r"차트가\s*(?:말해|보여|알려)", "'차트를 보면요'로"),
        (r"수치가\s*(?:답|말|증명|보여)", "'숫자로 확인하면'으로"),
        (r"거래량이\s*(?:말해|증명|보여주)", "'거래량을 보면'으로"),
        (r"캔들이\s*(?:말해|보여|알려)", "'캔들을 보면'으로"),
        (r"지표가\s*(?:말해|보여|알려|가리)", "'지표를 보면'으로"),
    ]
    for _ip, _ia in _INANIMATE:
        _im = re.search(_ip, flat)
        if _im:
            fail("무생물 주어", f"…{flat[max(0,_im.start()-15):_im.end()+15]}…",
                 f"{_ia} 바꾸세요")
            break

    # ── 14-g. 긴급 선언 존재 ──
    if not re.search(r"(?:긴급하게|급하게|서둘러서|바로\s*촬영|바로\s*영상|급하게\s*촬영|급하게\s*카메라|긴급\s*영상).{0,30}(?:촬영|만들|찍었|정리|올리|준비|들어갔|만든)", flat):
        fail("긴급 선언 누락", "긴급 영상 촬영 이유가 없습니다",
             "10_고정문구_변형.md 03번에서 긴급 선언 문구를 넣으세요")

    # ── 15. TTS 안전성 ── (사람이 안 읽고 바로 TTS로 가므로 가장 치명적)
    for pat, name, how in TTS_RISK:
        mm = re.search(pat, script)
        if mm:
            ctx = script[max(0, mm.start()-18):mm.end()+18].replace("\n", " ")
            fail(f"TTS 위험 · {name}", f"…{ctx}…", how)

    # ── 15. TTS 호흡 ──
    # 원본도 최장 109자까지 씀. 쉼표가 있으면 TTS가 거기서 쉰다.
    # 130자 넘거나, 100자 넘는데 쉼표가 하나도 없으면 진짜 못 읽는다.
    hard = [x for x in sents if len(x) > 130 or (len(x) > 100 and "," not in x)]
    if hard:
        fail("TTS 호흡", f"너무 긴 문장 {len(hard)}개 — …{hard[0][:40]}…",
             "쉼표를 넣거나 두 문장으로 쪼개세요. TTS가 숨을 못 쉽니다")
    soft = [x for x in sents if 90 < len(x) <= 130 and "," not in x]
    if soft:
        warn("긴 문장", f"{len(soft)}개 (90자 초과, 쉼표 없음)", "쉼표를 하나 넣으면 자연스러워집니다")
    nodot = [ln.strip() for ln in script.split("\n") if ln.strip() and ln.strip()[-1] not in ".?!"]
    if nodot:
        fail("마침표 누락", f"{len(nodot)}줄 — …{nodot[0][-38:]}…",
             "줄 끝에 마침표를 넣으세요. 없으면 TTS가 다음 문장과 이어 읽습니다")

    # ────────── 결과 출력 ──────────
    W = 66
    print()
    if fails:
        print("=" * W)
        print(f"   ❌  불합격 — {len(fails)}건.  고쳐서 다시 돌리세요")
        print("=" * W)
        for i, (name, detail, how) in enumerate(fails, 1):
            print(f"\n{i:2d}. [{name}]  {detail}")
            print(f"    → {how}")
    else:
        print("=" * W)
        print("   ✅  합격 — 업로드해도 됩니다")
        print("=" * W)
        print(f"   분량 {n:,}자 / {int(sec)//60}분 {int(sec)%60}초")
        if cta[0]:
            print(f"   CTA① {cta[0]:.0f}% 지점")

    if warns:
        print("\n" + "-" * W)
        print("   ⚠ 참고 (막지는 않습니다)")
        for name, detail, how in warns:
            print(f"   · [{name}] {detail} → {how}")

    print()

    # ── 관리자용 로그 (누가 몇 번 만에 통과했는지 남는다) ──
    try:
        logp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "검증로그.tsv")
        new = not os.path.exists(logp)
        with open(logp, "a", encoding="utf-8") as lf:
            if new:
                lf.write("시각\t사용자\t파일\t결과\t불합격건수\t분량\t항목\n")
            who = os.environ.get("USERNAME") or os.environ.get("USER") or "?"
            items = ";".join(sorted({f[0] for f in fails}))
            lf.write(f"{datetime.now():%Y-%m-%d %H:%M}\t{who}\t{os.path.basename(script_path)}\t"
                     f"{'불합격' if fails else '합격'}\t{len(fails)}\t{n}\t{items}\n")
    except Exception:
        pass

    approve = os.path.join(os.path.dirname(os.path.abspath(script_path)) or ".", "합격.txt")
    if fails:
        if os.path.exists(approve):
            os.remove(approve)
        print(f"   업로드 금지. {len(fails)}건 고친 뒤 이 명령을 다시 실행하세요.\n")
        return 1
    with open(approve, "w", encoding="utf-8") as f:
        f.write(f"{os.path.basename(script_path)}\n검증 통과: {datetime.now():%Y-%m-%d %H:%M}\n분량 {n:,}자\n")

    archive_script(script_path, script)          # 다음 편 중복 검사용으로 보관

    # ── TTS 입력용 파일 자동 생성 ──
    clean, changes = tts_sanitize(script)
    ttsp = os.path.join(os.path.dirname(os.path.abspath(script_path)) or ".", "TTS용_대본.txt")
    with open(ttsp, "w", encoding="utf-8") as f:
        f.write(clean)

    print(f"   '합격.txt' 생성됨. 이 파일이 있어야 업로드할 수 있습니다.")
    print()
    print("   " + "─" * (W - 6))
    print(f"   ★ 일레븐랩스에는 반드시 이 파일을 넣으세요")
    print(f"     → {os.path.basename(ttsp)}")
    if changes:
        print(f"     (자동 정리: {', '.join(changes[:6])}{' 외' if len(changes) > 6 else ''})")
    print("   " + "─" * (W - 6))
    print("   원본 대본 파일이나 마크다운 문서를 그대로 붙여넣지 마세요.")
    print("   타임코드·별표를 TTS가 소리 내어 읽습니다.\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    s = sys.argv[1]
    b = sys.argv[2] if len(sys.argv) > 2 else "brief.md"
    if not os.path.exists(s):
        print(f"\n[!] 대본 파일이 없습니다: {s}\n")
        sys.exit(2)
    sys.exit(run(s, b))
