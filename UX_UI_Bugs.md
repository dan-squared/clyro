# UX, UI, and Bugs Review

## Status
- Date: 2026-03-07
- Scope: repository-wide audit plus two implementation passes
- Validation: `python -m ruff check src tests benchmarks build_release.py`
- Validation: `python -m pytest tests`
- Validation: `python benchmarks/queue_regression.py --check`

## Fixed In Earlier Passes
- Unified the IPC endpoint used by GUI, single-instance detection, and CLI.
- Removed the undeclared `requests` dependency from the CLI by switching to stdlib HTTP.
- Fixed the image-to-PDF merge crash caused by a missing Pillow import.
- Reworked the optimization cache so cache hits are settings-aware and path-aware.
- Added cache invalidation when users force re-optimize, downscale, or undo.
- Replaced fragile batch auto-clear logic that depended on hidden progress bars.
- Wired `image_preserve_metadata` into the actual image processing path.
- Wired `dropzone_enabled` into startup/settings behavior.
- Wired `dropzone_require_alt` into drag acceptance.
- Changed update behavior from silent auto-download/install to notification-only.
- Aligned the main installer version string with the app version.
- Improved second-instance reveal behavior through IPC.

## Fixed In This Pass
1. Folder indexing is now a real visible state.
What changed: directory scans already ran off the UI thread; this pass made them visible as batch rows with a named folder label, indexed file counts, and the same dismiss action used for other batch items. Cancelling that row now cancels the scan cleanly.
What improved: large folder drops no longer feel like an invisible pre-step. Users can see progress, understand that work is happening, and stop the scan if they dropped the wrong folder.

2. Dropzone settings text now matches real behavior.
What changed: the Dropzone settings page now explicitly describes floating-dropzone availability, Alt-gated drops, and the toggle shortcut. The misleading implication of global drag-triggered reveal was removed.
What improved: the settings page now behaves like a control surface instead of partially outdated documentation.

3. App reachability is now explained in-product.
What changed: the About page now includes a System Status section that summarizes access paths, disabled feature groups, and update state. The Dropzone settings page also shows the current saved access path before the user closes the dialog.
What improved: users can tell whether the app is reachable from tray, floating dropzone, or shortcut without guessing.

4. Update discovery is now explicit and user-controlled.
What changed: startup update checks no longer try to install anything. Instead, the app now exposes a manual `Check for Updates` action in both tray and settings, plus an in-app dialog with release notes, `Later`, `Skip This Version`, and `Download`.
What improved: update flow is visible, reversible, and driven by user intent rather than background side effects.

5. Queue result states are now explainable.
What changed: optimization/conversion handlers now emit structured outcomes such as `optimized`, `converted`, `merged`, `skipped_larger`, and `unchanged`, plus short detail text. The single-file and batch UIs render those states distinctly, including clearer cancelled, cached, skipped, and failure messaging.
What improved: users can now distinguish between a deliberate skip, a cancel, a cache hit, a successful conversion, and a real failure.

6. High-impact settings now explain their tradeoffs.
What changed: the General, Quality, and Dropzone pages now include helper text for output placement, skip-if-larger behavior, metadata/privacy, audio/video quality tradeoffs, PDF merge/compression behavior, tray/dropzone reachability, and web download handling.
What improved: fewer settings require trial-and-error to understand, especially around privacy and destructive output behavior.

7. Mixed drop flows and queue cancellation paths now have stronger regression coverage.
What changed: tests now cover cancel-after-queue, retry-after-cancel, direct-file-plus-folder drops, multi-link convert rejection, mixed-type convert rejection, and updater checksum parsing.
What improved: the highest-risk real-world UI flows now have automated protection instead of depending on manual QA memory.

8. Runtime update trust is stronger.
What changed: update checks now look for a published installer checksum from release asset metadata, checksum files, or release notes. The update dialog shows whether a published SHA-256 was found, and the updater can verify a downloaded installer against that checksum if direct install is used again later.
What improved: the update path is still not a signed-update pipeline, but it is no longer blind metadata-only trust.

9. Settings schema drift was reduced.
What changed: config coercion now forces the current schema version on load so older config files do not keep stale schema versions forever after save.
What improved: future migrations become more reliable, and diagnostics around config versioning stop drifting.

## Remaining Risk
1. Update authenticity is checksum-based, not signature-based.
Current state: the app now surfaces published SHA-256 metadata when available and can verify downloads against it, which is a real trust improvement. It still does not validate a signed installer or signed release manifest.
What would improve further: Authenticode verification or a signed update manifest would move release trust from strong checksum hygiene to a fuller publisher-verification model.

## Recommended Next UX Polish
1. Add a first-run tool guidance panel.
Planned user-visible change: if FFmpeg or Ghostscript is missing, show a lightweight first-run explainer with exactly which capabilities are unavailable and where the user can still start.
Expected benefit: smoother onboarding and fewer "why is PDF/video disabled?" moments.

2. Add richer per-result next actions.
Planned user-visible change: failed or skipped jobs could expose context-specific actions such as `Retry aggressive`, `Open settings`, or `Reveal original`.
Expected benefit: the queue would become more self-healing and reduce dead-end outcomes further.
