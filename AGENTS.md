## Theme

- Layout: one two-column grid (`.grid`: context `aside` | `.grid-main`) shared by header, page head, body and footer (`theme/layout.html`). Pages fill blocks `title`, `lede`, `strip` (article metadata), `aside`, `body`.
- Templates: `main.html` (posts + plain pages), `home/writing/topics/topic/projects/project/404.html`; shared macros in `partials/lists.html` (`/ LABEL`, rows, filter tabs) and `partials/toc.html`.
- Styling: single `theme/css/site.css`; colours are `light-dark()` tokens (grey + `--accent` indigo). Light/dark/system all work without JS.
- JS (`theme/js/site.js`, progressive only): theme toggle, single-key nav shortcuts (`data-key` = first letter of nav title; W/T/P/A/M and `/` are taken), search overlay on `search/search_index.json` + `search/meta.json`, scrollspy, reading progress, copy buttons, lazy Mermaid from CDN.

## Gotchas

- `toc.baselevel: 2`: write sections with `#`; the page title is the only `<h1>`.
- `theme.name: null`: `404.html` only builds via `static_templates`; search plugin runs with `search_index_only: true` (UI is custom).
- Jinja: macros using `| url` must be imported `with context`; imports in a parent template aren't visible in child blocks.
- On `404.html` `base_url` is `/`; build home links as `base_url | trim('/') ~ '/'`.
- Avoid generic class names Mermaid uses (e.g. `.label`); ours is `.section-label`. Mermaid colours are literal hex in `site.js` — keep in sync with CSS tokens.
- Visually-hidden (absolute) spans inside horizontally scrolling rows need a positioned ancestor, or mobile gets horizontal overflow.
- Only `html { scroll-padding-top }` offsets anchors; don't add `scroll-margin` too.

## Limitations

- No `og:image`; no posts use Mermaid yet; topics exist only where content exists (no AI/Distributed Systems yet).

## Learned User Preferences

- Prefers a light, simple, uncluttered design; pushes back when the theme feels heavy.
- Visual direction: mostly grey palette with a subtle indigo accent (applied consistently, including the favicon), layout between stripe.dev and claude.dev blogs.
- Prefers understated site copy: no "Built with MkDocs" credit, no "engineering" qualifier in taglines.
- Wants documentation kept to a short README.md rather than long audit/record documents committed to the repo.
- Prefers concise commit messages.

## Learned Workspace Facts

- Personal MkDocs blog deployed to GitHub Pages; dependencies managed with uv (`uv run mkdocs serve`, `uv run mkdocs build --strict`).
- CI deploys on push to `main` via `.github/workflows/deploy.yml` using `uv run mkdocs gh-deploy --force --strict`.
- Custom theme lives in `theme/` (`custom_dir`); `theme/js/site.js` provides the search UI on top of the built-in search index.
- `hooks.py` derives reading time, listings, related articles, prev/next, breadcrumbs, RSS and search data; unknown post categories fail the strict build.
- Articles live in `docs/posts/YYYY-MM-DD-slug.md`; existing article URLs must never change.
- Topics are `docs/topics/<slug>.md` (`template: topic.html`) and projects are `docs/projects/<slug>.md` (`template: project.html`), both registered in `mkdocs.yml` nav.
- README.md documents local run and authoring conventions.
