const fs = require("fs");
const path = require("path");

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const DATA_DIR = path.join(ROOT_DIR, "docs", "data");
const JSON_OUTPUT = path.join(DATA_DIR, "cards_audit_report.json");
const MD_OUTPUT = path.join(DATA_DIR, "cards_audit_report.md");

const IGNORED_FILES = new Set([
  "index.json",
  "card_pipeline_column_report.json",
  "cards_audit_report.json"
]);

function nowIso() {
  return new Date().toISOString();
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function round(value, decimals = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  const factor = 10 ** decimals;
  return Math.round(number * factor) / factor;
}

function avg(values) {
  const numbers = values.map(Number).filter(Number.isFinite);
  if (!numbers.length) return 0;
  return round(numbers.reduce((sum, value) => sum + value, 0) / numbers.length, 1);
}

function increment(group, key) {
  const safeKey = key || "Indefinido";
  group[safeKey] = (group[safeKey] || 0) + 1;
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function escapeMarkdown(value) {
  return String(value ?? "")
    .replace(/\|/g, "\\|")
    .replace(/\r?\n/g, " ");
}

function formatNumber(value, decimals = 1) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(decimals) : "-";
}

function formatOdds(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "-";
}

function refereeLabel(referee) {
  if (!referee || referee.found === false) return "Nao encontrado";
  return referee.referee || referee.name || "Encontrado";
}

function oddsLabel(item) {
  if (!item.odds_available) return "-";
  return formatOdds(item.odds);
}

function breakdownLabel(breakdown) {
  if (!breakdown) return "-";
  return [
    `T${formatNumber(breakdown.team_stats?.score, 1)}/${breakdown.team_stats?.max ?? 35}`,
    `R${formatNumber(breakdown.referee?.score, 1)}/${breakdown.referee?.max ?? 25}`,
    `L${formatNumber(breakdown.league?.score, 1)}/${breakdown.league?.max ?? 15}`,
    `C${formatNumber(breakdown.context?.score, 1)}/${breakdown.context?.max ?? 15}`,
    `O${formatNumber(breakdown.odds?.score, 1)}/${breakdown.odds?.max ?? 10}`
  ].join(" ");
}

function roundOrNull(value, decimals = 1) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return round(number, decimals);
}

function scoreBucket(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return "Indefinido";
  if (value < 70) return "<70";
  if (value < 75) return "70-74";
  if (value < 80) return "75-79";
  if (value < 85) return "80-84";
  if (value < 90) return "85-89";
  return "90+";
}

function getGamesFromFile(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.jogos)) return payload.jogos;
  if (Array.isArray(payload.games)) return payload.games;
  if (Array.isArray(payload.matches)) return payload.matches;
  return [];
}

function listInputFiles() {
  if (!fs.existsSync(DATA_DIR)) return [];
  return fs.readdirSync(DATA_DIR)
    .filter((file) => file.endsWith(".json"))
    .filter((file) => !IGNORED_FILES.has(file))
    .map((file) => path.join(DATA_DIR, file))
    .sort((a, b) => path.basename(a).localeCompare(path.basename(b)));
}

