# -*- coding: utf-8 -*-
"""
구어체 가드 — 한국어 대본/원고의 보고서투·AI말투·번역체를 잡는 CLI 검사기.
TTS/유튜브/팟캐스트 대본에 최적화.

사용법: python check.py <파일경로>
"""
import sys, os, re

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── 금지 단어: 보고서투/AI투 → 구어체 ───
BANNED = [
    (r"일중\s*(?:공매도|거래|비중|매매)", "일중", "오늘 하루"),
    (r"사수(?:는|를|에|했|한)", "사수", "지켜줬고요 / 지켰고요"),
    (r"동반\s*(?:하락|상승|급락|급등|매도|매수)", "동반 하락/상승", "~하면서 같이 밀렸다/올랐다"),
    (r"반쪽\s*(?:나|줄|빠)", "반쪽 나다", "반토막 나다"),
    (r"선명해(?:져|지|요|집니다|진)", "선명해지다", "확실해요 / 보이죠 / 나와요"),
    (r"뒤집어서\s*(?:확인|보면|살펴)", "뒤집어서 확인", "반대로 보면 / 삭제"),
    (r"(?:매물|힘|에너지|연료)(?:이|가)?\s*소진", "소진", "다 나왔다 / 빠졌다"),
    (r"분기점", "분기점", "갈리는 자리 / 갈림길"),
    (r"(?:위에|위로|선\s*위에)\s*안착", "안착", "자리를 잡다 / 올라서다"),
    (r"변곡(?:\s*(?:점|신호|구간))?", "변곡", "방향이 바뀌는 / 꺾이는"),
    (r"(?:매력|가치|실적)(?:이|가)?\s*부각", "부각", "눈에 띄다 / 드러나다"),
    (r"따라서\s", "따라서", "그래서 / 그러니까"),
    (r"종합하면", "종합하면", "정리하면요 / 바로 결론부터"),
    (r"(?:인|된|라는)\s*셈이(?:에요|다|죠)", "~인 셈이에요", "~라는 거예요"),
    (r"뒷받침(?:하|합|해|된|을)", "뒷받침", "맞아떨어지다 / 같은 말을 하다"),
    (r"촉발", "촉발", "시작하게 한 / 원인이 된"),
    (r"괴리(?:가|를|도)?", "괴리", "차이 / 격차"),
    (r"위험\s*회피", "위험 회피", "공포 매도 / 겁먹고 던지는"),
    (r"여지(?:가|를|도)\s*(?:있|남|큰|작)", "여지", "~할 수 있다 / 가능성"),
    (r"(?:아주\s*)?뚜렷(?:한|하게|이)", "뚜렷한", "확실한 / 눈에 보이는"),
    (r"수렴(?:하|해|한)", "수렴", "따라 내려가는 / 맞춰가는"),
    (r"오독(?:이|을|하|에)", "오독", "잘못 읽는 거예요"),
    (r"유인(?:이|을)\s*(?:생기|만들)", "유인", "~해야 하는 상황"),
    (r"숫자로\s*짚어", "숫자로 짚어", "쉽게 설명드리겠습니다"),
    (r"(?<![가-힣])봉(?:을|이|은|의|에서|으로|도)", "봉", "캔들"),
    # 문법·표기
    (r"(주일|개월|시간|달|해|년)\s+새(?=[\s,.])", "기간+새", "~사이에"),
    (r"기반으로\s*한\s", "기반으로 한", "~에 기반을 둔"),
    (r"헤지(?!펀드)", "헤지", "헷지"),
    # AI 자기 고백
    (r"인정하고\s*들어가", "자기 고백", "삭제, 담담히 사실만"),
    (r"솔직하게\s*(?:말씀|하나)", "자기 고백", "삭제, 바로 본론"),
    (r"정직한\s*(?:거|겁니다|거예요)", "자기 고백", "삭제"),
    (r"숨기지\s*않고", "자기 고백", "삭제"),
    (r"겸허하게", "자기 고백", "삭제"),
    # AI 예고 필러
    (r"준비운동이고", "AI 필러", "삭제, 바로 본론"),
    (r"이유가\s*셋", "AI 필러", "삭제, 바로 나열"),
    (r"하나도\s*빼지\s*않고", "AI 필러", "삭제"),
    (r"처음부터\s*차근차근", "AI 필러", "삭제, 바로 시작"),
    (r"먼저\s*숫자부터\s*보겠", "AI 필러", "삭제, 바로 숫자부터"),
    # 보고서 전환어
    (r"결론적으로", "보고서 전환", "그래서 제 결론은요"),
    (r"이를\s*통해", "보고서 전환", "그래서 / 삭제"),
    (r"이러한\s*점에서", "보고서 전환", "그래서 / 삭제"),
    (r"살펴보겠습니다", "보고서 전환", "볼게요 / 바로 시작"),
    (r"나아가\s", "보고서 전환", "그럼 / 근데"),
    # 번역체
    (r"(?:는|은)\s*사실이다", "번역체", "한국어 자연어로"),
    (r"에\s*의해\s*(?:되|된|됐)", "번역체/수동태", "능동태로 전환"),
    # ── 전환 예고 필러 (원본 채널 0회 — 전환어와 내용을 한 문장으로 합칠 것) ──
    (r"(?:도|를|을|는)?\s*같이\s*보겠습니다", "전환 예고", "'~를 보면 [내용]' 한 문장으로"),
    (r"짚고\s*(?:가|갈|넘어)", "전환 예고", "예고 빼고 바로 내용"),
    (r"얘기가\s*나왔으니", "전환 예고", "삭제, 바로 내용"),
    # '일봉 차트를 먼저 보시게 되면요'(채널 고정 문구)는 통과시키고 예고형만 잡는다
    (r"먼저\s*(?:보겠|확인해\s*보겠|짚어\s*보겠|살펴)", "전환 예고", "'먼저' 빼고 바로 내용"),
    (r"말씀드릴게요\s*\.", "전환 예고", "삭제, 바로 본론"),
    (r"이제\s*(?:부터\s*)?(?:보|확인|살펴)겠", "전환 예고", "삭제, 바로 내용"),
    (r"차례로\s*(?:보|짚|확인)", "전환 예고", "삭제, 바로 내용"),
]


