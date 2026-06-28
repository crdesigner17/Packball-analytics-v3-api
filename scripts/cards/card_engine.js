const { getRefereeScore, findRefereeProfile } = require("./referee_service");
const { getLeagueScore } = require("./league_profile");
const { getTeamCardsScore, getTeamCardsStats } = require("./team_cards_stats");
const { getContextScore } = require("./match_context");
const { extractCardOddsFromMatch, getOddsScore } = require("./card_odds_service");
const { selectCardMarkets } = require("./card_market_selector");

const LINES = [2.5, 3.5, 4.5, 5.5, 6.5];

const LINE_RISK_PENALTY = {
  over: { 2.5: 0, 3.5: 1, 4.5: 3, 5.5: 5, 6.5: 8 },
  under: { 2.5: 8, 3.5: 5, 4.5: 3, 5.5: 1, 6.5: 0 }
};

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

function clamp(value, min = 0, max = 97) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(min, Math.min(max, value));
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

function dataQualityPenalty(quality) {
  if (quality >= 90) return 0;
  if (quality >= 80) return 2;
  if (quality >= 70) return 5;
  if (quality >= 60) return 10;
  return 10;
}

function dataSourceLevel(availability) {
  const hasCoreData = Boolean(availability.team && availability.league && availability.context);
  if (hasCoreData && availability.referee && availability.odds) return "ELITE";
  if (hasCoreData && availability.odds) return "ALTA";
  if (hasCoreData) return "MEDIA";
  return "BAIXA";
}

