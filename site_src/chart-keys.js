/* Keyboard access for the SVG charts: one Tab stop per chart, arrow keys between data marks.
 *
 * The chart builders give every data mark tabindex="0". A page with a thousand marks then has a
 * thousand Tab stops (jaatmed.html: 1902), which WCAG 2.1.1/2.4.3 fail in practice. This is the
 * "roving tabindex" pattern from the WAI-ARIA Authoring Practices: exactly one mark of a chart is
 * tabbable, arrow keys move focus (and so the tooltip) to the neighbouring mark, and the mark that
 * last had focus is the one Tab returns to.
 *
 * It lives outside the chart builders on purpose: it observes the DOM, so every present and future
 * chart gets it without touching eighteen call sites, and redraws (selectors) are picked up too. */
(() => {
  'use strict';
  const done = new WeakSet();
  const PAGE_STEP = 10;

  function step(key, i, last) {
    switch (key) {
      case 'ArrowRight': case 'ArrowDown': return Math.min(last, i + 1);
      case 'ArrowLeft': case 'ArrowUp': return Math.max(0, i - 1);
      case 'PageDown': return Math.min(last, i + PAGE_STEP);
      case 'PageUp': return Math.max(0, i - PAGE_STEP);
      case 'Home': return 0;
      case 'End': return last;
      default: return null;
    }
  }

  function setup(svg) {
    if (done.has(svg)) return;
    done.add(svg);
    const marks = [...svg.querySelectorAll('[tabindex="0"]')];
    if (marks.length < 2) return; // a single mark is already a single Tab stop
    marks.forEach((m, i) => m.setAttribute('tabindex', i === 0 ? '0' : '-1'));
    let current = 0;
    const indexOf = (node) => marks.findIndex((m) => m === node || m.contains(node));
    svg.addEventListener('focusin', (e) => {
      const i = indexOf(e.target);
      if (i < 0 || i === current) return;
      marks[current].setAttribute('tabindex', '-1');
      marks[i].setAttribute('tabindex', '0');
      current = i;
    });
    svg.addEventListener('keydown', (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const i = indexOf(e.target);
      if (i < 0) return;
      const next = step(e.key, i, marks.length - 1);
      if (next === null) return;
      e.preventDefault(); // arrows must not scroll the page while a chart has focus
      if (next !== i) marks[next].focus();
    });
  }

  function scan(root) {
    if (root.nodeType !== 1) return;
    if (root.matches('svg[role=img]')) setup(root);
    root.querySelectorAll('svg[role=img]').forEach(setup);
  }

  scan(document.body);
  new MutationObserver((records) => {
    for (const r of records) r.addedNodes.forEach(scan);
  }).observe(document.body, { childList: true, subtree: true });
})();
