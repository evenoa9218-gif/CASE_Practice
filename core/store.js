/**
 * store.js — 4체계(암기장·선택형·사례형·기록형) 공용 저장 추상화 레이어
 *
 * 설계 원칙:
 *   - API 표면을 먼저 고정한다. 내부 구현(IndexedDB → Firestore)은 나중에 갈아끼운다.
 *   - localStorage는 5MB 한계라 답안 전문을 담기엔 부족 → IndexedDB 사용
 *   - 모든 학습 결과는 쟁점 ID(issueId) 단위로 집계 가능해야 한다
 *
 * 공개 API (이 표면은 바꾸지 말 것 — 앱 4개가 의존):
 *   Store.init(opts)
 *   Store.getUser() / Store.setUser(uid)
 *   Store.record(result)            학습 결과 1건 기록 (선택형 채점/사례형 제출 공용)
 *   Store.getRecords(filter)        기록 조회
 *   Store.deleteRecord(at)
 *   Store.getMastery(subject)       쟁점별 숙달도 집계
 *   Store.getProgress(subject,round) / Store.setProgress(...)
 *   Store.getDraft(key) / Store.setDraft(key,text) / Store.clearDraft(key)
 *   Store.sync()                    (현재 no-op, Firestore 연결 시 구현)
 */
