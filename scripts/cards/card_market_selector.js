const OVER_TIERS = new Set(["MODERADO_OVER", "FORTE_OVER", "ELITE_OVER"]);
const HOT_TIERS = new Set(["FORTE_OVER", "ELITE_OVER"]);
const COLD_TIERS = new Set(["MODERADO_UNDER", "ELITE_UNDER"]);

const MARKET_DEFS = [
  { market: "Over 2.5 Cartoes", market_key: "cards_over_25", side: "over", line: 2.5 },
  { market: "Over 3.5 Cartoes", market_key: "cards_over_35", side: "over", line: 3.5 },
  { market: "Over 4.5 Cartoes", market_key: "cards_over_45", side: "over", line: 4.5 },
  { market: "Over 5.5 Cartoes", market_key: "cards_over_55", side: "over", line: 5.5 },
  { market: "Over 6.5 Cartoes", market_key: "cards_over_65", side: "over", line: 6.5 },
  { market: "Under 2.5 Cartoes", market_key: "cards_under_25", side: "under", line: 2.5 },
  { market: "Under 3.5 Cartoes", market_key: "cards_under_35", side: "under", line: 3.5 },
  { market: "Under 4.5 Cartoes", market_key: "cards_under_45", side: "under", line: 4.5 },
  { market: "Under 5.5 Cartoes", market_key: "cards_under_55", side: "under", line: 5.5 },
  { market: "Under 6.5 Cartoes", market_key: "cards_under_65", side: "under", line: 6.5 }
];

function lineKey(side, line) {
  return `${side}_${String(line).replace(".", "")}`;
}

function isLineAvailable(analysis, side, line) {
  if (!analysis.odds?.available) return true;
  const row = analysis.odds.total_cards.find((item) => item.line === line);
  if (!row) return false;
  return side === "under" ? row.under_odds !== null : row.over_odds !== null;
}

function getLeaguePercent(analysis, side, line) {
  return analysis.lineAnalyses?.[lineKey(side, line)]?.league?.percent ?? null;
}

function approveMarket(def, analysis) {
  const item = analysis.lineAnalyses?.[lineKey(def.side, def.line)];
  if (!item || !isLineAvailable(analysis, def.side, def.line)) return false;

  const score = item.score;
  const teamAvg = analysis.team_stats?.combined_avg;
  const refereeTier = analysis.referee?.tier || "UNKNOWN";
  const leaguePercent = getLeaguePercent(analysis, def.side, def.line);

  if (def.side === "over") {
    if (def.line === 2.5) return score >= 68 && (teamAvg >= 3.0 || OVER_TIERS.has(refereeTier) || leaguePercent >= 60);
    if (def.line === 3.5) return score >= 72 && (teamAvg >= 4.0 || OVER_TIERS.has(refereeTier));
    if (def.line === 4.5) return score >= 76 && teamAvg >= 4.8 && refereeTier !== "ELITE_UNDER";
    if (def.line === 5.5) return score >= 80 && teamAvg >= 5.2 && (OVER_TIERS.has(refereeTier) || leaguePercent >= 52);
    if (def.line === 6.5) return score >= 88 && teamAvg >= 6.0 && HOT_TIERS.has(refereeTier);
  }

  if (def.line === 2.5) return score >= 88 && teamAvg <= 2.6 && COLD_TIERS.has(refereeTier);
  if (def.line === 3.5) return score >= 80 && teamAvg <= 3.4 && !HOT_TIERS.has(refereeTier);
  if (def.line === 4.5) return score >= 76 && teamAvg <= 4.4 && refereeTier !== "ELITE_OVER";
  if (def.line === 5.5) return score >= 72 && teamAvg <= 5.2;
  if (def.line === 6.5) return score >= 68 && teamAvg <= 6.1;
  return false;
}

function oddForMarket(analysis, side, line) {
  const row = analysis.odds?.total_cards?.find((item) => item.line === line);
  if (!row) return null;
  return side === "under" ? row.under_odds : row.over_odds;
}

function selectSpecialMarkets(analysis) {
  const specials = [];
  const over25 = analysis.lineAnalyses?.over_25;
  const over45 = analysis.lineAnalyses?.over_45;

  if ((!analysis.odds?.available || analysis.odds.both_teams_card?.yes_odds) && over25?.score >= 70 && analysis.team_stats?.combined_avg >= 3.2) {
    specials.push({
      market: "Ambas equipes recebem cartao",
      market_key: "cards_both_card",
      approved: true,
      score: over25.score,
      odds: analysis.odds?.both_teams_card?.yes_odds ?? null,
      odds_available: Boolean(analysis.odds?.both_teams_card?.yes_odds),
      side: "yes",
      line: null
    });
  }

  if ((!analysis.odds?.available || analysis.odds.both_teams_2plus_cards?.yes_odds) && over45?.score >= 78 && analysis.team_stats?.combined_avg >= 4.8) {
    specials.push({
      market: "Ambas equipes 2+ cartoes",
      market_key: "cards_both_2plus",
      approved: true,
      score: over45.score,
      odds: analysis.odds?.both_teams_2plus_cards?.yes_odds ?? null,
      odds_available: Boolean(analysis.odds?.both_teams_2plus_cards?.yes_odds),
      side: "yes",
      line: null
    });
  }

  return specials;
}

function selectCardMarkets(match, analysis) {
  const selected = MARKET_DEFS
    .filter((def) => approveMarket(def, analysis))
    .map((def) => {
      const item = analysis.lineAnalyses[lineKey(def.side, def.line)];
      return {
        market: def.market,
        market_key: def.market_key,
        approved: true,
        score: item.score,
        confidence: item.confidence,
        odds: oddForMarket(analysis, def.side, def.line),
        odds_available: Boolean(oddForMarket(analysis, def.side, def.line)),
        line: def.line,
        side: def.side
      };
    });

  return [...selected, ...selectSpecialMarkets(analysis)].sort((a, b) => b.score - a.score);
}

module.exports = {
  selectCardMarkets,
  MARKET_DEFS
};
