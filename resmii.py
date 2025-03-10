import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta

def parse_ilan_sayfasi(url):
    ilanlar = []
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        return ilanlar  # Erişilemezse boş
    
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
    Daha önce yazdığımız mantık: ana başlıkları (card-title html-title),
    alt başlıkları (html-subtitle), fihrist maddeleri (fihrist-item mb-1),
    PDF/HTM link sayılarını, İLAN BÖLÜMÜ gibi alt sayfa linklerini toplar.
    Dönen sonuç sözlük yapısındadır.
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
        return rapor  # Eğer siteye ulaşılamazsa boş rapor
    
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    
    ana_basliklar = soup.find_all("div", class_="card-title html-title")
    
    for ana_baslik in ana_basliklar:
        ana_baslik_metin = ana_baslik.get_text(strip=True)
        
        if "İLAN BÖLÜMÜ" in ana_baslik_metin.upper():
            # İlan bölümü alt linkleri
            sonraki = ana_baslik.find_next_sibling()
            while sonraki:
                if ("card-title" in sonraki.get("class", []) 
                    and "html-title" in sonraki.get("class", [])):
                    break
                if ("fihrist-item" in sonraki.get("class", []) 
                    and "mb-1" in sonraki.get("class", [])):
                    a_tag = sonraki.find("a", href=True)
                    if a_tag:
                        link_text = a_tag.get_text(strip=True)
                        ilan_link = a_tag["href"]
                        if ilan_link.startswith("/"):
                            ilan_link = "https://www.resmigazete.gov.tr" + ilan_link
                        # Alt sayfayı parse et
                        ilan_sayfa_sonucu = parse_ilan_sayfasi(ilan_link)
                        rapor["İlan Bölümü"][link_text] = {
                            "url": ilan_link,
                            "ilanlar": ilan_sayfa_sonucu
                        }
                sonraki = sonraki.find_next_sibling()
            
        else:
            # Genel Bölümler
            rapor["Genel Bölümler"][ana_baslik_metin] = {}
            sonraki = ana_baslik.find_next_sibling()
            while sonraki:
                if ("card-title" in sonraki.get("class", []) 
                    and "html-title" in sonraki.get("class", [])):
                    break
                if "html-subtitle" in sonraki.get("class", []):
                    alt_baslik_metin = sonraki.get_text(strip=True)
                    toplam_madde = 0
                    pdf_sayisi = 0
                    htm_sayisi = 0
                    alt_sonraki = sonraki.find_next_sibling()
                    
                    while alt_sonraki:
                        if ("html-subtitle" in alt_sonraki.get("class", []) or
                            ("card-title" in alt_sonraki.get("class", []) and "html-title" in alt_sonraki.get("class", []))):
                            break
                        
                        if ("fihrist-item" in alt_sonraki.get("class", []) 
                            and "mb-1" in alt_sonraki.get("class", [])):
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


