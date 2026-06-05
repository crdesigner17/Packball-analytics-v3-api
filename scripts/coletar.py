"""
PackBall Analytics — Coletor API-Football v3.0
Substitui completamente os CSVs. Puxa dados direto da API-Football,
calcula todos os scores do modelo e grava o JSON final.

Endpoints utilizados:
  GET /fixtures?date=YYYY-MM-DD&league=X&season=Y   → fixtures do dia
  GET /fixtures/statistics?fixture=ID               → shots, corners, cards (histórico não disponível pre-match)
  GET /fixtures/headtohead?h2h=ID1-ID2              → H2H
  GET /fixtures/predictions?fixture=ID              → odds implícitas + winner
  GET /odds?fixture=ID&bookmaker=6                  → odds 1X2, over/under
  GET /teams/statistics?team=ID&league=L&season=S   → médias sazonais (gols, cantos, cartões, PPG, xG)

Fluxo por jogo:
  1. Listar fixtures do dia por liga
  2. Para cada fixture: buscar team/statistics de ambos os times
  3. Buscar H2H dos últimos 10 jogos
  4. Buscar odds (1X2 + over 1.5/2.5/corners/cards)
  5. Buscar predictions (win prob + advice)
  6. Calcular scores exatamente como processar.py
  7. Gravar JSON em docs/data/DD-MM-YYYY.json

Uso:
  python scripts/coletar.py --date 2026-05-31 --key SUA_CHAVE
  python scripts/coletar.py --date today --key SUA_CHAVE
  python scripts/coletar.py --key SUA_CHAVE          # usa data de hoje
"""
import os, sys, json, time, argparse
from datetime import datetime, date
import requests
import numpy as np
from ligas_config import blocked_name, favorite_league_names
from snapshots import build_bilhetes_snapshot, build_palpites_snapshot, attach_results_to_snapshots

# ── Configuração ────────────────────────────────────────────────────
BASE_URL  = "https://v3.football.api-sports.io"
OUT_DIR   = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
os.makedirs(OUT_DIR, exist_ok=True)

# Ligas suportadas → (league_id, nome, tier, season)
# Ligas europeias: season=2025 (temporada 2025/26)
# Ligas sul-americanas: season=2026 (calendário jan-dez)
LIGAS = {
    # Europa (temporada 2025/26 → season=2025)
    2:   ("Champions League",   "elite",  2025),
    3:   ("Europa League",      "elite",  2025),
    39:  ("Premier League",     "elite",  2025),
    135: ("Serie A",            "elite",  2025),
    140: ("La Liga",            "elite",  2025),
    78:  ("Bundesliga",         "elite",  2025),
    61:  ("Ligue 1",            "elite",  2025),
    88:  ("Eredivisie",         "normal", 2025),
    94:  ("Liga Portugal",      "normal", 2025),
    283: ("Superliga",          "normal", 2025),
    203: ("Super Lig",          "normal", 2025),
    # América do Sul (calendário jan-dez → season=2026)
    13:  ("Copa Libertadores",  "elite",  2026),
    1:   ("FIFA World Cup",     "elite",  2026),
    71:  ("Serie A",            "normal", 2026),  # Brasileirão
    72:  ("Serie B",            "normal", 2026),
    73:  ("Serie C",            "normal", 2026),
    75:  ("Copa do Brasil",     "normal", 2026),
    128: ("Liga Profesional de Fútbol", "normal", 2026),
    131: ("Copa Uruguay",       "normal", 2026),
    74:  ("Copa do Nordeste",   "normal", 2026),
    # Amistosos / Seleções
    10:  ("Friendlies",               "normal", 2026),
    960: ("UEFA Nations League",      "normal", 2025),
    29:  ("CONMEBOL Qualifiers",      "normal", 2026),
    32:  ("FIFA World Cup - Qualification South America", "normal", 2026),
}

LIGAS_PERMITIDAS = favorite_league_names(info[0] for info in LIGAS.values())
LIGAS = {
    league_id: info
    for league_id, info in LIGAS.items()
    if info[0] in LIGAS_PERMITIDAS
}

LIGAS_ELITE_IDS = {lid for lid, (nome, tier, season) in LIGAS.items() if tier == "elite"}

SEASON = 2025  # fallback — cada liga usa seu próprio season

# Retry / rate-limit
MAX_RETRIES   = 3
RETRY_DELAY   = 2.0   # segundos entre retries
CALL_DELAY    = 0.5   # segundos entre chamadas — ~120/min, dentro do limite de 300/min

# ── HTTP helper ─────────────────────────────────────────────────────
class APIClient:
    def __init__(self, api_key: str):
        self.headers = {
            "x-apisports-key": api_key,
            "x-apisports-host": "v3.football.api-sports.io",
        }
        self._calls = 0

    def get(self, endpoint: str, params: dict = None) -> dict | None:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(CALL_DELAY)
                r = requests.get(url, headers=self.headers, params=params, timeout=15)
                self._calls += 1
                if r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", 60))
                    print(f"  ⚠ Rate limit — aguardando {wait}s...")
                    time.sleep(wait)
                    continue
                if r.status_code != 200:
                    print(f"  ✗ HTTP {r.status_code} em {endpoint} params={params}")
                    return None
                data = r.json()
                if data.get("errors"):
                    print(f"  ✗ API error: {data['errors']}")
                    return None
                return data
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  ✗ Exceção em {endpoint}: {e}")
        return None

    def remaining(self) -> tuple[int, int]:
        """Retorna (used, limit) da conta."""
        data = self.get("/status")
        if data:
            sub = data.get("response", {}).get("subscription", {})
            req = data.get("response", {}).get("requests", {})
            return req.get("current", 0), req.get("limit_day", 0)
        return 0, 0

# ── Helpers matemáticos ─────────────────────────────────────────────
def s(v):
    try:
        f = float(v)
        return None if (f != f) else f  # NaN check
    except: return None

