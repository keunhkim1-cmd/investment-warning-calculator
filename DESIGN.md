# Design Rules — 근형봇

이 문서는 `DESIGN-import.md`를 현재 정적 SPA 구조에 맞게 이식한 최종 디자인 계약이다.
새 UI와 디자인 수정은 이 문서를 기준으로 하고, 참고 원본인 `DESIGN-import.md`보다 이 문서가 우선한다.

기준 구현은 다음 파일이다.

- `assets/css/base.css`: 색상, 타이포그래피, radius, 공통 컴포넌트 토큰의 source of truth
- `index.html`: 정적 app shell과 접근성 ID/role의 source of truth
- `assets/app/*.js`, `assets/secondary_pages.js`: 동적 렌더링 클래스 계약의 source of truth

근형봇은 KRX 시장경보와 기업 공시를 빠르게 확인하는 업무형 금융 리서치 도구다. 화면은 장식보다 회사명, 종목코드, 날짜, 가격, 조건 판정을 먼저 보여준다.

## 1. Visual Identity

- 기본 화면은 밝은 work surface다: `#f2f4f6` 배경, 흰 surface, 얇은 회색 border.
- primary action은 blue가 아니라 거의 검정에 가까운 neutral이다.
- 상태색은 의미가 있을 때만 사용하며, 색상만으로 상태를 전달하지 않는다.
- 화면은 marketing landing page가 아니라 오래 켜두는 업무 도구처럼 보여야 한다.
- 로그인, 주문, 잔고, 관심종목, 개인화 피드는 제품 범위가 아니다.
- 즐거움 요소는 독립 탭에 작고 조용하게 둔다. 전역 장식 ticker, glow, blob, glass, 과한 hero는 금지한다.

## 2. Tokens

모든 새 스타일은 token first로 작성한다. 임의 hex, 임의 font-size, 임의 radius를 feature code에 추가하지 않는다.

### Font

제품 UI 글꼴은 Pretendard 우선 단일 산세리프 스택이다.

