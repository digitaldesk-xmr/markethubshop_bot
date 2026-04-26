import os
import json
import sqlite3
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from nowpayment import NowPayments

# ==================== CONFIGURAZIONE ====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
NOWPAYMENTS_API_KEY = os.environ.get('NOWPAYMENTS_API_KEY')
ADMIN_CHAT_ID = "IL_TUO_ID_TELEGRAM"  # <-- Inserisci il tuo ID Telegram (es. "123456789")
# ========================================================

np_client = NowPayments(NOWPAYMENTS_API_KEY)

# ==================== DATABASE PER VERCEL (Linux) ====================
DB_PATH = "/tmp/markethub.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordini (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prodotti TEXT,
            totale REAL,
            valuta TEXT,
            stato TEXT,
            data TEXT,
            indirizzo TEXT
        )
    """)
    conn.commit()
    conn.close()

def salva_ordine(user_id, prodotti_id, totale, valuta, indirizzo=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ordini (user_id, prodotti, totale, valuta, stato, data, indirizzo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, json.dumps(prodotti_id), totale, valuta, "in_attesa", datetime.now().isoformat(), indirizzo))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

# ==================== CATALOGO CORSI ====================
CORSI = {
    "1": {
        "nome": "📘 Corso Crypto Base",
        "prezzo": 10,
        "valuta": "EUR",
        "descrizione": "Impara le basi in 7 giorni.\n✅ 5 moduli video\n✅ PDF scaricabile",
        "photo_url": "https://picsum.photos/id/0/500/300"
    },
    "2": {
        "nome": "🎓 Corso Trading Avanzato",
        "prezzo": 50,
        "valuta": "EUR",
        "descrizione": "Diventa un trader professionista.\n✅ 10 ore di video\n✅ Strumenti esclusivi",
        "photo_url": "https://picsum.photos/id/20/500/300"
    }
}

# ==================== PRODOTTI AMAZON ====================
PRODOTTI_AMAZON = {
    "amz_1": {
        "nome": "🎧 Cuffie Wireless Bluetooth",
        "prezzo": "39.99",
        "valuta": "EUR",
        "descrizione": "Cuffie con cancellazione del rumore.\n⭐ 4.5/5 su Amazon",
        "photo_url": "https://picsum.photos/id/1/500/300",
        "affiliate_link": "https://amzn.to/IL_TUO_LINK"
    }
}

# ==================== STATI CONVERSAZIONE ====================
SPEDIZIONE = 1

# ==================== NOTIFICA ADMIN ====================
async def notifica_admin(context, ordine_id, prodotto_nome, totale, indirizzo, username=None):
    if ADMIN_CHAT_ID == "IL_TUO_ID_TELEGRAM":
        print("⚠️ Admin ID non configurato")
        return
    messaggio = (
        f"📦 *NUOVO ORDINE #{ordine_id}*\n\n"
        f"📝 *Prodotto:* {prodotto_nome}\n"
        f"💰 *Totale:* {totale} EUR\n"
        f"🏠 *Indirizzo:* {indirizzo}\n"
        f"👤 *Utente:* @{username if username else 'N/A'}\n\n"
        f"🟢 *Pronto per la spedizione!*"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=messaggio, parse_mode="Markdown")
    except Exception as e:
        print(f"Errore notifica admin: {e}")

# ==================== HANDLER ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 I NOSTRI CORSI", callback_data="sezione_corsi")],
        [InlineKeyboardButton("🛍️ PRODOTTI AMAZON", callback_data="sezione_amazon")]
    ]
    await update.message.reply_text(
        "🟢 *MarketHub* 🟢\n\nScegli una categoria:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_sezione_corsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    for pid, corso in CORSI.items():
        keyboard.append([InlineKeyboardButton(
            f"{corso['nome']} - {corso['prezzo']}{corso['valuta']}",
            callback_data=f"corso_{pid}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="menu")])
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📚 *I nostri corsi*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_sezione_amazon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = []
    for pid, p in PRODOTTI_AMAZON.items():
        keyboard.append([InlineKeyboardButton(
            f"{p['nome']} - {p['prezzo']}{p['valuta']}",
            callback_data=f"amz_{pid}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="menu")])
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🛍️ *Prodotti Amazon consigliati*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_prodotto_amazon(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_id: str):
    query = update.callback_query
    p = PRODOTTI_AMAZON[prod_id]
    await query.answer()
    caption = (
        f"🛍️ *{p['nome']}*\n\n{p['descrizione']}\n\n"
        f"💰 Prezzo: {p['prezzo']} {p['valuta']}\n\n"
        f"🔗 **[ACQUISTA SU AMAZON]({p['affiliate_link']})**"
    )
    kb = [[InlineKeyboardButton("◀️ Torna indietro", callback_data="sezione_amazon")]]
    await query.message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=p["photo_url"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def corso_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, corso_id: str):
    query = update.callback_query
    corso = CORSI[corso_id]
    await query.answer()
    context.user_data['corso_id'] = corso_id
    reply_keyboard = [[KeyboardButton("📍 Condividi posizione", request_location=True)]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    await query.message.reply_text(
        "Per completare l'acquisto, ho bisogno del tuo *indirizzo di spedizione*:\n"
        "(Puoi scriverlo o condividere la posizione)",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    return SPEDIZIONE

async def ricevi_indirizzo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        indirizzo = f"https://maps.google.com/?q={update.message.location.latitude},{update.message.location.longitude}"
    else:
        indirizzo = update.message.text
    
    context.user_data['indirizzo'] = indirizzo
    corso_id = context.user_data.get('corso_id')
    corso = CORSI[corso_id]
    
    ordine_id = salva_ordine(
        user_id=update.effective_user.id,
        prodotti_id=[corso_id],
        totale=corso['prezzo'],
        valuta=corso['valuta'],
        indirizzo=indirizzo
    )
    
    try:
        invoice = np_client.payment.create_invoice(
            price_amount=corso['prezzo'],
            price_currency=corso['valuta']
        )
        payment_link = invoice.get("invoice_url")
        if not payment_link:
            raise Exception("Nessun link")
        
        caption = (
            f"✅ *Ordine #{ordine_id} creato!*\n"
            f"💰 *Totale:* {corso['prezzo']} {corso['valuta']}\n\n"
            f"🔗 **[CLICCA QUI PER PAGARE CON CRIPTO]({payment_link})**\n\n"
            f"_Dopo il pagamento, riceverai conferma direttamente qui su Telegram._"
        )
        
        await update.message.reply_text(
            "Grazie! Procedi con il pagamento:",
            reply_markup=ReplyKeyboardMarkup.remove_keyboard()
        )
        await update.message.reply_photo(
            photo=corso['photo_url'],
            caption=caption,
            parse_mode="Markdown"
        )
        
        await notifica_admin(
            context, ordine_id, corso['nome'], corso['prezzo'],
            indirizzo, update.effective_user.username
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {str(e)[:100]}")
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancella(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=ReplyKeyboardMarkup.remove_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "menu":
        await start(update, context)
    elif data == "sezione_corsi":
        await mostra_sezione_corsi(update, context)
    elif data == "sezione_amazon":
        await mostra_sezione_amazon(update, context)
    elif data.startswith("corso_"):
        corso_id = data.split("_")[1]
        await corso_pagamento(update, context, corso_id)
    elif data.startswith("amz_"):
        prod_id = data.split("_")[1]
        await mostra_prodotto_amazon(update, context, prod_id)

# ==================== INIZIALIZZAZIONE APP ====================
init_db()
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

conv_handler = ConversationHandler(
    entry_points=[],
    states={SPEDIZIONE: [MessageHandler(filters.TEXT | filters.LOCATION, ricevi_indirizzo)]},
    fallbacks=[CommandHandler("cancel", cancella)],
)
application.add_handler(conv_handler)

# ==================== HANDLER PER VERCEL ====================
def handler(event, context):
    try:
        body = json.loads(event['body'])
        update = Update.de_json(body, application.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.process_update(update))
        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}
    except Exception as e:
        print(f"Errore: {e}")
        return {'statusCode': 500, 'body': json.dumps({'status': 'error', 'message': str(e)})}
