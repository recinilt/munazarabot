# -*- coding: utf-8 -*-
"""
Münazara GPT v2 - Grup Münazara Botu
- Yeni google-genai SDK
- Fallback: Gemini → OpenRouter DeepSeek
- Grup desteği (@mention ile çalışır)
- Instructions v6.1 akışı
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Telegram
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatType

# Yeni Google GenAI SDK
from google import genai
from google.genai import types

# OpenRouter (OpenAI uyumlu)
from openai import OpenAI

load_dotenv()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# YAPILANDIRMA
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Bot username (runtime'da alınacak)
BOT_USERNAME = None

# ============================================
# MÜNAZARA OTURUMU
# ============================================

@dataclass
class MunazaraSession:
    """Bir grup için münazara oturumu"""
    state: str = "IDLE"  # IDLE, SETUP, DISCUSSING
    setup_step: int = 0
    
    # Ayarlar
    user_position: str = ""
    bot_position: str = ""
    severity: str = "🟡Orta"
    style: str = "Diyalektik"
    topic: str = ""
    
    # Tartışma durumu
    current_point: int = 0
    turn_count: int = 0
    points_won: list = field(default_factory=list)
    points_lost: list = field(default_factory=list)
    points_pending: list = field(default_factory=list)
    
    # Sohbet geçmişi
    chat_history: list = field(default_factory=list)
    
    # Web araştırma sonucu (kullanıcıya gösterilmez)
    research_notes: str = ""

# Grup oturumları: {chat_id: MunazaraSession}
sessions: Dict[int, MunazaraSession] = {}

# ============================================
# SETUP SORULARI
# ============================================

SETUP_QUESTIONS = [
    """🎭 **Münazara GPT'ye Hoş Geldiniz!**

Başlamadan önce ayarları yapalım.

**1️⃣ Siz kimsiniz?** (Savunacağınız pozisyon)

Sünni Müslüman / Şii Müslüman / Tasavvuf ehli / Deist / Agnostik / Ateist / Filozof / Diğer

_Cevabınızı yazın..._""",

    """**2️⃣ Ben hangi pozisyondan saldırayım?**

Sünni Müslüman / Selefî / Şii / Ateist / Agnostik / Materyalist filozof / Analitik felsefeci / Diğer

_Cevabınızı yazın..._""",

    """**3️⃣ Sertlik seviyesi:**

🟢 Hafif - Nazik, soru ağırlıklı
🟡 Orta - Direkt, iddia+soru dengeli  
🔴 Sert - Keskin, kaçışa sıfır tolerans
⚫ Vahşi - Acımasız, merhamet yok

_Emoji veya isim yazın..._""",

    """**4️⃣ Tartışma stili:**

**Sokratik** - Sadece soru, tuzak kuran
**Diyalektik** - İddia + soru karışık

_Birini seçin..._""",

    """**5️⃣ Konu:**

Din / Felsefe / Tasavvuf / Siyaset / Ekonomi / Bilim / Diğer

_Konuyu yazın veya spesifik bir tez belirtin..._"""
]

# ============================================
# SİSTEM PROMPTU (Instructions v6.1)
# ============================================

def get_system_prompt(session: MunazaraSession) -> str:
    """Oturuma göre sistem promptu oluştur"""
    
    return f"""# 🔥 MÜNAZARA GPT - RAKİP MODU

## KİMLİĞİN
Sen yardımcı değil, RAKİPSİN. Kullanıcının iddiasını çürütmek için kendi rolünün inançlarını SİLAH olarak kullanırsın.

## ROLLER
- KULLANICI: {session.user_position} (savunuyor)
- SEN: {session.bot_position} (saldırıyor)

## AYARLAR
- Sertlik: {session.severity}
- Stil: {session.style}
- Konu: {session.topic}

## ARAŞTIRMA NOTLARIN (KULLANICIYA GÖSTERME)
{session.research_notes}

## SALDIRI FORMATI (HER TURDA)
1. Mini anlama kontrolü (1 cümle): "Şunu diyorsun: [özetle]. Doğru mu?"
2. Karşı iddia (kendi rolünden): "[Rolüm]'a göre [temel inanç]. Seninle çelişiyor çünkü [sebep]."
3. Çürütücü soru: "Bu durumda [spesifik soru]?"

## ISRAR KURALI
Aynı noktada şunlardan biri olana kadar KAL:
A) Kullanıcı: "Haklısın" / "Geçelim" → Geç, yeni noktaya saldır
B) Sen çürütemezsin → "Tutarsızlık bulamadım. Argümanın tutarlı. Geçiyorum."
C) 5 tur geçti → "Kilitlendik. Askıya alıp geçiyorum."

