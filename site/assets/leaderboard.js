/* MRI Agent Bench results: paired counts, alphabetical models, explicit coverage. */
(function () {
  'use strict';
  var MRAB = window.MRAB, h = MRAB.h;
  var D, entries, names;
  var state = { view: 'both', heat: 'domain' };

  function inView(e) {
    return state.view === 'base' ? !e.addon : state.view === 'mrf' ? !!e.addon : true;
  }
  function viewLabel() {
    return state.view === 'base' ? 'baseline' : state.view === 'mrf' ? 'with MRFoundry' : 'baseline and with MRFoundry';
  }
  function modelOrder(a, b) { return (names[a] || a).localeCompare(names[b] || b); }

  function pairedTable(table, models, ids, caption) {
    table.textContent = '';
    table.appendChild(h('caption', { class: 'sr-only', text: caption + '; models listed alphabetically' }));
    table.appendChild(h('thead', null, h('tr', null,
      ['Model', 'Baseline', '+ MRFoundry', 'Difference', 'MRF-only / base-only', 'Exact p'].map(function (label) {
        return h('th', { scope: 'col', text: label });
      }))));
    table.appendChild(h('tbody', null, ids.map(function (model) {
      var v = models[model];
      return h('tr', null,
        h('th', { scope: 'row', text: names[model] || model }),
        h('td', { text: v.A + '/' + v.n }),
        h('td', { text: v.S + '/' + v.n }),
        h('td', { text: MRAB.pp((v.S - v.A) / v.n) }),
        h('td', { title: 'MRFoundry-only / baseline-only verified pairs', text: v.S_only + ' / ' + v.A_only }),
        h('td', { text: MRAB.pvalue(v.p) }));
    })));
  }

  function renderPairs() {
    var evaluation = D.leaderboard.offline_evaluation;
    if (!evaluation) return;
    var core = evaluation.core.by_model;
    pairedTable(document.getElementById('core-pairs'), core, Object.keys(core).sort(modelOrder), 'Core paired results');
    var box = document.getElementById('hard-cohorts'), hard = evaluation.hard.by_model;
    box.textContent = '';
    var sizes = Array.from(new Set(Object.keys(hard).map(function (model) { return hard[model].n; }))).sort(function (a, b) { return b - a; });
    sizes.forEach(function (size) {
      var ids = Object.keys(hard).filter(function (model) { return hard[model].n === size; }).sort(modelOrder);
      var label = size + ' trials per model · ' + ids.length + ' models';
      box.appendChild(h('h3', { class: 'cohort-title', text: label }));
      var table = h('table', { class: 'cohort-table' });
      pairedTable(table, hard, ids, 'Hard ' + label);
      box.appendChild(h('div', { class: 'table-wrap', tabindex: '0', role: 'region', 'aria-label': 'Hard ' + label }, table));
    });
  }

  function renderDetails() {
    var table = document.getElementById('arm-details');
    table.textContent = '';
    table.appendChild(h('caption', { class: 'sr-only', text: 'Core results by model and arm, including uncertainty and resources' }));
    table.appendChild(h('thead', null, h('tr', null,
      ['Model / arm', 'Verified', 'Rate', '95% Wilson CI', 'Median tokens', 'Median time'].map(function (label) {
        return h('th', { scope: 'col', text: label });
      }))));
    var sorted = entries.slice().sort(function (a, b) {
      return a.model_name.localeCompare(b.model_name) || Number(!!a.addon) - Number(!!b.addon);
    });
    table.appendChild(h('tbody', null, sorted.map(function (e) {
      return h('tr', null,
        h('th', { scope: 'row' }, e.model_name, h('span', { class: 'arm-label', text: e.addon ? '+ MRFoundry' : 'Baseline' })),
        h('td', { text: e.verified + '/' + e.runs }),
        h('td', { text: MRAB.pct(e.rate) }),
        h('td', { text: MRAB.ci(e.ci95) + '%' }),
        h('td', { text: MRAB.tokens(e.median_tokens) }),
        h('td', { text: MRAB.minutes(e.median_wall_s) }));
    })));
  }

  function heatClass(k, n) {
    if (!n) return 'na';
    var r = k / n;
    return r === 0 ? 'h0' : r < 0.5 ? 'h1' : r < 0.75 ? 'h2' : r < 1 ? 'h3' : 'h4';
  }

  function heatRows() {
    return entries.filter(inView).slice().sort(function (a, b) {
      return a.model_name.localeCompare(b.model_name) || Number(!!a.addon) - Number(!!b.addon);
    });
  }

  function renderHeat() {
    var t = document.getElementById('heat');
    t.textContent = '';
    var cols;
    if (state.heat === 'domain') {
      cols = D.domains.map(function (d) {
        return { label: d.short, title: d.name, cell: function (e) { return e.by_domain[d.code]; } };
      });
    } else {
      var famOf = D.leaderboard.family_of_instance || {};
      var instOf = {};
      Object.keys(famOf).forEach(function (i) { instOf[famOf[i]] = i; });
      var fams = [];
      D.domains.forEach(function (d) {
        D.families.forEach(function (f) { if (f.domain === d.code && instOf[f.id]) fams.push(f); });
      });
      cols = fams.map(function (f) {
        return { label: f.public_id + " · " + (f.display_title || f.title),
          title: f.public_id + ": " + (f.display_title || f.title), fam: true,
          cell: function (e) { return e.per_instance[instOf[f.id]]; } };
      });
    }
    t.appendChild(h('caption', { class: 'sr-only', text: 'Verified runs by ' + (state.heat === 'domain' ? 'domain' : 'task family') + ', ' + viewLabel() }));
    t.appendChild(h('thead', null, h('tr', null,
      h('th', { scope: 'col', text: 'Entry', style: { 'text-align': 'left' } }),
      h('th', { scope: 'col', text: 'All' }),
      cols.map(function (c) { return h('th', { scope: 'col', title: c.title, class: c.fam ? 'fam' : null, text: c.label }); }))));
    var tb = h('tbody');
    heatRows().forEach(function (e) {
      var name = e.model_name + (e.addon ? ' + ' + e.addon.name : '');
      tb.appendChild(h('tr', null,
        h('th', { scope: 'row' }, h('span', { style: { display: 'inline-flex', 'align-items': 'center', gap: '7px' } },
          h('span', { class: 'swatch' + (e.addon ? ' mrf' : ''), 'aria-hidden': 'true' }), e.model_name),
          h('span', { class: 'sub', text: (e.addon ? '+ ' + e.addon.name : 'Baseline') + (e.complete ? '' : ' · in progress') })),
        h('td', { class: 'all ' + heatClass(e.verified, e.runs), title: name + ', all: ' + e.verified + ' of ' + e.runs + ' runs verified', text: e.verified + '/' + e.runs }),
        cols.map(function (c) {
          var v = c.cell(e);
          if (!v || !v.runs) return h('td', { class: 'na', title: name + ', ' + c.title + ': no runs', text: '–' });
          return h('td', { class: heatClass(v.verified, v.runs), title: name + ', ' + c.title + ': ' + v.verified + ' of ' + v.runs + ' runs verified',
            text: v.verified + '/' + v.runs });
        })));
    });
    t.appendChild(tb);
  }

  function bindSeg(id, key) {
    var seg = document.getElementById(id);
    seg.querySelectorAll('button').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.getAttribute('data-v') === state[key]));
      button.addEventListener('click', function () {
        state[key] = button.getAttribute('data-v');
        seg.querySelectorAll('button').forEach(function (other) { other.setAttribute('aria-pressed', String(other === button)); });
        renderHeat();
      });
    });
  }

  MRAB.initLeaderboard = function (data) {
    D = data;
    entries = (D.leaderboard.entries || []).slice();
    names = {};
    entries.forEach(function (e) { names[e.model] = e.model_name; });
    bindSeg('view-seg', 'view');
    bindSeg('heat-seg', 'heat');
    MRAB.offlineSummary(D);
    renderPairs();
    renderDetails();
    renderHeat();
  };
})();