```css
font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

- 숫자, 날짜, 접수번호, 종목코드도 같은 글꼴을 쓴다.
- 숫자 정렬은 `font-variant-numeric: tabular-nums`로 처리한다.
- `font-mono`, `font-serif`, 새 외부 폰트는 도입하지 않는다.
- letter spacing은 기본 `0`이다. viewport width 기반 font scaling은 금지한다.

### Typography

CSS 변수 `--text-t1`부터 `--text-t9`만 사용한다.

| Token | Size | Line height | 용도 |
| --- | ---: | ---: | --- |
| `--text-t1` | 30px | 40px | 매우 드문 큰 결과 상태 |
| `--text-t2` | 26px | 35px | 독립 page title roomy |
| `--text-t3` | 22px | 31px | 독립 page title compact |
| `--text-t4` | 17px | 25.5px | 중요한 단일 데이터 강조 |
| `--text-t5` | 15px | 22.5px | section/card title, 주요 행 제목 |
| `--text-t6` | 14px | 21px | nav, label, table header |
| `--text-t7` | 13px | 19.5px | 설명, 날짜, 코드, compact body |
| `--text-t8` | 12px | 18px | badge, dense table cell |
| `--text-t9` | 11px | 16.5px | helper, xsmall button |

허용 weight는 400, 500, 600, 700이다. 700은 예외적 강조에만 쓴다.

### Colors

Primitive palette는 `--tds-*`, 실제 구현은 semantic `--color-*`를 사용한다.

- `--color-background`: app background
- `--color-surface`: 주요 카드, header, table cell
- `--color-surface-raised`: dropdown, overlay panel
- `--color-border`: 기본 divider, control border
- `--color-border-strong`: table header boundary, dropdown border
- `--color-text-primary`: 주요 텍스트
- `--color-text-secondary`: 보조 설명
- `--color-text-tertiary`: metadata, placeholder
- `--color-primary`: primary action
- `--color-primary-pressed`: primary hover/pressed
- `--color-primary-weak`: selected/hover background
- `--color-blue`, `--color-blue-weak`: report/category 정보
- `--color-success`, `--color-success-weak`: 성공, 해제 가능, 충족
- `--color-danger`, `--color-danger-weak`: 실패, 위험, 오류, 유지 위험
- `--color-warning`, `--color-warning-weak`: 투자경고, 보류, caution
- `--color-info`, `--color-info-weak`: 보조 정보

색상 규칙:

- primary button에 blue/green/purple을 쓰지 않는다.
- red는 실패, 위험, 유지/연장 위험에만 쓴다.
- green은 성공, 해제, 조건 통과에만 쓴다.
- yellow는 투자경고, 보류, 주의에만 쓴다.
- 상태 표현은 색상과 텍스트 label, badge, marker 중 하나 이상을 함께 사용한다.

### Radius And Stroke

- `--radius-surface: 8px`: 카드, dropdown, error panel
- `--radius-control: 12px`: search field, button, nav item
- badge는 `999px` pill을 허용한다.
- 구조는 shadow가 아니라 border로 만든다. 일반 카드 shadow는 금지한다.

## 3. Layout

- app shell max width는 `1280px`를 기본으로 한다.
- page padding은 mobile `16px`, tablet `24px`, desktop `32px`다.
- page gap은 16px 또는 20px를 기본으로 한다.
- 모바일에서는 한 column 업무 흐름을 유지한다.
- 표는 모바일에서 축소하지 않고 horizontal scroll을 유지한다.
- page section을 장식용 floating card처럼 겹겹이 만들지 않는다.

## 4. Component Contracts

### Top Navigation

- sticky top, 흰 surface, bottom border.
- mobile에서는 wrapping보다 horizontal scroll을 우선한다.
- active tab은 `aria-current="page"`와 neutral weak background로 표시한다.
- durable section은 popover가 아니라 route/tab으로 노출한다.

### Surface And Section

- 기본 surface는 `border: 1px solid var(--color-border)`, `background: var(--color-surface)`, `border-radius: var(--radius-surface)`.
- ordinary card padding은 16px, roomy card는 20px까지 허용한다.
- surface 안에 nested card를 만들지 않는다. 내부 구분은 `border-top`, `divide-y`, table row border로 한다.
- section title은 `--text-t5`, 600, primary color를 기본으로 한다.

### Search

- 검색은 근형봇의 1차 workflow다.
- placeholder는 `회사명 또는 종목코드`처럼 허용 입력을 말한다.
- `role="search"`와 접근 가능한 label을 유지한다.
- focus는 primary border와 weak ring으로 표시한다.
- 값이 있으면 clear button을 제공한다.
- submit button visible text는 `검색`이다.

### Button

- 버튼 variant는 `fill` 또는 `weak`, color는 `primary`, `danger`, `light`만 사용한다.
- primary fill은 neutral background다.
- icon-only/clear button은 `aria-label`을 가진다.
- loading button은 disabled와 안정적인 폭을 유지한다.

### Badge And Status

- badge는 빠른 상태 인식용이며 텍스트 label을 반드시 포함한다.
- `success`, `danger`, `warning`, `info`, `primary` tone만 사용한다.
- 반복 row 안 badge는 작은 pill을 기본으로 한다.

### Table

- wrapper는 horizontal scroll을 허용한다.
- header는 `--text-t8`, 600, tertiary color.
- numeric/date/code cell은 `tabular-nums`, right align이 기본이다.
- 첫 컬럼 label은 left align이다.
- empty cell은 `—`와 tertiary color를 쓴다.

### State Message

- loading/empty/error는 중앙 정렬을 허용한다.
- empty는 neutral, error는 danger weak background와 `role="alert"`를 사용한다.
- skeleton, empty, error copy를 동시에 보여주지 않는다.

## 5. Legacy Compatibility

현재 DOM과 JS는 `.warning-terminal`, `.tm-*`, `.forecast-*`, `.patch-*` 클래스를 사용한다. 이 이름은 호환 layer로 유지하지만, 시각 언어는 밝은 디자인 토큰을 따른다.

새 코드에서 다음을 직접 사용하지 않는다.

- `--tm-*`
- `--fs-*`
- `--mono`
- hard-coded dark colors
- terminal-only letter spacing

## 6. Verification

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
- 주요 표는 horizontal scroll 또는 충분한 min-width로 읽힌다.
- 검색, 예보 점검, 운세, 패치 노트 탭이 모두 동작한다.
