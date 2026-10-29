/* Holds back the page body until the charts are mounted, so nothing visible moves (CLS).
 *
 * The server HTML has empty chart placeholders (.chart-slot) that scripts fill after fetching
 * the data. Until then the headings below them sit near the top of the window, and every chart
 * that arrives pushes them down: measured Cumulative Layout Shift 0.4-1.0 against Google's
 * "good" limit of 0.1. Reserving a fixed height does not help because chart blocks range from
 * 140 to 1300 px. Instead the head script marks <html> "js-loading", CSS hides everything but
 * the <h1> (visibility:hidden, so layout still settles but nothing visible shifts), and this
 * file removes the mark once the slots are filled.
 *
 * Without JavaScript the class is never set and the page is shown as served. If this file
 * fails to run, the timer in the head script removes the mark after six seconds. */
(() => {
  'use strict';
  const root = document.documentElement;
  const MAX_WAIT_MS = 4000;
  const QUIET_MS = 500;
  const slots = [...document.querySelectorAll('.chart-slot')];
  let timer = 0;
  let observer = null;

  function reveal() {
    clearTimeout(timer);
    if (observer) observer.disconnect();
    root.classList.remove('js-loading');
    window.dispatchEvent(new Event('kaur:charts-ready'));
  }

  const filled = () => slots.filter((s) => s.childElementCount > 0).length;

  if (!slots.length) {
    reveal();
    return;
  }
  const settle = () => {
    clearTimeout(timer);
    // Everything mounted: show it. Otherwise wait for a quiet period after the last change,
    // which covers slots that legitimately stay empty (no data for that section).
    if (filled() === slots.length) reveal();
    else if (filled() > 0) timer = setTimeout(reveal, QUIET_MS);
  };
  observer = new MutationObserver(settle);
  observer.observe(document.querySelector('main'), { childList: true, subtree: true });
  setTimeout(reveal, MAX_WAIT_MS); // data never arrived (fetch failed): show what there is
  settle();
})();
