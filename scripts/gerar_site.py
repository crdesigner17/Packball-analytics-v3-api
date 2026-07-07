"""
WinMetrics — Gerador de Site v3.1
- Resultados integrados: linhas verde/vermelho/amarelo em cada tabela
- Placar nos cards Top 5
- KPI de assertividade no header
- Aba Histórico com gráfico de evolução por mercado
"""
import csv, json, os, re, unicodedata
from datetime import datetime, timezone
from ligas_config import LEAGUE_ALIASES, blocked_name, favorite_league_names, is_allowed_game, read_favorite_rows

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
OUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'index.html')
FAVORITE_LEAGUES = favorite_league_names()

def build_league_country_map():
    items = {}
    for row in read_favorite_rows():
        country = row.get('country') or ''
        league = row.get('league') or ''
        if not country or not league:
            continue
        meta = {'country': country}
        items.setdefault(league.lower(), meta)
        for alias in LEAGUE_ALIASES.get(league, []):
            items.setdefault(alias.lower(), meta)
    return items

LEAGUE_COUNTRY_MAP = build_league_country_map()

def filter_favorite_leagues(day_data):
    if not FAVORITE_LEAGUES or not isinstance(day_data, dict):
        return day_data
    def allowed_item(item):
        return is_allowed_game(item.get('country') or item.get('pais') or '', item.get('liga'))
    filtered = dict(day_data)
    filtered['jogos'] = [
        j for j in day_data.get('jogos', [])
        if (
            not isinstance(j, dict) or
            (
                allowed_item(j) and
                not blocked_name(' '.join(str(j.get(k, '')) for k in ('liga', 'jogo', 'home', 'away')))
            )
        )
    ]
    filtered['top5'] = [
        name for name in day_data.get('top5', [])
        if any(j.get('jogo') == name for j in filtered['jogos'])
    ]
    for key in ('palpites_snapshot',):
        if isinstance(day_data.get(key), list):
            filtered[key] = [
                j for j in day_data.get(key, [])
                if allowed_item(j)
            ]
    bilhetes_snapshot = day_data.get('bilhetes_snapshot')
    if isinstance(bilhetes_snapshot, dict):
        bilhetes_filtered = dict(bilhetes_snapshot)
        if isinstance(bilhetes_filtered.get('bilheteDia'), dict):
            sels = [s for s in bilhetes_filtered['bilheteDia'].get('sels', []) if allowed_item(s)]
            bilhetes_filtered['bilheteDia'] = dict(bilhetes_filtered['bilheteDia'], sels=sels)
        bilhetes = []
        for bilhete in bilhetes_snapshot.get('bilhetes', []):
            b = dict(bilhete.get('b') or {})
            sels = [s for s in b.get('sels', []) if allowed_item(s)]
            if not sels:
                continue
            b['sels'] = sels
            bilhete_copy = dict(bilhete)
            bilhete_copy['b'] = b
            bilhetes.append(bilhete_copy)
        bilhetes_filtered['bilhetes'] = bilhetes
        filtered['bilhetes_snapshot'] = bilhetes_filtered
    return filtered

def load_index():
    path = os.path.join(DATA_DIR, 'index.json')
    if not os.path.exists(path): return []
    with open(path, encoding='utf-8') as f: return json.load(f)

NON_CARD_MARKET_SCORES = [
    ('Over 1.5', 'score_15', 'grade_15', lambda j: j.get('passou_filtro')),
    ('Over 2.5', 'score_25', 'grade_25', lambda j: True),
    ('BTTS', 'score_btts', 'grade_btts', lambda j: True),
    ('Over 0.5 HT', 'score_05ht', 'grade_05ht', lambda j: True),
    ('Under 4.5', 'score_u45', 'grade_u45', lambda j: True),
    ('Under 3.5', 'score_u35', 'grade_u35', lambda j: j.get('under35_filter')),
    ('Esc 7.5', 'score_esc75', 'grade_esc75', lambda j: True),
    ('Esc 8.5', 'score_esc85', 'grade_esc85', lambda j: True),
]

def is_card_market(mkt):
    return 'cart' in str(mkt or '').lower()

def sanitize_card_markets(day_data):
    if not isinstance(day_data, dict):
        return day_data
    stats_summary = day_data.get('stats')
    if isinstance(stats_summary, dict):
        stats_summary.pop('cart25_aprovados', None)
    for stats_key in ('resultado_stats', 'resultado_stats_full'):
        stats = day_data.get(stats_key)
        if isinstance(stats, dict):
            for market in list(stats):
                if is_card_market(market):
                    stats.pop(market, None)

    for jogo in day_data.get('jogos', []) or []:
        if not isinstance(jogo, dict):
            continue
        for key in list(jogo):
            key_norm = str(key).lower()
            if 'card' in key_norm or 'cart' in key_norm:
                jogo.pop(key, None)
        resultado = jogo.get('resultado')
        if isinstance(resultado, dict):
            for key in ('cards_total', 'cart25_ok', 'cart35_ok'):
                resultado.pop(key, None)
        acertos = jogo.get('acertos')
        if isinstance(acertos, dict):
            for market in list(acertos):
                if is_card_market(market):
                    acertos.pop(market, None)
        if is_card_market(jogo.get('best_mkt')) or is_card_market(jogo.get('palpite_mkt')):
            candidates = []
            for market, score_key, grade_key, allowed in NON_CARD_MARKET_SCORES:
                try:
                    score = float(jogo.get(score_key) or 0)
                except Exception:
                    score = 0
                if score > 0 and allowed(jogo):
                    candidates.append((score, market, grade_key))
            if candidates:
                score, market, grade_key = max(candidates)
                jogo['best_mkt'] = market
                jogo['best_score'] = round(score, 1)
                jogo['best_grade'] = jogo.get(grade_key) or jogo.get('best_grade') or 'D'
                jogo['palpite_mkt'] = market
                jogo['palpite_score'] = round(score, 1)
                jogo['palpite_grade'] = jogo.get(grade_key) or jogo.get('palpite_grade') or 'D'

    def keep_non_card(item):
        if is_card_market((item or {}).get('mkt')):
            return False
        if isinstance(item, dict):
            for key in list(item):
                key_norm = str(key).lower()
                if 'card' in key_norm or 'cart' in key_norm:
                    item.pop(key, None)
        resultado = (item or {}).get('resultado')
        if isinstance(resultado, dict):
            for key in ('cards_total', 'cart25_ok', 'cart35_ok'):
                resultado.pop(key, None)
        return True

    if isinstance(day_data.get('palpites_snapshot'), list):
        day_data['palpites_snapshot'] = [item for item in day_data['palpites_snapshot'] if keep_non_card(item)]
    bilhetes_snapshot = day_data.get('bilhetes_snapshot')
    if isinstance(bilhetes_snapshot, dict):
        if isinstance(bilhetes_snapshot.get('bilheteDia'), dict):
            sels = [s for s in bilhetes_snapshot['bilheteDia'].get('sels', []) if keep_non_card(s)]
            bilhetes_snapshot['bilheteDia']['sels'] = sels
        for bilhete in bilhetes_snapshot.get('bilhetes', []):
            b = bilhete.get('b') or {}
            if isinstance(b, dict):
                b['sels'] = [s for s in b.get('sels', []) if keep_non_card(s)]
    return day_data

def load_day(date_str):
    path = os.path.join(DATA_DIR, f'{date_str}.json')
    if not os.path.exists(path): return None
    with open(path, encoding='utf-8') as f:
        day_data = filter_favorite_leagues(json.load(f))
    return sanitize_card_markets(enrich_resultado_final_csv(date_str, day_data))

def norm_team_name(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'\b(ec|fc|sc|ac|afc|cf|club|recife|campinas)\b', ' ', text.lower())
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    aliases = {
        'atletico go': 'atletico goianiense',
        'athletico': 'athletic',
        'nautico': 'nautico',
        'goias': 'goias',
        'ceara': 'ceara',
        'avai': 'avai',
        'confianca': 'confianca',
        'maranhao': 'maranhao',
    }
    return aliases.get(text, text)

def team_match_score(a, b):
    na, nb = norm_team_name(a), norm_team_name(b)
    if not na or not nb:
        return 0
    if na == nb or na in nb or nb in na:
        return 3
    ta, tb = set(na.split()), set(nb.split())
    return len(ta & tb)

def csv_float(value):
    try:
        text = str(value or '').strip().replace(',', '.')
        return float(text) if text else None
    except Exception:
        return None

def find_resultado_final_csv(date_str):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    date_short = '-'.join(date_str.split('-')[:2])
    candidates = [
        os.path.join(root, 'data', 'csv', date_str),
        os.path.join(root, 'data', 'csv', date_short),
        os.path.join(root, 'data', 'csv'),
        os.path.join(root, 'data', 'packball', date_str),
        os.path.join(root, 'data', 'packball', date_short),
        os.path.join(root, 'frontend', 'data', 'packball', date_str),
        os.path.join(root, 'frontend', 'data', 'packball', date_short),
        os.path.join(root, 'scripts'),
        os.path.join(root, 'docs', 'data'),
        root,
        os.path.join(os.path.expanduser('~'), 'Downloads'),
    ]
    target = date_str.lower()
    packball_roots = [
        os.path.join(root, 'data', 'packball'),
        os.path.join(root, 'frontend', 'data', 'packball'),
    ]
    search_folders = list(candidates)
    for packball_root in packball_roots:
        if os.path.isdir(packball_root):
            for current, dirs, _files in os.walk(packball_root):
                depth = os.path.relpath(current, packball_root).count(os.sep)
                if depth > 1:
                    dirs[:] = []
                    continue
                search_folders.append(current)
    seen = set()
    for folder in search_folders:
        folder_key = os.path.abspath(folder).lower()
        if folder_key in seen:
            continue
        seen.add(folder_key)
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            lower = fname.lower()
            if not lower.endswith('.csv'):
                continue
            if target in lower and 'resultado' in lower and ('final' in lower or '1x2' in lower):
                return os.path.join(folder, fname)
    return None

def read_resultado_final_rows(path, date_str):
    rows = []
    if not path:
        return rows
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)
        for raw in reader:
            if len(raw) < 13 or not str(raw[3] if len(raw) > 3 else '').startswith(date_str):
                continue
            rows.append({
                'source': os.path.basename(path),
                'country': raw[0] if len(raw) > 0 else None,
                'league': raw[2] if len(raw) > 2 else None,
                'hour': raw[3] if len(raw) > 3 else None,
                'home': raw[5] if len(raw) > 5 else None,
                'away': raw[8] if len(raw) > 8 else None,
                'odds_h': csv_float(raw[11] if len(raw) > 11 else None),
                'odds_a': csv_float(raw[12] if len(raw) > 12 else None),
                'ppg_h': csv_float(raw[38] if len(raw) > 38 else None),
                'ppg_a': csv_float(raw[39] if len(raw) > 39 else None),
                'exg_h': csv_float(raw[51] if len(raw) > 51 else None),
                'exg_a': csv_float(raw[52] if len(raw) > 52 else None),
                'avg_shots_h': csv_float(raw[60] if len(raw) > 60 else None),
                'avg_shots_a': csv_float(raw[61] if len(raw) > 61 else None),
                'avg_sot_h': csv_float(raw[62] if len(raw) > 62 else None),
                'avg_sot_a': csv_float(raw[63] if len(raw) > 63 else None),
                'raw': raw,
            })
    return rows

def enrich_resultado_final_csv(date_str, day_data):
    if not isinstance(day_data, dict) or not day_data.get('jogos'):
        return day_data
    rows = read_resultado_final_rows(find_resultado_final_csv(date_str), date_str)
    if not rows:
        return day_data
    for jogo in day_data.get('jogos', []):
        best, best_score = None, 0
        for row in rows:
            score = team_match_score(jogo.get('home'), row.get('home')) + team_match_score(jogo.get('away'), row.get('away'))
            if score > best_score:
                best, best_score = row, score
        if best and best_score >= 4:
            jogo['rf_csv'] = best
    return day_data

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
                'Esc 7.5','Esc 8.5']
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

RESPONSIVE_CSS = r'''
/* WM RESPONSIVE MOBILE */
html,body{max-width:100%;overflow-x:hidden}
img,svg,canvas,video{max-width:100%}
.tbl-wrap,.corner-table-wrap,.table-wrap,.live-table-wrap,.prev-tbl-wrap,.compare-table-wrap,.stats-table-card,.mini-table-card{
  -webkit-overflow-scrolling:touch;scrollbar-width:thin;scrollbar-color:var(--border) transparent;
}
.tbl-wrap table,.corner-table-wrap table{table-layout:auto}
@media(max-width:1180px){
  .ranking-cols{grid-template-columns:1fr}
  .hist-visual{grid-template-columns:1fr}
  .hist-hero{grid-template-columns:1fr 1fr}
  .hist-hero>div:first-child{grid-column:1/-1}
  .hist-layout{grid-template-columns:1fr}
  .hg-kpi-row{grid-template-columns:repeat(3,minmax(0,1fr))}
  .hg-panels{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:900px){
  :root{--mobile-topbar-h:52px}
  .app-layout{display:flex;flex-direction:column;gap:0;min-height:100vh;padding:0;background:var(--bg)}
  .sidebar{
    position:sticky;top:0;z-index:180;width:100%;height:auto;min-height:var(--mobile-topbar-h);
    max-height:none;border-right:0;border-bottom:1px solid var(--border);border-radius:0;
    padding:7px 8px;background:var(--s1);overflow-x:auto;overflow-y:hidden;
    display:flex;flex-direction:row;align-items:center;gap:8px;
  }
  .sidebar::-webkit-scrollbar{display:none}
  .sidebar-logo{
    min-height:0;padding:0 8px 0 0;border-bottom:0;flex:0 0 auto;
    display:flex;align-items:center;gap:8px;
  }
  .sidebar-logo-icon{width:30px;height:30px}
  .sidebar-logo-name{font-size:14px}
  .sidebar-logo-sub{font-size:8px;letter-spacing:1.4px}
  .sidebar-section{padding:0;margin:0;display:flex;align-items:center;gap:6px;min-width:0;overflow-x:auto;scrollbar-width:none}
  .sidebar-section::-webkit-scrollbar{display:none}
  .sidebar-divider,.sidebar-group-label,.sidebar-upgrade{display:none!important}
  .sidebar-item{
    height:36px;margin:0;flex:0 0 auto;padding:0 10px;border-radius:8px;
    white-space:nowrap;font-size:12px;border-left:0;display:inline-flex;align-items:center;
  }
  .sidebar-item.active{border-left:0;border-bottom:2px solid var(--green);padding-left:10px;background:rgba(0,200,150,.10)}
  .sidebar-pro,.sidebar-cnt{display:none}
  .content-area{width:100%;flex:1 1 auto}
  .page-hero-search,.page-hero-title,.main,.date-strip-shell,.mkt-cat-bar,.sub-filter-bar{
    width:calc(100% - 20px);max-width:none;
  }
  .page-hero-search{min-height:auto;padding:9px 0;align-items:stretch;gap:8px}
  .page-hero-title{min-height:auto;padding:18px 0 14px}
  .page-hero-heading h1{font-size:20px}
  .page-hero-subtitle{font-size:12px;max-width:100%}
  .page-hero-actions{min-width:0}
  .date-strip-shell{top:var(--mobile-topbar-h);grid-template-columns:38px minmax(0,1fr) 38px}
  .date-strip-arrow{height:48px}
  .date-strip-item{height:48px;min-width:62px;padding:0 10px}
  .date-strip-dow{font-size:10px}
  .date-strip-day{font-size:12px}
  .mkt-cat-bar{
    top:calc(var(--mobile-topbar-h) + 48px);overflow-x:auto;justify-content:flex-start;
    scrollbar-width:none;
  }
  .mkt-cat-bar::-webkit-scrollbar{display:none}
  .mkt-cat-tab{flex:0 0 auto;min-width:max-content;height:40px;padding:0 12px;font-size:12px}
  .sub-filter-bar{
    top:calc(var(--mobile-topbar-h) + 88px);overflow-x:auto;flex-wrap:nowrap;
    justify-content:flex-start;padding:6px 8px;scrollbar-width:none;
  }
  .sub-filter-bar::-webkit-scrollbar{display:none}
  .sub-filter-btn{flex:0 0 auto}
  .main{padding:14px 0 22px}
  .kpi-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
  .kpi{min-width:0;padding:11px 10px}
  .top-grid{grid-template-columns:1fr}
  .top-card{padding:13px}
  .top-liga,.top-jogo{padding-right:72px}
  .rf-grid,.corner-summary-grid,.bilhete-grid,.bilhete-destaques,.hist-summary-grid,.hist-audit-grid,.hg-panels,.hg-bottom{
    grid-template-columns:1fr;
  }
  .hg-hero,.hist-hero{grid-template-columns:1fr;padding:14px;gap:10px}
  .hg-kpi-row{grid-template-columns:repeat(2,minmax(0,1fr))}
  .hg-kpi{padding:12px;gap:10px}
  .hg-kpi-icon{width:34px;height:34px;border-radius:9px}
  .hg-kpi-val{font-size:22px}
  .hist-hero>div:first-child{grid-column:auto}
  .hist-hero-insights{grid-template-columns:1fr}
  .hist-visual{grid-template-columns:1fr;padding:12px;border-radius:12px}
  .hist-radial-wrap{grid-template-columns:112px minmax(0,1fr);gap:10px}
  .hist-radial{width:112px;height:112px}
  .hist-break-row{grid-template-columns:minmax(0,1fr) 50px}
  .hist-break-row em{display:none}
  .hist-panel-head{align-items:flex-start;flex-direction:column;gap:4px}
  .hist-panel-note{white-space:normal}
  .day-hist-row{grid-template-columns:52px minmax(0,1fr) 78px;gap:8px}
  .hist-market-row{grid-template-columns:26px minmax(0,1fr) 72px;padding:9px}
  .hg-rank-row{grid-template-columns:28px 6px minmax(0,1fr) 58px;gap:8px;padding:9px}
  .hg-day-row{grid-template-columns:42px minmax(0,1fr) 82px;gap:8px}
  .bilhete-dia,.bilhete-card{padding:14px}
  .bilhete-header{align-items:flex-start}
  .bilhete-row{
    display:grid;grid-template-columns:22px minmax(0,1fr);gap:6px 8px;align-items:start;
    padding:9px 0;
  }
  .bilhete-num{grid-row:1/4;width:auto}
  .bilhete-jogo{padding-right:0}
  .bilhete-mkt,.bilhete-odd-val,.bilhete-score-bar,.bilhete-res,.bilhete-market-stack{
    width:auto;min-width:0;max-width:none;padding-right:0;text-align:left;grid-column:2;
  }
  .bilhete-score-bar{width:100%;max-width:160px}
  .bilhete-market-line{grid-template-columns:minmax(0,1fr) 74px 42px;gap:6px}
  .bilhete-res{text-align:left}
  .bilhete-footer{align-items:flex-start;flex-direction:column}
  .ranking-col table,table{min-width:680px}
  .corner-table-wrap table{min-width:1080px}
  .cal-modal{align-items:flex-start;overflow-y:auto;padding:14px}
  .cal-box{width:min(100%,360px);min-width:0;padding:16px;margin:0 auto}
}
@media(max-width:560px){
  .sidebar-logo-text{display:none}
  .sidebar{padding:7px 6px}
  .sidebar-item{height:34px;padding:0 9px;font-size:11px;gap:7px}
  .sidebar-item i{width:14px!important;height:14px!important}
  .page-hero-search{flex-direction:column}
  .page-hero-searchbox{width:100%}
  .page-hero-actions{width:100%;margin-left:0;display:grid;grid-template-columns:1fr;gap:8px}
  .wm-update-pill,.wm-date-filter,.wm-date-filter-trigger{width:100%}
  .wm-date-filter-menu{left:0;right:auto;width:min(318px,calc(100vw - 32px))}
  .wm-filter-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}
  .wm-filter-fields{grid-template-columns:1fr}
  .kpi-row,.hg-kpi-row{grid-template-columns:1fr}
  .top-bottom{align-items:flex-start;flex-direction:column;gap:8px}
  .top-grade-block{align-items:flex-start}
  .hist-radial-wrap{grid-template-columns:1fr;justify-items:center}
  .hist-vlegend{width:100%}
  .hist-summary-grid{grid-template-columns:1fr}
  .hg-hero{padding:14px}
  .hg-taxa-val{font-size:32px}
  .hg-panel,.hg-card,.hist-panel{padding:13px}
  .hg-rank-detail,.hg-day-info{white-space:normal}
  .corner-summary-grid{grid-template-columns:1fr}
  .ranking-col table,table{min-width:620px}
  .corner-table-wrap table{min-width:980px}
  .empty{padding:24px 12px}
}
/* WM RESPONSIVE MOBILE END */
'''


def ensure_responsive_css(html):
    pattern = r'/\* WM RESPONSIVE MOBILE \*/.*?/\* WM RESPONSIVE MOBILE END \*/\n?'
    if '/* WM RESPONSIVE MOBILE */' in html:
        return re.sub(pattern, RESPONSIVE_CSS + '\n', html, flags=re.DOTALL)
    return html.replace('</style>', RESPONSIVE_CSS + '\n</style>', 1)


