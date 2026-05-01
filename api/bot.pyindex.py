import json
import os
import sys
import asyncio
import logging
import stripe
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from nowpayment import NowPayments

# FIX per Python 3.14
if sys.version_info >= (3, 8):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except:
        pass

# Configurazione dalle variabili d'ambiente Vercel
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
NOWPAYMENTS_API_KEY = os.environ.get('NOWPAYMENTS_API_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID', 0))

logging.basicConfig(level=logging.INFO)

stripe.api_key = STRIPE_SECRET_KEY
np_client = NowPayments(NOWPAYMENTS_API_KEY)

# ==================== IL TUO CATALOGO ====================
PRODOTTI = {
    "1": {"nome": "📘 Corso Crypto Base", "prezzo": 10, "valuta": "EUR",
          "descrizione": "Impara le basi in 7 giorni.\n✅ 5 moduli video\n✅ PDF scaricabile"},
    "2": {"nome": "🎓 Corso Trading Avanzato", "prezzo": 50, "valuta": "EUR",
          "descrizione": "Diventa un trader professionista.\n✅ 10 ore di video\n✅ Strumenti esclusivi"}
}

AMAZON = {
    "amz_1": {"nome": "🎧 Cuffie Wireless", "prezzo": "39.99", "valuta": "EUR",
              "descrizione": "Cuffie Bluetooth.\n⭐ 4.5/5 su Amazon",
              "link": "https://amzn.to/IL_TUO_LINK"}
}

SERVIZI = {
    "1": {"nome": "💻 Consulenza Crypto 1h", "prezzo": 75, "valuta": "EUR",
          "descrizione": "Consulenza personalizzata.\n✅ Analisi portfolio\n✅ Strategie"},
    "2": {"nome": "📊 Analisi Tecnica Avanzata", "prezzo": 120, "valuta": "EUR",
          "descrizione": "Report dettagliato.\n✅ Setup operativi"}
}

