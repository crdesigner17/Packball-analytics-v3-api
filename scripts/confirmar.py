"""
PackBall Analytics — Confirmador de Resultados v2.0
Busca os resultados reais na API-Football e compara com os palpites gerados.
Conta como palpite oficial apenas o best_mkt de jogos com Confiança Alta/Média (A+/A).

Uso:
  python scripts/confirmar.py --key SUA_CHAVE --date 2026-05-31
  python scripts/confirmar.py --key SUA_CHAVE --date today
"""
import os, sys, json, argparse, time
from datetime import datetime, date, timedelta
import requests
from snapshots import build_bilhetes_snapshot, build_palpites_snapshot, attach_results_to_snapshots

BASE_URL = "https://v3.football.api-sports.io"
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')

CALL_DELAY = 0.5

# Grades que contam como palpite oficial
GRADES_OFICIAIS = {'A+', 'A'}

# Mapeamento best_mkt → campo resultado
MKT_RESULTADO = {
    'Over 1.5':    'over15_ok',
    'Over 2.5':    'over25_ok',
    'BTTS':        'btts',
    'Over 0.5 HT': 'over05_ht_ok',
    'Under 4.5':   'under45_ok',
    'Under 3.5':   'under35_ok',
    'Esc 7.5':     'esc75_ok',
    'Esc 8.5':     'esc85_ok',
    'Cart 2.5':    'cart25_ok',
    'Cart 3.5':    'cart35_ok',
}

MKT_SCORE = {
    'Over 1.5':    'score_15',
    'Over 2.5':    'score_25',
    'BTTS':        'score_btts',
    'Over 0.5 HT': 'score_05ht',
    'Under 4.5':   'score_u45',
    'Under 3.5':   'score_u35',
    'Esc 7.5':     'score_esc75',
    'Esc 8.5':     'score_esc85',
    'Cart 2.5':    'score_cards25',
    'Cart 3.5':    'score_cards35',
}

# Todos os mercados para stats secundárias
MERCADOS_TODOS = {
    'Over 1.5':    {'score': 'score_15',      'min': 85, 'filtro': True},
    'Over 2.5':    {'score': 'score_25',      'min': 75, 'filtro': False},
    'BTTS':        {'score': 'score_btts',    'min': 70, 'filtro': False},
    'Over 0.5 HT': {'score': 'score_05ht',   'min': 75, 'filtro': False},
    'Under 4.5':   {'score': 'score_u45',     'min': 75, 'filtro': False},
    'Under 3.5':   {'score': 'score_u35',     'min': 75, 'filtro': False},
    'Esc 7.5':     {'score': 'score_esc75',   'min': 75, 'filtro': False},
    'Esc 8.5':     {'score': 'score_esc85',   'min': 75, 'filtro': False},
    'Cart 2.5':    {'score': 'score_cards25', 'min': 75, 'filtro': False},
    'Cart 3.5':    {'score': 'score_cards35', 'min': 75, 'filtro': False},
}

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

def buscar_resultados_api(client, date_str_api):
    print(f"\n🔍 Buscando resultados reais da API para {date_str_api}...")

    data = client.get("/fixtures", {
        "date": date_str_api,
        "status": "FT-AET-PEN",
        "timezone": "America/Sao_Paulo"
    })

    if not data or not data.get("response"):
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
            "under35_ok":   (gh_ft + ga_ft) <= 3,
            "under45_ok":   (gh_ft + ga_ft) <= 4,
            "placar":       f"{gh_ft}-{ga_ft}",
            "placar_ht":    f"{gh_ht}-{ga_ht}",
        }

        stat_data = client.get("/fixtures/statistics", {"fixture": fix["fixture"]["id"]})
        if stat_data and stat_data.get("response"):
            corners_total = 0
            cards_total   = 0
            has_corners   = False
            has_cards     = False
            for team_stat in stat_data["response"]:
                for item in team_stat.get("statistics", []):
                    t = item.get("type", "")
                    raw_v = item.get("value")
                    if raw_v is None:
                        continue
                    try: v = int(raw_v)
                    except: continue
                    if t == "Corner Kicks":
                        if v > 0:
                            has_corners = True
                        corners_total += v
                    if t in ("Yellow Cards", "Red Cards"):
                        if v > 0:
                            has_cards = True
                        cards_total += v

            resultado["corners_total"]  = corners_total if has_corners else None
            resultado["cards_total"]    = cards_total if has_cards else None
            resultado["esc75_ok"]       = corners_total > 7.5 if has_corners else None
            resultado["esc85_ok"]       = corners_total > 8.5 if has_corners else None
            resultado["cart25_ok"]      = cards_total > 2.5 if has_cards else None
            resultado["cart35_ok"]      = cards_total > 3.5 if has_cards else None
        else:
            resultado["corners_total"]  = None
            resultado["cards_total"]    = None
            resultado["esc75_ok"]       = None
            resultado["esc85_ok"]       = None
            resultado["cart25_ok"]      = None
            resultado["cart35_ok"]      = None

        key = (normalizar(home), normalizar(away))
        resultados[key] = resultado
        print(f"  ✓ {home} {resultado['placar']} {away} | "
              f"Cant:{resultado.get('corners_total','?')} "
              f"Cart:{resultado.get('cards_total','?')}")

    print(f"\n  → {len(resultados)} jogos finalizados encontrados")
    return resultados

