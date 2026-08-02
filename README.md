# Tempo.Spor Transfer Haberi Filtre Botu

RSS + anahtar kelime filtreleme ile çalışan, tamamen ücretsiz bir Telegram
bildirim botu. AI/API çağrısı kullanmaz.

## Nasıl çalışır?
1. GitHub Actions, `transfer_bot.py` scriptini her 10 dakikada bir çalıştırır.
2. Script; Fenerbahçe, Galatasaray, Beşiktaş, Trabzonspor, Real Madrid,
   Barcelona ve genel Transfer Merkezi RSS feed'lerini okur. Bayern Münih
   haberleri için "Avrupa'dan Futbol" feed'i başlıkta "Bayern" geçip
   geçmediğine göre süzülür.
3. Başlık/özet içinde "resmi açıklama", "imzaladı", "anlaştı", "flaş
   gelişme" gibi transfer/breaking-news niteliğindeki kelimelerden biri
   varsa, haber Telegram'a gönderilir.
4. Daha önce gönderilen haberler `sent_links.json` dosyasında tutulur,
   tekrar gönderilmez. Bu dosya her çalıştırmadan sonra otomatik commit
   edilir.

## Kurulum

### 1. Telegram bot oluşturun (henüz yoksa)
- Telegram'da [@BotFather](https://t.me/BotFather) ile konuşun
- `/newbot` komutu ile yeni bot oluşturun, size verdiği **token**'ı not edin

### 2. Chat ID'nizi öğrenin
- Botunuza Telegram'dan bir mesaj atın (örn. "merhaba")
- Tarayıcıda şu adrese gidin (TOKEN'ı kendi tokenınızla değiştirin):
  `https://api.telegram.org/botTOKEN/getUpdates`
- Dönen JSON içinde `"chat":{"id": ...}` kısmındaki sayıyı not edin
  (bu sizin chat ID'niz)

### 3. Bu klasörü GitHub'a yükleyin
- GitHub'da yeni bir repo oluşturun (private olabilir)
- Bu klasördeki dosyaları o repoya push edin:
  ```
  git init
  git add .
  git commit -m "İlk kurulum"
  git branch -M main
  git remote add origin <repo-url>
  git push -u origin main
  ```

### 4. Secrets'ları ekleyin
- Repo sayfasında: **Settings → Secrets and variables → Actions → New repository secret**
- İki secret ekleyin:
  - `TELEGRAM_BOT_TOKEN` → BotFather'dan aldığınız token
  - `TELEGRAM_CHAT_ID` → 2. adımda bulduğunuz chat ID

### 5. Test edin
- Repo sayfasında **Actions** sekmesine gidin
- "Transfer Haberi Filtre Botu" workflow'unu seçip **Run workflow**
  butonuna tıklayın (manuel tetikleme)
- Loglardan çalışıp çalışmadığını kontrol edin

Kurulumdan sonra bot otomatik olarak her 10 dakikada bir çalışacak ve
yeni bir "breaking" transfer haberi bulduğunda Telegram'a mesaj atacaktır.

## Ayarları değiştirmek isterseniz
`transfer_bot.py` dosyasının başındaki şu kısımları düzenleyebilirsiniz:
- `RSS_FEEDS` — takip edilen takım/kaynak listesi
- `BREAKING_KEYWORDS` — hangi kelimeler "breaking news" sayılsın
- Workflow dosyasındaki `cron: "*/10 * * * *"` — kontrol sıklığı
  (örn. her 5 dakikada bir için `*/5 * * * *`)

## Maliyet
$0. RSS okuma, Telegram Bot API ve GitHub Actions'ın ücretsiz kotası
(public repo'da sınırsız, private repo'da ayda 2000 dakika) bu iş yükü
için fazlasıyla yeterli.
