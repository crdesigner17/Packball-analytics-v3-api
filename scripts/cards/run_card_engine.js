const fs = require("fs");
const { analyzeCardsMarket } = require("./card_engine");

function normalizeLegacyMarketName(marketKey, fallback) {
  const names = {
    cards_over_25: "Cart 2.5",
    cards_over_35: "Cart 3.5",
    cards_over_45: "Cart 4.5",
    cards_over_55: "Cart 5.5",
    cards_over_65: "Cart 6.5",
    cards_under_25: "Under Cart 2.5",
    cards_under_35: "Under Cart 3.5",
    cards_under_45: "Under Cart 4.5",
    cards_under_55: "Under Cart 5.5",
    cards_under_65: "Under Cart 6.5",
    cards_both_card: "Ambas cartão",
    cards_both_2plus: "Ambas 2+ cartões"
  };
  return names[marketKey] || fallback || null;
}

function gradeForScore(score) {
  if (score >= 88) return "A+";
  if (score >= 78) return "A";
  if (score >= 68) return "B";
  if (score >= 58) return "C";
  return "D";
}

function lineScore(analysis, key) {
  return analysis.diagnostics?.lineAnalyses?.[key]?.score || 0;
}

function lineOdds(match, line, side) {
  const suffix = String(line).replace(".", "");
  if (side === "under") return match[`odds_cards_under_${suffix}`] ?? null;
  return match[`odds_cards_${suffix}`] ?? match[`odds_cards_over_${suffix}`] ?? null;
}

function buildCardOdds(match) {
  const totalCards = [];
  for (const line of [2.5, 3.5, 4.5, 5.5, 6.5]) {
    const over = lineOdds(match, line, "over");
    const under = lineOdds(match, line, "under");
    if (over !== null || under !== null) {
      totalCards.push({ line, over_odds: over, under_odds: under });
    }
  }

  return {
    total_cards: totalCards,
    both_teams_card: {
      yes_odds: match.odds_cards_both_yes ?? null,
      no_odds: match.odds_cards_both_no ?? null
    },
    both_teams_2plus_cards: {
      yes_odds: match.odds_cards_both_2plus_yes ?? null,
      no_odds: match.odds_cards_both_2plus_no ?? null
    }
  };
}

function normalizeMatch(match) {
  return {
    ...match,
    country: match.country || match.pais || match.league_country || "",
    league: match.league || match.liga || match.league_name || "",
    referee: match.referee || match.fixture_referee || "",
    home_cards_avg: match.home_cards_avg ?? match.avg_cards_h ?? match.cards_h ?? null,
    away_cards_avg: match.away_cards_avg ?? match.avg_cards_a ?? match.cards_a ?? null,
    card_odds: match.card_odds || buildCardOdds(match)
  };
}

function compactAnalysis(analysis) {
  return {
    market_group: analysis.market_group,
    approved: analysis.approved,
    best_market: analysis.best_market,
    market_key: analysis.market_key,
    line: analysis.line,
    side: analysis.side,
    score: analysis.score,
    score_before_cap: analysis.score_before_cap,
    score_bruto: analysis.score_bruto,
    score_cap: analysis.score_cap,
    score_final: analysis.score_final,
    final_score: analysis.final_score,
    confidence: analysis.confidence,
    data_quality: analysis.data_quality,
    data_quality_tier: analysis.data_quality_tier,
    data_source_level: analysis.data_source_level,
    line_value: analysis.line_value,
    line_value_score: analysis.line_value_score,
    line_risk_penalty: analysis.line_risk_penalty,
    breakdown: analysis.breakdown,
    odds_available: analysis.odds_available,
    odds: analysis.odds,
    reasons: analysis.reasons,
    submarkets: analysis.submarkets,
    referee: analysis.diagnostics?.referee || null,
    referee_under: analysis.diagnostics?.referee_under || null,
    team_stats: analysis.diagnostics?.team_stats || null,
    odds_data: analysis.diagnostics?.odds || null,
    context: analysis.diagnostics?.context || null,
    league_data: analysis.diagnostics?.league_data || false
  };
}

function toPipelinePatch(match) {
  const normalized = normalizeMatch(match);
  const analysis = analyzeCardsMarket(normalized);
  const bestLegacyName = normalizeLegacyMarketName(analysis.market_key, analysis.best_market);
  const scoreCards25 = lineScore(analysis, "over_25");
  const scoreCards35 = lineScore(analysis, "over_35");
  const scoreCards45 = lineScore(analysis, "over_45");
  const scoreCards55 = lineScore(analysis, "over_55");
  const scoreCards65 = lineScore(analysis, "over_65");

  return {
    cards_analysis: compactAnalysis(analysis),
    card_markets: analysis.submarkets,
    cards_best_mkt: bestLegacyName,
    cards_best_market: analysis.best_market,
    cards_market_key: analysis.market_key,
    cards_best_score: analysis.score,
    cards_score_before_cap: analysis.score_before_cap,
    cards_score_cap: analysis.score_cap,
    cards_score_final: analysis.score_final,
    cards_best_grade: analysis.confidence,
    cards_data_quality: analysis.data_quality,
    cards_data_source_level: analysis.data_source_level,
    cards_odds_available: analysis.odds_available,
    cards_reasons: analysis.reasons,
    score_cards25: Number(scoreCards25.toFixed(1)),
    score_cards35: Number(scoreCards35.toFixed(1)),
    score_cards45: Number(scoreCards45.toFixed(1)),
    score_cards55: Number(scoreCards55.toFixed(1)),
    score_cards65: Number(scoreCards65.toFixed(1)),
    grade_cart25: gradeForScore(scoreCards25),
    grade_cart35: gradeForScore(scoreCards35),
    grade_cart45: gradeForScore(scoreCards45),
    grade_cart55: gradeForScore(scoreCards55),
    grade_cart65: gradeForScore(scoreCards65),
    justif_cards: analysis.reasons?.length ? analysis.reasons.join(" · ") : match.justif_cards
  };
}

function main() {
  const input = fs.readFileSync(0, "utf8");
  const matches = JSON.parse(input || "[]");
  const patches = matches.map((match) => {
    try {
      return toPipelinePatch(match);
    } catch (error) {
      return {
        cards_analysis_error: error.message,
        card_markets: [],
        cards_best_mkt: null,
        cards_best_score: 0
      };
    }
  });
  process.stdout.write(JSON.stringify(patches));
}

main();
