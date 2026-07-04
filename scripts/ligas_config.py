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
    'ladies', 'frauenliga', 'wpsl', 'nwsl',
    'u17', 'u18', 'u19', 'u20', 'u21', 'u23',
    'u-17', 'u-18', 'u-19', 'u-20', 'u-21', 'u-23',
    'under 17', 'under 18', 'under 19', 'under 20', 'under 21', 'under 23',
    'under-17', 'under-18', 'under-19', 'under-20', 'under-21', 'under-23',
    'youth', 'academy', 'reserve', 'reserves', 'reserva', 'amateur',
]

LEAGUE_ALIASES = {
    'World Cup': ['World Cup', 'FIFA World Cup'],
    'Friendly International': ['Friendly International', 'Friendlies', 'International Friendlies'],
    'Euro Qualification': ['Euro Qualification', 'Euro Championship - Qualification'],
    'Liga Profesional de Fútbol': ['Liga Profesional de Fútbol', 'Liga Profesional'],
    '1. HNL': ['1. HNL', 'HNL'],
    'Division 1': ['Division 1', 'Primera División'],
    'Super League': ['Super League', 'Superliga', 'Chinese Super League', 'China Super League'],
    'Veikkausliiga': ['Veikkausliiga'],
    'Copa Chile': ['Copa Chile', 'Chile Cup'],
    'Liga Pro Serie A': ['Liga Pro Serie A', 'LigaPro Serie A', 'Liga Pro', 'LigaPro'],
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


COUNTRY_ALIASES = {
    'china pr': 'china',
}

_ALLOWED_GAME_CACHE = None


def norm_key(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()
    return re.sub(r'\s+', ' ', value)


def country_key(value):
    key = norm_key(value)
    return COUNTRY_ALIASES.get(key, key)


def blocked_name(value):
    value = str(value or '').lower()
    return any(keyword in value for keyword in EXCLUDED_KEYWORDS)


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
                if blocked_name(country) or blocked_name(league):
                    continue
                key = (country, league)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({'country': country, 'league': league})
    return rows


def expand_league_names(leagues):
    expanded = set(leagues)
    for league in list(leagues):
        expanded.update(LEAGUE_ALIASES.get(league, []))
    expanded.update(OFFICIAL_NATIONAL_LEAGUES)
    return expanded


def allowed_game_sets():
    global _ALLOWED_GAME_CACHE
    if _ALLOWED_GAME_CACHE is not None:
        return _ALLOWED_GAME_CACHE

    pairs = set()
    league_only = set()
    for row in read_favorite_rows():
        country = country_key(row.get('country'))
        for league in expand_league_names({row.get('league', '')}):
            league_norm = norm_key(league)
            if not league_norm:
                continue
            if country:
                pairs.add((country, league_norm))
            league_only.add(league_norm)

    official = {norm_key(league) for league in OFFICIAL_NATIONAL_LEAGUES}
    _ALLOWED_GAME_CACHE = pairs, league_only, official
    return _ALLOWED_GAME_CACHE


def is_allowed_game(country, league):
    if blocked_name(country) or blocked_name(league):
        return False

    league_norm = norm_key(league)
    if not league_norm:
        return False

    pairs, league_only, official = allowed_game_sets()
    if league_norm in official:
        return True

    country_norm = country_key(country)
    if country_norm:
        return (country_norm, league_norm) in pairs

    return league_norm in league_only


def favorite_league_names(extra_leagues=None):
    leagues = {row['league'] for row in read_favorite_rows()}
    if extra_leagues:
        leagues.update(extra_leagues)
    return expand_league_names(leagues)


def favorite_countries(extra_countries=None):
    countries = {row['country'] for row in read_favorite_rows() if row['country']}
    if extra_countries:
        countries.update(extra_countries)
    return countries
