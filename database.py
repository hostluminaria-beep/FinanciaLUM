import sqlite3
import json
import hashlib

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
            efectivo_ltr REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS codigos_registro (
            codigo TEXT PRIMARY KEY,
            usado INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS bancos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            monedas TEXT,
            deposito_inicial REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            banco_id INTEGER,
            moneda TEXT,
            saldo REAL DEFAULT 0,
            pin TEXT,
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
            monedas_aceptadas TEXT
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
            precio_lum REAL,
            precio_eur REAL,
            precio_ltr REAL,
            monedas_aceptadas TEXT,
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

def get_jugador_by_nombre(nombre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE nombre = ?", (nombre,))
    r = c.fetchone()
    conn.close()
    return r

def get_jugador_by_id(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE id = ?", (id,))
    r = c.fetchone()
    conn.close()
    return r

def registrar_jugador(nombre, contrasena):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hashed_pw = hash_password(contrasena)
    c.execute("INSERT INTO jugadores (nombre, contrasena) VALUES (?, ?)", (nombre, hashed_pw))
    conn.commit()
    conn.close()

def verificar_login(nombre, contrasena):
    jugador = get_jugador_by_nombre(nombre)
    if not jugador:
        return None
    if jugador[2] == hash_password(contrasena):
        return jugador
    return None

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

def get_bancos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM bancos")
    r = c.fetchall()
    conn.close()
    return r

def get_banco_by_id(banco_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM bancos WHERE id = ?", (banco_id,))
    r = c.fetchone()
    conn.close()
    return r

def add_banco(nombre, monedas, deposito):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO bancos (nombre, monedas, deposito_inicial) VALUES (?, ?, ?)",
              (nombre, json.dumps(monedas), deposito))
    conn.commit()
    conn.close()

def add_tipo_cambio(banco_id, de_moneda, a_moneda, compra, venta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tipos_cambio WHERE banco_id = ? AND de_moneda = ? AND a_moneda = ?",
              (banco_id, de_moneda, a_moneda))
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO tipos_cambio (banco_id, de_moneda, a_moneda, compra, venta) VALUES (?, ?, ?, ?, ?)",
                  (banco_id, de_moneda, a_moneda, compra, venta))
    else:
        c.execute("UPDATE tipos_cambio SET compra = ?, venta = ? WHERE banco_id = ? AND de_moneda = ? AND a_moneda = ?",
                  (compra, venta, banco_id, de_moneda, a_moneda))
    conn.commit()
    conn.close()

def crear_cuenta(jugador_id, banco_id, moneda, pin):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    banco = get_banco_by_id(banco_id)
    deposito = banco[3] if banco else 0
    c.execute("INSERT INTO cuentas (jugador_id, banco_id, moneda, pin, saldo) VALUES (?, ?, ?, ?, ?)",
              (jugador_id, banco_id, moneda, pin, deposito))
    cuenta_id = c.lastrowid
    c.execute(f"UPDATE jugadores SET efectivo_{moneda.lower()} = efectivo_{moneda.lower()} - ? WHERE id = ?",
              (deposito, jugador_id))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'debito', 'Depósito inicial', ?, ?, 'Apertura de cuenta')",
              (jugador_id, cuenta_id, deposito, moneda))
    conn.commit()
    conn.close()

def get_cuentas(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT c.id, b.nombre, c.moneda, c.saldo, c.pin FROM cuentas c JOIN bancos b ON c.banco_id = b.id WHERE c.jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_cuenta_by_id(cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM cuentas WHERE id = ?", (cuenta_id,))
    r = c.fetchone()
    conn.close()
    return r

def actualizar_saldo_cuenta(cuenta_id, monto):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_id))
    conn.commit()
    conn.close()

def transferir(jugador_id, cuenta_origen, cuenta_destino, monto, pin):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id, saldo, moneda, pin FROM cuentas WHERE id = ?", (cuenta_origen,))
    co = c.fetchone()
    if not co or co[0] != jugador_id or co[3] != pin or co[1] < monto:
        conn.close()
        return False, "Error en transferencia"
    c.execute("SELECT id, jugador_id, moneda FROM cuentas WHERE id = ?", (cuenta_destino,))
    cd = c.fetchone()
    if not cd or co[2] != cd[2]:
        conn.close()
        return False, "Cuenta destino no válida"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (monto, cuenta_origen))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_destino))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'debito', 'Transferencia', ?, ?, ?)",
              (jugador_id, cuenta_origen, monto, co[2], f"Enviada a cuenta {cuenta_destino}"))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Transferencia', ?, ?, ?)",
              (cd[1], cuenta_destino, monto, co[2], f"Recibida de cuenta {cuenta_origen}"))
    conn.commit()
    conn.close()
    return True, "Transferencia exitosa"

