import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

url = "https://amonot.online/guilds?name=Lowly+People&status=all"
r = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status HTTP: {r.status_code} | Size: {len(r.text)}")

soup = BeautifulSoup(r.text, "html.parser")
rows = soup.select(".char-table-row")
print(f"Rows encontradas: {len(rows)}")

online_count = 0
offline_count = 0

for i, row in enumerate(rows[:10]):
    # nome
    name_el = row.select_one('span[data-label="Nome"]')
    name = name_el.get_text(strip=True) if name_el else "?"

    # status_el
    status_el = row.select_one('span[data-label="Status"] .badge')
    status_classes = status_el.get("class", []) if status_el else []
    status_text = status_el.get_text(strip=True) if status_el else "NOT FOUND"

    # raw status span
    status_span = row.select_one('span[data-label="Status"]')
    status_span_html = str(status_span)[:200] if status_span else "NOT FOUND"

    is_online = "badge-success" in status_classes
    if is_online:
        online_count += 1
    else:
        offline_count += 1

    print(f"\n[{i+1}] {name}")
    print(f"  classes: {status_classes}")
    print(f"  text: {status_text}")
    print(f"  online: {is_online}")
    print(f"  raw html: {status_span_html}")

print(f"\nTotal amostra: {online_count} online, {offline_count} offline")
