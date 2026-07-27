# -*- coding: utf-8 -*-
"""민사법 사례집(정연석, 로스쿨 민사 사례형 기출문제집 해설편) 파싱.

구조: 책 페이지머리(Part N + 회차 목록, 노이즈) → 회차 헤더(단독 줄, 예:
"2026년제15히 변시" / "2025년06모") → 그 회차의 "제N문(의M)" 사례 블록들
반복 → 다음 회차 헤더... 회차 안에서 사례 라벨이 페이지머리처럼 한 번 더
겹쳐 나오기도 하지만(예: "제1문의 1제1문의 1 ..."), 줄 맨 앞만 파싱하면
문제없다.

모의고사는 "{연도}년 {MM}모"로 월 표기(06/08/10월) — 법전협 모의고사가
매년 6월/8월/10월 3회 시행되는 관례에 따라 06→1차, 08→2차, 10→3차로
매핑한다(문서 서두에서 "2025년 시행 법전협 모의시험 3회분" 등 확인).
"""
import json, re
from pathlib import Path
from paths import CASEBOOK, RAW   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

FILE = RAW / "사례집" / "민법" / "2026_06_정연석_로스쿨_민사_사례형_기출문제집_해설편.txt"
OUT = CASEBOOK / "civil_casebook_blocks.json"

BOOK_NOISE_RE = re.compile(r"^로스쿨\s*민사\s*사례형\s*기출문제집.*Part.*$")
# 뒤에 페이지번호가 붙기도 하고("2022년 06모 319"), "요약"만 있고 본문이 없는
# 축약판 구간도 있어(예: "2013년 제2회 변시 요약  903") 후자는 제외한다.
BAR_HEADER_RE = re.compile(r"^(\d{4})년\s*제?(\d{1,2})\s*[회히]\s*변시\s*(?:\d{1,4})?\s*$")
MOCK_HEADER_RE = re.compile(r"^(\d{4})년\s*(\d{2})\s*모\s*(?:\d{1,4})?\s*$")
CASE_LABEL_RE = re.compile(r"^제\s*(\d+)\s*문(?:\s*의\s*(\d+))?")

MONTH_TO_ROUND = {"06": 1, "08": 2, "10": 3}


def main():
    text = FILE.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # 1) 페이지머리 노이즈 제거
    lines = [l for l in lines if not BOOK_NOISE_RE.match(l.strip())]

    # 2) 회차 헤더 위치 찾기 (본문 시작 지점부터만; TOC/회차별분석표 구간은 건너뜀)
    #    본문은 첫 "Part" 페이지머리 이후부터이므로, 원본에서 첫 BAR_HEADER 매치부터 사용
    round_positions = []
    for i, l in enumerate(lines):
        s = l.strip()
        m = BAR_HEADER_RE.match(s)
        if m:
            round_positions.append((i, "변시", int(m.group(2)), None))
            continue
        m = MOCK_HEADER_RE.match(s)
        if m:
            year, mm = int(m.group(1)), m.group(2)
            if mm in MONTH_TO_ROUND:
                round_positions.append((i, "모의고사", year, MONTH_TO_ROUND[mm]))

    print(f"회차 헤더 {len(round_positions)}개 발견")

    # 3) 각 회차 구간의 텍스트에서 "제N문(의M)" 라벨로 사례 블록 분리
    all_blocks = []
    for idx, (line_i, kind, a, b) in enumerate(round_positions):
        start = line_i + 1
        end = round_positions[idx + 1][0] if idx + 1 < len(round_positions) else len(lines)
        section_lines = lines[start:end]

        if kind == "변시":
            exam_id = f"민사법_변시_{a}회_사례"
        else:
            exam_id = f"민사법_모의_{a}_{b}차_사례"

        # 라벨 위치 찾기
        label_positions = []
        for j, l in enumerate(section_lines):
            m = CASE_LABEL_RE.match(l.strip())
            if m:
                label_positions.append((j, int(m.group(1)), int(m.group(2)) if m.group(2) else None))

        for k, (j, qno, subno) in enumerate(label_positions):
            j_end = label_positions[k + 1][0] if k + 1 < len(label_positions) else len(section_lines)
            body = "\n".join(section_lines[j:j_end]).strip()
            label = f"제{qno}문" + (f"의{subno}" if subno else "")
            all_blocks.append({
                "examId": exam_id,
                "label": label,
                "qno": qno,
                "subno": subno,
                "answerText": body,
                "chars": len(body),
            })

    json.dump(all_blocks, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"사례 블록 {len(all_blocks)}개 저장 → {OUT}")

    # 회차별 커버리지 요약
    from collections import defaultdict
    by_exam = defaultdict(list)
    for b in all_blocks:
        by_exam[b["examId"]].append(b)
    real = sorted([k for k in by_exam if "변시" in k], key=lambda k: int(re.search(r"(\d+)회", k).group(1)))
    mock = sorted([k for k in by_exam if "모의" in k])
    print(f"\n=== 변시 커버리지 ({len(real)}개 회차) ===")
    for k in real:
        print(f"  {k}: 블록 {len(by_exam[k])}개, {sum(x['chars'] for x in by_exam[k]):,}자")
    print(f"\n=== 모의고사 커버리지 ({len(mock)}개 회차) ===")
    for k in mock:
        print(f"  {k}: 블록 {len(by_exam[k])}개, {sum(x['chars'] for x in by_exam[k]):,}자")


if __name__ == "__main__":
    main()
