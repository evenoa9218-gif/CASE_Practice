/**
 * 사례형 답안 AI 채점 프록시.
 *
 * 앱은 GitHub Pages에 정적으로 올라가므로 API 키를 둘 곳이 없다(공개 저장소라
 * 올리는 즉시 노출된다). 그래서 키는 이 Worker의 환경변수에만 두고, 앱은
 * 여기로 답안을 보내 채점 결과만 받는다.
 *
 * 문제·채점기준표는 앱이 보내지 않고 **Worker가 직접 가져온다.** 앱이 보내게
 * 두면 이 엔드포인트가 "아무 텍스트나 넣으면 답해주는 창구"가 되어버린다.
 * 클라이언트에서 오는 자유 텍스트는 답안 하나뿐이다.
 */

import Anthropic from '@anthropic-ai/sdk';

// 앱이 배포된 곳. 여기서 온 요청만 받는다.
const ALLOWED_ORIGINS = [
  'https://evenoa9218-gif.github.io',
];

// 시험 데이터를 가져올 곳. Worker가 직접 읽는다. 사례형과 기록형은 저장소가
// 다르고, 어느 쪽인지는 시험 ID 꼬리(_사례/_기록)가 말해 준다.
const DATA_BASES = {
  사례: 'https://evenoa9218-gif.github.io/CASE_Practice/data',
  기록: 'https://evenoa9218-gif.github.io/RECORD/data',
};

// 경로에 들어갈 값이므로 형식을 먼저 좁힌다. 과목은 목록으로, 시험 ID는
// 파이프라인이 만드는 `{과목}_{출처}_{회차}_(사례|기록)` 형태만 통과시킨다.
//
// ⚠️ 예전에는 `{과목}_(변시|모의)_{회차}_사례`만 받았는데, 그러면 실제 ID
// 614개 중 **569개가 거부됐다.** 모의고사는 `모의_2026_1차`로 밑줄이 하나 더
// 들어가고, 창작문제는 출처가 `로사정`·`박승수`이며 가지번호(`003-1`)도 쓴다.
// AI 채점이 변호사시험 45건에서만 되고 있었다.
const SUBJECTS = ['공법', '형사법', '민사법', '국제법', '국제거래법'];
const EXAM_ID_RE = /^[가-힣]{2,5}_[가-힣]{2,4}_[0-9가-힣]+(?:[-_][0-9가-힣]+)?_(사례|기록)$/;

// 사례형 답안은 한 문항 1.2만 자면 넉넉하다. 기록형 서면(소장·변론요지서)은
// 그 자체가 답안지 여러 장이라 상한을 따로 둔다.
const MAX_ANSWER_CHARS = { 사례: 12000, 기록: 24000 };
const MAX_TOKENS = 16000;         // 생각 + 피드백 합계
// 기록형 채점 근거(해설)는 3만 자를 넘기도 한다. 기준 잡는 데 필요한 만큼만 준다.
const MAX_BASIS_CHARS = 28000;

function cors(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function bad(status, message, origin) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(origin) },
  });
}

/** 시험 데이터를 가져온다. 같은 회차를 반복 채점하므로 캐시에 남긴다. */
async function loadExam(mode, subject, examId) {
  const url = `${DATA_BASES[mode]}/${encodeURIComponent(subject)}/exams/${encodeURIComponent(examId)}.json`;
  const cache = caches.default;
  let res = await cache.match(url);
  if (!res) {
    res = await fetch(url, { cf: { cacheTtl: 3600, cacheEverything: true } });
    if (!res.ok) return null;
    res = new Response(res.body, res);
    res.headers.set('Cache-Control', 'max-age=3600');
    await cache.put(url, res.clone());
  }
  return res.json();
}

const SYSTEM = `당신은 대한민국 변호사시험 사례형 채점위원이다. 수험생의 답안을
채점기준표(또는 모범답안)에 비추어 평가한다.

채점 원칙:
- 채점기준표에 있는 쟁점을 기준으로 삼는다. 기준표에 없는 쟁점을 새로 만들어
  감점하지 않는다.
- 답안에서 실제로 쓴 내용만 평가한다. 쓰지 않은 것을 짐작해서 점수를 주지 않는다.
- 결론보다 논증 과정(법리 서술 → 사안 포섭 → 결론)을 본다. 결론이 맞아도
  포섭이 없으면 배점의 절반을 넘기지 않는다.
- 판례·조문 인용의 정확성을 따진다. 틀린 인용은 명시적으로 지적한다.

출력 형식(마크다운):

## 쟁점별 채점
| 쟁점 | 배점 | 득점 | 평가 |
각 행은 채점기준표의 항목을 따른다.

## 잘한 점
실제 답안 문장을 인용하며 구체적으로.

## 놓친 쟁점
답안에 없는 것 중 기준표에 있는 것. 각 항목에 어떻게 썼어야 하는지 한두 문장.

## 다음에 고칠 것
가장 점수를 많이 올릴 수 있는 것부터 최대 3개.

마지막 줄에 반드시 아래 형식으로 총점만 적는다(다른 말 없이):
[[SCORE:정수]]`;