def check_banned(text):
    issues = []
    for pat, label, replacement in BANNED:
        for m in re.finditer(pat, text):
            flat = text.replace("\n", " ")
            ctx = flat[max(0, m.start()-15):m.end()+15]
            issues.append(("금지 단어", f"[{label}] …{ctx}…", replacement))
    return issues


def check_ending_monotone(text):
    issues = []
    sents = [s.strip() for s in re.split(r"(?<=[.?!요다죠])\s+|\n+", text) if len(s.strip()) >= 10]
    endings = []
    for s in sents:
        s = s.rstrip(".")
        if s.endswith("습니다") or s.endswith("입니다"):
            endings.append("습니다")
        elif s.endswith("어요") or s.endswith("았어요") or s.endswith("었어요") or s.endswith("예요") or s.endswith("이에요"):
            endings.append("요")
        elif s.endswith("거든요"):
            endings.append("거든요")
        elif s.endswith("거예요") or s.endswith("겁니다") or s.endswith("거죠"):
            endings.append("거")
        else:
            endings.append("other")
    for i in range(len(endings) - 3):
        if endings[i] == endings[i+1] == endings[i+2] == endings[i+3] and endings[i] != "other":
            issues.append(("어미 4연속", f"'{endings[i]}' 계열 4문장 연속", "다른 어미로 섞기 (~거든요/~잖아요/~라는 거예요)"))
            break
    return issues


def check_number_streak(text):
    issues = []
    num_re = re.compile(r"(?:천|백|만|억|조|퍼센트|배|원|포인트)")
    sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+|\n+", text) if len(s.strip()) >= 15]
    streak = 0
    for s in sents:
        if num_re.search(s):
            streak += 1
        else:
            streak = 0
        if streak >= 4:
            issues.append(("숫자 4연속", s[:40], "숫자 사이에 '이게 뭘 뜻하냐면' 해석 끼우기"))
            break
    return issues


