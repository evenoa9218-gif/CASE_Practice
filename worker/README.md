# AI 자동채점 Worker

사례형 답안을 채점기준표에 비추어 평가하고 피드백을 돌려주는 Cloudflare Worker.

앱은 GitHub Pages에 정적으로 올라가므로 API 키를 둘 곳이 없다 — 공개 저장소라
올리는 즉시 노출된다. 그래서 키는 이 Worker의 secret에만 두고, 앱은 답안을
여기로 보내 결과만 받는다. 피드백은 [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)의
프라이버시 경계에 따라 **기기 로컬에만** 저장된다.

---

## 배포

준비물: Cloudflare 계정(무료 플랜으로 충분), Anthropic API 키.

```bash
cd worker
npm install
npx wrangler login
npx wrangler deploy
npx wrangler secret put ANTHROPIC_API_KEY   # 붙여넣기 (화면에 안 보인다)
```

배포되면 `https://case-grader.<계정>.workers.dev` 같은 주소가 나온다.
그 주소를 앱의 `index.html` 안 `GRADER_URL`에 넣고 커밋하면 채점 버튼이 켜진다.
`GRADER_URL`이 비어 있으면 앱은 채점 기능을 숨긴 채 그대로 동작한다.

로컬에서 확인하려면:

```bash
npx wrangler dev
```

---

## 엔드포인트

`POST /` — 요청과 응답 모두 UTF-8.

```json
{ "subject": "공법", "examId": "공법_변시_15회_사례", "groupKey": "제1문의1", "answer": "..." }
```

응답은 **SSE 스트림**이다. 채점은 생각이 길어 수십 초가 걸리므로, 다 끝난 뒤
한 번에 주지 않고 쓰이는 대로 흘려보낸다.

```
data: {"t":"## 쟁점별 채점\n"}      ← 피드백 조각
data: {"done":true,"usage":{...}}   ← 완료 + 토큰 사용량
data: {"error":"..."}               ← 실패
```

피드백 마지막 줄의 `[[SCORE:87]]`이 총점이다. 앱이 이 값을 꺼내 기록에 남기고
화면에서는 지운다.

---

## 왜 문제·채점기준표를 앱이 안 보내는가

Worker가 `evenoa9218-gif.github.io`에서 **직접 가져온다.** 앱이 보내게 두면 이
엔드포인트가 "아무 텍스트나 넣으면 답해주는 창구"가 되어, 남의 API 키로
일반 LLM을 쓰는 통로가 된다. 지금 클라이언트에서 오는 자유 텍스트는 답안
하나뿐이고, 나머지는 과목명·시험ID·문항키뿐이라 형식 검사로 걸러진다.

가져온 시험 데이터는 Cache API에 1시간 남긴다 — 같은 회차를 반복 채점하므로
매번 다시 받을 이유가 없다.

## 무엇을 막고 무엇을 못 막는가

| 막는 것 | 방법 |
|---|---|
| 다른 사이트에서 호출 | `Origin` 허용목록 (`ALLOWED_ORIGINS`) |
| 한 사람이 계속 호출 | IP당 분당 10회 (`GRADE_LIMIT` 바인딩) |
| 긴 입력으로 요금 태우기 | 답안 12,000자 상한, 출력 16,000토큰 상한 |
| 임의 텍스트를 넣어 일반 LLM처럼 쓰기 | 문제·기준표를 Worker가 직접 가져옴 + 채점 전용 시스템 프롬프트 |

**못 막는 것**: `Origin` 헤더는 브라우저가 붙이는 값이라 curl로는 위조된다.
엔드포인트 주소를 아는 사람이 답안 자리에 아무 글이나 넣어 호출하는 것까지는
막지 못한다. 분당 10회·출력 상한이 피해를 제한하는 선이다.

**그러니 Anthropic 콘솔에서 사용량 한도를 걸어 두는 것을 권한다.** 위 방어가
모두 뚫려도 요금이 무한정 나가지 않는 마지막 선이다.

---

## 비용

문항 하나 채점에 입력 5~15K 토큰(문제+기준표), 출력 1~2K 토큰(생각 포함).
Claude Opus 5 기준 대략 **한 번에 $0.05~0.1**, 100번이면 $5~10쯤이다.

`GRADE_EFFORT`를 `medium`으로 낮추면 응답이 빨라지고 토큰이 줄지만 채점이
얕아진다. `wrangler.toml`의 `[vars]`에서 바꾼 뒤 다시 배포하면 된다.

Worker 자체는 무료 플랜의 하루 100,000요청 안에서 돌아간다.

---

## 문제가 생기면

```bash
npx wrangler tail       # 실시간 로그
```

| 증상 | 원인 |
|---|---|
| 403 `허용되지 않은 출처` | `ALLOWED_ORIGINS`에 앱 주소가 없다 |
| 500 `ANTHROPIC_API_KEY가 설정되지 않았다` | `wrangler secret put`을 안 했다 |
| 404 `시험 데이터를 찾지 못했다` | `DATA_BASE` 경로가 틀렸거나 해당 회차 JSON이 배포 안 됨 |
| 429 | 분당 10회 제한. `wrangler.toml`에서 조절 |
