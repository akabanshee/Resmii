import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta

# Bu anahtar kelimeleri içeren alt başlıkları "özel" kabul ediyoruz
SPECIAL_KEYWORDS = ["KANUN", "YÖNETMELİK", "TEBLİĞ", "GENELGE"]

def alt_baslik_is_special(heading_text):
    """
    Alt başlık metninde eğer SPECIAL_KEYWORDS içinden herhangi bir kelime geçiyorsa True döner.
    Normalleştirme yok: 'KANUN', 'KANUNLAR', 'KANUNUN' gibi her varyasyon ayrı başlıktır.
    """
    h_up = heading_text.upper()
    for kw in SPECIAL_KEYWORDS:
        if kw in h_up:
            return True
    return False

def parse_ilan_sayfasi(url):
    """
    İlan alt sayfasına gider, tüm <a> linklerini toplayarak
    .pdf / .htm linklerinin sayısını tutar.
    Dönüş: [ {metin, href, pdf_sayisi, htm_sayisi}, ... ]
    """
    ilanlar = []
    try:
        r = requests.get(url, timeout=10)  # timeout eklendi
        r.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"[Zaman Aşımı] İlan sayfası: {url}")
        return ilanlar
    except requests.exceptions.RequestException as e:
        print(f"[İstek Hatası] İlan sayfası: {url} - {e}")
        return ilanlar
    
    # Otomatik charset tespit yerine doğrudan UTF-8
    r.encoding = "utf-8"
    
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
    Bir günün (ör: 10.03.2025) Resmî Gazete sayfasını parse eder.
    Her ana başlık, alt başlık ve fihrist maddelerini raporlar.
    
    Dönüş:
    {
      "Genel Bölümler": {
        "<ANA_BASLIK>": {
          "<ALT_BASLIK>": {
            "toplam_madde": X,
            "pdf_sayisi": Y,
            "htm_sayisi": Z,
            "items": [
               {"title": "...", "format": "pdf|htm|pdf+htm|none"},
               ...
            ]
          },
          ...
        },
        ...
      },
      "İlan Bölümü": {
        "<link_text>": {
           "url": "...",
           "ilanlar": [ {metin, href, pdf_sayisi, htm_sayisi}, ... ]
        },
        ...
      }
    }
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }
    
    rapor = {"Genel Bölümler": {}, "İlan Bölümü": {}}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)  # timeout eklendi
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"[Zaman Aşımı] Ana sayfa: {url}")
        return rapor
    except requests.exceptions.RequestException as e:
        print(f"[İstek Hatası] Ana sayfa: {url} - {e}")
        return rapor
    
    # Otomatik tespit yerine doğrudan UTF-8
    response.encoding = "utf-8"
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Ana başlıklar: <div class="card-title html-title">
    ana_basliklar = soup.find_all("div", class_="card-title html-title")
    
    for ana_baslik in ana_basliklar:
        ana_baslik_metin = ana_baslik.get_text(strip=True)
        
        # İLAN BÖLÜMÜ
        if "İLAN BÖLÜMÜ" in ana_baslik_metin.upper():
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
            # GENEL BÖLÜMLER
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
                    items_list = []
                    
                    alt_sonraki = sonraki.find_next_sibling()
                    while alt_sonraki:
                        if ("html-subtitle" in alt_sonraki.get("class", []) or
                            ("card-title" in alt_sonraki.get("class", []) and "html-title" in alt_sonraki.get("class", []))):
                            break
                        
                        if ("fihrist-item" in alt_sonraki.get("class", []) and "mb-1" in alt_sonraki.get("class", [])):
                            toplam_madde += 1
                            maddelinks = alt_sonraki.find_all("a", href=True)
                            
                            item_text = alt_sonraki.get_text(" ", strip=True)
                            
                            item_pdf = 0
                            item_htm = 0
                            for ml in maddelinks:
                                ml_href = ml["href"].lower().strip()
                                if ml_href.endswith(".pdf"):
                                    item_pdf += 1
                                elif ml_href.endswith(".htm"):
                                    item_htm += 1
                            
                            # format
                            if item_pdf > 0 and item_htm == 0:
                                item_format = "pdf"
                            elif item_pdf == 0 and item_htm > 0:
                                item_format = "htm"
                            elif item_pdf > 0 and item_htm > 0:
                                item_format = "pdf+htm"
                            else:
                                item_format = "none"
                            
                            pdf_sayisi += item_pdf
                            htm_sayisi += item_htm
                            
                            items_list.append({
                                "title": item_text,
                                "format": item_format
                            })
                        
                        alt_sonraki = alt_sonraki.find_next_sibling()
                    
                    rapor["Genel Bölümler"][ana_baslik_metin][alt_baslik_metin] = {
                        "toplam_madde": toplam_madde,
                        "pdf_sayisi": pdf_sayisi,
                        "htm_sayisi": htm_sayisi,
                        "items": items_list
                    }
                sonraki = sonraki.find_next_sibling()
    
    return rapor

