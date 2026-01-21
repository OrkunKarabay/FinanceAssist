from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- GOOGLE SHEETS BAĞLANTILARI ---
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

def get_sheet():
    return get_client().open("FinansDB").sheet1

def get_settings_sheet():
    return get_client().open("FinansDB").worksheet("Ayarlar")

def get_subs_sheet():
    # Yeni Abonelikler Sayfası
    return get_client().open("FinansDB").worksheet("Abonelikler")

# --- OTOMATİK ABONELİK MOTORU ---
def abonelikleri_kontrol_et():
    try:
        subs_sheet = get_subs_sheet()
        main_sheet = get_sheet()
        
        abonelikler = subs_sheet.get_all_records()
        simdi = datetime.now()
        bu_ay_str = simdi.strftime("%Y-%m") # Örn: 2026-01
        bugun_gun = simdi.day
        
        guncellendi = False

        # Abonelikleri tek tek gez
        for i, sub in enumerate(abonelikler):
            # Eğer bu ay henüz ödenmediyse VE günü geldiyse (veya geçtiyse)
            odeme_gunu = int(sub['Odeme_Gunu'])
            son_islem = str(sub['Son_Islem_Ay']) # Excel bazen int okuyabilir, str yapalım

            if son_islem != bu_ay_str and bugun_gun >= odeme_gunu:
                # 1. Harcamalara Ekle
                yeni_satir = [
                    str(uuid.uuid4()),
                    sub['Baslik'],
                    float(sub['Tutar']),
                    sub['Kategori'],
                    sub['Platform'],
                    simdi.strftime("%Y-%m-%d %H:%M") # İşlem tarihi
                ]
                main_sheet.append_row(yeni_satir)
                
                # 2. Abonelik sayfasında "Son İşlem" tarihini güncelle
                # i+2 çünkü: i 0'dan başlar, Excel satırı 1'den başlar, 1 satır da başlıktır.
                subs_sheet.update_cell(i + 2, 7, bu_ay_str)
                guncellendi = True
                print(f"🔄 Otomatik Ödeme Eklendi: {sub['Baslik']}")

        return guncellendi
    except Exception as e:
        print(f"Abonelik Motoru Hatası: {e}")
        return False

@app.route('/')
def home():
    return render_template('index.html')

# --- APILER ---

@app.route('/api/maas', methods=['GET'])
def get_maas():
    try:
        sh = get_settings_sheet()
        val = sh.acell('A1').value
        return jsonify({"maas": float(val) if val and val.replace('.','',1).isdigit() else 0})
    except: return jsonify({"maas": 0})

@app.route('/api/maas', methods=['POST'])
def update_maas():
    try:
        get_settings_sheet().update('A1', [[request.json['maas']]])
        return jsonify({"mesaj": "OK"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/harcamalar', methods=['GET'])
def get_harcamalar():
    try:
        # ÖNCE KONTROL ET: Günü gelen abonelik var mı?
        abonelikleri_kontrol_et()
        
        sheet = get_sheet()
        all_rows = sheet.get_all_values()
        if not all_rows: return jsonify([])

        headers = all_rows[0]
        veriler = []
        for row in all_rows[1:]:
            item = {}
            for i, val in enumerate(row):
                if i < len(headers) and headers[i].strip(): item[headers[i]] = val
            veriler.append(item)
        return jsonify(veriler[::-1])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ekle', methods=['POST'])
def ekle():
    try:
        data = request.json
        
        # Eğer "Abonelik" ise farklı sayfaya, değilse ana sayfaya
        if data.get('is_abonelik'):
            sheet = get_subs_sheet()
            yeni_satir = [
                str(uuid.uuid4()), data['baslik'], float(data['tutar']),
                data['kategori'], data['platform'],
                data['odeme_gunu'], "YENI" # Son işlem "YENI" olsun ki ilk kontrolde eklesin
            ]
            sheet.append_row(yeni_satir)
        else:
            sheet = get_sheet()
            yeni_satir = [
                str(uuid.uuid4()), data['baslik'], float(data['tutar']),
                data['kategori'], data['platform'],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ]
            sheet.append_row(yeni_satir)
            
        return jsonify({"mesaj": "Eklendi"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sil/<id>', methods=['DELETE'])
def sil(id):
    try:
        sheet = get_sheet()
        try:
            cell = sheet.find(id)
            sheet.delete_rows(cell.row)
            return jsonify({"mesaj": "Silindi"})
        except: return jsonify({"error": "Yok"}), 404
    except Exception as e: return jsonify({"error": str(e)}), 500

# Abonelikleri Listeleme API'si
@app.route('/api/abonelikler', methods=['GET'])
def get_abonelikler():
    try:
        sheet = get_subs_sheet()
        records = sheet.get_all_records()
        return jsonify(records)
    except: return jsonify([])

# Abonelik Silme API'si
@app.route('/api/abonelik/sil/<id>', methods=['DELETE'])
def sil_abonelik(id):
    try:
        sheet = get_subs_sheet()
        cell = sheet.find(id)
        sheet.delete_rows(cell.row)
        return jsonify({"mesaj": "Abonelik İptal"})
    except: return jsonify({"error": "Hata"}), 500

if __name__ == '__main__':
    # Başlangıç Kontrolleri
    try:
        c = get_client()
        db = c.open("FinansDB")
        # Abonelikler sayfası yoksa oluştur
        try:
            db.worksheet("Abonelikler")
        except:
            ws = db.add_worksheet(title="Abonelikler", rows=20, cols=7)
            ws.append_row(["ID", "Baslik", "Tutar", "Kategori", "Platform", "Odeme_Gunu", "Son_Islem_Ay"])
            print("✅ 'Abonelikler' sayfası oluşturuldu.")
    except Exception as e:
        print(f"⚠️ Drive Hatası: {e}")

    app.run(debug=True, port=5001)