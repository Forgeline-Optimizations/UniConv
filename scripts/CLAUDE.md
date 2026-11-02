# Module: scripts

**Status:** Not yet built, planned for Sprint 3 (the sourcing audit starts in Sprint 1).
**Planned responsibility:** `fetch_binaries.py` downloads pinned Pandoc, ffmpeg and ffprobe
per platform (`win32-x86_64`, `darwin-arm64`), verifies SHA-256, extracts to
`vendor/<platform_tag>/`, sets `chmod +x` on macOS, and is idempotent (plan step 21).
**Expand this file when Sprint 3 begins.**
