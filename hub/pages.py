"""Server-rendered pages: /famille (grandma's remote) and /care (dashboard).

Everything inline (CSS, JS, SVG charts) — no CDN, works on LAN without
internet and through the tunnel without extra origins.
"""

import html
from datetime import datetime

from . import db

_BASE_CSS = """
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
       background: #f4f1ea; color: #2d2a26; padding: 16px; max-width: 720px;
       margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 8px 0 16px; }
h2 { font-size: 1.05rem; margin: 20px 0 8px; color: #6b5d4f; }
.card { background: #fff; border-radius: 14px; padding: 14px; margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,.08); }
button { font-size: 1.05rem; border: 0; border-radius: 12px; padding: 12px 18px;
         cursor: pointer; }
.status { font-size: .85rem; color: #6b5d4f; }
.err { color: #a33; }
"""


def famille_page(person: str) -> str:
    """Grandma's page: see through Reachy + make him speak."""
    p = html.escape(person.capitalize())
    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Reachy — Famille</title>
<style>{_BASE_CSS}
#snap {{ width: 100%; border-radius: 12px; background: #ddd; min-height: 200px; }}
#viewBtn {{ background: #4a7c59; color: #fff; width: 100%; }}
#sayBtn {{ background: #b5651d; color: #fff; width: 100%; margin-top: 8px; }}
textarea {{ width: 100%; font-size: 1.1rem; border-radius: 10px; border: 1px solid #ccc;
           padding: 10px; min-height: 70px; }}
.chip {{ background: #eee4d4; border-radius: 999px; padding: 8px 14px; margin: 4px 4px 0 0;
        display: inline-block; font-size: .95rem; cursor: pointer; }}
</style></head><body>
<h1>🤖 Reachy — bonjour {p} !</h1>

<div class="card">
  <h2>👁 Voir par les yeux de Reachy</h2>
  <img id="snap" alt="" hidden>
  <button id="viewBtn">Regarder</button>
  <div class="status" id="viewStatus"></div>
</div>

<div class="card">
  <h2>💬 Faire parler Reachy</h2>
  <div id="phrases"></div>
  <textarea id="msg" placeholder="Écrivez un petit message…"></textarea>
  <button id="sayBtn">Envoyer 📣</button>
  <div class="status" id="sayStatus"></div>
</div>

<script>
const $ = id => document.getElementById(id);
let viewing = false, timer = null;

async function api(path, opts) {{
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({{}}))).detail || r.status);
  return r;
}}

async function refreshSnap() {{
  try {{
    const r = await api('api/snapshot');
    const blob = await r.blob();
    const img = $('snap');
    if (img.src) URL.revokeObjectURL(img.src);
    img.src = URL.createObjectURL(blob);
    img.hidden = false;
    $('viewStatus').textContent = 'En direct · ' + new Date().toLocaleTimeString('fr-FR');
  }} catch (e) {{
    $('viewStatus').innerHTML = '<span class="err">Image indisponible (' + e.message + ')</span>';
  }}
}}

$('viewBtn').onclick = async () => {{
  viewing = !viewing;
  $('viewBtn').textContent = viewing ? 'Arrêter' : 'Regarder';
  if (viewing) {{
    api('api/view/start', {{method: 'POST'}}).catch(() => {{}});
    refreshSnap();
    timer = setInterval(refreshSnap, 2500);
  }} else {{
    clearInterval(timer);
    $('snap').hidden = true;
    $('viewStatus').textContent = '';
  }}
}};

$('sayBtn').onclick = async () => {{
  const text = $('msg').value.trim();
  if (!text) return;
  $('sayStatus').textContent = 'Envoi…';
  try {{
    await api('api/say', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                           body: JSON.stringify({{text}})}});
    $('sayStatus').textContent = 'Reachy transmet votre message 🎉';
    $('msg').value = '';
  }} catch (e) {{
    $('sayStatus').innerHTML = '<span class="err">Échec : ' + e.message + '</span>';
  }}
}};