def apply_visual_overrides(html):
    """Aplica somente ajustes visuais ao HTML gerado, preservando dados e lógica."""
    html = html.replace(
        "--nav-h:56px;--search-h:126px;--date-strip-h:53px;--market-bar-h:42px;--top-gap:8px;",
        "--nav-h:0px;--search-h:0px;--date-strip-h:53px;--market-bar-h:42px;--top-gap:0px;"
    )
    html = html.replace(
        "[data-theme=\"light\"] .sidebar{background:#ffffff;border-right-color:#e2e6f3}",
        "[data-theme=\"light\"] .sidebar{background:#ffffff;border-right-color:#e2e6f3}\n"
        "[data-theme=\"light\"] .sidebar-logo-name{color:#0F172A}\n"
        "[data-theme=\"light\"] .sidebar-logo{border-bottom-color:#e2e6f3}"
    )
    html = html.replace(
        "  box-shadow:0 2px 20px rgba(0,0,0,.5);\n}\n",
        "  box-shadow:0 2px 20px rgba(0,0,0,.5);\n}\n.navbar{display:none!important}\n",
        1
    )
    html = html.replace(
        ".history-search-global{\n  padding:var(--top-gap) 0 var(--top-gap);background:var(--bg);\n  position:sticky;top:var(--nav-h);z-index:130;width:calc(100% - 48px);max-width:1500px;margin:0 auto;\n}",
        ".history-search-global{\n  padding:var(--top-gap) 0 var(--top-gap);background:var(--bg);\n  position:sticky;top:var(--nav-h);z-index:130;width:calc(100% - 48px);max-width:1500px;margin:0 auto;\n}\n.history-search-global{display:none!important}"
    )
    html = html.replace("@media(max-width:920px){:root{--search-h:172px}", "@media(max-width:920px){:root{--search-h:0px}")
    html = html.replace("@media(max-width:560px){:root{--search-h:260px}", "@media(max-width:560px){:root{--search-h:0px}")
    html = html.replace(
        ".app-layout{display:flex;gap:var(--top-gap);min-height:calc(100vh - var(--nav-h));padding-top:var(--top-gap);background:var(--bg)}",
        ".app-layout{display:flex;gap:0;min-height:100vh;padding-top:0;background:var(--bg)}"
    )
    html = html.replace(
        "  position:sticky;top:calc(var(--nav-h) + var(--top-gap));height:calc(100vh - var(--nav-h) - var(--top-gap));\n"
        "  overflow-y:auto;z-index:80;\n"
        "  display:flex;flex-direction:column;\n"
        "  padding:12px 0;border-radius:0 10px 10px 0;",
        "  position:sticky;top:0;height:100vh;\n"
        "  overflow-y:auto;z-index:80;\n"
        "  display:flex;flex-direction:column;\n"
        "  padding:0;border-radius:0;"
    )
    html = html.replace(
        ".sidebar::-webkit-scrollbar{width:3px}",
        ".sidebar-logo{\n"
        "  padding:18px 20px 16px;display:flex;align-items:center;gap:10px;\n"
        "  border-bottom:1px solid var(--border);min-height:94px;\n"
        "}\n"
        ".sidebar-logo-icon{width:34px;height:34px;flex:0 0 auto}\n"
        ".sidebar-logo-text{display:flex;flex-direction:column;line-height:1}\n"
        ".sidebar-logo-name{font-size:16px;font-weight:800;color:#fff;letter-spacing:-.4px}\n"
        ".sidebar-logo-sub{font-size:9px;color:var(--blue);letter-spacing:2.4px;font-weight:700;text-transform:uppercase;margin-top:2px}\n"
        ".sidebar::-webkit-scrollbar{width:3px}"
    )
    html = html.replace(".sidebar-section{padding:0 8px;margin-bottom:4px}", ".sidebar-section{padding:10px 8px 0;margin-bottom:4px}")
    html = html.replace(
        ".sidebar-divider{height:1px;background:var(--border);margin:12px 16px}",
        ".sidebar-divider{height:1px;background:var(--border);margin:12px 16px}\n"
        ".sidebar-item.is-hidden,\n"
        ".sidebar-divider.is-hidden,\n"
        ".mkt-panel[id*=\"-bilhetes\"]{display:none!important}"
    )
    html = html.replace(".content-area::before{", ".content-area::before{", 1)
    html = html.replace(
        ".content-area.hist-mode::before{display:none}",
        ".content-area::before{display:none}\n.content-area.hist-mode::before{display:none}"
    )
    html = html.replace(
        ".content-area.hist-mode .history-search-global,\n.content-area.hist-mode .date-strip,",
        ".content-area.hist-mode .history-search-global,\n.content-area.hist-mode .date-strip-shell,\n.content-area.hist-mode .date-strip,"
    )
    html = html.replace(
        ".content-area.hist-mode .sub-filter-bar{display:none!important}",
        ".content-area.hist-mode .sub-filter-bar{display:none!important}\n.content-area.hist-mode .page-hero-title{display:none!important}",
        1
    )
    page_hero_css = r'''
.page-hero{
  background:#090e18;border-bottom:1px solid var(--border);
  box-shadow:0 1px 0 rgba(255,255,255,.02) inset;
}
.page-hero-search{
  min-height:52px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0;
  width:calc(100% - 48px);max-width:1500px;margin:0 auto;
}
.page-hero-searchbox{
  width:306px;max-width:100%;height:31px;border:1px solid rgba(148,163,184,.18);
  background:#111827;border-radius:6px;display:flex;align-items:center;gap:9px;
  padding:0 11px;color:var(--dim);
}
.page-hero-searchbox svg{width:14px;height:14px;stroke:currentColor;flex:0 0 auto}
.page-hero-searchbox input{
  width:100%;min-width:0;border:0;outline:0;background:transparent;
  color:var(--text2);font-size:12px;line-height:1;
}
.page-hero-searchbox input::placeholder{color:#68748a}
.page-hero-title{
  min-height:96px;padding:26px 0 20px;
  width:calc(100% - 48px);max-width:1500px;margin:0 auto;
  display:flex;flex-direction:column;align-items:flex-start;justify-content:center;
}
.page-hero-heading{display:flex;align-items:center;gap:9px;min-width:0}
.page-hero-heading h1{
  color:#fff;font-size:22px;font-weight:800;line-height:1.1;letter-spacing:-.3px;
}
.page-hero-pro{
  display:none;font-size:9px;font-weight:800;line-height:1;color:#fff;
  background:linear-gradient(135deg,#2563EB,#7C3AED);
  border-radius:4px;padding:4px 7px;letter-spacing:.5px;
}
.page-hero-pro.visible{display:inline-flex}
.page-hero-subtitle{
  margin-top:8px;color:#9ba9e7;font-size:13px;font-weight:500;line-height:1.35;
}
[data-theme="light"] .page-hero{background:#ffffff}
[data-theme="light"] .page-hero-searchbox{background:#f8fafc}
[data-theme="light"] .page-hero-heading h1{color:#0F172A}
[data-theme="light"] .page-hero-subtitle{color:#4f46e5}
'''
    html = html.replace("/* NEW DATE BAR */", page_hero_css + "\n/* NEW DATE BAR */")
    html = html.replace(
        ".date-strip{\n  background:var(--s1);border-bottom:1px solid var(--border);\n  display:flex;align-items:center;overflow-x:auto;\n  padding:0 16px;\n  scrollbar-width:thin;scrollbar-color:var(--border) transparent;\n  position:sticky;top:calc(var(--nav-h) + var(--search-h) + var(--top-gap));z-index:120;\n  border-left:none;border-radius:10px 10px 0 0;\n  box-shadow:0 8px 16px rgba(0,0,0,.18);overflow:hidden;\n  width:calc(100% - 48px);max-width:1500px;margin:0 auto;box-sizing:border-box;\n}\n.date-strip::-webkit-scrollbar{height:3px}\n.date-strip::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}",
        ".date-strip-shell{\n  position:sticky;top:calc(var(--nav-h) + var(--search-h) + var(--top-gap));z-index:120;\n  width:calc(100% - 48px);max-width:1500px;margin:0 auto;box-sizing:border-box;\n  display:grid;grid-template-columns:44px minmax(0,1fr) 44px;align-items:stretch;\n  background:var(--s1);border-bottom:1px solid var(--border);\n  border-radius:10px 10px 0 0;box-shadow:0 8px 16px rgba(0,0,0,.18);overflow:hidden;\n}\n.date-strip{\n  background:var(--s1);border-bottom:0;\n  display:flex;align-items:center;overflow-x:auto;\n  padding:0 12px;scrollbar-width:none;\n  border-left:none;border-radius:0;box-shadow:none;overflow-y:hidden;\n  width:100%;max-width:none;margin:0;box-sizing:border-box;scroll-behavior:smooth;\n}\n.date-strip::-webkit-scrollbar{display:none}\n.date-strip-arrow{\n  height:var(--date-strip-h);border:0;background:rgba(17,24,39,.94);color:var(--muted);\n  display:flex;align-items:center;justify-content:center;cursor:pointer;\n  border-right:1px solid var(--border);transition:background .15s,color .15s;\n  font-size:25px;font-weight:700;line-height:1;\n}\n.date-strip-arrow.next{border-right:0;border-left:1px solid var(--border)}\n.date-strip-arrow:hover{background:rgba(37,99,235,.12);color:var(--text)}\n.date-strip-arrow .date-arrow-fallback{display:inline-flex;align-items:center;justify-content:center;transform:translateY(-1px)}"
    )
    html = html.replace(
        ":root{--nav-h:52px}",
        ":root{--nav-h:0px}"
    )
    html = html.replace(
        ".main{padding:14px 0 18px;width:calc(100% - 16px)}",
        ".main{padding:14px 0 18px;width:calc(100% - 16px)}\n  .page-hero-search,.page-hero-title{width:calc(100% - 16px)}"
    )
    html = html.replace(
        ".date-strip,.mkt-cat-bar,.sub-filter-bar{width:calc(100% - 16px)}",
        ".date-strip-shell,.mkt-cat-bar,.sub-filter-bar{width:calc(100% - 16px)}"
    )
    sidebar_logo_html = r'''
    <div class="sidebar-logo">
      <svg class="sidebar-logo-icon" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id="sidebarLogoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#2563EB"/>
            <stop offset="100%" style="stop-color:#7C3AED"/>
          </linearGradient>
        </defs>
        <path d="M4,28 L10,12 L16,24 L20,16 L24,24 L30,12 L36,28" fill="none" stroke="url(#sidebarLogoGrad)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M26,10 L32,4" fill="none" stroke="#00C896" stroke-width="2.5" stroke-linecap="round"/>
        <polygon points="32,4 28,6 30,10" fill="#00C896"/>
      </svg>
      <div class="sidebar-logo-text">
        <span class="sidebar-logo-name">WinMetrics</span>
        <span class="sidebar-logo-sub">Analytics</span>
      </div>
    </div>'''
    html = html.replace('<aside class="sidebar" id="sidebar">\n    <div class="sidebar-section">', '<aside class="sidebar" id="sidebar">' + sidebar_logo_html + '\n    <div class="sidebar-section">')
    html = html.replace('<div class="sidebar-divider"></div>\n      <div class="sidebar-item" id="sb-bilhetes"', '<div class="sidebar-divider is-hidden"></div>\n      <div class="sidebar-item is-hidden" id="sb-bilhetes"')
    page_hero_html = r'''
    <section class="page-hero" aria-label="Cabe&ccedil;alho da p&aacute;gina">
      <div class="page-hero-search">
        <label class="page-hero-searchbox">
          <i data-lucide="search"></i>
          <input id="page-hero-search-input" type="search" placeholder="Buscar jogos, times, ligas..." autocomplete="off">
        </label>
      </div>
      <div class="page-hero-title">
        <div class="page-hero-heading">
          <h1 id="page-hero-title">Vis&atilde;o Geral</h1>
          <span class="page-hero-pro" id="page-hero-pro">PRO</span>
        </div>
        <p class="page-hero-subtitle" id="page-hero-subtitle">Resumo dos principais indicadores e oportunidades do dia.</p>
      </div>
    </section>'''
    html = html.replace('  <div class="content-area">\n    <div class="history-search-global"', '  <div class="content-area">' + page_hero_html + '\n    <div class="history-search-global"')
    html = html.replace('    <!-- DATE STRIP -->\n    <div class="date-strip" id="date-strip">', '    <!-- DATE STRIP -->\n    <div class="date-strip-shell">\n      <button class="date-strip-arrow prev" type="button" aria-label="Ver datas anteriores" onclick="shiftDateStrip(-1)">\n        <span class="date-arrow-fallback" aria-hidden="true">&#8249;</span>\n      </button>\n    <div class="date-strip" id="date-strip">')
    html = html.replace('    </div>\n\n    <!-- MARKET CATEGORY BAR -->', '    </div>\n      <button class="date-strip-arrow next" type="button" aria-label="Ver pr&oacute;ximas datas" onclick="shiftDateStrip(1)">\n        <span class="date-arrow-fallback" aria-hidden="true">&#8250;</span>\n      </button>\n    </div>\n\n    <!-- MARKET CATEGORY BAR -->', 1)
    hero_js = r'''
const PAGE_HERO_COPY = {
  visao: {title: 'Vis\u00e3o Geral', subtitle: 'Resumo dos principais indicadores e oportunidades do dia.'},
  ranking: {title: 'Melhores Previs\u00f5es', subtitle: 'As previs\u00f5es com maior probabilidade e valor esperado.', pro: true},
  bilhetes: {title: 'Bilhetes', subtitle: 'Combina\u00e7\u00f5es sugeridas para organizar entradas com mais crit\u00e9rio.'},
  historico: {title: 'Hist\u00f3rico Global', subtitle: 'Acompanhe a performance consolidada das previs\u00f5es.'},
  resultado: {title: 'Resultado Final', subtitle: 'Mercados de vencedor, dupla chance e prote\u00e7\u00f5es por jogo.'},
  gols: {title: 'Gols', subtitle: 'Leituras para linhas de gols com base nas estat\u00edsticas do confronto.'},
  escanteios: {title: 'Escanteios', subtitle: 'Oportunidades em cantos com volume e tend\u00eancia por partida.'}
};
function updatePageHero(key){
  const copy = PAGE_HERO_COPY[key] || PAGE_HERO_COPY.visao;
  const heroTitle = document.querySelector('.page-hero-title');
  const title = document.getElementById('page-hero-title');
  const subtitle = document.getElementById('page-hero-subtitle');
  const pro = document.getElementById('page-hero-pro');
  if(heroTitle) heroTitle.hidden = key === 'historico';
  if(title) title.textContent = copy.title;
  if(subtitle) subtitle.textContent = copy.subtitle;
  if(pro) pro.classList.toggle('visible', !!copy.pro);
}
function centerDateTab(tab, behavior='smooth'){
  const strip = document.getElementById('date-strip');
  if(!strip || !tab) return;
  const left = tab.offsetLeft - (strip.clientWidth / 2) + (tab.offsetWidth / 2);
  const maxLeft = Math.max(0, strip.scrollWidth - strip.clientWidth);
  strip.scrollTo({left:Math.min(maxLeft, Math.max(0,left)), behavior});
}
function centerCurrentDate(behavior='auto'){
  const today = new Date().toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).split('/').join('-');
  const tab = document.querySelector(`.date-strip-item[data-date="${today}"]`) || document.querySelector('.date-strip-item.active');
  centerDateTab(tab, behavior);
}
function shiftDateStrip(dir){
  const strip = document.getElementById('date-strip');
  if(!strip) return;
  const tabs = [...strip.querySelectorAll('.date-strip-item')].filter(tab=>!tab.hidden);
  if(!tabs.length) return;
  const center = strip.scrollLeft + (strip.clientWidth / 2);
  let currentIndex = 0;
  let bestDistance = Infinity;
  tabs.forEach((tab,index)=>{
    const tabCenter = tab.offsetLeft + (tab.offsetWidth / 2);
    const distance = Math.abs(tabCenter - center);
    if(distance < bestDistance){
      bestDistance = distance;
      currentIndex = index;
    }
  });
  const nextIndex = Math.min(tabs.length - 1, Math.max(0, currentIndex + dir));
  centerDateTab(tabs[nextIndex]);
}
'''
    html = html.replace("let historicoVisible=false;\n", "let historicoVisible=false;\n\n" + hero_js + "\n")
    html = html.replace("  historicoVisible=true;\n  renderHistoricoGlobal();", "  historicoVisible=true;\n  updatePageHero('historico');\n  renderHistoricoGlobal();")
    html = html.replace("if(tab){tab.classList.add('active');tab.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});}", "if(tab){tab.classList.add('active');centerDateTab(tab);requestAnimationFrame(()=>centerDateTab(tab,'auto'));}")
    html = html.replace("  if(mp)mp.classList.add('active');\n  if(mt)mt.classList.add('active');\n  renderMkt(date,mkt);", "  if(mp)mp.classList.add('active');\n  if(mt)mt.classList.add('active');\n  updatePageHero(mkt);\n  renderMkt(date,mkt);")
    html = html.replace("  activeCat = cat;\n  activeSubFilter = null;\n  updateSidebarActive(null);", "  activeCat = cat;\n  activeSubFilter = null;\n  updateSidebarActive(null);\n  updatePageHero(cat);")
    html = html.replace("switchDate(targetDate);\n  }", "switchDate(targetDate);\nsetTimeout(()=>centerCurrentDate('auto'), 80);\n  }", 1)
    html = html.replace("switchDate(targetDate);\n    }", "switchDate(targetDate);\nsetTimeout(()=>centerCurrentDate('auto'), 80);\n    }", 1)
    html = html.replace("</script>\n\n<!-- Bot", "window.addEventListener('load',()=>centerCurrentDate('auto'));\nwindow.addEventListener('resize',()=>centerCurrentDate('auto'));\n</script>\n\n<!-- Bot", 1)
    return html


def remove_card_market_ui(html):
    html = re.sub(
        r'\n// ── Cartões.*?\n// ── Bilhetes',
        '\n// ── Bilhetes',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(r"\n\.cards-summary-grid\{.*?\.cards-muted-note\{.*?\}", '', html, flags=re.DOTALL)
    html = html.replace('.rf-grid,.corner-summary-grid,.cards-summary-grid,.bilhete-grid,.bilhete-destaques,.hist-summary-grid,.hist-audit-grid,.hg-panels,.hg-bottom', '.rf-grid,.corner-summary-grid,.bilhete-grid,.bilhete-destaques,.hist-summary-grid,.hist-audit-grid,.hg-panels,.hg-bottom')
    html = re.sub(r"\n\s*\.cards-summary-grid\{[^}]*\}", '', html)
    html = re.sub(r"\n\s*\.cards-toolbar\{[^}]*\}", '', html)
    html = re.sub(r"\n\s*\.cards-filter-btn\{[^}]*\}", '', html)
    html = re.sub(
        r'\n// [^\n]*Cart[^\n]*\nlet activeCardQuickFilter.*?\n// [^\n]*Bilhetes',
        '\n// Bilhetes',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'\nlet activeCardQuickFilter.*?\n// [^\n]*Bilhetes',
        '\n// Bilhetes',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\n\s*else if\(mkt==='cartoes'\)\s*renderCart\(date,jogos\);",
        '',
        html,
    )
    html = re.sub(r"\nfunction isCardMarketName\(mkt\)\{.*?\n\}", '', html, flags=re.DOTALL)
    html = re.sub(
        r"\n\s*\} else if\(tipo==='cart'\)\{\s*filtrados=.*?cor='var\(--orange\)';\s*",
        "\n  ",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\n\s*const cardPick=d\.__cardPick\|\|null;\s*const mktKey=cardPick\?null:\(MKT_RESULT\[getPalpiteMkt\(d\)\]\|\|'over15_ok'\);\s*const rc=cardPick\?cardRowClass\(cardPick\):rowClass\(d,mktKey\);\s*const scoreField=cardPick\?cardPick\.score_final:\(tipo==='prem'\?getPalpiteScore\(d\):tipo==='15'\?d\.score_15:d\.score_esc75\);\s*const mktShow=cardPick\?cardMarketLabel\(cardPick\.market_key,cardPick\.market\):\(tipo==='prem'\?getPalpiteMkt\(d\):tipo==='15'\?'Over 1\.5':'Esc 7\.5'\);",
        "\n    const mktKey=MKT_RESULT[getPalpiteMkt(d)]||'over15_ok';\n    const rc=rowClass(d,mktKey);\n    const scoreField=tipo==='prem'?getPalpiteScore(d):tipo==='15'?d.score_15:d.score_esc75;\n    const mktShow=tipo==='prem'?getPalpiteMkt(d):tipo==='15'?'Over 1.5':'Esc 7.5';",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\n\s*const cardPick=d\.__cardPick\|\|null;\s*const mktKey=cardPick\?null:getPalpiteKey\(d\);\s*const rc=cardPick\?cardRowClass\(cardPick\):rowClass\(d,mktKey\);\s*const scoreField=cardPick\?cardPick\.score_final:\(tipo==='prem'\?getPalpiteScore\(d\):tipo==='15'\?d\.score_15:d\.score_esc75\);\s*const mktShow=cardPick\?cardMarketLabel\(cardPick\.market_key,cardPick\.market\):\(tipo==='prem'\?getPalpiteMkt\(d\):tipo==='15'\?'Over 1\.5':'Esc 7\.5'\);",
        "\n    const mktKey=getPalpiteKey(d);\n    const rc=rowClass(d,mktKey);\n    const scoreField=tipo==='prem'?getPalpiteScore(d):tipo==='15'?d.score_15:d.score_esc75;\n    const mktShow=tipo==='prem'?getPalpiteMkt(d):tipo==='15'?'Over 1.5':'Esc 7.5';",
        html,
        flags=re.DOTALL,
    )
    html = html.replace('${gradeHtml(cardPick?cardPick.grade:getPalpiteGrade(d))}', '${gradeHtml(getPalpiteGrade(d))}')
    html = html.replace('${cardPick?cardResultBadge(cardPick):resBadge(d,mktKey)}', '${resBadge(d,mktKey)}')
    html = html.replace("if(legacy && !isCardMarketName(legacy)){", "if(legacy){")
    html = re.sub(r"\n\s*const isCardAltMarket = .*?\n\s*if\(opts\.excludeCards\) mkts = mkts\.filter\(x=>!isCardAltMarket\(x\)\);", '', html, flags=re.DOTALL)
    html = html.replace("const ok = res ? (x.cardPick ? cardResultOk(x.cardPick) : resultOk(res,x.key)) : null;", "const ok = res ? resultOk(res,x.key) : null;")
    html = re.sub(r'\n\s*<option value="Cart" .*?</option>', '', html)
    html = re.sub(
        r"\n\s*'cartoes':\s*\[[^\]]*?\],",
        '',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\n\s*\}\} else if\(cat === 'cartoes'\)\{\{.*?const p = document\.getElementById\('mkt-'\+date\+'-cartoes'\);\s*if\(p\) p\.classList\.add\('active'\);",
        '',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"\n\s*\} else if\(cat === 'cartoes'\)\{.*?\n\s*\} else if\(cat === 'resultado'\)\{",
        "\n  } else if(cat === 'resultado'){",
        html,
        flags=re.DOTALL,
    )
    html = html.replace(
        "const MERCADOS   = ['Over 1.5','Over 2.5','BTTS','Over 0.5 HT','Under 4.5','Under 3.5','Esc 7.5','Esc 8.5','Cart 2.5','Cart 3.5'];",
        "const MERCADOS   = ['Over 1.5','Over 2.5','BTTS','Over 0.5 HT','Under 4.5','Under 3.5','Esc 7.5','Esc 8.5'];",
    )
    html = html.replace("  'Cart 2.5':    'cart25_ok',\n  'Cart 3.5':    'cart35_ok',\n", '')
    html = html.replace("  'Cart 2.5':'score_cards25','Cart 3.5':'score_cards35',\n", '')
    html = html.replace("'Esc 7.5':75,'Esc 8.5':75,'Cart 2.5':75,'Cart 3.5':75,", "'Esc 7.5':75,'Esc 8.5':75,")
    html = re.sub(r"\s*else if\(mkt==='Cart [23]\.5'\) val=d\.odds_cards_[23]5;", '', html)
    html = re.sub(r"\s*if\(mkt==='Cart [23]\.5'\)\s*return'Odd C[23]\.5';", '', html)
    html = html.replace("    'Cart 2.5':'grade_cart25','Cart 3.5':'grade_cart35',", '')
    html = html.replace(
        "const scoreField=cardPick?cardPick.score_final:(tipo==='prem'?getPalpiteScore(d):tipo==='15'?d.score_15:tipo==='esc'?d.score_esc75:d.score_cards25);",
        "const scoreField=cardPick?cardPick.score_final:(tipo==='prem'?getPalpiteScore(d):tipo==='15'?d.score_15:d.score_esc75);",
    )
    html = html.replace(
        "const mktShow=cardPick?cardMarketLabel(cardPick.market_key,cardPick.market):(tipo==='prem'?getPalpiteMkt(d):tipo==='15'?'Over 1.5':tipo==='esc'?'Esc 7.5':'Cart 2.5');",
        "const mktShow=cardPick?cardMarketLabel(cardPick.market_key,cardPick.market):(tipo==='prem'?getPalpiteMkt(d):tipo==='15'?'Over 1.5':'Esc 7.5');",
    )
    html = re.sub(
        r"const mktMiniNames=\{[^}]*Cart 2\.5[^}]*\};",
        "const mktMiniNames={'Over 1.5':'Over 1.5','Over 2.5':'Over 2.5','Esc 7.5':'Escanteios (Over)','Esc 8.5':'Esc 8.5','BTTS':'Ambas Marcam','Under 3.5':'Under 3.5','Under 4.5':'Under 4.5','Over 0.5 HT':'Over 0.5 HT'};",
        html,
    )
    html = re.sub(r"\n\s*const cart=res\.cards_total.*?\n", '\n', html)
    html = html.replace("${cart}", '')
    html = re.sub(
        r"\n\s*if\(\(mktKey==='cart25_ok' \|\| mktKey==='cart35_ok'\) && !hasPositiveStat\(res\.cards_total\)\)\{\s*return null;\s*\}",
        '',
        html,
        flags=re.DOTALL,
    )
    html = re.sub(r"\n\s*const cartRow=res&&res\.cards_total.*?\n", '\n', html)
    html = html.replace('<th>Cart.</th>', '')
    html = html.replace('<td class="mono">${cartRow}</td>', '')
    card_tab = '''      <div class="mkt-cat-tab disabled" data-cat="cartoes" aria-disabled="true" title="Cartões em breve">
        <i data-lucide="layers" style="width:14px;height:14px"></i> Cartões
      </div>
'''
    html = re.sub(
        r'\s*<div class="mkt-cat-tab[^"]*" data-cat="cartoes".*?</div>\s*',
        '\n' + card_tab,
        html,
        flags=re.DOTALL,
    )
    if 'data-cat="cartoes"' not in html:
        html = html.replace(
            '      <div class="mkt-cat-tab" data-cat="escanteios" onclick="switchCat(\'escanteios\')">\n'
            '        <i data-lucide="corner-up-right" style="width:14px;height:14px"></i> Escanteios\n'
            '      </div>\n',
            '      <div class="mkt-cat-tab" data-cat="escanteios" onclick="switchCat(\'escanteios\')">\n'
            '        <i data-lucide="corner-up-right" style="width:14px;height:14px"></i> Escanteios\n'
            '      </div>\n' + card_tab,
            1,
        )
    return html

def day_panel_html(d, day_data):
    jogos  = day_data.get('jogos', [])
    n15    = sum(1 for j in jogos if j['score_15'] >= 85 and j['passou_filtro'])
    nesc   = sum(1 for j in jogos if j['score_esc75'] >= 75)
    nprem  = sum(1 for j in jogos if (j.get('palpite_grade') or j.get('best_grade')) in ('A+', 'A'))
    fmt, wd = fmt_date(d)
    confirmado = day_data.get('resultado_confirmado', False)

    return f'''
<div id="day-{d}" class="day-panel">
  <div class="main">
    <div id="mkt-{d}-visao"        class="mkt-panel active"></div>
    <div id="mkt-{d}-ranking"      class="mkt-panel"></div>
    <div id="mkt-{d}-bilhetes"     class="mkt-panel"></div>
    <div id="mkt-{d}-resultado"    class="mkt-panel"></div>
    <div id="mkt-{d}-over15"       class="mkt-panel"></div>
    <div id="mkt-{d}-over25"       class="mkt-panel"></div>
    <div id="mkt-{d}-escanteios"   class="mkt-panel"></div>
    <div id="mkt-{d}-historico_dia" class="mkt-panel"></div>
  </div>
</div>'''


def patch_html(date_tabs_html, day_panels_html, all_data_json, globais_json, updated_iso_json):
    """
    Injeta apenas os dados dinâmicos no index.html existente, preservando
    todo o layout, CSS e JS do template.  Usa marcadores HTML como âncoras.
    """
    if not os.path.exists(OUT_FILE):
        raise FileNotFoundError(
            f"{OUT_FILE} nao existe. Crie/restaure o template visual antes de atualizar os dados."
        )

    with open(OUT_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    MARKERS = [
        '<!-- WM:DATE-TABS-START -->',
        '<!-- WM:DATE-TABS-END -->',
        '<!-- WM:DAY-PANELS-START -->',
        '<!-- WM:DAY-PANELS-END -->',
    ]
    if not all(m in html for m in MARKERS):
        missing = [m for m in MARKERS if m not in html]
        raise RuntimeError(
            "Marcadores seguros ausentes em docs/index.html: "
            + ", ".join(missing)
            + ". O gerador nao recria layout; ele so atualiza dados."
        )

    import re

    # 1. Substituir date-tabs
    html = re.sub(
        r'<!-- WM:DATE-TABS-START -->.*?<!-- WM:DATE-TABS-END -->',
        f'<!-- WM:DATE-TABS-START -->\n{date_tabs_html}\n<!-- WM:DATE-TABS-END -->',
        html, flags=re.DOTALL
    )

    # 2. Substituir day-panels (manter o <!-- DAY PANELS --> original entre os markers)
    html = re.sub(
        r'<!-- WM:DAY-PANELS-START -->.*?<!-- WM:DAY-PANELS-END -->',
        f'<!-- WM:DAY-PANELS-START -->\n<!-- DAY PANELS -->\n{day_panels_html}\n<!-- WM:DAY-PANELS-END -->',
        html, flags=re.DOTALL
    )

    # 3. Substituir ALL_DATA e GLOBAIS (linha inteira)
    html = re.sub(
        r'const ALL_DATA\s*=\s*\{.*?;',
        f'const ALL_DATA   = {all_data_json};',
        html, flags=re.DOTALL
    )
    html = re.sub(
        r'const GLOBAIS\s*=\s*\{.*?;',
        f'const GLOBAIS    = {globais_json};',
        html, flags=re.DOTALL
    )
    html = re.sub(
        r'const CARD_AUDIT\s*=\s*\{.*?;\n?',
        '',
        html,
        flags=re.DOTALL,
    )
    html, updated_count = re.subn(
        r'const WM_DATA_UPDATED_AT\s*=\s*.*?;',
        f'const WM_DATA_UPDATED_AT = {updated_iso_json};',
        html, flags=re.DOTALL
    )
    if updated_count != 1:
        raise RuntimeError(
            "Constante WM_DATA_UPDATED_AT ausente ou duplicada em docs/index.html."
        )

    html = remove_card_market_ui(html)
    html = ensure_responsive_css(html)
    return html


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
    updated_dt = datetime.now(timezone.utc)
    updated = updated_dt.strftime('%d/%m/%Y %H:%M UTC')
    updated_iso = updated_dt.isoformat().replace('+00:00', 'Z')

    # Tenta injetar só os dados no template existente (preserva layout/CSS/JS)
    html = patch_html(
        date_tabs_html='\n'.join(date_tabs_html),
        day_panels_html='\n'.join(day_panels_html),
        all_data_json=json.dumps(all_data, ensure_ascii=False),
        globais_json=json.dumps(globais, ensure_ascii=False),
        updated_iso_json=json.dumps(updated_iso),
    )

    if html is None:
        raise RuntimeError(
            "Atualizacao abortada: docs/index.html nao tem os marcadores WM. "
            "O gerador nao recria layout; ele so atualiza dados."
        )
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"OK docs/index.html atualizado somente com dados - {len(index)} datas - {updated}")

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
  --nav-h:56px;--search-h:126px;--date-strip-h:53px;--market-bar-h:42px;--top-gap:8px;
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
.mono,.kpi-val,.day-hist-date,.day-hist-info,.hist-taxa-val,.history-search-meta,.navbar-logo-sub,.navbar-clock,.placar-cell,.top-rank,.top-liga,.top-hora,.top-score,.res-badge,.conf,.badge,.bilhete-odd-total,.bilhete-odd-val,.bilhete-status,.bilhete-dia-badge,.bilhete-sels,.cnt,.date-strip-day{{font-family:'Inter',sans-serif!important}}
.metric-value{{font-size:13px;font-weight:800;line-height:1;color:var(--text)}}
.metric-value.em{{font-size:14px}}

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
.main{{padding:18px 0 22px;width:calc(100% - 48px);max-width:1500px;margin:0 auto}}

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

/* HISTORY SEARCH */
.history-search-global{{
  padding:var(--top-gap) 0 var(--top-gap);background:var(--bg);
  position:sticky;top:var(--nav-h);z-index:130;width:calc(100% - 48px);max-width:1500px;margin:0 auto;
}}
.history-search{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:0}}
.history-search-head{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;flex-wrap:wrap}}
.history-search-title{{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:800;color:var(--text)}}
.history-search-title svg{{width:16px;height:16px;color:var(--accent)}}
.history-search-meta{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace}}
.history-search-controls{{display:grid;grid-template-columns:minmax(220px,1fr) 150px 110px 150px;gap:8px;align-items:center}}
.history-search-input,.history-search-select{{
  height:36px;border:1px solid var(--border);border-radius:8px;background:var(--s2);
  color:var(--text);font-size:12px;padding:0 11px;outline:none;min-width:0;
}}
.history-search-input:focus,.history-search-select:focus{{border-color:var(--accent);box-shadow:0 0 0 2px rgba(37,99,235,.12)}}
.history-search-results{{margin-top:12px}}
.history-search-empty{{padding:16px;text-align:center;color:var(--muted);font-size:12px;background:rgba(255,255,255,.03);border:1px dashed var(--border);border-radius:9px}}
.history-chip-row{{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}}
.history-chip{{border:1px solid var(--border);background:var(--s2);color:var(--muted);height:28px;padding:0 10px;border-radius:999px;font-size:11px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:5px}}
.history-chip:hover,.history-chip.active{{color:var(--text);border-color:var(--accent);background:rgba(37,99,235,.1)}}
@media(max-width:920px){{:root{{--search-h:172px}}.history-search-controls{{grid-template-columns:1fr 1fr}}}}
@media(max-width:768px){{.history-search-global{{width:calc(100% - 16px)}}}}
@media(max-width:560px){{:root{{--search-h:260px}}.history-search-controls{{grid-template-columns:1fr}}}}

/* SECTION */
.sec-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);margin:18px 0 10px;display:flex;align-items:center;gap:8px}}
.sec-title:first-child{{margin-top:0}}
.sec-title svg{{width:15px;height:15px;color:var(--accent);stroke:currentColor;flex-shrink:0}}
.sec-title::after{{content:'';flex:1;height:1px;background:var(--border)}}

