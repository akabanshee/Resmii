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
    
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    
    ana_basliklar = soup.find_all("div", class_="card-title html-title")
    
    rapor = {}

    for ana_baslik in ana_basliklar:
        ana_baslik_metin = ana_baslik.get_text(strip=True)
        rapor[ana_baslik_metin] = {}
        
        sonraki = ana_baslik.find_next_sibling()
        
        while sonraki:
            # Yeni bir ana başlık gördüysek döngüden çık
            if ("card-title" in sonraki.get("class", []) 
                and "html-title" in sonraki.get("class", [])):
                break
            
            # Alt başlıkları arayalım
            if ("html-subtitle" in sonraki.get("class", [])):
                alt_baslik_metin = sonraki.get_text(strip=True)
                
                maddeler_sayisi = 0
                alt_sonraki = sonraki.find_next_sibling()
                
                while alt_sonraki:
                    # Yeni alt başlığa veya ana başlığa geldiysek dur
                    if ("html-subtitle" in alt_sonraki.get("class", []) or 
                        ("card-title" in alt_sonraki.get("class", []) and "html-title" in alt_sonraki.get("class", []))):
                        break
                    
                    if ("fihrist-item" in alt_sonraki.get("class", []) 
                        and "mb-1" in alt_sonraki.get("class", [])):
                        maddeler_sayisi += 1
                        
                    alt_sonraki = alt_sonraki.find_next_sibling()
                
                rapor[ana_baslik_metin][alt_baslik_metin] = maddeler_sayisi
            
            sonraki = sonraki.find_next_sibling()
    
    # Raporu bir .txt dosyasına yazalım
    with open("rapor.txt", "w", encoding="utf-8") as f:
        f.write("=== Resmî Gazete Analizi Raporu ===\n")
        for a_baslik, altlar in rapor.items():
            f.write(f"\nAna Başlık: {a_baslik}\n")
            if not altlar:
                f.write("  - Alt başlık bulunamadı.\n")
            else:
                for alt_baslik, madde_sayi in altlar.items():
                    f.write(f"  - {alt_baslik}: {madde_sayi} içerik\n")


if __name__ == "__main__":
    url = "https://www.resmigazete.gov.tr/10.03.2025"
    resmi_gazete_analizi(url)
