"""
Script de diagnóstico — rode uma vez para ver a estrutura da página PvP.
Não substitua o scraper.py com isso, é só para debug.
"""
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

# Print all table rows raw
rows = soup.select("table tr")
print(f"\nRows encontradas na <table>: {len(rows)}")
for i, row in enumerate(rows[:10]):
    cells = row.find_all("td")
    print(f"\n--- Row {i} ({len(cells)} cells) ---")
    for j, cell in enumerate(cells):
        print(f"  cell[{j}]: {cell.get_text(separator=' ', strip=True)[:120]}")
        # Print links inside
        for a in cell.find_all("a"):
            print(f"    <a href={a.get('href','')}> {a.get_text(strip=True)}")

# Also try divs in case it's not a table
print("\n\n--- Primeiros 3000 chars do HTML ---")
print(r.text[:3000])
