import requests
from bs4 import BeautifulSoup
import json, re
from datetime import datetime, timezone, timedelta

BRASILIA   = timezone(timedelta(hours=-3))
GUILD_NAME = "Lowly People"
GUILD_URL  = "https://amonot.online/guilds?name=Lowly+People&status=all"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

def scrape_guild():
    now = datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M (Brasília)")

    r = requests.get(GUILD_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # ── Metadados ────────────────────────────────────────────────────────────
    owner, founded = "", ""

    for card in soup.select(".info-card"):
        label = card.select_one(".info-label")
        value = card.select_one(".info-value")
        if not label or not value:
            continue
        l = label.get_text(strip=True)
        v = value.get_text(strip=True)
        if "Dono" in l or "Owner" in l:
            owner = v
        elif "Fundada" in l or "Founded" in l:
            founded = v

    # ── Membros ───────────────────────────────────────────────────────────────
    # O site organiza: div.characters-section > div.form-section-title (cargo)
    #                                          > div.characters-table > div.char-table-row
    members = []

    for section in soup.select(".characters-section"):
        # Título do cargo ex: "The Leader (1)", "Vice-Leader (4)", "Member (57)"
        title_el = section.select_one(".form-section-title")
        rank = ""
        if title_el:
            raw = title_el.get_text(strip=True)
            rank = re.sub(r'\s*\(\d+\)\s*$', '', raw).strip()  # remove "(57)"

        for row in section.select(".char-table-row"):
            def span(label):
                el = row.select_one(f'span[data-label="{label}"]')
                return el.get_text(strip=True) if el else ""

            name = span("Nome")
            if not name:
                continue

            try:    level  = int(span("Level"))
            except: level  = 0
            try:    resets = int(span("Resets"))
            except: resets = 0

            vocation = span("Vocação") or span("Vocation")
            nick     = span("Nick")

            status_el = row.select_one('span[data-label="Status"] .badge')
            if status_el:
                status = "online" if "badge-success" in status_el.get("class", []) else "offline"
            else:
                status = "offline"

            members.append({
                "name":     name,
                "level":    level,
                "resets":   resets,
                "vocation": vocation,
                "nick":     nick,
                "status":   status,
                "rank":     rank,
            })

    online_count  = sum(1 for m in members if m["status"] == "online")
    offline_count = len(members) - online_count

    return {
        "name":          GUILD_NAME,
        "updated_at":    now,
        "owner":         owner,
        "founded":       founded,
        "total_members": len(members),
        "online_count":  online_count,
        "offline_count": offline_count,
        "members":       members,
    }


if __name__ == "__main__":
    print("🔄 Coletando dados da guild...")
    data = scrape_guild()

    with open("guild_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Salvo com sucesso!")
    print(f"   👑 Dono: {data['owner']}")
    print(f"   📅 Fundada: {data['founded']}")
    print(f"   👥 Total: {data['total_members']} membros")
    print(f"   🟢 Online: {data['online_count']}")
    print(f"   ⚫ Offline: {data['offline_count']}")
    print(f"   🕐 Atualizado: {data['updated_at']}")

    if data["members"]:
        print("\n📋 Primeiros 5 membros:")
        for m in data["members"][:5]:
            status_icon = "🟢" if m["status"] == "online" else "⚫"
            print(f"   {status_icon} {m['name']} [{m['rank']}] | Lv {m['level']} | {m['resets']} resets | {m['vocation']}")
    else:
        print("\n⚠ Nenhum membro encontrado.")
