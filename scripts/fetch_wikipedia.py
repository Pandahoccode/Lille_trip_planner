"""Scrape city info from French Wikipedia: name, summary, infobox."""

import csv
import argparse
import sys
import os
import requests
from bs4 import BeautifulSoup

# Add src to path for verification import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


class WikipediaClient:
    """Wikipedia FR scraper: city name, summary, infobox → CSV."""

    def __init__(self, url, timeout=20):
        self.url = url
        self.timeout = timeout

    def download_html(self):
        headers = {"User-Agent": "Mozilla/5.0 (SAE project - BUT SD)"}
        r = requests.get(self.url, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    @staticmethod
    def _clean(txt):
        if not txt:
            return ""
        return " ".join(txt.split()).strip()

    def extract_city_name(self, soup):
        h1 = soup.find("h1")
        return self._clean(h1.get_text()) if h1 else ""

    def extract_summary(self, soup):
        """First two substantial paragraphs (≥80 chars)."""
        zone = soup.select_one("div.mw-content-ltr") or soup
        chunks = []
        for p in zone.find_all("p", recursive=True):
            text = self._clean(p.get_text(" ", strip=True))
            if len(text) >= 80:
                chunks.append(text)
            if len(chunks) >= 2:
                break
        return "\n".join(chunks)

    def extract_infobox(self, soup):
        """Parse Wikipedia FR infobox_v2 table → dict."""
        infos = {}
        table = soup.find("table", class_="infobox_v2")
        if not table:
            return infos
        for tr in table.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td:
                key = self._clean(th.get_text(" ", strip=True))
                val = self._clean(td.get_text(" ", strip=True))
                if key and val:
                    infos[key] = val
        return infos

    def scrape(self):
        soup = BeautifulSoup(self.download_html(), "html.parser")
        return (
            self.extract_city_name(soup),
            self.extract_summary(soup),
            self.extract_infobox(soup),
        )

    @staticmethod
    def export_csv(filename, city_name, summary, infobox, infobox_keys):
        row = {"city": city_name, "summary": summary}
        for key in infobox_keys:
            row[key] = infobox.get(key, "")
        with open(filename, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys(), delimiter=";")
            writer.writeheader()
            writer.writerow(row)

    def execute(self, filename, infobox_keys):
        city_name, summary, infobox = self.scrape()
        print(f"City: {city_name}")
        print(f"\nSummary:\n{summary[:400]}{'...' if len(summary) > 400 else ''}")
        self.export_csv(filename, city_name, summary, infobox, infobox_keys)
        print(f"\nCSV created: {filename}")


def verify_service():
    """Run verification logic (formerly test_wiki.py)"""
    from src.services import WikiService

    print("Running WikiService verification...")
    try:
        wiki = WikiService()
        print("Fetching Wikipedia summary for 'Lille, France'...")
        summary = wiki.get_summary("Lille, France")

        if summary:
            word_count = len(summary.split())
            print(f"\nSummary Length: {word_count} words")
            print("-" * 40)
            print(summary)
            print("-" * 40)

            if 150 <= word_count <= 250:
                print("\nSUCCESS: Summary length is within the expected range (approx 200 words).")
            else:
                print(f"\nWARNING: Summary length {word_count} is outside the expected range (approx 200 words).")
        else:
            print("\nERROR: Failed to fetch summary.")

    except Exception as e:
        print("\nCAUGHT EXCEPTION:")
        print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Wikipedia data or verify service.")
    parser.add_argument("--verify", action="store_true", help="Run verification logic")
    args = parser.parse_args()

    if args.verify:
        verify_service()
    else:
        KEYS = [
            "Pays", "Région", "Département", "Arrondissement",
            "Intercommunalité", "Maire", "Code postal",
            "Code commune", "Population municipale",
        ]
        WikipediaClient("https://fr.wikipedia.org/wiki/Lille").execute("city_info_lille.csv", KEYS)
