# -*- coding: utf-8 -*-
"""
변형 뱅크 생성기 — 원본 대본에서 실제 문장을 기능별로 뽑아 정리한다.

    python _tools/build_bank.py

왜 필요한가
    중복을 피하려고 AI가 문장을 새로 지어내면 원본에 없는 낯선 말투가 나온다.
    원본 12편 안에 이미 871개 문장이 있다. 새로 만들 게 아니라 여기서 골라 쓰면
    중복도 피하고 말투도 안 벗어난다.

출력: 09_변형뱅크.md
"""

import sys, os, re, glob
from collections import OrderedDict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "_raw")

# 안교수 포맷 12편만 사용 (김교수 구포맷 2편 제외)
KIM = {"wCHXQOMXea0", "pIFHlZcIv48"}

# (기능명, 설명, 판별 정규식) — 위에서부터 먼저 맞는 것으로 분류
FUNCS = [
    ("01 오프닝 · 인사",       "첫 인사와 자기소개",
     r"안녕하십니까|주주분들 반갑습니다|교수입니다"),
    ("02 오프닝 · 시세",       "현재가·등락률·거래량",
     r"전\s?거래일|전일보다|급락하고 있고|거래량은 약|주가 잡혔|주가 터졌|주까지 늘어"),
    ("03 후크",               "후크 다음에 오는 문장 — 우리 후크는 AGENTS.md 3번 참고",
     r"뭐를 놓치고|숫자만 볼게 아니라|숫자보다 더 중요한|사실만 볼게 아니라"),
    ("04 시장 전체",          "지수·상승하락 종목수",
     r"코스피는|코스피가|코스닥은|코스피 200|상승 종목|하락 종목|서킷 브레이커"),
    ("05 패닉 해석",          "사실을 시장 전체 현금화로 번역",
     r"패닉 장세|현금을 만들|현금화|위험 자산을 줄이|가리지 않고|위험 노출"),
    ("06 외국인 시그니처",     "수급을 짚고 들어가는 자리",
     r"제가 항상 말씀드리죠|외국인들의 움직임을 봐야|시장의 신호"),
    ("07 수급 숫자",          "외국인·기관·개인 금액",
     r"순\s?매도했|순매도하고|받아냈습니다|받아내고 있|순\s?매수했|선물에서도|던지고 있습니다"),
    ("08 수급 해석",          "그래서 이 구조가 무엇인가",
     r"구조입니다|구조라는|구조가 뭡|뜻입니다|현물만 파는게 아니라|유동성이 가격을"),
    ("09 긴급 선언",          "촬영 이유 + 시청 유지",
     r"긴급하게 영상을|영상을 촬영했습니다|끝까지 봐|눈 크게 뜨고|정신 똑바로 차리고"),
    ("10 양비론",             "양쪽 다 아니라고 못 박는 자리",
     r"때도 아니|날도 아니|자리도 아니|무작정|공포에 (전부|모든|휩쓸려)"),
    ("11 CTA① 구독",         "구독·좋아요·댓글 키워드",
     r"본격적으로 시청|구독과 좋아요 꼭|댓글로 .{0,6}(이)?라고|의미를 담아서|의미 담아서"),
    ("12 차트 진입",          "차트 해설 진입",
     r"일봉 차트를"),
    ("13 하락·조정 서사",      "고점 이후 어떻게 왔는가",
     r"고점을 만든|고점과 저점이 낮아지|조정을 받아왔|이어왔습니다|이동 평균선과 두꺼운|매물에 막혔"),
    ("14 이탈·붕괴",          "지지선이 무너진 순간",
     r"이탈했|무너졌고|무너진 겁|밀렸습니다|밀리면서|한 번에 이탈|버티려는 모습"),
    ("15 매물대 · 본전심리",   "위쪽 매물이 반등을 막는다",
     r"매물이 남아|본전 심리|본전이 가까|물린 물량|거래가 집중|매물대|두껍게 남아"),
    ("16 가격 ≠ 기업가치",     "하루 만에 사업가치가 사라지진 않는다",
     r"사업 가치가|하루 만에|사라졌다고|없어지는 건 아니|기업 가치가|좋은 자산도|먼저 팔"),
    ("17 거래량 해석",        "던진 쪽과 받은 쪽",
     r"거래량이 (최근보다|터졌|붙|늘)|던진 사람이|받은 주체|매집이라고|종가가 장중 저가"),
    ("18 지표 무력화",        "RSI가 낮다고 바닥이 아니다",
     r"RSI|심리도|과매도|지표가 낮|바닥은 숫자가|보조 지표"),
    ("19 세력 관점",          "세력 입장으로 관점을 옮기는 자리",
     r"생각해 보세요|세력들이|세력들 입장|위아래로 흔들|따라붙는 개인|테스트하고"),
    ("20 개인 순매수 경계",    "개인이 많이 샀다고 바닥이 아니다",
     r"개인 순매수|개인만 받|물타기|신용 유지|반대\s?매매|레버리지"),
    ("21 조건부 시나리오",     "A하면 X / 반대로 B하면 Y",
     r"반대로 |회복하지 못하|그친다면|그칠 수 있|진정되고 있다는|해석이 가능"),
    ("22 체크포인트",         "첫째·둘째·셋째",
     r"첫째|둘째|셋째|세 가지|딱 세|반드시 잡아야|확인해야 할"),
    ("23 기술적반등 vs 수급전환", "반등의 질을 봐야 한다",
     r"기술적 반등|수급 전환|완전히 다른 얘기|반등의 지|반등 폭보다|매도자가 잠시"),
    ("24 감정 · 심리",        "화자의 취약성 노출과 감정 관리",
     r"솔직히 말씀드리면|비트코인|감정적으로|마음이|화가|공포를 느끼|사람이다 보니"),
    ("25 사회적 증거",        "지난 회차 대응 기준을 언급",
     r"저번에 |남겨 주신 분|대응 기준을 (정리|잡)|연락도 받았"),
    ("26 CTA② 접근성",       "실시간으로 못 본다는 문제 제기",
     r"제 방송을|개인 번호를|문자 한\s?통|도움드리도록"),
    ("27 무료 해명",          "반론 선차단",
     r"오해하시는 분들|돈을 받는 거 아닙|상담비|가입비|무료로|부담 갖지"),
    ("28 요약",              "마무리 요약",
     r"다시 돌아와서|얼마까지 간다|약속은 드릴 수 없|계좌를 지키"),
    ("29 고립 공포 · 클로징",  "혼자 판단하지 말라는 마무리",
     r"혼자 하는 거 아닙|집단 지성|혼자 하지 마세요|선생님도 필요"),
    ("30 마무리 CTA",         "구독·좋아요·댓글 마무리",
     r"구독 아직 안 하신|좋아요 버튼 있죠|한 마디씩 남겨 주시기|이겨냅시다"),
]

