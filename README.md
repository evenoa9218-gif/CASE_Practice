# CASE_Practice — 사례형 연습

변호사시험 사례형 문제풀이 · 답안작성 · 아카이빙 페이지.
통합 학습 시스템(`evenoa9218-gif.github.io`)의 **위성 앱** 중 하나.

**배포**: https://evenoa9218-gif.github.io/CASE_Practice/

---

## 현재 수록 범위

| 과목 | 변호사시험 | 모의고사 | 채점기준표 | 사례집 모범답안 |
|---|---|---|---|---|
| 공법 | 15회 (1~15) | 40회 (2013~2026) | 40 | 54 |

- 변호사시험은 공식 채점기준표가 공개되지 않아, 사례집 모범답안이 유일한 채점 근거입니다.
- 55건 전부 채점 근거(채점기준표 또는 모범답안)를 확보했습니다.

## 구조

```
index.html              단일 파일 React 앱 (빌드 없음, CDN + Babel)
core/store.js           4체계 공용 저장 추상화 (IndexedDB)
data/
├─ issues_공법.json      쟁점 레지스트리 (PUB-0001 ~ PUB-0424)
└─ 공법/
   ├─ index.json        가벼운 인덱스 (264KB) — 시험 목록·쟁점·역인덱스
   └─ exams/*.json      회차별 상세 (지연 로딩, 총 7.2MB)
```

## 통합 규격

### 쟁점 ID — 4체계를 잇는 축

암기장·선택형·사례형·기록형이 같은 ID로 같은 논점을 지칭합니다.

```
PUB-0001  재판의전제성      path: ["공법","헌법"]
PUB-0003  협의의소익        path: ["공법","행정법"]
```

- **목차 위치를 ID에 넣지 않습니다.** 기본서 개정·목차 재편으로 태깅이 무효화되는 것을 막기 위함
- ID는 한 번 부여하면 재사용하지 않습니다
- 계층은 `path` 필드로 별도 관리
- 표기 흔들림(`비례원칙`↔`과잉금지원칙`)은 `aliases`로 통합

과목별 접두사: `PUB`(공법) · `CIV`(민사법) · `CRI`(형사법) · `INT`(국제법) · `ITL`(국제거래법)

### store.js — 이 API 표면은 바꾸지 않습니다

앱 4개가 의존하므로, 내부 구현(IndexedDB → Firestore)을 갈아끼워도 호출부는 그대로입니다.

```js
Store.init({ remoteUrl })          // remoteUrl 생략 시 로컬 전용
Store.setUser(uid) / getUser()
Store.record(result)               // 학습 결과 1건 (선택형·사례형 공용)
Store.getRecords(filter)
Store.getMastery(subject)          // 쟁점별 숙달도 집계 ← 연동 지점
Store.getProgress(subject, round) / setProgress(...)
Store.getDraft(key) / setDraft(key, text) / clearDraft(key)
Store.sync(subject)
```

`record()`에 넘기는 형태:

```js
{ subject, mode:'mcq'|'case'|'record'|'memo',
  examId, label, round, issueIds:[], text, seconds,
  correct, score, maxScore }
```

### 앱 간 이동

```
암기장 → 사례형   /CASE_Practice/?issue=PUB-0001
사례형 → 암기장   /Core_Notes/#PUB-0001
```

`?issue=` 파라미터는 이미 수신 구현되어 있습니다(해당 쟁점으로 자동 필터링).

### 프라이버시

답안 전문은 **기기 안(IndexedDB)에만** 저장됩니다.
원격에는 점수·소요시간·쟁점 ID 같은 요약만 전송합니다.

## 개발

정적 사이트이지만 `fetch`로 데이터를 읽으므로 `file://`로 직접 열면 동작하지 않습니다.

```bash
python -m http.server 8000
```

## 아직 안 된 것

- AI 채점 (Cloudflare Worker 프록시 필요 — API 키를 정적 페이지에 둘 수 없음)
- 나머지 4과목 (데이터는 준비 완료, 앱 반영 전)
- 허브 연동 (허브 페이지 구축 후)
