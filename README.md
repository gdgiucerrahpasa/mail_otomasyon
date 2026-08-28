# GDG Mail Otomasyon

Google Sheets üzerinden yönetilen, kişiselleştirilmiş soğuk e-posta ve otomatik hatırlatma gönderimi yapan bir FastAPI web uygulaması. GDG on Campus İÜC ekibinin sponsorluk/iletişim süreçlerini otomatikleştirmek için geliştirildi.

## Özellikler

- **Kimlik doğrulama** — kullanıcı adı + bcrypt şifreli basit admin girişi
- **Dashboard** — gönderimi manuel başlat/durdur, HTMX ile canlı log akışı
- **Taslak (Draft) yönetimi** — segment bazlı "ilk mail" / "hatırlatma" şablonları, placeholder desteği
- **Otomatik zamanlayıcı** — APScheduler ile belirlenen aralıklarla otomatik çalıştırma
- **Akıllı gönderim mantığı** — ilk temas, kademeli hatırlatmalar (gün bazlı), cevap alınan kişileri atlama, gönderici başına bekleme süresi ile spam önleme
- **Google Sheets entegrasyonu** — alıcı/gönderici verisi ve gönderim geçmişi tek bir Sheet üzerinde yönetilir
- **Gmail SMTP + IMAP** — her gönderici kendi Gmail hesabından (App Password ile) gönderir, hatırlatmalar gerçek Message-ID ile aynı thread'e düşer
- **Log görüntüleyici** — çalıştırma bazlı, seviye filtreli, sayfalanmış log kayıtları

## Teknoloji

FastAPI · SQLAlchemy (SQLite/PostgreSQL) · Jinja2 + HTMX · APScheduler · Google Sheets API · smtplib/imaplib

## Google Sheet Yapısı

Spreadsheet'te iki sayfa olmalı (adları Ayarlar sayfasından değiştirilebilir):

**"Kişi Bilgileri"** (göndericiler):

| İsim | Ünvan | Gmail | App Password | İmza Linki |
|---|---|---|---|---|

- `App Password`: gönderen Gmail hesabında 2FA açılıp oluşturulan [Uygulama Şifresi](https://myaccount.google.com/apppasswords)
- `İmza Linki`: Drive dosya **ID**'si (tam paylaşım linki değil), dosya "bağlantıya sahip olan herkes görüntüleyebilir" olmalı

**"Alıcı Listesi"** (hedef kişiler):

| Kişi Adı | Şirket | Pozisyon | E-posta | Son Mail Tarihi | Mail Sayısı | Message-ID | Datayı Giren | Dönüş Durumu | Segment |
|---|---|---|---|---|---|---|---|---|---|

- `Mail Sayısı` / `Son Mail Tarihi` / `Message-ID`: boş bırakılır, uygulama otomatik doldurur
- `Datayı Giren`: "Kişi Bilgileri"ndeki `İsim` ile birebir eşleşmeli
- `Segment`: hangi taslağın kullanılacağını belirler, taslağın `slug` alanıyla eşleşir
- `Dönüş Durumu`: `1` veya "dönüş var" yazılırsa o satır bir daha mail almaz

## Kurulum (Yerel Geliştirme)

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt   # Windows: venv\Scripts\pip
cp .env.example .env                        # değerleri doldur
venv/bin/uvicorn app.main:app --reload
```

Google Sheets erişimi için bir servis hesabı oluşturup JSON anahtarını `credentials.json` olarak proje köküne koy, ardından Sheet'i servis hesabının e-posta adresine (JSON içindeki `client_email`) Editör olarak paylaş.

### Ortam Değişkenleri

| Değişken | Açıklama |
|---|---|
| `APP_USERNAME` | Admin paneli kullanıcı adı |
| `APP_PASSWORD_HASH` | bcrypt hash (`bcrypt.hashpw(...)` ile üretilir) |
| `SECRET_KEY` | Session imzalama anahtarı |
| `HTTPS_ONLY` | `true`/`false` — session cookie'nin sadece HTTPS'te çalışması |
| `SESSION_MAX_AGE` | Oturum süresi (saniye) |
| `GOOGLE_SHEET_ID` | Spreadsheet ID (Ayarlar sayfasından da girilebilir) |
| `DATABASE_URL` | Opsiyonel, verilmezse `sqlite:///./mail_web.db` |
| `GOOGLE_CREDENTIALS_JSON` | Opsiyonel — dosya yüklemenin mümkün olmadığı ortamlarda servis hesabı JSON'unu doğrudan env değişkeni olarak vermek için |

## Uygulamayı Kullanma

1. `/settings` → sütun isimlerini kontrol et, "Bağlantıyı Test Et" ile Sheets erişimini doğrula
2. `/drafts` → her segment için bir "İlk Mail" ve bir "Hatırlatma" taslağı oluştur (aynı `slug`, farklı `is_reminder`)
3. `/` (Dashboard) → "Gönderimi Başlat" ile manuel çalıştır, veya Ayarlar'dan `schedule_enabled`'ı açıp otomatik çalışmasını sağla
4. `/logs` → geçmiş çalıştırmaların detaylarını incele

## Deploy

Bu uygulama sürekli açık kalan bir process gerektirir (in-process zamanlayıcı, bellek-içi çalışma kilidi) ve Gmail'e doğrudan SMTP/IMAP bağlantısı kurar. Bu yüzden outbound SMTP portlarını (25/465/587) engelleyen PaaS platformları (ör. Railway) **uygun değildir**.

Önerilen yöntem: gerçek bir VPS (Oracle Cloud Always Free gibi) üzerinde systemd + nginx ile kalıcı deploy — adım adım rehber için [deploy/DEPLOY.md](deploy/DEPLOY.md).