/* TOP CARDS */
.top-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-bottom:20px;align-items:start;max-width:100%;min-width:0}}
.top-grid::-webkit-scrollbar{{height:3px}}
.top-grid::-webkit-scrollbar-thumb{{background:var(--accent);border-radius:2px}}
.top-card{{width:100%;min-width:0;height:auto;align-self:start;background:var(--s1);border:1px solid var(--border);border-radius:11px;padding:14px;position:relative;overflow:hidden;transition:border-color .2s,transform .15s}}
.top-card:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.3)}}
.top-card:active{{transform:translateY(0);box-shadow:none}}
/* resultado overlay no card */
.tc-hit::after{{content:'';position:absolute;inset:0;background:rgba(0,200,150,.06);border:1px solid rgba(0,200,150,.25);border-radius:11px;pointer-events:none}}
.tc-miss::after{{content:'';position:absolute;inset:0;background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.25);border-radius:11px;pointer-events:none}}
.top-rank-block{{position:absolute;top:10px;right:12px;text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:3px;z-index:1}}
.top-rank{{position:static;font-size:13px;font-weight:800;color:rgba(255,255,255,.18);line-height:1}}
.top-status{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:800;letter-spacing:.4px;text-transform:uppercase;padding:2px 5px;border-radius:4px;line-height:1}}
.top-status.hit{{color:var(--green);background:rgba(0,200,150,.10);border:1px solid rgba(0,200,150,.25)}}
.top-status.miss{{color:var(--red);background:rgba(239,68,68,.10);border:1px solid rgba(239,68,68,.25)}}
.top-status.pending{{color:var(--yellow);background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.20)}}
.top-liga{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.7px;margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:86px}}
.league-meta{{display:flex;align-items:center;gap:7px;min-width:0;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:10px;line-height:1.3}}
.league-flag{{width:18px;height:18px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px;background:rgba(255,255,255,.06);object-fit:cover}}
.league-code{{font-weight:800;color:var(--text2);letter-spacing:.35px;text-transform:uppercase}}
.league-name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.top-liga .league-meta{{font-size:10px;color:inherit}}
.top-liga .league-flag{{width:16px;height:16px;font-size:12px}}
.top-jogo{{font-size:13px;font-weight:700;margin-bottom:2px;padding-right:86px;line-height:1.3;overflow-wrap:anywhere}}
.top-hora{{font-size:10px;color:var(--muted);font-family:'JetBrains Mono',monospace;margin-bottom:8px}}
.top-mkt{{font-size:10px;font-weight:700;color:var(--accent);margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}}
.top-bottom{{display:flex;align-items:center;justify-content:space-between;margin-top:6px}}
.top-score{{font-size:22px;font-weight:800;line-height:1}}
.top-grade-block{{display:flex;flex-direction:column;align-items:flex-end;gap:3px}}
.top-note{{font-size:10px;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px solid var(--border);line-height:1.55}}
/* placar no card */
.top-placar{{display:flex;align-items:center;gap:6px;margin-top:7px;padding:6px 10px;border-radius:6px;font-family:'JetBrains Mono',monospace}}
.top-placar.hit{{background:rgba(0,200,150,.1);border:1px solid rgba(0,200,150,.22)}}
.top-placar.miss{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2)}}
.top-placar.pending{{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.18)}}
.top-placar .ft{{font-size:15px;font-weight:700}}
.top-placar .ht{{font-size:10px;color:var(--muted)}}
.top-placar svg,.top-hora svg,.res-badge svg,.bilhete-status svg,.callout strong svg,.hist-detail svg,.day-hist-info svg,.mini-stat svg{{width:13px;height:13px;stroke:currentColor;flex-shrink:0;vertical-align:-2px}}
.mini-stat{{display:inline-flex;align-items:center;gap:3px}}
.mini-stat.ok{{color:var(--green)}}.mini-stat.err{{color:var(--red)}}.mini-stat.neutral{{color:var(--muted)}}
.top-hora{{display:flex;align-items:center;gap:5px}}
.top-placar .ht svg{{width:11px;height:11px;margin:0 2px 0 5px}}
.callout strong{{display:inline-flex;align-items:center;gap:6px}}

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
.res-badge{{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap}}
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
.corner-summary-grid{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:0 0 16px}}
.corner-summary-card{{background:var(--s1);border:1px solid var(--border);border-radius:8px;padding:12px 14px;min-width:0}}
.corner-summary-label{{font-size:10px;line-height:1.2;color:#8FB4E8;font-weight:800;text-transform:uppercase;letter-spacing:.9px;margin-bottom:8px}}
.corner-summary-value{{font-size:20px;line-height:1.05;color:var(--text);font-weight:900;font-family:'JetBrains Mono',monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.corner-summary-sub{{font-size:10px;color:var(--muted);font-weight:700;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.corner-table-wrap table{{min-width:1360px}}
.corner-table-wrap th,.corner-table-wrap td{{text-align:center}}
.corner-table-wrap th:nth-child(2),.corner-table-wrap td:nth-child(2){{text-align:left}}
.corner-table-wrap tbody tr.row-hit{{background:linear-gradient(90deg,rgba(0,200,150,.30),rgba(0,200,150,.16),rgba(8,18,26,.92))!important;box-shadow:inset 0 0 0 1px rgba(0,200,150,.34)}}
.corner-table-wrap tbody tr.row-miss{{background:linear-gradient(90deg,rgba(239,68,68,.28),rgba(239,68,68,.14),rgba(8,18,26,.92))!important;box-shadow:inset 0 0 0 1px rgba(239,68,68,.34)}}
.corner-table-wrap th:nth-child(n+5),.corner-table-wrap td:nth-child(n+5){{border-left:1px solid rgba(148,163,184,.16)}}
.corner-table-wrap th:nth-child(10),.corner-table-wrap td:nth-child(10){{border-left-color:rgba(59,130,246,.24)}}
.corner-table-wrap .corner-confidence{{min-width:116px;text-align:center}}
.corner-table-wrap .corner-over-cell{{display:flex;align-items:center;justify-content:center;gap:6px;min-width:146px;padding:0 4px;background:transparent;border:0;box-shadow:none;flex-wrap:nowrap;align-content:center}}
.corner-table-wrap .corner-over-track{{position:relative;width:58px;height:12px;background:rgba(2,18,27,.48);border:1px solid var(--green);border-radius:999px;overflow:hidden;box-shadow:none}}
.corner-table-wrap .corner-over-fill{{position:absolute;left:3px;top:50%;transform:translateY(-50%);height:6px;max-width:calc(100% - 6px);border-radius:999px;opacity:.86}}
.corner-table-wrap .corner-over-pct{{min-width:32px;font-size:11px;font-weight:800;text-align:right}}
.corner-table-wrap .corner-no-data{{display:inline-flex;align-items:center;justify-content:center;min-width:72px;color:#6F829E;font-size:10px;font-weight:800}}
.corner-table-wrap .corner-best-pick{{display:inline-flex;align-items:center;justify-content:center;min-width:104px;border-radius:999px;padding:5px 9px;background:rgba(0,200,150,.08);border:1px solid rgba(0,200,150,.18);color:var(--teal);font-size:10px;font-weight:900;white-space:nowrap}}
.corner-table-wrap .corner-best-pick.empty{{background:transparent;border-color:rgba(148,163,184,.12);color:#6F829E}}
.corner-table-wrap .corner-real{{display:inline-flex;align-items:center;justify-content:center;width:34px;height:28px;border-radius:8px;background:rgba(0,200,150,.18);border:1px solid rgba(0,200,150,.18);color:var(--teal);font-weight:900;font-size:15px}}
.corner-line-result{{display:flex;justify-content:center;margin-top:0}}
.corner-table-wrap .corner-line-result .res-badge{{height:18px;min-width:44px;padding:1px 5px;font-size:8px;border-radius:999px;justify-content:center}}
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
.row-num{{width:42px;text-align:center;color:var(--muted);font-weight:700}}
.td-conf{{text-align:center}}
.td-palpite{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}}
.alt-mkts{{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px;align-items:center}}
.alt-label{{font-size:9px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.6px;width:100%}}
.alt-badge{{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--border);background:rgba(255,255,255,.045);color:var(--text2);border-radius:5px;padding:3px 6px;font-size:10px;font-weight:700;font-family:'JetBrains Mono',monospace;line-height:1;white-space:nowrap}}
.alt-badge strong{{color:var(--green);font-weight:800}}
.alt-badge.primary{{border-color:rgba(37,99,235,.45);background:rgba(37,99,235,.12);color:#BFDBFE}}
.alt-badge.protect{{border-color:rgba(0,200,150,.35);background:rgba(0,200,150,.08);color:var(--green)}}
.alt-badge.hit{{border-color:rgba(0,200,150,.42);background:rgba(0,200,150,.12);color:var(--green)}}
.alt-badge.miss{{border-color:rgba(239,68,68,.42);background:rgba(239,68,68,.12);color:var(--red)}}
.alt-badge.pending{{color:var(--muted)}}
.alt-res{{font-size:9px;font-weight:800;margin-left:2px}}
.alt-cell{{min-width:170px;max-width:260px}}
.top-card .alt-mkts{{margin-top:10px}}

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

/* RESULTADO FINAL */
.rf-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}}
.rf-card{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:12px;min-width:0}}
.rf-card span{{display:flex;align-items:center;gap:6px;font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px}}
.rf-card span svg{{width:13px;height:13px;stroke:currentColor}}
.rf-card strong{{display:block;font-family:'Inter',sans-serif;font-size:24px;font-weight:900;line-height:1;color:var(--text)}}
.rf-card em{{display:block;font-style:normal;font-size:10px;color:var(--muted);font-family:'Inter',sans-serif;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.rf-card.ok strong{{color:var(--green)}}.rf-card.err strong{{color:var(--red)}}.rf-card.void strong{{color:var(--yellow)}}.rf-card.blue strong{{color:var(--blue)}}
.rf-market{{display:inline-flex;align-items:center;gap:5px;border-radius:5px;padding:3px 7px;font-size:10px;font-weight:800;font-family:'Inter',sans-serif;white-space:nowrap;border:1px solid rgba(59,130,246,.24);background:rgba(59,130,246,.08);color:var(--blue)}}
.rf-market.win{{border-color:rgba(0,200,150,.28);background:rgba(0,200,150,.08);color:var(--green)}}
.rf-market.dnb{{border-color:rgba(245,158,11,.32);background:rgba(245,158,11,.08);color:var(--yellow)}}
.rf-market.dc{{border-color:rgba(59,130,246,.28);background:rgba(59,130,246,.08);color:var(--blue)}}
.rf-reasons{{font-size:10px;color:var(--muted);line-height:1.45;max-width:320px}}
.rf-score{{font-family:'Inter',sans-serif;font-size:14px;font-weight:900}}
@media(max-width:920px){{.rf-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:560px){{.rf-grid{{grid-template-columns:1fr}}}}

/* PYRAMID */
.cpyr{{display:flex;flex-direction:column;gap:2px;font-family:'JetBrains Mono',monospace;font-size:10px}}
.cpyr-row{{display:flex;align-items:center;gap:3px}}
.cpyr-lbl{{color:var(--muted);width:36px;text-align:right}}
.cpyr-bar{{height:7px;border-radius:2px;min-width:2px}}
.cpyr-val{{min-width:26px}}

/* HISTÓRICO */
.hist-page{{display:flex;flex-direction:column;gap:12px}}
.hist-hero{{background:linear-gradient(135deg,rgba(37,99,235,.16),rgba(124,58,237,.10) 48%,rgba(0,200,150,.08));border:1px solid var(--border);border-radius:12px;padding:14px 16px;display:grid;grid-template-columns:minmax(360px,1fr) minmax(260px,320px) minmax(300px,380px);gap:14px;align-items:center;box-shadow:0 10px 28px rgba(0,0,0,.22);overflow:hidden;position:relative}}
.hist-hero::before{{content:'';position:absolute;inset:0;border-top:3px solid rgba(0,200,150,.48);pointer-events:none}}
.hist-kicker{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1.4px;color:var(--green);margin-bottom:4px}}
.hist-title{{font-size:20px;font-weight:800;line-height:1.15;color:var(--text)}}
.hist-subtitle{{font-size:11px;color:var(--muted);margin-top:5px;max-width:760px;white-space:normal;line-height:1.55}}
.hist-hero-insights{{display:grid;grid-template-columns:1fr;gap:7px}}
.hist-insight{{background:rgba(255,255,255,.035);border:1px solid rgba(148,163,184,.14);border-radius:9px;padding:9px 10px;min-width:0}}
.hist-insight-label{{font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}}
.hist-insight-value{{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:12px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-insight-rate{{font-family:'Inter',sans-serif;font-size:15px;font-weight:900;flex-shrink:0}}
.hist-score-card{{height:100%;background:transparent;border:1px solid rgba(148,163,184,.18);border-radius:10px;padding:12px;display:flex;flex-direction:column;justify-content:center;position:relative;overflow:hidden;box-shadow:none}}
.hist-score-card::before{{content:'';position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:99px;background:linear-gradient(180deg,var(--blue),var(--purple2));pointer-events:none}}
.hist-score-card::after{{content:none}}
.hist-score-label{{font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px}}
.hist-score-val{{font-family:'Inter',sans-serif;font-size:26px;font-weight:900;line-height:1}}
.hist-score-note{{font-size:10px;color:var(--text2);font-family:'Inter',sans-serif;font-weight:700;margin-top:5px;white-space:nowrap}}
.hist-eyebrow{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1.4px;color:var(--green);margin-bottom:4px}}
.hist-hero h2{{font-size:20px;font-weight:800;line-height:1.15;color:var(--text);margin:0}}
.hist-insight span{{display:block;font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}}
.hist-insight strong{{display:block;font-size:12px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-insight em{{display:block;font-style:normal;font-family:'Inter',sans-serif;font-size:10px;color:var(--text2);font-weight:700;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-score-card span{{position:relative;z-index:1;font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;padding-left:4px}}
.hist-score-card .hist-score-row{{position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:space-between;gap:12px;width:100%}}
.hist-score-card strong{{font-family:'Inter',sans-serif;font-size:32px;font-weight:900;line-height:1;letter-spacing:0;color:var(--green)}}
.hist-score-card em{{font-style:normal;font-size:9px;color:var(--text2);font-family:'Inter',sans-serif;font-weight:800;line-height:1.25;text-align:right;white-space:normal}}
.hist-score-card .hist-score-bar{{position:relative;z-index:1;height:6px;border-radius:999px;background:rgba(148,163,184,.14);overflow:hidden;margin-top:10px;width:100%}}
.hist-score-card .hist-score-bar i{{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--blue),var(--purple2));width:var(--score-width,0%)}}
.hist-visual{{background:linear-gradient(135deg,rgba(31,32,56,.94),rgba(19,28,49,.96));border:1px solid rgba(139,92,246,.18);border-radius:16px;padding:14px;display:grid;grid-template-columns:300px minmax(0,1fr) 250px;gap:14px;align-items:stretch;box-shadow:0 14px 36px rgba(0,0,0,.28);overflow:hidden}}
.hist-visual-card{{background:rgba(255,255,255,.025);border:1px solid rgba(148,163,184,.10);border-radius:12px;padding:12px;min-width:0}}
.hist-visual-title{{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--text2);margin-bottom:10px}}
.hist-radial-wrap{{display:grid;grid-template-columns:118px minmax(150px,1fr);gap:14px;align-items:center}}
.hist-radial{{width:118px;height:118px;border-radius:50%;position:relative;background:radial-gradient(circle at center,rgba(31,32,56,1) 0 40%,transparent 41%);flex-shrink:0}}
.hist-radial-ring{{position:absolute;inset:var(--inset);border-radius:50%;background:conic-gradient(var(--ring-color) 0 var(--ring-deg),rgba(255,255,255,.07) var(--ring-deg) 360deg)}}
.hist-radial-ring::after{{content:'';position:absolute;inset:8px;border-radius:50%;background:rgb(31,32,56)}}
.hist-radial-core{{position:absolute;inset:39px;border-radius:50%;background:rgba(17,24,39,.92);border:1px solid rgba(148,163,184,.14);display:flex;align-items:center;justify-content:center;font-family:'Inter',sans-serif;font-size:13px;font-weight:900;color:var(--text)}}
.hist-vlegend{{display:flex;flex-direction:column;gap:7px;min-width:0}}
.hist-vlegend-row{{display:grid;grid-template-columns:8px minmax(0,1fr) 42px;gap:7px;align-items:center;font-size:10px;color:var(--muted)}}
.hist-vdot{{width:8px;height:8px;border-radius:50%;background:var(--dot)}}
.hist-vlegend-name{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text2);font-weight:700}}
.hist-vlegend-rate{{font-family:'Inter',sans-serif;font-weight:900;text-align:right;color:var(--rate-color)}}
.hist-radial-bg{{fill:none;stroke:rgba(255,255,255,.055);stroke-width:7}}
.hist-radial-ring{{fill:none;stroke-width:7;stroke-linecap:round;filter:drop-shadow(0 0 7px rgba(139,92,246,.35))}}
.hist-radial-ring.green{{stroke:var(--green)}}
.hist-radial-ring.yellow{{stroke:var(--yellow)}}
.hist-radial-ring.blue{{stroke:var(--blue)}}
.hist-vlegend-item{{display:grid;grid-template-columns:8px minmax(104px,1fr) 46px;gap:8px;align-items:center;font-size:10px;color:var(--muted)}}
.hist-vlegend-item span:nth-child(2){{white-space:nowrap;overflow:visible;text-overflow:clip;color:var(--text2);font-weight:800}}
.hist-vlegend-item strong{{font-family:'Inter',sans-serif;font-weight:900;text-align:right;color:var(--text)}}
.hist-dot{{width:8px;height:8px;border-radius:50%;display:block}}
.hist-dot.green{{background:var(--green)}}
.hist-dot.yellow{{background:var(--yellow)}}
.hist-dot.blue{{background:var(--blue)}}
.hist-viz-svg{{width:100%;height:118px;display:block;overflow:visible}}
.hist-viz-axis{{stroke:rgba(148,163,184,.12);stroke-width:1}}
.hist-viz-line{{fill:none;stroke:url(#histLineGrad);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 8px rgba(139,92,246,.45))}}
.hist-viz-area{{fill:url(#histAreaGrad);opacity:.8}}
.hist-line{{width:100%;height:126px;display:block;overflow:visible}}
.hist-line-path{{fill:none;stroke:var(--purple2);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 8px rgba(139,92,246,.55))}}
.hist-line-area{{fill:rgba(124,58,237,.16)}}
.hist-market-mini{{display:flex;flex-direction:column;gap:8px}}
.hist-market-mini-row{{display:grid;grid-template-columns:minmax(0,1fr) 46px;gap:8px;align-items:center}}
.hist-market-mini-row{{grid-template-columns:minmax(0,1fr) minmax(54px,.8fr) 46px}}
.hist-market-mini-row span{{font-size:10px;font-weight:700;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-market-mini-row div{{height:5px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden}}
.hist-market-mini-row i{{display:block;height:100%;border-radius:99px}}
.hist-market-mini-row strong{{font-family:'Inter',sans-serif;font-size:11px;font-weight:900;text-align:right}}
.hist-market-mini-name{{font-size:10px;font-weight:700;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-market-mini-rate{{font-family:'Inter',sans-serif;font-size:11px;font-weight:900;text-align:right}}
.hist-market-mini-track{{grid-column:1/3;height:5px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden;margin-top:-4px}}
.hist-market-mini-fill{{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--purple2))}}
.hist-legend-note{{margin-top:10px;padding-top:9px;border-top:1px solid rgba(148,163,184,.12);font-size:9px;line-height:1.45;color:var(--muted)}}
.hist-legend-note strong{{color:var(--text2);font-weight:800}}
.hist-summary-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}}
.hist-summary-card{{background:var(--s1);border:1px solid var(--border);border-radius:9px;padding:10px 11px;min-width:0}}
.hist-summary-label{{font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-summary-value{{font-family:'Inter',sans-serif;font-size:21px;font-weight:800;line-height:1;color:var(--text)}}
.hist-summary-note{{font-size:9px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-summary-card span{{display:block;font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-summary-card strong{{display:block;font-family:'Inter',sans-serif;font-size:21px;font-weight:800;line-height:1;color:var(--text)}}
.hist-summary-card em{{display:block;font-style:normal;font-size:9px;color:var(--muted);margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-summary-card.ok strong{{color:var(--green)}}
.hist-summary-card.err strong{{color:var(--red)}}
.hist-audit-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;align-items:stretch}}
.hist-audit-panel{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:11px;min-width:0;position:relative;overflow:hidden;display:flex;flex-direction:column;height:100%}}
.hist-audit-panel.pro::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(135deg,#2563eb,#7c3aed)}}
.hist-audit-main{{display:grid;grid-template-columns:86px minmax(0,1fr);gap:10px;align-items:center;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border);min-height:84px}}
.hist-audit-score{{height:68px;border-radius:9px;background:linear-gradient(135deg,rgba(37,99,235,.14),rgba(0,200,150,.08));border:1px solid rgba(148,163,184,.14);display:flex;flex-direction:column;align-items:center;justify-content:center}}
.hist-audit-panel.pro .hist-audit-score{{background:linear-gradient(135deg,rgba(37,99,235,.24),rgba(124,58,237,.18));border-color:rgba(139,92,246,.32)}}
.hist-audit-val{{font-family:'Inter',sans-serif;font-size:20px;font-weight:800;line-height:1}}
.hist-audit-lbl{{font-size:8px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.7px;margin-top:3px}}
.hist-audit-main span{{display:block;font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}}
.hist-audit-main .hist-audit-kicker{{display:flex;align-items:center;gap:6px;font-size:9px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-audit-kicker svg{{width:13px;height:13px;stroke:currentColor;flex-shrink:0}}
.hist-audit-main strong{{display:block;font-size:12px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-audit-main em{{display:block;font-style:normal;font-size:9px;color:var(--muted);line-height:1.35;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-audit-title{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.8px;color:var(--text)}}
.hist-audit-copy{{font-size:9px;color:var(--muted);line-height:1.35;margin-top:3px}}
.hist-breakdown{{display:flex;flex-direction:column;gap:5px}}
.hist-break-list{{display:flex;flex-direction:column;gap:5px}}
.hist-break-row{{display:grid;grid-template-columns:minmax(0,1fr) 64px;gap:8px;align-items:center;padding:7px 8px;border-bottom:1px solid rgba(148,163,184,.1);border-radius:7px;border-left:3px solid transparent}}
.hist-break-row{{grid-template-columns:minmax(0,1fr) 56px minmax(94px,auto)}}
.hist-break-row:last-child{{border-bottom:none}}
.hist-break-row.tone-alta{{background:linear-gradient(90deg,rgba(0,200,150,.10),transparent);border-left-color:var(--green)}}
.hist-break-row.tone-media{{background:linear-gradient(90deg,rgba(59,130,246,.10),transparent);border-left-color:var(--blue)}}
.hist-break-row.tone-moderado{{background:linear-gradient(90deg,rgba(245,158,11,.10),transparent);border-left-color:var(--orange)}}
.hist-break-row.tone-pro{{background:linear-gradient(90deg,rgba(37,99,235,.12),rgba(124,58,237,.08),transparent);border-left-color:var(--purple2)}}
.hist-break-row.green{{background:linear-gradient(90deg,rgba(0,200,150,.10),transparent);border-left-color:var(--green)}}
.hist-break-row.yellow{{background:linear-gradient(90deg,rgba(245,158,11,.10),transparent);border-left-color:var(--yellow)}}
.hist-break-row.blue{{background:linear-gradient(90deg,rgba(59,130,246,.10),transparent);border-left-color:var(--blue)}}
.hist-break-row span{{font-size:11px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-break-row strong{{font-family:'Inter',sans-serif;font-size:14px;font-weight:900;text-align:right}}
.hist-break-row em{{font-style:normal;font-size:10px;color:var(--text2);font-family:'Inter',sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:700;text-align:right}}
.hist-break-row .ok{{color:var(--green)}}
.hist-break-row .err{{color:var(--red)}}
.hist-break-name{{font-size:11px;font-weight:800;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-break-detail{{font-size:10px;color:var(--text2);font-family:'Inter',sans-serif;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:700}}
.hist-break-rate{{font-family:'Inter',sans-serif;font-size:14px;font-weight:900;text-align:right}}
.hist-break-empty{{font-size:10px;color:var(--muted);text-align:right}}
.hist-layout{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:14px;align-items:start}}
.hist-panel{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:14px;min-width:0}}
.hist-panel-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px;border-bottom:1px solid var(--border);padding-bottom:10px}}
.hist-panel-title{{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--text)}}
.hist-panel-note{{font-size:10px;color:var(--muted);font-family:'Inter',sans-serif;white-space:nowrap}}
.hist-market-list{{display:flex;flex-direction:column;gap:8px}}
.hist-market-row{{display:grid;grid-template-columns:30px minmax(0,1fr) 86px;gap:10px;align-items:center;padding:10px;border:1px solid rgba(148,163,184,.12);border-radius:9px;background:rgba(255,255,255,.018)}}
.hist-market-row:hover{{border-color:rgba(59,130,246,.38);background:rgba(59,130,246,.035)}}
.hist-rank{{font-family:'Inter',sans-serif;font-size:11px;color:var(--muted);font-weight:800;text-align:center}}
.hist-market-row strong{{display:block;font-size:13px;color:var(--text);font-weight:700;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-market-row small{{display:block;font-size:10px;color:var(--muted);margin-top:3px;font-family:'Inter',sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-market-row .ok{{color:var(--green)}}
.hist-market-row .err{{color:var(--red)}}
.hist-market-taxa{{font-family:'Inter',sans-serif;font-size:18px;font-weight:900;text-align:right}}
.hist-mkt-name{{font-size:13px;color:var(--text);font-weight:700;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hist-detail{{font-size:10px;color:var(--muted);margin-top:3px;font-family:'Inter',sans-serif}}
.hist-rate{{text-align:right}}
.hist-taxa-val{{font-size:21px;font-weight:800;font-family:'Inter',sans-serif;line-height:1}}
.hist-rate-label{{font-size:9px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.8px;margin-top:2px}}
.hist-bar-track{{height:5px;background:rgba(255,255,255,.06);border-radius:99px;margin-top:8px;overflow:hidden;grid-column:2/4}}
.hist-bar-fill{{height:100%;border-radius:99px}}
.hist-days{{display:flex;flex-direction:column;gap:8px}}
.day-hist-row{{display:grid;grid-template-columns:58px minmax(0,1fr) 92px;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid rgba(148,163,184,.12)}}
.day-hist-row:last-child{{border-bottom:none}}
.day-hist-date{{font-family:'Inter',sans-serif;font-size:11px;color:var(--text);font-weight:800}}
.day-hist-bar{{height:22px;background:rgba(255,255,255,.045);border-radius:7px;overflow:hidden;position:relative}}
.day-hist-fill{{height:100%;border-radius:7px;display:flex;align-items:center;padding:0 7px;font-size:10px;font-weight:800;font-family:'Inter',sans-serif;color:#fff;min-width:2px}}
.day-hist-info{{font-family:'Inter',sans-serif;font-size:11px;text-align:right;font-weight:800}}
.day-hist-detail{{display:block;color:var(--muted);font-size:9px;font-weight:600;margin-top:2px}}
.hist-spark{{display:flex;align-items:flex-end;gap:4px;height:42px;margin-top:10px;padding-top:8px;border-top:1px solid var(--border)}}
.hist-spark-bar{{flex:1;min-width:5px;border-radius:3px 3px 0 0;opacity:.95}}

/* ── HISTÓRICO GLOBAL — NOVO DASHBOARD ─────────────────────────── */
.hg-page{{display:flex;flex-direction:column;gap:14px;padding:18px 0 28px}}
.hg-hero{{background:linear-gradient(135deg,rgba(37,99,235,.12),rgba(124,58,237,.08) 50%,rgba(0,200,150,.06));border:1px solid rgba(148,163,184,.16);border-radius:14px;padding:20px 24px;display:grid;grid-template-columns:minmax(300px,1.4fr) minmax(200px,.7fr) minmax(240px,.9fr);gap:18px;align-items:stretch;position:relative;overflow:hidden}}
.hg-hero::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--blue),var(--purple2),var(--green))}}
.hg-hero-copy{{display:flex;flex-direction:column;justify-content:center}}
.hg-hero-label{{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:1.8px;color:var(--green);margin-bottom:8px}}
.hg-hero h2{{font-size:22px;font-weight:900;color:var(--text);line-height:1.18;margin:0 0 10px}}
.hg-hero-sub{{font-size:12px;color:#AFC4F5;line-height:1.55;font-weight:500}}
.hg-taxa-box{{border:1px solid rgba(148,163,184,.16);border-radius:11px;padding:14px 16px;background:rgba(255,255,255,.025);height:100%;display:flex;flex-direction:column;justify-content:center}}
.hg-taxa-label{{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);margin-bottom:6px}}
.hg-taxa-val{{font-size:38px;font-weight:900;line-height:1;font-family:'Inter',sans-serif}}
.hg-taxa-note{{font-size:10px;color:var(--muted);margin:4px 0 10px;font-weight:600}}
.hg-taxa-bar{{height:5px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden}}
.hg-taxa-bar-fill{{height:100%;border-radius:99px}}
.hg-insights{{display:flex;flex-direction:column;gap:8px}}
.hg-insight{{background:rgba(255,255,255,.03);border:1px solid rgba(148,163,184,.12);border-radius:9px;padding:10px 12px}}
.hg-insight-lbl{{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:4px}}
.hg-insight-val{{font-size:13px;font-weight:800;color:var(--text);margin-bottom:3px}}
.hg-insight-note{{font-size:10px;color:var(--muted)}}
.hg-kpi-row{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}}
.hg-kpi{{background:var(--s1);border:1px solid var(--border);border-radius:11px;padding:14px 16px;display:flex;align-items:center;gap:13px;min-width:0}}
.hg-kpi-icon{{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.hg-kpi-icon svg{{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.8}}
.hg-kpi-icon.blue{{background:rgba(59,130,246,.12);color:var(--blue)}}
.hg-kpi-icon.green{{background:rgba(0,200,150,.12);color:var(--green)}}
.hg-kpi-icon.teal{{background:rgba(0,200,150,.1);color:var(--teal)}}
.hg-kpi-icon.red{{background:rgba(239,68,68,.1);color:var(--red)}}
.hg-kpi-icon.purple{{background:rgba(124,58,237,.12);color:var(--purple2)}}
.hg-kpi-val{{font-size:26px;font-weight:800;line-height:1;font-family:'Inter',sans-serif;color:var(--text)}}
.hg-kpi-lbl{{font-size:10px;color:var(--muted);margin-top:3px;font-weight:600}}
.hg-kpi.ok .hg-kpi-val{{color:var(--green)}}
.hg-kpi.err .hg-kpi-val{{color:var(--red)}}
.hg-panels{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;align-items:stretch}}
.hg-panel{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:16px;min-width:0;display:flex;flex-direction:column;gap:12px;position:relative;overflow:hidden}}
.hg-panel::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:12px 12px 0 0}}
.hg-panel.p-blue::before{{background:linear-gradient(90deg,var(--blue),var(--purple2))}}
.hg-panel.p-green::before{{background:linear-gradient(90deg,var(--green),var(--teal))}}
.hg-panel.p-yellow::before{{background:linear-gradient(90deg,var(--yellow),var(--orange))}}
.hg-panel.p-purple::before{{background:linear-gradient(90deg,var(--purple2),var(--blue))}}
.hg-panel-label{{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:1.4px;color:var(--muted)}}
.hg-panel-title{{font-size:13px;font-weight:800;color:var(--text)}}
.hg-panel-note{{font-size:10px;color:var(--muted);margin-top:2px}}
.hg-donut-wrap{{display:flex;flex-direction:column;align-items:center;gap:10px}}
.hg-donut-svg{{display:block;overflow:visible}}
.hg-donut-bg{{fill:none;stroke:rgba(255,255,255,.07);stroke-width:10}}
.hg-donut-ring{{fill:none;stroke-width:10;stroke-linecap:round}}
.hg-donut-val{{font-size:22px;font-weight:900;font-family:'Inter',sans-serif;dominant-baseline:central;text-anchor:middle}}
.hg-donut-badge{{display:inline-flex;align-items:center;gap:5px;border-radius:6px;padding:3px 8px;font-size:10px;font-weight:700;align-self:flex-start}}
.hg-donut-badge svg{{width:11px;height:11px;stroke:currentColor;fill:none}}
.hg-donut-stats{{font-size:10px;color:var(--muted);text-align:center}}
.hg-donut-stats .ok{{color:var(--green)}}
.hg-donut-stats .err{{color:var(--red)}}
.hg-cat-rows{{display:flex;flex-direction:column;gap:6px;flex:1}}
.hg-cat-row{{display:grid;grid-template-columns:minmax(0,1fr) 56px;gap:6px;align-items:center;padding:8px 10px;border-radius:8px;border-left:3px solid transparent}}
.hg-cat-row.alta{{background:rgba(0,200,150,.07);border-left-color:var(--green)}}
.hg-cat-row.media{{background:rgba(59,130,246,.07);border-left-color:var(--blue)}}
.hg-cat-row.moderado{{background:rgba(245,158,11,.07);border-left-color:var(--orange)}}
.hg-cat-row-name{{font-size:12px;font-weight:700;color:var(--text)}}
.hg-cat-row-detail{{font-size:9px;color:var(--muted);margin-top:1px}}
.hg-cat-row .ok{{color:var(--green)}}
.hg-cat-row .err{{color:var(--red)}}
.hg-cat-rate{{font-size:16px;font-weight:900;font-family:'Inter',sans-serif;text-align:right}}
.hg-mkt-mini{{display:flex;flex-direction:column;gap:5px;flex:1}}
.hg-mkt-mini-row{{display:grid;grid-template-columns:minmax(0,1fr) 54px;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid rgba(148,163,184,.08)}}
.hg-mkt-mini-row:last-child{{border-bottom:none}}
.hg-mkt-mini-name{{font-size:11px;font-weight:600;color:var(--text2)}}
.hg-mkt-mini-rate{{font-size:13px;font-weight:800;font-family:'Inter',sans-serif;text-align:right}}
.hg-bottom{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(300px,1fr);gap:14px;align-items:start}}
.hg-card{{background:var(--s1);border:1px solid var(--border);border-radius:12px;padding:16px;min-width:0}}
.hg-card-title{{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1.1px;color:var(--text);margin-bottom:14px;display:flex;align-items:center;gap:7px}}
.hg-card-title svg{{width:14px;height:14px;stroke:currentColor;fill:none}}
.hg-rank-list{{display:flex;flex-direction:column;gap:6px}}
.hg-rank-row{{display:grid;grid-template-columns:32px 8px minmax(0,1fr) 70px;gap:10px;align-items:center;padding:10px 12px;border:1px solid rgba(148,163,184,.1);border-radius:9px;background:rgba(255,255,255,.015)}}
.hg-rank-row:hover{{border-color:rgba(59,130,246,.3);background:rgba(59,130,246,.03)}}
.hg-rank-num{{font-size:12px;font-weight:800;color:var(--muted);text-align:center;font-family:'Inter',sans-serif}}
.hg-rank-bar{{width:4px;height:32px;border-radius:2px;flex-shrink:0}}
.hg-rank-main{{min-width:0}}
.hg-rank-name{{font-size:13px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hg-rank-detail{{font-size:10px;color:var(--muted);margin-top:2px}}
.hg-rank-detail .ok{{color:var(--green)}}
.hg-rank-detail .err{{color:var(--red)}}
.hg-rank-rate{{font-size:15px;font-weight:900;font-family:'Inter',sans-serif;text-align:right}}
.hg-days-list{{display:flex;flex-direction:column;gap:4px}}
.hg-day-row{{display:grid;grid-template-columns:44px minmax(0,1fr) 110px;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(148,163,184,.08)}}
.hg-day-row:last-child{{border-bottom:none}}
.hg-day-date{{font-size:11px;font-weight:700;color:var(--text2)}}
.hg-day-bar{{height:18px;background:rgba(255,255,255,.05);border-radius:5px;overflow:hidden}}
.hg-day-fill{{height:100%;border-radius:5px;min-width:2px}}
.hg-day-info{{font-size:10px;font-weight:700;font-family:'Inter',sans-serif;text-align:right;white-space:nowrap}}
.hg-day-info .ok{{color:var(--green)}}
.hg-day-info .err{{color:var(--red)}}
@media(max-width:1100px){{.hg-hero{{grid-template-columns:1fr 1fr}}.hg-hero-sub{{display:none}}}}
@media(max-width:900px){{.hg-panels{{grid-template-columns:repeat(2,1fr)}}.hg-hero{{grid-template-columns:1fr}}.hg-insights{{display:none}}}}
@media(max-width:680px){{.hg-kpi-row{{grid-template-columns:repeat(3,1fr)}}.hg-panels{{grid-template-columns:1fr}}.hg-bottom{{grid-template-columns:1fr}}}}

/* BILHETES */
.bilhete-dia{{background:linear-gradient(135deg,rgba(0,200,150,.08),rgba(37,99,235,.06));border:2px solid rgba(0,200,150,.4);border-radius:13px;padding:18px;margin-bottom:20px;position:relative;overflow:hidden}}
.bilhete-dia::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--green),var(--teal),var(--blue))}}
.bilhete-dia-badge{{display:inline-flex;align-items:center;gap:6px;background:rgba(0,200,150,.15);border:1px solid rgba(0,200,150,.3);border-radius:6px;padding:4px 10px;font-size:11px;font-weight:700;color:var(--green);margin-bottom:10px;font-family:'JetBrains Mono',monospace;letter-spacing:.5px}}
.bilhete-dia-badge svg,.bilhete-title svg{{width:14px;height:14px;display:inline-block;vertical-align:-2px;margin-right:6px;stroke:currentColor}}
.bilhete-card{{background:var(--s1);border:1px solid var(--border);border-radius:11px;padding:16px;margin-bottom:14px;position:relative;overflow:hidden;transition:all .2s}}
.bilhete-card:hover{{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,0,0,.3)}}
.bilhete-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.bilhete-premium::before{{background:linear-gradient(90deg,var(--green),var(--teal))}}
.bilhete-equilibrado::before{{background:linear-gradient(90deg,var(--yellow),var(--orange))}}
.bilhete-conservador::before{{background:linear-gradient(90deg,var(--blue),var(--purple))}}
.bilhete-bingo::before{{background:linear-gradient(90deg,var(--yellow),var(--green),var(--blue))}}
.bilhete-bingo{{border-color:rgba(245,158,11,.32);background:linear-gradient(180deg,rgba(245,158,11,.07),rgba(6,11,20,.02)),var(--s1)}}
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
.bilhete-res{{width:112px;flex-shrink:0;text-align:right;white-space:normal}}
.bilhete-res .res-badge{{white-space:normal;justify-content:center;text-align:center;line-height:1.15;padding:5px 6px}}
.bilhete-market-stack{{width:230px;flex-shrink:0;display:flex;flex-direction:column;gap:6px;padding-right:8px}}
.bilhete-market-line{{display:grid;grid-template-columns:minmax(72px,1fr) 92px 42px;align-items:center;gap:8px}}
.bilhete-market-line .bilhete-mkt{{width:auto;padding-right:0}}
.bilhete-market-line .bilhete-score-bar{{width:auto;padding-right:0}}
.bilhete-market-line .bilhete-odd-val{{width:auto;text-align:right}}
.bilhete-footer{{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:10px;border-top:1px solid var(--border);flex-wrap:wrap;gap:6px}}
.bilhete-sels{{font-size:11px;color:var(--muted)}}
.bilhete-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start}}
.bilhete-grid .bilhete-card{{margin-bottom:0;height:100%}}
.bilhete-destaques{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start;margin-bottom:18px}}
.bilhete-destaques .bilhete-dia,.bilhete-destaques .bilhete-card{{margin-bottom:0;height:100%}}
@media(max-width:920px){{.bilhete-grid,.bilhete-destaques{{grid-template-columns:1fr}}}}
@media(max-width:1120px){{.hist-hero{{grid-template-columns:1fr 1fr}}.hist-hero>div:first-child{{grid-column:1/-1}}.hist-hero-insights{{grid-template-columns:1fr 1fr}}}}
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
  height:calc(var(--search-h) + var(--top-gap) + var(--date-strip-h) + var(--market-bar-h));
  margin-bottom:calc(-1 * (var(--search-h) + var(--top-gap) + var(--date-strip-h) + var(--market-bar-h)));
  background:var(--bg);z-index:109;pointer-events:none;flex:0 0 auto;
}}
.content-area.hist-mode::before{{display:none}}
.content-area.hist-mode .history-search-global,
.content-area.hist-mode .date-strip,
.content-area.hist-mode .mkt-cat-bar,
.content-area.hist-mode .sub-filter-bar{{display:none!important}}
.content-area.hist-mode .page-hero-title{{display:none!important}}
.content-area.hist-mode #panel-historico .main{{padding-top:0}}
/* NEW DATE BAR */
.date-strip{{
  background:var(--s1);border-bottom:1px solid var(--border);
  display:flex;align-items:center;overflow-x:auto;
  padding:0 16px;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent;
  position:sticky;top:calc(var(--nav-h) + var(--search-h) + var(--top-gap));z-index:120;
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
  position:sticky;top:calc(var(--nav-h) + var(--search-h) + var(--top-gap) + var(--date-strip-h));z-index:115;
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
.mkt-cat-tab.disabled{{cursor:default;opacity:.55;pointer-events:none}}
/* SUB FILTER BAR */
.sub-filter-bar{{
  background:var(--s1);border-bottom:1px solid var(--border);
  display:none;min-height:42px;padding:6px 16px;gap:8px;flex-wrap:wrap;
  position:sticky;top:calc(var(--nav-h) + var(--search-h) + var(--top-gap) + var(--date-strip-h) + var(--market-bar-h));z-index:110;
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
  .main{{padding:14px 0 18px;width:calc(100% - 16px)}}
  .kpi{{min-width:85px;padding:10px 12px}}
  .kpi-val{{font-size:20px}}
  .mkt-tab{{padding:9px 11px;font-size:12px}}
  .date-strip,.mkt-cat-bar,.sub-filter-bar{{width:calc(100% - 16px)}}
  .date-strip{{padding:0 8px}}
  .date-strip-item{{min-width:64px;padding:0 12px}}
  .mkt-cat-tab{{padding:0 8px;font-size:12px}}
  .sub-filter-bar{{padding:6px 8px}}
  .sub-filter-btn{{height:30px;padding:0 12px;font-size:12px}}
  .top-grid{{grid-template-columns:1fr}}
  .hist-hero{{grid-template-columns:1fr;padding:13px;gap:10px}}
  .hist-hero-insights{{grid-template-columns:1fr}}
  .hist-score-card{{min-width:0;width:100%;height:auto;padding:12px}}
  .hist-visual{{grid-template-columns:1fr;padding:12px;gap:10px;border-radius:12px}}
  .hist-line{{height:132px}}
  .hist-radial-wrap{{grid-template-columns:112px minmax(0,1fr);gap:8px}}
  .hist-radial{{width:112px;height:112px}}
  .hist-summary-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}
  .hist-audit-grid{{grid-template-columns:1fr}}
  .hist-audit-main{{grid-template-columns:88px minmax(0,1fr)}}
  .hist-audit-score{{font-size:22px}}
  .hist-layout{{grid-template-columns:1fr}}
  .hist-market-row{{grid-template-columns:26px minmax(0,1fr) 72px;padding:9px}}
  .hist-taxa-val{{font-size:18px}}
  .day-hist-row{{grid-template-columns:52px minmax(0,1fr) 76px}}
  table{{min-width:640px}}
}}
{RESPONSIVE_CSS}
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
    <div class="history-search-global" id="global-history-search"></div>

    <!-- DATE STRIP -->
    <div class="date-strip" id="date-strip">
      {date_tabs_html}
    </div>

    <!-- MARKET CATEGORY BAR -->
    <div class="mkt-cat-bar" id="mkt-cat-bar">
      <div class="mkt-cat-tab" data-cat="resultado" onclick="switchCat('resultado')">
        <i data-lucide="shield-check" style="width:14px;height:14px"></i> Resultado Final
      </div>
      <div class="mkt-cat-tab" data-cat="gols" onclick="switchCat('gols')">
        <i data-lucide="crosshair" style="width:14px;height:14px"></i> Gols
      </div>
      <div class="mkt-cat-tab" data-cat="escanteios" onclick="switchCat('escanteios')">
        <i data-lucide="corner-up-right" style="width:14px;height:14px"></i> Escanteios
      </div>
      <div class="mkt-cat-tab disabled" data-cat="cartoes" aria-disabled="true" title="Cartões em breve">
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
const MERCADOS   = ['Over 1.5','Over 2.5','BTTS','Over 0.5 HT','Under 4.5','Under 3.5','Esc 7.5','Esc 8.5'];
const MKT_RESULT = {{
  'Over 1.5':    'over15_ok',
  'Over 2.5':    'over25_ok',
  'BTTS':        'btts',
  'Over 0.5 HT': 'over05_ht_ok',
  'Under 4.5':   'under45_ok',
  'Under 3.5':   'under35_ok',
  'Esc 7.5':     'esc75_ok',
  'Esc 8.5':     'esc85_ok',
}};
const MKT_SCORE = {{
  'Over 1.5':'score_15','Over 2.5':'score_25','BTTS':'score_btts',
  'Over 0.5 HT':'score_05ht','Under 4.5':'score_u45','Under 3.5':'score_u35',
  'Esc 7.5':'score_esc75','Esc 8.5':'score_esc85',
}};
const MKT_MIN = {{
  'Over 1.5':85,'Over 2.5':75,'BTTS':70,'Over 0.5 HT':75,'Under 4.5':75,'Under 3.5':75,
  'Esc 7.5':75,'Esc 8.5':75,
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
    titulo='🟡 Over 1.5 ≥85%'; cor='var(--yellow)';
  }} else if(tipo==='esc'){{
    filtrados=jogos.filter(d=>d.score_esc75>=75).sort((a,b)=>sortByGrade(a,b,d=>d.grade_esc75||getPalpiteGrade(d),d=>d.score_esc75));
    titulo='Over 7.5 Escanteios ≥75%'; cor='var(--teal)';
  }}
  if(!filtrados.length){{
    panel.innerHTML=`<div class="kpi-filter-panel"><div class="kpi-filter-title" style="color:${{cor}}">${{titulo}}</div><div class="empty">Nenhum jogo neste filtro.</div></div>`;
    panel.style.display='block'; return;
  }}
  const rows=filtrados.map((d,i)=>{{
    const mktKey=getPalpiteKey(d);
    const rc=rowClass(d,mktKey);
    const scoreField=tipo==='prem'?getPalpiteScore(d):tipo==='15'?d.score_15:d.score_esc75;
    const mktShow=tipo==='prem'?getPalpiteMkt(d):tipo==='15'?'Over 1.5':'Esc 7.5';
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
  if(mkt==='Over 1.5')      val=d.odds_o15||d.odd_over15||d.odd_justa_15||oddEstimate(d,mkt);
  else if(mkt==='Over 2.5') val=d.odds_o25;
  else if(mkt==='Esc 7.5')  val=d.odds_corners_75;
  else if(mkt==='Esc 8.5')  val=d.odds_corners_85;
  else if(mkt==='Under 3.5'||mkt==='Under 4.5') val=d.odds_u45;
  else if(mkt==='BTTS')     val=null;
  if(!val) return'—';
  return parseFloat(val).toFixed(2);
}}
function oddMktLabel(mkt){{
  if(mkt==='Over 1.5')      return'ODD';
  if(mkt==='Over 2.5')      return'Odd O2.5';
  if(mkt==='Esc 7.5')       return'Odd E7.5';
  if(mkt==='Esc 8.5')       return'Odd E8.5';
  if(mkt==='Under 3.5')     return'Odd U3.5';
  if(mkt==='Under 4.5')     return'Odd U4.5';
  return'Odd';
}}

function oddForMarket(d,mkt){{
  const detail = oddForMarketDetail(d,mkt);
  return detail ? detail.value : null;
}}
function oddEstimate(d,mkt){{
  const scoreField = MKT_SCORE[mkt];
  const score = scoreField ? d[scoreField] : null;
  const n = Number(score);
  if(!Number.isFinite(n) || n<=0) return null;
  const p = Math.max(50, Math.min(88, n));
  return Math.round(Math.max(1.12, Math.min(2, 100 / p))*100)/100;
}}
function oddForMarketDetail(d,mkt){{
  let val=null;
  if(mkt==='Over 1.5')      val=d.odds_o15||d.odd_over15||d.odd_justa_15;
  else if(mkt==='Over 2.5') val=d.odds_o25;
  else if(mkt==='Esc 7.5')  val=d.odds_corners_75;
  else if(mkt==='Esc 8.5')  val=d.odds_corners_85;
  else if(mkt==='Under 3.5'||mkt==='Under 4.5') val=d.odds_u45;
  const n=parseFloat(val);
  if(Number.isFinite(n) && n>1) return {{value:n, source:'real'}};
  const est = oddEstimate(d,mkt);
  return est ? {{value:est, source:'est'}} : null;
}}
function via(v){{
  if(v==='Via 1')return'<span class="via v1">VIA1</span>';
  if(v==='Via 2')return'<span class="via v2">VIA2</span>';
  if(v==='Via 3')return'<span class="via v3">VIA3</span>';
  return'<span class="via vx">—</span>';
}}
function cornerPctColor(v){{
  const pct=v!=null?v:0;
  return pct>=80?'var(--green)':pct>=60?'var(--teal)':pct>=40?'var(--yellow)':pct>=20?'var(--orange)':'var(--red)';
}}
function cornerLineBadge(ok){{
  if(ok===true)return'<span class="res-badge hit"><i data-lucide="circle-check"></i> GREEN</span>';
  if(ok===false)return'<span class="res-badge miss"><i data-lucide="circle-x"></i> RED</span>';
  return'<span class="res-badge pending"><i data-lucide="clock"></i> S/D</span>';
}}
function cornerLineStatus(d,line){{
  const res=getResultado(d);
  if(!res||res.corners_total==null)return null;
  const total=Number(res.corners_total);
  if(!Number.isFinite(total))return null;
  return total>line;
}}
function cornerBestPick(d){{
  const opts=CORNER_LINES.map(l=>({{label:l.label,line:l.line,value:Number(d[l.field])}})).filter(x=>Number.isFinite(x.value));
  if(!opts.length)return null;
  return opts.sort((a,b)=>b.value-a.value)[0];
}}
function cornerBestCell(d){{
  const pick=cornerBestPick(d);
  if(!pick)return'<td><span class="corner-best-pick empty">Sem dados</span></td>';
  return`<td><span class="corner-best-pick">${{pick.label}} · ${{fmtNum(pick.value,0)}}%</span></td>`;
}}
function cornerBestRowClass(d){{
  const pick=cornerBestPick(d);
  if(!pick)return'row-pending';
  const ok=cornerLineStatus(d,pick.line);
  if(ok===true)return'row-hit';
  if(ok===false)return'row-miss';
  return'row-pending';
}}
function cornerOverCell(v,d,line){{
  if(v==null||!Number.isFinite(Number(v)))return'<td><span class="corner-no-data">Sem dados</span></td>';
  const pct=v!=null?Math.min(Math.max(Number(v)||0,0),100):0;
  const c=cornerPctColor(v);
  const fillWidth=pct>0?`calc(${{pct}}% - 6px)`:'0';
  const status=d&&line!=null&&v!=null?cornerLineStatus(d,line):null;
  return`<td><div class="corner-over-cell">
    <span class="corner-over-pct" style="color:${{c}}">${{v!=null?fmtNum(v,0)+'%':'--'}}</span>
    <div class="corner-over-track" style="border-color:${{c}}"><div class="corner-over-fill" style="width:${{fillWidth}};background:${{c}}"></div></div>
    <div class="corner-line-result">${{cornerLineBadge(status)}}</div>
  </div></td>`;
}}
function pct(v){{return v!=null?v+'%':'—';}}
function pctText(v){{
  if(v==null||v==='')return'—';
  const n=Number(v);
  if(!Number.isFinite(n))return'—';
  return (Math.round(n*10)/10).toString().replace('.0','')+'%';
}}
const LEAGUE_COUNTRY_MAP = {json.dumps(LEAGUE_COUNTRY_MAP, ensure_ascii=False)};
const COUNTRY_META = {{
  'Argentina':['ARG','ar'],'Australia':['AUS','au'],'Belarus':['BLR','by'],'Belgium':['BEL','be'],
  'Bhutan':['BHU','bt'],'Brazil':['BRA','br'],'Chile':['CHI','cl'],'Croatia':['CRO','hr'],
  'Denmark':['DEN','dk'],'Ecuador':['ECU','ec'],'England':['ENG','gb-eng'],'Estonia':['EST','ee'],
  'Ethiopia':['ETH','et'],'Europe':['EUR','eu'],'Finland':['FIN','fi'],'France':['FRA','fr'],
  'Germany':['GER','de'],'Greece':['GRE','gr'],'Iceland':['ISL','is'],'Iran':['IRN','ir'],
  'Italy':['ITA','it'],'Kazakhstan':['KAZ','kz'],'Kyrgyzstan':['KGZ','kg'],'Lebanon':['LIB','lb'],
  'Lithuania':['LTU','lt'],'Morocco':['MAR','ma'],'Netherlands':['NED','nl'],'Norway':['NOR','no'],
  'Papua New Guinea':['PNG','pg'],'Paraguay':['PAR','py'],'Portugal':['POR','pt'],'Romania':['ROU','ro'],
  'Saudi Arabia':['KSA','sa'],'South America':['SOU','un'],'Spain':['ESP','es'],'Turkey':['TUR','tr'],
  'United States':['USA','us'],'World':['WOR','un'],'Yemen':['YEM','ye']
}};
Object.values(COUNTRY_META).forEach(meta=>{{ COUNTRY_META[meta[0]]=meta; }});
function leagueMeta(d){{
  const fallback=LEAGUE_COUNTRY_MAP[String(d.liga||'').toLowerCase()]||{{}};
  const country=d.country||fallback.country||'';
  const meta=COUNTRY_META[country]||[country.slice(0,3).toUpperCase(),''];
  return {{country, code:meta[0]||'', iso:meta[1]||'', league:d.liga||''}};
}}
function leagueMetaHtml(d){{
  const m=leagueMeta(d);
  const code=m.code?`<span class="league-code">${{m.code}}</span>`:'';
  const flag=m.iso?`<img class="league-flag" src="https://flagcdn.com/w40/${{m.iso}}.png" alt="${{m.code}}" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{{className:'league-flag',textContent:'📍'}}))">`:`<span class="league-flag">📍</span>`;
  return `<span class="league-meta" title="${{m.country?m.country+' · ':''}}${{m.league}}">${{flag}}${{code}}<span class="league-name">${{m.league}}</span></span>`;
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
  return`<td><div class="jogo-main">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div><div class="jogo-sub">${{leagueMetaHtml(d)}}</div></td>`;
}}
function getJogos(date){{return(ALL_DATA[date]||{{}}).jogos||[];}}

// ── Resultado helpers ──────────────────────────────────────────────
function getResultado(jogo){{return jogo.resultado||null;}}
function isConfirmado(date){{return !!(ALL_DATA[date]||{{}}).resultado_confirmado;}}
const LINHA_SEGURA_DIFF = 8;
function gradeForMkt(jogo,mkt){{
  const map = {{
    'Over 1.5':'grade_15','Over 2.5':'grade_25','Esc 7.5':'grade_esc75','Esc 8.5':'grade_esc85',
    'BTTS':'grade_btts','Over 0.5 HT':'grade_05ht',
    'Under 3.5':'grade_u35','Under 4.5':'grade_u45'
  }};
  const field = map[mkt];
  return (field && jogo[field]) || gradeFromScore(scoreForMkt(jogo,mkt));
}}
function scoreForMkt(jogo,mkt){{
  const field = MKT_SCORE[mkt];
  if(field && jogo[field] != null) return jogo[field];
  return jogo.palpite_score!=null?jogo.palpite_score:(jogo.best_score!=null?jogo.best_score:(jogo.score||0));
}}
function mainMarketCandidates(jogo){{
  const mkts=[];
  function push(mkt,key,score,grade,enabled=true){{
    const n=Number(score);
    if(!enabled || !Number.isFinite(n))return;
    mkts.push({{mkt,key,score:n,grade:grade||gradeFromScore(n),kind:'main'}});
  }}
  push('Over 1.5','over15_ok',jogo.score_15,jogo.grade_15,jogo.passou_filtro);
  push('Over 2.5','over25_ok',jogo.score_25,jogo.grade_25);
  push('BTTS','btts',jogo.score_btts,jogo.grade_btts);
  push('Over 0.5 HT','over05_ht_ok',jogo.score_05ht,jogo.grade_05ht);
  push('Under 4.5','under45_ok',jogo.score_u45,jogo.grade_u45);
  push('Under 3.5','under35_ok',jogo.score_u35,jogo.grade_u35,under35Filter(jogo));
  push('Esc 7.5','esc75_ok',jogo.score_esc75,jogo.grade_esc75);
  push('Esc 8.5','esc85_ok',jogo.score_esc85,jogo.grade_esc85);
  const rf=rfVisualPick(rfPick(jogo));
  if(rf){{
    mkts.push({{mkt:rfMarketLabel(rf),key:'rf',score:rf.score,grade:rf.grade||gradeFromScore(rf.score),kind:'rf',rf}});
  }}
  return mkts.sort((a,b)=>(b.score||0)-(a.score||0));
}}
function mainBestPick(jogo){{
  const picks=mainMarketCandidates(jogo);
  if(picks.length)return picks[0];
  const legacy=jogo.palpite_mkt||jogo.best_mkt||jogo.mkt||'';
  if(legacy){{
    return {{mkt:legacy,key:MKT_RESULT[legacy]||'over15_ok',score:scoreForMkt(jogo,legacy),grade:gradeForMkt(jogo,legacy),kind:'main'}};
  }}
  return {{mkt:'Over 1.5',key:'over15_ok',score:jogo.score_15||0,grade:jogo.grade_15||gradeFromScore(jogo.score_15||0),kind:'main'}};
}}
function normalizedPalpite(jogo){{
  const pick = mainBestPick(jogo);
  let mkt = pick.mkt||'';
  if(mkt==='Over 2.5' && (jogo.score_15||0)>=MKT_MIN['Over 1.5'] && jogo.passou_filtro && ((jogo.score_25||0)-(jogo.score_15||0))<LINHA_SEGURA_DIFF){{
    mkt='Over 1.5';
  }}
  if(mkt==='Esc 8.5' && jogo.score_esc75 != null && ((jogo.score_esc85||0)-(jogo.score_esc75||0))<LINHA_SEGURA_DIFF){{
    mkt='Esc 7.5';
  }}
  if(pick.kind==='rf')return pick;
  return {{mkt, score:scoreForMkt(jogo,mkt), grade:gradeForMkt(jogo,mkt), key:MKT_RESULT[mkt]||'over15_ok', kind:'main'}};
}}
function getPalpiteMkt(jogo){{return normalizedPalpite(jogo).mkt;}}
function getPalpiteGrade(jogo){{return normalizedPalpite(jogo).grade||'D';}}
function getPalpiteScore(jogo){{return normalizedPalpite(jogo).score||0;}}
function getPalpiteKey(jogo){{return normalizedPalpite(jogo).key||MKT_RESULT[getPalpiteMkt(jogo)]||'over15_ok';}}
function primaryResultBadge(jogo){{
  const pick=normalizedPalpite(jogo);
  if(pick.kind==='rf')return rfBadge(rfResult(jogo,pick.rf));
  return resBadge(jogo,pick.key||MKT_RESULT[pick.mkt]||'over15_ok');
}}
function primaryResultOk(jogo){{
  const pick=normalizedPalpite(jogo);
  if(pick.kind==='rf'){{
    const r=rfResult(jogo,pick.rf);
    if(r==='GREEN')return true;
    if(r==='RED')return false;
    return null;
  }}
  return resultOk(getResultado(jogo),pick.key||MKT_RESULT[pick.mkt]||'over15_ok');
}}
function primaryRowClass(jogo){{
  const pick=normalizedPalpite(jogo);
  if(pick.kind==='rf'){{
    const r=rfResult(jogo,pick.rf);
    if(r==='GREEN')return'row-hit';
    if(r==='RED')return'row-miss';
    return'row-pending';
  }}
  return rowClass(jogo,pick.key||MKT_RESULT[pick.mkt]||'over15_ok');
}}
function primaryPlacarCard(jogo){{
  const pick=normalizedPalpite(jogo);
  if(pick.kind==='rf'){{
    const res=getResultado(jogo);
    if(!res)return`<div class="top-placar pending"><i data-lucide="clock"></i><span class="ft">Aguardando</span></div>`;
    const r=rfResult(jogo,pick.rf);
    const cls=r==='GREEN'?'hit':r==='RED'?'miss':'pending';
    const icon=r==='GREEN'?'circle-check':r==='RED'?'circle-x':'circle-help';
    return`<div class="top-placar ${{cls}}"><i data-lucide="${{icon}}"></i><div><span class="ft">${{res.placar}}</span> <span class="ht">HT ${{res.placar_ht}}</span></div></div>`;
  }}
  return placarCard(jogo,pick.key||MKT_RESULT[pick.mkt]||'over15_ok');
}}
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
  if(!res)return'<span class="res-badge pending"><i data-lucide="clock"></i> Aguardando</span>';
  const ok=resultOk(res,mktKey);
  if(ok===true) return'<span class="res-badge hit"><i data-lucide="circle-check"></i> GREEN</span>';
  if(ok===false)return'<span class="res-badge miss"><i data-lucide="circle-x"></i> RED</span>';
  return'<span class="res-badge pending"><i data-lucide="triangle-alert"></i> Não confirmado</span>';
}}

function rowClass(jogo, mktKey){{
  const res=getResultado(jogo);
  if(!res)return'row-pending';
  const ok=resultOk(res,mktKey);
  if(ok===true)return'row-hit';
  if(ok===false)return'row-miss';
  return'row-pending';
}}

function resultOk(res, mktKey){{
  if(!res)return null;
  if(mktKey==='under35_ok' && res.under35_ok == null && res.gols_total != null){{
    return res.gols_total <= 3;
  }}
  return res[mktKey];
}}

function placarCell(jogo){{
  const res=getResultado(jogo);
  if(!res)return'<td class="mono muted">—</td>';
  return`<td><div class="placar-cell">${{res.placar}}</div><div class="placar-ht">HT ${{res.placar_ht}}</div></td>`;
}}

function placarCard(jogo, mktKey){{
  const res=getResultado(jogo);
  if(!res)return`<div class="top-placar pending"><i data-lucide="clock"></i><span class="ft">Aguardando</span></div>`;
  const ok=resultOk(res,mktKey);
  const cls=ok===true?'hit':ok===false?'miss':'pending';
  const icon=ok===true?'circle-check':ok===false?'circle-x':'circle-help';
  const cant=res.corners_total!=null?`<i data-lucide="flag"></i>${{res.corners_total}}`:'';
  return`<div class="top-placar ${{cls}}">
    <i data-lucide="${{icon}}"></i>
    <div><span class="ft">${{res.placar}}</span> <span class="ht">HT ${{res.placar_ht}}${{cant}}</span></div>
  </div>`;
}}

function under35Filter(d){{
  if(d.under35_filter === true) return true;
  if(d.under35_filter === false) return false;
  const score = d.score_u35 || 0;
  const prob = d.poisson_u35;
  const exg = d.exg_tot;
  const o25 = d.over25_g;
  const h2h = d.h2h_goals;
  const btts = d.btts_cf;
  const ppg = d.ppg_avg;
  const modelOk = prob != null && exg != null && prob >= 78 && exg <= 2.5;
  const noXgOk = prob == null && exg == null && (ppg == null || ppg <= 1.6) && (o25 == null || o25 <= 45);
  const blockersOk = (o25 == null || o25 <= 55) && (h2h == null || h2h <= 3.0) && (btts == null || btts <= 75);
  return score >= MKT_MIN['Under 3.5'] && blockersOk && (modelOk || noXgOk);
}}

function underMarketPick(d){{
  if(under35Filter(d)){{
    return {{
      mkt:'Under 3.5',
      key:'under35_ok',
      score:d.score_u35||0,
      grade:d.grade_u35||'D',
      poisson:d.poisson_u35,
      exg:d.exg_tot,
    }};
  }}
  if((d.score_u45||0) >= MKT_MIN['Under 4.5']){{
    return {{
      mkt:'Under 4.5',
      key:'under45_ok',
      score:d.score_u45||0,
      grade:d.grade_u45||'D',
      poisson:d.poisson_u45,
      exg:d.exg_tot,
    }};
  }}
  return null;
}}

function approvedMarkets(d){{
  const mkts = [];
  function push(mkt,key,score,grade,cls){{
    if(score == null) return;
    mkts.push({{mkt,key,score,grade:grade||gradeFromScore(score),cls:cls||''}});
  }}
  if((d.score_15||0) >= MKT_MIN['Over 1.5'] && d.passou_filtro) push('Over 1.5','over15_ok',d.score_15,d.grade_15,'primary');
  if((d.score_25||0) >= MKT_MIN['Over 2.5']) push('Over 2.5','over25_ok',d.score_25,d.grade_25);
  if((d.score_btts||0) >= MKT_MIN['BTTS']) push('BTTS','btts',d.score_btts,d.grade_btts);
  if((d.score_05ht||0) >= MKT_MIN['Over 0.5 HT']) push('Over 0.5 HT','over05_ht_ok',d.score_05ht,d.grade_05ht);
  const under = underMarketPick(d);
  if(under) push(under.mkt,under.key,under.score,under.grade,'protect');
  if((d.score_esc75||0) >= MKT_MIN['Esc 7.5']) push('Esc 7.5','esc75_ok',d.score_esc75,d.grade_esc75);
  if((d.score_esc85||0) >= MKT_MIN['Esc 8.5']) push('Esc 8.5','esc85_ok',d.score_esc85,d.grade_esc85);
  return mkts.sort((a,b)=>(b.score||0)-(a.score||0));
}}

function gradeFromScore(score){{
  if(score>=88)return'A+';
  if(score>=80)return'A';
  if(score>=70)return'B';
  if(score>=60)return'C';
  return'D';
}}

function approvedMarketsHtml(d, opts){{
  opts = opts || {{}};
  const primary = opts.primary || getPalpiteMkt(d);
  const max = opts.max || 4;
  let mkts = approvedMarkets(d).filter(x=>x.mkt!==primary);
  mkts = mkts.slice(0,max);
  if(!mkts.length) return opts.empty ? '<span class="muted" style="font-size:11px">Sem alternativas</span>' : '';
  const label = opts.label === false ? '' : '<span class="alt-label">Também aprovado</span>';
  const res = getResultado(d);
  return `<div class="alt-mkts">${{label}}${{mkts.map(x=>{{
    const ok = res ? resultOk(res,x.key) : null;
    const stCls = ok===true ? 'hit' : ok===false ? 'miss' : res ? 'pending' : '';
    const stTxt = ok===true ? 'GREEN' : ok===false ? 'RED' : res ? 'S/D' : '';
    return `<span class="alt-badge ${{x.cls}} ${{stCls}}">${{x.mkt}} <strong>${{pctText(x.score)}}</strong>${{stTxt?`<span class="alt-res">${{stTxt}}</span>`:''}}</span>`;
  }}).join('')}}</div>`;
}}

// ── Resultado Final helpers ───────────────────────────────────────
const RF_BACKTEST_START = '01-05-2026';
function dateObj(date){{
  const [dd,mm,yyyy]=String(date||'').split('-').map(Number);
  return new Date(yyyy||1970,(mm||1)-1,dd||1);
}}
function todayKey(){{
  return new Date().toLocaleDateString('pt-BR',{{day:'2-digit',month:'2-digit',year:'numeric'}}).split('/').join('-');
}}
function numVal(v){{const n=parseFloat(v);return Number.isFinite(n)?n:null;}}
function rfNum(d,k){{const v=numVal(d[k]);return v!=null?v:numVal((d.rf_csv||{{}})[k]);}}
function sideName(side){{return side==='home'?'Casa':'Visitante';}}
function rfFirstVal(d, keys){{
  for(const k of keys){{
    const v=rfNum(d,k);
    if(v!=null)return v;
  }}
  return null;
}}
function rfPair(d, homeKeys, awayKeys){{
  return {{h:rfFirstVal(d,homeKeys),a:rfFirstVal(d,awayKeys)}};
}}
function rfTier(v, tiers){{
  if(v==null)return 0;
  for(const t of tiers)if(v>=t[0])return t[1];
  return 0;
}}
function rfOddsPoints(odd){{
  if(odd==null)return 0;
  if(odd<=1.35)return 20;
  if(odd<=1.50)return 17;
  if(odd<=1.70)return 13;
  if(odd<=1.90)return 8;
  return 0;
}}
function rfMarketLabel(p){{
  if(!p)return'—';
  if(p.market==='win')return`Vitória ${{sideName(p.side)}}`;
  return p.side==='home'?'Dupla Chance 1X':'Dupla Chance X2';
}}
function rfFavSide(d){{
  const oh=rfNum(d,'odds_h'), oa=rfNum(d,'odds_a');
  const wh=rfNum(d,'win_home'), wa=rfNum(d,'win_away');
  if(oh&&oa&&oh!==oa)return {{side:oh<oa?'home':'away', favOdd:Math.min(oh,oa), dogOdd:Math.max(oh,oa), oddGap:Math.abs(oh-oa), impliedGap:Math.abs((1/oh)-(1/oa))*100, source:'odds'}};
  if(wh!=null&&wa!=null&&Math.abs(wh-wa)>=8)return {{side:wh>wa?'home':'away', favOdd:null, dogOdd:null, oddGap:null, impliedGap:Math.abs(wh-wa), source:'api'}};
  return null;
}}
function rfEdge(d, side){{
  const sign = side==='home'?1:-1;
  const shots=rfPair(d,['shots_h','avg_shots_h'],['shots_a','avg_shots_a']);
  const sot=rfPair(d,['sot_h','avg_sot_h'],['sot_a','avg_sot_a']);
  const metrics = [
    {{name:'PPG', diff:((rfNum(d,'ppg_h')||0)-(rfNum(d,'ppg_a')||0))*sign, min:.35, weight:18}},
    {{name:'xG', diff:((rfNum(d,'exg_h')||0)-(rfNum(d,'exg_a')||0))*sign, min:.25, weight:18}},
    {{name:'Ataque', diff:((rfNum(d,'avg_sc_h')||0)-(rfNum(d,'avg_sc_a')||0))*sign, min:.25, weight:14}},
    {{name:'Finalizações', diff:((shots.h||0)-(shots.a||0))*sign, min:2.5, weight:10}},
    {{name:'SOT', diff:((sot.h||0)-(sot.a||0))*sign, min:.8, weight:10}},
    {{name:'Prob. API', diff:((rfNum(d,'win_home')||0)-(rfNum(d,'win_away')||0))*sign, min:15, weight:20}},
  ];
  const ok = metrics.filter(m=>Number.isFinite(m.diff)&&m.diff>=m.min);
  const strength = ok.reduce((acc,m)=>acc+m.weight+Math.min(12,Math.abs(m.diff)*2),0);
  return {{ok, strength}};
}}
function rfDominanceIndex(d, side, favOdd){{
  const sign=side==='home'?1:-1;
  const used=[];
  let total=0;
  function add(name, exists, points){{
    if(exists)used.push(name);
    total += points||0;
  }}
  const ppg=rfPair(d,['ppg_h'],['ppg_a']);
  const xg=rfPair(d,['exg_h'],['exg_a']);
  const attack=rfPair(d,['avg_sc_h'],['avg_sc_a']);
  const defense=rfPair(d,['avg_co_h'],['avg_co_a']);
  const shots=rfPair(d,['shots_h','avg_shots_h'],['shots_a','avg_shots_a']);
  const sot=rfPair(d,['sot_h','avg_sot_h'],['sot_a','avg_sot_a']);
  const apiProb=side==='home'?rfNum(d,'win_home'):rfNum(d,'win_away');
  const ppgDiff=ppg.h!=null&&ppg.a!=null?((ppg.h-ppg.a)*sign):null;
  const xgDiff=xg.h!=null&&xg.a!=null?((xg.h-xg.a)*sign):null;
  const attackDiff=attack.h!=null&&attack.a!=null?((attack.h-attack.a)*sign):null;
  const defenseDiff=defense.h!=null&&defense.a!=null?((defense.a-defense.h)*sign):null;
  const shotsDiff=shots.h!=null&&shots.a!=null?((shots.h-shots.a)*sign):null;
  const sotDiff=sot.h!=null&&sot.a!=null?((sot.h-sot.a)*sign):null;

  add('Odds',favOdd!=null,rfOddsPoints(favOdd));
  add('PPG',ppgDiff!=null,rfTier(ppgDiff,[[1,20],[.70,16],[.50,12],[.30,8],[.15,4]]));
  add('xG',xgDiff!=null,rfTier(xgDiff,[[1.20,20],[.90,16],[.60,12],[.30,8],[.15,4]]));
  add('Ataque',attackDiff!=null,rfTier(attackDiff,[[1.20,15],[.80,12],[.50,9],[.30,6],[.15,3]]));
  add('Defesa',defenseDiff!=null,rfTier(defenseDiff,[[.80,10],[.60,8],[.40,6],[.20,3]]));
  add('Finalizações',shotsDiff!=null,rfTier(shotsDiff,[[5,5],[3,3]]));
  add('SOT',sotDiff!=null,rfTier(sotDiff,[[2,5],[1,3]]));
  add('API',apiProb!=null,rfTier(apiProb,[[70,5],[60,4],[55,3],[50,2]]));

  const quality=(used.length/8)*100;
  const mult=quality>=90 ? 1 : quality>=80 ? .97 : quality>=70 ? .94 : quality>=60 ? .90 : .85;
  const dominance=Math.max(0,Math.min(100,Math.round(total*mult*10)/10));
  return {{dominance,quality:Math.round(quality),used,total,apiProb}};
}}
function rfDominanceContextFloor(d, side, favOdd, dom){{
  const isWorldCup=String(d.liga||'').toLowerCase().includes('world cup');
  const ppg=rfPair(d,['ppg_h'],['ppg_a']);
  const sign=side==='home'?1:-1;
  const ppgDiff=ppg.h!=null&&ppg.a!=null?((ppg.h-ppg.a)*sign):null;
  let dominance=dom.dominance;
  if(isWorldCup && favOdd!=null && favOdd<=1.20 && dominance>=60)dominance=Math.max(dominance,95);
  else if(isWorldCup && favOdd!=null && favOdd<=1.25 && dominance>=60)dominance=Math.max(dominance,92);
  if(!isWorldCup && favOdd!=null && favOdd<=1.90 && ppgDiff!=null && ppgDiff>=1 && dominance>=55)dominance=Math.max(dominance,70);
  return {{...dom,dominance:Math.round(Math.min(100,dominance)*10)/10,isWorldCup}};
}}
function rfNameMatchesSide(d, side, name){{
  const target=String(side==='home'?d.home:d.away||'').toLowerCase();
  const value=String(name||'').toLowerCase();
  return !!target && !!value && (target.includes(value)||value.includes(target));
}}
function rfStrongWinFallback(d, side, favOdd, aligned, edge, dom){{
  if(!(favOdd!=null && favOdd<=1.45 && aligned>=4 && dom.dominance>=55))return false;
  const apiAligned=dom.apiProb!=null && dom.apiProb>=50 && rfNameMatchesSide(d,side,d.pred_winner);
  const hasCore=edge.ok.some(m=>m.name==='PPG') && edge.ok.some(m=>m.name==='xG') && edge.ok.some(m=>m.name==='Prob. API');
  return apiAligned && hasCore;
}}
function rfAnalysis(d){{
  const fav=rfFavSide(d);
  if(!fav)return {{approved:false,stage:'Sem favorito',reason:'odds 1X2 ausentes/iguais e probabilidade API sem diferença mínima',score:null,grade:null,p:null}};
  const side=fav.side;
  const edge=rfEdge(d,side);
  const aligned=edge.ok.length;
  const isFriendly=String(d.liga||'').toLowerCase().includes('friendly');
  const favOdd=fav.favOdd;
  const oddsScore=favOdd?Math.max(0,100-(favOdd*22)):(55+Math.min(30,fav.impliedGap||0));
  let score=Math.min(100,Math.round((oddsScore + edge.strength + Math.min(20,fav.impliedGap||0)) * 10)/10);
  const reasons=[`favorito ${{sideName(side)}}${{favOdd?` @ ${{favOdd.toFixed(2)}}`:''}}`, `${{aligned}} sinais alinhados`].concat(edge.ok.slice(0,4).map(m=>`${{m.name}} +${{m.diff.toFixed(m.name==='Prob. API'?0:1)}}`));

  if(isFriendly && (!favOdd || favOdd>1.30) && !edge.ok.find(m=>m.name==='PPG'||m.name==='Prob. API')){{
    return {{approved:false,stage:'Contexto',reason:'amistoso sem odd forte e sem PPG/API alinhado',side,score,grade:gradeFromScore(score),reasons,p:null}};
  }}

  let market=null;
  if((favOdd&&favOdd<=1.45&&aligned>=3) || (favOdd&&favOdd<=1.65&&aligned>=4&&edge.ok.find(m=>m.name==='Prob. API'))){{
    market='win'; score=Math.max(score,88);
  }} else if((favOdd&&favOdd<=1.75&&aligned>=3) || (!favOdd&&aligned>=4&&fav.impliedGap>=18)){{
    market='dnb'; score=Math.max(score,82);
  }} else if((favOdd&&favOdd<=1.90&&aligned>=2) || (!favOdd&&aligned>=3&&fav.impliedGap>=12)){{
    market='dc'; score=Math.max(score,76);
  }}
  if(!market){{
    return {{approved:false,stage:'Seleção de mercado',reason:'não atingiu odds/sinais mínimos para Vitória ou Dupla Chance',side,score,grade:gradeFromScore(score),reasons,p:null}};
  }}
  const dom=rfDominanceContextFloor(d,side,favOdd,rfDominanceIndex(d,side,favOdd));
  const strongWinFallback=market==='win' && rfStrongWinFallback(d,side,favOdd,aligned,edge,dom);
  if(dom.dominance<65 && !strongWinFallback){{
    reasons.push(`Dominância ${{Math.round(dom.dominance)}}`);
    return {{approved:false,stage:'Dominância',reason:`dominância ${{Math.round(dom.dominance)}} abaixo do mínimo 65`,side,market,score:Math.min(100,Math.round(score*10)/10),grade:gradeFromScore(score),dominance:dom.dominance,dataQuality:dom.quality,reasons,p:null}};
  }}
  const apiWinOk=dom.apiProb!=null && (dom.apiProb>=55 || (dom.isWorldCup && favOdd!=null && favOdd<=1.25 && dom.dominance>=90));
  if(!(strongWinFallback || (market==='win' && dom.dominance>=85 && favOdd!=null && favOdd<=1.60 && apiWinOk))){{
    market='dc';
  }}
  reasons.push(`Dominância ${{Math.round(dom.dominance)}}`);
  const p={{market,side,score:Math.min(100,Math.round(score*10)/10),grade:gradeFromScore(score),dominance:dom.dominance,dataQuality:dom.quality,reasons}};
  return {{approved:true,stage:'Aprovado',reason:'aprovado pelo filtro 1X2',side,market,score:p.score,grade:p.grade,dominance:dom.dominance,dataQuality:dom.quality,reasons,p}};
}}
function rfPick(d){{
  return rfAnalysis(d).p;
}}
function rfResult(jogo,pick){{
  const res=getResultado(jogo);
  if(!res)return 'PENDING';
  const hg=numVal(res.gols_home), ag=numVal(res.gols_away);
  if(hg==null||ag==null)return 'PENDING';
  const homeWin=hg>ag, awayWin=ag>hg, draw=hg===ag;
  if(pick.market==='win'){{
    return ((pick.side==='home'&&homeWin)||(pick.side==='away'&&awayWin))?'GREEN':'RED';
  }}
  if(pick.market==='dnb'){{
    if(draw)return 'VOID';
    return ((pick.side==='home'&&homeWin)||(pick.side==='away'&&awayWin))?'GREEN':'RED';
  }}
  if(pick.market==='dc'){{
    const lost=(pick.side==='home'&&awayWin)||(pick.side==='away'&&homeWin);
    return lost?'RED':'GREEN';
  }}
  return 'PENDING';
}}
function rfBadge(result){{
  if(result==='GREEN')return'<span class="res-badge hit"><i data-lucide="circle-check"></i> GREEN</span>';
  if(result==='RED')return'<span class="res-badge miss"><i data-lucide="circle-x"></i> RED</span>';
  if(result==='VOID')return'<span class="res-badge pending"><i data-lucide="rotate-ccw"></i> Anulado</span>';
  return'<span class="res-badge pending"><i data-lucide="clock"></i> Aguardando</span>';
}}
function rfVisualPick(pick){{
  if(!pick)return null;
  if(pick.market!=='dnb')return pick;
  return {{...pick,market:'dc',originalMarket:'dnb'}};
}}
function rfVisualAnalysis(analysis){{
  if(!analysis)return analysis;
  const p=rfVisualPick(analysis.p);
  const market=analysis.market==='dnb'?'dc':analysis.market;
  return {{...analysis,p,market}};
}}
function rfRowsForDate(date){{
  return getJogos(date).map(j=>({{j,p:rfVisualPick(rfPick(j))}})).filter(x=>x.p).sort((a,b)=>(b.p.score||0)-(a.p.score||0));
}}
function rfHistoricoRows(){{
  const start=dateObj(RF_BACKTEST_START);
  const end=dateObj(todayKey());
  return Object.keys(ALL_DATA).filter(d=>dateObj(d)>=start&&dateObj(d)<=end).sort((a,b)=>dateObj(a)-dateObj(b)).flatMap(d=>rfRowsForDate(d).map(x=>({{date:d,...x,result:rfResult(x.j,x.p)}})));
}}
function rfSummary(rows){{
  const s={{gerados:rows.length,green:0,red:0,void:0,pending:0}};
  rows.forEach(r=>{{if(r.result==='GREEN')s.green++;else if(r.result==='RED')s.red++;else if(r.result==='VOID')s.void++;else s.pending++;}});
  const den=s.green+s.red;
  s.taxa=den?Math.round((s.green/den)*1000)/10:null;
  return s;
}}
function rfTaxaText(t){{return t==null?'—':`${{t}}%`;}}

function cardOverlayClass(jogo){{
  const res=getResultado(jogo);
  if(!res)return'';
  const ac=jogo.acertos||{{}};
  const bestMktAcerto=ac[getPalpiteMkt(jogo)];
  if(bestMktAcerto){{
    if(bestMktAcerto.acertou===true)return' tc-hit';
    if(bestMktAcerto.acertou===false)return' tc-miss';
  }}
  const ok=primaryResultOk(jogo);
  if(ok===true)return' tc-hit';
  if(ok===false)return' tc-miss';
  return'';
}}

function topCardStatus(jogo){{
  const ok=primaryResultOk(jogo);
  if(ok===true)return{{text:'GREEN',cls:'hit'}};
  if(ok===false)return{{text:'RED',cls:'miss'}};
  return getResultado(jogo)?{{text:'Não confirmado',cls:'pending'}}:{{text:'Aguardando',cls:'pending'}};
}}

// ── Render Global KPIs (header) ────────────────────────────────────

// ── Visão Geral ────────────────────────────────────────────────────
const historicoSearchState = {{}};

function historicoSearchHtml(date){{
  const st = historicoSearchState[date] || {{q:'', status:'todos', grade:'todos', mercado:'todos'}};
  const totalDatas = Object.keys(ALL_DATA).filter(d=>d!=='index').length;
  return `<div class="history-search" id="history-search-${{date}}">
    <div class="history-search-head">
      <div class="history-search-title"><i data-lucide="search"></i> Pesquisar</div>
      <div class="history-search-meta">${{totalDatas}} datas carregadas · busca global</div>
    </div>
    <div class="history-search-controls">
      <input class="history-search-input" id="hist-q-${{date}}" value="${{st.q||''}}" placeholder="Pesquisar jogo, liga, mercado ou data..." oninput="runHistoricoSearch('${{date}}')">
      <select class="history-search-select" id="hist-status-${{date}}" onchange="runHistoricoSearch('${{date}}')">
        <option value="todos" ${{st.status==='todos'?'selected':''}}>Todos resultados</option>
        <option value="green" ${{st.status==='green'?'selected':''}}>Só Green</option>
        <option value="red" ${{st.status==='red'?'selected':''}}>Só Red</option>
        <option value="pendente" ${{st.status==='pendente'?'selected':''}}>Sem resultado</option>
      </select>
      <select class="history-search-select" id="hist-grade-${{date}}" onchange="runHistoricoSearch('${{date}}')">
        <option value="todos" ${{st.grade==='todos'?'selected':''}}>Todas grades</option>
        <option value="A+" ${{st.grade==='A+'?'selected':''}}>A+</option>
        <option value="A" ${{st.grade==='A'?'selected':''}}>A</option>
        <option value="B" ${{st.grade==='B'?'selected':''}}>B</option>
      </select>
      <select class="history-search-select" id="hist-mercado-${{date}}" onchange="runHistoricoSearch('${{date}}')">
        <option value="todos" ${{st.mercado==='todos'?'selected':''}}>Todos mercados</option>
        <option value="Over" ${{st.mercado==='Over'?'selected':''}}>Gols</option>
        <option value="Esc" ${{st.mercado==='Esc'?'selected':''}}>Escanteios</option>
        <option value="BTTS" ${{st.mercado==='BTTS'?'selected':''}}>BTTS</option>
        <option value="Under" ${{st.mercado==='Under'?'selected':''}}>Under</option>
      </select>
    </div>
    <div class="history-chip-row">
      <button class="history-chip" onclick="setHistoricoQuick('${{date}}','green')"><i data-lucide="circle-check"></i> Greens</button>
      <button class="history-chip" onclick="setHistoricoQuick('${{date}}','red')"><i data-lucide="circle-x"></i> Reds</button>
      <button class="history-chip" onclick="setHistoricoQuick('${{date}}','A+')">A+</button>
      <button class="history-chip" onclick="setHistoricoQuick('${{date}}','Esc')">Escanteios</button>
      <button class="history-chip" onclick="clearHistoricoSearch('${{date}}')">Limpar</button>
    </div>
    <div class="history-search-results" id="hist-results-${{date}}">
    </div>
  </div>`;
}}

function historicoAllRows(){{
  const rows = [];
  Object.keys(ALL_DATA).filter(d=>d!=='index').sort((a,b)=>{{
    const [da,ma,ya]=a.split('-').map(Number), [db,mb,yb]=b.split('-').map(Number);
    return new Date(yb,mb-1,db)-new Date(ya,ma-1,da);
  }}).forEach(date=>{{
    getJogos(date).forEach(j=>{{
      const mkt = getPalpiteMkt(j);
      const grade = getPalpiteGrade(j);
      const score = getPalpiteScore(j);
      const key = getPalpiteKey(j);
      const res = getResultado(j);
      const pick = normalizedPalpite(j);
      const ok = res ? primaryResultOk(j) : null;
      const status = ok===true ? 'green' : ok===false ? 'red' : 'pendente';
      const alternatives = approvedMarkets(j).map(x=>x.mkt).join(' ');
      rows.push({{date,j,mkt,grade,score,status,alternatives}});
    }});
  }});
  return rows;
}}

function runHistoricoSearch(date){{
  const qEl=document.getElementById('hist-q-'+date);
  const statusEl=document.getElementById('hist-status-'+date);
  const gradeEl=document.getElementById('hist-grade-'+date);
  const mercadoEl=document.getElementById('hist-mercado-'+date);
  const out=document.getElementById('hist-results-'+date);
  if(!out) return;
  const q=(qEl?.value||'').trim().toLowerCase();
  const status=statusEl?.value||'todos';
  const grade=gradeEl?.value||'todos';
  const mercado=mercadoEl?.value||'todos';
  historicoSearchState[date]={{q,status,grade,mercado}};
  const hasFilter = q || status!=='todos' || grade!=='todos' || mercado!=='todos';
  if(!hasFilter){{
    out.innerHTML='';
    return;
  }}
  const filtered = historicoAllRows().filter(r=>{{
    if(status!=='todos' && r.status!==status) return false;
    if(grade!=='todos' && r.grade!==grade) return false;
    if(mercado!=='todos' && !(`${{r.mkt}} ${{r.alternatives}}`.includes(mercado))) return false;
    if(q){{
      const hay = `${{r.date}} ${{r.j.jogo}} ${{r.j.liga}} ${{r.mkt}} ${{r.grade}} ${{r.alternatives}}`.toLowerCase();
      if(!hay.includes(q)) return false;
    }}
    return true;
  }}).sort((a,b)=>(b.score-a.score)).slice(0,80);
  if(!filtered.length){{
    out.innerHTML='<div class="history-search-empty">Nenhum resultado encontrado com esses filtros.</div>';
    return;
  }}
  const rows=filtered.map((r,i)=>{{
    const badge = r.status==='green' ? '<span class="res-badge hit"><i data-lucide="circle-check"></i> GREEN</span>' : r.status==='red' ? '<span class="res-badge miss"><i data-lucide="circle-x"></i> RED</span>' : '<span class="res-badge pending"><i data-lucide="clock"></i> S/D</span>';
    return `<tr class="${{r.status==='green'?'row-hit':r.status==='red'?'row-miss':''}}">
      <td class="row-num">${{i+1}}</td>
      <td><div class="jogo-main">${{r.j.jogo}}</div><div class="jogo-sub">${{leagueMetaHtml(r.j)}} · ${{r.j.hora}}</div></td>
      <td class="mono muted">${{r.date}}</td>
      <td>${{gradeHtml(r.grade)}}</td>
      <td class="td-palpite">${{r.mkt}}</td>
      <td class="mono" style="color:${{col(r.score)}};font-weight:700">${{pctText(r.score)}}</td>
      <td>${{badge}}</td>
    </tr>`;
  }}).join('');
  out.innerHTML=`<div class="tbl-wrap"><table>
    <thead><tr><th>#</th><th>Jogo</th><th>Data</th><th>Grade</th><th>Mercado</th><th>Score</th><th>Resultado</th></tr></thead>
    <tbody>${{rows}}</tbody>
  </table></div>`;
}}

function setHistoricoQuick(date,type){{
  const q=document.getElementById('hist-q-'+date);
  const status=document.getElementById('hist-status-'+date);
  const grade=document.getElementById('hist-grade-'+date);
  const mercado=document.getElementById('hist-mercado-'+date);
  if(type==='green' || type==='red') status.value=type;
  else if(type==='A+') grade.value='A+';
  else if(type==='Esc') mercado.value='Esc';
  if(q && !q.value) q.value='';
  runHistoricoSearch(date);
}}

function clearHistoricoSearch(date){{
  const q=document.getElementById('hist-q-'+date);
  const status=document.getElementById('hist-status-'+date);
  const grade=document.getElementById('hist-grade-'+date);
  const mercado=document.getElementById('hist-mercado-'+date);
  if(q) q.value='';
  if(status) status.value='todos';
  if(grade) grade.value='todos';
  if(mercado) mercado.value='todos';
  runHistoricoSearch(date);
}}

function renderGlobalHistoricoSearch(){{
  const box=document.getElementById('global-history-search');
  if(!box || box.dataset.ready==='1') return;
  box.innerHTML=historicoSearchHtml('global');
  box.dataset.ready='1';
  if(typeof ensureLucideIcons === 'function') ensureLucideIcons();
}}

function renderVisao(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-visao');
  const top=[...jogos].sort(sortByGrade).slice(0,5);
  const cls=['tc-aplus','tc-a','tc-b','tc-c','tc-d'];
  const t5=top.map((d,i)=>{{
    const c=col(getPalpiteScore(d));
    const overlay=cardOverlayClass(d);
    const status=topCardStatus(d);
    return`<div class="top-card ${{cls[i]}}${{overlay}}">
      <div class="top-rank-block"><div class="top-rank">#${{i+1}}</div><div class="top-status ${{status.cls}}">${{status.text}}</div></div>
      <div class="top-liga">${{leagueMetaHtml(d)}}</div>
      <div class="top-jogo">${{d.jogo}}${{d.is_elite?'<span class="elite">ELITE</span>':''}}</div>
      <div class="top-hora"><i data-lucide="clock"></i> ${{d.hora}}</div>
      <div class="top-mkt">${{getPalpiteMkt(d)}}</div>
      <div class="top-bottom">
        <div class="top-score" style="color:${{c}}">${{getPalpiteScore(d)}}%</div>
        <div class="top-grade-block">
          ${{gradeHtml(getPalpiteGrade(d))}}
          ${{oddMkt(d)!=='—'?`<span style="font-size:11px;color:var(--yellow);font-weight:800;margin-top:2px">Odd: ${{oddMkt(d)}}</span>`:''}}
        </div>
      </div>
      ${{primaryPlacarCard(d)}}
    </div>`;
  }}).join('');

  const rows=[...jogos].sort(sortByGrade).map((d,i)=>{{
    const rc=primaryRowClass(d);
    return`<tr class="${{rc}}">
      <td class="row-num">${{i+1}}</td>
      ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
      <td class="td-conf">${{gradeHtml(getPalpiteGrade(d))}}</td>
      <td class="td-palpite">${{getPalpiteMkt(d)}}</td>
      <td class="mono" style="color:${{col(getPalpiteScore(d))}};font-weight:700">${{pctText(getPalpiteScore(d))}}</td>
      ${{placarCell(d)}}
      <td>${{primaryResultBadge(d)}}</td>
    </tr>`;
  }}).join('');

  el.innerHTML=`
    <div class="sec-title"><i data-lucide="trophy"></i> Top 5 Palpites do Dia</div>
    <div class="top-grid">${{t5}}</div>
    <div class="sec-title"><i data-lucide="list"></i> Resumo Geral</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th style="color:var(--green)">Confiança</th><th style="color:var(--accent)">Melhor Palpite</th><th>Score</th><th>Placar</th><th>Resultado</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
}}

// ── Ranking ────────────────────────────────────────────────────────
function renderRanking(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-ranking');
  const snap=(ALL_DATA[date]||{{}}).palpites_snapshot||[];
  const fullById=new Map(jogos.filter(j=>j.fixture_id).map(j=>[String(j.fixture_id),j]));
  const fullByName=new Map(jogos.map(j=>[`${{j.home}} x ${{j.away}}`,j]));
  const enrichSnap = item => {{
    const full = (item.fixture_id && fullById.get(String(item.fixture_id))) || fullByName.get(`${{item.home}} x ${{item.away}}`) || {{}};
    return {{...item, ...full}};
  }};
  const base=jogos.length?jogos:(snap.length?snap.map(enrichSnap):[]);
  const sorted=[...base].sort(sortByGrade);
  const groups=[
    {{title:'Confian&ccedil;a Alta / M&eacute;dia', icon:'star', items:sorted.filter(d=>getPalpiteGrade(d)==='A+'||getPalpiteGrade(d)==='A')}},
    {{title:'Moderado', icon:'target', items:sorted.filter(d=>getPalpiteGrade(d)==='B')}},
    {{title:'Arriscado / Evitar', icon:'shield-check', items:sorted.filter(d=>getPalpiteGrade(d)==='C'||getPalpiteGrade(d)==='D')}}
  ];

  function tableFor(group){{
    const title = `<div class="sec-title"><i data-lucide="${{group.icon}}"></i> ${{group.title}}</div>`;
    if(!group.items.length)return`<div class="ranking-col">${{title}}<div class="empty">Nenhum jogo nesta categoria.</div></div>`;
    const rows=group.items.map((d,i)=>{{
      const rc=primaryRowClass(d);
      return`<tr class="${{rc}}">
        <td class="row-num">${{i+1}}</td>
        ${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td>${{gradeHtml(getPalpiteGrade(d))}}</td>
        <td class="td-palpite">${{getPalpiteMkt(d)}}</td>
        <td class="mono" style="color:${{col(getPalpiteScore(d))}};font-weight:700">${{pctText(getPalpiteScore(d))}}</td>
        <td class="alt-cell">${{approvedMarketsHtml(d, {{label:false, max:3, empty:true}})}}</td>
        ${{placarCell(d)}}
        <td>${{primaryResultBadge(d)}}</td>
      </tr>`;
    }}).join('');
    return`<div class="ranking-col">
      ${{title}}
      <div class="tbl-wrap"><table>
        <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Confian&ccedil;a</th><th>Melhor</th><th>Score</th><th>Alternativas</th><th>Placar</th><th>Resultado</th></tr></thead>
        <tbody>${{rows}}</tbody>
      </table></div>
    </div>`;
  }}

  el.innerHTML=`<div class="ranking-stack">${{groups.map(tableFor).join('')}}</div>`;
}}

// ── Resultado Final ────────────────────────────────────────────────
function renderResultadoFinal(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-resultado');
  const dayRows=rfRowsForDate(date).map(x=>({{date,j:x.j,p:x.p,result:rfResult(x.j,x.p)}}));
  const analysisRows=getJogos(date).map(j=>({{date,j,a:rfVisualAnalysis(rfAnalysis(j))}}));
  const approvedAnalysis=analysisRows.filter(r=>r.a.approved);
  const rejectedAnalysis=analysisRows.filter(r=>!r.a.approved);
  const histRows=rfHistoricoRows();
  const hist=rfSummary(histRows.filter(r=>r.result!=='PENDING'));
  const day=rfSummary(dayRows);
  const byMarket=['win','dc'].map(m=>{{
    const rows=histRows.filter(r=>r.p.market===m&&r.result!=='PENDING');
    return {{m,...rfSummary(rows)}};
  }});
  const mLabel={{win:'Vitória seca',dc:'Dupla Chance'}};
  // Taxa do dia
  const _taxaDia = day.green+day.red>0 ? Math.round(day.green/(day.green+day.red)*100) : null;
  const _taxaDiaColor = _taxaDia==null?'var(--muted)':_taxaDia>=70?'var(--green)':_taxaDia>=50?'var(--orange)':'var(--red)';
  const taxaDiaHtml = _taxaDia!=null ? `<div style="width:1px;height:24px;background:var(--border)"></div>
      <div style="display:flex;align-items:center;gap:8px">
        <i data-lucide="target" style="width:14px;height:14px;color:${{_taxaDiaColor}}"></i>
        <span style="font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.8px">Acerto do dia</span>
        <span style="font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:${{_taxaDiaColor}}">${{_taxaDia}}%</span>
      </div>` : '';
  const marketCards=byMarket.map(x=>`<div class="rf-card">
    <span><i data-lucide="${{x.m==='win'?'trophy':'shield'}}"></i>${{mLabel[x.m]}}</span>
    <strong>${{rfTaxaText(x.taxa)}}</strong>
    <em>${{x.green}} green · ${{x.red}} red · ${{x.gerados}} gerados</em>
  </div>`).join('');
  const approvedRowsHtml=approvedAnalysis.map((r,i)=>{{
    const p=r.a.p;
    const res=getResultado(r.j);
    const placar=res?`${{res.gols_home}}-${{res.gols_away}}`:'—';
    const result=rfResult(r.j,p);
    const cls=result==='GREEN'?'row-hit':result==='RED'?'row-miss':'row-pending';
    return`<tr class="${{cls}}">
      <td class="row-num">${{i+1}}</td>
      ${{jogoCell(r.j)}}
      <td class="mono muted">${{r.j.hora||'—'}}</td>
      <td><span class="rf-market ${{p.market}}">${{rfMarketLabel(p)}}</span></td>
      <td class="rf-score" style="color:${{col(p.score)}}">${{pctText(p.score)}}</td>
      <td>${{gradeHtml(p.grade)}}</td>
      <td class="mono muted">${{rfNum(r.j,'odds_h')?Number(rfNum(r.j,'odds_h')).toFixed(2):'—'}} x ${{rfNum(r.j,'odds_a')?Number(rfNum(r.j,'odds_a')).toFixed(2):'—'}}</td>
      <td class="mono">${{placar}}</td>
      <td>${{rfBadge(result)}}</td>
      <td><div class="rf-reasons">${{p.reasons.join(' · ')}}</div></td>
    </tr>`;
  }}).join('');
  const rejectedRowsHtml=rejectedAnalysis.map((r,i)=>{{
    const a=r.a;
    const res=getResultado(r.j);
    const placar=res?`${{res.gols_home}}-${{res.gols_away}}`:'—';
    const displayPick=a.market?{{...a,market:a.market}}:(a.side?{{...a,market:'win'}}:null);
    const resultPick=rfVisualPick(displayPick);
    const rejectedResult=resultPick?rfResult(r.j,resultPick):'PENDING';
    const rejectedStatus=rfBadge(rejectedResult);
    const rejectedCls=rejectedResult==='GREEN'?'row-hit':rejectedResult==='RED'?'row-miss':'row-pending';
    return`<tr class="${{rejectedCls}}">
      <td class="row-num">${{i+1}}</td>
      ${{jogoCell(r.j)}}
      <td class="mono muted">${{r.j.hora||'—'}}</td>
      <td>${{displayPick?`<span class="rf-market ${{displayPick.market}}">${{rfMarketLabel(displayPick)}}</span>`:'<span class="mono muted">Sem favorito</span>'}}</td>
      <td class="rf-score" style="color:${{col(a.score||0)}}">${{a.score!=null?pctText(a.score):'—'}}</td>
      <td>${{a.grade?gradeHtml(a.grade):'<span class="mono muted">—</span>'}}</td>
      <td class="mono muted">${{rfNum(r.j,'odds_h')?Number(rfNum(r.j,'odds_h')).toFixed(2):'—'}} x ${{rfNum(r.j,'odds_a')?Number(rfNum(r.j,'odds_a')).toFixed(2):'—'}}</td>
      <td class="mono">${{placar}}</td>
      <td>${{rejectedStatus}}</td>
      <td><div class="rf-reasons"><strong>${{a.stage}}:</strong> ${{a.reason}}${{a.reasons&&a.reasons.length?` · ${{a.reasons.join(' · ')}}`:''}}</div></td>
    </tr>`;
  }}).join('');

  el.innerHTML=`
    
    <div style="display:flex;align-items:center;gap:20px;padding:10px 0;margin-bottom:4px;flex-wrap:wrap;justify-content:center">
      <div style="display:flex;align-items:center;gap:8px">
        <i data-lucide="activity" style="width:14px;height:14px;color:var(--green)"></i>
        <span style="font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.8px">Taxa histórica</span>
        <span style="font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:var(--green)">${{rfTaxaText(hist.taxa)}}</span>
        <span style="font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace">${{hist.green}}✓ ${{hist.red}}✗ / ${{hist.gerados}}</span>
      </div>
      <div style="width:1px;height:24px;background:var(--border)"></div>
      <div style="display:flex;align-items:center;gap:8px">
        <i data-lucide="calendar-days" style="width:14px;height:14px;color:var(--blue)"></i>
        <span style="font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.8px">Analisados</span>
        <span style="font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;color:var(--blue)">${{analysisRows.length}}</span>
        <span style="font-size:11px;color:var(--muted);font-family:'JetBrains Mono',monospace">${{approvedAnalysis.length}} aprovados · ${{rejectedAnalysis.length}} reprovados</span>
      </div>
      ${{taxaDiaHtml}}
    </div>
    <div class="sec-title"><i data-lucide="shield-check"></i> Aprovado pelo filtro</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Mercado</th><th>Score</th><th>Confiança</th><th>Odds</th><th>Placar</th><th>Resultado</th><th>Motivos</th></tr></thead>
      <tbody>${{approvedRowsHtml||'<tr><td colspan="10" class="empty">Nenhum palpite de Resultado Final aprovado para esta data.</td></tr>'}}</tbody>
    </table></div>
    <div class="sec-title" style="margin-top:14px"><i data-lucide="filter-x"></i> Reprovado pelo filtro</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Mercado</th><th>Score</th><th>Confiança</th><th>Odds</th><th>Placar</th><th>Resultado</th><th>Motivo técnico</th></tr></thead>
      <tbody>${{rejectedRowsHtml||'<tr><td colspan="10" class="empty">Nenhum jogo reprovado pelo filtro nesta data.</td></tr>'}}</tbody>
    </table></div>`;
  ensureLucideIcons();
}}

// ── Over 1.5 ───────────────────────────────────────────────────────
function renderOver15(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over15');
  let rows=[...jogos].filter(d=>d.passou_filtro).sort((a,b)=>sortByGrade(a,b,d=>d.grade_15||getPalpiteGrade(d),d=>d.score_15));
  const html=rows.map((d,i)=>{{
    const rc=rowClass(d,'over15_ok');
    const prob = d.over15_g ?? d.score_15;
    const oddOver15 = d.odds_o15 || d.odd_over15 || d.odd_justa_15 || (prob ? 100 / prob : null);
    const probColor=prob>=85?'var(--green)':prob>=75?'var(--blue)':'var(--orange)';
    const scoreColor=col(d.score_15||0);
    return`<tr class="${{rc}}">
      <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
      <td class="mono muted">${{d.hora}}</td>
      <td class="mono" style="color:var(--blue)">${{d.exg_tot||'—'}}</td>
      <td><span class="metric-value em" style="color:${{probColor}}">${{prob!=null?Number(prob).toFixed(1):'—'}}%</span></td>
      <td class="mono" style="color:var(--yellow);font-weight:800;font-size:13px">${{odd(oddOver15)}}</td>
      <td>${{gradeHtml(d.grade_15)}}</td>
      <td class="mono" style="color:${{scoreColor}};font-weight:800">${{d.score_15!=null?Number(d.score_15).toFixed(1)+'%':'—'}}</td>
      ${{placarCell(d)}}
      <td>${{resBadge(d,'over15_ok')}}</td>
      <td>${{via(d.via)}}</td>
    </tr>`;
  }}).join('');
  el.innerHTML=`
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>xG</th><th style="color:var(--green)">Probabilidade</th><th style="color:var(--yellow)">ODD</th><th>Confiança</th><th>Score</th><th>Placar</th><th>Resultado</th><th>Via</th></tr></thead>
      <tbody>${{html||'<tr><td colspan="11" class="empty">Nenhum jogo passou o Filtro 3 Vias.</td></tr>'}}</tbody>
    </table></div>`;
}}

// ── Under 4.5 ────────────────────────────────────────────────────
function renderOver25(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-over25');
  const underRows=[...jogos]
    .map(d=>{{
      const picked = underMarketPick(d);
      if(picked) return {{jogo:d, under:picked}};
      const mkt = getPalpiteMkt(d);
      if(mkt==='Under 3.5' || mkt==='Under 4.5'){{
        return {{jogo:d, under:{{
          mkt,
          key:MKT_RESULT[mkt],
          score:getPalpiteScore(d),
          grade:getPalpiteGrade(d),
          poisson:mkt==='Under 3.5'?d.poisson_u35:d.poisson_u45,
          exg:d.exg_tot,
        }}}};
      }}
      return {{jogo:d, under:null}};
    }})
    .filter(x=>x.under)
    .sort((a,b)=>sortByGrade(a.jogo,b.jogo,d=>underMarketPick(d)?.grade||'D',d=>underMarketPick(d)?.score||0));
  el.innerHTML=`
    <div class="tbl-wrap"><table>
      <thead><tr>
        <th>#</th><th>Jogo</th><th>Hora</th><th>Mercado</th>
        <th style="color:var(--purple)">Poisson</th>
        <th style="color:var(--teal)">xG Total</th>
        <th>Placar</th><th>Resultado</th>
        <th>Score</th><th>Confiança</th>
      </tr></thead>
      <tbody>${{underRows.length ? underRows.map((x,i)=>{{
        const d=x.jogo;
        const u=x.under;
        const probColor=u.poisson>=85?'var(--green)':u.poisson>=75?'var(--blue)':'var(--muted)';
        const rc=rowClass(d,u.key);
        return`<tr class="${{rc}}">
          <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
          <td class="mono muted">${{d.hora}}</td>
          <td><span class="badge version">${{u.mkt}}</span></td>
          <td><span class="metric-value em" style="color:${{probColor}}">${{u.poisson?u.poisson+'%':'—'}}</span></td>
          <td class="mono" style="color:var(--teal);font-size:13px;font-weight:800">${{u.exg||'—'}}</td>
          ${{placarCell(d)}}<td>${{resBadge(d,u.key)}}</td>
          <td>${{bar(u.score)}}</td>
          <td>${{gradeHtml(u.grade)}}</td>
        </tr>`;
      }}).join('') : '<tr><td colspan="10" class="empty">Nenhum jogo passou nos filtros Under hoje.</td></tr>'}}</tbody>
    </table></div>`;
}}

// ── Escanteios ─────────────────────────────────────────────────────
const CORNER_LINES=[
  {{label:'Over 6.5',field:'over65_c',line:6.5}},
  {{label:'Over 7.5',field:'over75_c',line:7.5}},
  {{label:'Over 8.5',field:'over85_c',line:8.5}},
  {{label:'Over 9.5',field:'over95_c',line:9.5}},
  {{label:'Over 10.5',field:'over105_c',line:10.5}}
];
function cornerStatsForGames(games){{
  const byLine=CORNER_LINES.map(l=>({{...l,total:0,green:0,red:0,rate:null}}));
  const gameIds=new Set();
  (games||[]).forEach((d,idx)=>{{
    const res=getResultado(d);
    const totalCorners=res&&Number(res.corners_total);
    if(!Number.isFinite(totalCorners))return;
    let used=false;
    byLine.forEach(s=>{{
      if(d[s.field]==null||!Number.isFinite(Number(d[s.field])))return;
      s.total++;
      if(totalCorners>s.line)s.green++;else s.red++;
      used=true;
    }});
    if(used)gameIds.add(d.fixture_id||d.jogo||idx);
  }});
  byLine.forEach(s=>{{s.rate=s.total?Math.round((s.green/s.total)*1000)/10:null;}});
  const best=byLine.filter(s=>s.total>0).sort((a,b)=>(b.rate??-1)-(a.rate??-1)||b.total-a.total||a.line-b.line)[0]||null;
  return{{games:gameIds.size,lines:byLine,best}};
}}
function isUsableCornerValue(v){{
  if(v==null||v==='')return false;
  const n=Number(v);
  return Number.isFinite(n);
}}
function hasCompleteCornerData(d){{
  const vals=CORNER_LINES.map(l=>Number(d[l.field]));
  return CORNER_LINES.every(l=>isUsableCornerValue(d[l.field]))&&vals.some(v=>v>0);
}}
function allCornerGames(){{
  return Object.values(ALL_DATA).flatMap(day=>(day&&day.resultado_confirmado&&Array.isArray(day.jogos))?day.jogos.filter(hasCompleteCornerData):[]);
}}
function cornerSummaryCards(dayStats,globalStats){{
  const val=s=>s?`${{s.rate}}%`:'—';
  const sub=s=>s?`${{s.green}}/${{s.total}} greens`:'Sem resultados';
  return`<div class="corner-summary-grid">
    <div class="corner-summary-card"><div class="corner-summary-label">Jogos analisados dia</div><div class="corner-summary-value">${{dayStats.games}}</div><div class="corner-summary-sub">Com resultado de escanteios</div></div>
    <div class="corner-summary-card"><div class="corner-summary-label">Melhor linha dia</div><div class="corner-summary-value">${{dayStats.best?dayStats.best.label:'—'}}</div><div class="corner-summary-sub">${{sub(dayStats.best)}}</div></div>
    <div class="corner-summary-card"><div class="corner-summary-label">Melhor % dia</div><div class="corner-summary-value">${{val(dayStats.best)}}</div><div class="corner-summary-sub">Linha mais assertiva</div></div>
    <div class="corner-summary-card"><div class="corner-summary-label">Jogos analisados geral</div><div class="corner-summary-value">${{globalStats.games}}</div><div class="corner-summary-sub">Período finalizado</div></div>
    <div class="corner-summary-card"><div class="corner-summary-label">Melhor linha geral</div><div class="corner-summary-value">${{globalStats.best?globalStats.best.label:'—'}}</div><div class="corner-summary-sub">${{sub(globalStats.best)}}</div></div>
    <div class="corner-summary-card"><div class="corner-summary-label">Melhor % geral</div><div class="corner-summary-value">${{val(globalStats.best)}}</div><div class="corner-summary-sub">Todo o histórico</div></div>
  </div>`;
}}
function renderEsc(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-escanteios');
  if(!el)return;
  const cornerJogos=[...jogos].filter(hasCompleteCornerData);
  const r75=[...cornerJogos].sort((a,b)=>sortByGrade(a,b,d=>d.grade_esc75||getPalpiteGrade(d),d=>d.score_esc75));
  const dayStats=cornerStatsForGames(cornerJogos);
  const globalStats=cornerStatsForGames(allCornerGames());
  function escRows(rows){{
    const html = rows.slice(0,15).map((d,i)=>{{
      const res=getResultado(d);
      const cantReal=res&&res.corners_total!=null?`<td><span class="corner-real">${{res.corners_total}}</span></td>`:'<td class="mono muted">--</td>';
      return`<tr class="${{cornerBestRowClass(d)}}">
        <td class="mono muted">${{i+1}}</td>${{jogoCell(d)}}
        <td class="mono muted">${{d.hora}}</td>
        <td class="corner-confidence">${{confHtml(d.score_esc75)}}</td>
        ${{cornerOverCell(d.over65_c,d,6.5)}}
        ${{cornerOverCell(d.over75_c,d,7.5)}}
        ${{cornerOverCell(d.over85_c,d,8.5)}}
        ${{cornerOverCell(d.over95_c,d,9.5)}}
        ${{cornerOverCell(d.over105_c,d,10.5)}}
        ${{cantReal}}
      </tr>`;
    }}).join('');
    return html || '<tr><td colspan="10" class="empty">Nenhum jogo com dados úteis de escanteios nesta data.</td></tr>';
  }}
  el.innerHTML=`
    ${{cornerSummaryCards(dayStats,globalStats)}}
    <div class="tbl-wrap corner-table-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Confiança</th><th>Over 6.5 FT</th><th>Over 7.5 FT</th><th>Over 8.5 FT</th><th>Over 9.5 FT</th><th>Over 10.5 FT</th><th>Resultado Real</th></tr></thead>
      <tbody>${{escRows(r75)}}</tbody></table></div>`;
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

  // Bilhete 1 — Premium: até 4 seleções A+/A por score
  const b1 = montar([...altaConf].slice(0,4));

  // Bilhete 2 — Só A+: filtro mais restrito
  const somenteAplus = altaConf.filter(x=>x.grade==='A+');
  const b2 = somenteAplus.length>=2 ? montar(somenteAplus) : null;

  const bilhetes = [];
  const seen = new Set();
  const defs = [
    ['b1', b1, 'bilhete-premium',     'PREMIUM 4X'],
    ['b2', b2, 'bilhete-conservador', 'ELITE'],
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

function gerarBingoBilhetes(jogos){{
  const maxSels = 8;
  const maxJogos = 5;
  const linhaMaiorMinDiff = 8;
  const calcOdd = (sels)=>Math.round(sels.reduce((acc,s)=>acc*(s.oddVal||1),1)*100)/100;
  const countJogos = (sels)=>new Set(sels.map(s=>s.jogo)).size;
  const pickLinhaSegura = (aprovados, segura, maior)=>{{
    const s = aprovados.find(x=>x.mkt===segura);
    const m = aprovados.find(x=>x.mkt===maior);
    if(s && m) return (m.score - s.score) >= linhaMaiorMinDiff ? m : s;
    return s || m || null;
  }};
  const makeSel = (j,x)=>{{
    const odd = oddForMarketDetail(j,x.mkt);
    return {{
      jogo:j.jogo, liga:j.liga, hora:j.hora,
      mkt:x.mkt, score:x.score, grade:x.grade,
      oddVal:odd?odd.value:null, oddSource:odd?odd.source:null,
      resultado:j.resultado, acertos:j.acertos||{{}},
    }};
  }};
  const combos = jogos.map(j=>{{
    const aprovados = approvedMarkets(j);
    const gols = pickLinhaSegura(aprovados, 'Over 1.5', 'Over 2.5');
    const canto = pickLinhaSegura(aprovados, 'Esc 7.5', 'Esc 8.5');
    if(!gols || !canto) return null;
    const sels = [makeSel(j,gols), makeSel(j,canto)];
    const scoreMedio = Math.round(sels.reduce((a,s)=>a+(s.score||0),0)/sels.length);
    return {{
      jogo:j.jogo,
      sels,
      oddTotal:calcOdd(sels),
      scoreMedio,
    }};
  }}).filter(Boolean)
    .sort((a,b)=>(b.scoreMedio-a.scoreMedio)||((b.oddTotal||1)-(a.oddTotal||1)));
  const sels = [];
  for(const combo of combos){{
    if(sels.length+combo.sels.length>maxSels) break;
    const next = [...sels, ...combo.sels];
    if(countJogos(next)>maxJogos) break;
    sels.push(...combo.sels);
    if(calcOdd(sels)>=5) break;
  }}
  const seen = new Set(sels.map(s=>s.jogo+'|'+s.mkt));
  const aplus = jogos.map(j=>{{
    const mkt = getPalpiteMkt(j);
    const grade = j.palpite_grade || j.best_grade;
    const score = j.palpite_score ?? j.best_score;
    if(grade!=='A+' || !mkt || !score) return null;
    const item = makeSel(j,{{mkt, score, grade}});
    const key = item.jogo+'|'+item.mkt;
    if(seen.has(key)) return null;
    return item;
  }}).filter(Boolean)
    .sort((a,b)=>(b.score-a.score)||((b.oddVal||1)-(a.oddVal||1)));
  for(const item of aplus){{
    if(calcOdd(sels)>=5 || sels.length>=maxSels) break;
    const next = [...sels, item];
    if(countJogos(next)>maxJogos) continue;
    sels.push(item);
    seen.add(item.jogo+'|'+item.mkt);
  }}
  if(!sels.length) return [];
  const oddTotal = calcOdd(sels);
  const scoreMedio = Math.round(sels.reduce((a,s)=>a+(s.score||0),0)/sels.length);
  const tier = oddTotal>=5 ? 'OURO' : oddTotal>=3 ? 'PRATA' : 'FORTE';
  return [{{
    tipo:'bingo',
    b:{{sels, oddTotal, tier}},
    cls:'bilhete-bingo',
    label:`<i data-lucide="crosshair"></i>BINGO DO DIA`,
    scoreMedio,
  }}];
}}
function avaliarBilhete(sels, confirmado){{
  if(!confirmado) return {{status:'pending', acertos:0, total:sels.length}};
  let acertos=0, erros=0, sd=0;
  for(const s of sels){{
    const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
    const res = s.resultado;
    if(!res){{ sd++; continue; }}
    const ok = resultOk(res,mktKey);
    if(ok===true) acertos++;
    else if(ok===false) erros++;
    else sd++;
  }}
  if(erros>0) return {{status:'loss', acertos, erros, sd, total:sels.length}};
  if(sd>0) return {{status:'partial', acertos, erros, sd, total:sels.length}};
  return {{status:'win', acertos, erros:0, sd:0, total:sels.length}};
}}

// ── Bilhetes helpers ──────────────────────────────────────────────
function oddText(s){{
  if(!s.oddVal) return '—';
  return parseFloat(s.oddVal).toFixed(2);
}}

function renderSelectionStatus(s){{
  const res = s.resultado;
  if(!res) return '<span class="res-badge pending">⏳ Aguardando</span>';
  const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
  const ok = resultOk(res, mktKey);
  if(ok===true) return '<span class="res-badge hit">✓ GREEN</span>';
  if(ok===false) return '<span class="res-badge miss">✗ RED</span>';
  return '<span class="res-badge pending">⚠ Não confirmado</span>';
}}

function renderBilhetes(date, jogos){{
  const el = document.getElementById('mkt-'+date+'-bilhetes');
  const confirmado = isConfirmado(date);
  const snap=(ALL_DATA[date]||{{}}).bilhetes_snapshot;
  const resultado = snap || gerarBilhetes(jogos);
  const {{bilhetes, bilheteDia}} = resultado;
  const jogosByKey = new Map(jogos.map(j=>[`${{j.fixture_id||''}}|${{j.jogo}}`, j]));
  const findJogo = (s)=>jogosByKey.get(`${{s.fixture_id||''}}|${{s.jogo}}`) || jogos.find(j=>j.jogo===s.jogo);
  const hydrateSel = (s)=>{{
    if(s.oddVal) return s;
    const jogo = findJogo(s);
    if(!jogo) return s;
    const odd = oddForMarketDetail(jogo, s.mkt);
    return odd ? {{...s, oddVal:odd.value, oddSource:odd.source}} : s;
  }};
  const hydrateBilhete = (b)=>{{
    if(!b || !b.sels) return b;
    const sels = b.sels.map(hydrateSel);
    const oddTotal = Math.round(sels.reduce((acc,s)=>acc*(s.oddVal||1),1)*100)/100;
    return {{...b, sels, oddTotal}};
  }};
  const bilhetesHydrated = (bilhetes||[]).map(item=>({{...item, b:hydrateBilhete(item.b)}}));
  const bilheteDiaHydrated = hydrateBilhete(bilheteDia);
  const bingoBilhetes = gerarBingoBilhetes(jogos);
  const bingoDestaque = bingoBilhetes[0] || null;
  const todosBilhetes = [...bilhetesHydrated, ...bingoBilhetes.slice(1)];

  if((!todosBilhetes || todosBilhetes.length===0) && !bilheteDiaHydrated && !bingoDestaque){{
    el.innerHTML=`<div class="empty">Nenhum jogo com dados suficientes para gerar bilhetes hoje.</div>`;
    return;
  }}

  // Bilhete do Dia
  let diaHtml = '';
  if(bilheteDiaHydrated){{
    const av = avaliarBilhete(bilheteDiaHydrated.sels, confirmado);
    const overlayClass = av.status==='win'?' bilhete-win':av.status==='loss'?' bilhete-loss':'';
    const oddColor = !bilheteDiaHydrated.oddTotal?'var(--muted)':bilheteDiaHydrated.oddTotal>=5?'var(--green)':bilheteDiaHydrated.oddTotal>=3?'var(--yellow)':'var(--orange)';
    const scoreMedia = Math.round(bilheteDiaHydrated.sels.reduce((a,s)=>a+s.score,0)/bilheteDiaHydrated.sels.length);
    const diaHeader = `<div class="bilhete-row" style="border-bottom:1px solid rgba(0,200,150,.2);margin-bottom:4px;padding-bottom:6px">
      <span class="bilhete-num" style="color:var(--muted);font-size:9px">#</span>
      <div style="flex:1;min-width:0"><span style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Jogo</span></div>
      <span class="bilhete-mkt" style="font-size:9px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.7px">Mercado</span>
      <div class="bilhete-score-bar" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Confiança</div>
      <span class="bilhete-odd-val" style="font-size:9px;font-weight:700;color:var(--yellow);text-transform:uppercase;letter-spacing:.7px">Odd</span>
      <div class="bilhete-res" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Resultado</div>
    </div>`;
    const rows = bilheteDiaHydrated.sels.map((s,i)=>{{
      const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
      const res = s.resultado;
      let resHtml = '<span class="res-badge pending"><i data-lucide="clock"></i></span>';
      if(confirmado && res){{
        const ok = resultOk(res,mktKey);
        if(ok===true) resHtml='<span class="res-badge hit"><i data-lucide="circle-check"></i> GREEN</span>';
        else if(ok===false) resHtml='<span class="res-badge miss"><i data-lucide="circle-x"></i> RED</span>';
        else resHtml='<span class="res-badge pending"><i data-lucide="triangle-alert"></i> Não confirmado</span>';
      }}
      return`<div class="bilhete-row">
        <span class="bilhete-num">${{i+1}}</span>
        <div style="flex:1;min-width:0"><div class="bilhete-jogo">${{s.jogo}}</div><div class="bilhete-liga">${{leagueMetaHtml(s)}} · ${{s.hora}}</div></div>
        <span class="bilhete-mkt">${{s.mkt}}</span>
        <div class="bilhete-score-bar">${{bar(s.score,60)}}</div>
        <span class="bilhete-odd-val">${{s.oddVal?s.oddVal.toFixed(2):'—'}}</span>
        <div class="bilhete-res">${{resHtml}}</div>
      </div>`;
    }}).join('');
    let statusHtml = '';
    if(!confirmado) statusHtml='<span class="bilhete-status" style="color:var(--muted)"><i data-lucide="clock"></i> Aguardando</span>';
    else if(av.status==='win') statusHtml=`<span class="bilhete-status" style="color:var(--green)"><i data-lucide="circle-check"></i> GREEN! Odd: ${{bilheteDiaHydrated.oddTotal.toFixed(2)}}</span>`;
    else if(av.status==='loss') statusHtml=`<span class="bilhete-status" style="color:var(--red)"><i data-lucide="circle-x"></i> Perdeu (${{av.erros}} erro${{av.erros>1?'s':''}})</span>`;
    else statusHtml=`<span class="bilhete-status" style="color:var(--yellow)"><i data-lucide="triangle-alert"></i> Parcial — ${{av.sd}} sem dados</span>`;

    diaHtml=`<div class="bilhete-dia${{overlayClass}}">
      <div class="bilhete-dia-badge"><i data-lucide="trophy"></i>BILHETE DO DIA</div>
      <div class="bilhete-header">
        <div><div class="bilhete-title" style="font-size:15px">Os mais assertivos do dia</div>
        <div style="font-size:10px;color:var(--muted);margin-top:2px">${{bilheteDiaHydrated.sels.length}} seleções · Score médio ${{scoreMedia}}%</div></div>
        <div style="text-align:right">
          <div class="bilhete-odd-total" style="color:${{oddColor}}">${{bilheteDiaHydrated.oddTotal?bilheteDiaHydrated.oddTotal.toFixed(2):'—'}}</div>
          <div class="bilhete-odd-label">Odd combinada</div>
        </div>
      </div>
      <div style="border-top:1px solid rgba(0,200,150,.2);padding-top:10px">${{diaHeader}}${{rows}}</div>
      <div class="bilhete-footer"><span class="bilhete-sels">${{bilheteDiaHydrated.sels.filter(s=>s.grade==='A+').length}} A+ · ${{bilheteDiaHydrated.sels.filter(s=>s.grade==='A').length}} A</span>${{statusHtml}}</div>
    </div>`;
  }}

  const renderBilheteCard = (item)=>{{ const {{tipo, b, cls, label}} = item;
    const av = avaliarBilhete(b.sels, confirmado);
    const overlayClass = av.status==='win'?' bilhete-win':av.status==='loss'?' bilhete-loss':'';
    const oddColor = b.oddTotal >= 5 ? 'var(--green)' : b.oddTotal >= 3 ? 'var(--yellow)' : 'var(--orange)';

    const isBingo = tipo === 'bingo';
    const oddText = (s)=>s.oddVal ? s.oddVal.toFixed(2) : '—';
    const tierLabel = isBingo && b.tier ? ` · ${{b.tier==='OURO'?'Bingo Ouro':b.tier==='PRATA'?'Bingo Prata':'Bingo Forte'}}` : '';
    const bilheteHeader = isBingo ? `<div class="bilhete-row" style="border-bottom:1px solid var(--border);margin-bottom:4px;padding-bottom:6px">
      <span class="bilhete-num" style="color:var(--muted);font-size:9px">#</span>
      <div style="flex:1;min-width:0"><span style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Jogo</span></div>
      <div class="bilhete-market-stack" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Mercados</div>
      <div class="bilhete-res" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Resultado</div>
    </div>` : `<div class="bilhete-row" style="border-bottom:1px solid var(--border);margin-bottom:4px;padding-bottom:6px">
      <span class="bilhete-num" style="color:var(--muted);font-size:9px">#</span>
      <div style="flex:1;min-width:0"><span style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Jogo</span></div>
      <span class="bilhete-mkt" style="font-size:9px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.7px">Mercado</span>
      <div class="bilhete-score-bar" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Confiança</div>
      <span class="bilhete-odd-val" style="font-size:9px;font-weight:700;color:var(--yellow);text-transform:uppercase;letter-spacing:.7px">Odd</span>
      <div class="bilhete-res" style="font-size:9px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.7px">Resultado</div>
    </div>`;

    const renderSelectionStatus = (s) => {{
      const mktKey = MKT_RESULT[s.mkt]||'over15_ok';
      const res = s.resultado;
      let resHtml = '<span class="res-badge pending"><i data-lucide="clock"></i></span>';
      if(confirmado && res){{
        const ok = resultOk(res,mktKey);
        if(ok===true) resHtml='<span class="res-badge hit"><i data-lucide="circle-check"></i> GREEN</span>';
        else if(ok===false) resHtml='<span class="res-badge miss"><i data-lucide="circle-x"></i> RED</span>';
        else resHtml='<span class="res-badge pending"><i data-lucide="triangle-alert"></i> Não confirmado</span>';
      }}
      return resHtml;
    }};

    const rows = isBingo ? (()=>{{
      const groups = [];
      const byJogo = new Map();
      for(const s of b.sels){{
        const key = `${{s.jogo}}|${{s.hora}}`;
        if(!byJogo.has(key)){{
          byJogo.set(key, {{jogo:s.jogo, liga:s.liga, country:s.country, hora:s.hora, sels:[]}});
          groups.push(byJogo.get(key));
        }}
        byJogo.get(key).sels.push(s);
      }}
      return groups.map((g,i)=>{{
        const marketLines = g.sels.map(s=>`<div class="bilhete-market-line">
          <span class="bilhete-mkt">${{s.mkt}}</span>
          <div class="bilhete-score-bar">${{bar(s.score||0,60)}}</div>
          <span class="bilhete-odd-val">${{oddText(s)}}</span>
        </div>`).join('');
        const statuses = g.sels.map(renderSelectionStatus).join('<div style="height:4px"></div>');
        return`<div class="bilhete-row">
          <span class="bilhete-num">${{i+1}}</span>
          <div style="flex:1;min-width:0">
            <div class="bilhete-jogo">${{g.jogo}}</div>
            <div class="bilhete-liga">${{leagueMetaHtml(g)}} · ${{g.hora}}</div>
          </div>
          <div class="bilhete-market-stack">${{marketLines}}</div>
          <div class="bilhete-res">${{statuses}}</div>
        </div>`;
      }}).join('');
    }})() : b.sels.map((s,i)=>{{
      const resHtml = renderSelectionStatus(s);
      const scoreVal = s.score || 0;
      return`<div class="bilhete-row">
        <span class="bilhete-num">${{i+1}}</span>
        <div style="flex:1;min-width:0">
          <div class="bilhete-jogo">${{s.jogo}}</div>
          <div class="bilhete-liga">${{leagueMetaHtml(s)}} · ${{s.hora}}</div>
        </div>
        <span class="bilhete-mkt">${{s.mkt}}</span>
        <div class="bilhete-score-bar">${{bar(scoreVal,60)}}</div>
        <span class="bilhete-odd-val">${{oddText(s)}}</span>
        <div class="bilhete-res">${{resHtml}}</div>
      </div>`;
    }}).join('');

    let statusHtml = '';
    if(!confirmado){{
      statusHtml = '<span class="bilhete-status" style="color:var(--muted)"><i data-lucide="clock"></i> Aguardando resultados</span>';
    }} else if(av.status==='win'){{
      statusHtml = `<span class="bilhete-status" style="color:var(--green)"><i data-lucide="circle-check"></i> BILHETE GREEN! Odd: ${{b.oddTotal.toFixed(2)}}</span>`;
    }} else if(av.status==='loss'){{
      statusHtml = `<span class="bilhete-status" style="color:var(--red)"><i data-lucide="circle-x"></i> Perdeu (${{av.erros}} erro${{av.erros>1?'s':''}})</span>`;
    }} else if(av.status==='partial'){{
      statusHtml = `<span class="bilhete-status" style="color:var(--yellow)"><i data-lucide="triangle-alert"></i> Parcial — ${{av.sd}} sem dados</span>`;
    }}

    return`<div class="bilhete-card ${{cls}}${{overlayClass}}">
      <div class="bilhete-header">
        <div class="hg-hero-copy">
          <div class="bilhete-title">${{label}}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:2px">${{b.sels.length}} seleções${{tierLabel}}</div>
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
  }};

  const bingoDestaqueHtml = bingoDestaque ? renderBilheteCard(bingoDestaque) : '';
  const destaquesHtml = (diaHtml || bingoDestaqueHtml)
    ? `<div class="bilhete-destaques">${{diaHtml}}${{bingoDestaqueHtml}}</div>`
    : '';
  const listaTitulo = todosBilhetes.length ? '<div class="sec-title"><i data-lucide="ticket"></i> Todos os Bilhetes</div>' : '';
  const html = todosBilhetes.map(renderBilheteCard).join('');

  const callout = confirmado
    ? '<div class="callout ok"><strong><i data-lucide="circle-check"></i> Resultados disponíveis</strong> · Bilhetes avaliados com resultados reais.</div>'
    : '<div class="callout info"><strong><i data-lucide="target"></i> Bilhetes do Dia</strong> · Combinações geradas automaticamente pelo modelo. Aguardando resultados.</div>';

  el.innerHTML = callout + destaquesHtml + listaTitulo + `<div class="bilhete-grid">${{html}}</div>`;
}}

// ── Resultados do Dia ──────────────────────────────────────────────
function renderHistoricoDia(date,jogos){{
  const el=document.getElementById('mkt-'+date+'-historico_dia');
  const conf=isConfirmado(date);
  const stats=(ALL_DATA[date]||{{}}).resultado_stats||{{}};

  if(!conf){{
    const rows=[...jogos].sort(sortByGrade).map((d,i)=>{{
      return`<tr class="row-pending">
        <td class="row-num">${{i+1}}</td>
        ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
        <td>${{gradeHtml(getPalpiteGrade(d))}}</td>
        <td class="mono" style="font-size:11px;color:var(--muted)">${{getPalpiteMkt(d)}}</td>
        <td>${{bar(getPalpiteScore(d))}}</td>
        <td><span class="res-badge pending"><i data-lucide="clock"></i> Aguardando</span></td>
      </tr>`;
    }}).join('');
    el.innerHTML=`
      <div class="callout warn"><strong><i data-lucide="clock"></i> Resultados pendentes</strong> · Execute <code>confirmar.py --date ${{date.split('-').reverse().join('-')}}</code> após os jogos.</div>
      <div class="tbl-wrap"><table>
        <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Confiança</th><th>Mercado</th><th>Score</th><th>Status</th></tr></thead>
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
      <span style="font-size:10px;color:var(--muted);min-width:88px;display:inline-flex;align-items:center;gap:5px"><span class="mini-stat ok"><i data-lucide="circle-check"></i>${{s.acertos}}</span><span class="mini-stat err"><i data-lucide="circle-x"></i>${{s.erros}}</span><span class="mini-stat neutral">/ ${{s.palpites}}</span></span>
    </div>`;
  }}).join('');

  // Tabela completa com resultados
  const rows=[...jogos].sort(sortByGrade).map((d,i)=>{{
    const res=getResultado(d);
    const ac=d.acertos||{{}};
    const badges=Object.entries(ac).map(([mkt,info])=>{{
      const cls=info.acertou===true?'hit':info.acertou===false?'miss':'pending';
      const icon=info.acertou===true?'circle-check':info.acertou===false?'circle-x':'circle-help';
      return`<span class="res-badge ${{cls}}" style="margin:1px;font-size:9px"><i data-lucide="${{icon}}"></i> ${{mkt}}</span>`;
    }}).join('');
    const rc=primaryRowClass(d);
    const cantRow=res&&res.corners_total!=null?`<span class="mini-stat neutral"><i data-lucide="flag"></i>${{res.corners_total}}</span>`:'—';
    return`<tr class="${{rc}}">
      <td class="row-num">${{i+1}}</td>
      ${{jogoCell(d)}}<td class="mono muted">${{d.hora}}</td>
      ${{res?`<td><div class="placar-cell">${{res.placar}}</div><div class="placar-ht">HT ${{res.placar_ht}}</div></td>`:'<td class="mono muted">—</td>'}}
      <td class="mono">${{cantRow}}</td>
      <td style="max-width:230px">${{badges||'<span class="muted" style="font-size:11px">Sem palpites</span>'}}</td>
    </tr>`;
  }}).join('');

  // Totais
  let ta=0,te=0,tp=0;
  Object.values(stats).forEach(s=>{{ta+=s.acertos||0;te+=s.erros||0;tp+=s.palpites||0;}});
  const tGeral=ta+te>0?Math.round(ta/(ta+te)*100):null;
  const cG=tGeral==null?'var(--muted)':tGeral>=70?'var(--green)':tGeral>=50?'var(--orange)':'var(--red)';

  el.innerHTML=`
    <div class="callout ok"><strong><i data-lucide="circle-check"></i> Resultados confirmados</strong> · Dados reais da API-Football.</div>
    <div class="kpi-row" style="margin-bottom:16px">
      <div class="kpi"><div class="kpi-val" style="color:${{cG}}">${{tGeral!=null?tGeral+'%':'—'}}</div><div class="kpi-lbl">Taxa do Dia</div></div>
      <div class="kpi"><div class="kpi-val g">${{ta}}</div><div class="kpi-lbl">Acertos</div></div>
      <div class="kpi"><div class="kpi-val r">${{te}}</div><div class="kpi-lbl">Erros</div></div>
      <div class="kpi"><div class="kpi-val b">${{tp}}</div><div class="kpi-lbl">Palpites</div></div>
    </div>
    <div class="sec-title"><i data-lucide="bar-chart-2"></i> Taxa por Mercado</div>
    <div style="max-width:580px;margin-bottom:20px">${{taxaBars||'<div class="empty">Sem dados.</div>'}}</div>
    <div class="sec-title"><i data-lucide="list"></i> Todos os Jogos</div>
    <div class="tbl-wrap"><table>
      <thead><tr><th>#</th><th>Jogo</th><th>Hora</th><th>Placar</th><th>Cant.</th><th>Palpites e Acertos</th></tr></thead>
      <tbody>${{rows}}</tbody>
    </table></div>`;
}}

// ── Histórico Global ───────────────────────────────────────────────
function renderHistoricoGlobal(){{
  const el=document.getElementById('historico-content');
  const g=GLOBAIS;
  const pm=g.por_mercado||{{}};
  const dias=Object.keys(ALL_DATA).sort((a,b)=>{{
    const [da,ma,ya]=a.split('-').map(Number);
    const [db,mb,yb]=b.split('-').map(Number);
    return new Date(ya,ma-1,da)-new Date(yb,mb-1,db);
  }});

  if(g.dias_confirmados===0){{
    el.innerHTML=`<div class="callout warn" style="margin-top:20px"><strong><i data-lucide="clock"></i> Sem histórico confirmado ainda</strong> · Execute confirmar.py após os jogos de cada dia.</div>`;
    return;
  }}

  const confirmedDays=dias.filter(d=>!!(ALL_DATA[d]||{{}}).resultado_confirmado);
  const gerados=dias.reduce((acc,d)=>acc+(((ALL_DATA[d]||{{}}).jogos||[]).length),0);
  const auditados=(g.total_acertos||0)+(g.total_erros||0);
  const taxa=g.taxa_geral;
  const taxaColor=t=>t==null?'var(--muted)':t>=70?'var(--green)':t>=50?'var(--orange)':'var(--red)';
  const fmtTaxa=t=>t!=null?`${{t}}%`:'—';
  const categoryColor=grade=>grade==='A+'?'var(--green)':grade==='A'?'var(--yellow)':grade==='B'?'var(--blue)':'var(--text)';
  const marketColor=m=>m&&m.startsWith('Esc')?'var(--teal)':m==='BTTS'?'var(--yellow)':m&&m.startsWith('Under')?'var(--purple2)':'var(--blue)';
  const stat=()=>({{gerados:0,auditados:0,acertos:0,erros:0}});
  const taxaStat=s=>s.auditados>0?Math.round((s.acertos/s.auditados)*1000)/10:null;
  const addPick=(s,j)=>{{
    s.gerados++;
    const ok=primaryResultOk(j);
    if(ok===true){{s.auditados++;s.acertos++;}}
    else if(ok===false){{s.auditados++;s.erros++;}}
  }};
  const mergePick=(a,b)=>{{a.gerados+=b.gerados;a.auditados+=b.auditados;a.acertos+=b.acertos;a.erros+=b.erros;return a;}};
  const labelGrade=g=>g==='A+'?'Confiança Alta':g==='A'?'Confiança Média':g==='B'?'Moderado':g;
  const categoryStats={{'A+':stat(),'A':stat(),'B':stat()}};
  const top5Stats=stat();

  for(const d of dias){{
    const dayData=ALL_DATA[d]||{{}};
    const jogos=dayData.jogos||[];
    const snap=dayData.palpites_snapshot||[];
    const fullById=new Map(jogos.filter(j=>j.fixture_id).map(j=>[String(j.fixture_id),j]));
    const fullByName=new Map(jogos.map(j=>[`${{j.home}} x ${{j.away}}`,j]));
    const enrich=item=>{{
      const full=(item.fixture_id&&fullById.get(String(item.fixture_id)))||fullByName.get(`${{item.home}} x ${{item.away}}`)||jogos.find(j=>j.jogo===item.jogo)||{{}};
      return {{...item,...full}};
    }};
    const base=jogos.length?jogos:(snap.length?snap.map(enrich):[]);
    base.forEach(j=>{{
      const gr=getPalpiteGrade(j);
      if(categoryStats[gr]) addPick(categoryStats[gr],j);
    }});

    let topItems=[];
    if((dayData.top5||[]).length){{
      topItems=dayData.top5.map(name=>base.find(j=>j.jogo===name||`${{j.home}} x ${{j.away}}`===name)).filter(Boolean);
    }}
    if(!topItems.length) topItems=[...base].sort(sortByGrade).slice(0,5);
    topItems.forEach(j=>addPick(top5Stats,j));
  }}

  const marketStats=MERCADOS.map(m=>{{
    const s=pm[m]||{{}};
    const acertos=s.acertos||0;
    const erros=s.erros||0;
    const audit=acertos+erros;
    const t=audit>0?Math.round((acertos/audit)*1000)/10:null;
    return {{m,acertos,erros,auditados:audit,gerados:s.palpites||s.p||audit,taxa:t}};
  }}).filter(x=>x.gerados>0||x.auditados>0);

  const bestCategory=Object.entries(categoryStats)
    .map(([grade,s])=>({{grade,label:labelGrade(grade),...s,taxa:taxaStat(s)}}))
    .filter(x=>x.auditados>0)
    .sort((a,b)=>(b.taxa-a.taxa)||(b.auditados-a.auditados))[0]||null;
  const bestMarket=[...marketStats].filter(x=>x.auditados>0)
    .sort((a,b)=>(b.taxa-a.taxa)||(b.auditados-a.auditados))[0]||null;

  const ticketStats={{geral:stat(),dia:stat(),bingo:stat(),premium:stat(),elite:stat()}};
  const addTicket=(s,b,confirmed)=>{{
    if(!b||!b.sels||!b.sels.length)return;
    s.gerados++;
    const r=avaliarBilhete(b.sels,confirmed);
    if(r.status==='win'){{s.auditados++;s.acertos++;}}
    else if(r.status==='loss'){{s.auditados++;s.erros++;}}
  }};
  const hydrateTicket=(b,jogos)=>{{
    if(!b||!b.sels)return b;
    const byId=new Map(jogos.filter(j=>j.fixture_id).map(j=>[String(j.fixture_id),j]));
    const byName=new Map(jogos.map(j=>[j.jogo,j]));
    return {{...b,sels:b.sels.map(s=>{{
      const full=(s.fixture_id&&byId.get(String(s.fixture_id)))||byName.get(s.jogo)||null;
      return full?{{...s,resultado:full.resultado,acertos:full.acertos||s.acertos||{{}}}}:s;
    }})}};
  }};
  for(const d of dias){{
    const dayData=ALL_DATA[d]||{{}};
    const confirmed=!!dayData.resultado_confirmado;
    const jogos=dayData.jogos||[];
    const snap=dayData.bilhetes_snapshot;
    const generated=snap||gerarBilhetes(jogos);
    addTicket(ticketStats.dia,hydrateTicket(generated.bilheteDia,jogos),confirmed);
    (generated.bilhetes||[]).forEach(item=>{{
      const label=String(item.label||'').toLowerCase();
      const tipo=String(item.tipo||'').toLowerCase();
      const b=hydrateTicket(item.b,jogos);
      if(label.includes('elite')||tipo==='b2') addTicket(ticketStats.elite,b,confirmed);
      else if(label.includes('premium')||tipo==='b1') addTicket(ticketStats.premium,b,confirmed);
    }});
    gerarBingoBilhetes(jogos).forEach(item=>addTicket(ticketStats.bingo,hydrateTicket(item.b,jogos),confirmed));
  }}
  mergePick(ticketStats.geral,ticketStats.dia);
  mergePick(ticketStats.geral,ticketStats.bingo);
  mergePick(ticketStats.geral,ticketStats.premium);
  mergePick(ticketStats.geral,ticketStats.elite);

  const categoryItems=[
    {{key:'A+',label:'Confiança Alta',tone:'green'}},
    {{key:'A',label:'Confiança Média',tone:'yellow'}},
    {{key:'B',label:'Moderado',tone:'blue'}},
  ];
  const categoryRows=categoryItems.map(c=>{{
    const s=categoryStats[c.key];
    const t=taxaStat(s);
    return`<div class="hist-break-row ${{c.tone}}">
      <span>${{c.label}}</span>
      <strong style="color:${{taxaColor(t)}}">${{fmtTaxa(t)}}</strong>
      <em><span class="ok">${{s.acertos}}✓</span> <span class="err">${{s.erros}}✗</span> · ${{s.auditados}} confirmados</em>
    </div>`;
  }}).join('');

  const top5Taxa=taxaStat(top5Stats);
  const ticketRow=(label,s)=>{{
    const t=taxaStat(s);
    return`<div class="hist-break-row">
      <span>${{label}}</span>
      <strong style="color:${{taxaColor(t)}}">${{fmtTaxa(t)}}</strong>
      <em><span class="ok">${{s.acertos}}✓</span> <span class="err">${{s.erros}}✗</span> · ${{s.auditados}} confirmados</em>
    </div>`;
  }};

  const radialRows=categoryItems.map((c,i)=>{{
    const s=categoryStats[c.key];
    const t=taxaStat(s)||0;
    const r=48+i*9;
    const dash=Math.round((2*Math.PI*r)*(t/100));
    const gap=Math.round(2*Math.PI*r)-dash;
    return`<circle class="hist-radial-ring ${{c.tone}}" cx="74" cy="74" r="${{r}}" stroke-dasharray="${{dash}} ${{gap}}" transform="rotate(-90 74 74)"></circle>`;
  }}).join('');
  const radialLegend=categoryItems.map(c=>{{
    const t=taxaStat(categoryStats[c.key]);
    return`<div class="hist-vlegend-item"><span class="hist-dot ${{c.tone}}"></span><span>${{c.label}}</span><strong>${{fmtTaxa(t)}}</strong></div>`;
  }}).join('');

  const dayStats=confirmedDays.map(d=>{{
    const s=ALL_DATA[d].resultado_stats||{{}};
    let a=0,e=0;
    Object.values(s).forEach(x=>{{a+=x.acertos||0;e+=x.erros||0;}});
    const t=a+e>0?Math.round((a/(a+e))*1000)/10:null;
    return {{d,a,e,t}};
  }});
  const linePoints=dayStats.map((x,i)=>{{
    const denom=Math.max(1,dayStats.length-1);
    const px=12+(i/denom)*276;
    const py=104-((x.t||0)/100)*82;
    return `${{px}},${{py}}`;
  }}).join(' ');
  const areaPoints=linePoints?`12,112 ${{linePoints}} 288,112`:'';
  const dayBars=dayStats.slice(-10).map(x=>{{
    const [dd,mm]=x.d.split('-');
    const c=taxaColor(x.t);
    return`<div class="day-hist-row">
      <span class="day-hist-date">${{dd}}/${{mm}}</span>
      <div class="day-hist-bar"><div class="day-hist-fill" style="width:${{x.t||0}}%;background:${{c}}"></div></div>
      <span class="day-hist-info" style="color:${{c}}">${{fmtTaxa(x.t)}} · <span class="ok">${{x.a}}✓</span> <span class="err">${{x.e}}✗</span></span>
    </div>`;
  }}).join('');

  const marketRows=[...marketStats].filter(x=>x.auditados>0)
    .sort((a,b)=>(b.taxa-a.taxa)||(b.auditados-a.auditados))
    .map((s,i)=>`<div class="hist-market-row">
      <span class="hist-rank">${{i+1}}</span>
      <div><strong>${{s.m}}</strong><small><span class="ok">${{s.acertos}}✓</span> <span class="err">${{s.erros}}✗</span> · ${{s.auditados}} confirmados</small></div>
      <span class="hist-market-taxa" style="color:${{taxaColor(s.taxa)}}">${{fmtTaxa(s.taxa)}}</span>
    </div>`).join('');
  const marketMini=[...marketStats].filter(x=>x.auditados>0)
    .sort((a,b)=>(b.taxa-a.taxa)||(b.auditados-a.auditados)).slice(0,4)
    .map(s=>`<div class="hist-market-mini-row"><span>${{s.m}}</span><div><i style="width:${{s.taxa||0}}%;background:${{taxaColor(s.taxa)}}"></i></div><strong>${{fmtTaxa(s.taxa)}}</strong></div>`).join('');

  const cG=taxaColor(taxa);
  const bestCategoryColor=bestCategory?categoryColor(bestCategory.grade):'var(--text)';
  const bestMarketColor=bestMarket?marketColor(bestMarket.m):'var(--text)';

  // ── Vitória 1X2 stats ──────────────────────────────────────────
  const rfRows=rfHistoricoRows();
  const rfHist=rfSummary(rfRows.filter(r=>r.result!=='PENDING'));
  const rfTaxa=rfHist.taxa;
  const rfTaxaColor=taxaColor(rfTaxa);

  // ── Donut SVG helper ───────────────────────────────────────────
  function donutSvg(pct, color, size){{
    size=size||90;
    const r=size/2-8;
    const circ=2*Math.PI*r;
    const filled=Math.round(circ*(pct||0)/100*10)/10;
    const cx=size/2, cy=size/2;
    return `<svg class="hg-donut-svg" width="${{size}}" height="${{size}}" viewBox="0 0 ${{size}} ${{size}}">
      <circle class="hg-donut-bg" cx="${{cx}}" cy="${{cy}}" r="${{r}}"/>
      <circle class="hg-donut-ring" cx="${{cx}}" cy="${{cy}}" r="${{r}}"
        stroke="${{color}}" stroke-dasharray="${{filled}} ${{circ-filled}}"
        transform="rotate(-90 ${{cx}} ${{cy}})" filter="drop-shadow(0 0 6px ${{color}}88)"/>
      <text class="hg-donut-val" x="${{cx}}" y="${{cy}}" fill="${{color}}">${{pct!=null?Math.round(pct)+'%':'—'}}</text>
    </svg>`;
  }}

  // ── Top5 panel ─────────────────────────────────────────────────
  const top5Pct=top5Taxa!=null?Math.round(top5Taxa):null;
  const top5Lbl=top5Pct==null?'—':top5Pct>=80?'EXCELENTE':top5Pct>=65?'BOM':'REGULAR';
  const top5LblColor=top5Pct==null?'var(--muted)':top5Pct>=80?'var(--green)':top5Pct>=65?'var(--yellow)':'var(--orange)';

  // ── Category rows ──────────────────────────────────────────────
  const catDefs=[
    {{key:'A+',label:'Confiança Alta',cls:'alta'}},
    {{key:'A', label:'Confiança Média',cls:'media'}},
    {{key:'B', label:'Moderado',cls:'moderado'}},
  ];
  const catRowsHtml=catDefs.map(c=>{{
    const s=categoryStats[c.key];
    const t=taxaStat(s);
    return `<div class="hg-cat-row ${{c.cls}}">
      <div>
        <div class="hg-cat-row-name">${{c.label}}</div>
        <div class="hg-cat-row-detail"><span class="ok">${{s.acertos}}✓</span> · <span class="err">${{s.erros}}✗</span> · ${{s.auditados}} confirmados</div>
      </div>
      <div class="hg-cat-rate" style="color:${{taxaColor(t)}}">${{fmtTaxa(t)}}</div>
    </div>`;
  }}).join('');

  // ── Mercado mini ───────────────────────────────────────────────
  const mktMiniNames={{'Over 1.5':'Over 1.5','Over 2.5':'Over 2.5','Esc 7.5':'Escanteios (Over)','Esc 8.5':'Esc 8.5','BTTS':'Ambas Marcam','Under 3.5':'Under 3.5','Under 4.5':'Under 4.5','Over 0.5 HT':'Over 0.5 HT'}};
  const mktMiniHtml=[...marketStats].filter(x=>x.auditados>0)
    .sort((a,b)=>(b.taxa-a.taxa)||(b.auditados-a.auditados)).slice(0,5)
    .map(s=>`<div class="hg-mkt-mini-row">
      <div class="hg-mkt-mini-name">${{mktMiniNames[s.m]||s.m}}</div>
      <div class="hg-mkt-mini-rate" style="color:${{taxaColor(s.taxa)}}">${{fmtTaxa(s.taxa)}}</div>
    </div>`).join('');

  // ── Ranking rows ───────────────────────────────────────────────
  const rankRowsHtml=[...marketStats].filter(x=>x.auditados>0)
    .sort((a,b)=>(b.taxa-a.taxa)||(b.auditados-a.auditados))
    .map((s,i)=>`<div class="hg-rank-row">
      <div class="hg-rank-num">${{i+1}}</div>
      <div class="hg-rank-bar" style="background:${{taxaColor(s.taxa)}}"></div>
      <div class="hg-rank-main">
        <div class="hg-rank-name">${{s.m}}</div>
        <div class="hg-rank-detail"><span class="ok">${{s.acertos}}✓</span> · <span class="err">${{s.erros}}✗</span> · ${{s.auditados}} confirmados</div>
      </div>
      <div class="hg-rank-rate" style="color:${{taxaColor(s.taxa)}}">${{fmtTaxa(s.taxa)}}</div>
    </div>`).join('');

  // ── Dias bar ───────────────────────────────────────────────────
  const dayBarsHtml=dayStats.slice(-10).map(x=>{{
    const [dd,mm]=x.d.split('-');
    const c=taxaColor(x.t);
    const pct=x.t||0;
    return `<div class="hg-day-row">
      <div class="hg-day-date">${{dd}}/${{mm}}</div>
      <div class="hg-day-bar"><div class="hg-day-fill" style="width:${{pct}}%;background:${{c}}"></div></div>
      <div class="hg-day-info" style="color:${{c}}">${{fmtTaxa(x.t)}} · <span class="ok">${{x.a}}✓</span> <span class="err">${{x.e}}✗</span></div>
    </div>`;
  }}).join('');

  el.innerHTML=`
    <div class="hg-page">

      <!-- HERO -->
      <div class="hg-hero">
        <div>
          <div class="hg-hero-label">Performance Geral</div>
          <h2>Performance validada por resultados reais.</h2>
          <div class="hg-hero-sub">Gerados: todos os palpites disponibilizados na plataforma.<br>Confirmados: apenas previsões com resultado final definido (GREEN ou RED).</div>
        </div>
        <div class="hg-taxa-box">
          <div class="hg-taxa-label">Taxa Geral</div>
          <div class="hg-taxa-val" style="color:${{taxaColor(taxa)}}">${{fmtTaxa(taxa)}}</div>
          <div class="hg-taxa-note">Base estatística:<br>${{auditados}} previsões</div>
          <div class="hg-taxa-bar"><div class="hg-taxa-bar-fill" style="width:${{taxa||0}}%;background:${{taxaColor(taxa)}}"></div></div>
        </div>
        <div class="hg-insights">
          <div class="hg-insight">
            <div class="hg-insight-lbl">Melhor Categoria</div>
            <div class="hg-insight-val" style="color:${{bestCategoryColor}}">${{bestCategory?bestCategory.label:'—'}}</div>
            <div class="hg-insight-note">${{bestCategory?`<b style="color:${{bestCategoryColor}}">${{fmtTaxa(bestCategory.taxa)}}</b> · ${{bestCategory.auditados}} confirmados`:'sem amostra'}}</div>
          </div>
          <div class="hg-insight">
            <div class="hg-insight-lbl">Melhor Mercado</div>
            <div class="hg-insight-val" style="color:${{bestMarketColor}}">${{bestMarket?bestMarket.m:'—'}}</div>
            <div class="hg-insight-note">${{bestMarket?`<b style="color:${{bestMarketColor}}">${{fmtTaxa(bestMarket.taxa)}}</b> · ${{bestMarket.auditados}} confirmados`:'sem amostra'}}</div>
          </div>
        </div>
      </div>

      <!-- KPIs -->
      <div class="hg-kpi-row">
        <div class="hg-kpi">
          <div class="hg-kpi-icon blue"><svg viewBox="0 0 24 24"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg></div>
          <div><div class="hg-kpi-val">${{gerados}}</div><div class="hg-kpi-lbl">Gerados</div></div>
        </div>
        <div class="hg-kpi">
          <div class="hg-kpi-icon teal"><svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>
          <div><div class="hg-kpi-val">${{auditados}}</div><div class="hg-kpi-lbl">Confirmados</div></div>
        </div>
        <div class="hg-kpi ok">
          <div class="hg-kpi-icon green"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><circle cx="12" cy="12" r="3"/></svg></div>
          <div><div class="hg-kpi-val">${{g.total_acertos||0}}</div><div class="hg-kpi-lbl">Acertos</div></div>
        </div>
        <div class="hg-kpi err">
          <div class="hg-kpi-icon red"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></div>
          <div><div class="hg-kpi-val">${{g.total_erros||0}}</div><div class="hg-kpi-lbl">Erros</div></div>
        </div>
        <div class="hg-kpi">
          <div class="hg-kpi-icon purple"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
          <div><div class="hg-kpi-val">${{confirmedDays.length}}</div><div class="hg-kpi-lbl">Dias</div></div>
        </div>
      </div>

      <!-- 4 PAINÉIS -->
      <div class="hg-panels">
        <div class="hg-panel p-blue">
          <div>
            <div class="hg-panel-label">Top 5 do Dia</div>
            <div class="hg-panel-title">Taxa geral</div>
            <div class="hg-panel-note">${{top5Stats.auditados}} confirmados de ${{top5Stats.gerados}} gerados</div>
          </div>
          <div class="hg-donut-wrap">
            ${{donutSvg(top5Taxa,taxaColor(top5Taxa),100)}}
            <div class="hg-donut-stats"><span class="ok">${{top5Stats.acertos}}✓</span> · <span class="err">${{top5Stats.erros}}x</span> · ${{top5Stats.auditados}} confirmados</div>
            <div class="hg-donut-badge" style="color:${{top5LblColor}};border:1px solid ${{top5LblColor}}44;background:${{top5LblColor}}18">
              <svg viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/></svg>
              ${{top5Lbl}}
            </div>
          </div>
        </div>
        <div class="hg-panel p-green">
          <div>
            <div class="hg-panel-label">Melhores Previsões</div>
            <div class="hg-panel-title">Taxas por confiança</div>
            <div class="hg-panel-note">base completa dos jogos confirmados</div>
          </div>
          <div class="hg-cat-rows">${{catRowsHtml}}</div>
        </div>
        <div class="hg-panel p-yellow">
          <div>
            <div class="hg-panel-label">Vitória (1X2)</div>
            <div class="hg-panel-title">Taxa de assertividade</div>
            <div class="hg-panel-note">base completa dos jogos confirmados</div>
          </div>
          <div class="hg-donut-wrap">
            ${{donutSvg(rfTaxa,rfTaxaColor,100)}}
            <div class="hg-donut-stats"><span class="ok">${{rfHist.green}}✓</span> · <span class="err">${{rfHist.red}}x</span> · ${{rfHist.green+rfHist.red}} confirmados</div>
          </div>
        </div>
        <div class="hg-panel p-purple">
          <div>
            <div class="hg-panel-label">Taxa por Mercado</div>
            <div class="hg-panel-title">Desempenho geral</div>
            <div class="hg-panel-note">base completa dos jogos confirmados</div>
          </div>
          <div class="hg-mkt-mini">${{mktMiniHtml||'<div class="empty">Sem dados.</div>'}}</div>
        </div>
      </div>

      <!-- BOTTOM -->
      <div class="hg-bottom">
        <div class="hg-card">
          <div class="hg-card-title">
            <svg viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            Ranking por Mercado
          </div>
          <div class="hg-rank-list">${{rankRowsHtml||'<div class="empty">Sem mercados confirmados.</div>'}}</div>
        </div>
        <div class="hg-card">
          <div class="hg-card-title">
            <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Últimos Dias Confirmados
          </div>
          <div class="hg-days-list">${{dayBarsHtml||'<div class="empty">Sem dias confirmados.</div>'}}</div>
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

function showHistoricoGlobal(){{
  document.querySelector('.content-area')?.classList.add('hist-mode');
  document.querySelectorAll('.day-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.date-strip-item').forEach(t=>t.classList.remove('active'));
  document.getElementById('panel-historico').style.display='block';
  document.querySelectorAll('.sidebar-item').forEach(el=>el.classList.remove('active'));
  document.getElementById('sb-historico')?.classList.add('active');

  historicoVisible=true;
  renderHistoricoGlobal();
  if(typeof ensureLucideIcons === 'function') ensureLucideIcons();
}}

function switchDate(date){{
  document.querySelector('.content-area')?.classList.remove('hist-mode');
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
}}

function renderMkt(date,mkt){{
  const jogos=getJogos(date);
  if(mkt==='visao')          renderVisao(date,jogos);
  else if(mkt==='ranking')   renderRanking(date,jogos);
  else if(mkt==='resultado') renderResultadoFinal(date,jogos);
  else if(mkt==='over15')    renderOver15(date,jogos);
  else if(mkt==='over25')    renderOver25(date,jogos);
  else if(mkt==='escanteios')renderEsc(date,jogos);
  else if(mkt==='bilhetes')     renderBilhetes(date,jogos);
  else if(mkt==='historico_dia') renderHistoricoDia(date,jogos);
  if(typeof ensureLucideIcons === 'function') ensureLucideIcons();
}}

// ── Sidebar navigation ──────────────────────────────────────────────
function sidebarNav(mkt){{
  // If no date active, use the most recent one
  if(!activeDate){{
    const d = dates[dates.length-1];
    if(d) switchDate(d);
    else return;
  }}
  if(mkt==='visao'){{
    activeMkt[activeDate]='visao';
    switchDate(activeDate);
    updateSidebarActive('visao');
    return;
  }}
  if(historicoVisible || document.getElementById('panel-historico')?.style.display==='block'){{
    activeMkt[activeDate]=mkt;
    switchDate(activeDate);
  }} else {{
    switchMkt(activeDate, mkt);
  }}
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
}}

// ── Market category & sub-filters ──────────────────────────────────
let activeCat = null;
let activeSubFilter = null;

const CAT_SUBFILTERS = {{
  'gols':       [{{key:'over15',  label:'Over 1.5'}}, {{key:'over25', label:'Under'}}],
  'escanteios': [{{key:'esc75',   label:'Over 7.5'}}, {{key:'esc85',  label:'Over 8.5'}}],
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
  }} else if(cat === 'resultado'){{
    renderResultadoFinal(date, jogos);
    document.querySelectorAll(`#day-${{date}} .mkt-panel`).forEach(p=>p.classList.remove('active'));
    const p = document.getElementById('mkt-'+date+'-resultado');
    if(p) p.classList.add('active');
  }}
}}
// Inicializar ícones Lucide com fallback local para uso offline/file://
function ensureLucideIcons(){{
  if(typeof lucide !== 'undefined' && lucide.createIcons){{
    lucide.createIcons();
  }}
  const paths = {{
    'layout-dashboard':'<rect width="7" height="9" x="3" y="3" rx="1"></rect><rect width="7" height="5" x="14" y="3" rx="1"></rect><rect width="7" height="9" x="14" y="12" rx="1"></rect><rect width="7" height="5" x="3" y="16" rx="1"></rect>',
    'bar-chart-2':'<line x1="18" x2="18" y1="20" y2="10"></line><line x1="12" x2="12" y1="20" y2="4"></line><line x1="6" x2="6" y1="20" y2="14"></line>',
    'target':'<circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle>',
    'brain-circuit':'<path d="M12 5a3 3 0 0 0-5.83-1"></path><path d="M12 5a3 3 0 0 1 5.83-1"></path><path d="M7 4a3 3 0 0 0-2 5"></path><path d="M17 4a3 3 0 0 1 2 5"></path><path d="M5 9a3 3 0 0 0 1 5.8"></path><path d="M19 9a3 3 0 0 1-1 5.8"></path><path d="M8 18a3 3 0 0 0 4-2"></path><path d="M16 18a3 3 0 0 1-4-2"></path><path d="M9 9h1"></path><path d="M14 9h1"></path><path d="M12 12v4"></path>',
    'credit-card':'<rect width="20" height="14" x="2" y="5" rx="2"></rect><line x1="2" x2="22" y1="10" y2="10"></line>',
    'info':'<circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path>',
    'search':'<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path>',
    'list':'<line x1="8" x2="21" y1="6" y2="6"></line><line x1="8" x2="21" y1="12" y2="12"></line><line x1="8" x2="21" y1="18" y2="18"></line><line x1="3" x2="3.01" y1="6" y2="6"></line><line x1="3" x2="3.01" y1="12" y2="12"></line><line x1="3" x2="3.01" y1="18" y2="18"></line>',
    'calendar-days':'<path d="M8 2v4"></path><path d="M16 2v4"></path><rect width="18" height="18" x="3" y="4" rx="2"></rect><path d="M3 10h18"></path><path d="M8 14h.01"></path><path d="M12 14h.01"></path><path d="M16 14h.01"></path><path d="M8 18h.01"></path><path d="M12 18h.01"></path><path d="M16 18h.01"></path>',
    'clock':'<circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline>',
    'circle-x':'<circle cx="12" cy="12" r="10"></circle><path d="m15 9-6 6"></path><path d="m9 9 6 6"></path>',
    'triangle-alert':'<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><path d="M12 9v4"></path><path d="M12 17h.01"></path>',
    'circle-help':'<circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 1 1 5.83 1c0 2-3 2-3 4"></path><path d="M12 17h.01"></path>',
    'flag':'<path d="M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 8 2a6 6 0 0 0 4-1.2V14a6 6 0 0 1-4 1.2c-3 0-5-2-8-2a6 6 0 0 0-4 1.2"></path>',
    'square':'<rect width="16" height="16" x="4" y="4" rx="2"></rect>',
    'log-in':'<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><polyline points="10 17 15 12 10 7"></polyline><line x1="15" x2="3" y1="12" y2="12"></line>',
    'chevron-down':'<path d="m6 9 6 6 6-6"></path>',
    'rocket':'<path d="M4.5 16.5c-1.5 1.3-2 3-2 5 2 0 3.7-.5 5-2"></path><path d="M9 15 15 9"></path><path d="M15 9h4l2-6-6 2v4Z"></path><path d="M9 15H5l-2 6 6-2v-4Z"></path>',
    'arrow-right':'<path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path>',
    'grid-2x2':'<rect width="7" height="7" x="3" y="3" rx="1"></rect><rect width="7" height="7" x="14" y="3" rx="1"></rect><rect width="7" height="7" x="14" y="14" rx="1"></rect><rect width="7" height="7" x="3" y="14" rx="1"></rect>',
    'star':'<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>',
    'ticket':'<path d="M2 9a3 3 0 0 0 0 6v3a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-3a3 3 0 0 0 0-6V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"></path><path d="M13 5v2"></path><path d="M13 17v2"></path><path d="M13 11v2"></path>',
    'trending-up':'<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline><polyline points="16 7 22 7 22 13"></polyline>',
    'circle-check':'<circle cx="12" cy="12" r="10"></circle><path d="m9 12 2 2 4-4"></path>',
    'shield-check':'<path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3Z"></path><path d="m9 12 2 2 4-4"></path>',
    'crosshair':'<circle cx="12" cy="12" r="10"></circle><line x1="22" x2="18" y1="12" y2="12"></line><line x1="6" x2="2" y1="12" y2="12"></line><line x1="12" x2="12" y1="6" y2="2"></line><line x1="12" x2="12" y1="22" y2="18"></line>',
    'corner-up-right':'<polyline points="15 14 20 9 15 4"></polyline><path d="M4 20v-7a4 4 0 0 1 4-4h12"></path>',
    'layers':'<path d="m12.83 2.18 8.05 4.02a1.25 1.25 0 0 1 0 2.24l-8.05 4.02a1.85 1.85 0 0 1-1.66 0L3.12 8.44a1.25 1.25 0 0 1 0-2.24l8.05-4.02a1.85 1.85 0 0 1 1.66 0Z"></path><path d="m22 12.5-9.17 4.58a1.85 1.85 0 0 1-1.66 0L2 12.5"></path><path d="m22 17.5-9.17 4.58a1.85 1.85 0 0 1-1.66 0L2 17.5"></path>',
    'trophy':'<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path><path d="M4 22h16"></path><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"></path><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"></path><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"></path>',
    'shield':'<path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3Z"></path>',
    'activity':'<path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>',
    'rotate-ccw':'<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path>'
  }};
  document.querySelectorAll('i[data-lucide]').forEach(el=>{{
    const name = el.getAttribute('data-lucide');
    const path = paths[name];
    if(!path) return;
    const style = el.getAttribute('style') || '';
    const w = (style.match(/width:\\s*(\\d+)px/)||[])[1] || 14;
    const h = (style.match(/height:\\s*(\\d+)px/)||[])[1] || w;
    const wrap = document.createElement('span');
    wrap.innerHTML = `<svg data-fallback-lucide="${{name}}" width="${{w}}" height="${{h}}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${{path}}</svg>`;
    el.replaceWith(wrap.firstElementChild);
  }});
}}
ensureLucideIcons();

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
  renderGlobalHistoricoSearch();
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
    renderGlobalHistoricoSearch();
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


