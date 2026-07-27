# 데이터 파이프라인

원본 hwp/pdf 기출자료 → 텍스트 추출 → 쟁점 태깅 → 사례집 결합 → 정제 → 쟁점 레지스트리 → 앱 데이터(`../data/`).

원래 이 스크립트들은 Claude 세션의 임시 폴더(`AppData\Local\Temp\...\scratchpad`)에만 있어서
세션이 끝나면 사라질 위험이 있었다. 2026-07-27에 전부 저장소로 옮기고, 하드코딩된 절대경로를
[`scripts/paths.py`](scripts/paths.py) 상수 참조로 바꿨다.

---

## 폴더 구성

| 경로 | 내용 | 커밋됨 |
|---|---|:-:|
| `scripts/` | 파이프라인 스크립트 57개 + `paths.py` | ○ |
| `source/` | **태깅 결과 = 파이프라인의 정본 입력.** `{과목}_사례_final.json` 5과목 + `공법_변시_final.json` | ○ |
| `casebook/` | 사례집 파싱 블록 3종 + 공법 목차(`toc_raw`/`toc_matched`) | ○ |
| `registry/` | 쟁점 레지스트리 스냅샷 `issues_*.json`, `exam_issues_*.json` | ○ |
| `work/` | 중간 산출물(`final/`, `registry/`). 재생성 가능하므로 커밋 안 함 | ✕ |

`source/`와 `casebook/`만 있으면 `../data/` 전체를 처음부터 다시 만들 수 있다.
**2026-07-27 기준 공법·형사법·민사법 3과목 모두 재생성 결과가 커밋된 데이터와 바이트 단위로 동일함을 확인했다.**

---

## 재생성 방법

```bash
cd pipeline/scripts

# 공법
python -X utf8 merge_casebook_공법.py        # source + casebook → work/final/공법_사례_full.json
python -X utf8 apply_clean.py                # → work/final/공법_사례_full_clean.json
python -X utf8 build_issue_registry.py       # → work/registry/issues_공법.json  (PUB)
python -X utf8 build_case_app_data.py        # → ../../data/공법/

# 형사법
python -X utf8 merge_casebook_형사법.py
python -X utf8 clean_apply_형사법.py
python -X utf8 build_issue_registry_형사법.py   # CRI
python -X utf8 build_case_app_data_형사법.py

# 민사법
python -X utf8 merge_casebook_민사법.py
python -X utf8 clean_apply_민사법.py
python -X utf8 build_issue_registry_민사법.py   # CIV
python -X utf8 build_case_app_data_민사법.py

# 문항 라벨을 실제 시험 표기(제1문/제1문의1)로 재부여 — 앱 데이터 생성 뒤 반드시 실행
python -X utf8 relabel_groups.py             # 인자 없으면 공법·형사법·민사법 전부
```

`-X utf8`은 필수다. 윈도우 콘솔 기본 인코딩(cp949)으로는 한글 파일명·출력이 깨진다.

`build_case_app_data_*.py`는 `../data/{과목}/`을 **덮어쓴다.** 실행 후 `git diff`로 의도한 변경만
들어갔는지 확인할 것. 아무 변경이 없으면 재생성이 정확히 재현된 것이다.

### 새 과목 추가할 때