function normalizeApprovedGame(game, fileDate) {
  const analysis = game.cards_analysis || {};
  const breakdown = analysis.breakdown || {};
  const scoreFinal = round(analysis.score_final ?? analysis.final_score ?? analysis.score, 1);
  const scoreBeforeCap = round(
    analysis.score_before_cap
      ?? analysis.score_bruto
      ?? breakdown.score_before_cap
      ?? breakdown.score_bruto
      ?? analysis.score,
    1
  );
  const scoreCap = roundOrNull(analysis.score_cap ?? breakdown.score_cap, 1);
  const dataSourceLevel = analysis.data_source_level || breakdown.data_source_level || "BAIXA";
  const date = game.date || fileDate || null;
  return {
    date,
    jogo: game.jogo || `${game.home || ""} x ${game.away || ""}`.trim(),
    liga: game.liga || game.league || null,
    country: game.country || game.pais || null,
    home: game.home || null,
    away: game.away || null,
    market: analysis.best_market || null,
    market_key: analysis.market_key || null,
    line: analysis.line ?? null,
    side: analysis.side || null,
    score: scoreFinal,
    score_before_cap: scoreBeforeCap,
    score_bruto: scoreBeforeCap,
    score_cap: scoreCap,
    score_final: scoreFinal,
    final_score: scoreFinal,
    confidence: analysis.confidence || null,
    data_quality: round(analysis.data_quality, 1),
    data_source_level: dataSourceLevel,
    odds_available: Boolean(analysis.odds_available),
    odds: analysis.odds ?? null,
    line_value: analysis.line_value ?? null,
    line_value_score: analysis.line_value_score ?? null,
    line_risk_penalty: analysis.line_risk_penalty ?? null,
    breakdown: breakdown || null,
    reasons: asArray(analysis.reasons),
    submarkets: asArray(analysis.submarkets),
    referee: analysis.referee || null,
    team_stats: analysis.team_stats || null,
    context: analysis.context || null,
    cards_best_market: game.cards_best_market || null,
    cards_best_score: game.cards_best_score ?? null,
    cards_best_grade: game.cards_best_grade || null,
    cards_data_quality: game.cards_data_quality ?? null,
    card_markets: asArray(game.card_markets)
  };
}

function buildAlerts(item) {
  const alerts = [];
  const combinedAvg = Number(item.team_stats?.combined_avg);
  const market = `${item.market || ""} ${item.market_key || ""}`.toLowerCase();
  const isOver = item.side === "over" || market.includes("over");
  const isUnder = item.side === "under" || market.includes("under");
  const contextHigh = item.context?.importance === "high" || item.context?.level === "high";

  const lineValue = Number(item.line_value);
  if (Number(item.data_quality) < 70) alerts.push("DATA QUALITY abaixo de 70");
  if (Number(item.data_quality) < 60) alerts.push("data_quality < 60");
  if (!item.odds_available) alerts.push("odds_available = false");
  if (!item.referee?.found) alerts.push("referee.found = false");
  if (!item.team_stats?.available) alerts.push("team_stats.available = false");
  if (isOver && Number.isFinite(lineValue) && lineValue < 0.7) alerts.push("Over aprovado com line_value < 0.7");
  if (isUnder && Number.isFinite(lineValue) && lineValue < 0.7) alerts.push("Under aprovado com line_value < 0.7");
  if (isUnder && Number.isFinite(lineValue) && lineValue < 0.7) alerts.push("Under aprovado com line_value baixo");
  if (isOver && Number(item.line) === 5.5 && Number.isFinite(combinedAvg) && combinedAvg < 5.8) {
    alerts.push("OVER 5.5 aprovado com media inferior a 5.8");
  }
  if (isOver && Number(item.line) === 5.5 && Number.isFinite(lineValue) && lineValue < 0.8) {
    alerts.push("Over 5.5 aprovado com line_value < 0.8");
  }
  if (isOver && Number(item.line) === 6.5 && Number.isFinite(combinedAvg) && combinedAvg < 6.6) {
    alerts.push("OVER 6.5 aprovado com media inferior a 6.6");
  }
  if (isOver && Number(item.line) === 6.5 && Number.isFinite(lineValue) && lineValue < 1.0) {
    alerts.push("Over 6.5 aprovado com line_value < 1.0");
  }
  if (isUnder && contextHigh) alerts.push("UNDER aprovado em jogo de alta importancia");
  if (isUnder && contextHigh && Number(item.line) === 4.5) alerts.push("Under 4.5 aprovado em contexto high");
  if (Number(item.score) > 89 && !item.referee?.found) alerts.push("SCORE > 89 sem arbitro");
  if (Number(item.score) > 92 && !item.odds_available) alerts.push("SCORE > 92 sem odds");
  if (Number(item.score) > 94 && item.data_source_level !== "ELITE") alerts.push("SCORE > 94 sem dados ELITE");
  if (item.data_source_level === "BAIXA" && Number(item.score) > 80) alerts.push("Fonte BAIXA com score acima de 80");
  if (Number(item.score) > 90 && !item.referee?.found) alerts.push("SCORE muito alto (>90) sem arbitro");
  if (Number(item.score) > 90 && !item.odds_available) alerts.push("SCORE muito alto (>90) sem odds");
  if (Number(item.score) >= 88 && Number(item.data_quality) < 70) {
    alerts.push("score >= 88 mas data_quality < 70");
  }
  return alerts;
}

