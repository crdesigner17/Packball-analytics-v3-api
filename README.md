# ⚽ PackBall Analytics

Dashboard público de palpites de futebol, atualizado automaticamente via GitHub Actions.

**Taxa de acerto validada — Over 1.5 Gols: 88.6% (44 jogos)**

---

## 🚀 Como configurar do zero (15 minutos)

### 1. Criar o repositório no GitHub

1. Acesse [github.com/new](https://github.com/new)
2. Nome: `packball-analytics` (ou qualquer nome)
3. Marque **Public** (necessário para GitHub Pages gratuito)
4. Clique em **Create repository**

### 2. Fazer upload da estrutura

Você pode usar o GitHub Desktop (mais fácil) ou o terminal:

**Opção A — GitHub Desktop (recomendado):**
1. Baixe o [GitHub Desktop](https://desktop.github.com)
2. Clone o repositório que criou
3. Copie todos os arquivos desta pasta para dentro
4. Commit → Push

**Opção B — Terminal:**
```bash
git init
git remote add origin https://github.com/SEU_USUARIO/packball-analytics.git
git add .
git commit -m "Setup inicial"
git push -u origin main
```

### 3. Ativar GitHub Pages

1. No repositório → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` → pasta: `/docs`
4. Clique em **Save**
5. Aguarde 1-2 minutos → seu site estará em:
   `https://SEU_USUARIO.github.io/packball-analytics`

### 4. Adicionar CSVs do dia

Cada dia deve ter uma pasta com os 3 CSVs obrigatórios:

```
data/
└── csv/
    └── 30-05-2026/          ← pasta com a data no formato DD-MM-YYYY
        ├── PackBall_Custom_Geral_-_CR_Designer__30-05-2026.csv
        ├── PackBall_Custom_ESCANTEIOS__30-05-2026.csv
        └── PackBall_Custom_CARTÕES__30-05-2026.csv
```

**Como adicionar via GitHub (sem terminal):**
1. No repositório → clique em `data/csv/`
2. Clique em **Add file** → **Upload files**
3. Arraste os CSVs do dia
4. Na mensagem de commit: `CSVs 30/05/2026`
5. Clique em **Commit changes**

→ O pipeline roda automaticamente em segundos e o site atualiza.

### 5. Agendamento automático

O arquivo `.github/workflows/build.yml` já está configurado para rodar:
- **Todo dia às 07:00 UTC** (04:00 horário de Brasília)
- **Sempre que você faz upload de novos CSVs**
- **Manualmente** (Actions → Run workflow)

---

## 📁 Estrutura do Repositório

```
packball-analytics/
├── .github/
│   └── workflows/
│       └── build.yml          ← Automação GitHub Actions
├── data/
│   └── csv/
│       ├── 30-05-2026/        ← Uma pasta por dia
│       │   ├── *Geral*.csv
│       │   ├── *ESCANTEIOS*.csv
│       │   └── *CART*.csv
│       └── 31-05-2026/
│           └── ...
├── scripts/
│   ├── processar.py           ← Calcula todos os scores
│   └── gerar_site.py          ← Gera o HTML final
├── docs/
│   ├── index.html             ← Site público (gerado automaticamente)
│   └── data/
│       ├── index.json         ← Índice de todas as datas
│       ├── 30-05-2026.json    ← Dados por dia (gerado automaticamente)
│       └── ...
└── README.md
```

---

## 📊 Mercados Analisados

| Mercado | Status | Threshold |
|---------|--------|-----------|
| Over 1.5 Gols | ✅ Validado | ≥ 85% + Filtro 3 Vias |
| Escanteios Over 8.5 | ⚠️ Em validação | ≥ 75% provisório |
| Cartões Over 2.5 | ⚠️ Em observação | ≥ 75% |
| Over 2.5 Gols | 🔬 Em análise | — |
| BTTS | ❌ Não recomendado | 61.5% histórico |

---

## 🔄 Fluxo de Atualização

```
Você faz upload dos CSVs
        ↓
GitHub Actions detecta o push
        ↓
processar.py roda → gera JSONs em docs/data/
        ↓
gerar_site.py roda → gera docs/index.html
        ↓
GitHub commit automático
        ↓
GitHub Pages publica o site atualizado
```

Tempo total: ~30 segundos após o upload.

---

## ❓ Dúvidas Frequentes

**O site não atualizou após o upload dos CSVs**
→ Vá em Actions → verifique se o workflow rodou. Se deu erro, clique no workflow e veja o log.

**Quero ver palpites de vários dias ao mesmo tempo?**
→ Sim! O site mostra abas para cada data disponível. Basta ter CSVs de múltiplos dias em suas respectivas pastas.

**Posso rodar o pipeline manualmente?**
→ Sim. Actions → "PackBall Analytics — Build Diário" → Run workflow.

**Como testar localmente antes de publicar?**
```bash
pip install pandas numpy
python scripts/processar.py
python scripts/gerar_site.py
# Abrir docs/index.html no navegador
```

---

*PackBall Analytics v2.1 — Over 1.5 validado: 88.6% — Escanteios: índices corrigidos*

---

## 🔑 Configurar a chave da API

### No GitHub (para automação):
1. Repositório → **Settings** → **Secrets and variables** → **Actions**
2. Clique em **New repository secret**
3. Nome: `APIFOOTBALL_KEY`
4. Valor: sua chave da API-Football
5. Salvar

### Localmente:
```bash
python scripts/coletar.py --key SUA_CHAVE_AQUI --date today
```

### Parâmetros disponíveis:
| Parâmetro | Descrição |
|-----------|-----------|
| `--key`   | Chave API obrigatória |
| `--date`  | `today` (padrão) ou `2026-05-31` |
| `--season`| Temporada (padrão: 2025) |
| `--no-site` | Não regenera o HTML |

## 📊 Estimativa de chamadas API por dia

| Liga | Chamadas estimadas |
|------|-------------------|
| 1 liga, 5 jogos | ~55 chamadas |
| Todas as ligas (~19), dia normal | ~400–800 chamadas |
| Plano Free (100/dia) | Suficiente para 1-2 ligas |
| Plano Pro (7500/hora) | Suficiente para todas |

> **Dica:** No plano Free, rode o script para apenas as ligas do dia que você quer analisar, limitando o dict `LIGAS` no `coletar.py`.
