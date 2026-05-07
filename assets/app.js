// 앱 부트스트랩 — 모듈 결합 + 이벤트 와이어 + 초기화.
import { createSecondaryPageRenderers } from './secondary_pages.js?v=20260507-2';
import { appState } from './app/state.js?v=20260507-2';
import {
  apiErrorMessage,
  escHtml,
  fetchJson,
  hideSearchResults,
  setElementState,
  showRuntimeError,
} from './app/dom_utils.js?v=20260507-2';
import { toDateStr } from './app/calendar.js?v=20260507-2';
import { doSearch, selectResult } from './app/search.js?v=20260507-2';

// ────────────────────────────────────────────────
// 전역 에러 핸들러
// ────────────────────────────────────────────────
window.addEventListener('error', event => {
  showRuntimeError(event.error || event.message);
});
window.addEventListener('unhandledrejection', event => {
  showRuntimeError(event.reason || 'Unhandled promise rejection');
});

// ────────────────────────────────────────────────
// 공휴일 (data/holidays.json 단일 소스) — appState로 노출해 다른 모듈이 await
// ────────────────────────────────────────────────
appState.holidaysReady = fetchJson('/data/holidays.json')
  .then(arr => { appState.holidays = new Set(arr); })
  .catch(e => console.warn('공휴일 데이터 로드 실패, 주말만 판정합니다:', e));

// ────────────────────────────────────────────────
// 페이지 전환 (about / warning / forecast / fortune / patchnotes)
// ────────────────────────────────────────────────
const { renderFortune, renderMarketForecast, renderPatchNotes } = createSecondaryPageRenderers({
  apiErrorMessage,
  appState,
  escHtml,
  fetchJson,
  setElementState,
});

function switchPage(page, el) {
  const targetPage = document.getElementById('page-' + page);
  if (!targetPage) return;
  const activeNav = el || document.querySelector(`[data-page="${page}"]`);
  appState.ui.activePage = page;

  document.querySelectorAll('.page-section').forEach(panel => {
    const active = panel === targetPage;
    panel.classList.toggle('active', active);
    panel.hidden = !active;
    panel.setAttribute('aria-hidden', active ? 'false' : 'true');
  });

  const navButtons = Array.from(document.querySelectorAll('.nav-title, .nav-item'));
  navButtons.forEach((btn, idx) => {
    const active = btn === activeNav;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
    btn.tabIndex = active || (!activeNav && idx === 0) ? 0 : -1;
    if (active) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });

  document.body.classList.toggle('is-warning-active', page === 'warning');
  document.body.classList.toggle('is-terminal-active', page === 'warning' || page === 'about' || page === 'forecast' || page === 'fortune' || page === 'patchnotes');
  if (page !== 'warning') hideSearchResults();
  if (page === 'forecast') renderMarketForecast();
  if (page === 'fortune') renderFortune();
  if (page === 'patchnotes') renderPatchNotes();
}

// 초기 로드 시 소개 화면이 default active 이므로 body 클래스 반영
document.body.classList.add('is-terminal-active');

// 로컬 서버 상태 확인 (file:// 직접 열기일 때 검색 기능 비활성)
function checkServer() {
  if (appState.serverBase === null) {
    document.getElementById('serverNotice').classList.add('show');
    document.getElementById('searchBtn').disabled = true;
    document.getElementById('searchBtn').title = '로컬 서버를 먼저 실행하세요';
    document.getElementById('searchInput').title = '로컬 서버를 먼저 실행하세요';
  }
}
checkServer();

// ────────────────────────────────────────────────
// 이벤트 와이어
// ────────────────────────────────────────────────
const navSearchForm = document.getElementById('navSearchForm');
const navTabsEl = document.querySelector('.nav-tabs');
const navTabsWrap = document.querySelector('.nav-tabs-wrap');
const navScrollHintLeft = document.getElementById('navScrollHintLeft');
const navScrollHint = document.getElementById('navScrollHint');
const searchInputEl = document.getElementById('searchInput');
const searchClearBtn = document.getElementById('searchClearBtn');

const pageNavButtons = Array.from(document.querySelectorAll('.nav-title, .nav-item'));
pageNavButtons.forEach((btn, idx) => {
  btn.addEventListener('click', () => switchPage(btn.dataset.page, btn));
  btn.addEventListener('keydown', event => {
    let nextIdx = null;
    if (event.key === 'ArrowRight') nextIdx = (idx + 1) % pageNavButtons.length;
    else if (event.key === 'ArrowLeft') nextIdx = (idx - 1 + pageNavButtons.length) % pageNavButtons.length;
    else if (event.key === 'Home') nextIdx = 0;
    else if (event.key === 'End') nextIdx = pageNavButtons.length - 1;
    if (nextIdx == null) return;
    event.preventDefault();
    const next = pageNavButtons[nextIdx];
    next.focus();
    switchPage(next.dataset.page, next);
  });
});

