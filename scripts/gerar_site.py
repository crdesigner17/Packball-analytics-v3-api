"""
WinMetrics — Gerador de Site v3.1
- Resultados integrados: linhas verde/vermelho/amarelo em cada tabela
- Placar nos cards Top 5
- KPI de assertividade no header
- Aba Histórico com gráfico de evolução por mercado
"""
import json, os
from datetime import datetime
from ligas_config import blocked_name, favorite_league_names

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
OUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'index.html')
FAVORITE_LEAGUES = favorite_league_names()

def filter_favorite_leagues(day_data):
    if not FAVORITE_LEAGUES or not isinstance(day_data, dict):
        return day_data
    filtered = dict(day_data)
    filtered['jogos'] = [
        j for j in day_data.get('jogos', [])
        if (
            not isinstance(j, dict) or
            (
                j.get('liga') in FAVORITE_LEAGUES and
                not blocked_name(' '.join(str(j.get(k, '')) for k in ('liga', 'jogo', 'home', 'away')))
            )
        )
    ]
    return filtered

def load_index():
    path = os.path.join(DATA_DIR, 'index.json')
    if not os.path.exists(path): return []
    with open(path, encoding='utf-8') as f: return json.load(f)

def load_day(date_str):
    path = os.path.join(DATA_DIR, f'{date_str}.json')
    if not os.path.exists(path): return None
    with open(path, encoding='utf-8') as f:
        return filter_favorite_leagues(json.load(f))

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

def sanitize_for_site(value):
    """Remove símbolos visuais antigos do JSON embutido no HTML."""
    if isinstance(value, dict):
        return {k: sanitize_for_site(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_for_site(v) for v in value]
    if isinstance(value, str):
        replacements = {
            '✅': '', '⏳': '', '🏆': '', '📋': '', '📊': '', '📅': '', '🎯': '',
            '🟢': '', '🟡': '', '🔵': '', '🟠': '', '🔒': '', '🕐': '', '⭐': '',
            '🥇': '', '✗': '', '✓': '', '⚠': '', '🚩': '', '🟨': '',
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        return ' '.join(value.split())
    return value

def day_panel_html(d, day_data):
    jogos  = day_data.get('jogos', [])
    n15    = sum(1 for j in jogos if j['score_15'] >= 85 and j['passou_filtro'])
    nesc   = sum(1 for j in jogos if j['score_esc75'] >= 75)
    ncart  = sum(1 for j in jogos if j['score_cards25'] >= 75)
    nprem  = sum(1 for j in jogos if (j.get('palpite_grade') or j.get('best_grade')) in ('A+', 'A'))
    fmt, wd = fmt_date(d)
    confirmado = day_data.get('resultado_confirmado', False)

    return f'''
<div id="day-{d}" class="day-panel">
  <div class="main">
    <div id="mkt-{d}-visao"        class="mkt-panel active"></div>
    <div id="mkt-{d}-ranking"      class="mkt-panel"></div>
    <div id="mkt-{d}-bilhetes"     class="mkt-panel"></div>
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

        is_today = (day_date == today)
        today_cls = ' today' if is_today else ''
        date_tabs_html.append(f'''<div class="date-strip-item{today_cls}" data-date="{d}" onclick="switchDate('{d}')">
  <span class="date-strip-dow">{wd}</span>
  <span class="date-strip-day">{fmt.replace('/',  '.')}</span>
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
        all_data_json=json.dumps(sanitize_for_site(all_data), ensure_ascii=False),
        globais_json=json.dumps(globais, ensure_ascii=False),
        n_dates=len(index),
    )
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"docs/index.html gerado - {len(index)} datas - {updated}")