def son_1_yil_analizi(output_file="1_yil_raporu.txt"):
    """
    Bugünden geriye 1 yılın her gününü tarar. (timeout=10 ile yavaş/yanıtsız istekler atlanır)
    Her günün raporunu toplayıp, ana/alt başlık frekansı ve maddeleri .txt'ye yazar.
    """
    today = date.today()
    baslangic = date(today.year - 1, today.month, today.day)
    bitis = today
    
    heading_freq = {}
    sub_heading_freq = {}
    total_madde = 0
    total_pdf = 0
    total_htm = 0
    
    # Özel alt başlık detaylarını tutmak isterseniz ek bir yapı oluşturabilirsiniz.
    # Bu örnekte sadece frekans + toplu veri + maddeler raporluyoruz.
    
    current_day = baslangic
    while current_day <= bitis:
        iso_date_str = current_day.isoformat()
        rgz_date_str = current_day.strftime("%d.%m.%Y")
        
        url = f"https://www.resmigazete.gov.tr/{rgz_date_str}"
        gunluk_rapor = resmi_gazete_analizi(url)
        
        # GENEL BÖLÜMLER
        for ana_b, alt_dict in gunluk_rapor["Genel Bölümler"].items():
            heading_freq[ana_b] = heading_freq.get(ana_b, 0) + 1
            
            for alt_b, alt_info in alt_dict.items():
                sub_heading_freq[alt_b] = sub_heading_freq.get(alt_b, 0) + 1
                
                total_madde += alt_info["toplam_madde"]
                total_pdf += alt_info["pdf_sayisi"]
                total_htm += alt_info["htm_sayisi"]
        
        # İLAN BÖLÜMÜ
        ilan_data = gunluk_rapor["İlan Bölümü"]
        if ilan_data:
            heading_freq["İLAN BÖLÜMÜ"] = heading_freq.get("İLAN BÖLÜMÜ", 0) + 1
            for alt_b, alt_info in ilan_data.items():
                sub_heading_freq[alt_b] = sub_heading_freq.get(alt_b, 0) + 1
                
                pdf_ilan = sum(i["pdf_sayisi"] for i in alt_info["ilanlar"])
                htm_ilan = sum(i["htm_sayisi"] for i in alt_info["ilanlar"])
                total_pdf += pdf_ilan
                total_htm += htm_ilan
        
        current_day += timedelta(days=1)
    
    # Raporu yaz
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=== Son 1 Yıl Resmî Gazete Analizi (Timeout=10, UTF-8) ===\n\n")
        f.write(f"Başlangıç Tarihi: {baslangic}\n")
        f.write(f"Bitiş Tarihi: {bitis}\n\n")
        
        f.write(f"Toplam Madde: {total_madde}\n")
        f.write(f"Toplam PDF: {total_pdf}\n")
        f.write(f"Toplam HTM: {total_htm}\n\n")
        
        # Frekans
        heading_list = sorted(heading_freq.items(), key=lambda x: x[1], reverse=True)
        sub_list = sorted(sub_heading_freq.items(), key=lambda x: x[1], reverse=True)
        
        f.write(f"Farklı Ana Başlık Sayısı: {len(heading_list)}\n")
        f.write(f"Farklı Alt Başlık Sayısı: {len(sub_list)}\n\n")
        
        f.write("En Sık Geçen 5 Ana Başlık (kaç günde görülmüş):\n")
        for hb, c in heading_list[:5]:
            f.write(f"  - {hb}: {c}\n")
        
        f.write("\nEn Sık Geçen 10 Alt Başlık (kaç günde görülmüş):\n")
        for sb, c in sub_list[:10]:
            f.write(f"  - {sb}: {c}\n")
        
        f.write("\n=== TÜM ANA BAŞLIKLAR (frekans) ===\n")
        for hb, freq_val in heading_list:
            f.write(f"  - {hb}: {freq_val}\n")
        
        f.write("\n=== TÜM ALT BAŞLIKLAR (frekans) ===\n")
        for sb, freq_val in sub_list:
            f.write(f"  - {sb}: {freq_val}\n")
        
        f.write("\nNOT: Her başlık bir günde birçok defa da geçse 1 sayılır.\n")

def main():
    son_1_yil_analizi("1_yil_raporu.txt")
    print("1 yıllık rapor oluşturuldu: 1_yil_raporu.txt")

if __name__ == "__main__":
    main()
