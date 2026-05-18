import requests
from bs4 import BeautifulSoup
import json, re, time
from datetime import datetime, timezone, timedelta

BRASILIA          = timezone(timedelta(hours=-3))
GUILD_NAME        = "Lowly People"
GUILD_URL         = "https://amonot.online/guilds?name=Lowly+People&status=all"
KILLS_PVP_URL     = "https://amonot.online/index.php?page=lastkills&world=Baiak&type=pvp"
KILLS_ALL_URL     = "https://amonot.online/index.php?page=lastkills&world=Baiak"
CHAR_URL          = "https://amonot.online/characters?name={name}"
MAX_RESET_HISTORY = 7
MAX_DEATH_HISTORY = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

SKILL_KEYS = ["experience", "magic", "fist", "club", "sword", "axe", "distance", "shielding", "fishing"]
SKILL_LABELS = {
    "resets":     "Resets",
    "experience": "Experience",
    "magic":      "Magic Level",
    "fist":       "Fist",
    "club":       "Club",
    "sword":      "Sword",
    "axe":        "Axe",
    "distance":   "Distance",
    "shielding":  "Shielding",
    "fishing":    "Fishing",
}

def now_str():
    return datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")

def brasilia_now():
    return datetime.now(BRASILIA)

def guild_day_start():
    """Day boundary is 22:00 Brasília. Returns start of current guild day."""
    now = brasilia_now()
    today_22 = now.replace(hour=22, minute=0, second=0, microsecond=0)
    if now < today_22:
        today_22 -= timedelta(days=1)
    return today_22

def guild_week_start():
    start = guild_day_start()
    return start - timedelta(days=start.weekday())

def hour_key(dt=None):
    """Hourly snapshot key: YYYY-MM-DD-HH (Brasília)."""
    if dt is None:
        dt = brasilia_now()
    return dt.strftime("%Y-%m-%d-%H")

def hour_key_n_hours_ago(n):
    return hour_key(brasilia_now() - timedelta(hours=n))

def parse_death_time(time_str):
    try:
        dt = datetime.strptime(time_str.strip(), "%b %d, %Y %H:%M")
        return dt.replace(tzinfo=BRASILIA)
    except Exception:
        return None

# ── Guild members ─────────────────────────────────────────────────────────────
def fetch_members_from_url(url, forced_status=None):
    """Fetch members from a guild URL. If forced_status given, override all status values."""
    r = requests.get(url, headers=HEADERS, timeout=15)
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

            vocation = span("Vocação") or span("Vocation")
            nick     = span("Nick")

            if forced_status:
                status = forced_status
            else:
                status_el = row.select_one('span[data-label="Status"] .badge')
                if status_el:
                    status = "online" if "badge-success" in status_el.get("class", []) else "offline"
                else:
                    status_span = row.select_one('span[data-label="Status"]')
                    status = "online" if status_span and "online" in status_span.get_text(strip=True).lower() else "offline"

            members.append({
                "name": name, "level": level, "resets": resets,
                "vocation": vocation, "nick": nick,
                "status": status, "rank": rank,
            })
    return members, owner, founded

def scrape_guild_members():
    """Fetch online and offline members separately to guarantee correct status."""
    # Fetch online members
    url_online  = "https://amonot.online/guilds?name=Lowly+People&status=online"
    url_offline = "https://amonot.online/guilds?name=Lowly+People&status=offline"

    online_members,  owner,   founded = fetch_members_from_url(url_online,  forced_status="online")
    time.sleep(0.5)
    offline_members, _, _ = fetch_members_from_url(url_offline, forced_status="offline")

    # Merge: use name as key to avoid duplicates
    seen = set()
    members = []
    for m in online_members + offline_members:
        if m["name"] not in seen:
            seen.add(m["name"])
            members.append(m)

    online = sum(1 for m in members if m["status"] == "online")
    print(f"    → {len(members)} membros: {online} online, {len(members)-online} offline")
    return members, owner, founded

