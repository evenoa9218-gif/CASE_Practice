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

// 시험 데이터를 가져올 곳. Worker가 직접 읽는다.
const DATA_BASE = 'https://evenoa9218-gif.github.io/CASE_Practice/data';

// 경로에 들어갈 값이므로 형식을 먼저 좁힌다. 과목은 목록으로, 시험 ID는
// 파이프라인이 만드는 `{과목}_{변시|모의}_{회차}_사례` 형태만 통과시킨다.
const SUBJECTS = ['공법', '형사법', '민사법', '국제법', '국제거래법'];
const EXAM_ID_RE = /^[가-힣]+_(변시|모의)_[0-9가-힣]+_사례$/;

const MAX_ANSWER_CHARS = 12000;   // 사례형 한 문항 답안으로 넉넉한 상한
const MAX_TOKENS = 16000;         // 생각 + 피드백 합계

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
async function loadExam(subject, examId) {
  const url = `${DATA_BASE}/${encodeURIComponent(subject)}/exams/${encodeURIComponent(examId)}.json`;
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

function buildPrompt(exam, group, answer) {
  const parts = [];
  parts.push(`# 시험\n${exam.label}`);
  parts.push(`# 채점할 문항\n${group.label} (배점 ${group.points}점)`);

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
    const model = exam.casebookAnswers.map((a) => a.text || a).join('\n\n---\n\n');
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

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get('Origin') || '';

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

    const { subject, examId, groupKey, answer } = body || {};
    if (!SUBJECTS.includes(subject)) return bad(400, '알 수 없는 과목', origin);
    if (typeof examId !== 'string' || !EXAM_ID_RE.test(examId)) return bad(400, '알 수 없는 시험', origin);
    if (typeof answer !== 'string' || !answer.trim()) return bad(400, '답안이 비어 있다', origin);
    if (answer.length > MAX_ANSWER_CHARS) {
      return bad(413, `답안이 너무 길다 (최대 ${MAX_ANSWER_CHARS}자)`, origin);
    }

    const exam = await loadExam(subject, examId);
    if (!exam) return bad(404, '시험 데이터를 찾지 못했다', origin);

    const group = (exam.groups || []).find((x) => x.key === groupKey);
    if (!group) return bad(400, '알 수 없는 문항', origin);

    const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });

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
            system: SYSTEM,
            messages: [{ role: 'user', content: buildPrompt(exam, group, answer) }],
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
          send({ error: `채점 중 오류: ${e.message}` });
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
