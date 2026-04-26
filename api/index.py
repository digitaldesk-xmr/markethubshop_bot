import os
import json
import sqlite3
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from nowpayment import NowPayments

# ==================== CONFIGURAZIONE ====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
NOWPAYMENTS_API_KEY = os.environ.get('NOWPAYMENTS_API_KEY')
# ========================================================

np_client = NowPayments(NOWPAYMENTS_API_KEY)

# ==================== CATALOGO CORSI (pagamento crypto) ====================
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

# ==================== PRODOTTI AMAZON AFFILIAZIONE ====================
PRODOTTI_AMAZON = {
    "amz_1": {
        "nome": "🎧 Cuffie Wireless Bluetooth",
        "prezzo": "39.99",
        "valuta": "EUR",
        "descrizione": "Cuffie con cancellazione del rumore, 30h di autonomia.\n⭐ 4.5/5 su Amazon",
        "photo_url": "https://picsum.photos/id/1/500/300",
        "affiliate_link": "https://amzn.to/IL_TUO_LINK_AFFILIATO_1"
    },
    "amz_2": {
        "nome": "⌚ Smartwatch Fitness Tracker",
        "prezzo": "89.99",
        "valuta": "EUR",
        "descrizione": "Monitoraggio battito cardiaco, GPS, resistente all'acqua.\n⭐ 4.7/5 su Amazon",
        "photo_url": "https://picsum.photos/id/2/500/300",
        "affiliate_link": "https://amzn.to/IL_TUO_LINK_AFFILIATO_2"
    },
    "amz_3": {
        "nome": "🔋 Power Bank 20000mAh",
        "prezzo": "29.99",
        "valuta": "EUR",
        "descrizione": "Ricarica rapida, 3 porte USB, display digitale.\n⭐ 4.6/5 su Amazon",
        "photo_url": "https://picsum.photos/id/3/500/300",
        "affiliate_link": "https://amzn.to/IL_TUO_LINK_AFFILIATO_3"
    }
}
# ============================================================

def salva_ordine(user_id, prodotti_id, totale, valuta):
    conn = sqlite3.connect("/tmp/markethub.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordini (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prodotti TEXT,
            totale REAL,
            valuta TEXT,
            stato TEXT,
            data TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO ordini (user_id, prodotti, totale, valuta, stato, data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, json.dumps(prodotti_id), totale, valuta, "in_attesa", datetime.now().isoformat()))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra il catalogo con due sezioni"""
    keyboard = [
        [InlineKeyboardButton("📚 I NOSTRI CORSI", callback_data="sezione_corsi")],
        [InlineKeyboardButton("🛍️ PRODOTTI AMAZON", callback_data="sezione_amazon")]
    ]
    
    await update.message.reply_text(
        "🟢 *MarketHub* 🟢\n\n"
        "Benvenuto nel nostro negozio.\n"
        "Scegli una categoria:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_sezione_corsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra la lista dei corsi"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for pid, corso in CORSI.items():
        keyboard.append([InlineKeyboardButton(
            f"{corso['nome']} - {corso['prezzo']}{corso['valuta']}",
            callback_data=f"corso_{pid}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Torna al menu principale", callback_data="menu")])
    
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📚 *I nostri corsi*\n\nScegli un corso:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_sezione_amazon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra la lista dei prodotti Amazon"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for pid, prodotto in PRODOTTI_AMAZON.items():
        keyboard.append([InlineKeyboardButton(
            f"{prodotto['nome']} - {prodotto['prezzo']}{prodotto['valuta']}",
            callback_data=f"amz_{pid}"
        )])
    keyboard.append([InlineKeyboardButton("◀️ Torna al menu principale", callback_data="menu")])
    
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🛍️ *Prodotti Amazon consigliati*\n\nScegli un prodotto:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_corso(update: Update, context: ContextTypes.DEFAULT_TYPE, corso_id: str):
    """Mostra il corso e genera pagamento crypto"""
    query = update.callback_query
    corso = CORSI[corso_id]
    await query.answer()
    
    await query.edit_message_text(
        f"⏳ *Generazione pagamento per {corso['nome']}...*",
        parse_mode="Markdown"
    )
    
    try:
        invoice = np_client.payment.create_invoice(
            price_amount=corso["prezzo"],
            price_currency=corso["valuta"]
        )
        payment_link = invoice.get("invoice_url")
        if not payment_link:
            raise Exception("Nessun link di pagamento")
        
        ordine_id = salva_ordine(
            user_id=update.effective_user.id,
            prodotti_id=[corso_id],
            totale=corso["prezzo"],
            valuta=corso["valuta"]
        )
        
        caption = (
            f"✅ *Ordine #{ordine_id} creato!*\n"
            f"💰 *Totale:* {corso['prezzo']} {corso['valuta']}\n\n"
            f"🔗 **[CLICCA QUI PER PAGARE CON CRIPTO]({payment_link})**\n\n"
            f"📌 *Supporta:* Bitcoin, Monero (XMR), USDT, Ethereum e 100+ altre crypto\n\n"
            f"_Dopo il pagamento, riceverai il corso via email._"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Torna ai corsi", callback_data="sezione_corsi")]]
        
        await query.message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=corso["photo_url"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ *Errore*: {str(e)[:100]}\nRiprova più tardi.",
            parse_mode="Markdown"
        )

async def mostra_prodotto_amazon(update: Update, context: ContextTypes.DEFAULT_TYPE, prodotto_id: str):
    """Mostra il prodotto Amazon con link affiliato diretto"""
    query = update.callback_query
    prodotto = PRODOTTI_AMAZON[prodotto_id]
    await query.answer()
    
    caption = (
        f"🛍️ *{prodotto['nome']}*\n\n"
        f"{prodotto['descrizione']}\n\n"
        f"💰 *Prezzo:* {prodotto['prezzo']} {prodotto['valuta']}\n"
        f"🏪 *Venduto da:* Amazon\n\n"
        f"🔗 **[ACQUISTA SU AMAZON]({prodotto['affiliate_link']})**\n\n"
        f"_Quando acquisti tramite questo link, supporti il nostro progetto con una piccola commissione (senza costi aggiuntivi per te)._"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Torna ai prodotti Amazon", callback_data="sezione_amazon")]]
    
    await query.message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=prodotto["photo_url"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce tutti i callback dei pulsanti"""
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
        await mostra_corso(update, context, corso_id)
    elif data.startswith("amz_"):
        prodotto_id = data.split("_")[1]
        await mostra_prodotto_amazon(update, context, prodotto_id)

# Inizializzazione
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

# Handler per Vercel
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
