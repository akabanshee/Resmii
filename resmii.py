import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
import pandas as pd

ALT_KEYWORDS = [
    "KANUN", "KARAR", "TEBLİĞ", "YÖNETMELİK", "GENELGE",
    # Dilerseniz ekleyebileceğiniz diğer ibareler:
    # "BAKANLIKLARA VEKÂLET", "ATAMA", "CEZANIN KALDIRILMASI", "İDARİ BAĞLILIĞIN", "ANAYASA MAHKEMESİ", ...
]

def build_resmigazete_url(dt):
    """
    Tüm tarihler için eskiler/... formatı kullanılır:
    https://www.resmigazete.gov.tr/eskiler/YYYY/MM/YYYYMMDD.htm
    """
    yyyy = dt.strftime("%Y")
    mm = dt.strftime("%m")
    yyyymmdd = dt.strftime("%Y%m%d")
    return f"https://www.resmigazete.gov.tr/eskiler/{yyyy}/{mm}/{yyyymmdd}.htm"

def is_header(tag):
    """
    Bu fonksiyon, verilen tag’ın (örn. <p>, <span>, <td>)
    alt başlık (header) olup olmadığını belirlemeye çalışır.
    Koşullar:
      - Eğer tag içinde <u> ve <b> varsa, header olarak kabul edilir.
      - Veya tag’ın metni tamamen büyük harf ve uzunluğu 40 karakterden azsa.
    """
    if tag.find("u") and tag.find("b"):
        return True
    text = tag.get_text(strip=True)
    if text and text == text.upper() and len(text) <= 40:
        return True
    return False

def parse_fallback_all(soup):
    """
    Eski sayfa fallback: <p>, <span>, <td> etiketlerini tarar.
    'BÖLÜMÜ' (ancak 'İLAN' değil) => Ana Başlık.
    Alt başlık tespiti için:
      1) ALT_KEYWORDS içinden en az bir kelime içeriyorsa,
      2) veya tag is_header() True dönerse.
    Alt başlık altında bulunan link (.pdf/.htm) => Madde.
    """
    rapor = {"Genel Bölümler": {}}
    fallback_tags = soup.find_all(["p", "span", "td"])

    current_ana = None
    current_alt = None

    for tag in fallback_tags:
        text_raw = tag.get_text(strip=True)
        text_up = text_raw.upper()

        if not text_up:
            continue

        # ANA BAŞLIK: "BÖLÜMÜ" var ama "İLAN" yok
        if "BÖLÜMÜ" in text_up and "İLAN" not in text_up:
            current_ana = text_raw
            current_alt = None
            if current_ana not in rapor["Genel Bölümler"]:
                rapor["Genel Bölümler"][current_ana] = {}
        # ALT BAŞLIK: ALT_KEYWORDS veya is_header() sağlanıyorsa
        elif any(word in text_up for word in ALT_KEYWORDS) or is_header(tag):
            if current_ana:
                current_alt = text_raw
                rapor["Genel Bölümler"][current_ana][current_alt] = {
                    "toplam_madde": 0,
                    "pdf_sayisi": 0,
                    "htm_sayisi": 0,
                    "items": []
                }
        else:
            # MADDE: Eğer ana ve alt başlık tanımlıysa, tag içinde link varsa
            if current_ana and current_alt:
                linkler = tag.find_all("a", href=True)
                if linkler:
                    subdict = rapor["Genel Bölümler"][current_ana][current_alt]
                    for ln in linkler:
                        href = ln["href"].strip()
                        l_href = href.lower()
                        item_pdf = 1 if l_href.endswith(".pdf") else 0
                        item_htm = 1 if l_href.endswith(".htm") else 0

                        if item_pdf and not item_htm:
                            ifmt = "pdf"
                        elif item_htm and not item_pdf:
                            ifmt = "htm"
                        elif item_pdf and item_htm:
                            ifmt = "pdf+htm"
                        else:
                            ifmt = "none"

                        subdict["items"].append({
                            "title": text_raw,
                            "format": ifmt,
                            "links": href
                        })
                        subdict["toplam_madde"] += 1
                        subdict["pdf_sayisi"] += item_pdf
                        subdict["htm_sayisi"] += item_htm

    return rapor

def parse_old_page(soup):
    return parse_fallback_all(soup)

def parse_new_page(soup):
    """
    Modern (yeni) sayfa yapısı (2019+):
      - div.card-title.html-title => Ana Başlık
      - div.html-subtitle => Alt Başlık
      - fihrist-item => Maddeler (pdf/htm linkleri)
    """
    # Eğer tüm sayfalar eskiler formatında olacaksa bu kısım kullanılmayacak.
    return parse_old_page(soup)

def resmi_gazete_analizi(url, timeout=10):
    """
    Tüm tarihlerde eskiler formatı kullanıldığı için,
    doğrudan parse_old_page() çağrılır.
    """
    rapor = {"Genel Bölümler": {}}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/108.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return rapor

    # Önemli: Kodlamayı windows-1254 olarak ayarlıyoruz.
    resp.encoding = "windows-1254"
    soup = BeautifulSoup(resp.text, "html.parser")
    return parse_old_page(soup)

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

    df = pd.DataFrame(all_items)
    df.to_excel(output_file, index=False)
    print(f"Excel oluşturuldu: {output_file}")

def main():
    son_15_sene_excel("15_yil_deneme.xlsx")

if __name__ == "__main__":
    main()
