from datetime import datetime


GRADES_OFICIAIS = {'A+', 'A'}


def odd_mkt(jogo, mkt=None):
    mkt = mkt or jogo.get('palpite_mkt') or jogo.get('best_mkt')
    field = {
        'Over 1.5': 'odds_o15',
        'Over 2.5': 'odds_o25',
        'Cart 2.5': 'odds_cards_25',
        'Cart 3.5': 'odds_cards_35',
        'Esc 7.5': 'odds_corners_75',
        'Esc 8.5': 'odds_corners_85',
        'Under 3.5': 'odds_u45',
        'Under 4.5': 'odds_u45',
    }.get(mkt)
    if not field:
        return None
    try:
        value = jogo.get(field)
        return round(float(value), 2) if value else None
    except Exception:
        return None


def snapshot_item(jogo):
    mkt = jogo.get('palpite_mkt') or jogo.get('best_mkt') or ''
    grade = jogo.get('palpite_grade') or jogo.get('best_grade') or 'D'
    score = jogo.get('palpite_score')
    if score is None:
        score = jogo.get('best_score') or 0
    return {
        'fixture_id': jogo.get('fixture_id'),
        'jogo': jogo.get('jogo'),
        'home': jogo.get('home'),
        'away': jogo.get('away'),
        'liga': jogo.get('liga'),
        'hora': jogo.get('hora'),
        'mkt': mkt,
        'score': score,
        'grade': grade,
        'oddVal': odd_mkt(jogo, mkt),
        'resultado': jogo.get('resultado'),
        'acertos': jogo.get('acertos') or {},
    }


def build_palpites_snapshot(jogos):
    items = []
    for jogo in jogos:
        jogo.setdefault('palpite_mkt', jogo.get('best_mkt'))
        jogo.setdefault('palpite_grade', jogo.get('best_grade'))
        jogo.setdefault('palpite_score', jogo.get('best_score'))
        if jogo.get('palpite_grade') in GRADES_OFICIAIS:
            items.append(snapshot_item(jogo))
    return sorted(items, key=lambda x: x.get('score') or 0, reverse=True)


def _montar(pool, min_sel=2):
    if len(pool) < min_sel:
        return None
    odd_total = 1
    for item in pool:
        odd_total *= item.get('oddVal') or 1
    return {'sels': pool, 'oddTotal': round(odd_total, 2)}


def build_bilhetes_snapshot(jogos):
    alta = build_palpites_snapshot(jogos)
    dia_pool = [x for x in alta if x.get('grade') == 'A+' and (x.get('score') or 0) >= 90][:8]
    b_dia = _montar(dia_pool)

    b1 = _montar(list(alta)[:4])
    b2 = _montar([x for x in alta if x.get('grade') == 'A+'])

    bilhetes = []
    seen = set()
    defs = [
        ('b1', b1, 'bilhete-premium', 'Premium - Todos A+/A por Score'),
        ('b2', b2, 'bilhete-conservador', 'ELITE'),
    ]
    for tipo, bilhete, cls, label in defs:
        if not bilhete:
            continue
        key = '|'.join(sorted(f"{s.get('jogo')}:{s.get('mkt')}" for s in bilhete['sels']))
        if key in seen:
            continue
        seen.add(key)
        bilhetes.append({'tipo': tipo, 'b': bilhete, 'cls': cls, 'label': label})

    return {
        'created_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'bilhetes': bilhetes,
        'bilheteDia': b_dia,
    }


def _item_key(item):
    fid = item.get('fixture_id')
    if fid:
        return ('id', str(fid))
    return ('name', f"{item.get('home')} x {item.get('away')}")


def attach_results_to_snapshots(data_json):
    jogos_by_key = {}
    for jogo in data_json.get('jogos', []):
        item = snapshot_item(jogo)
        jogos_by_key[_item_key(item)] = item

    def update_item(item):
        found = jogos_by_key.get(_item_key(item))
        if not found:
            return item
        item['resultado'] = found.get('resultado')
        item['acertos'] = found.get('acertos') or {}
        return item

    data_json['palpites_snapshot'] = [
        update_item(dict(item)) for item in data_json.get('palpites_snapshot', [])
    ]

    bilhetes_snapshot = data_json.get('bilhetes_snapshot')
    if isinstance(bilhetes_snapshot, dict):
        for item in bilhetes_snapshot.get('bilheteDia', {}).get('sels', []) if bilhetes_snapshot.get('bilheteDia') else []:
            update_item(item)
        for bilhete in bilhetes_snapshot.get('bilhetes', []):
            for item in bilhete.get('b', {}).get('sels', []):
                update_item(item)
    return data_json
