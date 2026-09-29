/* Progressive enhancements only: every page is fully usable without this file. */
(() => {
  "use strict";

  const root = document.documentElement;
  const base = new URL((root.dataset.base || ".").replace(/\/+$/, "") + "/", location.href);
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  /* ---------- Theme mode: system → light → dark ---------------------- */
  const THEMES = ["system", "light", "dark"];
  const THEME_LABEL = { system: "System", light: "Light", dark: "Dark" };
  const darkQuery = matchMedia("(prefers-color-scheme: dark)");
  const themePref = () => root.dataset.themePref || "system";
  const resolvedTheme = () => root.dataset.theme || (darkQuery.matches ? "dark" : "light");

  function syncThemeToggle() {
    const pref = themePref();
    const next = THEMES[(THEMES.indexOf(pref) + 1) % THEMES.length];
    $$("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-label", `Color theme: ${THEME_LABEL[pref]}. Switch to ${THEME_LABEL[next]}`);
      btn.title = `Color theme: ${THEME_LABEL[pref]}`;
      const label = $("[data-theme-label]", btn);
      if (label) label.textContent = pref === "system" ? "Auto" : THEME_LABEL[pref];
    });
  }

  function setTheme(pref) {
    if (pref === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", pref);
    root.dataset.themePref = pref;
    try {
      if (pref === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", pref);
    } catch (_) { /* storage unavailable: preference lasts for this page only */ }
    syncThemeToggle();
    document.dispatchEvent(new Event("themechange"));
  }

  $$("[data-theme-toggle]").forEach((btn) =>
    btn.addEventListener("click", () => setTheme(THEMES[(THEMES.indexOf(themePref()) + 1) % THEMES.length]))
  );
  darkQuery.addEventListener("change", () => {
    if (themePref() === "system") document.dispatchEvent(new Event("themechange"));
  });
  syncThemeToggle();

  /* ---------- Dialog helpers ----------------------------------------- */
  function lightDismiss(dialog) {
    dialog.addEventListener("click", (e) => {
      if (e.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close();
    });
  }

  /* ---------- Single-key shortcuts shown as [W] [T] [P] [A] in the tab bar */
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.key.length !== 1) return;
    if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], dialog[open]")) return;
    const tab = $(`[data-key="${CSS.escape(e.key.toLowerCase())}"]`);
    if (tab) { e.preventDefault(); tab.click(); }
  });

  /* ---------- Search (built-in MkDocs index, no server) -------------- */
  const search = $("#search");
  if (search) {
    const input = $("#search-input");
    const results = $("#search-results");
    const status = $("#search-status");
    const GROUPS = ["Articles", "Topics", "Projects", "Pages"];
    let docs = null;
    let pages = null;
    let meta = {};
    let options = [];
    let active = -1;

    async function load() {
      if (docs) return;
      const [index, kinds] = await Promise.all([
        fetch(new URL("search/search_index.json", base)).then((r) => r.json()),
        fetch(new URL("search/meta.json", base)).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
      ]);
      meta = kinds;
      docs = index.docs.map((d) => {
        const [path, hash] = d.location.split("#");
        const text = d.text.replace(/\s#\s/g, " ");
        return { ...d, path, hash, text, t: d.title.toLowerCase(), x: text.toLowerCase() };
      });
      pages = new Map(docs.filter((d) => !d.hash).map((d) => [d.path, d]));
    }

    function open() {
      if (!search.open) search.showModal();
      input.select();
      load().then(render).catch(() => {
        results.innerHTML = '<p class="search-empty">Search is unavailable right now.</p>';
      });
    }

    const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const mark = (text, terms) =>
      escapeHtml(text).replace(new RegExp(`(${terms.map((t) => escapeRe(escapeHtml(t))).join("|")})`, "gi"), "<mark>$1</mark>");

    function snippet(text, terms) {
      const lower = text.toLowerCase();
      const at = Math.min(...terms.map((t) => lower.indexOf(t)).filter((i) => i >= 0));
      if (!Number.isFinite(at)) return text.slice(0, 140);
      const start = Math.max(0, at - 50);
      return (start ? "…" : "") + text.slice(start, start + 160).trim() + (start + 160 < text.length ? "…" : "");
    }

    function score(doc, terms) {
      let s = 0;
      for (const t of terms) {
        const inTitle = doc.t.includes(t);
        if (!inTitle && !doc.x.includes(t)) return 0;
        s += inTitle ? (doc.t.startsWith(t) ? 12 : 8) : 1;
      }
      return s;
    }

    function render() {
      const q = input.value.trim().toLowerCase();
      options = [];
      active = -1;
      if (!q || !docs) {
        results.innerHTML = "";
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        status.textContent = "";
        return;
      }
      const terms = q.split(/\s+/).filter(Boolean);
      const hits = new Map();
      for (const doc of docs) {
        const s = score(doc, terms);
        if (!s) continue;
        const hit = hits.get(doc.path) || { path: doc.path, score: 0, own: 0, sections: [] };
        if (doc.hash) hit.sections.push({ doc, s });
        else hit.own = s;
        hit.score += doc.hash ? s : s * 2;
        hits.set(doc.path, hit);
      }
      const ranked = [...hits.values()].sort((a, b) => b.score - a.score).slice(0, 12);
      if (!ranked.length) {
        results.innerHTML = `<p class="search-empty">No results for “${escapeHtml(input.value.trim())}”</p>`;
        input.setAttribute("aria-expanded", "false");
        status.textContent = "No results";
        return;
      }

      const grouped = new Map(GROUPS.map((g) => [g, []]));
      for (const hit of ranked) {
        const kind = (meta[hit.path] && meta[hit.path].kind) || "Pages";
        grouped.get(kind).push(hit);
      }

      let html = "";
      let n = 0;
      grouped.forEach((hitsInGroup, group) => {
        if (!hitsInGroup.length) return;
        html += `<div role="group" aria-labelledby="sg-${group}"><p class="search-group-label" id="sg-${group}">${group}</p>`;
        for (const hit of hitsInGroup) {
          const page = pages.get(hit.path);
          const title = page ? page.title : hit.path;
          const label = (meta[hit.path] && meta[hit.path].label) || "";
          const best = hit.own ? page : (hit.sections.sort((a, b) => b.s - a.s)[0] || {}).doc || page;
          const href = new URL(hit.path, base).href;
          html += `<a class="search-option" role="option" id="so-${n++}" href="${href}" aria-selected="false">
            <span class="search-option-title">${mark(title, terms)}</span>
            ${label ? `<span class="search-option-meta">${escapeHtml(label)}</span>` : ""}
            ${best && best.text ? `<span class="search-option-snippet">${mark(snippet(best.text, terms), terms)}</span>` : ""}
          </a>`;
          for (const { doc } of hit.sections.sort((a, b) => b.s - a.s).slice(0, 2)) {
            html += `<a class="search-option search-option--section" role="option" id="so-${n++}" href="${new URL(doc.location, base).href}" aria-selected="false">
              <span class="search-option-title">${mark(doc.title, terms)}</span>
            </a>`;
          }
        }
        html += "</div>";
      });
      results.innerHTML = html;
      options = $$(".search-option", results);
      input.setAttribute("aria-expanded", "true");
      status.textContent = `${ranked.length} page${ranked.length === 1 ? "" : "s"} found`;
      select(0);
    }

    function select(i) {
      if (!options.length) return;
      if (active >= 0 && options[active]) options[active].setAttribute("aria-selected", "false");
      active = (i + options.length) % options.length;
      const el = options[active];
      el.setAttribute("aria-selected", "true");
      input.setAttribute("aria-activedescendant", el.id);
      el.scrollIntoView({ block: "nearest" });
    }

    let timer;
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(render, 60); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); select(active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); select(active - 1); }
      else if (e.key === "Enter" && options[active]) { e.preventDefault(); options[active].click(); }
      // type=search swallows the first Esc to clear its value; close in one press instead.
      else if (e.key === "Escape") { e.preventDefault(); search.close(); }
    });
    results.addEventListener("mousemove", (e) => {
      const opt = e.target.closest(".search-option");
      if (opt && options.indexOf(opt) !== active) select(options.indexOf(opt));
    });
    results.addEventListener("click", (e) => { if (e.target.closest("a")) search.close(); });

    $$("[data-search-open]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); open(); }));
    $$("[data-search-close]", search).forEach((b) => b.addEventListener("click", () => search.close()));
    lightDismiss(search);

    document.addEventListener("keydown", (e) => {
      const typing = e.target.closest && e.target.closest("input, textarea, select, [contenteditable]");
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (search.open) search.close();
        else open();
      } else if (e.key === "/" && !typing && !search.open) {
        e.preventDefault();
        open();
      }
    });
  }

  /* ---------- On-this-page scrollspy --------------------------------- */
  const tocLinks = $$("[data-toc-link]");
  const targets = [...new Set(tocLinks.map((a) => a.getAttribute("href").slice(1)))]
    .map((id) => document.getElementById(decodeURIComponent(id)))
    .filter(Boolean);

  if (targets.length) {
    let queued = false;
    const update = () => {
      queued = false;
      const line = parseInt(getComputedStyle(root).scrollPaddingTop, 10) + 8 || 100;
      let current = null;
      for (const t of targets) {
        if (t.getBoundingClientRect().top <= line) current = t;
        else break;
      }
      if (current && innerHeight + scrollY >= root.scrollHeight - 4) current = targets[targets.length - 1];
      for (const a of tocLinks) {
        const on = !!current && a.getAttribute("href") === "#" + current.id;
        a.classList.toggle("is-active", on);
        if (on) a.setAttribute("aria-current", "location");
        else a.removeAttribute("aria-current");
        const box = on && a.closest(".toc");
        if (box && box.scrollHeight > box.clientHeight &&
            (a.offsetTop < box.scrollTop || a.offsetTop > box.scrollTop + box.clientHeight - 32)) {
          box.scrollTop = a.offsetTop - box.clientHeight / 2;
        }
      }
    };
    addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
    addEventListener("resize", update, { passive: true });
    update();
  }

  /* ---------- Reading progress + header rule on scroll -------------- */
  const header = $(".site-header");
  const prose = $(".prose");
  const fill = $("[data-progress-fill]");
  const value = $("[data-progress-value]");
  let ticking = false;
  const onScroll = () => {
    ticking = false;
    if (header) header.classList.toggle("is-scrolled", scrollY > 8);
    if (!fill || !prose) return;
    const r = prose.getBoundingClientRect();
    const total = r.height - innerHeight * 0.6;
    const pct = Math.round(Math.min(1, Math.max(0, (innerHeight * 0.4 - r.top) / Math.max(total, 1))) * 100);
    fill.style.width = pct + "%";
    value.textContent = String(pct).padStart(2, "0") + "%";
  };
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  onScroll();

  $$(".toc-mobile a").forEach((a) => a.addEventListener("click", () => { a.closest("details").open = false; }));

  /* ---------- Code blocks: language label + copy --------------------- */
  const LANGS = {
    bash: "Bash", sh: "Shell", shell: "Shell", zsh: "Shell", console: "Console", json: "JSON", yaml: "YAML", yml: "YAML",
    java: "Java", kotlin: "Kotlin", groovy: "Groovy", xml: "XML", html: "HTML", css: "CSS", js: "JavaScript",
    javascript: "JavaScript", ts: "TypeScript", typescript: "TypeScript", python: "Python", py: "Python", go: "Go",
    rust: "Rust", sql: "SQL", toml: "TOML", ini: "INI", properties: "Properties", dockerfile: "Dockerfile",
    text: "Text", diff: "Diff", http: "HTTP", markdown: "Markdown", md: "Markdown",
  };
  const COPY_ICON = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>';

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const ta = Object.assign(document.createElement("textarea"), { value: text });
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.append(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
  }

  $$(".highlight").forEach((block) => {
    const code = $("pre code", block);
    if (!code) return;
    const langClass = [...block.classList].find((c) => c.startsWith("language-"));
    const lang = langClass ? langClass.slice(9) : "";
    const label = LANGS[lang] || (lang && lang[0].toUpperCase() + lang.slice(1));

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "code-copy";
    btn.innerHTML = `${COPY_ICON}<span>Copy</span>`;
    btn.setAttribute("aria-label", label ? `Copy ${label} code` : "Copy code");
    btn.addEventListener("click", async () => {
      await copyText(code.textContent.replace(/\n$/, ""));
      btn.dataset.copied = "";
      btn.lastChild.textContent = "Copied";
      btn.setAttribute("aria-label", "Copied to clipboard");
      setTimeout(() => {
        delete btn.dataset.copied;
        btn.lastChild.textContent = "Copy";
        btn.setAttribute("aria-label", label ? `Copy ${label} code` : "Copy code");
      }, 1800);
    });

    if (label) {
      const head = document.createElement("div");
      head.className = "code-head";
      head.innerHTML = `<span>${label}</span>`;
      head.append(btn);
      block.prepend(head);
    } else {
      block.append(btn);
    }
    $("pre", block).tabIndex = 0;
  });

  /* ---------- Mermaid: loaded on demand, follows light/dark ---------- */
  const diagrams = $$("pre.mermaid").map((pre) => {
    const figure = document.createElement("figure");
    figure.className = "mermaid-figure";
    const el = document.createElement("div");
    el.className = "mermaid";
    el.dataset.source = pre.textContent.trim();
    el.textContent = el.dataset.source;
    figure.append(el);
    pre.replaceWith(figure);
    return el;
  });

  if (diagrams.length) {
    let mermaid = null;
    const renderDiagrams = async () => {
      if (!mermaid) {
        mermaid = (await import("https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs")).default;
      }
      // Mermaid needs literal colours (it derives shades itself), mirroring the CSS tokens.
      const palette = resolvedTheme() === "dark"
        ? { bg: "#151518", node: "#1e1e22", border: "#6366f1", text: "#e4e4e7", line: "#a1a1aa", accent: "#1e1b4b", note: "#27272a" }
        : { bg: "#f4f4f5", node: "#ffffff", border: "#818cf8", text: "#27272a", line: "#71717a", accent: "#e0e7ff", note: "#eaeaed" };
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        theme: "base",
        fontFamily: getComputedStyle(root).getPropertyValue("--font-sans").trim(),
        themeVariables: {
          darkMode: resolvedTheme() === "dark",
          fontSize: "14px",
          background: palette.bg,
          primaryColor: palette.node,
          primaryTextColor: palette.text,
          primaryBorderColor: palette.border,
          secondaryColor: palette.accent,
          tertiaryColor: palette.bg,
          lineColor: palette.line,
          textColor: palette.text,
          edgeLabelBackground: palette.bg,
          clusterBkg: palette.bg,
          clusterBorder: palette.border,
          actorBkg: palette.node,
          actorBorder: palette.border,
          actorTextColor: palette.text,
          signalColor: palette.text,
          signalTextColor: palette.text,
          labelTextColor: palette.text,
          noteBkgColor: palette.note,
          noteTextColor: palette.text,
          noteBorderColor: palette.border,
        },
        flowchart: { useMaxWidth: true, htmlLabels: true },
        sequence: { useMaxWidth: true },
      });
      for (const el of diagrams) {
        el.removeAttribute("data-processed");
        el.textContent = el.dataset.source;
      }
      await mermaid.run({ nodes: diagrams });
    };
    renderDiagrams().catch((err) => console.warn("Mermaid could not be loaded; showing diagram source.", err));
    document.addEventListener("themechange", () => { renderDiagrams().catch(() => {}); });
  }
})();
