import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

for url in [
    "https://amonot.online/guilds?name=Lowly+People&status=online",
    "https://amonot.online/guilds?name=Lowly+People&status=offline",
    "https://amonot.online/guilds?name=Lowly+People&status=all",
    "https://amonot.online/guilds?name=Lowly+People",
]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select(".char-table-row")
        sections = soup.select(".characters-section")
        print(f"\nURL: {url}")
        print(f"  Status: {r.status_code} | Size: {len(r.text)}")
        print(f"  .char-table-row: {len(rows)}")
        print(f"  .characters-section: {len(sections)}")
        if rows:
            first = rows[0]
            def sp(lbl):
                el = first.select_one(f'span[data-label="{lbl}"]')
                return el.get_text(strip=True) if el else "NOT FOUND"
            print(f"  Primeiro membro: Nome={sp('Nome')} Level={sp('Level')} Resets={sp('Resets')}")
    except Exception as e:
        print(f"\nURL: {url} → ERRO: {e}")
