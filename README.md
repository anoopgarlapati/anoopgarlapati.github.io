# anoopgarlapati.github.io

Source for [anoopgarlapati.github.io](https://anoopgarlapati.github.io), built with MkDocs and a custom theme in `theme/`.

## Run locally

```bash
uv run mkdocs serve            # http://127.0.0.1:8000
uv run mkdocs build --strict   # same check CI runs before deploying
```

Pushing to `main` deploys to GitHub Pages via `.github/workflows/deploy.yml`.

## Writing

**Article** — add `docs/posts/YYYY-MM-DD-slug.md`. All front matter is optional:

```yaml
---
title: Redis Sentinel + Lettuce: Understanding Failover
description: One or two sentences for the lede, listings, meta description and RSS.
date: 2026-09-29
updated: 2026-10-02          # shown only if different from date
categories: [Redis, Reliability]   # topic or subtopic names; the first is the primary topic
tags: [Redis, Sentinel, Lettuce]
---
```

Use `#` for sections (they render as `<h2>`; the title is the only `<h1>`). Reading time, listings, related articles, prev/next, breadcrumbs, RSS and search are derived by `hooks.py`. An unknown category fails the strict build.

**Topic** — add `docs/topics/<slug>.md` with `template: topic.html`, a `description` and `subtopics:` (list of names), then add it under `Topics` in `mkdocs.yml` `nav`.

**Project** — add `docs/projects/<slug>.md` with `template: project.html`, `category`, `repo` and optional `topics:`, then add it under `Projects` in `nav`.
