# Auditoria da importacao dos CSVs PackBall

Data: 2026-06-28

## Escopo

Auditoria restrita a leitura/importacao dos CSVs PackBall no `processar.py`.

Nao foram alterados:

- Card Engine
- seletor de mercados
- regras de decisao
- pesos dos scores

## Problema

O PackBall exporta CSVs com colunas agrupadas/duplicadas, como `Casa`, `Fora` e `Global`.

Nos arquivos deste ZIP, tentar `header=[0,1]` consome a primeira partida como segunda linha de cabecalho. Por isso a importacao agora:

1. tenta ler como MultiIndex;
2. valida se a segunda linha parece cabecalho real;
3. se a segunda linha for dados de partida, volta para cabecalho simples;
4. preserva nomes e indices reais das colunas para mapeamento explicito.

## Mapeamento PackBall de Cartoes

Campos internos alimentados:

- `avg_cards_h` <- coluna 11 `Casa`
- `avg_cards_a` <- coluna 12 `Fora`
- `avg_cards` / `avg_cards_total` <- coluna 15 `Global`
- `over25_cards` <- coluna 17 `Global.2`
- `over35_cards` <- coluna 18 `Global.3`
- `over45_cards` <- coluna 19 `Global.4`
- `over55_cards` <- coluna 20 `Global.5`
- `under25_cards` <- derivado de `100 - over25_cards`
- `under35_cards` <- derivado de `100 - over35_cards`
- `under45_cards` <- derivado de `100 - over45_cards`
- `under55_cards` <- derivado de `100 - over55_cards`
- `home_cards_avg` <- alias interno de `avg_cards_h`
- `away_cards_avg` <- alias interno de `avg_cards_a`

## Relatorio Gerado pelo Pipeline

Ao executar `scripts/processar.py`, o arquivo abaixo e gerado:

`docs/data/card_pipeline_column_report.json`

Ele mostra, por data:

- caminho do CSV lido;
- modo de cabecalho detectado;
- todas as colunas por indice;
- campo interno;
- coluna PackBall usada;
- indice da coluna;
- metodo de mapeamento;
- quantidade de valores nao nulos apos filtros.

## Validacao

Com os CSVs reais do ZIP:

- `27-06-2026`: 14 jogos processados.
- `28-06-2026`: 10 jogos processados.
- `South Africa x Canada`: `avg_cards=4.3`, `avg_cards_h=2.2`, `avg_cards_a=2.4`, `over25_cards=85.0`.
- `Fortaleza x Sport Recife`: `avg_cards=5.4`, `avg_cards_h=2.9`, `avg_cards_a=2.7`, `over25_cards=90.0`.
- `team_stats.available=True` nos jogos validados.

Comandos:

- `python -m py_compile scripts/processar.py`: passou.
- `npm run test:cards`: passou.