function scoreCapForAvailability(availability) {
  const hasCoreData = Boolean(availability.team && availability.league && availability.context);
  if (hasCoreData && availability.referee && availability.odds) return 100;
  if (hasCoreData && availability.odds) return 92;
  if (hasCoreData && availability.referee) return 94;
  if (hasCoreData) return 89;
  return 80;
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

function getLineRiskPenalty(line, side) {
  return LINE_RISK_PENALTY[side]?.[Number(line)] ?? 0;
}

function getLineValue(combinedAvg, line, side) {
  const avg = Number(combinedAvg);
  if (!Number.isFinite(avg)) return null;
  return round(side === "under" ? Number(line) - avg : avg - Number(line), 2);
}

function getLineValueScore(lineValue) {
  const value = Number(lineValue);
  if (!Number.isFinite(value) || value < 0.4) return 0;
  if (value >= 2.0) return 15;
  if (value >= 1.5) return 13;
  if (value >= 1.0) return 10;
  if (value >= 0.7) return 7;
  return 4;
}

function scoreSpread({ team, league, line, side, lineValue }) {
  let spread = 0;
  const combinedAvg = Number(team?.combined_avg);
  const leaguePercent = Number(league?.percent);
  const value = Number(lineValue);

  if (Number.isFinite(combinedAvg)) spread += (combinedAvg % 1) * 2.4;
  if (Number.isFinite(leaguePercent)) spread += ((leaguePercent % 10) - 5) * 0.18;
  if (Number.isFinite(value)) spread += Math.max(-1.5, Math.min(2.4, value * 0.55));
  spread += side === "under" ? 0.9 : 0;
  spread += (Number(line) - 4.5) * 0.25;
  if (side === "over" && Number(line) === 2.5) spread -= 0.8;
  return round(spread, 1);
}

function isHighUnderContext(context) {
  return context?.importance === "high";
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

function dataQualityCap(quality) {
  if (quality >= 90) return 100;
  if (quality >= 70) return 89;
  if (quality >= 50) return 69;
  return 0;
}

function dataQualityTier(quality) {
  if (quality >= 90) return "referee_team_odds";
  if (quality >= 70) return "team_context_league";
  if (quality >= 50) return "context_league_history";
  return "insufficient";
}

function componentAvailability({ team, referee, league, oddsScore, context }) {
  return {
    team: Boolean(team?.available),
    referee: Boolean(referee?.found),
    league: Boolean(league?.found),
    context: Boolean(context?.available),
    odds: Boolean(oddsScore?.odds_available)
  };
}

function calculateQualityFromAvailability(availability) {
  let quality = 0;
  if (availability.team) quality += 35;
  if (availability.league) quality += 30;
  if (availability.context) quality += 20;
  if (availability.referee) quality += 10;
  if (availability.odds) quality += 5;
  return quality;
}

function availableScoreMax(availability) {
  let max = 0;
  if (availability.team) max += 35;
  if (availability.referee) max += 25;
  if (availability.league) max += 15;
  if (availability.context) max += 15;
  if (availability.odds) max += 10;
  return max;
}

function normalizeScoreForDataQuality(rawScore, availability) {
  const max = availableScoreMax(availability);
  if (max <= 0) return 0;
  const quality = calculateQualityFromAvailability(availability);
  const normalized = (rawScore / max) * 100;
  return round(Math.min(normalized, dataQualityCap(quality)), 1);
}

function calculateDataQuality({ teamStats, referee, leagueScores, odds, context }) {
  return calculateQualityFromAvailability({
    team: Boolean(teamStats.available),
    referee: Boolean(referee.found),
    league: leagueScores.some((item) => item.found),
    context: Boolean(context.available),
    odds: Boolean(odds.available)
  });
}

function applyScoreCapToSelectedMarket(market) {
  if (!market) return null;
  const breakdown = market.breakdown || {};
  const availability = {
    ...(breakdown.availability || {}),
    odds: Boolean(market.odds_available || breakdown.availability?.odds)
  };
  const scoreBeforeCap = round(Number(breakdown.score_before_cap ?? breakdown.score_bruto ?? market.score ?? 0), 1);
  const scoreCap = scoreCapForAvailability(availability);
  const finalScore = round(Math.min(scoreBeforeCap, scoreCap), 1);
  const dataLevel = breakdown.data_source_level || dataSourceLevel(availability);
  const cappedBreakdown = {
    ...breakdown,
    data_source_level: dataLevel,
    score_before_cap: scoreBeforeCap,
    score_bruto: scoreBeforeCap,
    score_cap: scoreCap,
    score_cap_penalty: round(finalScore - scoreBeforeCap, 1),
    final_score: finalScore,
    total: finalScore
  };

  return {
    ...market,
    score: finalScore,
    score_before_cap: scoreBeforeCap,
    score_bruto: scoreBeforeCap,
    score_cap: scoreCap,
    score_final: finalScore,
    final_score: finalScore,
    data_source_level: dataLevel,
    confidence: grade(finalScore),
    breakdown: cappedBreakdown
  };
}

function analyzeLine(match, line, side, refereeOver, refereeUnder, odds) {
  const leagueName = getMatchLeagueName(match);
  const team = getTeamCardsScore(match, line, side);
  const referee = side === "under" ? refereeUnder : refereeOver;
  const league = getLeagueScore(leagueName, line, side);
  const context = getContextScore(match, side);
  const oddsScore = getOddsScore(oddsForLine(odds, line, side), side);
  const rawScore = round(team.score + referee.score + league.score + context.score + oddsScore.score, 1);
  const availability = componentAvailability({ team, referee, league, oddsScore, context });
  const dataQuality = calculateQualityFromAvailability(availability);
  const lineValue = getLineValue(team.combined_avg, line, side);
  const lineValueScore = getLineValueScore(lineValue);
  const lineRiskPenalty = getLineRiskPenalty(line, side);
  const underContextPenalty = side === "under" && isHighUnderContext(context) ? 15 : 0;
  const spread = scoreSpread({ team, league, line, side, lineValue });
  const adjustedRawScore = round(rawScore + spread, 1);
  const scoreBase = normalizeScoreForDataQuality(adjustedRawScore, availability);
  const qualityPenalty = dataQualityPenalty(dataQuality);
  const scoreBeforeQuality = scoreBase + lineValueScore - lineRiskPenalty - underContextPenalty;
  const qualityCappedScore = dataQuality < 60 ? Math.min(scoreBeforeQuality - qualityPenalty, 77.9) : scoreBeforeQuality - qualityPenalty;
  const scoreBeforeCap = round(clamp(qualityCappedScore), 1);
  const scoreCap = scoreCapForAvailability(availability);
  const finalScore = round(Math.min(scoreBeforeCap, scoreCap), 1);
  const sourceLevel = dataSourceLevel(availability);
  const breakdown = {
    team_stats: { score: round(team.score, 1), max: 35 },
    referee: { score: round(referee.score, 1), max: 25 },
    league: { score: round(league.score, 1), max: 15 },
    context: { score: round(context.score, 1), max: 15 },
    odds: { score: round(oddsScore.score, 1), max: 10 },
    raw_total: rawScore,
    distribution_adjustment: spread,
    adjusted_raw_total: adjustedRawScore,
    available_score_max: availableScoreMax(availability),
    score_base: scoreBase,
    line_value: lineValue,
    line_value_score: lineValueScore,
    line_risk_penalty: lineRiskPenalty,
    under_context_penalty: underContextPenalty,
    data_quality_penalty: qualityPenalty,
    quality_penalty: -qualityPenalty,
    availability,
    data_source_level: sourceLevel,
    score_before_cap: scoreBeforeCap,
    score_bruto: scoreBeforeCap,
    score_cap: scoreCap,
    score_cap_penalty: round(finalScore - scoreBeforeCap, 1),
    final_score: finalScore,
    total: finalScore
  };
  return {
    line,
    side,
    score: scoreBeforeCap,
    confidence: grade(scoreBeforeCap),
    raw_score: rawScore,
    score_before_cap: scoreBeforeCap,
    score_bruto: scoreBeforeCap,
    score_cap: scoreCap,
    score_final: finalScore,
    final_score: finalScore,
    available_score_max: availableScoreMax(availability),
    data_quality: dataQuality,
    data_source_level: sourceLevel,
    score_base: scoreBase,
    line_value: lineValue,
    line_value_score: lineValueScore,
    line_risk_penalty: lineRiskPenalty,
    under_context_penalty: underContextPenalty,
    data_quality_penalty: qualityPenalty,
    breakdown,
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

  const internalSubmarkets = selectCardMarkets(match, analysis);
  const submarkets = internalSubmarkets.map(applyScoreCapToSelectedMarket);
  const best = submarkets[0] || null;
  const adjustedConfidence = best ? applyDataQualityGrade(best.score, dataQuality) : "D";
  const fallbackAvailability = {
    team: Boolean(teamStats.available),
    referee: Boolean(refereeOver.found),
    league: leagueScores.some((item) => item.found),
    context: Boolean(context.available),
    odds: Boolean(odds.available)
  };

  return {
    market_group: "Cartoes",
    approved: Boolean(best),
    best_market: best?.market || null,
    market_key: best?.market_key || null,
    line: best?.line ?? null,
    side: best?.side || null,
    score: best ? best.score : 0,
    score_before_cap: best?.score_before_cap ?? 0,
    score_bruto: best?.score_bruto ?? 0,
    score_cap: best?.score_cap ?? scoreCapForAvailability(fallbackAvailability),
    score_final: best?.score_final ?? 0,
    final_score: best?.final_score ?? 0,
    confidence: adjustedConfidence,
    data_quality: dataQuality,
    data_quality_tier: dataQualityTier(dataQuality),
    data_source_level: best?.data_source_level || dataSourceLevel(fallbackAvailability),
    line_value: best?.line_value ?? null,
    line_value_score: best?.line_value_score ?? null,
    line_risk_penalty: best?.line_risk_penalty ?? null,
    breakdown: best?.breakdown || null,
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
