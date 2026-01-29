# 🎯 Münazara GPT - Koyeb Deploy Rehberi

## 📋 Gereksinimler
- GitHub hesabı
- Koyeb hesabı (ücretsiz)
- API anahtarları (Telegram, Gemini, OpenRouter)

---

## 🚀 ADIM ADIM KURULUM

### ADIM 1: GitHub Repository Oluştur

1. **GitHub'a git:** https://github.com/new
2. **Repository adı:** `munazara-bot` (veya istediğin bir isim)
3. **Public** seç (Koyeb free tier için gerekli)
4. **Create repository** tıkla

### ADIM 2: Dosyaları GitHub'a Yükle

**Seçenek A: Web arayüzünden (kolay)**
1. Yeni repo sayfasında "uploading an existing file" linkine tıkla
2. Bu klasördeki TÜM dosyaları sürükle-bırak:
   - `bot.py`
   - `app.py`
   - `requirements.txt`
   - `Procfile`
   - `.gitignore`
3. "Commit changes" tıkla

**Seçenek B: Git ile (terminal)**
```bash
# Klasöre git
cd koyeb-deploy

# Git başlat
git init
git add .
git commit -m "Münazara Bot - Koyeb deploy"

# GitHub'a bağla (kendi repo URL'ini yaz)
git remote add origin https://github.com/KULLANICI_ADIN/munazara-bot.git
git branch -M main
git push -u origin main
```

---

### ADIM 3: Koyeb Hesabı Aç

1. **Koyeb'e git:** https://app.koyeb.com/auth/signup
2. **GitHub ile giriş yap** (en kolay yol)
3. Hesap oluştur (kredi kartı GEREKMEZ)

---

### ADIM 4: GitHub'ı Koyeb'e Bağla

1. Koyeb dashboard'da **"Create Web Service"** tıkla
2. **"GitHub"** seç
3. **"Install GitHub App"** tıkla
4. GitHub'da Koyeb'e izin ver
5. Repository'ni seç: `munazara-bot`

---

### ADIM 5: Servis Ayarları

**Builder bölümünde:**
- Builder: **Buildpack** (otomatik seçili)
- Branch: **main**

**Instance bölümünde:**
- Instance type: **Free** (0.1 vCPU, 512MB RAM)

**Environment Variables bölümünde** (ÇOK ÖNEMLİ!):
"Add variable" tıklayarak şunları ekle:

| Key | Value | Type |
|-----|-------|------|
| `TELEGRAM_TOKEN` | Bot tokenin | Secret |
| `GEMINI_API_KEY` | Gemini API key | Secret |
| `OPENROUTER_API_KEY` | OpenRouter API key | Secret |
| `PORT` | `8000` | Plain |

**Ports bölümünde:**
- Port: `8000`
- Protocol: `HTTP`

---

### ADIM 6: Deploy Et

1. **App name:** `munazara-bot` (veya istediğin)
2. **"Deploy"** butonuna tıkla
3. Build işlemini bekle (2-5 dakika)

---

## ✅ KONTROL

Deploy başarılı olduktan sonra:

1. Koyeb dashboard'da **yeşil "Healthy"** yazısını gör
2. URL'e tıkla (örn: `munazara-bot-xxx.koyeb.app`)
3. Sayfada "✅ Münazara Bot Aktif!" yazısını gör
4. Telegram'da botuna `/start` yaz - cevap vermeli!

---

## 🔧 SORUN GİDERME

### Bot cevap vermiyor?
1. Koyeb > Service > Logs'a bak
2. Environment variables doğru mu kontrol et
3. Telegram token'ın geçerli mi?

### Health check failed?
- `app.py` dosyası var mı?
- `Procfile` doğru mu?
- PORT environment variable `8000` mi?

### Build failed?
- `requirements.txt` syntax hatası var mı?
- Python dosyalarında syntax hatası var mı?

---

## 🔄 GÜNCELLEME

Bot kodunu güncellemek için:
1. GitHub'da dosyayı düzenle
2. Commit et
3. Koyeb otomatik olarak yeniden deploy eder (auto-deploy açıksa)

Veya manuel:
- Koyeb > Service > Settings > **"Redeploy"**

---

## 📊 KOYEB FREE TIER LİMİTLERİ

| Özellik | Limit |
|---------|-------|
| Web Service | 1 adet |
| vCPU | 0.1 |
| RAM | 512 MB |
| Bandwidth | 100 GB/ay |
| Build dakika | 1000/ay |

**Bu bot için yeterli!** ✅

---

## 🎉 TAMAMLANDI!

Botun artık 7/24 çalışıyor. Bilgisayarını kapatsan bile bot aktif kalacak!

**URL örneği:** `https://munazara-bot-kullaniciadi-xxx.koyeb.app`
