// Presentation behaviour: draw charts when they come near the screen, keyboard navigation, notes (N), timer (T), contents.
(function () {
  const config = JSON.parse(document.getElementById("plot-config").textContent);
  const screens = Array.from(document.querySelectorAll(".screen"));
  const drawn = new Set();

  function draw(el) {
    const name = el.dataset.figure;
    if (drawn.has(el)) return;
    const src = document.getElementById("fig-" + name);
    if (!src || !window.Plotly) return;
    const fig = JSON.parse(src.textContent);
    Plotly.newPlot(el, fig.data, fig.layout, config);
    drawn.add(el);
  }
  const plots = Array.from(document.querySelectorAll(".plot[data-figure]"));
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) draw(e.target); }), { rootMargin: "600px 0px" });
    plots.forEach(p => io.observe(p));
  } else { plots.forEach(draw); }
  window.addEventListener("beforeprint", () => plots.forEach(draw));

  // current screen and progress bar
  let current = 0;
  function update() {
    const mid = window.innerHeight / 2;
    let best = 0;
    screens.forEach((s, i) => { if (s.getBoundingClientRect().top <= mid) best = i; });
    current = best;
    document.getElementById("progress").style.width = (100 * (current + 1) / screens.length) + "%";
    updateTimer();
  }
  window.addEventListener("scroll", () => window.requestAnimationFrame(update), { passive: true });

  function go(i) { const t = screens[Math.max(0, Math.min(screens.length - 1, i))]; if (t) t.scrollIntoView({ behavior: "smooth", block: "start" }); }

  // timer: total time since T was first pressed, and the planned minutes of the current chapter
  const timer = document.getElementById("timer");
  let started = null;
  function chapterOf(i) { const s = screens[i]; return s ? s.closest(".chapter") : null; }
  function fmt(sec) { const m = Math.floor(sec / 60), s = Math.floor(sec % 60); return m + ":" + String(s).padStart(2, "0"); }
  function updateTimer() {
    if (timer.hidden || started === null) return;
    const total = (Date.now() - started) / 1000;
    const ch = chapterOf(current);
    const plan = ch && ch.dataset.minutes ? " · poglavje: " + ch.dataset.minutes.replace(".", ",") + " min" : "";
    timer.textContent = fmt(total) + " / 20:00" + plan;
    timer.classList.toggle("over", total > 20 * 60);
  }
  setInterval(updateTimer, 1000);

  document.addEventListener("keydown", e => {
    if (e.target.closest("input, textarea")) return;
    const k = e.key;
    if (["ArrowDown", "ArrowRight", "PageDown", " "].includes(k)) { e.preventDefault(); go(current + 1); }
    else if (["ArrowUp", "ArrowLeft", "PageUp"].includes(k)) { e.preventDefault(); go(current - 1); }
    else if (k === "Home") { e.preventDefault(); go(0); }
    else if (k === "End") { e.preventDefault(); go(screens.length - 1); }
    else if (k === "n" || k === "N") { document.body.classList.toggle("show-notes"); }
    else if (k === "t" || k === "T") { if (started === null) started = Date.now(); timer.hidden = !timer.hidden; updateTimer(); }
  });

  // table of contents
  const toc = document.getElementById("toc"), btn = document.getElementById("toc-toggle");
  btn.addEventListener("click", () => { toc.classList.toggle("open"); btn.setAttribute("aria-expanded", toc.classList.contains("open")); });
  toc.querySelectorAll("a").forEach(a => a.addEventListener("click", () => toc.classList.remove("open")));

  window.addEventListener("resize", () => drawn.forEach(el => Plotly.Plots.resize(el)));
  update();
})();
