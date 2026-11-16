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
  기록: 'https://evenoa9218-gif.github.io/RECORD_Practice/data',   // 저장소 이름과 로컬 폴더명(RECORD)이 다르다
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
// 생각 + 피드백 합계. 기록형은 청구·피고가 여럿이라 생각만으로 1.6만 토큰을 다 쓰고
// 피드백을 한 글자도 못 낸 채 끊긴 적이 있다(민사 13회 소장, 2026-09-17 — 돈만 나감).
// 상한은 넘을 때만 의미가 있으므로 올려도 평소 비용은 그대로다.
const MAX_TOKENS = { 사례: 16000, 기록: 32000 };
// 기록형 채점 근거(해설)의 상한. 해설서는 4~6만 자인데 예전 상한 2.8만 자로 앞에서부터 자르면
// 정연석 민사 해설은 앞 3만 자가 문제 재수록이라 모범답안이 한 줄도 안 들어갔다(변시 30회차).
// 그 상태로 채점하면 모델이 법리를 스스로 세워 모범답안과 정반대로 감점한다(민사 13회 실측).
// 재수록은 commentaryBody 가 떼어 내고, 상한은 형사(노수환, 두 서면 합쳐 5만 자대)가 통째로 들어가게 잡는다.
// 같은 회차의 서면들이 이 근거를 캐시로 함께 쓰므로 서면별로 자르지 않는다.
const MAX_BASIS_CHARS = 60000;
// 데이터를 크게 바꿨을 때 올린다(loadExam 캐시 키). 2: 문항별 근거 자르기(basisSlice) 추가
// 3: 기록형 서면 목록·배점 바로잡기(fill_task_points)
const DATA_CACHE_VER = 4;

// 비용 기록용 단가(달러/100만 토큰, claude-opus-5). 캐시 쓰기는 5분 캐시 기준 1.25배.
// 단가가 바뀌면 여기만 고친다 — 이미 쌓인 행은 기록 당시 값으로 남는다.
const PRICE = { input: 5, cacheWrite: 6.25, cacheRead: 0.5, output: 25 };

function costOf(u) {
  return ((u.input_tokens || 0) * PRICE.input
    + (u.cache_creation_input_tokens || 0) * PRICE.cacheWrite
    + (u.cache_read_input_tokens || 0) * PRICE.cacheRead
    + (u.output_tokens || 0) * PRICE.output) / 1e6;
}

