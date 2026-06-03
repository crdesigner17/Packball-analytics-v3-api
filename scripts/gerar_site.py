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
    nesc   = sum(1 for j in jogos if j['score_esc75'] >= 75)
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
      <div class="mkt-tab"       data-mkt="ranking"     onclick="switchMkt('{d}','ranking')">🏅 Melhores Previsões <span class="cnt g">{nprem}</span></div>
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

    today = datetime.now().date()
    for entry in sorted(index, key=lambda x: datetime.strptime(x['date'], '%d-%m-%Y')):
        d = entry['date']
        day_data = load_day(d)
        if not day_data: continue
        # Não mostrar datas futuras sem jogos confirmados
        try:
            day_date = datetime.strptime(d, '%d-%m-%Y').date()
            if day_date > today and not day_data.get('jogos'):
                continue
        except:
            pass
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
.date-bar{{background:var(--s1);border-bottom:1px solid var(--border);display:flex;overflow-x:auto;gap:4px;padding:8px 16px;scrollbar-width:thin;scrollbar-color:var(--border) transparent;justify-content:center;position:sticky;top:61px;z-index:95}}
.date-bar::-webkit-scrollbar{{height:3px}}
.date-bar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.date-tab{{padding:7px 16px;font-size:12px;font-weight:600;color:var(--muted);cursor:pointer;border:1px solid var(--border);border-radius:7px;white-space:nowrap;transition:all .15s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;background:var(--s2);height:40px;min-width:80px}}
.date-tab:hover{{color:var(--text);border-color:var(--accent)}}
.date-tab.active{{color:var(--accent);border-color:var(--accent);background:rgba(249,115,22,.07)}}
.dt-label{{font-weight:700;font-size:12px;line-height:1;text-align:center}}
.dt-kpis{{display:flex;gap:3px;flex-wrap:wrap;justify-content:center}}
.dt-kpi{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px}}
.dt-kpi.g{{background:rgba(34,197,94,.1);color:var(--green)}}
.dt-kpi.b{{background:rgba(59,130,246,.1);color:var(--blue)}}
.dt-kpi.o{{background:rgba(249,115,22,.1);color:var(--orange)}}
.dt-kpi.prem{{background:rgba(255,215,0,.12);color:var(--aplus)}}

/* MKT BAR */
.mkt-bar{{background:var(--s1);border-bottom:1px solid var(--border);display:flex;justify-content:center;position:sticky;top:109px;z-index:90}}
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
.day-info{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);text-align:center;margin-bottom:10px;margin-top:8px}}

