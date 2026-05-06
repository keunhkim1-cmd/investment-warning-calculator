# 근형봇 — Style Reference
> Bright Market Research Desk — a quiet, work-focused interface for checking KRX market alerts, disclosures, prices, dates, and rule outcomes quickly.

**Theme:** light

근형봇은 KRX 시장경보와 기업 공시를 빠르게 확인하는 업무형 금융 리서치 도구다. 화면은 장식보다 회사명, 종목코드, 날짜, 가격, 조건 판정을 먼저 보여준다. 이 문서는 `DESIGN-import.md`를 현재 정적 SPA 구조에 맞게 이식한 최종 디자인 계약이며, 새 UI와 디자인 수정은 이 문서를 기준으로 한다.

기준 구현은 다음 파일이다.

- `assets/css/base.css`: 색상, 타이포그래피, radius, 공통 컴포넌트 토큰의 source of truth
- `index.html`: 정적 app shell과 접근성 ID/role의 source of truth
- `assets/app/*.js`, `assets/secondary_pages.js`: 동적 렌더링 클래스 계약의 source of truth

## Tokens — Colors

모든 새 스타일은 token first로 작성한다. 임의 hex를 feature code에 추가하지 않고, primitive palette는 `--tds-*`, 실제 구현은 semantic `--color-*`를 사용한다.

| Name | Value | Token | Role |
|------|-------|-------|------|
| Grey 50 | `#f9fafb` | `--tds-grey-50` | 가장 밝은 neutral tint, 보조 배경 후보 |
| Grey 100 | `#f2f4f6` | `--tds-grey-100` | app background, hover/selected weak background |
| Grey 200 | `#e5e8eb` | `--tds-grey-200` | 기본 divider, control border |
| Grey 300 | `#d1d6db` | `--tds-grey-300` | 강한 border, table header boundary |
| Grey 400 | `#b0b8c1` | `--tds-grey-400` | disabled 또는 낮은 대비 metadata |
| Grey 500 | `#8b95a1` | `--tds-grey-500` | tertiary text, placeholder, dense metadata |
| Grey 600 | `#6b7684` | `--tds-grey-600` | 보조 neutral text 후보 |
| Grey 700 | `#4e5968` | `--tds-grey-700` | secondary text |
| Grey 800 | `#333d4b` | `--tds-grey-800` | primary pressed/hover neutral |
| Grey 900 | `#191f28` | `--tds-grey-900` | primary text, primary action fill |
| Blue 50 | `#e8f3ff` | `--tds-blue-50` | report/category 정보 weak background |
| Blue 500 | `#3182f6` | `--tds-blue-500` | report/category 정보, link-like emphasis |
| Green 50 | `#f0faf6` | `--tds-green-50` | 성공, 해제 가능, 조건 통과 weak background |
| Green 500 | `#03b26c` | `--tds-green-500` | 성공, 해제 가능, 조건 통과 |
| Red 50 | `#ffeeee` | `--tds-red-50` | 실패, 위험, 오류 weak background |
| Red 500 | `#f04452` | `--tds-red-500` | 실패, 위험, 오류, 유지/연장 위험 |
| Yellow 50 | `#fff9e7` | `--tds-yellow-50` | 투자경고, 보류, 주의 weak background |
| Yellow 500 | `#ffc342` | `--tds-yellow-500` | caution accent 후보, 직접 사용보다 semantic token 우선 |
| Teal 50 | `#edf8f8` | `--tds-teal-50` | 보조 정보 weak background |
| Teal 500 | `#18a5a5` | `--tds-teal-500` | 보조 정보 |
| Background | `var(--tds-grey-100)` | `--color-background` | 전체 app canvas |
| Surface | `#ffffff` | `--color-surface` | 주요 카드, header, table cell |
| Raised Surface | `#ffffff` | `--color-surface-raised` | dropdown, overlay panel |
| Border | `var(--tds-grey-200)` | `--color-border` | 기본 divider, control border |
| Strong Border | `var(--tds-grey-300)` | `--color-border-strong` | table header boundary, dropdown border |
| Primary Text | `var(--tds-grey-900)` | `--color-text-primary` | 주요 텍스트 |
| Secondary Text | `var(--tds-grey-700)` | `--color-text-secondary` | 설명, 보조 문장 |
| Tertiary Text | `var(--tds-grey-500)` | `--color-text-tertiary` | metadata, placeholder |
| Primary Action | `var(--tds-grey-900)` | `--color-primary` | primary fill button, focus outline |
| Primary Pressed | `var(--tds-grey-800)` | `--color-primary-pressed` | primary hover/pressed |
| Primary Weak | `var(--tds-grey-100)` | `--color-primary-weak` | selected/hover neutral background |
| Blue | `var(--tds-blue-500)` | `--color-blue` | report/category 정보 |
| Blue Weak | `var(--tds-blue-50)` | `--color-blue-weak` | report/category 정보 background |
| Success | `var(--tds-green-500)` | `--color-success` | 성공, 해제, 조건 통과 |
| Success Weak | `var(--tds-green-50)` | `--color-success-weak` | 성공 상태 background |
| Danger | `var(--tds-red-500)` | `--color-danger` | 실패, 위험, 오류, 유지 위험 |
| Danger Weak | `var(--tds-red-50)` | `--color-danger-weak` | 위험 상태 background |
| Warning | `#b77900` | `--color-warning` | 투자경고, 보류, caution |
| Warning Weak | `var(--tds-yellow-50)` | `--color-warning-weak` | 주의 상태 background |
| Info | `var(--tds-teal-500)` | `--color-info` | 보조 정보 |
| Info Weak | `var(--tds-teal-50)` | `--color-info-weak` | 보조 정보 background |

