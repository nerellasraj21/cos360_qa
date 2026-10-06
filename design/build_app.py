import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCR = r"C:\Users\nerel\AppData\Local\Temp\claude\C--Users-nerel-Documents-Workspace-PythonWorkspace-COS360-Full-App\b2d11f31-c02c-4840-9a1a-bb2ed5039261\scratchpad"
sys.path.insert(0, os.path.join(SCR, "orbit"))
sys.path.insert(0, os.path.join(SCR, "rebrand"))

import io
import contextlib

with contextlib.redirect_stdout(io.StringIO()):
    import o_web
    from gen_lib import ICONS, FONTS
    from olib import logo
    import importlib.util
    spec = importlib.util.spec_from_file_location("themes_src", os.path.join(SCR, "orbit", "theme.py"))
    src = open(os.path.join(SCR, "orbit", "theme.py"), encoding="utf-8").read().split("for key, (title")[0]
    ns = {"__file__": os.path.join(SCR, "orbit", "theme.py")}
    exec(compile(src, "theme", "exec"), ns)

CLAY, CLAY_RGBA, SPEC, SPEC_RGBA = ns["CLAY"], ns["CLAY_RGBA"], ns["SPECTRUM"], ns["SPECTRUM_RGBA"]
apply = ns["apply"]

TARGETS = [
    (r'Admit a student', 'people.students.create'),
    (r'Take a payment|Open the counter|Take payment', 'accounts.counter.c:counter'),
    (r'Mark attendance|See who is absent', 'classes.attendance.c:classroom'),
    (r'Publish hall', 'exams.hall.c:hall'),
    (r'Open marks|Class 8 B marks', 'exams.marks.c:marks'),
    (r'Message parents|Send reminder', 'messages.comm'),
    (r'Aarav Sharma', 'people.students.c:student360'),
    (r'Receipt R-', 'accounts.receipts'),
    (r'Refund R-|Review', 'accounts.refunds'),
    (r'^Edit', 'people.students.edit'),
]


def wire(html):
    def repl(m):
        attrs, text = m.group(1) + m.group(2), re.sub(r"<[^>]+>", "", m.group(3)).strip()
        for pat, tgt in TARGETS:
            if re.search(pat, text):
                return '<a %s role="button" tabindex="0" data-act="go" data-go="%s">%s</a>' % (attrs.strip(), tgt, m.group(3))
        return '<a %s role="button" tabindex="0" data-act="noop">%s</a>' % (attrs.strip(), m.group(3))

    return re.sub(r'<a ([^>]*?)href="#"([^>]*)>(.*?)</a>', repl, html, flags=re.S)


def clean(html):
    html = wire(html)
    return html.replace("<script", "&lt;script")


ICONS = dict(ICONS)
ICONS["chevD"] = '<path d="M6 9l6 6 6-6"/>'
ICONS["chevL"] = '<path d="M15 6l-6 6 6 6"/>'
ICONS["menu"] = '<path d="M4 7h16M4 12h16M4 17h16"/>'
ICONS["chevR"] = '<path d="M9 6l6 6-6 6"/>'

spec = json.load(open(os.path.join(HERE, "screen_spec.json"), encoding="utf-8"))
bespoke = {"today": clean(o_web.today), "student360": clean(o_web.stu360)}
logo_html = logo(36, dark=True).replace("#0B6E6B", "#FFFFFF")

orbit_css = open(os.path.join(SCR, "orbit", "base", "orbit.css"), encoding="utf-8").read()
app_css = open(os.path.join(HERE, "src", "app.css"), encoding="utf-8").read()
css = orbit_css + "\n" + app_css

paper = {"clay": "#EDEBE3", "spectrum": "#ECECF7"}
css_clay = apply(css, CLAY, CLAY_RGBA) + ":root{--paper:%s}" % paper["clay"]
css_spec = apply(css, SPEC, SPEC_RGBA) + ":root{--paper:%s}" % paper["spectrum"]
logo_clay = apply(logo_html, CLAY, CLAY_RGBA)

themes = {
    "clay": {"hex": CLAY, "rgba": CLAY_RGBA},
    "spectrum": {"hex": SPEC, "rgba": SPEC_RGBA},
}
data = {"spec": spec, "bespoke": bespoke, "themes": themes, "icons": ICONS, "logo": logo_clay}
js = open(os.path.join(HERE, "src", "app.js"), encoding="utf-8").read()
payload = json.dumps(data, separators=(",", ":")).replace("</", "<" + chr(92) + "/")

html = f"""<meta charset="utf-8"><title>Vartul</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;600;700;800&family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style id="css-clay">{css_clay}</style>
<style id="css-spectrum">{css_spec}</style>
<style>
:root{{color-scheme:light}}
html,body{{margin:0;padding:0;background:var(--paper)}}
:root{{padding-top:0!important}}
#tools{{padding:10px 16px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;background:var(--paper)}}
#tools .seg button{{border:0;background:transparent;font:700 13px var(--f-body);padding:7px 12px;border-radius:9px;color:var(--ink-2);cursor:pointer;min-height:34px}}
#tools .seg button.on{{background:#fff;color:var(--brand-d);box-shadow:0 1px 2px rgba(20,20,19,.14)}}
#tools .note{{font-size:12.5px;color:var(--muted);font-weight:600;margin-left:auto}}
</style>
<div id="tools" class="tools"></div>
<div id="stage"><div id="frame"><div id="app"></div></div></div>
<script>window.__DATA__={payload};</script>
<script>{js}</script>
"""
out = os.path.join(HERE, "vartul_app.html")
open(out, "w", encoding="utf-8").write(html)
print("built", os.path.getsize(out) // 1024, "KB")
