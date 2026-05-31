"""
WinMetrics — Gerador de Site v3.1
- Resultados integrados: linhas verde/vermelho/amarelo em cada tabela
- Placar nos cards Top 5
- KPI de assertividade no header
- Aba Histórico com gráfico de evolução por mercado
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

def calcular_acertos_globais(all_data):
    """Calcula taxa de acerto acumulada para todos os dias confirmados."""
    mercados = ['Over 1.5','Over 2.5','BTTS','Over 0.5 HT','Under 4.5','Under 3.5',
                'Esc 7.5','Esc 8.5','Cart 2.5','Cart 3.5']
    totais = {m: {'palpites':0,'acertos':0,'erros':0} for m in mercados}
    dias_confirmados = 0

    for date_str, day_data in all_data.items():
        if not day_data.get('resultado_confirmado'):
            continue
        dias_confirmados += 1
        stats = day_data.get('resultado_stats', {})
        for m in mercados:
            s = stats.get(m, {})
            totais[m]['palpites'] += s.get('palpites', 0)
            totais[m]['acertos'] += s.get('acertos', 0)
            totais[m]['erros'] += s.get('erros', 0)

    for m in totais:
        v = totais[m]['acertos'] + totais[m]['erros']
        totais[m]['taxa'] = round(totais[m]['acertos']/v*100,1) if v > 0 else None

    total_p = sum(v['palpites'] for v in totais.values())
    total_a = sum(v['acertos'] for v in totais.values())
    total_e = sum(v['erros'] for v in totais.values())
    taxa_geral = round(total_a/(total_a+total_e)*100,1) if (total_a+total_e) > 0 else None

    return {
        'por_mercado': totais,
        'total_palpites': total_p,
        'total_acertos': total_a,
        'total_erros': total_e,
        'taxa_geral': taxa_geral,
        'dias_confirmados': dias_confirmados,
    }

def day_panel_html(d, day_data):
    jogos  = day_data.get('jogos', [])
    n15    = sum(1 for j in jogos if j['score_15'] >= 85 and j['passou_filtro'])
    nesc   = sum(1 for j in jogos if j['score_esc85'] >= 75)
    ncart  = sum(1 for j in jogos if j['score_cards25'] >= 75)
    nprem  = sum(1 for j in jogos if j.get('best_grade') in ('A+', 'A'))
    fmt, wd = fmt_date(d)
    confirmado = day_data.get('resultado_confirmado', False)
    res_badge = '✅' if confirmado else '⏳'

    return f'''
<div id="day-{d}" class="day-panel">
  <div class="mkt-bar">
    <div class="mkt-tabs">
      <div class="mkt-tab active" data-mkt="visao"      onclick="switchMkt('{d}','visao')">📊 Visão Geral</div>
      <div class="mkt-tab"       data-mkt="ranking"     onclick="switchMkt('{d}','ranking')">🏅 Ranking <span class="cnt g">{nprem}</span></div>
      <div class="mkt-tab"       data-mkt="over15"      onclick="switchMkt('{d}','over15')">⚽ Over 1.5 <span class="cnt b">{n15}</span></div>
      <div class="mkt-tab"       data-mkt="over25"      onclick="switchMkt('{d}','over25')">🔽 Under 3.5</div>
      <div class="mkt-tab"       data-mkt="escanteios"  onclick="switchMkt('{d}','escanteios')">🚩 Escanteios <span class="cnt g">{nesc}</span></div>
      <div class="mkt-tab"       data-mkt="cartoes"     onclick="switchMkt('{d}','cartoes')">🟨 Cartões <span class="cnt g">{ncart}</span></div>
      <div class="mkt-tab"       data-mkt="historico_dia" onclick="switchMkt('{d}','historico_dia')">{res_badge} Resultados</div>
    </div>
  </div>
  <div class="main">
    <div id="mkt-{d}-visao"        class="mkt-panel active"></div>
    <div id="mkt-{d}-ranking"      class="mkt-panel"></div>
    <div id="mkt-{d}-over15"       class="mkt-panel"></div>
    <div id="mkt-{d}-over25"       class="mkt-panel"></div>
    <div id="mkt-{d}-escanteios"   class="mkt-panel"></div>
    <div id="mkt-{d}-cartoes"      class="mkt-panel"></div>
    <div id="mkt-{d}-historico_dia" class="mkt-panel"></div>
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
        fmt, wd  = fmt_date(d)
        n15      = entry.get('over15', 0)
        nesc     = entry.get('esc85', 0)
        ncart    = entry.get('cart25', 0)
        nprem    = entry.get('premium', 0)
        conf     = day_data.get('resultado_confirmado', False)

        date_tabs_html.append(f'''<div class="date-tab" data-date="{d}" onclick="switchDate('{d}')">
  <span class="dt-label">{wd} {fmt}</span>
</div>''')
        day_panels_html.append(day_panel_html(d, day_data))
        all_data[d] = day_data

    # Calcular acertos globais para o header
    globais = calcular_acertos_globais(all_data)
    updated = datetime.now().strftime('%d/%m/%Y %H:%M UTC')

    html = build_html(
        updated=updated,
        date_tabs_html='\n'.join(date_tabs_html),
        day_panels_html='\n'.join(day_panels_html),
        all_data_json=json.dumps(all_data, ensure_ascii=False),
        globais_json=json.dumps(globais, ensure_ascii=False),
        n_dates=len(index),
    )
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✓ docs/index.html gerado — {len(index)} datas — {updated}")

def build_html(updated, date_tabs_html, day_panels_html, all_data_json, globais_json, n_dates):
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WinMetrics - AI Sports Analytics</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0d14;--s1:#111520;--s2:#161b28;--s3:#1c2235;--border:#232840;
  --accent:#f97316;--accent2:#fb923c;--blue:#3b82f6;--green:#22c55e;
  --orange:#f97316;--red:#ef4444;--yellow:#eab308;--teal:#14b8a6;
  --purple:#a855f7;--pink:#ec4899;--text:#e2e8f0;--muted:#64748b;
  --dim:#1e2436;--aplus:#ffd700;
}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;font-size:14px;min-height:100vh;line-height:1.5}}

/* HEADER */
.header{{
  background:linear-gradient(135deg,#0f1420,#141928);
  border-bottom:1px solid var(--border);padding:12px 28px;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  position:sticky;top:0;z-index:100;box-shadow:0 4px 24px rgba(0,0,0,.4);
  flex-wrap:wrap;
}}
.logo{{display:flex;align-items:center;gap:10px}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),#c2410c);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 0 16px rgba(249,115,22,.3)}}
.logo-text .name{{font-size:17px;font-weight:700;letter-spacing:-.3px}}
.logo-text .name em{{font-style:normal;color:var(--accent)}}
.logo-text .sub{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
/* Header KPIs globais */
.hkpi-row{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.hkpi{{display:flex;flex-direction:column;align-items:center;padding:5px 12px;border-radius:7px;background:var(--s2);border:1px solid var(--border);min-width:70px}}
.hkpi-val{{font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.hkpi-lbl{{font-size:9px;color:var(--muted);margin-top:2px;text-transform:uppercase;letter-spacing:.5px}}
.header-right{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.badge{{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:600;font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.badge.validated{{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.2)}}
.badge.version{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.badge.updated{{background:rgba(100,116,139,.1);color:var(--muted);border:1px solid var(--border);font-size:9px}}

/* DATE TABS */
.date-bar{{background:var(--s1);border-bottom:1px solid var(--border);display:flex;overflow-x:auto;gap:4px;padding:6px 12px;scrollbar-width:thin;scrollbar-color:var(--border) transparent}}
.date-bar::-webkit-scrollbar{{height:3px}}
.date-bar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.date-tab{{padding:7px 12px;font-size:12px;font-weight:600;color:var(--muted);cursor:pointer;border:1px solid var(--border);border-radius:7px;white-space:nowrap;transition:all .15s;display:flex;flex-direction:column;align-items:center;gap:3px;background:var(--s2);min-width:85px}}
.date-tab:hover{{color:var(--text);border-color:var(--accent)}}
.date-tab.active{{color:var(--accent);border-color:var(--accent);background:rgba(249,115,22,.07)}}
.dt-label{{font-weight:700;font-size:12px}}
.dt-kpis{{display:flex;gap:3px;flex-wrap:wrap;justify-content:center}}
.dt-kpi{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px}}
.dt-kpi.g{{background:rgba(34,197,94,.1);color:var(--green)}}
.dt-kpi.b{{background:rgba(59,130,246,.1);color:var(--blue)}}
.dt-kpi.o{{background:rgba(249,115,22,.1);color:var(--orange)}}
.dt-kpi.prem{{background:rgba(255,215,0,.12);color:var(--aplus)}}

/* MKT BAR */
.mkt-bar{{background:var(--s1);border-bottom:1px solid var(--border);display:flex;justify-content:center;position:sticky;top:61px;z-index:90;flex-direction:column}}
.mkt-tabs{{display:flex;overflow-x:auto;gap:0;padding:0 6px;scrollbar-width:none}}
.mkt-tabs::-webkit-scrollbar{{display:none}}
.mkt-tab{{padding:11px 16px;font-size:13px;font-weight:500;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;transition:all .15s;display:flex;align-items:center;gap:5px}}
.mkt-tab:hover{{color:var(--text)}}
.mkt-tab.active{{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}}
.cnt{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:2px 5px;border-radius:4px}}
.cnt.b{{color:var(--blue);background:rgba(59,130,246,.12)}}
.cnt.g{{color:var(--green);background:rgba(34,197,94,.12)}}

/* MAIN */
.main{{padding:20px 24px;max-width:1500px;margin:0 auto}}
.day-info{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);text-align:right;margin-bottom:14px}}

/* KPI ROW */
.kpi-row{{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:20px}}
.kpi{{background:var(--s1);border:1px solid var(--border);border-radius:9px;padding:14px 18px;text-align:center;min-width:110px;transition:border-color .2s}}
.kpi:hover{{border-color:var(--accent)}}
.kpi-val{{font-size:24px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.kpi-val.g{{color:var(--green)}}.kpi-val.b{{color:var(--blue)}}
.kpi-val.o{{color:var(--orange)}}.kpi-val.y{{color:var(--yellow)}}
.kpi-val.p{{color:var(--aplus)}}.kpi-val.r{{color:var(--red)}}
.kpi-lbl{{font-size:11px;color:var(--muted);margin-top:4px;font-weight:500}}

/* SECTION */
.sec-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);margin:20px 0 12px;display:flex;align-items:center;gap:8px}}
.sec-title::after{{content:'';flex:1;height:1px;background:var(--border)}}

/* TOP CARDS */
.top-grid{{display:flex;overflow-x:auto;gap:10px;margin-bottom:20px;padding-bottom:5px;align-items:stretch}}
.top-grid::-webkit-scrollbar{{height:3px}}
.top-grid::-webkit-scrollbar-thumb{{background:var(--accent);border-radius:2px}}
.top-card{{min-width:255px;max-width:255px;flex-shrink:0;background:var(--s1);border:1px solid var(--border);border-radius:11px;padding:14px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s}}
.top-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.top-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.tc-aplus::before{{background:linear-gradient(90deg,var(--aplus),#fbbf24)}}
.tc-a::before{{background:linear-gradient(90deg,var(--green),var(--teal))}}
.tc-b::before{{background:linear-gradient(90deg,var(--blue),var(--purple))}}
.tc-c::before{{background:linear-gradient(90deg,var(--orange),var(--yellow))}}
.tc-d::before{{background:linear-gradient(90deg,var(--red),#dc2626)}}
/* resultado overlay no card */
.tc-hit::after{{content:'';position:absolute;inset:0;background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.25);border-radius:11px;pointer-events:none}}
.tc-miss::after{{content:'';position:absolute;inset:0;background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.25);border-radius:11px;pointer-events:none}}
.top-rank{{position:absolute;top:10px;right:12px;font-size:18px;font-weight:700;color:rgba(255,255,255,.04);font-family:'JetBrains Mono',monospace}}
.top-liga{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.7px;margin-bottom:3px}}
.top-jogo{{font-size:13px;font-weight:700;margin-bottom:2px;padding-right:22px;line-height:1.3}}
.top-hora{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:8px}}
.top-mkt{{font-size:10px;font-weight:700;color:var(--accent);margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}}
.top-bottom{{display:flex;align-items:center;justify-content:space-between;margin-top:6px}}
.top-score{{font-size:30px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.top-grade-block{{display:flex;flex-direction:column;align-items:flex-end;gap:3px}}
.top-note{{font-size:10px;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px solid var(--border);line-height:1.55}}
/* placar no card */
.top-placar{{display:flex;align-items:center;gap:6px;margin-top:7px;padding:6px 10px;border-radius:6px;font-family:'JetBrains Mono',monospace}}
.top-placar.hit{{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2)}}
.top-placar.miss{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2)}}
.top-placar.pending{{background:rgba(234,179,8,.08);border:1px solid rgba(234,179,8,.15)}}
.top-placar .ft{{font-size:15px;font-weight:700}}
.top-placar .ht{{font-size:10px;color:var(--muted)}}
.top-placar .icon{{font-size:13px}}

/* GRADE PILLS */
.grade{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace}}
.grade.Aplus{{background:rgba(255,215,0,.12);color:var(--aplus);border:1px solid rgba(255,215,0,.25)}}
.grade.A{{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.2)}}
.grade.B{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.grade.C{{background:rgba(249,115,22,.1);color:var(--orange);border:1px solid rgba(249,115,22,.2)}}
.grade.D{{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}}

/* RESULT ROW COLORS */
.row-hit{{background:rgba(34,197,94,.05)!important;border-left:3px solid var(--green)}}
.row-miss{{background:rgba(239,68,68,.05)!important;border-left:3px solid var(--red)}}
.row-pending{{border-left:3px solid rgba(234,179,8,.4)}}
.res-badge{{display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.res-badge.hit{{background:rgba(34,197,94,.12);color:var(--green);border:1px solid rgba(34,197,94,.25)}}
.res-badge.miss{{background:rgba(239,68,68,.12);color:var(--red);border:1px solid rgba(239,68,68,.25)}}
.res-badge.pending{{background:rgba(234,179,8,.08);color:var(--yellow);border:1px solid rgba(234,179,8,.2)}}
.placar-cell{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.placar-ht{{font-size:10px;color:var(--muted)}}

/* CONF/VIA PILLS */
.conf{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace}}
.conf.MA{{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.2)}}
.conf.A{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.conf.M{{background:rgba(249,115,22,.1);color:var(--orange);border:1px solid rgba(249,115,22,.2)}}
.conf.B{{background:rgba(100,116,139,.1);color:var(--muted);border:1px solid var(--border)}}
.conf.R{{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}}
.via{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700}}
.via.v1{{color:var(--yellow)}}.via.v2{{color:var(--blue)}}.via.v3{{color:var(--green)}}.via.vx{{color:var(--dim)}}
.elite{{background:rgba(249,115,22,.15);color:var(--accent);border:1px solid rgba(249,115,22,.3);font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;margin-left:4px}}

/* TABLE */
.tbl-wrap{{overflow-x:auto;border-radius:9px;border:1px solid var(--border);margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead th{{background:var(--s2);padding:9px 12px;text-align:left;font-size:10px;font-weight:600;letter-spacing:.7px;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);white-space:nowrap}}
tbody tr{{border-bottom:1px solid rgba(35,40,64,.7);transition:background .1s}}
tbody tr:last-child{{border-bottom:none}}
tbody tr:hover{{background:rgba(255,255,255,.018)}}
tbody td{{padding:9px 12px;vertical-align:middle}}
.jogo-main{{font-weight:600;font-size:13px}}
.jogo-sub{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-top:1px}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:12px}}
.muted{{color:var(--muted)}}

/* BAR */
.bar-wrap{{display:flex;align-items:center;gap:6px;min-width:105px}}
.bar-num{{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:12px;min-width:36px}}
.bar-track{{flex:1;height:4px;background:rgba(255,255,255,.06);border-radius:2px;overflow:hidden;min-width:38px}}
.bar-fill{{height:100%;border-radius:2px}}

/* FILTERS */
.fbar{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}}
.fbar label{{font-size:12px;color:var(--muted)}}
select{{background:var(--s2);border:1px solid var(--border);color:var(--text);padding:5px 9px;border-radius:5px;font-size:12px;cursor:pointer}}

/* CALLOUTS */
.callout{{padding:11px 14px;border-radius:7px;margin-bottom:14px;font-size:13px;line-height:1.6;border-left:3px solid}}
.callout.info{{background:rgba(59,130,246,.06);border-color:var(--blue)}}
.callout.warn{{background:rgba(249,115,22,.06);border-color:var(--orange)}}
.callout.ok{{background:rgba(34,197,94,.06);border-color:var(--green)}}
.callout.gold{{background:rgba(255,215,0,.06);border-color:var(--aplus)}}
.callout strong{{font-weight:700}}
.callout.info strong{{color:var(--blue)}}.callout.warn strong{{color:var(--orange)}}
.callout.ok strong{{color:var(--green)}}.callout.gold strong{{color:var(--aplus)}}

/* PYRAMID */
.cpyr{{display:flex;flex-direction:column;gap:2px;font-family:'JetBrains Mono',monospace;font-size:10px}}
.cpyr-row{{display:flex;align-items:center;gap:3px}}
.cpyr-lbl{{color:var(--muted);width:36px;text-align:right}}
.cpyr-bar{{height:7px;border-radius:2px;min-width:2px}}
.cpyr-val{{min-width:26px}}

/* HISTÓRICO */
.hist-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:20px}}
.hist-mkt-card{{background:var(--s1);border:1px solid var(--border);border-radius:8px;padding:12px 14px}}
.hist-mkt-name{{font-size:11px;color:var(--muted);margin-bottom:6px;font-weight:600}}
.hist-taxa-val{{font-size:22px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.hist-detail{{font-size:10px;color:var(--muted);margin-top:3px}}
.hist-bar-track{{height:4px;background:rgba(255,255,255,.06);border-radius:2px;margin-top:8px;overflow:hidden}}
.hist-bar-fill{{height:100%;border-radius:2px}}
/* timeline por dia */
.day-hist-row{{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)}}
.day-hist-row:last-child{{border-bottom:none}}
.day-hist-date{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);min-width:60px}}
.day-hist-bar{{flex:1;height:20px;background:rgba(255,255,255,.04);border-radius:4px;overflow:hidden;position:relative}}
.day-hist-fill{{height:100%;border-radius:4px;display:flex;align-items:center;padding:0 6px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;color:#fff;min-width:2px}}
.day-hist-info{{font-family:'JetBrains Mono',monospace;font-size:11px;min-width:90px;text-align:right}}

/* PANELS */
.day-panel{{display:none}}.day-panel.active{{display:block}}
.mkt-panel{{display:none}}.mkt-panel.active{{display:block}}
.empty{{padding:36px;text-align:center;color:var(--muted);font-size:13px}}

/* CALENDAR */
.cal-btn{{
  padding:7px 14px;font-size:12px;font-weight:600;color:var(--muted);
  cursor:pointer;border:1px solid var(--border);border-radius:7px;
  background:var(--s2);white-space:nowrap;transition:all .15s;
  display:flex;align-items:center;gap:5px;flex-shrink:0;align-self:center;
}}
.cal-btn:hover{{color:var(--text);border-color:var(--accent)}}
.cal-modal{{
  position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:999;
  display:flex;align-items:center;justify-content:center;
}}
.cal-modal.hidden{{display:none}}
.cal-box{{
  background:var(--s1);border:1px solid var(--border);border-radius:14px;
  padding:24px;min-width:320px;box-shadow:0 20px 60px rgba(0,0,0,.5);
}}
.cal-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}}
.cal-title{{font-size:15px;font-weight:700;color:var(--text)}}
.cal-nav{{background:var(--s2);border:1px solid var(--border);border-radius:6px;
  padding:4px 10px;cursor:pointer;color:var(--text);font-size:14px;}}
.cal-nav:hover{{border-color:var(--accent);color:var(--accent)}}
.cal-grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;margin-bottom:16px}}
.cal-dow{{font-size:10px;font-weight:600;color:var(--muted);text-align:center;padding:4px 0;letter-spacing:.5px}}
.cal-day{{
  aspect-ratio:1;display:flex;align-items:center;justify-content:center;
  font-size:12px;font-family:'JetBrains Mono',monospace;font-weight:500;
  border-radius:6px;cursor:pointer;border:1px solid transparent;
  transition:all .15s;color:var(--muted);
}}
.cal-day:hover{{background:var(--s3);border-color:var(--border);color:var(--text)}}
.cal-day.today{{border-color:var(--accent);color:var(--accent)}}
.cal-day.has-data{{color:var(--text);background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.2)}}
.cal-day.has-data:hover{{background:rgba(59,130,246,.15);border-color:var(--blue)}}
.cal-day.confirmed{{background:rgba(34,197,94,.08);border-color:rgba(34,197,94,.2);color:var(--green)}}
.cal-day.confirmed:hover{{background:rgba(34,197,94,.15);border-color:var(--green)}}
.cal-day.future{{color:var(--muted);opacity:.5}}
.cal-day.empty{{cursor:default;pointer-events:none}}
.cal-day.selected{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.cal-status{{
  font-size:12px;color:var(--muted);text-align:center;padding:10px;
  background:var(--s2);border-radius:6px;border:1px solid var(--border);
  font-family:'JetBrains Mono',monospace;min-height:36px;
}}
.cal-status.loading{{color:var(--yellow)}}
.cal-status.success{{color:var(--green)}}
.cal-status.error{{color:var(--red)}}
.cal-legend{{display:flex;gap:12px;justify-content:center;margin-top:12px;flex-wrap:wrap}}
.cal-leg{{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)}}
.cal-leg-dot{{width:8px;height:8px;border-radius:2px}}

/* MOBILE */
@media(max-width:640px){{
  .header{{padding:10px 14px}}
  .main{{padding:12px 12px}}
  .kpi{{min-width:85px;padding:10px 12px}}
  .kpi-val{{font-size:20px}}
  .mkt-tab{{padding:9px 11px;font-size:12px}}
  .top-card{{min-width:230px}}
  .hkpi-row{{display:none}}
}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <svg width="280" height="70" viewBox="0 0 340 110" role="img" style="flex-shrink:0">
      <title>WinMetrics</title>
      <defs><clipPath id="bc"><circle cx="31" cy="55" r="28"/></clipPath></defs>
      <circle cx="31" cy="55" r="28" fill="#f97316"/>
      <polygon points="31,29 39,36 36,46 26,46 23,36" fill="#1a1a2e" opacity="0.85"/>
      <polygon points="52,47 58,55 53,63 45,61 43,52" fill="#1a1a2e" opacity="0.85"/>
      <polygon points="44,68 47,77 39,82 31,77 31,68" fill="#1a1a2e" opacity="0.85"/>
      <polygon points="19,68 12,77 13,82 22,82 25,73" fill="#1a1a2e" opacity="0.75" clip-path="url(#bc)"/>
      <polygon points="10,47 4,55 9,63 17,61 19,52" fill="#1a1a2e" opacity="0.75" clip-path="url(#bc)"/>
      <rect x="42" y="48" width="6" height="18" rx="1.5" fill="#fff" opacity="0.95" clip-path="url(#bc)"/>
      <rect x="50" y="42" width="6" height="24" rx="1.5" fill="#fff" opacity="0.95" clip-path="url(#bc)"/>
      <rect x="42" y="28" width="6" height="14" rx="1.5" fill="#f97316" opacity="0.6"/>
      <rect x="50" y="22" width="6" height="18" rx="1.5" fill="#f97316" opacity="0.8"/>
      <rect x="58" y="16" width="6" height="24" rx="1.5" fill="#f97316" opacity="1"/>
      <polyline points="45,42 53,35 61,28" fill="none" stroke="#f97316" stroke-width="1.5" stroke-linecap="round"/>
      <circle cx="61" cy="28" r="2.5" fill="#f97316"/>
      <text x="72" y="46" font-family="Inter,sans-serif" font-size="22" font-weight="700" fill="#f97316" letter-spacing="-0.5">Win</text>
      <text x="111" y="46" font-family="Inter,sans-serif" font-size="22" font-weight="300" fill="#e2e8f0" letter-spacing="-0.5">Metrics</text>
      <rect x="72" y="52" width="196" height="0.8" rx="0" fill="#f97316" opacity="0.3"/>
      <text x="73" y="66" font-family="Inter,sans-serif" font-size="8" font-weight="400" fill="#64748b" letter-spacing="1.8">AI SPORTS ANALYTICS</text>
    </svg>
  </div>
  <div class="hkpi-row" id="global-kpis">
    <!-- preenchido pelo JS -->
  </div>
  <div class="header-right">
    <span class="badge validated">✓ Over 1.5 · 88.6%</span>
    <span class="badge version">v3.1</span>
    <span class="badge updated">🕐 {updated}</span>
  </div>
</div>

<div class="date-bar" id="date-bar">
{date_tabs_html}
</div>

{day_panels_html}

<!-- MODAL CALENDÁRIO -->
<div class="cal-modal hidden" id="cal-modal" onclick="if(event.target===this)closeCal()">
  <div class="cal-box">
    <div class="cal-header">
      <button class="cal-nav" onclick="calNav(-1)">‹</button>
      <span class="cal-title" id="cal-title">Maio 2026</span>
      <button class="cal-nav" onclick="calNav(1)">›</button>
    </div>
    <div class="cal-grid" id="cal-grid"></div>
    <div class="cal-status" id="cal-status">Selecione uma data para carregar os palpites</div>
    <div class="cal-legend">
      <div class="cal-leg"><div class="cal-leg-dot" style="background:rgba(34,197,94,.4)"></div>Confirmado</div>
      <div class="cal-leg"><div class="cal-leg-dot" style="background:rgba(59,130,246,.4)"></div>Com dados</div>
      <div class="cal-leg"><div class="cal-leg-dot" style="background:rgba(249,115,22,.8)"></div>Hoje</div>
    </div>
  </div>
</div>

<!-- ABA HISTÓRICO GLOBAL -->
<div id="panel-historico" style="display:none">
  <div class="main">
    <div id="historico-content"></div>
  </div>
</div>

<script>
const ALL_DATA   = {all_data_json};
const GLOBAIS    = {globais_json};
const MERCADOS   = ['Over 1.5','Over 2.5','BTTS','Over 0.5 HT','Under 4.5','Under 3.5','Esc 7.5','Esc 8.5','Cart 2.5','Cart 3.5'];
const MKT_RESULT = {{
  'Over 1.5':    'over15_ok',
  'Over 2.5':    'over25_ok',
  'BTTS':        'btts',
  'Over 0.5 HT': 'over05_ht_ok',
  'Under 4.5':   'under45_ok',
  'Under 3.5':   'under45_ok',
  'Esc 7.5':     'esc75_ok',
  'Esc 8.5':     'esc85_ok',
  'Cart 2.5':    'cart25_ok',
  'Cart 3.5':    'cart35_ok',
}};
const MKT_SCORE = {{
  'Over 1.5':'score_15','Over 2.5':'score_25','BTTS':'score_btts',
  'Over 0.5 HT':'score_05ht','Under 4.5':'score_u45','Under 3.5':'score_u35',
  'Esc 7.5':'score_esc75','Esc 8.5':'score_esc85',
  'Cart 2.5':'score_cards25','Cart 3.5':'score_cards35',
}};
const MKT_MIN = {{
  'Over 1.5':85,'Over 2.5':75,'BTTS':70,'Over 0.5 HT':75,'Under 4.5':75,'Under 3.5':75,
  'Esc 7.5':75,'Esc 8.5':75,'Cart 2.5':75,'Cart 3.5':75,
}};

// ── Helpers ────────────────────────────────────────────────────────
function col(s){{
  if(s>=88)return'var(--aplus)';if(s>=80)return'var(--green)';
  if(s>=70)return'var(--blue)';if(s>=60)return'var(--orange)';return'var(--red)';
}}
function gradeClass(g){{return g==='A+'?'Aplus':g;}}
function gradeHtml(g){{return`<span class="grade ${{gradeClass(g)}}">${{g}}</span>`;}}
function confHtml(s){{
  if(s>=88)return'<span class="conf MA">M.ALTA</span>';
  if(s>=80)return'<span class="conf A">ALTA</span>';
  if(s>=70)return'<span class="conf M">MÉDIA</span>';
  if(s>=60)return'<span class="conf B">BAIXA</span>';
  return'<span class="conf R">RISCO</span>';
}}
function bar(s,w){{
  w=w||88;const c=col(s);
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
  return'<div class="cpyr">'+rows.map(([l,v,c])=>{{const w=v?Math.round(v*.36):0;return`<div class="cpyr-row"><span class="cpyr-lbl">${{l}}</span><div class="cpyr-bar" style="width:${{w}}px;background:${{c}}"></div><span class="cpyr-val">${{v!=null?v+'%':'—'}}</span></div>`;}}).join('')+'</div>';
}}
function jogoCell(d){{
  return`<td><div class="jogo-main">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div><div class="jogo-sub">${{d.liga}}</div></td>`;
}}
function getJogos(date){{return(ALL_DATA[date]||{{}}).jogos||[];}}

// ── Resultado helpers ──────────────────────────────────────────────
function getResultado(jogo){{return jogo.resultado||null;}}
function isConfirmado(date){{return !!(ALL_DATA[date]||{{}}).resultado_confirmado;}}

function resBadge(jogo, mktKey){{
  const res=getResultado(jogo);
  if(!res)return'<span class="res-badge pending">⏳ Aguardando</span>';
  const ok=res[mktKey];
  if(ok===true) return'<span class="res-badge hit">✓ GREEN</span>';
  if(ok===false)return'<span class="res-badge miss">✗ RED</span>';
  return'<span class="res-badge pending">? S/D</span>';
}}

function rowClass(jogo, mktKey){{
  const res=getResultado(jogo);
  if(!res)return'row-pending';
  const ok=res[mktKey];
  if(ok===true)return'row-hit';
  if(ok===false)return'row-miss';
  return'row-pending';
}}

function placarCell(jogo){{
  const res=getResultado(jogo);
  if(!res)return'<td class="mono muted">—</td>';
  return`<td><div class="placar-cell">${{res.placar}}</div><div class="placar-ht">HT ${{res.placar_ht}}</div></td>`;
}}

function placarCard(jogo, mktKey){{
  const res=getResultado(jogo);
  if(!res)return`<div class="top-placar pending"><span class="icon">⏳</span><span class="ft">Aguardando</span></div>`;
  const ok=res[mktKey];
  const cls=ok===true?'hit':ok===false?'miss':'pending';
  const icon=ok===true?'✓':ok===false?'✗':'?';
  const cant=res.corners_total!=null?` · ${{res.corners_total}}🚩`:'';
  const cart=res.cards_total!=null?` · ${{res.cards_total}}🟨`:'';
  return`<div class="top-placar ${{cls}}">
    <span class="icon">${{icon}}</span>
    <div><span class="ft">${{res.placar}}</span> <span class="ht">HT ${{res.placar_ht}}${{cant}}${{cart}}</span></div>
  </div>`;
}}

function cardOverlayClass(jogo){{
  const res=getResultado(jogo);
  if(!res)return'';
  const ac=jogo.acertos||{{}};
  const bestMktAcerto=ac[jogo.best_mkt];
  if(!bestMktAcerto)return'';
  if(bestMktAcerto.acertou===true)return' tc-hit';
  if(bestMktAcerto.acertou===false)return' tc-miss';
  return'';
}}

// ── Render Global KPIs (header) ────────────────────────────────────
function renderGlobalKpis(){{
  const g=GLOBAIS;
  if(!g||g.dias_confirmados===0){{
    document.getElementById('global-kpis').innerHTML=
      '<span style="font-size:11px;color:var(--muted)">Sem resultados confirmados ainda</span>';
    return;
  }}
  const taxa=g.taxa_geral;
  const c=taxa==null?'var(--muted)':taxa>=70?'var(--green)':taxa>=50?'var(--orange)':'var(--red)';
  document.getElementById('global-kpis').innerHTML=`
    <div class="hkpi"><div class="hkpi-val" style="color:${{c}}">${{taxa!=null?taxa+'%':'—'}}</div><div class="hkpi-lbl">Taxa Geral</div></div>
    <div class="hkpi"><div class="hkpi-val g">${{g.total_acertos}}</div><div class="hkpi-lbl">Acertos</div></div>
    <div class="hkpi"><div class="hkpi-val r">${{g.total_erros}}</div><div class="hkpi-lbl">Erros</div></div>
    <div class="hkpi"><div class="hkpi-val b">${{g.total_palpites}}</div><div class="hkpi-lbl">Palpites</div></div>
  `;
}}

// ── Visão Geral ────────────────────────────────────────────────────
function renderVisao(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-visao');
  const conf=isConfirmado(date);
  const a15=jogos.filter(d=>d.score_15>=85&&d.passou_filtro).length;
  const aesc=jogos.filter(d=>d.score_esc85>=75).length;
  const acart=jogos.filter(d=>d.score_cards25>=75).length;
  const aprem=jogos.filter(d=>d.best_grade==='A+'||d.best_grade==='A').length;
  const a05ht=jogos.filter(d=>d.score_05ht>=75).length;

  // Taxa do dia (se confirmado)
  let taxaDia='';
  if(conf){{
    const stats=(ALL_DATA[date]||{{}}).resultado_stats||{{}};
    let ta=0,te=0;
    Object.values(stats).forEach(s=>{{ta+=s.acertos||0;te+=s.erros||0;}});
    const t=ta+te>0?Math.round(ta/(ta+te)*100):null;
    const c=t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
    const tLabel=t!=null?t+'%':(ta+te===0?'—':'—');
    const tSub=ta+te>0?`${{ta}}✓ ${{te}}✗`:'sem dados';
    taxaDia=`<div class="kpi"><div class="kpi-val" style="color:${{c}}">${{tLabel}}</div><div class="kpi-lbl">Acerto do Dia</div><div style="font-size:9px;color:var(--muted);margin-top:2px;font-family:'JetBrains Mono',monospace">${{tSub}}</div></div>`;
  }}

  const kpi=`<div class="kpi-row">
    <div class="kpi"><div class="kpi-val b">${{jogos.length}}</div><div class="kpi-lbl">Jogos</div></div>
    <div class="kpi"><div class="kpi-val p">${{aprem}}</div><div class="kpi-lbl">Premium A+/A</div></div>
    <div class="kpi"><div class="kpi-val g">${{a15}}</div><div class="kpi-lbl">Over 1.5 ≥85%</div></div>

    <div class="kpi"><div class="kpi-val b">${{aesc}}</div><div class="kpi-lbl">Esc 8.5 ≥75%</div></div>
    <div class="kpi"><div class="kpi-val g">${{acart}}</div><div class="kpi-lbl">Cart 2.5 ≥75%</div></div>
    ${{taxaDia}}
  </div>`;

  const top=[...jogos].sort((a,b)=>b.best_score-a.best_score).slice(0,5);
  const cls=['tc-aplus','tc-a','tc-b','tc-c','tc-d'];
  const t5=top.map((d,i)=>{{
    const c=col(d.best_score);
    const mktKey=MKT_RESULT[d.best_mkt]||'over15_ok';
    const overlay=cardOverlayClass(d);
    return`<div class="top-card ${{cls[i]}}${{overlay}}">
      <div class="top-rank">#${{i+1}}</div>
      <div class="top-liga">${{d.liga}}</div>
      <div class="top-jogo">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div>
      <div class="top-hora">🕐 ${{d.hora}}</div>
      <div class="top-mkt">${{d.best_mkt}}</div>
      <div class="top-bottom">
        <div class="top-score" style="color:${{c}}">${{d.best_score}}%</div>
        <div class="top-grade-block">${{gradeHtml(d.best_grade)}}<span style="font-size:10px;color:var(--muted)">${{d.best_risk}}</span></div>
      </div>
      ${{placarCard(d, mktKey)}}
    </div>`;
  }}).join('');

  const rows=[...jogos].sort((a,b)=>b.best_score-a.best_score).map(d=>{{
    const mktKey=MKT_RESULT[d.best_mkt]||'over15_ok';
    const rc=rowClass(d,mktKey);
    return`<tr class="${{rc}}">
      ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
      <td>${{gradeHtml(d.best_grade)}}</td>
      <td class="mono" style="color:var(--muted);font-size:11px">${{d.best_mkt}}</td>
      <td>${{bar(d.score_15)}}</td><td>${{bar(d.score_esc85)}}</td><td>${{bar(d.score_cards25)}}</td>
      <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
      ${{placarCell(d)}}
      <td>${{resBadge(d,mktKey)}}</td>
    </tr>`;
  }}).join('');

  el.innerHTML=`
    <div class="day-info">${{jogos.length}} jogos · ${{date}}${{conf?' · ✅ Confirmado':''}}</div>
    ${{kpi}}
    <div class="sec-title">🏆 Top 5 Palpites do Dia</div>
    <div class="top-grid">${{t5}}</div>
    <div class="sec-title">📋 Resumo Geral</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Jogo</th><th>Hora</th><th>Grade</th><th>Mercado</th><th>Over 1.5</th><th>Esc 8.5</th><th>Cart 2.5</th><th>xG</th><th>Placar</th><th>Resultado</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
}}

// ── Ranking ────────────────────────────────────────────────────────
function renderRanking(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-ranking');
  const sorted=[...jogos].sort((a,b)=>b.best_score-a.best_score);
  const premium=sorted.filter(d=>d.best_grade==='A+'||d.best_grade==='A');
  const boas=sorted.filter(d=>d.best_grade==='B');
  const perigosas=sorted.filter(d=>d.best_grade==='C'||d.best_grade==='D');

  function section(items,calloutClass,calloutText){{
    if(!items.length)return'<div class="empty">Nenhum jogo nesta categoria.</div>';
    const rows=items.map((d,i)=>{{
      const mktKey=MKT_RESULT[d.best_mkt]||'over15_ok';
      const rc=rowClass(d,mktKey);
      return`<tr class="${{rc}}">
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{gradeHtml(d.best_grade)}}</td>
        <td class="mono" style="font-size:11px;color:var(--muted)">${{d.best_mkt}}</td>
        <td>${{bar(d.best_score)}}</td>
        <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
        ${{placarCell(d)}}
        <td>${{resBadge(d,mktKey)}}</td>
      </tr>`;
    }}).join('');
    return`<div class="callout ${{calloutClass}}">${{calloutText}}</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Grade</th><th>Mercado</th><th>Score</th><th>xG</th><th>Placar</th><th>Resultado</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
  }}

  el.innerHTML=`
    <div class="sec-title">🥇 Entradas Premium (A+ / A)</div>
    ${{section(premium,'gold','<strong>⭐ Entradas Premium</strong> · Score ≥80% com alta consistência estatística.')}}
    <div class="sec-title">📊 Boas Entradas (B)</div>
    ${{section(boas,'ok','<strong>✓ Boas Entradas</strong> · Score 70–79%. Risco médio.')}}
    <div class="sec-title">⚠ Jogos Perigosos (C / D)</div>
    ${{section(perigosas,'warn','<strong>⚠ Jogos Perigosos</strong> · Score abaixo de 70%. Alta variância.')}}`;
}}

// ── Over 1.5 ───────────────────────────────────────────────────────
function renderOver15(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over15');
  let rows=[...jogos].filter(d=>d.passou_filtro).sort((a,b)=>b.score_15-a.score_15);
  const total=rows.length;
  const html=rows.map((d,i)=>{{
    const rc=rowClass(d,'over15_ok');
    const probColor=d.over15_g>=85?'var(--green)':d.over15_g>=75?'var(--blue)':'var(--orange)';
    return`<tr class="${{rc}}">
      <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
      <td class="mono muted">${{d.hora}}</td>
      <td><span style="font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${{probColor}}">${{d.over15_g||'—'}}%</span></td>
      ${{placarCell(d)}}
      <td>${{resBadge(d,'over15_ok')}}</td>
      <td>${{bar(d.score_15)}}</td>
      <td>${{gradeHtml(d.grade_15)}}</td>
      <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
      <td>${{via(d.via)}}</td>
    </tr>`;
  }}).join('');
  el.innerHTML=`
    <div class="callout info"><strong>Over 1.5 Gols — Validado 88.6%</strong> · ${{total}} jogos aprovados no Filtro 3 Vias.</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th style="color:var(--green)">Probabilidade</th><th>Placar</th><th>Resultado</th><th>Score</th><th>Grade</th><th>xG</th><th>Via</th></tr></thead>
      <tbody>${{html||'<tr><td colspan="10" class="empty">Nenhum jogo passou o Filtro 3 Vias.</td></tr>'}}</tbody>
    </table></div>`;
}}

// ── Under 4.5 ────────────────────────────────────────────────────
function renderOver25(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over25');
  // Under 3.5: sort by score_u35, fallback to score_u45
  const ru35=[...jogos].sort((a,b)=>(b.score_u35||b.score_u45||0)-(a.score_u35||a.score_u45||0));
  el.innerHTML=`
    <div class="callout ok"><strong>Under 3.5 Gols</strong> · Foco em jogos de baixa produção ofensiva. Modelo Poisson via xG.</div>
    <div class="tbl-wrap"><table>
      <thead><tr>
        <th>#</th><th>Jogo</th><th>Hora</th>
        <th style="color:var(--purple)">Poisson U3.5</th>
        <th style="color:var(--teal)">xG Total</th>
        <th>Placar</th><th>Resultado</th>
        <th>Score U3.5</th><th>Grade</th>
      </tr></thead>
      <tbody>${{ru35.map((d,i)=>{{
        const u35prob=d.poisson_u35||null;
        const probColor=u35prob>=85?'var(--green)':u35prob>=75?'var(--blue)':'var(--muted)';
        const rc=rowClass(d,'under45_ok');
        return`<tr class="${{rc}}">
          <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
          <td class="mono muted">${{d.hora}}</td>
          <td><span style="font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${{probColor}}">${{u35prob?u35prob+'%':'—'}}</span></td>
          <td class="mono" style="color:var(--teal);font-size:14px;font-weight:600">${{d.exg_tot||'—'}}</td>
          ${{placarCell(d)}}<td>${{resBadge(d,'under45_ok')}}</td>
          <td>${{bar(d.score_u35||d.score_u45||0)}}</td>
          <td>${{gradeHtml(d.grade_u35||d.grade_u45||'D')}}</td>
        </tr>`;
      }}).join('')}}</tbody>
    </table></div>`;
}}

// ── Escanteios ─────────────────────────────────────────────────────
function renderEsc(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-escanteios');
  const r75=[...jogos].sort((a,b)=>b.score_esc75-a.score_esc75);
  const r85=[...jogos].sort((a,b)=>b.score_esc85-a.score_esc85);
  function escRows(rows,mktKey){{
    return rows.slice(0,15).map((d,i)=>{{
      const rc=rowClass(d,mktKey);
      const res=getResultado(d);
      const cantReal=res&&res.corners_total!=null?`<td class="mono" style="color:var(--teal)">${{res.corners_total}}</td>`:'<td class="mono muted">—</td>';
      return`<tr class="${{rc}}">
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{bar(mktKey==='esc75_ok'?d.score_esc75:d.score_esc85)}}</td>
        <td class="mono" style="color:var(--teal)">${{d.avg_corners||'—'}}</td>
        <td>${{pyramid(d)}}</td>
        ${{cantReal}}<td>${{resBadge(d,mktKey)}}</td>
      </tr>`;
    }}).join('');
  }}
  el.innerHTML=`
    <div class="callout ok"><strong>Escanteios Over 7.5 / 8.5</strong> · Threshold provisório ≥75%.</div>
    <div class="sec-title">🚩 Over 7.5</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Média</th><th>Pirâmide</th><th>Real</th><th>Resultado</th></tr></thead>
      <tbody>${{escRows(r75,'esc75_ok')}}</tbody></table></div>
    <div class="sec-title">🚩 Over 8.5</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Média</th><th>Pirâmide</th><th>Real</th><th>Resultado</th></tr></thead>
      <tbody>${{escRows(r85,'esc85_ok')}}</tbody></table></div>`;
}}

// ── Cartões ────────────────────────────────────────────────────────
function renderCart(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-cartoes');
  const rows=[...jogos].sort((a,b)=>b.score_cards25-a.score_cards25);
  el.innerHTML=`
    <div class="callout ok"><strong>Cartões Over 2.5 / Over 3.5</strong> · Alta consistência observada.</div>
    <div class="tbl-wrap"><table>
      <thead><tr>
        <th>#</th><th>Jogo</th><th>Hora</th>
        <th style="color:var(--yellow)">O2.5%</th>
        <th style="color:var(--orange)">O3.5%</th>
        <th>Real</th><th>Resultado</th>
        <th>Score 2.5</th><th>Grade</th><th>Score 3.5</th><th>Média</th>
      </tr></thead>
      <tbody>${{rows.map((d,i)=>{{
        const rc=rowClass(d,'cart25_ok');
        const res=getResultado(d);
        const cartReal=res&&res.cards_total!=null?`<td class="mono" style="color:var(--yellow);font-weight:700;font-size:15px">${{res.cards_total}}</td>`:'<td class="mono muted">—</td>';
        const p25color=d.over25_cards>=85?'var(--green)':d.over25_cards>=75?'var(--blue)':'var(--orange)';
        const p35color=d.over35_cards>=75?'var(--green)':d.over35_cards>=60?'var(--blue)':'var(--muted)';
        return`<tr class="${{rc}}">
          <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
          <td class="mono muted">${{d.hora}}</td>
          <td><span style="font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${{p25color}}">${{d.over25_cards||'—'}}%</span></td>
          <td><span style="font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${{p35color}}">${{d.over35_cards||'—'}}%</span></td>
          ${{cartReal}}<td>${{resBadge(d,'cart25_ok')}}</td>
          <td>${{bar(d.score_cards25)}}</td><td>${{gradeHtml(d.grade_cart25)}}</td>
          <td>${{bar(d.score_cards35,70)}}</td>
          <td class="mono" style="color:var(--yellow)">${{d.avg_cards||'—'}}</td>
        </tr>`;
      }}).join('')}}</tbody>
    </table></div>`;
}}

// ── Resultados do Dia ──────────────────────────────────────────────
function renderHistoricoDia(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-historico_dia');
  const conf=isConfirmado(date);
  const stats=(ALL_DATA[date]||{{}}).resultado_stats||{{}};

  if(!conf){{
    const rows=jogos.sort((a,b)=>b.best_score-a.best_score).map(d=>{{
      const mktKey=MKT_RESULT[d.best_mkt]||'over15_ok';
      return`<tr class="row-pending">
        ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
        <td>${{gradeHtml(d.best_grade)}}</td>
        <td class="mono" style="font-size:11px;color:var(--muted)">${{d.best_mkt}}</td>
        <td>${{bar(d.best_score)}}</td>
        <td><span class="res-badge pending">⏳ Aguardando</span></td>
      </tr>`;
    }}).join('');
    el.innerHTML=`
      <div class="callout warn"><strong>⏳ Resultados pendentes</strong> · Execute <code>confirmar.py --date ${{date.split('-').reverse().join('-')}}</code> após os jogos.</div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>Jogo</th><th>Hora</th><th>Grade</th><th>Mercado</th><th>Score</th><th>Status</th></tr></thead>
        <tbody>${{rows}}</tbody>
      </table></div>`;
    return;
  }}

  // Taxa por mercado
  const taxaBars=MERCADOS.filter(m=>stats[m]&&stats[m].palpites>0).map(m=>{{
    const s=stats[m];
    const t=s.taxa;
    const c=t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
    return`<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--border)">
      <span style="width:110px;font-size:12px;color:var(--muted)">${{m}}</span>
      <div style="flex:1;height:7px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden">
        <div style="height:100%;width:${{t||0}}%;background:${{c}};border-radius:3px"></div>
      </div>
      <span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:${{c}};min-width:42px;text-align:right">${{t!=null?t+'%':'—'}}</span>
      <span style="font-size:10px;color:var(--muted);min-width:75px">${{s.acertos}}✓ ${{s.erros}}✗ / ${{s.palpites}}</span>
    </div>`;
  }}).join('');

  // Tabela completa com resultados
  const rows=jogos.sort((a,b)=>b.best_score-a.best_score).map(d=>{{
    const res=getResultado(d);
    const ac=d.acertos||{{}};
    const badges=Object.entries(ac).map(([mkt,info])=>{{
      const cls=info.acertou===true?'hit':info.acertou===false?'miss':'pending';
      const icon=info.acertou===true?'✓':info.acertou===false?'✗':'?';
      return`<span class="res-badge ${{cls}}" style="margin:1px;font-size:9px">${{icon}} ${{mkt}}</span>`;
    }}).join('');
    const mktKey=MKT_RESULT[d.best_mkt]||'over15_ok';
    const rc=rowClass(d,mktKey);
    const cantRow=res&&res.corners_total!=null?res.corners_total+'🚩':'—';
    const cartRow=res&&res.cards_total!=null?res.cards_total+'🟨':'—';
    return`<tr class="${{rc}}">
      ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
      ${{res?`<td><div class="placar-cell">${{res.placar}}</div><div class="placar-ht">HT ${{res.placar_ht}}</div></td>`:'<td class="mono muted">—</td>'}}
      <td class="mono">${{cantRow}}</td><td class="mono">${{cartRow}}</td>
      <td style="max-width:230px">${{badges||'<span class="muted" style="font-size:11px">Sem palpites</span>'}}</td>
    </tr>`;
  }}).join('');

  // Totais
  let ta=0,te=0,tp=0;
  Object.values(stats).forEach(s=>{{ta+=s.acertos||0;te+=s.erros||0;tp+=s.palpites||0;}});
  const tGeral=ta+te>0?Math.round(ta/(ta+te)*100):null;
  const cG=tGeral==null?'var(--muted)':tGeral>=70?'var(--green)':tGeral>=50?'var(--orange)':'var(--red)';

  el.innerHTML=`
    <div class="callout ok"><strong>✅ Resultados confirmados</strong> · Dados reais da API-Football.</div>
    <div class="kpi-row" style="margin-bottom:16px">
      <div class="kpi"><div class="kpi-val" style="color:${{cG}}">${{tGeral!=null?tGeral+'%':'—'}}</div><div class="kpi-lbl">Taxa do Dia</div></div>
      <div class="kpi"><div class="kpi-val g">${{ta}}</div><div class="kpi-lbl">Acertos</div></div>
      <div class="kpi"><div class="kpi-val r">${{te}}</div><div class="kpi-lbl">Erros</div></div>
      <div class="kpi"><div class="kpi-val b">${{tp}}</div><div class="kpi-lbl">Palpites</div></div>
    </div>
    <div class="sec-title">📊 Taxa por Mercado</div>
    <div style="max-width:580px;margin-bottom:20px">${{taxaBars||'<div class="empty">Sem dados.</div>'}}</div>
    <div class="sec-title">📋 Todos os Jogos</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Jogo</th><th>Hora</th><th>Placar</th><th>Cant.</th><th>Cart.</th><th>Palpites e Acertos</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
}}

// ── Histórico Global ───────────────────────────────────────────────
function renderHistoricoGlobal(){{
  const el=document.getElementById('historico-content');
  const g=GLOBAIS;
  const pm=g.por_mercado||{{}};
  const dias=Object.keys(ALL_DATA).sort();

  if(g.dias_confirmados===0){{
    el.innerHTML=`<div class="callout warn" style="margin-top:20px"><strong>⏳ Sem histórico confirmado ainda</strong> · Execute confirmar.py após os jogos de cada dia.</div>`;
    return;
  }}

  // Cards por mercado
  const mktCards=MERCADOS.filter(m=>pm[m]&&pm[m].p>0).map(m=>{{
    const s=pm[m];
    const t=s.taxa;
    const c=t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
    return`<div class="hist-mkt-card">
      <div class="hist-mkt-name">${{m}}</div>
      <div class="hist-taxa-val" style="color:${{c}}">${{t!=null?t+'%':'—'}}</div>
      <div class="hist-detail">${{s.acertos}}✓ ${{s.erros}}✗ / ${{s.palpites}} palpites</div>
      <div class="hist-bar-track"><div class="hist-bar-fill" style="width:${{t||0}}%;background:${{c}}"></div></div>
    </div>`;
  }}).join('');

  // Timeline por dia
  const timeline=dias.map(d=>{{
    const dayData=ALL_DATA[d]||{{}};
    if(!dayData.resultado_confirmado)return'';
    const s=dayData.resultado_stats||{{}};
    let ta=0,te=0;
    Object.values(s).forEach(x=>{{ta+=x.acertos||0;te+=x.erros||0;}});
    const t=ta+te>0?Math.round(ta/(ta+te)*100):null;
    const c=t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
    const [dd,mm]=d.split('-');
    return`<div class="day-hist-row">
      <span class="day-hist-date">${{dd}}/${{mm}}</span>
      <div class="day-hist-bar">
        <div class="day-hist-fill" style="width:${{t||0}}%;background:${{c}}">${{t!=null&&t>15?t+'%':''}}</div>
      </div>
      <span class="day-hist-info" style="color:${{c}}">${{t!=null?t+'%':'—'}} <span style="color:var(--muted)">${{ta}}✓ ${{te}}✗</span></span>
    </div>`;
  }}).join('');

  const taxa=g.taxa_geral;
  const cG=taxa==null?'var(--muted)':taxa>=70?'var(--green)':taxa>=50?'var(--orange)':'var(--red)';

  el.innerHTML=`
    <div class="kpi-row" style="margin-bottom:20px">
      <div class="kpi"><div class="kpi-val" style="color:${{cG}}">${{taxa!=null?taxa+'%':'—'}}</div><div class="kpi-lbl">Taxa Geral</div></div>
      <div class="kpi"><div class="kpi-val g">${{g.total_acertos}}</div><div class="kpi-lbl">Total Acertos</div></div>
      <div class="kpi"><div class="kpi-val r">${{g.total_erros}}</div><div class="kpi-lbl">Total Erros</div></div>
      <div class="kpi"><div class="kpi-val b">${{g.total_palpites}}</div><div class="kpi-lbl">Total Palpites</div></div>

    </div>
    <div class="sec-title">📊 Taxa por Mercado (acumulado)</div>
    <div class="hist-grid">${{mktCards}}</div>
    <div class="sec-title">📅 Evolução por Dia</div>
    <div style="max-width:700px">${{timeline||'<div class="empty">Sem dias confirmados.</div>'}}</div>`;
}}

// ── Calendário ────────────────────────────────────────────────────
const GH_OWNER = 'crdesigner17';
const GH_REPO  = 'winmetrics-analytics';
const GH_TOKEN_KEY = 'wm_gh_token';

let calYear  = new Date().getFullYear();
let calMonth = new Date().getMonth();
const MONTHS_PT = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                   'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
const DAYS_PT   = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];

function openCal(){{
  document.getElementById('cal-modal').classList.remove('hidden');
  renderCal();
}}
function closeCal(){{
  document.getElementById('cal-modal').classList.add('hidden');
}}

function calNav(dir){{
  calMonth += dir;
  if(calMonth > 11){{ calMonth=0; calYear++; }}
  if(calMonth < 0) {{ calMonth=11; calYear--; }}
  renderCal();
}}

function renderCal(){{
  document.getElementById('cal-title').textContent = MONTHS_PT[calMonth]+' '+calYear;
  const grid = document.getElementById('cal-grid');
  const today = new Date();
  const todayStr = today.toISOString().slice(0,10).split('-').reverse().join('-'); // DD-MM-YYYY

  // Day-of-week headers
  let html = DAYS_PT.map(d=>`<div class="cal-dow">${{d}}</div>`).join('');

  // First day of month
  const first = new Date(calYear, calMonth, 1).getDay();
  for(let i=0;i<first;i++) html += '<div class="cal-day empty"></div>';

  // Days
  const days = new Date(calYear, calMonth+1, 0).getDate();
  for(let d=1;d<=days;d++){{
    const dd = String(d).padStart(2,'0');
    const mm = String(calMonth+1).padStart(2,'0');
    const dateKey = `${{dd}}-${{mm}}-${{calYear}}`; // DD-MM-YYYY
    const apiDate = `${{calYear}}-${{mm}}-${{dd}}`; // YYYY-MM-DD
    const dayDate = new Date(calYear, calMonth, d);
    const isFuture = dayDate > today;
    const isToday  = dateKey === todayStr;
    const hasData  = !!ALL_DATA[dateKey];
    const isConf   = hasData && ALL_DATA[dateKey].resultado_confirmado;

    let cls = 'cal-day';
    if(isToday)        cls += ' today';
    else if(isConf)    cls += ' confirmed';
    else if(hasData)   cls += ' has-data';
    else if(isFuture)  cls += ' future';

    html += `<div class="${{cls}}" onclick="calSelect('${{dateKey}}','${{apiDate}}')">${{d}}</div>`;
  }}

  grid.innerHTML = html;
}}

async function calSelect(dateKey, apiDate){{
  // Highlight selected
  document.querySelectorAll('.cal-day').forEach(d=>d.classList.remove('selected'));
  event.target.classList.add('selected');

  const status = document.getElementById('cal-status');
  const today = new Date();
  const selDate = new Date(apiDate);
  const isPast = selDate < new Date(today.toDateString());

  // If data already exists, just navigate to it
  if(ALL_DATA[dateKey]){{
    status.textContent = `✓ Dados já carregados para ${{dateKey}}`;
    status.className = 'cal-status success';
    closeCal();
    setTimeout(()=>switchDate(dateKey), 300);
    return;
  }}

  // Need to trigger workflow
  const token = localStorage.getItem(GH_TOKEN_KEY) || prompt('Cole seu GH_TOKEN para acionar o workflow:');
  if(!token){{ status.textContent = 'Token não fornecido.'; status.className='cal-status error'; return; }}
  localStorage.setItem(GH_TOKEN_KEY, token);

  status.textContent = `⏳ Acionando coleta para ${{apiDate}}...`;
  status.className = 'cal-status loading';

  // Trigger coletar workflow
  const ok = await triggerWorkflow('build.yml', {{ date: apiDate }}, token);
  if(!ok){{ status.textContent = '✗ Erro ao acionar workflow. Verifique o token.'; status.className='cal-status error'; return; }}

  status.textContent = `✓ Coleta iniciada para ${{apiDate}}! O dashboard atualiza em ~2 min.`;
  status.className = 'cal-status success';

  // If past date, also trigger confirmar
  if(isPast){{
    setTimeout(async()=>{{
      status.textContent = `⏳ Acionando confirmação de resultados...`;
      status.className = 'cal-status loading';
      const ok2 = await triggerWorkflow('confirmar.yml', {{ date: apiDate }}, token);
      if(ok2){{
        status.textContent = `✓ Coleta + confirmação iniciadas! Aguarde ~3 min e recarregue.`;
        status.className = 'cal-status success';
      }}
    }}, 5000);
  }}
}}

async function triggerWorkflow(workflow, inputs, token){{
  try{{
    const r = await fetch(
      `https://api.github.com/repos/${{GH_OWNER}}/${{GH_REPO}}/actions/workflows/${{workflow}}/dispatches`,
      {{
        method: 'POST',
        headers:{{
          'Authorization': `Bearer ${{token}}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json',
        }},
        body: JSON.stringify({{ ref:'main', inputs }})
      }}
    );
    return r.status === 204;
  }} catch(e){{
    console.error(e);
    return false;
  }}
}}

// ── Navigation ─────────────────────────────────────────────────────
let activeDate=null;
let activeMkt={{}};
let historicoVisible=false;

function showHistoricoGlobal(){{
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-historico').style.display='block';
  document.getElementById('btn-historico').style.color='var(--accent)';
  historicoVisible=true;
  renderHistoricoGlobal();
}}

function switchDate(date){{
  document.getElementById('panel-historico').style.display='none';
  document.getElementById('btn-historico').style.color='';
  historicoVisible=false;
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-tab').forEach(t=>t.classList.remove('active'));
  const panel=document.getElementById('day-'+date);
  const tab=document.querySelector(`[data-date="${{date}}"]`);
  if(panel)panel.classList.add('active');
  if(tab){{tab.classList.add('active');tab.scrollIntoView({{behavior:'smooth',block:'nearest',inline:'center'}});}}
  activeDate=date;
  if(!activeMkt[date])activeMkt[date]='visao';
  switchMkt(date,activeMkt[date]);
  // Mover date-bar para abaixo da mkt-bar
  const mktBar=panel?panel.querySelector('.mkt-bar'):null;
  const dateBar=document.getElementById('date-bar');
  if(mktBar&&dateBar)mktBar.parentNode.insertBefore(dateBar,mktBar.nextSibling);
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
  if(mkt==='visao')          renderVisao(date,jogos);
  else if(mkt==='ranking')   renderRanking(date,jogos);
  else if(mkt==='over15')    renderOver15(date,jogos);
  else if(mkt==='over25')    renderOver25(date,jogos);
  else if(mkt==='escanteios')renderEsc(date,jogos);
  else if(mkt==='cartoes')   renderCart(date,jogos);
  else if(mkt==='historico_dia') renderHistoricoDia(date,jogos);
}}

// Init — mover date-bar para abaixo da mkt-bar
renderGlobalKpis();
const dates=Object.keys(ALL_DATA);

function positionDateBar(date){{
  const panel=document.getElementById('day-'+date);
  const mktBar=panel?panel.querySelector('.mkt-bar'):null;
  const dateBar=document.getElementById('date-bar');
  if(mktBar&&dateBar){{
    mktBar.parentNode.insertBefore(dateBar, mktBar.nextSibling);
  }}
}}

if(dates.length){{
  switchDate(dates[0]);
  positionDateBar(dates[0]);
}}
</script>

<!-- Botão Histórico Global flutuante na date-bar -->
<style>
.hist-btn{{
  padding:7px 14px;font-size:12px;font-weight:600;color:var(--muted);
  cursor:pointer;border:1px solid var(--border);border-radius:7px;
  background:var(--s2);white-space:nowrap;transition:all .15s;
  display:flex;align-items:center;gap:5px;flex-shrink:0;align-self:center;
}}
.hist-btn:hover{{color:var(--text);border-color:var(--accent)}}
</style>
<script>
// Adiciona botão Histórico na date-bar
const dateBar=document.getElementById('date-bar');
const btn=document.createElement('div');
btn.id='btn-historico';
btn.className='date-tab';
btn.style.cssText='min-width:100px;cursor:pointer';
btn.innerHTML='<span class="dt-label">📈 Histórico</span><span style="font-size:9px;color:var(--muted);margin-top:2px">Visão geral</span>';
btn.onclick=showHistoricoGlobal;
dateBar.appendChild(btn);

const calBtn=document.createElement('div');
calBtn.className='date-tab';
calBtn.style.cssText='min-width:100px;cursor:pointer;border-color:rgba(249,115,22,.3)';
calBtn.innerHTML='<span class="dt-label">📅 Data</span><span style="font-size:9px;color:var(--accent);margin-top:2px">selecionar</span>';
calBtn.onclick=openCal;
dateBar.appendChild(calBtn);
</script>
</body>
</html>'''

if __name__ == '__main__':
    gerar_site()
