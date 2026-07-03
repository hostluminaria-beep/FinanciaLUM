from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import TOKEN, ADMIN_ID, MASTER_PASSWORD
import database as db
import json
import logging

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
            await update.message.reply_text("❌ Debes iniciar sesión primero. Usa /start")
            return
        context.user_data['jugador_id'] = user_sessions[user_id]
        return await func(update, context, *args, **kwargs)
    return wrapper

def admin_required(func):
    async def wrapper(update, context, *args, **kwargs):
        import time
        user_id = update.effective_user.id
        if user_id != ADMIN_ID or user_id not in admin_sessions or time.time() > admin_sessions[user_id]:
            await update.message.reply_text("❌ Acceso denegado. Usa /admin_login <contraseña>")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ============ INICIO ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔑 Iniciar Sesión", callback_data="login")],
        [InlineKeyboardButton("📝 Registrarse", callback_data="registro")],
    ]
    await update.message.reply_text(
        "🔐 *SISTEMA ECONÓMICO DE LUMINARIA*\n\n"
        "Este es el Sistema Oficial para los flujos financieros del Juego de Rol de Luminaria. "
        "Su uso implica la aceptación plena de los Lineamientos Administrativos vigentes.\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============ REGISTRO GUIADO ============
async def registro_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[update.effective_user.id] = {'state': 'esperando_codigo'}
    await query.edit_message_text(
        "📝 *REGISTRO DE JUGADOR*\n\n"
        "Paso 1/3: Introduce tu código de invitación.\n\n"
        "Escribe el código que te ha proporcionado el administrador:",
        parse_mode='Markdown'
    )

async def handle_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get('state')
    
    if state == 'esperando_codigo':
        codigo = update.message.text.strip()
        if db.validar_codigo(codigo):
            user_states[user_id] = {'state': 'esperando_nombre', 'codigo': codigo}
            await update.message.reply_text(
                "✅ Código válido.\n\n"
                "Paso 2/3: Elige tu nombre de jugador:"
            )
        else:
            await update.message.reply_text("❌ Código inválido o ya usado. Intenta de nuevo:")
    
    elif state == 'esperando_nombre':
        nombre = update.message.text.strip()
        if db.get_jugador_by_nombre(nombre):
            await update.message.reply_text("❌ Ese nombre ya existe. Elige otro:")
        else:
            user_states[user_id]['nombre'] = nombre
            user_states[user_id]['state'] = 'esperando_password'
            await update.message.reply_text(
                "✅ Nombre disponible.\n\n"
                "Paso 3/3: Elige tu contraseña:"
            )
    
    elif state == 'esperando_password':
        password = update.message.text.strip()
        nombre = user_states[user_id]['nombre']
        db.registrar_jugador(nombre, password)
        user_states.pop(user_id, None)
        await update.message.reply_text(
            f"✅ *¡Registro completado!*\n\n"
            f"Jugador: {nombre}\n"
            f"Efectivo inicial: 5000 LUM\n\n"
            f"Usa /login {nombre} <contraseña> para acceder",
            parse_mode='Markdown'
        )

# ============ LOGIN ============
async def login_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[update.effective_user.id] = {'state': 'login_nombre'}
    await query.edit_message_text(
        "🔑 *INICIAR SESIÓN*\n\n"
        "Introduce tu nombre de jugador:",
        parse_mode='Markdown'
    )

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get('state')
    
    if state == 'login_nombre':
        nombre = update.message.text.strip()
        jugador = db.get_jugador_by_nombre(nombre)
        if jugador:
            user_states[user_id] = {'state': 'login_password', 'jugador': jugador}
            await update.message.reply_text("Introduce tu contraseña:")
        else:
            await update.message.reply_text("❌ Jugador no encontrado. Intenta de nuevo:")
    
    elif state == 'login_password':
        password = update.message.text.strip()
        jugador = user_states[user_id]['jugador']
        if db.verificar_login(jugador[1], password):
            user_sessions[user_id] = jugador[0]
            user_states.pop(user_id, None)
            await menu_principal(update, context)
        else:
            await update.message.reply_text("❌ Contraseña incorrecta. Intenta de nuevo:")

# ============ MENÚ PRINCIPAL ============
async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💵 Activos Financieros", callback_data="menu_financiero")],
        [InlineKeyboardButton("📦 Inventario y Tiendas", callback_data="menu_inventario")],
        [InlineKeyboardButton("📈 Mercado de Valores", callback_data="menu_bolsa")],
        [InlineKeyboardButton("📊 Resumen Total", callback_data="menu_resumen")],
        [InlineKeyboardButton("📋 Historial", callback_data="menu_historial")],
    ]
    await update.message.reply_text(
        "🏦 *MENÚ PRINCIPAL*\n\nSelecciona una sección:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

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
        [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")],
    ]
    await query.edit_message_text(
        "💵 *ACTIVOS FINANCIEROS*\n\nSelecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============ CREAR CUENTA GUIADO ============
async def crear_cuenta_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data['jugador_id']
    bancos = db.get_bancos()
    keyboard = []
    for b in bancos:
        monedas = json.loads(b[2])
        keyboard.append([InlineKeyboardButton(f"{b[1]} (Depósito: {b[3]} {monedas[0]}) - {', '.join(monedas)}", callback_data=f"crear_banco_{b[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text(
        "🏦 *CREAR CUENTA BANCARIA*\n\n"
        "Selecciona un banco. Recuerda que cada cuenta es de una sola moneda "
        "y requiere un depósito inicial:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def crear_cuenta_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banco_id = int(query.data.split("_")[2])
    banco = db.get_banco_by_id(banco_id)
    monedas = json.loads(banco[2])
    context.user_data['crear_banco_id'] = banco_id
    keyboard = []
    for m in monedas:
        keyboard.append([InlineKeyboardButton(f"💰 {m}", callback_data=f"crear_moneda_{m}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_crear")])
    await query.edit_message_text(
        f"🏦 *{banco[1]}*\n\n"
        f"Depósito inicial: {banco[3]}\n"
        f"Selecciona la moneda de la cuenta:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def crear_cuenta_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    moneda = query.data.split("_")[2]
    context.user_data['crear_moneda'] = moneda
    user_states[update.effective_user.id] = {'state': 'crear_pin'}
    await query.edit_message_text(
        f"🔐 *CREAR CUENTA EN {moneda}*\n\n"
        f"Escribe un PIN de 4 dígitos para tu cuenta:",
        parse_mode='Markdown'
    )

async def handle_crear_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get('state') == 'crear_pin':
        pin = update.message.text.strip()
        jugador_id = context.user_data['jugador_id']
        banco_id = context.user_data['crear_banco_id']
        moneda = context.user_data['crear_moneda']
        
        # Verificar efectivo suficiente
        banco = db.get_banco_by_id(banco_id)
        efectivo = db.get_efectivo(jugador_id)
        idx = {'LUM': 0, 'EUR': 1, 'LTR': 2}
        if efectivo[idx[moneda]] < banco[3]:
            await update.message.reply_text(f"❌ No tienes suficiente efectivo en {moneda} para el depósito inicial de {banco[3]}")
            user_states.pop(user_id, None)
            return
        
        db.crear_cuenta(jugador_id, banco_id, moneda, pin)
        user_states.pop(user_id, None)
        await update.message.reply_text(
            f"✅ *Cuenta creada con éxito*\n\n"
            f"Banco: {banco[1]}\n"
            f"Moneda: {moneda}\n"
            f"Depósito inicial: {banco[3]} {moneda}\n"
            f"PIN: {pin}\n\n"
            f"Recuerda tu PIN para transferencias.",
            parse_mode='Markdown'
        )

# ============ VER CUENTAS ============
async def ver_cuentas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data['jugador_id']
    cuentas = db.get_cuentas(jugador_id)
    if not cuentas:
        await query.edit_message_text("No tienes cuentas bancarias. Crea una primero.")
        return
    texto = "🏦 *MIS CUENTAS*\n\n"
    for c in cuentas:
        texto += f"ID: {c[0]} | {c[1]} | {c[2]} | Saldo: {c[3]:.2f}\n"
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ EFECTIVO ============
async def ver_efectivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data['jugador_id']
    e = db.get_efectivo(jugador_id)
    texto = f"💵 *EFECTIVO*\n\nLUM: {e[0]:.2f}\nEUR: {e[1]:.2f}\nLTR: {e[2]:.2f}"
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ RESUMEN TOTAL ============
async def ver_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data['jugador_id']
    lum, eur, ltr, acciones = db.get_total_activos(jugador_id)
    # Conversión aproximada
    total_lum = lum + (eur * 1.10) + (ltr * 0.80) + acciones
    total_eur = (lum * 0.90) + eur + (ltr * 0.95) + (acciones * 0.90)
    texto = (
        f"📊 *RESUMEN DE ACTIVOS*\n\n"
        f"💰 Efectivo + Cuentas:\n"
        f"   LUM: {lum:,.2f}\n"
        f"   EUR: {eur:,.2f}\n"
        f"   LTR: {ltr:,.2f}\n"
        f"📈 Acciones: {acciones:,.2f} LUM\n\n"
        f"💎 Total estimado:\n"
        f"   ~{total_lum:,.2f} LUM\n"
        f"   ~{total_eur:,.2f} EUR"
    )
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ TRANSFERIR ============
async def transferir_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[update.effective_user.id] = {'state': 'transf_origen'}
    jugador_id = context.user_data['jugador_id']
    cuentas = db.get_cuentas(jugador_id)
    keyboard = []
    for c in cuentas:
        keyboard.append([InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"transf_origen_{c[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text(
        "💱 *TRANSFERENCIA*\n\nSelecciona la cuenta de origen:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def transferir_destino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cuenta_origen = int(query.data.split("_")[2])
    context.user_data['transf_origen'] = cuenta_origen
    user_states[update.effective_user.id] = {'state': 'transf_destino'}
    await query.edit_message_text(
        f"💱 *TRANSFERENCIA*\n\nCuenta origen: {cuenta_origen}\n\n"
        f"Escribe el ID de la cuenta destino:",
        parse_mode='Markdown'
    )

async def handle_transferir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get('state')
    jugador_id = context.user_data['jugador_id']
    
    if state == 'transf_destino':
        destino = int(update.message.text.strip())
        user_states[user_id] = {'state': 'transf_monto', 'destino': destino}
        await update.message.reply_text("Escribe el monto a transferir:")
    
    elif state == 'transf_monto':
        monto = float(update.message.text.strip())
        user_states[user_id]['monto'] = monto
        user_states[user_id]['state'] = 'transf_pin'
        await update.message.reply_text("Escribe el PIN de tu cuenta origen:")
    
    elif state == 'transf_pin':
        pin = update.message.text.strip()
        origen = context.user_data['transf_origen']
        destino = user_states[user_id]['destino']
        monto = user_states[user_id]['monto']
        ok, msg = db.transferir(jugador_id, origen, destino, monto, pin)
        user_states.pop(user_id, None)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

# ============ CONVERTIR MONEDA ============
async def convertir_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data['jugador_id']
    cuentas = db.get_cuentas(jugador_id)
    keyboard = []
    for c in cuentas:
        keyboard.append([InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"conv_origen_{c[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text(
        "🔄 *CONVERTIR MONEDA*\n\nSelecciona la cuenta de origen:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def convertir_destino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cuenta_origen = int(query.data.split("_")[2])
    context.user_data['conv_origen'] = cuenta_origen
    jugador_id = context.user_data['jugador_id']
    cuentas = db.get_cuentas(jugador_id)
    keyboard = []
    for c in cuentas:
        if c[0] != cuenta_origen:
            keyboard.append([InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"conv_destino_{c[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_convertir")])
    await query.edit_message_text(
        "🔄 *CONVERTIR MONEDA*\n\nSelecciona la cuenta de destino:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def convertir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cuenta_destino = int(query.data.split("_")[2])
    context.user_data['conv_destino'] = cuenta_destino
    user_states[update.effective_user.id] = {'state': 'conv_monto'}
    await query.edit_message_text(
        "🔄 *CONVERTIR MONEDA*\n\nEscribe el monto a convertir:",
        parse_mode='Markdown'
    )

async def handle_convertir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get('state') == 'conv_monto':
        monto = float(update.message.text.strip())
        origen = context.user_data['conv_origen']
        destino = context.user_data['conv_destino']
        ok, msg = db.convertir_moneda(origen, destino, monto)
        user_states.pop(user_id, None)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

# ============ TIPOS DE CAMBIO ============
async def ver_tasas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bancos = db.get_bancos()
    keyboard = []
    for b in bancos:
        keyboard.append([InlineKeyboardButton(b[1], callback_data=f"tasas_banco_{b[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text(
        "📊 *TIPOS DE CAMBIO*\n\nSelecciona un banco:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def mostrar_tasas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banco_id = int(query.data.split("_")[2])
    cambios = db.get_tipos_cambio(banco_id)
    if not cambios:
        await query.edit_message_text("No hay tipos de cambio para este banco.")
        return
    texto = "💱 *TIPOS DE CAMBIO*\n\n"
    for c in cambios:
        texto += f"{c[0]} → {c[1]}: Compra {c[2]:.4f} | Venta {c[3]:.4f}\n"
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="fin_tasas")]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ DEPOSITAR ============
async def depositar_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    jugador_id = context.user_data['jugador_id']
    cuentas = db.get_cuentas(jugador_id)
    keyboard = []
    for c in cuentas:
        keyboard.append([InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"dep_cuenta_{c[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text(
        "📥 *DEPOSITAR EFECTIVO*\n\nSelecciona la cuenta destino:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def depositar_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cuenta_id = int(query.data.split("_")[2])
    context.user_data['dep_cuenta'] = cuenta_id
    user_states[update.effective_user.id] = {'state': 'dep_monto'}
    await query.edit_message_text(
        "📥 *DEPOSITAR EFECTIVO*\n\nEscribe el monto y la moneda (ej: 100 LUM):",
        parse_mode='Markdown'
    )

async def handle_depositar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get('state') == 'dep_monto':
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text("Formato incorrecto. Usa: monto MONEDA (ej: 100 LUM)")
            return
        monto = float(parts[0])
        moneda = parts[1].upper()
        cuenta_id = context.user_data['dep_cuenta']
        jugador_id = context.user_data['jugador_id']
        ok, msg = db.depositar_efectivo(jugador_id, moneda, monto, cuenta_id)
        user_states.pop(user_id, None)
        await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

# ============ ADMIN ============
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import time
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
        [InlineKeyboardButton("🏦 Gestionar Bancos", callback_data="admin_bancos")],
        [InlineKeyboardButton("🏪 Gestionar Tiendas", callback_data="admin_tiendas")],
        [InlineKeyboardButton("🛒 Gestionar Productos", callback_data="admin_productos")],
        [InlineKeyboardButton("📈 Actualizar Bolsa", callback_data="admin_bolsa")],
        [InlineKeyboardButton("📦 Dar Item a Jugador", callback_data="admin_item")],
        [InlineKeyboardButton("💰 Ajustar Efectivo", callback_data="admin_ajustar")],
        [InlineKeyboardButton("💸 Crédito Especial", callback_data="admin_credito")],
        [InlineKeyboardButton("🔑 Generar Código", callback_data="admin_codigo")],
        [InlineKeyboardButton("👥 Ver Jugadores", callback_data="admin_usuarios")],
        [InlineKeyboardButton("🔄 Backup BD", callback_data="admin_backup")],
    ]
    await update.message.reply_text(
        "🔧 *PANEL DE ADMINISTRACIÓN*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============ CALLBACK PRINCIPAL ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "login":
        await login_guiado(update, context)
    elif data == "registro":
        await registro_guiado(update, context)
    elif data == "volver_menu":
        await menu_principal(update, context)
    elif data == "menu_financiero":
        await menu_financiero(update, context)
    elif data == "fin_cuentas":
        await ver_cuentas(update, context)
    elif data == "fin_crear":
        await crear_cuenta_guiado(update, context)
    elif data == "fin_efectivo":
        await ver_efectivo(update, context)
    elif data == "fin_transferir":
        await transferir_guiado(update, context)
    elif data == "fin_convertir":
        await convertir_guiado(update, context)
    elif data == "fin_tasas":
        await ver_tasas(update, context)
    elif data == "fin_depositar":
        await depositar_guiado(update, context)
    elif data == "menu_resumen":
        await ver_resumen(update, context)
    elif data.startswith("crear_banco_"):
        await crear_cuenta_moneda(update, context)
    elif data.startswith("crear_moneda_"):
        await crear_cuenta_pin(update, context)
    elif data.startswith("transf_origen_"):
        await transferir_destino(update, context)
    elif data.startswith("conv_origen_"):
        await convertir_destino(update, context)
    elif data.startswith("conv_destino_"):
        await convertir_monto(update, context)
    elif data.startswith("tasas_banco_"):
        await mostrar_tasas(update, context)
    elif data.startswith("dep_cuenta_"):
        await depositar_monto(update, context)
    elif data == "admin_codigo":
        await query.edit_message_text("Usa: /admin_codigo <codigo>")
    elif data == "admin_backup":
        import shutil
        from datetime import datetime
        fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(db.DB_PATH, f"backup_{fecha}.db")
        await query.edit_message_text(f"✅ Backup: backup_{fecha}.db")
    elif data == "admin_usuarios":
        import sqlite3
        conn = sqlite3.connect(db.DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, nombre, efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores")
        usuarios = c.fetchall()
        conn.close()
        texto = "👥 *JUGADORES*\n\n"
        for u in usuarios:
            texto += f"ID:{u[0]} {u[1]} | LUM:{u[2]:.0f} EUR:{u[3]:.0f} LTR:{u[4]:.0f}\n"
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "admin_bolsa":
        empresas = db.get_empresas()
        texto = "📈 *EMPRESAS*\n\n"
        for e in empresas:
            texto += f"ID:{e[0]} {e[1]} | Valor:{e[3]:.2f} | Disp:{e[4]}\n"
        texto += "\nActualizar: /admin_bolsa <id> <valor>"
        await query.edit_message_text(texto, parse_mode='Markdown')

@admin_required
async def admin_codigo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /admin_codigo <codigo>")
        return
    if db.generar_codigo(context.args[0]):
        await update.message.reply_text(f"✅ Código: {context.args[0]}")
    else:
        await update.message.reply_text("❌ Ya existe")

@admin_required
async def admin_bolsa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /admin_bolsa <empresa_id> <nuevo_valor>")
        return
    db.actualizar_valor_empresa(int(context.args[0]), float(context.args[1]))
    await update.message.reply_text("✅ Actualizado")

@admin_required
async def admin_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5:
        await update.message.reply_text("Uso: /admin_item <jugador_id> <nombre> <clasif> <cant> <unidad>")
        return
    db.agregar_inventario(int(context.args[0]), context.args[1], context.args[2], float(context.args[3]), context.args[4])
    await update.message.reply_text("✅ Item entregado")

@admin_required
async def admin_ajustar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 4:
        await update.message.reply_text("Uso: /admin_ajustar <jugador_id> <moneda> <monto>")
        return
    jugador_id = int(context.args[0])
    moneda = context.args[1].upper()
    monto = float(context.args[2])
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE jugadores SET efectivo_{moneda.lower()} = efectivo_{moneda.lower()} + ? WHERE id = ?", (monto, jugador_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Ajustado {monto} {moneda} a jugador {jugador_id}")

@admin_required
async def admin_credito_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Uso: /admin_credito <cuenta_id> <monto> <moneda>")
        return
    cuenta_id = int(context.args[0])
    monto = float(context.args[1])
    moneda = context.args[2].upper()
    cuenta = db.get_cuenta_by_id(cuenta_id)
    if not cuenta:
        await update.message.reply_text("❌ Cuenta no encontrada")
        return
    db.actualizar_saldo_cuenta(cuenta_id, monto)
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Crédito Especial', ?, ?, 'Crédito administrativo')",
              (cuenta[1], cuenta_id, monto, moneda))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Crédito de {monto} {moneda} a cuenta {cuenta_id}")

# ============ MAIN ============
if __name__ == "__main__":
    db.init_db()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin_login", admin_login))
    app.add_handler(CommandHandler("admin_codigo", admin_codigo_cmd))
    app.add_handler(CommandHandler("admin_bolsa", admin_bolsa_cmd))
    app.add_handler(CommandHandler("admin_item", admin_item_cmd))
    app.add_handler(CommandHandler("admin_ajustar", admin_ajustar_cmd))
    app.add_handler(CommandHandler("admin_credito", admin_credito_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registro))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_crear_pin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transferir))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_convertir))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_depositar))
    
    print("🤖 Bot iniciado...")
    app.run_polling()