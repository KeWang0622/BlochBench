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

  /* k-space art: radial spokes, rings and a three-interleave variable-density spiral (same motif as the banner). */
  MRAB.kspace = function (svg) {
    var R = 172, turns = 2.35, nil = 3, pts = 360, colors = ['#22d3ee', '#38bdf8', '#2dd4bf'];
    svg.setAttribute('viewBox', '-200 -200 400 400');
    var g = s('g', { stroke: '#5b7ea6', 'stroke-opacity': '0.24', 'stroke-width': '1', fill: 'none' });
    for (var i = 0; i < 16; i++) {
      var a = Math.PI * i / 16;
      g.appendChild(s('line', { x1: 196 * Math.cos(a), y1: 196 * Math.sin(a), x2: -196 * Math.cos(a), y2: -196 * Math.sin(a) }));
    }
    [58, 116, 174].forEach(function (r) { g.appendChild(s('circle', { r: r, 'stroke-opacity': '0.3' })); });
    svg.appendChild(g);
    function point(k, t) {
      var r = R * t, th = 2 * Math.PI * turns * Math.pow(t, 0.72) + 2 * Math.PI * k / nil;
      return [r * Math.cos(th), r * Math.sin(th)];
    }
    for (var k = 0; k < nil; k++) {
      var d = '';
      for (var j = 0; j <= pts; j++) {
        var p = point(k, j / pts);
        d += (j ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1);
      }
      var path = s('path', { d: d, class: 'traj draw' + (k ? ' d' + (k + 1) : ''), stroke: colors[k], 'stroke-opacity': k ? '0.75' : '0.95' });
      svg.appendChild(path);
      var len = Math.ceil(path.getTotalLength ? path.getTotalLength() : 2000);
      path.style.setProperty('--len', len);
      path.style.strokeDasharray = len;
    }
    var dots = s('g', { class: 'adc', fill: '#e0fbff' });
    for (var m = 6; m <= 72; m += 3) {
      var q = point(0, m / 72);
      dots.appendChild(s('circle', { cx: q[0].toFixed(1), cy: q[1].toFixed(1), r: '2.1' }));
    }
    svg.appendChild(dots);
    svg.appendChild(s('circle', { r: '4', fill: '#ffffff' }));
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
    var art = document.getElementById('kspace');
    if (art) MRAB.kspace(art);

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
    var page = document.body.getAttribute('data-page');
    MRAB.load().then(function (D) {
      MRAB.data = D;
      if (page === 'home') initHome(D);
      if (page === 'leaderboard' && MRAB.initLeaderboard) MRAB.initLeaderboard(D);
      if (page === 'tasks' && MRAB.initTasks) MRAB.initTasks(D);
    }).catch(showError);
  });
})();
