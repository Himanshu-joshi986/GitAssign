# Examples

## `demo_buggy_service.py`

A small, intentionally buggy service used by the **Demo Scan** workflow. Each
`BUG-*` marker is detected by GitAssign and turned into a queued issue. This is
a deterministic demo fixture, not a general static-analysis engine.

To try it:

1. Open the dashboard and enter or load a repository.
2. Go to the **Demo Scan** tab.
3. Upload `demo_buggy_service.py`.
4. Open the generated issues in the queue to preview recommendations.

The same scanner runs automatically during GitHub ingestion for up to 25 small
source files.
