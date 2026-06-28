"""
PackBall Analytics — Pipeline v3.0
Fusão do modelo validado v2.1 com metodologia profissional de análise multivariada.
Mercados: Over 1.5 · Over 2.5 · BTTS · Over 0.5 HT · Under 4.5 · Escanteios 7.5/8.5 · Cartões 2.5/3.5
Score profissional: A+ / A / B / C / D
"""
import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime
import warnings
from ligas_config import blocked_name, favorite_countries, favorite_league_names
from snapshots import build_bilhetes_snapshot, build_palpites_snapshot, attach_results_to_snapshots
from cards.pipeline_adapter import apply_cards_engine_to_matches
warnings.filterwarnings('ignore')

# ── Configuração ───────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'csv')
OUT_DIR  = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
os.makedirs(OUT_DIR, exist_ok=True)

COUNTRIES_OK = [
    'Europe','England','Spain','Italy','Germany','France',
    'Netherlands','Portugal','Romania','Turkey',
    'South America','Brazil','Argentina','Uruguay','Canada'
]
STATUS_OK = ['NS','INPLAY_1ST_HALF','INPLAY_2ND_HALF','HT','AWAITING_UPDATES','FT','FT_PEN','AET']
LIGAS_OK  = [
    'Champions League','Premier League','La Liga','Serie A','Bundesliga',
    'Europa League','Ligue 1','Eredivisie','Liga Portugal','Superliga',
    'Super Lig','Copa Libertadores','Serie B','Copa do Brasil',
    'Liga Profesional de Fútbol',
    # Amistosos de seleções
    'Friendlies','International Friendlies','Friendly International',
    'UEFA Nations League','CONMEBOL Qualifiers','FIFA World Cup - Qualification'
]
LIGAS_ELITE = {
    'Champions League','Europa League','Copa Libertadores',
    'Premier League','La Liga','Serie A','Bundesliga','Ligue 1'
}
COUNTRIES_OK = sorted(favorite_countries(COUNTRIES_OK))
LIGAS_OK = sorted(favorite_league_names(LIGAS_OK))

# ── Helpers ────────────────────────────────────────────────────────
def cp(v):
    try:    return float(str(v).replace(',','.').replace('%',''))
    except: return np.nan

def s(v):
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except: return None

def n(v, mn, mx):
    """Normaliza valor para 0-100."""
    try:
        f = float(v)
        if np.isnan(f): return None
        return max(0., min(100., (f - mn) / (mx - mn) * 100))
    except: return None

def ws(pairs):
    """Média ponderada ignorando nulos."""
    vv, ww = [], []
    for v, w in pairs:
        try:
            f = float(v)
            if not np.isnan(f): vv.append(f); ww.append(w)
        except: pass
    return sum(x*y for x,y in zip(vv,ww)) / sum(ww) if ww else 0

def avg_nn(*vals):
    """Média descartando None."""
    vv = [v for v in vals if v is not None]
    return float(np.mean(vv)) if vv else None

def grade(score):
    """Converte score numérico para grade profissional."""
    if score >= 88: return 'A+'
    if score >= 80: return 'A'
    if score >= 70: return 'B'
    if score >= 60: return 'C'
    return 'D'

def risk(score):
    """Nível de risco inverso ao score."""
    if score >= 88: return 'Muito Baixo'
    if score >= 80: return 'Baixo'
    if score >= 65: return 'Moderado'
    if score >= 50: return 'Arriscado'
    return 'Evitar'

def odd_justa(prob_pct):
    """Odd justa = 1 / probabilidade."""
    if prob_pct and prob_pct > 0:
        return round(100 / prob_pct, 2)
    return None

def prob_poisson(lam, k_min):
    """P(X >= k_min) usando distribuição de Poisson."""
    if lam is None or lam <= 0: return None
    prob = 0.0
    fac = 1
    for k in range(k_min):
        if k > 0: fac *= k
        prob += (lam**k * np.exp(-lam)) / fac
    return max(0., min(100., (1 - prob) * 100))

