"""
PackBall Analytics — Gerador de Site v3.0
Interface profissional com ranking A+/A/B/C/D, todos os mercados novos,
Ranking Premium, tabela de alinhamento multi-mercado e armadilhas.
"""
import json, os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
OUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'index.html')

def load_index():
    path = os.path.join(DATA_DIR, 'index.json')
    if not os.path.exists(path): return []
    with open(path, encoding='utf-8') as f: return json.load(f)

def load_day(date_str):
    path = os.path.join(DATA_DIR, f'{date_str}.json')
    if not os.path.exists(path): return None
    with open(path, encoding='utf-8') as f: return json.load(f)

def fmt_date(date_str):
    try:
        d = datetime.strptime(date_str, '%d-%m-%Y')
        dias = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']
        return d.strftime('%d/%m'), dias[d.weekday()]
    except:
        return date_str, ''

def day_panel_html(d, day_data):
    jogos = day_data.get('jogos', [])
    n15    = sum(1 for j in jogos if j['score_15'] >= 85 and j['passou_filtro'])
    nesc   = sum(1 for j in jogos if j['score_esc85'] >= 75)
    ncart  = sum(1 for j in jogos if j['score_cards25'] >= 75)
    nprem  = sum(1 for j in jogos if j.get('best_grade') in ('A+', 'A'))
    fmt, wd = fmt_date(d)

    return f'''
<div id="day-{d}" class="day-panel">
  <div class="mkt-bar">
    <div class="mkt-tabs">
      <div class="mkt-tab active" data-mkt="visao" onclick="switchMkt('{d}','visao')">📊 Visão Geral</div>
      <div class="mkt-tab" data-mkt="ranking" onclick="switchMkt('{d}','ranking')">🏅 Ranking <span class="cnt g">{nprem}</span></div>
      <div class="mkt-tab" data-mkt="over15" onclick="switchMkt('{d}','over15')">⚽ Over 1.5 <span class="cnt b">{n15}</span></div>
      <div class="mkt-tab" data-mkt="over25" onclick="switchMkt('{d}','over25')">⚽ Over 2.5</div>
      <div class="mkt-tab" data-mkt="ht" onclick="switchMkt('{d}','ht')">⏱ HT / Under</div>
      <div class="mkt-tab" data-mkt="escanteios" onclick="switchMkt('{d}','escanteios')">🚩 Escanteios <span class="cnt g">{nesc}</span></div>
      <div class="mkt-tab" data-mkt="cartoes" onclick="switchMkt('{d}','cartoes')">🟨 Cartões <span class="cnt g">{ncart}</span></div>
      <div class="mkt-tab" data-mkt="btts" onclick="switchMkt('{d}','btts')">🎯 BTTS</div>
    </div>
  </div>
  <div class="main">
    <div id="mkt-{d}-visao"     class="mkt-panel active"></div>
    <div id="mkt-{d}-ranking"   class="mkt-panel"></div>
    <div id="mkt-{d}-over15"    class="mkt-panel"></div>
    <div id="mkt-{d}-over25"    class="mkt-panel"></div>
    <div id="mkt-{d}-ht"        class="mkt-panel"></div>
    <div id="mkt-{d}-escanteios" class="mkt-panel"></div>
    <div id="mkt-{d}-cartoes"   class="mkt-panel"></div>
    <div id="mkt-{d}-btts"      class="mkt-panel"></div>
  </div>
</div>'''

def gerar_site():
    index = load_index()
    if not index:
        print("Nenhum dado encontrado."); return

    all_data, date_tabs_html, day_panels_html = {}, [], []

    for entry in sorted(index, key=lambda x: datetime.strptime(x['date'], '%d-%m-%Y')):
        d = entry['date']
        day_data = load_day(d)
        if not day_data: continue
        fmt, wd = fmt_date(d)
        n15    = entry.get('over15', 0)
        nesc   = entry.get('esc85', 0)
        ncart  = entry.get('cart25', 0)
        nprem  = entry.get('premium', 0)

        date_tabs_html.append(f'''<div class="date-tab" data-date="{d}" onclick="switchDate('{d}')">
  <span class="dt-label">{wd} {fmt}</span>
  <span class="dt-kpis">
    <span class="dt-kpi prem">P:{nprem}</span>
    <span class="dt-kpi g">O1.5:{n15}</span>
    <span class="dt-kpi b">Esc:{nesc}</span>
    <span class="dt-kpi o">Cart:{ncart}</span>
  </span>
</div>''')
        day_panels_html.append(day_panel_html(d, day_data))
        all_data[d] = day_data

    updated = datetime.now().strftime('%d/%m/%Y %H:%M UTC')
    html = build_html(
        updated=updated,
        date_tabs_html='\\n'.join(date_tabs_html),
        day_panels_html='\\n'.join(day_panels_html),
        all_data_json=json.dumps(all_data, ensure_ascii=False),
        n_dates=len(index),
    )
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✓ docs/index.html gerado — {len(index)} datas — {updated}")