// 채점 1건을 D1에 남긴다. 기록이 실패해도 채점 응답에는 영향을 주지 않는다.
async function logUsage(env, row) {
  if (!env.USAGE_DB) return;
  try {
    const u = row.usage || {};
    await env.USAGE_DB.prepare(
      `INSERT INTO usage (mode, subject, exam_id, unit, status, input_tokens, cache_write_tokens,
        cache_read_tokens, output_tokens, cost_usd, answer_chars, sliced, ip_hash)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(
      row.mode, row.subject, row.examId, row.unit ?? null, row.status,
      u.input_tokens ?? null, u.cache_creation_input_tokens ?? null,
      u.cache_read_input_tokens ?? null, u.output_tokens ?? null,
      row.usage ? costOf(u) : null, row.answerChars, row.sliced ? 1 : 0, row.ipHash,
    ).run();
  } catch (e) {
    console.error('usage log failed', e?.message);
  }
}

// 오늘·이번 달 쓴 돈을 D1 기록에서 더해 한도를 넘었는지 본다.
// 분당 요청 제한(GRADE_LIMIT)은 한 사람이 연타하는 것만 막는다 — 기록형 한 건이 $1 가까이 되므로
// 하루에 몇십 건만 돌아도 요금이 크게 뛴다. 돈 자체에도 상한을 둔다.
// 기록이 없거나 조회가 실패하면 **채점은 막지 않는다** — 안전장치 때문에 앱이 멈추는 게 더 나쁘다.
async function spentSoFar(env) {
  if (!env.USAGE_DB) return null;
  try {
    const r = await env.USAGE_DB.prepare(
      `SELECT
         COALESCE(SUM(CASE WHEN ts >= date('now') THEN cost_usd END), 0) AS today,
         COALESCE(SUM(CASE WHEN ts >= date('now', 'start of month') THEN cost_usd END), 0) AS month
       FROM usage`,
    ).first();
    return { today: Number(r?.today || 0), month: Number(r?.month || 0) };
  } catch (e) {
    console.error('usage sum failed', e?.message);
    return null;
  }
}

// 남용 추적용으로만 쓴다 — IP 원문은 저장하지 않는다.
async function hashIp(ip) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`grade:${ip}`));
  return [...new Uint8Array(d)].slice(0, 6).map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Anthropic SDK 오류를 화면에 띄울 한국어 문장으로 옮긴다.
 *
 * 예전에는 e.message 를 그대로 흘려보냈다. 그러면 화면에
 *   400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit
 *   balance is too low ..."}}
 * 같은 영어 JSON 덩어리가 찍힌다. 답안을 쓴 사람은 자기 답안이 잘못된 줄 알지만
 * 실제로는 대개 계정·혼잡 쪽 사정이고 답안과 무관하다. 무엇을 하면 되는지도 함께
 * 적는다 — 읽고 나서 할 일을 모르는 오류 문구는 없는 것과 같다.
 */
function friendlyError(e, colo) {
  const raw = String(e?.message || '');
  const status = e?.status;
  if (/credit balance is too low/i.test(raw)) {
    return 'Anthropic 계정의 크레딧이 떨어져 채점을 할 수 없습니다. '
      + 'console.anthropic.com 의 Plans & Billing 에서 충전하신 뒤 다시 시도해 주세요. '
      + '작성하신 답안과 지금까지 받은 첨삭은 그대로 남아 있습니다.';
  }
  if (status === 401 || /authentication|invalid x-api-key/i.test(raw)) {
    return 'Anthropic API 키가 거부되었습니다. 키가 만료되었거나 삭제되었을 수 있습니다.';
  }
  if (status === 429 || /rate.?limit/i.test(raw)) {
    return '요청이 몰려 잠시 제한되었습니다. 1~2분 뒤에 다시 시도해 주세요.';
  }
  if (status === 529 || /overloaded/i.test(raw)) {
    return 'Anthropic 서버가 혼잡합니다. 잠시 후 다시 시도해 주세요.';
  }
  // 이 상태코드는 대개 키나 요금이 아니라 실행 지역 때문에 난다.
  // Worker 가 어느 PoP 에서 돌았는지 모르면 매번 크레딧을 의심하게 된다.
  if (status === 403) {
    return 'Worker 가 실행된 지역(' + colo + ') 때문에 요청이 차단되었습니다. '
      + 'Anthropic 이 미지원 지역의 요청을 키 확인 전에 막습니다. '
      + '잠시 후 다시 시도하시면 다른 지역에서 실행되어 통과하기도 합니다.';
  }
  if (status >= 500) {
    return '채점 서버가 응답하지 못했습니다. 잠시 후 다시 시도해 주세요.';
  }
  return '채점 중 오류가 발생했습니다: ' + raw;
}

function cors(origin, list = ALLOWED_ORIGINS) {
  const allow = list.includes(origin) ? origin : list[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function bad(status, message, origin, list = ALLOWED_ORIGINS) {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(origin, list) },
  });
}

// ══════════════════════════════════════════════════════════════
// 의견함 — 앱에서 보낸 의견을 D1(feedback 표)에 쌓는다.
//
//   POST  /feedback   누구나(허용 출처에서). 의견 1건을 넣는다.
//   GET   /feedback   관리자만. 쌓인 의견을 읽는다.
//   PATCH /feedback   관리자만. 읽음·처리함 표시와 메모.
//
// 채점과 달리 **모델을 부르지 않는다** — 돈이 들지 않으므로 채점 한도와는 무관하다.
// 대신 누구나 쓸 수 있는 창구라 도배를 막아야 한다: 분당 제한(IP별) + 하루 총량.
//
// 관리자 열쇠(FEEDBACK_ADMIN_KEY)는 여기 적지 않는다. 배포하는 사람이 직접 넣는다:
//   npx wrangler secret put FEEDBACK_ADMIN_KEY
// 넣지 않으면 읽기 창구(GET·PATCH)는 닫혀 있고, 그래도 의견은 쌓인다
// (`npm run feedback` 으로는 열쇠 없이 읽을 수 있다 — wrangler 로그인이 열쇠다).
// ══════════════════════════════════════════════════════════════

// 의견을 받는 출처. 지금은 채점과 같다 — 통합사이트(허브 + 위성 앱 넷)뿐이다.
// ⚠ 율리(법조윤리)는 통합사이트와 **별개 앱**이다. 여기에 섞지 않는다(출처도 앱 이름도 넣지 않는다).
const FEEDBACK_ORIGINS = [...ALLOWED_ORIGINS];
const FB_APPS = ['HUB', 'MCQ', 'CASE', 'RECORD', 'NOTES'];
const FB_KINDS = ['오류', '제안', '기타'];
const FB_STATUS = ['new', 'seen', 'done'];
const FB_MAX_TEXT = 3000;
const FB_DAILY_ROWS = 300;      // 하루에 이보다 많이 쌓이면 도배로 보고 닫는다

function fbJson(obj, origin, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(origin, FEEDBACK_ORIGINS) },
  });
}

// 글자를 그대로 견주면 걸리는 시간으로 열쇠가 샌다. 둘 다 해시해서 견준다.
async function sameSecret(a, b) {
  const h = async (s) => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)));
  const [x, y] = await Promise.all([h(a), h(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

const clip = (v, n) => (typeof v === 'string' ? v.trim().slice(0, n) : '');

// ── 새 의견을 관리자 폰으로 바로 보낸다 — 웹 푸시 ─────────────────
// 노트북의 「의견함 보기.bat」은 wrangler 로그인이 있어야 열리고, 토큰이 떨어지면 나(Claude)도 못 읽는다.
// 그래서 들어오는 순간 폰에 밀어 준다. 외부 알림 서비스(ntfy 등)를 거치지 않고 브라우저 표준 웹 푸시로
// 직접 보낸다 — 본문은 기기 공개키로 암호화되어(RFC 8291) 푸시 서비스(구글·애플)도 읽지 못한다.
//   ⚠ ntfy.sh 를 먼저 붙였다가 걷어 냈다: 워커에서 ntfy.sh 로 가는 연결이 늘 522(시간 초과)였다.
//
// 받을 기기: D1 push_subs 표의 status='active' 행. 허브 /feedback-admin.html 에서 신청하면 pending 으로
// 들어오고, 관리자가 `npm run feedback -- push-ok N` 으로 승인한다.
// 서명 열쇠(VAPID_PRIVATE_JWK)는 wrangler secret 으로만 넣는다. 공개키는 허브 쪽에 그대로 적혀 있다.
const PUSH_HOSTS = /^(fcm\.googleapis\.com|[a-z0-9.-]+\.push\.apple\.com|updates\.push\.services\.mozilla\.com|[a-z0-9.-]+\.notify\.windows\.com|[a-z0-9.-]+\.push\.services\.mozilla\.com)$/;
const PUSH_SUBJECT = 'https://evenoa9218-gif.github.io/feedback-admin.html';
const PUSH_MAX_PENDING = 10;

const b64u = {
  enc(buf) {
    let s = '';
    for (const c of new Uint8Array(buf)) s += String.fromCharCode(c);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  },
  dec(str) {
    const s = atob(String(str).replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((str.length + 3) % 4));
    return Uint8Array.from(s, (c) => c.charCodeAt(0));
  },
};
const cat = (...parts) => {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
};
const utf8 = (s) => new TextEncoder().encode(s);

async function hkdf(salt, ikm, info, len) {
  const key = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, key, len * 8));
}

// 푸시 서비스에 「이 서버가 보냈다」고 밝히는 서명(VAPID, RFC 8292). 공개키(x,y)는 JWK 에서 꺼낸다.
async function vapidHeader(env, endpoint) {
  const jwk = JSON.parse(env.VAPID_PRIVATE_JWK);
  const key = await crypto.subtle.importKey('jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const head = b64u.enc(utf8(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const body = b64u.enc(utf8(JSON.stringify({
    aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: PUSH_SUBJECT,
  })));
  const sig = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, utf8(`${head}.${body}`));
  const pub = cat(new Uint8Array([4]), b64u.dec(jwk.x), b64u.dec(jwk.y));
  return `vapid t=${head}.${body}.${b64u.enc(sig)}, k=${b64u.enc(pub)}`;
}

// 본문 암호화 (RFC 8291 + RFC 8188 aes128gcm, 레코드 하나)
async function encryptPush(sub, plaintext) {
  const uaPub = b64u.dec(sub.p256dh), auth = b64u.dec(sub.auth);
  const eph = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const asPub = new Uint8Array(await crypto.subtle.exportKey('raw', eph.publicKey));
  const uaKey = await crypto.subtle.importKey('raw', uaPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, eph.privateKey, 256));
  const ikm = await hkdf(auth, shared, cat(utf8('WebPush: info\0'), uaPub, asPub), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, utf8('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, utf8('Content-Encoding: nonce\0'), 12);
  const aes = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, aes, cat(plaintext, new Uint8Array([2]))));
  const rs = new Uint8Array([0, 0, 16, 0]);                 // 레코드 크기 4096
  return cat(salt, rs, new Uint8Array([asPub.length]), asPub, ct);
}

async function sendPush(env, sub, payload) {
  const body = await encryptPush(sub, utf8(JSON.stringify(payload)));
  return fetch(sub.endpoint, {
    method: 'POST',
    headers: {
      Authorization: await vapidHeader(env, sub.endpoint),
      'Content-Encoding': 'aes128gcm',
      'Content-Type': 'application/octet-stream',
      TTL: '86400',            // 폰이 꺼져 있어도 하루 동안은 기다렸다 전한다
      Urgency: 'high',
    },
    body,
  });
}

// 승인된 기기 모두에 보낸다. 실패해도 의견 저장은 이미 끝났다.
async function notifyPhone(env, f) {
  if (!env.VAPID_PRIVATE_JWK || !env.USAGE_DB) return;
  let subs = [];
  try {
    subs = (await env.USAGE_DB.prepare(
      `SELECT id, endpoint, p256dh, auth FROM push_subs WHERE status = 'active'`).all()).results || [];
  } catch (e) { console.error('push subs read failed', e?.message); return; }
  if (!subs.length) return;
  const where = [f.ctx?.title, ...(f.ctx?.heads || []).slice(0, 2)].filter(Boolean).join(' › ');
  // 푸시 본문은 4KB 가 한도다(암호화 머리 포함). 글은 1,500자에서 자른다 — 전문은 의견함에 있다.
  const payload = {
    id: f.id, app: f.app, kind: f.kind, ts: new Date().toISOString(),
    text: f.text.length > 1500 ? f.text.slice(0, 1500) + ' …(잘림)' : f.text,
    user: f.user || '', contact: f.contact || '', where: where.slice(0, 200),
  };
  await Promise.all(subs.map(async (s) => {
    let note = null, ok = false;
    try {
      const r = await sendPush(env, s, payload);
      ok = r.ok;
      if (!r.ok) note = `${r.status} ${(await r.text()).slice(0, 150)}`;
      // 404·410 = 기기가 구독을 끊었다(앱 지움·권한 거둠). 지운다.
      if (r.status === 404 || r.status === 410) {
        await env.USAGE_DB.prepare(`DELETE FROM push_subs WHERE id = ?`).bind(s.id).run();
        return;
      }
    } catch (e) { note = String(e?.message || e).slice(0, 150); }
    if (note) console.error('push failed', s.id, note);
    await env.USAGE_DB.prepare(ok
      ? `UPDATE push_subs SET last_ok = datetime('now'), last_err = NULL WHERE id = ?`
      : `UPDATE push_subs SET last_err = ? WHERE id = ?`).bind(...(ok ? [s.id] : [note, s.id])).run().catch(() => {});
  }));
}

// 기기 신청 — 허브 /feedback-admin.html 의 「이 기기로 알림 받기」. 누구나 신청은 되지만 pending 이라
// 관리자가 승인하기 전에는 아무것도 받지 못한다.
async function handlePushSubscribe(request, env, origin) {
  const fail = (status, msg) => bad(status, msg, origin, FEEDBACK_ORIGINS);
  if (!FEEDBACK_ORIGINS.includes(origin)) return fail(403, '허용되지 않은 출처');
  if (request.method !== 'POST') return fail(405, '지원하지 않는 방식');
  if (!env.USAGE_DB) return fail(500, '저장할 곳이 설정되지 않았다');
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  if (env.GRADE_LIMIT) {
    const { success } = await env.GRADE_LIMIT.limit({ key: `push:${ip}` });
    if (!success) return fail(429, '잠시 후 다시 시도해 주세요');
  }
  let b;
  try { b = await request.json(); } catch { return fail(400, '잘못된 요청 형식'); }
  const endpoint = clip(b?.sub?.endpoint, 800);
  const p256dh = clip(b?.sub?.keys?.p256dh, 200);
  const auth = clip(b?.sub?.keys?.auth, 100);
  let host = '';
  try { const u = new URL(endpoint); host = u.protocol === 'https:' ? u.hostname : ''; } catch { host = ''; }
  if (!PUSH_HOSTS.test(host)) return fail(400, '알 수 없는 푸시 서비스');
  if (b64u.dec(p256dh).length !== 65 || b64u.dec(auth).length !== 16) return fail(400, '구독 열쇠 형식이 틀렸다');
  try {
    const had = await env.USAGE_DB.prepare(`SELECT id, status FROM push_subs WHERE endpoint = ?`).bind(endpoint).first();
    if (had) return fbJson({ ok: true, id: had.id, status: had.status }, origin);
    const n = await env.USAGE_DB.prepare(`SELECT count(*) AS n FROM push_subs WHERE status = 'pending'`).first();
    if (Number(n?.n || 0) >= PUSH_MAX_PENDING) return fail(429, '승인 대기 중인 신청이 너무 많습니다');
    const r = await env.USAGE_DB.prepare(
      `INSERT INTO push_subs (endpoint, p256dh, auth, label, ua) VALUES (?, ?, ?, ?, ?)`,
    ).bind(endpoint, p256dh, auth, clip(b?.label, 40) || null, clip(request.headers.get('User-Agent') || '', 300) || null).run();
    return fbJson({ ok: true, id: r?.meta?.last_row_id ?? null, status: 'pending' }, origin);
  } catch (e) {
    console.error('push subscribe failed', e?.message);
    return fail(500, '저장하지 못했습니다');
  }
}

async function handleFeedback(request, env, origin, waitUntil) {
  const fail = (status, msg) => bad(status, msg, origin, FEEDBACK_ORIGINS);
  if (!FEEDBACK_ORIGINS.includes(origin)) return fail(403, '허용되지 않은 출처');
  if (!env.USAGE_DB) return fail(500, '의견을 저장할 곳이 설정되지 않았다');
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';

  // ── 넣기 ──
  if (request.method === 'POST') {
    if (env.GRADE_LIMIT) {
      // 채점과 한도를 나눠 쓰지 않게 열쇠 앞에 표시를 붙인다
      const { success } = await env.GRADE_LIMIT.limit({ key: `fb:${ip}` });
      if (!success) return fail(429, '잠시 후 다시 보내 주세요');
    }
    let b;
    try { b = await request.json(); } catch { return fail(400, '잘못된 요청 형식'); }
    const app = clip(b?.app, 12).toUpperCase();
    const kind = clip(b?.kind, 6);
    const text = typeof b?.text === 'string' ? b.text.trim() : '';
    if (!FB_APPS.includes(app)) return fail(400, '알 수 없는 앱');
    if (!FB_KINDS.includes(kind)) return fail(400, '알 수 없는 종류');
    if (text.length < 2) return fail(400, '내용이 비어 있다');
    if (text.length > FB_MAX_TEXT) return fail(413, `내용이 너무 길다 (최대 ${FB_MAX_TEXT}자)`);

    let ctx = null;
    try { ctx = b?.ctx ? JSON.stringify(b.ctx).slice(0, 1500) : null; } catch { ctx = null; }

    try {
      const n = await env.USAGE_DB.prepare(
        `SELECT count(*) AS n FROM feedback WHERE ts >= date('now')`,
      ).first();
      if (Number(n?.n || 0) >= FB_DAILY_ROWS) return fail(429, '오늘은 의견함이 가득 찼습니다. 내일 다시 보내 주세요');
      const r = await env.USAGE_DB.prepare(
        `INSERT INTO feedback (app, kind, text, contact, user, ctx, ua, ip_hash)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      ).bind(
        app, kind, text, clip(b?.contact, 120) || null, clip(b?.user, 60) || null, ctx,
        clip(request.headers.get('User-Agent') || '', 300) || null, await hashIp(ip),
      ).run();
      const id = r?.meta?.last_row_id ?? null;
      let ctxObj = null;
      try { ctxObj = ctx ? JSON.parse(ctx) : null; } catch { ctxObj = null; }
      waitUntil(notifyPhone(env, {
        id, app, kind, text, user: clip(b?.user, 60), contact: clip(b?.contact, 120), ctx: ctxObj,
      }));
      return fbJson({ ok: true, id }, origin);
    } catch (e) {
      console.error('feedback insert failed', e?.message);
      return fail(500, '저장하지 못했습니다. 잠시 후 다시 보내 주세요');
    }
  }

  // ── 아래부터는 관리자만 ──
  if (request.method !== 'GET' && request.method !== 'PATCH') return fail(405, '지원하지 않는 방식');
  if (!env.FEEDBACK_ADMIN_KEY) return fail(503, '관리자 열쇠가 아직 설정되지 않았다 (wrangler secret put FEEDBACK_ADMIN_KEY)');
  if (env.GRADE_LIMIT) {
    // 열쇠를 마구 찍어 보는 것을 늦춘다
    const { success } = await env.GRADE_LIMIT.limit({ key: `fba:${ip}` });
    if (!success) return fail(429, '잠시 후 다시 시도해 주세요');
  }
  const given = (request.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!given || !(await sameSecret(given, env.FEEDBACK_ADMIN_KEY))) return fail(401, '열쇠가 맞지 않는다');

  try {
    if (request.method === 'GET') {
      const q = new URL(request.url).searchParams;
      const status = q.get('status');
      const limit = Math.min(Math.max(Number(q.get('limit')) || 100, 1), 300);
      const where = FB_STATUS.includes(status) ? 'WHERE status = ?' : '';
      const stmt = env.USAGE_DB.prepare(
        `SELECT id, ts, app, kind, text, contact, user, ctx, ua, status, note, done_ts
         FROM feedback ${where} ORDER BY id DESC LIMIT ${limit}`,
      );
      const rows = await (where ? stmt.bind(status) : stmt).all();
      const cnt = await env.USAGE_DB.prepare(
        `SELECT status, count(*) AS n FROM feedback GROUP BY status`,
      ).all();
      return fbJson({ rows: rows.results || [], counts: cnt.results || [] }, origin);
    }
    // PATCH
    let b;
    try { b = await request.json(); } catch { return fail(400, '잘못된 요청 형식'); }
    const id = Number(b?.id);
    if (!Number.isInteger(id) || id < 1) return fail(400, '알 수 없는 의견');
    if (!FB_STATUS.includes(b?.status)) return fail(400, '알 수 없는 상태');
    await env.USAGE_DB.prepare(
      `UPDATE feedback SET status = ?, note = COALESCE(?, note),
         done_ts = CASE WHEN ? = 'done' THEN datetime('now') ELSE done_ts END
       WHERE id = ?`,
    ).bind(b.status, typeof b?.note === 'string' ? b.note.trim().slice(0, 1000) : null, b.status, id).run();
    return fbJson({ ok: true }, origin);
  } catch (e) {
    console.error('feedback admin failed', e?.message);
    return fail(500, '의견함을 읽지 못했습니다');
  }
}

