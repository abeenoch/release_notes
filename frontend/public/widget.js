/* Release Notes — embeddable changelog widget
 *
 * Paste on any site:
 *   <script src="https://YOUR-ORIGIN/widget.js" data-repo="owner/repo" async></script>
 *
 * Renders the repo's latest public releases in a shadow DOM (styles can't
 * leak in or out) and links to the full vanity page. Read-only — subscribe
 * happens on the page itself.
 */
(function () {
  'use strict';

  var script = document.currentScript;
  if (!script) return;
  var repo = script.getAttribute('data-repo') || '';
  // Strict shape: owner/repo, nothing else — no path traversal, no protocol.
  if (!/^[\w.-]{1,100}\/[\w.-]{1,100}$/.test(repo)) {
    if (window.console) console.warn('Release Notes widget: invalid data-repo', repo);
    return;
  }
  var limit = parseInt(script.getAttribute('data-limit') || '5', 10);
  if (!(limit > 0) || limit > 50) limit = 5;

  var origin;
  try { origin = new URL(script.src).origin; } catch (e) { return; }

  var host = document.createElement('div');
  host.setAttribute('data-rn-widget', '');
  if (script.parentNode) script.parentNode.insertBefore(host, script.nextSibling);

  var shadow = host.attachShadow({ mode: 'open' });
  var style = [
    '.card{font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;',
    'border:1px solid #e4e4e7;border-radius:12px;background:#fff;overflow:hidden;}',
    '.head{display:flex;align-items:center;justify-content:space-between;gap:8px;',
    'padding:12px 16px;border-bottom:1px solid #e4e4e7;background:#fafafa;}',
    '.head a{font-weight:600;color:#18181b;text-decoration:none;}',
    '.head a:hover{text-decoration:underline;}',
    '.badge{font-size:11px;color:#71717a;}',
    '.item{padding:12px 16px;border-bottom:1px solid #f4f4f5;}',
    '.item:last-child{border-bottom:0;}',
    '.ver{font-weight:600;color:#18181b;}',
    '.date{font-size:12px;color:#a1a1aa;margin-left:8px;}',
    '.sum{color:#52525b;font-size:13px;margin-top:2px;',
    'display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}',
    '.empty,.err{padding:16px;color:#71717a;font-size:13px;}',
    '.foot{padding:8px 16px;font-size:11px;color:#a1a1aa;text-align:right;}',
    '.foot a{color:#71717a;text-decoration:none;} .foot a:hover{color:#18181b;}',
  ].join('');

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function render(data) {
    var card = el('div', 'card');
    var head = el('div', 'head');
    var title = el('a', null, data.full_name);
    title.href = origin + '/' + data.full_name;
    title.target = '_blank';
    head.appendChild(title);
    head.appendChild(el('span', 'badge', data.changelogs.length + ' release' +
      (data.changelogs.length === 1 ? '' : 's')));
    card.appendChild(head);

    if (!data.changelogs.length) {
      card.appendChild(el('div', 'empty', 'No releases yet.'));
    } else {
      data.changelogs.slice(0, limit).forEach(function (c) {
        var item = el('div', 'item');
        var line = el('div');
        line.appendChild(el('span', 'ver', c.version || c.to_tag || 'Unversioned'));
        var d = new Date(c.created_at);
        if (!isNaN(d)) line.appendChild(el('span', 'date', d.toISOString().slice(0, 10)));
        item.appendChild(line);
        if (c.summary) item.appendChild(el('div', 'sum', c.summary));
        card.appendChild(item);
      });
    }

    var foot = el('div', 'foot');
    var more = el('a', null, 'View all & subscribe →');
    more.href = origin + '/' + data.full_name;
    more.target = '_blank';
    foot.appendChild(more);
    card.appendChild(foot);

    shadow.innerHTML = '<style>' + style + '</style>';
    shadow.appendChild(card);
  }

  fetch(origin + '/api/public/' + encodeURI(repo), { headers: { Accept: 'application/json' } })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(render)
    .catch(function () {
      shadow.innerHTML = '<style>' + style + '</style>';
      var card = el('div', 'card');
      card.appendChild(el('div', 'err', 'Changelog unavailable.'));
      shadow.appendChild(card);
    });
})();