def n(v, mn, mx):
    try:
        f = float(v)
        if f != f: return None
        return max(0., min(100., (f - mn) / (mx - mn) * 100))
    except: return None

def ws(pairs):
    vv, ww = [], []
    for v, w in pairs:
        try:
            f = float(v)
            if f == f: vv.append(f); ww.append(w)
        except: pass
    return sum(x*y for x,y in zip(vv,ww)) / sum(ww) if ww else 0

def avg_nn(*vals):
    vv = [v for v in vals if v is not None]
    return float(np.mean(vv)) if vv else None

def grade(score):
    if score >= 85: return 'A+'
    if score >= 75: return 'A'
    if score >= 65: return 'B'
    if score >= 50: return 'C'
    return 'D'

def risk(score):
    if score >= 85: return 'Confiança Alta'
    if score >= 75: return 'Confiança Média'
    if score >= 65: return 'Moderado'
    if score >= 50: return 'Arriscado'
    return 'Evitar'

def odd_justa(prob_pct):
    if prob_pct and prob_pct > 0:
        return round(100 / prob_pct, 2)
    return None

def prob_poisson(lam, k_min):
    if lam is None or lam <= 0: return None
    prob, fac = 0.0, 1
    for k in range(k_min):
        if k > 0: fac *= k
        prob += (lam**k * np.exp(-lam)) / fac
    return max(0., min(100., (1 - prob) * 100))

# ── Coleta de estatísticas de time ──────────────────────────────────
def get_team_stats(client: APIClient, team_id: int, league_id: int, season: int) -> dict:
    """
    GET /teams/statistics → médias sazonais do time.
    Retorna dict com: ppg, avg_scored, avg_conceded, avg_corners,
                      avg_cards, over15_pct, over25_pct, btts_pct,
                      xg_avg, form (últimos 5 jogos)
    """
    data = client.get("/teams/statistics", {
        "team": team_id, "league": league_id, "season": season
    })
    if not data or not data.get("response"):
        return {}

    r = data["response"]
    goals   = r.get("goals", {})
    fixtures_played = r.get("fixtures", {}).get("played", {})
    played_total = (fixtures_played.get("home", 0) or 0) + (fixtures_played.get("away", 0) or 0)

    # PPG (pontos por jogo) — wins/draws
    wins   = r.get("fixtures", {}).get("wins", {})
    draws  = r.get("fixtures", {}).get("draws", {})
    w_total = (wins.get("home", 0) or 0) + (wins.get("away", 0) or 0)
    d_total = (draws.get("home", 0) or 0) + (draws.get("away", 0) or 0)
    ppg = round((w_total*3 + d_total) / played_total, 2) if played_total > 0 else None

    # Gols marcados / sofridos
    scored_avg   = s(goals.get("for",  {}).get("average", {}).get("total"))
    conceded_avg = s(goals.get("against", {}).get("average", {}).get("total"))

    # Over 1.5 e Over 2.5 por jogo — calculado a partir dos totais
    # API retorna goals.for.total.total e goals.against.total.total
    scored_total   = s(goals.get("for",  {}).get("total", {}).get("total"))
    conceded_total = s(goals.get("against", {}).get("total", {}).get("total"))

    # BTTS, corners, cards — disponíveis em alguns planos via /teams/statistics
    # Campos extras: biggest, clean_sheet, failed_to_score, penalty, lineups
    biggest = r.get("biggest", {})
    clean   = r.get("clean_sheet", {})
    cs_total = (clean.get("home", 0) or 0) + (clean.get("away", 0) or 0)
    btts_pct = round((1 - cs_total/played_total) * 100, 1) if played_total > 0 else None

    # Form (últimos 5 — string "WWDLL")
    form_str = r.get("form", "") or ""
    form5    = form_str[-5:] if len(form_str) >= 5 else form_str

    return {
        "ppg":           ppg,
        "avg_scored":    scored_avg,
        "avg_conceded":  conceded_avg,
        "btts_pct":      btts_pct,
        "form5":         form5,
        "played":        played_total,
        "wins":          w_total,
        "draws":         d_total,
    }

# ── Coleta H2H ─────────────────────────────────────────────────────
def get_h2h(client: APIClient, h2h_str: str, n: int = 10) -> dict:
    """
    GET /fixtures/headtohead?h2h=ID1-ID2&last=N
    Retorna: avg_goals, over15_pct, over25_pct, btts_pct, n_games
    """
    data = client.get("/fixtures/headtohead", {"h2h": h2h_str, "last": n})
    if not data or not data.get("response"):
        return {}

    jogos = data["response"]
    if not jogos:
        return {}

    gols_total, o15, o25, btts = 0, 0, 0, 0
    for jogo in jogos:
        score = jogo.get("score", {}).get("fulltime", {})
        gh = score.get("home") or 0
        ga = score.get("away") or 0
        total = gh + ga
        gols_total += total
        if total >= 2: o15 += 1
        if total >= 3: o25 += 1
        if gh > 0 and ga > 0: btts += 1

    n_j = len(jogos)
    return {
        "h2h_goals":    round(gols_total / n_j, 2) if n_j > 0 else None,
        "h2h_over15":   round(o15 / n_j * 100, 1) if n_j > 0 else None,
        "h2h_over25":   round(o25 / n_j * 100, 1) if n_j > 0 else None,
        "h2h_btts":     round(btts / n_j * 100, 1) if n_j > 0 else None,
        "h2h_n":        n_j,
    }

