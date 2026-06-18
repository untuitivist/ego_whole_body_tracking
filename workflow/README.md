# Workflow

Project-level scripts and adapters for ego whole-body tracking experiments live here.

Planned workflow code should stay thin and explicit:

- read or normalize third-party outputs from `third-parties/`
- align timestamps and coordinate frames
- write reproducible intermediate artifacts under dedicated result folders
- keep model checkpoints, datasets, and local environments out of Git
