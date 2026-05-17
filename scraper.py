import requests
from bs4 import BeautifulSoup
import json, re, time
from datetime import datetime, timezone, timedelta

BRASILIA   = timezone(timedelta(hours=-3))
GUILD_NAME = "Lowly People"
GUILD_URL  = "https://amonot.online/guilds?name=Lowly+People&status=all"
KILLS_URL  = "https://amonot.online/lastkills?world=Baiak&type=pvp"
KILLS_ALL_URL = "https://amonot.online/lastkills?world=Baiak"
MAX_RESET_HISTORY = 7
MAX_DEATH_HISTORY = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

def now_str():
    return datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")

def scrape_guild_members():
    r = requests.get(GUILD_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

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

    members = []
    for section in soup.select(".characters-section"):
        title_el = section.select_one(".form-section-title")
        rank = ""
        if title_el:
            raw = title_el.get_text(strip=True)
            rank = re.sub(r'\s*\(\d+\)\s*$', '', raw).strip()

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
            status = "online" if status_el and "badge-success" in status_el.get("class", []) else "offline"

            members.append({
                "name": name, "level": level, "resets": resets,
                "vocation": vocation, "nick": nick,
                "status": status, "rank": rank,
            })

    return members, owner, founded


def scrape_deaths(member_names_lower, pages=4):
    """Scrape last kills pages and return deaths filtered to guild members."""
    deaths_by_member = {}  # name_lower -> list of death dicts

    for page in range(1, pages + 1):
        url = KILLS_ALL_URL + (f"&p={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠ Erro ao buscar mortes pág {page}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tr")
        found_any = False

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            time_text = cells[0].get_text(strip=True)
            name_tag  = cells[1].find("a")
            if not name_tag:
                continue

            player_name = name_tag.get_text(strip=True)
            name_lower  = player_name.lower()

            if name_lower not in member_names_lower:
                continue

            found_any = True
            try:    death_level = int(cells[2].get_text(strip=True))
            except: death_level = 0

            killed_by = cells[3].get_text(strip=True)
            world     = cells[4].get_text(strip=True) if len(cells) > 4 else ""

            # Determine if PvP (killed by a player name, not "monstro")
            is_pvp = "(monstro)" not in killed_by.lower()

            entry = {
                "time":    time_text,
                "level":   death_level,
                "by":      killed_by,
                "is_pvp":  is_pvp,
                "world":   world,
            }

            canonical = member_names_lower[name_lower]
            if canonical not in deaths_by_member:
                deaths_by_member[canonical] = []
            deaths_by_member[canonical].append(entry)

        time.sleep(0.3)

    # Trim to MAX_DEATH_HISTORY per member
    for name in deaths_by_member:
        deaths_by_member[name] = deaths_by_member[name][:MAX_DEATH_HISTORY]

    return deaths_by_member


def update_reset_history(members, previous_data):
    """Compare resets vs previous run; record timestamp when reset count changes."""
    prev_map = {}
    if previous_data:
        for m in previous_data.get("members", []):
            prev_map[m["name"].lower()] = m

    for m in members:
        key = m["name"].lower()
        prev = prev_map.get(key, {})
        prev_resets  = prev.get("resets", None)
        prev_history = prev.get("reset_history", [])

        if prev_resets is not None and m["resets"] != prev_resets:
            # Reset count changed — record event
            new_entry = {
                "resets": m["resets"],
                "time":   now_str(),
            }
            prev_history = [new_entry] + prev_history
            prev_history = prev_history[:MAX_RESET_HISTORY]

        m["reset_history"] = prev_history

    return members


def load_previous(path="guild_data.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def scrape_guild():
    timestamp = datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M (Brasília)")

    print("  → Coletando membros da guild...")
    members, owner, founded = scrape_guild_members()

    print(f"  → {len(members)} membros encontrados. Verificando histórico de resets...")
    previous = load_previous()
    members = update_reset_history(members, previous)

    # Map lowercase name -> canonical name for fast lookup
    member_names_lower = {m["name"].lower(): m["name"] for m in members}

    print("  → Coletando mortes do servidor (últimas páginas)...")
    deaths_by_member = scrape_deaths(member_names_lower, pages=4)

    pvp_kills_count = {}
    if previous:
        for m in previous.get("members", []):
            pvp_kills_count[m["name"]] = m.get("pvp_kills", 0)

    # Attach deaths to members
    for m in members:
        name = m["name"]
        m["deaths"] = deaths_by_member.get(name, [])

        # Count PvP kills from deaths where another guild member killed this player
        # (approximation: count entries where is_pvp=True and "Maior dano" isn't present)
        pvp_deaths = [d for d in m["deaths"] if d["is_pvp"]]
        m["pvp_deaths_recent"] = len(pvp_deaths)

    online_count  = sum(1 for m in members if m["status"] == "online")
    offline_count = len(members) - online_count

    return {
        "name":          GUILD_NAME,
        "updated_at":    timestamp,
        "owner":         owner,
        "founded":       founded,
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

    print(f"\n✅ guild_data.json salvo!")
    print(f"   👑 Dono:    {data['owner']}")
    print(f"   📅 Fundada: {data['founded']}")
    print(f"   👥 Total:   {data['total_members']} membros")
    print(f"   🟢 Online:  {data['online_count']}")
    print(f"   ⚫ Offline: {data['offline_count']}")
    print(f"   🕐 Em:      {data['updated_at']}")

    resets_tracked = sum(1 for m in data["members"] if m.get("reset_history"))
    deaths_tracked = sum(1 for m in data["members"] if m.get("deaths"))
    print(f"   📈 Com histórico de resets: {resets_tracked}")
    print(f"   💀 Com mortes registradas:  {deaths_tracked}")

    if data["members"]:
        print("\n📋 Amostra (5 primeiros):")
        for m in data["members"][:5]:
            icon = "🟢" if m["status"] == "online" else "⚫"
            rh = len(m.get("reset_history", []))
            dh = len(m.get("deaths", []))
            print(f"   {icon} {m['name']} | Lv {m['level']} | {m['resets']}R | {m['vocation']} | resets_hist={rh} mortes={dh}")
