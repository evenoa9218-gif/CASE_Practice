"""문제 지문에서 통째로 빠진 앞머리(공통 기초사실)를 원본 시험지에서 되살린다.

무엇이 문제였나
  민사법 2013년 3차 지문은 곧바로 「1. 전소에서 甲 등이 …」로 시작한다. 그런데
  그 「전소」가 무엇인지 설명하는 <공통된 기초사실>이 없다. 전소의 매매 시점도,
  당사자 관계도 모른 채 일곱 문항을 풀어야 했던 것이다.

  원인은 늘 같다 — 이 시험은 기초사실을 **표(table) 안**에 넣었고, `hwp5txt`는
  표를 `<표>`로 치환하며, 정제 단계가 그 자리표시자를 지운다. 그래서 내용이
  흔적도 없이 사라졌다. (문항 표제가 사라졌던 것과 정확히 같은 사고다.)

범위
  165개 기출을 원본과 견줘 보니(공백을 뺀 글자 수 기준) 앞머리가 통째로 빠진
  것은 **이 한 건뿐**이다. 80% 아래로 나온 나머지 세 건(민사법 2014년 2·3차,
  공법 2016년 1차)은 사실관계가 이미 들어 있고, 차이는 시험지 머리와 참조조문
  표에서 온다. 그래서 대상을 목록으로 못박았다 — 자동 판정에 맡기면 멀쩡한
  지문에 엉뚱한 앞머리가 붙을 수 있다.

앞머리만 붙이는 이유
  지문 전체를 `hwp5proc xml` 추출본으로 갈아치우면 표 내용은 살아나지만
  「매수 인들은」처럼 원본의 자동 줄바꿈이 그대로 굳는다. 기존 지문은
  `hwp5txt` 로 문단 단위로 잘 뽑혀 있으므로, 빠진 앞머리만 가져다 붙인다.

사용
  python pipeline/scripts/restore_problem_head.py [--write]
"""
import json
import re
import sys
from pathlib import Path

from clean_text import clean_hwp
from extract_exam_plans import hwp_text

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(r"C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안")

# (시험 id, 과목, 원본 hwp 경로, 앞머리가 시작하는 자리, 끝나는 자리)
# 시작·끝을 글자로 못박는다. 앞쪽에는 시험지 제목과 답안지 유의사항 꼬리가
# 붙어 있어서, 어림으로 자르면 그것들이 지문 앞머리로 들어온다.
TARGETS = [(
    "민사법_모의_2013_3차_사례", "민사법",
    "민사법/문제/사례형/2. 2013년도 제3차 변호사시험 모의시험 민사법 사례형 문제 [13-3].hwp",
    "<공통된 기초사실>", "(아래 각 문항의 기재사실은",
)]

NOTICE_END = re.compile(r"가지고\s*갈\s*수\s*있습니다")
# xml 추출본은 서식이 바뀔 때마다 줄을 끊는다. 문장이 안 끝났으면 이어 붙이되
# 낱말이 붙어 버리지 않게 사이를 띄운다.
CONTINUES = re.compile(r"[.?!:》〉」\]]\s*$")
STARTS_NEW = re.compile(r"^[〈<\[【(]|^\d+\s*[.)]|^[가-하]\s*\.")


def head_of(path, since, until):
    text = hwp_text(str(path))
    m = list(NOTICE_END.finditer(text))
    body = text[m[-1].end():] if m else text
    start, cut = body.find(since), body.find(until)
    if start < 0 or cut <= start:
        return ""
    lines, out = [l.strip() for l in body[start:cut].split("\n")], []
    for line in lines:
        if not line:
            continue
        if out and not CONTINUES.search(out[-1]) and not STARTS_NEW.match(line):
            out[-1] += " " + line
        else:
            out.append(line)
    return clean_hwp("\n".join(out))


def main():
    write = "--write" in sys.argv
    for eid, subject, rel, since, until in TARGETS:
        src = RAW / rel
        if not src.exists():
            print(f"  [건너뜀] 원본 없음: {rel}")
            continue
        epath = ROOT / "data" / subject / "exams" / f"{eid}.json"
        exam = json.loads(epath.read_text(encoding="utf-8"))
        problem = exam["problemText"]

        head = head_of(src, since, until)
        if not head:
            print(f"  [건너뜀] 앞머리를 못 찾음: {eid}")
            continue
        anchor = re.sub(r"\s", "", head)[-25:]
        if anchor and anchor in re.sub(r"\s", "", problem):
            print(f"  {eid}: 이미 들어 있다 — 건너뜀")
            continue

        # 첫 줄(시험 이름)은 기존 지문에 이미 있으니 그 다음부터 끼워 넣는다.
        lines = problem.split("\n")
        exam["problemText"] = "\n".join([lines[0], "", head, ""] + lines[1:]).strip()
        print(f"  {eid}: 앞머리 {len(head):,}자 복원 "
              f"({len(problem):,} → {len(exam['problemText']):,}자)")
        print(f"     {head[:120]}…")
        if write:
            epath.write_text(json.dumps(exam, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            print("     → 기록함")


if __name__ == "__main__":
    main()