## KAÇIŞ TESPİTİ
| Kaçış | Tepki |
|-------|-------|
| Konu değiştirme | "Dur. Soruma cevap vermedin. Tekrar: [soru]" |
| "Allah bilir" | "Bu kaçış. Spesifik cevap ver: [soru]" |
| "X öyle demiş" | "O beni bağlamaz. SEN savunuyorsun. SEN açıkla." |
| Geçiştirme | "Hayır. Cevapla veya 'haklısın' de." |

## SERTLİK: {session.severity}
{"🟢Hafif: Nazik dil, soru ağırlıklı" if "Hafif" in session.severity else ""}
{"🟡Orta: Direkt dil, iddia+soru dengeli" if "Orta" in session.severity else ""}
{"🔴Sert: Keskin dil, kaçışa sıfır tolerans" if "Sert" in session.severity else ""}
{"⚫Vahşi: Acımasız, reductio ad absurdum, merhamet yok" if "Vahşi" in session.severity else ""}

## STİL: {session.style}
{"Sokratik: Karşı iddia YOK. Sadece tek soru ama tuzak kuran." if "Sokratik" in session.style else "Diyalektik: İddia + soru karışık."}

## TUR SONU
Her itirazın altına şunu ekle:
"1️⃣ Pes ettim | 2️⃣ Benim yerime cevap ver | 3️⃣ Geç"

## YASAKLAR
❌ Uzun paragraf ❌ Liste (zorunlu değilse) ❌ "Her iki taraf da haklı" ❌ Empati ❌ Akademik anlatım

## SINIRLAR
- Max 150 kelime/mesaj
- Günlük Türkçe
- Bir cümlede tek fikir
- Türkçe karakterler: ğüşıöçĞÜŞİÖÇ"""

# ============================================
# RATE LIMIT TRACKER
# ============================================

class RateLimitTracker:
    def __init__(self):
        self.requests_this_minute = 0
        self.requests_today = 0
        self.minute_reset = datetime.now()
        self.day_reset = datetime.now()
        self.blocked_until: Optional[datetime] = None
    
    def can_use_gemini(self) -> bool:
        now = datetime.now()
        
        if self.blocked_until and now < self.blocked_until:
            return False
        
        if now - self.minute_reset > timedelta(minutes=1):
            self.requests_this_minute = 0
            self.minute_reset = now
        
        if now - self.day_reset > timedelta(days=1):
            self.requests_today = 0
            self.day_reset = now
        
        # Limitler: 5 RPM, 250 RPD
        return self.requests_this_minute < 4 and self.requests_today < 240
    
    def record_request(self):
        self.requests_this_minute += 1
        self.requests_today += 1
    
    def block(self, seconds: int = 60):
        self.blocked_until = datetime.now() + timedelta(seconds=seconds)

rate_tracker = RateLimitTracker()

# ============================================
# GEMINI İSTEMCİSİ (YENİ SDK)
# ============================================

gemini_client = None

def setup_gemini():
    """Yeni google-genai SDK ile Gemini kurulumu"""
    global gemini_client
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY bulunamadı!")
        return None
    
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Gemini client oluşturuldu (yeni SDK)")
        return gemini_client
    except Exception as e:
        logger.error(f"Gemini kurulum hatası: {e}")
        return None

async def ask_gemini(system_prompt: str, user_message: str, chat_history: list) -> Tuple[Optional[str], bool]:
    """Gemini'ye sor (yeni SDK)"""
    if not gemini_client or not rate_tracker.can_use_gemini():
        return None, False
    
    try:
        # Mesaj geçmişini oluştur
        contents = []
        
        for msg in chat_history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            ))
        
        # Son kullanıcı mesajını ekle
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        ))
        
        # API çağrısı
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=500
            )
        )
        
        rate_tracker.record_request()
        return response.text, True
    
    except Exception as e:
        error_str = str(e).lower()
        if "429" in str(e) or "resource_exhausted" in error_str or "quota" in error_str:
            logger.warning(f"Gemini rate limit: {e}")
            rate_tracker.block(60)
            return None, False
        
        logger.error(f"Gemini hatası: {e}")
        return None, False

# ============================================
# OPENROUTER İSTEMCİSİ (YEDEK)
# ============================================

openrouter_client = None

def setup_openrouter():
    """OpenRouter kurulumu"""
    global openrouter_client
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY bulunamadı!")
        return None
    
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": "https://github.com/munazara-bot",
            "X-Title": "Munazara GPT Bot"
        }
    )
    return openrouter_client

