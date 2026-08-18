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
    """Grandma's page, designed for an older user: three huge actions
    (voice message, watch, written message), big type, high contrast,
    one thing at a time, plain-words feedback.
    """
    p = html.escape(person.capitalize())
    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Reachy — Famille</title>
<style>
* {{ box-sizing: border-box; margin: 0; -webkit-tap-highlight-color: transparent; }}
body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; background: #fffdf7;
       color: #1a1a1a; padding: 14px; max-width: 560px; margin: 0 auto;
       font-size: 20px; line-height: 1.4; }}
h1 {{ font-size: 1.5rem; text-align: center; margin: 6px 0 18px; }}
.big {{ display: block; width: 100%; border: 0; border-radius: 20px; padding: 22px;
       font-size: 1.5rem; font-weight: 700; color: #fff; cursor: pointer;
       margin-bottom: 16px; box-shadow: 0 3px 6px rgba(0,0,0,.2); }}
.big:active {{ transform: scale(.98); }}
#recBtn {{ background: #c0392b; }}
#recBtn.recording {{ background: #7b241c; animation: pulse 1s infinite; }}
#viewBtn {{ background: #1e6641; }}
#writeBtn {{ background: #8a5a00; }}
@keyframes pulse {{ 50% {{ opacity: .75; }} }}
#snap {{ width: 100%; border-radius: 16px; margin-bottom: 12px; display: none; }}
#writeZone {{ display: none; }}
textarea {{ width: 100%; font-size: 1.4rem; border-radius: 14px; border: 2px solid #999;
           padding: 14px; min-height: 90px; margin-bottom: 10px; }}
.chip {{ display: block; width: 100%; background: #f2e8d5; border: 2px solid #d9c9a3;
        border-radius: 14px; padding: 14px; margin-bottom: 8px; font-size: 1.15rem;
        text-align: left; cursor: pointer; }}
#status {{ text-align: center; font-size: 1.3rem; min-height: 2.2rem; margin: 10px 0;
          font-weight: 600; }}
.good {{ color: #1e6641; }} .bad {{ color: #b03a2e; }}
</style></head><body>
<h1>🤖 Bonjour {p} !</h1>
<div id="status"></div>

<button class="big" id="recBtn">🎙️ Parler à Reachy<br>
<span style="font-size:1rem;font-weight:400">Appuyez, parlez, réappuyez pour envoyer</span></button>

<img id="snap" alt="Ce que voit Reachy">
<button class="big" id="viewBtn">👁 Voir la maison</button>

<button class="big" id="writeBtn">✏️ Écrire un message</button>
<div id="writeZone">
  <div id="phrases"></div>
  <textarea id="msg" placeholder="Votre message…"></textarea>
  <button class="big" id="sayBtn" style="background:#8a5a00">📣 Reachy le dira à voix haute</button>
</div>

<script>
const $ = id => document.getElementById(id);
const status = (txt, cls) => {{ $('status').textContent = txt; $('status').className = cls || ''; }};

async function api(path, opts) {{
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({{}}))).detail || 'erreur ' + r.status);
  return r;
}}

// ── voice message: tap to record, tap again to send ──
let rec = null, chunks = [];
$('recBtn').onclick = async () => {{
  if (rec && rec.state === 'recording') {{ rec.stop(); return; }}
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{audio: true}});
    const mime = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm', '']
      .find(m => !m || MediaRecorder.isTypeSupported(m));
    rec = new MediaRecorder(stream, mime ? {{mimeType: mime}} : undefined);
    chunks = [];
    rec.ondataavailable = e => chunks.push(e.data);
    rec.onstop = async () => {{
      stream.getTracks().forEach(t => t.stop());
      $('recBtn').classList.remove('recording');
      $('recBtn').innerHTML = '🎙️ Parler à Reachy<br><span style="font-size:1rem;font-weight:400">Appuyez, parlez, réappuyez pour envoyer</span>';
      status('Envoi de votre voix…');
      const blob = new Blob(chunks, {{type: rec.mimeType || 'audio/webm'}});
      const ext = (rec.mimeType || '').includes('mp4') ? '.mp4' : '.webm';
      const form = new FormData();
      form.append('file', blob, 'message' + ext);
      try {{
        await api('api/voice', {{method: 'POST', body: form}});
        status('✔ Votre voix passe chez lui !', 'good');
      }} catch (e) {{ status('✖ Échec : ' + e.message, 'bad'); }}
    }};
    rec.start();
    $('recBtn').classList.add('recording');
    $('recBtn').innerHTML = '🔴 Je vous écoute…<br><span style="font-size:1rem;font-weight:400">Réappuyez quand vous avez fini</span>';
    status('Parlez maintenant');
  }} catch (e) {{ status('✖ Micro refusé — autorisez-le dans les réglages', 'bad'); }}
}};

// ── watch ──
let viewing = false, timer = null;
async function refreshSnap() {{
  try {{
    const r = await api('api/snapshot');
    const blob = await r.blob();
    if ($('snap').src) URL.revokeObjectURL($('snap').src);
    $('snap').src = URL.createObjectURL(blob);
    $('snap').style.display = 'block';
  }} catch (e) {{ status('✖ Image indisponible', 'bad'); }}
}}
$('viewBtn').onclick = () => {{
  viewing = !viewing;
  $('viewBtn').textContent = viewing ? '⏹ Arrêter de regarder' : '👁 Voir la maison';
  if (viewing) {{
    status('Reachy prévient que vous regardez');
    api('api/view/start', {{method: 'POST'}}).catch(() => {{}});
    refreshSnap(); timer = setInterval(refreshSnap, 2500);
  }} else {{
    clearInterval(timer); $('snap').style.display = 'none'; status('');
  }}
}};

// ── written message ──
$('writeBtn').onclick = () => {{
  const z = $('writeZone');
  z.style.display = z.style.display === 'block' ? 'none' : 'block';
}};
$('sayBtn').onclick = async () => {{
  const text = $('msg').value.trim();
  if (!text) return;
  status('Envoi…');
  try {{
    await api('api/say', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                           body: JSON.stringify({{text}})}});
    status('✔ Reachy le dit à voix haute !', 'good');
    $('msg').value = '';
  }} catch (e) {{ status('✖ Échec : ' + e.message, 'bad'); }}
}};
fetch('api/phrases').then(r => r.json()).then(list => {{
  $('phrases').innerHTML = list.map(t => `<button class="chip">${{t}}</button>`).join('');
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
