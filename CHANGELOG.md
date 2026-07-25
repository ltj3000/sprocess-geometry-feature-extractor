# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [1.0.0] - 2026-07-25

### Added

- Initial public release of the Sprocess geometry feature extractor toolkit.
- DF-ISE `.grd` boundary extraction for a target region/material within a rough ROI.
- Ordered contour generation and vertex compression.
- Automatic protrusion/recess detection based on both local slope behavior and physical background-edge direction.
- Remote Sentaurus VM wrapper script for SSH-based execution.
- Example ROI configuration and GitHub-ready repository structure.
- Skill packaging via `SKILL.md` for reuse in personal knowledge workflows.

### Notes

- Automatic feature detection is heuristic and works best when the ROI isolates the intended contour branch.
- For difficult shapes, narrowing the ROI remains the preferred refinement strategy.