`형사법` 접미사가 붙은 4개 스크립트를 복사해 과목명·접두사(`INT`/`ITL` 등)·사례집 파싱 규칙만
바꾸면 된다. 사례집은 책마다 마커 형식이 달라서 `split_casebook_*.py`는 매번 새로 써야 한다
(→ [책별 마커 형식](#책별-사례집-마커-형식)).

---

## 단계별 스크립트

### 0. 원본 추출 (로컬 hwp/pdf 필요 — `CASE_RAW` 환경변수)
| 스크립트 | 역할 |
|---|---|
| `extract_zips.py`, `rebuild_zip.py` | zip 자료 해제/재압축 (`zip` CLI가 없어 파이썬 `zipfile` 사용) |
| `extract_text.py`, `extract_text_all.py` | hwp → txt (`pyhwp`의 `hwp5txt`. 한글 COM 자동화는 쓰지 않음) |
| `probe_casebooks.py`, `test_pdf_extract.py` | 사례집 PDF에 텍스트층이 있는지 사전 판별 |
| `pdf2txt.py` | 텍스트층 있는 PDF → txt |
| `organize_txt.py`, `split_type.py`, `redistribute_giwok.py` | 과목/시험유형별 폴더 재배치 |
| `check_dupes.py`, `diff_dupes.py` | 중복 파일 해시 비교 / 내용 차이 확인 |

### 1. 인덱싱·태깅 입력
| 스크립트 | 역할 |
|---|---|
| `index_case_problems.py` | 문제 txt ↔ 채점기준표 txt 짝 맞추기 |
| `prep_tagging_input.py`, `prep_all_tag_inputs.py`, `prep_real_exam.py` | LLM 쟁점 태깅용 경량 입력 파일 생성 |
| `extract_citations.py` | 판례 사건번호·법조문 정규식 추출 (LLM 없이 결정론적) |

### 2. 태깅 결과 병합 → `source/`
| 스크립트 | 역할 |
|---|---|
| `classify.py`, `classify_batch2.py` | 태깅 배치 실행 |
| `merge_tags.py`, `merge_all_subjects.py`, `build_all_subjects.py` | 태깅 결과 + 정규식 추출 + 원문 병합, 무결성 검증 |
| `build_mock_exam_data.py`, `build_real_exam_data.py` | 모의고사/변시 분리 구축 |

### 3. 사례집 결합
| 스크립트 | 역할 |
|---|---|
| `probe_casebook_markers.py`, `probe_criminal_markers.py`, `probe_block_structure.py` | 책마다 다른 사례 구분 마커 형식 조사 |
| `split_casebook.py` / `_criminal.py` / `_civil.py` | 사례집을 사례 블록으로 분할 + 출처 시험에 매핑 → `casebook/*.json` |
| `merge_casebook_{공법,형사법,민사법}.py` | 태깅 데이터에 사례집 모범답안 결합 |

### 4. 정제
| 스크립트 | 역할 |
|---|---|
| `clean_text.py` | **정제기 본체.** `clean_hwp()`(표/그림 placeholder 제거, 빈 줄 축약), `clean_pdf()`(문장 중간 줄바꿈 병합, 페이지 머리글 제거, 조문 표기 정규화, OCR 교정) |
| `apply_clean.py`, `clean_apply_형사법.py`, `clean_apply_민사법.py` | 과목별 적용 + 책별 반복 머리글 제거 규칙 |
| `diagnose_text.py` | 정제 전후 품질 진단 |

> **의도적으로 하지 않는 정제 하나** — 조사(은/는/이/가) 앞 공백 병합은 넣었다가 뺐다.
> "있는 이 사건"의 "이"가 관형사인 경우와 기계적으로 구분이 불가능해서 원문이 훼손된다.

### 5. 쟁점 레지스트리
`build_issue_registry{,_형사법,_민사법}.py` → `work/registry/issues_{과목}.json`

과목 접두사(`PUB`/`CRI`/`CIV`, 예정 `INT`/`ITL`) + 4자리 번호의 **불변 ID**.
기본서 개정으로 목차가 바뀌어도 ID가 무효화되지 않도록 목차 위치를 ID에 넣지 않았다.
표기 흔들림은 `aliases`로 통합하고, 계층은 별도 `path` 필드에 둔다.

### 6. 앱 데이터
`build_case_app_data{,_형사법,_민사법}.py` → `../data/{과목}/index.json` + `exams/*.json` + `../data/issues_{과목}.json`
→ 이어서 `relabel_groups.py`로 문항 라벨 재부여.

### 7. 공법 전용 — 사례집 목차 브라우저
`parse_toc.py` → `match_toc.py` → `build_data_file.py` → `../data/공법/casebook_toc.json`

강성민 헌법·행정법 책의 "편 > 사례" 목차 284건을 파싱해 시험/문항에 94% 매칭.
형사법·민사법은 사례집 구조가 달라 이 모드가 없다(아래 참고).

### 그 밖에
`analyze_trends.py`(출제경향 분석 → [`../docs/경향분석_공법.md`](../docs/경향분석_공법.md)),
`gap_analysis.py`(자료 공백 점검),
`fix_mcq_paths.py`·`remove_bg_video.py`(MCQ 저장소 보수용, 이 앱과 무관),
`build_webapp_data.py`(구버전 웹앱 데이터 생성기, 현재 미사용).

---

## 책별 사례집 마커 형식

사례집은 출판사·저자마다 사례 구분 방식이 전혀 다르고 OCR 오인식도 섞여 있어,
공용 파서를 만들지 못하고 책마다 정규식을 새로 썼다.

| 과목 | 책 | 마커 형식 | 결과 |
|---|---|---|---|
| 공법 | 강성민 헌법 사례형 연습 / 행정법 사례형 연습 | `사례N.` 또는 `사례N` (주제별 편 구성) | 목차 284건, 94% 매칭 |
| 형사법 | 조균석 형사법 사례형 해설 | `사례N. [YY-변시(회)-Q]` (시험 회차순) | 변시 6~15회 10건 |
| 민사법 | 정연석 로스쿨 민사 사례형 기출문제집[해설편] | 책 자체가 `제N문의M` 표기 사용, 회차 머리글 `2026년제15회 변시` / `2025년06모` | 변시 8건 + 모의 25건 |

**자주 만난 OCR 오인식**: 회↔히, 모↔S, 제↔ス, 숫자 누락/중복, 페이지 번호가 머리글에 섞여 들어옴.
민사법 모의고사 머리글의 월 표기(`06`/`08`/`10모`)는 법전협 모의고사가 매년 6·8·10월 시행되는
관례에 따라 각각 1·2·3차로 매핑했다 — **실제 PDF로 검증하지는 못했다.**

---

## 저장소 밖 자료

원본 hwp/pdf와 사례집 txt는 **저작권 자료라 커밋하지 않는다.**
0~1단계 스크립트를 돌리려면 로컬에 원본이 있어야 하고, 경로를 환경변수로 지정해야 한다.

```bash
set CASE_RAW=D:\변시자료\모의고사 기출문제, 모범답안
set CASE_PDF_ROOT=D:\변시자료
set CASE_WORK=D:\tmp\case_work          # 기본값: pipeline/work
set HWP5TXT=C:\Python312\Scripts\hwp5txt.exe
```

2단계 이후(`source/`부터 앱 데이터까지)는 원본 없이 저장소만으로 돌아간다.

기본값은 원 작업 PC(`C:\Users\82109\Desktop\2026\변시대비 자료 및 pdf\...`) 기준이다.
[`scripts/paths.py`](scripts/paths.py) 참고.

---

## 알려진 한계

- **쟁점 자동분류 실패율**: 공법 205/424(48%)가 "공법일반", 형사법 227/550(41%)이 "형사법일반"으로 남았다. 민사법은 상법 분류가 27개(5.6%)뿐이라 상법 쟁점 상당수가 민법으로 흡수됐을 가능성이 크다.
- **채점근거 공백**: 형사법 변시 1~5회(조균석 책이 QR 온라인 제공으로 전환해 추출 불가), 민사법 변시 1·2·3·5·9·12·14회(정연석 책에 요약만 있음).
- **`relabel_groups.py`의 100점 규칙**은 공법 15회 실제 PDF로 검증했고 공법·형사법 110건 중 105건이 정확히 맞는다. 민사법은 배점 총합이 350점이라 **검증되지 않은 근사치**다.

전체 이슈 목록은 [`../HANDOFF.md`](../HANDOFF.md)의 "미해결 이슈" 참고.
