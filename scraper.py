import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json, re, time, random
from datetime import datetime, timezone, timedelta

BRASILIA          = timezone(timedelta(hours=-3))
GUILD_NAME        = "Lowly People"
ENEMY_GUILD_NAME  = "MentaliTY"
ENEMY_GUILD_URL   = "https://amonot.online/guilds?name=MentaliTY"
KILLS_PVP_URL     = "https://amonot.online/index.php?page=lastkills&world=Baiak&type=pvp"
KILLS_ALL_URL     = "https://amonot.online/index.php?page=lastkills&world=Baiak"
CHAR_URL          = "https://amonot.online/characters?name={name}"
MAX_RESET_HISTORY = 7
MAX_DEATH_HISTORY = 30

SKILL_KEYS = ["experience","magic","fist","club","sword","axe","distance","shielding","fishing"]
SKILL_LABELS = {
    "resets":"Resets","experience":"Experience","magic":"Magic Level",
    "fist":"Fist","club":"Club","sword":"Sword","axe":"Axe",
    "distance":"Distance","shielding":"Shielding","fishing":"Fishing",
}

# ── Session with retry + backoff ──────────────────────────────────────────────
def make_session():
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,          # 1s, 2s, 4s, 8s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "DNT":             "1",
    })
    return session

SESSION = make_session()

def safe_get(url, timeout=15, min_sleep=0.8, max_sleep=1.8):
    """GET with jitter sleep before request to avoid detection."""
    time.sleep(random.uniform(min_sleep, max_sleep))
    try:
        r = SESSION.get(url, timeout=timeout)
        if r.status_code == 429:
            print(f"    ⚠ Rate limited, aguardando 30s...")
            time.sleep(30)
            r = SESSION.get(url, timeout=timeout)
        return r
    except Exception as e:
        print(f"    ⚠ Erro ao buscar {url}: {e}")
        return None

# ── Time helpers ──────────────────────────────────────────────────────────────
def now_str():
    return datetime.now(BRASILIA).strftime("%d/%m/%Y %H:%M")

def brasilia_now():
    return datetime.now(BRASILIA)

def guild_day_start():
    now = brasilia_now()
    today_22 = now.replace(hour=22, minute=0, second=0, microsecond=0)
    if now < today_22:
        today_22 -= timedelta(days=1)
    return today_22

def guild_week_start():
    start = guild_day_start()
    return start - timedelta(days=start.weekday())

def hour_key(dt=None):
    if dt is None:
        dt = brasilia_now()
    return dt.strftime("%Y-%m-%d-%H")

def parse_death_time(time_str):
    try:
        dt = datetime.strptime(time_str.strip(), "%b %d, %Y %H:%M")
        return dt.replace(tzinfo=BRASILIA)
    except Exception:
        return None

