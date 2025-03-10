import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta

def parse_ilan_sayfasi(url):
    """İlan alt sayfasına gider, tüm <a> linklerini toplayarak PDF/HTM sayısını döndürür."""
    ilanlar = []
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        return ilanlar  # Sayfa erişilemezse boş
    
    soup = BeautifulSoup(r.text, "html.parser")
    linkler = soup.find_all("a", href=True)
    for l in linkler:
        metin = l.get_text(strip=True)
        href = l["href"].strip()
        
        pdf_say = 0
        htm_say = 0
        lower_href = href.lower()
        if lower_href.endswith(".pdf"):
            pdf_say = 1
        elif lower_href.endswith(".htm"):
            htm_say = 1
        
        ilanlar.append({
            "metin": metin,
            "href": href,
            "pdf_sayisi": pdf_say,
            "htm_sayisi": htm_say
        })
    return ilanlar


def resmi_gazete_analizi(url):
    """
    Bir günün (ör. 10.03.2025) Resmî Gazete sayfasını parse eder.
    Ana/Alt başlık, toplam madde, PDF/HTM sayısı, İlan alt sayfalarını döndürür.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }
    
    rapor = {
        "Genel Bölümler": {},
        "İlan Bölümü": {}
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return rapor  # Erişilemezse boş
    
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    
    ana_basliklar = soup.find_all("div", class_="card-title html-title")
    
    for ana_baslik in ana_basliklar:
        ana_baslik_metin = ana_baslik.get_text(strip=True)
        
        if "İLAN BÖLÜMÜ" in ana_baslik_metin.upper():
            # İlan linkleri
            sonraki = ana_baslik.find_next_sibling()
            while sonraki:
                if ("card-title" in sonraki.get("class", []) and "html-title" in sonraki.get("class", [])):
                    break
                if ("fihrist-item" in sonraki.get("class", []) and "mb-1" in sonraki.get("class", [])):
                    a_tag = sonraki.find("a", href=True)
                    if a_tag:
                        link_text = a_tag.get_text(strip=True)
                        ilan_link = a_tag["href"]
                        if ilan_link.startswith("/"):
                            ilan_link = "https://www.resmigazete.gov.tr" + ilan_link
                        
                        ilan_sayfa_sonucu = parse_ilan_sayfasi(ilan_link)
                        rapor["İlan Bölümü"][link_text] = {
                            "url": ilan_link,
                            "ilanlar": ilan_sayfa_sonucu
                        }
                sonraki = sonraki.find_next_sibling()
        else:
            # Genel başlık
            rapor["Genel Bölümler"][ana_baslik_metin] = {}
            sonraki = ana_baslik.find_next_sibling()
            
            while sonraki:
                if ("card-title" in sonraki.get("class", []) and "html-title" in sonraki.get("class", [])):
                    break
                if "html-subtitle" in sonraki.get("class", []):
                    alt_baslik_metin = sonraki.get_text(strip=True)
                    
                    toplam_madde = 0
                    pdf_sayisi = 0
                    htm_sayisi = 0
                    
                    alt_sonraki = sonraki.find_next_sibling()
                    while alt_sonraki:
                        # yeni alt başlık veya ana başlık gelince dur
                        if ("html-subtitle" in alt_sonraki.get("class", []) or
                            ("card-title" in alt_sonraki.get("class", []) and "html-title" in alt_sonraki.get("class", []))):
                            break
                        
                        if ("fihrist-item" in alt_sonraki.get("class", []) and "mb-1" in alt_sonraki.get("class", [])):
                            toplam_madde += 1
                            maddelinks = alt_sonraki.find_all("a", href=True)
                            for ml in maddelinks:
                                ml_href = ml["href"].lower().strip()
                                if ml_href.endswith(".pdf"):
                                    pdf_sayisi += 1
                                elif ml_href.endswith(".htm"):
                                    htm_sayisi += 1
                        
                        alt_sonraki = alt_sonraki.find_next_sibling()
                    
                    rapor["Genel Bölümler"][ana_baslik_metin][alt_baslik_metin] = {
                        "toplam_madde": toplam_madde,
                        "pdf_sayisi": pdf_sayisi,
                        "htm_sayisi": htm_sayisi
                    }
                sonraki = sonraki.find_next_sibling()
    
    return rapor


def yillik_analiz(baslangic_tarih, bitis_tarih, dosya_adi="yillik_rapor.txt"):
    """
    İki tarih arasında her günü parse ederek:
    - Günlük özet (madde, pdf, htm)
    - Ana/Alt başlık frekansı
    - Toplam analiz
    - TÜM benzersiz ana/alt başlıklar + frekansları
    """
    gunluk_ozet = {}
    heading_freq = {}      # { "YÜRÜTME VE İDARE BÖLÜMÜ": X, ... }
    sub_heading_freq = {}  # { "YÖNETMELİKLER": Y, ... }

    total_madde_all = 0
    total_pdf_all = 0
    total_htm_all = 0

    current_day = baslangic_tarih
    one_day = timedelta(days=1)
    
    while current_day <= bitis_tarih:
        day_str = current_day.strftime("%d.%m.%Y")
        url = f"https://www.resmigazete.gov.tr/{day_str}"
        
        rapor = resmi_gazete_analizi(url)
        
        daily_madde = 0
        daily_pdf = 0
        daily_htm = 0
        
        # GENEL BÖLÜMLER
        for ana_b, alt_dict in rapor["Genel Bölümler"].items():
            heading_freq[ana_b] = heading_freq.get(ana_b, 0) + 1
            for alt_b, vals in alt_dict.items():
                sub_heading_freq[alt_b] = sub_heading_freq.get(alt_b, 0) + 1
                daily_madde += vals["toplam_madde"]
                daily_pdf += vals["pdf_sayisi"]
                daily_htm += vals["htm_sayisi"]
        
        # İLAN BÖLÜMÜ
        if rapor["İlan Bölümü"]:
            heading_freq["İLAN BÖLÜMÜ"] = heading_freq.get("İLAN BÖLÜMÜ", 0) + 1
            for alt_b, data in rapor["İlan Bölümü"].items():
                sub_heading_freq[alt_b] = sub_heading_freq.get(alt_b, 0) + 1
                for ilan_info in data["ilanlar"]:
                    daily_pdf += ilan_info["pdf_sayisi"]
                    daily_htm += ilan_info["htm_sayisi"]
        
        gunluk_ozet[day_str] = (daily_madde, daily_pdf, daily_htm)
        
        total_madde_all += daily_madde
        total_pdf_all += daily_pdf
        total_htm_all += daily_htm
        
        current_day += one_day
    
    # Raporu yazma
    with open(dosya_adi, "w", encoding="utf-8") as f:
        f.write(f"=== {baslangic_tarih.strftime('%d.%m.%Y')} - {bitis_tarih.strftime('%d.%m.%Y')} YILLIK RAPOR ===\n\n")
        
        # Günlük özet (tarih sırasını reverse=True diyorsanız alfabetik ters olacak)
        all_days_sorted = sorted(gunluk_ozet.keys(), reverse=True)
        f.write("=== GÜNLÜK ÖZET ===\n")
        for d_str in all_days_sorted:
            m, p, h = gunluk_ozet[d_str]
            f.write(f"{d_str} => Madde: {m}, PDF: {p}, HTM: {h}\n")
        
        f.write("\n\n=== GENİŞ ANALİZ ===\n")
        f.write(f"Toplam Madde: {total_madde_all}\n")
        f.write(f"Toplam PDF: {total_pdf_all}\n")
        f.write(f"Toplam HTM: {total_htm_all}\n\n")
        
        # Sık geçen ana/alt başlık sayıları
        unique_headings = list(heading_freq.keys())
        unique_subheads = list(sub_heading_freq.keys())
        
        f.write(f"Farklı Ana Başlık Sayısı: {len(unique_headings)}\n")
        f.write(f"Farklı Alt Başlık Sayısı: {len(unique_subheads)}\n\n")
        
        # En sık geçen 5 ana başlık
        sorted_headings = sorted(heading_freq.items(), key=lambda x: x[1], reverse=True)
        top_5_headings = sorted_headings[:5]
        
        f.write("En Sık Geçen 5 Ana Başlık:\n")
        for baslik, cnt in top_5_headings:
            f.write(f"  - {baslik}: {cnt} günde yer almış.\n")
        
        # En sık geçen 10 alt başlık
        sorted_subs = sorted(sub_heading_freq.items(), key=lambda x: x[1], reverse=True)
        top_10_subs = sorted_subs[:10]
        
        f.write("\nEn Sık Geçen 10 Alt Başlık:\n")
        for subb, cnt in top_10_subs:
            f.write(f"  - {subb}: {cnt} günde yer almış.\n")
        
        # Tüm ana başlıklar (tek tek, frekanslarıyla)
        f.write("\n=== BÜTÜN ANA BAŞLIKLAR (frekans) ===\n")
        for hb, freq_val in sorted_headings:
            f.write(f"  - {hb}: {freq_val}\n")
        
        # Tüm alt başlıklar (tek tek, frekanslarıyla)
        f.write("\n=== BÜTÜN ALT BAŞLIKLAR (frekans) ===\n")
        for sb, freq_val in sorted_subs:
            f.write(f"  - {sb}: {freq_val}\n")
        
        f.write("\nNOT: Burada 'frekans' başlıkların kaç farklı günde geçtiğini ifade eder.\n")


def main():
    baslangic = date(2024, 3, 10)
    bitis = date(2025, 3, 10)
    
    yillik_analiz(baslangic, bitis, "yillik_rapor.txt")
    print("Yıllık rapor oluşturuldu: yillik_rapor.txt")


if __name__ == "__main__":
    main()
