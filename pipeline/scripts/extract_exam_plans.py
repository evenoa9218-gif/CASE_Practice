"""원본 시험지(hwp)에서 문항 표제와 배점 순서를 뽑는다.

왜 hwp인가
  hwp5txt 는 표(table)를 `<표>` 로 치환해 버린다. 그런데 변시/모의 시험지는
  「제1문의 1」 같은 문항 표제를 하나같이 표 안에 넣는다. 그래서 기존 txt 추출본
  56개에서 표제가 0~1개밖에 안 나왔고, 문항 라벨이 `문1..문21` 같은 근거 없는
  일련번호로 남아 있었다.

  hwp5proc xml 은 표 셀 내용을 그대로 내보낸다. 여기서 문서 순서대로 글자를
  모으면 표제와 (N점)이 원래 순서로 살아난다.

검증
  제15회 변시를 이 방법으로 뽑은 결과가, 사람이 실제 시험지를 보고 손으로
  맞춰 넣었던 relabel_civil.py 의 MANUAL(순서 재배열 + 문항별 설문 개수)과
  완전히 일치했다. → 방법이 옳다는 근거.

출력
  pipeline/casebook/exam_plans.json  {examId: {"source": 파일명,
                                               "plan": [[라벨, [배점...]], ...]}}
  hwp 원본은 저장소 밖(개인 자료)이라, 결과만 저장소에 남겨 재빌드 가능하게 한다.
"""
import glob
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "pipeline" / "casebook" / "exam_plans.json"

SRC_DIRS = {
    "민사법": r"C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안\민사법\문제\사례형",
    "공법": r"C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안\공법\문제\사례형",
    "형사법": r"C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안\형사법\문제\사례형",
}

HWP5PROC = r"C:\Users\82109\AppData\Local\Programs\Python\Python312\Scripts\hwp5proc.exe"

# 문항 표제. 「제1문」·「제1문의 2」가 보통이지만 2013년 모의고사 두 회차는
# 「〈 제 1-2 문 〉」처럼 붙임표를 쓴다. 이걸 못 잡으면 본문 표제가 통째로 사라지고,
# 답안지 유의사항에 적힌 「제3문」이 기준으로 남아 뒤 표제가 전부 걸러진다.
HEAD = re.compile(r"제\s*(\d+)\s*(?:[-–—]\s*(\d+)\s*)?문(?:\s*의\s*(\d+))?")
# 배점 표기 네 가지를 다 받는다.
#   (25점)                          보통
#   (20점. 이자는 계산하지 말 것)      배점 뒤에 단서가 붙는 경우
#   (설문 가와 나를 합하여 20점)        여러 설문을 묶어 한 번에 매기는 경우
#   (① 10점 + ② 10점 + ③ 20점 = 40점)  소계를 합산해 적는 경우 → 합계만 취한다
# 괄호 안에서 닫는 자리에 붙은 숫자만 본다. 그래서 세 번째 예의 「③ 20점」처럼
# 뒤에 「=」가 이어지는 조각은 배점으로 세지 않는다.
PTS = re.compile(r"[(（][^()（）]{0,25}?(\d{1,3})\s*점(?=\s*[)）.,])"
                 r"|=\s*(\d{1,3})\s*점(?=\s*[)）])")


def exam_id(subject, path):
    """파일명 → 앱의 시험 id. 못 알아보면 None."""
    b = os.path.basename(path)
    m = re.search(r"제\s*(\d+)\s*회\s*변호사시험", b)
    if m:
        return f"{subject}_변시_{int(m.group(1))}회_사례"
    m = re.search(r"(\d{4})\s*년도\s*제\s*(\d)\s*차", b)
    if m:
        return f"{subject}_모의_{m.group(1)}_{m.group(2)}차_사례"
    return None


