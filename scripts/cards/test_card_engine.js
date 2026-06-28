const assert = require("assert");
const { analyzeCardsMarket, analyzeCardsForMatches } = require("./card_engine");
const { extractCardOddsFromMatch } = require("./card_odds_service");
const { findRefereeProfile } = require("./referee_service");

function cardOdds(lines) {
  return {
    card_odds: {
      total_cards: lines.map(([line, over, under]) => ({
        line,
        over_odds: over,
        under_odds: under
      })),
      both_teams_card: { yes_odds: 1.7, no_odds: 2.1 },
      both_teams_2plus_cards: { yes_odds: 1.9, no_odds: 1.9 }
    }
  };
}

const baseHot = {
  country: "Brazil",
  league: "Serie B",
  round: "Final",
  referee: "Davi de Oliveira Lacerda",
  home_cards_avg: 3.3,
  away_cards_avg: 3.2,
  home_position: 2,
  away_position: 4,
  home_points: 58,
  away_points: 55,
  ...cardOdds([
    [2.5, 1.35, 3.2],
    [3.5, 1.55, 2.45],
    [4.5, 1.72, 2.05],
    [5.5, 1.95, 1.8],
    [6.5, 2.4, 1.5]
  ])
};

const baseCold = {
  country: "Brazil",
  league: "Serie B",
  round: "Rodada 12",
  referee: "Lucas Canetto",
  home_cards_avg: 1.4,
  away_cards_avg: 1.3,
  low_importance: true,
  ...cardOdds([
    [2.5, 2.8, 1.85],
    [3.5, 2.25, 1.8],
    [4.5, 1.8, 1.75],
    [5.5, 1.55, 1.55],
    [6.5, 1.4, 1.95]
  ])
};

function run() {
  const hotRef = findRefereeProfile("Davi Lacerda");
  assert.equal(hotRef.found, true, "match parcial de arbitro quente deve funcionar");

  const hot = analyzeCardsMarket(baseHot);
  assert.equal(hot.approved, true, "jogo quente deve aprovar algum mercado");
  assert(hot.submarkets.some((item) => item.market_key === "cards_over_55"), "jogo quente deve sustentar Over 5.5");

  const cold = analyzeCardsMarket(baseCold);
  assert.equal(cold.approved, true, "jogo frio deve aprovar under");
  assert(cold.submarkets.some((item) => item.market_key.startsWith("cards_under_")), "jogo frio deve selecionar under");

  const serieBOver = analyzeCardsMarket({
    ...baseHot,
    country: "Brazil",
    league: "Serie B",
    referee: "Davi de Oliveira Lacerda",
    home_cards_avg: 3.0,
    away_cards_avg: 3.0
  });
  assert(serieBOver.submarkets.some((item) => item.market_key === "cards_over_55"), "Serie B quente deve aprovar Over 5.5");

  const worldCup = analyzeCardsMarket({
    league: "World Cup",
    round: "Group Stage",
    referee: "Davi de Oliveira Lacerda",
    home_cards_avg: 1.8,
    away_cards_avg: 1.6,
    ...cardOdds([[2.5, 1.9, 1.9]])
  });
  assert(worldCup.submarkets.some((item) => item.market_key === "cards_over_25"), "Copa do Mundo deve aproveitar Over 2.5 quando sustentado");

  const noReferee = analyzeCardsMarket({
    ...baseHot,
    referee: ""
  });
  assert.equal(noReferee.diagnostics.referee.found, false, "jogo sem arbitro deve ser tratado");

  const noOdds = analyzeCardsMarket({
    ...baseHot,
    card_odds: undefined
  });
  assert.equal(noOdds.diagnostics.odds.available, false, "jogo sem odds deve continuar analisavel");

  const noTeamAvg = analyzeCardsMarket({
    league: "Serie A",
    referee: "Davi de Oliveira Lacerda",
    ...cardOdds([[4.5, 1.9, 1.9]])
  });
  assert.equal(noTeamAvg.diagnostics.team_stats.available, false, "jogo sem media dos times deve reduzir qualidade");

  const normalizedOdds = extractCardOddsFromMatch({
    bookmakers: [
      {
        markets: [
          {
            name: "Total de Cartoes",
            outcomes: [
              { name: "Mais de 2.5", odds: "1.70" },
              { name: "Menos de 2.5", odds: "2.05" },
              { name: "Mais de 5.5", odds: "2.10" },
              { name: "Menos de 5.5", odds: "1.65" }
            ]
          }
        ]
      }
    ]
  });
  assert.deepEqual(normalizedOdds.total_cards.map((item) => item.line), [2.5, 5.5], "odds com multiplas linhas devem ser normalizadas");

  const batch = analyzeCardsForMatches([baseHot, baseCold]);
  assert.equal(batch.length, 2, "batch deve retornar todos os jogos");
  assert(batch.every((match) => match.cards_analysis), "batch deve anexar cards_analysis");

  console.log("[Card Engine Test] Todos os testes passaram.");
  console.log(`[Card Engine Test] Hot best: ${hot.best_market} (${hot.score})`);
  console.log(`[Card Engine Test] Cold best: ${cold.best_market} (${cold.score})`);
}

run();
