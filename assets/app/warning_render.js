// 결과 카드(투자경고/투자주의) 렌더 — 순수 DOM 조작.
import {
  escHtml,
  fmt,
  stateMessageHtml,
  showSearchMessage,
} from './dom_utils.js?v=20260507-5';
import { countTradingDays } from './calendar.js?v=20260507-5';

export function hideWarningCards() {
  const rc = document.getElementById('resultCard');
  if (rc) {
    rc.classList.remove('show');
    ['sec-chart', 'sec-rules'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    const v = document.getElementById('sec-verdict');
    if (v) v.style.display = 'none';
  }
}

export function hideCautionCard() {
  document.getElementById('cautionCard').style.display = 'none';
}

export function showNotWarning() {
  showSearchMessage('현재 투자경고가 아님.');
  hideWarningCards();
  hideCautionCard();
}

function _cautionMetaHtml(d, showIndex) {
  const codeLabel = d.code ? ` (${escHtml(d.code)}${d.market ? '·' + escHtml(d.market) : ''})` : '';
  let html = `종목: <strong>${escHtml(d.stockName)}</strong>${codeLabel}`;

  const an = d.activeNotice;
  if (an) {
    html += ` &nbsp;|&nbsp; 지정예고일: <strong>${escHtml(an.noticeDate)}</strong>` +
            ` &nbsp;|&nbsp; 판단 기간: <strong>${escHtml(an.firstJudgmentDate)} ~ ${escHtml(an.lastJudgmentDate)}</strong>` +
            ` (판단일 ${escHtml(an.judgmentDayIndex)}/${escHtml(an.judgmentWindowTotal)})`;
  } else if (d.latestDesignationDate) {
    html += ` &nbsp;|&nbsp; 지정일: <strong>${escHtml(d.latestDesignationDate)}</strong>`;
    if (d.designationReason) html += ` &nbsp;|&nbsp; 사유: <strong>${escHtml(d.designationReason)}</strong>`;
  }

  if (showIndex && d.escalation) {
    const e = d.escalation;
    const idxTxt = typeof e.indexClose === 'number' ? e.indexClose.toLocaleString('ko-KR', { maximumFractionDigits: 2 }) : '';
    html += `<br/>현재가 <strong>${fmt(e.tClose)}원</strong> (${escHtml(e.tDate)})`;
    if (idxTxt) html += ` &nbsp;|&nbsp; ${escHtml(d.indexSymbol || '지수')} <strong>${idxTxt}</strong>`;
  }
  return html;
}

export function renderCaution(d) {
  const card = document.getElementById('cautionCard');
  const meta = document.getElementById('cautionMeta');
  const content = document.getElementById('cautionContent');
  const verdict = document.getElementById('cautionVerdict');

  meta.innerHTML = _cautionMetaHtml(d, true);

  const e = d.escalation;
  const setHtml = (s) => {
    const statusCls = s.allMet ? 'met' : 'unmet';
    const statusTxt = s.allMet ? '모두 충족' : '해당 없음';
    const conds = s.conditions.map(c => `
      <div class="caution-cond">
        <div class="caution-cond-mark ${c.met ? 'met' : 'unmet'}">${c.met ? '충족' : '미충족'}</div>
        <div>
          <div class="caution-cond-label">${escHtml(c.label)}</div>
          <div class="caution-cond-detail">${escHtml(c.detail)}</div>
        </div>
      </div>`).join('');
    return `
      <div class="caution-set">
        <div class="caution-set-head">
          <span class="caution-set-title">${escHtml(s.label)}</span>
          <span class="caution-set-status ${statusCls}">${statusTxt}</span>
        </div>
        ${conds}
      </div>`;
  };
  content.innerHTML = e.sets.map(setHtml).join('');

  verdict.classList.remove('keep', 'release', 'soft');
  verdict.style.display = '';
  const h = e.headline || { verdict: 'none' };
  if (h.verdict === 'strong') {
    const matched = e.sets[h.matchedSet];
    verdict.classList.add('keep');
    verdict.textContent = `→ 투자경고 지정 예상 · ${matched.label} 충족`;
  } else if (d.forecastSignal?.riskLevel === 'near') {
    verdict.classList.add('soft');
    verdict.textContent = `→ 투자경고 지정 근접 · ${d.forecastSignal.remainingText || '공개 가격조건 근접'}`;
  } else {
    verdict.classList.add('release');
    verdict.textContent = '→ 투자경고 지정 미해당';
  }

  card.style.display = 'block';
}

export function renderCautionNonPrice(d) {
  const card = document.getElementById('cautionCard');
  const meta = document.getElementById('cautionMeta');
  const content = document.getElementById('cautionContent');
  const verdict = document.getElementById('cautionVerdict');

  meta.innerHTML = _cautionMetaHtml(d, false);
  content.innerHTML = `
    <div class="caution-nonprice">
      이 종목은 <strong>${escHtml(d.designationReason || '')}</strong> 사유로 투자주의 지정되었습니다.<br/>
      가격 기반 투자경고 격상 조건(단기급등/중장기급등)은 적용되지 않습니다.
    </div>`;
  verdict.classList.remove('keep', 'release', 'soft');
  verdict.style.display = 'none';
  verdict.textContent = '';
  card.style.display = 'block';
}

export function renderCautionPartial(d) {
  const card = document.getElementById('cautionCard');
  const meta = document.getElementById('cautionMeta');
  const content = document.getElementById('cautionContent');
  const verdict = document.getElementById('cautionVerdict');
  verdict.classList.remove('keep', 'release', 'soft');
  verdict.style.display = 'none';
  verdict.textContent = '';

  meta.innerHTML = _cautionMetaHtml(d, false);
  const msg = d.status === 'code_not_found'
    ? '종목코드를 찾을 수 없어 격상 요건을 계산할 수 없습니다.'
    : `주가/지수 조회 불가: ${d.errorMessage || '알 수 없는 오류'}`;
  content.innerHTML = stateMessageHtml(msg, 'error');
  card.style.display = 'block';
}

// §2 Symbol header — partial (no price yet) or full (with price)
export function renderSymHeader(stockName, code, market, designationDate, priceData) {
  const h = document.getElementById('sym-header');
  if (!h) return;

  const tickerEl = h.querySelector('.ticker');
  const nameEl = h.querySelector('.name');
  const metaEl = h.querySelector('.meta');
  const chipsEl = h.querySelector('.chips');
  const valEl = h.querySelector('.px .val');
  const chgEl = h.querySelector('.px .chg');

  tickerEl.textContent = code || '------';
  nameEl.textContent = stockName || '—';

  const metaParts = [];
  if (market) metaParts.push(market);
  if (designationDate) metaParts.push('지정 ' + designationDate);
  metaEl.textContent = metaParts.join(' · ');

  chipsEl.innerHTML = '<span class="chip warn">투자경고 지정중</span>';

  if (priceData) {
    const close = priceData.tClose;
    const prev = priceData.prevClose || close;
    const delta = close - prev;
    const pct = prev ? (delta / prev * 100) : 0;
    const upDn = delta > 0 ? 'up' : delta < 0 ? 'dn' : '';
    const arrow = delta > 0 ? '▲' : delta < 0 ? '▼' : '·';
    valEl.textContent = fmt(close);
    valEl.classList.remove('up', 'dn');
    if (upDn) valEl.classList.add(upDn);
    chgEl.textContent = `${arrow} ${fmt(Math.abs(delta))} · ${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
    chgEl.classList.remove('up', 'dn');
    if (upDn) chgEl.classList.add(upDn);
  } else {
    valEl.textContent = '--';
    valEl.classList.remove('up', 'dn');
    chgEl.textContent = '';
    chgEl.classList.remove('up', 'dn');
  }
}

// §3 Timeline — 11 cells (D0 → T+1..T+9 → 해제)
export function renderTimeline(designationDate, today, releaseDate) {
  const track = document.querySelector('#sec-timeline .tm-tl-track');
  const foot = document.querySelector('#sec-timeline .tm-tl-foot');
  if (!track || !foot) return;

  const hasReleaseDate = releaseDate instanceof Date && !Number.isNaN(releaseDate.getTime());
  let daysPassed;
  if (today < designationDate) {
    daysPassed = 0;
  } else {
    const count = countTradingDays(designationDate, today);
    daysPassed = Math.max(0, Math.min(10, count - 1));
  }

  const labels = ['D0', 'T+1', 'T+2', 'T+3', 'T+4', 'T+5', 'T+6', 'T+7', 'T+8', 'T+9', hasReleaseDate ? '해제' : '보류'];
  track.innerHTML = labels.map((lbl, i) => {
    let cls = 'future';
    if (i === 10) cls = 'release';
    else if (i < daysPassed) cls = 'past';
    else if (i === daysPassed) cls = 'today';
    else cls = '';
    return `<div class="tm-tl-cell ${cls}">${lbl}</div>`;
  }).join('');

  const fmtDate = d => {
    if (!(d instanceof Date) || Number.isNaN(d.getTime())) return '—';
    const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  };
  foot.querySelector('.d1').textContent = fmtDate(designationDate);
  foot.querySelector('.d2').textContent = fmtDate(today) + ` · ${Math.min(daysPassed, 10)}거래일 경과`;
  foot.querySelector('.d3').textContent = hasReleaseDate ? fmtDate(releaseDate) : '산정 보류';

  const src = document.querySelector('#sec-timeline .tm-sec-head .src');
  if (src) {
    const dDay = Math.max(0, 10 - daysPassed);
    src.textContent = !hasReleaseDate ? '산정 보류' : (daysPassed >= 10 ? '해제 심사 가능' : `T · ${daysPassed}거래일 경과 · D-${dDay}`);
  }
}

// §4 Conditions table — 3 rows driven by t.policy (lookback / multiplier / 고가 윈도우)
export function renderConditions(t) {
  const tbody = document.getElementById('conditionsTbody');
  if (!tbody) return;
  const p = t.policy || { t5Lookback: 5, t5Multiplier: 1.6, t15Lookback: 15, t15Multiplier: 2, maxWindowDays: 15 };

  function statusReasonLabel(reason) {
    if (reason === 'future_judgment_date') return '판단일 전';
    if (reason === 'future_basis_date') return '기준일 전';
    if (reason === 'missing_basis_price') return '기준가 대기';
    if (reason === 'missing_evaluation_price') return '판단가 대기';
    return '보류';
  }

  function statusLabel(met, status, statusReason) {
    if (status === 'unavailable') return { cls: 'clear', flag: statusReasonLabel(statusReason) };
    return met ? { cls: 'hold', flag: '유지' } : { cls: 'clear', flag: '이탈' };
  }

  function pctText(tClose, thresh) {
    const close = Number(tClose);
    const threshold = Number(thresh);
    if (!Number.isFinite(close) || !Number.isFinite(threshold) || threshold === 0) return { text: '—', cls: '' };
    const pct = (close - threshold) / threshold * 100;
    return { text: `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`, cls: pct >= 0 ? 'up' : 'dn' };
  }

  function row(num, formula, desc, baseDate, baseClose, ratio, thresh, tClose, met, status, statusReason) {
    const { cls: statusCls, flag } = statusLabel(met, status, statusReason);
    const pct = pctText(tClose, thresh);
    return `
      <tr class="${statusCls}">
        <td>
          <div class="lbl-col">
            <div class="badge">${num}</div>
            <div class="txt">
              <div class="n">${formula}</div>
              <div class="d">${desc}</div>
            </div>
          </div>
        </td>
        <td class="num">${escHtml(baseDate)}</td>
        <td class="num">${fmt(baseClose)}</td>
        <td>${ratio}</td>
        <td class="num accent">${fmt(thresh)}</td>
        <td class="num ${pct.cls}">${fmt(tClose)}</td>
        <td class="num ${pct.cls}">${pct.text}</td>
        <td><span class="flag ${statusCls}">${flag}</span></td>
      </tr>`;
  }

  function row3(t, windowDays) {
    const { cls: statusCls, flag } = statusLabel(t.cond3, t.cond3Status, t.cond3StatusReason);
    const pct = pctText(t.tClose, t.max15);
    return `
      <tr class="${statusCls}">
        <td>
          <div class="lbl-col">
            <div class="badge">3</div>
            <div class="txt">
              <div class="n">= ${windowDays}일 최고가</div>
              <div class="d">${windowDays}일 최고가 테스트</div>
            </div>
          </div>
        </td>
        <td class="num">${escHtml(t.max15Date)}</td>
        <td class="num">${fmt(t.max15)}</td>
        <td>—</td>
        <td class="num accent">${fmt(t.max15)}</td>
        <td class="num ${pct.cls}">${fmt(t.tClose)}</td>
        <td class="num ${pct.cls}">${pct.text}</td>
        <td><span class="flag ${statusCls}">${flag}</span></td>
      </tr>`;
  }

  const pct1 = Math.round((p.t5Multiplier - 1) * 100);
  const pct2 = Math.round((p.t15Multiplier - 1) * 100);
  const formula1 = `T-${p.t5Lookback} 종가 × ${p.t5Multiplier}`;
  const formula2 = `T-${p.t15Lookback} 종가 × ${p.t15Multiplier}`;
  const desc1 = `${p.t5Lookback}일 ${pct1}% 급등 테스트`;
  const desc2 = `${p.t15Lookback}일 ${pct2}% 급등 테스트`;
  const ratio1 = `${p.t5Multiplier}×`;
  const ratio2 = `${p.t15Multiplier}×`;

  tbody.innerHTML =
    row(1, formula1, desc1, t.t5Date, t.t5Close, ratio1, t.thresh1, t.tClose, t.cond1, t.cond1Status, t.cond1StatusReason) +
    row(2, formula2, desc2, t.t15Date, t.t15Close, ratio2, t.thresh2, t.tClose, t.cond2, t.cond2Status, t.cond2StatusReason) +
    row3(t, p.maxWindowDays);
}

// §5 Verdict — release / hold variants
export function renderVerdict(t, releaseDate) {
  const v = document.getElementById('sec-verdict');
  if (!v) return;

  const hasReleaseDate = releaseDate instanceof Date && !Number.isNaN(releaseDate.getTime());
  const anyClear = !t.cond1 || !t.cond2 || !t.cond3;
  const missing = [];
  if (!t.cond1) missing.push('①');
  if (!t.cond2) missing.push('②');
  if (!t.cond3) missing.push('③');

  v.classList.remove('hold', 'risk');
  v.style.display = 'flex';

  const fmtDate = d => {
    if (!(d instanceof Date) || Number.isNaN(d.getTime())) return '—';
    const m = String(d.getMonth() + 1).padStart(2, '0'), dd = String(d.getDate()).padStart(2, '0');
    return `${m}-${dd}`;
  };

  const tagEl = v.querySelector('.tag');
  const hEl = v.querySelector('.h');
  const bEl = v.querySelector('.b');
  const dEl = v.querySelector('.side .d');

  if (t.unavailable) {
    tagEl.textContent = '산정 보류';
    hEl.textContent = '투자경고 해제 가능일 산정 보류';
    bEl.textContent = t.unavailableReason || '가격 또는 거래정지 상태를 확인할 수 없어 해제 조건을 산정하지 못했습니다.';
    dEl.textContent = '—';
    return;
  }

  if (anyClear) {
    tagEl.textContent = '해제 예정';
    hEl.textContent = `${fmtDate(releaseDate)} 투자경고 해제 예정`;
    bEl.textContent = `조건 ${missing.join('·')} 미충족 — KRX §4-2 기준상 해제 판단일에 세 조건 중 하나라도 미충족이면 해제 대상으로 판정됩니다.`;
    dEl.textContent = hasReleaseDate ? fmtDate(releaseDate) : '—';
  } else {
    v.classList.add('hold');
    const p = t.policy;
    const summary = `① T-${p.t5Lookback} × ${p.t5Multiplier}, ② T-${p.t15Lookback} × ${p.t15Multiplier}, ③ ${p.maxWindowDays}일 최고가`;
    tagEl.textContent = '경고 유지';
    hEl.textContent = '3가지 조건 모두 충족 · 경고 유지';
    bEl.textContent = `${summary} — 세 조건이 동시에 충족되어 투자경고가 유지됩니다.`;
    dEl.textContent = '—';
  }
}

// §7 KRX Rules — static 4 items
export function renderRules(releaseDate) {
  const box = document.getElementById('rulesContent');
  if (!box) return;

  const fmtDate = d => {
    if (!d) return '—';
    const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), dd = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
  };

  box.innerHTML = `
    <div class="r"><span class="k">1</span><span class="v">지정일로부터 10 매매거래일 경과 후 해제 심사 시작</span><span class="m num">${fmtDate(releaseDate)}</span></div>
    <div class="r"><span class="k">2</span><span class="v">해제 판단일에 ① ② ③ 세 조건 모두 충족 시 경고 유지. 하나라도 미충족이면 해제 대상.</span><span class="m">3 중 3</span></div>
    <div class="r"><span class="k">3</span><span class="v">지정 기간 중 신용융자 금지, 위탁증거금 100% 현금</span><span class="m">—</span></div>
    <div class="r"><span class="k">4</span><span class="v">실제 지정과 해제는 KRX 최종 공시 기준을 따릅니다.</span><span class="m">KRX</span></div>`;
}

// Chart legend (§6) — T 종가 + 3 thresholds as swatches
export function renderChartLegend(t, priceData) {
  const legend = document.getElementById('chartLegend');
  if (!legend) return;
  let tEntry = '';
  if (typeof t.tClose === 'number') {
    let lastColor = 'var(--color-text-primary)';
    const prices = priceData && Array.isArray(priceData.prices) ? priceData.prices : null;
    if (prices && prices.length >= 2) {
      const delta = prices[prices.length - 1].close - prices[prices.length - 2].close;
      lastColor = delta >= 0 ? 'var(--color-danger)' : 'var(--color-blue)';
    }
    tEntry = `<span class="t-mark">T ${escHtml(t.tDate || '')} · 종가 <b style="color:${lastColor}">${fmt(t.tClose)}</b></span>`;
  }
  legend.innerHTML = `
    ${tEntry}
    <span><span class="sw" style="background:var(--color-primary)"></span>① ${fmt(t.thresh1)}</span>
    <span><span class="sw" style="background:var(--color-danger)"></span>② ${fmt(t.thresh2)}</span>
    <span><span class="sw" style="background:var(--color-success)"></span>③ ${fmt(t.max15)}</span>`;
}