# ── Parse members from a guild page ──────────────────────────────────────────
def parse_members_from_soup(soup, forced_status=None):
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
            rank = re.sub(r'\s*\(\d+\)\s*$', '', title_el.get_text(strip=True)).strip()

        for row in section.select(".char-table-row"):
            def sp(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(strip=True) if el else ""

            name = sp("Nome")
            if not name:
                continue
            try:    level  = int(sp("Level"))
            except: level  = 0
            try:    resets = int(sp("Resets"))
            except: resets = 0

            vocation = sp("Vocação") or sp("Vocation")
            nick     = sp("Nick")

            if forced_status:
                status = forced_status
            else:
                badge = row.select_one('span[data-label="Status"] .badge')
                if badge:
                    status = "online" if "badge-success" in badge.get("class", []) else "offline"
                else:
                    ss = row.select_one('span[data-label="Status"]')
                    status = "online" if ss and "online" in ss.get_text(strip=True).lower() else "offline"

            members.append({
                "name": name, "level": level, "resets": resets,
                "vocation": vocation, "nick": nick,
                "status": status, "rank": rank,
            })
    return members, owner, founded

def fetch_guild_members(guild_name_encoded):
    """Fetch online + offline separately for accurate status."""
    base = f"https://amonot.online/guilds?name={guild_name_encoded}"
    all_members = []
    owner, founded = "", ""
    seen = set()

    for status_filter, forced in [("online", "online"), ("offline", "offline")]:
        url = f"{base}&status={status_filter}"
        r = safe_get(url)
        if not r or r.status_code != 200:
            print(f"    ⚠ Falha ao buscar {guild_name_encoded} ({status_filter})")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        members, o, f = parse_members_from_soup(soup, forced_status=forced)
        if o: owner = o
        if f: founded = f
        for m in members:
            if m["name"] not in seen:
                seen.add(m["name"])
                all_members.append(m)

    online = sum(1 for m in all_members if m["status"] == "online")
    print(f"    → {guild_name_encoded}: {len(all_members)} membros ({online} online)")
    return all_members, owner, founded

# ── Character stats ───────────────────────────────────────────────────────────
def scrape_char_stats(name):
    url = CHAR_URL.format(name=requests.utils.quote(name))
    stats = {k: 0 for k in SKILL_KEYS}
    r = safe_get(url, timeout=12, min_sleep=1.0, max_sleep=2.0)
    if not r or r.status_code != 200:
        return stats
    try:
        soup = BeautifulSoup(r.text, "html.parser")
        skill_map = {
            "Experience Points": "experience", "Experience": "experience",
            "Magic Level": "magic", "Magic level": "magic",
            "Fist Fighting": "fist",  "Club Fighting": "club",
            "Sword Fighting": "sword", "Axe Fighting": "axe",
            "Distance Fighting": "distance", "Shielding": "shielding",
            "Fishing": "fishing",
        }
        # Try table rows
        for row in soup.select("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                lbl = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                for label, key in skill_map.items():
                    if label.lower() in lbl.lower():
                        val_raw = re.sub(r'[^\d]', '', val)
                        if val_raw:
                            try: stats[key] = int(val_raw)
                            except: pass
        # Try info-cards
        for card in soup.select(".info-card"):
            lbl_el = card.select_one(".info-label")
            val_el = card.select_one(".info-value")
            if lbl_el and val_el:
                lbl = lbl_el.get_text(strip=True)
                val = re.sub(r'[^\d]', '', val_el.get_text(strip=True))
                for label, key in skill_map.items():
                    if label.lower() in lbl.lower() and val:
                        try: stats[key] = int(val)
                        except: pass
        # Text fallback
        lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
        for i, line in enumerate(lines):
            for label, key in skill_map.items():
                if line == label and i + 1 < len(lines):
                    val_raw = re.sub(r'[^\d]', '', lines[i+1])
                    if val_raw:
                        try: stats[key] = int(val_raw)
                        except: pass
                    break
    except Exception as e:
        print(f"    ⚠ stats {name}: {e}")
    return stats

def scrape_all_char_stats(members):
    total = len(members)
    for i, m in enumerate(members):
        print(f"    [{i+1}/{total}] {m['name']}...")
        m["stats"] = scrape_char_stats(m["name"])
    return members

def build_rankings(members):
    rankings = {}
    for cat in ["resets"] + SKILL_KEYS:
        if cat == "resets":
            entries = [{"name": m["name"], "value": m["resets"],
                        "level": m["level"], "vocation": m["vocation"]} for m in members]
        else:
            entries = [{"name": m["name"], "value": m.get("stats", {}).get(cat, 0),
                        "level": m["level"], "vocation": m["vocation"]} for m in members]
        entries.sort(key=lambda x: x["value"], reverse=True)
        for i, e in enumerate(entries):
            e["guild_rank"] = i + 1
        rankings[cat] = {"name": SKILL_LABELS.get(cat, cat),
                         "val_label": SKILL_LABELS.get(cat, cat), "entries": entries}
    return rankings

# ── Deaths ────────────────────────────────────────────────────────────────────
def scrape_deaths(member_names_lower, pages=6):
    deaths_by_member = {}
    for page in range(1, pages + 1):
        url = KILLS_ALL_URL + (f"&p={page}" if page > 1 else "")
        r = safe_get(url, min_sleep=0.5, max_sleep=1.2)
        if not r or r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select("div.char-table-row"):
            def sp(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(separator=" ", strip=True) if el else ""
            time_text   = sp("Hora")
            name_tag    = row.select_one('span[data-label="Jogador Morto"] a')
            player_name = name_tag.get_text(strip=True) if name_tag else sp("Jogador Morto")
            if not player_name or player_name.lower() not in member_names_lower:
                continue
            try:    dlevel = int(sp("Level"))
            except: dlevel = 0
            killed_by = sp("Morto Por")
            is_pvp    = "(jogador)" in killed_by.lower()
            canonical = member_names_lower[player_name.lower()]
            deaths_by_member.setdefault(canonical, []).append({
                "time": time_text, "level": dlevel,
                "by": killed_by, "is_pvp": is_pvp,
            })
    for name in deaths_by_member:
        deaths_by_member[name] = deaths_by_member[name][:MAX_DEATH_HISTORY]
    return deaths_by_member

# ── War tracker ───────────────────────────────────────────────────────────────
def scrape_war_kills(our_names_lower, enemy_names_lower, pages=10):
    """
    Track kills between Lowly People and MentaliTY on the PvP lastkills page.
    Returns:
      our_kills   = {lp_member: count}   (LP killed enemy)
      enemy_kills = {enemy_member: count} (enemy killed LP)
      war_log     = [{time, killer, victim, killer_guild, victim_guild}]
    """
    our_kills   = {}
    enemy_kills = {}
    war_log     = []
    day_start   = guild_day_start()
    week_start  = guild_week_start()

    # per-member daily/weekly
    our_kills_day  = {}
    our_kills_week = {}
    enemy_kills_day  = {}
    enemy_kills_week = {}

    for page in range(1, pages + 1):
        url = KILLS_PVP_URL + (f"&p={page}" if page > 1 else "")
        r = safe_get(url, min_sleep=0.5, max_sleep=1.2)
        if not r or r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("div.char-table-row")
        found_war = False

        for row in rows:
            def sp(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(separator=" ", strip=True) if el else ""

            time_text = sp("Hora")
            victim_tag = row.select_one('span[data-label="Jogador Morto"] a')
            victim = victim_tag.get_text(strip=True) if victim_tag else sp("Jogador Morto")
            killed_by = sp("Morto Por")
            if not killed_by or not victim:
                continue

            victim_lower   = victim.lower()
            killedby_lower = killed_by.lower()

            # Find killer name (LP member in "Morto Por" text)
            killer_lp     = next((c for n, c in our_names_lower.items() if n in killedby_lower), None)
            killer_enemy  = next((c for n, c in enemy_names_lower.items() if n in killedby_lower), None)
            victim_is_lp  = victim_lower in our_names_lower
            victim_is_enemy = victim_lower in enemy_names_lower

            # LP killed enemy
            if killer_lp and victim_is_enemy:
                found_war = True
                our_kills[killer_lp] = our_kills.get(killer_lp, 0) + 1
                dt = parse_death_time(time_text)
                if dt:
                    if dt >= day_start:
                        our_kills_day[killer_lp] = our_kills_day.get(killer_lp, 0) + 1
                    if dt >= week_start:
                        our_kills_week[killer_lp] = our_kills_week.get(killer_lp, 0) + 1
                war_log.append({"time": time_text, "killer": killer_lp,
                                "victim": victim, "killer_guild": "lp", "victim_guild": "enemy"})

            # Enemy killed LP
            elif killer_enemy and victim_is_lp:
                found_war = True
                enemy_kills[killer_enemy] = enemy_kills.get(killer_enemy, 0) + 1
                dt = parse_death_time(time_text)
                if dt:
                    if dt >= day_start:
                        enemy_kills_day[killer_enemy] = enemy_kills_day.get(killer_enemy, 0) + 1
                    if dt >= week_start:
                        enemy_kills_week[killer_enemy] = enemy_kills_week.get(killer_enemy, 0) + 1
                war_log.append({"time": time_text, "killer": killer_enemy,
                                "victim": victim, "killer_guild": "enemy", "victim_guild": "lp"})

        if not found_war and page > 4:
            break

    war_log = war_log[:200]
    return (our_kills, our_kills_day, our_kills_week,
            enemy_kills, enemy_kills_day, enemy_kills_week,
            war_log)

# ── PvP kills (general) ───────────────────────────────────────────────────────
def scrape_pvp_kills(member_names_lower, pages=6):
    kills_total = {}
    kills_today = {}
    kills_week  = {}
    day_start   = guild_day_start()
    week_start  = guild_week_start()

    for page in range(1, pages + 1):
        url = KILLS_PVP_URL + (f"&p={page}" if page > 1 else "")
        r = safe_get(url, min_sleep=0.5, max_sleep=1.2)
        if not r or r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        found_any = False
        for row in soup.select("div.char-table-row"):
            def sp(lbl):
                el = row.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(separator=" ", strip=True) if el else ""
            time_text = sp("Hora")
            killed_by = sp("Morto Por")
            if not killed_by or "(monstro)" in killed_by.lower():
                continue
            killer = next((c for n, c in member_names_lower.items() if n in killed_by.lower()), None)
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

        if not found_any and page > 2:
            break

    return kills_total, kills_today, kills_week

# ── Reset history ─────────────────────────────────────────────────────────────
def update_reset_history(members, previous_data):
    prev_map = {}
    if previous_data:
        for m in previous_data.get("members", []):
            prev_map[m["name"].lower()] = m

    now_key = hour_key()
    for m in members:
        key  = m["name"].lower()
        prev = prev_map.get(key, {})
        prev_resets  = prev.get("resets", None)
        prev_history = list(prev.get("reset_history", []))

        if prev_resets is not None and m["resets"] != prev_resets:
            prev_history = [{"resets": m["resets"], "time": now_str()}] + prev_history
            prev_history = prev_history[:MAX_RESET_HISTORY]
        m["reset_history"] = prev_history

        hourly = dict(prev.get("hourly_snapshots", {}))
        hourly[now_key] = m["resets"]
        cutoff = hour_key(brasilia_now() - timedelta(days=8))
        m["hourly_snapshots"] = {k: v for k, v in hourly.items() if k >= cutoff}

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
    hourly = member.get("hourly_snapshots", {})
    if not hourly:
        return 0
    cutoff_key = hour_key(brasilia_now() - timedelta(hours=hours_ago))
    past_keys  = sorted(k for k in hourly if k <= cutoff_key)
    baseline   = hourly[past_keys[-1]] if past_keys else hourly[sorted(hourly.keys())[0]]
    return max(0, member["resets"] - baseline)

def compute_resets_today(members):
    today = []
    for m in members:
        gained_day  = resets_since(m, 24)
        gained_week = resets_since(m, 24*7)
        if gained_day > 0 or gained_week > 0:
            today.append({"name": m["name"], "resets": m["resets"],
                          "resets_gained": gained_day, "resets_7d": gained_week,
                          "vocation": m.get("vocation", "")})
    today.sort(key=lambda x: x["resets_gained"], reverse=True)
    return today

# ── Main ──────────────────────────────────────────────────────────────────────
def scrape_guild():
    timestamp = datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M (Brasília)")

    print("  → Membros Lowly People...")
    members, owner, founded = fetch_guild_members("Lowly+People")
    previous = load_previous()
    members  = update_reset_history(members, previous)
    member_names_lower = {m["name"].lower(): m["name"] for m in members}

    print("  → Membros MentaliTY...")
    enemy_members, _, _ = fetch_guild_members("MentaliTY")
    enemy_names_lower   = {m["name"].lower(): m["name"] for m in enemy_members}

    print(f"  → Stats individuais ({len(members)} membros)...")
    members = scrape_all_char_stats(members)

    print("  → Mortes (lastkills)...")
    deaths_by_member = scrape_deaths(member_names_lower, pages=6)

    print("  → Abates PvP gerais...")
    kills_total, kills_today, kills_week = scrape_pvp_kills(member_names_lower, pages=6)

    print("  → Guerra LP vs MentaliTY...")
    (our_kills, our_kills_day, our_kills_week,
     enemy_kills, enemy_kills_day, enemy_kills_week,
     war_log) = scrape_war_kills(member_names_lower, enemy_names_lower, pages=10)

    print("  → Rankings...")
    highscores = build_rankings(members)

    for m in members:
        name = m["name"]
        m["deaths"]          = deaths_by_member.get(name, [])
        m["pvp_kills_total"] = kills_total.get(name, 0)
        m["pvp_kills_today"] = kills_today.get(name, 0)
        m["pvp_kills_week"]  = kills_week.get(name, 0)
        m["war_kills"]       = our_kills.get(name, 0)
        m["war_kills_day"]   = our_kills_day.get(name, 0)
        m["war_kills_week"]  = our_kills_week.get(name, 0)

    # Enemy members war stats
    enemy_list = []
    for m in enemy_members:
        name = m["name"]
        enemy_list.append({
            "name":      name,
            "level":     m["level"],
            "vocation":  m["vocation"],
            "resets":    m["resets"],
            "status":    m["status"],
            "war_kills": enemy_kills.get(name, 0),
            "war_kills_day":  enemy_kills_day.get(name, 0),
            "war_kills_week": enemy_kills_week.get(name, 0),
        })

    total_lp_kills    = sum(our_kills.values())
    total_enemy_kills = sum(enemy_kills.values())
    lp_deaths_in_war  = sum(1 for e in war_log if e["victim_guild"] == "lp")
    enemy_deaths_war  = sum(1 for e in war_log if e["victim_guild"] == "enemy")

    war_data = {
        "enemy_guild":         ENEMY_GUILD_NAME,
        "lp_kills_total":      total_lp_kills,
        "enemy_kills_total":   total_enemy_kills,
        "lp_deaths_war":       lp_deaths_in_war,
        "enemy_deaths_war":    enemy_deaths_war,
        "lp_kills_today":      sum(our_kills_day.values()),
        "enemy_kills_today":   sum(enemy_kills_day.values()),
        "lp_kills_week":       sum(our_kills_week.values()),
        "enemy_kills_week":    sum(enemy_kills_week.values()),
        "lp_top_killers":      sorted(
            [{"name": n, "kills": k, "kills_day": our_kills_day.get(n,0),
              "kills_week": our_kills_week.get(n,0)} for n, k in our_kills.items()],
            key=lambda x: x["kills"], reverse=True
        ),
        "enemy_top_killers":   sorted(
            [{"name": n, "kills": k, "kills_day": enemy_kills_day.get(n,0),
              "kills_week": enemy_kills_week.get(n,0)} for n, k in enemy_kills.items()],
            key=lambda x: x["kills"], reverse=True
        ),
        "war_log": war_log,
        "enemy_members": enemy_list,
    }

    resets_today  = compute_resets_today(members)
    online_count  = sum(1 for m in members if m["status"] == "online")
    offline_count = len(members) - online_count

    print(f"\n  ⚔ Guerra: LP {total_lp_kills} kills / MentaliTY {total_enemy_kills} kills")

    return {
        "name":            GUILD_NAME,
        "updated_at":      timestamp,
        "owner":           owner,
        "founded":         founded,
        "total_members":   len(members),
        "online_count":    online_count,
        "offline_count":   offline_count,
        "guild_day_start": guild_day_start().strftime("%d/%m/%Y às %H:%M (Brasília)"),
        "members":         members,
        "resets_today":    resets_today,
        "highscores":      highscores,
        "war":             war_data,
    }


if __name__ == "__main__":
    print("🔄 Iniciando coleta completa...")
    data = scrape_guild()
    with open("guild_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Salvo!")
    print(f"   👥 Membros:     {data['total_members']} ({data['online_count']} online)")
    print(f"   🔄 Resets hoje: {len(data['resets_today'])}")
    print(f"   ⚔ Guerra LP:   {data['war']['lp_kills_total']} kills / {data['war']['lp_deaths_war']} mortes")
    print(f"   ⚔ Guerra Enemy:{data['war']['enemy_kills_total']} kills / {data['war']['enemy_deaths_war']} mortes")
    print(f"   🕐 Em:          {data['updated_at']}")
