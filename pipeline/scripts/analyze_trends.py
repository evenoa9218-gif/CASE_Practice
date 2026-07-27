# -*- coding: utf-8 -*-
"""공법 사례형 출제경향 분석.

핵심 매핑: 모의고사 Y년(1·2·3차) → 다음해 1월 시행 변시 제(Y-2010)회
  예) 2024년 모의고사 → 2025년 1월 제14회 변시
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from paths import WORK   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

SCRATCH = WORK
MOCK = SCRATCH / "공법_사례_final.json"
REAL_SRC = SCRATCH / "공법_변시_사례_1to15.json"
REAL_TAGDIR = SCRATCH / "tag_output_real"
REAL_OUT = SCRATCH / "공법_변시_final.json"
REPORT = SCRATCH / "공법_경향분석.md"


def mock_year_to_hoi(year: int) -> int:
    """모의고사 연도 → 그 다음해 1월 시행 변시 회차."""
    return year - 2010


def hoi_to_mock_year(hoi: int) -> int:
    """변시 회차 → 그 전해 모의고사 연도."""
    return hoi + 2010


# ── 변시 태깅 결과 병합 ────────────────────────────────
def build_real():
    tags = {}
    for f in sorted(REAL_TAGDIR.glob("real_*.json")):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", f.read_text(encoding="utf-8").strip())
        for it in json.loads(raw):
            tags[it["id"]] = it
    src = json.load(open(REAL_SRC, encoding="utf-8"))
    out = []
    for rec in src:
        t = tags.get(rec["id"], {})
        out.append({
            "id": rec["id"], "hoi": rec["hoi"], "year": rec["year"], "label": rec["label"],
            "problemText": rec["problemText"],
            "majorField": t.get("majorField"),
            "subFields": t.get("subFields", []),
            "issueKeywords": t.get("issueKeywords", []),
            "factSummary": t.get("factSummary"),
            "questionStructure": t.get("questionStructure", []),
            "inferredCases": t.get("inferredCases", []),
        })
    out.sort(key=lambda r: r["hoi"])
    json.dump(out, open(REAL_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return out


def norm(kw: str) -> str:
    """키워드 표기 정규화 (비교 정확도용)."""
    k = kw.strip()
    k = re.sub(r"\s+", "", k)
    k = k.replace("·", "").replace("‧", "").replace("・", "")
    aliases = {
        "포괄위임입법금지원칙": "포괄위임금지원칙",
        "포괄위임입법금지": "포괄위임금지원칙",
        "포괄위임금지": "포괄위임금지원칙",
        "비례원칙": "과잉금지원칙",
        "과잉금지": "과잉금지원칙",
        "명확성": "명확성원칙",
        "신뢰보호": "신뢰보호원칙",
        "소의이익": "협의의소익",
        "권리보호이익": "협의의소익",
        "처분성인정여부": "처분성",
        "대상적격": "처분성",
    }
    return aliases.get(k, k)


def main():
    real = build_real()
    mock = json.load(open(MOCK, encoding="utf-8"))
    mock.sort(key=lambda r: (r["year"], r["round"]))

    lines = []
    A = lines.append

    A("# 공법 사례형 출제경향 분석")
    A("")
    A(f"- 모의고사 {len(mock)}건 (2013년 1차 ~ 2026년 1차)")
    A(f"- 실제 변호사시험 {len(real)}건 (제1회/2012년 ~ 제15회/2026년)")
    A("- **연결 규칙**: 모의고사 Y년(1·2·3차) → 다음해 1월 시행 **제(Y−2010)회 변시**")
    A("  - 예: 2024년 모의고사 1·2·3차 → 2025년 1월 제14회 변시")
    A("")

    # ── 1. 변시 단독 분석 ──────────────────────────────
    A("---")
    A("")
    A("## 1. 변호사시험 단독 분석 (제1~15회)")
    A("")

    A("### 1-1. 회차별 출제 쟁점")
    A("")
    A("| 회차 | 시행연도 | 분야 | 핵심 쟁점 |")
    A("|---|---|---|---|")
    for r in real:
        kws = ", ".join(r["issueKeywords"][:6]) if r["issueKeywords"] else "-"
        A(f"| 제{r['hoi']}회 | {r['year']} | {r['majorField'] or '-'} | {kws} |")
    A("")

    real_kw = Counter()
    kw_hoi = defaultdict(list)
    for r in real:
        for k in r["issueKeywords"]:
            nk = norm(k)
            real_kw[nk] += 1
            kw_hoi[nk].append(r["hoi"])

    A("### 1-2. 반복 출제 쟁점 (2회 이상)")
    A("")
    A("| 쟁점 | 출제횟수 | 출제 회차 | 최근 출제 후 경과 |")
    A("|---|---|---|---|")
    for k, v in real_kw.most_common():
        if v < 2:
            continue
        hois = sorted(kw_hoi[k])
        gap = 15 - max(hois)
        A(f"| {k} | {v}회 | {', '.join(f'제{h}회' for h in hois)} | {gap}회차 전 |")
    A("")

    A("### 1-3. 출제 주기 (반복 쟁점의 평균 간격)")
    A("")
    A("| 쟁점 | 출제 회차 | 평균 간격 | 다음 예상 |")
    A("|---|---|---|---|")
    cycle_rows = []
    for k, hois in kw_hoi.items():
        hs = sorted(set(hois))
        if len(hs) < 3:
            continue
        gaps = [hs[i + 1] - hs[i] for i in range(len(hs) - 1)]
        avg = sum(gaps) / len(gaps)
        nxt = max(hs) + avg
        cycle_rows.append((k, hs, avg, nxt))
    cycle_rows.sort(key=lambda x: x[3])
    for k, hs, avg, nxt in cycle_rows:
        A(f"| {k} | {', '.join(str(h) for h in hs)}회 | {avg:.1f}회차 | 제{nxt:.0f}회 전후 |")
    A("")

    A("### 1-4. 직전 회차 회피 경향 (연속 출제 여부)")
    A("")
    consec = 0
    total_pairs = 0
    for i in range(len(real) - 1):
        a = {norm(k) for k in real[i]["issueKeywords"]}
        b = {norm(k) for k in real[i + 1]["issueKeywords"]}
        if not a or not b:
            continue
        total_pairs += 1
        overlap = a & b
        if overlap:
            consec += 1
        A(f"- 제{real[i]['hoi']}회 → 제{real[i+1]['hoi']}회: 중복 {len(overlap)}개"
          + (f" ({', '.join(sorted(overlap))})" if overlap else " — 완전 회피"))
    A("")
    if total_pairs:
        A(f"**연속 회차 간 쟁점 중복률: {consec}/{total_pairs} ({consec/total_pairs*100:.0f}%)**")
    A("")

    # ── 2. 모의고사 → 변시 반영 ────────────────────────
    A("---")
    A("")
    A("## 2. 모의고사 → 다음해 변시 반영 분석")
    A("")
    A("모의고사 Y년 1·2·3차에 나온 쟁점이, 다음해 1월 제(Y−2010)회 변시에 실제로 나왔는지 검증")
    A("")

    mock_by_year = defaultdict(list)
    for m in mock:
        mock_by_year[m["year"]].append(m)
    real_by_hoi = {r["hoi"]: r for r in real}

    A("| 모의고사 연도 | → 변시 | 모의 쟁점수 | 변시 쟁점수 | 적중 | 적중률 | 적중 쟁점 |")
    A("|---|---|---|---|---|---|---|")
    hit_rows = []
    for year in sorted(mock_by_year):
        hoi = mock_year_to_hoi(year)
        r = real_by_hoi.get(hoi)
        if not r or not r["issueKeywords"]:
            continue
        mkws = set()
        for m in mock_by_year[year]:
            mkws |= {norm(k) for k in m["issueKeywords"]}
        rkws = {norm(k) for k in r["issueKeywords"]}
        hits = mkws & rkws
        rate = len(hits) / len(rkws) * 100 if rkws else 0
        hit_rows.append((year, hoi, len(mkws), len(rkws), len(hits), rate, hits))
        A(f"| {year}년 | 제{hoi}회({r['year']}) | {len(mkws)} | {len(rkws)} | {len(hits)} | "
          f"{rate:.0f}% | {', '.join(sorted(hits)) if hits else '-'} |")
    A("")
    if hit_rows:
        avg_rate = sum(h[5] for h in hit_rows) / len(hit_rows)
        A(f"**평균 적중률: {avg_rate:.1f}%** (변시 쟁점 중 직전해 모의고사에서 다뤄진 비율)")
    A("")

    # ── 3. 미출제 / 예상 쟁점 ──────────────────────────
    A("---")
    A("")
    A("## 3. 미출제 쟁점 & 예상 쟁점")
    A("")

    mock_kw = Counter()
    mock_kw_where = defaultdict(list)
    for m in mock:
        for k in m["issueKeywords"]:
            nk = norm(k)
            mock_kw[nk] += 1
            mock_kw_where[nk].append(f"{m['year']}-{m['round']}차")

    never_real = [(k, v) for k, v in mock_kw.most_common() if k not in real_kw]
    A(f"### 3-1. 모의고사에는 자주 나왔으나 변시 미출제 (상위 25종 / 총 {len(never_real)}종)")
    A("")
    A("| 쟁점 | 모의 출제횟수 | 출제된 모의고사 |")
    A("|---|---|---|")
    for k, v in never_real[:25]:
        A(f"| {k} | {v}회 | {', '.join(mock_kw_where[k][:5])} |")
    A("")

    A("### 3-2. 최근 변시 공백 쟁점 (과거 출제됐으나 최근 5회 미출제)")
    A("")
    recent = set()
    for r in real:
        if r["hoi"] >= 11:
            recent |= {norm(k) for k in r["issueKeywords"]}
    A("| 쟁점 | 과거 출제 회차 | 공백 |")
    A("|---|---|---|")
    for k, hois in sorted(kw_hoi.items(), key=lambda x: -len(x[1])):
        if k in recent:
            continue
        hs = sorted(hois)
        A(f"| {k} | {', '.join(f'제{h}회' for h in hs)} | 제{max(hs)}회 이후 {15-max(hs)}회차 |")
    A("")

    A("### 3-3. 직전해(2025년) 모의고사 쟁점 → 제15회 검증 및 제16회 참고")
    A("")
    latest_mock_year = 2025
    lm = mock_by_year.get(latest_mock_year, [])
    if lm:
        lm_kw = Counter()
        for m in lm:
            for k in m["issueKeywords"]:
                lm_kw[norm(k)] += 1
        r15 = real_by_hoi.get(15)
        r15_kw = {norm(k) for k in (r15["issueKeywords"] if r15 else [])}
        A(f"2025년 모의고사(1·2·3차) 쟁점 {len(lm_kw)}종 중 제15회 변시 출제 여부:")
        A("")
        A("| 쟁점 | 모의 빈도 | 제15회 출제 |")
        A("|---|---|---|")
        for k, v in lm_kw.most_common(20):
            A(f"| {k} | {v} | {'O' if k in r15_kw else '-'} |")
        A("")

    A("### 3-4. 2026년 1차 모의고사 쟁점 (제16회 변시 대비)")
    A("")
    m26 = mock_by_year.get(2026, [])
    if m26:
        for m in m26:
            A(f"**{m['label']}**")
            A("")
            A(f"- 사실관계: {m['factSummary']}")
            A(f"- 쟁점: {', '.join(m['issueKeywords'])}")
            past = [k for k in m["issueKeywords"] if norm(k) in real_kw]
            fresh = [k for k in m["issueKeywords"] if norm(k) not in real_kw]
            A(f"- 변시 기출 쟁점: {', '.join(past) if past else '없음'}")
            A(f"- 변시 미출제 쟁점: {', '.join(fresh) if fresh else '없음'}")
            A("")

    # ── 4. 누적 쟁점 정리 ──────────────────────────────
    A("---")
    A("")
    A("## 4. 누적 쟁점 총정리")
    A("")
    all_kw = Counter()
    for r in real:
        for k in r["issueKeywords"]:
            all_kw[norm(k)] += 1
    for m in mock:
        for k in m["issueKeywords"]:
            all_kw[norm(k)] += 1
    A(f"전체 고유 쟁점 {len(all_kw)}종 (변시 {len(real_kw)}종, 모의 {len(mock_kw)}종)")
    A("")
    A("| 쟁점 | 변시 | 모의 | 합계 |")
    A("|---|---|---|---|")
    for k, v in all_kw.most_common(50):
        A(f"| {k} | {real_kw.get(k,0)} | {mock_kw.get(k,0)} | {v} |")
    A("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"분석 완료 -> {REPORT}")
    print(f"변시 데이터 -> {REAL_OUT}")
    print(f"\n변시 {len(real)}건, 모의 {len(mock)}건")
    tagged = sum(1 for r in real if r["issueKeywords"])
    print(f"변시 태깅 완료: {tagged}/{len(real)}")


if __name__ == "__main__":
    main()