def get_tipos_cambio(banco_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT de_moneda, a_moneda, compra, venta FROM tipos_cambio WHERE banco_id = ?", (banco_id,))
    r = c.fetchall()
    conn.close()
    return r

def convertir_moneda(cuenta_origen, cuenta_destino, monto):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id, banco_id, saldo, moneda FROM cuentas WHERE id = ?", (cuenta_origen,))
    co = c.fetchone()
    if not co or co[2] < monto:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("SELECT moneda FROM cuentas WHERE id = ?", (cuenta_destino,))
    cd = c.fetchone()
    if not cd:
        conn.close()
        return False, "Cuenta destino no encontrada"
    c.execute("SELECT venta FROM tipos_cambio WHERE banco_id = ? AND de_moneda = ? AND a_moneda = ?",
              (co[1], co[3], cd[0]))
    tipo = c.fetchone()
    if not tipo:
        conn.close()
        return False, "Tipo de cambio no disponible"
    monto_destino = monto * tipo[0]
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (monto, cuenta_origen))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto_destino, cuenta_destino))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'debito', 'Conversión', ?, ?, ?)",
              (co[0], cuenta_origen, monto, co[3], f"Convertido a {cd[0]}"))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Conversión', ?, ?, ?)",
              (co[0], cuenta_destino, monto_destino, cd[0], f"Convertido desde {co[3]}"))
    conn.commit()
    conn.close()
    return True, f"Convertido: {monto_destino:.2f} {cd[0]}"

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
    acciones_valor = c.fetchone()[0] or 0
    conn.close()
    total_lum = (e[0] if e else 0) + sum(s for m, s in cuentas if m == 'LUM')
    total_eur = (e[1] if e else 0) + sum(s for m, s in cuentas if m == 'EUR')
    total_ltr = (e[2] if e else 0) + sum(s for m, s in cuentas if m == 'LTR')
    return total_lum, total_eur, total_ltr, acciones_valor

def depositar_efectivo(jugador_id, moneda, monto, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    columna = f"efectivo_{moneda.lower()}"
    c.execute(f"SELECT {columna} FROM jugadores WHERE id = ?", (jugador_id,))
    e = c.fetchone()
    if not e or e[0] < monto:
        conn.close()
        return False, "Efectivo insuficiente"
    c.execute("SELECT moneda, jugador_id FROM cuentas WHERE id = ?", (cuenta_id,))
    cuenta = c.fetchone()
    if not cuenta or cuenta[1] != jugador_id or cuenta[0] != moneda:
        conn.close()
        return False, "Cuenta no válida"
    c.execute(f"UPDATE jugadores SET {columna} = {columna} - ? WHERE id = ?", (monto, jugador_id))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_id))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Depósito', ?, ?, 'Depósito desde efectivo')",
              (jugador_id, cuenta_id, monto, moneda))
    conn.commit()
    conn.close()
    return True, "Depósito exitoso"

def get_tiendas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tiendas")
    r = c.fetchall()
    conn.close()
    return r

def get_tienda_by_id(tienda_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tiendas WHERE id = ?", (tienda_id,))
    r = c.fetchone()
    conn.close()
    return r

def add_tienda(nombre, tipo, precio_lum, precio_eur, precio_ltr, monedas):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO tiendas (nombre, tipo, precio_cuenta_lum, precio_cuenta_eur, precio_cuenta_ltr, monedas_aceptadas) VALUES (?, ?, ?, ?, ?, ?)",
              (nombre, tipo, precio_lum, precio_eur, precio_ltr, json.dumps(monedas)))
    conn.commit()
    conn.close()

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
        cuenta = c.fetchone()
        if not cuenta or cuenta[1] != jugador_id or cuenta[2] != moneda or cuenta[0] < precio:
            conn.close()
            return False, "Saldo insuficiente o cuenta no válida"
        c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    else:
        columna = f"efectivo_{moneda.lower()}"
        c.execute(f"SELECT {columna} FROM jugadores WHERE id = ?", (jugador_id,))
        e = c.fetchone()
        if not e or e[0] < precio:
            conn.close()
            return False, "Efectivo insuficiente"
        c.execute(f"UPDATE jugadores SET {columna} = {columna} - ? WHERE id = ?", (precio, jugador_id))
    c.execute("INSERT INTO cuentas_tienda (jugador_id, tienda_id) VALUES (?, ?)", (jugador_id, tienda_id))
    conn.commit()
    conn.close()
    return True, f"Cuenta en {tienda[1]} creada"

def add_producto_tienda(tienda_id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, monedas):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO productos_tienda (tienda_id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, monedas_aceptadas) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (tienda_id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, json.dumps(monedas)))
    conn.commit()
    conn.close()

def buscar_productos(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT p.id, t.nombre, p.nombre, p.clasificacion, p.precio_lum, p.precio_eur, p.precio_ltr, p.monedas_aceptadas FROM productos_tienda p JOIN tiendas t ON p.tienda_id = t.id WHERE p.nombre LIKE ? ORDER BY p.precio_lum ASC",
              (f"%{query}%",))
    r = c.fetchall()
    conn.close()
    return r

