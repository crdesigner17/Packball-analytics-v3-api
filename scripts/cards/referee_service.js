const fs = require("fs");
const path = require("path");

const ROOT_DIR = path.resolve(__dirname, "..", "..");
const REFEREE_FILE = path.join(ROOT_DIR, "data", "referee_profiles.json");

const TIER_SCORES = {
  ELITE_OVER: 25,
  FORTE_OVER: 21,
  MODERADO_OVER: 16,
  NEUTRO: 10,
  MODERADO_UNDER: 4,
  ELITE_UNDER: 0,
  UNKNOWN: 0
};

function normalizeText(value) {
  let text = String(value || "");
  if (/[ÃÂ]/.test(text)) text = Buffer.from(text, "latin1").toString("utf8");
  return text.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function normalizeRefereeName(name) {
  const text = normalizeText(name).split(",")[0].replace(/\([^)]*\)/g, " ");
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\b(brasil|brazil|argentina|uruguay|paraguay|chile|colombia|peru|ecuador|bolivia|venezuela)\b/gi, " ")
    .replace(/[^a-zA-Z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function makeRefereeId(name) {
  return normalizeRefereeName(name).replace(/\s+/g, "_");
}

function round(value, decimals = 1) {
  if (!Number.isFinite(value)) return 0;
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function loadRefereeProfiles(options = {}) {
  const file = options.file || REFEREE_FILE;
  if (!fs.existsSync(file)) return [];
  const profiles = JSON.parse(fs.readFileSync(file, "utf8"));
  return profiles.map((profile) => ({
    ...profile,
    id: profile.id || makeRefereeId(profile.referee),
    referee_normalized: normalizeRefereeName(profile.referee),
    confidence: Number(profile.confidence ?? confidenceFromMatches(profile.matches))
  }));
}

function confidenceFromMatches(matches) {
  const total = Number(matches || 0);
  if (total >= 30) return 100;
  if (total >= 20) return 95;
  if (total >= 15) return 90;
  if (total >= 10) return 80;
  if (total >= 5) return 70;
  return total > 0 ? 50 : 0;
}

function initialsMatch(input, candidate) {
  const inputParts = normalizeRefereeName(input).split(" ").filter(Boolean);
  const candidateParts = normalizeRefereeName(candidate).split(" ").filter(Boolean);
  if (inputParts.length < 2 || candidateParts.length < 2) return false;
  const lastInput = inputParts[inputParts.length - 1];
  const lastCandidate = candidateParts[candidateParts.length - 1];
  if (lastInput !== lastCandidate) return false;
  const firstInput = inputParts[0];
  const firstCandidate = candidateParts[0];
  return firstInput.length === 1
    ? firstCandidate.startsWith(firstInput)
    : firstCandidate === firstInput;
}

function partialNameMatch(input, candidate) {
  const inputParts = normalizeRefereeName(input).split(" ").filter((part) => part.length > 1);
  const candidateName = normalizeRefereeName(candidate);
  if (inputParts.length === 0) return false;
  return inputParts.every((part) => candidateName.split(" ").some((candidatePart) => candidatePart.startsWith(part)));
}

function unknownReferee(refereeName) {
  return {
    found: false,
    referee: normalizeText(refereeName),
    score: 0,
    confidence: 0,
    tier: "UNKNOWN"
  };
}

function findRefereeProfile(refereeName, options = {}) {
  if (!refereeName) return unknownReferee(refereeName);
  const profiles = options.profiles || loadRefereeProfiles(options);
  const id = makeRefereeId(refereeName);
  const normalized = normalizeRefereeName(refereeName);

  let profile = profiles.find((item) => item.id === id);
  if (!profile) profile = profiles.find((item) => normalizeRefereeName(item.referee) === normalized);
  if (!profile) profile = profiles.find((item) => initialsMatch(refereeName, item.referee));
  if (!profile) profile = profiles.find((item) => partialNameMatch(refereeName, item.referee));

  if (!profile) return unknownReferee(refereeName);

  return {
    found: true,
    ...profile,
    tier: profile.discipline_tier || "UNKNOWN",
    confidence: Number(profile.confidence ?? confidenceFromMatches(profile.matches))
  };
}

function getRefereeScore(refereeName, options = {}) {
  const profile = findRefereeProfile(refereeName, options);
  if (!profile.found) return profile;
  const tier = profile.discipline_tier || profile.tier || "UNKNOWN";
  const baseScore = TIER_SCORES[tier] ?? 0;
  const confidence = Number(profile.confidence ?? 0);
  return {
    found: true,
    referee: profile.referee,
    id: profile.id,
    tier,
    confidence,
    score: round(baseScore * (confidence / 100), 1),
    profile
  };
}

module.exports = {
  loadRefereeProfiles,
  normalizeRefereeName,
  makeRefereeId,
  findRefereeProfile,
  getRefereeScore
};
