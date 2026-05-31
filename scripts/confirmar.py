"""
PackBall Analytics — Confirmador de Resultados v1.0
Busca os resultados reais na API-Football e compara com os palpites gerados.
Atualiza o JSON do dia com os resultados e acertos por mercado.

Uso:
  python scripts/confirmar.py --key SUA_CHAVE --date 2026-05-31
  python scripts/confirmar.py --key SUA_CHAVE --date today
"""
import os, sys, json, argparse, time
from datetime import datetime, date, timedelta
import requests

BASE_URL = "https://v3.football.api-sports.io"
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')

CALL_DELAY = 0.5  # segundos entre chamadas

# ── Thresholds por mercado ─────────────────────────────────────────
# Define quais jogos contam como "palpite dado" e como avaliar o acerto
MERCADOS = {
    'Over 1.5':    {'score': 'score_15',      'min': 85, 'filtro': True},
    'Over 2.5':    {'score': 'score_25',      'min': 75, 'filtro': False},
    'BTTS':        {'score': 'score_btts',    'min': 70, 'filtro': False},
    'Over 0.5 HT': {'score': 'score_05ht',   'min': 75, 'filtro': False},
    'Under 4.5':   {'score': 'score_u45',     'min': 75, 'filtro': False},
    'Esc 7.5':     {'score': 'score_esc75',   'min': 75, 'filtro': False},
    'Esc 8.5':     {'score': 'score_esc85',   'min': 75, 'filtro': False},
    'Cart 2.5':    {'score': 'score_cards25', 'min': 75, 'filtro': False},
    'Cart 3.5':    {'score': 'score_cards35', 'min': 75, 'filtro': False},
}

# ── HTTP helper ─────────────────────────────────────────────────────
class APIClient:
    def __init__(self, api_key):
        self.headers = {
            "x-apisports-key": api_key,
            "x-apisports-host": "v3.football.api-sports.io",
        }

    def get(self, endpoint, params=None):
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        for attempt in range(3):
            try:
                time.sleep(CALL_DELAY)
                r = requests.get(url, headers=self.headers, params=params, timeout=15)
                if r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", 60))
                    print(f"  ⚠ Rate limit — aguardando {wait}s...")
                    time.sleep(wait)
                    continue
                if r.status_code != 200:
                    return None
                data = r.json()
                if data.get("errors"):
                    print(f"  ✗ API error: {data['errors']}")
                    return None
                return data
            except Exception as e:
                if attempt == 2:
                    print(f"  ✗ Exceção: {e}")
        return None

# ── Buscar resultados reais da API ──────────────────────────────────
def buscar_resultados_api(client, date_str_api):
    """
    Busca todos os fixtures de uma data com placar final.
    Retorna dict: {(home_norm, away_norm): resultado_dict}
    """
    print(f"\n🔍 Buscando resultados reais da API para {date_str_api}...")

    data = client.get("/fixtures", {
        "date": date_str_api,
        "status": "FT-AET-PEN",  # apenas jogos finalizados
        "timezone": "America/Sao_Paulo"
    })

    if not data or not data.get("response"):
        # Tenta sem filtro de status (alguns jogos podem ter status diferente)
        data = client.get("/fixtures", {
            "date": date_str_api,
            "timezone": "America/Sao_Paulo"
        })

    if not data or not data.get("response"):
        print("  ✗ Nenhum resultado encontrado na API")
        return {}

    resultados = {}
    status_finais = {"FT", "AET", "PEN", "FT_PEN"}

    for fix in data["response"]:
        status = fix.get("fixture", {}).get("status", {}).get("short", "")
        if status not in status_finais:
            continue

        home = fix["teams"]["home"]["name"]
        away = fix["teams"]["away"]["name"]
        score = fix.get("score", {})
        ft    = score.get("fulltime", {})
        ht    = score.get("halftime", {})

        gh_ft = ft.get("home") if ft.get("home") is not None else 0
        ga_ft = ft.get("away") if ft.get("away") is not None else 0
        gh_ht = ht.get("home") if ht.get("home") is not None else 0
        ga_ht = ht.get("away") if ht.get("away") is not None else 0

        resultado = {
            "fixture_id":   fix["fixture"]["id"],
            "status":       status,
            "gols_home":    gh_ft,
            "gols_away":    ga_ft,
            "gols_total":   gh_ft + ga_ft,
            "gols_ht":      gh_ht + ga_ht,
            "btts":         gh_ft > 0 and ga_ft > 0,
            "over05_ht_ok": (gh_ht + ga_ht) >= 1,
            "over15_ok":    (gh_ft + ga_ft) >= 2,
            "over25_ok":    (gh_ft + ga_ft) >= 3,
            "under45_ok":   (gh_ft + ga_ft) <= 4,
            "placar":       f"{gh_ft}-{ga_ft}",
            "placar_ht":    f"{gh_ht}-{ga_ht}",
        }

        # Buscar estatísticas do jogo (corners + cards)
        stat_data = client.get("/fixtures/statistics", {
            "fixture": fix["fixture"]["id"]
        })
        if stat_data and stat_data.get("response"):
            corners_total = 0
            cards_total   = 0
            for team_stat in stat_data["response"]:
                for item in team_stat.get("statistics", []):
                    t = item.get("type", "")
                    v = item.get("value") or 0
                    try: v = int(v)
                    except: v = 0
                    if t == "Corner Kicks":
                        corners_total += v
                    if t in ("Yellow Cards", "Red Cards"):
                        cards_total += v

            resultado["corners_total"]  = corners_total
            resultado["cards_total"]    = cards_total
            resultado["esc75_ok"]       = corners_total > 7.5
            resultado["esc85_ok"]       = corners_total > 8.5
            resultado["cart25_ok"]      = cards_total > 2.5
            resultado["cart35_ok"]      = cards_total > 3.5
        else:
            resultado["corners_total"]  = None
            resultado["cards_total"]    = None
            resultado["esc75_ok"]       = None
            resultado["esc85_ok"]       = None
            resultado["cart25_ok"]      = None
            resultado["cart35_ok"]      = None

        # Indexar por nome normalizado para matching
        key = (normalizar(home), normalizar(away))
        resultados[key] = resultado
        print(f"  ✓ {home} {resultado['placar']} {away} | "
              f"Cant:{resultado.get('corners_total','?')} "
              f"Cart:{resultado.get('cards_total','?')}")

    print(f"\n  → {len(resultados)} jogos finalizados encontrados")
    return resultados

