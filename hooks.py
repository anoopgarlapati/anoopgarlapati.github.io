"""Build-time data model for the theme.

Pages are classified by convention, so adding content never requires touching
this file:

* articles  -- any page under ``posts/``
* topics    -- pages with ``template: topic.html`` (``subtopics:`` lists subsections)
* projects  -- pages with ``template: project.html``

Articles opt into topics with ``categories:``; each entry may name a topic or a
subtopic. Everything else (reading time, related articles, prev/next, breadcrumbs,
RSS feed, search labels) is derived.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

log = logging.getLogger("mkdocs.hooks.site")

WORDS_PER_MINUTE = 220
RELATED_LIMIT = 3
_state: dict = {}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _as_date(value) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _fmt(d: dt.date | None) -> str:
    return f"{d:%Y-%m-%d}" if d else ""


def _first_paragraph(content: str, limit: int = 180) -> str:
    match = re.search(r"<p>(.*?)</p>", content, re.DOTALL)
    if not match:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


# --------------------------------------------------------------------------- #
# Collection
# --------------------------------------------------------------------------- #


def on_pre_build(config):
    _state.clear()
    _state.update(articles={}, topics={}, projects={}, words={}, order=[])


def on_nav(nav, config, files):
    _state["order"] = [p.file.src_uri for p in nav.pages]
    return nav


def on_page_markdown(markdown, page, config, files):
    _state["words"][page.file.src_uri] = len(re.findall(r"\w+", markdown))
    return markdown


def on_page_content(content, page, config, files):
    # Wide tables scroll inside their own (keyboard-focusable) region instead of the page.
    tables = iter(range(1, content.count("<table>") + 1))
    content = re.sub(
        "<table>",
        lambda _: (
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="Table {next(tables)}"><table>'
        ),
        content,
    ).replace("</table>", "</table></div>")

    meta = page.meta
    src = page.file.src_uri
    description = meta.get("description") or _first_paragraph(content)
    record = {"title": page.title, "url": page.url, "description": description, "page": page}

    if src.startswith("posts/"):
        date = _as_date(meta.get("date"))
        updated = _as_date(meta.get("updated"))
        words = _state["words"].get(src, 0)
        record.update(
            date=date,
            date_display=_fmt(date),
            updated=updated if updated and updated != date else None,
            updated_display=_fmt(updated) if updated and updated != date else "",
            reading_time=max(1, round(words / WORDS_PER_MINUTE)),
            tags=list(meta.get("tags") or []),
            categories=list(meta.get("categories") or []),
        )
        _state["articles"][page.url] = record
    elif meta.get("template") == "topic.html":
        record.update(
            slug=Path(src).stem,
            subtopic_names=list(meta.get("subtopics") or []),
        )
        _state["topics"][page.url] = record
    elif meta.get("template") == "project.html":
        record.update(
            category=meta.get("category") or "Projects",
            repo=meta.get("repo"),
            topic_names=list(meta.get("topics") or []),
        )
        _state["projects"][page.url] = record

    page.meta.setdefault("description", description)
    return content


# --------------------------------------------------------------------------- #
# Linking (runs once, after every page has been read)
# --------------------------------------------------------------------------- #


def _nav_index(record) -> int:
    order = _state["order"]
    src = record["page"].file.src_uri
    return order.index(src) if src in order else len(order)


def _resolve(names, lookup, where):
    """Map category names to (topic, subtopic-or-None) pairs."""
    resolved = []
    for name in names:
        hit = lookup.get(str(name).lower())
        if hit is None:
            log.warning("%s: unknown category %r (not a topic or subtopic)", where, name)
        elif hit not in resolved:
            resolved.append(hit)
    return resolved


def on_env(env, config, files):
    topics = sorted(_state["topics"].values(), key=_nav_index)
    articles = sorted(_state["articles"].values(), key=lambda a: a["date"] or dt.date.min, reverse=True)
    projects = sorted(_state["projects"].values(), key=_nav_index)

    lookup: dict = {}
    for topic in topics:
        topic["subtopics"] = [
            {"name": n, "slug": _slug(n), "url": f"{topic['url']}#{_slug(n)}", "articles": []}
            for n in topic["subtopic_names"]
        ]
        topic.update(articles=[], projects=[], general=[])
        lookup[topic["title"].lower()] = (topic["url"], None)
        for sub in topic["subtopics"]:
            lookup[sub["name"].lower()] = (topic["url"], sub["slug"])

    by_url = {t["url"]: t for t in topics}

    def sub_of(topic, slug):
        return next(s for s in topic["subtopics"] if s["slug"] == slug)

    for art in articles:
        pairs = _resolve(art["categories"], lookup, art["page"].file.src_uri)
        art["topics"], art["subtopics"] = [], []
        for topic_url, slug in pairs:
            topic = by_url[topic_url]
            if topic not in art["topics"]:
                art["topics"].append(topic)
                topic["articles"].append(art)
            if slug:
                sub = sub_of(topic, slug)
                art["subtopics"].append({"topic": topic, **sub})
                sub["articles"].append(art)
        for topic in art["topics"]:
            if not any(s["topic"] is topic for s in art["subtopics"]):
                topic["general"].append(art)
        art["topic"] = art["topics"][0] if art["topics"] else None
        art["subtopic"] = next((s for s in art["subtopics"] if s["topic"] is art["topic"]), None)

    for project in projects:
        pairs = _resolve(project["topic_names"], lookup, project["page"].file.src_uri)
        project["topics"] = []
        for topic_url, _ in pairs:
            topic = by_url[topic_url]
            if topic not in project["topics"]:
                project["topics"].append(topic)
                topic["projects"].append(project)

    # Chronological neighbours and related reading.
    for i, art in enumerate(articles):
        art["newer"] = articles[i - 1] if i > 0 else None
        art["older"] = articles[i + 1] if i + 1 < len(articles) else None
        art["related"] = _related(art, articles)

    _state["pub"] = {"articles": articles, "topics": topics, "projects": projects}
    return env


def _related(art, articles):
    subs = {(s["topic"]["url"], s["slug"]) for s in art["subtopics"]}
    topics = {t["url"] for t in art["topics"]}
    tags = {t.lower() for t in art["tags"]}
    scored = []
    for other in articles:
        if other is art:
            continue
        score = (
            3 * len(subs & {(s["topic"]["url"], s["slug"]) for s in other["subtopics"]})
            + 2 * len(topics & {t["url"] for t in other["topics"]})
            + len(tags & {t.lower() for t in other["tags"]})
        )
        if score:
            scored.append((score, other["date"] or dt.date.min, other))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [s[2] for s in scored[:RELATED_LIMIT]]


# --------------------------------------------------------------------------- #
# Per-page context
# --------------------------------------------------------------------------- #


def _breadcrumbs(article, topic, project):
    """Parent trail shown above the page title (the title itself is the <h1>)."""
    if article is not None:
        crumbs = [{"title": "Writing", "url": "writing/"}]
        if article["topic"]:
            crumbs.append({"title": article["topic"]["title"], "url": article["topic"]["url"]})
        if article["subtopic"]:
            crumbs.append({"title": article["subtopic"]["name"], "url": article["subtopic"]["url"]})
        return crumbs
    if topic is not None:
        return [{"title": "Topics", "url": "topics/"}]
    if project is not None:
        return [{"title": "Projects", "url": "projects/"}]
    return []


def on_page_context(context, page, config, nav):
    article = _state["articles"].get(page.url)
    topic = _state["topics"].get(page.url)
    project = _state["projects"].get(page.url)
    context.update(
        pub=_state["pub"],
        article=article,
        topic=topic,
        project=project,
        breadcrumbs=_breadcrumbs(article, topic, project),
    )
    return context


def on_template_context(context, template_name, config):
    # Static templates such as 404.html have no page but still render the footer.
    context.setdefault("pub", _state.get("pub"))
    return context


# --------------------------------------------------------------------------- #
# Extra outputs
# --------------------------------------------------------------------------- #


def on_post_build(config):
    pub = _state.get("pub")
    if not pub:
        return
    site_dir = Path(config.site_dir)
    site_url = config.site_url.rstrip("/") + "/"

    items = []
    for art in pub["articles"]:
        link = site_url + art["url"]
        pub_date = ""
        if art["date"]:
            published = dt.datetime.combine(art["date"], dt.time(), dt.UTC)
            pub_date = f"<pubDate>{format_datetime(published)}</pubDate>"
        categories = "".join(f"<category>{escape(t['title'])}</category>" for t in art["topics"])
        items.append(
            f"<item><title>{escape(art['title'])}</title><link>{link}</link>"
            f'<guid isPermaLink="true">{link}</guid>{pub_date}'
            f"<description>{escape(art['description'])}</description>{categories}</item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>{escape(config.site_name)}</title><link>{site_url}</link>"
        f"<description>{escape(config.site_description or '')}</description>"
        f'<language>en</language><atom:link href="{site_url}feed.xml" rel="self" type="application/rss+xml"/>'
        + "".join(items)
        + "</channel></rss>\n"
    )
    (site_dir / "feed.xml").write_text(feed, encoding="utf-8")

    # Lets the search UI label and group results without a second index.
    kinds = {
        a["url"]: {"kind": "Articles", "label": a["topic"]["title"] if a["topic"] else ""}
        for a in pub["articles"]
    }
    kinds.update({t["url"]: {"kind": "Topics", "label": "Topic"} for t in pub["topics"]})
    kinds.update({p["url"]: {"kind": "Projects", "label": p["category"]} for p in pub["projects"]})
    (site_dir / "search" / "meta.json").write_text(json.dumps(kinds), encoding="utf-8")
