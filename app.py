import sqlite3
import random
import hashlib
import base64
import requests
import time
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'mucurlu_ozel_guvenlik_anahtari'

# --- PARATİKA AYARLARI ---
PARATIKA_API_URL = "https://vpos.paratika.com.tr/api/v2"
MERCHANT_CODE = "10005757"
MERCHANT_KEY = "UXomv9RzPyczSjLd4M1g"

# --- VERİTABANI KURULUMU ---
def veri_hazirla():
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sepet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                urun_ad TEXT,
                urun_kod TEXT,
                fiyat REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS siparisler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                musteri_ad TEXT,
                telefon TEXT,
                toplam_tutar TEXT,
                odeme_yontemi TEXT,
                siparis_no TEXT,
                tarih DATETIME DEFAULT CURRENT_TIMESTAMP,
                durum TEXT DEFAULT 'Beklemede'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS urunler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                urun_ad TEXT,
                urun_kod TEXT,
                fiyat REAL,
                kategori TEXT,
                alt_kategori TEXT,
                resim_url TEXT,
                marka_detay TEXT,
                teslimat TEXT,
                uyumlu_seri TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS duyurular (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resim_url TEXT,
                hedef_link TEXT
            )
        ''')
        conn.commit()

veri_hazirla()

# --- PARA FORMATLAMA (20.000,00₺ Formatı) ---
def format_para(deger):
    try:
        return "{:,.2f}".format(float(deger)).replace(',', 'X').replace('.', ',').replace('X', '.') + "₺"
    except:
        return "0,00₺"

# --- ARAMA FONKSİYONU ---
@app.route('/arama')
def arama():
    sorgu = request.args.get('q', '')
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM urunler WHERE urun_ad LIKE ? OR urun_kod LIKE ?",
                       ('%' + sorgu + '%', '%' + sorgu + '%'))
        db_urunler = cursor.fetchall()

        cursor.execute("SELECT * FROM duyurular")
        duyurular = [{"resim_url": d[1], "hedef_link": d[2]} for d in cursor.fetchall()]

    liste_urunler = []
    for u in db_urunler:
        liste_urunler.append({
            "id": u[0], "ad": u[1], "kod": u[2], "fiyat": format_para(u[3]),
            "kategori": u[4], "alt": u[5], "resim": u[6]
        })

    return render_template('index.html', urunler=liste_urunler, duyurular=duyurular, baslik=f"'{sorgu}' İçin Arama Sonuçları", sayfa=1, toplam_sayfa=1)

# --- ANA SAYFA VE SAYFALAMA AYARI ---
@app.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM duyurular")
        db_duyurular = cursor.fetchall()
        duyurular = [{"resim_url": d[1], "hedef_link": d[2]} for d in db_duyurular]

        cursor.execute("SELECT * FROM urunler WHERE kategori = 'Anasayfa' LIMIT ? OFFSET ?", (per_page, offset))
        db_urunler = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM urunler WHERE kategori = 'Anasayfa'")
        toplam_urun = cursor.fetchone()[0]
        toplam_sayfa = (toplam_urun + per_page - 1) // per_page

    liste_urunler = []
    for u in db_urunler:
        liste_urunler.append({
            "id": u[0], "ad": u[1], "kod": u[2], "fiyat": format_para(u[3]),
            "kategori": u[4], "alt": u[5], "resim": u[6]
        })

    return render_template('index.html', urunler=liste_urunler, duyurular=duyurular, sayfa=page, toplam_sayfa=toplam_sayfa, aktif_kategori='Anasayfa')

@app.route('/hakkimizda')
def hakkimizda():
    return render_template('hakkimizda.html')

@app.route('/mesafeli-satis-sozlesmesi')
def sozlesme():
    return render_template('sozlesme.html')

@app.route('/iptal-ve-iade-kosullari')
def iade_kosullari():
    return render_template('iptal-iade.html')

@app.route('/gizlilik-ve-cerez-politikasi')
def gizlilik():
    return render_template('gizlilik.html')

@app.route('/kvkk-aydinlatma-metni')
def kvkk():
    return render_template('kvkk.html')

@app.route('/iletisim')
def iletisim():
    return render_template('iletisim.html')

@app.route('/urun/<int:id>')
def urun_detay(id):
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM urunler WHERE id = ?", (id,))
        u = cursor.fetchone()

    if u:
        urun_verisi = {
            "id": u[0], "ad": u[1], "kod": u[2], "fiyat": format_para(u[3]),
            "kategori": u[4], "alt": u[5], "resim": u[6],
            "marka_detay": u[7] if u[7] else "MUCURLU Elite",
            "teslimat": u[8] if u[8] else "Aynı Gün Sevk",
            "uyumlu_seri": u[9] if u[9] else "-"
        }
        return render_template('urun_detay.html', urun=urun_verisi)
    else:
        return "Ürün bulunamadı!", 404

@app.route('/kategori/<ana_kat>/<alt_kat>')
def kategori_filtre(ana_kat, alt_kat):
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM duyurular")
        duyurular = [{"resim_url": d[1], "hedef_link": d[2]} for d in cursor.fetchall()]

        cursor.execute("SELECT * FROM urunler WHERE kategori = ? AND alt_kategori = ? LIMIT ? OFFSET ?", (ana_kat, alt_kat, per_page, offset))
        db_urunler = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM urunler WHERE kategori = ? AND alt_kategori = ?", (ana_kat, alt_kat))
        toplam_urun = cursor.fetchone()[0]
        toplam_sayfa = (toplam_urun + per_page - 1) // per_page

    liste_urunler = []
    for u in db_urunler:
        liste_urunler.append({
            "id": u[0], "ad": u[1], "kod": u[2], "fiyat": format_para(u[3]),
            "kategori": u[4], "alt": u[5], "resim": u[6]
        })

    return render_template('index.html', urunler=liste_urunler, duyurular=duyurular, sayfa=page, toplam_sayfa=toplam_sayfa, baslik=f"{ana_kat} - {alt_kat}")

@app.route('/sepete-ekle/<int:urun_id>', methods=['POST'])
def sepete_ekle(urun_id):
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT urun_ad, urun_kod, fiyat FROM urunler WHERE id = ?', (urun_id,))
        urun = cursor.fetchone()

        if urun:
            cursor.execute('INSERT INTO sepet (urun_ad, urun_kod, fiyat) VALUES (?, ?, ?)',
                           (urun[0], urun[1], urun[2]))
            conn.commit()
    return redirect(url_for('sepeti_goster'))

@app.route('/sepetim')
def sepeti_goster():
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, urun_ad, urun_kod, fiyat FROM sepet')
        rows = cursor.fetchall()

    sepet = []
    ara_toplam_sayi = 0
    for r in rows:
        sepet.append({"db_id": r[0], "ad": r[1], "kod": r[2], "fiyat": format_para(r[3])})
        ara_toplam_sayi += r[3]
    kdv_sayi = ara_toplam_sayi * 0.20
    genel_toplam_sayi = ara_toplam_sayi + kdv_sayi
    return render_template('sepetim.html', sepet=sepet, ara_toplam=format_para(ara_toplam_sayi), kdv_tutari=format_para(kdv_sayi), genel_toplam=format_para(genel_toplam_sayi))

@app.route('/sepetten-cikar/<int:db_id>')
def sepetten_cikar(db_id):
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sepet WHERE id = ?', (db_id,))
        conn.commit()
    return redirect(url_for('sepeti_goster'))

@app.route('/odeme-adimi')
def odeme_adimi():
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT fiyat FROM sepet')
        rows = cursor.fetchall()
    toplam_sayi = sum(r[0] for r in rows) * 1.20
    return render_template('odeme.html', toplam=format_para(toplam_sayi))

@app.route('/siparis-tamamla', methods=['GET','POST'])
def siparis_tamamla():
    ad_soyad = request.form.get('ad_soyad')
    telefon = request.form.get('telefon')
    odeme_tipi = request.form.get('odeme_tipi')
    email = "destek@mucurlu.com"

    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT urun_ad, fiyat FROM sepet')
        rows = cursor.fetchall()

        if not rows:
            return redirect(url_for('home'))

        toplam_sayi = sum(r[1] for r in rows) * 1.20
        formatli_toplam = format_para(toplam_sayi)
        siparis_no = str(int(time.time()))

        cursor.execute('''
            INSERT INTO siparisler (musteri_ad, telefon, toplam_tutar, odeme_yontemi, siparis_no, durum)
            VALUES (?, ?, ?, ?, ?, 'Beklemede')
        ''', (ad_soyad, telefon, formatli_toplam, odeme_tipi, siparis_no))

        conn.commit()

    if odeme_tipi == 'kart':
        # --- PARATİKA KESİN ÇÖZÜM ---
        tutar_str = "{:.2f}".format(toplam_sayi)
        ok_url = url_for('siparis_onay_ekrani', siparis_no=siparis_no, _external=True)
        fail_url = url_for('home', _external=True)
        
        action = "SESSIONTOKEN"
        hash_str = f"{MERCHANT_KEY}{MERCHANT_CODE}{action}{siparis_no}{tutar_str}TRY{ok_url}{fail_url}"
        token = hashlib.sha1(hash_str.encode()).hexdigest()

        params = {
            "action": str(action),
            "merchantCode": str(MERCHANT_CODE),
            "orderId": str(siparis_no),
            "amount": str(tutar_str),
            "currency": "TRY",
            "okUrl": str(ok_url),
            "failUrl": str(fail_url),
            "token": str(token),
            "customerName": str(ad_soyad),
            "customerEmail": str(email),
            "customerPhone": str(telefon),
            "isConfirm": "Y"
        }

        try:
            api_url = "https://vpos.paratika.com.tr/paratika/api/v2"
            response = requests.post(api_url, data=params)
            
            if response.status_code == 200 and response.text.strip():
                res_json = response.json()
                if res_json.get('responseCode') == '00':
                    session_token = res_json.get('sessionToken')
                    return redirect(f"https://vpos.paratika.com.tr/merchant/post/sale/{session_token}")
                else:
                    return f"Paratika Hatası: {res_json.get('responseMessage')} (Kod: {res_json.get('responseCode')})"
            else:
                return f"Paratika Sunucu Hatası! Durum Kodu: {response.status_code}"
        except Exception as e:
            return "Bağlantı Hatası: " + str(e)
    else:
        with sqlite3.connect('client_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sepet')
            conn.commit()
        return render_template('iban_odeme.html', siparis_no=siparis_no, toplam=formatli_toplam, ad_soyad=ad_soyad)

@app.route('/payment/callback', methods=['POST'])
def payment_callback():
    order_id = request.form.get('orderId')
    status = request.form.get('status')
    if status == 'SUCCESS':
        with sqlite3.connect('client_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE siparisler SET durum = 'Onaylandı' WHERE siparis_no = ?", (order_id,))
            cursor.execute('DELETE FROM sepet')
            conn.commit()
    return "OK"

@app.route('/urun-ekle', methods=['POST'])
def urun_ekle():
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))

    try:
        ad = request.form.get('ad')
        kod = request.form.get('kod')
        fiyat_raw = request.form.get('fiyat')
        fiyat = float(fiyat_raw) if fiyat_raw else 0.0
        kat = request.form.get('kategori')
        resim = request.form.get('resim')
        m_detay = request.form.get('marka_detay', 'MUCURLU Elite')
        teslim = request.form.get('teslimat', 'Aynı Gün Sevk')
        seri = request.form.get('uyumlu_seri', '-')

        secilen_alt_kategoriler = request.form.getlist('alt_kategoriler')

        with sqlite3.connect('client_data.db') as conn:
            cursor = conn.cursor()

            if not secilen_alt_kategoriler or kat == 'Anasayfa':
                cursor.execute('''
                    INSERT INTO urunler (urun_ad, urun_kod, fiyat, kategori, alt_kategori, resim_url, marka_detay, teslimat, uyumlu_seri)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (ad, kod, fiyat, kat, "Genel", resim, m_detay, teslim, seri))
            else:
                for alt in secilen_alt_kategoriler:
                    cursor.execute('''
                        INSERT INTO urunler (urun_ad, urun_kod, fiyat, kategori, alt_kategori, resim_url, marka_detay, teslimat, uyumlu_seri)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (ad, kod, fiyat, kat, alt, resim, m_detay, teslim, seri))
            conn.commit()
    except Exception as e:
        print(f"Ekleme Hatası: {e}")

    return redirect(url_for('admin_paneli'))

@app.route('/duyuru-ekle', methods=['POST'])
def duyuru_ekle():
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))
    resim = request.form.get('resim_url')
    link = request.form.get('hedef_link')
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO duyurular (resim_url, hedef_link) VALUES (?, ?)', (resim, link))
        conn.commit()
    return redirect(url_for('admin_paneli'))

@app.route('/duyuru-sil/<int:id>')
def duyuru_sil(id):
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM duyurular WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('admin_paneli'))

@app.route('/urun-duzenle/<int:id>')
def urun_duzenle(id):
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM urunler WHERE id = ?", (id,))
        urun = cursor.fetchone()
    if urun:
        return render_template('urun_duzenle.html', urun=urun)
    return "Ürün bulunamadı!", 404

@app.route('/urun-guncelle/<int:id>', methods=['POST'])
def urun_guncelle(id):
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))

    ad = request.form.get('ad')
    kod = request.form.get('kod')
    fiyat = request.form.get('fiyat')
    resim = request.form.get('resim')

    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE urunler
            SET urun_ad = ?, urun_kod = ?, fiyat = ?, resim_url = ?
            WHERE id = ?
        ''', (ad, kod, fiyat, resim, id))
        conn.commit()
    return redirect(url_for('admin_paneli'))