BAD = re.compile(r"[a-zA-Z]{4,}|\.\.\.|…")           # 자막 깨짐 의심

# ★ 원본 채널의 시그니처 문구 — 우리는 우리 문구를 쓰므로 뱅크에서 뺀다 (B안)
ORIG_SIGNATURE = re.compile(
    r"뭐를 놓치고 있는지|제가 항상 말씀드리죠|외국인들의 움직임을 봐야|"
    r"이게 뭐냐면요|일봉 차트를 먼저|여러분들 생각해 보세요|"
    r"본격적으로 시청 전에|제 방송을 모두|다시 돌아와서 우리"
)
NOISE = re.compile(r"^\s*(자|어|음|네|그|저)\s*[,.]?\s*$")


def clean(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([.,?!])", r"\1", s)
    return s


def main():
    files = [f for f in sorted(glob.glob(os.path.join(RAW, "*.plain.txt")))
             if os.path.basename(f).split(".")[0] not in KIM]
    if not files:
        print("[!] _raw/*.plain.txt 가 없습니다."); return 2

    sents = []
    for f in files:
        t = re.sub(r"\s+", " ", open(f, encoding="utf-8").read())
        for s in re.split(r"(?<=[.?!])\s+", t):
            s = clean(s)
            if ORIG_SIGNATURE.search(s):
                continue
            if 12 <= len(s) <= 120 and not BAD.search(s) and not NOISE.match(s):
                sents.append(s)

    buckets = OrderedDict((n, []) for n, _, _ in FUNCS)
    unclassified = []
    for s in sents:
        for name, _, pat in FUNCS:
            if re.search(pat, s):
                buckets[name].append(s)
                break
        else:
            unclassified.append(s)

    # 거의 같은 문장 제거 (앞 18자 기준)
    for k in buckets:
        seen, out = set(), []
        for s in buckets[k]:
            key = re.sub(r"[^가-힣]", "", s)[:18]
            if key in seen:
                continue
            seen.add(key); out.append(s)
        buckets[k] = sorted(out, key=len)

    desc = {n: d for n, d, _ in FUNCS}
    total = sum(len(v) for v in buckets.values())
    out = []
    out.append("# 변형 뱅크 — 원본 안교수 12편에서 뽑은 실제 문장\n")
    out.append("> **새 문장을 지어내지 마세요.** 여기서 골라 쓰면 중복도 피하고 말투도 안 벗어납니다.\n")
    out.append("> 같은 기능에 여러 개가 있습니다. 회차마다 **다른 번호를 고르세요.**\n")
    out.append(f"> 자동 생성: `python _tools/build_bank.py` · 원본 12편 / 분류된 문장 {total}개\n")
    out.append("\n---\n")
    for name, _, _ in FUNCS:
        v = buckets[name]
        if not v:
            continue
        out.append(f"\n## {name}  ({len(v)}개)\n")
        out.append(f"*{desc[name]}*\n")
        for i, s in enumerate(v[:14], 1):
            out.append(f"{i}. {s}")
        if len(v) > 14:
            out.append(f"\n<sub>… 외 {len(v)-14}개</sub>")
        out.append("")
    out.append("\n---\n")
    out.append("## 쓰는 법\n")
    out.append("1. 블록마다 위 목록에서 **하나 고릅니다.**")
    out.append("2. **지난 회차에 쓴 번호는 피합니다.**")
    out.append("3. 종목명·숫자만 이번 브리프 값으로 바꿉니다.")
    out.append("4. 목록에 없는 표현이 필요하면 — **만들지 말고 비슷한 기능의 다른 문장을 고릅니다.**")

    path = os.path.join(HERE, "..", "09_변형뱅크.md")
    open(path, "w", encoding="utf-8").write("\n".join(out))

    print(f"분류 {total}개 / 미분류 {len(unclassified)}개")
    print(f"{'기능':28s} 문장수")
    print("-" * 40)
    for name, _, _ in FUNCS:
        if buckets[name]:
            print(f"{name:28s} {len(buckets[name]):4d}")
    print(f"\n생성 완료: 09_변형뱅크.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
