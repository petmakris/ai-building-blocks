// Theme toggle, and the walkthrough: the step being read lights up its part of the diagram.
(function () {
  const root = document.documentElement;
  try { const t = localStorage.getItem("theme"); if (t) root.dataset.theme = t; } catch (e) { /* storage blocked */ }
  document.getElementById("theme")?.addEventListener("click", () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* storage blocked */ }
  });
  const steps = [...document.querySelectorAll(".step")];
  const marks = [...document.querySelectorAll(".st")];
  // On a phone the diagram zooms to the step being read: the lane names stay on top,
  // and the view shows only that step's rows, across the full width.
  const svg = document.querySelector(".stage svg");
  const full = svg && svg.getAttribute("viewBox");
  const phone = matchMedia("(max-width: 860px)");
  const headsEl = svg && svg.querySelector(".lane-head");
  if (headsEl) svg.appendChild(headsEl);   // drawn last, so the lane names cover anything behind them
  function zoom(n) {
    if (!svg) return;
    const heads = svg.querySelector(".lane-head");
    if (!phone.matches) { svg.setAttribute("viewBox", full); if (heads) heads.removeAttribute("transform"); return; }
    const g = svg.querySelector('.st[data-step="' + n + '"]');
    if (!g) return;
    const b = g.getBBox();
    const W = +full.split(" ")[2];
    const top = Math.max(0, b.y - 64);
    const h = b.height + 64 + 26;
    svg.setAttribute("viewBox", "0 " + top + " " + W + " " + h);
    if (heads) heads.setAttribute("transform", "translate(0 " + Math.max(0, top - 4) + ")");
  }
  function show(n) {
    steps.forEach((s) => s.classList.toggle("on", +s.dataset.step === n));
    marks.forEach((m) => {
      const k = +m.dataset.step;
      m.classList.toggle("on", k === n);
      m.classList.toggle("done", k < n);
    });
    zoom(n);
  }
  phone.addEventListener?.("change", () => { const on = document.querySelector(".step.on"); if (on) zoom(+on.dataset.step); });
  if (!steps.length) return;
  show(+steps[0].dataset.step);
  if (!("IntersectionObserver" in window)) { marks.forEach((m) => m.classList.add("on")); steps.forEach((s) => s.classList.add("on")); return; }
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) show(+e.target.dataset.step); }),
    { rootMargin: matchMedia("(max-width: 860px)").matches ? "-62% 0px -28% 0px" : "-45% 0px -45% 0px" });
  steps.forEach((s) => io.observe(s));
})();