def build_html(updated, date_tabs_html, day_panels_html, all_data_json, globais_json, n_dates):
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WinMetrics - AI Sports Analytics</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/lucide/0.363.0/umd/lucide.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#060B14;--s1:#0B1120;--s2:#111827;--s3:#131C31;--s4:#1A2338;
  --border:rgba(148,163,184,.16);
  --accent:#2563EB;--accent2:#7C3AED;--blue:#3B82F6;--green:#00C896;
  --green2:#10B981;--orange:#F59E0B;--red:#EF4444;--yellow:#F59E0B;--teal:#00C896;
  --purple:#7C3AED;--purple2:#8B5CF6;--pink:#8B5CF6;--text:#F8FAFC;--text2:#E2E8F0;--muted:#94A3B8;
  --dim:#64748B;--aplus:#00C896;
  --nav-h:56px;--date-strip-h:53px;--market-bar-h:42px;--top-gap:8px;
}}
[data-theme="light"]{{
  --bg:#F8FAFC;--s1:#FFFFFF;--s2:#F1F5F9;--s3:#E2E8F0;--s4:#CBD5E1;--border:#CBD5E1;
  --text:#0F172A;--text2:#1E293B;--muted:#64748B;--dim:#94A3B8;
}}
[data-theme="light"] .navbar{{background:rgba(255,255,255,.96);border-bottom-color:rgba(0,0,0,.08)}}
[data-theme="light"] .navbar-logo-name{{color:#0F172A}}
[data-theme="light"] .navbar-link{{color:rgba(15,23,42,.58)}}
[data-theme="light"] .navbar-link:hover{{color:#0F172A;background:rgba(37,99,235,.06)}}
[data-theme="light"] .navbar-link.active{{color:#2563eb;background:rgba(37,99,235,.08)}}
[data-theme="light"] .navbar-theme{{color:rgba(15,23,42,.72);border-color:rgba(15,23,42,.14);background:rgba(15,23,42,.04)}}
[data-theme="light"] .navbar-theme:hover{{color:#0F172A;background:rgba(37,99,235,.08)}}
[data-theme="light"] .sidebar{{background:#ffffff;border-right-color:#e2e6f3}}
[data-theme="light"] .date-strip{{background:#ffffff}}
[data-theme="light"] .mkt-cat-bar{{background:#F1F5F9}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;font-size:14px;min-height:100vh;line-height:1.5;-webkit-font-smoothing:antialiased;letter-spacing:.01em}}
h1,h2,h3,h4,h5,h6{{font-family:'Inter',sans-serif;font-weight:700}}
button,input,select{{font-family:'Inter',sans-serif}}

/* NAVBAR */
.navbar{{
  background:rgba(6,11,20,.92);backdrop-filter:blur(12px);
  border-bottom:1px solid rgba(59,130,246,.15);
  padding:0 24px;height:var(--nav-h);gap:18px;
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:200;
  box-shadow:0 2px 20px rgba(0,0,0,.5);
}}
.navbar-logo{{display:flex;align-items:center;gap:14px;text-decoration:none;flex:0 0 auto;min-width:max-content}}
.navbar-logo-icon{{width:32px;height:32px}}
.navbar-logo-text{{display:flex;flex-direction:column;line-height:1}}
.navbar-logo-name{{font-size:16px;font-weight:700;color:#fff;letter-spacing:-.3px}}
.navbar-logo-sub{{font-size:9px;color:var(--blue);letter-spacing:2px;font-weight:500;text-transform:uppercase}}
.navbar-links{{display:flex;align-items:center;justify-content:center;gap:4px;flex:1 1 auto;min-width:0;overflow:hidden}}
.navbar-link{{
  height:34px;min-width:0;max-width:132px;padding:0 12px;font-size:clamp(11px,1vw,13px);font-weight:500;color:rgba(255,255,255,.65);
  cursor:pointer;border-radius:7px;transition:all .18s;white-space:nowrap;line-height:1;
  display:inline-flex;align-items:center;justify-content:center;gap:6px;letter-spacing:0;
  font-family:'Inter',sans-serif;flex:0 1 auto;text-align:center;overflow:hidden;text-overflow:ellipsis;
}}
.navbar-link:hover{{color:#fff;background:rgba(255,255,255,.08);transform:translateY(-1px)}}
.navbar-link.active{{color:#fff;background:linear-gradient(135deg,rgba(37,99,235,.28),rgba(124,58,237,.22));font-weight:600}}

.navbar-link svg{{width:14px;height:14px;opacity:.7}}
.navbar-actions{{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex:0 0 auto}}
.navbar-theme{{
  width:34px;height:34px;border-radius:8px;border:1px solid rgba(255,255,255,.12);
  background:rgba(255,255,255,.05);cursor:pointer;display:flex;align-items:center;
  justify-content:center;color:rgba(255,255,255,.6);transition:all .15s;font-size:14px;
}}
.navbar-theme:hover{{background:rgba(255,255,255,.1);color:#fff}}
.navbar-btn-entrar{{
  height:34px;min-width:0;padding:0 14px;font-size:clamp(11px,1vw,13px);font-weight:600;line-height:1;
  border:1px solid rgba(59,130,246,.5);color:#60a5fa;
  border-radius:8px;cursor:pointer;transition:all .2s;
  background:rgba(59,130,246,.08);display:inline-flex;align-items:center;justify-content:center;gap:6px;
  letter-spacing:0;white-space:nowrap;text-align:center;overflow:hidden;text-overflow:ellipsis;
}}
.navbar-btn-entrar:hover{{background:rgba(37,99,235,.18);border-color:var(--blue);color:#BFDBFE;transform:translateY(-1px)}}
.navbar-btn-criar{{
  height:34px;min-width:0;padding:0 16px;font-size:clamp(11px,1vw,13px);font-weight:600;color:#fff;line-height:1;
  background:linear-gradient(135deg,#2563EB 0%,#7C3AED 100%);
  border:none;border-radius:8px;cursor:pointer;transition:all .2s;
  display:inline-flex;align-items:center;justify-content:center;gap:7px;white-space:nowrap;text-align:center;
  box-shadow:0 0 24px rgba(37,99,235,.35),inset 0 1px 0 rgba(255,255,255,.1);
  letter-spacing:0;position:relative;overflow:hidden;text-overflow:ellipsis;
}}
.navbar-btn-criar::before{{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,#3B82F6 0%,#8B5CF6 100%);
  opacity:0;transition:opacity .2s;
}}
.navbar-btn-criar:hover{{box-shadow:0 0 32px rgba(37,99,235,.55),inset 0 1px 0 rgba(255,255,255,.15);transform:translateY(-1px)}}
.navbar-btn-criar:hover::before{{opacity:1}}
.navbar-link i,.navbar-btn-entrar i,.navbar-btn-criar i,.navbar-theme i{{
  display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;
}}
.navbar-theme svg{{
  width:15px;height:15px;display:block;stroke:currentColor;fill:none;flex-shrink:0;opacity:1;visibility:visible;
}}

/* HEADER */
.header{{
  background:linear-gradient(135deg,#060B14,#0B1120);
  border-bottom:1px solid var(--border);padding:12px 28px;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  position:sticky;top:0;z-index:100;box-shadow:0 4px 24px rgba(0,0,0,.4);
  flex-wrap:wrap;
}}
.logo{{display:flex;align-items:center;gap:10px}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 0 16px rgba(37,99,235,.32)}}
.logo-text .name{{font-size:17px;font-weight:700;letter-spacing:-.3px}}
.logo-text .name em{{font-style:normal;color:var(--accent)}}
.logo-text .sub{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.header-right{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.badge{{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:600;font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.badge.validated{{background:rgba(0,200,150,.1);color:var(--green);border:1px solid rgba(0,200,150,.22)}}
.badge.version{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.badge.updated{{background:rgba(100,116,139,.1);color:var(--muted);border:1px solid var(--border);font-size:9px}}

/* DATE TABS */
.date-bar{{background:var(--s1);border-bottom:1px solid var(--border);display:flex;overflow-x:auto;gap:4px;padding:8px 16px;scrollbar-width:thin;scrollbar-color:var(--border) transparent;justify-content:center;position:sticky;top:126px;z-index:95}}
.date-bar::-webkit-scrollbar{{height:3px}}
.date-bar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.date-tab{{padding:7px 16px;font-size:12px;font-weight:600;color:var(--muted);cursor:pointer;border:1px solid var(--border);border-radius:7px;white-space:nowrap;transition:all .15s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;background:var(--s2);height:40px;min-width:80px}}
.date-tab:hover{{color:var(--text);border-color:var(--accent);transform:translateY(-1px);box-shadow:0 2px 12px rgba(37,99,235,.18)}}
.date-tab:active{{transform:translateY(0)}}
.date-tab.active{{color:var(--accent);border-color:var(--accent);background:rgba(37,99,235,.08)}}
.dt-label{{font-weight:700;font-size:12px;line-height:1;text-align:center}}
.dt-kpis{{display:flex;gap:3px;flex-wrap:wrap;justify-content:center}}
.dt-kpi{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px}}
.dt-kpi.g{{background:rgba(0,200,150,.1);color:var(--green)}}
.dt-kpi.b{{background:rgba(59,130,246,.1);color:var(--blue)}}
.dt-kpi.o{{background:rgba(245,158,11,.1);color:var(--orange)}}
.dt-kpi.prem{{background:rgba(0,200,150,.12);color:var(--aplus)}}

/* MKT BAR */
.mkt-bar{{background:var(--s1);border-bottom:1px solid var(--border);display:flex;justify-content:center;position:sticky;top:174px;z-index:90}}
.mkt-tabs{{display:flex;overflow-x:auto;gap:0;padding:0 6px;scrollbar-width:none}}
.mkt-tabs::-webkit-scrollbar{{display:none}}
.mkt-tab{{padding:11px 16px;font-size:13px;font-weight:500;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;transition:all .15s;display:flex;align-items:center;gap:5px}}
.mkt-tab:hover{{color:var(--text);background:rgba(255,255,255,.04);border-radius:6px 6px 0 0}}
.mkt-tab.active{{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}}
.cnt{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:2px 5px;border-radius:4px}}
.cnt.b{{color:var(--blue);background:rgba(59,130,246,.12)}}
.cnt.g{{color:var(--green);background:rgba(0,200,150,.12)}}

/* MAIN */
.main{{padding:20px 24px;max-width:1500px;margin:0 auto}}

/* KPI ROW */
.kpi-row{{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:16px;padding:10px 0;border-bottom:1px solid var(--border)}}
.kpi{{background:var(--s2);border:1px solid var(--border);border-radius:10px;padding:12px 18px;text-align:center;min-width:120px;transition:all .2s;cursor:default}}
.kpi:hover{{border-color:var(--accent)}}
.kpi.clickable{{cursor:pointer}}
.kpi.clickable:hover{{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,.4)}}
.kpi.clickable:active{{transform:translateY(0);box-shadow:none}}
.kpi.active{{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,.4)}}
.kpi.kpi-blue{{border-color:rgba(59,130,246,.3);background:rgba(59,130,246,.06)}}
.kpi.kpi-blue.active,.kpi.kpi-blue:hover{{border-color:var(--blue);background:rgba(59,130,246,.12)}}
.kpi.kpi-green{{border-color:rgba(0,200,150,.32);background:rgba(0,200,150,.06)}}
.kpi.kpi-green.active,.kpi.kpi-green:hover{{border-color:var(--green);background:rgba(0,200,150,.12)}}
.kpi.kpi-yellow{{border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.06)}}
.kpi.kpi-yellow.active,.kpi.kpi-yellow:hover{{border-color:var(--yellow);background:rgba(245,158,11,.12)}}
.kpi.kpi-teal{{border-color:rgba(0,200,150,.3);background:rgba(0,200,150,.06)}}
.kpi.kpi-teal.active,.kpi.kpi-teal:hover{{border-color:var(--teal);background:rgba(0,200,150,.12)}}
.kpi.kpi-orange{{border-color:rgba(245,158,11,.3);background:rgba(245,158,11,.06)}}
.kpi.kpi-orange.active,.kpi.kpi-orange:hover{{border-color:var(--orange);background:rgba(245,158,11,.12)}}
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
.sec-title svg,.sec-title i{{width:14px;height:14px;flex-shrink:0}}
.inline-icon{{width:13px;height:13px;display:inline-flex;align-items:center;justify-content:center;vertical-align:-2px;flex-shrink:0}}
.inline-icon svg{{width:13px;height:13px;display:block}}

/* TOP CARDS */
.top-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-bottom:20px;align-items:stretch;max-width:100%;min-width:0}}
.top-grid::-webkit-scrollbar{{height:3px}}
.top-grid::-webkit-scrollbar-thumb{{background:var(--accent);border-radius:2px}}
.top-card{{width:100%;min-width:0;background:var(--s1);border:1px solid var(--border);border-radius:11px;padding:14px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s}}
.top-card:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3)}}
.top-card:active{{transform:translateY(0);box-shadow:none}}
/* resultado overlay no card */
.tc-hit::after{{content:'';position:absolute;inset:0;background:rgba(0,200,150,.06);border:1px solid rgba(0,200,150,.25);border-radius:11px;pointer-events:none}}
.tc-miss::after{{content:'';position:absolute;inset:0;background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.25);border-radius:11px;pointer-events:none}}
.top-rank{{position:absolute;top:10px;right:12px;font-size:18px;font-weight:700;color:rgba(255,255,255,.04);font-family:'JetBrains Mono',monospace}}
.top-liga{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.7px;margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:24px}}
.top-jogo{{font-size:13px;font-weight:700;margin-bottom:2px;padding-right:22px;line-height:1.3;overflow-wrap:anywhere}}
.top-hora{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:8px}}
.top-mkt{{font-size:10px;font-weight:700;color:var(--accent);margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}}
.top-bottom{{display:flex;align-items:center;justify-content:space-between;margin-top:6px}}
.top-score{{font-size:30px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1}}
.top-grade-block{{display:flex;flex-direction:column;align-items:flex-end;gap:3px}}
.top-note{{font-size:10px;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px solid var(--border);line-height:1.55}}
/* placar no card */
.top-placar{{display:flex;align-items:center;gap:6px;margin-top:7px;padding:6px 10px;border-radius:6px;font-family:'JetBrains Mono',monospace}}
.top-placar.hit{{background:rgba(0,200,150,.1);border:1px solid rgba(0,200,150,.22)}}
.top-placar.miss{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2)}}
.top-placar.pending{{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.18)}}
.top-placar .ft{{font-size:15px;font-weight:700}}
.top-placar .ht{{font-size:10px;color:var(--muted)}}
.top-placar .icon{{font-size:13px}}

/* GRADE PILLS */
.grade{{display:inline-block;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;font-family:'Inter',sans-serif;white-space:nowrap}}
.grade.Aplus{{background:rgba(0,200,150,.12);color:var(--green);border:1px solid rgba(0,200,150,.3)}}
.grade.A{{background:rgba(245,158,11,.1);color:var(--yellow);border:1px solid rgba(245,158,11,.3)}}
.grade.B{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.grade.C{{background:rgba(124,58,237,.1);color:var(--purple2);border:1px solid rgba(124,58,237,.24)}}
.grade.D{{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}}

/* RESULT ROW COLORS */
.row-hit{{background:rgba(0,200,150,.05)!important;border-left:3px solid var(--green)}}
.row-miss{{background:rgba(239,68,68,.05)!important;border-left:3px solid var(--red)}}
.row-pending{{border-left:3px solid rgba(245,158,11,.4)}}
.res-badge{{display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.res-badge svg{{width:11px;height:11px;flex-shrink:0}}
.res-badge.hit{{background:rgba(0,200,150,.12);color:var(--green);border:1px solid rgba(0,200,150,.25)}}
.res-badge.miss{{background:rgba(239,68,68,.12);color:var(--red);border:1px solid rgba(239,68,68,.25)}}
.res-badge.pending{{background:rgba(59,130,246,.08);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.placar-cell{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700}}
.placar-ht{{font-size:10px;color:var(--muted)}}

/* CONF/VIA PILLS */
.conf{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace}}
.conf.MA{{background:rgba(0,200,150,.1);color:var(--green);border:1px solid rgba(0,200,150,.22)}}
.conf.A{{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.2)}}
.conf.M{{background:rgba(245,158,11,.1);color:var(--orange);border:1px solid rgba(245,158,11,.22)}}
.conf.B{{background:rgba(100,116,139,.1);color:var(--muted);border:1px solid var(--border)}}
.conf.R{{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.2)}}
.via{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700}}
.via.v1{{color:var(--yellow)}}.via.v2{{color:var(--blue)}}.via.v3{{color:var(--green)}}.via.vx{{color:var(--dim)}}
.elite{{background:rgba(37,99,235,.14);color:var(--accent);border:1px solid rgba(37,99,235,.3);font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;margin-left:4px}}

/* TABLE */
.tbl-wrap{{width:100%;max-width:100%;min-width:0;overflow-x:auto;overscroll-behavior-x:contain;border-radius:9px;border:1px solid var(--border);margin-bottom:18px}}
table{{width:100%;min-width:760px;border-collapse:collapse;font-size:13px}}
thead th{{background:var(--s2);padding:9px 12px;text-align:left;font-size:10px;font-weight:600;letter-spacing:.7px;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);white-space:nowrap;font-family:'Inter',sans-serif}}
tbody tr{{border-bottom:1px solid rgba(148,163,184,.12);transition:background .1s}}
tbody tr:last-child{{border-bottom:none}}
tbody tr:hover{{background:rgba(255,255,255,.018)}}
tbody td{{padding:9px 12px;vertical-align:middle}}
.jogo-main{{font-weight:600;font-size:13px}}
.jogo-sub{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-top:1px}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:12px}}
.muted{{color:var(--muted)}}
.td-conf{{text-align:center}}
.td-palpite{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}}

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
.callout{{padding:11px 14px;border-radius:7px;margin-bottom:14px;font-size:13px;line-height:1.6;border-left:3px solid;font-family:'Inter',sans-serif}}
.callout.info{{background:rgba(59,130,246,.06);border-color:var(--blue)}}
.callout.warn{{background:rgba(245,158,11,.06);border-color:var(--orange)}}
.callout.ok{{background:rgba(0,200,150,.06);border-color:var(--green)}}
.callout.gold{{background:rgba(0,200,150,.06);border-color:var(--aplus)}}
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
.hist-page{{display:flex;flex-direction:column;gap:12px}}
.hist-hero{{
  background:linear-gradient(135deg,rgba(37,99,235,.16),rgba(124,58,237,.10) 48%,rgba(0,200,150,.08));
  border:1px solid var(--border);border-radius:12px;padding:14px 16px;
  display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,360px) auto;gap:14px;align-items:center;
  box-shadow:0 10px 28px rgba(0,0,0,.22);overflow:hidden;position:relative;
}}
.hist-hero::before{{content:'';position:absolute;inset:0;border-top:3px solid rgba(0,200,150,.48);pointer-events:none}}
.hist-kicker{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1.4px;color:var(--green);margin-bottom:4px}}
.hist-title{{font-size:20px;font-weight:800;line-height:1.15;letter-spacing:0;color:var(--text)}}
.hist-subtitle{{font-size:11px;color:var(--muted);margin-top:5px;max-width:620px}}
.hist-hero-insights{{display:grid;grid-template-columns:1fr;gap:7px}}
.hist-insight{{background:rgba(255,255,255,.035);border:1px solid rgba(148,163,184,.14);border-radius:9px;padding:9px 10px;min-width:0}}
.hist-insight-label{{font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}}
.hist-insight-value{{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:12px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-insight-rate{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:900;flex-shrink:0}}
.hist-score-card{{height:100%;min-width:126px;background:linear-gradient(135deg,rgba(0,200,150,.13),rgba(37,99,235,.10));border:1px solid rgba(0,200,150,.22);border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;justify-content:center;position:relative;overflow:hidden}}
.hist-score-card::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--green)}}
.hist-score-label{{font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px}}
.hist-score-val{{font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:900;line-height:1}}
.hist-score-note{{font-size:10px;color:var(--text2);font-family:'JetBrains Mono',monospace;font-weight:700;margin-top:5px;white-space:nowrap}}
.hist-visual{{
  background:linear-gradient(135deg,rgba(31,32,56,.94),rgba(19,28,49,.96));
  border:1px solid rgba(139,92,246,.18);border-radius:16px;padding:14px;
  display:grid;grid-template-columns:220px minmax(0,1fr) 240px;gap:14px;align-items:stretch;
  box-shadow:0 14px 36px rgba(0,0,0,.28);overflow:hidden;
}}
.hist-visual-card{{background:rgba(255,255,255,.025);border:1px solid rgba(148,163,184,.10);border-radius:12px;padding:12px;min-width:0}}
.hist-visual-title{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--text2);margin-bottom:10px}}
.hist-radial-wrap{{display:grid;grid-template-columns:118px minmax(0,1fr);gap:12px;align-items:center}}
.hist-radial{{width:118px;height:118px;border-radius:50%;position:relative;background:radial-gradient(circle at center,rgba(31,32,56,1) 0 40%,transparent 41%)}}
.hist-radial-ring{{position:absolute;inset:var(--inset);border-radius:50%;background:conic-gradient(var(--ring-color) 0 var(--ring-deg),rgba(255,255,255,.07) var(--ring-deg) 360deg)}}
.hist-radial-ring::after{{content:'';position:absolute;inset:8px;border-radius:50%;background:rgb(31,32,56)}}
.hist-radial-core{{position:absolute;inset:39px;border-radius:50%;background:rgba(17,24,39,.92);border:1px solid rgba(148,163,184,.14);display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:900;color:var(--text)}}
.hist-vlegend{{display:flex;flex-direction:column;gap:7px;min-width:0}}
.hist-vlegend-row{{display:grid;grid-template-columns:8px minmax(0,1fr) 42px;gap:7px;align-items:center;font-size:10px;color:var(--muted)}}
.hist-vdot{{width:8px;height:8px;border-radius:50%;background:var(--dot)}}
.hist-vlegend-name{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text2);font-weight:700}}
.hist-vlegend-rate{{font-family:'JetBrains Mono',monospace;font-weight:900;text-align:right;color:var(--rate-color)}}
.hist-viz-svg{{width:100%;height:118px;display:block;overflow:visible}}
.hist-viz-axis{{stroke:rgba(148,163,184,.12);stroke-width:1}}
.hist-viz-line{{fill:none;stroke:url(#histLineGrad);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 8px rgba(139,92,246,.45))}}
.hist-viz-area{{fill:url(#histAreaGrad);opacity:.8}}
.hist-market-mini{{display:flex;flex-direction:column;gap:8px}}
.hist-market-mini-row{{display:grid;grid-template-columns:minmax(0,1fr) 46px;gap:8px;align-items:center}}
.hist-market-mini-name{{font-size:10px;font-weight:700;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-market-mini-rate{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:900;text-align:right}}
.hist-market-mini-track{{grid-column:1/3;height:5px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden;margin-top:-4px}}
.hist-market-mini-fill{{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--purple2))}}
.hist-legend-note{{margin-top:10px;padding-top:9px;border-top:1px solid rgba(148,163,184,.12);font-size:9px;line-height:1.45;color:var(--muted)}}
.hist-legend-note strong{{color:var(--text2);font-weight:800}}
.hist-summary-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}}
.hist-summary-card{{background:var(--s1);border:1px solid var(--border);border-radius:9px;padding:10px 11px;min-width:0}}
.hist-summary-label{{font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-summary-value{{font-family:'JetBrains Mono',monospace;font-size:21px;font-weight:800;line-height:1;color:var(--text)}}
.hist-summary-note{{font-size:9px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-audit-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;align-items:start}}
.hist-audit-panel{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:11px;min-width:0;position:relative;overflow:hidden}}
.hist-audit-panel.pro::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(135deg,#2563eb,#7c3aed)}}
.hist-audit-main{{display:grid;grid-template-columns:88px minmax(0,1fr);gap:10px;align-items:center;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.hist-audit-score{{height:68px;border-radius:9px;background:linear-gradient(135deg,rgba(37,99,235,.14),rgba(0,200,150,.08));border:1px solid rgba(148,163,184,.14);display:flex;flex-direction:column;align-items:center;justify-content:center}}
.hist-audit-panel.pro .hist-audit-score{{background:linear-gradient(135deg,rgba(37,99,235,.24),rgba(124,58,237,.18));border-color:rgba(139,92,246,.32)}}
.hist-audit-val{{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:800;line-height:1}}
.hist-audit-lbl{{font-size:8px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.7px;margin-top:3px}}
.hist-audit-title{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.8px;color:var(--text)}}
.hist-audit-copy{{font-size:9px;color:var(--muted);line-height:1.35;margin-top:3px}}
.hist-breakdown{{display:flex;flex-direction:column;gap:5px}}
.hist-break-row{{display:grid;grid-template-columns:minmax(0,1fr) 64px;gap:8px;align-items:center;padding:7px 8px;border-bottom:1px solid rgba(148,163,184,.1);border-radius:7px;border-left:3px solid transparent}}
.hist-break-row:last-child{{border-bottom:none}}
.hist-break-row.tone-alta{{background:linear-gradient(90deg,rgba(0,200,150,.10),transparent);border-left-color:var(--green)}}
.hist-break-row.tone-media{{background:linear-gradient(90deg,rgba(59,130,246,.10),transparent);border-left-color:var(--blue)}}
.hist-break-row.tone-moderado{{background:linear-gradient(90deg,rgba(245,158,11,.10),transparent);border-left-color:var(--orange)}}
.hist-break-row.tone-pro{{background:linear-gradient(90deg,rgba(37,99,235,.12),rgba(124,58,237,.08),transparent);border-left-color:var(--purple2)}}
.hist-break-name{{font-size:11px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-break-detail{{font-size:10px;color:var(--text2);font-family:'JetBrains Mono',monospace;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:700}}
.hist-break-rate{{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:900;text-align:right}}
.hist-break-empty{{font-size:10px;color:var(--muted);text-align:right}}
.hist-layout{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:14px;align-items:start}}
.hist-panel{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:14px;min-width:0}}
.hist-panel-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px;border-bottom:1px solid var(--border);padding-bottom:10px}}
.hist-panel-title{{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--text)}}
.hist-panel-note{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;white-space:nowrap}}
.hist-market-list{{display:flex;flex-direction:column;gap:8px}}
.hist-market-row{{display:grid;grid-template-columns:30px minmax(0,1fr) 86px;gap:10px;align-items:center;padding:10px;border:1px solid rgba(148,163,184,.12);border-radius:9px;background:rgba(255,255,255,.018)}}
.hist-market-row:hover{{border-color:rgba(59,130,246,.38);background:rgba(59,130,246,.035)}}
.hist-rank{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);font-weight:800;text-align:center}}
.hist-mkt-name{{font-size:13px;color:var(--text);font-weight:700;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-detail{{font-size:10px;color:var(--muted);margin-top:3px;font-family:'JetBrains Mono',monospace}}
.hist-rate{{text-align:right}}
.hist-taxa-val{{font-size:21px;font-weight:800;font-family:'JetBrains Mono',monospace;line-height:1}}
.hist-rate-label{{font-size:9px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.8px;margin-top:2px}}
.hist-bar-track{{height:5px;background:rgba(255,255,255,.06);border-radius:99px;margin-top:8px;overflow:hidden;grid-column:2/4}}
.hist-bar-fill{{height:100%;border-radius:99px}}
.hist-days{{display:flex;flex-direction:column;gap:8px}}
.day-hist-row{{display:grid;grid-template-columns:58px minmax(0,1fr) 92px;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid rgba(148,163,184,.12)}}
.day-hist-row:last-child{{border-bottom:none}}
.day-hist-date{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--text);font-weight:800}}
.day-hist-bar{{height:22px;background:rgba(255,255,255,.045);border-radius:7px;overflow:hidden;position:relative}}
.day-hist-fill{{height:100%;border-radius:7px;display:flex;align-items:center;padding:0 7px;font-size:10px;font-weight:800;font-family:'JetBrains Mono',monospace;color:#fff;min-width:2px}}
.day-hist-info{{font-family:'JetBrains Mono',monospace;font-size:11px;text-align:right;font-weight:800}}
.day-hist-detail{{display:block;color:var(--muted);font-size:9px;font-weight:600;margin-top:2px}}
.hist-spark{{display:flex;align-items:flex-end;gap:4px;height:42px;margin-top:10px;padding-top:8px;border-top:1px solid var(--border)}}
.hist-spark-bar{{flex:1;min-width:5px;border-radius:3px 3px 0 0;opacity:.95}}

/* BILHETES */
.bilhete-dia{{background:linear-gradient(135deg,rgba(0,200,150,.08),rgba(37,99,235,.06));border:2px solid rgba(0,200,150,.4);border-radius:13px;padding:18px;margin-bottom:20px;position:relative;overflow:hidden}}
.bilhete-dia::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--green),var(--teal),var(--blue))}}
.bilhete-dia-badge{{display:inline-flex;align-items:center;gap:6px;background:rgba(0,200,150,.15);border:1px solid rgba(0,200,150,.3);border-radius:6px;padding:4px 10px;font-size:11px;font-weight:700;color:var(--green);margin-bottom:10px;font-family:'JetBrains Mono',monospace;letter-spacing:.5px}}
.bilhete-card{{background:var(--s1);border:1px solid var(--border);border-radius:11px;padding:16px;margin-bottom:14px;position:relative;overflow:hidden;transition:all .2s}}
.bilhete-card:hover{{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,.3)}}
.bilhete-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.bilhete-premium::before{{background:linear-gradient(90deg,var(--green),var(--teal))}}
.bilhete-equilibrado::before{{background:linear-gradient(90deg,var(--yellow),var(--orange))}}
.bilhete-conservador::before{{background:linear-gradient(90deg,var(--blue),var(--purple))}}
.bilhete-win::after{{content:'';position:absolute;inset:0;background:rgba(0,200,150,.04);border:1px solid rgba(0,200,150,.2);border-radius:11px;pointer-events:none}}
.bilhete-loss::after{{content:'';position:absolute;inset:0;background:rgba(239,68,68,.04);border:1px solid rgba(239,68,68,.2);border-radius:11px;pointer-events:none}}
.bilhete-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px}}
.bilhete-title{{font-size:13px;font-weight:700;color:var(--text)}}
.bilhete-odd-total{{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:var(--yellow)}}
.bilhete-odd-label{{font-size:10px;color:var(--muted);margin-top:1px;text-align:right}}
.bilhete-row{{display:flex;align-items:center;gap:0;padding:7px 0;border-bottom:1px solid rgba(35,40,64,.5)}}
.bilhete-row:last-child{{border-bottom:none}}
.bilhete-num{{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);width:22px;flex-shrink:0}}
.bilhete-jogo{{flex:1;font-size:12px;font-weight:600;min-width:0;padding-right:8px}}
.bilhete-liga{{font-size:10px;color:var(--muted)}}
.bilhete-mkt{{font-size:10px;color:var(--accent);font-weight:700;width:80px;flex-shrink:0;text-align:left;padding-right:8px}}
.bilhete-odd-val{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:var(--yellow);width:48px;flex-shrink:0;text-align:center}}
.bilhete-score-bar{{width:100px;flex-shrink:0;padding-right:8px}}
.bilhete-res{{width:80px;flex-shrink:0;text-align:right}}
.bilhete-footer{{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:10px;border-top:1px solid var(--border);flex-wrap:wrap;gap:6px}}
.bilhete-sels{{font-size:11px;color:var(--muted)}}
.bilhete-status{{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700}}