def check_pct_density(text):
    issues = []
    for para in re.split(r"\n\s*\n", text):
        pcts = re.findall(r"퍼센트|%", para)
        if len(pcts) >= 3:
            preview = para.strip().replace("\n", " ")[:50]
            issues.append(("퍼센트 과다", f"{len(pcts)}개: {preview}…", "핵심 1~2개만, 나머지는 해석으로"))
    return issues


def check_noun_pile(text):
    issues = []
    for m in re.finditer(r"[가-힣]+(?:은|는)\s+[가-힣]+(?:고|이고),\s*[가-힣]+(?:은|는)\s+[가-힣]+(?:습니다|입니다|이다|였다)", text):
        issues.append(("명사형 나열", m.group(0)[:50], "'~했고요, ~였어요' 구어체로 풀기"))
    return issues


def check_inanimate_subject(text):
    issues = []
    patterns = [
        (r"차트가\s*(?:말해|보여|알려|가리)", "차트가 말해준다"),
        (r"수치가\s*(?:답을|말을|증명)", "수치가 답을 내놨다"),
        (r"숫자가\s*(?:말해|보여|증명)", "숫자가 말해준다"),
        (r"데이터가\s*(?:말해|보여|증명)", "데이터가 말해준다"),
        (r"시장이\s*(?:말해|보여|증명)", "시장이 말해준다"),
    ]
    for pat, label in patterns:
        if re.search(pat, text):
            issues.append(("무생물 주어", label, "사람 주어로: '차트를 보면요' / '숫자로 확인하면'"))
    return issues


def check_near_duplicate(text):
    issues = []
    def _sh2(s):
        s = re.sub(r"[^가-힣0-9]", "", s)
        return set(s[i:i+2] for i in range(len(s) - 1))
    sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+|\n+", text) if len(s.strip()) >= 20]
    for i in range(len(sents) - 1):
        a2, b2 = _sh2(sents[i]), _sh2(sents[i + 1])
        if a2 and b2 and len(a2 & b2) / len(a2 | b2) >= 0.23:
            issues.append(("인접 중복", sents[i + 1][:40], "하나로 합치거나 삭제"))
    return issues


def check_report_transitions(text):
    issues = []
    report_words = [
        (r"다음으로\s*살펴보겠습니다", "다음으로 살펴보겠습니다"),
        (r"이어서\s", "이어서"),
        (r"그러나\s", "그러나"),
        (r"하지만\s", "하지만"),
    ]
    for pat, label in report_words:
        for m in re.finditer(pat, text):
            issues.append(("보고서 전환", label, "'자, 그럼~' / '근데' / 바로 시작"))
    return issues


def main():
    if len(sys.argv) < 2:
        print("사용법: python check.py <파일경로>")
        print("  한국어 대본/원고의 보고서투·AI말투·번역체를 잡아 구어체 대체안을 제시합니다.")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    text = open(path, encoding="utf-8").read()
    fname = os.path.basename(path)

    print(f"=== 구어체 검수: {fname} ===\n")

    # 글자수
    n = len(text.replace("\n", "").replace(" ", ""))
    print(f"본문 {n}자\n")

    # 검사 실행
    word_issues = check_banned(text)
    struct_issues = []
    struct_issues.extend(check_ending_monotone(text))
    struct_issues.extend(check_number_streak(text))
    struct_issues.extend(check_pct_density(text))
    struct_issues.extend(check_noun_pile(text))
    struct_issues.extend(check_inanimate_subject(text))
    struct_issues.extend(check_near_duplicate(text))
    struct_issues.extend(check_report_transitions(text))

    total = len(word_issues) + len(struct_issues)

    if word_issues:
        print(f"📝 금지 단어 {len(word_issues)}건:")
        for kind, detail, fix in word_issues:
            print(f"  {detail}")
            print(f"    → {fix}")
        print()

    if struct_issues:
        print(f"📐 문장 구조 {len(struct_issues)}건:")
        for kind, detail, fix in struct_issues:
            print(f"  [{kind}] {detail}")
            print(f"    → {fix}")
        print()

    if total == 0:
        print("✅ 구어체 OK — 보고서투·AI투 없음")
    else:
        print(f"⚠️ 총 {total}건 — 위 항목 확인 후 수정")


if __name__ == "__main__":
    main()
