import pandas as pd

# Dosyanın yolu
file_path = '/Users/basakayverdi/Desktop/15_yil_duplicates.xlsx'

# Excel dosyasını yükleme
df = pd.read_excel(file_path)

# Mükerrer verileri kaldırma (tüm sütunlar bazında)
df_cleaned = df.drop_duplicates()

# Linklerin başına URL ekleme
base_url = "https://www.resmigazete.gov.tr/eskiler/2019/01/"
df_cleaned.loc[:, 'Link(ler)'] = base_url + df_cleaned['Link(ler)'].str.replace('.htm', '.pdf')

# Temizlenmiş dosyayı masaüstüne kaydetme
output_path = '/Users/basakayverdi/Desktop/15_yil_cleaned.xlsx'
df_cleaned.to_excel(output_path, index=False)

print(f"Toplam madde sayısı: {len(df_cleaned)}")
print(f"Temizlenmiş dosya kaydedildi: {output_path}")
