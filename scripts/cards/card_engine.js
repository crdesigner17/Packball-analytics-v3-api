const { getRefereeScore, findRefereeProfile } = require("./referee_service");
const { getLeagueScore } = require("./league_profile");
const { getTeamCardsScore, getTeamCardsStats } = require("./team_cards_stats");
const { getContextScore } = require("./match_context");
const { extractCardOddsFromMatch, getOddsScore } = require("./card_odds_service");
const { selectCardMarkets } = require("./card_market_selector");

const LINES = [2.5, 3.5, 4.5, 5.5, 6.5];

const UNDER_REFEREE_SCORES = {
  ELITE_OVER: 0,
  FORTE_OVER: 0,
  MODERADO_OVER: 4,
  NEUTRO: 10,
  MODERADO_UNDER: 21,
  ELITE_UNDER: 25,
  UNKNOWN: 0
};

function round(value, decimals = 1) {
  if (!Number.isFinite(value)) return 0;
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function getMatchRefereeName(match = {}) {
  return match.referee || match.fixture?.referee || match.officials?.referee || match.game?.referee || "";
}

function getMatchLeagueName(match = {}) {
  const country = match.country || match.league?.country || match.fixture?.league?.country || "";
  const league = match.league?.name || match.league_name || match.league || match.liga || match.competition || match.fixture?.league?.name || "";
  return `${country} ${league}`.trim();
}

function grade(score) {
  if (score >= 88) return "A+";
  if (score >= 78) return "A";
  if (score >= 68) return "B";
  if (score >= 58) return "C";
  return "D";
}

function lowerGrade(value) {
  const order = ["A+", "A", "B", "C", "D"];
  const index = order.indexOf(value);
  return order[Math.min(index + 1, order.length - 1)] || value;
}

function applyDataQualityGrade(score, quality) {
  let current = grade(score);
  if (quality < 60 && ["A+", "A"].includes(current)) return "B";
  if (quality >= 60 && quality < 80) return lowerGrade(current);
  return current;
}

function refereeUnderScore(refereeProfile) {
  if (!refereeProfile?.found) {
    return { found: false, score: 0, tier: "UNKNOWN", confidence: 0 };
  }
  const tier = refereeProfile.discipline_tier || refereeProfile.tier || "UNKNOWN";
  const confidence = Number(refereeProfile.confidence || 0);
  return {
    found: true,
    referee: refereeProfile.referee,
    tier,
    confidence,
    score: round((UNDER_REFEREE_SCORES[tier] || 0) * (confidence / 100), 1),
    profile: refereeProfile
  };
}

function oddsForLine(odds, line, side) {
  const row = odds.total_cards.find((item) => item.line === line);
  if (!row) return null;
  return side === "under" ? row.under_odds : row.over_odds;
}

function buildReasons(analysis, selected) {
  const reasons = [];
  if (analysis.team_stats.available) {
    reasons.push(selected.side === "under" ? "Media combinada de cartoes abaixo da linha" : "Media combinada de cartoes acima da linha");
  }
  if (analysis.referee.found) reasons.push(`Arbitro com perfil ${analysis.referee.tier}`);
  if (analysis.league_data) reasons.push(selected.side === "under" ? "Liga historicamente favoravel ao under de cartoes" : "Liga historicamente quente para cartoes");
  if (analysis.context?.score > 0) reasons.push(analysis.context.reasons[0] || "Contexto relevante do jogo");
  if (selected.odds_available) reasons.push("Odd de cartoes disponivel via API");
  return reasons;
}

function calculateDataQuality({ teamStats, referee, leagueScores, odds, context }) {
  let quality = 0;
  if (teamStats.available) quality += 20;
  if (referee.found) quality += 20;
  if (leagueScores.some((item) => item.found)) quality += 20;
  if (odds.available) quality += 20;
  if (context.available) quality += 20;
  return quality;
}

function analyzeLine(match, line, side, refereeOver, refereeUnder, odds) {
  const leagueName = getMatchLeagueName(match);
  const team = getTeamCardsScore(match, line, side);
  const referee = side === "under" ? refereeUnder : refereeOver;
  const league = getLeagueScore(leagueName, line, side);
  const context = getContextScore(match, side);
  const oddsScore = getOddsScore(oddsForLine(odds, line, side), side);
  const score = round(team.score + referee.score + league.score + context.score + oddsScore.score, 1);
  return {
    line,
    side,
    score,
    confidence: grade(score),
    team,
    referee,
    league,
    context,
    odds: oddsScore
  };
}

function analyzeCardsMarket(match = {}) {
  const refereeName = getMatchRefereeName(match);
  const refereeOver = getRefereeScore(refereeName);
  const refereeProfile = findRefereeProfile(refereeName);
  const refereeUnder = refereeUnderScore(refereeProfile);
  const odds = extractCardOddsFromMatch(match);
  const teamStats = getTeamCardsStats(match);

  const lineAnalyses = {};
  const leagueScores = [];
  for (const line of LINES) {
    for (const side of ["over", "under"]) {
      const item = analyzeLine(match, line, side, refereeOver, refereeUnder, odds);
      lineAnalyses[`${side}_${String(line).replace(".", "")}`] = item;
      leagueScores.push(item.league);
    }
  }

  const context = getContextScore(match, "over");
  const dataQuality = calculateDataQuality({ teamStats, referee: refereeOver, leagueScores, odds, context });
  const analysis = {
    team_stats: teamStats,
    referee: refereeOver,
    referee_under: refereeUnder,
    odds,
    context,
    lineAnalyses,
    league_data: leagueScores.some((item) => item.found),
    data_quality_percent: dataQuality
  };

  const submarkets = selectCardMarkets(match, analysis);
  const best = submarkets[0] || null;
  const adjustedConfidence = best ? applyDataQualityGrade(best.score, dataQuality) : "D";

  return {
    market_group: "Cartoes",
    approved: Boolean(best),
    best_market: best?.market || null,
    market_key: best?.market_key || null,
    line: best?.line ?? null,
    side: best?.side || null,
    score: best ? best.score : 0,
    confidence: adjustedConfidence,
    data_quality: dataQuality,
    odds_available: Boolean(best?.odds_available),
    odds: best?.odds ?? null,
    reasons: best ? buildReasons(analysis, best) : ["Nenhum mercado de cartoes aprovado com sustentacao suficiente"],
    submarkets,
    diagnostics: analysis
  };
}

function analyzeCardsForMatches(matches = []) {
  return matches.map((match) => ({
    ...match,
    cards_analysis: analyzeCardsMarket(match)
  }));
}

module.exports = {
  analyzeCardsMarket,
  analyzeCardsForMatches
};
