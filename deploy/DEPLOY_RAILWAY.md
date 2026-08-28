# Railway Deploy Adımları

Bu uygulama tek process içinde çalışan bir zamanlayıcı (APScheduler) ve
bellek-içi (in-memory) bir "şu an çalışıyor mu" kilidi kullanıyor
([app/state.py](../app/state.py), [app/scheduler.py](../app/scheduler.py)).
Bu yüzden Railway'de **replica/instance sayısı kesinlikle 1'de kalmalı** —
birden fazla instance açılırsa zamanlayıcı ve gönderim kilidi birbirinden
habersiz iki kopya halinde çalışır ve aynı maile iki kere gönderim riski
doğar.

## 1. Repo'yu Railway'e bağla

1. https://railway.app → New Project → Deploy from GitHub repo
2. Bu repoyu seç. Railway, `requirements.txt` + `Procfile`'ı otomatik algılar
   (Nixpacks). Ek bir Dockerfile gerekmez.

## 2. Postgres ekle

SQLite dosyası Railway'in dosya sistiminde kalıcı değildir (her deploy'da
sıfırlanır) — bu yüzden production'da mutlaka Postgres kullan:

1. Proje içinde "+ New" → Database → PostgreSQL
2. Railway otomatik olarak `DATABASE_URL` değişkenini web servisine enjekte
   eder (Variables sekmesinde "Reference" olarak görünür). Elle bir şey
   yapmana gerek yok — [app/database.py](../app/database.py) hem
   `postgres://` hem `postgresql://` biçimini kabul edecek şekilde
   düzenlendi.

## 3. Environment değişkenlerini gir

Web servisinin **Variables** sekmesine ekle:

```
APP_USERNAME=admin
APP_PASSWORD_HASH=   # python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('SIFRENIZ'))"
SECRET_KEY=          # python -c "import secrets; print(secrets.token_hex(32))"
HTTPS_ONLY=true
SESSION_MAX_AGE=43200
GOOGLE_SHEET_ID=     # opsiyonel, Ayarlar sayfasından da girilebilir
```

### Google Sheets kimlik bilgisi

Railway'de dosya yükleme imkânı yok, bu yüzden servis hesabı JSON'unu bir
değişken olarak veriyoruz — uygulama her açılışta bunu `credentials.json`
dosyasına yazıyor ([app/main.py](../app/main.py), `_write_service_account_from_env`):

```
GOOGLE_CREDENTIALS_JSON={"type":"service_account","project_id":"...", ...tüm JSON tek satırda...}
```

Bu servis hesabının e-postasını (`client_email` alanı) hedef Google
Sheet'e **Editör** olarak paylaşmayı unutma — aksi halde okuma/yazma
başarısız olur.

(OAuth `token.json` akışı burada kullanılamaz çünkü tarayıcıda interaktif
onay gerektirir; headless bir sunucuda servis hesabı tek pratik yol.)

## 4. Deploy et ve doğrula

1. Railway otomatik build + deploy eder, `Procfile`'daki komutu çalıştırır:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
2. Settings → Generate Domain ile bir `*.up.railway.app` adresi al
   (veya kendi domainini bağla)
3. Deploy loglarında `init_db` ve scheduler başlatma satırlarını kontrol et
4. `/login` sayfasına git, `APP_USERNAME` / şifreni gir
5. Ayarlar sayfasından "Bağlantıyı Test Et" ile Sheets bağlantısını doğrula

## Notlar

- **Replikayı asla 1'in üstüne çıkarma** (Settings → yatay ölçekleme kapalı
  kalmalı).
- Gönderim motoru (`app/services/engine.py`) gönderici başına dakikalarca
  `time.sleep` ile bekliyor — bu Railway'de sorun değil çünkü process
  sürekli ayakta kalıyor (Vercel gibi serverless platformların aksine).
- Redeploy'da `credentials.json` yeniden env değişkeninden yazılır,
  Postgres verisi ise kalıcıdır (ayrı bir servis).