(function (global) {
  'use strict';

  const DB_NAME = 'lawhub';
  const DB_VER = 1;
  const ST_RECORDS = 'records';   // 학습 결과 (사례형 답안, 선택형 정오답)
  const ST_KV = 'kv';             // 진도·설정·임시저장

  let _db = null;
  let _uid = null;
  let _remote = null;             // {url} — Firebase RTDB REST. 없으면 로컬 전용

  // ── IndexedDB 초기화 ─────────────────────────────────
  function openDB() {
    return new Promise((resolve, reject) => {
      if (_db) return resolve(_db);
      const req = indexedDB.open(DB_NAME, DB_VER);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(ST_RECORDS)) {
          const s = db.createObjectStore(ST_RECORDS, { keyPath: 'at' });
          s.createIndex('uid_subject', ['uid', 'subject']);
          s.createIndex('uid_examId', ['uid', 'examId']);
        }
        if (!db.objectStoreNames.contains(ST_KV)) {
          db.createObjectStore(ST_KV, { keyPath: 'k' });
        }
      };
      req.onsuccess = () => { _db = req.result; resolve(_db); };
      req.onerror = () => reject(req.error);
    });
  }

  function tx(store, mode) {
    return openDB().then(db => db.transaction(store, mode).objectStore(store));
  }

  function reqP(r) {
    return new Promise((res, rej) => {
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }

  // ── 원격 동기화 (Firebase RTDB REST) ─────────────────
  async function remoteSet(path, data) {
    if (!_remote) return;
    try {
      await fetch(`${_remote.url}/${path}.json`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    } catch (_) { /* 오프라인이어도 로컬은 이미 저장됨 */ }
  }

  async function remoteGet(path) {
    if (!_remote) return null;
    try {
      const r = await fetch(`${_remote.url}/${path}.json`);
      return r.ok ? await r.json() : null;
    } catch (_) { return null; }
  }

  const safeId = (s) => String(s).replace(/[.#$\[\]\/]/g, '_');

  // ── 공개 API ─────────────────────────────────────────
  const Store = {
    /** @param {{remoteUrl?:string}} opts */
    async init(opts = {}) {
      await openDB();
      if (opts.remoteUrl) _remote = { url: opts.remoteUrl.replace(/\/$/, '') };
      _uid = localStorage.getItem('lawhub_uid') || null;
      return { uid: _uid, remote: !!_remote };
    },

    getUser() { return _uid; },

    setUser(uid) {
      _uid = uid || null;
      if (_uid) localStorage.setItem('lawhub_uid', _uid);
      else localStorage.removeItem('lawhub_uid');
      return _uid;
    },

    isRemote() { return !!_remote; },

    /**
     * 학습 결과 1건 기록.
     * @param {{
     *   subject:string, mode:'mcq'|'case'|'record'|'memo',
     *   examId?:string, label?:string, round?:number,
     *   issueIds?:string[], text?:string, seconds?:number,
     *   correct?:boolean, score?:number, maxScore?:number,
     *   feedback?:object
     * }} result
     */
    async record(result) {
      if (!_uid) throw new Error('Store: 사용자 미설정');
      const rec = {
        at: Date.now(),
        uid: _uid,
        subject: result.subject,
        mode: result.mode || 'case',
        examId: result.examId || null,
        label: result.label || null,
        round: result.round ?? 1,
        issueIds: result.issueIds || [],
        text: result.text || '',
        chars: (result.text || '').length,
        seconds: result.seconds ?? 0,
        correct: result.correct ?? null,
        score: result.score ?? null,
        maxScore: result.maxScore ?? null,
        feedback: result.feedback || null,
      };
      const s = await tx(ST_RECORDS, 'readwrite');
      await reqP(s.add(rec));
      // 원격에는 답안 전문 제외한 요약만 (용량·프라이버시)
      const { text, feedback, ...light } = rec;
      remoteSet(`case_users/${safeId(_uid)}/records/${rec.at}`, light);
      return rec;
    },

    /** @param {{subject?:string, examId?:string, mode?:string, limit?:number}} filter */
    async getRecords(filter = {}) {
      if (!_uid) return [];
      const s = await tx(ST_RECORDS, 'readonly');
      const all = await reqP(s.getAll());
      let out = all.filter(r => r.uid === _uid);
      if (filter.subject) out = out.filter(r => r.subject === filter.subject);
      if (filter.examId) out = out.filter(r => r.examId === filter.examId);
      if (filter.mode) out = out.filter(r => r.mode === filter.mode);
      out.sort((a, b) => b.at - a.at);
      return filter.limit ? out.slice(0, filter.limit) : out;
    },

    async deleteRecord(at) {
      const s = await tx(ST_RECORDS, 'readwrite');
      await reqP(s.delete(at));
      remoteSet(`case_users/${safeId(_uid)}/records/${at}`, null);
    },

    /**
     * 쟁점별 숙달도 집계 — 암기장·통계 화면이 이 값을 읽는다.
     * @returns {Object<string,{attempts:number,lastSeen:number,correct:number,
     *                          avgScore:number|null, modes:string[]}>}
     */
    async getMastery(subject) {
      const recs = await this.getRecords({ subject });
      const m = {};
      for (const r of recs) {
        for (const iid of (r.issueIds || [])) {
          if (!m[iid]) m[iid] = { attempts: 0, correct: 0, scored: 0, scoreSum: 0, lastSeen: 0, modes: new Set() };
          const e = m[iid];
          e.attempts++;
          if (r.correct === true) e.correct++;
          if (typeof r.score === 'number' && r.maxScore) { e.scored++; e.scoreSum += r.score / r.maxScore; }
          e.lastSeen = Math.max(e.lastSeen, r.at);
          e.modes.add(r.mode);
        }
      }
      const out = {};
      for (const [k, e] of Object.entries(m)) {
        out[k] = {
          attempts: e.attempts,
          correct: e.correct,
          lastSeen: e.lastSeen,
          avgScore: e.scored ? +(e.scoreSum / e.scored).toFixed(3) : null,
          modes: [...e.modes],
        };
      }
      return out;
    },

    // ── 진도(회독) ───────────────────────────────────
    async getProgress(subject, round = 1) {
      const v = await this._kvGet(`prog:${_uid}:${subject}:${round}`);
      return v || {};
    },
    async setProgress(subject, round, obj) {
      await this._kvSet(`prog:${_uid}:${subject}:${round}`, obj);
      remoteSet(`case_users/${safeId(_uid)}/progress/${subject}/r${round}`, obj);
    },

    // ── 답안 임시저장 ─────────────────────────────────
    async getDraft(key) { return (await this._kvGet(`draft:${_uid}:${key}`)) || ''; },
    async setDraft(key, text) { return this._kvSet(`draft:${_uid}:${key}`, text); },
    async clearDraft(key) {
      const s = await tx(ST_KV, 'readwrite');
      return reqP(s.delete(`draft:${_uid}:${key}`));
    },

    // ── 내부 KV ──────────────────────────────────────
    async _kvGet(k) {
      const s = await tx(ST_KV, 'readonly');
      const v = await reqP(s.get(k));
      return v ? v.v : null;
    },
    async _kvSet(k, v) {
      const s = await tx(ST_KV, 'readwrite');
      return reqP(s.put({ k, v }));
    },

    /** 원격 → 로컬 병합. 현재는 진도만. (Firestore 전환 시 확장) */
    async sync(subject) {
      if (!_remote || !_uid) return { synced: false };
      let merged = 0;
      for (let r = 1; r <= 4; r++) {
        const remote = await remoteGet(`case_users/${safeId(_uid)}/progress/${subject}/r${r}`);
        if (!remote) continue;
        const local = await this.getProgress(subject, r);
        const next = { ...remote, ...local };   // 로컬 우선
        await this._kvSet(`prog:${_uid}:${subject}:${r}`, next);
        merged++;
      }
      return { synced: true, merged };
    },
  };

  global.Store = Store;
})(window);
