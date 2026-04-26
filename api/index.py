import os
import json
import sqlite3
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from nowpayment import NowPayments

# ---------- CONFIGURAZIONE ----------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
NOWPAYMENTS_API_KEY = os.environ.get('NOWPAYMENTS_API_KEY')
# -----------------------------------

# Inizializza client NowPayments
np_client = NowPayments(NOWPAYMENTS_API_KEY)

# ---------- CATALOGO PRODOTTI ----------
PRODOTTI = {
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
# -----------------------------------

# Inizializza l'applicazione Telegram
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ---------- FUNZIONI DATABASE ----------
def salva_ordine(user_id, prodotti_id, totale, valuta):
    """Salva un nuovo ordine nel database temporaneo"""
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

# ---------- COMANDI BOT ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra il catalogo dei prodotti"""
    keyboard = []
    for pid, prodotto in PRODOTTI.items():
        keyboard.append([InlineKeyboardButton(
            f"{prodotto['nome']} - {prodotto['prezzo']}{prodotto['valuta']}",
            callback_data=f"prod_{pid}"
        )])
    
    await update.message.reply_text(
        "🟢 *MarketHub* 🟢\n\nBenvenuto nel nostro negozio.\nScegli un prodotto:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def mostra_prodotto(update: Update, context: ContextTypes.DEFAULT_TYPE, prodotto_id: str):
    """Mostra il prodotto, genera il pagamento e salva l'ordine"""
    query = update.callback_query
    prodotto = PRODOTTI[prodotto_id]
    await query.answer()
    
    # Messaggio temporaneo di caricamento
    await query.edit_message_text(
        f"⏳ *Generazione pagamento per {prodotto['nome']}...*",
        parse_mode="Markdown"
    )
    
    try:
        # Crea invoice su NowPayments
        invoice = np_client.payment.create_invoice(
            price_amount=prodotto["prezzo"],
            price_currency=prodotto["valuta"]
        )
        payment_link = invoice.get("invoice_url")
        if not payment_link:
            raise Exception("Nessun link di pagamento ricevuto")
        
        # Salva l'ordine nel database
        ordine_id = salva_ordine(
            user_id=update.effective_user.id,
            prodotti_id=[prodotto_id],
            totale=prodotto["prezzo"],
            valuta=prodotto["valuta"]
        )
        
        # Testo del messaggio con il link di pagamento
        caption = (
            f"✅ *Ordine #{ordine_id} creato!*\n"
            f"💰 *Totale:* {prodotto['prezzo']} {prodotto['valuta']}\n\n"
            f"🔗 **[CLICCA QUI PER PAGARE CON CRIPTO]({payment_link})**\n\n"
            f"📌 *Supporta:* Bitcoin, Monero (XMR), USDT, Ethereum e 100+ altre crypto\n\n"
            f"_Dopo il pagamento, lo stato dell'ordine verrà aggiornato._"
        )
        
        keyboard = [[InlineKeyboardButton("◀️ Torna al catalogo", callback_data="catalogo")]]
        
        # Cancella il vecchio messaggio di caricamento e invia il prodotto con immagine
        await query.message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=prodotto["photo_url"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ *Errore*: {str(e)[:100]}\nRiprova più tardi.",
            parse_mode="Markdown"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce tutti i callback dei pulsanti"""
    query = update.callback_query
    await query.answer()
    
    # Pulsante "Torna al catalogo"
    if query.data == "catalogo":
        # Elimina il messaggio corrente (quello con il prodotto e il link)
        await query.message.delete()
        
        # Ricostruisce il catalogo da zero
        keyboard = []
        for pid, prodotto in PRODOTTI.items():
            keyboard.append([InlineKeyboardButton(
                f"{prodotto['nome']} - {prodotto['prezzo']}{prodotto['valuta']}",
                callback_data=f"prod_{pid}"
            )])
        
        # Invia un nuovo messaggio con il catalogo
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🟢 *MarketHub* 🟢\n\nBenvenuto nel nostro negozio.\nScegli un prodotto:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    # Pulsante di un prodotto
    elif query.data.startswith("prod_"):
        prodotto_id = query.data.split("_")[1]
        await mostra_prodotto(update, context, prodotto_id)

# Registra i command handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

# ---------- FUNZIONE PRINCIPALE PER VERCEL ----------
def handler(event, context):
    """
    Funzione serverless che Vercel chiama quando arriva una richiesta POST.
    """
    try:
        # Estrae il corpo della richiesta (l'update di Telegram)
        body = json.loads(event['body'])
        
        # Crea un oggetto Update di python-telegram-bot
        update = Update.de_json(body, application.bot)
        
        # Crea un loop di eventi asincrono per eseguire il processamento
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.process_update(update))
        
        # Risponde a Vercel (e quindi a Telegram) che tutto è ok
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'ok'})
        }
    except Exception as e:
        # In caso di errore, lo logga e risponde con un errore
        print(f"Errore: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'status': 'error', 'message': str(e)})
        }
