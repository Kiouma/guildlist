import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

URL = "https://amonot.online/guilds?name=Lowly+People&status=all"

def scrape_guild():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(URL, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    guild_data = {
        "name": "Lowly People",
        "updated_at": datetime.utcnow().strftime("%d/%m/%Y às %H:%M UTC"),
        "owner": "",
        "founded": "",
        "total_members": 0,
        "members": []
    }

    # Dono e fundação
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        text = p.get_text(separator=" ", strip=True)
        if "Dono" in text:
            guild_data["owner"] = text.replace("Dono", "").strip()
        if "Fundada" in text:
            guild_data["founded"] = text.replace("Fundada em", "").strip()

    # Tenta pegar dono pelo layout de tabela/div
    all_text = soup.get_text(separator="\n")
    lines = [l.strip() for l in all_text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if line == "Dono" and i + 1 < len(lines):
            guild_data["owner"] = lines[i + 1]
        if line.startswith("Fundada em"):
            guild_data["founded"] = line.replace("Fundada em", "").strip()
        if line.startswith("Membros"):
            try:
                guild_data["total_members"] = int(lines[i + 1])
            except:
                pass

    # Membros — pega todas as linhas de tabela com dados
    rows = soup.find_all("tr")
    current_rank = ""

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            # Verifica se é linha de rank (th)
            headers_row = row.find_all("th")
            if headers_row:
                continue
            # Verifica se é cabeçalho de grupo (rank)
            rank_cell = row.find("td", colspan=True)
            if rank_cell:
                current_rank = rank_cell.get_text(strip=True)
            continue

        if len(cells) >= 5:
            name_tag = cells[0].find("a")
            name = name_tag.get_text(strip=True) if name_tag else cells[0].get_text(strip=True)

            try:
                level = int(cells[1].get_text(strip=True))
            except:
                level = 0
            try:
                resets = int(cells[2].get_text(strip=True))
            except:
                resets = 0

            vocation = cells[3].get_text(strip=True)
            nick = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            status_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            status = "online" if "Online" in status_text else "offline"

            if name and name not in ("Nome", ""):
                guild_data["members"].append({
                    "name": name,
                    "level": level,
                    "resets": resets,
                    "vocation": vocation,
                    "nick": nick,
                    "status": status,
                    "rank": current_rank
                })

    # Fallback: busca por links de personagem se a tabela não funcionou
    if not guild_data["members"]:
        char_links = soup.select("a[href*='/characters?name=']")
        for link in char_links:
            row = link.find_parent("tr")
            if not row:
                continue
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            name = link.get_text(strip=True)
            try:
                level = int(cells[1].get_text(strip=True))
            except:
                level = 0
            try:
                resets = int(cells[2].get_text(strip=True))
            except:
                resets = 0
            vocation = cells[3].get_text(strip=True)
            nick = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            status_raw = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            status = "online" if "Online" in status_raw else "offline"

            guild_data["members"].append({
                "name": name,
                "level": level,
                "resets": resets,
                "vocation": vocation,
                "nick": nick,
                "status": status,
                "rank": ""
            })

    guild_data["total_members"] = len(guild_data["members"])
    online_count = sum(1 for m in guild_data["members"] if m["status"] == "online")
    guild_data["online_count"] = online_count
    guild_data["offline_count"] = guild_data["total_members"] - online_count

    return guild_data


if __name__ == "__main__":
    data = scrape_guild()
    with open("guild_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Dados salvos! {data['total_members']} membros encontrados ({data['online_count']} online).")
