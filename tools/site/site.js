// Theme toggle, search over every item id, and Mermaid rendered in the page's colours.
(function () {
  const root = document.documentElement;
  const store = {
    get() { try { return localStorage.getItem("theme"); } catch (e) { return null; } },
    set(v) { try { localStorage.setItem("theme", v); } catch (e) { /* private window */ } },
  };
  const saved = store.get();
  if (saved) root.dataset.theme = saved;

  function dark() {
    if (root.dataset.theme) return root.dataset.theme === "dark";
    return matchMedia("(prefers-color-scheme: dark)").matches;
  }

  // ---- Mermaid
  const sources = new Map();
  function tokens() {
    const s = getComputedStyle(root);
    const v = (n) => s.getPropertyValue(n).trim();
    return {
      darkMode: dark(),
      fontFamily: "Inter, system-ui, sans-serif",
      fontSize: "13px",
      background: v("--sunk"),
      primaryColor: v("--card"),
      primaryTextColor: v("--fg"),
      primaryBorderColor: v("--line"),
      secondaryColor: v("--accent-bg"),
      tertiaryColor: v("--sunk"),
      lineColor: v("--dim"),
      textColor: v("--fg"),
      actorBkg: v("--card"),
      actorBorder: v("--accent"),
      actorTextColor: v("--fg"),
      actorLineColor: v("--line"),
      signalColor: v("--fg"),
      signalTextColor: v("--fg"),
      labelBoxBkgColor: v("--accent-bg"),
      labelBoxBorderColor: v("--accent"),
      labelTextColor: v("--fg"),
      loopTextColor: v("--fg"),
      noteBkgColor: v("--accent-bg"),
      noteBorderColor: v("--accent"),
      noteTextColor: v("--fg"),
      activationBkgColor: v("--accent-bg"),
      sequenceNumberColor: v("--card"),
      stateBkg: v("--card"),
      stateLabelColor: v("--fg"),
      transitionColor: v("--dim"),
      transitionLabelColor: v("--fg"),
      compositeBackground: v("--sunk"),
      nodeBorder: v("--accent"),
      mainBkg: v("--card"),
      clusterBkg: v("--sunk"),
      edgeLabelBackground: v("--card"),
    };
  }
  async function draw() {
    const mermaid = window.__mermaid;
    if (!mermaid) return;
    const nodes = document.querySelectorAll("pre.mermaid");
    nodes.forEach((n, i) => {
      if (!sources.has(n)) sources.set(n, n.textContent);
      n.removeAttribute("data-processed");
      n.textContent = sources.get(n);
    });
    mermaid.initialize({
      startOnLoad: false, theme: "base", themeVariables: tokens(), securityLevel: "strict",
      sequence: { useMaxWidth: false, wrap: true, width: 160, actorMargin: 32, messageMargin: 36, boxMargin: 10, noteMargin: 10, mirrorActors: true, actorFontSize: 14, messageFontSize: 14, noteFontSize: 13 },
      state: { useMaxWidth: false },
      flowchart: { useMaxWidth: true, htmlLabels: false, curve: "basis" },
    });
    try {
      await mermaid.run({ nodes: [...nodes], suppressErrors: true });
    } catch (e) { console.error(e); }
    fit();
    document.dispatchEvent(new Event("diagrams-drawn"));
  }
  // Fit each diagram to its column, never below 75% of full size; past that it scrolls.
  const MIN = 0.75;
  function fit() {
    document.querySelectorAll(".diagram").forEach((fig) => {
      const svg = fig.querySelector("svg");
      if (!svg) return;
      const vb = svg.viewBox && svg.viewBox.baseVal;
      const w = vb && vb.width ? vb.width : svg.getBBox().width;
      const h = vb && vb.height ? vb.height : svg.getBBox().height;
      const room = fig.clientWidth - 30;
      const scale = Math.max(MIN, Math.min(1, room / w));
      svg.style.width = Math.round(w * scale) + "px";
      svg.style.height = Math.round(h * scale) + "px";
      if (!fig.querySelector(".zoom")) {
        const b = document.createElement("button");
        b.type = "button"; b.className = "zoom"; b.textContent = "Full size";
        b.addEventListener("click", () => openFull(fig));
        fig.prepend(b);
      }
    });
  }
  function openFull(fig) {
    const svg = fig.querySelector("svg");
    const dlg = document.createElement("dialog");
    dlg.className = "full";
    const bar = document.createElement("div");
    bar.className = "full-bar";
    const cap = fig.querySelector("figcaption");
    bar.innerHTML = "<span></span><button type='button'>Close</button>";
    bar.firstChild.textContent = cap ? cap.textContent : "";
    const body = document.createElement("div");
    body.className = "full-body";
    const copy = svg.cloneNode(true);
    copy.style.width = ""; copy.style.height = "";
    copy.removeAttribute("style");
    body.appendChild(copy);
    dlg.append(bar, body);
    document.body.appendChild(dlg);
    bar.querySelector("button").addEventListener("click", () => dlg.close());
    dlg.addEventListener("close", () => dlg.remove());
    dlg.showModal();
  }
  addEventListener("resize", () => { clearTimeout(fit.t); fit.t = setTimeout(fit, 150); });

  if (window.__mermaid) draw(); else window.addEventListener("mermaid-ready", draw, { once: true });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (!root.dataset.theme) draw(); });

  document.getElementById("theme")?.addEventListener("click", () => {
    const next = dark() ? "light" : "dark";
    root.dataset.theme = next;
    store.set(next);
    draw();
  });

  // ---- search
  const q = document.getElementById("q");
  const box = document.getElementById("results");
  let index = null, sel = -1;
  async function load() {
    if (index) return index;
    const r = await fetch(window.SITE_ROOT + "assets/search.json");
    index = await r.json();
    return index;
  }
  function render(list) {
    box.innerHTML = "";
    sel = -1;
    if (!list.length) { box.hidden = true; return; }
    for (const it of list.slice(0, 14)) {
      const a = document.createElement("a");
      a.href = window.SITE_ROOT + it.u;
      a.innerHTML = '<span class="rid"></span><span></span><span class="rb"></span>';
      a.children[0].textContent = it.id;
      a.children[1].textContent = it.t;
      a.children[2].textContent = it.b;
      box.appendChild(a);
    }
    box.hidden = false;
  }
  q?.addEventListener("focus", load);
  q?.addEventListener("input", async () => {
    const words = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) { box.hidden = true; return; }
    const all = await load();
    const hits = all.filter((it) => {
      const hay = (it.id + " " + it.t + " " + it.b).toLowerCase();
      return words.every((w) => hay.includes(w));
    });
    hits.sort((a, b) => (a.id.toLowerCase().includes(words[0]) ? 0 : 1) - (b.id.toLowerCase().includes(words[0]) ? 0 : 1));
    render(hits);
  });
  q?.addEventListener("keydown", (e) => {
    const links = [...box.querySelectorAll("a")];
    if (!links.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
      links.forEach((l, i) => l.classList.toggle("sel", i === sel));
    } else if (e.key === "Enter") {
      (links[sel] || links[0]).click();
    } else if (e.key === "Escape") {
      box.hidden = true;
    }
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".search")) box.hidden = true; });
})();
