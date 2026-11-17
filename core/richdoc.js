/**
 * richdoc.js — 사례형·기록형 공용 「읽기 좋은 본문 + 형광펜·밑줄·수정」 부품
 *
 * ⚠ 같은 파일이 두 저장소에 있다: CASE_Practice/core/richdoc.js · RECORD/core/richdoc.js
 *   한쪽을 고치면 다른 쪽에도 그대로 복사한다.
 *
 * 쓰는 법 (React 전역이 먼저 있어야 한다):
 *   <RichDoc docId="공법_변시_15회_사례:rubric" text={…} kind="rubric"/>
 *   kind: 'rubric'(채점기준표) · 'answer'(모범답안·해설) · 'plain'(문제·기록 — 꾸밈 없이 표시만)
 *
 * 1) 읽기 좋게 — 원문 글자는 하나도 바꾸지 않고 **보여 주는 모양만** 바꾼다
 *    · 제목 줄(Ⅰ. / 1. / 가. / (1) / 문제 1 / 〈해설〉 / 배점 달린 줄)은 굵게
 *    · 판례 인용(대법원·헌재·대판, [참고판례], 【판시사항】~판결 전문)은 음영 상자
 *    · 강성민 사례집의 〈문제〉 부분은 문제 상자, 〈각주〉 아래는 각주 상자
 *    · 배점 「(10점)」은 색으로
 *    · 옛 OCR 에 남은 책 머리말(「614 ［제4편］ 통치구조론」 따위)은 흐리게(지우지 않는다)
 * 2) 표시하기 — 글을 고르면 도구가 뜬다: 형광펜 3색·밑줄·지우기. 「✎ 수정」은 글 자체를 고친다.
 *    표시는 글자 위치 + 앞뒤 문맥으로 저장해서, 글을 고쳐도 같은 문장을 다시 찾아 붙는다.
 *    저장: Store.getNote/setNote (사용자별·기기별 IndexedDB).
 */
