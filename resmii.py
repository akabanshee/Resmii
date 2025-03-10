import requests
from bs4 import BeautifulSoup

def resmi_gazete_analizi(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/108.0.0.0 Safari/537.36"
        )
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("Zaman aşımına uğradı (timeout).")
        return
    except requests.exceptions.RequestException as e:
        print(f"İstek başarısız: {e}")
        return
    
    # Türkçe karakter problemi yaşamamak için encoding
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Ana başlıklar: <div class="card-title html-title">
    ana_basliklar = soup.find_all("div", class_="card-title html-title")
    
    # Rapor sözlüğü:
    # {
    #    "YÜRÜTME VE İDARE BÖLÜMÜ": {
    #         "YÖNETMELİKLER": {
    #             "toplam_madde": X,
    #             "pdf_sayisi": Y,
    #             "htm_sayisi": Z
    #         },
    #         ...
    #    },
    #    ...
    # }
    rapor = {}

    for ana_baslik in ana_basliklar:
        ana_baslik_metin = ana_baslik.get_text(strip=True)
        rapor[ana_baslik_metin] = {}
        
        sonraki = ana_baslik.find_next_sibling()
        
        while sonraki:
            # Yeni bir ana başlığa gelince alt başlık döngüsünü durdur
            if ("card-title" in sonraki.get("class", []) 
                and "html-title" in sonraki.get("class", [])):
                break
            
            # Alt başlık: <div class="html-subtitle" ...>
            if "html-subtitle" in sonraki.get("class", []):
                alt_baslik_metin = sonraki.get_text(strip=True)
                
                # Sayaçlar
                toplam_madde = 0
                pdf_sayisi = 0
                htm_sayisi = 0
                
                # Alt başlıktan sonraki kardeşleri tarayarak fihrist maddelerini bulalım
                alt_sonraki = sonraki.find_next_sibling()
                
                while alt_sonraki:
                    # Yeni alt başlık veya yeni ana başlık gördüysek dur
                    if ("html-subtitle" in alt_sonraki.get("class", []) or 
                        ("card-title" in alt_sonraki.get("class", []) and "html-title" in alt_sonraki.get("class", []))):
                        break
                    
                    # Madde: <div class="fihrist-item mb-1">
                    if ("fihrist-item" in alt_sonraki.get("class", []) 
                        and "mb-1" in alt_sonraki.get("class", [])):
                        
                        toplam_madde += 1
                        
                        # Linkleri kontrol edelim
                        links = alt_sonraki.find_all("a", href=True)
                        for link in links:
                            href_lower = link['href'].lower()
                            if href_lower.endswith('.pdf'):
                                pdf_sayisi += 1
                            elif href_lower.endswith('.htm'):
                                htm_sayisi += 1
                    
                    alt_sonraki = alt_sonraki.find_next_sibling()
                
                # Rapor sözlüğüne ekle
                rapor[ana_baslik_metin][alt_baslik_metin] = {
                    "toplam_madde": toplam_madde,
                    "pdf_sayisi": pdf_sayisi,
                    "htm_sayisi": htm_sayisi
                }
            
            sonraki = sonraki.find_next_sibling()
    
    # Raporu rapor.txt dosyasına yazalım:
    with open("rapor.txt", "w", encoding="utf-8") as f:
        f.write("=== Resmî Gazete Analizi Raporu ===\n\n")
        for a_baslik, altlar in rapor.items():
            f.write(f"Ana Başlık: {a_baslik}\n")
            if not altlar:
                f.write("  - Alt başlık bulunamadı.\n\n")
            else:
                for alt_baslik, veriler in altlar.items():
                    t_madde = veriler["toplam_madde"]
                    pdf_s = veriler["pdf_sayisi"]
                    htm_s = veriler["htm_sayisi"]
                    f.write(f"  - {alt_baslik}:\n")
                    f.write(f"      Toplam Madde: {t_madde}\n")
                    f.write(f"      PDF Sayısı  : {pdf_s}\n")
                    f.write(f"      HTM Sayısı  : {htm_s}\n")
                f.write("\n")


if __name__ == "__main__":
    url = "https://www.resmigazete.gov.tr/10.03.2025"
    resmi_gazete_analizi(url)
