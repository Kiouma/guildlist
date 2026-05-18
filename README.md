# ⚔️ Lowly People — Painel da Guild

Painel web completo da guild **Lowly People** do servidor [AmonOT](https://amonot.online) (World: Baiak), com atualização automática horária de todos os dados.

🌐 **Acesse o painel:** `(https://lowly-people.vercel.app/)`

---

## ✨ Funcionalidades

### 🏰 Guild
- Lista completa de membros com **cargo, level, resets, vocação e status online/offline**
- Botão de expandir por membro mostrando **histórico dos últimos 7 resets** e **mortes recentes**
- Filtros rápidos: Todos / Online / Offline
- Busca por nome ou vocação
- Ordenação clicável por qualquer coluna

### 🏆 Ranking
- Rankings internos da guild por categoria: **Resets, Experience, Magic Level, Fist, Club, Sword, Axe, Distance, Shielding, Fishing**
- Stats coletados do perfil individual de cada membro
- Medalhas ouro/prata/bronze para o top 3

### 🔄 Resets do Dia
- Membros que fizeram reset nas últimas 24h (período 22h→22h, horário Brasília)
- Mostra quantos resets foram feitos no dia e nos **últimos 7 dias**
- Baseado em snapshots horários — precisão de 1 hora

### ⚔️ PvP
- Abates de cada membro detectados nas páginas de Últimas Mortes (PvP) de Baiak
- Colunas: **Total, Semana e Hoje**
- Badge vermelho para membros com 3+ abates no dia

### 🛠️ Ferramentas (Calculadoras)
- **Ascensão** — distribua pontos com barra arrastável, limite de 500 por atributo, bônus por ponto, custo de reset acumulado
- **Reroll de Atributos** — probabilidade de sair atributos desejados, custo em tokens e KK
- **Upgrade de Item** — chances por nível, tentativas médias e custo esperado em tokens

---

## 📁 Estrutura do Repositório

```
├── index.html                        # Site do painel (frontend)
├── scraper.py                        # Script que coleta todos os dados
├── guild_data.json                   # Dados gerados automaticamente (não edite)
└── .github/
    └── workflows/
        └── update.yml                # Agendamento automático (GitHub Actions)
```

---

## 🔄 Dados Coletados Automaticamente

A cada hora o scraper coleta:

| Dado | Fonte |
|---|---|
| Lista de membros + status online/offline | `/guilds?name=Lowly+People&status=online` e `offline` |
| Stats individuais (skills, exp) | `/characters?name=X` para cada membro |
| Mortes recentes | `/index.php?page=lastkills&world=Baiak` |
| Abates PvP | `/index.php?page=lastkills&world=Baiak&type=pvp` |
| Snapshots horários de resets | Comparação com run anterior |

---

## 🚀 Como Publicar (primeira vez)

**1. Subir os arquivos**
Faça upload de `index.html`, `scraper.py` e `.github/workflows/update.yml` no repositório.

**2. Ativar o GitHub Pages**
- Vá em **Settings → Pages**
- Source: **Deploy from a branch** → branch `main` / pasta `/ (root)`
- Clique em **Save**

**3. Rodar o scraper pela primeira vez**
- Vá em **Actions → Atualizar Dados da Guild → Run workflow**

O `guild_data.json` será gerado e o site já estará funcional.

---

## ⏱️ Agendamento Automático

O GitHub Actions roda o scraper **a cada hora** automaticamente.

Para rodar manualmente:
> **Actions → Atualizar Dados da Guild → Run workflow**

Para mudar a frequência, edite a linha `cron:` no `update.yml`:

| Frequência | Valor |
|---|---|
| A cada hora | `0 * * * *` |
| A cada 30 min | `0,30 * * * *` |
| Todo dia às 9h (Brasília) | `0 12 * * *` |

---

## 🛠️ Dependências

Instaladas automaticamente pelo GitHub Actions:

```
requests
beautifulsoup4
```

---

## ⚠️ Observações

- O status online/offline é buscado via duas URLs separadas (`?status=online` e `?status=offline`) para garantir precisão
- Os resets do dia acumulam a partir da primeira execução — os dados de 7 dias ficam completos após 7 dias de execuções horárias
- Os abates PvP são contados a partir das páginas públicas de Últimas Mortes — mortes antigas fora do alcance das páginas não são contabilizadas
- Este projeto faz scraping de dados públicos do AmonOT exclusivamente para uso interno da staff