색상 규칙:

- Primary button에 blue, green, purple을 쓰지 않는다.
- Red는 실패, 위험, 오류, 유지/연장 위험에만 쓴다.
- Green은 성공, 해제, 조건 통과에만 쓴다.
- Yellow는 투자경고, 보류, 주의에만 쓴다.
- 상태 표현은 색상과 텍스트 label, badge, marker 중 하나 이상을 함께 사용한다.

## Tokens — Typography

제품 UI 글꼴은 Pretendard 우선 단일 산세리프 스택이다. 숫자, 날짜, 접수번호, 종목코드도 같은 글꼴을 쓰고, 숫자 정렬은 `font-variant-numeric: tabular-nums`로 처리한다.

### Pretendard UI — Primary typeface for all product UI text, labels, tables, controls, and compact financial data. · `--font-ui`

- **Substitute:** `-apple-system`, `BlinkMacSystemFont`, `"Segoe UI"`, `sans-serif`
- **Weights:** 400, 500, 600, 700
- **Letter spacing:** `0`
- **Role:** 장시간 켜두는 업무 도구에 맞는 중립적이고 읽기 쉬운 UI 글꼴. 새 외부 폰트, `font-mono`, `font-serif`는 도입하지 않는다.

### Type Scale

CSS 변수 `--text-t1`부터 `--text-t9`만 사용한다. 700 weight는 예외적 강조에만 쓴다.

| Role | Size | Line Height | Letter Spacing | Token |
|------|------|-------------|----------------|-------|
| result-lg | 30px | 40px | 0 | `--text-t1` |
| page-title-roomy | 26px | 35px | 0 | `--text-t2` |
| page-title-compact | 22px | 31px | 0 | `--text-t3` |
| data-emphasis | 17px | 25.5px | 0 | `--text-t4` |
| section-title | 15px | 22.5px | 0 | `--text-t5` |
| nav-label | 14px | 21px | 0 | `--text-t6` |
| compact-body | 13px | 19.5px | 0 | `--text-t7` |
| dense-cell | 12px | 18px | 0 | `--text-t8` |
| helper | 11px | 16.5px | 0 | `--text-t9` |

## Tokens — Spacing & Shapes

**Base unit:** 4px

**Density:** compact comfortable

### Layout Scale

| Name | Value | Token | Role |
|------|-------|-------|------|
| Page max width | 1280px | `--page-max` | app shell max width |
| Mobile gutter | 16px | `--page-gutter` | default page padding |
| Tablet gutter | 24px | `--page-gutter @ min-width 640px` | tablet page padding |
| Desktop gutter | 32px | `--page-gutter @ min-width 1024px` | desktop page padding |
| Page gap | 20px | `--page-gap` | 기본 page section gap |

