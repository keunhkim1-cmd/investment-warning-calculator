// 검색 / 가격 조회 / 결과 렌더 오케스트레이션.
import {
  apiErrorMessage,
  escHtml,
  fetchJson,
  hideSearchResults,
  safeStockCode,
  setConditionsTableState,
  setSearchResultsBusy,
  setSearchResultsOpen,
  showSearchError,
  showSearchLoading,
  showSearchMessage,
} from './dom_utils.js?v=20260507-5';
import { appState, isCurrentSearch, isCurrentWarning } from './state.js?v=20260507-5';
import {
  hideCautionCard,
  hideWarningCards,
  renderChartLegend,
  renderConditions,
  renderRules,
  renderSymHeader,
  renderTimeline,
  renderVerdict,
  showNotWarning,
} from './warning_render.js?v=20260507-5';
import { renderInlineChart, syncTvChartByName } from './chart.js?v=20260507-5';
import { addTradingDays } from './calendar.js?v=20260507-5';

// ────────────────────────────────────────────────
// KRX KIND 검색
// ────────────────────────────────────────────────
function showWarningPage() {
  window.dispatchEvent(new CustomEvent('geunhyeongbot:show-warning-page'));
}

export async function doSearch() {
  const inputEl = document.getElementById('searchInput');
  const query = inputEl.value.trim();
  if (!query) {
    showSearchMessage('종목명을 입력하세요.');
    inputEl.focus();
    return;
  }

  if (appState.serverBase === null) {
    showSearchMessage('로컬 서버가 필요합니다. 터미널에서 python3 serve.py 를 실행한 뒤 다시 시도하세요.');
    return;
  }

  const searchRequestId = ++appState.search.requestId;
  appState.warning.requestId += 1;

  // TV 차트는 즉시 동기화 (경고 여부와 무관)
  syncTvChartByName(query);

  const btn = document.getElementById('searchBtn');

  btn.disabled = true;
  btn.textContent = '조회 중...';
  showSearchLoading('조회 중...');

  try {
    const url = `/api/warn-search?name=${encodeURIComponent(query)}`;
    const data = await fetchJson(url);
    if (!isCurrentSearch(searchRequestId)) return;

    const apiError = apiErrorMessage(data);
    if (apiError || data.error) {
      showSearchError(apiError || data.error);
      return;
    }

    const results = (data.results || []).filter(r => r.level === '투자경고');
    if (results.length === 0) {
      hideWarningCards();
      if (data.message) {
        hideCautionCard();
        showSearchMessage(data.message);
        return;
      }
      showNotWarning();
      return;
    }
    hideCautionCard();

    if (results.length === 1) {
      hideSearchResults();
      selectResult(results[0]);
      return;
    }

    renderSearchResults(results);
  } catch (e) {
    if (!isCurrentSearch(searchRequestId)) return;
    showSearchError(`서버 연결 오류: ${e.message}`);
  } finally {
    if (isCurrentSearch(searchRequestId)) {
      btn.disabled = false;
      btn.textContent = '검색';
    }
  }
}

export function renderSearchResults(results) {
  appState.search.results = results;
  const resultsEl = document.getElementById('searchResults');

  const header = `<div class="search-results-header">${results.length}건의 지정 이력 — 항목을 클릭하면 자동 입력됩니다</div>`;

  const items = results.map((r, idx) => {
    const optionLabel = `${r.stockName || '종목명 없음'} ${r.level || '지정 이력'} ${r.designationDate || '날짜 없음'} 선택`;
    return `
      <button type="button" class="result-item" data-idx="${idx}" aria-label="${escHtml(optionLabel)}">
        <div class="result-item-left">
          <span class="result-stock-name">${escHtml(r.stockName || '—')}</span>
          <span class="result-level-badge level-warning">${escHtml(r.level)}</span>
        </div>
        <div class="result-date">${escHtml(r.designationDate)}</div>
      </button>`;
  }).join('');

  resultsEl.innerHTML = header + items;
  setSearchResultsBusy(false);
  setSearchResultsOpen(true);
}

export function selectResult(r) {
  const warningRequestId = ++appState.warning.requestId;
  hideCautionCard();
  const name = r.stockName || document.getElementById('searchInput').value;
  document.getElementById('stockName').value = name;
  document.getElementById('designationDate').value = r.designationDate;
  hideSearchResults();
  showWarningPage();

  // 사용자가 클릭한 종목으로 TV 차트 즉시 동기화
  syncTvChartByName(name);

  // 기준가 조회 → 해제 여부 판별 후 결과 표시
  checkAndDisplay(r, warningRequestId);
}

