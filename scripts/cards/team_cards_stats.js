function valueAtPath(object, path) {
  return path.split(".").reduce((current, key) => (current && current[key] !== undefined ? current[key] : undefined), object);
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "object" && value.average !== undefined) return toNumber(value.average);
  if (typeof value === "object" && value.avg !== undefined) return toNumber(value.avg);
  const number = Number.parseFloat(String(value).replace(",", "."));
  return Number.isFinite(number) ? number : null;
}

const HOME_PATHS = [
  "home_cards_avg",
  "cards_h",
  "avg_cards_h",
  "yellow_cards_h",
  "home_yellow_cards_avg",
  "home_avg_cards",
  "home_cards_per_game",
  "home.statistics.cards",
  "away.statistics.cards_for_home_unused",
  "teams.home.cards_avg",
  "teams.home.cards",
  "statistics.home.cards"
];

const AWAY_PATHS = [
  "away_cards_avg",
  "cards_a",
  "avg_cards_a",
  "yellow_cards_a",
  "away_yellow_cards_avg",
  "away_avg_cards",
  "away_cards_per_game",
  "away.statistics.cards",
  "teams.away.cards_avg",
  "teams.away.cards",
  "statistics.away.cards"
];

function firstNumber(match, paths) {
  for (const path of paths) {
    const value = toNumber(valueAtPath(match, path));
    if (value !== null) return value;
  }
  return null;
}

function getTeamCardsStats(match = {}) {
  const home_avg = firstNumber(match, HOME_PATHS);
  const away_avg = firstNumber(match, AWAY_PATHS);
  const available = home_avg !== null && away_avg !== null;
  const combined_avg = available ? Number((home_avg + away_avg).toFixed(2)) : null;
  return { available, home_avg, away_avg, combined_avg };
}

function getCombinedCardsAvg(match) {
  return getTeamCardsStats(match).combined_avg;
}

function scoreCombinedAvg(combinedAvg, line, side) {
  if (combinedAvg === null || combinedAvg === undefined) return 0;
  if (side === "under") {
    if (combinedAvg <= line - 0.8) return 35;
    if (combinedAvg <= line - 0.4) return 30;
    if (combinedAvg <= line) return 24;
    if (combinedAvg <= line + 0.4) return 16;
    if (combinedAvg <= line + 0.8) return 8;
    return 0;
  }

  if (combinedAvg >= line + 0.8) return 35;
  if (combinedAvg >= line + 0.4) return 30;
  if (combinedAvg >= line) return 24;
  if (combinedAvg >= line - 0.4) return 16;
  if (combinedAvg >= line - 0.8) return 8;
  return 0;
}

function getTeamCardsScore(match, line, side = "over") {
  const stats = getTeamCardsStats(match);
  return {
    ...stats,
    score: stats.available ? scoreCombinedAvg(stats.combined_avg, Number(line), side) : 0
  };
}

module.exports = {
  getTeamCardsStats,
  getCombinedCardsAvg,
  getTeamCardsScore
};
