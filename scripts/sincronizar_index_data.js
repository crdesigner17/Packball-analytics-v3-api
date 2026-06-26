const fs = require('fs');
const path = require('path');

const root = process.cwd();
const docsDir = path.join(root, 'docs');
const dataDir = path.join(docsDir, 'data');
const indexPath = path.join(docsDir, 'index.html');

function dateKeyToTime(key) {
  const match = key.match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (!match) return Number.POSITIVE_INFINITY;
  const [, dd, mm, yyyy] = match;
  return Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd));
}

function readAllData() {
  if (!fs.existsSync(dataDir)) {
    throw new Error(`Pasta nao encontrada: ${dataDir}`);
  }

  const files = fs.readdirSync(dataDir)
    .filter((file) => /^\d{2}-\d{2}-\d{4}\.json$/.test(file))
    .sort((a, b) => dateKeyToTime(a.slice(0, -5)) - dateKeyToTime(b.slice(0, -5)));

  if (!files.length) {
    throw new Error(`Nenhum JSON diario encontrado em ${dataDir}`);
  }

  const allData = {};
  for (const file of files) {
    const key = file.slice(0, -5);
    const fullPath = path.join(dataDir, file);
    allData[key] = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
  }

  return allData;
}

function findConstObjectEnd(source, objectStart) {
  let depth = 0;
  let inString = false;
  let stringQuote = '';
  let escaping = false;

  for (let i = objectStart; i < source.length; i += 1) {
    const char = source[i];

    if (inString) {
      if (escaping) {
        escaping = false;
      } else if (char === '\\') {
        escaping = true;
      } else if (char === stringQuote) {
        inString = false;
      }
      continue;
    }

    if (char === '"' || char === "'") {
      inString = true;
      stringQuote = char;
      continue;
    }

    if (char === '{') depth += 1;
    if (char === '}') {
      depth -= 1;
      if (depth === 0) return i + 1;
    }
  }

  throw new Error('Nao consegui localizar o fim do objeto ALL_DATA no index.html');
}

function replaceAllData(html, allData) {
  const marker = 'const ALL_DATA';
  const markerIndex = html.indexOf(marker);
  if (markerIndex === -1) {
    throw new Error('Constante ALL_DATA nao encontrada no index.html');
  }

  const equalsIndex = html.indexOf('=', markerIndex);
  const objectStart = html.indexOf('{', equalsIndex);
  if (equalsIndex === -1 || objectStart === -1) {
    throw new Error('Formato invalido da constante ALL_DATA');
  }

  const objectEnd = findConstObjectEnd(html, objectStart);
  const semicolonEnd = html[objectEnd] === ';' ? objectEnd + 1 : objectEnd;
  const json = JSON.stringify(allData);

  return `${html.slice(0, markerIndex)}const ALL_DATA   = ${json};${html.slice(semicolonEnd)}`;
}

function ensureNoFutureDatesInHistorico(html) {
  const oldLine = "const dias=wmHistoricoDateFilter?.dates?.length ? allDias.filter(d=>wmHistoricoDateFilter.dates.includes(d)) : allDias;";
  const newLines = [
    "const diasBase=allDias.filter(d=>dateObj(d)<=dateObj(todayKey()));",
    "const dias=wmHistoricoDateFilter?.dates?.length ? diasBase.filter(d=>wmHistoricoDateFilter.dates.includes(d)) : diasBase;",
  ].join('\n  ');

  if (html.includes(newLines)) return html;
  if (!html.includes(oldLine)) return html;

  return html.replace(oldLine, newLines);
}

function main() {
  const allData = readAllData();
  let html = fs.readFileSync(indexPath, 'utf8');
  html = replaceAllData(html, allData);
  html = ensureNoFutureDatesInHistorico(html);
  fs.writeFileSync(indexPath, html, 'utf8');

  const keys = Object.keys(allData);
  console.log(`index.html sincronizado com ${keys.length} JSONs (${keys[0]} a ${keys[keys.length - 1]}).`);
}

main();
