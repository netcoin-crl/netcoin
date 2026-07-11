# v0.42 Website UI Clarity and Copy-Reduction Pass

This release audits the public website surfaces and removes unnecessary visual and copy noise without adding new product areas.

## Design flaws found

- The feature directory was always visible and competed with the page's primary job.
- Product-completion panels repeated long explanations instead of showing short status, action, and next step blocks.
- Local notes over-explained privacy on every page.
- Profile/mode descriptions and directory subtitles were too long for small screens.
- Completion cards used too much padding and paragraph copy.
- Internal proof/Phase language appeared before user-facing tasks.

## What changed

- The feature directory is now collapsed behind a compact **Directory** control.
- Command palette, notification center, mode copy, directory subtitles, and completion panels were shortened.
- v0.42 CSS adds compact card density, shorter panel intros, tighter timeline rows, and better mobile scan paths.
- Strict browser/accessibility proof tokens remain visible, so prior proof gates continue to work.

## Non-goals

This is not a mainnet-readiness claim. Hardware wallet devices, CAPTCHA credentials, custody proof, external audit, public soak, and incident-history evidence remain separate strict gates.
