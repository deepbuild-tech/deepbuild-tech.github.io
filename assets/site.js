/* DeepBuild: motion only. Every word is in the HTML; this file only animates it.
   Loaded in <head> without defer so the "js" class is set before first paint.
   Failsafes: if setup throws, the "js" class is removed so nothing stays hidden; and the
   page opening is force-revealed after 1.5 s in case the observer never fires. */
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) return;
  root.classList.add("js");

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function revealOpening() {
    document.querySelectorAll("[data-lines], .hero .fade, .page-head .fade, .notfound .fade, .hero-rule")
      .forEach(function (el) { el.classList.add("is-in"); });
  }
  setTimeout(revealOpening, 1500);

  ready(function () {
    try { setup(); } catch (err) { root.classList.remove("js"); }
  });

  function setup() {
    // Header: frosted once the page has scrolled.
    var header = document.querySelector(".site-header");
    var sentinel = document.createElement("div");
    sentinel.setAttribute("aria-hidden", "true");
    sentinel.style.cssText = "position:absolute;top:0;left:0;width:1px;height:8px;";
    document.body.prepend(sentinel);
    new IntersectionObserver(function (e) {
      header.classList.toggle("is-scrolled", !e[0].isIntersecting);
    }).observe(sentinel);

    // Stagger index for masked lines.
    document.querySelectorAll("[data-lines]").forEach(function (group) {
      group.querySelectorAll(".line > span").forEach(function (s, i) {
        s.style.setProperty("--i", i);
      });
    });
    document.querySelectorAll(".fade[data-delay]").forEach(function (el) {
      el.style.setProperty("--d", el.getAttribute("data-delay") + "ms");
    });

    // Reveal on entering the viewport (hero items are already in view, so they run on load).
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.15 });
    document.querySelectorAll("[data-lines], .line[data-reveal], .fade, .hero-rule").forEach(function (el) {
      io.observe(el);
    });

    // Statement: wrap words, then light each one as it crosses the reading line.
    document.querySelectorAll(".statement").forEach(function (p) {
      var walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
      var nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(function (node) {
        var frag = document.createDocumentFragment();
        node.textContent.split(/(\s+)/).forEach(function (part) {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
          var s = document.createElement("span");
          s.className = "w";
          s.textContent = part;
          frag.appendChild(s);
        });
        node.parentNode.replaceChild(frag, node);
      });
      var lit = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          en.target.classList.toggle("is-lit", en.boundingClientRect.top < window.innerHeight * 0.62);
        });
      }, { rootMargin: "0px 0px -38% 0px", threshold: [0, 1] });
      p.querySelectorAll(".w").forEach(function (w) { lit.observe(w); });
    });
  }
})();
