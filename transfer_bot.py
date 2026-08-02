#!/usr/bin/env python3
"""
Tempo.Spor Transfer Haberi Filtre Botu
----------------------------------------
RSS feed'lerinden Türk takımları (Fenerbahçe, Galatasaray, Beşiktaş,
Trabzonspor) ve yabancı dev kulüpler (Bayern Münih, Real Madrid,
Barcelona) haberlerini çeker, "breaking news" niteliğindeki transfer
haberlerini anahtar kelimeyle filtreler ve Telegram'a gönderir.

Maliyet: $0 — sadece RSS + Telegram Bot API kullanılıyor, AI çağrısı yok.
Çalışma şekli: GitHub Actions üzerinde cron ile periyodik çalıştırılır.
Tekrarlayan bildirim göndermemek için gönderilen haber linkleri
sent_links.json dosyasında saklanır (workflow bunu commit'ler).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------------------

# Takip edilecek RSS feed'leri: (etiket, url)
RSS_FEEDS = [
    ("Fenerbahçe", "https://www.fotomac.com.tr/rss/fenerbahce.xml"),
    ("Galatasaray", "https://www.fotomac.com.tr/rss/galatasaray.xml"),
    ("Beşiktaş", "https://www.fotomac.com.tr/rss/besiktas.xml"),
    ("Trabzonspor", "https://www.fotomac.com.tr/rss/trabzonspor.xml"),
    ("Real Madrid", "https://www.fotomac.com.tr/rss/realmadrid.xml"),
    ("Barcelona", "https://www.fotomac.com.tr/rss/barcelona.xml"),
    ("Transfer Merkezi", "https://www.fotomac.com.tr/rss/transfer.xml"),
    # Bayern Münih için ayrı feed yok; Avrupa futbolu genelinden
    # başlıkta "Bayern" geçenleri BAYERN_KEYWORDS ile ayrıca süzüyoruz.
    ("Avrupa'dan Futbol", "https://www.fotomac.com.tr/rss/avrupadanfutbol.xml"),
]

# Bu kulüpler ana feed'leri olmadığı için başlıkta aranacak isimler
EXTRA_CLUB_KEYWORDS = {
    "Bayern Münih": ["bayern münih", "bayern munih", "fc bayern", "bayern'de", "bayern'in"],
}

# "Breaking news" / transfer niteliğindeki haber olduğunu gösteren kelimeler.
# Başlık bu kelimelerden en az birini içermiyorsa haber atlanır.
BREAKING_KEYWORDS = [
    "resmi açıklama", "resmi olarak", "resmen", "kap açıklaması",
    "imzaladı", "imza attı", "imza töreni", "anlaştı", "anlaşma sağlandı",
    "transfer oldu", "kadrosuna kattı", "renklerine katıldı",
    "ayrılık", "veda etti", "yollarını ayırdı", "sözleşmesini feshetti",
    "flaş gelişme", "son dakika", "bomba transfer", "resmi teklif",
    "görüşmeler başladı", "el sıkıştı",
]

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

STATE_FILE = Path(__file__).parent / "sent_links.json"
MAX_STORED_LINKS = 500  # dosyanın sonsuza kadar büyümesini önlemek için


# ---------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------------------------

def fetch_rss(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_items(xml_text: str):
    """RSS XML'inden (title, link, description) listesi çıkarır."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        title = (title_el.text or "").strip() if title_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        desc = (desc_el.text or "").strip() if desc_el is not None else ""
        if title and link:
            items.append((title, link, desc))
    return items


def matches_breaking(title: str, desc: str) -> bool:
    text = f"{title} {desc}".lower()
    return any(keyword in text for keyword in BREAKING_KEYWORDS)


def matches_extra_club(title: str, desc: str):
    text = f"{title} {desc}".lower()
    for club, keywords in EXTRA_CLUB_KEYWORDS.items():
        if any(k in text for k in keywords):
            return club
    return None


def load_sent_links() -> set:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def save_sent_links(links: set):
    # sadece son N linki tut
    trimmed = list(links)[-MAX_STORED_LINKS:]
    STATE_FILE.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("HATA: TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID tanımlı değil.", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}", file=sys.stderr)
        return False


def format_message(club_label: str, title: str, link: str) -> str:
    return (
        f"🚨 <b>{club_label}</b>\n\n"
        f"{title}\n\n"
        f"🔗 {link}"
    )


# ---------------------------------------------------------------------------
# ANA AKIŞ
# ---------------------------------------------------------------------------

def main():
    sent_links = load_sent_links()
    new_sent = set(sent_links)
    found_count = 0

    for label, feed_url in RSS_FEEDS:
        try:
            xml_text = fetch_rss(feed_url)
        except Exception as e:
            print(f"[{label}] feed alınamadı: {e}", file=sys.stderr)
            continue

        items = parse_items(xml_text)

        for title, link, desc in items:
            if link in sent_links:
                continue

            club_label = label
            extra_club = matches_extra_club(title, desc)
            if extra_club:
                club_label = extra_club
            elif label == "Avrupa'dan Futbol":
                # Genel Avrupa feed'inde sadece takip edilen kulüpler dışındaki
                # haberleri atla (Bayern dışında burada özel takip yok)
                continue

            if not matches_breaking(title, desc):
                continue

            message = format_message(club_label, title, link)
            ok = send_telegram_message(message)
            if ok:
                print(f"Gönderildi [{club_label}]: {title}")
                new_sent.add(link)
                found_count += 1
            else:
                print(f"Gönderilemedi [{club_label}]: {title}", file=sys.stderr)

    save_sent_links(new_sent)
    print(f"Toplam yeni bildirim: {found_count}")


if __name__ == "__main__":
    main()
