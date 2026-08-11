"""민사법 변시 1·2·3회에 「민민소 사례 CBT실전답안」 해설을 채점 근거로 붙인다.

왜
  이 세 회차는 정연석 책에 요약만 있어(건당 400~1,600자, 문항 수보다 답안 건수도
  적다) AI 채점이 사실상 근거 없이 돌아간다. 다른 회차는 재OCR로 보강돼 건당
  1.5k~4.9k자가 있다.

  그런데 `casebook_cases.json` 에는 박승수 CBT실전답안이 변시 1~15회 전부에
  회차당 1.3만~1.5만 자로 이미 들어와 있었다. 사례집 브라우저에서만 보이고
  채점 근거(`casebookAnswers`)로는 안 쓰이고 있었을 뿐이다.

  네 회차 이후는 손대지 않는다. 이미 근거가 충분한데 답안을 두 배로 늘리면
  채점 프롬프트만 커진다.

당사자 기호 교정
  이 책도 박승수·학연 조합이라 「민법 기본사례」와 같은 OCR 버릇이 있다. 이 세
  회차만 봐도 `乙`이 37회인데 **`Z`+조사가 79회**다 — 乙의 3분의 2가 로마자 Z로
  흘렀다. 甲(58)·丙(58)에 견주면 분포부터 뒤집혀 있다. 이걸 두면 채점기가 당사자를
  못 알아본다.

  다만 `parkss_body_fixes.apply()` 를 통째로 쓰지는 않는다. 그쪽엔 「민법 기본사례」
  지면에만 있는 교정(제목 띠 잡음·그 책의 오탈자·`i차`→`丙` 같은 국소 규칙)이
  섞여 있어 다른 책에 대면 없던 오류를 만든다. 근거가 책과 무관하게 성립하는
  `LETTER_PARTY`(로마자+조사 → 당사자 기호)만 가져다 쓴다.

책 뒷부분 잘라내기
  마지막 블록(제1회 제2문)이 133,008자다. 사례집 분할기가 마지막 사례에 책의
  나머지(판권지 + 전 회차 문제편)를 통째로 붙였기 때문이다. 실제 해설은 앞
  5,900자뿐이고 나머지는 문제 지문이라, 그대로 넣으면 채점기에 **문제를 답안이라고**
  주는 꼴이 된다. 저자 약력·판권지·문제편이 시작되는 자리에서 자른다.

사용
  python pipeline/scripts/add_cbt_answers.py [--write]
  여러 번 돌려도 같은 답안을 두 번 붙이지 않는다.
"""
import json
import re
import sys
from pathlib import Path

from parkss_body_fixes import LETTER_PARTY

ROOT = Path(__file__).resolve().parents[2]
SUBJECT = "민사법"
BOOK = "민민소 사례 CBT실전답안"
TARGETS = [1, 2, 3]

# 해설이 끝나고 책 뒷부분이 시작되는 자리. 가장 먼저 나오는 것에서 자른다.
TAIL = re.compile(r"\[약\s*력\]|편저자\s*박승수|발행일\s*[::]|ISBN|\[문제편\]")


def body(text):
    m = TAIL.search(text)
    text = (text[:m.start()] if m else text).strip()
    for rx, to in LETTER_PARTY:
        text = rx.sub(to, text)
    return text


def main():
    write = "--write" in sys.argv
    cases = json.loads((ROOT / "data" / SUBJECT / "casebook_cases.json").read_text("utf-8"))

    picked = {}
    for v in cases.values():
        if v.get("book") != BOOK:
            continue
        eid = (v.get("source") or {}).get("examId", "")
        m = re.fullmatch(r"민사법_변시_(\d+)회_사례", eid)
        if m and int(m.group(1)) in TARGETS:
            picked.setdefault(eid, []).append(v)

    ipath = ROOT / "data" / SUBJECT / "index.json"
    index = json.loads(ipath.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in index["exams"]}

    for eid, items in sorted(picked.items()):
        epath = ROOT / "data" / SUBJECT / "exams" / f"{eid}.json"
        exam = json.loads(epath.read_text(encoding="utf-8"))
        have = {a.get("book") for a in exam.get("casebookAnswers") or []}
        if BOOK in have:
            print(f"  {eid}: 이미 붙어 있다 — 건너뜀")
            continue

        added, chars = [], 0
        for v in sorted(items, key=lambda x: x.get("title") or ""):
            t = body(v.get("text") or "")
            if not t:
                continue
            added.append({
                "author": v.get("author") or "",
                "area": v.get("area") or "",
                "book": BOOK,
                "caseNo": "",
                "header": v.get("title") or (v.get("source") or {}).get("label", ""),
                "answerText": t,
            })
            chars += len(t)
            cut = len(v.get("text") or "") - len(t)
            print(f"  {eid}  {v.get('title'):12s} {len(t):>7,}자"
                  + (f"  (뒷부분 {cut:,}자 잘라냄)" if cut else ""))

        if not added:
            continue
        before = sum(len(a.get("answerText") or "") for a in exam.get("casebookAnswers") or [])
        exam.setdefault("casebookAnswers", []).extend(added)
        exam["casebookChars"] = before + chars
        print(f"  {eid}  → 채점 근거 {before:,}자 → {before + chars:,}자\n")

        if write:
            epath.write_text(json.dumps(exam, ensure_ascii=False, indent=1), encoding="utf-8")
            it = by_id.get(eid)
            if it is not None:
                it["hasCasebook"] = True
                it["casebookChars"] = exam["casebookChars"]

    if write:
        ipath.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print("→ 기록함")


if __name__ == "__main__":
    main()