# ── Coleta Odds ────────────────────────────────────────────────────
def get_odds(client: APIClient, fixture_id: int) -> dict:
    """
    GET /odds?fixture=ID&bookmaker=6  (bookmaker 6 = Bet365)
    Extrai: odds 1X2, over 1.5/2.5, corners 8.5, cards 2.5
    """
    data = client.get("/odds", {"fixture": fixture_id, "bookmaker": 6})
    if not data or not data.get("response"):
        # Tenta sem especificar bookmaker
        data = client.get("/odds", {"fixture": fixture_id})
    if not data or not data.get("response"):
        return {}

    result = {}
    for bm in data["response"]:
        for bet in bm.get("bookmakers", [{}])[0].get("bets", []):
            name = bet.get("name", "").lower()
            vals = {str(v["value"]).lower(): s(v.get("odd")) for v in bet.get("values", [])}

            if "match winner" in name:
                result["odds_h"] = vals.get("home")
                result["odds_d"] = vals.get("draw")
                result["odds_a"] = vals.get("away")

            elif "goals over/under" in name:
                result["odds_o15"] = vals.get("over 1.5")
                result["odds_o25"] = vals.get("over 2.5")
                result["odds_u45"] = vals.get("under 4.5")

            elif "corner" in name and "over/under" in name:
                for k, v in vals.items():
                    if "over 7.5" in k:  result["odds_corners_75"] = v
                    if "over 8.5" in k:  result["odds_corners_85"] = v

            elif "card" in name and "over/under" in name:
                for k, v in vals.items():
                    if "over 2.5" in k:  result["odds_cards_25"] = v
                    if "over 3.5" in k:  result["odds_cards_35"] = v

    # Converter odds para probabilidades implícitas (sem margem)
    def to_prob(odd): return round(100 / odd, 1) if odd and odd > 1 else None

    if result.get("odds_h") and result.get("odds_d") and result.get("odds_a"):
        margin = sum(1/o for o in [result["odds_h"], result["odds_d"], result["odds_a"]] if o)
        if margin > 0:
            result["prob_h"]   = round(100 / result["odds_h"] / margin * 100, 1)
            result["prob_d"]   = round(100 / result["odds_d"] / margin * 100, 1)
            result["prob_a"]   = round(100 / result["odds_a"] / margin * 100, 1)

    return result

# ── Coleta Predictions ─────────────────────────────────────────────
def get_predictions(client: APIClient, fixture_id: int) -> dict:
    """
    GET /predictions?fixture=ID
    Extrai: over15_pct, over25_pct, under25_pct, btts_pct, win_home, win_away, xg_h, xg_a
    """
    data = client.get("/predictions", {"fixture": fixture_id})
    if not data or not data.get("response"):
        return {}

    r = data["response"][0] if data["response"] else {}
    pred     = r.get("predictions", {})
    percent  = pred.get("percent", {})
    teams    = r.get("teams", {})
    comp     = r.get("comparison", {})
    under25  = pred.get("under_over", {})

    result = {
        "pred_winner": pred.get("winner", {}).get("name"),
        "pred_advice": pred.get("advice"),
        "over15_pct":  None,
        "over25_pct":  None,
        "btts_pct":    None,
        "under25_pct": None,
    }

    # Percent vem como {"home":"45%","draw":"25%","away":"30%"}
    def pct_to_float(v):
        try: return float(str(v).replace("%","").strip())
        except: return None

    result["win_home"] = pct_to_float(percent.get("home"))
    result["win_draw"] = pct_to_float(percent.get("draws"))
    result["win_away"] = pct_to_float(percent.get("away"))

    # Goals comparison — pode conter over/under implícito
    goals_h = comp.get("goals_h2h", {})
    goals_a = comp.get("goals", {})

    # under_over field (se disponível no plano)
    uo = under25 if isinstance(under25, dict) else {}
    result["over15_pct"]  = pct_to_float(uo.get("over", {}).get("1.5") if isinstance(uo.get("over"), dict) else None) or pct_to_float(uo.get("1.5"))
    result["over25_pct"]  = pct_to_float(uo.get("over", {}).get("2.5") if isinstance(uo.get("over"), dict) else None) or pct_to_float(uo.get("2.5"))
    result["under25_pct"] = pct_to_float(uo.get("under", {}).get("2.5") if isinstance(uo.get("under"), dict) else None)
    goals_pred = pred.get("goals", {})
    result["btts_pct"]    = pct_to_float(goals_pred.get("both") if isinstance(goals_pred, dict) else None)

    # Ataque/defesa relativo (0-100) que a API fornece
    att_h = pct_to_float(comp.get("att", {}).get("home"))
    att_a = pct_to_float(comp.get("att", {}).get("away"))
    def_h = pct_to_float(comp.get("def", {}).get("home"))
    def_a = pct_to_float(comp.get("def", {}).get("away"))
    result["att_h"] = att_h
    result["att_a"] = att_a
    result["def_h"] = def_h
    result["def_a"] = def_a

    return result