async def ask_openrouter(system_prompt: str, user_message: str, chat_history: list) -> Tuple[Optional[str], bool]:
    """OpenRouter (DeepSeek R1) ile sor"""
    if not openrouter_client:
        return None, False
    
    try:
        messages = [{"role": "system", "content": system_prompt}]
        
        for msg in chat_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        messages.append({"role": "user", "content": user_message})
        
        response = openrouter_client.chat.completions.create(
            model="deepseek/deepseek-r1-0528:free",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content, True
    
    except Exception as e:
        logger.error(f"OpenRouter hatası: {e}")
        return None, False

# ============================================
# FALLBACK SİSTEMİ
# ============================================

async def get_ai_response(session: MunazaraSession, user_message: str) -> Tuple[str, str]:
    """Fallback sistemli AI cevabı"""
    
    system_prompt = get_system_prompt(session)
    
    # 1. Gemini dene
    response, success = await ask_gemini(system_prompt, user_message, session.chat_history)
    if success and response:
        return response, "Gemini"
    
    # 2. OpenRouter dene
    logger.info("Gemini başarısız, OpenRouter'a geçiliyor...")
    response, success = await ask_openrouter(system_prompt, user_message, session.chat_history)
    if success and response:
        return response, "DeepSeek"
    
    return "⚠️ Şu anda yanıt veremiyorum. Lütfen biraz sonra tekrar deneyin.", "Yok"

# ============================================
# WEB ARAŞTIRMASI (Ayarlar sonrası)
# ============================================

async def do_research(session: MunazaraSession) -> str:
    """Pozisyonlar hakkında web araştırması yap"""
    
    research_prompt = f"""Şu iki pozisyon arasındaki temel farkları ve tartışma noktalarını kısaca özetle:
    
Pozisyon 1: {session.user_position}
Pozisyon 2: {session.bot_position}
Konu: {session.topic}

Şunları listele (kısa):
1. Pozisyon 1'in temel inançları (3 madde)
2. Pozisyon 2'nin temel inançları (3 madde)  
3. Ana çelişki/tartışma noktaları (3 madde)
4. Saldırı için kullanılabilecek zayıf noktalar (3 madde)

Türkçe yaz, kısa tut."""

    # Basit araştırma (system prompt olmadan)
    try:
        if gemini_client and rate_tracker.can_use_gemini():
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=research_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=800
                )
            )
            rate_tracker.record_request()
            return response.text
    except Exception as e:
        logger.warning(f"Araştırma hatası: {e}")
    
    return "Araştırma yapılamadı, genel bilgilerle devam ediliyor."

# ============================================
# TELEGRAM HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start komutu"""
    chat_type = update.effective_chat.type
    
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        msg = f"""🎭 **Münazara GPT - Grup Modu**

Bu bot grupla münazara yapar. Tüm grup üyeleri = bir taraf, bot = karşı taraf.

**Komutlar:**
/munazara - Yeni münazara başlat
/bitir - Münazarayı bitir ve özet al
/durum - Mevcut oturum durumu
/sifirla - Oturumu sıfırla

**Kullanım:**
Münazara başladıktan sonra @{BOT_USERNAME} yazarak botu etiketleyin.

_Örnek: @{BOT_USERNAME} Allah'ın varlığı mantıksal zorunluluktur_"""
    else:
        msg = """🎭 **Münazara GPT**

Bu bot seninle münazara yapar. Sen bir taraf, bot karşı taraf.

/munazara yazarak başla!"""
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def munazara_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/munazara - Yeni münazara başlat"""
    chat_id = update.effective_chat.id
    
    # Yeni oturum oluştur
    sessions[chat_id] = MunazaraSession(state="SETUP", setup_step=0)
    
    # İlk soruyu gönder
    await update.message.reply_text(SETUP_QUESTIONS[0], parse_mode="Markdown")

async def bitir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/bitir - Münazarayı bitir"""
    chat_id = update.effective_chat.id
    session = sessions.get(chat_id)
    
    if not session or session.state == "IDLE":
        await update.message.reply_text("❌ Aktif münazara yok.")
        return
    
    # Özet oluştur
    summary = f"""📊 **MÜNAZARA ÖZETİ**

**Pozisyonlar:**
👤 Siz: {session.user_position}
🤖 Ben: {session.bot_position}

**Ayarlar:**
Sertlik: {session.severity}
Stil: {session.style}
Konu: {session.topic}

**Sonuçlar:**
✅ Çürütülen noktalar: {len(session.points_won)}
{chr(10).join(['• ' + p for p in session.points_won]) if session.points_won else '• Yok'}

❌ Savunulan noktalar: {len(session.points_lost)}
{chr(10).join(['• ' + p for p in session.points_lost]) if session.points_lost else '• Yok'}

⏸️ Askıdaki noktalar: {len(session.points_pending)}
{chr(10).join(['• ' + p for p in session.points_pending]) if session.points_pending else '• Yok'}

**Toplam tur:** {session.turn_count}

_Münazara sonlandırıldı. Yeni münazara için /munazara yazın._"""
    
    # Oturumu sıfırla
    sessions[chat_id] = MunazaraSession()
    
    await update.message.reply_text(summary, parse_mode="Markdown")