function collectAudit() {
  const files = listInputFiles();
  const approved = [];
  let totalGames = 0;
  let gamesWithCardsAnalysis = 0;

  for (const filePath of files) {
    const payload = readJson(filePath);
    const fileDate = path.basename(filePath, ".json");
    const games = getGamesFromFile(payload);
    totalGames += games.length;

    for (const game of games) {
      if (game.cards_analysis) gamesWithCardsAnalysis += 1;
      if (game.cards_analysis?.approved === true) {
        const item = normalizeApprovedGame(game, fileDate);
        item.alerts = buildAlerts(item);
        approved.push(item);
      }
    }
  }

  const byDate = {};
  const byLeague = {};
  const byMarketKey = {};
  const scoreDistribution = {};
  const byDataSourceLevel = { ELITE: 0, ALTA: 0, MEDIA: 0, BAIXA: 0 };
  for (const item of approved) {
    increment(byDate, item.date);
    increment(byLeague, item.liga);
    increment(byMarketKey, item.market_key);
    increment(scoreDistribution, scoreBucket(item.score));
    increment(byDataSourceLevel, item.data_source_level);
  }
  const topScores = [...approved].sort((a, b) => b.score - a.score).slice(0, 10);

  return {
    generated_at: nowIso(),
    summary: {
      total_games: totalGames,
      games_with_cards_analysis: gamesWithCardsAnalysis,
      approved_cards: approved.length,
      avg_score: avg(approved.map((item) => item.score)),
      avg_score_before_cap: avg(approved.map((item) => item.score_before_cap)),
      avg_data_quality: avg(approved.map((item) => item.data_quality)),
      without_referee: approved.filter((item) => !item.referee?.found).length,
      without_odds: approved.filter((item) => !item.odds_available).length,
      with_team_stats: approved.filter((item) => item.team_stats?.available === true).length,
      by_date: byDate,
      by_league: byLeague,
      by_market_key: byMarketKey,
      by_data_source_level: byDataSourceLevel,
      score_distribution: scoreDistribution
    },
    top_scores: topScores,
    approved
  };
}

function groupTable(title, group) {
  const rows = Object.entries(group).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return [
    `## ${title}`,
    "",
    "| Grupo | Aprovados |",
    "|---|---:|",
    ...rows.map(([key, count]) => `| ${escapeMarkdown(key)} | ${count} |`),
    ""
  ].join("\n");
}

function approvedTable(approved) {
  const rows = approved.map((item) => {
    const avgCards = formatNumber(item.team_stats?.combined_avg, 1);
    return [
      item.date,
      item.jogo,
      item.liga,
      item.market,
      formatNumber(item.score_before_cap, 1),
      formatNumber(item.score_cap, 1),
      formatNumber(item.score_final, 1),
      item.confidence,
      formatNumber(item.data_quality, 1),
      item.data_source_level,
      avgCards,
      formatNumber(item.line_value, 2),
      formatNumber(item.line_value_score, 0),
      formatNumber(item.line_risk_penalty, 0),
      breakdownLabel(item.breakdown),
      refereeLabel(item.referee),
      oddsLabel(item)
    ].map(escapeMarkdown).join(" | ");
  });

  return [
    "## Tabela de Aprovados",
    "",
    "| Data | Jogo | Liga | Mercado | Score Bruto | Score Cap | Score Final | Grade | Qualidade | Data Source | Media Cartoes | Line Value | Line Value Score | Penalidade Linha | Breakdown | Arbitro | Odds |",
    "|---|---|---|---|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---|---|---:|",
    ...rows.map((row) => `| ${row} |`),
    ""
  ].join("\n");
}

function scoreDistributionSection(distribution) {
  const order = ["<70", "70-74", "75-79", "80-84", "85-89", "90+", "Indefinido"];
  const rows = order
    .filter((bucket) => distribution[bucket])
    .map((bucket) => `| ${bucket} | ${distribution[bucket]} |`);

  return [
    "## Distribuicao por Score",
    "",
    "| Faixa | Jogos |",
    "|---|---:|",
    ...rows,
    ""
  ].join("\n");
}

