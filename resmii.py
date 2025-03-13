import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
from collections import defaultdict

SPECIAL_HEADINGS = [
    "GENELGE",
    "KANUN",
    "KANUNLAR",
    "TEBLİĞ",
    "TEBLİĞLER",
    "YÖNETMELİK",
    "YÖNETMELİKLER"
]

def resmi_gazete_analizi(url, timeout=10):
    """
    Bir günün Resmî Gazete sayfasını parse eder,
    sadece 'Genel Bölümler'i inceler (İlan bölümü atlanır).
    
    Dönüş:
    {
      "Genel Bölümler": {
         "<ANA_BASLIK>": {
            "<ALT_BASLIK>": {
               "toplam_madde": X,
               "pdf_sayisi": Y,
               "htm_sayisi": Z,
               "items": [
                  {"title":"...", "format":"pdf|htm|pdf+htm|none"},
                  ...
               ]
            },
            ...
         }
      }
    }
    """
    rapor = {"Genel Bölümler": {}}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            "AppleWebKit/537.36 (KHTML, like Gecko)"
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[Hata - {url}] {e}")
        return rapor  # Boş sözlük döndür

    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    ana_basliklar = soup.find_all("div", class_="card-title html-title")
    for ana_b in ana_basliklar:
        ana_text = ana_b.get_text(strip=True)
        # İlan bölümünü atla
        if "İLAN BÖLÜMÜ" in ana_text.upper():
            continue

        rapor["Genel Bölümler"][ana_text] = {}
        sibl = ana_b.find_next_sibling()
        while sibl:
            # Yeni ana başlık => dur
            if ("card-title" in sibl.get("class", []) and "html-title" in sibl.get("class", [])):
                break

            # Alt başlık => <div class="html-subtitle">
            if "html-subtitle" in sibl.get("class", []):
                alt_text = sibl.get_text(strip=True)

                toplam_madde = 0
                pdf_say = 0
                htm_say = 0
                items_list = []

                n_ = sibl.find_next_sibling()
                while n_:
                    # Yeni alt başlık / ana başlık => dur
                    if ("html-subtitle" in n_.get("class", []) or
                        ("card-title" in n_.get("class", []) and "html-title" in n_.get("class", []))):
                        break

                    # fihrist maddesi => <div class="fihrist-item mb-1">
                    if ("fihrist-item" in n_.get("class", []) and "mb-1" in n_.get("class", [])):
                        toplam_madde += 1

                        linkler = n_.find_all("a", href=True)
                        item_pdf = 0
                        item_htm = 0
                        for ln in linkler:
                            l_href = ln["href"].lower().strip()
                            if l_href.endswith(".pdf"):
                                item_pdf += 1
                            elif l_href.endswith(".htm"):
                                item_htm += 1

                        pdf_say += item_pdf
                        htm_say += item_htm

                        # format
                        if item_pdf > 0 and item_htm == 0:
                            ifmt = "pdf"
                        elif item_pdf == 0 and item_htm > 0:
                            ifmt = "htm"
                        elif item_pdf > 0 and item_htm > 0:
                            ifmt = "pdf+htm"
                        else:
                            ifmt = "none"

                        item_text = n_.get_text(" ", strip=True)
                        items_list.append({
                            "title": item_text,
                            "format": ifmt
                        })

                    n_ = n_.find_next_sibling()

                rapor["Genel Bölümler"][ana_text][alt_text] = {
                    "toplam_madde": toplam_madde,
                    "pdf_sayisi": pdf_say,
                    "htm_sayisi": htm_say,
                    "items": items_list
                }

            sibl = sibl.find_next_sibling()

    return rapor


