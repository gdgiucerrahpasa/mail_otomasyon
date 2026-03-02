# Mail Otomasyon — Kurulum ve Kullanım

## Gereksinimler

- Python 3.10+
- Google Cloud Console'da bir proje (Gmail + Sheets API aktif)

## Kurulum

```bash
pip install -r requirements.txt
```

## Google API Kurulumu

1. [Google Cloud Console](https://console.cloud.google.com) → Yeni proje oluştur
2. **APIs & Services → Library** → "Google Sheets API" etkinleştir
3. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Application type: Desktop app
   - JSON'u indirip `credentials.json` olarak klasöre koy
4. İlk çalıştırmada tarayıcıda OAuth ekranı açılır, hesabınızı seçin.
   `token.json` otomatik oluşturulur.

## Google Sheets Yapısı

### "Kişi Bilgileri" sayfası (gönderenler):
| İsim | Ünvan | Gmail | App Password | İmza Linki |
|------|-------|-------|--------------|-----------|
| Ali Yılmaz | Koordinatör | ali@gmail.com | xxxx yyyy | https://drive... |

**App Password:** Gmail → Hesap → Güvenlik → 2 Adımlı Doğrulama → Uygulama Şifreleri

**İmza Linki:** Google Drive'da "Herkese açık" yapılmış resmin linki  
(Format: `https://drive.usercontent.google.com/download?id=FILE_ID`)

### "Alıcı Listesi" sayfası:
| Kişi Adı | Şirket | Pozisyon | E-posta | Son Mail Tarihi | Mail Sayısı | Message-ID | Datayı Giren | Dönüş Durumu | Şablon No |
|----------|--------|----------|---------|----------------|-------------|------------|--------------|--------------|-----------|
| Mehmet Bey | XYZ A.Ş. | Pazarlama Müd. | m@xyz.com | 2024-01-15 | 1 | <msg@gmail.com> | Ali Yılmaz | | 1 |

**Şablon No:** Hangi mail şablonunun kullanılacağı (1, 2, 3, veya 4). Boş bırakılırsa varsayılan 1 kullanılır.  
**Dönüş Durumu:** Dönüş aldıysanız `1` yazın → o satıra bir daha mail atılmaz.

## Çalıştırma

```bash
python main.py
```

## Sekme Açıklamaları

| Sekme | İçerik |
|-------|--------|
| 🔗 Bağlantı | Spreadsheet ID, credentials dosyası, sayfa adları |
| 📊 Sütunlar | Her iki tablodaki sütun başlıklarını eşle |
| ✉️ Şablonlar | 4 mail metni + hatırlatma metni, konu, CC/BCC, ekler |
| ⚙️ Ayarlar | Bekleme süresi, hatırlatma günü, max mail |
| 🚀 Gönderim | Başlat / Durdur, canlı log |

## Şablon Yer Tutucuları

`[Kişi Adı]` · `[Şirket Adı]` · `[Pozisyon]` · `[Datayı Giren]` · `[Ünvan]`

## Gönderim Mantığı

| Mail Sayısı | Yapılan İşlem |
|-------------|--------------|
| 0 | Sheets'teki "Şablon No" sütunundaki değere göre ilk mail (1→Şablon 1, 2→Şablon 2, vb.) |
| 1+ | Hatırlatma kontrolü: 3 gün geçmişse aynı şablonla tekrar gönderim |
| 5+ | Gönderim durduruluyor |

**Şablon Seçimi:**
- **Şablon No = 1** → Şablon 1 kullanılır
- **Şablon No = 2** → Şablon 2 kullanılır
- **Şablon No = 3** → Şablon 3 kullanılır
- **Şablon No = 4** → Şablon 4 kullanılır
- **Hatırlatma** → Hatırlatma şablonu kullanılır (In-Reply-To ile aynı zincir)

- **Gönderici değişiminde** 3 dakika beklenir (spam önlemi).
- **Hatırlatma maili** orijinal message-id'yi kullanır → Gmail'de aynı zincirde görünür.
- **Dönüş Durumu = 1** olan satırlar tamamen atlanır.