const SYSTEM_RECORD = `당신은 대한민국 변호사시험 기록형 채점위원이다. 수험생이 사건 기록을
읽고 작성한 서면(소장·답변서·변론요지서·검토의견서·헌법소원심판청구서 등)을
채점기준표(또는 해설)에 비추어 평가한다.

채점 원칙:
- 채점기준표가 있으면 그 항목과 배점이 유일한 기준이다. 기준표에 없는 쟁점을
  만들어 감점하지 않는다.
- 기록형은 서면의 '양식'도 점수다. 서면 종류에 맞는 필수 기재사항을 본다.
  · 소장: 당사자·소송대리인, 청구취지, 청구원인, 입증방법·첨부서류, 법원 표시
  · 답변서·준비서면: 청구취지에 대한 답변, 청구원인에 대한 인부, 항변
  · 변론요지서(형사): 공소사실별 목차, 증거능력·증명력 탄핵, 사실오인·법리·양형 주장
  · 검토의견서·검토보고서(형사): 쟁점별 결론(유·무죄, 기소 여부)과 근거
  · 헌법소원심판청구서: 청구인, 침해된 권리, 침해 원인 공권력, 청구취지,
    적법요건(기본권침해의 자기·현재·직접관련성, 보충성, 청구기간), 본안(제한되는 기본권 → 위헌심사)
  · 행정소송 소장: 처분 표시, 소송요건(대상적격·원고적격·피고적격·제소기간·관할), 본안 위법사유
- 청구취지·주문은 기록형의 핵심 배점이다. 금액, 이자(기산일·이율·근거), 목적물
  표시, 당사자 표시, 소송비용, 가집행 문구를 글자 단위로 따지고, 틀렸으면
  올바른 문구를 그대로 제시한다.
- 사실과 증거 인용의 정확성을 본다. 기록에 있는 사실·증거(갑 제○호증 등)에
  근거했는지, 기록에 없는 사실을 지어내지 않았는지 확인하고 지어낸 것은
  명시적으로 지적한다.
- 문제가 '기재하지 말라'고 한 부분(작성 제외 사항)을 어겼는지 확인한다.
- 답안에서 실제로 쓴 내용만 평가한다. 쓰지 않은 것을 짐작해서 점수를 주지 않는다.

출력 형식(마크다운):

## 양식·형식
서면 종류에 맞는 필수 기재사항의 충족 여부. 청구취지(주문)가 있으면 문구 단위 평가.

## 쟁점별 채점
| 쟁점 | 배점 | 득점 | 평가 |
채점기준표의 항목을 따른다. 기준표가 없으면 해설의 쟁점 순서를 따른다.

## 잘한 점
실제 답안 문장을 인용하며 구체적으로.

## 놓친 것
답안에 없는 것 중 기준표(해설)에 있는 것. 각 항목에 어떻게 썼어야 하는지 한두 문장.

## 다음에 고칠 것
가장 점수를 많이 올릴 수 있는 것부터 최대 3개.

마지막 줄에 반드시 아래 형식으로 총점만 적는다(다른 말 없이):
[[SCORE:정수]]`;

/** 기록형 채점 근거: 기준표가 정본, 없으면 해설. 둘 다 없으면 그 사실을 밝힌다. */
function buildRecordPrompt(exam, task, answer) {
  const parts = [];
  parts.push(`# 시험\n${exam.label}`);
  parts.push(`# 채점할 서면\n${task.title}` +
    (task.points > 0 ? ` (배점 ${task.points}점)` : ' (배점 미표시 — 100점 만점으로 채점한다)'));
  if (exam.problemBlock) parts.push(`# 작성 요령(문제 지시)\n${exam.problemBlock}`);
  if (exam.problemText) parts.push(`# 사건 기록 전문\n${exam.problemText}`);

  const rubric = (exam.rubricText || '').trim();
  if (rubric.length > 300) {
    parts.push(`# 채점기준표\n${rubric}`);
  } else if (exam.commentaries?.length) {
    let budget = MAX_BASIS_CHARS;
    const chunks = [];
    for (const c of exam.commentaries) {
      if (budget <= 0) break;
      const t = (c.text || '').slice(0, budget);
      budget -= t.length;
      chunks.push(`[${c.author} — ${c.title}]\n${t}`);
    }
    parts.push(`# 해설 (공식 채점기준표가 없어 해설서를 기준으로 삼는다)\n${chunks.join('\n\n---\n\n')}`);
  } else {
    parts.push(
      `# 채점 근거 없음\n이 회차는 채점기준표도 해설도 확보되지 않았다. ` +
        `해당 서면의 일반적 작성 기준(양식·요건사실·기록 인용의 완결성)으로 평가하고, ` +
        `총평 첫머리에 "공식 채점기준 없이 평가한 결과"임을 밝혀라.`,
    );
  }

  parts.push(`# 수험생 답안(${task.title})\n${answer}`);
  return parts.join('\n\n');
}

