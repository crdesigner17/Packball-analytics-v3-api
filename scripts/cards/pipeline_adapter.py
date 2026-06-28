import json
import os
import subprocess
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BRIDGE_JS = os.path.join(ROOT_DIR, 'scripts', 'cards', 'run_card_engine.js')


def _card_candidate_from_patch(patch):
    market = patch.get('cards_best_mkt')
    score = patch.get('cards_best_score') or 0
    approved = bool(patch.get('cards_analysis', {}).get('approved'))
    return market, score, approved


def _risk(score):
    if score >= 88:
        return 'Muito Baixo'
    if score >= 78:
        return 'Baixo'
    if score >= 68:
        return 'Moderado'
    if score >= 58:
        return 'Arriscado'
    return 'Evitar'


def apply_cards_engine_to_match(jogo):
    enriched = apply_cards_engine_to_matches([jogo])
    return enriched[0] if enriched else jogo


def apply_cards_engine_to_matches(jogos):
    if not jogos or not os.path.exists(BRIDGE_JS):
        return jogos

    try:
        proc = subprocess.run(
            ['node', BRIDGE_JS],
            input=json.dumps(jogos, ensure_ascii=False),
            text=True,
            encoding='utf-8',
            capture_output=True,
            cwd=ROOT_DIR,
            timeout=60,
        )
    except Exception as exc:
        print(f"  ⚠ Motor de cartões indisponível: {exc}", file=sys.stderr)
        return jogos

    if proc.returncode != 0:
        print(f"  ⚠ Motor de cartões falhou: {proc.stderr.strip()}", file=sys.stderr)
        return jogos

    try:
        patches = json.loads(proc.stdout or '[]')
    except Exception as exc:
        print(f"  ⚠ Resposta inválida do motor de cartões: {exc}", file=sys.stderr)
        return jogos

    enriched = []
    for jogo, patch in zip(jogos, patches):
        item = dict(jogo)
        item.update(patch)

        market, score, approved = _card_candidate_from_patch(patch)
        if approved and market and score > (item.get('best_score') or 0):
            item['best_mkt'] = market
            item['best_score'] = round(score, 1)
            item['best_grade'] = patch.get('cards_best_grade') or item.get('best_grade')
            item['best_risk'] = _risk(score)

        enriched.append(item)

    return enriched