### Border Radius

| Element | Value | Token |
|---------|-------|-------|
| cards, dropdowns, error panels | 8px | `--radius-surface` |
| search fields, buttons, nav items | 12px | `--radius-control` |
| badges | 999px | component-local pill |

### Shadows

| Name | Value | Token | Role |
|------|-------|-------|------|
| focus ring | `0 0 0 3px rgba(25, 31, 40, 0.08)` | `--shadow-focus` | focused controls only |

### Layout Rules

- 모바일에서는 한 column 업무 흐름을 유지한다.
- 표는 모바일에서 축소하지 않고 horizontal scroll을 유지한다.
- Page section을 장식용 floating card처럼 겹겹이 만들지 않는다.
- 구조는 shadow가 아니라 border로 만든다. 일반 카드 shadow는 금지한다.

## Components

### Top Navigation
**Role:** Primary app navigation between durable sections.

Sticky top, 52px height, white translucent surface, bottom border. Mobile에서는 wrapping보다 horizontal scroll을 우선한다. Active tab은 `aria-current="page"`와 neutral weak background로 표시한다. Durable section은 popover가 아니라 route/tab으로 노출한다.

### Surface And Section
**Role:** Main content grouping for search, results, forecasts, fortune, and release notes.

Use `border: 1px solid var(--color-border)`, `background: var(--color-surface)`, `border-radius: var(--radius-surface)`. Ordinary card padding은 16px, roomy card는 20px까지 허용한다. Surface 안에 nested card를 만들지 않고, 내부 구분은 `border-top`, `divide-y`, table row border로 처리한다.

### Search
**Role:** Primary workflow entry point.

Placeholder는 `회사명 또는 종목코드`처럼 허용 입력을 말한다. `role="search"`와 접근 가능한 label을 유지한다. Focus는 primary border와 weak ring으로 표시한다. 값이 있으면 clear button을 제공하고, submit button visible text는 `검색`이다.

### Button
**Role:** Commands and compact workflow actions.

Variant는 `fill` 또는 `weak`, color는 `primary`, `danger`, `light`만 사용한다. Primary fill은 neutral background다. Icon-only 또는 clear button은 `aria-label`을 가진다. Loading button은 disabled와 안정적인 폭을 유지한다.

### Badge And Status
**Role:** Fast status recognition in rows, summaries, and rule outcomes.

Badge는 텍스트 label을 반드시 포함한다. Tone은 `success`, `danger`, `warning`, `info`, `primary`만 사용한다. 반복 row 안 badge는 작은 pill을 기본으로 한다.

### Table
**Role:** Dense financial, disclosure, price, and date data.

Wrapper는 horizontal scroll을 허용한다. Header는 `--text-t8`, weight 600, tertiary color. Numeric, date, code cell은 `tabular-nums`, right align이 기본이다. 첫 컬럼 label은 left align이다. Empty cell은 `—`와 tertiary color를 쓴다.

### State Message
**Role:** Loading, empty, and error feedback.

Loading, empty, error는 중앙 정렬을 허용한다. Empty는 neutral tone, error는 danger weak background와 `role="alert"`를 사용한다. Skeleton, empty, error copy를 동시에 보여주지 않는다.

## Do's and Don'ts

### Do

- 밝은 work surface를 기본으로 유지한다: `#f2f4f6` 배경, 흰 surface, 얇은 회색 border.
- 사용자가 보는 page title, section title, hero, kicker, eyebrow, badge성 보조 헤더는 한국어를 기본으로 한다.
- 회사명, 종목코드, 날짜, 가격, 조건 판정이 장식보다 먼저 읽히게 한다.
- KRX, DART, NAVER, AI처럼 공식 약어나 고유 서비스명은 출처, 데이터명, 명령 설명에만 제한적으로 사용한다.
- Status color는 의미가 있을 때만 사용하고, 색상 외 label, badge, marker를 함께 제공한다.
- 프론트엔드 변경 후 `scripts/check_frontend_smoke.py`로 영어-only 헤더가 다시 들어오지 않았는지 확인한다.