function buildPrompt(exam, group, answer) {
  const parts = [];
  parts.push(`# 시험\n${exam.label}`);
  // 배점이 없는 문항이 있다. 창작문제 사례집 중에는 책이 배점을 아예 매기지 않은
  // 것이 많은데(박승수 민법 기본사례 286개 중 115개), 없는 배점을 `0점`이라고
  // 알려주면 채점이 엉뚱해진다. 그렇다고 빼기만 하면 채점자가 제멋대로 만점을
  // 잡아 점수가 사례마다 다른 잣대로 나온다 — **100점 만점으로 못박는다.**
  // 앱도 배점이 없으면 100을 만점으로 삼아 표시·기록한다(index.html의 maxPts).
  parts.push(`# 채점할 문항\n${group.label} ` +
    (group.points > 0 ? `(배점 ${group.points}점)` : '(배점 미표시 — 100점 만점으로 채점한다)'));

  if (group.questions?.length) {
    const qs = group.questions
      .map((q) => `- ${q.no ? q.no + ' ' : ''}${q.ask}${q.points ? ` (${q.points}점)` : ''}`)
      .join('\n');
    parts.push(`# 설문\n${qs}`);
  }
  if (exam.problemText) parts.push(`# 문제 전문\n${exam.problemText}`);

  // 채점 근거는 기준표가 정본, 없으면 사례집 모범답안으로 대신한다.
  if (exam.rubricText) {
    parts.push(`# 채점기준표\n${exam.rubricText}`);
  } else if (exam.casebookAnswers?.length) {
    // 데이터의 본문 필드는 `answerText` 다. 예전에 `a.text` 만 보다가 undefined 가
    // 되어, 채점기준표가 없는 494건(변시 30 + 창작문제 464)에서 모범답안이
    // "[object Object]" 로 들어가고 있었다. `header` 에 문항 라벨이 있으니 같이 준다.
    const model = exam.casebookAnswers
      .map((a) => (typeof a === 'string' ? a
        : [a.header, a.answerText || a.text].filter(Boolean).join('\n')))
      .filter(Boolean)
      .join('\n\n---\n\n');
    parts.push(
      `# 모범답안 (공식 채점기준표가 없어 사례집 모범답안을 기준으로 삼는다)\n${model}`,
    );
  } else {
    parts.push(
      `# 채점 근거 없음\n이 회차는 채점기준표도 모범답안도 확보되지 않았다. ` +
        `일반적인 사례형 작성 기준(법리·포섭·결론의 완결성)으로 평가하고, ` +
        `총평 첫머리에 "공식 채점기준표 없이 평가한 결과"임을 밝혀라.`,
    );
  }

  parts.push(`# 수험생 답안\n${answer}`);
  return parts.join('\n\n');
}

/**
 * Anthropic으로 나가는 요청의 **출구 지역**을 고정하기 위한 통로.
 *
 * 상태를 담지 않는다 — Durable Object를 쓰는 이유는 오로지 `locationHint`로
 * 실행 지역을 지정할 수 있기 때문이다. 들어온 요청을 그대로 흘려보내면
 * 이 DO가 있는 지역(미국 동부)에서 나간다.
 */
