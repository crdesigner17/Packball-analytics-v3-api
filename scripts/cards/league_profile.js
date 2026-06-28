const fs = require("fs");
const path = require("path");

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const CSV_CANDIDATES = [
  path.join(ROOT_DIR, "scripts", "ligas_cartoes.csv"),
  path.join(ROOT_DIR, "data", "ligas_cartoes.csv")
];

function normalizeText(value) {
  return String(value || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function normalizeLeagueName(name) {
  return normalizeText(name)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function parseNumber(value) {
  const text = normalizeText(value).replace("%", "").replace(",", ".");
  const number = Number.parseFloat(text);
  return Number.isFinite(number) ? number : null;
}

function parseCsvLine(line) {
  const values = [];
  let current = "";
  let quoted = false;
  for (const char of line) {
    if (char === '"') {
      quoted = !quoted;
    } else if (char === ";" && !quoted) {
      values.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  values.push(current);
  return values.map((value) => value.trim().replace(/^"|"$/g, ""));
}

function loadLeagueProfiles(options = {}) {
  const file = options.file || CSV_CANDIDATES.find((candidate) => fs.existsSync(candidate));
  if (!file) return [];
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/).filter(Boolean);
  const headers = parseCsvLine(lines.shift() || "").map((header) => normalizeLeagueName(header));
  return lines.map((line) => {
    const values = parseCsvLine(line);
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
    const league = row.league || row["league"] || values[2] || "";
    return {
      country: row.country || values[0] || "",
      short: row.short || values[1] || "",
      league: normalizeText(league),
      league_normalized: normalizeLeagueName(league),
      season: row.season || values[3] || "",
      active: String(row.active || values[4] || "").toLowerCase() === "true",
      over_25: parseNumber(row["2 5"] ?? row["+2 5"] ?? row["+2.5"] ?? values[8]),
      over_35: parseNumber(row["3 5"] ?? row["+3 5"] ?? row["+3.5"] ?? values[9]),
      over_45: parseNumber(row["4 5"] ?? row["+4 5"] ?? row["+4.5"] ?? values[10]),
      over_55: parseNumber(row["5 5"] ?? row["+5 5"] ?? row["+5.5"] ?? values[11])
    };
  }).filter((row) => row.league);
}

function findLeagueProfile(leagueName, options = {}) {
  const profiles = options.profiles || loadLeagueProfiles(options);
  const normalized = normalizeLeagueName(leagueName);
  if (!normalized) return null;
  const withCountry = profiles.find((profile) => {
    const country = normalizeLeagueName(profile.country);
    const short = normalizeLeagueName(profile.short);
    return profile.league_normalized
      && normalized.includes(profile.league_normalized)
      && ((country && normalized.includes(country)) || (short && normalized.includes(short)));
  });
  if (withCountry) return withCountry;
  return profiles.find((profile) => profile.league_normalized === normalized)
    || profiles.find((profile) => normalized.includes(profile.league_normalized) || profile.league_normalized.includes(normalized))
    || null;
}

function scorePercent(percent) {
  if (percent === null || percent === undefined) return 5;
  if (percent >= 60) return 15;
  if (percent >= 52) return 13;
  if (percent >= 45) return 10;
  if (percent >= 38) return 6;
  if (percent >= 30) return 3;
  return 0;
}

function getLinePercent(profile, line, side) {
  if (!profile) return null;
  const key = `over_${String(line).replace(".", "")}`;
  const overPercent = profile[key];
  if (side === "under") return overPercent === null || overPercent === undefined ? null : 100 - overPercent;
  return overPercent;
}

function getLeagueScore(leagueName, line, side = "over", options = {}) {
  const profile = findLeagueProfile(leagueName, options);
  if (!profile) {
    return { found: false, score: 5, percent: null, profile: null };
  }
  const percent = getLinePercent(profile, line, side);
  return {
    found: true,
    score: scorePercent(percent),
    percent,
    profile
  };
}

module.exports = {
  loadLeagueProfiles,
  normalizeLeagueName,
  findLeagueProfile,
  getLeagueScore
};
