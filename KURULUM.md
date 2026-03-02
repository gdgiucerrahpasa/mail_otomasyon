# 📧 Mail Otomasyon - Kurulum Kılavuzu

## 📋 Gereksinimler

- **Python 3.10 veya üzeri**
- **Google hesabı** (Gmail + Google Sheets erişimi için)
- **İnternet bağlantısı**

---

## 🚀 Hızlı Kurulum (Adım Adım)

### 1️⃣ Python Kurulumu Kontrolü

Terminali aç (Windows: cmd veya PowerShell, Mac/Linux: Terminal) ve şunu yaz:

```bash
python --version
```

Eğer `Python 3.10` veya üzeri görmüyorsan, [python.org](https://www.python.org/downloads/) adresinden indir.

---

### 2️⃣ Proje Klasörünü Aç

Zip dosyasını çıkart ve klasöre gir:

```bash
cd mail_otomasyon_final
```

veya klasörün bulunduğu yere git.

---

### 3️⃣ Gerekli Kütüphaneleri Kur

```bash
pip install -r requirements.txt
```

**Not:** Eğer `pip` bulunamazsa şunu dene:
```bash
python -m pip install -r requirements.txt
```

veya Mac/Linux'ta:
```bash
pip3 install -r requirements.txt
```

---

### 4️⃣ Google Cloud Console Ayarları

#### a) Proje Oluştur
1. [Google Cloud Console](https://console.cloud.google.com) adresine git
2. **Yeni Proje** oluştur (örn. "Mail Otomasyon")

#### b) Google Sheets API'yi Etkinleştir
1. Sol menüden **APIs & Services → Library**
2. "Google Sheets API" ara ve **Enable** (Etkinleştir)

#### c) OAuth 2.0 Credentials Oluştur
1. **APIs & Services → Credentials**
2. **Create Credentials → OAuth client ID**
3. **Application type:** Desktop app
4. İsim ver (örn. "Mail Otomasyon Desktop")
5. **Create** → JSON dosyasını indir

#### d) JSON Dosyasını Kopyala
İndirilen JSON dosyasını `credentials.json` olarak **proje klasörüne** yapıştır.

---

### 5️⃣ Google Sheets Hazırlığı

#### Sayfa 1: "Kişi Bilgileri" (Gönderenler)

| İsim | Ünvan | Gmail | App Password | İmza Linki |
|------|-------|-------|--------------|-----------|
| Ali Yılmaz | Koordinatör | ali@gmail.com | xxxx xxxx xxxx xxxx | https://drive.usercontent.google.com/download?id=FILE_ID |

**Gmail App Password Nasıl Alınır:**
1. Gmail → Sağ üst profil fotoğrafı → **Hesabı Yönet**
2. **Güvenlik** → **2 Adımlı Doğrulama** (aktif et)
3. **Uygulama Şifreleri** → "Mail" seç → **Oluştur**
4. Çıkan 16 haneli şifreyi kopyala

**İmza Resmi Linki Nasıl Alınır:**
1. Drive'a imza resmini yükle
2. Sağ tık → **Paylaş** → **Bağlantıyı al** → **Erişimi olan herkes** → **Kopyala**
3. Link formatı: `https://drive.google.com/file/d/FILE_ID/view`
4. Bunu şuna çevir: `https://drive.usercontent.google.com/download?id=FILE_ID`

#### Sayfa 2: "Alıcı Listesi"

| Kişi Adı | Şirket | Pozisyon | E-posta | Son Mail Tarihi | Mail Sayısı | Message-ID | Datayı Giren | Dönüş Durumu | Şablon No |
|----------|--------|----------|---------|----------------|-------------|------------|--------------|--------------|-----------|
| Ahmet Bey | ABC A.Ş. | Müdür | ahmet@abc.com | | 0 | | Ali Yılmaz | | 1 |

**Sütun Açıklamaları:**
- **Şablon No:** Hangi mail şablonu kullanılacak (1, 2, 3, veya 4)
- **Mail Sayısı:** Kaç kere mail atıldı (başlangıç: 0)
- **Dönüş Durumu:** Cevap geldiyse `1` yaz → bir daha mail atılmaz
- **Datayı Giren:** "Kişi Bilgileri" sayfasındaki hangi kişinin hesabından gönderilecek

---

### 6️⃣ Uygulamayı Başlat

```bash
python main.py
```

**İlk çalıştırmada:**
- Tarayıcı açılır → Google hesabınızı seçin
- "Bu uygulama doğrulanmadı" uyarısı → **Gelişmiş** → **... (güvenli değil) uygulamasına git**
- **Devam Et**
- `token.json` otomatik oluşturulur

---

## 🎨 Uygulama Kullanımı

### Sekmeler:

| Sekme | Ne Yapılır |
|-------|-----------|
| 🔗 **Bağlantı** | Spreadsheet ID gir, credentials.json yükle, sayfa isimlerini ayarla |
| 📊 **Sütunlar** | Google Sheets'teki sütun başlıklarını eşleştir |
| ✉️ **Şablonlar** | 4 mail şablonu + hatırlatma, konu, CC/BCC, ek dosyalar |
| ⚙️ **Ayarlar** | Bekleme süresi (180 sn), hatırlatma günü (3), max mail (50) |
| 🚀 **Gönderim** | **Gönderimi Başlat** butonuna bas, canlı logları izle |

---

## 🔧 İlk Ayar Adımları (UI'da)

### 1. Bağlantı Sekmesi
- **Spreadsheet ID:** Google Sheets URL'sindeki ID'yi yapıştır  
  `https://docs.google.com/spreadsheets/d/[BU_KISIM_ID]/edit`
- **Credentials JSON:** `credentials.json` dosyasını seç
- **Gönderenler sayfası:** `Kişi Bilgileri`
- **Alıcılar sayfası:** `Alıcı Listesi`
- **Bağlantıyı Test Et** → Yeşil ✅ görmeli

### 2. Sütunlar Sekmesi
Her iki tablodaki sütun başlıklarını tam olarak yaz (büyük/küçük harf farketmez).

### 3. Şablonlar Sekmesi
- **Mail Konusu:** Örn. "İş Birliği Teklifi"
- **4 Şablon + Hatırlatma:** HTML destekli metinler yaz
- **Yer tutucular:** `[Kişi Adı]` `[Şirket Adı]` `[Pozisyon]` `[Datayı Giren]` `[Ünvan]`
- **CC/BCC:** Virgülle ayır (örn. `cc@example.com, bcc@example.com`)
- **Ekler:** PDF veya diğer dosyaları seç

### 4. Gönderim Sekmesi
**▶ Gönderimi Başlat** → Logları izle → Tamamlandığında özet görürsün.

---

## 🐛 Sorun Giderme

### "ModuleNotFoundError: No module named 'google'"
```bash
pip install -r requirements.txt --force-reinstall
```

### "Spreadsheet bulunamadı" hatası
- Spreadsheet ID'yi kontrol et
- Google hesabının sheet'e erişimi olmalı

### "SMTP Auth Error"
- Gmail App Password'ü doğru kopyaladın mı?
- 2 Adımlı Doğrulama aktif mi?

### "Satır güncellenemedi"
- Sütun başlıkları tam olarak eşleşmeli
- "Sütunlar" sekmesinden kontrol et

### "Token expired" hatası
`token.json` dosyasını sil, uygulamayı yeniden başlat.

---

## 📝 Gönderim Mantığı Özeti

```
Mail Sayısı = 0 → Sheets'teki "Şablon No"ya göre ilk mail
Mail Sayısı ≥ 1 → 3 gün geçmişse "Hatırlatma" şablonu (aynı zincir)
Dönüş Durumu = 1 → Atla (bir daha mail atma)
```

**Gönderici rotasyonu:** Her gönderici değişiminde 3 dk bekleme (spam önlemi)

---

## 📞 Destek

Sorun yaşarsan `mail_otomasyon.log` dosyasını kontrol et, detaylı hatalar orada.

**Başarılar! 🚀**