/**
 * 시험 데이터를 가져온다. 같은 회차를 반복 채점하므로 캐시에 남긴다.
 * ⚠ 캐시는 짧게(5분) 둔다. 1시간으로 두었더니 데이터를 고쳐 올린 뒤에도 옛 JSON 으로
 *   채점해, 문항별 근거 자르기를 배포하고도 한동안 전체 근거가 나갔다(검증 채점 1회를 버렸다).
 */
async function loadExam(mode, subject, examId) {
  // 캐시 키 꼬리의 v 는 데이터를 크게 바꿨을 때 올린다 — 데이터센터마다 남은 옛 캐시를 한 번에 끊는다.
  // (Pages 는 쿼리를 무시하므로 받는 파일은 같다)
  const url = `${DATA_BASES[mode]}/${encodeURIComponent(subject)}/exams/${encodeURIComponent(examId)}.json?v=${DATA_CACHE_VER}`;
  const cache = caches.default;
  let res = await cache.match(url);
  if (!res) {
    res = await fetch(url, { cf: { cacheTtl: 300, cacheEverything: true } });
    if (!res.ok) return null;
    res = new Response(res.body, res);
    res.headers.set('Cache-Control', 'max-age=300');
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

공통 규율(두 채점기가 같은 목소리를 내도록 여기서 못박는다):
- **어투: 채점 서술은 명사형·음슴체로 통일한다.** 평가·판단은 "~했음 / ~처리함 /
  ~누락됨 / ~부족함 / ~없음"으로, 학생에게 시키는 말은 "~할 것"으로 끝낸다.
  "~이다 / ~하였다 / ~하라" 같은 평서체·명령형이나 존댓말을 섞지 마라 — 같은 앱에서
  문항마다 말투가 달라지면 채점표가 아니라 사람이 기분 따라 쓴 글처럼 읽힌다.
  **다만 판례·법리·조문의 내용 자체는 평서체("~이다 / ~하여야 한다 / ~에 해당한다")로 쓴다.**
  법리는 시험장에서 그 문장 그대로 적어야 하는 것이라, 채점자의 말투로 변형하면
  외울 문장이 망가진다. 세 가지가 한 항목 안에서 섞여도 된다:
  · 법리(평서체): "백색실선은 통행금지를 내용으로 하는 안전표지에 해당하지 않는다."
  · 평가(음슴체): "위 법리는 적었으나 사안에 대입하지 않아 포섭이 누락됨."
  · 지시(할 것):  "이율이 나오면 제한최고이율 초과 여부부터 검토할 것."
- **득점은 정수 하나로 적는다.** "0~1" 같은 범위, "최소한의 배려로 1점" 같은 온정
  가점을 주지 마라. 표의 득점 합계와 마지막 [[SCORE:n]]이 반드시 일치해야 한다.
- **판례번호·조문번호는 위에 주어진 채점 근거(기준표·모범답안·해설·문제)에 있는 것만
  인용한다.** 근거에 없는데 기억나는 판례를 덧붙이지 마라. 법리만 서술하고 번호는 생략한다.
  틀린 번호를 외우게 하는 것이 안 알려주는 것보다 훨씬 해롭다.
  **반대로 근거에 번호가 있으면 반드시 꺼내 적는다.** 기준표는 사건번호를 각주에 두는
  일이 많다 — 본문에 안 보인다고 없는 것으로 치지 말고 각주까지 훑는다. 번호를 빼고
  법리만 주면 그 쟁점을 다시 찾아볼 수가 없다.
- **적용 법령은 문제의 사실관계 시점을 기준으로 판단한다.** 이율·요건이 그 뒤 개정됐다면
  개정 전 기준으로 채점하고, 헷갈릴 소지가 있으면 그 사실을 한 줄로 밝힌다.
- 답안이 통째로 부실하면 "잘한 점"에 억지로 채우지 말고 "없음 — (한 줄 이유)"라고 적어라.
  점수로 이어지지 않는 칭찬은 학습에 도움이 되지 않는다.
- **채점할 문항 몫만 채점한다.** 기준표·모범답안·해설·문제 전문에는 다른 문항 몫이 함께
  들어 있을 수 있고, 거기 붙은 번호("문제 1", "1)-①")가 위에 적힌 문항 표시와 다를 수 있다.
  설문 내용으로 이 문항에 해당하는 부분을 찾아, 표·첨삭·놓친 쟁점을 그 배점 항목으로만 채운다.
- **세부 배점은 근거에 있는 그대로 쓴다.** 근거(모범답안·해설 등)에 항목별 배점이 없어 표의 배점을
  직접 나눠야 하면, 표 바로 위에 "※ 근거에 세부 배점이 없어 쟁점 비중으로 나눈 추정 배점임"라고
  한 줄로 밝힌다. 근거에 이미 배점이 매겨진 항목을 더 잘게 쪼개 표 행을 만들지 않는다(예: 기준표의 "Ⅲ. 15점"을
  3·6·6점으로 나누지 마라). 그 밖의 자리에서도 쪼갠 점수("6점 상당")를 만들지 않고,
  "다음에 고칠 것"의 점수는 표의 항목 배점 안에서 "약 n점"으로 적는다.
- **낫표(「 」)는 학생 답안을 인용할 때만 쓴다.** 화면이 낫표 안을 학생 문장 모양으로 그리므로,
  기준표 문구·체크리스트·공식·고쳐 쓸 문장·강조할 낱말은 큰따옴표("")로 쓰거나 따옴표 없이 쓴다.
- **근거에 없는 판례·조문을 "존재하지 않는다"고 단정하지 마라.** 확인할 수 있는 것은 근거와의
  일치 여부뿐이다 — "기준표(모범답안)의 판례와 다름" 또는 "근거에서 확인되지 않음"으로 적는다.


출력 형식(마크다운):

## 쟁점별 채점
| 쟁점 | 배점 | 득점 | 감점 근거 |
각 행은 채점기준표의 항목을 따른다. "감점 근거" 칸에는 **무엇을 안 써서 몇 점이
깎였는지**를 적는다("법리는 썼으나 포섭 없음 −2, 결론 오류 −1"). 만점인 행은
"만점"이라고만 적는다. 이 칸의 감점과 "첨삭"의 꼬리표 감점이 서로 어긋나면 안 된다.

## 첨삭
답안 문장에 직접 빨간 펜을 대듯 고쳐 준다. **이 절이 이 채점의 핵심이다.**
강의실에서 교수가 답안지를 들고 한 줄씩 짚어 주듯, 무엇이 왜 문제인지·기준표가
그 자리에서 무엇을 요구하는지·몇 점이 깎이는지를 모두 적는다. 형식은 항목마다
아래 다섯 줄이며, 셋째·넷째 줄은 해당하는 것이 없으면 건너뛴다:

> 「(학생이 쓴 문장을 그대로)」
> ~~틀린 부분~~ → **고쳐 쓸 말**
> **기준표** "(기준표·모범답안이 이 자리에서 요구하는 문구)" (배점 n점) — 감점 근거 한 줄
> **판례** 대법원 2024. 6. 20. 선고 2022도12175 판결 — (법리를 시험장에서 쓸 문장 그대로)
> [결론 오류 −3점] 무엇이 왜 틀렸는지 한두 문장.

- **꼬리표에 감점을 붙인다.** "[결론 오류 −3점]"처럼 사유 뒤에 한 칸 띄고 "−n점"을 적는다.
  감점이 그 항목 배점 전부인 경우도, 깎이지 않은 [좋음]도 같은 형식으로 적는다
  ([좋음]은 "+n점" 또는 "감점 없음"). **각 항목 감점의 합은 "쟁점별 채점" 표에서
  그 쟁점이 잃은 점수와 맞아야 한다.**
- **"기준표" 줄은 위에 주어진 근거에 실제로 있는 문구만 옮긴다.** 근거에 그 항목의
  세부 배점이 없으면 배점 괄호를 생략하고 문구만 적는다. 배점을 지어내지 마라.
- **"판례" 줄에는 들어갔어야 할 판례의 사건번호를 반드시 함께 적는다.** "대법원 2024. 6. 20.
  선고 2022도12175 판결" 형태로 쓰고, 이어서 "—" 뒤에 법리를 붙인다. 헌재 결정은
  "헌재 2019. 4. 11. 2017헌바127", 조문이 근거면 "형사소송법 제312조 제3항"처럼
  조·항·호까지 적는다. 번호를 아는 것이 공부의 절반이라 법리만 주면 반쪽짜리다.
- **번호는 위에 주어진 채점 근거에서 찾는다.** 기준표·모범답안은 사건번호를 **각주**에
  두는 일이 아주 많으니 본문만 보고 "번호가 없다"고 단정하지 마라 — 각주까지 훑어본다.
- **근거 어디에도 번호가 없으면 비워 둔다.** 기억나는 번호를 지어내 붙이지 마라.
  그때는 "**판례** (근거에 사건번호 없음) — 법리"로 적는다. 틀린 번호를 외우게 하는 것이
  안 알려주는 것보다 훨씬 해롭다.
- **근거에 판례도 조문도 없으면 "판례" 줄을 통째로 뺀다.**
- **어투:** "기준표"·"판례" 줄의 법리 문장은 평서체 그대로 옮기고, 꼬리표 뒤 설명은 음슴체.

**대괄호 안에는 사유 이름과 감점만 넣는다.** "[사유] 결론 오류 —"처럼 쓰지 마라 —
화면이 대괄호 안을 그대로 꼬리표로 찍기 때문에 "사유"라는 쓸모없는 딱지가 붙는다.

답안에 아예 없어서 인용할 문장이 없는 논점은 첫 줄을 이렇게 쓴다:
> 「(누락) 이자제한법 적용」
그다음 줄은 화살표 없이 고쳐 쓸 말만 적고, 나머지 줄은 위와 같다.

사유 이름은 다음 중에서 고른다(해당하는 것이 없으면 직접 적는다):
- **판례 근거 부족** — 결론은 맞으나 근거 판례를 대지 않았다
- **판례 오기** — 판례의 취지·사건번호·결론을 잘못 적었다
- **조문 오기** — 조·항·호가 틀렸거나 다른 법률을 들었다
- **정확성 부족** — 뉘앙스는 맞지만 요건·효과의 표현이 두루뭉술하다
- **누락** — 써야 할 법리·논거·요건을 빠뜨렸다
- **포섭 누락** — 법리는 썼으나 사안의 사실에 대입하지 않았다(법리·논거 자체를 빠뜨린 것은 "누락")
- **논리 비약** — 앞 문장에서 결론이 바로 도출되지 않는다
- **결론 오류** — 결론 자체가 틀렸다
- **불필요** — 배점에 없는 내용이라 시간만 쓴 부분. 그 안에 법리 오류가 있으면 함께 짚는다

지켜야 할 것:
- **답안에 실제로 있는 문장만 인용한다.** 없는 문장을 지어내 첨삭하지 마라. 인용은 답안의 글자를
  그대로 옮긴다 — 목차 제목과 본문을 한 줄로 합치거나 "—"·말줄임표 같은 기호를 끼워 넣지 마라.
- 고칠 곳이 많으면 **점수에 영향이 큰 것부터 최대 8개**만 고른다. 사소한 표현은 넘긴다.
- 잘 쓴 문장에도 첨삭을 단다 — 그때는 사유 자리에 [좋음]을 쓰고 왜 점수를 받았는지 한 줄.
  **한 문항에 하나 이상은 넣는다.** 어디가 점수가 됐는지 모르면 다음에 그것까지 버린다.
- 답안이 한두 줄뿐이라 첨삭할 문장 자체가 없으면 "첨삭할 문장이 없음 — (한 줄 이유)"라고만 적는다.

## 잘한 점
항목마다 한 줄 목록으로 쓴다: 줄 머리에 '- ', 이어서 낫표로 감싼 답안 문장 그대로, 그 뒤에 ' — 왜 잘했는지'. 인용 블록(>)은 쓰지 않는다(첨삭 카드로 그려진다).

## 놓친 쟁점
답안에 없는 것 중 기준표에 있는 것. 항목마다 **(1) 잃은 점수, (2) 근거 판례의 사건번호,
(3) 시험장에서 그대로 쓸 수 있는 모범 문장**을 적는다. 모범 문장은 요약하지 말고 답안에
옮겨 적을 수 있는 완성된 문장으로 쓴다 — 이 절이 다음 답안의 재료가 된다. 사건번호는
"첨삭"에서와 같은 규칙으로 근거(각주 포함)에서 찾아 적고, 없으면 비운다.
형식은 "- **쟁점 이름** (−n점) — 대법원 2024. 6. 20. 선고 2022도12175 판결. 모범 문장(평서체)."

## 다음에 고칠 것
가장 점수를 많이 올릴 수 있는 것부터 최대 3개.


"## 다음에 고칠 것"의 각 항목은 **다음 답안에서 바로 쓸 수 있는 형태**여야 한다:
- 무엇을 놓쳤는지가 아니라 **어떤 신호를 보면 무엇을 떠올려야 하는지**를 적는다.
  (예: "이율이 나오면 제한최고이율 초과 여부부터 검토할 것 — 월 5%처럼 비상식적으로 높은
  이율은 출제자가 이자제한법을 묻겠다는 신호임")
- 가능하면 **한 줄 공식·체크리스트**로 압축한다.
  (예: "선이자 공제 → 실제 수령액을 원본으로 → 초과분은 약정원본에 충당")
- 그 항목을 고쳤을 때 **몇 점을 더 받을 수 있었는지**를 함께 적는다.

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

공통 규율(두 채점기가 같은 목소리를 내도록 여기서 못박는다):
- **어투: 채점 서술은 명사형·음슴체로 통일한다.** 평가·판단은 "~했음 / ~처리함 /
  ~누락됨 / ~부족함 / ~없음"으로, 학생에게 시키는 말은 "~할 것"으로 끝낸다.
  "~이다 / ~하였다 / ~하라" 같은 평서체·명령형이나 존댓말을 섞지 마라 — 같은 앱에서
  문항마다 말투가 달라지면 채점표가 아니라 사람이 기분 따라 쓴 글처럼 읽힌다.
  **다만 판례·법리·조문의 내용 자체는 평서체("~이다 / ~하여야 한다 / ~에 해당한다")로 쓴다.**
  법리는 시험장에서 그 문장 그대로 적어야 하는 것이라, 채점자의 말투로 변형하면
  외울 문장이 망가진다. 세 가지가 한 항목 안에서 섞여도 된다:
  · 법리(평서체): "백색실선은 통행금지를 내용으로 하는 안전표지에 해당하지 않는다."
  · 평가(음슴체): "위 법리는 적었으나 사안에 대입하지 않아 포섭이 누락됨."
  · 지시(할 것):  "이율이 나오면 제한최고이율 초과 여부부터 검토할 것."
- **득점은 정수 하나로 적는다.** "0~1" 같은 범위, "최소한의 배려로 1점" 같은 온정
  가점을 주지 마라. 표의 득점 합계와 마지막 [[SCORE:n]]이 반드시 일치해야 한다.
- **판례번호·조문번호는 위에 주어진 채점 근거(기준표·모범답안·해설·문제)에 있는 것만
  인용한다.** 근거에 없는데 기억나는 판례를 덧붙이지 마라. 법리만 서술하고 번호는 생략한다.
  틀린 번호를 외우게 하는 것이 안 알려주는 것보다 훨씬 해롭다.
  **반대로 근거에 번호가 있으면 반드시 꺼내 적는다.** 기준표는 사건번호를 각주에 두는
  일이 많다 — 본문에 안 보인다고 없는 것으로 치지 말고 각주까지 훑는다. 번호를 빼고
  법리만 주면 그 쟁점을 다시 찾아볼 수가 없다.
- **사건 기록 전문은 한글 파일에서 뽑아 표(임료 확인서·계산표·등기부 표 등)가 빠져 있을 수 있다.**
  금액·날짜·비율이 기록에서 안 보이면 해설·모범답안의 수치를 따르고, 둘 다에 없으면 수치를 지어내지
  말고 "기록에서 확인되지 않음"이라고 적어라. **법리 판단이 해설·모범답안과 갈리면 해설을 따른다** —
  네 판단이 더 낫다고 보더라도 감점 근거로 쓰지 말고, 필요하면 한 줄 참고로만 덧붙여라.
- **적용 법령은 문제의 사실관계 시점을 기준으로 판단한다.** 이율·요건이 그 뒤 개정됐다면
  개정 전 기준으로 채점하고, 헷갈릴 소지가 있으면 그 사실을 한 줄로 밝힌다.
- 답안이 통째로 부실하면 "잘한 점"에 억지로 채우지 말고 "없음 — (한 줄 이유)"라고 적어라.
  점수로 이어지지 않는 칭찬은 학습에 도움이 되지 않는다.
- **채점할 문항 몫만 채점한다.** 기준표·모범답안·해설·문제 전문에는 다른 문항 몫이 함께
  들어 있을 수 있고, 거기 붙은 번호("문제 1", "1)-①")가 위에 적힌 문항 표시와 다를 수 있다.
  설문 내용으로 이 문항에 해당하는 부분을 찾아, 표·첨삭·놓친 쟁점을 그 배점 항목으로만 채운다.
- **세부 배점은 근거에 있는 그대로 쓴다.** 근거(모범답안·해설 등)에 항목별 배점이 없어 표의 배점을
  직접 나눠야 하면, 표 바로 위에 "※ 근거에 세부 배점이 없어 쟁점 비중으로 나눈 추정 배점임"라고
  한 줄로 밝힌다. 근거에 이미 배점이 매겨진 항목을 더 잘게 쪼개 표 행을 만들지 않는다(예: 기준표의 "Ⅲ. 15점"을
  3·6·6점으로 나누지 마라). 그 밖의 자리에서도 쪼갠 점수("6점 상당")를 만들지 않고,
  "다음에 고칠 것"의 점수는 표의 항목 배점 안에서 "약 n점"으로 적는다.
- **낫표(「 」)는 학생 답안을 인용할 때만 쓴다.** 화면이 낫표 안을 학생 문장 모양으로 그리므로,
  기준표 문구·체크리스트·공식·고쳐 쓸 문장·강조할 낱말은 큰따옴표("")로 쓰거나 따옴표 없이 쓴다.
- **근거에 없는 판례·조문을 "존재하지 않는다"고 단정하지 마라.** 확인할 수 있는 것은 근거와의
  일치 여부뿐이다 — "기준표(모범답안)의 판례와 다름" 또는 "근거에서 확인되지 않음"으로 적는다.

출력 형식(마크다운):

## 양식·형식
서면 종류에 맞는 필수 기재사항의 충족 여부. 청구취지(주문)가 있으면 문구 단위 평가.

## 쟁점별 채점
| 쟁점 | 배점 | 득점 | 평가 |
채점기준표의 항목을 따른다. 기준표가 없으면 해설의 쟁점 순서를 따른다.

## 첨삭
답안 문장에 직접 빨간 펜을 대듯 고쳐 준다. **이 절이 이 채점의 핵심이다.**
강의실에서 교수가 답안지를 들고 한 줄씩 짚어 주듯, 무엇이 왜 문제인지·기준표가
그 자리에서 무엇을 요구하는지·몇 점이 깎이는지를 모두 적는다. 형식은 항목마다
아래 다섯 줄이며, 셋째·넷째 줄은 해당하는 것이 없으면 건너뛴다:

> 「(학생이 쓴 문장을 그대로)」
> ~~틀린 부분~~ → **고쳐 쓸 말**
> **기준표** "(기준표·모범답안이 이 자리에서 요구하는 문구)" (배점 n점) — 감점 근거 한 줄
> **판례** 대법원 2024. 6. 20. 선고 2022도12175 판결 — (법리를 시험장에서 쓸 문장 그대로)
> [결론 오류 −3점] 무엇이 왜 틀렸는지 한두 문장.

- **꼬리표에 감점을 붙인다.** "[결론 오류 −3점]"처럼 사유 뒤에 한 칸 띄고 "−n점"을 적는다.
  감점이 그 항목 배점 전부인 경우도, 깎이지 않은 [좋음]도 같은 형식으로 적는다
  ([좋음]은 "+n점" 또는 "감점 없음"). **각 항목 감점의 합은 "쟁점별 채점" 표에서
  그 쟁점이 잃은 점수와 맞아야 한다.**
- **"기준표" 줄은 위에 주어진 근거에 실제로 있는 문구만 옮긴다.** 근거에 그 항목의
  세부 배점이 없으면 배점 괄호를 생략하고 문구만 적는다. 배점을 지어내지 마라.
- **"판례" 줄에는 들어갔어야 할 판례의 사건번호를 반드시 함께 적는다.** "대법원 2024. 6. 20.
  선고 2022도12175 판결" 형태로 쓰고, 이어서 "—" 뒤에 법리를 붙인다. 헌재 결정은
  "헌재 2019. 4. 11. 2017헌바127", 조문이 근거면 "형사소송법 제312조 제3항"처럼
  조·항·호까지 적는다. 번호를 아는 것이 공부의 절반이라 법리만 주면 반쪽짜리다.
- **번호는 위에 주어진 채점 근거에서 찾는다.** 기준표·모범답안은 사건번호를 **각주**에
  두는 일이 아주 많으니 본문만 보고 "번호가 없다"고 단정하지 마라 — 각주까지 훑어본다.
- **근거 어디에도 번호가 없으면 비워 둔다.** 기억나는 번호를 지어내 붙이지 마라.
  그때는 "**판례** (근거에 사건번호 없음) — 법리"로 적는다. 틀린 번호를 외우게 하는 것이
  안 알려주는 것보다 훨씬 해롭다.
- **근거에 판례도 조문도 없으면 "판례" 줄을 통째로 뺀다.**
- **어투:** "기준표"·"판례" 줄의 법리 문장은 평서체 그대로 옮기고, 꼬리표 뒤 설명은 음슴체.

**대괄호 안에는 사유 이름과 감점만 넣는다.** "[사유] 결론 오류 —"처럼 쓰지 마라 —
화면이 대괄호 안을 그대로 꼬리표로 찍기 때문에 "사유"라는 쓸모없는 딱지가 붙는다.

답안에 아예 없어서 인용할 문장이 없는 논점은 첫 줄을 이렇게 쓴다:
> 「(누락) 이자제한법 적용」
그다음 줄은 화살표 없이 고쳐 쓸 말만 적고, 나머지 줄은 위와 같다.

사유 이름은 다음 중에서 고른다(해당하는 것이 없으면 직접 적는다):
- **판례 근거 부족** — 결론은 맞으나 근거 판례를 대지 않았다
- **판례 오기** — 판례의 취지·사건번호·결론을 잘못 적었다
- **조문 오기** — 조·항·호가 틀렸거나 다른 법률을 들었다
- **정확성 부족** — 뉘앙스는 맞지만 요건·효과의 표현이 두루뭉술하다
- **누락** — 써야 할 법리·논거·요건을 빠뜨렸다
- **포섭 누락** — 법리는 썼으나 사안의 사실에 대입하지 않았다(법리·논거 자체를 빠뜨린 것은 "누락")
- **논리 비약** — 앞 문장에서 결론이 바로 도출되지 않는다
- **결론 오류** — 결론 자체가 틀렸다
- **불필요** — 배점에 없는 내용이라 시간만 쓴 부분. 그 안에 법리 오류가 있으면 함께 짚는다

지켜야 할 것:
- **답안에 실제로 있는 문장만 인용한다.** 없는 문장을 지어내 첨삭하지 마라. 인용은 답안의 글자를
  그대로 옮긴다 — 목차 제목과 본문을 한 줄로 합치거나 "—"·말줄임표 같은 기호를 끼워 넣지 마라.
- 고칠 곳이 많으면 **점수에 영향이 큰 것부터 최대 8개**만 고른다. 사소한 표현은 넘긴다.
- 잘 쓴 문장에도 첨삭을 단다 — 그때는 사유 자리에 [좋음]을 쓰고 왜 점수를 받았는지 한 줄.
  **한 문항에 하나 이상은 넣는다.** 어디가 점수가 됐는지 모르면 다음에 그것까지 버린다.
- 답안이 한두 줄뿐이라 첨삭할 문장 자체가 없으면 "첨삭할 문장이 없음 — (한 줄 이유)"라고만 적는다.

## 잘한 점
항목마다 한 줄 목록으로 쓴다: 줄 머리에 '- ', 이어서 낫표로 감싼 답안 문장 그대로, 그 뒤에 ' — 왜 잘했는지'. 인용 블록(>)은 쓰지 않는다(첨삭 카드로 그려진다).

## 놓친 것
답안에 없는 것 중 기준표(해설)에 있는 것. 항목마다 **(1) 잃은 점수, (2) 근거 판례의
사건번호, (3) 시험장에서 그대로 쓸 수 있는 모범 문장**을 적는다. 모범 문장은 요약하지
말고 답안에 옮겨 적을 수 있는 완성된 문장으로 쓴다 — 이 절이 다음 답안의 재료가 된다.
사건번호는 "첨삭"에서와 같은 규칙으로 근거(각주 포함)에서 찾아 적고, 없으면 비운다.
형식은 "- **쟁점 이름** (−n점) — 대법원 2024. 6. 20. 선고 2022도12175 판결. 모범 문장(평서체)."

## 다음에 고칠 것
가장 점수를 많이 올릴 수 있는 것부터 최대 3개.


"## 다음에 고칠 것"의 각 항목은 **다음 답안에서 바로 쓸 수 있는 형태**여야 한다:
- 무엇을 놓쳤는지가 아니라 **어떤 신호를 보면 무엇을 떠올려야 하는지**를 적는다.
  (예: "이율이 나오면 제한최고이율 초과 여부부터 검토할 것 — 월 5%처럼 비상식적으로 높은
  이율은 출제자가 이자제한법을 묻겠다는 신호임")
- 가능하면 **한 줄 공식·체크리스트**로 압축한다.
  (예: "선이자 공제 → 실제 수령액을 원본으로 → 초과분은 약정원본에 충당")
- 그 항목을 고쳤을 때 **몇 점을 더 받을 수 있었는지**를 함께 적는다.

마지막 줄에 반드시 아래 형식으로 총점만 적는다(다른 말 없이):
[[SCORE:정수]]`;

/** 기록형 채점 근거: 기준표가 정본, 없으면 해설. 둘 다 없으면 그 사실을 밝힌다. */
// 해설서 앞에 문제·기록이 다시 실려 있으면 떼어 낸다(정연석 민사 앞 3만 자, 노수환 형사 앞 4만 자).
// 그 경계는 RECORD/pipeline/mark_answer_span.js 가 회차마다 미리 재어 answerAt 에 적어 둔다 —
// 스캔 OCR 이라 표제로는 못 찾고, 문제 전문과 겹치는 구간을 세어야 잡힌다.
// answerAt 이 없는(오래된) 데이터는 쪽 머리 "…해설〉"로라도 잘라 본다.
function commentaryBody(c) {
  const text = c.text || '';
  if (Number.isInteger(c.answerAt) && c.answerAt > 0 && c.answerAt < text.length) {
    return text.slice(c.answerAt);
  }
  const i = text.search(/해\s*설\s*〉/);
  if (i <= 0) return text;
  const head = text.lastIndexOf('〈', i);
  return text.slice(head >= 0 ? head : i);
}

function buildRecordPrompt(exam, task, answer) {
  const parts = [];
  parts.push(`# 시험\n${exam.label}`);
  // 서면별 배점은 RECORD/pipeline/fill_task_points.js 가 원문에서 확정해 둔다(민사 소장 175 등).
  // 서면이 여럿인데 배점이 비었으면 근거가 없어 비워 둔 회차다 — 100점 환산이라는 사실을 밝히게 한다.
  const others = (exam.tasks || []).length > 1;
  parts.push(`# 채점할 서면\n${task.title}` +
    (task.points > 0 ? ` (배점 ${task.points}점)`
      : others ? ' (서면별 배점 미공개 — 기록형 만점을 여러 서면이 나누는데 이 서면 몫이 확인되지 않았다. ' +
          '100점 만점으로 환산해 채점하고, 출력 맨 첫 줄(첫 ## 제목보다 위)에 "서면별 배점이 공개되지 않아 100점 환산으로 평가한 결과"임을 한 줄로 밝혀라)'
      : ' (배점 미표시 — 100점 만점으로 채점한다)'));
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
      const t = commentaryBody(c).slice(0, budget);
      budget -= t.length;
      chunks.push(`[${c.author} — ${c.title}]\n${t}`);
    }
    parts.push(`# 해설 (공식 채점기준표가 없어 해설서를 기준으로 삼는다)\n${chunks.join('\n\n---\n\n')}`);
  } else {
    parts.push(
      `# 채점 근거 없음\n이 회차는 채점기준표도 해설도 확보되지 않았다. ` +
        `해당 서면의 일반적 작성 기준(양식·요건사실·기록 인용의 완결성)으로 평가하고, ` +
        `출력 맨 첫 줄(첫 ## 제목보다 위)에 "공식 채점기준 없이 평가한 결과"임을 한 줄로 밝혀라.`,
    );
  }

  // 답안만 떼어 돌려준다 — 앞부분(문제·채점기준)은 회차마다 고정이라 캐시 대상이다.
  return { basis: parts.join('\n\n'), answer: `# 수험생 답안(${task.title})\n${answer}` };
}

/**
 * 문항별로 잘라 둔 채점 근거(pipeline/scripts/slice_basis.js 가 만든다).
 * sig 가 지금 데이터와 다르면(데이터를 다시 만들고 자르기를 안 돌렸으면) null — 전체를 쓴다.
 * 반환: { rubric } | { answers } | null
 * (casebookText 는 잘라 낸 본문 한 조각을 답안 하나처럼 돌려준다)
 */
function slicedBasis(exam, group) {
  const bs = group.basisSlice;
  if (!bs) return null;
  if (bs.src === 'rubric' && exam.rubricText && bs.sig === exam.rubricText.length
      && Array.isArray(bs.ranges) && bs.ranges.length) {
    return { rubric: bs.ranges.map(([a, b]) => exam.rubricText.slice(a, b)).join('\n\n…\n\n') };
  }
  // 답안이 회차당 한 덩어리인 사례집(로사정·박승수)은 본문 안의 「〈문제 1〉」「[설문 (1)」
  // 표지 자리로 잘라 둔다 — 머리글이 회차 이름뿐이라 답안 단위로는 나눌 수 없다.
  if (bs.src === 'casebookText' && !exam.rubricText && exam.casebookAnswers?.length
      && bs.sig === exam.casebookAnswers.map((x) => (x.answerText || '').length).join(',')
      && exam.casebookAnswers[bs.ai] && Array.isArray(bs.ranges) && bs.ranges.length) {
    const a = exam.casebookAnswers[bs.ai];
    const text = bs.ranges.map(([x, y]) => (a.answerText || '').slice(x, y)).join('\n\n…\n\n');
    return { answers: [{ header: a.header, answerText: text }] };
  }
  if (bs.src === 'casebook' && !exam.rubricText && exam.casebookAnswers?.length
      && bs.sig === exam.casebookAnswers.map((x) => (x.answerText || '').length).join(',')
      && Array.isArray(bs.idx) && bs.idx.every((i) => exam.casebookAnswers[i])) {
    return { answers: bs.idx.map((i) => exam.casebookAnswers[i]) };
  }
  return null;
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
  else {
    // 선택과목 모의 5회차는 원본이 과목별로 나뉘지 않은 통합 파일에만 있어 지문을 확보하지 못했다.
    // 지문 없이 채점하면 모델이 사실관계를 지어내 포섭을 평가할 수 있다.
    parts.push(
      `# 문제 지문 없음\n이 회차는 문제 지문(사실관계)이 확보되지 않았다. 사실관계를 추측해 채우지 마라. ` +
        `포섭은 설문과 채점 근거에 드러난 사실로만 평가하고, 출력 맨 첫 줄(첫 ## 제목보다 위)에 ` +
        `"문제 지문 없이 설문·채점기준표만으로 평가한 결과"임을 한 줄로 밝혀라.`,
    );
  }

  // 채점 근거는 기준표가 정본, 없으면 사례집 모범답안으로 대신한다.
  // 문항별로 잘라 둔 조각이 있으면 그것만 보낸다 — 문항 하나 채점에 회차 전체 근거(형사 변시
  // 14회는 11만 자)를 보내던 것이 비용의 대부분이었다. 문제 전문은 공통 사실관계 때문에 통째로 둔다.
  const cut = slicedBasis(exam, group);
  if (cut?.rubric) {
    parts.push(`# 채점기준표 (이 문항에 해당하는 부분만 발췌)\n${cut.rubric}`);
  } else if (cut?.answers && !cut.answers.length) {
    // 사례집에 이 문항의 답안이 아예 없다(민사 변시 제3문 상법 등). 예전엔 다른 문항의
    // 모범답안을 근거로 채점하고 있었다.
    parts.push(
      `# 채점 근거 없음\n사례집에 이 문항의 모범답안이 실려 있지 않다. ` +
        `일반적인 사례형 작성 기준(법리·포섭·결론의 완결성)으로 평가하고, ` +
        `출력 맨 첫 줄(첫 ## 제목보다 위)에 "공식 채점기준표·모범답안 없이 평가한 결과"임을 한 줄로 밝혀라.`,
    );
  } else if (exam.rubricText) {
    parts.push(`# 채점기준표\n${exam.rubricText}`);
  } else if (exam.casebookAnswers?.length) {
    // 데이터의 본문 필드는 `answerText` 다. 예전에 `a.text` 만 보다가 undefined 가
    // 되어, 채점기준표가 없는 494건(변시 30 + 창작문제 464)에서 모범답안이
    // "[object Object]" 로 들어가고 있었다. `header` 에 문항 라벨이 있으니 같이 준다.
    const model = (cut?.answers || exam.casebookAnswers)
      .map((a) => (typeof a === 'string' ? a
        : [a.header, a.answerText || a.text].filter(Boolean).join('\n')))
      .filter(Boolean)
      .join('\n\n---\n\n');
    parts.push(
      `# 모범답안 (공식 채점기준표가 없어 사례집 모범답안을 기준으로 삼는다` +
        (cut?.answers ? ' — 이 문항이 속한 문의 답안만 발췌했다. 같은 문의 다른 설문 몫이 섞여 있을 수 있다' : '') +
        `)\n${model}`,
    );
  } else {
    parts.push(
      `# 채점 근거 없음\n이 회차는 채점기준표도 모범답안도 확보되지 않았다. ` +
        `일반적인 사례형 작성 기준(법리·포섭·결론의 완결성)으로 평가하고, ` +
        `출력 맨 첫 줄(첫 ## 제목보다 위)에 "공식 채점기준표 없이 평가한 결과"임을 한 줄로 밝혀라.`,
    );
  }

  // 답안만 떼어 돌려준다 — 앞부분(문제·채점기준)은 회차마다 고정이라 캐시 대상이다.
  return { basis: parts.join('\n\n'), answer: `# 수험생 답안\n${answer}` };
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

    // 의견함은 채점과 길이 다르다 — 받는 방식(GET·PATCH)도, 필요한 것(API 키 없음)도 다르다.
    const fbPath = new URL(request.url).pathname.replace(/\/+$/, '');
    const isFeedback = fbPath === '/feedback' || fbPath === '/feedback/push';

    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: cors(origin, isFeedback ? FEEDBACK_ORIGINS : ALLOWED_ORIGINS),
      });
    }
    if (fbPath === '/feedback/push') return handlePushSubscribe(request, env, origin);
    if (isFeedback) return handleFeedback(request, env, origin, (p) => ctx.waitUntil(p));
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

    const { subject, examId, groupKey, taskNo, answer, dry } = body || {};
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

    // 점검용: 모델을 부르지 않고 무엇을 보낼지만 알려준다(글자 수만 — 근거 본문은 돌려주지 않는다).
    // 근거 자르기가 실제로 적용되는지 돈 들이지 않고 확인하려고 둔다.
    if (dry === true) {
      const g = mode === '기록' ? null : (exam.groups || []).find((x) => x.key === groupKey);
      const cut = g ? slicedBasis(exam, g) : null;
      return new Response(JSON.stringify({
        mode, sliced: !!cut, noBasis: !!(cut?.answers && !cut.answers.length),
        systemChars: system.length, basisChars: prompt.basis.length, answerChars: prompt.answer.length,
      }), { headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(origin) } });
    }

    // 돈 한도. 넘으면 채점을 받지 않는다(설정이 없으면 하루 $5 / 한 달 $50).
    const capDay = Number(env.DAILY_USD ?? 5);
    const capMonth = Number(env.MONTHLY_USD ?? 50);
    const spent = await spentSoFar(env);
    if (spent && (spent.today >= capDay || spent.month >= capMonth)) {
      const which = spent.today >= capDay
        ? `오늘 채점에 쓴 금액이 한도($${capDay})에 닿았습니다 — 지금까지 $${spent.today.toFixed(2)}`
        : `이번 달 채점에 쓴 금액이 한도($${capMonth})에 닿았습니다 — 지금까지 $${spent.month.toFixed(2)}`;
      return bad(429, `${which}. 한도를 올리려면 worker/wrangler.toml 의 DAILY_USD·MONTHLY_USD 를 고치고 다시 배포하세요.`, origin);
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
    const log = {
      mode, subject, examId, unit: mode === '기록' ? String(taskNo) : groupKey,
      answerChars: answer.length,
      sliced: mode === '사례' && !!slicedBasis(exam, (exam.groups || []).find((x) => x.key === groupKey)),
      ipHash: await hashIp(request.headers.get('CF-Connecting-IP') || 'unknown'),
      status: 'error', usage: null,
    };
    let ms;
    const stream = new ReadableStream({
      async start(controller) {
        const send = (obj) =>
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
        try {
          ms = client.messages.stream({
            model: 'claude-opus-5',
            max_tokens: MAX_TOKENS[mode],
            output_config: { effort: env.GRADE_EFFORT || 'high' },
            // 채점 지침은 모든 호출에서 같다 — 캐시에 얹어 매번 다시 읽히지 않게 한다.
            system: [{ type: 'text', text: system, cache_control: { type: 'ephemeral' } }],
            // 프롬프트를 둘로 나눈다: 앞쪽(문제·채점기준표)은 같은 회차를 다시 채점하거나
            // 다음 문항을 채점할 때 그대로 재사용되므로 캐시하고, 답안만 새로 읽힌다.
            // 기록형은 문제+기준표가 1만 토큰을 넘어 이 차이가 크다.
            messages: [{
              role: 'user',
              content: [
                { type: 'text', text: prompt.basis, cache_control: { type: 'ephemeral' } },
                { type: 'text', text: prompt.answer },
              ],
            }],
          });

          let wrote = false;
          for await (const ev of ms) {
            if (ev.type === 'content_block_delta' && ev.delta.type === 'text_delta') {
              wrote = true;
              send({ t: ev.delta.text });
            }
          }

          const final = await ms.finalMessage();
          log.usage = final.usage;
          log.status = final.stop_reason === 'refusal' || final.stop_reason === 'max_tokens'
            ? final.stop_reason : 'ok';
          if (final.stop_reason === 'refusal') {
            send({ error: '채점을 완료하지 못했습니다. 답안 내용을 확인해 주세요.' });
          } else if (final.stop_reason === 'max_tokens') {
            send({ error: wrote
              ? '피드백이 길어 중간에 끊겼습니다. 답안을 나눠서 채점해 주세요.'
              : '채점 검토가 길어져 결과를 쓰기 전에 끊겼습니다. 잠시 후 다시 시도해 주세요.' });
          }
          send({ done: true, usage: final.usage });
        } catch (e) {
          // 도중에 끊겨도 이미 쓴 토큰은 청구된다. 받은 데까지의 사용량이라도 남긴다
          // (출력 토큰 집계는 끝에 오므로 끊긴 건은 실제보다 적게 찍힐 수 있다).
          if (!log.usage) {
            log.usage = ms?.currentMessage?.usage || null;
            log.status = e?.name === 'TypeError' ? 'aborted' : 'error';
          }
          // API 쪽에서 막힌 것인지 이쪽 잘못인지 나중에 가리려면 요청 ID가 있어야
          // 한다. Anthropic 지원에 문의할 때 이것부터 묻는다.
          const id = e?.request_id || e?.headers?.['request-id'];
          console.error('grade failed',
            { status: e?.status, colo, request_id: id, msg: e?.message });
          // 요청 ID 는 Anthropic 에 문의할 때 필요하지만 화면에서는 군더더기다.
          // 원인이 계정·혼잡처럼 분명한 경우에는 붙이지 않는다.
          const known = /credit balance|authentication|invalid x-api-key|rate.?limit|overloaded/i
            .test(String(e?.message || '')) || e?.status === 403 || e?.status === 429;
          send({ error: friendlyError(e, colo) + (id && !known ? ` (요청 ID ${id})` : '') });
        } finally {
          ctx.waitUntil(logUsage(env, log));
          try { controller.close(); } catch { /* 이미 끊긴 연결 */ }
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
