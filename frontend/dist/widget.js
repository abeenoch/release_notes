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
  mountNear(host, script);

  var shadow = host.attachShadow({ mode: 'open' });
  var style = [
    '.card{font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;',
    'border:1px solid #e4e4e7;border-radius:12px;background:#fff;overflow:hidden;',
    // pointer-events is inherited: re-enable hit-testing on our card so a host
    // page's `pointer-events:none` ancestor can't make the widget visible-but-dead.
    'pointer-events:auto;}',
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

  // If the snippet is pasted into <head> (very common), inserting beside the
  // script would drop the widget into a display:none subtree. Fall back to body.
  function mountNear(node, ref) {
    var parent = ref.parentNode;
    if (!parent || parent === document.head || parent.tagName === 'HTML') {
      parent = document.body || parent;
    }
    if (!parent) return;
    if (parent === ref.parentNode) parent.insertBefore(node, ref.nextSibling);
    else parent.appendChild(node);
  }

  // Host pages (SPA routers, themes, analytics) often attach document-level
  // click handlers that preventDefault every <a>. Our links live in a shadow
  // DOM, so such a handler can swallow the click and the "View all & subscribe"
  // link silently does nothing. Stop the event before it reaches the page; if a
  // capture-phase handler already cancelled it, navigate ourselves so the link
  // still works.
  function makeLink(url, text) {
    var a = el('a', null, text);
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.addEventListener('click', function (e) {
      e.stopPropagation();
      if (e.defaultPrevented) {
        e.preventDefault();
        window.open(url, '_blank', 'noopener');
      }
    });
    return a;
  }

  function render(data) {
    var card = el('div', 'card');
    var head = el('div', 'head');
    var pageUrl = origin + '/' + data.full_name;
    head.appendChild(makeLink(pageUrl, data.full_name));
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
    foot.appendChild(makeLink(pageUrl, 'View all & subscribe →'));
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
