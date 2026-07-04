import sqlite3
import json
import hashlib
from datetime import datetime, timedelta

DB_PATH = 'economia.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS jugadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            contrasena TEXT,
            efectivo_lum REAL DEFAULT 5000,
            efectivo_eur REAL DEFAULT 0,
            efectivo_ltr REAL DEFAULT 0,
            ubicacion_id INTEGER DEFAULT 1,
            FOREIGN KEY(ubicacion_id) REFERENCES ubicaciones(id)
        );
        CREATE TABLE IF NOT EXISTS codigos_registro (
            codigo TEXT PRIMARY KEY,
            usado INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ubicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            region TEXT,
            tipo TEXT DEFAULT 'ciudad'
        );
        CREATE TABLE IF NOT EXISTS rutas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origen_id INTEGER,
            destino_id INTEGER,
            precio_publico_lum REAL DEFAULT 0,
            precio_publico_eur REAL DEFAULT 0,
            tiempo_publico INTEGER DEFAULT 120,
            precio_especial_lum REAL DEFAULT 0,
            precio_especial_eur REAL DEFAULT 0,
            tiempo_especial INTEGER DEFAULT 60,
            precio_premium_lum REAL DEFAULT 0,
            precio_premium_eur REAL DEFAULT 0,
            tiempo_premium INTEGER DEFAULT 30,
            FOREIGN KEY(origen_id) REFERENCES ubicaciones(id),
            FOREIGN KEY(destino_id) REFERENCES ubicaciones(id)
        );
        CREATE TABLE IF NOT EXISTS viajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            origen_id INTEGER,
            destino_id INTEGER,
            tipo_transporte TEXT,
            costo_lum REAL DEFAULT 0,
            costo_eur REAL DEFAULT 0,
            tiempo INTEGER DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(jugador_id) REFERENCES jugadores(id)
        );
        CREATE TABLE IF NOT EXISTS bancos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            monedas TEXT,
            deposito_eur REAL DEFAULT 0,
            deposito_lum REAL DEFAULT 0,
            deposito_ltr REAL DEFAULT 0,
            interes REAL DEFAULT 0,
            comision_mismo_banco REAL DEFAULT 0,
            comision_otro_banco REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            banco_id INTEGER,
            moneda TEXT,
            saldo REAL DEFAULT 0,
            pin TEXT,
            tipo TEXT DEFAULT 'corriente',
            fecha_apertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_interes TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(jugador_id) REFERENCES jugadores(id),
            FOREIGN KEY(banco_id) REFERENCES bancos(id)
        );
        CREATE TABLE IF NOT EXISTS tipos_cambio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco_id INTEGER,
            de_moneda TEXT,
            a_moneda TEXT,
            compra REAL,
            venta REAL,
            FOREIGN KEY(banco_id) REFERENCES bancos(id)
        );
        CREATE TABLE IF NOT EXISTS tiendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            tipo TEXT DEFAULT 'tienda',
            precio_cuenta_lum REAL DEFAULT 0,
            precio_cuenta_eur REAL DEFAULT 0,
            precio_cuenta_ltr REAL DEFAULT 0,
            monedas_aceptadas TEXT,
            ubicacion_id INTEGER DEFAULT 1,
            FOREIGN KEY(ubicacion_id) REFERENCES ubicaciones(id)
        );
        CREATE TABLE IF NOT EXISTS cuentas_tienda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            tienda_id INTEGER,
            FOREIGN KEY(jugador_id) REFERENCES jugadores(id),
            FOREIGN KEY(tienda_id) REFERENCES tiendas(id)
        );
        CREATE TABLE IF NOT EXISTS productos_tienda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tienda_id INTEGER,
            nombre TEXT,
            clasificacion TEXT,
            precio_lum REAL DEFAULT 0,
            precio_eur REAL DEFAULT 0,
            precio_ltr REAL DEFAULT 0,
            monedas_aceptadas TEXT,
            stock INTEGER DEFAULT 1,
            FOREIGN KEY(tienda_id) REFERENCES tiendas(id)
        );
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            nombre TEXT,
            clasificacion TEXT,
            cantidad REAL,
            unidad TEXT,
            en_venta INTEGER DEFAULT 0,
            precio_venta_lum REAL,
            precio_venta_eur REAL,
            precio_venta_ltr REAL,
            tienda_id INTEGER,
            FOREIGN KEY(jugador_id) REFERENCES jugadores(id),
            FOREIGN KEY(tienda_id) REFERENCES tiendas(id)
        );
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            sector TEXT,
            valor_accion REAL,
            acciones_totales INTEGER,
            acciones_disponibles INTEGER,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS acciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            empresa_id INTEGER,
            cantidad INTEGER,
            precio_compra REAL,
            en_venta INTEGER DEFAULT 0,
            precio_venta REAL,
            FOREIGN KEY(jugador_id) REFERENCES jugadores(id),
            FOREIGN KEY(empresa_id) REFERENCES empresas(id)
        );
        CREATE TABLE IF NOT EXISTS transacciones_financieras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            cuenta_id INTEGER,
            tipo TEXT,
            operacion TEXT,
            monto REAL,
            moneda TEXT,
            concepto TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