def hwp_text(path):
    """hwp → 문서 순서대로 이어붙인 글자열 (표 셀 포함)."""
    r = subprocess.run([HWP5PROC, "xml", path], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return ""
    try:
        root = ET.fromstring(r.stdout.decode("utf-8", "replace"))
    except ET.ParseError:
        return ""
    buf = []

    def walk(e):
        if e.tag.endswith("Text"):
            if e.text:
                buf.append(e.text)
        for c in e:
            walk(c)
        if e.tail and e.tail.strip():
            buf.append(e.tail)

    walk(root)
    return "\n".join(buf)


def plan_of(text):
    """문서 순서대로 [(문항라벨, [{"points":N, "text":설문원문}, ...])] 를 만든다.

    표지의 「제1문」처럼 배점이 뒤따르지 않는 표제는, 다음 표제가 나올 때
    라벨만 덮어써서 자연히 사라진다.

    설문 원문은 배점 표시 직전 300자. 앱의 요약된 `ask` 와 시험지 설문을
    짝지어 순서를 바로잡는 데 쓴다.
    """
    marks = []
    for m in HEAD.finditer(text):
        major, minor = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
        # 「제1-2문」도 「제1문의2」로 적어 회차끼리 표기를 맞춘다.
        label = f"제{major}문" + (f"의{minor}" if minor else "")
        marks.append((m.start(), "H", label, (major, minor)))
    for m in PTS.finditer(text):
        marks.append((m.start(), "P", int(m.group(1) or m.group(2)), m.start()))
    marks.sort(key=lambda x: x[0])

    plan, last_end, armed, seen = [], 0, False, (0, 0)
    for pos, kind, val, at in marks:
        if kind == "H":
            # 본문이 시작된 뒤로 표제는 오름차순이다. 되돌아가는 것은 회고적
            # 언급(「다만 제2문의2 문제 1에서 추가된…」)이나 반복 표기이니 버린다.
            # 첫 배점 전에는 따지지 않는다 — 답안지 유의사항이 「제3문」까지
            # 미리 들먹여서, 그걸 기준 삼으면 진짜 표제가 전부 걸러진다.
            if armed and at <= seen:
                continue
            seen = at
            if plan and not plan[-1][1]:
                plan[-1][0] = val          # 배점 없이 표제만 연달아 → 마지막 것만 유효
            else:
                plan.append([val, []])
            last_end = pos
        elif plan:
            snippet = re.sub(r"\s+", " ", text[max(last_end, at - 300):at]).strip()
            plan[-1][1].append({"points": val, "text": snippet})
            last_end, armed = at, True
    return [p for p in plan if p[1]]


def main():
    subjects = sys.argv[1:] or list(SRC_DIRS)
    index = {}
    for subj in subjects:
        d = SRC_DIRS.get(subj)
        if not d or not os.path.isdir(d):
            print(f"[건너뜀] {subj}: 원본 폴더 없음")
            continue
        files = sorted(glob.glob(os.path.join(d, "*.hwp")))
        for f in files:
            eid = exam_id(subj, f)
            if not eid:
                print(f"  [식별 실패] {os.path.basename(f)}")
                continue
            plan = plan_of(hwp_text(f))
            if not plan:
                continue
            prev = index.get(eid)
            # 같은 시험에 파일이 둘이면 문항을 더 많이 건진 쪽을 쓴다
            if prev and len(prev["plan"]) >= len(plan):
                continue
            index[eid] = {"source": os.path.basename(f), "plan": plan}
            tot = sum(q["points"] for _, qs in plan for q in qs)
            print(f"  {eid:28s} 문항 {len(plan):2d}  설문 "
                  f"{sum(len(qs) for _, qs in plan):2d}  총점 {tot}")

    # 표제가 「제1문」으로 시작하지 않으면 앞쪽 표제를 놓친 것이다. 답안지
    # 유의사항이 「제3문」까지 미리 들먹이기 때문에, 본문 표제를 못 잡으면
    # 그게 기준으로 남아 뒤 표제가 전부 걸러지고 한 문항으로 뭉친다.
    # 2013년 모의 두 회차가 실제로 그렇게 뭉쳐 있었다(「제 1-2 문」 표기).
    odd = [e for e, v in index.items() if not v["plan"][0][0].startswith("제1문")]
    if odd:
        print(f"\n[확인 필요] 제1문으로 시작하지 않는 시험 {len(odd)}건:")
        for e in odd:
            print(f"   {e}  {[l for l, _ in index[e]['plan']]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {OUT.relative_to(ROOT)}  시험 {len(index)}개")


if __name__ == "__main__":
    main()
