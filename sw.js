/**
 * sw.js — 사례형 연습 서비스워커 (스코프 `/CASE_Practice/`)
 *
 * 왜 넣나: 답안을 쓰는 앱인데 지하철·강의실처럼 신호가 끊기는 곳에서 아예 안 열렸다.
 * 답안 초안은 IndexedDB 에 있으니 **앱 껍데기와 문제 데이터만 살려 두면**
 * 오프라인에서도 이어서 쓸 수 있다. (AI 채점은 어차피 네트워크가 필요하다)
 *
 * 전략:
 *   문서·앱 자산  network-first — 배포한 화면이 곧바로 보여야 한다.
 *                 캐시 우선으로 두면 고쳐 배포해도 한 번은 옛 화면이 뜬다.
 *   data/*.json  cache-first + 뒤에서 갱신 — 문제 데이터는 잘 안 바뀌고 크다.
 *                 먼저 내주어 빨리 열리게 하고, 새 판은 다음 방문에 반영된다.
 *   교차 오리진   손대지 않는다 — 채점 Worker 호출을 가로채면 안 된다.
 */
'use strict';

const VERSION = 'cp-v1';
const SHELL = `case-shell-${VERSION}`;
const DATA = `case-data-${VERSION}`;
const KEEP = new Set([SHELL, DATA]);
const BASE = new URL(self.registration.scope).pathname;   // '/CASE_Practice/'

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(SHELL);
    // 개별 실패가 설치 전체를 막지 않게 하나씩 넣는다.
    await Promise.all([BASE, BASE + 'index.html', BASE + 'core/store.js'].map(
      (u) => c.add(new Request(u, { cache: 'reload' })).catch(() => {}),
    ));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((n) => (n.startsWith('case-shell-') || n.startsWith('case-data-')) && !KEEP.has(n))
      .map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

const ok = (r) => r && r.ok && r.status === 200 && r.type === 'basic';

async function networkFirst(req, cacheName, fallback) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (ok(res)) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req);
    if (hit) return hit;
    if (fallback) {
      const fb = await cache.match(fallback);
      if (fb) return fb;
    }
    throw err;
  }
}

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  const fresh = fetch(req).then((res) => {
    if (ok(res)) cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  if (hit) return hit;                 // 있으면 곧바로, 갱신은 뒤에서
  const res = await fresh;
  if (res) return res;
  throw new Error('offline and not cached');
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (req.headers.has('range')) return;

  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.origin !== self.location.origin) return;   // 채점 Worker 호출 등은 그대로 통과

  const p = url.pathname;
  if (!p.startsWith(BASE)) return;

  if (p.includes('/data/') && p.endsWith('.json')) {
    e.respondWith(cacheFirst(req, DATA));
    return;
  }
  e.respondWith(networkFirst(req, SHELL, req.mode === 'navigate' ? BASE + 'index.html' : null));
});