async function checkAndDisplay(r, warningRequestId) {
  const requestId = warningRequestId || ++appState.warning.requestId;
  await appState.holidaysReady;
  if (!isCurrentWarning(requestId)) return;

  if (r.level !== '투자경고') {
    showNotWarning();
    return;
  }

  await calculate();
  if (!isCurrentWarning(requestId)) return;
  fetchPriceThresholds(r.stockName, requestId);
}

// ────────────────────────────────────────────────
// 기준가 조회 → 터미널 섹션 스택에 렌더
// ────────────────────────────────────────────────
async function fetchPriceThresholds(stockName, warningRequestId) {
  const requestId = warningRequestId || ++appState.warning.requestId;
  setConditionsTableState('조회 중...', 'loading');

  try {
    const codeData = await fetchJson(`/api/stock-code?name=${encodeURIComponent(stockName)}`);
    if (!isCurrentWarning(requestId)) return;
    const codeError = apiErrorMessage(codeData);
    if (codeError || codeData.error || !codeData.items || codeData.items.length === 0) {
      setConditionsTableState(`종목코드를 찾을 수 없습니다: ${stockName}`, 'error');
      return;
    }
    const item = codeData.items[0];
    const code = safeStockCode(item.code);
    if (!code) {
      setConditionsTableState(`종목코드를 찾을 수 없습니다: ${stockName}`, 'error');
      return;
    }

    const priceData = await fetchJson(`/api/stock-price?code=${encodeURIComponent(code)}`);
    if (!isCurrentWarning(requestId)) return;
    const priceError = apiErrorMessage(priceData);
    if (priceError || priceData.error) {
      setConditionsTableState(priceError || priceData.error, 'error');
      return;
    }

    const t = priceData.thresholds;
    if (t.error) {
      setConditionsTableState(t.error, 'error');
      return;
    }

    const desigStr = document.getElementById('designationDate').value;
    renderSymHeader(stockName, code, item.market, desigStr, t);
    renderConditions(t);
    const releaseDate = appState.warning.releaseDate || new Date();
    renderVerdict(t, releaseDate);
    renderChartLegend(t, priceData);
    renderInlineChart(priceData, code, stockName);

  } catch (e) {
    if (!isCurrentWarning(requestId)) return;
    setConditionsTableState(`가격 조회 오류: ${e.message}`, 'error');
  }
}

// ────────────────────────────────────────────────
// 계산 → 터미널 섹션 스택 렌더
// ────────────────────────────────────────────────
export async function calculate() {
  await appState.holidaysReady;
  const stockName = document.getElementById('stockName').value.trim();
  const designationDateStr = document.getElementById('designationDate').value;
  const tradingStop = document.getElementById('tradingStop').value;
  const resumeDateStr = document.getElementById('resumeDate').value;

  if (!stockName) { showSearchError('종목명을 입력해주세요.'); return; }
  if (!designationDateStr) { showSearchError('지정일을 입력해주세요.'); return; }

  const designationDate = new Date(designationDateStr + 'T00:00:00');
  const today = new Date(); today.setHours(0, 0, 0, 0);

  let startDate;
  if (tradingStop === 'yes2') {
    if (!resumeDateStr) { showSearchError('매매거래 재개일을 입력해주세요.'); return; }
    startDate = new Date(resumeDateStr + 'T00:00:00');
  } else {
    startDate = new Date(designationDate);
  }

  const releaseDate = addTradingDays(startDate, 10);

  // Sym header (partial — price will fill via fetchPriceThresholds)
  renderSymHeader(stockName, null, null, designationDateStr, null);

  // Timeline
  renderTimeline(startDate, today, releaseDate);

  // Release date chip + cache for verdict
  const rc = document.getElementById('resultCard');
  const y = releaseDate.getFullYear();
  const m = String(releaseDate.getMonth() + 1).padStart(2, '0');
  const d = String(releaseDate.getDate()).padStart(2, '0');
  appState.warning.releaseDate = releaseDate;
  rc.dataset.releaseDate = `${y}-${m}-${d}`;

  // Rules
  renderRules(releaseDate);
  document.getElementById('sec-rules').style.display = '';

  rc.classList.add('show');
  showWarningPage();
  rc.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
