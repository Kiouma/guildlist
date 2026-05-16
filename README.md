# ⚔️ Lowly People — Painel da Guild

Painel web automático da guild **Lowly People** do servidor [AmonOT](https://amonot.online), com atualização horária dos dados de membros diretamente do site oficial.

🌐 **Acesse o painel:** `https://seu-usuario.github.io/lowly-people-guild`

---

## ✨ Funcionalidades

- Lista completa de membros com **cargo, level, resets, vocação e status**
- Indicador de **online / offline** em tempo real
- **Busca** por nome ou vocação
- **Filtros** rápidos: Todos / Online / Offline
- **Ordenação** clicável por qualquer coluna
- Links diretos para o perfil de cada personagem no AmonOT
- Atualização automática **a cada hora**, sem precisar fazer nada

---

## 📁 Estrutura do Repositório

```
├── index.html                        # Site do painel (frontend)
├── scraper.py                        # Script que coleta os dados do AmonOT
├── guild_data.json                   # Dados gerados automaticamente (não edite)
└── .github/
    └── workflows/
        └── update.yml                # Agendamento automático (GitHub Actions)
```

---

## 🚀 Como Publicar (primeira vez)

### 1. Subir os arquivos
Faça upload de `index.html`, `scraper.py` no repositório.
Crie o arquivo `.github/workflows/update.yml` com o conteúdo correspondente.

### 2. Ativar o GitHub Pages
- Vá em **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `main` / pasta: `/ (root)`
- Clique em **Save**

### 3. Rodar o scraper pela primeira vez
- Vá em **Actions → Atualizar Dados da Guild**
- Clique em **Run workflow**

O `guild_data.json` será gerado e o site já estará funcional.

---

## 🔄 Atualização Automática

O GitHub Actions roda o scraper **a cada hora** automaticamente.

Para rodar manualmente a qualquer momento:
> **Actions → Atualizar Dados da Guild → Run workflow**

Para mudar a frequência, edite a linha `cron:` no arquivo `update.yml`:

| Frequência | Valor do cron |
|---|---|
| A cada hora | `0 * * * *` |
| A cada 30 min | `0,30 * * * *` |
| Todo dia às 9h (Brasília) | `0 12 * * *` |

---

## 🛠️ Dependências

O scraper usa apenas bibliotecas Python padrão/leves, instaladas automaticamente pelo GitHub Actions:

- `requests` — requisições HTTP
- `beautifulsoup4` — parsing do HTML

---

## ⚠️ Aviso

Este projeto faz scraping público da página de guild do AmonOT exclusivamente para uso interno da staff. Nenhum dado sensível é coletado — apenas as informações já visíveis publicamente na página da guild.
