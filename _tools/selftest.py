# -*- coding: utf-8 -*-
"""
검증기 자체를 검증하는 회귀 테스트

    python _tools/selftest.py

왜 필요한가
    검증 규칙은 두 가지로 틀릴 수 있다.
      ① 오탐 — 원본 안교수가 실제로 쓰는 표현을 '금지'로 막는다  → 직원이 검증기를 무시하게 된다
      ② 놓침 — 명백한 AI 문장을 통과시킨다                      → 이상한 대본이 그대로 나간다
    이 테스트는 둘 다 잡는다.

    ①은 원본 14편을 정답지로 쓴다. 원본이 걸리면 그 규칙이 틀린 것이다.
    ②는 일부러 AI스럽게 쓴 문장을 넣어 걸리는지 확인한다.

규칙을 고칠 때마다 반드시 실행할 것.
"""

import sys, os, re, glob, importlib.util

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "_raw")

spec = importlib.util.spec_from_file_location("v", os.path.join(HERE, "validate.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


# 원본이 "반드시 통과해야 하는" 규칙만 검사한다.
# 구조 규칙(분량·인사 위치·후크 위치)과 TTS 규칙은 제외 —
# 원본과 우리 대본은 그 부분이 의도적으로 다르고,
# 자막은 TTS 출력을 받아적은 것이라 표기가 원본 대본과 다르다.
STYLE_RULES = (
    [("금지 단어", p, a) for p, a in V.BANNED_WORDS] +
    [("예고 필러", p, a) for p, a in V.FILLER] +
    [("문어체 종결", p, a) for p, a in V.LITERARY_ENDINGS]
)

# 일부러 AI스럽게 쓴 문장 — 반드시 걸려야 한다
AI_SAMPLES = [
    ("보고서투",   "이번 조정은 수급과 실적의 괴리에서 촉발된 것으로 보이며, 주요 분기점에 도달했습니다."),
    ("AI 자기고백", "인정하고 들어가겠습니다. 숨기지 않고 겸허하게 말씀드리면 지표는 혼조입니다."),
    ("AI 예고필러", "처음부터 차근차근 살펴보겠습니다. 다음으로 넘어가 보겠습니다."),
    ("보고서 전환", "종합하면 결론적으로 이를 통해 반등 가능성을 확인할 수 있습니다."),
    ("문어체 어미", "이러한 점에서 매수세가 유입되고 있다는 사실이다."),
    ("전환 예고",   "거래량 얘기가 나왔으니 짚고 갈게요. 먼저 살펴보겠습니다."),
]


def load_corpus():
    out = {}
    for f in sorted(glob.glob(os.path.join(RAW, "*.plain.txt"))):
        name = os.path.basename(f).replace(".plain.txt", "")
        out[name] = re.sub(r"\s+", " ", open(f, encoding="utf-8").read())
    return out


def main():
    corpus = load_corpus()
    if not corpus:
        print("\n[!] _raw/*.plain.txt 가 없습니다. 원본 자막을 먼저 받아 주세요.\n")
        return 2

    W = 70
    print("=" * W)
    print("■ 테스트 1 — 원본 안교수 대본이 우리 문체 규칙을 통과하는가")
    print("=" * W)
    print(f"  대상: 원본 {len(corpus)}편")
    print()

    false_pos = {}
    for name, text in corpus.items():
        for kind, pat, alt in STYLE_RULES:
            m = re.search(pat, text)
            if m:
                false_pos.setdefault((kind, pat), []).append(
                    (name, text[max(0, m.start() - 20):m.end() + 20]))

    if false_pos:
        print(f"  ❌ 오탐 {len(false_pos)}건 — 원본이 쓰는 표현을 막고 있습니다\n")
        for (kind, pat), hits in sorted(false_pos.items(), key=lambda x: -len(x[1])):
            print(f"   [{len(hits):2d}/{len(corpus)}편] {kind}  {pat}")
            print(f"        …{hits[0][1]}…")
            if len(hits) >= len(corpus) * 0.25:
                print(f"        → 원본 25% 이상이 씁니다. 이 규칙은 빼거나 경고로 낮추세요.")
            else:
                print(f"        → 드물게 쓰입니다. SOFT_WORDS로 옮기는 걸 검토하세요.")
            print()
        t1 = False
    else:
        print("  ✅ 통과 — 원본을 하나도 오탐하지 않습니다\n")
        t1 = True

    print("=" * W)
    print("■ 테스트 2 — 명백한 AI 문장을 잡아내는가")
    print("=" * W)
    print()
    missed = []
    for label, sample in AI_SAMPLES:
        hit = [k for k, p, _ in STYLE_RULES if re.search(p, sample)]
        if hit:
            print(f"  ✅ [{label}] 걸림 ({', '.join(sorted(set(hit)))})")
        else:
            print(f"  ❌ [{label}] 놓침 — {sample[:44]}…")
            missed.append(label)
    t2 = not missed
    print()

    print("=" * W)
    print("■ 테스트 3 — 코퍼스 어미 사전이 제대로 만들어졌는가")
    print("=" * W)
    endings, stats = V.load_corpus_profile()
    t3 = bool(endings) and len(endings) > 200
    if endings:
        print(f"  어미 사전 {len(endings):,}개 수집")
        print(f"  문장길이 편차 기준 {stats['sd_min']:.0f} ~ {stats['sd_max']:.0f}")
        probe = ["합니다만", "인 것입니다", "라 하겠습니다", "이라 할 수 있습니다"]
        caught = [p for p in probe if V.sentence_ending(p + ".") not in endings]
        print(f"  문어체 표본 {len(probe)}개 중 {len(caught)}개를 '원본에 없음'으로 판정")
        print(f"  {'✅ 통과' if t3 else '❌ 사전이 너무 작습니다'}")
    else:
        print("  ❌ 코퍼스를 못 읽었습니다")
    print()

    ok = t1 and t2 and t3
    print("=" * W)
    print(f"   {'✅  전체 통과 — 검증기를 믿고 쓰셔도 됩니다' if ok else '❌  실패 — validate.py 규칙을 고치세요'}")
    print("=" * W)
    print(f"   원본 오탐 없음 {'✅' if t1 else '❌'}   AI 문장 검출 {'✅' if t2 else '❌'}   어미 사전 {'✅' if t3 else '❌'}")
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