def normalizar(nome):
    import unicodedata, re
    nome = unicodedata.normalize('NFD', nome)
    nome = ''.join(c for c in nome if unicodedata.category(c) != 'Mn')
    nome = nome.lower().strip()
    nome = re.sub(r'\s+', ' ', nome)
    for sufixo in [' fc', ' cf', ' sc', ' ac', ' fk', ' if', ' bk', ' sk']:
        nome = nome.replace(sufixo, '')
    return nome.strip()

def match_jogo(home_palpite, away_palpite, resultados):
    h = normalizar(home_palpite)
    a = normalizar(away_palpite)
    if (h, a) in resultados:
        return resultados[(h, a)]
    for (rh, ra), resultado in resultados.items():
        if (h in rh or rh in h) and (a in ra or ra in a):
            return resultado
        if (h in ra or ra in h) and (a in rh or rh in a):
            return resultado
    return None

def processar_confirmacao(date_str_api, resultados_api, data_json):
    jogos = data_json.get("jogos", [])
    nao_encontrados = []
    if not data_json.get("palpites_snapshot"):
        data_json["palpites_snapshot"] = build_palpites_snapshot(jogos)
    if not data_json.get("bilhetes_snapshot"):
        data_json["bilhetes_snapshot"] = build_bilhetes_snapshot(jogos)

    # Stats oficiais: apenas best_mkt de jogos A+/A
    stats_oficiais = {mkt: {"palpites": 0, "acertos": 0, "erros": 0, "sem_dados": 0}
                      for mkt in MKT_RESULTADO}

    # Stats secundárias: todos os mercados por threshold (para referência)
    stats_todos = {mkt: {"palpites": 0, "acertos": 0, "erros": 0, "sem_dados": 0}
                   for mkt in MERCADOS_TODOS}

    for jogo in jogos:
        resultado = match_jogo(jogo["home"], jogo["away"], resultados_api)

        if resultado is None:
            jogo["resultado"] = None
            jogo["acertos"]   = {}
            nao_encontrados.append(jogo["jogo"])
            continue

        jogo["resultado"] = resultado

        # ── Palpite oficial: usa o snapshot gerado antes do resultado ──
        # Nunca troca mercado no momento de confirmar. Se o palpite original
        # perdeu, ele continua RED mesmo que outro mercado do jogo tenha batido.
        palpite_mkt   = jogo.get("palpite_mkt") or jogo.get("best_mkt", "")
        palpite_grade = jogo.get("palpite_grade") or jogo.get("best_grade", "D")
        palpite_score = jogo.get("palpite_score")
        if palpite_score is None:
            palpite_score = jogo.get("best_score", 0)

        jogo["palpite_mkt"] = palpite_mkt
        jogo["palpite_grade"] = palpite_grade
        jogo["palpite_score"] = palpite_score

        acertos    = {}

        palpite_filtro_ok = palpite_mkt != 'Under 3.5' or jogo.get("under35_filter", False)
        if palpite_grade in GRADES_OFICIAIS and palpite_mkt in MKT_RESULTADO and palpite_filtro_ok:
            campo_res = MKT_RESULTADO[palpite_mkt]
            acertou   = resultado.get(campo_res)
            score_field = MKT_SCORE.get(palpite_mkt)
            acertos[palpite_mkt] = {
                "score":   palpite_score if palpite_score is not None else jogo.get(score_field, 0),
                "palpite": True,
                "acertou": acertou,
            }
            # Acumular stats oficiais
            if palpite_mkt in stats_oficiais:
                stats_oficiais[palpite_mkt]["palpites"] += 1
                if acertou is True:
                    stats_oficiais[palpite_mkt]["acertos"] += 1
                elif acertou is False:
                    stats_oficiais[palpite_mkt]["erros"] += 1
                else:
                    stats_oficiais[palpite_mkt]["sem_dados"] += 1

        jogo["acertos"] = acertos

        # ── Stats secundárias: todos os mercados por threshold ──
        for mkt, cfg in MERCADOS_TODOS.items():
            score    = jogo.get(cfg["score"], 0) or 0
            filtro_ok = (not cfg["filtro"]) or jogo.get("passou_filtro", False)
            if mkt == 'Under 3.5':
                filtro_ok = filtro_ok and jogo.get("under35_filter", False)
            if score >= cfg["min"] and filtro_ok:
                campo_res = MKT_RESULTADO.get(mkt)
                acertou   = resultado.get(campo_res) if campo_res else None
                stats_todos[mkt]["palpites"] += 1
                if acertou is True:
                    stats_todos[mkt]["acertos"] += 1
                elif acertou is False:
                    stats_todos[mkt]["erros"] += 1
                else:
                    stats_todos[mkt]["sem_dados"] += 1

    # Taxa de acerto
    for s in list(stats_oficiais.values()) + list(stats_todos.values()):
        validos = s["acertos"] + s["erros"]
        s["taxa"] = round(s["acertos"] / validos * 100, 1) if validos > 0 else None

    # Salvar apenas stats oficiais no JSON (usadas pelo dashboard)
    data_json["resultado_stats"]     = stats_oficiais
    data_json["resultado_stats_full"] = stats_todos  # referência completa
    data_json["resultado_confirmado"] = True
    data_json = attach_results_to_snapshots(data_json)

    if nao_encontrados:
        print(f"\n  ⚠ {len(nao_encontrados)} jogos sem resultado encontrado:")
        for j in nao_encontrados:
            print(f"     - {j}")

    return data_json, stats_oficiais, stats_todos

