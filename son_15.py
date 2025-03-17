import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import pandas as pd

ALT_KEYWORDS = [
    "KANUN", "KARAR", "TEBLİĞ", "YÖNETMELİK", "GENELGE",
]

def build_resmigazete_url(dt):
    yyyy = dt.strftime("%Y")
    mm = dt.strftime("%m")
    yyyymmdd = dt.strftime("%Y%m%d")
    return f"https://www.resmigazete.gov.tr/eskiler/{yyyy}/{mm}/{yyyymmdd}.htm"

def parse_fallback_all(soup):
    rapor = {"Genel Bölümler": {}}
    fallback_tags = soup.find_all(["p", "span", "td", "a"])

    current_ana = None
    current_alt = None

    for tag in fallback_tags:
        text_raw = tag.get_text(strip=True)
        text_up = text_raw.upper()

        if not text_up:
            continue

        if "BÖLÜMÜ" in text_up and "İLAN" not in text_up:
            current_ana = text_raw
            current_alt = None
            if current_ana not in rapor["Genel Bölümler"]:
                rapor["Genel Bölümler"][current_ana] = {}

        else:
            is_alt = any(word in text_up for word in ALT_KEYWORDS)
            is_alt = is_alt or (text_up == text_raw and len(text_up) >= 5)
            if is_alt:
                if current_ana:
                    current_alt = text_raw
                    rapor["Genel Bölümler"][current_ana][current_alt] = {
                        "toplam_madde": 0,
                        "pdf_sayisi": 0,
                        "htm_sayisi": 0,
                        "items": []
                    }
            else:
                if current_ana and current_alt:
                    linkler = tag.find_all("a", href=True)
                    if linkler:
                        subdict = rapor["Genel Bölümler"][current_ana][current_alt]
                        for ln in linkler:
                            href = ln["href"].strip()
                            l_href = href.lower()
                            item_pdf = 1 if l_href.endswith(".pdf") else 0
                            item_htm = 1 if l_href.endswith(".htm") else 0
                            subdict["items"].append({
                                "title": text_raw,
                                "format": "pdf" if item_pdf else "htm",
                                "links": href
                            })
                            subdict["toplam_madde"] += 1
                            subdict["pdf_sayisi"] += item_pdf
                            subdict["htm_sayisi"] += item_htm

    return rapor

def resmi_gazete_analizi(url, timeout=10):
    rapor = {"Genel Bölümler": {}}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return rapor

    resp.encoding = "ISO-8859-9"  # Karakter hatalarını çözmek için güncellendi
    soup = BeautifulSoup(resp.text, "html.parser")

    return parse_fallback_all(soup)

def son_15_sene_excel(output_file="15_yil_deneme.xlsx"):
    today = date.today()
    start = date(today.year - 15, today.month, today.day)
    end = today

    all_items = []
    one_day = timedelta(days=1)
    curr = start

    while curr <= end:
        iso_str = curr.isoformat()
        url = build_resmigazete_url(curr)
        gunluk_rapor = resmi_gazete_analizi(url, timeout=10)
        genel_bolum = gunluk_rapor.get("Genel Bölümler", {})

        if not genel_bolum:
            curr += one_day
            continue

        for ana_b, alt_dict in genel_bolum.items():
            for alt_b, data_ in alt_dict.items():
                for it in data_.get("items", []):
                    all_items.append({
                        "Tarih": iso_str,
                        "Ana Başlık": ana_b,
                        "Alt Başlık": alt_b,
                        "Madde Adı": it.get("title", ""),
                        "Link(ler)": it.get("links", ""),
                        "Format": it.get("format", "")
                    })

        curr += one_day

    df = pd.DataFrame(all_items).drop_duplicates(subset=["Tarih", "Madde Adı"])  # Aynı tarih ve maddeyi filtreler
    df.to_excel(output_file, index=False)
    print(f"Excel oluşturuldu: {output_file}")

def main():
    son_15_sene_excel("15_yil_deneme.xlsx")

if __name__ == "__main__":
    main()
