function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function number(value) {
  const parsed = Number.parseFloat(String(value ?? "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function getRoundNumber(match = {}) {
  const text = `${match.round || ""} ${match.stage || ""} ${match.fixture?.round || ""}`;
  const found = text.match(/\b(\d{1,2})\b/);
  return found ? Number(found[1]) : null;
}

function getMatchContext(match = {}) {
  const text = normalizeText([
    match.league,
    match.round,
    match.stage,
    match.fixture?.round,
    match.fixture?.status?.long,
    match.competition
  ].join(" "));

  const isKnockout = Boolean(match.is_knockout || match.is_cup)
    || /copa|cup|final|semifinal|semi final|quarter|quartas|oitavas|round of 16|knockout|mata mata|playoff|play off/.test(text);
  const isFinal = /final|semifinal|semi final/.test(text);
  const isClassic = Boolean(match.is_classic || match.rivalry || match.is_rivalry)
    || /classico|rival/.test(text);

  const homePosition = number(match.home_position ?? match.standings?.home?.position);
  const awayPosition = number(match.away_position ?? match.standings?.away?.position);
  const homePoints = number(match.home_points ?? match.standings?.home?.points);
  const awayPoints = number(match.away_points ?? match.standings?.away?.points);
  const directTableFight = homePosition !== null && awayPosition !== null && homePoints !== null && awayPoints !== null
    && Math.abs(homePosition - awayPosition) <= 4
    && Math.abs(homePoints - awayPoints) <= 6;

  const accessOrRelegation = /acesso|rebaixamento|promotion|relegation/.test(text)
    || [homePosition, awayPosition].some((positionValue) => positionValue !== null && (positionValue <= 4 || positionValue >= 16));

  const round = getRoundNumber(match);
  const lateSeason = Boolean(match.is_late_season) || (round !== null && round >= 30);

  let importance = "normal";
  let over_score = 0;
  let under_score = 10;
  const reasons = [];

  if (isKnockout || isFinal) {
    importance = "high";
    over_score = 15;
    under_score = 0;
    reasons.push("Jogo eliminatorio ou fase final");
  } else if (isClassic) {
    importance = "rivalry";
    over_score = 12;
    under_score = 0;
    reasons.push("Classico ou rivalidade");
  } else if (accessOrRelegation) {
    importance = "table_pressure";
    over_score = 10;
    under_score = 2;
    reasons.push("Pressao de acesso ou rebaixamento");
  } else if (directTableFight) {
    importance = "direct_fight";
    over_score = 8;
    under_score = 4;
    reasons.push("Confronto direto na tabela");
  } else if (lateSeason) {
    importance = "late_season";
    over_score = 6;
    under_score = 6;
    reasons.push("Fim de temporada");
  } else if (match.low_importance) {
    importance = "low";
    over_score = 0;
    under_score = 8;
    reasons.push("Baixa importancia");
  } else {
    reasons.push("Jogo comum");
  }

  return {
    available: true,
    importance,
    over_score,
    under_score,
    reasons
  };
}

function getContextScore(match, side = "over") {
  const context = getMatchContext(match);
  return {
    ...context,
    score: side === "under" ? context.under_score : context.over_score
  };
}

module.exports = {
  getMatchContext,
  getContextScore
};