function focusNavSearch() {
  searchInputEl.focus();
}

function syncSearchClear() {
  if (!searchClearBtn || !searchInputEl) return;
  const hasQuery = searchInputEl.value.trim().length > 0;
  searchClearBtn.hidden = !hasQuery;
}

navSearchForm.addEventListener('submit', (event) => {
  event.preventDefault();
  doSearch();
});

searchInputEl.addEventListener('input', syncSearchClear);
searchInputEl.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') hideSearchResults();
});
if (searchClearBtn) {
  searchClearBtn.addEventListener('click', () => {
    searchInputEl.value = '';
    syncSearchClear();
    hideSearchResults();
    searchInputEl.focus();
  });
}

function syncNavScrollHint() {
  if (!navTabsEl || !navTabsWrap || !navScrollHintLeft || !navScrollHint) return;
  const maxScroll = Math.max(0, navTabsEl.scrollWidth - navTabsEl.clientWidth);
  const canScroll = maxScroll > 2;
  const atScrollStart = !canScroll || navTabsEl.scrollLeft <= 2;
  const atScrollEnd = !canScroll || navTabsEl.scrollLeft >= maxScroll - 2;
  navTabsWrap.classList.toggle('can-scroll', canScroll);
  navTabsWrap.classList.toggle('at-scroll-start', atScrollStart);
  navTabsWrap.classList.toggle('at-scroll-end', atScrollEnd);
  navScrollHintLeft.hidden = atScrollStart;
  navScrollHint.hidden = atScrollEnd;
}

function scrollNavTabs(direction) {
  if (!navTabsEl) return;
  navTabsEl.scrollBy({
    left: direction * Math.max(120, Math.round(navTabsEl.clientWidth * 0.72)),
    behavior: 'smooth',
  });
}

if (navTabsEl && navScrollHintLeft && navScrollHint) {
  navTabsEl.addEventListener('scroll', syncNavScrollHint, { passive: true });
  navScrollHintLeft.addEventListener('click', () => scrollNavTabs(-1));
  navScrollHint.addEventListener('click', () => scrollNavTabs(1));
  window.addEventListener('resize', syncNavScrollHint);
  requestAnimationFrame(syncNavScrollHint);
}

document.getElementById('searchResults').addEventListener('click', (e) => {
  const item = e.target.closest('.result-item');
  if (item && item.dataset.idx != null) {
    selectResult(appState.search.results[item.dataset.idx]);
  }
});

function isTextEntryTarget(target) {
  if (!(target instanceof Element)) return false;
  return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
}

document.addEventListener('keydown', (event) => {
  if (event.key !== '/' || event.defaultPrevented) return;
  if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
  if (isTextEntryTarget(event.target)) return;
  event.preventDefault();
  focusNavSearch();
});

const forecastRefreshBtn = document.getElementById('forecastRefreshBtn');
if (forecastRefreshBtn) {
  forecastRefreshBtn.addEventListener('click', () => renderMarketForecast({ force: true }));
}

window.addEventListener('geunhyeongbot:forecast-check', event => {
  const stockName = event.detail?.stockName || '';
  if (!stockName) return;
  const input = document.getElementById('searchInput');
  input.value = stockName;
  syncSearchClear();
  input.focus();
  doSearch();
});

window.addEventListener('geunhyeongbot:show-warning-page', () => {
  switchPage('warning');
});

// 외부 클릭 시 검색 결과 닫기
document.addEventListener('click', (e) => {
  if (!e.target.closest('.nav-search')) {
    hideSearchResults();
  }
});

// 지정일 기본값(오늘)
document.getElementById('designationDate').value = toDateStr(new Date());

function initTickerTape() {
  const track = document.getElementById('tickerTrack');
  if (!track) return;
  const items = [
    'ㅅㅅㅅ 금지',
    '가즈아 금지',
    '심상정인데? 금지',
    '오늘 xxx 개쎄다 금지',
    '거래대금 언급 금지',
    '거래량 보소 금지',
    '미쳤다 금지',
    '다행이다 금지',
    '차 살까? 금지',
    '계좌 고점이다 금지',
    '나이스! 금지',
    'xxx 왜 안삼? 금지',
    '했제 금지',
    '해외 골프 금지',
  ];
  const segment = items.map(item => `<span class="ticker-item">${escHtml(item)}</span>`).join('');
  track.innerHTML = segment + segment;
}

initTickerTape();
syncSearchClear();
syncNavScrollHint();
