# Frontend Build ROI

This project currently serves a zero-dependency static SPA through `index.html`,
`assets/app.css`, and `assets/app.js`. The current recommendation is to defer a
bundler until the frontend crosses one of the thresholds below.

## Current Measurements

Measured on 2026-04-24 after extracting inline CSS and JS:

| Asset | Raw | gzip |
| --- | ---: | ---: |
| `index.html` | 13.2 KB | 3.9 KB |
| `assets/app.css` | 49.6 KB | 8.6 KB |
| `assets/app.js` | 47.0 KB | 12.2 KB |
| Total | 109.8 KB | 24.8 KB |

`index.html` is `max-age=0, must-revalidate`; versioned `/assets/*` files are
`max-age=31536000, immutable`. That means repeat visits should usually revalidate
only the 4 KB gzip HTML shell while keeping CSS and JS in browser cache.

## Decision

Do not introduce Vite/esbuild yet.

The current SPA has two tabs, no third-party frontend dependencies, and no
runtime package graph to tree-shake. The patch notes data is already loaded only
when needed, and the initial investment-warning calculator is the primary path.
A bundler would mainly add a build step, package manager maintenance, source-map
handling, deployment path changes, and more cache/versioning conventions.

The highest ROI work has already happened:

- Split HTML, CSS, and JS into separately cacheable files.
- Keep the HTML shell small enough to revalidate cheaply.
- Use immutable versioned static assets.

The per-asset size budget gate (`scripts/check_frontend_budget.py`) was
retired on 2026-05-11. Reasoning: the limits were a self-imposed regression
fence with no external counterpart while Vercel/Upstash free tiers stay far
from saturation. They generated red CI mail without signaling a real
constraint. Re-introduce when an actual constraint bites (Vercel free-tier
bandwidth/cost, Lighthouse regression, user-reported latency).

## Trigger Points

Revisit a bundler when any of these become true:

- `assets/app.js` exceeds 40 KB gzip or 80 KB raw.
- The app grows to three or more substantial tabs with route-specific logic.
- TypeScript, shared component modules, or unit-tested frontend utilities become
  necessary for maintainability.
- Manual asset versioning starts causing release mistakes.
- CSS grows enough that per-route CSS or post-processing would materially reduce
  first-load cost.

## Best First Build Step

If the thresholds are hit, prefer a minimal esbuild pipeline before a full Vite
migration:

1. Move source files to `src/app.js` and `src/app.css`.
2. Emit hashed files to `assets/dist/`.
3. Generate or update the asset tags in `index.html`.
4. Preserve the existing Python local server and Vercel headers.
5. Keep CSP at `script-src 'self'` plus the JSON-LD hash.

Vite becomes worthwhile when local frontend iteration speed, HMR, TypeScript,
and module organization matter more than the extra project machinery.

## Budget Check

Retired on 2026-05-11. See the **Decision** section above.