def normalizar(nome):
    """Normaliza nome de time para matching fuzzy."""
    import unicodedata, re
    nome = unicodedata.normalize('NFD', nome)
    nome = ''.join(c for c in nome if unicodedata.category(c) != 'Mn')
    nome = nome.lower().strip()
    nome = re.sub(r'\s+', ' ', nome)
    # Remove sufixos comuns
    for sufixo in [' fc', ' cf', ' sc', ' ac', ' fk', ' if', ' bk', ' sk']:
        nome = nome.replace(sufixo, '')
    return nome.strip()

def match_jogo(home_palpite, away_palpite, resultados):
    """Tenta encontrar o resultado correspondente ao palpite."""
    h = normalizar(home_palpite)
    a = normalizar(away_palpite)

    # Match exato
    if (h, a) in resultados:
        return resultados[(h, a)]

    # Match parcial (um nome contém o outro)
    for (rh, ra), resultado in resultados.items():
        if (h in rh or rh in h) and (a in ra or ra in a):
            return resultado
        # Invertido (improvável mas seguro)
        if (h in ra or ra in h) and (a in rh or rh in a):
            return resultado

    return None

# ── Avaliar acerto por mercado ──────────────────────────────────────
def avaliar_acerto(jogo, resultado):
    """
    Para cada mercado onde o modelo deu palpite (score >= threshold),
    verifica se o resultado confirmou.
    Retorna dict com acertos/erros por mercado.
    """
    if resultado is None:
        return {}

    mapa_resultado = {
        'Over 1.5':    resultado.get('over15_ok'),
        'Over 2.5':    resultado.get('over25_ok'),
        'BTTS':        resultado.get('btts'),
        'Over 0.5 HT': resultado.get('over05_ht_ok'),
        'Under 4.5':   resultado.get('under45_ok'),
        'Esc 7.5':     resultado.get('esc75_ok'),
        'Esc 8.5':     resultado.get('esc85_ok'),
        'Cart 2.5':    resultado.get('cart25_ok'),
        'Cart 3.5':    resultado.get('cart35_ok'),
    }

    acertos = {}
    for mkt, cfg in MERCADOS.items():
        score = jogo.get(cfg['score'], 0) or 0
        filtro_ok = (not cfg['filtro']) or jogo.get('passou_filtro', False)

        # Só avalia se o modelo deu palpite nesse mercado
        if score >= cfg['min'] and filtro_ok:
            resultado_ok = mapa_resultado.get(mkt)
            acertos[mkt] = {
                'score':     score,
                'palpite':   True,
                'acertou':   resultado_ok,   # True/False/None (sem dados)
            }

    return acertos