async def durum_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/durum - Oturum durumu"""
    chat_id = update.effective_chat.id
    session = sessions.get(chat_id)
    
    if not session or session.state == "IDLE":
        await update.message.reply_text("❌ Aktif münazara yok. /munazara ile başlat.")
        return
    
    gemini_status = "✅" if rate_tracker.can_use_gemini() else "⏳ Limit"
    
    msg = f"""📊 **Oturum Durumu**

**Durum:** {session.state}
**Pozisyonlar:** {session.user_position} vs {session.bot_position}
**Sertlik:** {session.severity}
**Stil:** {session.style}
**Konu:** {session.topic}

**İstatistikler:**
• Tur: {session.turn_count}
• Kazanılan: {len(session.points_won)}
• Kaybedilen: {len(session.points_lost)}
• Askıda: {len(session.points_pending)}

**API Durumu:**
Gemini: {gemini_status} ({rate_tracker.requests_today}/250 günlük)
OpenRouter: ✅ Yedek hazır"""
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def sifirla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/sifirla - Oturumu sıfırla"""
    chat_id = update.effective_chat.id
    sessions[chat_id] = MunazaraSession()
    await update.message.reply_text("🔄 Oturum sıfırlandı. /munazara ile yeniden başlayabilirsiniz.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mesaj işleyici"""
    if not update.message or not update.message.text:
        return
    
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    message_text = update.message.text
    user_name = update.effective_user.first_name or "Kullanıcı"
    
    # Oturum al veya oluştur
    if chat_id not in sessions:
        sessions[chat_id] = MunazaraSession()
    
    session = sessions[chat_id]
    
    # GRUP: Sadece @mention veya reply ile çalış
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        is_mentioned = BOT_USERNAME and f"@{BOT_USERNAME.lower()}" in message_text.lower()
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user and
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        
        # SETUP modunda her mesajı al
        if session.state != "SETUP" and not is_mentioned and not is_reply_to_bot:
            return
        
        # @mention'ı mesajdan çıkar
        if BOT_USERNAME:
            message_text = message_text.replace(f"@{BOT_USERNAME}", "").strip()
    
    # IDLE durumunda
    if session.state == "IDLE":
        if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await update.message.reply_text(
                "❌ Aktif münazara yok. /munazara ile başlatın.",
                reply_to_message_id=update.message.message_id
            )
        return
    
    # SETUP durumunda - ayarları topla
    if session.state == "SETUP":
        await handle_setup(update, context, session, message_text)
        return
    
    # DISCUSSING durumunda - münazara
    if session.state == "DISCUSSING":
        await handle_discussion(update, context, session, message_text, user_name)
        return

async def handle_setup(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MunazaraSession, message_text: str):
    """Setup adımlarını işle"""
    chat_id = update.effective_chat.id
    step = session.setup_step
    
    # Cevabı kaydet
    if step == 0:
        session.user_position = message_text
    elif step == 1:
        session.bot_position = message_text
    elif step == 2:
        # Sertlik seviyesi
        text_lower = message_text.lower()
        if "hafif" in text_lower or "🟢" in message_text:
            session.severity = "🟢Hafif"
        elif "vahşi" in text_lower or "⚫" in message_text:
            session.severity = "⚫Vahşi"
        elif "sert" in text_lower or "🔴" in message_text:
            session.severity = "🔴Sert"
        else:
            session.severity = "🟡Orta"
    elif step == 3:
        # Stil
        if "sokratik" in message_text.lower():
            session.style = "Sokratik"
        else:
            session.style = "Diyalektik"
    elif step == 4:
        session.topic = message_text
    
    # Sonraki adıma geç
    session.setup_step += 1
    
    if session.setup_step < len(SETUP_QUESTIONS):
        # Sonraki soruyu sor
        await update.message.reply_text(
            SETUP_QUESTIONS[session.setup_step], 
            parse_mode="Markdown"
        )
    else:
        # Setup tamamlandı - araştırma yap
        await update.message.reply_text("⏳ Ayarlar kaydedildi. Araştırma yapılıyor...")
        
        # Web araştırması
        session.research_notes = await do_research(session)
        
        # Tartışma moduna geç
        session.state = "DISCUSSING"
        
        bot_mention = f"@{BOT_USERNAME}" if BOT_USERNAME else "botu etiketleyerek"
        
        ready_msg = f"""✅ **Münazara Hazır!**

**Pozisyonlar:**
👤 Siz: {session.user_position}
🤖 Ben: {session.bot_position}

**Ayarlar:**
Sertlik: {session.severity}
Stil: {session.style}
Konu: {session.topic}

⚠️ **KURAL:** Bir çürütmemi geçmem için "haklısın" demeniz gerekir.

🎯 Şimdi ilk iddianızı söyleyin! ({bot_mention} ile başlayın)"""
        
        await update.message.reply_text(ready_msg, parse_mode="Markdown")

async def handle_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE, session: MunazaraSession, message_text: str, user_name: str):
    """Tartışma mesajlarını işle"""
    
    # Özel komutları kontrol et
    text_lower = message_text.lower().strip()
    
    # "haklısın" tespiti
    if any(phrase in text_lower for phrase in ["haklısın", "haklısin", "pes", "1️⃣"]):
        # Nokta kazanıldı
        if session.chat_history:
            last_point = session.chat_history[-1].get("content", "")[:50] + "..."
            session.points_won.append(last_point)
        
        session.turn_count = 0
        await update.message.reply_text(
            "✅ Bu noktayı geçiyorum. Başka açıdan saldırıyorum.\n\nYeni iddianızı söyleyin.",
            reply_to_message_id=update.message.message_id
        )
        return
    
    # "geç" tespiti
    if any(phrase in text_lower for phrase in ["geç", "geçelim", "3️⃣"]):
        if session.chat_history:
            last_point = session.chat_history[-1].get("content", "")[:50] + "..."
            session.points_pending.append(last_point)
        
        session.turn_count = 0
        await update.message.reply_text(
            "⏸️ Askıya aldım, çözülmedi, not ettim. Başka noktaya geçiyorum.\n\nYeni iddianızı söyleyin.",
            reply_to_message_id=update.message.message_id
        )
        return
    
    # "2️⃣ cevap ver" tespiti
    if "2️⃣" in message_text or "cevap ver" in text_lower:
        message_text = "Benim yerime cevap ver ve devam et."
    
    # Yazıyor göster
    await update.message.chat.send_action("typing")
    
    # Geçmişe kullanıcı mesajını ekle
    session.chat_history.append({"role": "user", "content": f"[{user_name}]: {message_text}"})
    
    # AI cevabı al
    response, model_used = await get_ai_response(session, message_text)
    
    # Geçmişe bot cevabını ekle
    session.chat_history.append({"role": "assistant", "content": response})
    
    # Tur sayacı
    session.turn_count += 1
    
    # 5 tur kontrolü
    if session.turn_count >= 5:
        response += "\n\n⚠️ _5 tur oldu. Kilitlendik mi? 'geç' yazabilirsiniz._"
    
    # Cevabı gönder
    footer = f"\n\n_[{model_used}]_"
    
    try:
        await update.message.reply_text(
            response + footer, 
            parse_mode="Markdown",
            reply_to_message_id=update.message.message_id
        )
    except:
        await update.message.reply_text(
            response + f"\n\n[{model_used}]",
            reply_to_message_id=update.message.message_id
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hata yakalayıcı"""
    logger.error(f"Hata: {context.error}")

# ============================================
# ANA FONKSİYON
# ============================================

def main():
    """Bot'u başlat"""
    global BOT_USERNAME
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN bulunamadı!")
        return
    
    # API'leri kur
    setup_gemini()
    setup_openrouter()
    
    # Uygulama oluştur
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Bot username'i al
    async def post_init(application: Application):
        global BOT_USERNAME
        bot_info = await application.bot.get_me()
        BOT_USERNAME = bot_info.username
        logger.info(f"Bot username: @{BOT_USERNAME}")
    
    app.post_init = post_init
    
    # Handler'ları ekle
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("munazara", munazara_command))
    app.add_handler(CommandHandler("bitir", bitir_command))
    app.add_handler(CommandHandler("durum", durum_command))
    app.add_handler(CommandHandler("sifirla", sifirla_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.add_error_handler(error_handler)
    
    # Başlat
    logger.info("🎭 Münazara GPT v2 başlatılıyor...")
    logger.info(f"Gemini: {'✅' if gemini_client else '❌'}")
    logger.info(f"OpenRouter: {'✅' if openrouter_client else '❌'}")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
