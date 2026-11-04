/* MRI Agent Bench site: shared helpers and the overview page. Plain JavaScript, no dependencies. */
(function () {
  'use strict';
  var MRAB = (window.MRAB = window.MRAB || {});
  var SVGNS = 'http://www.w3.org/2000/svg';

  /* Data: data/data.js defines window.MRAB_DATA (works from file://); otherwise fetch the JSON files. */
  MRAB.load = function () {
    if (window.MRAB_DATA) return Promise.resolve(window.MRAB_DATA);
    function get(f) {
      return fetch('data/' + f).then(function (r) {
        if (!r.ok) throw new Error('Could not load data/' + f);
        return r.json();
      });
    }
    return Promise.all([get('summary.json'), get('families.json'), get('leaderboard.json')]).then(function (x) {
      return { summary: x[0], domains: x[1].domains, families: x[1].families, leaderboard: x[2] };
    });
  };

  /* Tiny element builder: h('a', {href: '#', class: 'x', text: 'hi'}, child, ...). Text is never parsed as HTML. */
  function h(tag, props) {
    var el = document.createElement(tag);
    setProps(el, props);
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function s(tag, props) {
    var el = document.createElementNS(SVGNS, tag);
    setProps(el, props);
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function setProps(el, props) {
    if (!props) return;
    Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'text') el.textContent = v;
      else if (k === 'style' && typeof v === 'object') Object.keys(v).forEach(function (p) { el.style.setProperty(p, v[p]); });
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    });
  }
  function append(el, c) {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { append(el, x); }); return; }
    el.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
  }
  MRAB.h = h;
  MRAB.s = s;

  /* Number formatting */
  function trim1(v) { return Math.abs(v - Math.round(v)) < 0.05 ? String(Math.round(v)) : v.toFixed(1); }
  MRAB.pct = function (x) { return x === null || x === undefined ? '–' : trim1(100 * x) + '%'; };
  MRAB.ci = function (c) { return trim1(100 * c[0]) + '–' + trim1(100 * c[1]); };
  MRAB.tokens = function (n) { return n === null || n === undefined ? '–' : (n / 1e6).toFixed(2) + ' M'; };
  MRAB.minutes = function (sec) { return sec === null || sec === undefined ? '–' : fixed1(sec / 60) + ' min'; };
  // Match the source report's round-half-even formatting, including the 21.25 pp CI endpoint.
  function fixed1(v) {
    var scaled = Math.abs(v) * 10, whole = Math.floor(scaled);
    var rounded = Math.abs(scaled - whole - 0.5) < 1e-9 ? whole + (whole % 2) : Math.round(scaled);
    return (rounded / 10).toFixed(1);
  }
  MRAB.pp = function (d) { var v = 100 * d; return (v > 0.05 ? '+' : v < -0.05 ? '−' : '') + fixed1(v) + ' pp'; };

  MRAB.pvalue = function (p) { return p < 0.0001 ? p.toExponential(1) : p.toFixed(4); };
  MRAB.pairedCI = function (ci) { return MRAB.pp(ci[0]).replace(' pp', '') + ' to ' + MRAB.pp(ci[1]); };

  /* Completed offline aggregate summaries; per-entry medians remain in the Core table. */
  MRAB.offlineSummary = function (D) {
    var box = document.getElementById('offline-summary');
    var evaluation = D.leaderboard.offline_evaluation;
    if (!box || !evaluation) return;
    box.textContent = '';
    ['core', 'hard'].forEach(function (tier) {
      var group = evaluation[tier], v = group.all;
      box.appendChild(h('article', { class: 'card offline-card' },
        h('p', { class: 'eyebrow', text: tier === 'core' ? 'Core · 240 paired trials' : 'Hard · 134 paired trials' }),
        h('h2', null, h('span', { class: 'baseline-value', text: MRAB.pct(v.A / v.n) }),
          h('span', { class: 'muted', text: ' → ' }), h('span', { class: 'skills-value', text: MRAB.pct(v.S / v.n) })),
        h('p', { class: 'small', text: 'Verified runs · ' + v.A + '/' + v.n + ' → ' + v.S + '/' + v.n }),
        h('p', null, h('b', { text: MRAB.pp(v.diff) }), ' · 95% paired CI ' + MRAB.pairedCI(v.ci)),
        h('p', { class: 'small', text: v.n + ' pairs · ' + group.n_models + ' models · exact McNemar p = ' + MRAB.pvalue(v.p) }),
        h('p', { class: 'small', text: tier === 'core' ? 'Same 24 public trials for each model; diffusion declines despite the aggregate increase.' :
          'Interval includes no improvement. Three models × 30 trials; four models × 11 trials.' }),
        h('p', { class: 'small token-summary', text: 'MRFoundry / baseline: ' + v.tok_ratio.toFixed(2) + '× total tokens; ' + v.tok_per_success_ratio.toFixed(2) + '× tokens per success.' })));
    });
  };

  /* Copy buttons for code blocks marked data-copy. */
  function initCopy() {
    document.querySelectorAll('.code[data-copy]').forEach(function (block) {
      var pre = block.querySelector('pre');
      var btn = block.querySelector('.copy');
      if (!pre || !btn) return;
      btn.addEventListener('click', function () {
        var txt = pre.innerText.replace(/\n$/, '');
        var done = function () { btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = 'Copy'; }, 1600); };
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(txt).then(done, function () { fallback(txt); done(); });
        } else { fallback(txt); done(); }
      });
    });
    function fallback(txt) {
      var ta = h('textarea', { style: { position: 'fixed', opacity: '0' } });
      ta.value = txt;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (err) { /* ignore */ }
      ta.remove();
    }
  }

  /* ---------------------------------------------------------------- overview page */
  function initHome(D) {
    var target = document.getElementById('home-study');
    if (!target) return;
    var evaluation = D.leaderboard.offline_evaluation;
    target.textContent = '';
    ['core', 'hard'].forEach(function (tier) {
      var group = evaluation[tier], v = group.all;
      target.appendChild(h('article', { class: 'study-result' },
        h('p', { class: 'eyebrow', text: tier === 'core' ? 'Core / public' : 'Hard / nonpublic' }),
        h('div', { class: 'study-counts' },
          h('span', { class: 'baseline-value', text: v.A }), h('span', { class: 'count-arrow', text: '→' }),
          h('span', { class: 'skills-value', text: v.S }), h('span', { class: 'count-denominator', text: '/ ' + v.n })),
        h('p', { class: 'small', text: 'Verified trials · no skills → with MRFoundry skills' }),
        h('p', { class: 'study-difference' }, h('strong', { text: MRAB.pp(v.diff) }),
          ' · 95% paired CI ' + MRAB.pairedCI(v.ci)),
        h('p', { class: 'small muted', text: tier === 'core' ? '10 models × 24 paired trials' :
          '3 models × 30 pairs + 4 models × 11 pairs' })));
    });
  }

  /* A deep link into a collapsed results section should reveal its contents. */
  function revealFragment() {
    var id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch (err) { return; }
    var target = document.getElementById(id);
    if (!target) return;
    var detail = target.closest('details');
    if (!detail) return;
    while (detail) {
      detail.open = true;
      detail = detail.parentElement && detail.parentElement.closest('details');
    }
    target.scrollIntoView({ block: 'start' });
  }

  function showError(err) {
    var box = document.querySelector('[data-error]');
    if (box) {
      box.hidden = false;
      box.textContent = 'The data files could not be loaded (' + err.message + '). Reload the page, or use the linked repository documentation.';
    }
    if (window.console) console.error(err);
  }
  MRAB.showError = showError;

  document.addEventListener('DOMContentLoaded', function () {
    initCopy();
    window.addEventListener('hashchange', revealFragment);
    var page = document.body.getAttribute('data-page');
    MRAB.load().then(function (D) {
      MRAB.data = D;
      if (page === 'home') initHome(D);
      if (page === 'leaderboard' && MRAB.initLeaderboard) MRAB.initLeaderboard(D);
      if (page === 'tasks' && MRAB.initTasks) MRAB.initTasks(D);
      revealFragment();
    }).catch(showError);
  });
})();
