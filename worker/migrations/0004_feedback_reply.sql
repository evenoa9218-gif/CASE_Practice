-- 의견함 답장 — 관리자가 쓴 답을 보낸 사람이 사이트에 다시 들어왔을 때 띄운다.
-- cid: 의견을 보낸 브라우저의 무작위 표식(feedback.js 가 localStorage law_fb_cid 에 만든다).
--      통합사이트 앱 다섯 곳이 한 출처(evenoa9218-gif.github.io)라 어느 앱에 들어와도 같은 표식이다.
--      이 표식이 없는 옛 의견(#1~)은 로그인 ID(user)로 대신 찾는다.
ALTER TABLE feedback ADD COLUMN cid TEXT;
ALTER TABLE feedback ADD COLUMN reply TEXT;        -- 관리자 답장
ALTER TABLE feedback ADD COLUMN reply_ts TEXT;     -- 답장 쓴 때(UTC)
ALTER TABLE feedback ADD COLUMN reply_seen TEXT;   -- 보낸 사람이 「확인」을 누른 때. NULL 이면 아직 띄운다
CREATE INDEX IF NOT EXISTS feedback_cid ON feedback(cid);
CREATE INDEX IF NOT EXISTS feedback_user ON feedback(user);
