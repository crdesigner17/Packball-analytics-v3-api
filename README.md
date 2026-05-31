# ⚽ WinMetrics - AI Sports Analytics

Dashboard de análise estatística profissional para apostas esportivas.

**Taxa de acerto validada — Over 1.5 Gols: 88.6%**

🌐 **Site:** https://crdesigner17.github.io/winmetrics-analytics

---

## 🏆 Mercados Analisados

| Mercado | Status | Threshold |
|---------|--------|-----------|
| Over 1.5 Gols | ✅ Validado 88.6% | ≥80% + Filtro Vias |
| Escanteios Over 7.5 | ⚠️ Em validação | ≥75% |
| Escanteios Over 8.5 | ⚠️ Em validação | ≥75% |
| Cartões Over 2.5 | ⚠️ Em observação | ≥75% |
| Under 4.5 Gols | 🆕 Novo | ≥75% |

## 📈 Grade Profissional

| Grade | Score | Risco |
|-------|-------|-------|
| A+ | ≥88% | Muito Baixo |
| A | ≥80% | Baixo |
| B | ≥70% | Médio |
| C | ≥60% | Alto |
| D | <60% | Muito Alto |

## 🚀 Pipeline

- **04h (Brasília)** → `coletar.py` busca jogos na API-Football
- **A cada hora** → `confirmar.py` atualiza resultados finalizados
- **Automático** → `gerar_site.py` publica o dashboard

## 🔑 Secrets necessários

| Secret | Descrição |
|--------|-----------|
| `APIFOOTBALL_KEY` | Chave da API-Football |

---

*WinMetrics v3.1 — Powered by API-Football*
