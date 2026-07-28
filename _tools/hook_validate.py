# -*- coding: utf-8 -*-
"""
PostToolUse 훅 — 대본 .txt 파일이 저장될 때마다 자동으로 검증한다.

Claude Code가 Write/Edit를 끝내면 이 스크립트를 호출한다.
불합격이면 decision=block 으로 결과를 Claude에게 되돌려서 스스로 고치게 만든다.

설정 위치: .claude/settings.json  (PostToolUse / Write|Edit)
"""

import sys, os, json, subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

# 대본이 아닌 파일까지 검사하면 시끄러워진다. 아래 조건을 모두 만족할 때만 검사.
MIN_CHARS = 1500                      # 진짜 대본은 3,000자 이상
SKIP_DIRS = ("_tools", ".claude", "__pycache__")
SKIP_NAMES = ("TTS용_대본.txt", "합격.txt", "ids.txt", "meta.txt")


def out(obj):
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    path = ti.get("file_path") or tr.get("filePath") or ""
    if not path or not path.lower().endswith(".txt"):
        sys.exit(0)

    name = os.path.basename(path)
    if name in SKIP_NAMES or any(f"{os.sep}{d}{os.sep}" in path for d in SKIP_DIRS):
        sys.exit(0)
    if not os.path.exists(path):
        sys.exit(0)
    try:
        if len(open(path, encoding="utf-8").read()) < MIN_CHARS:
            sys.exit(0)
    except Exception:
        sys.exit(0)

    brief = os.path.join(ROOT, "brief.md")
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "validate.py"), path, brief],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except Exception as e:
        out({"systemMessage": f"[검증 훅] 실행 실패: {e}"})

    report = (r.stdout or "").strip()

    if r.returncode == 0:
        out({"systemMessage": f"✅ 대본 검증 통과 — {name}",
             "suppressOutput": True})

    out({
        "decision": "block",
        "reason": (
            "대본이 검증을 통과하지 못했습니다. 아래 항목을 전부 고치고 파일을 다시 저장하세요.\n"
            "합격할 때까지 반복하고, 합격 전에는 완료했다고 말하지 마세요.\n\n"
            + report
        ),
        "systemMessage": f"❌ 대본 검증 불합격 — {name} (Claude가 자동으로 고칩니다)",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": report,
        },
    })


if __name__ == "__main__":
    main()
