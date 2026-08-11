"""사례집 모범답안에서 뒤바뀐 당사자 기호를 되돌린다.

무엇이 문제인가
  사례집은 PDF OCR을 거치는데 `乙`·`丙`·`戊`가 자주 다른 한자로 읽힌다.
  `乙`→`江`·`己`·`心`·`石`, `丙`→`內`·`因`·`西`·`雨`, `戊`→`成`.
  형사법 변시 15회 해설이 가장 심해서 `乙`과 `丙`이 **한 번도 안 나오고**
  대신 `己 16 · 因 21 · 內 65 · 江 36 · 成 60`이 들어차 있었다. 이 회차 해설은
  나중에 따로 넣은 파일이라 기존 교정 파이프라인을 안 거쳤다.

  사례형은 "누구의 죄책인가"를 묻는 시험이다. 당사자가 뒤바뀐 답안을 채점
  근거로 주면 채점이 통째로 무의미해진다.

무엇을 근거로 고치는가
  **같은 시험의 문제 지문.** 지문은 hwp에서 바로 뽑은 것이라 깨지지 않았다.
  지문에 그 기호가 한 번도 안 나오고 대신 제자리 기호가 나온다면, 해설 쪽
  기호는 오인식이다. 실제로 형사법 15회 시험지에는 甲42·乙9·丙20·丁24·戊13이
  나오고 `己`를 비롯한 의심 기호는 하나도 없다.

무엇을 건드리지 않는가
  - **창작문제(로사정·박승수).** 이미 전용 파이프라인에서 지면과 1:1 대조해
    교정했다. 박승수 사례 281처럼 **진짜 `己`가 당사자인 사례**도 있어서,
    한 번 더 훑으면 맞는 것을 틀리게 만든다.
  - **한자어 속 글자.** `自己`·`構成`·`成立`·`原因`·`內容`·`良心`의 그 글자들이다.
    앞뒤가 한자면 손대지 않고, 뒤에 한글 조사나 구두점이 올 때만 당사자로 본다.

사용
  python pipeline/scripts/fix_casebook_party.py [과목...] [--write]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# OCR이 흘려 놓은 글자 → 제자리 당사자 기호. 로사정 작업에서 지면과 1:1로
# 대조해 확인한 매핑이다.
HANJA = {"江": "乙", "心": "乙", "石": "乙", "己": "乙",
         "內": "丙", "因": "丙", "西": "丙", "雨": "丙",
         "成": "戊"}
# 로마자로 흘러버린 것. `ZL`은 `乙`을 세로로 쪼개 읽은 것이다.
LATIN = {"ZL": "乙", "Z": "乙", "z": "乙", "T": "丁"}
MAP = {**HANJA, **LATIN}

# 숫자 `6`도 `乙`로 자주 읽히지만 일부러 두었다. 뒤에 조사 `도`가 오는 자리를
# 허용하면 판례번호 `2006도2556`이 통째로 걸린다. 얻는 것보다 잃는 것이 크다.

# 당사자로 쓰인 자리만 고른다. 뒤에 한글 조사나 구두점이 와야 한다
# (成立·內容·因果 배제). 앞은 한자면 제외 — 自己·構成·原因·良心이 그렇다.
JOSA = r"[의은는이가을를에과와도만]"
def rx(ch):
    before = r"(?<![A-Za-z])" if ch in LATIN else r"(?<![一-鿿])"
    return re.compile(before + ch + r"(?=" + JOSA + r"|[,、·)\]\s])")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    subjects = args or ["공법", "형사법", "민사법"]
    write = "--write" in sys.argv

    for subject in subjects:
        ipath = ROOT / "data" / subject / "index.json"
        index = json.loads(ipath.read_text(encoding="utf-8"))
        total, touched = Counter(), []

        for it in index["exams"]:
            # 창작문제는 이미 전용 교정을 거쳤다 — 다시 훑지 않는다.
            if it["id"].split("_")[1] not in ("변시", "모의"):
                continue
            epath = ROOT / "data" / subject / "exams" / f"{it['id']}.json"
            exam = json.loads(epath.read_text(encoding="utf-8"))
            answers = exam.get("casebookAnswers") or []
            if not answers:
                continue
            problem = exam.get("problemText") or ""

            # 지문에 없는 기호만, 그리고 제자리 기호가 지문에 실제로 있을 때만 고친다.
            live = {bad: good for bad, good in MAP.items()
                    if problem.count(bad) == 0 and problem.count(good) > 0}
            if not live:
                continue

            hits = Counter()
            for a in answers:
                t = a.get("answerText") or ""
                for bad, good in live.items():
                    t, n = rx(bad).subn(good, t)
                    hits[f"{bad}→{good}"] += n
                a["answerText"] = t
            if not sum(hits.values()):
                continue
            touched.append((it["id"], sum(hits.values()), dict(hits)))
            total.update(hits)
            if write:
                epath.write_text(json.dumps(exam, ensure_ascii=False, indent=1),
                                 encoding="utf-8")

        touched.sort(key=lambda r: -r[1])
        print(f"\n■ {subject} — {len(touched)}개 시험 {sum(total.values())}자 교정 "
              f"{dict(total)}")
        for eid, n, h in touched[:10]:
            print(f"   {eid:26s} {n:4d}자 {h}")
        if len(touched) > 10:
            print(f"   … 외 {len(touched) - 10}건")
        if write and touched:
            print("   → 기록함")


if __name__ == "__main__":
    main()
