"""Build-time data model for the theme.

Pages are classified by convention, so adding content never requires touching
this file:

* articles  -- any page under ``posts/``
* topics    -- pages with ``template: topic.html`` (``subtopics:`` lists subsections)
* projects  -- pages with ``template: project.html``

Articles opt into topics with ``categories:``; each entry may name a topic or a
subtopic. Everything else (reading time, related articles, prev/next, breadcrumbs,
social preview cards, RSS feed, search labels) is derived.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import logging
import math
import random
import re
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

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
        slug = Path(src).stem
        custom_image = meta.get("image")
        image_path = str(custom_image).lstrip("/") if custom_image else f"og/{slug}.png"
        site_url = config.site_url.rstrip("/") + "/"
        record.update(
            slug=slug,
            date=date,
            date_display=_fmt(date),
            updated=updated if updated and updated != date else None,
            updated_display=_fmt(updated) if updated and updated != date else "",
            reading_time=max(1, round(words / WORDS_PER_MINUTE)),
            tags=list(meta.get("tags") or []),
            categories=list(meta.get("categories") or []),
            image=image_path,
            image_url=custom_image if str(custom_image or "").startswith(("http://", "https://")) else site_url + image_path,
            custom_image=bool(custom_image),
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

    # Deterministic Open Graph / social preview cards (1200x630 PNG) per article.
    og_dir = site_dir / "og"
    og_dir.mkdir(parents=True, exist_ok=True)
    for art in pub["articles"]:
        if not art.get("custom_image"):
            _render_og_card(art, config, og_dir / f"{art['slug']}.png")


# --------------------------------------------------------------------------- #
# Deterministic social card generator (1200x630 PNG, 2x supersampled)
# --------------------------------------------------------------------------- #

_SANS_CANDIDATES = [
    ("HelveticaNeue.ttc", 10),  # macOS Helvetica Neue Medium
    ("SFNS.ttf", 0),
    ("DejaVuSans-Bold.ttf", 0),
    ("LiberationSans-Bold.ttf", 0),
    ("Arial Bold.ttf", 0),
    ("Arial.ttf", 0),
]
_SANS_REG_CANDIDATES = [
    ("HelveticaNeue.ttc", 0),
    ("SFNS.ttf", 0),
    ("DejaVuSans.ttf", 0),
    ("LiberationSans-Regular.ttf", 0),
    ("Arial.ttf", 0),
]
_MONO_CANDIDATES = [
    ("Menlo.ttc", 0),
    ("SFNSMono.ttf", 0),
    ("DejaVuSansMono.ttf", 0),
    ("LiberationMono-Regular.ttf", 0),
    ("Courier New.ttf", 0),
]

# Theme palette (2x supersampled canvas matches theme/css/site.css light tokens)
_BG = (244, 244, 245)          # #f4f4f5
_SURFACE = (234, 234, 237)     # #eaeaed
_HEADING = (12, 12, 15)        # #0c0c0f
_FG = (39, 39, 42)             # #27272a
_MUTED = (91, 91, 102)         # #5b5b66
_RULE = (217, 217, 222)        # #d9d9de
_RULE_STRONG = (39, 39, 42)    # #27272a
_ACCENT = (79, 70, 229)        # #4f46e5
_ACCENT_MID = (129, 140, 248)  # #818cf8
_ACCENT_SOFT = (224, 231, 255) # #e0e7ff
_WHITE = (252, 252, 253)

_SECONDARY_ACCENTS = [
    ((12, 100, 117), (196, 233, 240)),   # teal (#0c6475)
    ((91, 63, 208), (226, 217, 252)),    # violet (#5b3fd0)
    ((42, 79, 192), (214, 226, 255)),    # cobalt (#2a4fc0)
    ((15, 107, 71), (204, 238, 223)),    # emerald (#0f6b47)
]


def _load_font(candidates: list[tuple[str, int]], size: int):
    for name, index in candidates:
        try:
            return ImageFont.truetype(name, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines - 1:
                break
    if cur:
        consumed = sum(len(line.split()) for line in lines)
        remaining = " ".join(words[consumed:])
        while draw.textlength(remaining, font=font) > max_width and " " in remaining:
            remaining = remaining.rsplit(" ", 1)[0] + "…"
        lines.append(remaining)
    return lines


def _pick_motif(art: dict, digest: bytes) -> str:
    tokens = " ".join(
        [art["slug"]] + art.get("categories", []) + art.get("tags", [])
    ).lower()
    if any(k in tokens for k in ("container", "appliance", "docker", "k8s", "kubernetes", "cloud", "deploy", "architecture")):
        return "containers"
    if any(k in tokens for k in ("gc", "garbage", "jvm", "memory", "heap", "g1", "cache", "database")):
        return "memory"
    if any(k in tokens for k in ("aop", "pointcut", "aspectj", "spring", "latency", "network", "routing", "proxy")):
        return "lattice"
    if any(k in tokens for k in ("ide", "cursor", "vscode", "tooling", "debug", "test", "maven", "build")):
        return "blueprint"
    motifs = ("containers", "memory", "lattice", "blueprint")
    return motifs[digest[0] % len(motifs)]


def _draw_tree_elbow(draw: ImageDraw.ImageDraw, x: int, y: int, color=_MUTED):
    """Crisp pixel-aligned '└' connector independent of font glyph metrics."""
    draw.line([(x + 4, y + 4), (x + 4, y + 22)], fill=color, width=2)
    draw.line([(x + 4, y + 22), (x + 18, y + 22)], fill=color, width=2)
def _iso(cx: float, cy: float, x: float, y: float, z: float, scale: float = 1.0) -> tuple[float, float]:
    """Isometric projection helper (x, y horizontal plane; z vertical up)."""
    ang = math.radians(30)
    px = cx + (x - y) * math.cos(ang) * scale
    py = cy + (x + y) * math.sin(ang) * scale - z * scale
    return (px, py)


def _draw_iso_box(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    x: float,
    y: float,
    z: float,
    dx: float,
    dy: float,
    dz: float,
    scale: float,
    top_fill,
    left_fill,
    right_fill,
    stroke=_RULE_STRONG,
    width: int = 3,
):
    p001 = _iso(cx, cy, x, y, z + dz, scale)
    p101 = _iso(cx, cy, x + dx, y, z + dz, scale)
    p111 = _iso(cx, cy, x + dx, y + dy, z + dz, scale)
    p011 = _iso(cx, cy, x, y + dy, z + dz, scale)
    p100 = _iso(cx, cy, x + dx, y, z, scale)
    p110 = _iso(cx, cy, x + dx, y + dy, z, scale)
    p010 = _iso(cx, cy, x, y + dy, z, scale)

    draw.polygon([p011, p111, p110, p010], fill=left_fill, outline=stroke, width=width)
    draw.polygon([p101, p111, p110, p100], fill=right_fill, outline=stroke, width=width)
    draw.polygon([p001, p101, p111, p011], fill=top_fill, outline=stroke, width=width)


def _draw_hatched_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color, step: int = 16, width: int = 2):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    for d in range(-h, w + h, step):
        sx0 = max(x0, x0 + d)
        sy0 = y0 + max(0, -d)
        sx1 = min(x1, x0 + d + h)
        sy1 = min(y1, y0 + (x1 - (x0 + d)))
        if sx0 < sx1 and sy0 < sy1:
            draw.line([(sx0, sy0), (sx1, sy1)], fill=color, width=width)


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p0: tuple[float, float],
    p1: tuple[float, float],
    fill,
    width: int = 2,
    dash: int = 10,
    gap: int = 8,
):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    ux, uy = dx / dist, dy / dist
    pos = 0.0
    while pos < dist:
        end = min(dist, pos + dash)
        draw.line(
            [(p0[0] + ux * pos, p0[1] + uy * pos), (p0[0] + ux * end, p0[1] + uy * end)],
            fill=fill,
            width=width,
        )
        pos += dash + gap


def _draw_artboard_chrome(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], rng: random.Random, seed_hex: str, mono_small):
    ax0, ay0, ax1, ay1 = rect
    draw.rectangle(rect, fill=_SURFACE)

    # Subtle architectural dot-grid + crosshairs
    step = 48
    for gx in range(ax0 + step, ax1, step):
        for gy in range(ay0 + step, ay1, step):
            draw.rectangle((gx - 1, gy - 1, gx + 1, gy + 1), fill=_RULE)

    for gx in (ax0 + 96, ax1 - 96):
        for gy in (ay0 + 96, ay1 - 96):
            draw.line([(gx - 10, gy), (gx + 10, gy)], fill=_MUTED, width=2)
            draw.line([(gx, gy - 10), (gx, gy + 10)], fill=_MUTED, width=2)

    # Corner technical coordinates
    draw.text((ax0 + 28, ay0 + 22), f"FIG // 0x{seed_hex[:6].upper()}", fill=_MUTED, font=mono_small)
    spec_label = f"S:{rng.randint(10, 99)}.{rng.randint(10, 99)}"
    sw = draw.textlength(spec_label, font=mono_small)
    draw.text((ax1 - 28 - sw, ay1 - 44), spec_label, fill=_MUTED, font=mono_small)


def _draw_motif_containers(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], rng: random.Random, sec_accent):
    ax0, ay0, ax1, ay1 = rect
    cx = (ax0 + ax1) / 2
    cy = (ay0 + ay1) / 2 + 80
    scale = 1.95
    sec_dark, sec_soft = sec_accent

    # Base infrastructure slab (host plane)
    _draw_iso_box(
        draw, cx, cy, -110, -110, -28, 220, 220, 18, scale,
        top_fill=_BG, left_fill=_RULE, right_fill=(196, 196, 204), stroke=_RULE_STRONG, width=3,
    )
    # Isometric grid lines on the base slab
    for g in range(-80, 100, 40):
        draw.line([_iso(cx, cy, g, -110, -10, scale), _iso(cx, cy, g, 110, -10, scale)], fill=_RULE, width=2)
        draw.line([_iso(cx, cy, -110, g, -10, scale), _iso(cx, cy, 110, g, -10, scale)], fill=_RULE, width=2)

    # Decoupled separation plane (dashed wireframe boundary)
    z_plane = 36 + rng.randint(-6, 10)
    plane_pts = [
        _iso(cx, cy, -105, -105, z_plane, scale),
        _iso(cx, cy, 105, -105, z_plane, scale),
        _iso(cx, cy, 105, 105, z_plane, scale),
        _iso(cx, cy, -105, 105, z_plane, scale),
    ]
    for i in range(4):
        _draw_dashed_line(draw, plane_pts[i], plane_pts[(i + 1) % 4], fill=_ACCENT, width=3, dash=12, gap=8)

    # Modular container cells arranged deterministically in isometric depth order (back-to-front)
    cells = []
    for gx in (-85, -15, 55):
        for gy in (-85, -15, 55):
            if rng.random() < 0.78:
                h = rng.choice([34, 48, 64, 82])
                z0 = z_plane + rng.choice([12, 28, 46])
                kind = rng.choices(["neutral", "accent", "secondary"], weights=[0.5, 0.32, 0.18])[0]
                cells.append((gx + gy, gx, gy, z0, 52, 52, h, kind))
    # Guarantee at least two focal accent containers
    if not any(c[7] == "accent" for c in cells) and cells:
        idx = len(cells) // 2
        c = cells[idx]
        cells[idx] = (*c[:7], "accent")

    cells.sort(key=lambda item: (item[0], item[3]))
    for _, gx, gy, z0, dx, dy, dz, kind in cells:
        # Vertical projection tether down to the host slab
        p_bot = _iso(cx, cy, gx + dx / 2, gy + dy / 2, -10, scale)
        p_box = _iso(cx, cy, gx + dx / 2, gy + dy / 2, z0, scale)
        _draw_dashed_line(draw, p_bot, p_box, fill=_MUTED, width=2, dash=6, gap=6)

        if kind == "accent":
            top_f, left_f, right_f = _ACCENT_MID, _ACCENT, (55, 48, 163)
            stroke = _HEADING
        elif kind == "secondary":
            top_f, left_f, right_f = sec_soft, _BG, _RULE
            stroke = sec_dark
        else:
            top_f, left_f, right_f = _WHITE, _BG, _RULE
            stroke = _RULE_STRONG
        _draw_iso_box(draw, cx, cy, gx, gy, z0, dx, dy, dz, scale, top_f, left_f, right_f, stroke=stroke, width=3)


def _draw_motif_memory(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], rng: random.Random, sec_accent):
    ax0, ay0, ax1, ay1 = rect
    sec_dark, sec_soft = sec_accent
    cols, rows = 6, 6
    cell = 88
    gap = 12
    grid_w = cols * cell + (cols - 1) * gap
    gx0 = ax0 + ((ax1 - ax0) - grid_w) // 2
    gy0 = ay0 + 116

    # Choose 1-2 humongous multi-cell regions + active GC cells deterministically
    occupied = set()
    spans = []
    for _ in range(2):
        r = rng.randint(0, rows - 2)
        c = rng.randint(0, cols - 3)
        w = rng.choice([2, 3])
        cells = {(r, c + dc) for dc in range(w)}
        if not (cells & occupied):
            occupied |= cells
            spans.append((r, c, w, 1, "humongous"))

    for r in range(rows):
        for c in range(cols):
            if (r, c) in occupied:
                continue
            roll = rng.random()
            if roll < 0.20:
                kind = "eden"
            elif roll < 0.36:
                kind = "survivor"
            elif roll < 0.58:
                kind = "hatched"
            else:
                kind = "free"
            spans.append((r, c, 1, 1, kind))

    for r, c, w, h, kind in spans:
        x0 = gx0 + c * (cell + gap)
        y0 = gy0 + r * (cell + gap)
        x1 = x0 + w * cell + (w - 1) * gap
        y1 = y0 + h * cell + (h - 1) * gap
        if kind == "humongous":
            draw.rectangle((x0, y0, x1, y1), fill=_ACCENT, outline=_HEADING, width=3)
            _draw_hatched_rect(draw, (x0 + 6, y0 + 6, x1 - 6, y1 - 6), _ACCENT_MID, step=18, width=2)
            draw.rectangle((x0 + 14, y0 + 14, x0 + 30, y0 + 30), fill=_WHITE)
        elif kind == "eden":
            draw.rectangle((x0, y0, x1, y1), fill=_ACCENT_SOFT, outline=_ACCENT, width=3)
            draw.ellipse((x0 + 28, y0 + 28, x1 - 28, y1 - 28), fill=_ACCENT)
        elif kind == "survivor":
            draw.rectangle((x0, y0, x1, y1), fill=sec_soft, outline=sec_dark, width=3)
        elif kind == "hatched":
            draw.rectangle((x0, y0, x1, y1), fill=_BG, outline=_RULE_STRONG, width=2)
            _draw_hatched_rect(draw, (x0 + 4, y0 + 4, x1 - 4, y1 - 4), _RULE, step=14, width=2)
        else:
            draw.rectangle((x0, y0, x1, y1), fill=_WHITE, outline=_RULE_STRONG, width=2)

    # Bottom telemetry bar strip
    bar_y0 = gy0 + rows * (cell + gap) + 32
    bar_w = grid_w
    n_bars = 28
    step = bar_w / n_bars
    for i in range(n_bars):
        bx = gx0 + i * step
        bh = rng.randint(14, 56)
        color = _ACCENT if i % 5 == 0 else (sec_dark if i % 7 == 0 else (_RULE_STRONG if i % 3 == 0 else _MUTED))
        draw.rectangle((bx, bar_y0 + 56 - bh, bx + step - 6, bar_y0 + 56), fill=color)


def _draw_motif_lattice(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], rng: random.Random, sec_accent):
    ax0, ay0, ax1, ay1 = rect
    cx = (ax0 + ax1) / 2
    cy = (ay0 + ay1) / 2
    sec_dark, sec_soft = sec_accent

    # Concentric evaluation rings
    for r, col, w in ((310, _RULE, 2), (235, _RULE_STRONG, 2), (155, _ACCENT_MID, 3)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=w)

    # Central pointcut diamond / filter gate
    d_rad = 175
    diamond = [(cx, cy - d_rad), (cx + d_rad, cy), (cx, cy + d_rad), (cx - d_rad, cy)]
    draw.polygon(diamond, fill=_ACCENT_SOFT, outline=_ACCENT, width=4)
    _draw_hatched_rect(draw, (int(cx - 75), int(cy - 75), int(cx + 75), int(cy + 75)), _WHITE, step=14, width=3)
    draw.rectangle((cx - 75, cy - 75, cx + 75, cy + 75), outline=_HEADING, width=3)

    # Layered join-point signal tracks from left to right (ordered cleanly through the gate)
    n_tracks = 7
    y_span = 520
    y_start = cy - y_span / 2
    matched_indices = sorted(set(rng.sample(range(n_tracks), k=3)) | {n_tracks // 2})
    gate_offsets = {
        idx: (rank - (len(matched_indices) - 1) / 2) * 36
        for rank, idx in enumerate(matched_indices)
    }

    for i in range(n_tracks):
        ty = y_start + i * (y_span / (n_tracks - 1))
        in_pt = (ax0 + 54, ty)
        jitter = rng.randint(-14, 14)
        mid_l = (cx - 155, ty + jitter)
        mid_r = (cx + 155, ty - jitter)
        out_pt = (ax1 - 54, ty)

        if i in gate_offsets:
            gate_pt = (cx, cy + gate_offsets[i])
            draw.line([in_pt, mid_l, gate_pt, mid_r, out_pt], fill=_ACCENT, width=4, joint="curve")
            for px, py in (in_pt, mid_l, gate_pt, mid_r, out_pt):
                draw.ellipse((px - 9, py - 9, px + 9, py + 9), fill=_WHITE, outline=_ACCENT, width=4)
            draw.ellipse((gate_pt[0] - 6, gate_pt[1] - 6, gate_pt[0] + 6, gate_pt[1] + 6), fill=_ACCENT)
        else:
            # Pruned static-analysis candidate: stops at filter boundary
            _draw_dashed_line(draw, in_pt, mid_l, fill=_MUTED, width=2, dash=10, gap=8)
            draw.ellipse((in_pt[0] - 6, in_pt[1] - 6, in_pt[0] + 6, in_pt[1] + 6), fill=_BG, outline=_MUTED, width=2)
            draw.line([(mid_l[0] - 7, mid_l[1] - 7), (mid_l[0] + 7, mid_l[1] + 7)], fill=sec_dark, width=3)
            draw.line([(mid_l[0] - 7, mid_l[1] + 7), (mid_l[0] + 7, mid_l[1] - 7)], fill=sec_dark, width=3)


def _draw_motif_blueprint(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], rng: random.Random, sec_accent):
    ax0, ay0, ax1, ay1 = rect
    sec_dark, sec_soft = sec_accent

    # Shadowed architectural window frame
    wx0, wy0, wx1, wy1 = ax0 + 68, ay0 + 86, ax1 - 88, ay1 - 210
    draw.rectangle((wx0 + 18, wy0 + 18, wx1 + 18, wy1 + 18), fill=_RULE, outline=_RULE_STRONG, width=2)
    draw.rectangle((wx0, wy0, wx1, wy1), fill=_WHITE, outline=_HEADING, width=3)

    # Window header bar + window controls
    draw.rectangle((wx0, wy0, wx1, wy0 + 48), fill=_BG, outline=_HEADING, width=3)
    for idx, col in enumerate((_ACCENT, sec_dark, _MUTED)):
        cx_dot = wx0 + 28 + idx * 24
        cy_dot = wy0 + 24
        draw.ellipse((cx_dot - 6, cy_dot - 6, cx_dot + 6, cy_dot + 6), fill=col)

    # Left gutter + code/coverage rhythm bars
    gutter_x = wx0 + 76
    draw.line([(gutter_x, wy0 + 48), (gutter_x, wy1)], fill=_RULE, width=2)

    row_y = wy0 + 80
    line_num = 1
    while row_y < wy1 - 36:
        is_hl = rng.random() < 0.24
        if is_hl:
            draw.rectangle((wx0 + 3, row_y - 8, wx1 - 3, row_y + 24), fill=_ACCENT_SOFT)
            draw.rectangle((wx0 + 3, row_y - 8, wx0 + 11, row_y + 24), fill=_ACCENT)
            draw.ellipse((wx0 + 38, row_y + 2, wx0 + 50, row_y + 14), fill=_ACCENT)
        else:
            draw.rectangle((wx0 + 34, row_y + 5, wx0 + 52, row_y + 11), fill=_RULE)

        indent = rng.choice([0, 28, 56, 84])
        cur_x = gutter_x + 26 + indent
        n_segs = rng.randint(2, 4)
        for s in range(n_segs):
            seg_w = rng.randint(44, 150)
            if cur_x + seg_w > wx1 - 28:
                break
            col = _ACCENT if (is_hl and s == 0) else (sec_dark if rng.random() < 0.2 else _FG if s == 0 else _RULE_STRONG)
            if col == _RULE_STRONG and not is_hl:
                col = (180, 180, 190)
            draw.rounded_rectangle((cur_x, row_y, cur_x + seg_w, row_y + 14), radius=4, fill=col)
            cur_x += seg_w + 14

        row_y += 42
        line_num += 1

    # Overlapping diagnostic / coverage radar card at bottom-right
    dx0, dy0, dx1, dy1 = ax0 + 250, ay1 - 320, ax1 - 52, ay1 - 74
    draw.rectangle((dx0 + 12, dy0 + 12, dx1 + 12, dy1 + 12), fill=_RULE_STRONG)
    draw.rectangle((dx0, dy0, dx1, dy1), fill=_BG, outline=_HEADING, width=3)
    _draw_hatched_rect(draw, (dx0 + 16, dy0 + 16, dx0 + 200, dy1 - 16), _RULE, step=14, width=2)

    # Radial gauge inside the diagnostic card
    gcx, gcy, grad = dx0 + 108, (dy0 + dy1) // 2, 68
    draw.ellipse((gcx - grad, gcy - grad, gcx + grad, gcy + grad), fill=_WHITE, outline=_RULE_STRONG, width=3)
    draw.pieslice((gcx - grad, gcy - grad, gcx + grad, gcy + grad), start=-90, end=rng.randint(140, 230), fill=_ACCENT_SOFT, outline=_ACCENT, width=3)
    draw.ellipse((gcx - 34, gcy - 34, gcx + 34, gcy + 34), fill=_WHITE, outline=_HEADING, width=3)
    draw.ellipse((gcx - 10, gcy - 10, gcx + 10, gcy + 10), fill=_ACCENT)

    # Metric bars on right side of diagnostic card
    mx0 = dx0 + 216
    for idx in range(4):
        my = dy0 + 42 + idx * 44
        draw.rectangle((mx0, my, dx1 - 28, my + 18), fill=_WHITE, outline=_RULE_STRONG, width=2)
        fill_w = int((dx1 - 28 - mx0) * rng.uniform(0.45, 0.92))
        bar_col = _ACCENT if idx in (0, 2) else sec_dark
        draw.rectangle((mx0, my, mx0 + fill_w, my + 18), fill=bar_col)


def _render_og_card(art: dict, config, out_path: Path):
    # Render at 2x (2400x1260) and downsample to 1200x630 with LANCZOS for crisp anti-aliasing
    W, H = 2400, 1260
    img = Image.new("RGB", (W, H), _BG)
    draw = ImageDraw.Draw(img)

    digest = hashlib.sha256(art["slug"].encode("utf-8")).digest()
    seed_int = int.from_bytes(digest[:8], "big")
    rng = random.Random(seed_int)
    sec_accent = _SECONDARY_ACCENTS[digest[1] % len(_SECONDARY_ACCENTS)]

    # Fonts (2x scaled sizes)
    font_mono = _load_font(_MONO_CANDIDATES, 26)
    font_mono_sm = _load_font(_MONO_CANDIDATES, 22)
    font_lede = _load_font(_SANS_REG_CANDIDATES, 34)

    title = art["title"]
    if len(title) > 68:
        title_size, max_title_lines = 68, 4
    elif len(title) > 45:
        title_size, max_title_lines = 76, 3
    else:
        title_size, max_title_lines = 86, 3
    font_title = _load_font(_SANS_CANDIDATES, title_size)

    # Outer architectural frame + top indigo accent bar
    draw.rectangle((0, 0, W, 12), fill=_ACCENT)
    margin_x, margin_y = 96, 88
    split_x = 1460
    draw.rectangle((margin_x, margin_y, W - margin_x, H - margin_y), outline=_RULE_STRONG, width=3)
    draw.line([(split_x, margin_y), (split_x, H - margin_y)], fill=_RULE_STRONG, width=3)

    # Right artboard: deterministic generative artwork
    art_rect = (split_x + 3, margin_y + 3, W - margin_x - 3, H - margin_y - 3)
    _draw_artboard_chrome(draw, art_rect, rng, digest.hex(), font_mono_sm)
    motif = _pick_motif(art, digest)
    if motif == "containers":
        _draw_motif_containers(draw, art_rect, rng, sec_accent)
    elif motif == "memory":
        _draw_motif_memory(draw, art_rect, rng, sec_accent)
    elif motif == "lattice":
        _draw_motif_lattice(draw, art_rect, rng, sec_accent)
    else:
        _draw_motif_blueprint(draw, art_rect, rng, sec_accent)

    # Left column content (mirrors site layout: header brand + topic -> title + lede -> metadata strip)
    lx0 = margin_x + 64
    lx1 = split_x - 64
    col_w = lx1 - lx0

    # Top header row inside left column
    hy = margin_y + 56
    draw.rectangle((lx0, hy + 2, lx0 + 24, hy + 26), fill=_ACCENT)
    brand_text = (config.site_author or config.site_name).upper()
    draw.text((lx0 + 42, hy), brand_text, fill=_HEADING, font=font_mono)

    topic_parts = []
    if art.get("topic"):
        topic_parts.append(art["topic"]["title"].upper())
        if art.get("subtopic"):
            topic_parts.append(art["subtopic"]["name"].upper())
    elif art.get("categories"):
        topic_parts.append(str(art["categories"][0]).upper())
    topic_label = "/ " + " · ".join(topic_parts) if topic_parts else "/ WRITING"
    tw = draw.textlength(topic_label, font=font_mono)
    draw.text((lx1 - tw, hy), topic_label, fill=_MUTED, font=font_mono)

    rule_y = hy + 52
    draw.line([(lx0, rule_y), (lx1, rule_y)], fill=_RULE_STRONG, width=3)

    # Title + lede block
    title_lines = _wrap_lines(draw, title, font_title, col_w, max_lines=max_title_lines)
    line_h = int(title_size * 1.18)
    ty = rule_y + 58
    for line in title_lines:
        draw.text((lx0, ty), line, fill=_HEADING, font=font_title)
        ty += line_h

    desc = art.get("description") or ""
    if desc and len(title_lines) <= 3:
        ty += 24
        lede_lines = _wrap_lines(draw, desc, font_lede, col_w, max_lines=2)
        for line in lede_lines:
            draw.text((lx0, ty), line, fill=_MUTED, font=font_lede)
            ty += 48

    # Bottom metadata strip (matches .strip in theme/main.html)
    strip_y = H - margin_y - 148
    draw.line([(lx0, strip_y), (lx1, strip_y)], fill=_RULE, width=2)

    meta_y = strip_y + 28
    cx_meta = lx0
    if art.get("date_display"):
        draw.text((cx_meta, meta_y), "PUBLISHED", fill=_MUTED, font=font_mono_sm)
        _draw_tree_elbow(draw, cx_meta, meta_y + 34)
        draw.text((cx_meta + 28, meta_y + 34), art["date_display"], fill=_HEADING, font=font_mono)
        cx_meta += 250

    draw.text((cx_meta, meta_y), "READING TIME", fill=_MUTED, font=font_mono_sm)
    _draw_tree_elbow(draw, cx_meta, meta_y + 34)
    draw.text((cx_meta + 28, meta_y + 34), f"{art['reading_time']} min", fill=_HEADING, font=font_mono)
    cx_meta += 250

    tags = art.get("tags") or []
    if tags:
        draw.text((cx_meta, meta_y), "TAGS", fill=_MUTED, font=font_mono_sm)
        tx = cx_meta
        ty_tag = meta_y + 32
        for tag in tags[:3]:
            label = str(tag)
            pad_x = 16
            pill_w = int(draw.textlength(label, font=font_mono_sm)) + pad_x * 2
            if tx + pill_w > lx1:
                break
            draw.rounded_rectangle((tx, ty_tag, tx + pill_w, ty_tag + 38), radius=6, fill=_BG, outline=_RULE_STRONG, width=2)
            draw.text((tx + pad_x, ty_tag + 7), label, fill=_FG, font=font_mono_sm)
            tx += pill_w + 12

    out_img = img.resize((1200, 630), resample=Image.Resampling.LANCZOS)
    out_img.save(out_path, format="PNG", optimize=True)

