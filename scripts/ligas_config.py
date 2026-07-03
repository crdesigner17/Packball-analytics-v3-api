import csv
import os
import re
import unicodedata


BASE_DIR = os.path.dirname(__file__)

FAVORITE_LEAGUE_FILES = [
    os.path.join(BASE_DIR, 'ligas_1x2.csv'),
    os.path.join(BASE_DIR, 'ligas_gols.csv'),
    os.path.join(BASE_DIR, 'ligas_escanteios.csv'),
    os.path.join(BASE_DIR, 'ligas_cartoes.csv'),
]

EXCLUDED_KEYWORDS = [
    'women', 'womens', 'feminino', 'feminina', 'femenino', 'femenina',
    'ladies', 'frauenliga', 'wpsl', 'nwsl', 'uws',
    'u17', 'u18', 'u19', 'u20', 'u21', 'u23',
    'u-17', 'u-18', 'u-19', 'u-20', 'u-21', 'u-23',
    'under 17', 'under 18', 'under 19', 'under 20', 'under 21', 'under 23',
    'under-17', 'under-18', 'under-19', 'under-20', 'under-21', 'under-23',
    'youth', 'academy', 'reserve', 'reserves', 'reserva', 'amateur',
]

# Base antiga dos CSVs + novas ligas confirmadas. Duplicadas sao ignoradas.
EXTRA_ALLOWED_ROWS = [
    ('United States', 'Major League Soccer'),
    ('Syria', 'Premier League'),
    ('Sweden', 'Allsvenskan'),
    ('Ireland', 'Premier Division'),
    ('Ireland', 'First Division'),
    ('Paraguay', 'Division Intermedia'),
    ('New Zealand', 'National League'),
    ('Lithuania', 'A Lyga'),
    ('Latvia', 'Virsliga'),
    ('Iceland', 'Inkasso-Deildin'),
    ('Faroe Islands', 'Meistaradeildin'),
    ('Finland', 'Ykkosliiga'),
    ('Ecuador', 'LigaPro'),
    ('China PR', 'Super League'),
    ('Australia', 'Victoria Premier League 2'),
]

DENIED_ROWS = {
    ('World', 'Club Friendlies 3'),
    ('World', 'Club Friendlies 4'),
    ('United States', 'USL League Two'),
}

DENIED_LEAGUES = {
    'Club Friendlies 3',
    'Club Friendlies 4',
    'USL League Two',
}

LEAGUE_ALIASES = {
    'World Cup': ['World Cup', 'FIFA World Cup'],
    'Friendly International': ['Friendly International', 'Friendlies', 'International Friendlies'],
    'Euro Qualification': ['Euro Qualification', 'Euro Championship - Qualification'],
    'Champions League': ['Champions League', 'UEFA Champions League'],
    'Europa League': ['Europa League', 'UEFA Europa League'],
    'Europa Conference League': ['Europa Conference League', 'UEFA Conference League'],
    'Liga Profesional de Futbol': ['Liga Profesional de Futbol', 'Liga Profesional de Fútbol', 'Liga Profesional'],
    'Liga Profesional de Fútbol': ['Liga Profesional de Futbol', 'Liga Profesional de Fútbol', 'Liga Profesional'],
    '1. HNL': ['1. HNL', 'HNL'],
    'Division 1': ['Division 1', 'Primera Division', 'Primera División'],
    'Super League': ['Super League', 'Superliga'],
    'USL Championship': ['USL Championship'],
    'USL League One': ['USL League One'],
    'USL League Two': ['USL League Two'],
    'Major League Soccer': ['Major League Soccer', 'MLS'],
    'Premier Division': ['Premier Division'],
    'First Division': ['First Division'],
    '1. Division': ['1. Division'],
    'A Lyga': ['A Lyga'],
    '1. Lyga': ['1. Lyga'],
    'Ykkosliiga': ['Ykkosliiga', 'Ykkösliiga'],
    'Ykkönen': ['Ykkönen', 'Ykkonen'],
    'LigaPro': ['LigaPro', 'Liga Pro'],
}

OFFICIAL_NATIONAL_LEAGUES = {
    'World Cup',
    'FIFA World Cup',
    'FIFA World Cup - Qualification',
    'FIFA World Cup - Qualification South America',
    'CONMEBOL Qualifiers',
    'UEFA Nations League',
    'Friendly International',
    'Friendlies',
    'International Friendlies',
}


def norm_key(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()
    return re.sub(r'\s+', ' ', value)


def blocked_name(value):
    value = str(value or '').lower()
    return any(keyword in value for keyword in EXCLUDED_KEYWORDS)


def is_denied_league(country, league):
    country_key = norm_key(country)
    league_key = norm_key(league)
    denied_rows = {(norm_key(c), norm_key(l)) for c, l in DENIED_ROWS}
    denied_leagues = {norm_key(l) for l in DENIED_LEAGUES}
    return league_key in denied_leagues or (country_key, league_key) in denied_rows


def append_row(rows, seen, country, league):
    if not country or not league:
        return
    if blocked_name(country) or blocked_name(league):
        return
    if is_denied_league(country, league):
        return
    key = (country, league)
    if key in seen:
        return
    seen.add(key)
    rows.append({'country': country, 'league': league})


def read_favorite_rows():
    rows = []
    seen = set()
    for path in FAVORITE_LEAGUE_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f, delimiter=';'):
                clean = {str(k).strip(): str(v).strip() for k, v in row.items()}
                active = clean.get('Active', '').lower() in ('true', '1', 'yes', 'sim')
                country = clean.get('Country', '')
                league = clean.get('League', '')
                if not active or not league:
                    continue
                append_row(rows, seen, country, league)
    for country, league in EXTRA_ALLOWED_ROWS:
        append_row(rows, seen, country, league)
    return rows


def expand_league_names(leagues):
    expanded = set(leagues)
    pending = list(leagues)
    while pending:
        league = pending.pop()
        for alias in LEAGUE_ALIASES.get(league, []):
            if alias not in expanded:
                expanded.add(alias)
                pending.append(alias)
    expanded.update(OFFICIAL_NATIONAL_LEAGUES)
    return expanded


def league_allowed(league):
    allowed = {norm_key(row['league']) for row in read_favorite_rows()}
    allowed.update(norm_key(alias) for alias in expand_league_names({row['league'] for row in read_favorite_rows()}))
    return norm_key(league) in allowed


def is_allowed_game(country, league):
    return bool(league) and not is_denied_league(country, league) and league_allowed(league)


def favorite_league_names(extra_leagues=None):
    leagues = {row['league'] for row in read_favorite_rows()}
    if extra_leagues:
        allowed = {norm_key(league) for league in expand_league_names(leagues)}
        leagues.update(league for league in extra_leagues if norm_key(league) in allowed)
    return expand_league_names(leagues)


def favorite_countries(extra_countries=None):
    countries = {row['country'] for row in read_favorite_rows() if row['country']}
    if extra_countries:
        countries.update(extra_countries)
    return countries
