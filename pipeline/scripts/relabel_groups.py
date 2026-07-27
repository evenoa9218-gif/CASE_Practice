# -*- coding: utf-8 -*-
"""문항 그룹 라벨을 실제 변호사시험 표기(제1문/제1문의1 등)로 재부여.
   근거: 사례형은 배점이 문항(제N문)당 정확히 100점이고, 한 문 안에 사례가
   여럿이면 '의1,의2,...'로 나뉜다(예: 15회 공법 제1문의1~3=각35/35/30=100,
   제2문=100). 그룹 배점을 순서대로 누적하다 100점(이상)에서 문항을 닫는다.

   주의: 민사법은 배점 총합이 350점이라 이 규칙이 검증되지 않았다(근사치).

   사용법: python -X utf8 relabel_groups.py [과목 ...]   (기본값: 공법 형사법 민사법)"""
import json
import sys
from pathlib import Path
from paths import APP   # 저장소 기준 상대경로 (pipeline/scripts/paths.py)

def relabel(groups):
    clusters, cur, cum = [], [], 0
    for g in groups:
        cur.append(g)
        cum += g.get("points") or 0
        if cum >= 100:
            clusters.append(cur)
            cur, cum = [], 0
    if cur:
        clusters.append(cur)
    labels = []
    for i, cluster in enumerate(clusters, start=1):
        if len(cluster) == 1:
            labels.append(f"제{i}문")
        else:
            for j in range(len(cluster)):
                labels.append(f"제{i}문의{j+1}")
    return labels

def process_subject(subj):
    data_dir = APP / "data" / subj
    idx_path = data_dir / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    changed = 0
    mismatches = []

    for e in idx["exams"]:
        labels = relabel(e["groups"])
        if len(labels) != len(e["groups"]):
            mismatches.append(e["id"])
            continue
        for g, lab in zip(e["groups"], labels):
            g["key"] = lab
            g["label"] = lab
        changed += 1

        # exams/*.json 도 동일하게 갱신
        ep = data_dir / "exams" / f"{e['id']}.json"
        detail = json.loads(ep.read_text(encoding="utf-8"))
        dlabels = relabel(detail["groups"])
        if len(dlabels) == len(detail["groups"]):
            for g, lab in zip(detail["groups"], dlabels):
                g["key"] = lab
                g["label"] = lab
        ep.write_text(json.dumps(detail, ensure_ascii=False), encoding="utf-8")

    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{subj}: {changed}/{len(idx['exams'])}건 재라벨링, 불일치 {len(mismatches)}건 {mismatches}")

for subj in (sys.argv[1:] or ["공법", "형사법", "민사법"]):
    process_subject(subj)