# ==================== FUNZIONI PAGAMENTO ====================
async def paga_crypto(update, context, item, back_callback):
    q = update.callback_query
    await q.answer()
    try:
        inv = np_client.payment.create_invoice(price_amount=item["prezzo"], price_currency=item["valuta"])
        link = inv.get("invoice_url")
        testo = f"✅ *{item['nome']}*\n\n💰 {item['prezzo']}€\n\n🔗 [PAGA CON CRIPTO]({link})"
        kb = [[InlineKeyboardButton("◀️ Torna al catalogo", callback_data=back_callback)]]
        await q.edit_message_text(testo, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception as e:
        await q.edit_message_text(f"❌ Errore: {e}", parse_mode="Markdown")

async def paga_stripe(update, context, item, back_callback):
    q = update.callback_query
    await q.answer()
    try:
        prezzo_cent = int(float(item['prezzo']) * 100)
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price_data': {'currency': item['valuta'].lower(), 'product_data': {'name': item['nome']}, 'unit_amount': prezzo_cent}, 'quantity': 1}],
            mode='payment',
            success_url='https://t.me/{}?start=success'.format(context.bot.username),
            cancel_url='https://t.me/{}?start=cancel'.format(context.bot.username),
        )
        testo = f"✅ *{item['nome']}*\n\n💰 {item['prezzo']}€\n\n🔗 [PAGA CON CARTA]({session.url})"
        kb = [[InlineKeyboardButton("◀️ Torna al catalogo", callback_data=back_callback)]]
        await q.edit_message_text(testo, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except Exception as e:
        await q.edit_message_text(f"❌ Errore Stripe: {e}", parse_mode="Markdown")

# ==================== HANDLER (stessi del tuo bot) ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 PRODOTTI", callback_data="sezione_prodotti")],
        [InlineKeyboardButton("🛍️ AMAZON", callback_data="sezione_amazon")],
        [InlineKeyboardButton("💼 SERVIZI", callback_data="sezione_servizi")]
    ]
    await update.message.reply_text("🟢 *MarketHub* 🟢\n\nScegli una categoria:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def sezione_prodotti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [[InlineKeyboardButton(f"{p['nome']} - {p['prezzo']}€", callback_data=f"prod_{pid}")] for pid, p in PRODOTTI.items()]
    kb.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="menu")])
    await q.message.edit_text("📦 *PRODOTTI*\n\nScegli un prodotto:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def dettaglio_prodotto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    pid = q.data.split("_")[1]
    p = PRODOTTI[pid]
    await q.answer()
    kb = [
        [InlineKeyboardButton("₿ PAGA CON CRYPTO", callback_data=f"crypto_{pid}")],
        [InlineKeyboardButton("💳 PAGA CON CARTA", callback_data=f"stripe_{pid}")],
        [InlineKeyboardButton("◀️ INDIETRO", callback_data="sezione_prodotti")]
    ]
    await q.edit_message_text(f"*{p['nome']}*\n\n{p['descrizione']}\n\n💰 {p['prezzo']}€\n\nScegli metodo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def crypto_prod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split("_")[1]
    await paga_crypto(update, context, PRODOTTI[pid], "sezione_prodotti")

async def stripe_prod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = update.callback_query.data.split("_")[1]
    await paga_stripe(update, context, PRODOTTI[pid], "sezione_prodotti")

async def sezione_amazon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [[InlineKeyboardButton(f"🛒 {a['nome']} - {a['prezzo']}€", url=a['link'])] for aid, a in AMAZON.items()]
    kb.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="menu")])
    await q.message.edit_text("🛍️ *AMAZON*\n\nClicca sul prodotto:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def sezione_servizi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [[InlineKeyboardButton(f"{s['nome']} - {s['prezzo']}€", callback_data=f"serv_{sid}")] for sid, s in SERVIZI.items()]
    kb.append([InlineKeyboardButton("◀️ Torna al menu", callback_data="menu")])
    await q.message.edit_text("💼 *SERVIZI*\n\nScegli un servizio:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def dettaglio_servizio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    sid = q.data.split("_")[1]
    s = SERVIZI[sid]
    await q.answer()
    kb = [
        [InlineKeyboardButton("₿ PAGA CON CRYPTO", callback_data=f"crypto_serv_{sid}")],
        [InlineKeyboardButton("💳 PAGA CON CARTA", callback_data=f"stripe_serv_{sid}")],
        [InlineKeyboardButton("◀️ INDIETRO", callback_data="sezione_servizi")]
    ]
    await q.edit_message_text(f"*{s['nome']}*\n\n{s['descrizione']}\n\n💰 {s['prezzo']}€\n\nScegli metodo:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def crypto_serv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = update.callback_query.data.split("_")[2]
    await paga_crypto(update, context, SERVIZI[sid], "sezione_servizi")

async def stripe_serv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = update.callback_query.data.split("_")[2]
    await paga_stripe(update, context, SERVIZI[sid], "sezione_servizi")

# ==================== CALLBACK ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    await q.answer()
    
    if data == "menu":
        await q.message.delete()
        kb = [
            [InlineKeyboardButton("📦 PRODOTTI", callback_data="sezione_prodotti")],
            [InlineKeyboardButton("🛍️ AMAZON", callback_data="sezione_amazon")],
            [InlineKeyboardButton("💼 SERVIZI", callback_data="sezione_servizi")]
        ]
        await context.bot.send_message(chat_id=update.effective_chat.id, text="🟢 *MarketHub* 🟢\n\nScegli una categoria:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif data == "sezione_prodotti":
        await sezione_prodotti(update, context)
    elif data == "sezione_amazon":
        await sezione_amazon(update, context)
    elif data == "sezione_servizi":
        await sezione_servizi(update, context)
    elif data.startswith("prod_"):
        await dettaglio_prodotto(update, context)
    elif data.startswith("crypto_") and not data.startswith("crypto_serv_"):
        await crypto_prod(update, context)
    elif data.startswith("stripe_") and not data.startswith("stripe_serv_"):
        await stripe_prod(update, context)
    elif data.startswith("serv_"):
        await dettaglio_servizio(update, context)
    elif data.startswith("crypto_serv_"):
        await crypto_serv(update, context)
    elif data.startswith("stripe_serv_"):
        await stripe_serv(update, context)

# ==================== ENTRY POINT PER VERCEL ====================
# Inizializza l'applicazione una volta all'avvio
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

def handler(event, context):
    """Funzione serverless chiamata da Vercel"""
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