# ── Processar JSON do dia ───────────────────────────────────────────
def processar_confirmacao(date_str_api, resultados_api, data_json):
    """
    Itera sobre os jogos do JSON do dia, faz o match com os resultados
    e anota o acerto em cada jogo.
    """
    jogos = data_json.get("jogos", [])
    nao_encontrados = []
    stats_mercados  = {mkt: {"palpites": 0, "acertos": 0, "erros": 0, "sem_dados": 0}
                       for mkt in MERCADOS}

    for jogo in jogos:
        resultado = match_jogo(jogo["home"], jogo["away"], resultados_api)

        if resultado is None:
            jogo["resultado"] = None
            jogo["acertos"]   = {}
            nao_encontrados.append(jogo["jogo"])
            continue

        # Anotar resultado no jogo
        jogo["resultado"] = resultado
        jogo["acertos"]   = avaliar_acerto(jogo, resultado)

        # Acumular stats por mercado
        for mkt, info in jogo["acertos"].items():
            stats_mercados[mkt]["palpites"] += 1
            if info["acertou"] is True:
                stats_mercados[mkt]["acertos"] += 1
            elif info["acertou"] is False:
                stats_mercados[mkt]["erros"] += 1
            else:
                stats_mercados[mkt]["sem_dados"] += 1

    # Taxa de acerto por mercado
    for mkt, s in stats_mercados.items():
        if s["palpites"] > 0:
            validos = s["acertos"] + s["erros"]
            s["taxa"] = round(s["acertos"] / validos * 100, 1) if validos > 0 else None
        else:
            s["taxa"] = None

    data_json["resultado_stats"] = stats_mercados
    data_json["resultado_confirmado"] = True

    if nao_encontrados:
        print(f"\n  ⚠ {len(nao_encontrados)} jogos sem resultado encontrado:")
        for j in nao_encontrados:
            print(f"     - {j}")

    return data_json, stats_mercados

# ── Imprimir resumo ─────────────────────────────────────────────────
def imprimir_resumo(date_fmt, stats):
    print(f"\n{'='*55}")
    print(f"  📊 RESULTADOS — {date_fmt}")
    print(f"{'='*55}")
    print(f"  {'Mercado':<15} {'Palpites':>8} {'Acertos':>8} {'Erros':>8} {'Taxa':>8}")
    print(f"  {'-'*51}")

    for mkt, s in stats.items():
        if s["palpites"] == 0:
            continue
        taxa = f"{s['taxa']}%" if s['taxa'] is not None else "—"
        emoji = "✅" if (s['taxa'] or 0) >= 70 else "❌" if (s['taxa'] or 0) < 50 else "⚠️"
        print(f"  {emoji} {mkt:<14} {s['palpites']:>8} {s['acertos']:>8} "
              f"{s['erros']:>8} {taxa:>8}")

    print(f"{'='*55}\n")

# ── Entry point ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PackBall Analytics — Confirmador de Resultados")
    parser.add_argument("--key",  required=True, help="Chave API-Football")
    parser.add_argument("--date", default="yesterday",
                        help="Data YYYY-MM-DD, 'today' ou 'yesterday' (padrão: ontem)")
    parser.add_argument("--no-site", action="store_true", help="Não regenerar o HTML")
    args = parser.parse_args()

    if args.date == "today":
        date_api = date.today().strftime("%Y-%m-%d")
    elif args.date == "yesterday":
        date_api = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        date_api = args.date

    # Converter para formato do JSON (DD-MM-YYYY)
    d = datetime.strptime(date_api, "%Y-%m-%d")
    date_fmt = d.strftime("%d-%m-%Y")

    print(f"🔎 PackBall Analytics — Confirmador v1.0")
    print(f"   Confirmando resultados de: {date_fmt}")

    # Carregar JSON do dia
    json_path = os.path.join(DATA_DIR, f"{date_fmt}.json")
    if not os.path.exists(json_path):
        print(f"  ✗ JSON não encontrado: {json_path}")
        print(f"    Execute coletar.py para essa data primeiro.")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data_json = json.load(f)

    jogos = data_json.get("jogos", [])
    print(f"   {len(jogos)} jogos no JSON do dia")

    # Buscar resultados na API
    client = APIClient(args.key)
    resultados_api = buscar_resultados_api(client, date_api)

    if not resultados_api:
        print("\n⚠ Nenhum resultado finalizado encontrado na API.")
        print("  (Jogos podem ainda estar em andamento ou a data está incorreta)")
        sys.exit(0)

    # Processar e anotar
    data_json, stats = processar_confirmacao(date_api, resultados_api, data_json)

    # Salvar JSON atualizado
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data_json, f, ensure_ascii=False, indent=2)
    print(f"\n✓ JSON atualizado: {json_path}")

    # Resumo no log
    imprimir_resumo(date_fmt, stats)

    # Regenerar site
    if not args.no_site:
        site_script = os.path.join(os.path.dirname(__file__), "gerar_site.py")
        if os.path.exists(site_script):
            import subprocess
            result = subprocess.run([sys.executable, site_script],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                print(result.stdout.strip())
            else:
                print(f"⚠ Erro ao gerar site: {result.stderr}")

    print(f"\n✅ Confirmação concluída!")

if __name__ == "__main__":
    main()