(function (global) {
  'use strict';
  const h = global.React.createElement;
  const { useState, useEffect, useMemo, useRef, useCallback } = global.React;

  // ── 모양 ────────────────────────────────────────────
  const CSS = `
.rd{position:relative;white-space:pre-wrap;word-break:break-word;font-size:14.8px;line-height:1.9;color:var(--tx)}
.rd-l{min-height:1em}
.rd-l + .rd-l{margin-top:.55em}
.rd-li + .rd-li{margin-top:.28em}
.rd-blank{height:.55em}
.rd-h1{font-weight:800;font-size:1.04em;color:var(--gold);margin-top:.9em}
.rd-h2{font-weight:700;margin-top:.6em}
.rd-h3{font-weight:650;margin-top:.35em}
.rd-l:first-child,.rd-bar + .rd-l{margin-top:0}
.rd-li{padding-left:1.05em;text-indent:-1.05em}
.rd-box .rd-l + .rd-l{margin-top:.3em}
.rd-pg{color:var(--tx3);font-size:.82em}
.rd-doc{font-weight:800;text-align:center;font-size:1.05em;letter-spacing:.04em;margin-top:.5em}
.rd-docstart{border-top:1px dashed var(--bd2);padding-top:1em;margin-top:1.7em !important}
.rd-qline{padding-left:1.75em;text-indent:-1.75em}
.rd-qa{display:inline-block;text-indent:0;min-width:1.35em;margin-right:.4em;font-weight:800;color:var(--gold)}
.rd-qa-a{color:var(--tx2)}
.rd-pt{color:var(--gold);font-weight:700}
.rd-box{border-radius:0 7px 7px 0;padding:7px 12px;margin:8px 0}
.rd-box.pan{background:var(--sf2);border-left:3px solid var(--gold);font-size:.93em;color:var(--tx2)}
.rd-box.prob{background:var(--sf2);border-left:3px solid var(--bd2);border-radius:7px}
.rd-box.q{background:var(--sf2);border:1px solid var(--bd2);border-left:3px solid var(--gold);border-radius:7px;padding:9px 13px;font-weight:600}
.rd-box.q .rd-l + .rd-l{margin-top:.5em}
.rd-box.ref{border-left:2px solid var(--bd2);border-radius:0;margin-left:.6em;padding:2px 0 2px 12px;font-size:.88em;line-height:1.75;color:var(--tx2)}
.rd-box.ref .rd-h3{margin-top:.7em;color:var(--tx)}
.rd-lead{font-weight:700;color:var(--tx)}
.rd-box.foot{border-left:2px dashed var(--bd2);font-size:.86em;color:var(--tx2)}
.rd-hl-y{background:rgba(255,213,0,.42)}
.rd-hl-g{background:rgba(70,200,110,.34)}
.rd-hl-p{background:rgba(255,110,170,.32)}
.rd-ul{text-decoration:underline;text-decoration-color:#e0483e;text-decoration-thickness:2px;text-underline-offset:3px}
.rd-bar{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin:-2px 0 4px;white-space:normal}
.rd-edit-btn{font-size:12px;padding:2px 9px;border-radius:7px;border:1px solid var(--bd2);background:var(--sf);
  color:var(--tx2);cursor:pointer;opacity:.75}
.rd-edit-btn:hover{opacity:1}
/* 마우스가 있는 기기에서는 「✎ 수정」을 글에 올렸을 때만 띄운다 — 블록마다 한 줄씩 먹던 여백을 없앤다 */
@media (hover:hover){
  .rd-bar{position:absolute;top:-6px;right:-2px;margin:0;z-index:3;opacity:0;transition:opacity .12s;pointer-events:none}
  .rd:hover > .rd-bar,.rd-bar:focus-within{opacity:1;pointer-events:auto}
  .rd-bar:has(.rd-edited){position:static;opacity:1;pointer-events:auto;margin:-2px 0 4px}
}
.rd-edited{font-size:11.5px;color:var(--gold)}
.rd-ta{width:100%;min-height:340px;font:inherit;font-size:14.5px;line-height:1.8;padding:10px;border-radius:8px;
  border:1px solid var(--bd2);background:var(--sf);color:var(--tx);resize:vertical;white-space:pre-wrap}
.rd-row{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0}
.rd-btn{font-size:13px;padding:5px 12px;border-radius:8px;border:1px solid var(--bd2);background:var(--sf);color:var(--tx);cursor:pointer}
.rd-btn.on{background:var(--gold);border-color:var(--gold);color:#fff}
.rd-tool{position:fixed;z-index:200;display:flex;gap:4px;padding:5px;border-radius:11px;background:var(--sf);
  border:1px solid var(--bd2);box-shadow:0 6px 22px rgba(0,0,0,.22)}
.rd-tool button{min-width:34px;height:32px;border-radius:8px;border:1px solid var(--bd2);background:var(--sf);
  color:var(--tx);font-size:13px;cursor:pointer;padding:0 7px}
.rd-tool .y{background:rgba(255,213,0,.6)} .rd-tool .g{background:rgba(70,200,110,.5)} .rd-tool .p{background:rgba(255,110,170,.45)}
.rd-tool .u{text-decoration:underline;text-decoration-color:#e0483e;text-decoration-thickness:2px;font-weight:700}
@media (pointer:coarse){ .rd-tool{left:50% !important;top:auto !important;bottom:14px;transform:translateX(-50%)}
  .rd-tool button{min-width:44px;height:40px;font-size:14px} }
`;
  if (!document.getElementById('rd-style')) {
    const st = document.createElement('style'); st.id = 'rd-style'; st.textContent = CSS;
    document.head.appendChild(st);
  }

  // ── 판례 줄 가려내기 ─────────────────────────────────
  // 줄머리(불릿 떼고)가 「대법원 2020.」「헌재 2020.」「대판 2020」「[참고판례]」「<참조 판례>」면 판례를 연다.
  // 뒤 줄은 빈 줄이나 기준표 줄머리(1. 가. ① - ○ 사안…)가 나올 때까지 판례다.
  // 「참조 판례」 꼬리표만 있는 줄 뒤는 판례 본문이 1. 2. 로 나뉘기도 해 큰 제목·빈 줄에서만 끊는다.
  // 기록형 기준표의 판례 전문(【판시사항】… 반대의견)은 빈 줄을 넘어 이어지고,
  // 【이 유】 본문은 대법관 서명 줄이나 <끝> 까지 통째로 판례다.
  // 사례·기록 기준표 62,790줄에 돌려 641덩어리 — 애매하면 본문으로 둔다(기준을 판례로 가리는 것보다 낫다).
  const PAN_LEAD  = /^[\s\-–*※∙·•○◦]*/;
  const PAN_DOC   = /^【\s*(?:판시사항|판결요지|결정요지|원심판결|주\s*문|이\s*유|참조판례|관련판례|참조조문|전\s*문|원\s*고|피\s*고)[^】]*】/;
  const PAN_OPEN  = /^[\[(<【]?\s*(?:(?:참[고조]|관련)\s*판례|대법원\s*(?:\d{4}|판례\s*:)|대판\s*\d|\S{0,6}(?:지방|고등|행정|가정)법원\s*\d|헌재\s*\d{4}|헌법재판소\s*\d{4})/;
  const PAN_LABEL = /^[\[(<【]?\s*(?:참[고조]|관련)\s*판례\s*[\])>】]?\s*:?\s*$/;
  const PAN_STOP  = /^\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|\d+\s*[.)]|\(\d+\)|[가-하]\s*[.)]|\([가-하]\)|[①-⑳]|[○●■□▶◆◇※*∙·•]|[-–]|<|【|〈|문제|설문|사안|따라서|결론|검토|소결|[^\s:]{1,12}설\s*:)/;
  const PAN_HARD  = /^\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|문제\s*\d|설문|〈|[-–○]\s*(?:사안|따라서|결론)|<|.*\(\d+점\)\s*$|.*<\d+점>\s*$|.*\[기재사항[^\]]*\]\s*$)/;
  const PAN_JUDG  = /^【\s*이\s*유\s*】/;
  const PAN_SIGN  = /^\s*(?:대법관|재판장|재판관)\s/;
  const PAN_JEND  = /^\s*(?:<\s*끝\s*>|제\s*\d+\s*문\s*$)/;

  function panFlags(L) {
    const out = new Array(L.length).fill(false);
    let mode = '';
    for (let i = 0; i < L.length; i++) {
      const ln = L[i], body = ln.replace(PAN_LEAD, '');
      if (mode === 'judg') {
        if (PAN_JEND.test(ln)) mode = '';
        else { if (PAN_SIGN.test(ln)) mode = ''; out[i] = true; continue; }
      }
      if (PAN_DOC.test(ln.trim())) { mode = PAN_JUDG.test(ln.trim()) ? 'judg' : 'doc'; out[i] = true; continue; }
      if (body && PAN_OPEN.test(body)) { mode = PAN_LABEL.test(body) ? 'label' : 'cite'; out[i] = true; continue; }
      if (mode && !ln.trim()) {
        let j = i + 1; while (j < L.length && !L[j].trim()) j++;
        if (mode === 'doc' && j < L.length && !PAN_HARD.test(L[j]) && !PAN_JEND.test(L[j])) { out[i] = true; continue; }
        mode = '';
      } else if (mode && !(mode === 'cite' ? PAN_STOP : PAN_HARD).test(ln)) { out[i] = true; continue; }
      else mode = '';
    }
    // 판례 덩어리 끝의 빈 줄은 상자 밖으로
    for (let i = L.length - 1; i >= 0; i--) if (out[i] && !L[i].trim() && !(out[i + 1])) out[i] = false;
    return out;
  }

  // ── 제목 줄 ─────────────────────────────────────────
  const SENT_END = /(?:[다음함임됨요]|니다)\s*[.。]?\s*$/;
  const ROMAN = /^(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|(?:I|II|III|IV|V|VI|VII|VIII|IX|X))\s*[.．]\s*\S/;
  const POINTS = /[(<（]\s*\d+(?:\.\d+)?\s*점\s*[)>）]\s*$/;
  function headLevel(t, kind) {
    if (!t) return '';
    const n = t.length;
    if (ROMAN.test(t) && n <= 60) return 'h1';
    if (/^〈[^〉]{1,12}〉/.test(t) && n <= 200) return 'h1';
    if (/^(?:문제|설문)\s*\d+/.test(t) && n <= 60) return 'h1';
    if (/^제\s*\d+\s*문/.test(t) && n <= 40) return 'h1';
    if (/^\[사례\s*\d+\]/.test(t)) return 'h1';
    if (/^─{2,}.*─{2,}$/.test(t)) return 'h1';
    if (kind === 'rubric' && POINTS.test(t) && n <= 80) return 'h2';
    if (/^\d+\)\s*-\s*[①-⑳]/.test(t) && n <= 70) return 'h2';
    if (SENT_END.test(t)) return '';
    if (/^\d{1,2}\s*[.．]\s*\S/.test(t) && !/^\d{1,2}\s*[.．]\s*\d/.test(t) && n <= 45) return 'h2';
    if (n > 40) return '';
    if (/^[가-하]\s*[.．]\s*\S/.test(t)) return 'h3';
    if (/^\(\d{1,2}\)\s*\S/.test(t)) return 'h3';
    if (/^\d{1,2}\)\s*\S/.test(t) && !/대법원|헌재|선고|판결|결정/.test(t)) return 'h3';
    // ①② 는 기준표에서만 제목이다. 답안에서는 문장 속 나열이 줄머리로 잘린 것이 많다(「사안에서 甲은 / ① 확정된 원금…」)
    if (kind === 'rubric' && /^[①-⑳]\s*\S/.test(t) && n <= 30) return 'h3';
    if (/^○\s*\S/.test(t)) return 'h3';
    return '';
  }
  // 옛 OCR 이 본문에 남긴 책 머리말·쪽 번호 — 흐리게만
  const PAGE_NOISE = [
    /^\d{2,4}\s*[［\[]\s*제\s*\d+\s*편\s*[］\]]/, /^\d{2,4}\s+\S{0,8}사례형\S{0,4}$/, /^\d{4}\s*년?\s*\S{0,6}\s*\S{0,6}사례형(?:\s*연습)?\s*\S{0,8}$/,
    /^제\s*\d+\s*[장편]\s*\S{1,12}\s*\d{2,4}$/, /^\d{2,4}\s+제\s*\d+\s*[장편]\s*\S{1,12}$/,
    /^\d{1,4}\s+.{0,20}(?:기출문제집|기록형\s*\S{0,6}|사례형\s*\S{0,6})$/, /^.{0,20}(?:기출문제집|기록형\s*기출\S{0,4})\s+\d{1,4}$/,
  ];

  const NL = String.fromCharCode(10);

  // ── 잘린 줄 잇기 ───────────────────────────────────
  // PDF 에서 옮긴 글은 쪽 폭에서 줄이 끊겨 있다(정연석 사례집 40%, 기록형 해설 34%, 박승수 20%).
  // 앞 줄이 28자 이상 본문 줄이고 문장 끝이 아니며, 다음 줄이 제목·항목 머리가 아니면 한 문단으로 잇는다.
  //   (「문서에서 꽉 찬 줄 길이」로 재 보았더니, 긴 문단과 잘린 줄이 섞인 정연석 사례집에서 기준이 너무 커져 못 이었다)
  // **보여 줄 때만** 잇는다 — 원문의 줄바꿈 글자는 그대로 두고 그 자리를 빈칸으로 그린다(글 위치가 안 어긋난다).
  const WRAP_END = /[.。?!:;」』)\]>〉】]\s*$|(?:다|음|함|임|됨|요)\s*$/;
  const WRAP_HEAD = /^\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]|\d+\s*[.)]|\(\d+\)|[가-하]\s*[.)]|\([가-하]\)|[①-⑳]|[○●■□▶◆◇※*∙·•ㆍ\-–]|〈|【|\[|─)/;
  function joinWrapped(lines, L) {
    const out = [];
    for (let i = 0; i < lines.length; i++) {
      const cur = lines[i], prev = out[out.length - 1];
      const a = i > 0 ? L[i - 1].trim() : '', b = L[i].trim();
      if (prev && i > 0 && !cur.cls && prev.lastCls === '' && prev.box === cur.box &&
          !(cur.box === 'foot' && /^\d{1,3}\s/.test(b)) &&          // 각주 번호 줄은 새 각주
          a.length >= 28 && !WRAP_END.test(a) && b && !WRAP_HEAD.test(b)) {
        prev.e = cur.e; prev.lastCls = cur.cls; prev.joined = true;
        continue;
      }
      out.push(Object.assign({ lastCls: cur.cls }, cur));
    }
    return out;
  }

  // ── 벽글 나누기 ─────────────────────────────────────
  // 해설 PDF 를 옮기며 문장들이 줄바꿈도 빈칸도 없이 붙은 덩어리가 있다(「받아 보았습니다.귀하의 통지서에서…」).
  // 380자가 넘는 본문 줄은 문장 끝(「다.」「요.」…)에서 끊어 160자 이상씩 문단으로 그린다 — 역시 보여 줄 때만.
  const SENT_CUT = /(?:다|요|음|함|임|됨)\.["”’」』)]?\s*(?=\S)/g;
  // 항목 머리가 앞 문장에 붙어 버린 자리(「…성립한다.(나) 배임수재죄…」 「…논하시오. (20점)2) (2)와 관련하여…」).
  // 문장 끝·배점 바로 뒤에 빈칸 없이 오는 「(나)」「（4）」「2)」「2.」 앞에서 끊는다.
  const MARK_CUT = /(?<=[.。?)）])(?=[(（](?:\d{1,2}|[가-하])[)）]\s?\S)|(?<=점\)|[다요]\.)(?=\d{1,2}[.)]\s?[^\d\s])/g;
  function splitWalls(lines, text) {
    const out = [];
    for (const ln of lines) {
      if (ln.cls || ln.e - ln.s <= 380) { out.push(ln); continue; }
      const seg = text.slice(ln.s, ln.e);
      const cuts = [];
      let m;
      SENT_CUT.lastIndex = 0;
      while ((m = SENT_CUT.exec(seg))) cuts.push([m.index + m[0].length, 160]);
      MARK_CUT.lastIndex = 0;
      while ((m = MARK_CUT.exec(seg))) { cuts.push([m.index, 30]); if (m[0] === '') MARK_CUT.lastIndex++; }
      cuts.sort((a, b) => a[0] - b[0]);
      let start = 0;
      for (const [cut, min] of cuts) {
        if (cut - start >= min && seg.length - cut >= 40) {
          out.push(Object.assign({}, ln, { s: ln.s + start, e: ln.s + cut }, start ? { qa: '' } : {}));
          start = cut;
        }
      }
      out.push(Object.assign({}, ln, { s: ln.s + start, e: ln.e }, start ? { qa: '' } : {}));
    }
    return out;
  }

  // ── 본문에 붙은 각주 떼기 ───────────────────────────
  // 쪽 아래 각주가 본문 줄 끝에 이어 붙은 책이 있다(형법 사례집):
  //   「…업무상배임죄가 성립한다.1) 대법원 2012. 5. 10. 선고 2010도3532 판결.2) 대법원 2013. …」
  // 「N) 대법원/헌재/본 사례…」가 번호 순서대로 두 번 이상 이어지면 그 앞에서 끊어 각주 상자로 보낸다.
  const NOTE_CUT = /(?<=[.。)\]」』”"다])\s?(\d{1,3})\)\s?(?=대법원|대판|헌재|헌법재판소|서울|부산|대구|광주|대전|수원|同|동지|본 |이에 |다만|한편|참고|위 )/g;
  function splitNotes(lines, text) {
    const out = [];
    for (const ln of lines) {
      if (ln.cls || ln.box || ln.e - ln.s < 60) { out.push(ln); continue; }
      const seg = text.slice(ln.s, ln.e);
      const hits = [];
      let m;
      NOTE_CUT.lastIndex = 0;
      while ((m = NOTE_CUT.exec(seg))) hits.push([m.index + (m[0].length - m[0].trimStart().length), +m[1]]);
      // 번호가 차례로 늘어나는 꼬리만 각주로 본다(본문의 「1) 대법원은…」 같은 항목과 가르기 위해 두 개 이상)
      let k = hits.length - 1;
      while (k > 0 && hits[k][1] === hits[k - 1][1] + 1) k--;
      const run = hits.slice(k);
      if (run.length < 2) { out.push(ln); continue; }
      out.push(Object.assign({}, ln, { e: ln.s + run[0][0] }));
      // 마지막 각주는 첫 문장 끝에서 끝난다. 쪽이 넘어가며 잘린 각주는 다음 쪽 머리말(「사례 19 [26…」) 앞에서.
      // 그 뒤는 다시 본문이다 — 한 줄로 붙은 글에서 각주 뒤 본문까지 각주 상자에 넣지 않도록.
      const lastAt = run[run.length - 1][0], rest = seg.slice(lastAt);
      const m1 = /(?:판결|결정|다|음|함|임)\.(?=\S|$)/.exec(rest), m2 = /\s?사례\s*\d+\s*[\[.]|\s?\d{2,4}\s*\S{0,6}사례형\s?해설/.exec(rest);
      const ends = [m1 && m1.index + m1[0].length, m2 && m2.index].filter((x) => x != null && x > 0);
      const lastEnd = ends.length ? lastAt + Math.min(...ends) : seg.length;
      run.forEach(([at], i) => out.push(Object.assign({}, ln, {
        s: ln.s + at, e: ln.s + (i + 1 < run.length ? run[i + 1][0] : lastEnd), box: 'foot', joined: false })));
      if (lastEnd < seg.length) out.push(Object.assign({}, ln, { s: ln.s + lastEnd, joined: false }));
    }
    return out;
  }

  // ── 기록(기록형 시험의 사건 기록) ─────────────────────
  // 기록은 공소장·조서·판결·고소장이 이어 붙은 문서 묶음이다. 서식 줄(「주소 ⏎ 성명」)이 많아
  // 잘린 줄 잇기는 하지 않는다. 대신 문서 경계와 머리말·발언자·문답을 드러낸다.
  //   · 문서 이름(「공 판 조 서」 「처벌불원서」 「이한방에 대한 고소취소장(사본)」) → 가운데 굵게,
  //     새 문서가 시작되는 첫 줄에는 점선 구분선
  //   · 【…】 [작성요령] <범죄일람표> 「제목 : …」 Ⅱ. → 굵은 머리말 / 2글자 띄어 쓴 「주 문」「이 유」 → 머리말
  //   · 공판조서의 「재판장」「검 사」「피고인 김갑동의 변호인」 → 발언자(굵게)
  //   · 조서의 「문…」「답…」 → 첫 글자를 꼬리표로
  const DOC_SUFFIX = /(?:조서|신청서|불원서|취소장|공소장|고소장|고발장|진술서|보고서?|의견서|요지서|청구서|결정서?|판결문?|소장|답변서|준비서면|확인서|계약서|내용증명|통지서|증명서|등본|각서|합의서|영수증|진단서|감정서|사실조회회신|회신서?|명령|약정서|차용증|위임장)(?:\s*\((?:사본|생략|요약)\))?$/;
  const SPEAKER = /^(?:재판장|검\s*사|소송관계인|피고인(?:들)?(?:\s+\S{2,4})?(?:의\s*변호인)?|변\s*호\s*인|증\s*인(?:\s+\S{2,4})?|원고\s*소송대리인|피고\s*소송대리인|원\s*고|피\s*고)$/;
  function recordLevel(t) {
    const n = t.length;
    if (!t || n > 34) return '';
    if (/^(?:[가-힣]\s+){2,}[가-힣]$/.test(t)) {
      // 띄어 쓴 줄: 문서 이름(공 판 조 서)·기관(부 산 지 방 법 원)이면 문서, 아니면(범 죄 사 실 · 피 고 인 이 을 남) 머리말
      const c = t.replace(/\s+/g, '');
      return DOC_SUFFIX.test(c) || /(?:법원|지원|검찰청|경찰서|위원회|헌법재판소|구청|시청)$/.test(c) || c === '판결' ? 'doc' : 'h2';
    }
    if (!/[:：]|^\s*[\d(①-⑳○※\-]/.test(t) && n <= 26 && DOC_SUFFIX.test(t)) return 'doc';
    if (/^[가-힣]\s+[가-힣]$/.test(t)) return 'h2';                                // 주 문 · 이 유 · 다 음
    if (/^【[^】]{1,20}】$|^\[[^\]]{1,20}\]$|^<[^>]{1,20}>$|^〈[^〉]{1,20}〉$/.test(t)) return 'h2';
    if (/^제\s*목\s*[:：]/.test(t)) return 'h2';
    if (ROMAN.test(t)) return 'h2';
    if (SPEAKER.test(t)) return 'h3';
    if (/^[-─━=_~·]{8,}$/.test(t)) return 'pg';
    return '';
  }
  function classifyRecord(text) {
    const L = text.split('\n');
    const pos = []; { let o = 0; for (const l of L) { pos.push(o); o += l.length + 1; } }
    let josa = false, prevDoc = true;
    return L.map((ln, i) => {
      const t = ln.trim();
      const e = { s: pos[i], e: pos[i] + ln.length, cls: '', box: '' };
      if (!t) { e.cls = 'blank'; return e; }
      let lv = recordLevel(t);
      // 문단 머리글(「가. 특정범죄…」)은 사례 문제와 같은 규칙으로
      if (!lv && /^[가-하]\s*[.．]\s*\S/.test(t) && t.length <= 40 && !SENT_END.test(t)) lv = 'h3';
      if (lv === 'doc') {
        e.cls = 'doc' + (prevDoc ? '' : ' rd-docstart');
        josa = /조서$/.test(t.replace(/\s+/g, ''));
        prevDoc = true;
        return e;
      }
      prevDoc = false;
      if (lv) { e.cls = lv; return e; }
      if (josa && /^\s*[문답](?=\S)/.test(ln)) e.qa = /^\s*문/.test(ln) ? 'q' : 'a';
      return e;
    });
  }

  /** 줄(또는 이어 붙인 문단)마다 {s,e,cls,box} — s,e 는 전체 글에서의 위치 */
  function classify(text, kind) {
    if (kind === 'record') return splitWalls(classifyRecord(text), text);
    let lines = classifyLines(text, kind === 'problem' ? 'plain' : kind);
    const L0 = text.split(NL);
    if (kind === 'problem') markArticles(lines, L0);     // 앱이 이미 사실관계·설문·참조조문 칸을 나눠 준다 — 조문 머리만 굵게
    if (kind === 'answer') {
      // 사례집 답안의 〈문제〉 구간
      for (let i = 0; i < lines.length;) {
        if (lines[i].box !== 'prob') { i++; continue; }
        let j = i; while (j < lines.length && (lines[j].box === 'prob' || lines[j].cls === 'blank')) j++;
        markProblem(lines, L0, i, j, false);
        i = j;
      }
    }
    if (kind === 'answer' || kind === 'problem') lines = joinWrapped(lines, L0);
    if (kind === 'answer') lines = splitNotes(lines, text);
    return splitWalls(lines, text);
  }

  // ── 문제 안의 구조 ──────────────────────────────────
  // 문제 글은 ① 사실관계 ② 설문(「1. … (20점)」) ③ 유의사항·참조 조문 순이다. 전에는 셋을 한 상자에
  // 같은 모양으로 넣어 어디가 물음인지 안 보였다.
  //   사실관계 = 본문 그대로(문단 띄움) / 설문 = 상자 / 유의사항·참조 조문 = 작게 들여 쓰고,
  //   법령 이름은 굵게, 조문 머리 「제5조(사업의 허가 등)」만 굵게.
  const REF_HEAD = /^\s*(?:※\s*유의\s*사항|[\[<〈【]?\s*참\s*[조고]\s*조\s*문\s*[\]>〉】]?|[\[<〈【]\s*관\s*[련계]\s*법\s*령[^\]>〉】]*[\]>〉】]|※\s*아래의?\s*(?:조문|법령)|아래\s*법령은)/;
  const Q_HEAD = /^\s*(?:문제\s*)?\d{1,2}\s*[.．](?!\s*\d{1,2}\s*[.．](?!\s*\d))\s*\S/;
  const ART_HEAD = /^\s*제\s*\d+\s*조(?:\s*의\s*\d+)?\s*[(（][^)）]{1,40}[)）]/;
  const LAW_NAME = /^\s*[｢「]?[가-힣A-Za-z0-9·ㆍ\s]{2,40}(?:법|법률|시행령|시행규칙|규칙|조례|규정|협약|헌법)[｣」]?(?:\s*[(（][^)）]{1,30}[)）])?\s*$/;
  function markArticles(lines, L) {
    if (L.filter((l) => ART_HEAD.test(l)).length < 2) return;
    for (let i = 0; i < lines.length; i++) {
      const t = L[i].trim();
      if (lines[i].cls) continue;
      const m = ART_HEAD.exec(L[i]);
      if (m) lines[i].lead = m[0].length;
      else if (REF_HEAD.test(t) || (LAW_NAME.test(t) && t.length <= 44)) lines[i].cls = 'h3';
    }
  }
  function markProblem(lines, L, a, b, boxFacts) {
    let stage = 'fact';
    for (let i = a; i < b; i++) {
      const ln = lines[i], t = L[i].trim();
      if (ln.cls === 'blank') { ln.box = ''; continue; }
      if (ln.cls === 'h1') continue;
      if (REF_HEAD.test(t)) stage = 'ref';
      else if (stage !== 'ref' && Q_HEAD.test(t) && /점\s*[)）]|[?？]\s*$|시오|인가|는가/.test(L.slice(i, i + 6).join(' '))) stage = 'q';
      else if (stage === 'q' && /^\s*[<〈\[【]/.test(t) && !/점\s*[)）]/.test(t)) stage = 'fact';   // 〈추가된 사실관계〉로 돌아감
      if (stage === 'ref') {
        ln.box = 'ref';
        if (REF_HEAD.test(t) && t.length <= 30) ln.cls = 'h3';
        else if (REF_HEAD.test(t)) { /* 유의 문구가 본문과 한 줄 — 그대로 */ }
        else if (LAW_NAME.test(t) && t.length <= 44) ln.cls = 'h3';
        else { const m = ART_HEAD.exec(L[i]); if (m) ln.lead = m[0].length; }
      } else if (stage === 'q') { ln.box = 'q'; }
      else { ln.box = boxFacts ? 'prob' : ''; if (/^\s*[<〈\[【][^>〉\]】]{1,20}[>〉\]】]\s*$/.test(t)) ln.cls = 'h3'; }
    }
    return lines;
  }
  function classifyLines(text, kind) {
    const L = text.split('\n');
    const pos = []; { let o = 0; for (const l of L) { pos.push(o); o += l.length + 1; } }
    const pan = kind === 'plain' ? L.map(() => false) : panFlags(L);
    const hasJudge = kind === 'answer' && /〈해설/.test(text);
    let sec = '';                       // '' · 'prob'(〈문제〉 뒤) · 'foot'(〈각주〉 뒤)
    return L.map((ln, i) => {
      const t = ln.trim();
      let cls = '', box = '';
      if (kind !== 'plain') {
        if (kind === 'answer') {
          if (/^〈\s*각주\s*〉$|^─+\s*각주\s*─+$/.test(t)) { sec = 'foot'; return { s: pos[i], e: pos[i] + ln.length, cls: 'h1', box: '' }; }
          if (hasJudge && /^〈\s*문제\s*\d*\s*〉$/.test(t)) { sec = 'prob'; return { s: pos[i], e: pos[i] + ln.length, cls: 'h1', box: '' }; }
          if (/^〈[^〉]{1,12}〉/.test(t) || /^─{2,}.*─{2,}$/.test(t)) sec = '';
          if (PAGE_NOISE.some((r) => r.test(t)) && t.length <= 40) cls = 'pg';
        }
        if (sec) box = sec;
        else if (pan[i]) box = 'pan';
        if (!cls && !box) cls = headLevel(t, kind);
      }
      if (!t) cls = 'blank';
      return { s: pos[i], e: pos[i] + ln.length, cls, box };
    });
  }

  // ── 표시 붙이기 ─────────────────────────────────────
  // 저장한 위치에 같은 글이 그대로 있으면 그 자리, 아니면 앞뒤 문맥이 가장 잘 맞는 같은 글을 찾는다.
  function anchor(marks, body) {
    const out = [];
    for (const m of marks || []) {
      if (body.slice(m.s, m.e) === m.q) { out.push(m); continue; }
      let best = -1, score = -1, from = 0;
      for (;;) {
        const i = body.indexOf(m.q, from); if (i < 0) break;
        let sc = 0;
        const pre = body.slice(Math.max(0, i - (m.pre || '').length), i), suf = body.slice(i + m.q.length, i + m.q.length + (m.suf || '').length);
        for (let k = 1; k <= pre.length && pre[pre.length - k] === m.pre[m.pre.length - k]; k++) sc++;
        for (let k = 0; k < suf.length && suf[k] === m.suf[k]; k++) sc++;
        sc -= Math.abs(i - m.s) / 1e6;
        if (sc > score) { score = sc; best = i; }
        from = i + 1;
      }
      if (best >= 0 && m.q) out.push(Object.assign({}, m, { s: best, e: best + m.q.length }));
    }
    return out;
  }

  // 화면 위치 → 글 위치. 줄 div 에는 data-o/data-e, 글 조각 span 에는 data-o.
  function offsetOf(root, node, off) {
    if (!root.contains(node)) return null;
    if (node.nodeType === 3) {
      const sp = node.parentElement && node.parentElement.closest('[data-o]');
      return sp ? +sp.dataset.o + off : null;
    }
    const el = node;
    if (off < el.childNodes.length) {
      const c = el.childNodes[off];
      const t = c.nodeType === 1 ? (c.matches('[data-o]') ? c : c.querySelector('[data-o]')) : null;
      if (t) return +t.dataset.o;
    }
    const all = el.querySelectorAll ? el.querySelectorAll('[data-o]') : [];
    const last = all.length ? all[all.length - 1] : el.closest && el.closest('[data-o]');
    if (!last) return null;
    return last.dataset.e != null ? +last.dataset.e : +last.dataset.o + last.textContent.length;
  }

  const POINT_RE = /[(<（]\s*\d+(?:\.\d+)?\s*점\s*[)>）]/g;

  function RichDoc({ docId, text, kind, className }) {
    kind = kind || 'plain';
    text = text || '';
    const [note, setNote] = useState(null);
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState('');
    const [tool, setTool] = useState(null);        // {s,e,x,y}
    const root = useRef(null);

    useEffect(() => {
      let alive = true; setNote(null); setEditing(false); setTool(null);
      if (global.Store && global.Store.getNote) global.Store.getNote(docId).then((v) => { if (alive) setNote(v || {}); }).catch(() => alive && setNote({}));
      else setNote({});
      return () => { alive = false; };
    }, [docId]);

    const body = (note && typeof note.edited === 'string') ? note.edited : text;
    const marks = useMemo(() => anchor(note && note.marks, body), [note, body]);
    const lines = useMemo(() => classify(body, kind), [body, kind]);

    const save = useCallback((next) => {
      setNote(next);
      if (global.Store && global.Store.setNote) global.Store.setNote(docId, next).catch(() => {});
    }, [docId]);

    // 글 고르기 → 도구
    useEffect(() => {
      let timer = null;
      const check = () => {
        const r = root.current; if (!r || editing) return;
        const sel = global.getSelection();
        if (!sel || !sel.rangeCount || sel.isCollapsed) { setTool(null); return; }
        const rg = sel.getRangeAt(0);
        if (!r.contains(rg.commonAncestorContainer)) { setTool((t) => (t ? null : t)); return; }
        let s = offsetOf(r, rg.startContainer, rg.startOffset), e = offsetOf(r, rg.endContainer, rg.endOffset);
        if (s == null || e == null) return;
        if (s > e) { const x = s; s = e; e = x; }
        while (s < e && /\s/.test(body[s])) s++;
        while (e > s && /\s/.test(body[e - 1])) e--;
        if (e <= s) { setTool(null); return; }
        const b = rg.getBoundingClientRect();
        setTool({ s, e, x: Math.max(8, Math.min(global.innerWidth - 250, b.left + b.width / 2 - 120)), y: Math.max(8, b.top - 50) });
      };
      const later = () => { clearTimeout(timer); timer = setTimeout(check, 120); };
      document.addEventListener('selectionchange', later);
      document.addEventListener('mouseup', later);
      return () => { clearTimeout(timer); document.removeEventListener('selectionchange', later); document.removeEventListener('mouseup', later); };
    }, [body, editing]);

    const apply = (t, c) => {
      if (!tool) return;
      const { s, e } = tool;
      let list = (note && note.marks ? anchor(note.marks, body) : []);
      if (t === 'x') list = list.filter((m) => m.e <= s || m.s >= e);
      else {
        // 같은 종류(형광펜끼리·밑줄끼리)가 겹치면 새것으로 갈아 끼운다
        const same = (m) => (t === 'ul' ? m.t === 'ul' : m.t === 'hl');
        list = list.filter((m) => !(same(m) && m.s < e && m.e > s));
        list.push({ id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), s, e, t, c: c || '',
          q: body.slice(s, e), pre: body.slice(Math.max(0, s - 24), s), suf: body.slice(e, e + 24) });
      }
      save(Object.assign({}, note || {}, { marks: list }));
      const sel = global.getSelection(); if (sel) sel.removeAllRanges();
      setTool(null);
    };

    if (note === null) return h('div', { className: 'rd ' + (className || '') }, text);

    if (editing) {
      return h('div', { className: (className || '') },
        h('textarea', { className: 'rd-ta', value: draft, onChange: (ev) => setDraft(ev.target.value) }),
        h('div', { className: 'rd-row' },
          h('button', { className: 'rd-btn on', onClick: () => {
            const edited = draft === text ? null : draft;
            const kept = anchor(note.marks, edited == null ? text : edited);
            save(Object.assign({}, note, { edited, marks: kept }));
            setEditing(false);
          } }, '저장'),
          h('button', { className: 'rd-btn', onClick: () => setEditing(false) }, '취소'),
          typeof note.edited === 'string' && h('button', { className: 'rd-btn', onClick: () => {
            if (!global.confirm('고친 글을 버리고 원문으로 되돌릴까요? (형광펜·밑줄은 원문에 같은 글이 있으면 남습니다)')) return;
            save(Object.assign({}, note, { edited: null, marks: anchor(note.marks, text) }));
            setEditing(false);
          } }, '원문으로 되돌리기')),
        h('div', { className: 'muted', style: { fontSize: 12 } }, '고친 글은 이 기기에만 저장됩니다. 원문은 그대로 남아 언제든 되돌릴 수 있습니다.'));
    }

    // 줄 → 조각(형광펜·밑줄·배점 경계에서 자른다)
    const renderLine = (ln, i) => {
      if (ln.cls === 'blank') return h('div', { key: i, className: 'rd-l rd-blank', 'data-o': ln.s, 'data-e': ln.e });
      const cuts = new Set([ln.s, ln.e]);
      const ms = marks.filter((m) => m.s < ln.e && m.e > ln.s);
      for (const m of ms) { if (m.s > ln.s) cuts.add(m.s); if (m.e < ln.e) cuts.add(m.e); }
      const pts = [];
      if (kind !== 'plain') {
        POINT_RE.lastIndex = 0; const seg = body.slice(ln.s, ln.e); let mm;
        while ((mm = POINT_RE.exec(seg))) { const a = ln.s + mm.index, b = a + mm[0].length; pts.push([a, b]); cuts.add(a); cuts.add(b); }
      }
      if (ln.lead && ln.s + ln.lead < ln.e) cuts.add(ln.s + ln.lead);
      let qa = null;
      if (ln.qa) { const k = ln.s + (body.slice(ln.s, ln.e).length - body.slice(ln.s, ln.e).trimStart().length); qa = [k, k + 1]; cuts.add(k); cuts.add(k + 1); }
      const cs = [...cuts].sort((a, b) => a - b);
      const kids = [];
      for (let k = 0; k < cs.length - 1; k++) {
        const a = cs[k], b = cs[k + 1]; if (b <= a) continue;
        let cl = '';
        for (const m of ms) if (m.s <= a && m.e >= b) cl += m.t === 'ul' ? ' rd-ul' : ' rd-hl-' + (m.c || 'y');
        if (pts.some((p) => p[0] <= a && p[1] >= b)) cl += ' rd-pt';
        if (qa && qa[0] <= a && qa[1] >= b) cl += ' rd-qa rd-qa-' + ln.qa;
        if (ln.lead && b <= ln.s + ln.lead) cl += ' rd-lead';
        const seg = body.slice(a, b);
        kids.push(h('span', { key: a, 'data-o': a, className: cl.trim() || undefined }, ln.joined ? seg.split(NL).join(' ') : seg));
      }
      const li = !ln.cls && !ln.qa && /^\s*(?:[-–∙·•ㆍ*○◦]|[①-⑳]|\(\d{1,2}\)|\d{1,2}\))\s*/.test(body.slice(ln.s, ln.s + 6));
      return h('div', { key: i, className: 'rd-l' + (ln.cls ? ' rd-' + ln.cls : '') + (li ? ' rd-li' : '') + (ln.qa ? ' rd-qline' : ''),
        'data-o': ln.s, 'data-e': ln.e }, kids);
    };
    const out = [];
    // 빈 줄이 겹치면 하나만 그린다(원문 글자는 그대로 — 그리기만 건너뛴다). 상자 맨 앞·뒤의 빈 줄도 건너뛴다.
    const skip = (k) => lines[k].cls === 'blank' && (k === 0 || lines[k - 1].cls === 'blank' ||
      (lines[k].box && (k + 1 >= lines.length || lines[k + 1].box !== lines[k].box || lines[k - 1].box !== lines[k].box)));
    for (let i = 0; i < lines.length;) {
      const bx = lines[i].box;
      if (!bx) { if (!skip(i)) out.push(renderLine(lines[i], i)); i++; continue; }
      const grp = [];
      let j = i;
      while (j < lines.length && lines[j].box === bx) { if (!skip(j)) grp.push(renderLine(lines[j], j)); j++; }
      out.push(h('div', { key: 'b' + i, className: 'rd-box ' + bx }, grp));
      i = j;
    }

    return h(global.React.Fragment, null,
      h('div', { className: 'rd ' + (className || ''), ref: root },
        h('div', { className: 'rd-bar' },
          typeof note.edited === 'string' && h('span', { className: 'rd-edited' }, '✎ 내가 고친 글'),
          h('button', { className: 'rd-edit-btn', title: '이 글을 고친다(원문은 보존)', onClick: () => { setDraft(body); setEditing(true); } }, '✎ 수정')),
        out),
      tool && h('div', { className: 'rd-tool', style: { left: tool.x, top: tool.y },
        onMouseDown: (ev) => ev.preventDefault(), onPointerDown: (ev) => ev.preventDefault() },
        h('button', { className: 'y', title: '노랑 형광펜', onClick: () => apply('hl', 'y') }, ''),
        h('button', { className: 'g', title: '초록 형광펜', onClick: () => apply('hl', 'g') }, ''),
        h('button', { className: 'p', title: '분홍 형광펜', onClick: () => apply('hl', 'p') }, ''),
        h('button', { className: 'u', title: '밑줄', onClick: () => apply('ul') }, '밑줄'),
        h('button', { title: '고른 부분의 표시 지우기', onClick: () => apply('x') }, '지우기')));
  }

  global.RichDoc = RichDoc;
  global.RichDocClassify = classify;     // 시험용
})(window);
