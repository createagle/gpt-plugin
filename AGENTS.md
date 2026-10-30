# Createagle GPT plugin distribution

This repository is the user's default distribution source for GPT plugins. Unless explicitly directed elsewhere, add future GPT plugins here under `plugins/<stable-name>/` and register them in `.agents/plugins/marketplace.json`.

- Use portable root `plugin.json` and bundled `skills/` directories. Keep names stable and increment each changed plugin's semantic version.
- Keep the default skill host-neutral. Discover browser, executor, and Pages tools at runtime; put host-specific examples in optional adapters. Do not hardcode machine paths, session IDs, Page IDs, accounts, or credentials.
- Do not claim that pushing GitHub installs a plugin into ChatGPT or proves mobile support. Account/workspace import and runtime capabilities are separate checks.
- Preserve source fidelity, image attachment handling, checkpointing, and user edits. Never silently substitute summaries or external image links.
- Do not commit course content, downloaded user media, session captures, job state, or personal caches. Tests use synthetic fixtures.
- Run `python3 scripts/validate_catalog.py`, `python3 -m unittest discover -s tests`, and `node --test tests/*.test.mjs`. Build distributions with `python3 scripts/package_plugins.py`.
- Before pushing, inspect the changed files and verify the remote head. Never force-push or replace unrelated work.