# ── Coleta estatísticas de fixture (shots, corners, cards de jogos recentes) ──
def get_recent_fixture_stats(client: APIClient, team_id: int, league_id: int, season: int, n: int = 10) -> dict:
    """
    Busca últimos N fixtures do time e calcula médias de:
    corners, cards, shots, xG por jogo.

    GET /fixtures?team=ID&league=L&season=S&last=N
    Para cada fixture: GET /fixtures/statistics?fixture=FID
    """
    data = client.get("/fixtures", {
        "team": team_id, "league": league_id,
        "season": season, "last": n, "status": "FT"
    })
    if not data or not data.get("response"):
        return {}

    fixtures = data["response"]
    if not fixtures:
        return {}

    corners_list, cards_list, shots_list, sot_list = [], [], [], []
    goals_ht_list, over05ht_list, over15ht_list = [], [], []

    for fix in fixtures[:n]:
        fid = fix["fixture"]["id"]
        stat_data = client.get("/fixtures/statistics", {"fixture": fid})
        if not stat_data or not stat_data.get("response"):
            continue

        home_stats, away_stats = {}, {}
        for team_stat in stat_data["response"]:
            tid = team_stat.get("team", {}).get("id")
            raw = {item["type"]: item["value"] for item in team_stat.get("statistics", [])}
            if tid == team_id:
                home_stats = raw
            else:
                away_stats = raw

        def stat(d, key):
            v = d.get(key)
            try: return float(str(v).replace("%","")) if v is not None else None
            except: return None

        # Corners
        ch = stat(home_stats, "Corner Kicks"); ca = stat(away_stats, "Corner Kicks")
        if ch is not None and ca is not None:
            corners_list.append(ch + ca)

        # Cards (yellow + red)
        yh = stat(home_stats, "Yellow Cards") or 0
        rh = stat(home_stats, "Red Cards") or 0
        ya = stat(away_stats, "Yellow Cards") or 0
        ra = stat(away_stats, "Red Cards") or 0
        cards_list.append(yh + rh + ya + ra)

        # Shots
        sh = stat(home_stats, "Total Shots"); sa = stat(away_stats, "Total Shots")
        if sh is not None and sa is not None:
            shots_list.append(sh + sa)

        soth = stat(home_stats, "Shots on Goal"); sota = stat(away_stats, "Shots on Goal")
        if soth is not None and sota is not None:
            sot_list.append(soth + sota)

        # Gols HT
        ght = fix.get("score", {}).get("halftime", {})
        gh_ht = (ght.get("home") or 0) + (ght.get("away") or 0)
        goals_ht_list.append(gh_ht)
        over05ht_list.append(1 if gh_ht >= 1 else 0)
        over15ht_list.append(1 if gh_ht >= 2 else 0)

    def safe_mean(lst): return round(float(np.mean(lst)), 2) if lst else None
    def safe_pct(lst):  return round(float(np.mean(lst))*100, 1) if lst else None

    n_done = len(corners_list)
    result = {
        "avg_corners":  safe_mean(corners_list),
        "avg_cards":    safe_mean(cards_list),
        "avg_shots":    safe_mean(shots_list),
        "avg_sot":      safe_mean(sot_list),
        "over05_ht":    safe_pct(over05ht_list),
        "over15_ht":    safe_pct(over15ht_list),
        "n_fixtures":   n_done,
    }

    # Over 7.5 / 8.5 / 9.5 / 10.5 corners
    if corners_list:
        for thr, key in [(6.5,"over65_c"),(7.5,"over75_c"),(8.5,"over85_c"),(9.5,"over95_c"),(10.5,"over105_c")]:
            result[key] = round(sum(1 for x in corners_list if x > thr) / len(corners_list) * 100, 1)
    else:
        for k in ["over65_c","over75_c","over85_c","over95_c","over105_c"]:
            result[k] = None

    # Over 2.5 / 3.5 / 4.5 cartões
    if cards_list:
        for thr, key in [(2.5,"over25_cards"),(3.5,"over35_cards"),(4.5,"over45_cards")]:
            result[key] = round(sum(1 for x in cards_list if x > thr) / len(cards_list) * 100, 1)
    else:
        for k in ["over25_cards","over35_cards","over45_cards"]:
            result[k] = None

    return result