function dataSourceSection(group) {
  const order = ["ELITE", "ALTA", "MEDIA", "BAIXA"];
  return [
    "## Resumo das Fontes",
    "",
    "| Fonte | Jogos |",
    "|---|---:|",
    ...order.map((level) => `| ${level} | ${group?.[level] || 0} |`),
    ""
  ].join("\n");
}

function topScoresSection(topScores) {
  const rows = topScores.map((item, index) => [
    index + 1,
    item.date,
    item.jogo,
    item.liga,
    item.market,
    formatNumber(item.score_before_cap, 1),
    formatNumber(item.score_cap, 1),
    formatNumber(item.score_final, 1),
    item.confidence,
    formatNumber(item.data_quality, 1),
    item.data_source_level,
    formatNumber(item.line_value, 2)
  ].map(escapeMarkdown).join(" | "));

  return [
    "## Top 10 Maiores Scores",
    "",
    "| # | Data | Jogo | Liga | Mercado | Bruto | Cap | Final | Grade | Qualidade | Fonte | Line Value |",
    "|---:|---|---|---|---|---:|---:|---:|---|---:|---|---:|",
    ...rows.map((row) => `| ${row} |`),
    ""
  ].join("\n");
}

function alertsSection(approved) {
  const alertRows = [];
  for (const item of approved) {
    for (const alert of item.alerts || []) {
      alertRows.push(`| ${escapeMarkdown(item.date)} | ${escapeMarkdown(item.jogo)} | ${escapeMarkdown(item.market)} | ${escapeMarkdown(alert)} |`);
    }
  }

  if (!alertRows.length) {
    return ["## Lista de Alertas", "", "Nenhum alerta encontrado.", ""].join("\n");
  }

  return [
    "## Lista de Alertas",
    "",
    "| Data | Jogo | Mercado | Alerta |",
    "|---|---|---|---|",
    ...alertRows,
    ""
  ].join("\n");
}

function buildMarkdown(report) {
  const { summary, approved } = report;
  return [
    "# Auditoria do Mercado de Cartoes",
    "",
    `Gerado em: ${report.generated_at}`,
    "",
    "## Resumo Geral",
    "",
    `- Total de jogos analisados: ${summary.total_games}`,
    `- Jogos com cards_analysis: ${summary.games_with_cards_analysis}`,
    `- Palpites de cartoes aprovados: ${summary.approved_cards}`,
    `- Media de score: ${formatNumber(summary.avg_score, 1)}`,
    `- Media de score bruto: ${formatNumber(summary.avg_score_before_cap, 1)}`,
    `- Media de data_quality: ${formatNumber(summary.avg_data_quality, 1)}`,
    `- Sem arbitro: ${summary.without_referee}`,
    `- Sem odds: ${summary.without_odds}`,
    `- Com team_stats.available = true: ${summary.with_team_stats}`,
    "",
    approvedTable(approved),
    groupTable("Agrupamento por Mercado", summary.by_market_key),
    groupTable("Agrupamento por Liga", summary.by_league),
    dataSourceSection(summary.by_data_source_level),
    scoreDistributionSection(summary.score_distribution),
    topScoresSection(report.top_scores || []),
    alertsSection(approved)
  ].join("\n");
}

function writeReports(report) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(JSON_OUTPUT, JSON.stringify(report, null, 2), "utf8");
  fs.writeFileSync(MD_OUTPUT, buildMarkdown(report), "utf8");
}

function main() {
  const report = collectAudit();
  writeReports(report);
  console.log(`[Card Audit] Jogos analisados: ${report.summary.total_games}`);
  console.log(`[Card Audit] Aprovados: ${report.summary.approved_cards}`);
  console.log(`[Card Audit] JSON: ${path.relative(ROOT_DIR, JSON_OUTPUT)}`);
  console.log(`[Card Audit] Markdown: ${path.relative(ROOT_DIR, MD_OUTPUT)}`);
}

main();