def comprar_producto_tienda(jugador_id, producto_id, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM productos_tienda WHERE id = ?", (producto_id,))
    prod = c.fetchone()
    if not prod:
        conn.close()
        return False, "Producto no encontrado"
    c.execute("SELECT saldo, moneda FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, jugador_id))
    cuenta = c.fetchone()
    if not cuenta:
        conn.close()
        return False, "Cuenta no válida"
    monedas_ok = json.loads(prod[7])
    if cuenta[1] not in monedas_ok:
        conn.close()
        return False, f"Esta tienda no acepta {cuenta[1]}"
    precios = {'LUM': prod[3], 'EUR': prod[4], 'LTR': prod[5]}
    precio = precios.get(cuenta[1], 0)
    if cuenta[0] < precio:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    c.execute("INSERT INTO inventario (jugador_id, nombre, clasificacion, cantidad, unidad) VALUES (?, ?, ?, 1, 'unidad')",
              (jugador_id, prod[2], prod[3]))
    conn.commit()
    conn.close()
    return True, f"Comprado: {prod[2]} por {precio} {cuenta[1]}"

def get_inventario(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM inventario WHERE jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_inventario_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM inventario WHERE id = ?", (item_id,))
    r = c.fetchone()
    conn.close()
    return r

def ofertar_item(jugador_id, item_id, precio_lum, precio_eur, precio_ltr, tienda_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id FROM inventario WHERE id = ?", (item_id,))
    item = c.fetchone()
    if not item or item[0] != jugador_id:
        conn.close()
        return False, "Item no válido"
    c.execute("UPDATE inventario SET en_venta = 1, precio_venta_lum = ?, precio_venta_eur = ?, precio_venta_ltr = ?, tienda_id = ? WHERE id = ?",
              (precio_lum, precio_eur, precio_ltr, tienda_id, item_id))
    conn.commit()
    conn.close()
    return True, "Item en venta"

def buscar_ofertas(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT i.id, i.nombre, i.clasificacion, i.precio_venta_lum, i.precio_venta_eur, i.precio_venta_ltr, j.nombre, i.cantidad FROM inventario i JOIN jugadores j ON i.jugador_id = j.id WHERE i.en_venta = 1 AND i.nombre LIKE ? ORDER BY i.precio_venta_lum ASC",
              (f"%{query}%",))
    r = c.fetchall()
    conn.close()
    return r

def comprar_item_comprador(comprador_id, item_id, cuenta_id, moneda):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    item = get_inventario_item(item_id)
    if not item or not item[6] or item[1] == comprador_id:
        conn.close()
        return False, "Item no disponible"
    precios = {'LUM': item[7], 'EUR': item[8], 'LTR': item[9]}
    if moneda not in precios or not precios[moneda]:
        conn.close()
        return False, "Moneda no aceptada"
    precio = precios[moneda]
    c.execute("SELECT saldo, jugador_id FROM cuentas WHERE id = ?", (cuenta_id,))
    cuenta = c.fetchone()
    if not cuenta or cuenta[1] != comprador_id or cuenta[0] < precio:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("SELECT id FROM cuentas WHERE jugador_id = ? AND moneda = ? LIMIT 1", (item[1], moneda))
    cv = c.fetchone()
    if not cv:
        conn.close()
        return False, "Vendedor sin cuenta"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (precio, cv[0]))
    c.execute("UPDATE inventario SET jugador_id = ?, en_venta = 0, precio_venta_lum = NULL, precio_venta_eur = NULL, precio_venta_ltr = NULL, tienda_id = NULL WHERE id = ?",
              (comprador_id, item_id))
    conn.commit()
    conn.close()
    return True, "Compra exitosa"

def get_empresas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM empresas")
    r = c.fetchall()
    conn.close()
    return r

def get_empresa_by_id(empresa_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,))
    r = c.fetchone()
    conn.close()
    return r

def add_empresa(nombre, sector, valor, totales, disponibles):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO empresas (nombre, sector, valor_accion, acciones_totales, acciones_disponibles) VALUES (?, ?, ?, ?, ?)",
              (nombre, sector, valor, totales, disponibles))
    conn.commit()
    conn.close()

def actualizar_valor_empresa(empresa_id, nuevo_valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE empresas SET valor_accion = ?, fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = ?", (nuevo_valor, empresa_id))
    conn.commit()
    conn.close()

def get_acciones_jugador(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT a.id, e.nombre, a.cantidad, e.valor_accion, a.precio_compra, a.en_venta, a.precio_venta FROM acciones a JOIN empresas e ON a.empresa_id = e.id WHERE a.jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def buscar_ofertas_acciones(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT a.id, e.nombre, a.cantidad, a.precio_venta, j.nombre FROM acciones a JOIN empresas e ON a.empresa_id = e.id JOIN jugadores j ON a.jugador_id = j.id WHERE a.en_venta = 1 AND e.nombre LIKE ? ORDER BY a.precio_venta ASC",
              (f"%{query}%",))
    r = c.fetchall()
    conn.close()
    return r

def comprar_acciones(jugador_id, empresa_id, cantidad, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    empresa = get_empresa_by_id(empresa_id)
    if not empresa or empresa[4] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    costo = empresa[3] * cantidad
    c.execute("SELECT saldo FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, jugador_id))
    cuenta = c.fetchone()
    if not cuenta or cuenta[0] < costo:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (costo, cuenta_id))
    c.execute("UPDATE empresas SET acciones_disponibles = acciones_disponibles - ? WHERE id = ?", (cantidad, empresa_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id = ? AND empresa_id = ? AND en_venta = 0", (jugador_id, empresa_id))
    existente = c.fetchone()
    if existente:
        c.execute("UPDATE acciones SET cantidad = cantidad + ?, precio_compra = ? WHERE id = ?", (cantidad, empresa[3], existente[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?, ?, ?, ?)", (jugador_id, empresa_id, cantidad, empresa[3]))
    conn.commit()
    conn.close()
    return True, f"Compradas {cantidad} acciones de {empresa[1]}"

def vender_acciones(jugador_id, acciones_id, cantidad, precio_venta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM acciones WHERE id = ? AND jugador_id = ?", (acciones_id, jugador_id))
    accion = c.fetchone()
    if not accion or accion[3] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    c.execute("UPDATE acciones SET cantidad = cantidad - ?, en_venta = 1, precio_venta = ? WHERE id = ?", (cantidad, precio_venta, acciones_id))
    conn.commit()
    conn.close()
    return True, "Acciones en venta"

def comprar_oferta_acciones(comprador_id, accion_id, cantidad, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM acciones WHERE id = ? AND en_venta = 1", (accion_id,))
    accion = c.fetchone()
    if not accion or accion[3] < cantidad:
        conn.close()
        return False, "Oferta no disponible"
    costo = accion[7] * cantidad
    c.execute("SELECT saldo FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, comprador_id))
    cuenta = c.fetchone()
    if not cuenta or cuenta[0] < costo:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (costo, cuenta_id))
    c.execute("SELECT id FROM cuentas WHERE jugador_id = ? LIMIT 1", (accion[1],))
    cv = c.fetchone()
    if cv:
        c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (costo, cv[0]))
    c.execute("UPDATE acciones SET cantidad = cantidad - ?, en_venta = CASE WHEN cantidad - ? <= 0 THEN 0 ELSE 1 END WHERE id = ?",
              (cantidad, cantidad, accion_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id = ? AND empresa_id = ? AND en_venta = 0", (comprador_id, accion[2]))
    existente = c.fetchone()
    if existente:
        c.execute("UPDATE acciones SET cantidad = cantidad + ? WHERE id = ?", (cantidad, existente[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?, ?, ?, ?)",
                  (comprador_id, accion[2], cantidad, accion[7]))
    conn.commit()
    conn.close()
    return True, "Compra exitosa"

def get_historial_financiero(jugador_id, limite=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT tipo, operacion, monto, moneda, concepto, fecha FROM transacciones_financieras WHERE jugador_id = ? ORDER BY fecha DESC LIMIT ?", (jugador_id, limite))
    r = c.fetchall()
    conn.close()
    return r

def agregar_inventario(jugador_id, nombre, clasificacion, cantidad, unidad):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO inventario (jugador_id, nombre, clasificacion, cantidad, unidad) VALUES (?, ?, ?, ?, ?)",
              (jugador_id, nombre, clasificacion, cantidad, unidad))
    conn.commit()
    conn.close()            saldo REAL DEFAULT 0,
            pin TEXT,
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
            monedas_aceptadas TEXT
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
            precio_lum REAL,
            precio_eur REAL,
            precio_ltr REAL,
            monedas_aceptadas TEXT,
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
        CREATE TABLE IF NOT EXISTS ofertas_acciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acciones_id INTEGER,
            jugador_id INTEGER,
            empresa_id INTEGER,
            cantidad INTEGER,
            precio_venta REAL,
            activa INTEGER DEFAULT 1,
            FOREIGN KEY(acciones_id) REFERENCES acciones(id),
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
        CREATE TABLE IF NOT EXISTS transacciones_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador_id INTEGER,
            tipo TEXT,
            operacion TEXT,
            activo TEXT,
            cantidad REAL,
            cuenta_beneficiada TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()
    seed_data()

def seed_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    bancos = [
        ("CaixaPujol", '["EUR","LUM"]', 100),
        ("Sabadell", '["EUR","LUM","LTR"]', 200),
        ("BBVA", '["EUR","LUM"]', 150),
        ("CrèditAgricole", '["EUR","LTR"]', 100),
        ("SBCL", '["LUM","LTR"]', 50),
        ("Banc del Pirineu", '["EUR","LUM","LTR"]', 300),
    ]
    for nombre, monedas, deposito in bancos:
        c.execute("INSERT OR IGNORE INTO bancos (nombre, monedas, deposito_inicial) VALUES (?, ?, ?)",
                 (nombre, monedas, deposito))
    
    c.execute("SELECT id FROM bancos")
    bancos_ids = [row[0] for row in c.fetchall()]
    
    for banco_id in bancos_ids:
        cambios = [
            (banco_id, "LUM", "EUR", 0.85, 0.95),
            (banco_id, "EUR", "LUM", 1.05, 1.15),
            (banco_id, "LUM", "LTR", 0.75, 0.85),
            (banco_id, "LTR", "LUM", 1.10, 1.20),
            (banco_id, "EUR", "LTR", 0.90, 1.00),
            (banco_id, "LTR", "EUR", 0.95, 1.05),
        ]
        for de_moneda, a_moneda, compra, venta in cambios:
            try:
                c.execute("INSERT OR IGNORE INTO tipos_cambio (banco_id, de_moneda, a_moneda, compra, venta) VALUES (?, ?, ?, ?, ?)",
                         (banco_id, de_moneda, a_moneda, compra, venta))
            except:
                pass
    
    tiendas = [
        ("Pirinmart", "tienda", 0, 0, 0, '["EUR","LUM","LTR"]'),
        ("Mercadona", "tienda", 50, 40, 45, '["EUR","LUM"]'),
        ("Amazon", "tienda", 100, 85, 90, '["EUR","LUM","LTR"]'),
        ("Inmobiliaria Pujol", "inmobiliaria", 500, 425, 450, '["EUR","LUM"]'),
    ]
    for nombre, tipo, pl, pe, plr, mon in tiendas:
        c.execute("INSERT OR IGNORE INTO tiendas (nombre, tipo, precio_cuenta_lum, precio_cuenta_eur, precio_cuenta_ltr, monedas_aceptadas) VALUES (?, ?, ?, ?, ?, ?)",
                 (nombre, tipo, pl, pe, plr, mon))
    
    c.execute("SELECT id FROM tiendas")
    tiendas_ids = [row[0] for row in c.fetchall()]
    
    productos = [
        (tiendas_ids[0] if len(tiendas_ids) > 0 else 1, "Pan de LUM", "F", 5, 4, 4, '["LUM","EUR"]'),
        (tiendas_ids[0] if len(tiendas_ids) > 0 else 1, "Queso de Cabra", "E", 15, 12, 13, '["LUM","EUR","LTR"]'),
        (tiendas_ids[1] if len(tiendas_ids) > 1 else 1, "Leche Fresca", "F", 3, 2, 3, '["EUR"]'),
        (tiendas_ids[1] if len(tiendas_ids) > 1 else 1, "Carne de Res", "D", 25, 21, 22, '["EUR","LUM"]'),
        (tiendas_ids[2] if len(tiendas_ids) > 2 else 1, "Libro Antiguo", "C", 75, 63, 68, '["LUM","EUR","LTR"]'),
        (tiendas_ids[2] if len(tiendas_ids) > 2 else 1, "Tablet Mágica", "B", 300, 255, 270, '["LUM","EUR"]'),
        (tiendas_ids[3] if len(tiendas_ids) > 3 else 1, "Casa Rural", "A", 5000, 4250, 4500, '["EUR","LUM"]'),
        (tiendas_ids[3] if len(tiendas_ids) > 3 else 1, "Terreno Agrícola", "B", 2000, 1700, 1800, '["EUR","LTR"]'),
    ]
    
    c.execute("SELECT COUNT(*) FROM productos_tienda")
    if c.fetchone()[0] == 0:
        for tienda_id, nombre, clasif, pl, pe, plr, mon in productos:
            c.execute("INSERT INTO productos_tienda (tienda_id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, monedas_aceptadas) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (tienda_id, nombre, clasif, pl, pe, plr, mon))
    
    empresas = [
        ("Luminaria Corp", "Tecnología", 100.0, 1000, 500),
        ("Minas del Norte", "Minería", 75.0, 800, 400),
        ("Banco Imperial", "Finanzas", 150.0, 500, 250),
        ("Transportes LUM", "Logística", 50.0, 1200, 600),
        ("Energías Unidas", "Energía", 200.0, 600, 300),
    ]
    
    c.execute("SELECT COUNT(*) FROM empresas")
    if c.fetchone()[0] == 0:
        for nombre, sector, valor, totales, disponibles in empresas:
            c.execute("INSERT INTO empresas (nombre, sector, valor_accion, acciones_totales, acciones_disponibles) VALUES (?, ?, ?, ?, ?)",
                     (nombre, sector, valor, totales, disponibles))
    
    conn.commit()
    conn.close()

# ============ FUNCIONES JUGADORES ============
def get_jugador_by_nombre(nombre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE nombre = ?", (nombre,))
    r = c.fetchone()
    conn.close()
    return r

def get_jugador_by_id(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM jugadores WHERE id = ?", (id,))
    r = c.fetchone()
    conn.close()
    return r

def registrar_jugador(nombre, contrasena):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hashed_pw = hash_password(contrasena)
    c.execute("INSERT INTO jugadores (nombre, contrasena) VALUES (?, ?)", (nombre, hashed_pw))
    conn.commit()
    conn.close()

def verificar_login(nombre, contrasena):
    jugador = get_jugador_by_nombre(nombre)
    if not jugador:
        return None
    if jugador[2] == hash_password(contrasena):
        return jugador
    return None

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
        success = c.rowcount > 0
        conn.close()
        return success
    except:
        conn.close()
        return False

# ============ FUNCIONES BANCOS ============
def get_bancos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM bancos")
    r = c.fetchall()
    conn.close()
    return r

def get_banco_by_id(banco_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM bancos WHERE id = ?", (banco_id,))
    r = c.fetchone()
    conn.close()
    return r

def crear_cuenta(jugador_id, banco_id, moneda, pin):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    banco = get_banco_by_id(banco_id)
    deposito = banco[3] if banco else 0
    c.execute("INSERT INTO cuentas (jugador_id, banco_id, moneda, pin, saldo) VALUES (?, ?, ?, ?, ?)",
              (jugador_id, banco_id, moneda, pin, deposito))
    c.execute(f"UPDATE jugadores SET efectivo_{moneda.lower()} = efectivo_{moneda.lower()} - ? WHERE id = ?",
              (deposito, jugador_id))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, last_insert_rowid(), 'debito', 'Depósito inicial', ?, ?, 'Apertura de cuenta')",
              (jugador_id, deposito, moneda))
    conn.commit()
    conn.close()

def get_cuentas(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT c.id, b.nombre, c.moneda, c.saldo, c.pin FROM cuentas c JOIN bancos b ON c.banco_id = b.id WHERE c.jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_cuenta_by_id(cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM cuentas WHERE id = ?", (cuenta_id,))
    r = c.fetchone()
    conn.close()
    return r

def actualizar_saldo_cuenta(cuenta_id, monto):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_id))
    conn.commit()
    conn.close()

def transferir(jugador_id, cuenta_origen, cuenta_destino, monto, pin):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id, saldo, moneda, pin FROM cuentas WHERE id = ?", (cuenta_origen,))
    co = c.fetchone()
    if not co or co[0] != jugador_id or co[3] != pin or co[1] < monto:
        conn.close()
        return False, "Error en transferencia"
    c.execute("SELECT id, jugador_id, moneda FROM cuentas WHERE id = ?", (cuenta_destino,))
    cd = c.fetchone()
    if not cd or co[2] != cd[2]:
        conn.close()
        return False, "Cuenta destino no válida"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (monto, cuenta_origen))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_destino))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'debito', 'Transferencia', ?, ?, ?)",
              (jugador_id, cuenta_origen, monto, co[2], f"Enviada a cuenta {cuenta_destino}"))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Transferencia', ?, ?, ?)",
              (cd[1], cuenta_destino, monto, co[2], f"Recibida de cuenta {cuenta_origen}"))
    conn.commit()
    conn.close()
    return True, "Transferencia exitosa"

def get_tipos_cambio(banco_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT de_moneda, a_moneda, compra, venta FROM tipos_cambio WHERE banco_id = ?", (banco_id,))
    r = c.fetchall()
    conn.close()
    return r

def convertir_moneda(cuenta_origen, cuenta_destino, monto):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id, banco_id, saldo, moneda FROM cuentas WHERE id = ?", (cuenta_origen,))
    co = c.fetchone()
    if not co or co[2] < monto:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("SELECT moneda FROM cuentas WHERE id = ?", (cuenta_destino,))
    cd = c.fetchone()
    if not cd:
        conn.close()
        return False, "Cuenta destino no encontrada"
    c.execute("SELECT venta FROM tipos_cambio WHERE banco_id = ? AND de_moneda = ? AND a_moneda = ?",
              (co[1], co[3], cd[0]))
    tipo = c.fetchone()
    if not tipo:
        conn.close()
        return False, "Tipo de cambio no disponible"
    monto_destino = monto * tipo[0]
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (monto, cuenta_origen))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto_destino, cuenta_destino))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'debito', 'Conversión', ?, ?, ?)",
              (co[0], cuenta_origen, monto, co[3], f"Convertido a {cd[0]}"))
    c.execute("INSERT INTO transacciones_financieras (jugador_id, cuenta_id, tipo, operacion, monto, moneda, concepto) VALUES (?, ?, 'credito', 'Conversión', ?, ?, ?)",
              (co[0], cuenta_destino, monto_destino, cd[0], f"Convertido desde {co[3]}"))
    conn.commit()
    conn.close()
    return True, f"Convertido: {monto_destino:.2f} {cd[0]}"

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
    # Efectivo
    c.execute("SELECT efectivo_lum, efectivo_eur, efectivo_ltr FROM jugadores WHERE id = ?", (jugador_id,))
    e = c.fetchone()
    # Cuentas
    c.execute("SELECT moneda, SUM(saldo) FROM cuentas WHERE jugador_id = ? GROUP BY moneda", (jugador_id,))
    cuentas = c.fetchall()
    # Acciones
    c.execute("SELECT SUM(a.cantidad * e.valor_accion) FROM acciones a JOIN empresas e ON a.empresa_id = e.id WHERE a.jugador_id = ?", (jugador_id,))
    acciones_valor = c.fetchone()[0] or 0
    conn.close()
    
    total_lum = e[0] if e else 0
    total_eur = e[1] if e else 0
    total_ltr = e[2] if e else 0
    
    for moneda, saldo in cuentas:
        if moneda == 'LUM': total_lum += saldo
        elif moneda == 'EUR': total_eur += saldo
        elif moneda == 'LTR': total_ltr += saldo
    
    return total_lum, total_eur, total_ltr, acciones_valor

def depositar_efectivo(jugador_id, moneda, monto, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    columna = f"efectivo_{moneda.lower()}"
    c.execute(f"SELECT {columna} FROM jugadores WHERE id = ?", (jugador_id,))
    e = c.fetchone()
    if not e or e[0] < monto:
        conn.close()
        return False, "Efectivo insuficiente"
    c.execute("SELECT moneda, jugador_id FROM cuentas WHERE id = ?", (cuenta_id,))
    cuenta = c.fetchone()
    if not cuenta or cuenta[1] != jugador_id or cuenta[0] != moneda:
        conn.close()
        return False, "Cuenta no válida"
    c.execute(f"UPDATE jugadores SET {columna} = {columna} - ? WHERE id = ?", (monto, jugador_id))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (monto, cuenta_id))
    conn.commit()
    conn.close()
    return True, "Depósito exitoso"

# ============ FUNCIONES TIENDAS ============
def get_tiendas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tiendas")
    r = c.fetchall()
    conn.close()
    return r

def get_tienda_by_id(tienda_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tiendas WHERE id = ?", (tienda_id,))
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
        cuenta = c.fetchone()
        if not cuenta or cuenta[1] != jugador_id or cuenta[2] != moneda or cuenta[0] < precio:
            conn.close()
            return False, "Saldo insuficiente o cuenta no válida"
        c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    else:
        columna = f"efectivo_{moneda.lower()}"
        c.execute(f"SELECT {columna} FROM jugadores WHERE id = ?", (jugador_id,))
        e = c.fetchone()
        if not e or e[0] < precio:
            conn.close()
            return False, "Efectivo insuficiente"
        c.execute(f"UPDATE jugadores SET {columna} = {columna} - ? WHERE id = ?", (precio, jugador_id))
    
    c.execute("INSERT INTO cuentas_tienda (jugador_id, tienda_id) VALUES (?, ?)", (jugador_id, tienda_id))
    conn.commit()
    conn.close()
    return True, f"Cuenta en {tienda[1]} creada"

def buscar_productos(tienda_id, nombre=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if nombre:
        c.execute("SELECT id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, monedas_aceptadas FROM productos_tienda WHERE tienda_id = ? AND nombre LIKE ? ORDER BY precio_lum ASC",
                  (tienda_id, f"%{nombre}%"))
    else:
        c.execute("SELECT id, nombre, clasificacion, precio_lum, precio_eur, precio_ltr, monedas_aceptadas FROM productos_tienda WHERE tienda_id = ? ORDER BY precio_lum ASC",
                  (tienda_id,))
    r = c.fetchall()
    conn.close()
    return r

def comprar_producto_tienda(jugador_id, tienda_id, producto_id, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM productos_tienda WHERE id = ? AND tienda_id = ?", (producto_id, tienda_id))
    prod = c.fetchone()
    if not prod:
        conn.close()
        return False, "Producto no encontrado"
    c.execute("SELECT saldo, moneda FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, jugador_id))
    cuenta = c.fetchone()
    if not cuenta:
        conn.close()
        return False, "Cuenta no válida"
    monedas_ok = json.loads(prod[7])
    if cuenta[1] not in monedas_ok:
        conn.close()
        return False, f"Esta tienda no acepta {cuenta[1]}"
    precios = {'LUM': prod[3], 'EUR': prod[4], 'LTR': prod[5]}
    precio = precios.get(cuenta[1], 0)
    if cuenta[0] < precio:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    c.execute("INSERT INTO inventario (jugador_id, nombre, clasificacion, cantidad, unidad) VALUES (?, ?, ?, 1, 'unidad')",
              (jugador_id, prod[2], prod[3]))
    conn.commit()
    conn.close()
    return True, f"Comprado: {prod[2]}"

# ============ FUNCIONES INVENTARIO ============
def get_inventario(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nombre, clasificacion, cantidad, unidad, en_venta, precio_venta_lum, precio_venta_eur, precio_venta_ltr, tienda_id FROM inventario WHERE jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_inventario_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM inventario WHERE id = ?", (item_id,))
    r = c.fetchone()
    conn.close()
    return r

def ofertar_item(jugador_id, item_id, precio_lum, precio_eur, precio_ltr, tienda_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id FROM inventario WHERE id = ?", (item_id,))
    item = c.fetchone()
    if not item or item[0] != jugador_id:
        conn.close()
        return False, "Item no válido"
    c.execute("UPDATE inventario SET en_venta = 1, precio_venta_lum = ?, precio_venta_eur = ?, precio_venta_ltr = ?, tienda_id = ? WHERE id = ?",
              (precio_lum, precio_eur, precio_ltr, tienda_id, item_id))
    conn.commit()
    conn.close()
    return True, "Item en venta"

def desofertar_item(jugador_id, item_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT jugador_id FROM inventario WHERE id = ?", (item_id,))
    item = c.fetchone()
    if not item or item[0] != jugador_id:
        conn.close()
        return False, "Item no válido"
    c.execute("UPDATE inventario SET en_venta = 0, precio_venta_lum = NULL, precio_venta_eur = NULL, precio_venta_ltr = NULL, tienda_id = NULL WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return True, "Venta cancelada"

def comprar_item_comprador(comprador_id, item_id, cuenta_id, moneda):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    item = get_inventario_item(item_id)
    if not item or not item[6] or item[1] == comprador_id:
        conn.close()
        return False, "Item no disponible"
    precios = {'LUM': item[7], 'EUR': item[8], 'LTR': item[9]}
    if moneda not in precios or not precios[moneda]:
        conn.close()
        return False, "Moneda no aceptada"
    precio = precios[moneda]
    c.execute("SELECT saldo, jugador_id FROM cuentas WHERE id = ?", (cuenta_id,))
    cuenta = c.fetchone()
    if not cuenta or cuenta[1] != comprador_id or cuenta[0] < precio:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("SELECT id FROM cuentas WHERE jugador_id = ? AND moneda = ? LIMIT 1", (item[1], moneda))
    cv = c.fetchone()
    if not cv:
        conn.close()
        return False, "Vendedor sin cuenta"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (precio, cuenta_id))
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (precio, cv[0]))
    c.execute("UPDATE inventario SET jugador_id = ?, en_venta = 0, precio_venta_lum = NULL, precio_venta_eur = NULL, precio_venta_ltr = NULL, tienda_id = NULL WHERE id = ?",
              (comprador_id, item_id))
    conn.commit()
    conn.close()
    return True, "Compra exitosa"

# ============ FUNCIONES BOLSA ============
def get_empresas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM empresas")
    r = c.fetchall()
    conn.close()
    return r

def get_acciones_jugador(jugador_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT a.id, e.nombre, a.cantidad, e.valor_accion, a.precio_compra, a.en_venta, a.precio_venta FROM acciones a JOIN empresas e ON a.empresa_id = e.id WHERE a.jugador_id = ?", (jugador_id,))
    r = c.fetchall()
    conn.close()
    return r

def get_ofertas_acciones():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT o.id, e.nombre, o.cantidad, o.precio_venta, j.nombre, o.cantidad * o.precio_venta as total FROM ofertas_acciones o JOIN empresas e ON o.empresa_id = e.id JOIN jugadores j ON o.jugador_id = j.id WHERE o.activa = 1 ORDER BY total ASC")
    r = c.fetchall()
    conn.close()
    return r

def comprar_acciones(jugador_id, empresa_id, cantidad, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    empresa = get_empresa_by_id(empresa_id)
    if not empresa or empresa[4] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    costo = empresa[3] * cantidad
    c.execute("SELECT saldo, moneda FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, jugador_id))
    cuenta = c.fetchone()
    if not cuenta or cuenta[0] < costo:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (costo, cuenta_id))
    c.execute("UPDATE empresas SET acciones_disponibles = acciones_disponibles - ? WHERE id = ?", (cantidad, empresa_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id = ? AND empresa_id = ? AND en_venta = 0", (jugador_id, empresa_id))
    existente = c.fetchone()
    if existente:
        c.execute("UPDATE acciones SET cantidad = cantidad + ?, precio_compra = ? WHERE id = ?", (cantidad, empresa[3], existente[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?, ?, ?, ?)", (jugador_id, empresa_id, cantidad, empresa[3]))
    conn.commit()
    conn.close()
    return True, f"Compradas {cantidad} acciones de {empresa[1]}"

def get_empresa_by_id(empresa_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,))
    r = c.fetchone()
    conn.close()
    return r

def vender_acciones(jugador_id, acciones_id, cantidad, precio_venta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM acciones WHERE id = ? AND jugador_id = ?", (acciones_id, jugador_id))
    accion = c.fetchone()
    if not accion or accion[3] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    c.execute("UPDATE acciones SET cantidad = cantidad - ? WHERE id = ?", (cantidad, acciones_id))
    c.execute("INSERT INTO ofertas_acciones (acciones_id, jugador_id, empresa_id, cantidad, precio_venta) VALUES (?, ?, ?, ?, ?)",
              (acciones_id, jugador_id, accion[2], cantidad, precio_venta))
    conn.commit()
    conn.close()
    return True, "Acciones en venta"

def comprar_oferta_acciones(comprador_id, oferta_id, cantidad, cuenta_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM ofertas_acciones WHERE id = ? AND activa = 1", (oferta_id,))
    oferta = c.fetchone()
    if not oferta or oferta[3] < cantidad:
        conn.close()
        return False, "Oferta no disponible"
    costo = oferta[4] * cantidad
    c.execute("SELECT saldo FROM cuentas WHERE id = ? AND jugador_id = ?", (cuenta_id, comprador_id))
    cuenta = c.fetchone()
    if not cuenta or cuenta[0] < costo:
        conn.close()
        return False, "Saldo insuficiente"
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE id = ?", (costo, cuenta_id))
    c.execute("SELECT id FROM cuentas WHERE jugador_id = ? LIMIT 1", (oferta[2],))
    cv = c.fetchone()
    if cv:
        c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE id = ?", (costo, cv[0]))
    c.execute("UPDATE ofertas_acciones SET cantidad = cantidad - ?, activa = CASE WHEN cantidad - ? <= 0 THEN 0 ELSE 1 END WHERE id = ?",
              (cantidad, cantidad, oferta_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id = ? AND empresa_id = ? AND en_venta = 0", (comprador_id, oferta[3]))
    existente = c.fetchone()
    if existente:
        c.execute("UPDATE acciones SET cantidad = cantidad + ? WHERE id = ?", (cantidad, existente[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?, ?, ?, ?)",
                  (comprador_id, oferta[3], cantidad, oferta[4]))
    conn.commit()
    conn.close()
    return True, "Compra exitosa"

def transferir_acciones(de_jugador, para_jugador, acciones_id, cantidad):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM acciones WHERE id = ? AND jugador_id = ?", (acciones_id, de_jugador))
    accion = c.fetchone()
    if not accion or accion[3] < cantidad:
        conn.close()
        return False, "Acciones insuficientes"
    if not get_jugador_by_id(para_jugador):
        conn.close()
        return False, "Destino no existe"
    c.execute("UPDATE acciones SET cantidad = cantidad - ? WHERE id = ?", (cantidad, acciones_id))
    c.execute("SELECT id FROM acciones WHERE jugador_id = ? AND empresa_id = ?", (para_jugador, accion[2]))
    existente = c.fetchone()
    if existente:
        c.execute("UPDATE acciones SET cantidad = cantidad + ? WHERE id = ?", (cantidad, existente[0]))
    else:
        c.execute("INSERT INTO acciones (jugador_id, empresa_id, cantidad, precio_compra) VALUES (?, ?, ?, ?)",
                  (para_jugador, accion[2], cantidad, accion[4]))
    conn.commit()
    conn.close()
    return True, "Transferencia exitosa"

def actualizar_valor_empresa(empresa_id, nuevo_valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE empresas SET valor_accion = ?, fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = ?", (nuevo_valor, empresa_id))
    conn.commit()
    conn.close()

def get_historial_financiero(jugador_id, limite=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT tipo, operacion, monto, moneda, concepto, fecha FROM transacciones_financieras WHERE jugador_id = ? ORDER BY fecha DESC LIMIT ?", (jugador_id, limite))
    r = c.fetchall()
    conn.close()
    return r

def agregar_inventario(jugador_id, nombre, clasificacion, cantidad, unidad):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO inventario (jugador_id, nombre, clasificacion, cantidad, unidad) VALUES (?, ?, ?, ?, ?)",
              (jugador_id, nombre, clasificacion, cantidad, unidad))
    conn.commit()
    conn.close()