# ── Score engine (idêntico ao processar.py v3.0) ────────────────────
def calcular_scores(jogo: dict) -> dict:
    o15g    = jogo.get('over15_g')
    o25g    = jogo.get('over25_g')
    o15h    = jogo.get('over15_h'); o15a = jogo.get('over15_a')
    o25h    = jogo.get('over25_h'); o25a = jogo.get('over25_a')
    ppg_h   = jogo.get('ppg_h');   ppg_a = jogo.get('ppg_a')
    exg_h   = jogo.get('exg_h');   exg_a = jogo.get('exg_a')
    h2h_g   = jogo.get('h2h_goals')
    avg_sc_h = jogo.get('avg_sc_h'); avg_sc_a = jogo.get('avg_sc_a')
    btts_h  = jogo.get('btts_h');  btts_a = jogo.get('btts_a')
    avg_c   = jogo.get('avg_corners')
    o65c    = jogo.get('over65_c'); o75c = jogo.get('over75_c'); o85c = jogo.get('over85_c')
    o95c    = jogo.get('over95_c'); o105c = jogo.get('over105_c')
    avg_shots = jogo.get('avg_shots')
    avg_cards = jogo.get('avg_cards')
    o25cards  = jogo.get('over25_cards'); o35cards = jogo.get('over35_cards')
    o05ht     = jogo.get('over05_ht');    o15ht = jogo.get('over15_ht')
    u25h      = jogo.get('under25_h');    u25a  = jogo.get('under25_a')
    avg_sot   = jogo.get('avg_sot')

    # Derivados
    exg_tot  = (exg_h + exg_a) if (exg_h and exg_a) else None
    ppg_vals = [x for x in [ppg_h, ppg_a] if x is not None]
    ppg_avg  = float(np.mean(ppg_vals)) if ppg_vals else None
    ppg_min  = min(ppg_vals) if ppg_vals else 0
    o15cf    = avg_nn(o15h, o15a)
    o25cf    = avg_nn(o25h, o25a)
    af_avg   = avg_nn(avg_sc_h, avg_sc_a)
    btts_cf  = avg_nn(btts_h, btts_a)
    u25cf    = avg_nn(u25h, u25a)
    sot_n    = n(avg_sot, 0, 20) if avg_sot else None

    prob_o15 = prob_poisson(exg_tot, 2) if exg_tot else None
    prob_o25 = prob_poisson(exg_tot, 3) if exg_tot else None
    prob_u45 = (100 - prob_poisson(exg_tot, 5)) if exg_tot else None
    prob_u35 = (100 - prob_poisson(exg_tot, 4)) if exg_tot else None

    # Normalizações
    h2h_nv = n(h2h_g, 0, 5)
    ppg_n  = n(ppg_avg, 0, 3)
    af_n   = n(af_avg, 0, 4)
    exg_n  = n(exg_tot, 0, 5)
    cant_n = n(avg_c, 0, 15)
    shots_n= n(avg_shots, 0, 40)
    cards_n= n(avg_cards, 0, 8)

    # Over 1.5 — Modo API
    # score_15 = over15_g (probabilidade do endpoint predictions)
    # Via 4: predictions >= 85% já é filtro de qualidade da API
    s15 = float(o15g) if o15g is not None else ws([(ppg_n,50),(af_n,30),(exg_n or 50,20)])

    via1 = exg_tot is not None and exg_tot >= 4.5
    via2 = exg_tot is not None and exg_tot >= 2.0 and ppg_min >= 0.7
    via3 = exg_tot is None and (o15g or 0) >= 90 and (ppg_avg or 0) >= 1.5
    via4 = (o15g or 0) >= 85   # predictions alta = qualidade garantida pela API
    passou = via1 or via2 or via3 or via4
    via_str = "Via 1" if via1 else "Via 2" if via2 else "Via 3" if via3 else "Via 4" if via4 else "Reprovado"



    # Over 2.5
    if exg_n is not None:
        s25 = ws([(o25g,28),(o25cf,18),(h2h_nv,12),(ppg_n,12),(af_n,8),(exg_n,17),(prob_o25 or 50,5)])
    else:
        s25 = ws([(o25g,35),(o25cf,22),(h2h_nv,15),(ppg_n,15),(af_n,13)])

    s_btts    = ws([(btts_cf,40),(h2h_nv,15),(ppg_n,15),(af_n,15),(o15g,10),(exg_n or 50,5)])
    s_05ht    = ws([(o05ht,45),(o15ht or 50,15),(ppg_n,15),(af_n,15),(sot_n or 50,10)]) if o05ht else ws([(ppg_n,40),(af_n,30),(o15g or 50,20),(sot_n or 50,10)])
    s_u45     = ws([(prob_u45,35),(u25cf or 50,25),(100-(exg_n or 50),20),(50,20)]) if prob_u45 else ws([(u25cf or 50,40),(100-(ppg_n or 50),30),(50,30)])
    s_u35     = ws([(prob_u35,45),(u25cf or 50,20),(100-(exg_n or 50),25),(50,10)]) if prob_u35 else ws([(u25cf or 50,50),(100-(ppg_n or 50),30),(50,20)])
    s_esc75   = ws([(cant_n,40),(o75c,30),(shots_n,15),(o65c or 50,10),(ppg_n,5)])
    s_esc85   = ws([(cant_n,38),(o85c,32),(shots_n,15),(o75c,10),(ppg_n,5)])
    s_cards25 = ws([(o25cards,45),(cards_n,35),(ppg_n,10),(50,10)])
    s_cards35 = ws([(o35cards,50),(cards_n,30),(ppg_n,10),(50,10)])

    candidatos = [
        ('Over 1.5', s15, passou),
        ('Over 2.5', s25, True),
        ('BTTS',     s_btts, True),
        ('Over 0.5 HT', s_05ht, True),
        ('Under 4.5', s_u45, True),
            ('Under 3.5', s_u35, True),
        ('Esc 7.5', s_esc75, True),
        ('Cart 2.5', s_cards25, True),
    ]
    best = max(candidatos, key=lambda x: x[1] if x[2] else 0)

    def justif_15():
        parts = []
        if o15g:   parts.append(f"O1.5 {o15g:.0f}%")
        if exg_tot:parts.append(f"xG {exg_tot:.1f}")
        if ppg_avg:parts.append(f"PPG {ppg_avg:.1f}")
        if h2h_g:  parts.append(f"H2H {h2h_g:.1f} gols")
        if via_str != "Reprovado": parts.append(f"{via_str} ✓")
        return " · ".join(parts) or "Dados insuficientes"

    return {
        "exg_tot":     round(exg_tot,2) if exg_tot else None,
        "ppg_avg":     round(ppg_avg,2) if ppg_avg else None,
        "ppg_min":     round(ppg_min,2),
        "btts_cf":     round(btts_cf,1) if btts_cf else None,
        "poisson_o15": round(prob_o15,1) if prob_o15 else None,
        "poisson_o25": round(prob_o25,1) if prob_o25 else None,
        "poisson_u45": round(prob_u45,1) if prob_u45 else None,
                "poisson_u35": round(prob_u35,1) if prob_u35 else None,
        "score_15":    round(s15,1),
        "score_25":    round(s25,1),
        "score_btts":  round(s_btts,1),
        "score_05ht":  round(s_05ht,1),
        "score_u45":   round(s_u45,1),
        "score_esc75": round(s_esc75,1),
        "score_esc85": round(s_esc85,1),
        "score_cards25":round(s_cards25,1),
        "score_cards35":round(s_cards35,1),
        "passou_filtro": bool(passou),
        "via":           via_str,
        "grade_15":    grade(s15) if passou else 'D',
        "grade_25":    grade(s25),
        "grade_btts":  grade(s_btts),
        "grade_05ht":  grade(s_05ht),
        "grade_u45":   grade(s_u45),
                "grade_u35":   grade(s_u35),
        "grade_esc85": grade(s_esc85),
        "grade_esc75": grade(s_esc75),
        "grade_cart25":grade(s_cards25),
        "odd_justa_15":    odd_justa(o15g),
        "odd_justa_25":    odd_justa(o25g),
        "odd_justa_btts":  odd_justa(btts_cf),
        "odd_justa_05ht":  odd_justa(o05ht),
        "odd_justa_esc85": odd_justa(o85c),
        "odd_justa_cart25":odd_justa(o25cards),
        "best_mkt":    best[0],
        "best_score":  round(best[1],1),
        "best_grade":  grade(best[1]),
        "best_risk":   risk(best[1]),
        "justif_15":   justif_15(),
        "justif_esc":  f"Média {avg_c or '—'} cant · O8.5: {o85c or '—'}% · O7.5: {o75c or '—'}%",
        "justif_cards":f"Média {avg_cards or '—'} cart · O2.5: {o25cards or '—'}% · O3.5: {o35cards or '—'}%",
    }

