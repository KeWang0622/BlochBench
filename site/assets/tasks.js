/* BlochBench tasks page: family cards grouped by domain, with domain filter and search. */
(function () {
  'use strict';
  var MRAB = window.MRAB;
  var h = MRAB.h, s = MRAB.s;

  function icon(name) {
    var paths = {
      clock: ['M12 7v5l3 2', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z'],
      check: ['M9 12l2 2 4-4', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z'],
      layers: ['M12 3l9 5-9 5-9-5 9-5z', 'M3 13l9 5 9-5'],
      x: ['M9 9l6 6', 'M15 9l-6 6', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z']
    }[name];
    return s('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true' }, paths.map(function (d) { return s('path', { d: d }); }));
  }

  var state = { domain: 'all', q: '' };
  var D;

  function matches(f) {
    if (state.domain !== 'all' && f.domain !== state.domain) return false;
    if (!state.q) return true;
    var hay = [f.id, f.title, f.input, f.output, f.verification, f.summary, f.domain_name, f.check_names.join(' ')].join(' ').toLowerCase();
    return state.q.split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }

  function card(f) {
    return h('article', { class: 'task', id: f.id, 'aria-labelledby': 't-' + f.id },
      h('h3', { id: 't-' + f.id, text: f.display_title || f.title }),
      h('dl', { class: 'task-contract' },
        h('dt', { text: 'Given' }), h('dd', { text: f.input || f.summary }),
        h('dt', { text: 'Deliver' }), h('dd', { text: f.output || 'Files specified by the task.' }),
        h('dt', { text: 'Check' }), h('dd', { text: f.verification || 'Independent checks against the task specification.' })),
      h('div', { class: 'facts' },
        h('span', { title: 'Time cap per run' }, icon('clock'), f.cap_min + ' min'),
        h('span', { title: 'Public instances' }, icon('layers'), f.instances.length + ' instances')),
      h('details', null,
        h('summary', { text: 'Checks and technical identifiers' }),
        h('p', { class: 'technical-id' }, 'Family ID: ', h('code', { text: f.id })),
        h('p', null, f.checks + ' checks · ' + f.negative_controls + ' negative controls · ' +
          (f.review === 'pending' ? 'expert review pending' : 'review ' + f.review)),
        h('ul', null, f.check_names.map(function (c) { return h('li', null, h('code', { text: c })); }))),
      h('div', { class: 'links' },
        h('a', { href: f.url, 'aria-label': (f.display_title || f.title) + ': specification, grader and controls on GitHub' }, 'Task specification and code ↗')));
  }

  function render() {
    var root = document.getElementById('task-groups');
    root.textContent = '';
    var shown = 0;
    D.domains.forEach(function (d) {
      var fams = D.families.filter(function (f) { return f.domain === d.code && matches(f); });
      if (!fams.length) return;
      shown += fams.length;
      root.appendChild(h('section', { class: 'domain-group', id: 'd-' + d.code, 'aria-labelledby': 'h-' + d.code, style: { padding: '0' } },
        h('header', null,
          h('h2', { id: 'h-' + d.code, text: d.name }),
          h('span', { class: 'meta', text: d.families + (d.families === 1 ? ' task type' : ' task types') + ' · ' + d.instances + ' instances · ' + d.checks + ' checks' })),
        h('div', { class: 'task-grid' }, fams.map(card))));
    });
    if (!shown) root.appendChild(h('div', { class: 'empty', text: 'No task matches this filter.' }));
    var count = document.getElementById('task-count');
    if (count) count.textContent = shown === D.families.length ? 'Showing all ' + shown + ' task types' : 'Showing ' + shown + ' of ' + D.families.length + ' task types';
  }

  function chips() {
    var bar = document.getElementById('domain-filter');
    bar.textContent = '';
    var all = [{ code: 'all', short: 'All', families: D.families.length, name: 'All domains' }].concat(D.domains);
    all.forEach(function (d) {
      bar.appendChild(h('button', { type: 'button', class: 'chip', 'aria-pressed': String(state.domain === d.code), title: d.name,
        onclick: function () {
          state.domain = d.code;
          bar.querySelectorAll('.chip').forEach(function (c) { c.setAttribute('aria-pressed', String(c === this)); }, this);
          render();
        } }, d.short, h('span', { class: 'n', text: String(d.families) })));
    });
  }

  MRAB.initTasks = function (data) {
    D = data;
    chips();
    render();
    var input = document.getElementById('task-search');
    if (input) input.addEventListener('input', function () { state.q = input.value.trim().toLowerCase(); render(); });
    if (location.hash) {
      var target = document.getElementById(location.hash.slice(1));
      if (target) setTimeout(function () { target.scrollIntoView(); }, 0);
    }
  };
})();