/* PANELS */
.day-panel{{display:none}}.day-panel.active{{display:block}}
.mkt-panel{{display:none;min-width:0;max-width:100%}}.mkt-panel.active{{display:block}}
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
.cal-day.confirmed{{background:rgba(0,200,150,.08);border-color:rgba(0,200,150,.2);color:var(--green)}}
.cal-day.confirmed:hover{{background:rgba(0,200,150,.15);border-color:var(--green)}}
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


/* SIDEBAR */
.app-layout{{display:flex;gap:var(--top-gap);min-height:calc(100vh - var(--nav-h));padding-top:var(--top-gap);background:var(--bg)}}
.sidebar{{
  width:220px;flex-shrink:0;background:var(--s1);
  border-right:1px solid var(--border);
  position:sticky;top:calc(var(--nav-h) + var(--top-gap));height:calc(100vh - var(--nav-h) - var(--top-gap));
  overflow-y:auto;z-index:80;
  display:flex;flex-direction:column;
  padding:12px 0;border-radius:0 10px 10px 0;
}}
.sidebar::-webkit-scrollbar{{width:3px}}
.sidebar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.sidebar-section{{padding:0 8px;margin-bottom:4px}}
.sidebar-label{{
  font-size:10px;font-weight:700;color:var(--muted);
  letter-spacing:1.2px;text-transform:uppercase;
  padding:8px 10px 4px;
}}
.sidebar-item{{
  display:flex;align-items:center;gap:10px;
  padding:9px 12px;border-radius:8px;
  font-size:13px;font-weight:500;color:var(--muted);
  cursor:pointer;transition:all .15s;margin-bottom:2px;
  font-family:'Inter',sans-serif;white-space:nowrap;
}}
.sidebar-item:hover{{color:var(--text);background:rgba(255,255,255,.05)}}
.sidebar-item.active{{
  color:var(--green);background:rgba(0,200,150,.08);
  font-weight:600;border-left:3px solid var(--green);
  padding-left:9px;
}}
.sidebar-item i{{width:16px;height:16px;flex-shrink:0}}
.sidebar-pro{{margin-left:auto;font-size:9px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;padding:1px 6px;border-radius:3px;font-weight:700;letter-spacing:.3px;flex-shrink:0}}
.sidebar-divider{{height:1px;background:var(--border);margin:12px 16px}}
.sidebar-group-label{{
  font-size:10px;font-weight:700;color:var(--muted);
  letter-spacing:1.5px;text-transform:uppercase;
  padding:10px 16px 4px;opacity:.6;
}}
.sidebar-cnt{{
  margin-left:auto;font-family:'JetBrains Mono',monospace;
  font-size:10px;font-weight:700;padding:2px 6px;
  border-radius:4px;background:rgba(0,200,150,.12);color:var(--green);
}}
/* CONTENT AREA */
.content-area{{flex:1;min-width:0;display:flex;flex-direction:column;position:relative;z-index:1;background:var(--bg)}}
.content-area::before{{
  content:'';display:block;position:sticky;top:var(--nav-h);
  height:calc(var(--top-gap) + var(--date-strip-h) + var(--market-bar-h));
  margin-bottom:calc(-1 * (var(--top-gap) + var(--date-strip-h) + var(--market-bar-h)));
  background:var(--bg);z-index:109;pointer-events:none;flex:0 0 auto;
}}
/* NEW DATE BAR */
.date-strip{{
  background:var(--s1);border-bottom:1px solid var(--border);
  display:flex;align-items:center;overflow-x:auto;
  padding:0 16px;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent;
  position:sticky;top:calc(var(--nav-h) + var(--top-gap));z-index:120;
  border-left:none;border-radius:10px 10px 0 0;
  box-shadow:0 8px 16px rgba(0,0,0,.18);overflow:hidden;
  width:calc(100% - 48px);max-width:1500px;margin:0 auto;box-sizing:border-box;
}}
.date-strip::-webkit-scrollbar{{height:3px}}
.date-strip::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.date-strip-item{{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:var(--date-strip-h);padding:0 18px;min-width:72px;cursor:pointer;
  border-bottom:3px solid transparent;transition:all .15s;
  color:var(--muted);font-family:'Inter',sans-serif;gap:3px;line-height:1;
  white-space:nowrap;flex-shrink:0;text-align:center;
}}
.date-strip-item:hover{{color:var(--text);background:rgba(255,255,255,.03)}}
.date-strip-item.active{{
  color:var(--green);border-bottom-color:var(--green);
  background:rgba(0,200,150,.04);font-weight:600;
}}
.date-strip-item.today{{color:var(--green)}}
.date-strip-dow{{font-size:11px;font-weight:600;letter-spacing:.5px;text-transform:uppercase}}
.date-strip-day{{font-size:13px;font-weight:700;font-family:'JetBrains Mono',monospace}}
/* MARKET TABS */
.mkt-cat-bar{{
  background:var(--s2);border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0;
  position:sticky;top:calc(var(--nav-h) + var(--top-gap) + var(--date-strip-h));z-index:115;
  width:calc(100% - 48px);max-width:1500px;margin:0 auto;box-sizing:border-box;border-radius:0 0 10px 10px;overflow:hidden;
  box-shadow:0 8px 16px rgba(0,0,0,.16);
}}
.mkt-cat-tab{{
  flex:1;min-width:0;height:var(--market-bar-h);padding:0 16px;font-size:clamp(11px,1vw,13px);font-weight:500;color:var(--muted);
  cursor:pointer;border-bottom:2px solid transparent;
  transition:all .15s;white-space:nowrap;line-height:1;
  display:flex;align-items:center;justify-content:center;gap:7px;
  font-family:'Inter',sans-serif;text-align:center;overflow:hidden;text-overflow:ellipsis;
}}
.mkt-cat-tab:hover{{color:var(--text)}}
.mkt-cat-tab.active{{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}}
/* SUB FILTER BAR */
.sub-filter-bar{{
  background:var(--s1);border-bottom:1px solid var(--border);
  display:none;min-height:42px;padding:6px 16px;gap:8px;flex-wrap:wrap;
  position:sticky;top:calc(var(--nav-h) + var(--top-gap) + var(--date-strip-h) + var(--market-bar-h));z-index:110;
  box-shadow:0 8px 16px rgba(0,0,0,.12);
  width:calc(100% - 48px);max-width:1500px;margin:0 auto;box-sizing:border-box;
}}
.sub-filter-bar.visible{{display:flex;justify-content:center;align-items:center}}
.sub-filter-btn{{
  height:30px;min-width:0;padding:0 16px;font-size:clamp(11px,1vw,12px);font-weight:600;line-height:1;
  border:1px solid var(--border);border-radius:20px;
  color:var(--muted);background:var(--s2);
  cursor:pointer;transition:all .15s;white-space:nowrap;
  font-family:'Inter',sans-serif;display:inline-flex;align-items:center;justify-content:center;text-align:center;overflow:hidden;text-overflow:ellipsis;
}}
.sub-filter-btn:hover{{color:var(--text);border-color:var(--accent)}}
.sub-filter-btn.active{{
  color:var(--bg);background:var(--green);
  border-color:var(--green);
}}
.ranking-cols{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;align-items:start}}
.ranking-col{{min-width:0}}
.ranking-col .tbl-wrap{{margin-bottom:0}}
.ranking-col table{{min-width:760px;font-size:12px}}
.ranking-col thead th{{padding:8px 9px}}
.ranking-col tbody td{{padding:8px 9px}}
.ranking-stack{{display:flex;flex-direction:column;gap:18px}}

/* MOBILE */
@media(max-width:640px){{
  :root{{--nav-h:52px}}
  .navbar{{padding:0 10px;gap:8px}}
  .navbar-logo{{gap:8px}}
  .navbar-logo-icon{{width:28px;height:28px}}
  .navbar-logo-name{{font-size:14px}}
  .navbar-logo-sub{{font-size:8px;letter-spacing:1.4px}}
  .navbar-links{{justify-content:flex-start;overflow-x:auto;scrollbar-width:none}}
  .navbar-links::-webkit-scrollbar{{display:none}}
  .navbar-link{{height:32px;max-width:none;padding:0 10px;font-size:12px;flex:0 0 auto}}
  .navbar-actions{{gap:5px}}
  .navbar-actions>div:first-child{{display:none!important}}
  .navbar-btn-entrar{{height:32px;padding:0 10px;font-size:12px}}
  .navbar-btn-criar{{height:32px;padding:0 10px;font-size:12px}}
  .navbar-theme{{width:32px;height:32px}}
  .header{{padding:10px 14px}}
  .main{{padding:12px 12px}}
  .kpi{{min-width:85px;padding:10px 12px}}
  .kpi-val{{font-size:20px}}
  .mkt-tab{{padding:9px 11px;font-size:12px}}
  .date-strip{{padding:0 8px}}
  .date-strip-item{{min-width:64px;padding:0 12px}}
  .mkt-cat-tab{{padding:0 8px;font-size:12px}}
  .sub-filter-bar{{padding:6px 8px}}
  .sub-filter-btn{{height:30px;padding:0 12px;font-size:12px}}
  .top-grid{{grid-template-columns:1fr}}
  .hist-hero{{grid-template-columns:1fr;padding:13px}}
  .hist-hero-insights{{grid-template-columns:1fr}}
  .hist-score-card{{min-width:0;width:100%;height:auto}}
  .hist-visual{{grid-template-columns:1fr;padding:12px}}
  .hist-radial-wrap{{grid-template-columns:112px minmax(0,1fr)}}
  .hist-radial{{width:112px;height:112px}}
  .hist-title{{font-size:21px}}
  .hist-summary-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .hist-audit-grid{{grid-template-columns:1fr}}
  .hist-audit-main{{grid-template-columns:98px minmax(0,1fr)}}
  .hist-layout{{grid-template-columns:1fr}}
  .hist-market-row{{grid-template-columns:26px minmax(0,1fr) 72px;padding:9px}}
  .hist-taxa-val{{font-size:18px}}
  .day-hist-row{{grid-template-columns:52px minmax(0,1fr) 76px}}
  table{{min-width:640px}}
}}
</style>
</head>
<body>