# ── Processamento de uma data completa ──────────────────────────────
def processar_data(client: APIClient, date_str: str) -> list:
    """
    date_str: 'YYYY-MM-DD'
    Retorna lista de jogos prontos para gravar em JSON.
    """
    print(f"\n📅 Processando {date_str}...")
    results = []
    team_cache    = {}  # (team_id, league_id) → stats
    fixture_cache = {}  # fixture_id → recent stats

    for league_id, liga_info in LIGAS.items():
        liga_nome = liga_info[0]; tier = liga_info[1]
        print(f"  🏆 {liga_nome} (liga {league_id})...")

        liga_season = liga_info[2] if len(liga_info) > 2 else SEASON
        data = client.get("/fixtures", {
            "date": date_str, "league": league_id,
            "season": liga_season, "timezone": "America/Sao_Paulo"
        })
        if not data or not data.get("response"):
            print(f"     ⏭ Sem jogos")
            continue

        fixtures = data["response"]
        # Filtrar apenas status relevantes
        STATUS_OK = {"NS","1H","HT","2H","ET","P","LIVE","FT","AET","PEN"}
        fixtures = [f for f in fixtures if f.get("fixture",{}).get("status",{}).get("short","") in STATUS_OK]
        # Filtrar seleções sub-20 e sub-21
        fixtures = [f for f in fixtures if not blocked_name(
            f"{f['league']['name']} {f['teams']['home']['name']} {f['teams']['away']['name']}"
        )]

        if not fixtures:
            print(f"     ⏭ Sem fixtures válidos")
            continue

        print(f"     → {len(fixtures)} jogos")

        for fix in fixtures:
            fid     = fix["fixture"]["id"]
            home_id = fix["teams"]["home"]["id"]
            away_id = fix["teams"]["away"]["id"]
            home_nm = fix["teams"]["home"]["name"]
            away_nm = fix["teams"]["away"]["name"]
            hora    = fix["fixture"]["date"][11:16]  # "HH:MM"
            is_elite= league_id in LIGAS_ELITE_IDS

            print(f"     ⚽ {home_nm} x {away_nm} [{fid}]")

            # ── Team statistics ──
            def get_cached_stats(tid):
                key = (tid, league_id)
                if key not in team_cache:
                    team_cache[key] = get_team_stats(client, tid, league_id, liga_season)
                return team_cache[key]

            ts_h = get_cached_stats(home_id)
            ts_a = get_cached_stats(away_id)

            # ── Fixtures recentes para corners/cards/shots ──
            def get_cached_fixture_stats(tid):
                key = (tid, league_id)
                if key not in fixture_cache:
                    fixture_cache[key] = get_recent_fixture_stats(client, tid, league_id, liga_season, n=10)
                return fixture_cache[key]

            rs_h = get_cached_fixture_stats(home_id)
            rs_a = get_cached_fixture_stats(away_id)

            # ── H2H ──
            h2h_str = f"{home_id}-{away_id}"
            h2h = get_h2h(client, h2h_str, n=10)

            # ── Odds ──
            odds = get_odds(client, fid)

            # ── Predictions ──
            preds = get_predictions(client, fid)

            # ── Médias mescladas (casa + fora) ──
            avg_corners_h = rs_h.get("avg_corners"); avg_corners_a = rs_a.get("avg_corners")
            avg_corners   = avg_nn(avg_corners_h, avg_corners_a)
            avg_cards_h   = rs_h.get("avg_cards");   avg_cards_a   = rs_a.get("avg_cards")
            avg_cards     = avg_nn(avg_cards_h, avg_cards_a)
            avg_shots     = avg_nn(rs_h.get("avg_shots"),  rs_a.get("avg_shots"))
            avg_sot       = avg_nn(rs_h.get("avg_sot"),    rs_a.get("avg_sot"))

            # Over corners / cards médio entre os dois times
            def avg_over(key): return avg_nn(rs_h.get(key), rs_a.get(key))

            # Over 15 / 25 — usar predictions + team stats
            # Predictions retorna % diretamente se disponível
            o15g  = preds.get("over15_pct")
            o25g  = preds.get("over25_pct")
            btts_g= preds.get("btts_pct")
            o05ht = avg_nn(rs_h.get("over05_ht"), rs_a.get("over05_ht"))
            o15ht = avg_nn(rs_h.get("over15_ht"), rs_a.get("over15_ht"))

            # Fallback: calcular over15/25 via h2h
            if o15g is None and h2h.get("h2h_over15") is not None:
                o15g = h2h["h2h_over15"]
            if o25g is None and h2h.get("h2h_over25") is not None:
                o25g = h2h["h2h_over25"]

            # BTTS médio time + H2H
            btts_h_pct = ts_h.get("btts_pct")
            btts_a_pct = ts_a.get("btts_pct")
            if btts_g is None: btts_g = avg_nn(btts_h_pct, btts_a_pct)

            # xG — estimado via odds implícitas + PPG (sem endpoint direto no plano Free)
            # Plano Pro: disponível em /fixtures?id=X (campo goals.home/away xg)
            # Aqui: estimativa via Poisson inverso a partir das odds over 2.5
            xg_h = None; xg_a = None
            # Estimativa simples: xG ≈ PPG * 0.75 (proxy)
            if ts_h.get("ppg") and ts_a.get("ppg"):
                # Usando scored avg como proxy de xG
                xg_h = ts_h.get("avg_scored")
                xg_a = ts_a.get("avg_scored")

            # Montar objeto do jogo
            jogo = {
                "date":     date_str.replace("-","")[:4][::-1] if False else f"{date_str[8:10]}-{date_str[5:7]}-{date_str[:4]}",
                "jogo":     f"{home_nm} x {away_nm}",
                "liga":     liga_nome,
                "hora":     hora,
                "home":     home_nm,
                "away":     away_nm,
                "fixture_id": fid,
                "home_id":  home_id,
                "away_id":  away_id,
                "is_elite": is_elite,

                # Odds brutas
                "odds_h":  odds.get("odds_h"),
                "odds_d":  odds.get("odds_d"),
                "odds_a":  odds.get("odds_a"),

                # Over gols
                "over15_g": o15g,
                "over25_g": o25g,
                "over15_h": None,  # não disponível via /teams/statistics
                "over15_a": None,  # score usa over15_g como fallback
                "over25_h": None, "over25_a": None,

                # xG
                "exg_h": xg_h, "exg_a": xg_a,

                # PPG
                "ppg_h": ts_h.get("ppg"), "ppg_a": ts_a.get("ppg"),

                # H2H
                "h2h_goals": h2h.get("h2h_goals"),
                "h2h_n":     h2h.get("h2h_n"),

                # Médias ataque
                "avg_sc_h": ts_h.get("avg_scored"),
                "avg_sc_a": ts_a.get("avg_scored"),
                "avg_co_h": ts_h.get("avg_conceded"),
                "avg_co_a": ts_a.get("avg_conceded"),

                # BTTS
                "btts_h": btts_h_pct, "btts_a": btts_a_pct,

                # HT
                "over05_ht": o05ht, "over15_ht": o15ht,

                # Shots
                "avg_shots_h": rs_h.get("avg_shots"), "avg_shots_a": rs_a.get("avg_shots"),
                "avg_sot_h":   rs_h.get("avg_sot"),   "avg_sot_a":   rs_a.get("avg_sot"),
                "avg_sot":     avg_sot,
                "avg_shots":   avg_shots,

                # Corners
                "avg_corners":  avg_corners,
                "avg_corners_h": avg_corners_h,
                "avg_corners_a": avg_corners_a,
                "over65_c":  avg_over("over65_c"),
                "over75_c":  avg_over("over75_c"),
                "over85_c":  avg_over("over85_c"),
                "over95_c":  avg_over("over95_c"),
                "over105_c": avg_over("over105_c"),

                # Cards
                "avg_cards":    avg_cards,
                "avg_cards_h":  avg_cards_h,
                "avg_cards_a":  avg_cards_a,
                "over25_cards": avg_over("over25_cards"),
                "over35_cards": avg_over("over35_cards"),
                "over45_cards": avg_over("over45_cards"),

                # Predictions
                "pred_winner": preds.get("pred_winner"),
                "pred_advice": preds.get("pred_advice"),
                "win_home":    preds.get("win_home"),
                "win_away":    preds.get("win_away"),

                # Form
                "form_h": ts_h.get("form5"),
                "form_a": ts_a.get("form5"),

                # Under 2.5 (proxy)
                "under25_h": None, "under25_a": None,
            }

            # Calcular todos os scores
            scores = calcular_scores(jogo)
            jogo.update(scores)
            # Adicionar exg_tot calculado no scores
            jogo["exg_tot"] = scores.get("exg_tot")
            jogo["ppg_avg"] = scores.get("ppg_avg")
            jogo["ppg_min"] = scores.get("ppg_min")
            jogo["btts_cf"] = scores.get("btts_cf")

            results.append(jogo)
            print(f"       ✓ score_best={jogo['best_score']} ({jogo['best_grade']}) → {jogo['best_mkt']}")

    return results

