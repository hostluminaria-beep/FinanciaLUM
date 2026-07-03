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
            await update.message.reply_text("❌ Debes iniciar sesión primero. Usa /start")
            return
        context.user_data['jugador_id'] = user_sessions[user_id]
        return await func(update, context, *args, **kwargs)
    return wrapper

def admin_required(func):
    async def wrapper(update, context, *args, **kwargs):
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
        "📝 *REGISTRO DE JUGADOR*\n\nPaso 1/3: Introduce tu código de invitación:",
        parse_mode='Markdown'
    )

async def login_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[update.effective_user.id] = {'state': 'login_nombre'}
    await query.edit_message_text("🔑 *INICIAR SESIÓN*\n\nIntroduce tu nombre de jugador:", parse_mode='Markdown')

# ============ MANEJADOR DE MENSAJES (REGISTRO Y LOGIN) ============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {}).get('state')
    
    if state == 'esperando_codigo':
        if db.validar_codigo(text):
            user_states[user_id] = {'state': 'esperando_nombre'}
            await update.message.reply_text("✅ Código válido.\n\nPaso 2/3: Elige tu nombre de jugador:")
        else:
            await update.message.reply_text("❌ Código inválido o ya usado. Intenta de nuevo:")
    
    elif state == 'esperando_nombre':
        if db.get_jugador_by_nombre(text):
            await update.message.reply_text("❌ Ese nombre ya existe. Elige otro:")
        else:
            user_states[user_id]['nombre'] = text
            user_states[user_id]['state'] = 'esperando_password'
            await update.message.reply_text("✅ Nombre disponible.\n\nPaso 3/3: Elige tu contraseña:")
    
    elif state == 'esperando_password':
        nombre = user_states[user_id]['nombre']
        db.registrar_jugador(nombre, text)
        user_states.pop(user_id, None)
        await update.message.reply_text(
            f"✅ *¡Registro completado!*\n\nJugador: {nombre}\nEfectivo inicial: 5000 LUM\n\nUsa /start para iniciar sesión",
            parse_mode='Markdown'
        )
    
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
            await update.message.reply_text("❌ No se encontraron productos. Busca de nuevo:")
            return
        keyboard = []
        for r in resultados[:20]:
            monedas = json.loads(r[7])
            keyboard.append([InlineKeyboardButton(
                f"🏪 {r[1]} | {r[2]} ({r[3]}) | LUM:{r[4]:.0f} EUR:{r[5]:.0f} LTR:{r[6]:.0f}",
                callback_data=f"comprar_prod_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text(
            f"🛒 *Resultados para \"{text}\"*\n\nSelecciona un producto para comprar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif state == 'buscar_oferta':
        resultados = db.buscar_ofertas(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron ofertas. Busca de nuevo:")
            return
        keyboard = []
        for r in resultados[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📦 {r[1]} ({r[2]}) | LUM:{r[3]:.0f} EUR:{r[4]:.0f} LTR:{r[5]:.0f} | Vendedor:{r[6]}",
                callback_data=f"comprar_oferta_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text(
            f"📦 *Ofertas para \"{text}\"*\n\nSelecciona una oferta para comprar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif state == 'buscar_acciones':
        resultados = db.buscar_ofertas_acciones(text)
        if not resultados:
            await update.message.reply_text("❌ No se encontraron acciones. Busca de nuevo:")
            return
        keyboard = []
        for r in resultados[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📈 {r[1]} | Cant:{r[2]} | Precio:{r[3]:.2f} | Vendedor:{r[4]}",
                callback_data=f"comprar_accion_{r[0]}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="volver_menu")])
        user_states.pop(user_id, None)
        await update.message.reply_text(
            f"📈 *Acciones en venta para \"{text}\"*\n\nSelecciona para comprar:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ============ MENÚ PRINCIPAL ============
async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💵 Activos Financieros", callback_data="menu_financiero")],
        [InlineKeyboardButton("🔍 Buscar en Tiendas", callback_data="buscar_tienda")],
        [InlineKeyboardButton("📦 Buscar Ofertas", callback_data="buscar_oferta")],
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
    await query.edit_message_text("💵 *ACTIVOS FINANCIEROS*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ CREAR CUENTA ============
async def crear_cuenta_guiado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bancos = db.get_bancos()
    keyboard = []
    for b in bancos:
        monedas = json.loads(b[2])
        keyboard.append([InlineKeyboardButton(f"{b[1]} (Dep:{b[3]} {monedas[0]}) - {', '.join(monedas)}", callback_data=f"crear_banco_{b[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
    await query.edit_message_text("🏦 *CREAR CUENTA*\n\nSelecciona un banco:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def crear_cuenta_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    banco_id = int(query.data.split("_")[2])
    banco = db.get_banco_by_id(banco_id)
    context.user_data['crear_banco_id'] = banco_id
    monedas = json.loads(banco[2])
    keyboard = [[InlineKeyboardButton(f"💰 {m}", callback_data=f"crear_moneda_{m}")] for m in monedas]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="fin_crear")])
    await query.edit_message_text(f"🏦 *{banco[1]}*\nDepósito inicial: {banco[3]}\nSelecciona moneda:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def crear_cuenta_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['crear_moneda'] = query.data.split("_")[2]
    user_states[update.effective_user.id] = {'state': 'crear_pin'}
    await query.edit_message_text("🔐 Escribe un PIN de 4 dígitos para tu cuenta:", parse_mode='Markdown')

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
        await query.edit_message_text("🔍 *BUSCAR PRODUCTO*\n\nEscribe el nombre del producto que buscas:", parse_mode='Markdown')
    elif data == "buscar_oferta":
        user_states[user_id] = {'state': 'buscar_oferta'}
        await query.edit_message_text("📦 *BUSCAR OFERTAS*\n\nEscribe el nombre del item que buscas:", parse_mode='Markdown')
    elif data == "menu_bolsa":
        keyboard = [
            [InlineKeyboardButton("📊 Ver Empresas", callback_data="bolsa_empresas")],
            [InlineKeyboardButton("🔍 Buscar Acciones en Venta", callback_data="buscar_acciones")],
            [InlineKeyboardButton("📋 Mis Acciones", callback_data="bolsa_mis")],
            [InlineKeyboardButton("🔙 Volver", callback_data="volver_menu")],
        ]
        await query.edit_message_text("📈 *MERCADO DE VALORES*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "buscar_acciones":
        user_states[user_id] = {'state': 'buscar_acciones'}
        await query.edit_message_text("📈 *BUSCAR ACCIONES*\n\nEscribe el nombre de la empresa:", parse_mode='Markdown')
    elif data == "bolsa_empresas":
        empresas = db.get_empresas()
        keyboard = [[InlineKeyboardButton(f"{e[1]} - {e[3]:.2f} LUM ({e[4]} disp.)", callback_data=f"bolsa_comp_{e[0]}")] for e in empresas]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_bolsa")])
        await query.edit_message_text("📈 *EMPRESAS*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("bolsa_comp_"):
        context.user_data['bolsa_empresa'] = int(data.split("_")[2])
        await query.edit_message_text("Escribe: /compra_accion <cantidad> <cuenta_id>")
    elif data == "bolsa_mis":
        acciones = db.get_acciones_jugador(jugador_id)
        texto = "📋 *MIS ACCIONES*\n\n" + ("\n".join([f"ID:{a[0]} {a[1]} | Cant:{a[2]} | Valor:{a[3]:.2f} | Vendiendo:{'Sí' if a[5] else 'No'}" for a in acciones]) if acciones else "No tienes acciones.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data.startswith("crear_banco_"):
        await crear_cuenta_moneda(update, context)
    elif data.startswith("crear_moneda_"):
        await crear_cuenta_pin(update, context)
    elif data.startswith("comprar_prod_"):
        prod_id = int(data.split("_")[2])
        context.user_data['compra_prod_id'] = prod_id
        await query.edit_message_text("Escribe: /comprar <cuenta_id>")
    elif data.startswith("comprar_oferta_"):
        oferta_id = int(data.split("_")[2])
        context.user_data['compra_oferta_id'] = oferta_id
        await query.edit_message_text("Escribe: /comprar_oferta <cuenta_id> <moneda>")
    elif data.startswith("comprar_accion_"):
        acc_id = int(data.split("_")[2])
        context.user_data['compra_acc_id'] = acc_id
        await query.edit_message_text("Escribe: /comprar_oferta_accion <cantidad> <cuenta_id>")
    elif data == "menu_historial":
        hist = db.get_historial_financiero(jugador_id)
        texto = "📋 *HISTORIAL*\n\n" + ("\n".join([f"{t[5][:16]} | {t[0]} | {t[1]} | {t[2]:.2f} {t[3]} | {t[4]}" for t in hist]) if hist else "Sin movimientos.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "fin_tasas":
        bancos = db.get_bancos()
        keyboard = [[InlineKeyboardButton(b[1], callback_data=f"tasas_{b[0]}")] for b in bancos]
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_financiero")])
        await query.edit_message_text("📊 *TIPOS DE CAMBIO*\n\nSelecciona un banco:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("tasas_"):
        banco_id = int(data.split("_")[1])
        cambios = db.get_tipos_cambio(banco_id)
        texto = "💱 *TIPOS DE CAMBIO*\n\n" + ("\n".join([f"{c[0]}→{c[1]}: C:{c[2]:.4f} V:{c[3]:.4f}" for c in cambios]) if cambios else "Sin tipos definidos.")
        await query.edit_message_text(texto, parse_mode='Markdown')
    elif data == "fin_transferir":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"transf_{c[0]}")] for c in cuentas]
        await query.edit_message_text("💱 *TRANSFERIR*\n\nSelecciona cuenta origen:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("transf_"):
        context.user_data['transf_origen'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'transf_destino'}
        await query.edit_message_text("Escribe el ID de la cuenta destino:")
    elif data == "fin_convertir":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"conv_{c[0]}")] for c in cuentas]
        await query.edit_message_text("🔄 *CONVERTIR*\n\nSelecciona cuenta origen:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("conv_"):
        context.user_data['conv_origen'] = int(data.split("_")[1])
        cuentas = [c for c in db.get_cuentas(jugador_id) if c[0] != int(data.split("_")[1])]
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"convd_{c[0]}")] for c in cuentas]
        await query.edit_message_text("🔄 *CONVERTIR*\n\nSelecciona cuenta destino:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("convd_"):
        context.user_data['conv_destino'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'conv_monto'}
        await query.edit_message_text("Escribe el monto a convertir:")
    elif data == "fin_depositar":
        cuentas = db.get_cuentas(jugador_id)
        keyboard = [[InlineKeyboardButton(f"ID:{c[0]} {c[1]} {c[2]} {c[3]:.2f}", callback_data=f"dep_{c[0]}")] for c in cuentas]
        await query.edit_message_text("📥 *DEPOSITAR*\n\nSelecciona cuenta:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data.startswith("dep_"):
        context.user_data['dep_cuenta'] = int(data.split("_")[1])
        user_states[user_id] = {'state': 'dep_monto'}
        await query.edit_message_text("Escribe: monto MONEDA (ej: 100 LUM)")

# ============ COMANDOS ============
@login_required
async def comprar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /comprar <cuenta_id>")
        return
    prod_id = context.user_data.get('compra_prod_id')
    if not prod_id:
        await update.message.reply_text("Primero busca un producto con el menú")
        return
    ok, msg = db.comprar_producto_tienda(context.user_data['jugador_id'], prod_id, int(context.args[0]))
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def comprar_oferta_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /comprar_oferta <cuenta_id> <moneda>")
        return
    oferta_id = context.user_data.get('compra_oferta_id')
    ok, msg = db.comprar_item_comprador(context.user_data['jugador_id'], oferta_id, int(context.args[0]), context.args[1].upper())
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def comprar_accion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /compra_accion <cantidad> <cuenta_id>")
        return
    emp_id = context.user_data.get('bolsa_empresa')
    ok, msg = db.comprar_acciones(context.user_data['jugador_id'], emp_id, int(context.args[0]), int(context.args[1]))
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def comprar_oferta_accion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /comprar_oferta_accion <cantidad> <cuenta_id>")
        return
    acc_id = context.user_data.get('compra_acc_id')
    ok, msg = db.comprar_oferta_acciones(context.user_data['jugador_id'], acc_id, int(context.args[0]), int(context.args[1]))
    await update.message.reply_text(f"{'✅' if ok else '❌'} {msg}")

@login_required
async def vender_accion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Uso: /vender_accion <accion_id> <cantidad> <precio>")
        return
    ok, msg = db.vender_acciones(context.user_data['jugador_id'], int(context.args[0]), int(context.args[1]), float(context.args[2]))
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
    keyboard = [
        [InlineKeyboardButton("🏦 Add Banco", callback_data="admin_addbanco")],
        [InlineKeyboardButton("💱 Add Tipo Cambio", callback_data="admin_addcambio")],
        [InlineKeyboardButton("🏪 Add Tienda", callback_data="admin_addtienda")],
        [InlineKeyboardButton("🛒 Add Producto", callback_data="admin_addproducto")],
        [InlineKeyboardButton("📈 Add Empresa", callback_data="admin_addempresa")],
        [InlineKeyboardButton("📈 Update Bolsa", callback_data="admin_updatebolsa")],
        [InlineKeyboardButton("📦 Dar Item", callback_data="admin_item")],
        [InlineKeyboardButton("💰 Ajustar Efectivo", callback_data="admin_ajustar")],
        [InlineKeyboardButton("💸 Crédito Especial", callback_data="admin_credito")],
        [InlineKeyboardButton("🔑 Generar Código", callback_data="admin_codigo")],
        [InlineKeyboardButton("👥 Ver Jugadores", callback_data="admin_usuarios")],
    ]
    await update.message.reply_text("🔧 *PANEL ADMIN*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============ CALLBACK ADMIN ============
async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    if data == "admin_codigo":
        user_states[user_id] = {'state': 'admin_codigo'}
        await query.edit_message_text("Escribe el código: /admin_codigo <codigo>")
    elif data == "admin_addbanco":
        user_states[user_id] = {'state': 'admin_banco'}
        await query.edit_message_text("Escribe: /admin_addbanco <nombre> <monedas_json> <deposito>\nEj: /admin_addbanco Caixa '[\"EUR\",\"LUM\"]' 100")
    elif data == "admin_addcambio":
        user_states[user_id] = {'state': 'admin_cambio'}
        await query.edit_message_text("Escribe: /admin_addcambio <banco_id> <de> <a> <compra> <venta>")
    elif data == "admin_addtienda":
        user_states[user_id] = {'state': 'admin_tienda'}
        await query.edit_message_text("Escribe: /admin_addtienda <nombre> <tipo> <plum> <peur> <pltr> <monedas_json>")
    elif data == "admin_addproducto":
        user_states[user_id] = {'state': 'admin_producto'}
        await query.edit_message_text("Escribe: /admin_addproducto <tienda_id> <nombre> <clasif> <plum> <peur> <pltr> <monedas_json>")
    elif data == "admin_addempresa":
        user_states[user_id] = {'state': 'admin_empresa'}
        await query.edit_message_text("Escribe: /admin_addempresa <nombre> <sector> <valor> <totales> <disp>")
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

# ============ COMANDOS ADMIN ============
@admin_required
async def admin_codigo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /admin_codigo <codigo>")
        return
    db.generar_codigo(context.args[0])
    await update.message.reply_text(f"✅ Código: {context.args[0]}")

@admin_required
async def admin_addbanco_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Uso: /admin_addbanco <nombre> <monedas_json> <deposito>")
        return
    db.add_banco(context.args[0], json.loads(context.args[1]), float(context.args[2]))
    await update.message.reply_text("✅ Banco creado")

@admin_required
async def admin_addcambio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5:
        await update.message.reply_text("Uso: /admin_addcambio <banco_id> <de> <a> <compra> <venta>")
        return
    db.add_tipo_cambio(int(context.args[0]), context.args[1], context.args[2], float(context.args[3]), float(context.args[4]))
    await update.message.reply_text("✅ Tipo de cambio añadido")

@admin_required
async def admin_addtienda_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 6:
        await update.message.reply_text("Uso: /admin_addtienda <nombre> <tipo> <plum> <peur> <pltr> <monedas_json>")
        return
    db.add_tienda(context.args[0], context.args[1], float(context.args[2]), float(context.args[3]), float(context.args[4]), json.loads(context.args[5]))
    await update.message.reply_text("✅ Tienda creada")

@admin_required
async def admin_addproducto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 7:
        await update.message.reply_text("Uso: /admin_addproducto <tienda_id> <nombre> <clasif> <plum> <peur> <pltr> <monedas_json>")
        return
    db.add_producto_tienda(int(context.args[0]), context.args[1], context.args[2], float(context.args[3]), float(context.args[4]), float(context.args[5]), json.loads(context.args[6]))
    await update.message.reply_text("✅ Producto añadido")

@admin_required
async def admin_addempresa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5:
        await update.message.reply_text("Uso: /admin_addempresa <nombre> <sector> <valor> <totales> <disp>")
        return
    db.add_empresa(context.args[0], context.args[1], float(context.args[2]), int(context.args[3]), int(context.args[4]))
    await update.message.reply_text("✅ Empresa creada")

@admin_required
async def admin_updatebolsa_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /admin_updatebolsa <empresa_id> <nuevo_valor>")
        return
    db.actualizar_valor_empresa(int(context.args[0]), float(context.args[1]))
    await update.message.reply_text("✅ Valor actualizado")

@admin_required
async def admin_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 5:
        await update.message.reply_text("Uso: /admin_item <jugador_id> <nombre> <clasif> <cant> <unidad>")
        return
    db.agregar_inventario(int(context.args[0]), context.args[1], context.args[2], float(context.args[3]), context.args[4])
    await update.message.reply_text("✅ Item entregado")

@admin_required
async def admin_ajustar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("Uso: /admin_ajustar <jugador_id> <moneda> <monto>")
        return
    import sqlite3
    conn = sqlite3.connect(db.DB_PATH)
    c = conn.cursor()
    c.execute(f"UPDATE jugadores SET efectivo_{context.args[1].lower()} = efectivo_{context.args[1].lower()} + ? WHERE id = ?", (float(context.args[2]), int(context.args[0])))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Ajustado")

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
    app.add_handler(CommandHandler("comprar", comprar_cmd))
    app.add_handler(CommandHandler("comprar_oferta", comprar_oferta_cmd))
    app.add_handler(CommandHandler("compra_accion", comprar_accion_cmd))
    app.add_handler(CommandHandler("comprar_oferta_accion", comprar_oferta_accion_cmd))
    app.add_handler(CommandHandler("vender_accion", vender_accion_cmd))
    app.add_handler(CommandHandler("admin_codigo", admin_codigo_cmd))
    app.add_handler(CommandHandler("admin_addbanco", admin_addbanco_cmd))
    app.add_handler(CommandHandler("admin_addcambio", admin_addcambio_cmd))
    app.add_handler(CommandHandler("admin_addtienda", admin_addtienda_cmd))
    app.add_handler(CommandHandler("admin_addproducto", admin_addproducto_cmd))
    app.add_handler(CommandHandler("admin_addempresa", admin_addempresa_cmd))
    app.add_handler(CommandHandler("admin_updatebolsa", admin_updatebolsa_cmd))
    app.add_handler(CommandHandler("admin_item", admin_item_cmd))
    app.add_handler(CommandHandler("admin_ajustar", admin_ajustar_cmd))
    app.add_handler(CommandHandler("admin_credito", admin_credito_cmd))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(?!admin_).*"))
    app.add_handler(CallbackQueryHandler(admin_button, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot iniciado...")
    app.run_polling()