fetch('api/phrases').then(r => r.json()).then(list => {{
  $('phrases').innerHTML = list.map(p =>
    `<span class="chip">${{p}}</span>`).join('');
  for (const chip of document.querySelectorAll('.chip'))
    chip.onclick = () => {{ $('msg').value = chip.textContent; }};
}}).catch(() => {{}});
</script></body></html>"""


# ── care dashboard ───────────────────────────────────────────────────────────

_KIND_FR = {
    "visit": "👥 visite",
    "meal": "🍽 repas",
    "medication": "💊 médicament",
    "mood": "🙂 humeur",
    "activity": "🚶 activité",
    "note": "📝 note",
}


def _bar_svg(counts: list[dict]) -> str:
    """Conversation volume per day, inline SVG bars."""
    if not counts:
        return ""
    w, h, bw = 660, 90, max(4, 660 // max(len(counts), 1) - 4)
    mx = max((c["turns"] for c in counts), default=1) or 1
    bars = []
    for i, c in enumerate(counts):
        bh = round((c["turns"] / mx) * (h - 20))
        x = i * (bw + 4)
        bars.append(
            f'<rect x="{x}" y="{h - bh - 14}" width="{bw}" height="{bh}" rx="2" fill="#4a7c59">'
            f'<title>{c["day"]}: {c["turns"]} tours</title></rect>'
            f'<text x="{x + bw / 2}" y="{h - 2}" font-size="8" text-anchor="middle" '
            f'fill="#6b5d4f">{c["day"][8:]}</text>'
        )
    return f'<svg viewBox="0 0 {w} {h}" width="100%">{"".join(bars)}</svg>'


def care_page(day: str | None = None) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    day = day or today
    counts = db.daily_counts(14)
    events = db.journal_for_day(day)
    last = db.last_events(8)
    moods = db.mood_entries(14)
    reps = db.repeated_utterances(30)

    def row(e: dict) -> str:
        t = html.escape(e["ts"][11:16])
        return (
            f'<tr><td class="ts">{t}</td><td>{_KIND_FR.get(e["kind"], e["kind"])}</td>'
            f"<td>{html.escape(e['text'])}</td></tr>"
        )

    events_html = (
        f'<table>{"".join(row(e) for e in events)}</table>'
        if events
        else "<p class='status'>Rien dans le journal ce jour-là.</p>"
    )
    last_html = "".join(
        f"<li><b>{html.escape(e['ts'][:16].replace('T', ' '))}</b> — "
        f"{_KIND_FR.get(e['kind'], e['kind'])} : {html.escape(e['text'])}</li>"
        for e in last
    ) or "<li class='status'>Journal vide pour l'instant.</li>"
    moods_html = "".join(
        f"<li><b>{html.escape(m['day'][5:])}</b> {html.escape(m['text'])}</li>" for m in moods
    ) or "<li class='status'>Pas d'humeur consignée sur 14 jours.</li>"

    reps_rows = "".join(
        f"<tr><td>{html.escape(c['example'])}</td><td>{c['count']}×</td>"
        f"<td>{c['this_week']}× cette sem. / {c['prev_week']}× la préc.</td></tr>"
        for c in reps[:12]
    )
    reps_html = (
        f"<table><tr><th>Phrase</th><th>Total 30 j</th><th>Tendance</th></tr>{reps_rows}</table>"
        if reps_rows
        else "<p class='status'>Aucune répétition détectée (≥3× sur 30 jours).</p>"
    )

    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reachy — Suivi</title>
<style>{_BASE_CSS}
table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
td, th {{ padding: 5px 8px; border-bottom: 1px solid #eee; text-align: left;
         vertical-align: top; }}
.ts {{ color: #6b5d4f; white-space: nowrap; }}
input[type=date] {{ font-size: 1rem; padding: 6px; border-radius: 8px;
                    border: 1px solid #ccc; }}
li {{ margin-bottom: 4px; }}
ul {{ padding-left: 18px; }}
</style></head><body>
<h1>📊 Suivi Reachy Mémoire</h1>

<div class="card"><h2>Conversation (tours de parole / jour, 14 j)</h2>{_bar_svg(counts)}</div>

<div class="card"><h2>🔁 Questions / phrases répétées (30 j)</h2>{reps_html}
<p class="status">Une phrase qui monte d'une semaine à l'autre est un signal à surveiller.</p></div>

<div class="card"><h2>🙂 Humeur (14 j)</h2><ul>{moods_html}</ul></div>

<div class="card"><h2>📅 Journal du jour
<input type="date" value="{day}" max="{today}"
 onchange="location.search='?day='+this.value"></h2>{events_html}</div>

<div class="card"><h2>Derniers événements</h2><ul>{last_html}</ul></div>
</body></html>"""
