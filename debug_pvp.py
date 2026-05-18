import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

url = "https://amonot.online/index.php?page=lastkills&world=Baiak&type=pvp"
r = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {r.status_code}  |  Size: {len(r.text)} bytes")

soup = BeautifulSoup(r.text, "html.parser")

# Find all divs with class containing "kill", "death", "last", "row"
for cls in ["kill", "death", "last", "row", "char", "player"]:
    found = soup.select(f'[class*="{cls}"]')
    if found:
        print(f"\n--- class*='{cls}' ({len(found)} elements) ---")
        for el in found[:3]:
            print(f"  tag={el.name} class={el.get('class')} text={el.get_text(separator=' ', strip=True)[:150]}")

# Print a large chunk of HTML around first death entry
raw = r.text
# find "Morto por" or "Killed by" or pvp indicators
for kw in ["Morto por", "morto por", "Killed by", "killed by", "pvp", "data-label"]:
    idx = raw.find(kw)
    if idx > 0:
        print(f"\n--- Found '{kw}' at pos {idx} ---")
        print(raw[max(0,idx-200):idx+400])
        break

# Also print first 500 chars after <main or <section or <article
for tag in ["<main", "<section", "<article", "<div id=\"content", "<div class=\"content"]:
    idx = raw.find(tag)
    if idx > 0:
        print(f"\n--- {tag} at {idx} ---")
        print(raw[idx:idx+800])
        break
