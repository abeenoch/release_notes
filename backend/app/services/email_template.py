"""Rich branded HTML email template for changelog notifications."""
from __future__ import annotations

import html as _html
import re


def _inline(s: str) -> str:
    s = _html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r'<code style="background:#f4f4f5;padding:1px 5px;border-radius:4px;font-family:monospace;font-size:13px;">\1</code>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" style="color:#b45309;text-decoration:underline;">\1</a>',
        s,
    )
    return s


def _strip_duplicate_title(lines: list[str]) -> list[str]:
    """Drop a leading '# Changelog …' heading — the template header already
    renders the subject as its H1, so keeping the markdown H1 duplicates
    'Changelog — <version>' in every mail."""
    out = list(lines)
    for i, line in enumerate(out):
        if not line.strip():
            continue
        if re.match(r"^#\s+Changelog\b", line.strip(), flags=re.IGNORECASE):
            return out[i + 1 :]
        return out
    return out


# Inline, email-safe copy of frontend/public/favicon.svg (the Release Notes
# document icon). Referencing /favicon.svg by URL won't load in mail clients,
# so the SVG is inlined.
_LOGO_SVG = (
    '<svg width="32" height="32" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" '
    'role="img" aria-label="Release Notes" style="display:block;">'
    '<defs><linearGradient id="rn-grad" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#f59e0b"/>'
    '<stop offset="1" stop-color="#d97706"/>'
    "</linearGradient></defs>"
    '<rect width="64" height="64" rx="15" fill="url(#rn-grad)"/>'
    '<g fill="none" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" '
    'stroke-linejoin="round" transform="translate(10 10) scale(1.9)">'
    '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>'
    '<polyline points="14 2 14 8 20 8"/>'
    '<line x1="16" y1="13" x2="8" y2="13"/>'
    '<line x1="16" y1="17" x2="8" y2="17"/>'
    '<line x1="10" y1="9" x2="8" y2="9"/>'
    "</g></svg>"
)


def changelog_email_html(
    subject: str,
    markdown: str,
    repo_name: str | None = None,
    release_url: str | None = None,
) -> str:
    """Render a changelog markdown blob into a branded, email-safe HTML template."""
    lines = _strip_duplicate_title(markdown.split("\n"))
    body: list[str] = []
    in_list = False
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                body.append("</code></pre>")
                in_code = False
            else:
                if in_list:
                    body.append("</ul>")
                    in_list = False
                body.append(
                    '<pre style="background:#18181b;color:#e4e4e7;padding:12px 14px;'
                    'border-radius:8px;overflow-x:auto;font-family:monospace;font-size:12px;'
                    'line-height:1.5;margin:12px 0;"><code>'
                )
                in_code = True
            continue
        if in_code:
            body.append(_html.escape(line))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            if in_list:
                body.append("</ul>")
                in_list = False
            level = len(m.group(1))
            sizes = {1: "22px", 2: "18px", 3: "15px", 4: "14px"}
            weight = "700" if level <= 2 else "600"
            border = (
                'border-bottom:1px solid #e4e4e7;padding-bottom:4px;'
                if level == 2
                else ""
            )
            body.append(
                f'<h{level} style="margin:18px 0 8px;font-size:{sizes[level]};'
                f'font-weight:{weight};color:#18181b;{border}">{_inline(m.group(2))}</h{level}>'
            )
            continue

        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            if not in_list:
                body.append(
                    '<ul style="margin:8px 0;padding-left:22px;'
                    'list-style:disc;color:#3f3f46;">'
                )
                in_list = True
            body.append(
                f'<li style="margin:3px 0;line-height:1.55;">{_inline(m.group(1))}</li>'
            )
            continue

        if in_list:
            body.append("</ul>")
            in_list = False
        if re.match(r"^\s*$", line):
            continue
        body.append(
            f'<p style="margin:8px 0;line-height:1.6;color:#3f3f46;">{_inline(line)}</p>'
        )

    if in_list:
        body.append("</ul>")
    if in_code:
        body.append("</code></pre>")
    content = "\n".join(body)

    cta = ""
    if release_url:
        cta = (
            f'<a href="{_html.escape(release_url)}" '
            'style="display:inline-block;background:#d97706;color:#fff;'
            'text-decoration:none;font-weight:600;font-size:14px;padding:10px 18px;'
            'border-radius:8px;margin-top:4px;">View release on GitHub</a>'
        )

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:24px;background:#f4f4f5;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:16px;border:1px solid #e4e4e7;overflow:hidden;">
    <tr>
      <td style="background:linear-gradient(135deg,#f59e0b,#d97706);padding:20px 24px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
          <td style="vertical-align:middle;">
            <table role="presentation" cellpadding="0" cellspacing="0"><tr>
              <td style="vertical-align:middle;width:32px;">{_LOGO_SVG}</td>
              <td style="vertical-align:middle;color:#fff;font-weight:700;font-size:16px;padding-left:10px;">Release Notes</td>
            </tr></table>
          </td>
          <td style="text-align:right;color:rgba(255,255,255,0.9);font-size:12px;">{ _html.escape(repo_name or '') }</td>
        </tr></table>
      </td>
    </tr>
    <tr><td style="padding:24px;">
      <p style="margin:0 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:#71717a;">Changelog</p>
      <h1 style="margin:0 0 16px;font-size:22px;color:#18181b;">{ _html.escape(subject) }</h1>
      {content}
      <div style="margin:20px 0 0;">{cta}</div>
    </td></tr>
    <tr><td style="padding:16px 24px;background:#fafafa;border-top:1px solid #e4e4e7;">
      <p style="margin:0;font-size:12px;color:#71717a;">
        Auto-generated by Release Notes — incremental, AI-written changelogs.
      </p>
    </td></tr>
  </table>
</body>
</html>"""
