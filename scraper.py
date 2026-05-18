import requests
from bs4 import BeautifulSoup
import json, re, time
from datetime import datetime, timezone, timedelta

BRASILIA          = timezone(timedelta(hours=-3))
GUILD_NAME        = "Lowly People"
GUILD_URL         = "https://amonot.online/guilds?name=Lowly+People&status=all"
KILLS_ALL_URL     = "https://amonot.online/lastkills?world=Baiak"
HIGHSCORES_BASE   = "https://amonot.online/index.php?page=highscores&skill={cat}&vocation=all&world=3"
MAX_RESET_HISTORY = 7
MAX_DEATH_HISTORY = 30

# Categorias padrão do highscore (skill= param na URL)
HIGHSCORE_CATS = [
    ("resets",      "Resets",      "Resets"),
    ("experience",  "Experience",  "Experience"),
    ("magic",       "Magic Level", "Skill"),
    ("fist",        "Fist",        "Skill"),
    ("club",        "Club",        "Skill"),
    ("sword",       "Sword",       "Skill"),
    ("axe",         "Axe",         "Skill"),
    ("distance",    "Distance",    "Skill"),
    ("shielding",   "Shielding",   "Skill"),
    ("fishing",     "Fishing",     "Skill"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

def now_str():
    return datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")

def brasilia_now():
    return datetime.now(BRASILIA)

def guild_day_start():
    now = brasilia_now()
    today_5am = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now < today_5am:
        today_5am -= timedelta(days=1)
    return today_5am

def guild_week_start():
    start = guild_day_start()
    return start - timedelta(days=start.weekday())

def parse_death_time(time_str):
    try:
        dt = datetime.strptime(time_str.strip(), "%b %d, %Y %H:%M")
        return dt.replace(tzinfo=BRASILIA)
    except Exception:
        return None

# ── Guild members ────────────────────────────────────────────────────────────
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
            def span(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(strip=True) if el else ""

            name = span("Nome")
            if not name:
                continue
            try:    level  = int(span("Level"))
            except: level  = 0
            try:    resets = int(span("Resets"))
            except: resets = 0

            vocation  = span("Vocação") or span("Vocation")
            nick      = span("Nick")
            status_el = row.select_one('span[data-label="Status"] .badge')
            status    = "online" if status_el and "badge-success" in status_el.get("class", []) else "offline"

            members.append({
                "name": name, "level": level, "resets": resets,
                "vocation": vocation, "nick": nick,
                "status": status, "rank": rank,
            })
    return members, owner, founded

# ── Highscores ───────────────────────────────────────────────────────────────
def scrape_highscore_category(cat_key, member_names_lower, pages=15):
    results = []
    seen = set()
    for page in range(1, pages + 1):
        url = HIGHSCORES_BASE.format(cat=cat_key) + (f"&p={page}" if page > 1 else "&p=1")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"    ⚠ {cat_key} pág {page}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tr")
        found_on_page = False

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            try:
                global_rank = int(cells[0].get_text(strip=True))
            except:
                continue

            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if name.lower() not in member_names_lower:
                continue

            found_on_page = True
            if name.lower() in seen:
                continue
            seen.add(name.lower())

            try:    level = int(cells[2].get_text(strip=True))
            except: level = 0
            vocation  = cells[3].get_text(strip=True)
            value_fmt = cells[4].get_text(strip=True)
            value_raw = re.sub(r'[^\d]', '', value_fmt)
            try:    value = int(value_raw)
            except: value = 0

            results.append({
                "rank":      global_rank,
                "name":      name,
                "level":     level,
                "vocation":  vocation,
                "value":     value,
                "value_fmt": value_fmt,
            })

        time.sleep(0.25)
        # Stop if no guild member found on this page and we already have results
        if not found_on_page and len(results) > 0 and page > 3:
            break

    results.sort(key=lambda x: x["rank"])
    for i, entry in enumerate(results):
        entry["guild_rank"] = i + 1
    return results

def scrape_highscores(member_names_lower):
    print("  → Coletando highscores...")
    highscores = {}
    for cat_key, cat_name, val_label in HIGHSCORE_CATS:
        print(f"    • {cat_name}...")
        entries = scrape_highscore_category(cat_key, member_names_lower)
        highscores[cat_key] = {
            "name":      cat_name,
            "val_label": val_label,
            "entries":   entries,
        }
        time.sleep(0.3)
    return highscores

# ── Deaths ───────────────────────────────────────────────────────────────────
def scrape_deaths(member_names_lower, pages=6):
    deaths_by_member = {}
    for page in range(1, pages + 1):
        url = KILLS_ALL_URL + (f"&p={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠ Mortes pág {page}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            time_text = cells[0].get_text(strip=True)
            name_tag  = cells[1].find("a")
            if not name_tag:
                continue
            player_name = name_tag.get_text(strip=True)
            if player_name.lower() not in member_names_lower:
                continue
            try:    dlevel = int(cells[2].get_text(strip=True))
            except: dlevel = 0
            killed_by = cells[3].get_text(strip=True)
            is_pvp    = "(monstro)" not in killed_by.lower()
            canonical = member_names_lower[player_name.lower()]
            deaths_by_member.setdefault(canonical, []).append({
                "time": time_text, "level": dlevel,
                "by": killed_by, "is_pvp": is_pvp,
            })
        time.sleep(0.25)

    for name in deaths_by_member:
        deaths_by_member[name] = deaths_by_member[name][:MAX_DEATH_HISTORY]
    return deaths_by_member

# ── PvP kills ────────────────────────────────────────────────────────────────
def scrape_pvp_kills(member_names_lower, pages=6):
    kills_total = {}
    kills_today = {}
    kills_week  = {}
    day_start   = guild_day_start()
    week_start  = guild_week_start()
    pvp_url     = "https://amonot.online/lastkills?world=Baiak&type=pvp"

    for page in range(1, pages + 1):
        url = pvp_url + (f"&p={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠ PvP pág {page}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        found_any = False
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            time_text  = cells[0].get_text(strip=True)
            killed_by  = cells[3].get_text(separator=" ", strip=True)
            if "(monstro)" in killed_by.lower():
                continue

            killer = None
            for lower_name, canonical in member_names_lower.items():
                if lower_name in killed_by.lower():
                    killer = canonical
                    break
            if not killer:
                continue

            found_any = True
            kills_total[killer] = kills_total.get(killer, 0) + 1
            dt = parse_death_time(time_text)
            if dt:
                if dt >= day_start:
                    kills_today[killer] = kills_today.get(killer, 0) + 1
                if dt >= week_start:
                    kills_week[killer] = kills_week.get(killer, 0) + 1

        time.sleep(0.25)
        if not found_any and page > 2:
            break

    return kills_total, kills_today, kills_week

# ── Reset history ────────────────────────────────────────────────────────────
def update_reset_history(members, previous_data):
    prev_map = {}
    if previous_data:
        for m in previous_data.get("members", []):
            prev_map[m["name"].lower()] = m

    for m in members:
        key  = m["name"].lower()
        prev = prev_map.get(key, {})
        prev_resets  = prev.get("resets", None)
        prev_history = list(prev.get("reset_history", []))
        if prev_resets is not None and m["resets"] != prev_resets:
            prev_history = [{"resets": m["resets"], "time": now_str()}] + prev_history
            prev_history = prev_history[:MAX_RESET_HISTORY]
        m["reset_history"] = prev_history
    return members

def load_previous(path="guild_data.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def compute_resets_today(members):
    day_start = guild_day_start()
    today = []
    for m in members:
        for entry in m.get("reset_history", []):
            try:
                dt = datetime.strptime(entry["time"], "%d/%m/%Y %H:%M").replace(tzinfo=BRASILIA)
                if dt >= day_start:
                    today.append({
                        "name":     m["name"],
                        "resets":   entry["resets"],
                        "time":     entry["time"],
                        "vocation": m.get("vocation", ""),
                    })
            except Exception:
                pass
    today.sort(key=lambda x: x["time"], reverse=True)
    return today

# ── Main ─────────────────────────────────────────────────────────────────────
def scrape_guild():
    timestamp = datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M (Brasília)")

    print("  → Membros...")
    members, owner, founded = scrape_guild_members()
    previous = load_previous()
    members  = update_reset_history(members, previous)
    member_names_lower = {m["name"].lower(): m["name"] for m in members}

    print("  → Mortes...")
    deaths_by_member = scrape_deaths(member_names_lower, pages=6)

    print("  → Abates PvP...")
    kills_total, kills_today, kills_week = scrape_pvp_kills(member_names_lower, pages=6)

    highscores = scrape_highscores(member_names_lower)

    for m in members:
        name = m["name"]
        m["deaths"]          = deaths_by_member.get(name, [])
        m["pvp_kills_total"] = kills_total.get(name, 0)
        m["pvp_kills_today"] = kills_today.get(name, 0)
        m["pvp_kills_week"]  = kills_week.get(name, 0)

    resets_today = compute_resets_today(members)
    online_count  = sum(1 for m in members if m["status"] == "online")
    offline_count = len(members) - online_count

    return {
        "name":            GUILD_NAME,
        "updated_at":      timestamp,
        "owner":           owner,
        "founded":         founded,
        "total_members":   len(members),
        "online_count":    online_count,
        "offline_count":   offline_count,
        "guild_day_start": guild_day_start().strftime("%d/%m/%Y %H:%M"),
        "members":         members,
        "resets_today":    resets_today,
        "highscores":      highscores,
    }


if __name__ == "__main__":
    print("🔄 Iniciando coleta completa...")
    data = scrape_guild()
    with open("guild_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Salvo!")
    print(f"   👥 Membros:     {data['total_members']}")
    print(f"   🟢 Online:      {data['online_count']}")
    print(f"   🔄 Resets hoje: {len(data['resets_today'])}")
    print(f"   🕐 Em:          {data['updated_at']}")
    for cat_key, cat in data["highscores"].items():
        print(f"   🏆 {cat['name']}: {len(cat['entries'])} membros no ranking")
    if data["members"]:
        print("\n📋 Amostra (3 primeiros):")
        for m in data["members"][:3]:
            icon = "🟢" if m["status"] == "online" else "⚫"
            print(f"   {icon} {m['name']} | {m['resets']}R | kills: {m['pvp_kills_total']} total / {m['pvp_kills_today']} hoje")