# ── Extração de colunas ────────────────────────────────────────────
def fex(raw, idx_map):
    """Filtra linhas válidas e extrai colunas por índice."""
    df = raw.copy()
    df = df[df.iloc[:, 4].isin(STATUS_OK)]
    df = df[df.iloc[:, 0].isin(COUNTRIES_OK)]
    ll = df.iloc[:, 2].str.lower().fillna('')
    df = df[~ll.apply(blocked_name)]
    if df.shape[1] < 10:
        return pd.DataFrame(columns=['country','home','away','league','hour'])
    teams = (
        df.iloc[:, 5].astype(str).str.lower().fillna('') + ' ' +
        df.iloc[:, 8].astype(str).str.lower().fillna('')
    )
    df = df[~teams.apply(blocked_name)]
    df = df[df.iloc[:, 2].str.strip().isin(LIGAS_OK)]
    df = df.drop_duplicates(
        subset=[raw.columns[5], raw.columns[8], raw.columns[2]]
    ).reset_index(drop=True)

    result = pd.DataFrame({
        'country': df.iloc[:, 0],
        'home':   df.iloc[:, 5],
        'away':   df.iloc[:, 8],
        'league': df.iloc[:, 2],
        'hour':   df.iloc[:, 3],
    })
    for name, idx in idx_map.items():
        if idx < df.shape[1]:
            result[name] = df.iloc[:, idx].apply(cp)
        else:
            result[name] = np.nan
    return result

# ── Carregar CSVs ──────────────────────────────────────────────────
def load_csvs(date_str):
    folder = os.path.join(DATA_DIR, date_str)
    if not os.path.isdir(folder):
        return None

    def find(keywords):
        for fname in os.listdir(folder):
            fl = fname.lower()
            if fname.endswith('.csv') and all(k.lower() in fl for k in keywords):
                return os.path.join(folder, fname)
        return None

    paths = {
        'geral': find(['geral']) or find(['general']),
        'esc':   find(['escanteio']) or find(['escanteios']),
        'cart':  find(['cart']),
    }
    missing = [k for k, v in paths.items() if v is None]
    if missing:
        print(f"  ⚠ CSVs não encontrados: {missing}")
        return None
    try:
        dfs = {k: pd.read_csv(v, sep=None, engine='python', encoding='utf-8-sig')
               for k, v in paths.items()}
        print(f"  ✓ CSVs carregados para {date_str}")
        return dfs
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return None