### Don't

- `Warning Check`, `Research Terminal`, `Market Alert Forecast`, `Daily Fortune`, `Release Log`처럼 장식용 영어 헤더를 새로 만들지 않는다.
- Marketing landing page처럼 과한 hero, glow, blob, glass, 전역 장식 ticker를 만들지 않는다.
- 로그인, 주문, 잔고, 관심종목, 개인화 피드를 제품 범위에 넣지 않는다.
- Primary action에 blue, green, purple을 쓰지 않는다.
- Surface 안에 nested card를 만들거나 일반 카드 shadow로 elevation을 만들지 않는다.
- 임의 font-size, 임의 radius, hard-coded dark colors를 feature code에 추가하지 않는다.

## Surfaces

| Level | Name | Value | Purpose |
|-------|------|-------|---------|
| 0 | Work Canvas | `var(--color-background)` / `#f2f4f6` | 전체 app background |
| 1 | Main Surface | `var(--color-surface)` / `#ffffff` | 주요 카드, header, table cell |
| 2 | Raised Surface | `var(--color-surface-raised)` / `#ffffff` | dropdown, overlay panel |
| 3 | Weak Neutral | `var(--color-primary-weak)` / `#f2f4f6` | selected tab, hover, weak grouping |
| 4 | Status Weak Areas | `--color-*-weak` | success, danger, warning, info 상태 배경 |

## Elevation

근형봇은 elevation을 shadow가 아니라 surface color, border, divider, spacing으로 만든다. 일반 카드 shadow는 금지하고, `--shadow-focus`는 focused control에만 사용한다. Dropdown과 overlay는 `--color-surface-raised`와 `--color-border-strong`으로 구분한다.

## Imagery

제품 UI는 이미지나 장식 그래픽보다 데이터 판독성을 우선한다. 즐거움 요소는 독립 탭에 작고 조용하게 두며, 핵심 업무 화면에는 전역 장식 ticker, glow, blob, glass, dark hero를 넣지 않는다. 아이콘은 기능을 설명하거나 조작 대상을 분명히 할 때만 사용한다.

## Legacy Compatibility

현재 DOM과 JS는 `.warning-terminal`, `.tm-*`, `.forecast-*`, `.patch-*` 클래스를 사용한다. 이 이름은 호환 layer로 유지하지만, 시각 언어는 밝은 디자인 토큰을 따른다.

새 코드에서 다음을 직접 사용하지 않는다.

- `--tm-*`
- `--fs-*`
- `--mono`
- hard-coded dark colors
- terminal-only letter spacing

## Agent Prompt Guide

### Quick Color Reference

- Primary Text: `#191f28` via `--color-text-primary`
- Page Background: `#f2f4f6` via `--color-background`
- Surface: `#ffffff` via `--color-surface`
- Primary Action: `#191f28` via `--color-primary`
- Border: `#e5e8eb` via `--color-border`
- Info Blue: `#3182f6` via `--color-blue`
- Success: `#03b26c` via `--color-success`
- Danger: `#f04452` via `--color-danger`
- Warning: `#b77900` via `--color-warning`

### Example Component Prompts

1. Create a search panel: White surface, 8px radius, 1px `--color-border`, 16px padding. Title `종목 검색` uses `--text-t5`, weight 600, `--color-text-primary`. Input placeholder is `회사명 또는 종목코드`, 12px control radius, visible submit button label `검색`.
2. Create a warning status badge: Small pill badge with visible Korean label. Use `--color-danger` and `--color-danger-weak` only when the row represents failure, risk, error, or warning-maintenance risk.
3. Create a dense disclosure table: Header uses `--text-t8`, weight 600, `--color-text-tertiary`. Date and code cells use tabular numbers and right alignment. Keep horizontal scroll on mobile.
4. Create a top navigation bar: Sticky 52px white translucent surface with bottom border. Active route uses `aria-current="page"` and `--color-primary-weak`; labels remain Korean.

## Similar Products