export class UsRelay {
  async fetch(request) {
    return fetch(request);
  }
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get('Origin') || '';
    const colo = request.cf?.colo || '?';   // 실행된 Cloudflare PoP. 403 진단에 쓴다.

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors(origin) });
    }
    if (request.method !== 'POST') return bad(405, 'POST만 받는다', origin);
    if (!ALLOWED_ORIGINS.includes(origin)) return bad(403, '허용되지 않은 출처', origin);
    if (!env.ANTHROPIC_API_KEY) return bad(500, 'ANTHROPIC_API_KEY가 설정되지 않았다', origin);

    // 분당 요청 수 제한. 바인딩을 안 붙였으면 이 단계는 건너뛴다.
    if (env.GRADE_LIMIT) {
      const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
      const { success } = await env.GRADE_LIMIT.limit({ key: ip });
      if (!success) return bad(429, '잠시 후 다시 시도해 주세요', origin);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return bad(400, '잘못된 요청 형식', origin);
    }

    const { subject, examId, groupKey, taskNo, answer } = body || {};
    if (!SUBJECTS.includes(subject)) return bad(400, '알 수 없는 과목', origin);
    if (typeof examId !== 'string' || !EXAM_ID_RE.test(examId)) return bad(400, '알 수 없는 시험', origin);
    const mode = examId.endsWith('_기록') ? '기록' : '사례';
    if (typeof answer !== 'string' || !answer.trim()) return bad(400, '답안이 비어 있다', origin);
    if (answer.length > MAX_ANSWER_CHARS[mode]) {
      return bad(413, `답안이 너무 길다 (최대 ${MAX_ANSWER_CHARS[mode]}자)`, origin);
    }

    const exam = await loadExam(mode, subject, examId);
    if (!exam) return bad(404, '시험 데이터를 찾지 못했다', origin);

    let system, prompt;
    if (mode === '기록') {
      // 과제를 자동으로 못 뽑은 회차는 앱이 '답안' 칸 하나(no=1)로 폴백한다.
      const tasks = exam.tasks?.length ? exam.tasks : [{ no: 1, title: '답안', points: null }];
      const task = tasks.find((t) => t.no === Number(taskNo));
      if (!task) return bad(400, '알 수 없는 서면', origin);
      system = SYSTEM_RECORD;
      prompt = buildRecordPrompt(exam, task, answer);
    } else {
      const group = (exam.groups || []).find((x) => x.key === groupKey);
      if (!group) return bad(400, '알 수 없는 문항', origin);
      system = SYSTEM;
      prompt = buildPrompt(exam, group, answer);
    }

    // Anthropic 호출은 반드시 북미에서 나가게 한다.
    //
    // Worker는 요청자와 가까운 PoP에서 실행되는데, 한국에서 부르면 홍콩(HKG)에
    // 걸리는 일이 잦다. Anthropic은 미지원 지역의 요청을 **키를 확인하기도 전에**
    // 403 forbidden으로 끊는다. 그래서 어제 되던 채점이 오늘 안 되고 재시도하면
    // 갑자기 되는 일이 반복됐다. `[placement] mode = "smart"`로는 안 잡혔다.
    //
    // Durable Object는 만들 때 지역을 지정할 수 있다. 그 안에서 fetch 하면
    // 그 지역에서 나간다. 그래서 DO를 미국 동부에 하나 두고 통로로만 쓴다.
    const relay = env.US.get(env.US.idFromName('anthropic'), { locationHint: 'enam' });
    const client = new Anthropic({
      apiKey: env.ANTHROPIC_API_KEY,
      fetch: (input, init) => relay.fetch(new Request(input, init)),
    });

    // 채점은 생각이 길어 응답까지 수십 초가 걸린다. 스트리밍으로 보내
    // 사용자가 진행 상황을 보게 하고, 연결이 끊기는 것도 막는다.
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const send = (obj) =>
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
        try {
          const ms = client.messages.stream({
            model: 'claude-opus-5',
            max_tokens: MAX_TOKENS,
            output_config: { effort: env.GRADE_EFFORT || 'high' },
            system,
            messages: [{ role: 'user', content: prompt }],
          });

          for await (const ev of ms) {
            if (ev.type === 'content_block_delta' && ev.delta.type === 'text_delta') {
              send({ t: ev.delta.text });
            }
          }

          const final = await ms.finalMessage();
          if (final.stop_reason === 'refusal') {
            send({ error: '채점을 완료하지 못했습니다. 답안 내용을 확인해 주세요.' });
          } else if (final.stop_reason === 'max_tokens') {
            send({ error: '피드백이 길어 중간에 끊겼습니다. 답안을 나눠서 채점해 주세요.' });
          }
          send({ done: true, usage: final.usage });
        } catch (e) {
          // API 쪽에서 막힌 것인지 이쪽 잘못인지 나중에 가리려면 요청 ID가 있어야
          // 한다. Anthropic 지원에 문의할 때 이것부터 묻는다.
          const id = e?.request_id || e?.headers?.['request-id'];
          console.error('grade failed',
            { status: e?.status, colo, request_id: id, msg: e?.message });
          // 403 은 거의 언제나 키나 요금 문제가 아니라 **실행 지역** 문제다.
          // Worker가 어느 PoP에서 돌았는지 모르면 매번 크레딧을 의심하게 된다.
          const where = e?.status === 403
            ? `\n\n이 오류는 Worker가 실행된 지역(${colo}) 때문일 수 있습니다. `
              + `Anthropic이 미지원 지역의 요청을 키 확인 전에 차단합니다. `
              + `잠시 후 다시 시도하면 다른 지역에서 실행되어 통과하기도 합니다.`
            : '';
          send({ error: `채점 중 오류: ${e.message}` + (id ? ` (요청 ID ${id})` : '') + where });
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        ...cors(origin),
      },
    });
  },
};
