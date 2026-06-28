# Auditoria do Pipeline de Cartoes - WinMetrics

Data: 2026-06-28

## Diagnostico

O Card Engine V1 estava recebendo `null` em `avg_cards`, `over25_cards`, `over35_cards`, `over45_cards` e sem estatisticas de times porque o fluxo CSV dependia de indices fixos no `processar.py`.

Campos antigos esperados por indice:

- `avg_cards_total`: indice 28
- `avg_cards_h`: indice 29
- `avg_cards_a`: indice 30
- `over25_cards`: indice 47
- `over35_cards`: indice 48
- `over45_cards`: indice 49

Quando a exportacao do CSV muda ordem, idioma, nomes ou quantidade de colunas, esses indices deixam de apontar para as colunas de cartoes. O resultado final chega ao JSON com todos os campos de cartoes vazios.

## Correcao Implementada

O `processar.py` agora resolve colunas por nome primeiro e usa os indices antigos apenas como fallback de compatibilidade.

Campos gravados no JSON final:

- `avg_cards`
- `avg_cards_h`
- `avg_cards_a`
- `home_cards_avg`
- `away_cards_avg`
- `over25_cards`
- `over35_cards`
- `over45_cards`

Se `avg_cards_total` nao existir, `avg_cards` e calculado por `avg_cards_h` e `avg_cards_a`.

Percentuais de cartoes em escala `0-1` sao normalizados para `0-100`.

## Aliases Aceitos

`avg_cards_h`: `avg_cards_h`, `home_cards_avg`, `home avg cards`, `home cards avg`, `cards avg home`, `team_a_cards`, `cards_home`, `yellow cards home`, `casa cartoes`, `mandante cartoes`.

`avg_cards_a`: `avg_cards_a`, `away_cards_avg`, `away avg cards`, `away cards avg`, `cards avg away`, `team_b_cards`, `cards_away`, `yellow cards away`, `fora cartoes`, `visitante cartoes`.

`avg_cards_total`: `avg_cards_total`, `avg_cards`, `average cards total`, `avg total cards`, `total cards avg`, `match cards avg`, `cards per match`, `cards per game`, `media cartoes`.

`over25_cards`: `over25_cards`, `over_25_cards`, `over 2.5 cards`, `cards over 2.5`, `+2.5 cards`, `2.5+ cards`, `mais de 2.5 cartoes`.

`over35_cards`: `over35_cards`, `over_35_cards`, `over 3.5 cards`, `cards over 3.5`, `+3.5 cards`, `3.5+ cards`, `mais de 3.5 cartoes`.

`over45_cards`: `over45_cards`, `over_45_cards`, `over 4.5 cards`, `cards over 4.5`, `+4.5 cards`, `4.5+ cards`, `mais de 4.5 cartoes`.

## Relatorio Automatico

Ao executar o pipeline, o arquivo abaixo e gerado:

`docs/data/card_pipeline_column_report.json`

Ele mostra, por data:

- caminho do CSV de cartoes;
- todas as colunas reais encontradas;
- coluna usada para cada campo;
- indice usado;
- metodo (`alias`, `alias_partial`, `index_fallback`, `missing`);
- quantidade de valores nao nulos apos filtros.

## API / coletar.py

`coletar.py` continua enviando `fixture.referee` como `referee` ao Card Engine.

Se a API nao fornecer arbitro, o motor continua funcionando com:

- estatisticas dos times;
- perfil historico da liga;
- contexto da partida.

Tambem foi corrigido o calculo de cartoes recentes da API para nao gravar zero falso quando a API nao retorna estatisticas de cartoes.

## Validacao

- `npm run test:cards`: passou.
- `python -m py_compile scripts/processar.py scripts/coletar.py scripts/cards/pipeline_adapter.py`: passou.
- Teste sintetico com cabeçalhos `Home Cards Avg`, `Away Cards Avg`, `Over 2.5 Cards`, `Over 3.5 Cards`, `Over 4.5 Cards`: passou e preencheu os campos de cartoes.