<!-- NAVBAR -->
<nav class="navbar">
  <a class="navbar-logo" href="#">
    <svg class="navbar-logo-icon" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="wg1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#2563EB"/>
          <stop offset="100%" style="stop-color:#7C3AED"/>
        </linearGradient>
      </defs>
      <path d="M4,28 L10,12 L16,24 L20,16 L24,24 L30,12 L36,28" fill="none" stroke="url(#wg1)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M26,10 L32,4" fill="none" stroke="#00C896" stroke-width="2.5" stroke-linecap="round"/>
      <polygon points="32,4 28,6 30,10" fill="#00C896"/>
    </svg>
    <div class="navbar-logo-text">
      <span class="navbar-logo-name">WinMetrics</span>
      <span class="navbar-logo-sub">Analytics</span>
    </div>
  </a>
  <div class="navbar-links">
    <div class="navbar-link active"><i data-lucide="layout-dashboard" style="width:14px;height:14px"></i> Dashboard</div>
    <div class="navbar-link" onclick="alert('Em breve!')"><i data-lucide="bar-chart-2" style="width:14px;height:14px"></i> Análises</div>
    <div class="navbar-link" onclick="alert('Em breve!')"><i data-lucide="target" style="width:14px;height:14px"></i> Mercados</div>
    <div class="navbar-link" onclick="alert('Em breve!')"><i data-lucide="brain-circuit" style="width:14px;height:14px"></i> IA Preditiva</div>
    <div class="navbar-link" onclick="alert('Em breve!')"><i data-lucide="credit-card" style="width:14px;height:14px"></i> Planos</div>
    <div class="navbar-link" onclick="alert('Em breve!')"><i data-lucide="info" style="width:14px;height:14px"></i> Sobre</div>
  </div>
  <div class="navbar-actions">
    <div style="display:flex;flex-direction:column;align-items:flex-end;margin-right:8px">
      <span id="navbar-clock" style="font-size:8px;font-weight:600;color:rgba(255,255,255,.8);font-family:'JetBrains Mono',monospace"></span>
      <span style="font-size:9px;color:rgba(255,255,255,.35);font-family:'JetBrains Mono',monospace;letter-spacing:.5px">v3.1</span>
    </div>
    <div class="navbar-theme" id="theme-btn" title="Alternar tema" onclick="toggleTheme()"></div>
    <div class="navbar-btn-entrar"><i data-lucide="log-in" style="width:14px;height:14px"></i> Entrar <i data-lucide="chevron-down" style="width:12px;height:12px"></i></div>
    <div class="navbar-btn-criar"><i data-lucide="rocket" style="width:14px;height:14px"></i> Criar conta grátis <i data-lucide="arrow-right" style="width:14px;height:14px"></i></div>
  </div>
</nav>

<div class="app-layout">
  <!-- SIDEBAR -->
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-item active" id="sb-visao" onclick="sidebarNav('visao')">
        <i data-lucide="grid-2x2" style="width:16px;height:16px"></i> Visão Geral
      </div>
      <div class="sidebar-divider"></div>
      <div class="sidebar-item" id="sb-ranking" onclick="sidebarNav('ranking')">
        <i data-lucide="star" style="width:16px;height:16px"></i> Melhores Previsões
        <span class="sidebar-pro">PRO</span>
      </div>
      <div class="sidebar-divider"></div>
      <div class="sidebar-item" id="sb-bilhetes" onclick="sidebarNav('bilhetes')">
        <i data-lucide="ticket" style="width:16px;height:16px"></i> Bilhetes
      </div>
      <div class="sidebar-divider"></div>
      <div class="sidebar-item" id="sb-historico" onclick="showHistoricoGlobal()">
        <i data-lucide="trending-up" style="width:16px;height:16px"></i> Histórico Global
      </div>
    </div>
  </aside>

  <!-- CONTENT -->
  <div class="content-area">
    <!-- DATE STRIP -->
    <div class="date-strip" id="date-strip">
      {date_tabs_html}
    </div>

    <!-- MARKET CATEGORY BAR -->
    <div class="mkt-cat-bar" id="mkt-cat-bar">
      <div class="mkt-cat-tab" data-cat="resultado" onclick="switchCat('resultado')">
        <i data-lucide="shield-check" style="width:14px;height:14px"></i> Resultado Final
        <span style="font-size:9px;background:rgba(100,116,139,.12);color:var(--muted);padding:1px 6px;border-radius:3px;margin-left:4px;letter-spacing:.3px;font-weight:500">Em breve</span>
      </div>
      <div class="mkt-cat-tab" data-cat="gols" onclick="switchCat('gols')">
        <i data-lucide="crosshair" style="width:14px;height:14px"></i> Gols
      </div>
      <div class="mkt-cat-tab" data-cat="escanteios" onclick="switchCat('escanteios')">
        <i data-lucide="corner-up-right" style="width:14px;height:14px"></i> Escanteios
      </div>
      <div class="mkt-cat-tab" data-cat="cartoes" onclick="switchCat('cartoes')">
        <i data-lucide="layers" style="width:14px;height:14px"></i> Cartões
      </div>
    </div>

    <!-- SUB FILTER BAR -->
    <div class="sub-filter-bar" id="sub-filter-bar"></div>

    <!-- DAY PANELS -->
    {day_panels_html}

    <!-- HISTÓRICO GLOBAL -->
    <div id="panel-historico" style="display:none">
      <div class="main">
        <div id="historico-content"></div>
      </div>
    </div>
  </div>
</div>

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
      <div class="cal-leg"><div class="cal-leg-dot" style="background:rgba(0,200,150,.4)"></div>Confirmado</div>
      <div class="cal-leg"><div class="cal-leg-dot" style="background:rgba(59,130,246,.4)"></div>Com dados</div>
      <div class="cal-leg"><div class="cal-leg-dot" style="background:rgba(245,158,11,.8)"></div>Hoje</div>
    </div>
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
    filtrados=jogos.filter(d=>getPalpiteGrade(d)==='A+'||getPalpiteGrade(d)==='A').sort(sortByGrade);
    titulo='Alta Confiança'; cor='var(--green)';
  }} else if(tipo==='15'){{
    filtrados=jogos.filter(d=>d.score_15>=85&&d.passou_filtro).sort((a,b)=>sortByGrade(a,b,d=>d.grade_15||getPalpiteGrade(d),d=>d.score_15));
    titulo='Over 1.5 ≥85%'; cor='var(--yellow)';
  }} else if(tipo==='esc'){{
    filtrados=jogos.filter(d=>d.score_esc75>=75).sort((a,b)=>sortByGrade(a,b,d=>d.grade_esc75||getPalpiteGrade(d),d=>d.score_esc75));
    titulo='Over 7.5 Escanteios ≥75%'; cor='var(--teal)';
  }} else if(tipo==='cart'){{
    filtrados=jogos.filter(d=>d.score_cards25>=75).sort((a,b)=>sortByGrade(a,b,d=>d.grade_cart25||getPalpiteGrade(d),d=>d.score_cards25));
    titulo='Over 2.5 Cartões ≥75%'; cor='var(--orange)';
  }}
  if(!filtrados.length){{
    panel.innerHTML=`<div class="kpi-filter-panel"><div class="kpi-filter-title" style="color:${{cor}}">${{titulo}}</div><div class="empty">Nenhum jogo neste filtro.</div></div>`;
    panel.style.display='block'; return;
  }}
  const rows=filtrados.map((d,i)=>{{
    const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';
    const rc=rowClass(d,mktKey);
    const scoreField=tipo==='prem'?getPalpiteScore(d):tipo==='15'?d.score_15:tipo==='esc'?d.score_esc75:d.score_cards25;
    const mktShow=tipo==='prem'?getPalpiteMkt(d):tipo==='15'?'Over 1.5':tipo==='esc'?'Esc 7.5':'Cart 2.5';
    return`<tr class="${{rc}}">
      <td class="mono muted">${{i+1}}</td>
      ${{jogoCell(d)}}
      <td class="mono muted">${{d.hora}}</td>
      <td>${{gradeHtml(getPalpiteGrade(d))}}</td>
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
  if(d.oddVal) return parseFloat(d.oddVal).toFixed(2);
  const mkt=getPalpiteMkt(d);
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
function pctText(v){{
  if(v==null||v==='')return'—';
  const n=Number(v);
  if(!Number.isFinite(n))return'—';
  return (Math.round(n*10)/10).toString().replace('.0','')+'%';
}}
function ico(name,size){{
  size=size||13;
  return`<i data-lucide="${{name}}" class="inline-icon" style="width:${{size}}px;height:${{size}}px"></i>`;
}}
function pyramid(d){{
  const rows=[['6.5',d.over65_c],['7.5',d.over75_c],['8.5',d.over85_c],['9.5',d.over95_c],['10.5',d.over105_c]];
  return'<div style="display:flex;flex-direction:column;gap:3px;min-width:120px">'+rows.map(([l,v])=>{{
    const pct=v!=null?v:0;
    const c=pct>=80?'var(--green)':pct>=60?'var(--teal)':pct>=40?'var(--yellow)':pct>=20?'var(--orange)':'var(--red)';
    const w=Math.round(pct*0.7);
    return`<div style="display:flex;align-items:center;gap:5px">
      <span style="font-size:9px;color:var(--muted);font-family:'JetBrains Mono',monospace;min-width:28px;text-align:right">${{l}}</span>
      <div style="flex:1;height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden;max-width:70px">
        <div style="height:100%;width:${{w}}%;background:${{c}};border-radius:3px"></div>
      </div>
      <span style="font-size:9px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${{c}};min-width:32px">${{v!=null?v+'%':'—'}}</span>
    </div>`;
  }}).join('')+'</div>';
}}
function jogoCell(d){{
  return`<td><div class="jogo-main">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div><div class="jogo-sub">${{d.liga}}</div></td>`;
}}
function getJogos(date){{return(ALL_DATA[date]||{{}}).jogos||[];}}

// ── Resultado helpers ──────────────────────────────────────────────
function getResultado(jogo){{return jogo.resultado||null;}}
function isConfirmado(date){{return !!(ALL_DATA[date]||{{}}).resultado_confirmado;}}
function getPalpiteMkt(jogo){{return jogo.palpite_mkt||jogo.best_mkt||jogo.mkt||'';}}
function getPalpiteGrade(jogo){{return jogo.palpite_grade||jogo.best_grade||jogo.grade||'D';}}
function getPalpiteScore(jogo){{return jogo.palpite_score!=null?jogo.palpite_score:(jogo.best_score!=null?jogo.best_score:(jogo.score||0));}}
const GRADE_ORDER={{'A+':0,'A':1,'B':2,'C':3,'D':4}};
function gradeRank(g){{return GRADE_ORDER[g]??99;}}
function sortByGrade(a,b,gradeFn,scoreFn){{
  gradeFn=gradeFn||getPalpiteGrade;
  scoreFn=scoreFn||getPalpiteScore;
  const gr=gradeRank(gradeFn(a))-gradeRank(gradeFn(b));
  if(gr!==0)return gr;
  return (scoreFn(b)||0)-(scoreFn(a)||0);
}}

function resBadge(jogo, mktKey){{
  const res=getResultado(jogo);
  if(!res)return`<span class="res-badge pending">${{ico('clock',11)}} Aguardando</span>`;
  const ok=res[mktKey];
  if(ok===true) return`<span class="res-badge hit">${{ico('check',11)}} GREEN</span>`;
  if(ok===false)return`<span class="res-badge miss">${{ico('x',11)}} RED</span>`;
  return`<span class="res-badge pending">${{ico('circle-alert',11)}} Não confirmado</span>`;
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
  if(!res)return`<div class="top-placar pending"><span class="icon">${{ico('clock',13)}}</span><span class="ft">Aguardando</span></div>`;
  const ok=res[mktKey];
  const cls=ok===true?'hit':ok===false?'miss':'pending';
  const icon=ok===true?ico('check',13):ok===false?ico('x',13):ico('circle-help',13);
  const cant=res.corners_total!=null?` · ${{res.corners_total}} cant.`:'';
  const cart=res.cards_total!=null?` · ${{res.cards_total}} cart.`:'';
  return`<div class="top-placar ${{cls}}">
    <span class="icon">${{icon}}</span>
    <div><span class="ft">${{res.placar}}</span> <span class="ht">HT ${{res.placar_ht}}${{cant}}${{cart}}</span></div>
  </div>`;
}}

function cardOverlayClass(jogo){{
  const res=getResultado(jogo);
  if(!res)return'';
  const ac=jogo.acertos||{{}};
  const bestMktAcerto=ac[getPalpiteMkt(jogo)];
  if(!bestMktAcerto)return'';
  if(bestMktAcerto.acertou===true)return' tc-hit';
  if(bestMktAcerto.acertou===false)return' tc-miss';
  return'';
}}

// ── Render Global KPIs (header) ────────────────────────────────────

// ── Visão Geral ────────────────────────────────────────────────────
function renderVisao(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-visao');
  const conf=isConfirmado(date);
  const snap=(ALL_DATA[date]||{{}}).palpites_snapshot||[];
  const a15=jogos.filter(d=>d.score_15>=85&&d.passou_filtro).length;
  const aesc=jogos.filter(d=>d.score_esc75>=75).length;
  const acart=jogos.filter(d=>d.score_cards25>=75).length;
  const aprem=snap.length||jogos.filter(d=>getPalpiteGrade(d)==='A+'||getPalpiteGrade(d)==='A').length;
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
    const tSub=ta+te>0?`${{ta}} acertos · ${{te}} erros`:'sem dados';
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

  const top=[...(snap.length?snap:jogos)].sort(sortByGrade).slice(0,5);
  const cls=['tc-aplus','tc-a','tc-b','tc-c','tc-d'];
  const t5=top.map((d,i)=>{{
    const c=col(getPalpiteScore(d));
    const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';
    const overlay=cardOverlayClass(d);
    return`<div class="top-card ${{cls[i]}}${{overlay}}">
      <div class="top-rank">#${{i+1}}</div>
      <div class="top-liga">${{d.liga}}</div>
      <div class="top-jogo">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div>
      <div class="top-hora">${{ico('clock',11)}} ${{d.hora}}</div>
      <div class="top-mkt">${{getPalpiteMkt(d)}}</div>
      <div class="top-bottom">
        <div class="top-score" style="color:${{c}}">${{getPalpiteScore(d)}}%</div>
        <div class="top-grade-block">
          ${{gradeHtml(getPalpiteGrade(d))}}
          ${{oddMkt(d)!=='—'?`<span style="font-size:11px;color:var(--yellow);font-family:'JetBrains Mono',monospace;font-weight:700;margin-top:2px">Odd: ${{oddMkt(d)}}</span>`:''}}
        </div>
      </div>
      ${{placarCard(d, mktKey)}}
    </div>`;
  }}).join('');

  const rows=[...jogos].sort(sortByGrade).map(d=>{{
    const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';
    const rc=rowClass(d,mktKey);
    return`<tr class="${{rc}}">
      ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
      <td class="td-conf">${{gradeHtml(getPalpiteGrade(d))}}</td>
      <td class="td-palpite">${{getPalpiteMkt(d)}}</td>
      <td class="mono" style="color:${{col(getPalpiteScore(d))}};font-weight:700">${{pctText(getPalpiteScore(d))}}</td>
      <td class="mono" style="color:${{col(d.score_15)}};font-weight:700">${{pctText(d.score_15)}}</td>
      <td class="mono" style="color:${{col(d.score_esc75)}};font-weight:700">${{pctText(d.score_esc75)}}</td>
      <td class="mono" style="color:${{col(d.score_cards25)}};font-weight:700">${{pctText(d.score_cards25)}}</td>
      ${{placarCell(d)}}
      <td>${{resBadge(d,mktKey)}}</td>
    </tr>`;
  }}).join('');

  el.innerHTML=`
    ${{kpi}}
    <div class="sec-title">${{ico('trophy',14)}} Top 5 Palpites do Dia</div>
    <div class="top-grid">${{t5}}</div>
    <div class="sec-title">${{ico('list-checks',14)}} Resumo Geral</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Jogo</th><th>Hora</th><th style="color:var(--green)">Confiança</th><th style="color:var(--accent)">Palpite</th><th>Score Palpite</th><th>Over 1.5</th><th>Esc 7.5</th><th>Cart 2.5</th><th>Placar</th><th>Resultado</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
}}

// ── Ranking ────────────────────────────────────────────────────────
function renderRanking(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-ranking');
  const snap=(ALL_DATA[date]||{{}}).palpites_snapshot||[];
  const base=jogos.length?jogos:snap;
  const sorted=[...base].sort(sortByGrade);
  const groups=[
    {{title:'Confian&ccedil;a Alta / M&eacute;dia', items:sorted.filter(d=>getPalpiteGrade(d)==='A+'||getPalpiteGrade(d)==='A')}},
    {{title:'Moderado', items:sorted.filter(d=>getPalpiteGrade(d)==='B')}},
    {{title:'Arriscado / Evitar', items:sorted.filter(d=>getPalpiteGrade(d)==='C'||getPalpiteGrade(d)==='D')}}
  ];

  function tableFor(group){{
    if(!group.items.length)return`<div class="ranking-col"><div class="sec-title">${{group.title}}</div><div class="empty">Nenhum jogo nesta categoria.</div></div>`;
    const rows=group.items.map(d=>{{
      const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';
      const rc=rowClass(d,mktKey);
      return`<tr class="${{rc}}">
        ${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{gradeHtml(getPalpiteGrade(d))}}</td>
        <td class="td-palpite">${{getPalpiteMkt(d)}}</td>
        <td class="mono" style="color:${{col(getPalpiteScore(d))}};font-weight:700">${{pctText(getPalpiteScore(d))}}</td>
        ${{placarCell(d)}}
        <td>${{resBadge(d,mktKey)}}</td>
      </tr>`;
    }}).join('');
    return`<div class="ranking-col">
      <div class="sec-title">${{group.title}}</div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>Jogo</th><th>Hora</th><th>Confian&ccedil;a</th><th>Palpite</th><th>Score</th><th>Placar</th><th>Resultado</th></tr></thead>
        <tbody>${{rows}}</tbody>
      </table></div>
    </div>`;
  }}

  el.innerHTML=`<div class="ranking-stack">${{groups.map(tableFor).join('')}}</div>`;
}}

