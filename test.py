import gspread
from oauth2client.service_account import ServiceAccountCredentials

try:
    print("1. Bağlantı kuruluyor...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    
    print("2. Tablo aranıyor...")
    sheet = client.open("FinansDB").sheet1
    
    print("3. Yazma testi yapılıyor...")
    sheet.update_cell(1, 1, "Bağlantı Başarılı!")
    
    print("✅ HARİKA! Her şey çalışıyor. Flask uygulamasını başlatabilirsin.")

except FileNotFoundError:
    print("❌ HATA: 'credentials.json' dosyası bulunamadı. Adını veya yerini kontrol et.")
except gspread.exceptions.SpreadsheetNotFound:
    print("❌ HATA: Tablo bulunamadı!")
    print("   - Tablo adının 'MovyFinansDB' olduğundan emin ol.")
    print("   - Tabloyu client_email adresine paylaştığından emin ol.")
except Exception as e:
    print(f"❌ BEKLENMEYEN HATA: {e}")