# ── Processamento ──────────────────────────────────────────────────
def processar_dia(date_str, dfs):
    geral_raw = dfs['geral']
    esc_raw   = dfs['esc']
    cart_raw  = dfs['cart']

    # ── Mapeamento colunas GERAL ──
    g = fex(geral_raw, {
        # Odds
        'odds_h': 11, 'odds_d': 12, 'odds_a': 13,
        # Over 1.5
        'over15_h': 17, 'over15_a': 18, 'over15_g': 22,
        # Over 2.5
        'over25_h': 20, 'over25_a': 21, 'over25_g': 30,
        # H2H
        'h2h_goals': 24, 'h2h_n': 25,
        # Médias de gols marcados/sofridos
        'avg_sc_h': 26, 'avg_sc_a': 27,
        'avg_co_h': 28, 'avg_co_a': 29,
        # Liga média gols
        'avg_goals_league': 34,
        # PPG
        'ppg_h': 38, 'ppg_a': 39,
        # Under 2.5
        'under25_h': 43, 'under25_a': 44,
        # xG
        'exg_h': 51, 'exg_a': 52,
        # xGA
        'xga_h': 53, 'xga_a': 54,
        # BTTS
        'btts_h': 58, 'btts_a': 59,
        # Finalizações por time
        'shots_h': 60, 'shots_a': 61,
        'shots_ot_h': 62, 'shots_ot_a': 63,
        # Total shots médio (liga/ambos)
        'avg_total_shots': 35,
        # Dangerous attacks
        'avg_da': 37,
        # Over 0.5 HT e Over 1.5 HT
        'over05_ht': 65, 'over15_ht': 66,
    })

    # ── Mapeamento colunas ESCANTEIOS ──
    e = fex(esc_raw, {
        'avg_corners_h': 33, 'avg_corners_a': 34,
        'avg_corners_total': 37,
        'over65_c': 48, 'over75_c': 49, 'over85_c': 50,
        'over95_c': 51, 'over105_c': 52,
        'avg_shots': 67,
    })

    # ── Mapeamento colunas CARTÕES ──
    c = fex(cart_raw, {
        'avg_cards_h': 29, 'avg_cards_a': 30,
        'avg_cards_total': 28,
        'over25_cards': 47, 'over35_cards': 48, 'over45_cards': 49,
    })

    # Garantir colunas mesmo se vazio
    for col in ['avg_corners_h','avg_corners_a','avg_corners_total',
                'over65_c','over75_c','over85_c','over95_c','over105_c','avg_shots']:
        if col not in e.columns: e[col] = np.nan
    for col in ['avg_cards_h','avg_cards_a','avg_cards_total',
                'over25_cards','over35_cards','over45_cards']:
        if col not in c.columns: c[col] = np.nan

    # ── Merge ──
    m = (g
         .merge(e[['home','away','league',
                   'avg_corners_h','avg_corners_a','avg_corners_total',
                   'over65_c','over75_c','over85_c','over95_c','over105_c','avg_shots']],
                on=['home','away','league'], how='left')
         .merge(c[['home','away','league',
                   'avg_cards_h','avg_cards_a','avg_cards_total',
                   'over25_cards','over35_cards','over45_cards']],
                on=['home','away','league'], how='left'))

    results = []
    for _, r in m.iterrows():
        # ── Extrair valores brutos ──
        o15g   = s(r.get('over15_g'));  o15h = s(r.get('over15_h'));  o15a = s(r.get('over15_a'))
        o25g   = s(r.get('over25_g'));  o25h = s(r.get('over25_h'));  o25a = s(r.get('over25_a'))
        ppg_h  = s(r.get('ppg_h'));     ppg_a = s(r.get('ppg_a'))
        exg_h  = s(r.get('exg_h'));     exg_a = s(r.get('exg_a'))
        xga_h  = s(r.get('xga_h'));     xga_a = s(r.get('xga_a'))
        h2h_g  = s(r.get('h2h_goals')); h2h_n = s(r.get('h2h_n'))
        avg_sc_h = s(r.get('avg_sc_h'));avg_sc_a = s(r.get('avg_sc_a'))
        avg_co_h = s(r.get('avg_co_h'));avg_co_a = s(r.get('avg_co_a'))
        btts_h = s(r.get('btts_h'));    btts_a = s(r.get('btts_a'))
        avg_gl = s(r.get('avg_goals_league'))
        shots_h= s(r.get('shots_h'));   shots_a = s(r.get('shots_a'))
        sot_h  = s(r.get('shots_ot_h'));sot_a = s(r.get('shots_ot_a'))
        avg_ts = s(r.get('avg_total_shots'))
        avg_da = s(r.get('avg_da'))
        o05ht  = s(r.get('over05_ht')); o15ht = s(r.get('over15_ht'))
        u25h   = s(r.get('under25_h')); u25a  = s(r.get('under25_a'))
        avg_c  = s(r.get('avg_corners_total'))
        ch     = s(r.get('avg_corners_h')); ca = s(r.get('avg_corners_a'))
        o65c   = s(r.get('over65_c')); o75c = s(r.get('over75_c'))
        o85c   = s(r.get('over85_c')); o95c = s(r.get('over95_c')); o105c = s(r.get('over105_c'))
        avg_shots = s(r.get('avg_shots'))
        avg_cards = s(r.get('avg_cards_total'))
        ch_cards  = s(r.get('avg_cards_h')); ca_cards = s(r.get('avg_cards_a'))
        o25cards  = s(r.get('over25_cards'))
        o35cards  = s(r.get('over35_cards'))
        o45cards  = s(r.get('over45_cards'))

        # ── Derivados ──
        exg_tot   = avg_nn(exg_h, exg_a) and (exg_h + exg_a) if (exg_h is not None and exg_a is not None) else None
        if exg_h is not None and exg_a is not None:
            exg_tot = exg_h + exg_a
        ppg_vals  = [x for x in [ppg_h, ppg_a] if x is not None]
        ppg_avg   = float(np.mean(ppg_vals)) if ppg_vals else None
        ppg_min   = min(ppg_vals) if ppg_vals else 0
        o15cf     = avg_nn(o15h, o15a)
        o25cf     = avg_nn(o25h, o25a)
        af_avg    = avg_nn(avg_sc_h, avg_sc_a)  # média gols marcados (ataque)
        btts_cf   = avg_nn(btts_h, btts_a)
        u25cf     = avg_nn(u25h, u25a)
        shots_tot = avg_nn(shots_h, shots_a)
        sot_tot   = avg_nn(sot_h, sot_a)
        # Modelo Poisson para xG
        prob_o15_poisson = prob_poisson(exg_tot, 2) if exg_tot else None   # P(gols >= 2)
        prob_o25_poisson = prob_poisson(exg_tot, 3) if exg_tot else None   # P(gols >= 3)
        prob_u45_poisson = (100 - prob_poisson(exg_tot, 5)) if exg_tot else None  # P(gols < 5)
        prob_u35_poisson = (100 - prob_poisson(exg_tot, 4)) if exg_tot else None  # P(gols < 4) = Under 3.5

        # ── Normalizações ──
        h2h_nv    = n(h2h_g, 0, 5)
        ppg_n     = n(ppg_avg, 0, 3)
        af_n      = n(af_avg, 0, 4)
        exg_n     = n(exg_tot, 0, 5)
        cant_n    = n(avg_c, 0, 15)
        shots_n   = n(avg_shots, 0, 40)      # escanteios CSV shots
        cards_n   = n(avg_cards, 0, 8)
        sot_n     = n(sot_tot, 0, 10)        # finalizações no alvo
        da_n      = n(avg_da, 0, 25)         # ataques perigosos
        ts_n      = n(shots_tot, 0, 20)      # total finalizações

        # ════════════════════════════════════════════════════════════
        # SCORES PROFISSIONAIS
        # ════════════════════════════════════════════════════════════

        # ── Over 1.5 Gols ──
        # Base: over15_g (30%), media conf casa/fora (18%), H2H (12%),
        #       PPG (12%), ataque (8%), xG (15%), Poisson (5%)
        if exg_n is not None:
            s15 = ws([
                (o15g,           30),
                (o15cf,          18),
                (h2h_nv,         12),
                (ppg_n,          12),
                (af_n,            8),
                (exg_n,          15),
                (prob_o15_poisson or 50, 5),
            ])
        else:
            s15 = ws([
                (o15g,  35), (o15cf, 22), (h2h_nv, 15),
                (ppg_n, 15), (af_n,  13),
            ])

        # Filtro 3 Vias (validado 88.6%)
        via1 = exg_tot is not None and exg_tot >= 4.5
        via2 = exg_tot is not None and exg_tot >= 2.0 and ppg_min >= 1.0
        via3 = exg_tot is None and (o15g or 0) >= 90 and (ppg_avg or 0) >= 2.0
        passou = via1 or via2 or via3
        via_str = "Via 1" if via1 else "Via 2" if via2 else "Via 3" if via3 else "Reprovado"

        # ── Over 2.5 Gols ──
        if exg_n is not None:
            s25 = ws([
                (o25g,              28),
                (o25cf,             18),
                (h2h_nv,            12),
                (ppg_n,             12),
                (af_n,               8),
                (exg_n,             17),
                (prob_o25_poisson or 50, 5),
            ])
        else:
            s25 = ws([
                (o25g, 35), (o25cf, 22), (h2h_nv, 15),
                (ppg_n, 15), (af_n, 13),
            ])

        # ── BTTS ──
        s_btts = ws([
            (btts_cf,  40),
            (h2h_nv,   15),
            (ppg_n,    15),
            (af_n,     15),
            (o15g,     10),
            (exg_n or 50, 5),
        ])

        # ── Over 0.5 HT ──
        # Usa diretamente o% histórico + xG parcial estimado + pressão ofensiva
        if o05ht is not None:
            s_05ht = ws([
                (o05ht,         45),
                (o15ht or 50,   15),
                (ppg_n,         15),
                (af_n,          15),
                (sot_n or 50,   10),
            ])
        else:
            s_05ht = ws([
                (ppg_n, 40), (af_n, 30), (o15g or 50, 20), (sot_n or 50, 10),
            ])

        # ── Under 4.5 Gols ──
        if prob_u45_poisson is not None:
            s_u45 = ws([
                (prob_u45_poisson, 35),
                (u25cf or 50,      25),
                (100 - (exg_n or 50), 20),
                (avg_gl or 50,     10),
                (50,               10),
            ])
        else:
            s_u45 = ws([
                (u25cf or 50, 40),
                (100 - (ppg_n or 50), 30),
                (50, 30),
            ])

        # ── Under 3.5 Gols ──
        # Mais restritivo que Under 4.5 — foca em jogos de baixa produção
        if prob_u35_poisson is not None:
            s_u35 = ws([
                (prob_u35_poisson,     45),  # Poisson é o sinal mais forte
                (u25cf or 50,          20),  # histórico under 2.5 como proxy
                (100 - (exg_n or 50),  25),  # xG baixo = melhor
                (50,                   10),  # prior conservador
            ])
        else:
            s_u35 = ws([
                (u25cf or 50,              50),
                (100 - (ppg_n or 50),      30),
                (50,                       20),
            ])
        under35_model_ok = (
            prob_u35_poisson is not None and
            exg_tot is not None and
            prob_u35_poisson >= 78 and
            exg_tot <= 2.5
        )
        under35_no_xg_ok = (
            prob_u35_poisson is None and
            exg_tot is None and
            (u25cf or 0) >= 65 and
            (ppg_avg is None or ppg_avg <= 1.6)
        )
        under35_blockers_ok = (
            (o25g is None or o25g <= 55) and
            (h2h_g is None or h2h_g <= 3.0) and
            (btts_cf is None or btts_cf <= 75)
        )
        under35_passou = s_u35 >= 75 and under35_blockers_ok and (under35_model_ok or under35_no_xg_ok)

        # ── Escanteios Over 7.5 ──
        s_esc75 = ws([
            (cant_n,             40),
            (o75c,               30),
            (shots_n,            15),
            (o65c or 50,         10),
            (ppg_n,               5),
        ])

        # ── Escanteios Over 8.5 ──
        s_esc85 = ws([
            (cant_n,             38),
            (o85c,               32),
            (shots_n,            15),
            (o75c,               10),
            (ppg_n,               5),
        ])

        # ── Cartões Over 2.5 ──
        s_cards25 = ws([
            (o25cards,   45),
            (cards_n,    35),
            (ppg_n,      10),
            (50,         10),
        ])

        # ── Cartões Over 3.5 ──
        s_cards35 = ws([
            (o35cards,   50),
            (cards_n,    30),
            (ppg_n,      10),
            (50,         10),
        ])

        # ── Score de Consistência Geral (multi-mercado) ──
        # Quanto mais mercados alinhados, maior a confiança global
        mercados_scores = [s for s in [s15, s25, s_btts, s_05ht] if s > 0]
        consistencia = float(np.std(mercados_scores)) if len(mercados_scores) > 1 else 50
        score_geral = float(np.mean(mercados_scores)) if mercados_scores else 50

        # ── Justificativa automática ──
        def justif_15():
            parts = []
            if o15g: parts.append(f"O1.5 global {o15g:.0f}%")
            if exg_tot: parts.append(f"xG total {exg_tot:.1f}")
            if ppg_avg: parts.append(f"PPG médio {ppg_avg:.1f}")
            if h2h_g: parts.append(f"H2H {h2h_g:.1f} gols/jogo")
            if via_str != "Reprovado": parts.append(f"Filtro {via_str} ✓")
            return " · ".join(parts) if parts else "Dados insuficientes"

        def justif_esc():
            parts = []
            if avg_c: parts.append(f"Média {avg_c:.1f} cant")
            if o85c: parts.append(f"O8.5: {o85c:.0f}%")
            if o75c: parts.append(f"O7.5: {o75c:.0f}%")
            return " · ".join(parts) if parts else "Dados insuficientes"

        def justif_cards():
            parts = []
            if avg_cards: parts.append(f"Média {avg_cards:.1f} cart")
            if o25cards: parts.append(f"O2.5: {o25cards:.0f}%")
            if o35cards: parts.append(f"O3.5: {o35cards:.0f}%")
            return " · ".join(parts) if parts else "Dados insuficientes"

        hora = str(r['hour'])[-5:] if str(r['hour']) != 'nan' else ''
        liga = str(r['league'])

        # ── Melhor mercado do jogo ──
        candidatos = [
            ('Over 1.5', s15, passou),
            ('Over 2.5', s25, True),
            ('BTTS',     s_btts, True),
            ('Over 0.5 HT', s_05ht, True),
            ('Under 4.5', s_u45, True),
            ('Under 3.5', s_u35, under35_passou),
            ('Esc 7.5', s_esc75, True),
            ('Cart 2.5', s_cards25, True),
        ]
        best = max(candidatos, key=lambda x: x[1] if x[2] else 0)
        best_mkt, best_score = best[0], best[1]

        jogo_out = {
            'date':   date_str,
            'jogo':   f"{r['home']} x {r['away']}",
            'liga':   liga,
            'country': str(r.get('country', '')),
            'hora':   hora,
            'home':   str(r['home']),
            'away':   str(r['away']),
            'is_elite': liga in LIGAS_ELITE,

            # Odds
            'odds_h': s(r.get('odds_h')), 'odds_d': s(r.get('odds_d')), 'odds_a': s(r.get('odds_a')),

            # Dados base
            'over15_g': o15g, 'over25_g': o25g,
            'exg_h': exg_h, 'exg_a': exg_a,
            'exg_tot': round(exg_tot, 2) if exg_tot else None,
            'ppg_h': ppg_h, 'ppg_a': ppg_a,
            'ppg_avg': round(ppg_avg, 2) if ppg_avg else None,
            'ppg_min': round(ppg_min, 2),
            'h2h_goals': h2h_g,
            'btts_h': btts_h, 'btts_a': btts_a,
            'btts_cf': round(btts_cf, 1) if btts_cf else None,
            'over05_ht': o05ht, 'over15_ht': o15ht,
            'avg_shots_h': shots_h, 'avg_shots_a': shots_a,
            'avg_sot_h': sot_h, 'avg_sot_a': sot_a,
            'avg_da': avg_da,

            # Escanteios
            'avg_corners': avg_c,
            'over65_c': o65c, 'over75_c': o75c, 'over85_c': o85c,
            'over95_c': o95c, 'over105_c': o105c,

            # Cartões
            'avg_cards': avg_cards,
            'over25_cards': o25cards, 'over35_cards': o35cards, 'over45_cards': o45cards,

            # Probabilidades Poisson
            'poisson_o15': round(prob_o15_poisson, 1) if prob_o15_poisson else None,
            'poisson_o25': round(prob_o25_poisson, 1) if prob_o25_poisson else None,
            'poisson_u45': round(prob_u45_poisson, 1) if prob_u45_poisson else None,
            'poisson_u35': round(prob_u35_poisson, 1) if prob_u35_poisson else None,

            # Scores principais
            'score_15':       round(s15, 1),
            'score_25':       round(s25, 1),
            'score_btts':     round(s_btts, 1),
            'score_05ht':     round(s_05ht, 1),
            'score_u45':      round(s_u45, 1),
            'score_u35':      round(s_u35, 1),
            'score_esc75':    round(s_esc75, 1),
            'score_esc85':    round(s_esc85, 1),
            'score_cards25':  round(s_cards25, 1),
            'score_cards35':  round(s_cards35, 1),

            # Filtro e via
            'passou_filtro': bool(passou),
            'via':           via_str,
            'under35_filter': bool(under35_passou),

            # Grade profissional por mercado
            'grade_15':    grade(s15) if passou else 'D',
            'grade_25':    grade(s25),
            'grade_btts':  grade(s_btts),
            'grade_05ht':  grade(s_05ht),
            'grade_u45':   grade(s_u45),
            'grade_u35':   grade(s_u35) if under35_passou else 'D',
            'grade_esc85': grade(s_esc85),
            'grade_esc75': grade(s_esc75),
            'grade_cart25':grade(s_cards25),

            # Odd justa por mercado
            'odd_justa_15':    odd_justa(o15g),
            'odd_justa_25':    odd_justa(o25g),
            'odd_justa_btts':  odd_justa(btts_cf),
            'odd_justa_05ht':  odd_justa(o05ht),
            'odd_justa_esc85': odd_justa(o85c),
            'odd_justa_cart25':odd_justa(o25cards),

            # Melhor mercado do jogo
            'best_mkt':    best_mkt,
            'best_score':  round(best_score, 1),
            'best_grade':  grade(best_score),
            'best_risk':   risk(best_score),

            # Justificativas
            'justif_15':   justif_15(),
            'justif_esc':  justif_esc(),
            'justif_cards': justif_cards(),
        }
        results.append(jogo_out)

    return apply_cards_engine_to_matches(results)


