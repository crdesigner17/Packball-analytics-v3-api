const fs = require("fs/promises");
const path = require("path");

let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (error) {
  console.error("[Referee Profiles] Playwright nao encontrado. Rode `npm install` antes de executar.");
  process.exit(1);
}

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const DATA_DIR = path.join(ROOT_DIR, "data");
const OUTPUT_FILE = path.join(DATA_DIR, "referee_profiles.json");
const DEBUG_FILE = path.join(DATA_DIR, "referee_profiles_debug.json");

const HEADLESS = process.env.HEADLESS !== "false";
const PAGE_TIMEOUT_MS = Number.parseInt(process.env.REFEREE_TIMEOUT_MS || "45000", 10);
const WAIT_BETWEEN_LEAGUES_MS = Number.parseInt(process.env.REFEREE_WAIT_MS || "1500", 10);

const LEAGUES = [
  {
    country: "Brazil",
    league: "Serie A",
    league_code: "BRA1",
    season: 2025,
    url: "https://www.transfermarkt.com.br/campeonato-brasileiro-serie-a/schiedsrichter/pokalwettbewerb/BRA1/saison_id/2025/plus/1"
  },
  {
    country: "Brazil",
    league: "Serie B",
    league_code: "BRA2",
    season: 2025,
    url: "https://www.transfermarkt.com.br/campeonato-brasileiro-serie-b/schiedsrichter/wettbewerb/BRA2/saison_id/2025/plus/1"
  }
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nowIsoDate() {
  return new Date().toISOString();
}

function normalizeText(value) {
  let text = String(value || "");
  if (/[ÃÂ]/.test(text)) {
    text = Buffer.from(text, "latin1").toString("utf8");
  }
  return text
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function textKey(value) {
  return normalizeText(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function makeRefereeId(name) {
  return textKey(name)
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function calculateRefereeConfidence(matches) {
  if (matches >= 30) return 100;
  if (matches >= 20) return 95;
  if (matches >= 15) return 90;
  if (matches >= 10) return 80;
  if (matches >= 5) return 70;
  return 50;
}

function normalizeRefereeName(value) {
  return normalizeText(value);
}

function normalizeBrazilianNumber(value) {
  const raw = normalizeText(value)
    .replace(/[^\d,.-]/g, "")
    .replace(/^[-–—]+$/, "");

  if (!raw) return 0;

  const hasComma = raw.includes(",");
  const hasDot = raw.includes(".");

  let normalized = raw;
  if (hasComma && hasDot) {
    normalized = raw.replace(/\./g, "").replace(",", ".");
  } else if (hasComma) {
    normalized = raw.replace(",", ".");
  } else if (hasDot && /^\d{1,3}(?:\.\d{3})+$/.test(raw)) {
    normalized = raw.replace(/\./g, "");
  }

  const number = Number.parseFloat(normalized);
  return Number.isFinite(number) ? number : 0;
}

function round(value, decimals = 2) {
  if (!Number.isFinite(value)) return 0;
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function classifyDisciplineTier(cardsAvgTotal) {
  if (cardsAvgTotal >= 6.2) return "ELITE_OVER";
  if (cardsAvgTotal >= 5.7) return "FORTE_OVER";
  if (cardsAvgTotal >= 5.1) return "MODERADO_OVER";
  if (cardsAvgTotal >= 4.5) return "NEUTRO";
  if (cardsAvgTotal >= 4.0) return "MODERADO_UNDER";
  return "ELITE_UNDER";
}

function buildHeaderMap(headers) {
  const map = new Map();
  headers.forEach((header, index) => {
    const key = textKey(header);
    if (key && !map.has(key)) map.set(key, index);
  });
  return map;
}

function findHeaderIndex(headerMap, candidates) {
  for (const [header, index] of headerMap.entries()) {
    if (candidates.some((candidate) => header.includes(candidate))) return index;
  }
  return null;
}

function looksLikeDate(value) {
  return /^\d{2}\/\d{2}\/\d{4}$/.test(normalizeText(value));
}

function looksLikeRefereeName(value) {
  const text = normalizeRefereeName(value);
  const key = textKey(text);
  if (text.length < 5 || text.length > 80) return false;
  if (!/[a-zA-ZÀ-ÿ]{2,}/.test(text)) return false;
  if (/temporada|estatistica|arbitro|schiedsrichter|brasil$/.test(key)) return false;
  return true;
}

function parseRowByKnownTransfermarktLayouts(row) {
  if (row.length >= 14 && looksLikeRefereeName(row[1]) && looksLikeDate(row[12])) {
    return {
      referee: row[1],
      matches: row[13],
      yellow_cards: row[4],
      second_yellow_cards: row[6],
      red_cards: row[8],
      penalties: row[10]
    };
  }

  if (row.length >= 15 && looksLikeRefereeName(row[2]) && looksLikeDate(row[4])) {
    return {
      referee: row[2],
      matches: row[6],
      yellow_cards: row[7],
      second_yellow_cards: row[9],
      red_cards: row[11],
      penalties: row[13]
    };
  }

  return null;
}

function parseRowByHeaders(row, headerMap) {
  const refereeIndex = findHeaderIndex(headerMap, ["arbitro", "referee", "schiedsrichter"]);
  const matchesIndex = findHeaderIndex(headerMap, ["jogos", "partidas", "matches", "spiele", "utilizacoes"]);
  const yellowIndex = findHeaderIndex(headerMap, ["amarelos", "cartoes amarelos", "yellow", "gelbe"]);
  const secondYellowIndex = findHeaderIndex(headerMap, ["segundo amarelo", "2 amarelo", "2 amarelos", "gelb-rot", "second yellow"]);
  const redIndex = findHeaderIndex(headerMap, ["vermelhos", "cartoes vermelhos", "red", "rote"]);
  const penaltiesIndex = findHeaderIndex(headerMap, ["penaltis", "penalties", "elfmeter"]);

  if (refereeIndex === null || matchesIndex === null || yellowIndex === null) return null;
  if (!looksLikeRefereeName(row[refereeIndex])) return null;

  return {
    referee: row[refereeIndex],
    matches: row[matchesIndex],
    yellow_cards: row[yellowIndex],
    second_yellow_cards: secondYellowIndex === null ? 0 : row[secondYellowIndex],
    red_cards: redIndex === null ? 0 : row[redIndex],
    penalties: penaltiesIndex === null ? 0 : row[penaltiesIndex]
  };
}

function makeProfile(raw, leagueConfig, debugLeague, row) {
  const referee = normalizeRefereeName(raw.referee);
  const matches = normalizeBrazilianNumber(raw.matches);
  if (matches <= 0) {
    debugLeague.skipped_rows.push({ row, reason: "missing_matches" });
    return null;
  }

  const yellowCards = normalizeBrazilianNumber(raw.yellow_cards);
  const secondYellowCards = normalizeBrazilianNumber(raw.second_yellow_cards);
  const redCards = normalizeBrazilianNumber(raw.red_cards);
  const penalties = normalizeBrazilianNumber(raw.penalties);
  const yellowAvg = round(yellowCards / matches, 2);
  const redAvg = round(redCards / matches, 2);
  const penaltyAvg = round(penalties / matches, 2);
  const cardsAvgTotal = round((yellowCards + secondYellowCards + redCards) / matches, 2);

  return {
    id: makeRefereeId(referee),
    source: "Transfermarkt",
    country: leagueConfig.country,
    league: leagueConfig.league,
    league_code: leagueConfig.league_code,
    season: leagueConfig.season,
    referee,
    matches,
    yellow_cards: yellowCards,
    yellow_avg: yellowAvg,
    second_yellow_cards: secondYellowCards,
    red_cards: redCards,
    red_avg: redAvg,
    penalties,
    penalty_avg: penaltyAvg,
    cards_avg_total: cardsAvgTotal,
    confidence: calculateRefereeConfidence(matches),
    discipline_tier: classifyDisciplineTier(cardsAvgTotal),
    updated_at: nowIsoDate()
  };
}

function parseRefereeRows(tableData, leagueConfig, debugLeague) {
  const profiles = [];

  for (const table of tableData) {
    const headerMap = buildHeaderMap(table.headers);

    for (const row of table.rows) {
      const raw = parseRowByKnownTransfermarktLayouts(row) || parseRowByHeaders(row, headerMap);
      if (!raw) {
        if (row.length > 3) debugLeague.skipped_rows.push({ row, reason: "unrecognized_row_layout" });
        continue;
      }

      const profile = makeProfile(raw, leagueConfig, debugLeague, row);
      if (profile) profiles.push(profile);
    }
  }

  return profiles;
}

function dedupeProfiles(profiles) {
  const seen = new Set();
  const output = [];

  for (const profile of profiles) {
    const key = [
      profile.country,
      profile.league_code,
      profile.season,
      textKey(profile.referee)
    ].join("|");

    if (seen.has(key)) continue;
    seen.add(key);
    output.push(profile);
  }

  return output;
}

async function safeGoto(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: PAGE_TIMEOUT_MS });
  await page.waitForLoadState("networkidle", { timeout: PAGE_TIMEOUT_MS }).catch(() => {});
}

async function acceptCookies(page) {
  const selectors = [
    "button:has-text('Aceitar')",
    "button:has-text('Accept')",
    "button:has-text('Concordo')",
    "button:has-text('OK')",
    "[role='button']:has-text('Aceitar')",
    "[role='button']:has-text('Accept')"
  ];

  for (const selector of selectors) {
    const button = page.locator(selector).first();
    if (await button.isVisible({ timeout: 1500 }).catch(() => false)) {
      await button.click({ timeout: 3000 }).catch(() => {});
      await sleep(500);
      return;
    }
  }
}

async function extractTables(page) {
  return page.evaluate(() => {
    const normalize = (value) => String(value || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();

    return [...document.querySelectorAll("table")].map((table) => {
      const headerCells = [...table.querySelectorAll("thead th")];
      const headers = headerCells.length > 0
        ? headerCells.map((cell) => normalize(cell.innerText || cell.textContent))
        : [...table.querySelectorAll("tr:first-child th, tr:first-child td")].map((cell) => normalize(cell.innerText || cell.textContent));

      const rows = [...table.querySelectorAll("tbody tr")]
        .map((tr) => [...tr.querySelectorAll("td")].map((cell) => normalize(cell.innerText || cell.textContent)))
        .filter((row) => row.some(Boolean));

      return { headers, rows };
    }).filter((table) => table.rows.length > 0);
  });
}

async function scrapeLeague(context, leagueConfig, debug) {
  const page = await context.newPage();
  page.setDefaultTimeout(PAGE_TIMEOUT_MS);

  const debugLeague = {
    league: leagueConfig.league,
    league_code: leagueConfig.league_code,
    season: leagueConfig.season,
    url: leagueConfig.url,
    tables_found: 0,
    referees_found: 0,
    skipped_rows: [],
    error: null
  };

  try {
    console.log(`[Referee Profiles] Processando liga: ${leagueConfig.league} (${leagueConfig.league_code})`);
    await safeGoto(page, leagueConfig.url);
    await acceptCookies(page);

    const tableData = await extractTables(page);
    debugLeague.tables_found = tableData.length;

    if (tableData.length === 0) {
      debugLeague.error = "no_tables_found";
      debug.leagues.push(debugLeague);
      return [];
    }

    const profiles = parseRefereeRows(tableData, leagueConfig, debugLeague);
    const deduped = dedupeProfiles(profiles);
    debugLeague.referees_found = deduped.length;
    debugLeague.headers = tableData.map((table) => table.headers);
    debug.leagues.push(debugLeague);

    console.log(`[Referee Profiles] Arbitros encontrados em ${leagueConfig.league}: ${deduped.length}`);
    return deduped;
  } catch (error) {
    debugLeague.error = error.message;
    debug.leagues.push(debugLeague);
    console.warn(`[Referee Profiles] Falha em ${leagueConfig.league}: ${error.message}`);
    return [];
  } finally {
    await page.close().catch(() => {});
  }
}

async function main() {
  const debug = {
    started_at: nowIsoDate(),
    leagues: [],
    summary: {}
  };

  await fs.mkdir(DATA_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
  });

  const allProfiles = [];

  try {
    for (const leagueConfig of LEAGUES) {
      const profiles = await scrapeLeague(context, leagueConfig, debug);
      allProfiles.push(...profiles);
      await sleep(WAIT_BETWEEN_LEAGUES_MS);
    }

    const deduped = dedupeProfiles(allProfiles).sort((a, b) => (
      a.league_code.localeCompare(b.league_code)
      || b.cards_avg_total - a.cards_avg_total
      || a.referee.localeCompare(b.referee)
    ));

    debug.summary = {
      finished_at: nowIsoDate(),
      leagues_processed: LEAGUES.length,
      referees_saved: deduped.length,
      output_file: path.relative(ROOT_DIR, OUTPUT_FILE)
    };

    await fs.writeFile(OUTPUT_FILE, `${JSON.stringify(deduped, null, 2)}\n`, "utf8");
    await fs.writeFile(DEBUG_FILE, `${JSON.stringify(debug, null, 2)}\n`, "utf8");

    console.log(`[Referee Profiles] Arquivo salvo: ${path.relative(ROOT_DIR, OUTPUT_FILE)}`);
    console.log(`[Referee Profiles] Debug salvo: ${path.relative(ROOT_DIR, DEBUG_FILE)}`);
    console.log(`[Referee Profiles] Total de arbitros salvos: ${deduped.length}`);
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(`[Referee Profiles] Erro fatal: ${error.stack || error.message}`);
  process.exitCode = 1;
});
