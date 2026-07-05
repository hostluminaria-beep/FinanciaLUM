from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import TOKEN, ADMIN_ID, MASTER_PASSWORD
import database as db
import json
import logging
import time
import os

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
        return await func(update, context, *args, **kwargs)
    return wrapper

def admin_required(func):
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID or user_id not in admin_sessions or time.time() > admin_sessions[user_id]:
            await update.message.reply_text("❌ Acceso denegado. Usa /admin")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ============ COMANDOS DE MENÚ ============
async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in user_sessions:
        context.user_data['jugador_id'] = user_sessions[update.effective_user.id]
        await menu_principal(update, context)
    else:
        await start(update, context)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and update.effective_user.id in admin_sessions and time.time() < admin_sessions[update.effective_user.id]:
        await menu_admin(update, context)
    else:
        await update.message.reply_text("Usa /admin_login <contraseña>")

# ============ INICIO ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔑 Iniciar Sesión", callback_data="login")],
        [InlineKeyboardButton("📝 Registrarse", callback_data="registro")],
        [InlineKeyboardButton("ℹ️ Acerca de", callback_data="acerca")],
    ]
    await update.message.reply_text(
        "🔐 *SISTEMA ECONÓMICO DE LUMINARIA*\n\n"
        "Sistema Oficial para los flujos financieros del Juego de Rol de Luminaria.\n"
        "Administración: Victor Granado\n\n"
        "Comandos:\n"
        "/menu - Menú de jugador\n"
        "/admin - Menú de administrador",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============ ACERCA DE ============
async def acerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "ℹ️ *ACERCA DE*\n\n"
        "Sistema Económico de Luminaria\n"
        "Juego de Rol Oficial\n\n"
        "Administración: Victor Granado\n"
        "Versión: 2.0\n"
        "Sede: República de Luminaria\n\n"
        "© 2026 Todos los derechos reservados"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(texto, parse_mode='Markdown')
    else:
        await update.message.reply_text(texto, parse_mode='Markdown')

# ============ REGISTRO GUIADO ============
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

# ============ MANEJADOR DE MENSAJES ============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {}).get('state')
    
    if state == 'esperando_codigo':
        if db.validar_codigo(text):
            user_states[user_id] = {'state': 'esperando_nombre'}
            await update.message.reply_text("✅ Código válido.\n\nPaso 2/4: Elige tu nombre de jugador:")
        else:
            await update.message.reply_text("❌ Código inválido. Intenta de nuevo:")
    
    elif state == 'esperando_nombre':
        if db.get_jugador_by_nombre(text):
            await update.message.reply_text("❌ Ese nombre ya existe. Elige otro:")
        else:
            user_states[user_id]['nombre'] = text
            user_states[user_id]['state'] = 'esperando_password'
            await update.message.reply_text("✅ Nombre disponible.\n\nPaso 3/4: Elige tu contraseña:")
    
    elif state == 'esperando_password':
        user_states[user_id]['password'] = text
        ubicaciones = db.get_ubicaciones()
        if ubicaciones:
            keyboard = [[InlineKeyboardButton(u[1], callback_data=f"reg_ubi_{u[0]}")] for u in ubicaciones]
            user_states[user_id]['state'] = 'esperando_ubicacion'
            await update.message.reply_text("✅ Contraseña guardada.\n\nPaso 4/4: Elige tu ubicación inicial:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            db.registrar_jugador(user_states[user_id]['nombre'], text, 1)
            user_states.pop(user_id, None)
            await update.message.reply_text("✅ *¡Registro completado!*\n\nUsa /menu para empezar", parse_mode='Markdown')
    
    elif state == 'login_nombre':
        jugador = db.get_jugador_by_nombre(text)
        if jugador:
            user_states[user_id] = {'state': 'login_password', 'jugador': jugador}
            await update.message.reply_text("Introduce tu contraseña:")
        else:
            await update.message.reply_text("❌ Jugador no encontrado. Intenta de nuevo:")
    
    elif state == 'login_password':
        jugador = user_states[user_id]['jugador']
        if db.verificar_login(jugador[1], text):
            user_sessions[user_id] = jugador[0]
            context.user_data['jugador_id'] = jugador[0]
            user_states.pop(user_id, None)
            await menu_principal(update, context)
        else:
            await update.message.reply_text("❌ Contraseña incorrecta. Intenta de nuevo:")
    
    elif state == 'buscar_producto':
        resultados = db.buscar_productos(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron productos.")
            return
        keyboard = []
        for r in resultados[:20]:
            monedas = json.loads(r[7])
            stock = r[8] if len(r) > 8 else '?'
            keyboard.append([InlineKeyboardButton(
                f"🏪 {r[1]} | {r[2]} ({r[3]}) | LUM:{r[4]:.0f} EUR:{r[5]:.0f} Stock:{stock}",
                callback_data=f"comprar_prod_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text(f"🛒 Resultados para \"{text}\":", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif state == 'buscar_oferta':
        resultados = db.buscar_ofertas(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron ofertas.")
            return
        keyboard = []
        for r in resultados[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📦 {r[1]} ({r[2]}) | LUM:{r[3]:.0f} EUR:{r[4]:.0f} | {r[6]}",
                callback_data=f"comprar_oferta_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text(f"📦 Ofertas para \"{text}\":", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif state == 'buscar_acciones':
        resultados = db.buscar_ofertas_acciones(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron acciones.")
            return
        keyboard = []
        for r in resultados[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📈 {r[1]} | Cant:{r[2]} | Precio:{r[3]:.2f} | {r[4]}",
                callback_data=f"comprar_accion_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Menú", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text(f"📈 Acciones para \"{text}\":", reply_markup=InlineKeyboardMarkup(keyboard))

# ============ MENÚ PRINCIPAL ============
async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jugador_id = context.user_data.get('jugador_id')
    ubicacion = db.get_ubicacion_jugador(jugador_id)
    loc_text = f"{ubicacion[1]} ({ubicacion[2]})" if ubicacion else "Desconocida"
    
    keyboard = [
        [InlineKeyboardButton("💵 Activos Financieros", callback_data="menu_financiero")],
        [InlineKeyboardButton("🔍 Buscar en Tiendas", callback_data="buscar_tienda")],
        [InlineKeyboardButton("📦 Buscar Ofertas", callback_data="buscar_oferta")],
        [InlineKeyboardButton("📈 Mercado de Valores", callback_data="menu_bolsa")],
        [InlineKeyboardButton("🚆 Viajar", callback_data="menu_viajes")],
        [InlineKeyboardButton("📊 Resumen Total", callback_data="menu_resumen")],
        [InlineKeyboardButton("📋 Historial", callback_data="menu_historial")],
        [InlineKeyboardButton("ℹ️ Acerca de", callback_data="acerca")],
    ]
    await update.message.reply_text(
        f"🏦 *MENÚ PRINCIPAL*\n📍 Ubicación: {loc_text}\n\nSelecciona una sección:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============ CALLBACK PRINCIPAL ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    jugador_id = context.user_data.get('jugador_id')
    user_id = update.effective_user.id
    
    if data == "login":
        await login_guiado(update, context)
    elif data == "registro":
        await registro_guiado(update, context)
    elif data == "acerca":
        await acerca(update, context)
    elif data == "volver_menu":
        await menu_principal(update, context)
    elif data == "menu_financiero":
        await menu_financiero(update, context)
    elif data == "fin_cuentas":
        cuentas = db.get_cuentas(jugador_id)
        texto = "🏦 *MIS CUENTAS*\n\n" + ("\n".join([f"ID:{c[0]} | {c[1]} | {c[2]} | {c[3]:.2f}" for c in cuentas]) if cuentas else "No tienes cuentas.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "fin_crear":
        await crear_cuenta_guiado(update, context)
    elif data == "fin_efectivo":
        e = db.get_efectivo(jugador_id)
        await query.edit_message_text(f"💵 *EFECTIVO*\n\nLUM: {e[0]:.2f}\nEUR: {e[1]:.2f}\nLTR: {e[2]:.2f}", parse_mode='Markdown')
    elif data == "menu_resumen":
        lum, eur, ltr, acc = db.get_total_activos(jugador_id)
        await query.edit_message_text(f"📊 *RESUMEN*\n\n💰 LUM: {lum:,.2f}\n💰 EUR: {eur:,.2f}\n💰 LTR: {ltr:,.2f}\n📈 Acciones: {acc:,.2f} LUM", parse_mode='Markdown')
    elif data == "buscar_tienda":
        user_states[user_id] = {'state': 'buscar_producto'}
        await query.edit_message_text("🔍 Escribe el nombre del producto:")
    elif data == "buscar_oferta":
        user_states[user_id] = {'state': 'buscar_oferta'}
        await query.edit_message_text("📦 Escribe el nombre del item:")
    elif data == "menu_bolsa":
        keyboard = [
            [InlineKeyboardButton("📊 Ver Empresas", callback_data="bolsa_empresas")],
            [InlineKeyboardButton("🔍 Buscar Acciones", callback_data="buscar_acciones")],
            [InlineKeyboardButton("📋 Mis Acciones", callback_data="bolsa_mis")],
            [InlineKeyboardButton("🔙 Volver al Menú", callback_data="volver_menu")],
        ]
        await query.edit_message_text("📈 *MERCADO DE VALORES*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "buscar_acciones":
        user_states[user_id] = {'state': 'buscar_acciones'}
        await query.edit_message_text("📈 Escribe el nombre de la empresa:")
    elif data == "bolsa_empresas":
        empresas = db.get_empresas()
        keyboard = [[InlineKeyboardButton(f"{e[1]} - {e[3]:.2f} LUM", callback_data=f"bolsa_comp_{e[0]}")] for e in empresas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_bolsa")])
        await query.edit_message_text("📈 *EMPRESAS*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "bolsa_mis":
        acciones = db.get_acciones_jugador(jugador_id)
        texto = "📋 *MIS ACCIONES*\n\n" + ("\n".join([f"ID:{a[0]} {a[1]} | Cant:{a[2]} | Valor:{a[3]:.2f}" for a in acciones]) if acciones else "No tienes acciones.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "menu_viajes":
        await menu_viajes(update, context)
    elif data == "menu_historial":
        hist = db.get_historial_financiero(jugador_id)
        texto = "📋 *HISTORIAL*\n\n" + ("\n".join([f"{t[5][:16]} | {t[0]} | {t[1]} | {t[2]:.2f} {t[3]}" for t in hist]) if hist else "Sin movimientos.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "fin_tasas":
        bancos = db.get_bancos()
        keyboard = [[InlineKeyboardButton(b[1], callback_data=f"tasas_{b[0]}")] for b in bancos]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("📊 *TIPOS DE CAMBIO*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("tasas_"):
        banco_id = int(data.split("_")[1])
        cambios = db.get_tipos_cambio(banco_id)
        texto = "💱 *TIPOS DE CAMBIO*\n\n" + ("\n".join([f"{c[0]}→{c[1]}: C:{c[2]:.4f} V:{c[3]:.4f}" for c in cambios]) if cambios else "Sin tipos.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "fin_transferir":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"transf_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("💱 *TRANSFERIR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("transf_"):
        context.user_data['transf_origen'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'transf_destino'}
        await query.edit_message_text("Escribe el ID de la cuenta destino:")
    elif data == "fin_convertir":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"conv_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("🔄 *CONVERTIR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("conv_"):
        origen = int(data.split("_")[1])
        context.user_data['conv_origen'] = origen
        cuentas = [c for c in db.get_cuentas(jugador_id) if c[0] != origen]
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"convd_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_convertir")])
        await query.edit_message_text("🔄 *CONVERTIR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("convd_"):
        context.user_data['conv_destino'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'conv_monto'}
        await query.edit_message_text("Escribe el monto a convertir:")
    elif data == "fin_depositar":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"dep_{c[0]}")] for c in cuentas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("📥 *DEPOSITAR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("dep_"):
        context.user_data['dep_cuenta'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'dep_monto'}
        await query.edit_message_text("Escribe: monto MONEDA (ej: 100 LUM)")
    elif data.startswith("crear_banco_"):
        await crear_cuenta_moneda(update, context)
    elif data.startswith("crear_moneda_"):
        await crear_cuenta_pin(update, context)
    elif data.startswith("comprar_prod_"):
        context.user_data['compra_prod_id'] = int(data.split("_")[2])
        await query.edit_message_text("Escribe: /comprar <cuenta_id>")
    elif data.startswith("comprar_oferta_"):
        context.user_data['compra_oferta_id'] = int(data.split("_")[2])
        await query.edit_message_text("Escribe: /comprar_oferta <cuenta_id> <moneda>")
    elif data.startswith("comprar_accion_"):
        context.user_data['compra_acc_id'] = int(data.split("_")[2])
        await query.edit_message_text("Escribe: /comprar_oferta_accion <cantidad> <cuenta_id>")
    elif data.startswith("bolsa_comp_"):
        context.user_data['bolsa_empresa'] = int(data.split("_")[2])
        await query.edit_message_text("Escribe: /compra_accion <cantidad> <cuenta_id>")
    elif data.startswith("viaje_destino_"):
        await viaje_transporte(update, context)
    elif data.startswith("viaje_"):
        await viaje_confirmar(update, context)
    elif data.startswith("reg_ubi_"):
        ubicacion_id = int(data.split("_")[2])
        nombre = user_states[user_id]['nombre']
        password = user_states[user_id]['password']
        db.registrar_jugador(nombre, password, ubicacion_id)
        user_states.pop(user_id, None)
        await query.edit_message_text(f"✅ *¡Registro completado!*\n\nJugador: {nombre}\n\nUsa /menu para empezar", parse_mode='Markdown')

# ============ MENÚ FINANCIERO ============
async def menu_financiero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🏦 Ver Cuentas", callback_data="fin_cuentas")],
        [InlineKeyboardButton("➕ Crear Cuenta", callback_data="fin_crear")],
        [InlineKeyboardButton("💱 Transferir", callback_data="fin_transferir")],
        [InlineKeyboardButton("🔄 Convertir Moneda", callback_data="fin_convertir")],
        [InlineKeyboardButton("💵 Ver Efectivo", callback_data="fin_efectivo")],
        [InlineKeyboardButton("📥 Depositar Efectivo", callback_data="fin_depositar")],
        [InlineKeyboardButton("📊 Tipos de Cambio", callback_data="fin_tasas")],
        [InlineKeyboardButton("🔙 Volver al Menú", callback_data="volver_menu")],
    ]
    await query.edit_message_text("💵 *ACTIVOS FINANCIEROS*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ CREAR CUENTA ============
async def crear_cuenta_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bancos = db.get_bancos()
    if not bancos:
        await query.edit_message_text("No hay bancos. El admin debe importarlos.")
        return
    keyboard = []
    for b in bancos:
        monedas = json.loads(b[2])
        keyboard.append([InlineKeyboardButton(f"{b[1]} - {', '.join(monedas)} (Int:{b[6]}%)", callback_data=f"crear_banco_{b[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text("🏦 *CREAR CUENTA*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def crear_cuenta_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banco_id = int(query.data.split("_")[2])
    banco = db.get_banco_by_id(banco_id)
    context.user_data['crear_banco_id'] = banco_id
    monedas = json.loads(banco[2])
    keyboard = []
    for m in monedas:
        dep = banco[4] if m == 'LUM' else banco[3] if m == 'EUR' else banco[5]
        keyboard.append([InlineKeyboardButton(f"💰 {m} (Depósito: {dep})", callback_data=f"crear_moneda_{m}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_crear")])
    await query.edit_message_text(f"🏦 *{banco[1]}*\n\nSelecciona moneda:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def crear_cuenta_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['crear_moneda'] = query.data.split("_")[2]
    user_states[update.effective_user.id] = {'state': 'crear_pin'}
    await query.edit_message_text("🔐 Escribe un PIN de 4 dígitos:")

# ============ VIAJES ============
async def menu_viajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data.get('jugador_id')
    ubicacion = db.get_ubicacion_jugador(jugador_id)
    if not ubicacion:
        await query.edit_message_text("No tienes ubicación asignada.")
        return
    rutas = db.get_rutas_desde(ubicacion[0])
    if not rutas:
        await query.edit_message_text("No hay rutas disponibles desde tu ubicación.")
        return
    keyboard = []
    for r in rutas:
        keyboard.append([InlineKeyboardButton(f"🚆 {r[12]}", callback_data=f"viaje_destino_{r[2]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="volver_menu")])
    await query.edit_message_text(f"🚆 *VIAJAR DESDE {ubicacion[1]}*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def viaje_transporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    destino_id = int(query.data.split("_")[2])
    context.user_data['viaje_destino'] = destino_id
    jugador_id = context.user_data.get('jugador_id')
    ubicacion = db.get_ubicacion_jugador(jugador_id)
    ruta = db.get_ruta(ubicacion[0], destino_id)
    if not ruta:
        await query.edit_message_text("Ruta no disponible.")
        return
    keyboard = [
        [InlineKeyboardButton(f"🚌 Público - LUM:{ruta[3]:.0f} EUR:{ruta[4]:.2f} ({ruta[5]}min)", callback_data="viaje_publico")],
        [InlineKeyboardButton(f"🚗 Especial - LUM:{ruta[6]:.0f} EUR:{ruta[7]:.2f} ({ruta[8]}min)", callback_data="viaje_especial")],
        [InlineKeyboardButton(f"✈️ Premium - LUM:{ruta[9]:.0f} EUR:{ruta[10]:.2f} ({ruta[11]}min)", callback_data="viaje_premium")],
        [InlineKeyboardButton("🔙 Volver", callback_data="menu_viajes")],
    ]
    await query.edit_message_text("🚆 *TIPO DE TRANSPORTE*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def viaje_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = query.data.split("_")[1]
    jugador_id = context.user_data.get('jugador_id')
    destino_id = context.user_data.get('viaje_destino')
    ok, msg = db.viajar(jugador_id, destino_id, tipo)
    await query.edit_message_text(f"{'✅' if ok else '❌'} {msg}")

# ============ COMANDOS DE COMPRA ============
@login_required
async def comprar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /comprar <cuenta_id>")
        return
    prod_id = context.user_data.get('compra_prod_id')
    if not prod_id:
        await update.message.reply_text("Primero busca un producto")
        return
    ok, msg = db.comprar_producto_tienda(context.user_data['jugador_id'], prod_id, int(context.args[0]))
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def comprar_oferta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /comprar_oferta <cuenta_id> <moneda>")
        return
    ok, msg = db.comprar_item_comprador(context.user_data['jugador_id'], context.user_data.get('compra_oferta_id'), int(context.args[0]), context.args[1].upper())
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def comprar_accion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /compra_accion <cantidad> <cuenta_id>")
        return
    ok, msg = db.comprar_acciones(context.user_data['jugador_id'], context.user_data.get('bolsa_empresa'), int(context.args[0]), int(context.args[1]))
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def comprar_oferta_accion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /comprar_oferta_accion <cantidad> <cuenta_id>")
        return
    ok, msg = db.comprar_oferta_acciones(context.user_data['jugador_id'], context.user_data.get('compra_acc_id'), int(context.args[0]), int(context.args[1]))
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

# ============ ADMIN ============
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ No autorizado")
        return
    if not context.args or context.args[0] != MASTER_PASSWORD:
        await update.message.reply_text("🔐 Usa: /admin_login <contraseña>")
        return
    admin_sessions[update.effective_user.id] = time.time() + 1800
    await menu_admin(update, context)

async def menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 Importar Bancos", callback_data="admin_importar_bancos")],
        [InlineKeyboardButton("📥 Importar Ubicaciones", callback_data="admin_importar_ubi")],
        [InlineKeyboardButton("📥 Importar Rutas", callback_data="admin_importar_rutas")],
        [InlineKeyboardButton("📥 Importar Tiendas", callback_data="admin_importar_tiendas")],
        [InlineKeyboardButton("📥 Importar Productos", callback_data="admin_importar_prod")],
        [InlineKeyboardButton("📤 Exportar Jugadores", callback_data="admin_exportar_jug")],
        [InlineKeyboardButton("📈 Update Bolsa", callback_data="admin_updatebolsa")],
        [InlineKeyboardButton("📦 Dar Item", callback_data="admin_item")],
        [InlineKeyboardButton("💰 Ajustar Efectivo", callback_data="admin_ajustar")],
        [InlineKeyboardButton("💸 Crédito Especial", callback_data="admin_credito")],
        [InlineKeyboardButton("🔑 Generar Código", callback_data="admin_codigo")],
        [InlineKeyboardButton("👥 Ver Jugadores", callback_data="admin_usuarios")],
    ]
    await update.message.reply_text("🔧 *PANEL ADMIN*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ CALLBACK ADMIN (BOTONES CON ACCIÓN DIRECTA) ============
async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data == "admin_importar_bancos":
        await admin_importar_bancos_directo(update, context)
    elif data == "admin_importar_ubi":
        await admin_importar_ubicaciones_directo(update, context)
    elif data == "admin_importar_rutas":
        await admin_importar_rutas_directo(update, context)
    elif data == "admin_importar_tiendas":
        await admin_importar_tiendas_directo(update, context)
    elif data == "admin_importar_prod":
        await query.edit_message_text("Uso: /admin_importar_productos <nombre_tienda>")
    elif data == "admin_exportar_jug":
        await admin_exportar_jugadores_directo(update, context)
    elif data == "admin_codigo":
        user_states[user_id] = {'state': 'admin_codigo'}
        await query.edit_message_text("Escribe: /admin_codigo <codigo>")
    elif data == "admin_updatebolsa":
        user_states[user_id] = {'state': 'admin_updatebolsa'}
        await query.edit_message_text("Escribe: /admin_updatebolsa <empresa_id> <nuevo_valor>")
    elif data == "admin_item":
        user_states[user_id] = {'state': 'admin_item'}
        await query.edit_message_text("Escribe: /admin_item <jugador_id> <nombre> <clasif> <cant> <unidad>")
    elif data == "admin_ajustar":
        user_states[user_id] = {'state': 'admin_ajustar'}
        await query.edit_message_text("Escribe: /admin_ajustar <jugador_id> <moneda> <monto>")
    elif data == "admin_credito":
        user_states[user_id] = {'state': 'admin_credito'}
        await query.edit_message_text("Escribe: /admin_credito <cuenta_id> <monto> <moneda>")
    elif data == "admin_usuarios":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre, efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores")
        usuarios = c.fetchall()
        conn.close()
        texto = "👥 *JUGADORES*\n\n" + "\n".join([f"ID:{u[0]} {u[1]} | LUM:{u[2]:.0f} EUR:{u[3]:.0f} LTR:{u[4]:.0f}" for u in usuarios])
        await query.edit_message_text(texto, parse_mode='Markdown')

# ============ FUNCIONES ADMIN DIRECTAS (BOTONES) ============
async def admin_importar_bancos_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('bancos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        creados, cambios = db.importar_bancos_json(data)
        await update.callback_query.edit_message_text(f"✅ Bancos: {creados} creados, {cambios} tipos de cambio")
    except FileNotFoundError:
        await update.callback_query.edit_message_text("❌ bancos.json no encontrado en GitHub")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Error: {e}")

async def admin_importar_ubicaciones_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('ubicaciones.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        creadas = db.importar_ubicaciones_json(data)
        await update.callback_query.edit_message_text(f"✅ Ubicaciones: {creadas} creadas")
    except FileNotFoundError:
        await update.callback_query.edit_message_text("❌ ubicaciones.json no encontrado en GitHub")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Error: {e}")

async def admin_importar_rutas_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('rutas.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        creadas = db.importar_rutas_json(data)
        await update.callback_query.edit_message_text(f"✅ Rutas: {creadas} creadas")
    except FileNotFoundError:
        await update.callback_query.edit_message_text("❌ rutas.json no encontrado en GitHub")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Error: {e}")

async def admin_importar_tiendas_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open('tiendas.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        creadas = db.importar_tiendas_json(data)
        await update.callback_query.edit_message_text(f"✅ Tiendas: {creadas} creadas")
    except FileNotFoundError:
        await update.callback_query.edit_message_text("❌ tiendas.json no encontrado en GitHub")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Error: {e}")

async def admin_exportar_jugadores_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import sqlite3
        from datetime import datetime
        
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, nombre, efectivo_lum, efectivo_eur, efectivo_ltr, ubicacion_id FROM jugadores")
        jugadores = [dict(row) for row in c.fetchall()]
        conn.close()
        
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jugadores_{fecha}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({"jugadores": jugadores}, f, indent=2, ensure_ascii=False)
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=filename,
                caption=f"👥 {len(jugadores)} jugadores exportados"
            )
        
        os.remove(filename)
        await update.callback_query.edit_message_text(f"✅ {len(jugadores)} jugadores exportados. Revisa el archivo enviado.")
    
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Error: {e}")

# ============ MAIN ============
if __name__ == "__main__":
    db.init_db()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("admin_login", admin_login))
    app.add_handler(CommandHandler("comprar", comprar_cmd))
    app.add_handler(CommandHandler("comprar_oferta", comprar_oferta_cmd))
    app.add_handler(CommandHandler("compra_accion", comprar_accion_cmd))
    app.add_handler(CommandHandler("comprar_oferta_accion", comprar_oferta_accion_cmd))
    app.add_handler(CommandHandler("admin_importar_bancos", admin_importar_bancos_directo))
    app.add_handler(CommandHandler("admin_importar_ubicaciones", admin_importar_ubicaciones_directo))
    app.add_handler(CommandHandler("admin_importar_rutas", admin_importar_rutas_directo))
    app.add_handler(CommandHandler("admin_importar_tiendas", admin_importar_tiendas_directo))
    app.add_handler(CommandHandler("admin_exportar_jugadores", admin_exportar_jugadores_directo))
    app.add_handler(CallbackQueryHandler(admin_button, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot iniciado...")
    app.run_polling()