# ── Gravar JSON ─────────────────────────────────────────────────────
def gravar_dia(date_str_api: str, jogos: list, force: bool = False):
    """date_str_api: YYYY-MM-DD → converte para DD-MM-YYYY no arquivo."""
    d = datetime.strptime(date_str_api, "%Y-%m-%d")
    date_fmt = d.strftime("%d-%m-%Y")

    aprovados15   = [j for j in jogos if j['score_15'] >= 85 and j['passou_filtro']]
    aprovados_esc = [j for j in jogos if j['score_esc75'] >= 75]
    aprovados_cart= [j for j in jogos if j['score_cards25'] >= 75]
    premium       = [j for j in jogos if j.get('best_grade') in ('A+','A')]

    # Preservar resultados já confirmados do JSON anterior
    out_path = os.path.join(OUT_DIR, f"{date_fmt}.json")
    resultado_confirmado = False
    resultado_stats      = {}
    resultado_stats_full = {}
    palpites_snapshot    = None
    bilhetes_snapshot    = None
    resultados_existentes = {}
    jogos_existentes_count = 0

    if os.path.exists(out_path):
        try:
            with open(out_path, encoding="utf-8") as f:
                old_json = json.load(f)
            resultado_confirmado  = old_json.get("resultado_confirmado", False)
            resultado_stats       = old_json.get("resultado_stats", {})
            resultado_stats_full  = old_json.get("resultado_stats_full", {})
            palpites_snapshot     = old_json.get("palpites_snapshot")
            bilhetes_snapshot     = old_json.get("bilhetes_snapshot")
            jogos_existentes_count = len(old_json.get("jogos", []))
            # Mapear palpites/resultados por nome do jogo. O palpite original
            # precisa sobreviver ao reprocessamento para RED continuar RED.
            for j in old_json.get("jogos", []):
                resultados_existentes[j["jogo"]] = {
                    "resultado":      j.get("resultado"),
                    "acertos":        j.get("acertos", {}),
                    "best_mkt":       j.get("best_mkt"),
                    "best_grade":     j.get("best_grade"),
                    "best_score":     j.get("best_score"),
                    "palpite_mkt":    j.get("palpite_mkt") or j.get("best_mkt"),
                    "palpite_grade":  j.get("palpite_grade") or j.get("best_grade"),
                    "palpite_score":  j.get("palpite_score", j.get("best_score")),
                }
        except:
            pass

    # Proteção: não sobrescrever se API retornou menos jogos que o existente
    # Isso evita que reprocessamentos parciais destruam dados de CSVs mais completos
    if not force and jogos_existentes_count > 0 and len(jogos) < jogos_existentes_count * 0.5:
        print(f"  ⚠ Proteção ativada: API retornou {len(jogos)} jogos vs {jogos_existentes_count} existentes.")
        print(f"  ⚠ Mantendo dados existentes para {date_fmt}. Use --force para sobrescrever.")
        return

    # Reinjetar resultados preservados nos novos jogos
    for j in jogos:
        existente = resultados_existentes.get(j["jogo"])
        if existente:
            if existente.get("resultado"):
                j["resultado"] = existente["resultado"]
                j["acertos"]   = existente["acertos"]
            if existente.get("palpite_mkt") and not force:
                j["palpite_mkt"]   = existente["palpite_mkt"]
                j["palpite_grade"] = existente["palpite_grade"]
                j["palpite_score"] = existente["palpite_score"]
                j["best_mkt"]      = existente["palpite_mkt"]
                j["best_grade"]    = existente["palpite_grade"]
                j["best_score"]    = existente["palpite_score"]
            elif existente.get("resultado") and existente.get("best_mkt"):
                j["best_mkt"]   = existente["best_mkt"]
                j["best_grade"] = existente["best_grade"]
                j["best_score"] = existente["best_score"]
                j["palpite_mkt"]   = existente.get("palpite_mkt") or existente["best_mkt"]
                j["palpite_grade"] = existente.get("palpite_grade") or existente["best_grade"]
                j["palpite_score"] = existente.get("palpite_score", existente["best_score"])

        j.setdefault("palpite_mkt", j.get("best_mkt"))
        j.setdefault("palpite_grade", j.get("best_grade"))
        j.setdefault("palpite_score", j.get("best_score"))

    if not palpites_snapshot or force:
        palpites_snapshot = build_palpites_snapshot(jogos)
    if not bilhetes_snapshot or force:
        bilhetes_snapshot = build_bilhetes_snapshot(jogos)

    dia_json = {
        "date":  date_fmt,
        "jogos": jogos,
        "top5":  [j['jogo'] for j in sorted(jogos, key=lambda x: x['best_score'], reverse=True)[:5]],
        "palpites_snapshot": palpites_snapshot,
        "bilhetes_snapshot": bilhetes_snapshot,
        "resultado_confirmado": resultado_confirmado,
        "resultado_stats":      resultado_stats,
        "resultado_stats_full": resultado_stats_full,
        "stats": {
            "total":            len(jogos),
            "over15_aprovados": len(aprovados15),
            "esc85_aprovados":  len(aprovados_esc),
            "cart25_aprovados": len(aprovados_cart),
            "premium":          len(premium),
        }
    }
    dia_json = attach_results_to_snapshots(dia_json)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dia_json, f, ensure_ascii=False, indent=2)
    print(f"\n✓ {out_path} gravado ({len(jogos)} jogos) | resultados preservados: {len(resultados_existentes)}")

    # Atualizar index.json
    index_path = os.path.join(OUT_DIR, "index.json")
    index = []
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            try: index = json.load(f)
            except: index = []

    # Remove entrada existente da mesma data
    index = [e for e in index if e.get("date") != date_fmt]
    index.append({
        "date":    date_fmt,
        "total":   len(jogos),
        "over15":  len(aprovados15),
        "esc85":   len(aprovados_esc),
        "cart25":  len(aprovados_cart),
        "premium": len(premium),
    })
    index = sorted(index, key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"), reverse=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    print(f"✓ index.json atualizado ({len(index)} datas)")

# ── Entry point ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PackBall Analytics — Coletor API-Football v3.0")
    parser.add_argument("--key",  required=True, help="Chave API-Football (x-apisports-key)")
    parser.add_argument("--date", default="today", help="Data YYYY-MM-DD ou 'today' (padrão: hoje)")
    parser.add_argument("--season", type=int, default=SEASON, help=f"Temporada (padrão: {SEASON})")
    parser.add_argument("--no-site", action="store_true", help="Não regenerar o HTML após coletar")
    parser.add_argument("--force", action="store_true", help="Forçar sobrescrita mesmo se arquivo existir")
    args = parser.parse_args()

    if args.date == "today":
        date_str = date.today().strftime("%Y-%m-%d")
    else:
        date_str = args.date

    print(f"🚀 PackBall Analytics Coletor v3.0")
    print(f"   Data: {date_str} | Temporada: {args.season}")

    client = APIClient(args.key)

    # Verificar quota
    used, limit = client.remaining()
    if limit > 0:
        print(f"   Quota API: {used}/{limit} chamadas hoje")
        if limit - used < 50:
            print(f"   ⚠ ATENÇÃO: menos de 50 chamadas restantes!")

    jogos = processar_data(client, date_str)

    if not jogos:
        print("\n⚠ Nenhum jogo encontrado/processado.")
        sys.exit(0)

    gravar_dia(date_str, jogos, force=getattr(args, "force", False))

    # Regenerar site
    if not args.no_site:
        site_script = os.path.join(os.path.dirname(__file__), "gerar_site.py")
        if os.path.exists(site_script):
            import subprocess
            result = subprocess.run([sys.executable, site_script], capture_output=True, text=True)
            if result.returncode == 0:
                print(result.stdout.strip())
            else:
                print(f"⚠ Erro ao gerar site: {result.stderr}")

    print(f"\n✅ Concluído — {len(jogos)} jogos | chamadas API: {client._calls}")

if __name__ == "__main__":
    main()
