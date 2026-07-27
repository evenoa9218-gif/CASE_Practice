# -*- coding: utf-8 -*-
r"""파이프라인 스크립트가 공용으로 쓰는 경로 상수.

원래 이 스크립트들은 임시 스크래치패드의 절대경로를 하드코딩하고 있었다.
저장소로 옮기면서 전부 이 모듈의 상수를 참조하도록 바꿨다.

저장소 안에 있는 것(APP/SOURCE/CASEBOOK/REGISTRY)은 클론만 하면 바로 쓸 수 있다.
저장소 밖에 있는 것(RAW/PDF_ROOT/HWP5TXT/WORK)은 개인 로컬 자료라 커밋할 수 없으므로,
다른 PC에서 돌릴 땐 환경변수로 지정하거나 아래 기본값을 고쳐야 한다.

    set CASE_RAW=D:\변시자료\모의고사 기출문제, 모범답안
    set CASE_PDF_ROOT=D:\변시자료
    set CASE_WORK=D:\tmp\case_work
    set HWP5TXT=C:\Python312\Scripts\hwp5txt.exe
"""
import os
from pathlib import Path

# ── 저장소 안 (커밋되어 있음, 어디서 클론하든 동작) ──────────────
APP      = Path(__file__).resolve().parents[2]   # CASE_Practice 저장소 루트
PIPELINE = APP / "pipeline"
SOURCE   = PIPELINE / "source"      # 태깅 결과 {과목}_사례_final.json — 파이프라인의 정본 입력
CASEBOOK = PIPELINE / "casebook"    # 사례집 파싱 블록 + 공법 목차(toc_raw/toc_matched)
REGISTRY = PIPELINE / "registry"    # 쟁점 레지스트리 원본 issues_*.json

# ── 저장소 밖 (개인 로컬 자료 — 저작권 자료라 커밋 불가) ─────────
def _env(name, default):
    return Path(os.environ.get(name, default))

# 원본 hwp/pdf 기출자료 루트. 하위에 과목별 문제/채점기준표/사례집 폴더가 있다.
RAW = _env("CASE_RAW",
           r"C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\모의고사 기출문제, 모범답안")

# 변환 전 원본 PDF 루트 (RAW의 상위)
PDF_ROOT = _env("CASE_PDF_ROOT", r"C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf")

# 중간 산출물 작업 폴더. 재생성 가능하므로 커밋하지 않는다(.gitignore).
WORK = _env("CASE_WORK", str(PIPELINE / "work"))

# pyhwp의 hwp5txt 실행파일 (hwp → txt 추출 단계에서만 필요)
HWP5TXT = os.environ.get(
    "HWP5TXT",
    r"C:\Users\82109\AppData\Local\Programs\Python\Python312\Scripts\hwp5txt.exe")

# MCQ(선택형) 저장소 로컬 경로 — fix_mcq_paths.py 등 MCQ 보수 스크립트 전용
MCQ_REPO = _env("MCQ_REPO", r"C:\Users\82109\Desktop\2026\projects\MCQ")

for _d in (WORK,):
    _d.mkdir(parents=True, exist_ok=True)