# ── Consolidar histórico ───────────────────────────────────────────
def consolidar_historico(all_results):
    por_data = {}
    for r in all_results:
        por_data.setdefault(r['date'], []).append(r)

    index = []
    for date_str, jogos in sorted(por_data.items()):
        aprovados15  = [j for j in jogos if j['score_15'] >= 85 and j['passou_filtro']]
        aprovados_esc = [j for j in jogos if j['score_esc75'] >= 75]
        aprovados_cart = [j for j in jogos if j['score_cards25'] >= 75]
        premium = [j for j in jogos if j['best_grade'] in ('A+', 'A')]
        # Top 5 do dia por best_score
        top5 = sorted(jogos, key=lambda x: x['best_score'], reverse=True)[:5]

        dia_json = {
            'date':   date_str,
            'jogos':  jogos,
            'top5':   [j['jogo'] for j in top5],
            'palpites_snapshot': build_palpites_snapshot(jogos),
            'bilhetes_snapshot': build_bilhetes_snapshot(jogos),
            'stats': {
                'total':           len(jogos),
                'over15_aprovados': len(aprovados15),
                'esc85_aprovados':  len(aprovados_esc),
                'cart25_aprovados': len(aprovados_cart),
                'premium':          len(premium),
            }
        }
        out_path = os.path.join(OUT_DIR, f'{date_str}.json')
        if os.path.exists(out_path):
            try:
                with open(out_path, encoding='utf-8') as f:
                    old_json = json.load(f)
                if old_json.get('palpites_snapshot'):
                    dia_json['palpites_snapshot'] = old_json['palpites_snapshot']
                if old_json.get('bilhetes_snapshot'):
                    dia_json['bilhetes_snapshot'] = old_json['bilhetes_snapshot']
                for key in ('resultado_confirmado', 'resultado_stats', 'resultado_stats_full'):
                    if key in old_json:
                        dia_json[key] = old_json[key]
            except Exception:
                pass
        dia_json = attach_results_to_snapshots(dia_json)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(dia_json, f, ensure_ascii=False)

        index.append({
            'date':    date_str,
            'total':   len(jogos),
            'over15':  len(aprovados15),
            'esc85':   len(aprovados_esc),
            'cart25':  len(aprovados_cart),
            'premium': len(premium),
        })
        print(f"  ✓ {date_str} → {len(jogos)} jogos | "
              f"O1.5: {len(aprovados15)} | Esc: {len(aprovados_esc)} | "
              f"Cart: {len(aprovados_cart)} | Premium: {len(premium)}")

    with open(os.path.join(OUT_DIR, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(sorted(index, key=lambda x: x['date'], reverse=True), f, ensure_ascii=False)
    print(f"\n✓ index.json gravado com {len(index)} datas")


# ── Entry point ────────────────────────────────────────────────────
if __name__ == '__main__':
    date_dirs = sorted([
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
    ])
    if not date_dirs:
        print("Nenhuma pasta encontrada em data/csv/")
        sys.exit(0)

    print(f"Datas encontradas: {date_dirs}")
    all_results = []

    for date_str in date_dirs:
        print(f"\nProcessando {date_str}...")
        dfs = load_csvs(date_str)
        if dfs is None: continue
        try:
            results = processar_dia(date_str, dfs)
            all_results.extend(results)
            print(f"  ✓ {len(results)} jogos processados")
        except Exception as e:
            print(f"  ✗ Erro: {e}")
            import traceback; traceback.print_exc()

    if all_results:
        print(f"\nConsolidando {len(all_results)} jogos...")
        consolidar_historico(all_results)
    else:
        print("Nenhum resultado gerado.")