def build_html(updated, date_tabs_html, day_panels_html, all_data_json, n_dates):
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PackBall Analytics v3.0</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0d14;
  --s1:#111520;
  --s2:#161b28;
  --s3:#1c2235;
  --border:#232840;
  --accent:#f97316;
  --accent2:#fb923c;
  --blue:#3b82f6;
  --green:#22c55e;
  --orange:#f97316;
  --red:#ef4444;
  --yellow:#eab308;
  --teal:#14b8a6;
  --purple:#a855f7;
  --pink:#ec4899;
  --text:#e2e8f0;
  --muted:#64748b;
  --dim:#1e2436;
  --aplus:#ffd700;
  --a:#22c55e;
  --b:#3b82f6;
  --c:#f97316;
  --d:#ef4444;
}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;font-size:14px;min-height:100vh;line-height:1.5}}

/* HEADER */
.header{{
  background:linear-gradient(135deg,#0f1420 0%,#141928 100%);
  border-bottom:1px solid var(--border);
  padding:16px 32px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  position:sticky;top:0;z-index:100;
  box-shadow:0 4px 24px rgba(0,0,0,.4);
}}
.logo{{display:flex;align-items:center;gap:12px}}
.logo-icon{{width:40px;height:40px;background:linear-gradient(135deg,var(--accent),#c2410c);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 0 20px rgba(249,115,22,.3)}}
.logo-text .name{{font-size:18px;font-weight:700;letter-spacing:-.3px}}
.logo-text .name em{{font-style:normal;color:var(--accent)}}
.logo-text .sub{{font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.header-badges{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.badge{{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.badge.validated{{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.2)}}
.badge.version{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.badge.updated{{background:rgba(100,116,139,.1);color:var(--muted);border:1px solid var(--border);font-size:10px}}

/* DATE TABS */
.date-bar{{
  background:var(--s1);
  border-bottom:1px solid var(--border);
  display:flex;overflow-x:auto;gap:4px;padding:8px 16px;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent;
}}
.date-bar::-webkit-scrollbar{{height:3px}}
.date-bar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.date-tab{{
  padding:8px 14px;font-size:12px;font-weight:600;color:var(--muted);
  cursor:pointer;border:1px solid var(--border);border-radius:8px;
  white-space:nowrap;transition:all .15s;
  display:flex;flex-direction:column;align-items:center;gap:4px;
  background:var(--s2);min-width:90px;
}}
.date-tab:hover{{color:var(--text);border-color:var(--accent);background:var(--s3)}}
.date-tab.active{{color:var(--accent);border-color:var(--accent);background:rgba(249,115,22,.07)}}
.dt-label{{font-weight:700;font-size:13px}}
.dt-kpis{{display:flex;gap:4px;flex-wrap:wrap;justify-content:center}}
.dt-kpi{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px}}
.dt-kpi.g{{background:rgba(34,197,94,.1);color:var(--green)}}
.dt-kpi.b{{background:rgba(59,130,246,.1);color:var(--blue)}}
.dt-kpi.o{{background:rgba(249,115,22,.1);color:var(--orange)}}
.dt-kpi.prem{{background:rgba(255,215,0,.12);color:var(--aplus)}}

/* MKT BAR */
.mkt-bar{{
  background:var(--s1);
  border-bottom:1px solid var(--border);
  display:flex;justify-content:center;
  position:sticky;top:73px;z-index:90;
}}
.mkt-tabs{{display:flex;overflow-x:auto;gap:0;padding:0 8px;
  scrollbar-width:none;}}
.mkt-tabs::-webkit-scrollbar{{display:none}}
.mkt-tab{{
  padding:12px 18px;font-size:13px;font-weight:500;color:var(--muted);
  cursor:pointer;border-bottom:2px solid transparent;
  white-space:nowrap;transition:all .15s;
  display:flex;align-items:center;gap:6px;
}}
.mkt-tab:hover{{color:var(--text)}}
.mkt-tab.active{{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}}
.cnt{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:2px 6px;border-radius:5px}}
.cnt.b{{color:var(--blue);background:rgba(59,130,246,.12)}}
.cnt.g{{color:var(--green);background:rgba(34,197,94,.12)}}
.cnt.o{{color:var(--orange);background:rgba(249,115,22,.12)}}

/* MAIN */
.main{{padding:24px 28px;max-width:1500px;margin:0 auto}}
.day-info{{
  font-family:'JetBrains Mono',monospace;font-size:11px;
  color:var(--muted);text-align:right;margin-bottom:16px;
}}

/* KPI ROW */
.kpi-row{{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-bottom:24px}}
.kpi{{
  background:var(--s1);border:1px solid var(--border);border-radius:10px;
  padding:16px 20px;text-align:center;min-width:120px;
  transition:border-color .2s;
}}
.kpi:hover{{border-color:var(--accent)}}
.kpi-val{{font-size:26px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.kpi-val.g{{color:var(--green)}}.kpi-val.b{{color:var(--blue)}}
.kpi-val.o{{color:var(--orange)}}.kpi-val.y{{color:var(--yellow)}}
.kpi-val.p{{color:var(--aplus)}}.kpi-val.r{{color:var(--red)}}
.kpi-lbl{{font-size:11px;color:var(--muted);margin-top:5px;font-weight:500}}

/* SECTION */
.sec-title{{
  font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
  color:var(--muted);margin:22px 0 14px;
  display:flex;align-items:center;gap:10px;
}}
.sec-title::after{{content:'';flex:1;height:1px;background:var(--border)}}

/* TOP CARDS */
.top-grid{{display:flex;overflow-x:auto;gap:12px;margin-bottom:22px;padding-bottom:6px;align-items:stretch}}
.top-grid::-webkit-scrollbar{{height:4px}}
.top-grid::-webkit-scrollbar-thumb{{background:var(--accent);border-radius:2px}}
.top-card{{
  min-width:270px;max-width:270px;flex-shrink:0;
  background:var(--s1);border:1px solid var(--border);border-radius:12px;
  padding:16px;position:relative;overflow:hidden;
  transition:border-color .2s,transform .15s;cursor:default;
}}
.top-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.top-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.tc-aplus::before{{background:linear-gradient(90deg,var(--aplus),#fbbf24)}}
.tc-a::before{{background:linear-gradient(90deg,var(--green),var(--teal))}}
.tc-b::before{{background:linear-gradient(90deg,var(--blue),var(--purple))}}
.tc-c::before{{background:linear-gradient(90deg,var(--orange),var(--yellow))}}
.tc-d::before{{background:linear-gradient(90deg,var(--red),#dc2626)}}
.top-rank{{position:absolute;top:10px;right:12px;font-size:20px;font-weight:700;color:rgba(255,255,255,.04);font-family:'JetBrains Mono',monospace}}
.top-liga{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px}}
.top-jogo{{font-size:13px;font-weight:700;margin-bottom:2px;padding-right:24px;line-height:1.35;color:var(--text)}}
.top-hora{{font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:10px}}
.top-mkt{{font-size:11px;font-weight:600;color:var(--accent);margin-bottom:8px;text-transform:uppercase;letter-spacing:.4px}}
.top-bottom{{display:flex;align-items:center;justify-content:space-between;margin-top:8px}}
.top-score{{font-size:32px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.top-grade-block{{display:flex;flex-direction:column;align-items:flex-end;gap:4px}}
.top-note{{font-size:10px;color:var(--muted);margin-top:10px;padding-top:10px;border-top:1px solid var(--border);line-height:1.6}}
.top-odds{{font-size:10px;font-family:'JetBrains Mono',monospace;color:var(--teal);margin-top:4px}}

/* GRADE PILLS */
.grade{{display:inline-block;padding:3px 8px;border-radius:5px;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:.3px}}
.grade.Aplus{{background:rgba(255,215,0,.12);color:var(--aplus);border:1px solid rgba(255,215,0,.25)}}
.grade.A{{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.2)}}
.grade.B{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.grade.C{{background:rgba(249,115,22,.1);color:var(--orange);border:1px solid rgba(249,115,22,.2)}}
.grade.D{{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}}

/* CONF PILLS */
.conf{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace}}
.conf.MA{{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.2)}}
.conf.A{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.conf.M{{background:rgba(249,115,22,.1);color:var(--orange);border:1px solid rgba(249,115,22,.2)}}
.conf.B{{background:rgba(100,116,139,.1);color:var(--muted);border:1px solid var(--border)}}
.conf.R{{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}}

/* VIA PILLS */
.via{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700}}
.via.v1{{color:var(--yellow)}}.via.v2{{color:var(--blue)}}.via.v3{{color:var(--green)}}.via.vx{{color:var(--dim)}}

/* ELITE */
.elite{{background:rgba(249,115,22,.15);color:var(--accent);border:1px solid rgba(249,115,22,.3);font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;margin-left:5px}}

/* TABLE */
.tbl-wrap{{overflow-x:auto;border-radius:10px;border:1px solid var(--border);margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead th{{
  background:var(--s2);padding:10px 13px;text-align:left;
  font-size:10px;font-weight:600;letter-spacing:.8px;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid var(--border);white-space:nowrap;
}}
tbody tr{{border-bottom:1px solid rgba(35,40,64,.7);transition:background .1s}}
tbody tr:last-child{{border-bottom:none}}
tbody tr:hover{{background:rgba(255,255,255,.02)}}
tbody td{{padding:10px 13px;vertical-align:middle}}
.jogo-main{{font-weight:600;font-size:13px;color:var(--text)}}
.jogo-sub{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-top:1px}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:12px}}
.muted{{color:var(--muted)}}

/* BAR */
.bar-wrap{{display:flex;align-items:center;gap:7px;min-width:110px}}
.bar-num{{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:12px;min-width:38px}}
.bar-track{{flex:1;height:4px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden;min-width:40px}}
.bar-fill{{height:100%;border-radius:2px}}

/* MULTI-SCORE TABLE (ranking) */
.ms-table td.s{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600;text-align:center}}
.ms-table th{{text-align:center}}

/* FILTERS */
.fbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}}
.fbar label{{font-size:12px;color:var(--muted)}}
.chk-label{{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);cursor:pointer}}
select{{background:var(--s2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;font-family:'Inter',sans-serif;cursor:pointer}}
select:focus{{outline:1px solid var(--accent)}}

/* CALLOUTS */
.callout{{padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:13px;line-height:1.65;border-left:3px solid}}
.callout.info{{background:rgba(59,130,246,.06);border-color:var(--blue)}}
.callout.warn{{background:rgba(249,115,22,.06);border-color:var(--orange)}}
.callout.ok{{background:rgba(34,197,94,.06);border-color:var(--green)}}
.callout.gold{{background:rgba(255,215,0,.06);border-color:var(--aplus)}}
.callout strong{{font-weight:700}}
.callout.info strong{{color:var(--blue)}}
.callout.warn strong{{color:var(--orange)}}
.callout.ok strong{{color:var(--green)}}
.callout.gold strong{{color:var(--aplus)}}

/* PYRAMID */
.cpyr{{display:flex;flex-direction:column;gap:2px;font-family:'JetBrains Mono',monospace;font-size:10px}}
.cpyr-row{{display:flex;align-items:center;gap:4px}}
.cpyr-lbl{{color:var(--muted);width:38px;text-align:right}}
.cpyr-bar{{height:8px;border-radius:2px;min-width:2px}}
.cpyr-val{{min-width:28px}}

/* ALIGNMENT MATRIX */
.align-matrix{{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:6px;margin-bottom:16px}}
.align-cell{{background:var(--s2);border:1px solid var(--border);border-radius:6px;padding:8px;text-align:center}}
.align-cell .mkt{{font-size:10px;color:var(--muted);margin-bottom:4px}}
.align-cell .val{{font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace}}

/* ARMADILHA */
.trap-row td{{background:rgba(239,68,68,.03)!important}}
.trap-icon{{color:var(--red);font-size:13px}}

/* PANELS */
.day-panel{{display:none}}.day-panel.active{{display:block}}
.mkt-panel{{display:none}}.mkt-panel.active{{display:block}}

/* EMPTY */
.empty{{padding:40px;text-align:center;color:var(--muted);font-size:13px}}

/* MOBILE */
@media(max-width:640px){{
  .header{{padding:12px 16px;flex-wrap:wrap}}
  .main{{padding:14px 14px}}
  .kpi{{min-width:90px;padding:12px 14px}}
  .kpi-val{{font-size:20px}}
  .mkt-tab{{padding:10px 12px;font-size:12px}}
  .top-card{{min-width:240px}}
}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">⚽</div>
    <div class="logo-text">
      <div class="name">Pack<em>Ball</em> Analytics</div>
      <div class="sub">Análise Estatística Profissional</div>
    </div>
  </div>
  <div class="header-badges">
    <span class="badge validated">✓ Over 1.5 · 88.6%</span>
    <span class="badge version">v3.0</span>
    <span class="badge updated">🕐 {updated}</span>
  </div>
</div>

<div class="date-bar" id="date-bar">
{date_tabs_html}
</div>

{day_panels_html}

<script>
const ALL_DATA = {all_data_json};

// ── Helpers ──────────────────────────────────────────────────────
function col(s){{
  if(s>=88)return'var(--aplus)';
  if(s>=80)return'var(--green)';
  if(s>=70)return'var(--blue)';
  if(s>=60)return'var(--orange)';
  return'var(--red)';
}}
function gradeClass(g){{return g==='A+'?'Aplus':g;}}
function gradeHtml(g){{
  return`<span class="grade ${{gradeClass(g)}}">${{g}}</span>`;
}}
function confHtml(s){{
  if(s>=88)return'<span class="conf MA">M.ALTA</span>';
  if(s>=80)return'<span class="conf A">ALTA</span>';
  if(s>=70)return'<span class="conf M">MÉDIA</span>';
  if(s>=60)return'<span class="conf B">BAIXA</span>';
  return'<span class="conf R">RISCO</span>';
}}
function bar(s,w){{
  w=w||90;const c=col(s);
  return`<div class="bar-wrap"><span class="bar-num" style="color:${{c}}">${{s}}%</span><div class="bar-track" style="width:${{w}}px"><div class="bar-fill" style="width:${{Math.min(s,100)}}%;background:${{c}}"></div></div></div>`;
}}
function via(v){{
  if(v==='Via 1')return'<span class="via v1">VIA1</span>';
  if(v==='Via 2')return'<span class="via v2">VIA2</span>';
  if(v==='Via 3')return'<span class="via v3">VIA3</span>';
  return'<span class="via vx">—</span>';
}}
function pct(v){{return v!=null?v+'%':'—';}}
function pyramid(d){{
  const rows=[['6.5',d.over65_c,'var(--green)'],['7.5',d.over75_c,'var(--teal)'],['8.5',d.over85_c,'var(--blue)'],['9.5',d.over95_c,'var(--orange)'],['10.5',d.over105_c,'var(--red)']];
  return'<div class="cpyr">'+rows.map(([l,v,c])=>{{const w=v?Math.round(v*.38):0;return`<div class="cpyr-row"><span class="cpyr-lbl">${{l}}</span><div class="cpyr-bar" style="width:${{w}}px;background:${{c}}"></div><span class="cpyr-val">${{v!=null?v+'%':'—'}}</span></div>`;}}).join('')+'</div>';
}}
function jogoCell(d){{
  return`<td><div class="jogo-main">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div><div class="jogo-sub">${{d.liga}}</div></td>`;
}}
function oddCell(val){{
  if(!val)return'<td class="mono muted">—</td>';
  return`<td class="mono" style="color:var(--teal)">${{val}}</td>`;
}}
function getJogos(date){{return(ALL_DATA[date]||{{}}).jogos||[];}}

// armadilha = score 65+ em 1 mercado mas baixo nos outros
function isArmadilha(d){{
  const scores=[d.score_15,d.score_25,d.score_btts,d.score_05ht];
  const max=Math.max(...scores);
  const avg=scores.reduce((a,b)=>a+b,0)/scores.length;
  return max>=70&&avg<55;
}}

// ── Render functions ─────────────────────────────────────────────
function renderVisao(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-visao');
  const a15=jogos.filter(d=>d.score_15>=85&&d.passou_filtro).length;
  const aesc=jogos.filter(d=>d.score_esc85>=75).length;
  const acart=jogos.filter(d=>d.score_cards25>=75).length;
  const aprem=jogos.filter(d=>d.best_grade==='A+'||d.best_grade==='A').length;
  const a05ht=jogos.filter(d=>d.score_05ht>=75).length;

  // KPIs
  const kpi=`<div class="kpi-row">
    <div class="kpi"><div class="kpi-val b">${{jogos.length}}</div><div class="kpi-lbl">Jogos</div></div>
    <div class="kpi"><div class="kpi-val p">${{aprem}}</div><div class="kpi-lbl">Premium A+/A</div></div>
    <div class="kpi"><div class="kpi-val g">${{a15}}</div><div class="kpi-lbl">Over 1.5 ≥85%</div></div>
    <div class="kpi"><div class="kpi-val o">${{a05ht}}</div><div class="kpi-lbl">Over 0.5 HT ≥75%</div></div>
    <div class="kpi"><div class="kpi-val b">${{aesc}}</div><div class="kpi-lbl">Esc 8.5 ≥75%</div></div>
    <div class="kpi"><div class="kpi-val g">${{acart}}</div><div class="kpi-lbl">Cart 2.5 ≥75%</div></div>
  </div>`;

  // Top 5
  const top=[...jogos].sort((a,b)=>b.best_score-a.best_score).slice(0,5);
  const cls=['tc-aplus','tc-a','tc-b','tc-c','tc-d'];
  const t5=top.map((d,i)=>{{
    const c=col(d.best_score);
    const oj=d['odd_justa_'+d.best_mkt.toLowerCase().replace(/[ .]/g,'_')]||null;
    return`<div class="top-card ${{cls[i]}}">
      <div class="top-rank">#${{i+1}}</div>
      <div class="top-liga">${{d.liga}}</div>
      <div class="top-jogo">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div>
      <div class="top-hora">🕐 ${{d.hora}}</div>
      <div class="top-mkt">${{d.best_mkt}}</div>
      <div class="top-bottom">
        <div class="top-score" style="color:${{c}}">${{d.best_score}}%</div>
        <div class="top-grade-block">${{gradeHtml(d.best_grade)}}<span style="font-size:10px;color:var(--muted)">${{d.best_risk}}</span></div>
      </div>
      <div class="top-note">${{d.justif_15||'—'}}</div>
      ${{oj?`<div class="top-odds">Odd justa: ~${{oj}}</div>`:''}}
    </div>`;
  }}).join('');

  // Resumo tabela
  const rows=[...jogos].sort((a,b)=>b.best_score-a.best_score).map(d=>{{
    const trap=isArmadilha(d)?'<span class="trap-icon" title="Possível armadilha de mercado">⚠</span>':'';
    return`<tr class="${{isArmadilha(d)?'trap-row':''}}">
      ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
      <td>${{gradeHtml(d.best_grade)}}</td>
      <td class="mono" style="color:var(--muted);font-size:11px">${{d.best_mkt}}</td>
      <td>${{bar(d.score_15)}}</td>
      <td>${{bar(d.score_esc85)}}</td>
      <td>${{bar(d.score_cards25)}}</td>
      <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
      <td>${{trap}}</td>
    </tr>`;
  }}).join('');

  el.innerHTML=`
    <div class="day-info">${{jogos.length}} jogos analisados · ${{date}}</div>
    ${{kpi}}
    <div class="sec-title">🏆 Top 5 Palpites do Dia</div>
    <div class="top-grid">${{t5}}</div>
    <div class="sec-title">📋 Resumo Geral</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Jogo</th><th>Hora</th><th>Grade</th><th>Melhor Mercado</th><th>Over 1.5</th><th>Esc 8.5</th><th>Cart 2.5</th><th>xG</th><th></th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>
    <div class="callout warn" style="margin-top:12px">
      <strong>⚠ Armadilhas de Mercado</strong> · Jogos marcados com ⚠ apresentam alto score em um mercado mas baixa consistência geral. Evite entradas sem análise extra.
    </div>`;
}}

function renderRanking(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-ranking');
  const sorted=[...jogos].sort((a,b)=>b.best_score-a.best_score);
  const premium=sorted.filter(d=>d.best_grade==='A+'||d.best_grade==='A');
  const boas=sorted.filter(d=>d.best_grade==='B');
  const perigosas=sorted.filter(d=>d.best_grade==='C'||d.best_grade==='D');

  function section(titulo,items,calloutClass,calloutText){{
    if(!items.length)return'';
    const rows=items.map((d,i)=>`<tr>
      <td class="mono muted">${{i+1}}</td>
      ${{jogoCell(d)}}
      <td class="mono muted">${{d.hora}}</td>
      <td>${{gradeHtml(d.best_grade)}}</td>
      <td class="mono" style="color:var(--muted);font-size:11px">${{d.best_mkt}}</td>
      <td>${{bar(d.best_score)}}</td>
      <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
      <td class="mono" style="color:var(--teal)">${{d['odd_justa_15']?'~'+d['odd_justa_15']:'—'}}</td>
      <td class="s mono" style="color:var(--green)">${{d.score_15}}</td>
      <td class="s mono" style="color:var(--blue)">${{d.score_25}}</td>
      <td class="s mono" style="color:var(--orange)">${{d.score_btts}}</td>
      <td class="s mono" style="color:var(--yellow)">${{d.score_05ht}}</td>
      <td>${{d.best_risk}}</td>
      <td style="font-size:11px;max-width:200px;color:var(--muted)">${{d.justif_15||'—'}}</td>
    </tr>`).join('');
    return`
      <div class="callout ${{calloutClass}}">${{calloutText}}</div>
      <div class="tbl-wrap"><table class="ms-table">
        <thead><tr>
          <th>#</th><th>Jogo</th><th>Hora</th><th>Grade</th><th>Mercado</th>
          <th>Score</th><th>xG</th><th>Odd Justa</th>
          <th>O1.5</th><th>O2.5</th><th>BTTS</th><th>0.5HT</th>
          <th>Risco</th><th>Justificativa</th>
        </tr></thead>
        <tbody>${{rows}}</tbody>
      </table></div>`;
  }}

  el.innerHTML=`
    <div class="sec-title">🥇 Entradas Premium (A+ / A)</div>
    ${{section('Premium',premium,'gold','<strong>⭐ Entradas Premium</strong> · Score ≥80% com consistência estatística alta. Maior valor esperado do dia.')}}
    ${{premium.length===0?'<div class="empty">Nenhuma entrada premium hoje.</div>':''}}
    <div class="sec-title">📊 Boas Entradas (B)</div>
    ${{section('Boas',boas,'ok','<strong>✓ Boas Entradas</strong> · Score 70–79%. Risco médio, fundamentação estatística razoável.')}}
    ${{boas.length===0?'<div class="empty">Nenhuma entrada boa hoje.</div>':''}}
    <div class="sec-title">⚠ Jogos Perigosos (C / D)</div>
    ${{section('Perigosos',perigosas,'warn','<strong>⚠ Jogos Perigosos</strong> · Score abaixo de 70%. Alta variância, evitar ou observar.')}}
    ${{perigosas.length===0?'<div class="empty">Nenhum jogo perigoso identificado.</div>':''}}
  `;
}}

function renderOver15(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over15');
  const min=0;
  let rows=[...jogos].filter(d=>d.score_15>=min&&d.passou_filtro).sort((a,b)=>b.score_15-a.score_15);
  const html=rows.map((d,i)=>`<tr>
    <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
    <td class="mono muted">${{d.hora}}</td>
    <td>${{bar(d.score_15)}}</td>
    <td>${{gradeHtml(d.grade_15)}}</td>
    <td class="mono">${{pct(d.over15_g)}}</td>
    <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
    <td class="mono" style="color:var(--purple)">${{d.poisson_o15?d.poisson_o15+'%':'—'}}</td>
    <td class="mono">${{d.ppg_min}}</td>
    <td>${{via(d.via)}}</td>
    ${{oddCell(d.odd_justa_15)}}
    <td>${{confHtml(d.score_15)}}</td>
    <td style="font-size:11px;color:var(--muted);max-width:180px">${{d.justif_15||'—'}}</td>
  </tr>`).join('');
  el.innerHTML=`
    <div class="callout info"><strong>Over 1.5 Gols — Validado 88.6%</strong> · Threshold ≥85% + Filtro 3 Vias ativo. Inclui probabilidade Poisson via xG.</div>
    <div class="fbar">
      <label>Score mínimo:</label>
      <select onchange="filterOver15('${{date}}',this.value)">
        <option value="0">Aprovados no filtro 3 vias</option>
        <option value="65">≥65%</option><option value="75">≥75%</option><option value="85">≥85%</option>
      </select>
    </div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Grade</th><th>Over 1.5%</th><th>xG Total</th><th>Poisson</th><th>PPG min</th><th>Via</th><th>Odd Justa</th><th>Conf.</th><th>Justificativa</th></tr></thead>
      <tbody id="tb15-${{date}}">${{html||'<tr><td colspan="13" class="empty">Nenhum jogo passou o Filtro 3 Vias.</td></tr>'}}</tbody>
    </table></div>`;
}}
function filterOver15(date,min){{
  const jogos=getJogos(date);
  const m=+min;
  let rows;
  if(m===0)rows=[...jogos].filter(d=>d.passou_filtro).sort((a,b)=>b.score_15-a.score_15);
  else rows=[...jogos].filter(d=>d.score_15>=m).sort((a,b)=>b.score_15-a.score_15);
  document.getElementById('tb15-'+date).innerHTML=rows.map((d,i)=>`<tr>
    <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
    <td class="mono muted">${{d.hora}}</td>
    <td>${{bar(d.score_15)}}</td>
    <td>${{gradeHtml(d.grade_15)}}</td>
    <td class="mono">${{pct(d.over15_g)}}</td>
    <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
    <td class="mono" style="color:var(--purple)">${{d.poisson_o15?d.poisson_o15+'%':'—'}}</td>
    <td class="mono">${{d.ppg_min}}</td>
    <td>${{via(d.via)}}</td>
    ${{oddCell(d.odd_justa_15)}}
    <td>${{confHtml(d.score_15)}}</td>
    <td style="font-size:11px;color:var(--muted);max-width:180px">${{d.justif_15||'—'}}</td>
  </tr>`).join('')||'<tr><td colspan="13" class="empty">Sem jogos.</td></tr>';
}}

function renderOver25(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over25');
  const rows=[...jogos].sort((a,b)=>b.score_25-a.score_25);
  el.innerHTML=`
    <div class="callout warn"><strong>Over 2.5 Gols</strong> · Mercado em análise. Inclui probabilidade Poisson. Use como complemento ao Over 1.5.</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Grade</th><th>Over 2.5%</th><th>xG Total</th><th>Poisson O2.5</th><th>Odd Justa</th><th>Conf.</th></tr></thead>
      <tbody>${{rows.map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_25)}}</td>
        <td>${{gradeHtml(d.grade_25)}}</td>
        <td class="mono">${{pct(d.over25_g)}}</td>
        <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
        <td class="mono" style="color:var(--purple)">${{d.poisson_o25?d.poisson_o25+'%':'—'}}</td>
        ${{oddCell(d.odd_justa_25)}}
        <td>${{confHtml(d.score_25)}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>`;
}}

function renderHT(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-ht');
  const r05=[...jogos].sort((a,b)=>b.score_05ht-a.score_05ht);
  const ru45=[...jogos].sort((a,b)=>b.score_u45-a.score_u45);
  el.innerHTML=`
    <div class="sec-title">⏱ Over 0.5 HT — Gol no Primeiro Tempo</div>
    <div class="callout info"><strong>Over 0.5 HT</strong> · Pelo menos 1 gol no 1º tempo. Baseado no histórico HT e pressão ofensiva.</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Grade</th><th>O0.5HT%</th><th>O1.5HT%</th><th>xG</th><th>Odd Justa</th><th>Conf.</th></tr></thead>
      <tbody>${{r05.map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_05ht)}}</td>
        <td>${{gradeHtml(d.grade_05ht)}}</td>
        <td class="mono">${{pct(d.over05_ht)}}</td>
        <td class="mono">${{pct(d.over15_ht)}}</td>
        <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
        ${{oddCell(d.odd_justa_05ht)}}
        <td>${{confHtml(d.score_05ht)}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>
    <div class="sec-title" style="margin-top:24px">🔽 Under 4.5 Gols</div>
    <div class="callout ok"><strong>Under 4.5 Gols</strong> · Alta taxa base (~95%+ histórico). Usar como mercado ancorável em combos.</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Grade</th><th>Poisson U4.5</th><th>xG</th><th>Conf.</th></tr></thead>
      <tbody>${{ru45.map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_u45)}}</td>
        <td>${{gradeHtml(d.grade_u45)}}</td>
        <td class="mono" style="color:var(--purple)">${{d.poisson_u45?d.poisson_u45+'%':'—'}}</td>
        <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
        <td>${{confHtml(d.score_u45)}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>`;
}}

function renderEsc(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-escanteios');
  const r75=[...jogos].sort((a,b)=>b.score_esc75-a.score_esc75);
  const r85=[...jogos].sort((a,b)=>b.score_esc85-a.score_esc85);
  el.innerHTML=`
    <div class="callout ok"><strong>Escanteios Over 7.5 / 8.5</strong> · Threshold provisório ≥75%. Baseado em média de cantos, shots e over%.</div>
    <div class="sec-title">🚩 Over 7.5 Escanteios</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score 7.5</th><th>Grade</th><th>Média Cant.</th><th>6.5→7.5→8.5→9.5→10.5</th><th>Conf.</th></tr></thead>
      <tbody>${{r75.slice(0,15).map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_esc75)}}</td>
        <td>${{gradeHtml(d.grade_esc75)}}</td>
        <td class="mono" style="color:var(--teal)">${{d.avg_corners||'—'}}</td>
        <td>${{pyramid(d)}}</td>
        <td>${{confHtml(d.score_esc75)}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>
    <div class="sec-title">🚩 Over 8.5 Escanteios</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score 8.5</th><th>Grade</th><th>Média Cant.</th><th>Over 7.5→8.5→9.5</th><th>Odd Justa</th><th>Conf.</th></tr></thead>
      <tbody>${{r85.slice(0,15).map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_esc85)}}</td>
        <td>${{gradeHtml(d.grade_esc85)}}</td>
        <td class="mono" style="color:var(--teal)">${{d.avg_corners||'—'}}</td>
        <td>${{pyramid(d)}}</td>
        ${{oddCell(d.odd_justa_esc85)}}
        <td>${{confHtml(d.score_esc85)}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>`;
}}

function renderCart(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-cartoes');
  const rows=[...jogos].sort((a,b)=>b.score_cards25-a.score_cards25);
  el.innerHTML=`
    <div class="callout ok"><strong>Cartões Over 2.5 / 3.5</strong> · Alta consistência observada. Filtro ≥75% recomendado.</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score 2.5</th><th>Grade</th><th>Score 3.5</th><th>Média Cart.</th><th>O2.5%</th><th>O3.5%</th><th>Odd Justa</th><th>Justificativa</th></tr></thead>
      <tbody>${{rows.map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_cards25)}}</td>
        <td>${{gradeHtml(d.grade_cart25)}}</td>
        <td>${{bar(d.score_cards35,70)}}</td>
        <td class="mono" style="color:var(--yellow)">${{d.avg_cards||'—'}}</td>
        <td class="mono">${{pct(d.over25_cards)}}</td>
        <td class="mono">${{pct(d.over35_cards)}}</td>
        ${{oddCell(d.odd_justa_cart25)}}
        <td style="font-size:11px;color:var(--muted)">${{d.justif_cards||'—'}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>`;
}}

function renderBtts(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-btts');
  const rows=[...jogos].sort((a,b)=>b.score_btts-a.score_btts);
  el.innerHTML=`
    <div class="callout warn"><strong>BTTS — Ambos Marcam</strong> · Acerto histórico 61.5%. Use como mercado complementar, não principal.</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Grade</th><th>BTTS Casa</th><th>BTTS Fora</th><th>BTTS Médio</th><th>xG</th><th>Odd Justa</th><th>Conf.</th></tr></thead>
      <tbody>${{rows.map((d,i)=>`<tr>
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(d.score_btts)}}</td>
        <td>${{gradeHtml(d.grade_btts)}}</td>
        <td class="mono">${{pct(d.btts_h)}}</td>
        <td class="mono">${{pct(d.btts_a)}}</td>
        <td class="mono">${{d.btts_cf!=null?d.btts_cf+'%':'—'}}</td>
        <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
        ${{oddCell(d.odd_justa_btts)}}
        <td>${{confHtml(d.score_btts)}}</td>
      </tr>`).join('')}}</tbody>
    </table></div>`;
}}

// ── Navigation ───────────────────────────────────────────────────
let activeDate=null;
let activeMkt={{}};

function switchDate(date){{
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-tab').forEach(t=>t.classList.remove('active'));
  const panel=document.getElementById('day-'+date);
  const tab=document.querySelector(`[data-date="${{date}}"]`);
  if(panel)panel.classList.add('active');
  if(tab){{tab.classList.add('active');tab.scrollIntoView({{behavior:'smooth',block:'nearest',inline:'center'}});}}
  activeDate=date;
  if(!activeMkt[date])activeMkt[date]='visao';
  switchMkt(date,activeMkt[date]);
}}

function switchMkt(date,mkt){{
  activeMkt[date]=mkt;
  const panel=document.getElementById('day-'+date);
  if(!panel)return;
  panel.querySelectorAll('.mkt-panel').forEach(p=>p.classList.remove('active'));
  panel.querySelectorAll('.mkt-tab').forEach(t=>t.classList.remove('active'));
  const mp=panel.querySelector('#mkt-'+date+'-'+mkt);
  const mt=panel.querySelector(`[data-mkt="${{mkt}}"]`);
  if(mp)mp.classList.add('active');
  if(mt)mt.classList.add('active');
  renderMkt(date,mkt);
}}

function renderMkt(date,mkt){{
  const jogos=getJogos(date);
  if(mkt==='visao')       renderVisao(date,jogos);
  else if(mkt==='ranking')    renderRanking(date,jogos);
  else if(mkt==='over15')     renderOver15(date,jogos);
  else if(mkt==='over25')     renderOver25(date,jogos);
  else if(mkt==='ht')         renderHT(date,jogos);
  else if(mkt==='escanteios') renderEsc(date,jogos);
  else if(mkt==='cartoes')    renderCart(date,jogos);
  else if(mkt==='btts')       renderBtts(date,jogos);
}}

// Init
const dates=Object.keys(ALL_DATA);
if(dates.length) switchDate(dates[0]);
</script>
</body>
</html>'''

if __name__ == '__main__':
    gerar_site()