# ============ JUGADORES ============
def get_jugador_by_nombre(nombre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE nombre = ?", (nombre,))
    r = c.fetchone()
    conn.close()
    return r

def get_jugador_by_id(jid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE id = ?", (jid,))
    r = c.fetchone()
    conn.close()
    return r

def registrar_jugador(nombre, contrasena, ubicacion_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO jugadores (nombre, contrasena, ubicacion_id) VALUES (?, ?, ?)",
              (nombre, hash_password(contrasena), ubicacion_id))
    conn.commit()
    conn.close()

def verificar_login(nombre, contrasena):
    j = get_jugador_by_nombre(nombre)
    if j and j[2] == hash_password(contrasena):
        return j
    return None

def get_ubicacion_jugador(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT u.id, u.nombre, u.region FROM jugadores j JOIN ubicaciones u ON j.ubicacion_id = u.id WHERE j.id = ?", (jugador_id,))
    r = c.fetchone()
    conn.close()
    return r

def cambiar_ubicacion(jugador_id, ubicacion_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE jugadores SET ubicacion_id = ? WHERE id = ?", (ubicacion_id, jugador_id))
    conn.commit()
    conn.close()

def validar_codigo(codigo):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT usado FROM codigos_registro WHERE codigo = ?", (codigo,))
    r = c.fetchone()
    if not r or r[0] == 1:
        conn.close()
        return False
    c.execute("DELETE FROM codigos_registro WHERE codigo = ?", (codigo,))
    conn.commit()
    conn.close()
    return True

def generar_codigo(codigo):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO codigos_registro (codigo, usado) VALUES (?, 0)", (codigo,))
        conn.commit()
        return c.rowcount > 0
    except:
        conn.close()
        return False

# ============ UBICACIONES Y VIAJES ============
def get_ubicaciones():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM ubicaciones ORDER BY nombre")
    r = c.fetchall()
    conn.close()
    return r

def add_ubicacion(nombre, region, tipo='ciudad'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO ubicaciones (nombre, region, tipo) VALUES (?, ?, ?)", (nombre, region, tipo))
    conn.commit()
    conn.close()

def get_rutas_desde(origen_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT r.*, u.nombre as destino_nombre FROM rutas r JOIN ubicaciones u ON r.destino_id = u.id WHERE r.origen_id = ?", (origen_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_ruta(origen_id, destino_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM rutas WHERE origen_id = ? AND destino_id = ?", (origen_id, destino_id))
    r = c.fetchone()
    conn.close()
    return r

def add_ruta(origen_id, destino_id, p_pub_lum, p_pub_eur, t_pub, p_esp_lum, p_esp_eur, t_esp, p_pre_lum, p_pre_eur, t_pre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM rutas WHERE origen_id = ? AND destino_id = ?", (origen_id, destino_id))
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO rutas (origen_id, destino_id, precio_publico_lum, precio_publico_eur, tiempo_publico, precio_especial_lum, precio_especial_eur, tiempo_especial, precio_premium_lum, precio_premium_eur, tiempo_premium) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (origen_id, destino_id, p_pub_lum, p_pub_eur, t_pub, p_esp_lum, p_esp_eur, t_esp, p_pre_lum, p_pre_eur, t_pre))
    conn.commit()
    conn.close()

def puede_viajar(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hoy = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT SUM(tiempo) FROM viajes WHERE jugador_id = ? AND date(fecha) = ?", (jugador_id, hoy))
    total = c.fetchone()[0] or 0
    conn.close()
    return total < 1440

def viajar(jugador_id, destino_id, tipo_transporte):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ubicacion_id FROM jugadores WHERE id = ?", (jugador_id,))
    origen_id = c.fetchone()[0]
    ruta = get_ruta(origen_id, destino_id)
    if not ruta:
        conn.close()
        return False, "Ruta no disponible"
    
    if tipo_transporte == 'publico':
        costo_lum = ruta[3]
        costo_eur = ruta[4]
        tiempo = ruta[5]
    elif tipo_transporte == 'especial':
        costo_lum = ruta[6]
        costo_eur = ruta[7]
        tiempo = ruta[8]
    else:
        costo_lum = ruta[9]
        costo_eur = ruta[10]
        tiempo = ruta[11]
    
    if not puede_viajar(jugador_id):
        conn.close()
        return False, "Ya no puedes viajar más hoy"
    
    c.execute("INSERT INTO viajes (jugador_id, origen_id, destino_id, tipo_transporte, costo_lum, costo_eur, tiempo) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (jugador_id, origen_id, destino_id, tipo_transporte, costo_lum, costo_eur, tiempo))
    c.execute("UPDATE jugadores SET ubicacion_id = ? WHERE id = ?", (destino_id, jugador_id))
    conn.commit()
    conn.close()
    return True, f"Viaje a destino completado. Tiempo: {tiempo} min"

# ============ BANCOS ============
def get_bancos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM bancos")
    r = c.fetchall()
    conn.close()
    return r

def get_banco_by_id(bid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM bancos WHERE id = ?", (bid,))
    r = c.fetchone()
    conn.close()
    return r

def crear_cuenta(jugador_id, banco_id, moneda, pin):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    banco = get_banco_by_id(banco_id)
    deposito = banco[4] if moneda == 'LUM' else banco[3] if moneda == 'EUR' else banco[5]
    c.execute("SELECT efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores WHERE id = ?", (jugador_id,))
    ef = c.fetchone()
    idx = {'LUM': 0, 'EUR': 1, 'LTR': 2}
    if ef[idx[moneda]] < deposito:
        conn.close()
        return False, f"Efectivo insuficiente en {moneda}"
    c.execute(f"UPDATE jugadores SET efectivo_{moneda.lower()} = efectivo_{moneda.lower()} - ? WHERE id = ?", (deposito, jugador_id))
    c.execute("INSERT INTO cuentas (jugador_id, banco_id, moneda, pin, saldo) VALUES (?, ?, ?, ?, ?)",
              (jugador_id, banco_id, moneda, pin, deposito))
    conn.commit()
    conn.close()
    return True, f"Cuenta creada en {banco[1]}"

def get_cuentas(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT c.id, b.nombre, c.moneda, c.saldo, c.pin FROM cuentas c JOIN bancos b ON c.banco_id = b.id WHERE c.jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_cuenta_by_id(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM cuentas WHERE id = ?", (cid,))
    r = c.fetchone()
    conn.close()
    return r

def actualizar_saldo_cuenta(cuenta_id, monto):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_id))
    conn.commit()
    conn.close()

def transferir(jugador_id, origen, destino, monto, pin):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id, saldo, moneda, pin, banco_id FROM cuentas WHERE id = ?", (origen,))
    co = c.fetchone()
    if not co or co[0] != jugador_id or co[3] != pin or co[1] < monto:
        conn.close()
        return False, "Error en transferencia"
    c.execute("SELECT id, jugador_id, moneda, banco_id FROM cuentas WHERE id = ?", (destino,))
    cd = c.fetchone()
    if not cd or co[2] != cd[2]:
        conn.close()
        return False, "Cuenta destino no válida"
    
    banco = get_banco_by_id(co[4])
    comision = banco[6] if co[4] == cd[3] else banco[7]
    total = monto + comision
    if co[1] < total:
        conn.close()
        return False, f"Saldo insuficiente (comisión: {comision} EUR)"
    
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (total, origen))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, destino))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'debito', 'Transferencia', ?, ?, ?)",
              (jugador_id, origen, monto, co[2], f"Enviada a {destino}"))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Transferencia', ?, ?, ?)",
              (cd[1], destino, monto, co[2], f"Recibida de {origen}"))
    conn.commit()
    conn.close()
    return True, f"Transferencia exitosa (comisión: {comision} EUR)"

def get_tipos_cambio(banco_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT de_moneda, a_moneda, compra, venta FROM tipos_cambio WHERE banco_id = ?", (banco_id,))
    r = c.fetchall()
    conn.close()
    return r

def convertir_moneda(origen, destino, monto):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id, banco_id, saldo, moneda FROM cuentas WHERE id = ?", (origen,))
    co = c.fetchone()
    if not co or co[2] < monto:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("SELECT moneda FROM cuentas WHERE id = ?", (destino,))
    cd = c.fetchone()
    if not cd:
        conn.close()
        return False, "Cuenta destino no encontrada"
    c.execute("SELECT venta FROM tipos_cambio WHERE banco_id = ? AND de_moneda = ? AND a_moneda = ?",
              (co[1], co[3], cd[0]))
    t = c.fetchone()
    if not t:
        conn.close()
        return False, "Tipo de cambio no disponible"
    md = monto * t[0]
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (monto, origen))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (md, destino))
    conn.commit()
    conn.close()
    return True, f"Convertido: {md:.2f} {cd[0]}"

def get_efectivo(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores WHERE id = ?", (jugador_id,))
    r = c.fetchone()
    conn.close()
    return r

def get_total_activos(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores WHERE id = ?", (jugador_id,))
    e = c.fetchone()
    c.execute("SELECT moneda, SUM(saldo) FROM cuentas WHERE jugador_id = ? GROUP BY moneda", (jugador_id,))
    cuentas = c.fetchall()
    c.execute("SELECT SUM(a.cantidad * e.valor_accion) FROM acciones a JOIN empresas e ON a.empresa_id = e.id WHERE a.jugador_id = ?", (jugador_id,))
    av = c.fetchone()[0] or 0
    conn.close()
    tl = (e[0] if e else 0) + sum(s for m, s in cuentas if m == 'LUM')
    te = (e[1] if e else 0) + sum(s for m, s in cuentas if m == 'EUR')
    tlr = (e[2] if e else 0) + sum(s for m, s in cuentas if m == 'LTR')
    return tl, te, tlr, av

def depositar_efectivo(jugador_id, moneda, monto, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    col = f"efectivo_{moneda.lower()}"
    c.execute(f"SELECT {col} FROM jugadores WHERE id = ?", (jugador_id,))
    e = c.fetchone()
    if not e or e[0] < monto:
        conn.close()
        return False, "Efectivo insuficiente"
    c.execute("SELECT moneda, jugador_id FROM cuentas WHERE id = ?", (cuenta_id,))
    cu = c.fetchone()
    if not cu or cu[1] != jugador_id or cu[0] != moneda:
        conn.close()
        return False, "Cuenta no válida"
    c.execute(f"UPDATE jugadores SET {col} = {col} - ? WHERE id = ?", (monto, jugador_id))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_id))
    conn.commit()
    conn.close()
    return True, "Depósito exitoso"

def cobrar_interes(cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT c.saldo, c.ultimo_interes, b.interes FROM cuentas c JOIN bancos b ON c.banco_id = b.id WHERE c.id = ?", (cuenta_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return False
    ahora = datetime.now()
    if r[1] and (ahora - datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S')).days < 30:
        conn.close()
        return False
    interes = r[0] * (r[2] / 100)
    c.execute("UPDATE cuentas SET saldo = saldo + ?, ultimo_interes = ? WHERE id = ?", (interes, ahora, cuenta_id))
    conn.commit()
    conn.close()
    return True

# ============ TIENDAS Y PRODUCTOS ============
def get_tiendas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tiendas")
    r = c.fetchall()
    conn.close()
    return r

def get_tienda_by_id(tid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tiendas WHERE id = ?", (tid,))
    r = c.fetchone()
    conn.close()
    return r

def tiene_cuenta_tienda(jugador_id, tienda_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM cuentas_tienda WHERE jugador_id = ? AND tienda_id = ?", (jugador_id, tienda_id))
    r = c.fetchone()
    conn.close()
    return r is not None

def comprar_cuenta_tienda(jugador_id, tienda_id, moneda, cuenta_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tienda = get_tienda_by_id(tienda_id)
    precios = {'LUM': tienda[3], 'EUR': tienda[4], 'LTR': tienda[5]}
    precio = precios.get(moneda, 0)
    if cuenta_id:
        c.execute("SELECT saldo, jugador_id, moneda FROM cuentas WHERE id = ?", (cuenta_id,))
        cu = c.fetchone()
        if not cu or cu[1] != jugador_id or cu[2] != moneda or cu[0] < precio:
            conn.close()
            return False, "Saldo insuficiente"
        c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    else:
        col = f"efectivo_{moneda.lower()}"
        c.execute(f"SELECT {col} FROM jugadores WHERE id = ?", (jugador_id,))
        e = c.fetchone()
        if not e or e[0] < precio:
            conn.close()
            return False, "Efectivo insuficiente"
        c.execute(f"UPDATE jugadores SET {col} = {col} - ? WHERE id = ?", (precio, jugador_id))
    c.execute("INSERT INTO cuentas_tienda (jugador_id, tienda_id) VALUES (?, ?)", (jugador_id, tienda_id))
    conn.commit()
    conn.close()
    return True, f"Cuenta en {tienda[1]} creada"

def buscar_productos(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT p.id, t.nombre, p.nombre, p.clasificacion, p.precio_lum, p.precio_eur, p.precio_ltr, p.monedas_aceptadas, p.stock FROM productos_tienda p JOIN tiendas t ON p.tienda_id = t.id WHERE p.nombre LIKE ? ORDER BY p.precio_lum ASC", (f"%{query}%",))
    r = c.fetchall()
    conn.close()
    return r

def comprar_producto_tienda(jugador_id, producto_id, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM productos_tienda WHERE id = ?", (producto_id,))
    p = c.fetchone()
    if not p or p[9] <= 0:
        conn.close()
        return False, "Producto agotado"
    c.execute("SELECT saldo, moneda FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, jugador_id))
    cu = c.fetchone()
    if not cu:
        conn.close()
        return False, "Cuenta no válida"
    mok = json.loads(p[8])
    if cu[1] not in mok:
        conn.close()
        return False, f"No acepta {cu[1]}"
    precios = {'LUM': p[4], 'EUR': p[5], 'LTR': p[6]}
    precio = precios.get(cu[1], 0)
    if cu[0] < precio:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    c.execute("UPDATE productos_tienda SET stock = stock - 1 WHERE id = ?", (producto_id,))
    c.execute("INSERT INTO inventario (jugador_id, nombre, clasificacion, cantidad, unidad) VALUES (?, ?, ?, 1, 'unidad')",
              (jugador_id, p[2], p[3]))
    conn.commit()
    conn.close()
    return True, f"Comprado: {p[2]}"

# ============ INVENTARIO ============
def get_inventario(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM inventario WHERE jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_inventario_item(iid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM inventario WHERE id = ?", (iid,))
    r = c.fetchone()
    conn.close()
    return r

def buscar_ofertas(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT i.id, i.nombre, i.clasificacion, i.precio_venta_lum, i.precio_venta_eur, i.precio_venta_ltr, j.nombre FROM inventario i JOIN jugadores j ON i.jugador_id=j.id WHERE i.en_venta=1 AND i.nombre LIKE ? ORDER BY i.precio_venta_lum ASC", (f"%{query}%",))
    r = c.fetchall()
    conn.close()
    return r

def ofertar_item(jugador_id, item_id, pl, pe, plr, tienda_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id FROM inventario WHERE id = ?", (item_id,))
    it = c.fetchone()
    if not it or it[0] != jugador_id:
        conn.close()
        return False, "Item no válido"
    c.execute("UPDATE inventario SET en_venta=1, precio_venta_lum=?, precio_venta_eur=?, precio_venta_ltr=?, tienda_id=? WHERE id=?",
              (pl, pe, plr, tienda_id, item_id))
    conn.commit()
    conn.close()
    return True, "Item en venta"

def comprar_item_comprador(comprador_id, item_id, cuenta_id, moneda):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    item = get_inventario_item(item_id)
    if not item or not item[6] or item[1] == comprador_id:
        conn.close()
        return False, "Item no disponible"
    # Verificar misma ubicación
    c.execute("SELECT ubicacion_id FROM jugadores WHERE id = ?", (comprador_id,))
    uc = c.fetchone()[0]
    c.execute("SELECT ubicacion_id FROM jugadores WHERE id = ?", (item[1],))
    uv = c.fetchone()[0]
    if uc != uv:
        conn.close()
        return False, "Debes estar en la misma ubicación que el vendedor"
    precios = {'LUM': item[7], 'EUR': item[8], 'LTR': item[9]}
    if moneda not in precios or not precios[moneda]:
        conn.close()
        return False, "Moneda no aceptada"
    precio = precios[moneda]
    c.execute("SELECT saldo FROM cuentas WHERE id=? AND jugador_id=?", (cuenta_id, comprador_id))
    cu = c.fetchone()
    if not cu or cu[0] < precio:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("SELECT id FROM cuentas WHERE jugador_id=? AND moneda=? LIMIT 1", (item[1], moneda))
    cv = c.fetchone()
    if not cv:
        conn.close()
        return False, "Vendedor sin cuenta"
    c.execute("UPDATE cuentas SET saldo=saldo-? WHERE id=?", (precio, cuenta_id))
    c.execute("UPDATE cuentas SET saldo=saldo+? WHERE id=?", (precio, cv[0]))
    c.execute("UPDATE inventario SET jugador_id=?, en_venta=0, precio_venta_lum=NULL, precio_venta_eur=NULL, precio_venta_ltr=NULL, tienda_id=NULL WHERE id=?",
              (comprador_id, item_id))
    conn.commit()
    conn.close()
    return True, "Compra exitosa"

# ============ EMPRESAS Y ACCIONES ============
def get_empresas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM empresas")
    r = c.fetchall()
    conn.close()
    return r

def get_empresa_by_id(eid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM empresas WHERE id = ?", (eid,))
    r = c.fetchone()
    conn.close()
    return r

def add_empresa(nombre, sector, valor, totales, disponibles):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO empresas (nombre, sector, valor_accion, acciones_totales, acciones_disponibles) VALUES (?,?,?,?,?)",
              (nombre, sector, valor, totales, disponibles))
    conn.commit()
    conn.close()

def actualizar_valor_empresa(empresa_id, nuevo_valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE empresas SET valor_accion=?, fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?", (nuevo_valor, empresa_id))
    conn.commit()
    conn.close()

def get_acciones_jugador(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT a.id, e.nombre, a.cantidad, e.valor_accion, a.precio_compra, a.en_venta, a.precio_venta FROM acciones a JOIN empresas e ON a.empresa_id=e.id WHERE a.jugador_id=?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def buscar_ofertas_acciones(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT a.id, e.nombre, a.cantidad, a.precio_venta, j.nombre FROM acciones a JOIN empresas e ON a.empresa_id=e.id JOIN jugadores j ON a.jugador_id=j.id WHERE a.en_venta=1 AND e.nombre LIKE ? ORDER BY a.precio_venta ASC", (f"%{query}%",))
    r = c.fetchall()
    conn.close()
    return r

def comprar_acciones(jugador_id, empresa_id, cantidad, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    emp = get_empresa_by_id(empresa_id)
    if not emp or emp[4] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    costo = emp[3] * cantidad
    c.execute("SELECT saldo FROM cuentas WHERE id=? AND jugador_id=?", (cuenta_id, jugador_id))
    cu = c.fetchone()
    if not cu or cu[0] < costo:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo=saldo-? WHERE id=?", (costo, cuenta_id))
    c.execute("UPDATE empresas SET acciones_disponibles=acciones_disponibles-? WHERE id=?", (cantidad, empresa_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id=? AND empresa_id=? AND en_venta=0", (jugador_id, empresa_id))
    ex = c.fetchone()
    if ex:
        c.execute("UPDATE acciones SET cantidad=cantidad+?, precio_compra=? WHERE id=?", (cantidad, emp[3], ex[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?,?,?,?)", (jugador_id, empresa_id, cantidad, emp[3]))
    conn.commit()
    conn.close()
    return True, f"Compradas {cantidad} acciones"

def vender_acciones(jugador_id, acciones_id, cantidad, precio_venta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM acciones WHERE id=? AND jugador_id=?", (acciones_id, jugador_id))
    a = c.fetchone()
    if not a or a[3] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    c.execute("UPDATE acciones SET cantidad=cantidad-?, en_venta=1, precio_venta=? WHERE id=?", (cantidad, precio_venta, acciones_id))
    conn.commit()
    conn.close()
    return True, "Acciones en venta"

def comprar_oferta_acciones(comprador_id, accion_id, cantidad, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM acciones WHERE id=? AND en_venta=1", (accion_id,))
    a = c.fetchone()
    if not a or a[3] < cantidad:
        conn.close()
        return False, "Oferta no disponible"
    costo = a[7] * cantidad
    c.execute("SELECT saldo FROM cuentas WHERE id=? AND jugador_id=?", (cuenta_id, comprador_id))
    cu = c.fetchone()
    if not cu or cu[0] < costo:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo=saldo-? WHERE id=?", (costo, cuenta_id))
    c.execute("SELECT id FROM cuentas WHERE jugador_id=? LIMIT 1", (a[1],))
    cv = c.fetchone()
    if cv:
        c.execute("UPDATE cuentas SET saldo=saldo+? WHERE id=?", (costo, cv[0]))
    c.execute("UPDATE acciones SET cantidad=cantidad-?, en_venta=CASE WHEN cantidad-?<=0 THEN 0 ELSE 1 END WHERE id=?", (cantidad, cantidad, accion_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id=? AND empresa_id=? AND en_venta=0", (comprador_id, a[2]))
    ex = c.fetchone()
    if ex:
        c.execute("UPDATE acciones SET cantidad=cantidad+? WHERE id=?", (cantidad, ex[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?,?,?,?)", (comprador_id, a[2], cantidad, a[7]))
    conn.commit()
    conn.close()
    return True, "Compra exitosa"

def get_historial_financiero(jugador_id, limite=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT tipo, operacion, monto, moneda, concepto, fecha FROM transacciones_financieras WHERE jugador_id=? ORDER BY fecha DESC LIMIT ?", (jugador_id, limite))
    r = c.fetchall()
    conn.close()
    return r

def agregar_inventario(jugador_id, nombre, clasif, cantidad, unidad):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO inventario (jugador_id, nombre, clasificacion, cantidad, unidad) VALUES (?,?,?,?,?)",
              (jugador_id, nombre, clasif, cantidad, unidad))
    conn.commit()
    conn.close()

# ============ IMPORTACIÓN JSON ============
def importar_bancos_json(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    creados = 0
    cambios = 0
    for banco in data.get('bancos', []):
        nombre = banco['nombre']
        monedas = json.dumps(banco['monedas'])
        dep_eur = banco['depositos'].get('EUR', 0)
        dep_lum = banco['depositos'].get('LUM', 0)
        dep_ltr = banco['depositos'].get('LTR', 0)
        interes = banco.get('interes', 0)
        com_mismo = banco.get('comision_transferencia', {}).get('mismo_banco', 0)
        com_otro = banco.get('comision_transferencia', {}).get('otro_banco', 0)
        
        c.execute("SELECT id FROM bancos WHERE nombre = ?", (nombre,))
        ex = c.fetchone()
        if not ex:
            c.execute("INSERT INTO bancos (nombre, monedas, deposito_eur, deposito_lum, deposito_ltr, interes, comision_mismo_banco, comision_otro_banco) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (nombre, monedas, dep_eur, dep_lum, dep_ltr, interes, com_mismo, com_otro))
            banco_id = c.lastrowid
            creados += 1
        else:
            banco_id = ex[0]
        
        for tipo in banco.get('tipos_cambio', []):
            c.execute("SELECT COUNT(*) FROM tipos_cambio WHERE banco_id = ? AND de_moneda = ? AND a_moneda = ?",
                      (banco_id, tipo['de'], tipo['a']))
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO tipos_cambio (banco_id, de_moneda, a_moneda, compra, venta) VALUES (?, ?, ?, ?, ?)",
                          (banco_id, tipo['de'], tipo['a'], tipo['compra'], tipo['venta']))
                cambios += 1
    conn.commit()
    conn.close()
    return creados, cambios

def importar_ubicaciones_json(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    creadas = 0
    for u in data.get('ubicaciones', []):
        c.execute("SELECT COUNT(*) FROM ubicaciones WHERE nombre = ?", (u['nombre'],))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO ubicaciones (nombre, region, tipo) VALUES (?, ?, ?)",
                      (u['nombre'], u.get('region', ''), u.get('tipo', 'ciudad')))
            creadas += 1
    conn.commit()
    conn.close()
    return creadas

def importar_rutas_json(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    creadas = 0
    for r in data.get('rutas', []):
        c.execute("SELECT id FROM ubicaciones WHERE nombre = ?", (r['origen'],))
        o = c.fetchone()
        c.execute("SELECT id FROM ubicaciones WHERE nombre = ?", (r['destino'],))
        d = c.fetchone()
        if o and d:
            c.execute("SELECT COUNT(*) FROM rutas WHERE origen_id = ? AND destino_id = ?", (o[0], d[0]))
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO rutas (origen_id, destino_id, precio_publico_lum, precio_publico_eur, tiempo_publico, precio_especial_lum, precio_especial_eur, tiempo_especial, precio_premium_lum, precio_premium_eur, tiempo_premium) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (o[0], d[0], r['publico']['lum'], r['publico']['eur'], r['publico']['tiempo'],
                           r['especial']['lum'], r['especial']['eur'], r['especial']['tiempo'],
                           r['premium']['lum'], r['premium']['eur'], r['premium']['tiempo']))
                creadas += 1
    conn.commit()
    conn.close()
    return creadas

def importar_tiendas_json(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    creadas = 0
    for t in data.get('tiendas', []):
        c.execute("SELECT id FROM tiendas WHERE nombre = ?", (t['nombre'],))
        if c.fetchone() is None:
            c.execute("INSERT INTO tiendas (nombre, tipo, precio_cuenta_lum, precio_cuenta_eur, precio_cuenta_ltr, monedas_aceptadas, ubicacion_id) VALUES (?, ?, ?, ?, ?, ?, 1)",
                      (t['nombre'], t.get('tipo', 'tienda'), t.get('precio_cuenta', {}).get('LUM', 0),
                       t.get('precio_cuenta', {}).get('EUR', 0), t.get('precio_cuenta', {}).get('LTR', 0),
                       json.dumps(t.get('monedas_aceptadas', ['LUM', 'EUR']))))
            creadas += 1
    conn.commit()
    conn.close()
    return creadas

def importar_productos_json(tienda_nombre, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM tiendas WHERE nombre = ?", (tienda_nombre,))
    tienda = c.fetchone()
    if not tienda:
        conn.close()
        return 0
    tienda_id = tienda[0]
    creados = 0
    for cat in data.get('categorias', []):
        for p in cat.get('productos', []):
            c.execute("SELECT COUNT(*) FROM productos_tienda WHERE tienda_id = ? AND nombre = ?", (tienda_id, p['nombre']))
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO productos_tienda (tienda_id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, monedas_aceptadas, stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (tienda_id, p['nombre'], cat['clasificacion'], p['precio_lum'], p.get('precio_eur', 0),
                           p.get('precio_ltr', 0), json.dumps(p.get('monedas_aceptadas', ['LUM', 'EUR'])),
                           p.get('cantidad', p.get('stock', 1))))
                creados += 1
    conn.commit()
    conn.close()
    return creados
