# Sunucu Deploy Adımları — mailotomasyon.gdgoncampusiuc.com

## 1. Kodu sunucuya kopyala

```bash
# Sunucuda
sudo mkdir -p /var/www/gdg_mail_web
sudo chown $USER:$USER /var/www/gdg_mail_web

# Yerel makineden
scp -r /path/to/gdg_mail_web user@sunucu_ip:/var/www/
```

Ya da git clone kullan:

```bash
git clone https://github.com/kullanici/repo.git /var/www/gdg_mail_web
```

## 2. Python ortamı kur

```bash
cd /var/www/gdg_mail_web
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## 3. .env dosyasını oluştur

```bash
cp deploy/env.example .env
nano .env
```

### Şifre hash'i üret (sunucuda veya yerel):

```bash
python3 -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('ŞIFRENIZI_YAZIN'))"
```

Çıkan hash'i `.env` içindeki `APP_PASSWORD_HASH=` satırına yapıştır.

### Secret key üret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Çıkan değeri `SECRET_KEY=` satırına yapıştır.

## 4. Systemd servisini kur

```bash
sudo cp deploy/gdg-mail.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gdg-mail
sudo systemctl start gdg-mail

# Durum kontrol
sudo systemctl status gdg-mail
sudo journalctl -u gdg-mail -f
```

## 5. SSL sertifikası al (Certbot)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d mailotomasyon.gdgoncampusiuc.com
```

## 6. Nginx config'i kur

```bash
sudo cp deploy/nginx_mail.conf /etc/nginx/sites-available/mailotomasyon.gdgoncampusiuc.com
sudo ln -s /etc/nginx/sites-available/mailotomasyon.gdgoncampusiuc.com \
           /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 7. DNS kaydı ekle

Domain panelinde (Cloudflare, vb.):

```
Type: A
Name: mailotomasyon
Value: sunucu_ip_adresi
TTL:  Auto
```

## Servis yönetimi

```bash
sudo systemctl restart gdg-mail   # yeniden başlat
sudo systemctl stop gdg-mail      # durdur
sudo journalctl -u gdg-mail -f    # canlı log
```