// ── Over 1.5 ───────────────────────────────────────────────────────
function renderOver15(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over15');
  let rows=[...jogos].filter(d=>d.passou_filtro).sort((a,b)=>sortByGrade(a,b,d=>d.grade_15||getPalpiteGrade(d),d=>d.score_15));
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
  const ru35=[...jogos].sort((a,b)=>sortByGrade(a,b,d=>d.grade_u35||d.grade_u45||getPalpiteGrade(d),d=>d.score_u35||d.score_u45||0));
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
  const r75=[...jogos].sort((a,b)=>sortByGrade(a,b,d=>d.grade_esc75||getPalpiteGrade(d),d=>d.score_esc75));
  const r85=[...jogos].sort((a,b)=>sortByGrade(a,b,d=>d.grade_esc85||getPalpiteGrade(d),d=>d.score_esc85));
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
    <div class="sec-title">${{ico('corner-up-right',14)}} Over 7.5</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Média</th><th>Pirâmide</th><th>Real</th><th>Resultado</th></tr></thead>
      <tbody>${{escRows(r75,'esc75_ok')}}</tbody></table></div>
    <div class="sec-title">${{ico('corner-up-right',14)}} Over 8.5</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Score</th><th>Média</th><th>Pirâmide</th><th>Real</th><th>Resultado</th></tr></thead>
      <tbody>${{escRows(r85,'esc85_ok')}}</tbody></table></div>`;
}}

// ── Cartões ────────────────────────────────────────────────────────
function renderCart(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-cartoes');
  const rows=[...jogos].sort((a,b)=>sortByGrade(a,b,d=>d.grade_cart25||getPalpiteGrade(d),d=>d.score_cards25));
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

// ── Bilhetes ───────────────────────────────────────────────────────
function gerarBilhetes(jogos){{
  // Candidatos: apenas A+/A — qualidade como único critério
  const altaConf = jogos
    .filter(j=>getPalpiteGrade(j)==='A+'||getPalpiteGrade(j)==='A')
    .sort(sortByGrade)
    .map(j=>{{
      const oddVal = parseFloat(oddMkt(j))||null;
      return {{
        jogo:j.jogo, liga:j.liga, hora:j.hora,
        mkt:getPalpiteMkt(j), score:getPalpiteScore(j), grade:getPalpiteGrade(j),
        oddVal, resultado:j.resultado, acertos:j.acertos||{{}},
      }};
    }});

  function montar(pool, min=2){{
    if(pool.length < min) return null;
    const oddTotal = pool.reduce((acc,s)=>acc*(s.oddVal||1),1);
    return {{sels:pool, oddTotal:Math.round(oddTotal*100)/100}};
  }}

  // Bilhete do Dia — só A+ score>=90%, máx 8
  const diaPool = altaConf.filter(x=>x.grade==='A+'&&x.score>=90).slice(0,8);
  const bDia = diaPool.length>=2 ? {{
    sels:diaPool,
    oddTotal:Math.round(diaPool.reduce((acc,s)=>acc*(s.oddVal||1),1)*100)/100
  }} : null;

  // Bilhete 1 — Premium: todos A+/A por score
  const b1 = montar([...altaConf]);

  // Bilhete 2 — Só A+: filtro mais restrito
  const somenteAplus = altaConf.filter(x=>x.grade==='A+');
  const b2 = somenteAplus.length>=2 ? montar(somenteAplus) : null;

  const bilhetes = [];
  const seen = new Set();
  const defs = [
    ['b1', b1, 'bilhete-premium',     'Premium - Todos A+/A por Score'],
    ['b2', b2, 'bilhete-conservador', 'Confiança Alta - Só A+'],
  ];
  for(const [tipo, b, cls, label] of defs){{
    if(!b) continue;
    const key = b.sels.map(s=>s.jogo+s.mkt).sort().join('|');
    if(seen.has(key)) continue;
    seen.add(key);
    bilhetes.push({{tipo, b, cls, label}});
  }}
  return {{bilhetes, bilheteDia: bDia}};
}}
function avaliarBilhete(sels, confirmado){{
  if(!confirmado) return {{status:'pending', acertos:0, total:sels.length}};
  let acertos=0, erros=0, sd=0;
  for(const s of sels){{
    const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
    const res = s.resultado;
    if(!res){{ sd++; continue; }}
    const ok = res[mktKey];
    if(ok===true) acertos++;
    else if(ok===false) erros++;
    else sd++;
  }}
  if(erros>0) return {{status:'loss', acertos, erros, sd, total:sels.length}};
  if(sd>0) return {{status:'partial', acertos, erros, sd, total:sels.length}};
  return {{status:'win', acertos, erros:0, sd:0, total:sels.length}};
}}

function renderBilhetes(date, jogos){{
  const el = document.getElementById('mkt-'+date+'-bilhetes');
  const confirmado = isConfirmado(date);
  const snap=(ALL_DATA[date]||{{}}).bilhetes_snapshot;
  const resultado = snap || gerarBilhetes(jogos);
  const {{bilhetes, bilheteDia}} = resultado;

  if((!bilhetes || bilhetes.length===0) && !bilheteDia){{
    el.innerHTML=`<div class="empty">Nenhum jogo com dados suficientes para gerar bilhetes hoje.</div>`;
    return;
  }}

  // Bilhete do Dia
  let diaHtml = '';
  if(bilheteDia){{
    const av = avaliarBilhete(bilheteDia.sels, confirmado);
    const overlayClass = av.status==='win'?' bilhete-win':av.status==='loss'?' bilhete-loss':'';
    const oddColor = !bilheteDia.oddTotal?'var(--muted)':bilheteDia.oddTotal>=5?'var(--green)':bilheteDia.oddTotal>=3?'var(--yellow)':'var(--orange)';
    const scoreMedia = Math.round(bilheteDia.sels.reduce((a,s)=>a+s.score,0)/bilheteDia.sels.length);
    const diaHeader = `<div class="bilhete-row" style="border-bottom:1px solid rgba(0,200,150,.2);margin-bottom:4px;padding-bottom:6px">
      <span class="bilhete-num" style="color:var(--muted);font-size:9px">#</span>
      <div style="flex:1;min-width:0"><span style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Jogo</span></div>
      <span class="bilhete-mkt" style="font-size:9px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.7px">Mercado</span>
      <div class="bilhete-score-bar" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Confiança</div>
      <span class="bilhete-odd-val" style="font-size:9px;font-weight:700;color:var(--yellow);text-transform:uppercase;letter-spacing:.7px">Odd</span>
      <div class="bilhete-res" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Resultado</div>
    </div>`;
    const rows = bilheteDia.sels.map((s,i)=>{{
      const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
      const res = s.resultado;
      let resHtml = `<span class="res-badge pending">${{ico('clock',11)}}</span>`;
      if(confirmado && res){{
        const ok = res[mktKey];
        if(ok===true) resHtml=`<span class="res-badge hit">${{ico('check',11)}} GREEN</span>`;
        else if(ok===false) resHtml=`<span class="res-badge miss">${{ico('x',11)}} RED</span>`;
        else resHtml=`<span class="res-badge pending">${{ico('circle-alert',11)}} Não confirmado</span>`;
      }}
      return`<div class="bilhete-row">
        <span class="bilhete-num">${{i+1}}</span>
        <div style="flex:1;min-width:0"><div class="bilhete-jogo">${{s.jogo}}</div><div class="bilhete-liga">${{s.liga}} · ${{s.hora}}</div></div>
        <span class="bilhete-mkt">${{s.mkt}}</span>
        <div class="bilhete-score-bar">${{bar(s.score,60)}}</div>
        <span class="bilhete-odd-val">${{s.oddVal?s.oddVal.toFixed(2):'—'}}</span>
        <div class="bilhete-res">${{resHtml}}</div>
      </div>`;
    }}).join('');
    let statusHtml = '';
    if(!confirmado) statusHtml=`<span class="bilhete-status" style="color:var(--muted)">${{ico('clock',12)}} Aguardando</span>`;
    else if(av.status==='win') statusHtml=`<span class="bilhete-status" style="color:var(--green)">${{ico('check-circle',12)}} GREEN! Odd: ${{bilheteDia.oddTotal.toFixed(2)}}</span>`;
    else if(av.status==='loss') statusHtml=`<span class="bilhete-status" style="color:var(--red)">${{ico('x-circle',12)}} Perdeu (${{av.erros}} erro${{av.erros>1?'s':''}})</span>`;
    else statusHtml=`<span class="bilhete-status" style="color:var(--yellow)">${{ico('circle-alert',12)}} Parcial - ${{av.sd}} sem dados</span>`;

    diaHtml=`<div class="bilhete-dia${{overlayClass}}">
      <div class="bilhete-dia-badge">${{ico('trophy',12)}} BILHETE DO DIA</div>
      <div class="bilhete-header">
        <div><div class="bilhete-title" style="font-size:15px">Os mais assertivos do dia</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px">${{bilheteDia.sels.length}} seleções · Score médio ${{scoreMedia}}%</div></div>
        <div style="text-align:right">
          <div class="bilhete-odd-total" style="color:${{oddColor}}">${{bilheteDia.oddTotal?bilheteDia.oddTotal.toFixed(2):'—'}}</div>
          <div class="bilhete-odd-label">Odd combinada</div>
        </div>
      </div>
      <div style="border-top:1px solid rgba(0,200,150,.2);padding-top:10px">${{diaHeader}}${{rows}}</div>
      <div class="bilhete-footer"><span class="bilhete-sels">${{bilheteDia.sels.filter(s=>s.grade==='A+').length}} A+ · ${{bilheteDia.sels.filter(s=>s.grade==='A').length}} A</span>${{statusHtml}}</div>
    </div>
    <div class="sec-title">${{ico('list-checks',14)}} Todos os Bilhetes</div>`;
  }}

  const html = bilhetes.map((item)=>{{ const {{tipo, b, cls, label}} = item;
    const av = avaliarBilhete(b.sels, confirmado);
    const overlayClass = av.status==='win'?' bilhete-win':av.status==='loss'?' bilhete-loss':'';
    const oddColor = b.oddTotal >= 5 ? 'var(--green)' : b.oddTotal >= 3 ? 'var(--yellow)' : 'var(--orange)';

    const bilheteHeader = `<div class="bilhete-row" style="border-bottom:1px solid var(--border);margin-bottom:4px;padding-bottom:6px">
      <span class="bilhete-num" style="color:var(--muted);font-size:9px">#</span>
      <div style="flex:1;min-width:0"><span style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Jogo</span></div>
      <span class="bilhete-mkt" style="font-size:9px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.7px">Mercado</span>
      <div class="bilhete-score-bar" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Confiança</div>
      <span class="bilhete-odd-val" style="font-size:9px;font-weight:700;color:var(--yellow);text-transform:uppercase;letter-spacing:.7px">Odd</span>
      <div class="bilhete-res" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Resultado</div>
    </div>`;
    const rows = b.sels.map((s,i)=>{{
      const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
      const res = s.resultado;
      let resHtml = `<span class="res-badge pending">${{ico('clock',11)}}</span>`;
      if(confirmado && res){{
        const ok = res[mktKey];
        if(ok===true) resHtml=`<span class="res-badge hit">${{ico('check',11)}} GREEN</span>`;
        else if(ok===false) resHtml=`<span class="res-badge miss">${{ico('x',11)}} RED</span>`;
        else resHtml=`<span class="res-badge pending">${{ico('circle-alert',11)}} Não confirmado</span>`;
      }}
      const scoreVal = s.score || 0;
      return`<div class="bilhete-row">
        <span class="bilhete-num">${{i+1}}</span>
        <div style="flex:1;min-width:0">
          <div class="bilhete-jogo">${{s.jogo}}</div>
          <div class="bilhete-liga">${{s.liga}} · ${{s.hora}}</div>
        </div>
        <span class="bilhete-mkt">${{s.mkt}}</span>
        <div class="bilhete-score-bar">${{bar(scoreVal,60)}}</div>
        <span class="bilhete-odd-val">${{s.oddVal?s.oddVal.toFixed(2):'—'}}</span>
        <div class="bilhete-res">${{resHtml}}</div>
      </div>`;
    }}).join('');

    let statusHtml = '';
    if(!confirmado){{
      statusHtml = `<span class="bilhete-status" style="color:var(--muted)">${{ico('clock',12)}} Aguardando resultados</span>`;
    }} else if(av.status==='win'){{
      statusHtml = `<span class="bilhete-status" style="color:var(--green)">${{ico('check-circle',12)}} BILHETE GREEN! Odd: ${{b.oddTotal.toFixed(2)}}</span>`;
    }} else if(av.status==='loss'){{
      statusHtml = `<span class="bilhete-status" style="color:var(--red)">${{ico('x-circle',12)}} Perdeu (${{av.erros}} erro${{av.erros>1?'s':''}})</span>`;
    }} else if(av.status==='partial'){{
      statusHtml = `<span class="bilhete-status" style="color:var(--yellow)">${{ico('circle-alert',12)}} Parcial - ${{av.sd}} sem dados</span>`;
    }}

    return`<div class="bilhete-card ${{cls}}${{overlayClass}}">
      <div class="bilhete-header">
        <div>
          <div class="bilhete-title">${{label}}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px">${{b.sels.length}} seleções</div>
        </div>
        <div style="text-align:right">
          <div class="bilhete-odd-total" style="color:${{oddColor}}">${{b.oddTotal?b.oddTotal.toFixed(2):'—'}}</div>
          <div class="bilhete-odd-label">Odd combinada</div>
        </div>
      </div>
      <div style="border-top:1px solid var(--border);padding-top:10px">${{bilheteHeader}}${{rows}}</div>
      <div class="bilhete-footer">
        <span class="bilhete-sels">${{b.sels.filter(s=>s.grade==='A+'||s.grade==='A').length}} A+/A · ${{b.sels.filter(s=>s.grade==='B').length}} B</span>
        ${{statusHtml}}
      </div>
    </div>`;
  }}).join('');

  const callout = confirmado
    ? `<div class="callout ok"><strong>${{ico('check-circle',13)}} Resultados disponíveis</strong> · Bilhetes avaliados com resultados reais.</div>`
    : `<div class="callout info"><strong>${{ico('target',13)}} Bilhetes do Dia</strong> · Combinações geradas automaticamente pelo modelo. Aguardando resultados.</div>`;

  el.innerHTML = callout + diaHtml + html;
}}

// ── Resultados do Dia ──────────────────────────────────────────────
function renderHistoricoDia(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-historico_dia');
  const conf=isConfirmado(date);
  const stats=(ALL_DATA[date]||{{}}).resultado_stats||{{}};

  if(!conf){{
    const rows=[...jogos].sort(sortByGrade).map(d=>{{
      const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';
      return`<tr class="row-pending">
        ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
        <td>${{gradeHtml(getPalpiteGrade(d))}}</td>
        <td class="mono" style="font-size:11px;color:var(--muted)">${{getPalpiteMkt(d)}}</td>
        <td>${{bar(getPalpiteScore(d))}}</td>
        <td><span class="res-badge pending">${{ico('clock',11)}} Aguardando</span></td>
      </tr>`;
    }}).join('');
    el.innerHTML=`
      <div class="callout warn"><strong>${{ico('clock',13)}} Resultados pendentes</strong> · Execute <code>confirmar.py --date ${{date.split('-').reverse().join('-')}}</code> após os jogos.</div>
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
      <span style="font-size:10px;color:var(--muted);min-width:95px">${{s.acertos}} acertos · ${{s.erros}} erros / ${{s.palpites}}</span>
    </div>`;
  }}).join('');

  // Tabela completa com resultados
  const rows=[...jogos].sort(sortByGrade).map(d=>{{
    const res=getResultado(d);
    const ac=d.acertos||{{}};
    const badges=Object.entries(ac).map(([mkt,info])=>{{
      const cls=info.acertou===true?'hit':info.acertou===false?'miss':'pending';
      const icon=info.acertou===true?ico('check',10):info.acertou===false?ico('x',10):ico('circle-help',10);
      return`<span class="res-badge ${{cls}}" style="margin:1px;font-size:9px">${{icon}} ${{mkt}}</span>`;
    }}).join('');
    const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';
    const rc=rowClass(d,mktKey);
    const cantRow=res&&res.corners_total!=null?res.corners_total:'—';
    const cartRow=res&&res.cards_total!=null?res.cards_total:'—';
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
    <div class="callout ok"><strong>${{ico('check-circle',13)}} Resultados confirmados</strong> · Dados reais da API-Football.</div>
    <div class="kpi-row" style="margin-bottom:16px">
      <div class="kpi"><div class="kpi-val" style="color:${{cG}}">${{tGeral!=null?tGeral+'%':'—'}}</div><div class="kpi-lbl">Taxa do Dia</div></div>
      <div class="kpi"><div class="kpi-val g">${{ta}}</div><div class="kpi-lbl">Acertos</div></div>
      <div class="kpi"><div class="kpi-val r">${{te}}</div><div class="kpi-lbl">Erros</div></div>
      <div class="kpi"><div class="kpi-val b">${{tp}}</div><div class="kpi-lbl">Palpites</div></div>
    </div>
    <div class="sec-title">${{ico('bar-chart-2',14)}} Taxa por Mercado</div>
    <div style="max-width:580px;margin-bottom:20px">${{taxaBars||'<div class="empty">Sem dados.</div>'}}</div>
    <div class="sec-title">${{ico('list-checks',14)}} Todos os Jogos</div>
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
    el.innerHTML=`<div class="callout warn" style="margin-top:20px"><strong>${{ico('clock',13)}} Sem histórico confirmado ainda</strong> · Execute confirmar.py após os jogos de cada dia.</div>`;
    return;
  }}

  const colorForTaxa=t=>t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
  const avaliados=(g.total_acertos||0)+(g.total_erros||0);
  const gerados=dias.reduce((acc,d)=>acc+(((ALL_DATA[d]||{{}}).jogos||[]).length),0);
  const geradosConfirmados=dias.reduce((acc,d)=>{{
    const day=ALL_DATA[d]||{{}};
    return acc+(day.resultado_confirmado?((day.jogos||[]).length):0);
  }},0);
  const pendentes=Math.max(0,(g.total_palpites||0)-avaliados);
  const taxa=g.taxa_geral;
  const cG=colorForTaxa(taxa);

  function blankPickStat(){{return {{acertos:0,erros:0,palpites:0}};}}
  function addPick(stat,item){{
    if(!item)return;
    const mktKey=MKT_RESULT[item.mkt||getPalpiteMkt(item)]||'over15_ok';
    const res=item.resultado;
    if(!res)return;
    const ok=res[mktKey];
    if(ok===true){{stat.acertos++;stat.palpites++;}}
    else if(ok===false){{stat.erros++;stat.palpites++;}}
  }}
  function taxaStat(stat){{
    const total=(stat.acertos||0)+(stat.erros||0);
    return total>0?Math.round((stat.acertos||0)/total*1000)/10:null;
  }}
  function mergePickStat(target,src){{
    target.acertos+=(src.acertos||0);target.erros+=(src.erros||0);target.palpites+=(src.palpites||0);
  }}
  function breakRow(label,stat,tone){{
    const t=taxaStat(stat), c=colorForTaxa(t);
    const cls=tone?` tone-${{tone}}`:'';
    if(t==null)return`<div class="hist-break-row${{cls}}"><div><div class="hist-break-name">${{label}}</div><div class="hist-break-detail">sem histórico confirmado</div></div><div class="hist-break-empty">—</div></div>`;
    return`<div class="hist-break-row${{cls}}">
      <div><div class="hist-break-name">${{label}}</div><div class="hist-break-detail">${{stat.acertos}} acertos · ${{stat.erros}} erros · ${{stat.palpites}} avaliados</div></div>
      <div class="hist-break-rate" style="color:${{c}}">${{t}}%</div>
    </div>`;
  }}
  function auditPanel(title,subtitle,totalStat,rows,variant){{
    const t=taxaStat(totalStat), c=colorForTaxa(t);
    const cls=variant?` ${{variant}}`:'';
    return`<div class="hist-audit-panel${{cls}}">
      <div class="hist-audit-main">
        <div class="hist-audit-score">
          <div class="hist-audit-val" style="color:${{c}}">${{t!=null?t+'%':'—'}}</div>
          <div class="hist-audit-lbl">taxa geral</div>
        </div>
        <div>
          <div class="hist-audit-title">${{title}}</div>
          <div class="hist-audit-copy">${{subtitle}}</div>
        </div>
      </div>
      <div class="hist-breakdown">${{rows}}</div>
    </div>`;
  }}
  function statLabel(stat){{
    const t=taxaStat(stat), c=colorForTaxa(t);
    return {{taxa:t,color:c,text:t!=null?t+'%':'—'}};
  }}

  const bestStats={{
    geral:blankPickStat(), alta:blankPickStat(), media:blankPickStat(), moderado:blankPickStat()
  }};
  const topStats={{geral:blankPickStat()}};
  const ticketStats={{
    geral:{{wins:0,losses:0,tickets:0,legs:blankPickStat()}},
    dia:{{wins:0,losses:0,tickets:0,legs:blankPickStat()}},
    bingo:{{wins:0,losses:0,tickets:0,legs:blankPickStat()}},
    premium:{{wins:0,losses:0,tickets:0,legs:blankPickStat()}},
    elite:{{wins:0,losses:0,tickets:0,legs:blankPickStat()}}
  }};
  function addTicketStat(bucket,sels){{
    if(!sels||!sels.length)return;
    const av=avaliarBilhete(sels,true);
    if(av.status!=='win'&&av.status!=='loss')return;
    bucket.tickets++;
    if(av.status==='win')bucket.wins++;
    else bucket.losses++;
    sels.forEach(s=>addPick(bucket.legs,s));
  }}
  function mergeTicketStat(target,src){{
    target.wins+=src.wins;target.losses+=src.losses;target.tickets+=src.tickets;mergePickStat(target.legs,src.legs);
  }}
  function ticketPickStat(stat){{return {{acertos:stat.wins,erros:stat.losses,palpites:stat.tickets}};}}
  function ticketRow(label,stat){{
    const t=ticketsTaxa(stat), c=colorForTaxa(t);
    if(t==null)return`<div class="hist-break-row tone-pro"><div><div class="hist-break-name">${{label}}</div><div class="hist-break-detail">sem bilhetes fechados</div></div><div class="hist-break-empty">—</div></div>`;
    return`<div class="hist-break-row tone-pro">
      <div><div class="hist-break-name">${{label}}</div><div class="hist-break-detail">${{stat.wins}} green · ${{stat.losses}} red · ${{stat.legs.acertos}}/${{stat.legs.erros}} seleções</div></div>
      <div class="hist-break-rate" style="color:${{c}}">${{t}}%</div>
    </div>`;
  }}
  function ticketsTaxa(stat){{
    const total=(stat.wins||0)+(stat.losses||0);
    return total>0?Math.round((stat.wins||0)/total*1000)/10:null;
  }}

  dias.forEach(d=>{{
    const dayData=ALL_DATA[d]||{{}};
    if(!dayData.resultado_confirmado)return;
    const jogos=dayData.jogos||[];
    const snap=dayData.palpites_snapshot||[];
    const bestBase=jogos.length?jogos:snap;
    bestBase.forEach(item=>{{
      addPick(bestStats.geral,item);
      const grade=item.grade||getPalpiteGrade(item);
      if(grade==='A+')addPick(bestStats.alta,item);
      else if(grade==='A')addPick(bestStats.media,item);
      else if(grade==='B')addPick(bestStats.moderado,item);
    }});

    const topNames=dayData.top5||[];
    const topBase=snap.length?snap:jogos;
    if(topNames.length){{
      topNames.forEach(name=>addPick(topStats.geral,topBase.find(x=>x.jogo===name)));
    }} else {{
      [...topBase].sort(sortByGrade).slice(0,5).forEach(item=>addPick(topStats.geral,item));
    }}

    const bs=dayData.bilhetes_snapshot||{{}};
    if(bs.bilheteDia)addTicketStat(ticketStats.dia,bs.bilheteDia.sels);
    (bs.bilhetes||[]).forEach(item=>{{
      const label=(item.label||'').toLowerCase();
      const tipo=(item.tipo||'').toLowerCase();
      const sels=(item.b||{{}}).sels||[];
      let bucket=null;
      if(label.includes('bingo')||tipo.includes('bingo'))bucket=ticketStats.bingo;
      else if(label.includes('premium')||tipo==='b1')bucket=ticketStats.premium;
      else if(label.includes('elite')||label.includes('confian')||tipo==='b2')bucket=ticketStats.elite;
      if(bucket){{addTicketStat(bucket,sels);}}
    }});
  }});
  mergeTicketStat(ticketStats.geral,ticketStats.dia);
  mergeTicketStat(ticketStats.geral,ticketStats.bingo);
  mergeTicketStat(ticketStats.geral,ticketStats.premium);
  mergeTicketStat(ticketStats.geral,ticketStats.elite);

  const categoryStats=[
    {{label:'Confiança Alta',stat:bestStats.alta}},
    {{label:'Confiança Média',stat:bestStats.media}},
    {{label:'Moderado',stat:bestStats.moderado}}
  ].filter(x=>taxaStat(x.stat)!=null).sort((a,b)=>{{
    const tr=taxaStat(b.stat)-taxaStat(a.stat);
    if(tr)return tr;
    return (b.stat.palpites||0)-(a.stat.palpites||0);
  }});
  const melhorCategoria=categoryStats[0]||null;
  const melhorCategoriaRate=melhorCategoria?statLabel(melhorCategoria.stat):null;

  const marketStats=MERCADOS.map(m=>{{
    const s=pm[m]||{{}};
    const acertos=s.acertos||0;
    const erros=s.erros||0;
    const palpites=s.palpites||s.p||0;
    const avaliadosM=acertos+erros;
    return {{m,s,taxa:s.taxa,acertos,erros,palpites,avaliados:avaliadosM}};
  }}).filter(x=>x.palpites>0||x.avaliados>0).sort((a,b)=>{{
    const tr=(b.taxa??-1)-(a.taxa??-1);
    if(tr)return tr;
    return (b.avaliados-a.avaliados)||(b.palpites-a.palpites);
  }});
  const melhor=marketStats[0]||null;
  const melhorMercadoRate=melhor?{{taxa:melhor.taxa,color:colorForTaxa(melhor.taxa),text:melhor.taxa!=null?melhor.taxa+'%':'—'}}:null;

  const mktCards=marketStats.map((x,i)=>{{
    const c=colorForTaxa(x.taxa);
    return`<div class="hist-market-row">
      <div class="hist-rank">${{String(i+1).padStart(2,'0')}}</div>
      <div>
        <div class="hist-mkt-name">${{x.m}}</div>
        <div class="hist-detail">${{x.acertos}} acertos · ${{x.erros}} erros · ${{x.palpites}} palpites</div>
      </div>
      <div class="hist-rate">
        <div class="hist-taxa-val" style="color:${{c}}">${{x.taxa!=null?x.taxa+'%':'—'}}</div>
        <div class="hist-rate-label">taxa</div>
      </div>
      <div class="hist-bar-track"><div class="hist-bar-fill" style="width:${{x.taxa||0}}%;background:${{c}}"></div></div>
    </div>`;
  }}).join('');

  const confirmedDias=dias.filter(d=>(ALL_DATA[d]||{{}}).resultado_confirmado);
  const categoryVisual=[
    {{label:'Alta',full:'Confian&ccedil;a Alta',stat:bestStats.alta,color:'var(--green)',tone:'#00C896'}},
    {{label:'M&eacute;dia',full:'Confian&ccedil;a M&eacute;dia',stat:bestStats.media,color:'var(--blue)',tone:'#3B82F6'}},
    {{label:'Moderado',full:'Moderado',stat:bestStats.moderado,color:'var(--orange)',tone:'#F59E0B'}}
  ].map(x=>{{const t=taxaStat(x.stat);return {{...x,taxa:t||0,text:t!=null?t+'%':'—'}};}});
  const radialHtml=categoryVisual.map((x,i)=>{{
    const inset=2+i*14;
    const deg=Math.max(0,Math.min(100,x.taxa))*3.6;
    return`<div class="hist-radial-ring" style="--inset:${{inset}}px;--ring-color:${{x.tone}};--ring-deg:${{deg}}deg"></div>`;
  }}).join('');
  const categoryLegend=categoryVisual.map(x=>`
    <div class="hist-vlegend-row">
      <span class="hist-vdot" style="--dot:${{x.tone}}"></span>
      <span class="hist-vlegend-name">${{x.full}}</span>
      <span class="hist-vlegend-rate" style="--rate-color:${{x.color}}">${{x.text}}</span>
    </div>`).join('');
  const dayPoints=confirmedDias.map(d=>{{
    const s=(ALL_DATA[d]||{{}}).resultado_stats||{{}};
    let ta=0,te=0;
    Object.values(s).forEach(x=>{{ta+=x.acertos||0;te+=x.erros||0;}});
    return ta+te>0?Math.round(ta/(ta+te)*100):0;
  }});
  const visualPoints=dayPoints.slice(-10);
  const svgW=320, svgH=118, pad=12;
  const linePts=visualPoints.map((v,i)=>{{
    const x=visualPoints.length<=1?pad:i*((svgW-pad*2)/(visualPoints.length-1))+pad;
    const y=svgH-pad-(Math.max(0,Math.min(100,v))/100)*(svgH-pad*2);
    return [Math.round(x*10)/10,Math.round(y*10)/10];
  }});
  const linePath=linePts.map((p,i)=>`${{i?'L':'M'}} ${{p[0]}} ${{p[1]}}`).join(' ');
  const areaPath=linePts.length?`${{linePath}} L ${{linePts[linePts.length-1][0]}} ${{svgH-pad}} L ${{linePts[0][0]}} ${{svgH-pad}} Z`:'';
  const topMarketMini=marketStats.slice(0,4).map(x=>{{
    const c=colorForTaxa(x.taxa);
    return`<div class="hist-market-mini-row">
      <div class="hist-market-mini-name">${{x.m}}</div>
      <div class="hist-market-mini-rate" style="color:${{c}}">${{x.taxa!=null?x.taxa+'%':'—'}}</div>
      <div class="hist-market-mini-track"><div class="hist-market-mini-fill" style="width:${{x.taxa||0}}%;background:linear-gradient(90deg,${{c}},var(--purple2))"></div></div>
    </div>`;
  }}).join('');
  const timeline=confirmedDias.map(d=>{{
    const dayData=ALL_DATA[d]||{{}};
    const s=dayData.resultado_stats||{{}};
    let ta=0,te=0;
    Object.values(s).forEach(x=>{{ta+=x.acertos||0;te+=x.erros||0;}});
    const t=ta+te>0?Math.round(ta/(ta+te)*100):null;
    const c=colorForTaxa(t);
    const [dd,mm]=d.split('-');
    return`<div class="day-hist-row">
      <span class="day-hist-date">${{dd}}/${{mm}}</span>
      <div class="day-hist-bar">
        <div class="day-hist-fill" style="width:${{t||0}}%;background:${{c}}">${{t!=null&&t>15?t+'%':''}}</div>
      </div>
      <span class="day-hist-info" style="color:${{c}}">${{t!=null?t+'%':'—'}} <span class="day-hist-detail">${{ta}} / ${{te}}</span></span>
    </div>`;
  }}).join('');
  const spark=confirmedDias.slice(-14).map(d=>{{
    const s=(ALL_DATA[d]||{{}}).resultado_stats||{{}};
    let ta=0,te=0;
    Object.values(s).forEach(x=>{{ta+=x.acertos||0;te+=x.erros||0;}});
    const t=ta+te>0?Math.round(ta/(ta+te)*100):0;
    const c=colorForTaxa(t);
    return`<div class="hist-spark-bar" title="${{d}} · ${{t}}%" style="height:${{Math.max(8,t*.42)}}px;background:${{c}}"></div>`;
  }}).join('');

  el.innerHTML=`
    <div class="hist-page">
      <div class="hist-hero">
        <div>
          <div class="hist-kicker">Histórico Global</div>
          <div class="hist-title">Performance acumulada dos palpites confirmados</div>
          <div class="hist-subtitle">Consolida apenas jogos com resultado processado. Mercados sem avaliação ficam fora do ranking.</div>
        </div>
        <div class="hist-hero-insights">
          <div class="hist-insight">
            <div class="hist-insight-label">Melhor categoria</div>
            <div class="hist-insight-value"><span>${{melhorCategoria?melhorCategoria.label:'Sem histórico'}}</span><strong class="hist-insight-rate" style="color:${{melhorCategoriaRate?melhorCategoriaRate.color:'var(--muted)'}}">${{melhorCategoriaRate?melhorCategoriaRate.text:'—'}}</strong></div>
          </div>
          <div class="hist-insight">
            <div class="hist-insight-label">Melhor mercado</div>
            <div class="hist-insight-value"><span>${{melhor?melhor.m:'Sem mercado'}}</span><strong class="hist-insight-rate" style="color:${{melhorMercadoRate?melhorMercadoRate.color:'var(--muted)'}}">${{melhorMercadoRate?melhorMercadoRate.text:'—'}}</strong></div>
          </div>
        </div>
        <div class="hist-score-card">
          <div class="hist-score-label">Taxa geral</div>
          <div class="hist-score-val" style="color:${{cG}}">${{taxa!=null?taxa+'%':'—'}}</div>
          <div class="hist-score-note">${{g.total_acertos||0}} acertos · ${{g.total_erros||0}} erros</div>
        </div>
      </div>

      <div class="hist-visual">
        <div class="hist-visual-card">
          <div class="hist-visual-title">Categorias</div>
          <div class="hist-radial-wrap">
            <div class="hist-radial">${{radialHtml}}<div class="hist-radial-core">${{taxa!=null?taxa+'%':'—'}}</div></div>
            <div class="hist-vlegend">${{categoryLegend}}</div>
          </div>
          <div class="hist-legend-note"><strong>Alta</strong> = A+ · <strong>M&eacute;dia</strong> = A · <strong>Moderado</strong> = B. Taxas usam apenas palpites com resultado confirmado.</div>
        </div>
        <div class="hist-visual-card">
          <div class="hist-visual-title">Evolu&ccedil;&atilde;o dos dias confirmados</div>
          <svg class="hist-viz-svg" viewBox="0 0 320 118" preserveAspectRatio="none">
            <defs>
              <linearGradient id="histLineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#3B82F6"/>
                <stop offset="55%" stop-color="#8B5CF6"/>
                <stop offset="100%" stop-color="#00C896"/>
              </linearGradient>
              <linearGradient id="histAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#8B5CF6" stop-opacity=".32"/>
                <stop offset="100%" stop-color="#8B5CF6" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <line class="hist-viz-axis" x1="12" y1="24" x2="308" y2="24"></line>
            <line class="hist-viz-axis" x1="12" y1="59" x2="308" y2="59"></line>
            <line class="hist-viz-axis" x1="12" y1="94" x2="308" y2="94"></line>
            ${{areaPath?`<path class="hist-viz-area" d="${{areaPath}}"></path>`:''}}
            ${{linePath?`<path class="hist-viz-line" d="${{linePath}}"></path>`:''}}
          </svg>
          <div class="hist-legend-note"><strong>Linha</strong> = taxa diária dos jogos confirmados. Serve para ver tendência, não entra como nova regra de cálculo.</div>
        </div>
        <div class="hist-visual-card">
          <div class="hist-visual-title">Mercados em destaque</div>
          <div class="hist-market-mini">${{topMarketMini||'<div class="empty">Sem mercados avaliados.</div>'}}</div>
          <div class="hist-legend-note"><strong>Mercado</strong> = melhor taxa por tipo de palpite. Em empate, prioriza maior volume avaliado.</div>
        </div>
      </div>

      <div class="hist-summary-grid">
        <div class="hist-summary-card"><div class="hist-summary-label">Gerados</div><div class="hist-summary-value" style="color:var(--blue)">${{gerados}}</div><div class="hist-summary-note">todos disponíveis no site</div></div>
        <div class="hist-summary-card"><div class="hist-summary-label">Auditados</div><div class="hist-summary-value" style="color:var(--purple2)">${{g.total_palpites||0}}</div><div class="hist-summary-note">${{avaliados}} com green/red</div></div>
        <div class="hist-summary-card"><div class="hist-summary-label">Acertos</div><div class="hist-summary-value" style="color:var(--green)">${{g.total_acertos||0}}</div><div class="hist-summary-note">greens confirmados</div></div>
        <div class="hist-summary-card"><div class="hist-summary-label">Erros</div><div class="hist-summary-value" style="color:var(--red)">${{g.total_erros||0}}</div><div class="hist-summary-note">reds confirmados</div></div>
        <div class="hist-summary-card"><div class="hist-summary-label">Dias</div><div class="hist-summary-value" style="color:var(--teal)">${{g.dias_confirmados||0}}</div><div class="hist-summary-note">${{pendentes}} sem avaliação</div></div>
      </div>

      <div class="hist-audit-grid">
        ${{auditPanel(
          'Melhores Previsões',
          'Taxa dos palpites exibidos na aba Melhores Previsões, separados por nível de confiança.',
          bestStats.geral,
          breakRow('Confiança Alta',bestStats.alta,'alta')+breakRow('Confiança Média',bestStats.media,'media')+breakRow('Moderado',bestStats.moderado,'moderado'),
          'pro'
        )}}
        ${{auditPanel(
          'Top 5 do Dia',
          'Taxa acumulada dos cinco cards destacados diariamente na Visão Geral.',
          topStats.geral,
          breakRow('Cards Top 5',topStats.geral,'pro')
        )}}
        ${{auditPanel(
          'Bilhetes',
          'Taxa por bilhete fechado: green quando todas as seleções avaliadas batem.',
          ticketPickStat(ticketStats.geral),
          ticketRow('Bilhete do dia',ticketStats.dia)+ticketRow('Bingo do dia',ticketStats.bingo)+ticketRow('Premium 4x',ticketStats.premium)+ticketRow('Elite',ticketStats.elite)
        )}}
      </div>

      <div class="hist-layout">
        <div class="hist-panel">
          <div class="hist-panel-head">
            <div>
              <div class="hist-panel-title">Ranking por mercado</div>
              <div class="hist-summary-note">${{melhor?`Melhor: ${{melhor.m}} · ${{melhor.taxa}}%`:'Sem mercado avaliado'}}</div>
            </div>
            <div class="hist-panel-note">${{marketStats.length}} mercados</div>
          </div>
          <div class="hist-market-list">${{mktCards||'<div class="empty">Sem mercados avaliados.</div>'}}</div>
        </div>

        <div class="hist-panel">
          <div class="hist-panel-head">
            <div>
              <div class="hist-panel-title">Evolução diária</div>
              <div class="hist-summary-note">Últimos dias confirmados em ordem cronológica</div>
            </div>
            <div class="hist-panel-note">${{confirmedDias.length}} dias</div>
          </div>
          <div class="hist-days">${{timeline||'<div class="empty">Sem dias confirmados.</div>'}}</div>
          ${{spark?`<div class="hist-spark">${{spark}}</div>`:''}}
        </div>
      </div>
    </div>`;
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
    status.textContent = `Dados já carregados para ${{dateKey}}`;
    status.className = 'cal-status success';
    closeCal();
    setTimeout(()=>switchDate(dateKey), 300);
    return;
  }}

  // Need to trigger workflow
  const token = localStorage.getItem(GH_TOKEN_KEY) || prompt('Cole seu GH_TOKEN para acionar o workflow:');
  if(!token){{ status.textContent = 'Token não fornecido.'; status.className='cal-status error'; return; }}
  localStorage.setItem(GH_TOKEN_KEY, token);

  status.textContent = `Acionando coleta para ${{apiDate}}...`;
  status.className = 'cal-status loading';

  // Trigger coletar workflow
  const ok = await triggerWorkflow('build.yml', {{ date: apiDate }}, token);
  if(!ok){{ status.textContent = 'Erro ao acionar workflow. Verifique o token.'; status.className='cal-status error'; return; }}

  status.textContent = `Coleta iniciada para ${{apiDate}}! O dashboard atualiza em ~2 min.`;
  status.className = 'cal-status success';

  // If past date, also trigger confirmar
  if(isPast){{
    setTimeout(async()=>{{
      status.textContent = `Acionando confirmação de resultados...`;
      status.className = 'cal-status loading';
      const ok2 = await triggerWorkflow('confirmar.yml', {{ date: apiDate }}, token);
      if(ok2){{
        status.textContent = `Coleta + confirmação iniciadas! Aguarde ~3 min e recarregue.`;
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
const FALLBACK_ICONS={{
  'layout-dashboard':'<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
  'bar-chart-2':'<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  'target':'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  'brain-circuit':'<path d="M12 5a3 3 0 0 0-5.8-1A3.5 3.5 0 0 0 3 7.5c0 1 .4 1.9 1 2.5a4 4 0 0 0 0 6 3.5 3.5 0 0 0 3.8 3.4A3 3 0 0 0 12 17"/><path d="M12 5a3 3 0 0 1 5.8-1A3.5 3.5 0 0 1 21 7.5c0 1-.4 1.9-1 2.5a4 4 0 0 1 0 6 3.5 3.5 0 0 1-3.8 3.4A3 3 0 0 1 12 17"/><path d="M9 12h6"/><path d="M12 9v6"/>',
  'credit-card':'<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>',
  'info':'<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  'log-in':'<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>',
  'chevron-down':'<path d="m6 9 6 6 6-6"/>',
  'rocket':'<path d="M4.5 16.5c-1.5 1.3-2 3.4-2 5 1.6 0 3.7-.5 5-2"/><path d="M9 15 4 10l6-2 4-4c2-2 5-2 7-1-1 2-1 5-3 7l-4 4-2 6-5-5Z"/><path d="M14 6h.01"/>',
  'arrow-right':'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  'grid-2x2':'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  'star':'<polygon points="12 2 15 8.5 22 9.3 17 14.1 18.2 21 12 17.6 5.8 21 7 14.1 2 9.3 9 8.5 12 2"/>',
  'ticket':'<path d="M2 9a3 3 0 0 0 0 6v3a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-3a3 3 0 0 0 0-6V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/>',
  'trending-up':'<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
  'shield-check':'<path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3Z"/><path d="m9 12 2 2 4-4"/>',
  'crosshair':'<circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/>',
  'corner-up-right':'<polyline points="15 14 20 9 15 4"/><path d="M4 20v-7a4 4 0 0 1 4-4h12"/>',
  'layers':'<path d="m12 2 10 5-10 5L2 7Z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
  'clock':'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  'check':'<path d="M20 6 9 17l-5-5"/>',
  'x':'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  'circle-alert':'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  'check-circle':'<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m9 11 3 3L22 4"/>',
  'x-circle':'<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
  'trophy':'<path d="M8 21h8"/><path d="M12 17v4"/><path d="M7 4h10v6a5 5 0 0 1-10 0Z"/><path d="M5 9H4a2 2 0 0 1-2-2V5h5"/><path d="M19 9h1a2 2 0 0 0 2-2V5h-5"/>',
  'list-checks':'<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  'lock':'<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  'circle-help':'<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-3 2-3 4"/><path d="M12 17h.01"/>'
}};
function renderFallbackIcons(){{
  document.querySelectorAll('[data-lucide]').forEach(el=>{{
    const name=el.getAttribute('data-lucide');
    const body=FALLBACK_ICONS[name];
    if(!body)return;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('viewBox','0 0 24 24');
    svg.setAttribute('fill','none');
    svg.setAttribute('stroke','currentColor');
    svg.setAttribute('stroke-width','2');
    svg.setAttribute('stroke-linecap','round');
    svg.setAttribute('stroke-linejoin','round');
    svg.setAttribute('aria-hidden','true');
    svg.setAttribute('data-lucide-fallback',name);
    svg.innerHTML=body;
    svg.className=el.className;
    const style=el.getAttribute('style');
    if(style)svg.setAttribute('style',style);
    el.replaceWith(svg);
  }});
}}
function refreshIcons(){{
  if(typeof lucide !== 'undefined') lucide.createIcons();
  else renderFallbackIcons();
}}

function showHistoricoGlobal(){{
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-strip-item').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.sidebar-item').forEach(el=>el.classList.remove('active'));
  document.getElementById('sb-historico')?.classList.add('active');
  const subBar=document.getElementById('sub-filter-bar');
  if(subBar){{subBar.classList.remove('visible');subBar.innerHTML='';}}
  document.getElementById('panel-historico').style.display='block';

  historicoVisible=true;
  renderHistoricoGlobal();
  refreshIcons();
}}

function switchDate(date){{
  const histPanel=document.getElementById('panel-historico');
  if(histPanel)histPanel.style.display='none';

  historicoVisible=false;
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-strip-item').forEach(t=>t.classList.remove('active'));
  const panel=document.getElementById('day-'+date);
  const tab=document.querySelector(`[data-date="${{date}}"]`);
  if(!panel){{ console.warn('Panel not found for date:',date); return; }}
  panel.classList.add('active');
  if(tab){{tab.classList.add('active');tab.scrollIntoView({{behavior:'smooth',block:'nearest',inline:'center'}});}}
  // Update sidebar active state
  updateSidebarActive(activeMkt[date]||'visao');
  activeDate=date;
  if(!activeMkt[date])activeMkt[date]='visao';
  switchMkt(date, activeMkt[date]);
  refreshIcons();
}}

function switchMkt(date,mkt){{
  activeMkt[date]=mkt;
  clearMarketCategoryState();
  const panel=document.getElementById('day-'+date);
  if(!panel)return;
  panel.querySelectorAll('.mkt-panel').forEach(p=>p.classList.remove('active'));
  panel.querySelectorAll('.mkt-tab').forEach(t=>t.classList.remove('active'));
  const mp=panel.querySelector('#mkt-'+date+'-'+mkt);
  const mt=panel.querySelector(`[data-mkt="${{mkt}}"]`);
  if(mp)mp.classList.add('active');
  if(mt)mt.classList.add('active');
  renderMkt(date,mkt);
  refreshIcons();
}}

function renderMkt(date,mkt){{
  const jogos=getJogos(date);
  if(mkt==='visao')          renderVisao(date,jogos);
  else if(mkt==='ranking')   renderRanking(date,jogos);
  else if(mkt==='over15')    renderOver15(date,jogos);
  else if(mkt==='over25')    renderOver25(date,jogos);
  else if(mkt==='escanteios')renderEsc(date,jogos);
  else if(mkt==='cartoes')   renderCart(date,jogos);
  else if(mkt==='bilhetes')     renderBilhetes(date,jogos);
  else if(mkt==='historico_dia') renderHistoricoDia(date,jogos);
}}

// ── Sidebar navigation ──────────────────────────────────────────────
function sidebarNav(mkt){{
  // If no date active, use the most recent one
  if(!activeDate){{
    const d = dates[dates.length-1];
    if(d) switchDate(d);
    else return;
  }}
  switchMkt(activeDate, mkt);
  updateSidebarActive(mkt);
}}

function updateSidebarActive(mkt){{
  document.querySelectorAll('.sidebar-item').forEach(el=>el.classList.remove('active'));
  const map = {{
    'visao':'sb-visao','ranking':'sb-ranking','bilhetes':'sb-bilhetes'
  }};
  const id = map[mkt];
  if(id) document.getElementById(id)?.classList.add('active');
  // Update sidebar counts
  if(activeDate){{
    const jogos = getJogos(activeDate);
    const nprem = jogos.filter(j=>j.best_grade==='A+'||j.best_grade==='A').length;
    const el = document.getElementById('sb-cnt-ranking');
    if(el) el.textContent = nprem || '—';
  }}
  refreshIcons();
}}

// ── Market category & sub-filters ──────────────────────────────────
let activeCat = null;
let activeSubFilter = null;

const CAT_SUBFILTERS = {{
  'gols':       [{{key:'over15',  label:'Over 1.5'}}, {{key:'over25', label:'Under 3.5'}}],
  'escanteios': [{{key:'esc75',   label:'Over 7.5'}}, {{key:'esc85',  label:'Over 8.5'}}],
  'cartoes':    [{{key:'cart25',  label:'Over 2.5'}}, {{key:'cart35', label:'Over 3.5'}}],
  'resultado':  [],
}};

function clearMarketCategoryState(){{
  activeCat = null;
  activeSubFilter = null;
  document.querySelectorAll('.mkt-cat-tab').forEach(t=>t.classList.remove('active'));
  const bar = document.getElementById('sub-filter-bar');
  if(bar){{
    bar.classList.remove('visible');
    bar.innerHTML = '';
  }}
}}

function renderSubFilters(cat){{
  const bar = document.getElementById('sub-filter-bar');
  if(!bar) return;
  const filters = CAT_SUBFILTERS[cat] || [];
  if(!filters.length){{
    bar.classList.remove('visible');
    bar.innerHTML = '';
    return;
  }}
  bar.classList.add('visible');
  // Default first sub-filter active
  if(!activeSubFilter || !filters.find(f=>f.key===activeSubFilter)){{
    activeSubFilter = filters[0].key;
  }}
  bar.innerHTML = filters.map(f=>
    `<div class="sub-filter-btn${{activeSubFilter===f.key?' active':''}}" onclick="switchSubFilter('${{f.key}}')">${{f.label}}</div>`
  ).join('');
  refreshIcons();
}}

function switchSubFilter(key){{
  if(!activeCat) return;
  activeSubFilter = key;
  // Re-render sub-filter buttons
  renderSubFilters(activeCat);
  if(!activeDate) return;
  renderCatContent(activeDate, activeCat, key);
}}


function switchCat(cat){{
  activeCat = cat;
  activeSubFilter = null;
  updateSidebarActive(null);
  document.querySelectorAll('.mkt-cat-tab').forEach(t=>t.classList.remove('active'));
  document.querySelector(`[data-cat="${{cat}}"]`)?.classList.add('active');
  renderSubFilters(cat);
  if(!activeDate) return;
  const filters = CAT_SUBFILTERS[cat];
  const firstKey = filters && filters.length ? filters[0].key : null;
  if(firstKey) activeSubFilter = firstKey;
  renderCatContent(activeDate, cat, firstKey);
  refreshIcons();
}}

function renderCatContent(date, cat, subKey){{
  const jogos = getJogos(date);
  if(cat === 'gols'){{
    if(subKey === 'over15') renderOver15(date, jogos);
    else renderOver25(date, jogos);
    const panel = document.getElementById('mkt-'+date+'-over15');
    const panel2 = document.getElementById('mkt-'+date+'-over25');
    document.querySelectorAll(`#day-${{date}} .mkt-panel`).forEach(p=>p.classList.remove('active'));
    if(subKey === 'over15' && panel) panel.classList.add('active');
    else if(panel2) panel2.classList.add('active');
  }} else if(cat === 'escanteios'){{
    renderEsc(date, jogos);
    document.querySelectorAll(`#day-${{date}} .mkt-panel`).forEach(p=>p.classList.remove('active'));
    const p = document.getElementById('mkt-'+date+'-escanteios');
    if(p) p.classList.add('active');
  }} else if(cat === 'cartoes'){{
    renderCart(date, jogos);
    document.querySelectorAll(`#day-${{date}} .mkt-panel`).forEach(p=>p.classList.remove('active'));
    const p = document.getElementById('mkt-'+date+'-cartoes');
    if(p) p.classList.add('active');
  }} else if(cat === 'resultado'){{
    // Em breve
    document.querySelectorAll(`#day-${{date}} .mkt-panel`).forEach(p=>p.classList.remove('active'));
    const p = document.getElementById('mkt-'+date+'-visao');
    if(p){{
      p.classList.add('active');
      p.innerHTML=`<div class="empty" style="padding:60px;text-align:center">
        <div style="font-size:32px;margin-bottom:12px">${{ico('lock',28)}}</div>
        <div style="font-size:16px;font-weight:700;color:var(--text);margin-bottom:6px">Resultado Final</div>
        <div style="font-size:13px;color:var(--muted)">Esta funcionalidade estará disponível em breve.</div>
      </div>`;
    }}
  }}
}}
// Inicializar ícones Lucide
if(typeof lucide !== 'undefined') lucide.createIcons();