# ── Character profile → extract skills/exp ───────────────────────────────────
def scrape_char_stats(name):
    """Fetch character page and extract experience + skills."""
    url = CHAR_URL.format(name=requests.utils.quote(name))
    stats = {k: 0 for k in SKILL_KEYS}
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return stats
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        # Pattern: label on one line, value on next (or nearby)
        skill_map = {
            "Experience": "experience",
            "Magic Level": "magic",
            "Magic level": "magic",
            "Fist Fighting": "fist",
            "Fist fighting": "fist",
            "Club Fighting": "club",
            "Club fighting": "club",
            "Sword Fighting": "sword",
            "Sword fighting": "sword",
            "Axe Fighting": "axe",
            "Axe fighting": "axe",
            "Distance Fighting": "distance",
            "Distance fighting": "distance",
            "Shielding": "shielding",
            "Fishing": "fishing",
        }
        for i, line in enumerate(lines):
            for label, key in skill_map.items():
                if line.strip() == label and i + 1 < len(lines):
                    val_raw = re.sub(r'[^\d]', '', lines[i + 1])
                    if val_raw:
                        try:
                            stats[key] = int(val_raw)
                        except:
                            pass
                    break

        # Also try table rows: <td>Experience Points</td><td>1,234,567</td>
        for row in soup.select("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                lbl = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                for label, key in skill_map.items():
                    if label.lower() in lbl.lower():
                        val_raw = re.sub(r'[^\d]', '', val)
                        if val_raw:
                            try:
                                stats[key] = int(val_raw)
                            except:
                                pass

        # Try info-card / info-value pattern (same as guild page)
        for card in soup.select(".info-card, .character-info, .stat-box, [class*='stat'], [class*='skill']"):
            label_el = card.select_one(".info-label, .stat-label, .skill-name, th, label")
            value_el = card.select_one(".info-value, .stat-value, .skill-value, td, span")
            if label_el and value_el:
                lbl = label_el.get_text(strip=True)
                val = value_el.get_text(strip=True)
                for label, key in skill_map.items():
                    if label.lower() in lbl.lower():
                        val_raw = re.sub(r'[^\d]', '', val)
                        if val_raw:
                            try:
                                stats[key] = int(val_raw)
                            except:
                                pass

    except Exception as e:
        print(f"    ⚠ {name}: {e}")
    return stats

def scrape_all_char_stats(members):
    """Fetch stats for all members and attach to each member dict."""
    total = len(members)
    for i, m in enumerate(members):
        print(f"    [{i+1}/{total}] {m['name']}...")
        stats = scrape_char_stats(m["name"])
        m["stats"] = stats
        time.sleep(0.3)
    return members

def build_rankings(members):
    """Build guild-internal rankings for each stat category."""
    rankings = {}
    all_cats = ["resets"] + SKILL_KEYS

    for cat in all_cats:
        if cat == "resets":
            entries = [{"name": m["name"], "value": m["resets"], "level": m["level"], "vocation": m["vocation"]} for m in members]
        else:
            entries = [{"name": m["name"], "value": m.get("stats", {}).get(cat, 0), "level": m["level"], "vocation": m["vocation"]} for m in members]

        entries.sort(key=lambda x: x["value"], reverse=True)
        for i, e in enumerate(entries):
            e["guild_rank"] = i + 1

        rankings[cat] = {
            "name":      SKILL_LABELS.get(cat, cat),
            "val_label": SKILL_LABELS.get(cat, cat),
            "entries":   entries,
        }
    return rankings

# ── Deaths ────────────────────────────────────────────────────────────────────
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
        for row in soup.select("div.char-table-row"):
            def sp(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(separator=" ", strip=True) if el else ""

            time_text   = sp("Hora")
            player_name = sp("Jogador Morto")
            # name may be inside an <a> tag
            name_tag = row.select_one('span[data-label="Jogador Morto"] a')
            if name_tag:
                player_name = name_tag.get_text(strip=True)
            if not player_name or player_name.lower() not in member_names_lower:
                continue
            level_raw = sp("Level")
            try:    dlevel = int(level_raw)
            except: dlevel = 0
            killed_by = sp("Morto Por")
            is_pvp    = "(jogador)" in killed_by.lower() or "(monstro)" not in killed_by.lower()
            canonical = member_names_lower[player_name.lower()]
            deaths_by_member.setdefault(canonical, []).append({
                "time": time_text, "level": dlevel,
                "by": killed_by, "is_pvp": is_pvp,
            })
        time.sleep(0.25)

    for name in deaths_by_member:
        deaths_by_member[name] = deaths_by_member[name][:MAX_DEATH_HISTORY]
    return deaths_by_member

# ── PvP kills ─────────────────────────────────────────────────────────────────
# Page uses div.char-table-row, each row has span[data-label] children:
# "Hora", "Jogador Morto", "Level", "Morto Por", "Mundo"
# Example row text: "May 17, 2026 21:59 Jotabringer 993 Sauron Knight (jogador) Maior dano: X Baiak"
def scrape_pvp_kills(member_names_lower, pages=6):
    kills_total = {}
    kills_today = {}
    kills_week  = {}
    day_start   = guild_day_start()
    week_start  = guild_week_start()

    for page in range(1, pages + 1):
        url = KILLS_PVP_URL + (f"&p={page}" if page > 1 else "")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"  ⚠ PvP pág {page}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("div.char-table-row")
        print(f"    pág {page}: {len(rows)} linhas encontradas")
        found_any = False

        for row in rows:
            def sp(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(separator=" ", strip=True) if el else ""

            time_text = sp("Hora")
            killed_by = sp("Morto Por")

            if not killed_by:
                # fallback: read all spans in order
                spans = row.find_all("span")
                texts = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]
                # structure: hora, jogador, level, morto_por, mundo
                if len(texts) >= 4:
                    time_text = texts[0]
                    killed_by = texts[3]

            if not killed_by:
                continue

            # Find which guild member appears as killer
            killed_by_lower = killed_by.lower()
            killer = None
            for lower_name, canonical in member_names_lower.items():
                if lower_name in killed_by_lower:
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

# ── Reset history ─────────────────────────────────────────────────────────────
def update_reset_history(members, previous_data):
    prev_map = {}
    if previous_data:
        for m in previous_data.get("members", []):
            prev_map[m["name"].lower()] = m

    now_key = hour_key()  # current hour key

    for m in members:
        key  = m["name"].lower()
        prev = prev_map.get(key, {})
        prev_resets  = prev.get("resets", None)
        prev_history = list(prev.get("reset_history", []))

        # Record in event history whenever resets change
        if prev_resets is not None and m["resets"] != prev_resets:
            prev_history = [{"resets": m["resets"], "time": now_str()}] + prev_history
            prev_history = prev_history[:MAX_RESET_HISTORY]
        m["reset_history"] = prev_history

        # Hourly snapshots: {hour_key: resets_value}
        # Store every hour; keep 7*24+1 = 169 entries (7 days + buffer)
        hourly = dict(prev.get("hourly_snapshots", {}))
        hourly[now_key] = m["resets"]
        # Prune entries older than 8 days
        cutoff = hour_key(brasilia_now() - timedelta(days=8))
        hourly = {k: v for k, v in hourly.items() if k >= cutoff}
        m["hourly_snapshots"] = hourly

        # Preserve previous stats if we can't fetch them this run
        if "stats" not in m and "stats" in prev:
            m["stats"] = prev["stats"]
    return members

def load_previous(path="guild_data.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def resets_since(member, hours_ago):
    """
    How many resets did this member gain in the last N hours?
    Uses hourly_snapshots: finds the oldest snapshot within [now-hours_ago, now]
    and computes current - that value.
    """
    hourly = member.get("hourly_snapshots", {})
    if not hourly:
        return 0
    cutoff_key = hour_key(brasilia_now() - timedelta(hours=hours_ago))
    # Get snapshot at or just before the cutoff
    past_keys = sorted(k for k in hourly if k <= cutoff_key)
    if not past_keys:
        # No snapshot that old — use oldest available
        oldest_key = sorted(hourly.keys())[0]
        baseline = hourly[oldest_key]
    else:
        baseline = hourly[past_keys[-1]]
    return max(0, member["resets"] - baseline)

def compute_resets_today(members):
    """
    Resets do dia = aumento de resets nas últimas 24h (período 22h→22h).
    Verifica hourly_snapshots de hora em hora.
    Também calcula resets dos últimos 7 dias.
    """
    today = []
    for m in members:
        gained_day  = resets_since(m, 24)   # últimas 24h
        gained_week = resets_since(m, 24*7)  # últimos 7 dias

        if gained_day > 0 or gained_week > 0:
            today.append({
                "name":           m["name"],
                "resets":         m["resets"],
                "resets_gained":  gained_day,
                "resets_7d":      gained_week,
                "vocation":       m.get("vocation", ""),
            })

    today.sort(key=lambda x: x["resets_gained"], reverse=True)
    return today

# ── Main ──────────────────────────────────────────────────────────────────────
def scrape_guild():
    timestamp = datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M (Brasília)")

    print("  → Membros da guild...")
    members, owner, founded = scrape_guild_members()
    previous = load_previous()
    members  = update_reset_history(members, previous)
    member_names_lower = {m["name"].lower(): m["name"] for m in members}

    print(f"  → {len(members)} membros. Buscando stats individuais (1 req/membro)...")
    members = scrape_all_char_stats(members)

    print("  → Mortes (lastkills)...")
    deaths_by_member = scrape_deaths(member_names_lower, pages=6)

    print("  → Abates PvP...")
    kills_total, kills_today, kills_week = scrape_pvp_kills(member_names_lower, pages=6)

    print("  → Construindo rankings internos...")
    highscores = build_rankings(members)

    for m in members:
        name = m["name"]
        m["deaths"]          = deaths_by_member.get(name, [])
        m["pvp_kills_total"] = kills_total.get(name, 0)
        m["pvp_kills_today"] = kills_today.get(name, 0)
        m["pvp_kills_week"]  = kills_week.get(name, 0)

    resets_today  = compute_resets_today(members)
    online_count  = sum(1 for m in members if m["status"] == "online")
    offline_count = len(members) - online_count

    return {
        "name":             GUILD_NAME,
        "updated_at":       timestamp,
        "owner":            owner,
        "founded":          founded,
        "total_members":    len(members),
        "online_count":     online_count,
        "offline_count":    offline_count,
        "guild_day_start":  guild_day_start().strftime("%d/%m/%Y às %H:%M (Brasília)"),
        "members":          members,
        "resets_today":     resets_today,
        "highscores":       highscores,
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
    for cat, hs in data["highscores"].items():
        top = hs["entries"][0] if hs["entries"] else None
        if top:
            print(f"   🏆 {hs['name']}: #{1} = {top['name']} ({top['value']})")
    if data["members"]:
        print("\n📋 Amostra (3 primeiros):")
        for m in data["members"][:3]:
            icon = "🟢" if m["status"] == "online" else "⚫"
            stats = m.get("stats", {})
            print(f"   {icon} {m['name']} | {m['resets']}R | exp={stats.get('experience',0):,} | kills={m['pvp_kills_total']}")