def raporu_haftalik_txt_yaz(haftalik_veri, dosya_adi="haftalik_rapor.txt"):
    """
    haftalik_veri: { "2025-03-10": rapor_gunu, "2025-03-09": rapor_gunu, ... }
    Bu fonksiyon, sıralı şekilde raporları yazıp en sona bir özet analiz ekler.
    """
    # Basit bir analiz yapmak için PDF, HTM, toplam madde sayılarının
    # yedi gün boyunca toplanmasını sağlayacağız:
    total_pdf = 0
    total_htm = 0
    total_madde = 0
    
    with open(dosya_adi, "w", encoding="utf-8") as f:
        f.write("=== Bir Haftalık Resmî Gazete Analizi ===\n\n")
        
        # Tarihleri (anahtarları) "yeniden eskiye" sıralıyoruz:
        tarih_listesi = sorted(haftalik_veri.keys(), reverse=True)
        
        for gun_str in tarih_listesi:
            rapor = haftalik_veri[gun_str]
            f.write(f"--- {gun_str} Tarihli Rapor ---\n\n")
            
            # 1) Genel Bölümler
            genel = rapor.get("Genel Bölümler", {})
            if not genel:
                f.write("  (Genel Bölüm kaydı bulunamadı veya siteye erişilemedi)\n\n")
            else:
                for ana_b, altlar in genel.items():
                    f.write(f"Ana Başlık: {ana_b}\n")
                    if not altlar:
                        f.write("  - Alt başlık yok.\n\n")
                    else:
                        for alt_b, veriler in altlar.items():
                            f.write(f"  - {alt_b}:\n")
                            t_madde = veriler["toplam_madde"]
                            pdf_s = veriler["pdf_sayisi"]
                            htm_s = veriler["htm_sayisi"]
                            
                            f.write(f"      Toplam Madde: {t_madde}\n")
                            f.write(f"      PDF Sayısı  : {pdf_s}\n")
                            f.write(f"      HTM Sayısı  : {htm_s}\n\n")
                            
                            # Analiz için toplayalım
                            total_madde += t_madde
                            total_pdf += pdf_s
                            total_htm += htm_s
                
            # 2) İlan Bölümü
            ilanlar = rapor.get("İlan Bölümü", {})
            f.write("İLAN BÖLÜMÜ:\n")
            if not ilanlar:
                f.write("  - (İlan bölümü yok veya erişilemedi)\n\n")
            else:
                for alt_baslik, data in ilanlar.items():
                    f.write(f"  {alt_baslik} => {data['url']}\n")
                    # data['ilanlar'] -> liste
                    if not data["ilanlar"]:
                        f.write("    * Hiç ilan linki yok.\n\n")
                    else:
                        for idx, ilan_info in enumerate(data["ilanlar"], 1):
                            f.write(f"    {idx}. {ilan_info['metin']}\n")
                            f.write(f"       Link : {ilan_info['href']}\n")
                            f.write(f"       PDF  : {ilan_info['pdf_sayisi']}, HTM : {ilan_info['htm_sayisi']}\n\n")
                            total_pdf += ilan_info['pdf_sayisi']
                            total_htm += ilan_info['htm_sayisi']
            f.write("\n\n")
        
        # Hafta Sonu Analizi
        f.write("=== HAFTALIK GENEL ANALİZ ===\n")
        f.write(f"Toplam Madde (Genel Bölümler): {total_madde}\n")
        f.write(f"Toplam PDF Bağlantısı: {total_pdf}\n")
        f.write(f"Toplam HTM Bağlantısı: {total_htm}\n")
        
        # Burada isterseniz pdf_orani = total_pdf / (total_pdf+total_htm) gibi
        # ek istatistik de ekleyebilirsiniz.


def main():
    # Örnek: Bugünü 10 Mart 2025 kabul edelim.
    # 7 günlük rapor (bugün dahil)
    # En güncel = 10.03.2025, sonra 09.03.2025, ... 04.03.2025
    
    base_date = date(2025, 3, 10)
    gunluk_raporlar = {}  # { "10.03.2025": rapor, "09.03.2025": rapor, ... }
    
    for i in range(7):
        # i = 0 => bugünün raporu, i=1 => dün, ...
        current_day = base_date - timedelta(days=i)
        day_str = current_day.strftime("%d.%m.%Y")  # 10.03.2025 format
        
        url = f"https://www.resmigazete.gov.tr/{day_str}"
        rapor = resmi_gazete_analizi(url)
        
        # Anahtar olarak "10.03.2025" kullanıyoruz:
        gunluk_raporlar[day_str] = rapor
    
    # Artık 7 günlük rapor sözlüğümüz var. Bunu txt dosyasına yazalım.
    raporu_haftalik_txt_yaz(gunluk_raporlar, "haftalik_rapor.txt")
    
    print("Haftalık rapor oluşturuldu: haftalik_rapor.txt")


if __name__ == "__main__":
    main()
