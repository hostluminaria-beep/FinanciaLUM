from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import TOKEN, ADMIN_ID, MASTER_PASSWORD
import database as db
import json
import logging
import time

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Application.builder().token(TOKEN).build()
user_sessions = {}
admin_sessions = {}
user_states = {}

def login_required(func):
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in user_sessions:
            await update.message.reply_text("❌ Debes iniciar sesión. Usa /menu")
            return
        context.user_data['jugador_id'] = user_sessions[user_id]
        db.verificar_guardado()
        return await func(update, context, *args, **kwargs)
    return wrapper

def admin_required(func):
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID or user_id not in admin_sessions or time.time() > admin_sessions[user_id]:
            await update.message.reply_text("❌ Acceso denegado. Usa /admin_login")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ============ INICIO ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔑 Iniciar Sesión", callback_data="login")],
        [InlineKeyboardButton("📝 Registrarse", callback_data="registro")],
        [InlineKeyboardButton("ℹ️ Acerca de", callback_data="acerca")],
    ]
    await update.message.reply_text(
        "🔐 *DINEROLUM BOT*\n\nSistema financiero oficial del Juego de Rol Luminaria.\nAdministración: Victor Granado\n\n/menu - Menú de jugador",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def acerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    txt = "ℹ️ *ACERCA DE*\n\nDineroLUM Bot\nSistema financiero oficial de Luminaria\n\nAdministración: Victor Granado\nVersión: 4.0\n© 2026"
    if query:
        await query.answer()
        await query.edit_message_text(txt, parse_mode='Markdown')
    else:
        await update.message.reply_text(txt, parse_mode='Markdown')

# ============ REGISTRO ============
async def registro_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[update.effective_user.id] = {'state': 'esperando_codigo'}
    await query.edit_message_text("📝 *REGISTRO*\n\nPaso 1/4: Introduce tu código de invitación:", parse_mode='Markdown')

async def login_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[update.effective_user.id] = {'state': 'login_nombre'}
    await query.edit_message_text("🔑 *INICIAR SESIÓN*\n\nIntroduce tu nombre de jugador:", parse_mode='Markdown')

# ============ HANDLE MESSAGE ============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {}).get('state')
    if state is None:
        return
    
    if state == 'crear_pin':
        pin = text
        jugador_id = context.user_data.get('jugador_id')
        banco_id = context.user_data.get('crear_banco_id')
        moneda = context.user_data.get('crear_moneda')
        if not jugador_id or not banco_id or not moneda:
            await update.message.reply_text("❌ Error.")
            user_states.pop(user_id, None)
            return
        ok, msg = db.crear_cuenta(jugador_id, banco_id, moneda, pin)
        user_states.pop(user_id, None)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
        if ok:
            await menu_principal(update, context)
        return
    
    if state == 'transf_pin':
        pin = text
        origen = context.user_data.get('transf_origen')
        destino = user_states[user_id].get('destino')
        monto = user_states[user_id].get('monto')
        jugador_id = context.user_data.get('jugador_id')
        ok, msg = db.transferir(jugador_id, origen, destino, monto, pin)
        user_states.pop(user_id, None)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
        if ok:
            await menu_principal(update, context)
        return
    
    if state == 'esperando_codigo':
        if db.validar_codigo(text):
            user_states[user_id] = {'state': 'esperando_nombre'}
            await update.message.reply_text("✅ Código válido.\n\nPaso 2/4: Elige tu nombre de jugador:")
        else:
            await update.message.reply_text("❌ Código inválido.")
        return
    
    if state == 'esperando_nombre':
        if db.get_jugador_by_nombre(text):
            await update.message.reply_text("❌ Ese nombre ya existe.")
        else:
            user_states[user_id]['nombre'] = text
            user_states[user_id]['state'] = 'esperando_password'
            await update.message.reply_text("Paso 3/4: Elige tu contraseña:")
        return
    
    if state == 'esperando_password':
        user_states[user_id]['password'] = text
        ubicaciones = db.get_ubicaciones()
        if not ubicaciones:
            await update.message.reply_text("❌ No hay ubicaciones.")
            user_states.pop(user_id, None)
            return
        keyboard = [[InlineKeyboardButton(u[1], callback_data=f"reg_ubi_{u[0]}")] for u in ubicaciones]
        user_states[user_id]['state'] = 'esperando_ubicacion'
        await update.message.reply_text("Paso 4/4: Elige tu ubicación:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if state == 'login_nombre':
        jugador = db.get_jugador_by_nombre(text)
        if jugador:
            user_states[user_id] = {'state': 'login_password', 'jugador': jugador}
            await update.message.reply_text("Introduce tu contraseña:")
        else:
            await update.message.reply_text("❌ Jugador no encontrado.")
        return
    
    if state == 'login_password':
        jugador = user_states[user_id]['jugador']
        if db.verificar_login(jugador[1], text):
            user_sessions[user_id] = jugador[0]
            context.user_data['jugador_id'] = jugador[0]
            user_states.pop(user_id, None)
            await menu_principal(update, context)
        else:
            await update.message.reply_text("❌ Contraseña incorrecta.")
        return
    
    if state == 'transf_destino':
        try:
            user_states[user_id] = {'state': 'transf_monto', 'destino': int(text)}
            await update.message.reply_text("Escribe el monto a transferir:")
        except:
            await update.message.reply_text("❌ ID inválido.")
        return
    
    if state == 'transf_monto':
        try:
            user_states[user_id]['monto'] = float(text)
            user_states[user_id]['state'] = 'transf_pin'
            await update.message.reply_text("Escribe el PIN de tu cuenta origen:")
        except:
            await update.message.reply_text("❌ Monto inválido.")
        return
    
    if state == 'conv_monto':
        try:
            monto = float(text)
            ok, msg = db.convertir_moneda(context.user_data.get('conv_origen'), context.user_data.get('conv_destino'), monto)
            user_states.pop(user_id, None)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            if ok:
                await menu_principal(update, context)
        except:
            await update.message.reply_text("❌ Monto inválido.")
        return
    
    if state == 'dep_monto':
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("Formato: monto MONEDA (ej: 100 LUM)")
            return
        try:
            monto = float(parts[0])
            moneda = parts[1].upper()
            ok, msg = db.depositar_efectivo(context.user_data.get('jugador_id'), moneda, monto, context.user_data.get('dep_cuenta'))
            user_states.pop(user_id, None)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            if ok:
                await menu_principal(update, context)
        except:
            await update.message.reply_text("❌ Error.")
        return
    
    if state == 'buscar_producto':
        tienda_id = context.user_data.get('tienda_buscar_id')
        if not tienda_id:
            await update.message.reply_text("❌ Selecciona una tienda primero.")
            user_states.pop(user_id, None)
            return
        resultados = db.buscar_productos(tienda_id, text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron productos.")
            user_states.pop(user_id, None)
            return
        keyboard = []
        for r in resultados[:20]:
            monedas = json.loads(r[7])
            stock = r[8] if len(r) > 8 else '?'
            keyboard.append([InlineKeyboardButton(
                f"{r[2]} ({r[3]}) | LUM:{r[4]:.0f} EUR:{r[5]:.0f} Stock:{stock}",
                callback_data=f"comprar_prod_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text("🛒 Resultados:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if state == 'buscar_oferta':
        resultados = db.buscar_ofertas(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron ofertas.")
            user_states.pop(user_id, None)
            return
        keyboard = []
        for r in resultados[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📦 {r[1]} ({r[2]}) | LUM:{r[3]:.0f} EUR:{r[4]:.0f} | {r[6]}",
                callback_data=f"comprar_oferta_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text("📦 Ofertas:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if state == 'buscar_acciones':
        resultados = db.buscar_ofertas_acciones(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron acciones.")
            user_states.pop(user_id, None)
            return
        keyboard = []
        for r in resultados[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📈 {r[1]} | Cant:{r[2]} | Precio:{r[3]:.2f} | {r[4]}",
                callback_data=f"comprar_accion_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text("📈 Acciones:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if state == 'transf_efectivo_jugador':
        try:
            destino_id = int(text)
            context.user_data['transf_efectivo_destino'] = destino_id
            user_states[user_id] = {'state': 'transf_efectivo_moneda'}
            await update.message.reply_text("Elige moneda:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("LUM", callback_data="tef_moneda_LUM")],
                [InlineKeyboardButton("EUR", callback_data="tef_moneda_EUR")],
                [InlineKeyboardButton("LTR", callback_data="tef_moneda_LTR")],
            ]))
        except:
            await update.message.reply_text("❌ ID inválido.")
        return
    
    if state == 'transf_efectivo_monto':
        try:
            monto = float(text)
            de_id = context.user_data.get('jugador_id')
            para_id = context.user_data.get('transf_efectivo_destino')
            moneda = context.user_data.get('transf_efectivo_moneda')
            ok, msg = db.transferir_efectivo(de_id, para_id, moneda, monto)
            user_states.pop(user_id, None)
            await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")
            if ok:
                await menu_principal(update, context)
        except:
            await update.message.reply_text("❌ Monto inválido.")
        return

# ============ MENÚ PRINCIPAL ============
async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jugador_id = context.user_data.get('jugador_id')
    ubicacion = db.get_ubicacion_jugador(jugador_id)
    loc_text = f"{ubicacion[1]} ({ubicacion[2]})" if ubicacion else "Desconocida"
    keyboard = [
        [InlineKeyboardButton("💵 Activos Financieros", callback_data="menu_financiero")],
        [InlineKeyboardButton("🛒 Tiendas", callback_data="menu_tiendas")],
        [InlineKeyboardButton("📦 Buscar Ofertas", callback_data="buscar_oferta")],
        [InlineKeyboardButton("📈 Mercado de Valores", callback_data="menu_bolsa")],
        [InlineKeyboardButton("🎒 Inventario", callback_data="menu_inventario")],
        [InlineKeyboardButton("💸 Transferir Efectivo", callback_data="transf_efectivo")],
        [InlineKeyboardButton("🚆 Viajar", callback_data="menu_viajes")],
        [InlineKeyboardButton("📊 Resumen Total", callback_data="menu_resumen")],
        [InlineKeyboardButton("📋 Historial", callback_data="menu_historial")],
    ]
    await update.message.reply_text(
        f"🏦 *MENÚ PRINCIPAL*\n📍 Ubicación: {loc_text}",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

# ============ MENÚ TIENDAS ============
async def menu_tiendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tiendas = db.get_tiendas()
    if not tiendas:
        await query.edit_message_text("No hay tiendas.")
        return
    keyboard = [[InlineKeyboardButton(t[1], callback_data=f"tienda_{t[0]}")] for t in tiendas]
    keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
    await query.edit_message_text("🛒 *TIENDAS*\n\nSelecciona una tienda:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ MENÚ INVENTARIO ============
async def menu_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data.get('jugador_id')
    inventario = db.get_inventario(jugador_id)
    if not inventario:
        await query.edit_message_text("Tu inventario está vacío.")
        return
    keyboard = []
    for i in inventario:
        estado = "🟢 Venta" if i[6] else "🔴"
        keyboard.append([InlineKeyboardButton(f"{estado} {i[2]} ({i[3]}) x{i[4]}", callback_data=f"inv_{i[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
    await query.edit_message_text("🎒 *INVENTARIO*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ CALLBACK PRINCIPAL ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    jugador_id = context.user_data.get('jugador_id')
    user_id = update.effective_user.id
    
    if data == "login": await login_guiado(update, context)
    elif data == "registro": await registro_guiado(update, context)
    elif data == "acerca": await acerca(update, context)
    elif data == "volver_menu": await menu_principal(update, context)
    elif data == "menu_financiero": await menu_financiero(update, context)
    elif data == "menu_tiendas": await menu_tiendas(update, context)
    elif data == "menu_inventario": await menu_inventario(update, context)
    
    elif data == "fin_cuentas":
        cuentas = db.get_cuentas(jugador_id)
        txt = "🏦 *MIS CUENTAS*\n\n" + ("\n".join([f"ID:{c[0]} | {c[1]} | {c[2]} | {c[3]:.2f}" for c in cuentas]) if cuentas else "No tienes cuentas.")
        await query.edit_message_text(txt, parse_mode='Markdown')
    
    elif data == "fin_crear": await crear_cuenta_guiado(update, context)
    
    elif data == "fin_efectivo":
        e = db.get_efectivo(jugador_id)
        await query.edit_message_text(f"💵 *EFECTIVO*\n\nLUM: {e[0]:.2f}\nEUR: {e[1]:.2f}\nLTR: {e[2]:.2f}", parse_mode='Markdown')
    
    elif data == "menu_resumen":
        lum, eur, ltr, acc = db.get_total_activos(jugador_id)
        await query.edit_message_text(f"📊 *RESUMEN*\n\n💰 LUM: {lum:,.2f}\n💰 EUR: {eur:,.2f}\n💰 LTR: {ltr:,.2f}\n📈 Acciones: {acc:,.2f} EUR", parse_mode='Markdown')
    
    elif data == "buscar_oferta":
        user_states[user_id] = {'state': 'buscar_oferta'}
        await query.edit_message_text("📦 Escribe el nombre del item:")
    
    elif data == "transf_efectivo":
        user_states[user_id] = {'state': 'transf_efectivo_jugador'}
        await query.edit_message_text("💸 Escribe el ID del jugador destino:")
    
    elif data.startswith("tef_moneda_"):
        moneda = data.split("_")[2]
        context.user_data['transf_efectivo_moneda'] = moneda
        user_states[user_id] = {'state': 'transf_efectivo_monto'}
        await query.edit_message_text(f"Escribe el monto en {moneda}:")
    
    elif data.startswith("tienda_"):
        tienda_id = int(data.split("_")[1])
        context.user_data['tienda_buscar_id'] = tienda_id
        user_states[user_id] = {'state': 'buscar_producto'}
        tienda = db.get_tienda_by_id(tienda_id)
        await query.edit_message_text(f"🔍 Buscar en {tienda[1]}:\n\nEscribe una palabra clave:")
    
    elif data == "menu_bolsa":
        keyboard = [
            [InlineKeyboardButton("📊 Ver Empresas", callback_data="bolsa_empresas")],
            [InlineKeyboardButton("🔍 Buscar Acciones", callback_data="buscar_acciones")],
            [InlineKeyboardButton("📋 Mis Acciones", callback_data="bolsa_mis")],
            [InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")],
        ]
        await query.edit_message_text("📈 *MERCADO DE VALORES*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "buscar_acciones":
        user_states[user_id] = {'state': 'buscar_acciones'}
        await query.edit_message_text("📈 Escribe el nombre de la empresa:")
    
    elif data == "bolsa_empresas":
        empresas = db.get_empresas()
        keyboard = [[InlineKeyboardButton(f"{e[1]} - {e[3]:.2f} EUR", callback_data=f"bolsa_comp_{e[0]}")] for e in empresas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_bolsa")])
        await query.edit_message_text("📈 *EMPRESAS*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "bolsa_mis":
        acciones = db.get_acciones_jugador(jugador_id)
        txt = "📋 *MIS ACCIONES*\n\n" + ("\n".join([f"ID:{a[0]} {a[1]} | Cant:{a[2]} | Valor:{a[3]:.2f} EUR" for a in acciones]) if acciones else "No tienes acciones.")
        await query.edit_message_text(txt, parse_mode='Markdown')
    
    elif data == "menu_viajes": await menu_viajes(update, context)
    
    elif data == "menu_historial":
        hist = db.get_historial_financiero(jugador_id)
        txt = "📋 *HISTORIAL*\n\n" + ("\n".join([f"{t[5][:16]} | {t[0]} | {t[1]} | {t[2]:.2f} {t[3]}" for t in hist]) if hist else "Sin movimientos.")
        await query.edit_message_text(txt, parse_mode='Markdown')
    
    elif data == "fin_tasas":
        bancos = db.get_bancos()
        keyboard = [[InlineKeyboardButton(b[1], callback_data=f"tasas_{b[0]}")] for b in bancos]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("📊 *TIPOS DE CAMBIO*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("tasas_"):
        banco_id = int(data.split("_")[1])
        cambios = db.get_tipos_cambio(banco_id)
        txt = "💱 *TIPOS DE CAMBIO*\n\n" + ("\n".join([f"{c[0]}→{c[1]}: C:{c[2]:.4f} V:{c[3]:.4f}" for c in cambios]) if cambios else "Sin tipos.")
        await query.edit_message_text(txt, parse_mode='Markdown')
    
    elif data == "fin_transferir":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"transf_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("💱 *TRANSFERIR*\n\nSelecciona cuenta origen:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("transf_"):
        context.user_data['transf_origen'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'transf_destino'}
        await query.edit_message_text("Escribe el ID de la cuenta destino:")
    
    elif data == "fin_convertir":
        bancos = db.get_bancos()
        keyboard = [[InlineKeyboardButton(b[1], callback_data=f"convbanco_{b[0]}")] for b in bancos]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("🔄 *CONVERTIR*\n\nSelecciona el banco:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("convbanco_"):
        banco_id = int(data.split("_")[1])
        context.user_data['conv_banco'] = banco_id
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"conv_{c[0]}")] for c in cuentas if c[1] == db.get_banco_by_id(banco_id)[1]]
        keyboard.append([InlineKeyboardButton("💵 Efectivo", callback_data="conv_efectivo")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_convertir")])
        await query.edit_message_text("🔄 *CONVERTIR*\n\nSelecciona origen:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("conv_"):
        origen = int(data.split("_")[1])
        context.user_data['conv_origen'] = origen
        cuentas = [c for c in db.get_cuentas(jugador_id) if c[0] != origen]
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"convd_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("💵 Efectivo", callback_data="convd_efectivo")])
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_convertir")])
        await query.edit_message_text("🔄 *CONVERTIR*\n\nSelecciona destino:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("convd_"):
        context.user_data['conv_destino'] = int(data.split("_")[1]) if data.split("_")[1] != "efectivo" else 0
        user_states[user_id] = {'state': 'conv_monto'}
        await query.edit_message_text("Escribe el monto a convertir:")
    
    elif data == "fin_depositar":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"dep_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("📥 *DEPOSITAR*\n\nSelecciona cuenta:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("dep_"):
        context.user_data['dep_cuenta'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'dep_monto'}
        await query.edit_message_text("Escribe: monto MONEDA (ej: 100 LUM)")
    
    elif data.startswith("crear_banco_"): await crear_cuenta_moneda(update, context)
    elif data.startswith("crear_moneda_"): await crear_cuenta_pin(update, context)
    
    elif data.startswith("comprar_prod_"):
        prod_id = int(data.split("_")[2])
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"compra_con_{prod_id}_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_tiendas")])
        await query.edit_message_text("🛒 *COMPRAR*\n\nSelecciona cuenta:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("compra_con_"):
        parts = data.split("_")
        prod_id = int(parts[2])
        cuenta_id = int(parts[3])
        ok, msg = db.comprar_producto_tienda(jugador_id, prod_id, cuenta_id)
        await query.edit_message_text(f"{'✅' if ok else '❌'} {msg}")
    
    elif data.startswith("comprar_oferta_"):
        oferta_id = int(data.split("_")[2])
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"compofer_{oferta_id}_{c[0]}_{c[2]}")] for c in cuentas]
        await query.edit_message_text("📦 *COMPRAR*\n\nSelecciona cuenta:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("compofer_"):
        parts = data.split("_")
        oferta_id = int(parts[1])
        cuenta_id = int(parts[2])
        moneda = parts[3]
        ok, msg = db.comprar_item_comprador(jugador_id, oferta_id, cuenta_id, moneda)
        await query.edit_message_text(f"{'✅' if ok else '❌'} {msg}")
    
    elif data.startswith("bolsa_comp_"):
        empresa_id = int(data.split("_")[2])
        cuentas = [c for c in db.get_cuentas(jugador_id) if c[2] == 'EUR']
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[3]:.2f} EUR", callback_data=f"bolsacomp_{empresa_id}_{c[0]}")] for c in cuentas]
        await query.edit_message_text("📈 *COMPRAR ACCIONES*\n\nSelecciona cuenta EUR:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("bolsacomp_"):
        parts = data.split("_")
        empresa_id = int(parts[1])
        cuenta_id = int(parts[2])
        user_states[user_id] = {'state': 'bolsa_cant', 'empresa_id': empresa_id, 'cuenta_id': cuenta_id}
        await query.edit_message_text("Escribe la cantidad de acciones:")
    
    elif data.startswith("comprar_accion_"):
        acc_id = int(data.split("_")[2])
        cuentas = [c for c in db.get_cuentas(jugador_id) if c[2] == 'EUR']
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[3]:.2f} EUR", callback_data=f"compoferacc_{acc_id}_{c[0]}")] for c in cuentas]
        await query.edit_message_text("📈 *COMPRAR*\n\nSelecciona cuenta EUR:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data.startswith("compoferacc_"):
        parts = data.split("_")
        acc_id = int(parts[1])
        cuenta_id = int(parts[2])
        user_states[user_id] = {'state': 'oferta_cant', 'acc_id': acc_id, 'cuenta_id': cuenta_id}
        await query.edit_message_text("Escribe la cantidad de acciones:")
    
    elif data.startswith("inv_"):
        item_id = int(data.split("_")[1])
        item = db.get_inventario_item(item_id)
        if item:
            keyboard = [
                [InlineKeyboardButton("💰 Vender", callback_data=f"vender_{item_id}")],
                [InlineKeyboardButton("📤 Transferir", callback_data=f"transfitem_{item_id}")],
                [InlineKeyboardButton("🔙 Volver", callback_data="menu_inventario")],
            ]
            await query.edit_message_text(f"📦 {item[2]} ({item[3]}) x{item[4]}", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("vender_"):
        item_id = int(data.split("_")[1])
        user_states[user_id] = {'state': 'vender_precio', 'item_id': item_id}
        await query.edit_message_text("Escribe: precio_lum precio_eur precio_ltr (0 para no aceptar)")
    
    elif data.startswith("transfitem_"):
        item_id = int(data.split("_")[1])
        context.user_data['transf_item'] = item_id
        user_states[user_id] = {'state': 'transf_item_destino'}
        await query.edit_message_text("Escribe el ID del jugador destino:")
    
    elif data.startswith("viaje_destino_"): await viaje_transporte(update, context)
    elif data.startswith("viaje_publico") or data.startswith("viaje_especial") or data.startswith("viaje_premium"): await viaje_confirmar(update, context)
    
    elif data.startswith("reg_ubi_"):
        ubicacion_id = int(data.split("_")[2])
        nombre = user_states[user_id]['nombre']
        password = user_states[user_id]['password']
        db.registrar_jugador(nombre, password, ubicacion_id)
        user_states.pop(user_id, None)
        await query.edit_message_text(f"✅ *¡Registro completado!*\n\nJugador: {nombre}\n\nUsa /menu para empezar", parse_mode='Markdown')

# ============ ADMIN ============
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ No autorizado")
        return
    if not context.args or context.args[0] != MASTER_PASSWORD:
        await update.message.reply_text("🔐 Usa: /admin_login <contraseña>")
        return
    admin_sessions[update.effective_user.id] = time.time() + 1800
    keyboard = [
        [InlineKeyboardButton("📥 Importar", callback_data="admin_importar")],
        [InlineKeyboardButton("📤 Exportar", callback_data="admin_exportar")],
        [InlineKeyboardButton("💾 Guardar Estado", callback_data="admin_guardar")],
        [InlineKeyboardButton("➕ Crear", callback_data="admin_crear")],
        [InlineKeyboardButton("❌ Eliminar", callback_data="admin_eliminar")],
        [InlineKeyboardButton("👥 Ver Jugadores", callback_data="admin_usuarios")],
        [InlineKeyboardButton("📈 Update Bolsa", callback_data="admin_updatebolsa")],
    ]
    await update.message.reply_text("🔧 *PANEL ADMIN*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "admin_importar":
        keyboard = [
            [InlineKeyboardButton("📥 Importar TODO", callback_data="admin_importar_todo")],
            [InlineKeyboardButton("🏦 Bancos", callback_data="admin_importar_bancos")],
            [InlineKeyboardButton("📍 Ubicaciones", callback_data="admin_importar_ubi")],
            [InlineKeyboardButton("🚆 Rutas", callback_data="admin_importar_rutas")],
            [InlineKeyboardButton("🏪 Tiendas", callback_data="admin_importar_tiendas")],
            [InlineKeyboardButton("📈 Empresas", callback_data="admin_importar_empresas")],
            [InlineKeyboardButton("🛒 Catálogo", callback_data="admin_importar_prod")],
            [InlineKeyboardButton("🔙 Volver", callback_data="admin_volver")],
            [InlineKeyboardButton("👥 Jugadores", callback_data="admin_importar_jug")],
        ]
        await query.edit_message_text("📥 *IMPORTAR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "admin_exportar":
        db.guardar_estado()
        await query.edit_message_text("✅ Estado exportado a GitHub")
    
    elif data == "admin_guardar":
        db.guardar_estado()
        await query.edit_message_text("✅ Estado guardado manualmente")
    
    elif data == "admin_crear":
        keyboard = [
            [InlineKeyboardButton("🔑 Código", callback_data="admin_codigo")],
            [InlineKeyboardButton("🏦 Banco", callback_data="admin_addbanco")],
            [InlineKeyboardButton("📈 Empresa", callback_data="admin_addempresa")],
            [InlineKeyboardButton("💸 Crédito", callback_data="admin_credito")],
            [InlineKeyboardButton("📦 Item", callback_data="admin_item")],
            [InlineKeyboardButton("🔙 Volver", callback_data="admin_volver")],
        ]
        await query.edit_message_text("➕ *CREAR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "admin_eliminar":
        keyboard = [
            [InlineKeyboardButton("🗑️ Código", callback_data="admin_del_codigo")],
            [InlineKeyboardButton("🗑️ Banco", callback_data="admin_del_banco")],
            [InlineKeyboardButton("🗑️ Cuenta", callback_data="admin_del_cuenta")],
            [InlineKeyboardButton("🗑️ Jugador", callback_data="admin_del_jugador")],
            [InlineKeyboardButton("🔙 Volver", callback_data="admin_volver")],
        ]
        await query.edit_message_text("❌ *ELIMINAR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "admin_volver": await admin_login(update, context)
    
    elif data == "admin_importar_todo":
        b, _ = db.importar_bancos_desde_json()
        u = db.importar_ubicaciones_desde_json()
        r = db.importar_rutas_desde_json()
        t = db.importar_tiendas_desde_json()
        e = db.importar_empresas_desde_json()
        await query.edit_message_text(f"✅ TODO importado\n🏦 Bancos: {b}\n📍 Ubicaciones: {u}\n🚆 Rutas: {r}\n🏪 Tiendas: {t}\n📈 Empresas: {e}")
    
    elif data == "admin_importar_bancos":
        c, t = db.importar_bancos_desde_json()
        await query.edit_message_text(f"✅ Bancos: {c} creados, {t} cambios")
    elif data == "admin_importar_ubi":
        c = db.importar_ubicaciones_desde_json()
        await query.edit_message_text(f"✅ Ubicaciones: {c}")
    elif data == "admin_importar_rutas":
        c = db.importar_rutas_desde_json()
        await query.edit_message_text(f"✅ Rutas: {c}")
    elif data == "admin_importar_tiendas":
        c = db.importar_tiendas_desde_json()
        await query.edit_message_text(f"✅ Tiendas: {c}")
    elif data == "admin_importar_empresas":
        c = db.importar_empresas_desde_json()
        await query.edit_message_text(f"✅ Empresas: {c}")
    elif data == "admin_importar_prod":
        await query.edit_message_text("Escribe: /admin_importar_catalogo <tienda>")
    
    elif data == "admin_codigo":
        await query.edit_message_text("Escribe: /admin_codigo <codigo>")
    elif data == "admin_addbanco":
        await query.edit_message_text("Escribe: /admin_addbanco <nombre> <monedas_json> <dep_eur> <dep_lum> <dep_ltr> <interes> <com_mismo> <com_otro>")
    elif data == "admin_addempresa":
        await query.edit_message_text("Escribe: /admin_addempresa <nombre> <sector> <valor> <totales> <disp>")
    elif data == "admin_credito":
        await query.edit_message_text("Escribe: /admin_credito <cuenta_id> <monto> <moneda>")
    elif data == "admin_item":
        await query.edit_message_text("Escribe: /admin_item <id> <nombre> <clasif> <cant> <unidad>")
    elif data == "admin_updatebolsa":
        await query.edit_message_text("Escribe: /admin_updatebolsa <empresa_id> <valor>")
    
    elif data == "admin_del_codigo":
        await query.edit_message_text("Escribe: /admin_del_codigo <codigo>")
    elif data == "admin_del_banco":
        await query.edit_message_text("Escribe: /admin_del_banco <banco_id>")
    elif data == "admin_del_cuenta":
        await query.edit_message_text("Escribe: /admin_del_cuenta <cuenta_id>")
    elif data == "admin_del_jugador":
        await query.edit_message_text("Escribe: /admin_del_jugador <jugador_id>")
    
    elif data == "admin_usuarios":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre, efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores")
        u = c.fetchall()
        conn.close()
        txt = "👥 *JUGADORES*\n\n" + "\n".join([f"ID:{j[0]} {j[1]} | LUM:{j[2]:.0f} EUR:{j[3]:.0f} LTR:{j[4]:.0f}" for j in u])
        await query.edit_message_text(txt, parse_mode='Markdown')

    elif data == "admin_importar_jug":
    await query.edit_message_text("Adjunta jugadores.json o escribe: /admin_importar_jugadores")

# ============ COMANDOS ADMIN ============
@admin_required
async def admin_codigo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Uso: /admin_codigo <codigo>"); return
    db.generar_codigo(context.args[0]); await update.message.reply_text(f"✅ {context.args[0]}")

@admin_required
async def admin_addbanco_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 8: await update.message.reply_text("Uso: /admin_addbanco <nombre> <monedas_json> <dep_eur> <dep_lum> <dep_ltr> <interes> <com_mismo> <com_otro>"); return
    db.add_banco(context.args[0], json.loads(context.args[1]), float(context.args[2]), float(context.args[3]), float(context.args[4]), float(context.args[5]), float(context.args[6]), float(context.args[7]))
    await update.message.reply_text("✅ Banco creado")

@admin_required
async def admin_addempresa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5: await update.message.reply_text("Uso: /admin_addempresa <nombre> <sector> <valor> <totales> <disp>"); return
    db.add_empresa(context.args[0], context.args[1], float(context.args[2]), int(context.args[3]), int(context.args[4]))
    await update.message.reply_text("✅ Empresa creada")

@admin_required
async def admin_credito_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3: await update.message.reply_text("Uso: /admin_credito <cuenta_id> <monto> <moneda>"); return
    db.actualizar_saldo_cuenta(int(context.args[0]), float(context.args[1]))
    await update.message.reply_text(f"✅ Crédito de {context.args[1]} {context.args[2]}")

@admin_required
async def admin_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5: await update.message.reply_text("Uso: /admin_item <id> <nombre> <clasif> <cant> <unidad>"); return
    db.agregar_inventario(int(context.args[0]), context.args[1], context.args[2], float(context.args[3]), context.args[4])
    await update.message.reply_text("✅ Item entregado")

@admin_required
async def admin_updatebolsa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: await update.message.reply_text("Uso: /admin_updatebolsa <empresa_id> <valor>"); return
    db.actualizar_valor_empresa(int(context.args[0]), float(context.args[1]))
    await update.message.reply_text("✅ Actualizado")

@admin_required
async def admin_del_codigo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    db.eliminar_codigo(context.args[0]); await update.message.reply_text("✅ Eliminado")

@admin_required
async def admin_del_banco_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    db.eliminar_banco(int(context.args[0])); await update.message.reply_text("✅ Eliminado")

@admin_required
async def admin_del_cuenta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    db.eliminar_cuenta(int(context.args[0])); await update.message.reply_text("✅ Eliminada")

@admin_required
async def admin_del_jugador_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    db.eliminar_jugador(int(context.args[0])); await update.message.reply_text("✅ Eliminado")

@admin_required
async def admin_importar_catalogo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Uso: /admin_importar_catalogo <tienda>"); return
    c = db.importar_productos_desde_json(' '.join(context.args))
    await update.message.reply_text(f"✅ {c} productos")

@admin_required
async def admin_importar_jugadores_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Importa jugadores desde un archivo JSON adjunto o desde data/jugadores.json"""
    try:
        # Si se adjunta un archivo
        if update.message.document:
            file = await update.message.document.get_file()
            filename = "jugadores_import.json"
            await file.download_to_drive(filename)
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            creados = db.importar_jugadores(data)
            os.remove(filename)
            await update.message.reply_text(f"✅ {creados} jugadores importados desde archivo")
        else:
            # Cargar desde data/jugadores.json
            filepath = os.path.join(db.DATA_DIR, 'jugadores.json')
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                creados = db.importar_jugadores(data)
                await update.message.reply_text(f"✅ {creados} jugadores importados desde jugadores.json")
            else:
                # Cargar desde estado.json
                filepath = os.path.join(db.DATA_DIR, 'estado.json')
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    creados = db.importar_jugadores(data)
                    await update.message.reply_text(f"✅ {creados} jugadores importados desde estado.json")
                else:
                    await update.message.reply_text("❌ No se encontró jugadores.json ni estado.json. Adjunta un archivo JSON.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ============ MAIN ============
if __name__ == "__main__":
    db.init_db()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("admin_login", admin_login))
    app.add_handler(CommandHandler("admin_codigo", admin_codigo_cmd))
    app.add_handler(CommandHandler("admin_addbanco", admin_addbanco_cmd))
    app.add_handler(CommandHandler("admin_addempresa", admin_addempresa_cmd))
    app.add_handler(CommandHandler("admin_credito", admin_credito_cmd))
    app.add_handler(CommandHandler("admin_item", admin_item_cmd))
    app.add_handler(CommandHandler("admin_updatebolsa", admin_updatebolsa_cmd))
    app.add_handler(CommandHandler("admin_del_codigo", admin_del_codigo_cmd))
    app.add_handler(CommandHandler("admin_del_banco", admin_del_banco_cmd))
    app.add_handler(CommandHandler("admin_del_cuenta", admin_del_cuenta_cmd))
    app.add_handler(CommandHandler("admin_del_jugador", admin_del_jugador_cmd))
    app.add_handler(CommandHandler("admin_importar_catalogo", admin_importar_catalogo_cmd))
    app.add_handler(CallbackQueryHandler(admin_button, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("admin_importar_jugadores", admin_importar_jugadores_cmd))
    print("🤖 DineroLUM Bot iniciado...")
    app.run_polling()
