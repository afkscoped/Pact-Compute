# Accessibility

Verified 13 November 2026 (Asia/Calcutta). Base Git revision `4bbc1d7077f3d3084df9eb1337b734880ee79181` on `sasha-work`, with the local review patch. Executable source fingerprint `c6441d4bf64cdfa97c3e64e299eb038e9cfd1e0a83cf60d7f4be3380fd52da21`; exact files in [source-manifest.json](source-manifest.json).

Automated axe checks with WCAG A/AA tags returned **zero violations** on sign-in and consumer Home at 390px. [Raw results](accessibility-axe.json). Actual browser checks cover keyboard skip-to-main focus, mobile navigation, 390px document width and reduced-motion emulation. Existing semantic labels and source-linked UI were preserved.

BLOCKED for a complete WCAG 2.2 AA conformance decision: a qualified manual review must cover screen readers, 200% zoom/reflow, focus order/return in every dialog, chart/table alternatives, all roles and dynamically changing errors. Automation on two views cannot certify the whole console. Use the [W3C criteria](https://www.w3.org/TR/WCAG22/) as the review checklist; record browser/assistive technology, view, steps and result for each criterion. [Frontend report](FRONTEND_VALIDATION_REPORT.md).