- **KRX 정보데이터시스템** — 공시와 시장경보 데이터를 빠르게 확인하는 업무형 정보 구조.
- **DART** — 문서와 접수번호 중심의 판독성 높은 공시 탐색 경험.
- **Toss Securities** — 밝은 neutral 기반, 명확한 상태색, 빠른 모바일 판독성.
- **Linear** — 장시간 사용에 맞춘 compact density, 조용한 surface hierarchy, 명확한 keyboard/workflow affordance.

## Quick Start

### CSS Custom Properties

```css
:root {
  /* Primitive colors */
  --tds-grey-50: #f9fafb;
  --tds-grey-100: #f2f4f6;
  --tds-grey-200: #e5e8eb;
  --tds-grey-300: #d1d6db;
  --tds-grey-400: #b0b8c1;
  --tds-grey-500: #8b95a1;
  --tds-grey-600: #6b7684;
  --tds-grey-700: #4e5968;
  --tds-grey-800: #333d4b;
  --tds-grey-900: #191f28;
  --tds-blue-50: #e8f3ff;
  --tds-blue-500: #3182f6;
  --tds-green-50: #f0faf6;
  --tds-green-500: #03b26c;
  --tds-red-50: #ffeeee;
  --tds-red-500: #f04452;
  --tds-yellow-50: #fff9e7;
  --tds-yellow-500: #ffc342;
  --tds-teal-50: #edf8f8;
  --tds-teal-500: #18a5a5;

  /* Semantic colors */
  --color-background: var(--tds-grey-100);
  --color-surface: #ffffff;
  --color-surface-raised: #ffffff;
  --color-border: var(--tds-grey-200);
  --color-border-strong: var(--tds-grey-300);
  --color-text-primary: var(--tds-grey-900);
  --color-text-secondary: var(--tds-grey-700);
  --color-text-tertiary: var(--tds-grey-500);
  --color-primary: var(--tds-grey-900);
  --color-primary-pressed: var(--tds-grey-800);
  --color-primary-weak: var(--tds-grey-100);
  --color-blue: var(--tds-blue-500);
  --color-blue-weak: var(--tds-blue-50);
  --color-success: var(--tds-green-500);
  --color-success-weak: var(--tds-green-50);
  --color-danger: var(--tds-red-500);
  --color-danger-weak: var(--tds-red-50);
  --color-warning: #b77900;
  --color-warning-weak: var(--tds-yellow-50);
  --color-info: var(--tds-teal-500);
  --color-info-weak: var(--tds-teal-50);

  /* Typography */
  --font-ui: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --text-t1: 30px;
  --text-t2: 26px;
  --text-t3: 22px;
  --text-t4: 17px;
  --text-t5: 15px;
  --text-t6: 14px;
  --text-t7: 13px;
  --text-t8: 12px;
  --text-t9: 11px;
  --leading-t1: 40px;
  --leading-t2: 35px;
  --leading-t3: 31px;
  --leading-t4: 25.5px;
  --leading-t5: 22.5px;
  --leading-t6: 21px;
  --leading-t7: 19.5px;
  --leading-t8: 18px;
  --leading-t9: 16.5px;

  /* Shape and layout */
  --radius-surface: 8px;
  --radius-control: 12px;
  --shadow-focus: 0 0 0 3px rgba(25, 31, 40, 0.08);
  --page-max: 1280px;
  --page-gutter: 16px;
  --page-gap: 20px;
}
```

## Verification

프론트엔드 변경 후 다음을 통과해야 한다.

```bash
python3 scripts/sync_frontend_metadata.py --check
python3 scripts/check_frontend_smoke.py
python3 scripts/check_frontend_budget.py
python -m pytest tests/test_playwright_flows.py --disable-socket --allow-hosts=127.0.0.1,localhost
```

브라우저에서 desktop `1280x900`, mobile `390x844` 기준으로 확인한다.

- 배경이 dark가 아니다.
- 카드 radius는 8px, control radius는 12px다.
- 텍스트와 버튼이 겹치지 않는다.
- 장식용 영어 헤더나 영어-only 제목이 보이지 않는다.
- 주요 표는 horizontal scroll 또는 충분한 min-width로 읽힌다.
- 검색, 예보 점검, 운세, 패치 노트 탭이 모두 동작한다.