// ── Tema claro/escuro ──────────────────────────────────────────────
function setThemeIcon(icon){{
  const btn = document.getElementById('theme-btn');
  if(!btn) return;
  const sun=`<svg id="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="12" cy="12" r="4"></circle>
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"></path>
  </svg>`;
  const moon=`<svg id="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
  </svg>`;
  btn.innerHTML=icon==='moon'?moon:sun;
}}
function toggleTheme(){{
  const html = document.documentElement;
  const isLight = html.getAttribute('data-theme') === 'light';
  if(isLight){{
    html.removeAttribute('data-theme');
    localStorage.setItem('wm_theme','dark');
    setThemeIcon('sun');
  }} else {{
    html.setAttribute('data-theme','light');
    localStorage.setItem('wm_theme','light');
    setThemeIcon('moon');
  }}
}}
// Restaurar tema salvo
(function(){{
  const saved = localStorage.getItem('wm_theme');
  if(saved === 'light'){{
    document.documentElement.setAttribute('data-theme','light');
    setTimeout(()=>setThemeIcon('moon'),100);
  }} else {{
    setTimeout(()=>setThemeIcon('sun'),100);
  }}
}})();

// Relógio navbar
function updateClock(){{
  const now = new Date();
  const d = String(now.getDate()).padStart(2,'0');
  const m = String(now.getMonth()+1).padStart(2,'0');
  const y = now.getFullYear();
  const h = String(now.getHours()).padStart(2,'0');
  const min = String(now.getMinutes()).padStart(2,'0');
  const el = document.getElementById('navbar-clock');
  if(el) el.textContent = `${{d}}/${{m}}/${{y}} ${{h}}:${{min}}`;
}}
updateClock();
setInterval(updateClock, 30000);

