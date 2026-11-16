-- 의견함 웹 푸시 — 새 의견이 들어오면 관리자 폰으로 바로 알린다.
-- 기기 하나(브라우저 구독 하나) = 1행. 허브의 /feedback-admin.html 「이 기기로 알림 받기」가 넣는다.
-- 누구나 신청은 할 수 있으므로 처음엔 pending 이다. 관리자가 노트북에서
--   npm run feedback -- push-ok 3
-- 으로 승인해야 그 기기로 의견이 간다(승인 = wrangler 로그인).
CREATE TABLE IF NOT EXISTS push_subs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),   -- UTC
  endpoint TEXT NOT NULL UNIQUE,  -- 브라우저 푸시 서비스 주소 (FCM·애플·모질라…)
  p256dh TEXT NOT NULL,           -- 기기 공개키 (base64url) — 본문 암호화에 쓴다
  auth TEXT NOT NULL,             -- 기기 인증 비밀 (base64url)
  label TEXT,                     -- 신청할 때 적은 기기 이름
  ua TEXT,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending(대기) / active(받음)
  last_ok TEXT,                   -- 마지막으로 보내기 성공한 때
  last_err TEXT                   -- 마지막 실패 사유
);
