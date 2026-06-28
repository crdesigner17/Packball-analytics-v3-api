function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number.parseFloat(String(value).replace(",", "."));
  return Number.isFinite(number) ? number : null;
}

function isCardsMarketName(name) {
  return /cards|cartoes|cartao|bookings/.test(normalizeText(name));
}

function flattenMarkets(source) {
  if (!source) return [];
  if (Array.isArray(source)) return source.flatMap(flattenMarkets);
  if (typeof source !== "object") return [];

  const markets = [];
  if (source.markets) markets.push(...flattenMarkets(source.markets));
  if (source.odds) markets.push(...flattenMarkets(source.odds));
  if (source.bookmakers) markets.push(...flattenMarkets(source.bookmakers));
  if (source.card_odds) markets.push(source.card_odds);
  if (source.prediction?.odds) markets.push(...flattenMarkets(source.prediction.odds));
  if (source.name || source.market || source.label || source.total_cards || source.values || source.outcomes) markets.push(source);
  return markets;
}

function upsertLine(lines, line, side, odds) {
  if (line === null || odds === null) return;
  let row = lines.find((item) => item.line === line);
  if (!row) {
    row = { line, over_odds: null, under_odds: null };
    lines.push(row);
  }
  if (side === "over") row.over_odds = odds;
  if (side === "under") row.under_odds = odds;
}

function parseOutcome(outcome, marketName, normalized) {
  const name = normalizeText([outcome.name, outcome.label, outcome.selection, outcome.header, marketName].join(" "));
  const line = toNumber(outcome.line ?? outcome.handicap ?? outcome.total ?? (name.match(/(\d{1,2}(?:[,.]\d)?)/)?.[1]));
  const odds = toNumber(outcome.odds ?? outcome.price ?? outcome.value ?? outcome.odd);
  const side = /under|menos/.test(name) ? "under" : /over|mais/.test(name) ? "over" : null;
  if (side && line !== null && odds !== null) upsertLine(normalized.total_cards, line, side, odds);

  if (/ambas|both teams/.test(name) && /2\+|2 ou mais|2 or more/.test(name)) {
    if (/sim|yes/.test(name)) normalized.both_teams_2plus_cards.yes_odds = odds;
    if (/nao|não|no/.test(name)) normalized.both_teams_2plus_cards.no_odds = odds;
  } else if (/ambas|both teams/.test(name)) {
    if (/sim|yes/.test(name)) normalized.both_teams_card.yes_odds = odds;
    if (/nao|não|no/.test(name)) normalized.both_teams_card.no_odds = odds;
  }
}

function parseMarket(market, normalized) {
  if (market.total_cards && Array.isArray(market.total_cards)) {
    market.total_cards.forEach((row) => {
      const line = toNumber(row.line);
      upsertLine(normalized.total_cards, line, "over", toNumber(row.over_odds));
      upsertLine(normalized.total_cards, line, "under", toNumber(row.under_odds));
    });
  }
  if (market.both_teams_card) normalized.both_teams_card = { ...normalized.both_teams_card, ...market.both_teams_card };
  if (market.both_teams_2plus_cards) normalized.both_teams_2plus_cards = { ...normalized.both_teams_2plus_cards, ...market.both_teams_2plus_cards };

  const marketName = [market.name, market.market, market.label, market.title, market.key].filter(Boolean).join(" ");
  if (!isCardsMarketName(marketName) && !market.total_cards) return;
  const outcomes = market.outcomes || market.values || market.selections || market.runners || [];
  if (Array.isArray(outcomes)) outcomes.forEach((outcome) => parseOutcome(outcome, marketName, normalized));
}

function extractCardOddsFromMatch(match = {}) {
  const normalized = {
    available: false,
    total_cards: [],
    both_teams_card: { yes_odds: null, no_odds: null },
    both_teams_2plus_cards: { yes_odds: null, no_odds: null }
  };

  flattenMarkets(match).forEach((market) => parseMarket(market, normalized));
  normalized.total_cards.sort((a, b) => a.line - b.line);
  normalized.available = normalized.total_cards.length > 0
    || normalized.both_teams_card.yes_odds !== null
    || normalized.both_teams_2plus_cards.yes_odds !== null;
  return normalized;
}

function findCardOdds(match) {
  return extractCardOddsFromMatch(match);
}

function getAvailableCardLines(match) {
  return extractCardOddsFromMatch(match).total_cards.map((row) => row.line);
}

function getOddsScore(odds, side = "over") {
  const value = odds && typeof odds === "object" ? toNumber(side === "under" ? odds.under_odds : odds.over_odds) : toNumber(odds);
  if (value === null) return { odds_available: false, score: 0, odds: null };
  if (value >= 1.85) return { odds_available: true, score: 10, odds: value };
  if (value >= 1.75) return { odds_available: true, score: 8, odds: value };
  if (value >= 1.65) return { odds_available: true, score: 5, odds: value };
  if (value >= 1.5) return { odds_available: true, score: 2, odds: value };
  return { odds_available: true, score: 0, odds: value };
}

module.exports = {
  extractCardOddsFromMatch,
  findCardOdds,
  getAvailableCardLines,
  getOddsScore
};