def imprimir_resumo(date_fmt, stats_oficiais, stats_todos):
    print(f"\n{'='*55}")
    print(f"  📊 PALPITES OFICIAIS (A+/A best_mkt) — {date_fmt}")
    print(f"{'='*55}")
    print(f"  {'Mercado':<15} {'Palp':>6} {'✓':>5} {'✗':>5} {'Taxa':>8}")
    print(f"  {'-'*43}")
    total_p = total_a = total_e = 0
    for mkt, s in stats_oficiais.items():
        if s["palpites"] == 0: continue
        taxa = f"{s['taxa']}%" if s['taxa'] is not None else "—"
        emoji = "✅" if (s['taxa'] or 0) >= 70 else "❌" if (s['taxa'] or 0) < 50 else "⚠️"
        print(f"  {emoji} {mkt:<14} {s['palpites']:>6} {s['acertos']:>5} {s['erros']:>5} {taxa:>8}")
        total_p += s["palpites"]; total_a += s["acertos"]; total_e += s["erros"]
    taxa_g = round(total_a/(total_a+total_e)*100,1) if (total_a+total_e)>0 else None
    print(f"  {'-'*43}")
    print(f"  TOTAL          {total_p:>6} {total_a:>5} {total_e:>5} {str(taxa_g)+'%' if taxa_g else '—':>8}")
    print(f"\n  📋 Referência completa (todos os mercados por threshold):")
    for mkt, s in stats_todos.items():
        if s["palpites"] == 0: continue
        taxa = f"{s['taxa']}%" if s['taxa'] is not None else "—"
        print(f"     {mkt:<14} {s['palpites']:>4}p {s['acertos']:>3}✓ {s['erros']:>3}✗ {taxa:>7}")
    print(f"{'='*55}\n")

def main():
    parser = argparse.ArgumentParser(description="PackBall Analytics — Confirmador v2.0")
    parser.add_argument("--key",  required=True)
    parser.add_argument("--date", default="yesterday")
    parser.add_argument("--no-site", action="store_true")
    args = parser.parse_args()

    if args.date == "today":
        date_api = date.today().strftime("%Y-%m-%d")
    elif args.date == "yesterday":
        date_api = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        date_api = args.date

    d = datetime.strptime(date_api, "%Y-%m-%d")
    date_fmt = d.strftime("%d-%m-%Y")

    print(f"🔎 PackBall Analytics — Confirmador v2.0")
    print(f"   Confirmando: {date_fmt} | Palpites oficiais: A+/A best_mkt")

    json_path = os.path.join(DATA_DIR, f"{date_fmt}.json")
    if not os.path.exists(json_path):
        print(f"  ✗ JSON não encontrado: {json_path}")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data_json = json.load(f)

    jogos = data_json.get("jogos", [])
    oficiais = [j for j in jogos if j.get("best_grade") in GRADES_OFICIAIS]
    print(f"   {len(jogos)} jogos no dia | {len(oficiais)} palpites oficiais A+/A")

    client = APIClient(args.key)
    resultados_api = buscar_resultados_api(client, date_api)

    if not resultados_api:
        print("\n⚠ Nenhum resultado finalizado encontrado na API.")
        sys.exit(0)

    data_json, stats_oficiais, stats_todos = processar_confirmacao(
        date_api, resultados_api, data_json
    )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data_json, f, ensure_ascii=False, indent=2)
    print(f"\n✓ JSON atualizado: {json_path}")

    imprimir_resumo(date_fmt, stats_oficiais, stats_todos)

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
