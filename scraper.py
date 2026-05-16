import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta

# Horário de Brasília (UTC-3)
BRASILIA = timezone(timedelta(hours=-3))

GUILD_NAME = "Lowly People"
BASE_URL   = "https://amonot.online"
GUILD_URL  = f"{BASE_URL}/guilds?name=Lowly+People"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

# ── Tentativa 1: API JSON ──────────────────────────────────────────────────
def try_api():
    candidates = [
        f"{BASE_URL}/api/guilds?name=Lowly+People",
        f"{BASE_URL}/api/guild?name=Lowly+People",
        f"{BASE_URL}/api/guilds/Lowly+People",
    ]
    for url in candidates:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and "json" in r.headers.get("Content-Type", ""):
                data = r.json()
                print(f"✅ API encontrada: {url}")
                return data
        except Exception:
            pass
    return None

# ── Tentativa 2: Scraping HTML ─────────────────────────────────────────────
def try_html_scraping():
    r = requests.get(GUILD_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    members = []
    current_rank = ""

    for row in soup.find_all("tr"):
        cells = row.find_all("td")

        if len(cells) == 1 and cells[0].get("colspan"):
            current_rank = cells[0].get_text(strip=True)
            continue

        if not cells:
            continue

        if len(cells) >= 4:
            name_tag = cells[0].find("a")
            name = name_tag.get_text(strip=True) if name_tag else cells[0].get_text(strip=True)

            if not name or name in ("Nome", "Name", ""):
                continue

            try:    level  = int(cells[1].get_text(strip=True))
            except: level  = 0
            try:    resets = int(cells[2].get_text(strip=True))
            except: resets = 0

            vocation   = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            nick       = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            status_raw = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            status     = "online" if "online" in status_raw.lower() else "offline"

            members.append({
                "name": name, "level": level, "resets": resets,
                "vocation": vocation, "nick": nick, "status": status, "rank": current_rank,
            })

    # Fallback por links
    if not members:
        print("⚠ Tabela padrão não encontrada, tentando fallback por links...")
        for link in soup.select("a[href*='characters']"):
            row = link.find_parent("tr")
            if not row:
                continue
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            name = link.get_text(strip=True)
            if not name:
                continue
            try:    level  = int(cells[1].get_text(strip=True))
            except: level  = 0
            try:    resets = int(cells[2].get_text(strip=True))
            except: resets = 0
            vocation   = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            nick       = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            status_raw = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            status     = "online" if "online" in status_raw.lower() else "offline"
            members.append({
                "name": name, "level": level, "resets": resets,
                "vocation": vocation, "nick": nick, "status": status, "rank": "",
            })

    # Metadados
    owner, founded = "", ""
    lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if line in ("Dono", "Owner", "Leader") and i + 1 < len(lines):
            owner = lines[i + 1]
        if "Fundada em" in line or "Founded" in line:
            founded = line.split("em")[-1].strip() if "em" in line else line

    print(f"📄 HTML scraping: {len(members)} membros encontrados")
    return {"owner": owner, "founded": founded, "members": members}

# ── Montagem final ─────────────────────────────────────────────────────────
def scrape_guild():
    now_brasilia = datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M (Brasília)")
    raw = try_api() or try_html_scraping()
    members = raw.get("members", [])
    if not isinstance(members, list):
        members = []

    online_count  = sum(1 for m in members if str(m.get("status", "")).lower() == "online")
    offline_count = len(members) - online_count

    return {
        "name":          GUILD_NAME,
        "updated_at":    now_brasilia,
        "owner":         raw.get("owner", ""),
        "founded":       raw.get("founded", ""),
        "total_members": len(members),
        "online_count":  online_count,
        "offline_count": offline_count,
        "members":       members,
    }


if __name__ == "__main__":
    print("🔄 Iniciando coleta de dados...")
    data = scrape_guild()

    with open("guild_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ guild_data.json salvo!")
    print(f"   👥 Total: {data['total_members']} membros")
    print(f"   🟢 Online: {data['online_count']}")
    print(f"   ⚫ Offline: {data['offline_count']}")
    print(f"   🕐 Atualizado: {data['updated_at']}")

    if data["members"]:
        print("\n📋 Primeiros membros:")
        for m in data["members"][:5]:
            print(f"   - {m['name']} | Level {m['level']} | {m['vocation']} | {m['status']}")
    else:
        print("\n⚠ ATENÇÃO: Nenhum membro encontrado! Salvando debug_page.html...")
        try:
            r = requests.get(GUILD_URL, headers=HEADERS, timeout=15)
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("   📄 debug_page.html salvo. Verifique o HTML recebido.")
        except Exception as e:
            print(f"   Erro ao salvar debug: {e}")