def son_x_sene_genel_bolum(x_sene=5, output_file="5_yil_sadece_genel_pdf_html_percent.txt"):
    """
    Son x_sene yıl => sadece GENEL BÖLÜMLER.
    - Ana/alt başlık frekansı (kaç günde görüldü), PDF/HTM toplamları, yüzdeleri
    - Önemli alt başlık (SPECIAL_HEADINGS) altındaki maddeler (isim + format)
    - YÖNETMELİK(LER)/KANUN(LAR) maddeleri
    KeyError: 'GENELGE' düzeltmesi => items_ = alt_dates[d_]
    """
    today = date.today()
    start = date(today.year - x_sene, today.month, today.day)
    end = today

    heading_freq = {}
    sub_heading_freq = {}

    heading_pdf_htm = defaultdict(lambda: {"pdf": 0, "htm": 0})
    sub_pdf_htm = defaultdict(lambda: {"pdf": 0, "htm": 0})

    total_madde = 0
    total_pdf = 0
    total_htm = 0

    # Önemli alt başlıklar -> { alt_baslik_up: { "yyyy-mm-dd": [ items...], ... }, ... }
    special_details = {sh: {} for sh in SPECIAL_HEADINGS}
    manage_law_list = []

    one_day = timedelta(days=1)
    curr = start

    while curr <= end:
        iso_str = curr.isoformat()
        rgz_str = curr.strftime("%d.%m.%Y")
        url = f"https://www.resmigazete.gov.tr/{rgz_str}"

        gunluk_rapor = resmi_gazete_analizi(url, timeout=10)
        genel_bolum = gunluk_rapor.get("Genel Bölümler", {})

        if not genel_bolum:
            curr += one_day
            continue

        for ana_b, alt_dict in genel_bolum.items():
            heading_freq[ana_b] = heading_freq.get(ana_b, 0) + 1

            for alt_b, data_ in alt_dict.items():
                sub_heading_freq[alt_b] = sub_heading_freq.get(alt_b, 0) + 1

                # Madde sayıları
                m = data_["toplam_madde"]
                p = data_["pdf_sayisi"]
                h = data_["htm_sayisi"]

                total_madde += m
                total_pdf += p
                total_htm += h

                heading_pdf_htm[ana_b]["pdf"] += p
                heading_pdf_htm[ana_b]["htm"] += h

                sub_pdf_htm[alt_b]["pdf"] += p
                sub_pdf_htm[alt_b]["htm"] += h

                # Önemli alt başlık?
                alt_b_up = alt_b.upper()
                if alt_b_up in special_details:
                    # Tarih kaydı yoksa oluştur
                    if iso_str not in special_details[alt_b_up]:
                        special_details[alt_b_up][iso_str] = []
                    # fihrist maddelerini ekle
                    special_details[alt_b_up][iso_str].extend(data_["items"])

                    # YÖNETMELİK(LER)/KANUN(LAR) -> manage_law_list
                    if alt_b_up in ["YÖNETMELİK", "YÖNETMELİKLER", "KANUN", "KANUNLAR"]:
                        for it_ in data_["items"]:
                            manage_law_list.append({
                                "date": iso_str,
                                "heading": alt_b,
                                "title": it_["title"],
                                "format": it_["format"]
                            })

        curr += one_day

    # Rapor yazma
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"=== Son {x_sene} Yıl (Sadece GENEL BÖLÜMLER) Analizi ===\n\n")
        f.write(f"Başlangıç Tarihi: {start}\n")
        f.write(f"Bitiş Tarihi: {end}\n\n")

        f.write(f"Toplam Madde: {total_madde}\n")
        f.write(f"Toplam PDF: {total_pdf}\n")
        f.write(f"Toplam HTM: {total_htm}\n\n")

        # Frekans
        heading_sorted = sorted(heading_freq.items(), key=lambda x: x[1], reverse=True)
        sub_sorted = sorted(sub_heading_freq.items(), key=lambda x: x[1], reverse=True)

        f.write(f"Farklı Ana Başlık Sayısı: {len(heading_sorted)}\n")
        f.write(f"Farklı Alt Başlık Sayısı: {len(sub_sorted)}\n\n")

        f.write("En Sık Geçen 5 Ana Başlık (kaç günde?):\n")
        for hb, cnt in heading_sorted[:5]:
            f.write(f"  - {hb}: {cnt}\n")

        f.write("\nEn Sık Geçen 10 Alt Başlık (kaç günde?):\n")
        for sb, cnt in sub_sorted[:10]:
            f.write(f"  - {sb}: {cnt}\n")

        # ANA BAŞLIK + PDF/HTM + %
        f.write("\n=== TÜM ANA BAŞLIKLAR (frekans, PDF/HTM sayıları ve Yüzdeleri) ===\n")
        for hb, freqv in heading_sorted:
            pdf_ = heading_pdf_htm[hb]["pdf"]
            htm_ = heading_pdf_htm[hb]["htm"]
            total_links = pdf_ + htm_
            if total_links > 0:
                pdf_percent = 100.0 * pdf_ / total_links
                htm_percent = 100.0 * htm_ / total_links
            else:
                pdf_percent = 0.0
                htm_percent = 0.0

            f.write(
                f"  - {hb} => Gün Frekansı: {freqv}, "
                f"PDF: {pdf_} (%{pdf_percent:.1f}), "
                f"HTM: {htm_} (%{htm_percent:.1f})\n"
            )

        # ALT BAŞLIK + PDF/HTM + %
        f.write("\n=== TÜM ALT BAŞLIKLAR (frekans, PDF/HTM sayıları ve Yüzdeleri) ===\n")
        for sb, freqv in sub_sorted:
            pdf_ = sub_pdf_htm[sb]["pdf"]
            htm_ = sub_pdf_htm[sb]["htm"]
            total_links = pdf_ + htm_
            if total_links > 0:
                pdf_percent = 100.0 * pdf_ / total_links
                htm_percent = 100.0 * htm_ / total_links
            else:
                pdf_percent = 0.0
                htm_percent = 0.0

            f.write(
                f"  - {sb} => Gün Frekansı: {freqv}, "
                f"PDF: {pdf_} (%{pdf_percent:.1f}), "
                f"HTM: {htm_} (%{htm_percent:.1f})\n"
            )

        # ÖNEMLİ ALT BAŞLIKLAR => items_ = alt_dates[d_]
        f.write("\n=== ÖNEMLİ ALT BAŞLIKLARIN MADDE DETAYLARI ===\n")
        for alt_up in special_details:
            alt_dates = special_details[alt_up]
            if not alt_dates:
                continue
            f.write(f"\n-- {alt_up} --\n")
            # Doğru indeksleme: items_ = alt_dates[d_]
            for d_ in sorted(alt_dates.keys()):
                items_ = alt_dates[d_]  # Fix KeyError => alt_dates[d_], not alt_dates[alt_up][d_]
                if not items_:
                    continue
                f.write(f"  {d_} => {len(items_)} madde:\n")
                idx = 1
                for it_ in items_:
                    f.write(f"    {idx}. {it_['title']} [format={it_['format']}]\n")
                    idx += 1

        # YÖNETMELİK(KLER) / KANUN(LAR)
        f.write("\n=== YÖNETMELİK(KLER) / KANUN(LAR) MADDELERİ ===\n")
        if not manage_law_list:
            f.write("  (Hiç kayıt yok.)\n")
        else:
            ml_sorted = sorted(manage_law_list, key=lambda x: x["date"])
            for rec in ml_sorted:
                f.write(f"  - {rec['date']} | {rec['heading']} | {rec['title']} [format={rec['format']}]\n")

        f.write("\nNOT: KeyError('GENELGE') hatası 'items_ = alt_dates[d_]' düzeltmesiyle giderildi.\n")

def main():
    # 5 yıllık rapor
    son_x_sene_genel_bolum(x_sene=5, output_file="5_yil_sadece_genel_pdf_html_percent.txt")
    print("Rapor oluşturuldu: 5_yil_sadece_genel_pdf_html_percent.txt")

if __name__ == "__main__":
    main()
