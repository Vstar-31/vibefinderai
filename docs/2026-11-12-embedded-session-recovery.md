# Embedded analysis recovery and readability

Changes are limited to VibeFinderAI's `Themed.AI` frontend branch.

An analysis 401 previously signed out and cleared the prompt. The desktop companion
now supports a correlated renewal request. The module retries the same analysis body
once with the renewed token. There is a 20-second response bound, and concurrent
failures share a renewal. Sign Out, Reset Engine, manual authentication, and unmount
cancel the operation. Older desktops and ordinary browsers retain an explicit
reconnect fallback while preserving prompt and filters. Token changes do not send
another initial APP_READY signal when the signed-in state remains true.

Raised low-contrast foreground labels and placeholders from translucent brown to
opaque warm text. Decorative borders/backgrounds and the palette remain unchanged.
The final visual check is pending because Windows became locked during GUI testing.
This is not presented as a fix for all native missing-text/rendering symptoms.

Validation:

- 22 frontend tests passed, including renewal/retry, unchanged request body, concurrent
  failures, mismatched response IDs, cancellation before/after 401, timeout, old-host
  compatibility, rejected renewal, and standalone fallback.
- Production Vite build passed.
- App.jsx baseline/current lint diagnostics match by rule (8 no-empty, 4 no-unused-vars,
  1 exhaustive-deps). New session modules add no lint findings. Repository-wide legacy
  lint remains non-green (57 diagnostics).
- CI now runs npm test as well as the existing build.
- Native baseline playback loaded Heartbeats and advanced to 0:10/2:42 before the
  test process disappeared. No matching Windows crash event was found; cause unknown.
- Remaining GUI checks: repeated pause/resume, next, minimise/restore, world switching,
  live in-place expiry recovery, contrast, and native missing text.