// Ordenar datas corretamente (DD-MM-YYYY)
const dates=Object.keys(ALL_DATA).sort((a,b)=>{{
  const [da,ma,ya]=a.split('-').map(Number);
  const [db,mb,yb]=b.split('-').map(Number);
  return new Date(ya,ma-1,da)-new Date(yb,mb-1,db);
}});

// Aguardar DOM completo antes de renderizar
window.addEventListener('DOMContentLoaded',function(){{
  if(dates.length){{
    const today = new Date().toLocaleDateString('pt-BR',{{day:'2-digit',month:'2-digit',year:'numeric'}}).split('/').join('-');
const todayKey = today;
const targetDate = dates.includes(todayKey) ? todayKey : dates.filter(d=>{{
  const [dd,mm,yyyy]=d.split('-').map(Number);
  return new Date(yyyy,mm-1,dd) <= new Date();
}}).pop() || dates[dates.length-1];
switchDate(targetDate);
  }}
}});

// Fallback se DOMContentLoaded já disparou
if(document.readyState==='complete'||document.readyState==='interactive'){{
  setTimeout(function(){{
    if(dates.length&&!activeDate){{
      const today = new Date().toLocaleDateString('pt-BR',{{day:'2-digit',month:'2-digit',year:'numeric'}}).split('/').join('-');
const todayKey = today;
const targetDate = dates.includes(todayKey) ? todayKey : dates.filter(d=>{{
  const [dd,mm,yyyy]=d.split('-').map(Number);
  return new Date(yyyy,mm-1,dd) <= new Date();
}}).pop() || dates[dates.length-1];
switchDate(targetDate);
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

</script>
</body>
</html>'''

if __name__ == '__main__':
    gerar_site()