@app.route('/urun-sil/<int:id>')
def urun_sil(id):
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM urunler WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('admin_paneli'))

@app.route('/siparis-sil/<int:id>')
def siparis_sil(id):
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))
    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM siparisler WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('admin_paneli'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pasw = request.form.get('password')
        if user == 'admin' and pasw == 'mucurlu42':
            session['admin_girdi'] = True
            return redirect(url_for('admin_paneli'))
        else:
            return "Hatalı giriş!"
    return '''
        <div style="max-width:300px; margin:100px auto; text-align:center; font-family:sans-serif; padding:20px; border:1px solid #ddd; border-radius:10px;">
            <h2 style="color:#e60000;">MUCURLU ADMİN</h2>
            <form method="post">
                <input type="text" name="username" placeholder="Kullanıcı Adı" style="width:100%; padding:10px; margin-bottom:10px; border-radius:5px; border:1.5px solid #eee;" required><br>
                <input type="password" name="password" placeholder="Şifre" style="width:100%; padding:10px; margin-bottom:15px; border-radius:5px; border:1.5px solid #eee;" required><br>
                <button type="submit" style="background:#1a1a1a; color:white; border:none; padding:12px; width:100%; border-radius:5px; font-weight:bold; cursor:pointer;">GİRİŞ YAP</button>
            </form>
        </div>
    '''

@app.route('/mucurlu-admin')
def admin_paneli():
    if not session.get('admin_girdi'):
        return redirect(url_for('login'))

    kategoriler_sistemi = {
        "Scania": ["4 Serisi", "5 Serisi", "6 Serisi", "7 Serisi"],
        "Mercedes-Benz": ["Actros MP3", "Actros MP4", "Atego", "Axor", "Arocs"],
        "MAN": ["TGA", "TGX", "TGS"],
        "DAF": ["XF 105", "XF 106", "CF Serisi"],
        "VOLVO": ["FH Serisi", "FM Serisi"],
        "RENAULT": ["Premium", "T-Range"]
    }

    with sqlite3.connect('client_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM siparisler WHERE durum = 'Onaylandı' ORDER BY id DESC")
        siparisler = cursor.fetchall()
        cursor.execute('SELECT * FROM urunler ORDER BY id DESC')
        urunler = cursor.fetchall()
        cursor.execute('SELECT * FROM duyurular ORDER BY id DESC')
        duyurular_admin = cursor.fetchall()

    return render_template('admin.html', siparisler=siparisler, urunler=urunler, duyurular=duyurular_admin, kat_sistemi=kategoriler_sistemi)

@app.route('/logout')
def logout():
    session.pop('admin_girdi', None)
    return redirect(url_for('login'))

@app.route('/siparis-onay-ekrani/<siparis_no>')
def siparis_onay_ekrani(siparis_no):
    return render_template('siparis_onay.html', siparis_no=siparis_no)

def veritabani_guncelle():
    conn = sqlite3.connect('client_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE siparisler ADD COLUMN durum TEXT DEFAULT 'bekliyor'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

veritabani_guncelle()

def sutun_ekle_garanti():
    conn = sqlite3.connect('client_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE siparisler ADD COLUMN durum TEXT DEFAULT 'Beklemede'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

sutun_ekle_garanti()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