/* KPI ROW */
.kpi-row{{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:16px;padding:10px 0;border-bottom:1px solid var(--border)}}
.kpi{{background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:12px 18px;text-align:center;min-width:120px;transition:all .2s;cursor:default}}
.kpi:hover{{border-color:var(--accent)}}
.kpi.clickable{{cursor:pointer}}
.kpi.clickable:hover{{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,.3)}}
.kpi.active{{transform:translateY(-2px);box-shadow:0 4px 16px rgba(0,0,0,.3)}}
.kpi.kpi-blue{{border-color:rgba(59,130,246,.3);background:rgba(59,130,246,.06)}}
.kpi.kpi-blue.active,.kpi.kpi-blue:hover{{border-color:var(--blue);background:rgba(59,130,246,.12)}}
.kpi.kpi-green{{border-color:rgba(34,197,94,.3);background:rgba(34,197,94,.06)}}
.kpi.kpi-green.active,.kpi.kpi-green:hover{{border-color:var(--green);background:rgba(34,197,94,.12)}}
.kpi.kpi-yellow{{border-color:rgba(234,179,8,.3);background:rgba(234,179,8,.06)}}
.kpi.kpi-yellow.active,.kpi.kpi-yellow:hover{{border-color:var(--yellow);background:rgba(234,179,8,.12)}}
.kpi.kpi-teal{{border-color:rgba(20,184,166,.3);background:rgba(20,184,166,.06)}}
.kpi.kpi-teal.active,.kpi.kpi-teal:hover{{border-color:var(--teal);background:rgba(20,184,166,.12)}}
.kpi.kpi-orange{{border-color:rgba(249,115,22,.3);background:rgba(249,115,22,.06)}}
.kpi.kpi-orange.active,.kpi.kpi-orange:hover{{border-color:var(--orange);background:rgba(249,115,22,.12)}}
.kpi-filter-panel{{background:var(--s1);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px;animation:fadeIn .2s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(-6px)}}to{{opacity:1;transform:translateY(0)}}}}
.kpi-filter-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.kpi-filter-title::after{{content:'';flex:1;height:1px;background:var(--border)}}
.kpi-val{{font-size:28px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
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
.grade{{display:inline-block;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;font-family:'Inter',sans-serif;white-space:nowrap}}
.grade.Aplus{{background:rgba(34,197,94,.12);color:var(--green);border:1px solid rgba(34,197,94,.3)}}
.grade.A{{background:rgba(234,179,8,.1);color:var(--yellow);border:1px solid rgba(234,179,8,.3)}}
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
    <img src="data:image/png;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAQABgADASIAAhEBAxEB/8QAHQABAAEFAQEBAAAAAAAAAAAAAAcEBQYICQMCAf/EAGUQAQABAwMBBAYDCgUMCw0JAAABAgMEBQYRBwgSITETQVFhcYEUIpEJFSMyQlJygqGzFiRisbQXMzc4Y3WSorLB0dIYJTVDVGVzk8LT4SYnNEVGU1Z0g5Wjw+MoNkRHV4WUpfD/xAAcAQEAAgMBAQEAAAAAAAAAAAAAAQQDBQYHAgj/xAA4EQEAAgECBAELAwMDBQEAAAAAAQIDBBEFEiExQQYTFCJRYXGBkcHRMqGxQuHwI3KSBxVDUlOC/9oADAMBAAIRAxEAPwDTIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH/9k=" style="height:52px;flex-shrink:0;object-fit:contain" alt="WinMetrics Analytics">
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
// ── KPI Filter ────────────────────────────────────────────────────
let activeKpi = {{}};
function kpiFilter(date, tipo, count){{
  const panel = document.getElementById('kpi-panel-'+date);
  const jogos = getJogos(date);
  // Toggle
  if(activeKpi[date]===tipo){{
    activeKpi[date]=null;
    panel.style.display='none';
    document.querySelectorAll(`[id^="kpi-"][id$="-${{date}}"]`).forEach(el=>el.classList.remove('active'));
    return;
  }}
  activeKpi[date]=tipo;
  // Highlight ativo
  document.querySelectorAll(`[id^="kpi-"][id$="-${{date}}"]`).forEach(el=>el.classList.remove('active'));
  document.getElementById(`kpi-${{tipo}}-${{date}}`).classList.add('active');
  // Filtrar jogos
  let filtrados=[], titulo='', cor='var(--text)';
  if(tipo==='prem'){{
    filtrados=jogos.filter(d=>d.best_grade==='A+'||d.best_grade==='A').sort((a,b)=>b.best_score-a.best_score);
    titulo='🟢 Alta Confiança'; cor='var(--green)';
  }} else if(tipo==='15'){{
    filtrados=jogos.filter(d=>d.score_15>=85&&d.passou_filtro).sort((a,b)=>b.score_15-a.score_15);
    titulo='🟡 Over 1.5 ≥85%'; cor='var(--yellow)';
  }} else if(tipo==='esc'){{
    filtrados=jogos.filter(d=>d.score_esc75>=75).sort((a,b)=>b.score_esc75-a.score_esc75);
    titulo='🔵 Over 7.5 Escanteios ≥75%'; cor='var(--teal)';
  }} else if(tipo==='cart'){{
    filtrados=jogos.filter(d=>d.score_cards25>=75).sort((a,b)=>b.score_cards25-a.score_cards25);
    titulo='🟠 Over 2.5 Cartões ≥75%'; cor='var(--orange)';
  }}
  if(!filtrados.length){{
    panel.innerHTML=`<div class="kpi-filter-panel"><div class="kpi-filter-title" style="color:${{cor}}">${{titulo}}</div><div class="empty">Nenhum jogo neste filtro.</div></div>`;
    panel.style.display='block'; return;
  }}
  const rows=filtrados.map((d,i)=>{{
    const mktKey=MKT_RESULT[d.best_mkt]||'over15_ok';
    const rc=rowClass(d,mktKey);
    const scoreField=tipo==='prem'?d.best_score:tipo==='15'?d.score_15:tipo==='esc'?d.score_esc75:d.score_cards25;
    const mktShow=tipo==='prem'?d.best_mkt:tipo==='15'?'Over 1.5':tipo==='esc'?'Esc 7.5':'Cart 2.5';
    return`<tr class="${{rc}}">
      <td class="mono muted">${{i+1}}</td>
      ${{jogoCell(d)}}
      <td class="mono muted">${{d.hora}}</td>
      <td>${{gradeHtml(d.best_grade)}}</td>
      <td class="mono" style="font-size:11px;color:var(--muted)">${{mktShow}}</td>
      <td>${{bar(scoreField)}}</td>
      <td class="mono" style="color:var(--yellow);font-weight:700">${{oddMkt(d)}}</td>
      ${{placarCell(d)}}
      <td>${{resBadge(d,mktKey)}}</td>
    </tr>`;
  }}).join('');
  panel.innerHTML=`<div class="kpi-filter-panel">
    <div class="kpi-filter-title" style="color:${{cor}}">${{titulo}} · ${{filtrados.length}} jogos</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Confiança</th><th>Mercado</th><th>Score</th><th style="color:var(--yellow)">Odd</th><th>Placar</th><th>Resultado</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>
  </div>`;
  panel.style.display='block';
  panel.scrollIntoView({{behavior:'smooth',block:'nearest'}});
}}

function col(s){{
  if(s>=85)return'var(--green)';
  if(s>=75)return'var(--yellow)';
  if(s>=65)return'var(--blue)';
  if(s>=50)return'var(--orange)';
  return'var(--red)';
}}
function gradeClass(g){{return g==='A+'?'Aplus':g;}}
const GRADE_NOME={{'A+':'Confiança Alta','A':'Confiança Média','B':'Moderado','C':'Arriscado','D':'Evitar'}};
function gradeHtml(g){{
  return`<span class="grade ${{gradeClass(g)}}" title="${{g}}">${{GRADE_NOME[g]||g}}</span>`;
}}
function confHtml(s){{
  if(s>=85)return'<span class="conf MA">Conf. Alta</span>';
  if(s>=75)return'<span class="conf A">Conf. Média</span>';
  if(s>=65)return'<span class="conf M">Moderado</span>';
  if(s>=50)return'<span class="conf B">Arriscado</span>';
  return'<span class="conf R">Evitar</span>';
}}
function bar(s,w){{
  w=w||88;const c=col(s);
  return`<div class="bar-wrap"><span class="bar-num" style="color:${{c}}">${{s}}%</span><div class="bar-track" style="width:${{w}}px"><div class="bar-fill" style="width:${{Math.min(s,100)}}%;background:${{c}}"></div></div></div>`;
}}
function odd(v){{
  if(!v||v==='—')return'—';
  return parseFloat(v).toFixed(2);
}}
function oddMkt(d){{
  const mkt=d.best_mkt||'';
  let val=null;
  if(mkt==='Over 1.5')      val=d.odds_o15||d.odd_over15;
  else if(mkt==='Over 2.5') val=d.odds_o25;
  else if(mkt==='Cart 2.5') val=d.odds_cards_25;
  else if(mkt==='Cart 3.5') val=d.odds_cards_35;
  else if(mkt==='Esc 7.5')  val=d.odds_corners_75;
  else if(mkt==='Esc 8.5')  val=d.odds_corners_85;
  else if(mkt==='Under 3.5'||mkt==='Under 4.5') val=d.odds_u45;
  else if(mkt==='BTTS')     val=null;
  if(!val) return'—';
  return parseFloat(val).toFixed(2);
}}
function oddMktLabel(mkt){{
  if(mkt==='Over 1.5')      return'Odd O1.5';
  if(mkt==='Over 2.5')      return'Odd O2.5';
  if(mkt==='Cart 2.5')      return'Odd C2.5';
  if(mkt==='Cart 3.5')      return'Odd C3.5';
  if(mkt==='Esc 7.5')       return'Odd E7.5';
  if(mkt==='Esc 8.5')       return'Odd E8.5';
  if(mkt==='Under 3.5')     return'Odd U3.5';
  if(mkt==='Under 4.5')     return'Odd U4.5';
  return'Odd';
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
  const aesc=jogos.filter(d=>d.score_esc75>=75).length;
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

  const kpi=`<div class="kpi-row" id="kpi-row-${{date}}">
    <div class="kpi kpi-blue"><div class="kpi-val b">${{jogos.length}}</div><div class="kpi-lbl">Jogos Filtrados</div></div>
    <div class="kpi kpi-green clickable" id="kpi-prem-${{date}}" onclick="kpiFilter('${{date}}','prem')"><div class="kpi-val g">${{aprem}}</div><div class="kpi-lbl">Alta Confiança</div></div>
    <div class="kpi kpi-yellow clickable" id="kpi-15-${{date}}" onclick="kpiFilter('${{date}}','15')"><div class="kpi-val y">${{a15}}</div><div class="kpi-lbl">Over 1.5</div></div>
    <div class="kpi kpi-teal clickable" id="kpi-esc-${{date}}" onclick="kpiFilter('${{date}}','esc')"><div class="kpi-val t">${{aesc}}</div><div class="kpi-lbl">Over 7.5 Escanteios</div></div>
    <div class="kpi kpi-orange clickable" id="kpi-cart-${{date}}" onclick="kpiFilter('${{date}}','cart')"><div class="kpi-val o">${{acart}}</div><div class="kpi-lbl">Over 2.5 Cartões</div></div>
    ${{taxaDia}}
  </div>
  <div id="kpi-panel-${{date}}" style="display:none"></div>`;

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
        <div class="top-grade-block">
          ${{gradeHtml(d.best_grade)}}
          ${{oddMkt(d)!=='—'?`<span style="font-size:11px;color:var(--yellow);font-family:'JetBrains Mono',monospace;font-weight:700;margin-top:3px">Odd: ${{oddMkt(d)}}</span>`:''}}
        </div>
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
      <td class="mono" style="color:var(--yellow);font-weight:700;font-size:14px">${{oddMkt(d)}}</td>
      <td>${{bar(d.score_15)}}</td><td>${{bar(d.score_esc85)}}</td><td>${{bar(d.score_cards25)}}</td>
      <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
      <td class="mono" style="color:var(--yellow);font-weight:600">${{odd(d.odds_h)}}</td>
      <td class="mono muted">${{odd(d.odds_d)}}</td>
      <td class="mono" style="color:var(--yellow);font-weight:600">${{odd(d.odds_a)}}</td>
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
      <thead><tr><th>Jogo</th><th>Hora</th><th>Confiança</th><th>Mercado</th><th style="color:var(--yellow)">Odd</th><th>Over 1.5</th><th>Esc 8.5</th><th>Cart 2.5</th><th>xG</th><th style="color:var(--yellow)">Casa</th><th style="color:var(--muted)">Empate</th><th style="color:var(--yellow)">Fora</th><th>Placar</th><th>Resultado</th></tr></thead>
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
        <td class="mono" style="color:var(--yellow);font-weight:700;font-size:14px">${{oddMkt(d)}}</td>
        <td>${{bar(d.best_score)}}</td>
        <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
        <td class="mono" style="color:var(--yellow);font-weight:600">${{odd(d.odds_h)}}</td>
        <td class="mono muted">${{odd(d.odds_d)}}</td>
        <td class="mono" style="color:var(--yellow);font-weight:600">${{odd(d.odds_a)}}</td>
        ${{placarCell(d)}}
        <td>${{resBadge(d,mktKey)}}</td>
      </tr>`;
    }}).join('');
    return`<div class="callout ${{calloutClass}}">${{calloutText}}</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Confiança</th><th>Mercado</th><th style="color:var(--yellow)">Odd</th><th>Score</th><th>xG</th><th style="color:var(--yellow)">Casa</th><th style="color:var(--muted)">Empate</th><th style="color:var(--yellow)">Fora</th><th>Placar</th><th>Resultado</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
  }}

  el.innerHTML=`
    <div class="sec-title">🥇 Confiança Alta / Média</div>
    ${{section(premium,'gold','<strong>⭐ Confiança Alta / Média</strong> · Score ≥75% com alta consistência estatística.')}}
    <div class="sec-title">📊 Moderado</div>
    ${{section(boas,'ok','<strong>✓ Moderado</strong> · Score 65–74%. Risco moderado.')}}
    <div class="sec-title">⚠ Arriscado / Evitar</div>
    ${{section(perigosas,'warn','<strong>⚠ Arriscado / Evitar</strong> · Score abaixo de 65%. Alta variância.')}}`;
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
      <td class="mono" style="color:var(--yellow);font-weight:700;font-size:14px">${{odd(d.odd_over15)}}</td>
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
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th style="color:var(--green)">Probabilidade</th><th style="color:var(--yellow)">Odd O1.5</th><th>Placar</th><th>Resultado</th><th>Score</th><th>Confiança</th><th>xG</th><th>Via</th></tr></thead>
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
        <th>Score U3.5</th><th>Confiança</th>
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
        <th>Score 2.5</th><th>Confiança</th><th>Score 3.5</th><th>Média</th>
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
        <thead><tr><th>Jogo</th><th>Hora</th><th>Confiança</th><th>Mercado</th><th>Score</th><th>Status</th></tr></thead>
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
  const mktCards=MERCADOS.filter(m=>pm[m]&&(pm[m].palpites||pm[m].p||0)>0).map(m=>{{
    const s=pm[m];
    const t=s.taxa;
    const c=t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
    return`<div class="hist-mkt-card">
      <div class="hist-mkt-name">${{m}}</div>
      <div class="hist-taxa-val" style="color:${{c}}">${{t!=null?t+'%':'—'}}</div>
      <div class="hist-detail">${{s.acertos||0}}✓ ${{s.erros||0}}✗ / ${{s.palpites||0}} palpites</div>
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
  const histPanel=document.getElementById('panel-historico');
  const histBtn=document.getElementById('btn-historico');
  if(histPanel)histPanel.style.display='none';
  if(histBtn)histBtn.style.color='';
  historicoVisible=false;
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-tab').forEach(t=>t.classList.remove('active'));
  const panel=document.getElementById('day-'+date);
  const tab=document.querySelector(`[data-date="${{date}}"]`);
  if(!panel){{ console.warn('Panel not found for date:',date); return; }}
  panel.classList.add('active');
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
  if(mkt==='visao')          renderVisao(date,jogos);
  else if(mkt==='ranking')   renderRanking(date,jogos);
  else if(mkt==='over15')    renderOver15(date,jogos);
  else if(mkt==='over25')    renderOver25(date,jogos);
  else if(mkt==='escanteios')renderEsc(date,jogos);
  else if(mkt==='cartoes')   renderCart(date,jogos);
  else if(mkt==='historico_dia') renderHistoricoDia(date,jogos);
}}

// Init
renderGlobalKpis();

// Ordenar datas corretamente (DD-MM-YYYY)
const dates=Object.keys(ALL_DATA).sort((a,b)=>{{
  const [da,ma,ya]=a.split('-').map(Number);
  const [db,mb,yb]=b.split('-').map(Number);
  return new Date(ya,ma-1,da)-new Date(yb,mb-1,db);
}});

// Aguardar DOM completo antes de renderizar
window.addEventListener('DOMContentLoaded',function(){{
  if(dates.length){{
    const lastDate=dates[dates.length-1];
    switchDate(lastDate);
  }}
}});

// Fallback se DOMContentLoaded já disparou
if(document.readyState==='complete'||document.readyState==='interactive'){{
  setTimeout(function(){{
    if(dates.length&&!activeDate){{
      const lastDate=dates[dates.length-1];
      switchDate(lastDate);
    }}
  }},100);
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
btn.style.cssText='min-width:100px;cursor:pointer;height:40px;justify-content:center';
btn.innerHTML='<span class="dt-label">📈 Histórico</span><span style="font-size:9px;color:var(--muted);margin-top:2px">Visão geral</span>';
btn.onclick=showHistoricoGlobal;
dateBar.appendChild(btn);

const calBtn=document.createElement('div');
calBtn.className='date-tab';
calBtn.style.cssText='min-width:100px;cursor:pointer;border-color:rgba(249,115,22,.3);height:40px;justify-content:center';
calBtn.innerHTML='<span class="dt-label">📅 Data</span><span style="font-size:9px;color:var(--accent);margin-top:2px">selecionar</span>';
calBtn.onclick=openCal;
dateBar.appendChild(calBtn);
</script>
</body>
</html>'''

if __name__ == '__main__':
    gerar_site()
