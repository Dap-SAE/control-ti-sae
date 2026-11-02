import io
import PIL.Image
import pandas as pd
import qrcode
import sqlite3
import streamlit as st
from datetime import datetime
import hashlib

# Configuración de página
st.set_page_config(
    page_title="Control TI - SAE", page_icon="💻", layout="wide"
)

# Notificación flotante persistente para confirmar guardados tras un st.rerun()
if "msg_exito" in st.session_state and st.session_state.msg_exito:
    st.toast(st.session_state.msg_exito, icon="🎉")
    st.session_state.msg_exito = None

DB_NAME = "control_ti.db"


def init_db():
    # Uso de gestor de contexto (with) para asegurar el cierre automático de la conexión
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # 1. COMPUTADORES
        c.execute("""
            CREATE TABLE IF NOT EXISTS computadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sucursal TEXT, estado TEXT, tipo_equipo TEXT, nombre_equipo TEXT UNIQUE,
                serial_number TEXT, mac_ethernet TEXT, mac_wifi TEXT, fecha_inicio TEXT,
                usuario TEXT, marca_modelo TEXT, procesador TEXT, ram TEXT, version_windows TEXT,
                version_antivirus TEXT, dominio_tsae TEXT, estado_actualizacion TEXT,
                act_automatica TEXT, office TEXT, cuenta_office_365 TEXT, anydesk TEXT,
                pass_any TEXT, observacion TEXT, email TEXT, acceso_sap TEXT,
                ultima_mantencion TEXT, ultima_actualizacion_planilla TEXT, ex_usuario TEXT,
                proveedor TEXT, num_factura TEXT
            )
        """)

        # 2. CUENTAS DE CORREO a 14. GPS FLOTA y USUARIOS
        tablas_sql = [
            """CREATE TABLE IF NOT EXISTS cuentas_correo (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sociedad TEXT, correo TEXT UNIQUE, persona_asignada TEXT,
                sucursal TEXT, almacenamiento_gb TEXT, estado TEXT, password TEXT, notas TEXT)""",
            """CREATE TABLE IF NOT EXISTS credenciales_o365 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta TEXT UNIQUE, power_bi TEXT, password TEXT,
                power_bi_gateway TEXT, clave_recuperacion TEXT, tenant TEXT, notas TEXT)""",
            """CREATE TABLE IF NOT EXISTS impresoras (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sucursal TEXT, ip TEXT, marca TEXT, modelo TEXT,
                serial_number TEXT, mac TEXT, fecha_compra TEXT, area TEXT, ubicacion TEXT, persona_asignada TEXT, 
                estado TEXT, toner TEXT, admin TEXT, observacion TEXT)""",
            """CREATE TABLE IF NOT EXISTS credenciales_wifi (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sucursal TEXT, ssid TEXT, password TEXT, ip TEXT, notas TEXT)""",
            """CREATE TABLE IF NOT EXISTS servidores (
                id INTEGER PRIMARY KEY AUTOINCREMENT, servidor TEXT UNIQUE, ip TEXT, usuario TEXT, password TEXT,
                password_nueva TEXT, espacio_disco TEXT, ram TEXT, notas TEXT)""",
            """CREATE TABLE IF NOT EXISTS enlaces_telecom (
                id INTEGER PRIMARY KEY AUTOINCREMENT, proveedor TEXT, sucursal TEXT, codigo_servicio TEXT,
                segmento_lan TEXT, firewall TEXT, wan TEXT, banda_ancha TEXT, notas TEXT)""",
            """CREATE TABLE IF NOT EXISTS acceso_camaras (
                id INTEGER PRIMARY KEY AUTOINCREMENT, sucursal TEXT, ip_sn TEXT, nombre TEXT, usuario TEXT, 
                password TEXT, notas TEXT)""",
            """CREATE TABLE IF NOT EXISTS tickets_red (
                id INTEGER PRIMARY KEY AUTOINCREMENT, num_ticket TEXT, fecha_apertura TEXT, sucursal TEXT,
                motivo TEXT, estado TEXT, fecha_cierre TEXT, demora TEXT, observacion TEXT)""",
            """CREATE TABLE IF NOT EXISTS tickets_gotruck (
                id INTEGER PRIMARY KEY AUTOINCREMENT, num_ticket TEXT, fecha_apertura TEXT, sucursal TEXT,
                motivo TEXT, estado TEXT, fecha_cierre TEXT, demora TEXT, observacion TEXT)""",
            """CREATE TABLE IF NOT EXISTS historial_asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_equipo TEXT, usuario TEXT,
                fecha_asignacion TEXT, fecha_devolucion TEXT, observacion TEXT)""",
            """CREATE TABLE IF NOT EXISTS asignacion_ip_entel (
                id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, client_name TEXT, 
                mac_address TEXT, lan_ip TEXT)""",
            """CREATE TABLE IF NOT EXISTS ip_libres (
                id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT, ip_disponible TEXT)""",
            
            # --- TABLA GPS  ---
            """CREATE TABLE IF NOT EXISTS gps_flota (
                id INTEGER PRIMARY KEY AUTOINCREMENT, patente TEXT, vin TEXT, tipo TEXT,
                marca TEXT, modelo TEXT, anio TEXT, imei TEXT, ultimo_reporte TEXT,
                proveedor_gps TEXT, sucursal TEXT, estado TEXT)""",
                
            # --- TABLA USUARIOS ---
            """CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE,
                password_hash TEXT, rol TEXT, estado TEXT)""",  # <--- ESTA ES LA COMA CRÍTICA FALTANTE
                
            # --- TABLA SERVIDORES GCP ---
            """CREATE TABLE IF NOT EXISTS usuarios_gcp (
                id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, sucursal TEXT, 
                usuario_ad_cloud TEXT, name_domain_user TEXT, password_ad_cloud TEXT, 
                usuario_sap TEXT, status TEXT, cliente TEXT, acceso_sap_31_01 TEXT)""",
                
            # --- TABLA GCP RESUMEN (NUEVA) ---
            """CREATE TABLE IF NOT EXISTS gcp_resumen (
                id INTEGER PRIMARY KEY AUTOINCREMENT, correo TEXT, usuario TEXT, 
                password TEXT, acceso_maquina TEXT)"""
        ]

        # PRIMERO: Crear todas las tablas
        for query in tablas_sql:
            c.execute(query)

        # SEGUNDO: Verificar y crear el usuario administrador por defecto
        c.execute("SELECT COUNT(*) FROM usuarios")
        if c.fetchone()[0] == 0:
            default_hash = hashlib.sha256("admin123".encode()).hexdigest()
            conn.execute("INSERT INTO usuarios (username, password_hash, rol, estado) VALUES (?, ?, ?, ?)", 
                         ("admin", default_hash, "Administrador", "ACTIVO"))

        # Migración automática de computadores
        c.execute("PRAGMA table_info(computadores)")
        cols_existentes = [col[1] for col in c.fetchall()]
        
        if "teamviewer" in cols_existentes and "pass_any" not in cols_existentes:
            try: conn.execute("ALTER TABLE computadores RENAME COLUMN teamviewer TO pass_any")
            except Exception: pass
        if "proveedor" not in cols_existentes:
            try: conn.execute("ALTER TABLE computadores ADD COLUMN proveedor TEXT")
            except Exception: pass
        if "num_factura" not in cols_existentes:
            try: conn.execute("ALTER TABLE computadores ADD COLUMN num_factura TEXT")
            except Exception: pass

init_db()


# --- FUNCIONES DE BASE DE DATOS OPTIMIZADAS ---
def run_query(query, params=()):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Error de base de datos (Lectura): {e}")
        return pd.DataFrame()


def execute_db(query, params=()):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(query, params)
            # El commit es automático al salir del bloque 'with' exitosamente
    except Exception as e:
        st.error(f"Error de base de datos (Escritura): {e}")
        raise e


def execute_many_db(query, params_list):
    """Ejecuta inserciones/actualizaciones masivas de forma optimizada y segura."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.executemany(query, params_list)
    except Exception as e:
        st.error(f"Error de base de datos (Escritura Masiva): {e}")
        raise e

# --- MATRIZ DE PERMISOS POR ROL ---
# Define qué módulos puede ver cada rol. Usa "*" para acceso total.
PERMISOS = {
    "Administrador": ["*"],
    "Técnico": ["Panel General", "Equipos", "Tickets", "Cuentas Redes", "Servidores GCP"],
    "Lector": ["Panel General"]
}

def tiene_permiso(rol, modulo_categoria):
    if rol not in PERMISOS: return False
    if "*" in PERMISOS[rol]: return True
    return modulo_categoria in PERMISOS[rol]

# --- ESTADO DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.rol = None
    st.session_state.usuario_actual = None

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🔐 Acceso al Sistema - Control TI")
    
    col_log1, col_log2, col_log3 = st.columns([1, 2, 1])
    with col_log2:
        with st.form("form_login"):
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            btn_login = st.form_submit_button("Ingresar", use_container_width=True)
            
            if btn_login:
                hash_input = hashlib.sha256(password_input.encode()).hexdigest()
                df_user = run_query("SELECT username, rol FROM usuarios WHERE username=? AND password_hash=? AND estado='ACTIVO'", (usuario_input, hash_input))
                
                if not df_user.empty:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = df_user.iloc[0]["username"]
                    st.session_state.rol = df_user.iloc[0]["rol"]
                    st.session_state.modulo_activo = "Panel General: Resumen General"
                    st.rerun()
                else:
                    st.error("⚠️ Credenciales incorrectas o usuario inactivo.")
    
    # Detiene la ejecución del resto del script si no está logueado
    st.stop()

# --- INTERFAZ BARRA LATERAL ---
st.sidebar.title("🗂️ Control TI - Menú")

# Info del usuario y Logout
st.sidebar.success(f"👤 **{st.session_state.usuario_actual}** | Rol: {st.session_state.rol}")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
    st.session_state.autenticado = False
    st.rerun()
st.sidebar.divider()

if "modulo_activo" not in st.session_state:
    st.session_state.modulo_activo = "Panel General: Resumen General"

# 1. PANEL GENERAL
if tiene_permiso(st.session_state.rol, "Panel General"):
    with st.sidebar.expander("📊 Panel General", expanded=True):
        if st.button("📊 Resumen General", use_container_width=True):
            st.session_state.modulo_activo = "Panel General: Resumen General"

# 2. EQUIPOS / COMPUTADORES
if tiene_permiso(st.session_state.rol, "Equipos"):
    with st.sidebar.expander("💻 Equipos / Computadores"):
        if st.button("➕ Registrar Equipo", use_container_width=True):
            st.session_state.modulo_activo = "Equipos: Registrar Equipo"
        if st.button("🔍 Buscar", use_container_width=True):
            st.session_state.modulo_activo = "Equipos: Buscar"
        if st.button("🏷️ Generador de Etiquetas QR", use_container_width=True):
            st.session_state.modulo_activo = "Equipos: Generar QR"

# 3. CUENTAS & REDES
if tiene_permiso(st.session_state.rol, "Cuentas Redes"):
    with st.sidebar.expander("🌐 Cuentas & Redes"):
        if st.button("✉️ Cuentas correo", use_container_width=True):
            st.session_state.modulo_activo = "Casilla correo"
        if st.button("🔐 Licencias Office 365", use_container_width=True):
            st.session_state.modulo_activo = "Licencias Office 365"
        if st.button("🛜 Redes WiFi", use_container_width=True):
            st.session_state.modulo_activo = "Redes WiFi"
        if st.button("🌐 Asignación IP Entel", use_container_width=True):
            st.session_state.modulo_activo = "Asignación IP Entel"
        if st.button("🖥️ Servidores Local", use_container_width=True):
            st.session_state.modulo_activo = "Servidores Local"
        if st.button("📹 Acceso a Cámaras", use_container_width=True):
            st.session_state.modulo_activo = "Acceso a Cámaras"
        if st.button("📡 Enlaces Entel", use_container_width=True):
            st.session_state.modulo_activo = "Enlaces Entel"
        if st.button("🖨️ Impresoras", use_container_width=True):
            st.session_state.modulo_activo = "Impresoras"
        if st.button("👥 Usuarios - Servidores GCP", use_container_width=True):
            st.session_state.modulo_activo = "Usuarios - Servidores GCP"    

# 4. REGISTRO DE TICKET
if tiene_permiso(st.session_state.rol, "Tickets"):
    with st.sidebar.expander("🎫 Registro de Ticket"):
        if st.button("📡 Historial de Tickets Entel", use_container_width=True):
            st.session_state.modulo_activo = "Historial de Tickets Entel"
        if st.button("🚛 Historial de Tickets Gotruck", use_container_width=True):
            st.session_state.modulo_activo = "Historial de Tickets Gotruck"

# 5. CARGA DE DATOS
if tiene_permiso(st.session_state.rol, "Carga Datos"):
    with st.sidebar.expander("🚀 Carga de Datos"):
        if st.button("🚀 Carga Masiva (Excel Completo)", use_container_width=True):
            st.session_state.modulo_activo = "Carga Masiva (Excel Completo)"

# 6. GESTIÓN DE FLOTA Y GPS (NUEVO MENÚ)
if tiene_permiso(st.session_state.rol, "Flota GPS"):
    with st.sidebar.expander("📍 Flota & GPS"):
        if st.button("🛰️ Control de GPS", use_container_width=True):
            st.session_state.modulo_activo = "Control de GPS"

# --- MÓDULO EXCLUSIVO DE ADMINISTRACIÓN ---
if tiene_permiso(st.session_state.rol, "Administrador"):
    st.sidebar.divider()
    if st.sidebar.button("⚙️ Gestión de Usuarios", use_container_width=True):
        st.session_state.modulo_activo = "Gestion Usuarios"


# ==============================================================================
# RENDERIZADO DE CONTENIDO SEGÚN MÓDULO SELECCIONADO
# ==============================================================================
mod = st.session_state.modulo_activo

# ------------------------------------------------------------------------------
# 1. PANEL GENERAL - DASHBOARD EJECUTIVO (SUCURSALES FIJAS)
# ------------------------------------------------------------------------------
if mod == "Panel General: Resumen General":
    col_titulo, col_btn = st.columns([3, 1])
    with col_titulo:
        st.title("📊 Panel General - Dashboard Ejecutivo de TI")
        st.markdown(
            "Vista consolidada en tiempo real de todo el inventario informático y servicios de la empresa."
        )
    with col_btn:
        st.write("")
        if st.button("🔄 Refrescar Datos", use_container_width=True):
            st.rerun()

    # Carga de datos reales
    dfs = {
        "eq": run_query("SELECT * FROM computadores"),
        "mail": run_query("SELECT * FROM cuentas_correo"),
        "o365": run_query("SELECT * FROM credenciales_o365"),
        "imp": run_query("SELECT * FROM impresoras"),
        "srv": run_query("SELECT * FROM servidores"),
        "wifi": run_query("SELECT * FROM credenciales_wifi"),
        "enl": run_query("SELECT * FROM enlaces_telecom"),
        "cam": run_query("SELECT * FROM acceso_camaras"),
        "tkt": run_query("SELECT * FROM tickets_red")
    }

    SUCURSALES_FIJAS = [
        "Coquimbo", "Santiago", "Iquique", "La Chimba", 
        "La Negra", "Copiapo", "Calama", "Caldera", "Mejillones"
    ]

    def estandarizar_sucursal(val):
        if not val or pd.isna(val):
            return "OTRA"
        s = str(val).strip().upper()
        if "COQUIMBO" in s or "COQ" in s: return "Coquimbo"
        elif "SANTIAGO" in s or "STGO" in s: return "Santiago"
        elif "IQUIQUE" in s or "IQQ" in s: return "Iquique"
        elif "CHIMBA" in s: return "La Chimba"
        elif "NEGRA" in s: return "La Negra"
        elif "COPIAPO" in s: return "Copiapo"
        elif "CALAMA" in s: return "Calama"
        elif "CALDERA" in s: return "Caldera"
        elif "MEJILLONES" in s: return "Mejillones"
        else: return "Otra"

    for key, df in dfs.items():
        if not df.empty and "sucursal" in df.columns:
            dfs[key]["sucursal_std"] = df["sucursal"].apply(estandarizar_sucursal)

    if not dfs["eq"].empty and "estado" in dfs["eq"].columns:
        dfs["eq"]["estado"] = dfs["eq"]["estado"].fillna("SIN ESTADO").astype(str).str.strip().str.upper()

    col_filtro, _ = st.columns([1, 2])
    sucursales_disp = ["Todas las Sucursales"] + SUCURSALES_FIJAS
    sucursal_sel = col_filtro.selectbox("📌 Filtrar Dashboard por Sucursal:", sucursales_disp)

    if sucursal_sel != "Todas las Sucursales":
        for key in ["eq", "mail", "imp", "wifi", "enl", "cam", "tkt"]:
            if not dfs[key].empty and "sucursal_std" in dfs[key].columns:
                dfs[key] = dfs[key][dfs[key]["sucursal_std"] == sucursal_sel]

    st.divider()

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("💻 Computadores", len(dfs["eq"]))
    kpi2.metric("✉️ Casillas Correo", len(dfs["mail"]))
    kpi3.metric("🔐 Licencias 365", len(dfs["o365"]))
    kpi4.metric("🖨️ Impresoras", len(dfs["imp"]))
    kpi5.metric("🖥️ Servidores", len(dfs["srv"]))

    st.markdown("---")

    c_left, c_right = st.columns(2)

    with c_left:
        st.subheader("🖥️ Equipos por Sucursal")
        if not dfs["eq"].empty and "sucursal_std" in dfs["eq"].columns:
            df_suc = dfs["eq"]["sucursal_std"].value_counts().reset_index()
            df_suc.columns = ["Sucursal", "Cantidad"]
            st.bar_chart(data=df_suc, x="Sucursal", y="Cantidad", use_container_width=True)
        else:
            st.info("Sin información de computadores registrada.")

    with c_right:
        st.subheader("📊 Estado Equipos")
        if not dfs["eq"].empty and "estado" in dfs["eq"].columns:
            df_est = dfs["eq"]["estado"].value_counts().reset_index()
            df_est.columns = ["Estado", "Cantidad"]
            st.bar_chart(data=df_est, x="Estado", y="Cantidad", use_container_width=True)
        else:
            st.info("Sin información de estados de equipos.")

    st.markdown("---")

    c_m1, c_m2, c_m3 = st.columns(3)

    with c_m1:
        st.subheader("✉️ Casillas de Correo")
        if not dfs["mail"].empty and "sucursal_std" in dfs["mail"].columns:
            df_m_suc = dfs["mail"]["sucursal_std"].value_counts().reset_index()
            df_m_suc.columns = ["Sucursal", "Casillas"]
            st.dataframe(df_m_suc, use_container_width=True, hide_index=True)
        else:
            st.info("Sin cuentas registradas.")

    with c_m2:
        st.subheader("🖨️ Impresoras")
        if not dfs["imp"].empty and "marca" in dfs["imp"].columns:
            df_i_m = dfs["imp"]["marca"].value_counts().reset_index()
            df_i_m.columns = ["Marca", "Cantidad"]
            st.dataframe(df_i_m, use_container_width=True, hide_index=True)
        else:
            st.info("Sin impresoras registradas.")

    with c_m3:
        st.subheader("🎫 Estado de Tickets")
        if not dfs["tkt"].empty and "estado" in dfs["tkt"].columns:
            df_tk_est = dfs["tkt"]["estado"].value_counts().reset_index()
            df_tk_est.columns = ["Estado Ticket", "Cantidad"]
            st.dataframe(df_tk_est, use_container_width=True, hide_index=True)
        else:
            st.info("Sin tickets registrados.")

    st.markdown("---")

    st.subheader("📡 Resumen de Conectividad & Servicios Críticos")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("🛜 Redes WiFi", len(dfs["wifi"]))
    i2.metric("📡 Enlaces Telecom", len(dfs["enl"]))
    i3.metric("📹 DVRs / Cámaras", len(dfs["cam"]))
    i4.metric("🎫 Total Tickets Historico", len(dfs["tkt"]))

# ------------------------------------------------------------------------------
# RESTO DE MÓDULOS
# ------------------------------------------------------------------------------
elif mod == "Equipos: Registrar Equipo":
    st.title("💻 Equipos / Computadores - Registrar Equipo")
    ESTADOS = ["ACTIVO", "INACTIVO", "STOCK", "EN MANTENCION", "BAJA"]
    TIPOS_EQUIPO = ["NOTEBOOK", "DESKTOP", "ALL IN ONE", "SERVER"]

    df_s = run_query("SELECT DISTINCT sucursal FROM computadores WHERE sucursal IS NOT NULL AND sucursal != ''")
    sucursales_dinamicas = (
        sorted(df_s["sucursal"].astype(str).str.strip().unique().tolist())
        if not df_s.empty else ["Coquimbo", "Santiago", "Iquique", "La Chimba", "La Negra", "Copiapo", "Calama", "Caldera", "Mejillones"]
    )

    with st.form("form_nuevo"):
        col1, col2, col3 = st.columns(3)
        
        sucursal = col1.selectbox("Sucursal", sucursales_dinamicas)
        estado = col1.selectbox("Estado", ESTADOS)
        tipo_equipo = col1.selectbox("Tipo Equipo", TIPOS_EQUIPO)
        nombre_equipo = col1.text_input("Nombre Equipo (ej: DESKTOP-XYZ) *")
        serial_number = col1.text_input("Serial Number")
        usuario = col1.text_input("Usuario Asignado")
        ex_usuario = col1.text_input("Ex Usuario")
        email = col1.text_input("Email Usuario")
        proveedor = col1.text_input("Proveedor")

        marca_modelo = col2.text_input("Marca / Modelo")
        procesador = col2.text_input("Procesador")
        ram = col2.text_input("Memoria RAM")
        version_windows = col2.text_input("Versión Windows")
        version_antivirus = col2.text_input("Versión Antivirus")
        mac_ethernet = col2.text_input("MAC Ethernet")
        mac_wifi = col2.text_input("MAC Wifi")
        fecha_inicio = col2.date_input("Fecha Inicio").strftime("%Y-%m-%d")
        num_factura = col2.text_input("N° Factura")

        office = col3.text_input("Versión Office")
        cuenta_office_365 = col3.text_input("Cuenta Office 365")
        anydesk = col3.text_input("ID Anydesk")
        teamviewer = col3.text_input("Pass-Any")
        acceso_sap = col3.selectbox("Acceso a SAP", ["SI", "NO", "N/A"])
        dominio_tsae = col3.selectbox("Dominio TSAE", ["si", "no"])
        act_automatica = col3.text_input("Act. Automática")
        ultima_mantencion = col3.text_input("Última Mantención")
        observacion = st.text_area("Observaciones")

        if st.form_submit_button("Guardar Equipo"):
            if nombre_equipo:
                try:
                    execute_db(
                        """
                        INSERT OR REPLACE INTO computadores (
                            sucursal, estado, tipo_equipo, nombre_equipo, serial_number, mac_ethernet, mac_wifi,
                            fecha_inicio, usuario, marca_modelo, procesador, ram, version_windows, version_antivirus,
                            dominio_tsae, act_automatica, office, cuenta_office_365, anydesk, pass_any, observacion,
                            email, acceso_sap, ultima_mantencion, ex_usuario, proveedor, num_factura
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (sucursal, estado, tipo_equipo, nombre_equipo, serial_number, mac_ethernet, mac_wifi,
                         fecha_inicio, usuario, marca_modelo, procesador, ram, version_windows, version_antivirus,
                         dominio_tsae, act_automatica, office, cuenta_office_365, anydesk, teamviewer, observacion,
                         email, acceso_sap, ultima_mantencion, ex_usuario, proveedor, num_factura)
                    )
                    st.session_state.msg_exito = f"Equipo '{nombre_equipo}' guardado correctamente."
                    st.rerun()
                except Exception as e:
                    pass
            else:
                st.warning("El Nombre de Equipo es obligatorio.")

elif mod == "Equipos: Buscar":
    st.title("💻 Equipos / Computadores - Búsqueda Avanzada")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar, o desplazarte hasta la última fila vacía (símbolo '+') para **agregar un nuevo equipo**. Presiona 'Guardar Cambios' al terminar.*")

    col_txt, col_qr = st.columns([3, 1])

    with col_txt:
        busqueda_txt = st.text_input("Buscar por Nombre de Equipo, Serial, Anydesk, Usuario, Marca o Email")

    with col_qr:
        st.write("")
        st.write("")
        escaneo_qr = st.toggle("📷 Leer QR con Cámara", value=False)

    busqueda = busqueda_txt

    if escaneo_qr:
        st.info("📷 Apunta con tu cámara al código QR impreso en el equipo para buscarlo automáticamente.")
        qr_img = st.camera_input("Capturar código QR")
        if qr_img:
            try:
                import cv2
                import numpy as np

                bytes_data = qr_img.getvalue()
                cv_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(cv_img)

                if data:
                    st.success(f"✅ Código QR detectado: `{data}`")
                    if "EQUIPO:" in data:
                        busqueda = data.split("EQUIPO:")[1].split("|")[0].strip()
                    else:
                        busqueda = data.strip()
                else:
                    st.warning("⚠️ No se detectó un código QR válido en la captura. Intenta centrarlo mejor.")
            except ImportError:
                st.error("⚠️ Para procesar capturas de cámara debes instalar OpenCV (`pip install opencv-python`).")

    q = """
        SELECT id, sucursal, estado, tipo_equipo, nombre_equipo, serial_number, mac_ethernet, mac_wifi, fecha_inicio,
               usuario, marca_modelo, procesador, ram, version_windows, version_antivirus, dominio_tsae,
               act_automatica, office, cuenta_office_365, anydesk, pass_any AS "Pass-Any", observacion, email,
               acceso_sap, ultima_mantencion, ex_usuario, proveedor AS "Proveedor", num_factura AS "N° Factura"
        FROM computadores
    """
    params = ()
    if busqueda:
        q += " WHERE nombre_equipo LIKE ? OR serial_number LIKE ? OR usuario LIKE ? OR anydesk LIKE ? OR marca_modelo LIKE ? OR email LIKE ?"
        term = f"%{busqueda}%"
        params = (term, term, term, term, term, term)

    res = run_query(q, params)

    # Si está vacío, creamos la estructura base para que siempre se vea la tabla y permita agregar
    if res.empty:
        res = pd.DataFrame(columns=["id", "sucursal", "estado", "tipo_equipo", "nombre_equipo", "serial_number", "mac_ethernet", "mac_wifi", "fecha_inicio", "usuario", "marca_modelo", "procesador", "ram", "version_windows", "version_antivirus", "dominio_tsae", "act_automatica", "office", "cuenta_office_365", "anydesk", "Pass-Any", "observacion", "email", "acceso_sap", "ultima_mantencion", "ex_usuario", "Proveedor", "N° Factura"])

    res_editada = st.data_editor(
        res, hide_index=True, use_container_width=True, 
        num_rows="dynamic", # <-- Propiedad habilitada para agregar registros
        disabled=["id"],    # <-- Se removió nombre_equipo para que puedas nombrar los equipos nuevos
        key="editor_computadores_buscar"
    )

    col_save, col_dl = st.columns([1, 1])

    with col_save:
        if st.button("💾 Guardar Cambios en Base de Datos", key="btn_save_eq"):
            editor_state = st.session_state.get("editor_computadores_buscar", {})
            edited_rows = editor_state.get("edited_rows", {})
            deleted_rows = editor_state.get("deleted_rows", [])

            # Lógica de historial de asignaciones solo para filas existentes
            for row_idx, changes in edited_rows.items():
                if row_idx < len(res):
                    nombre_equipo = res.iloc[row_idx]["nombre_equipo"]
                    
                    if "usuario" in changes:
                        nuevo_usuario = changes["usuario"]
                        usuario_anterior = res.iloc[row_idx]["usuario"]
                        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        execute_db("""
                            UPDATE historial_asignaciones 
                            SET fecha_devolucion = ? 
                            WHERE nombre_equipo = ? AND fecha_devolucion IS NULL
                        """, (fecha_actual, nombre_equipo))

                        execute_db("""
                            INSERT INTO historial_asignaciones (nombre_equipo, usuario, fecha_asignacion, observacion)
                            VALUES (?, ?, ?, ?)
                        """, (nombre_equipo, nuevo_usuario, fecha_actual, f"Reasignado (Anterior: {usuario_anterior})"))

            def clean_field(val):
                return "" if pd.isna(val) or val is None else str(val).strip()

            datos_actualizacion = []
            datos_insercion = []

            for _, row in res_editada.iterrows():
                row_id = row.get("id")
                tupla_datos = (
                    clean_field(row.get("sucursal")), clean_field(row.get("estado")), clean_field(row.get("tipo_equipo")),
                    clean_field(row.get("nombre_equipo")), clean_field(row.get("serial_number")), clean_field(row.get("mac_ethernet")), 
                    clean_field(row.get("mac_wifi")), clean_field(row.get("fecha_inicio")), clean_field(row.get("usuario")), 
                    clean_field(row.get("marca_modelo")), clean_field(row.get("procesador")), clean_field(row.get("ram")), 
                    clean_field(row.get("version_windows")), clean_field(row.get("version_antivirus")), clean_field(row.get("dominio_tsae")), 
                    clean_field(row.get("act_automatica")), clean_field(row.get("office")), clean_field(row.get("cuenta_office_365")), 
                    clean_field(row.get("anydesk")), clean_field(row.get("Pass-Any")), clean_field(row.get("observacion")), 
                    clean_field(row.get("email")), clean_field(row.get("acceso_sap")), clean_field(row.get("ultima_mantencion")), 
                    clean_field(row.get("ex_usuario")), clean_field(row.get("Proveedor")), clean_field(row.get("N° Factura"))
                )

                if pd.isna(row_id):
                    # Es una nueva fila
                    datos_insercion.append(tupla_datos)
                else:
                    # Es una actualización
                    datos_actualizacion.append(tupla_datos + (row_id,))

            query_update = """
                UPDATE computadores
                SET sucursal=?, estado=?, tipo_equipo=?, nombre_equipo=?, serial_number=?, mac_ethernet=?, mac_wifi=?,
                    fecha_inicio=?, usuario=?, marca_modelo=?, procesador=?, ram=?, version_windows=?,
                    version_antivirus=?, dominio_tsae=?, act_automatica=?, office=?, cuenta_office_365=?,
                    anydesk=?, pass_any=?, observacion=?, email=?, acceso_sap=?, ultima_mantencion=?, ex_usuario=?,
                    proveedor=?, num_factura=?
                WHERE id=?
            """
            
            query_insert = """
                INSERT INTO computadores (
                    sucursal, estado, tipo_equipo, nombre_equipo, serial_number, mac_ethernet, mac_wifi,
                    fecha_inicio, usuario, marca_modelo, procesador, ram, version_windows, version_antivirus,
                    dominio_tsae, act_automatica, office, cuenta_office_365, anydesk, pass_any, observacion,
                    email, acceso_sap, ultima_mantencion, ex_usuario, proveedor, num_factura
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """
            try:
                # 1. Actualizar registros modificados
                if datos_actualizacion:
                    execute_many_db(query_update, datos_actualizacion)
                # 2. Insertar registros nuevos
                if datos_insercion:
                    execute_many_db(query_insert, datos_insercion)
                # 3. Borrar registros eliminados en la interfaz (opcional, habilita selección de fila y "Suprimir")
                if deleted_rows:
                    for r_idx in deleted_rows:
                        d_id = res.iloc[r_idx]["id"]
                        execute_db("DELETE FROM computadores WHERE id=?", (d_id,))

                st.session_state.msg_exito = "¡Información de equipos actualizada y guardada correctamente!"
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    with col_dl:
        res_editada.to_excel("reporte_inventario.xlsx", index=False)
        with open("reporte_inventario.xlsx", "rb") as f:
            st.download_button("📥 Descargar Resultado en Excel", data=f, file_name="Equipos_Filtrados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    
    st.divider()
    st.subheader("🕰️ Historial de Asignaciones por Equipo")
    
    equipo_historial = st.selectbox("Selecciona un equipo para ver su historial de usuarios:", res["nombre_equipo"].dropna().unique().tolist())
    
    if equipo_historial:
        df_historial = run_query(
            "SELECT usuario AS 'Usuario Asignado', fecha_asignacion AS 'Fecha de Asignación', fecha_devolucion AS 'Fecha Devolución', observacion AS 'Observaciones' FROM historial_asignaciones WHERE nombre_equipo = ? ORDER BY id DESC", 
            (equipo_historial,)
        )
        if not df_historial.empty:
            st.dataframe(df_historial, use_container_width=True, hide_index=True)
        else:
            st.info(f"El equipo {equipo_historial} aún no tiene un historial de re-asignaciones registrado.")


# ------------------------------------------------------------------------------
# MÓDULO EXTERNO: GPS Y FLOTA
# ------------------------------------------------------------------------------
elif mod == "Control de GPS":
    import gps  # Importamos el nuevo archivo gps.py
    gps.render_gps_module()


# ------------------------------------------------------------------------------
# LICENCIAS OFFICE 365
# ------------------------------------------------------------------------------
elif mod == "Licencias Office 365":
    st.title("🔐 Cuentas & Redes - Licencias Office 365")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar la contraseña o datos y luego presionar 'Guardar Cambios'.*")

    df_o365 = run_query('SELECT id, cuenta, power_bi, password AS "Contraseña", power_bi_gateway, clave_recuperacion AS "Clave de recuperacion" FROM credenciales_o365')

    if not df_o365.empty:
        st.metric("Total Cuentas 365", len(df_o365))
        df_editada = st.data_editor(df_o365, hide_index=True, use_container_width=True, disabled=["id", "cuenta"], key="editor_o365")

        if st.button("💾 Guardar Cambios en Base de Datos", key="btn_o365"):
            datos = [(row["power_bi"], row["Contraseña"], row["power_bi_gateway"], row["Clave de recuperacion"], row["id"]) for _, row in df_editada.iterrows()]
            try:
                execute_many_db("UPDATE credenciales_o365 SET power_bi = ?, password = ?, power_bi_gateway = ?, clave_recuperacion = ? WHERE id = ?", datos)
                st.session_state.msg_exito = "¡Contraseñas y datos actualizados correctamente!"
                st.rerun()
            except: pass
    else:
        st.info("No hay licencias cargadas.")

# ------------------------------------------------------------------------------
# REDES WIFI
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# REDES WIFI
# ------------------------------------------------------------------------------
elif mod == "Redes WiFi":
    st.title("🛜 Cuentas & Redes - Redes WiFi")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar. Para **agregar una nueva red**, desplázate hasta la última fila vacía (tiene un símbolo '+'). Selecciona filas y presiona la tecla 'Suprimir' o 'Delete' para borrarlas.*")

    df_wifi = run_query('SELECT id, sucursal AS "Sucursal", ssid AS "Nombre SSID", password AS "Contraseña", ip AS "IP", notas AS "Notas" FROM credenciales_wifi')

    # Si la base de datos está vacía, mostramos la tabla en blanco con las columnas correctas
    if df_wifi.empty:
        df_wifi = pd.DataFrame(columns=["id", "Sucursal", "Nombre SSID", "Contraseña", "IP", "Notas"])

    # Tabla dinámica que permite agregar y borrar filas
    df_wifi_editada = st.data_editor(
        df_wifi, 
        hide_index=True, 
        use_container_width=True, 
        num_rows="dynamic",  # <--- Esta es la instrucción clave para agregar más redes
        disabled=["id"], 
        key="editor_wifi"
    )

    if st.button("💾 Guardar Cambios en Base de Datos", key="btn_wifi"):
        cambios = st.session_state.get("editor_wifi", {})
        try:
            with sqlite3.connect(DB_NAME) as conn:
                # 1. Modificar redes existentes
                for row_idx, updates in cambios.get("edited_rows", {}).items():
                    real_id = int(df_wifi.iloc[int(row_idx)]["id"])
                    sucursal = updates.get("Sucursal", df_wifi.iloc[int(row_idx)]["Sucursal"])
                    ssid = updates.get("Nombre SSID", df_wifi.iloc[int(row_idx)]["Nombre SSID"])
                    password = updates.get("Contraseña", df_wifi.iloc[int(row_idx)]["Contraseña"])
                    ip = updates.get("IP", df_wifi.iloc[int(row_idx)]["IP"])
                    notas = updates.get("Notas", df_wifi.iloc[int(row_idx)]["Notas"])
                    
                    conn.execute("UPDATE credenciales_wifi SET sucursal=?, ssid=?, password=?, ip=?, notas=? WHERE id=?", 
                                 (sucursal, ssid, password, ip, notas, real_id))
                
                # 2. Agregar nuevas redes (Filas nuevas)
                for new_row in cambios.get("added_rows", []):
                    sucursal = new_row.get("Sucursal", "")
                    ssid = new_row.get("Nombre SSID", "")
                    password = new_row.get("Contraseña", "")
                    ip = new_row.get("IP", "")
                    notas = new_row.get("Notas", "")
                    
                    conn.execute("INSERT INTO credenciales_wifi (sucursal, ssid, password, ip, notas) VALUES (?, ?, ?, ?, ?)", 
                                 (sucursal, ssid, password, ip, notas))
                    
                # 3. Eliminar redes (Filas borradas)
                for row_idx in cambios.get("deleted_rows", []):
                    real_id = int(df_wifi.iloc[int(row_idx)]["id"])
                    conn.execute("DELETE FROM credenciales_wifi WHERE id=?", (real_id,))
                    
            st.session_state.msg_exito = "¡Redes WiFi actualizadas correctamente!"
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

# ------------------------------------------------------------------------------
# ASIGNACIÓN IP ENTEL (NUEVO MÓDULO)
# ------------------------------------------------------------------------------
elif mod == "Asignación IP Entel":
    st.title("🌐 Cuentas & Redes - Asignación IP Entel")
    st.markdown("💡 *Administra y filtra las direcciones IP (Asignadas y Libres). Puedes agregar nuevas filas al final de la tabla y se guardarán en la categoría que tengas filtrada.*")

    # 1. IP ASIGNADAS
    st.subheader("📡 IP Asignadas (Entel Nueva)")
    df_entel = run_query('SELECT id, categoria AS "Categoría", client_name AS "Client Name", mac_address AS "MAC Address", lan_ip AS "LAN IP" FROM asignacion_ip_entel')
    
    if df_entel.empty:
        df_entel = pd.DataFrame(columns=["id", "Categoría", "Client Name", "MAC Address", "LAN IP"])
        
    cat_entel = ["Todas"] + [c for c in df_entel["Categoría"].dropna().unique() if c]
    
    # --- NUEVA SECCIÓN DE FILTROS (BÚSQUEDA Y CATEGORÍA) ---
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        busqueda_ip = st.text_input("🔍 Buscar por Nombre, MAC o IP:")
    with col_f2:
        filtro_cat_e = st.selectbox("📌 Filtrar Asignadas por Categoría:", cat_entel)
    
    df_entel_view = df_entel.copy()
    
    # Aplicar filtro de Categoría
    if filtro_cat_e != "Todas" and not df_entel_view.empty:
        df_entel_view = df_entel_view[df_entel_view["Categoría"] == filtro_cat_e]
        
    # Aplicar filtro de Búsqueda
    if busqueda_ip and not df_entel_view.empty:
        mask = (
            df_entel_view["Client Name"].astype(str).str.contains(busqueda_ip, case=False, na=False) |
            df_entel_view["MAC Address"].astype(str).str.contains(busqueda_ip, case=False, na=False) |
            df_entel_view["LAN IP"].astype(str).str.contains(busqueda_ip, case=False, na=False)
        )
        df_entel_view = df_entel_view[mask]
        
    df_entel_view = df_entel_view.reset_index(drop=True)

    df_entel_edit = st.data_editor(
        df_entel_view, 
        hide_index=True, 
        use_container_width=True, 
        num_rows="dynamic",
        disabled=["id"],
        key="editor_entel"
    )
    
    if st.button("💾 Guardar Cambios Asignadas", key="btn_save_entel"):
        cambios = st.session_state.get("editor_entel", {})
        try:
            with sqlite3.connect(DB_NAME) as conn:
                # Modificaciones
                for row_idx, updates in cambios.get("edited_rows", {}).items():
                    real_id = int(df_entel_view.iloc[int(row_idx)]["id"])
                    cat = updates.get("Categoría", df_entel_view.iloc[int(row_idx)]["Categoría"])
                    c_name = updates.get("Client Name", df_entel_view.iloc[int(row_idx)]["Client Name"])
                    mac = updates.get("MAC Address", df_entel_view.iloc[int(row_idx)]["MAC Address"])
                    ip = updates.get("LAN IP", df_entel_view.iloc[int(row_idx)]["LAN IP"])
                    conn.execute("UPDATE asignacion_ip_entel SET categoria=?, client_name=?, mac_address=?, lan_ip=? WHERE id=?", (cat, c_name, mac, ip, real_id))
                
                # Nuevas filas
                for new_row in cambios.get("added_rows", []):
                    cat = new_row.get("Categoría", filtro_cat_e if filtro_cat_e != "Todas" else "General")
                    c_name = new_row.get("Client Name", "")
                    mac = new_row.get("MAC Address", "")
                    ip = new_row.get("LAN IP", "")
                    conn.execute("INSERT INTO asignacion_ip_entel (categoria, client_name, mac_address, lan_ip) VALUES (?, ?, ?, ?)", (cat, c_name, mac, ip))
                    
                # Filas eliminadas
                for row_idx in cambios.get("deleted_rows", []):
                    real_id = int(df_entel_view.iloc[int(row_idx)]["id"])
                    conn.execute("DELETE FROM asignacion_ip_entel WHERE id=?", (real_id,))
                    
            st.session_state.msg_exito = "¡Asignaciones IP Entel guardadas correctamente!"
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar asignaciones: {e}")

    st.divider()

    # 2. IP LIBRES
    st.subheader("🆓 IP Libres")
    df_libres = run_query('SELECT id, categoria AS "Categoría", ip_disponible AS "IP Disponible" FROM ip_libres')
    
    if df_libres.empty:
        df_libres = pd.DataFrame(columns=["id", "Categoría", "IP Disponible"])
        
    cat_libres = ["Todas"] + [c for c in df_libres["Categoría"].unique() if c]
    
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        busqueda_libre = st.text_input("🔍 Buscar IP Libre:")
    with col_l2:
        filtro_cat_l = st.selectbox("📌 Filtrar Libres por Categoría:", cat_libres)
    
    df_libres_view = df_libres.copy()
    
    if filtro_cat_l != "Todas" and not df_libres_view.empty:
        df_libres_view = df_libres_view[df_libres_view["Categoría"] == filtro_cat_l]
        
    if busqueda_libre and not df_libres_view.empty:
        df_libres_view = df_libres_view[df_libres_view["IP Disponible"].astype(str).str.contains(busqueda_libre, case=False, na=False)]
        
    df_libres_view = df_libres_view.reset_index(drop=True)

    df_libres_edit = st.data_editor(
        df_libres_view, 
        hide_index=True, 
        use_container_width=True, 
        num_rows="dynamic",
        disabled=["id"],
        key="editor_libres"
    )
    
    if st.button("💾 Guardar Cambios IP Libres", key="btn_save_libres"):
        cambios = st.session_state.get("editor_libres", {})
        try:
            with sqlite3.connect(DB_NAME) as conn:
                for row_idx, updates in cambios.get("edited_rows", {}).items():
                    real_id = int(df_libres_view.iloc[int(row_idx)]["id"])
                    cat = updates.get("Categoría", df_libres_view.iloc[int(row_idx)]["Categoría"])
                    ip = updates.get("IP Disponible", df_libres_view.iloc[int(row_idx)]["IP Disponible"])
                    conn.execute("UPDATE ip_libres SET categoria=?, ip_disponible=? WHERE id=?", (cat, ip, real_id))
                
                for new_row in cambios.get("added_rows", []):
                    cat = new_row.get("Categoría", filtro_cat_l if filtro_cat_l != "Todas" else "General")
                    ip = new_row.get("IP Disponible", "")
                    conn.execute("INSERT INTO ip_libres (categoria, ip_disponible) VALUES (?, ?)", (cat, ip))
                    
                for row_idx in cambios.get("deleted_rows", []):
                    real_id = int(df_libres_view.iloc[int(row_idx)]["id"])
                    conn.execute("DELETE FROM ip_libres WHERE id=?", (real_id,))
                    
            st.session_state.msg_exito = "¡IP Libres guardadas correctamente!"
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar IP Libres: {e}")

# ------------------------------------------------------------------------------
# GENERADOR DE ETIQUETAS QR
# ------------------------------------------------------------------------------
elif mod == "Equipos: Generar QR":
    st.title("🏷️ Generador de Etiquetas QR - Inventario Físico")
    st.markdown("Crea e imprime etiquetas QR permanentes para pegar en el chasis de los equipos informáticos.")

    modo_qr = st.radio("Modo de Generación:", ["Etiqueta Individual", "Lote Masivo por Sucursal"], horizontal=True)
    df_todos = run_query("SELECT nombre_equipo, serial_number, usuario, sucursal, tipo_equipo FROM computadores")

    if not df_todos.empty:
        if modo_qr == "Etiqueta Individual":
            col_sel, col_prev = st.columns([1, 1])
            with col_sel:
                opciones_qr = (df_todos["nombre_equipo"] + " | Usr: " + df_todos["usuario"].fillna("Sin Asignar")).tolist()
                opcion_sel = st.selectbox("Selecciona el Equipo:", opciones_qr)
                equipo_qr_sel = opcion_sel.split(" | ")[0]
                eq_info = df_todos[df_todos["nombre_equipo"] == equipo_qr_sel].iloc[0]

                datos_qr = f"EQUIPO:{eq_info['nombre_equipo']}|SERIAL:{eq_info['serial_number'] or 'N/A'}"
                qr = qrcode.QRCode(box_size=10, border=2)
                qr.add_data(datos_qr)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white")

                buf = io.BytesIO()
                img_qr.save(buf, format="PNG")
                byte_im = buf.getvalue()

                st.write("**Detalles impresos en la etiqueta:**")
                st.write(f"- **Equipo:** {eq_info['nombre_equipo']}")
                st.write(f"- **Serial:** {eq_info['serial_number'] or 'N/A'}")
                st.write(f"- **Usuario Actual:** {eq_info['usuario'] or 'Sin Asignar'}")
                st.write(f"- **Sucursal:** {eq_info['sucursal'] or 'N/A'}")

                st.download_button(label=f"🖨️ Descargar Etiqueta ({eq_info['nombre_equipo']}.png)", data=byte_im, file_name=f"QR_{eq_info['nombre_equipo']}.png", mime="image/png", use_container_width=True)

            with col_prev:
                st.subheader("Vista Previa de la Etiqueta")
                st.image(byte_im, caption=f"Código QR: {eq_info['nombre_equipo']}", width=250)

        elif modo_qr == "Lote Masivo por Sucursal":
            SUCURSALES_FIJAS = ["Coquimbo", "Santiago", "Iquique", "La Chimba", "La Negra", "Copiapo", "Calama", "Caldera", "Mejillones"]
            sucursal_qr = st.selectbox("Filtrar Equipos por Sucursal:", SUCURSALES_FIJAS)
            df_filtrado = df_todos[df_todos["sucursal"].astype(str).str.upper() == sucursal_qr.upper()]

            if not df_filtrado.empty:
                st.success(f"Se encontraron {len(df_filtrado)} equipos en {sucursal_qr} listos para etiquetar.")
                st.dataframe(df_filtrado[["nombre_equipo", "tipo_equipo", "serial_number", "usuario"]], use_container_width=True, hide_index=True)
            else:
                st.info(f"No hay equipos registrados en la sucursal {sucursal_qr}.")
    else:
        st.info("No hay equipos en la base de datos para generar códigos QR.")

# ------------------------------------------------------------------------------
# SERVIDORES LOCAL
# ------------------------------------------------------------------------------
elif mod == "Servidores Local":
    st.title("🖥️ Servidores Local")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar Servidor, IP, Usuario, Contraseñas, Disco, RAM o Notas y presionar 'Guardar Cambios'.*")

    df_srv = run_query('SELECT id, servidor AS "Servidor", ip AS "IP", usuario AS "Usuario", password AS "Contraseña", password_nueva AS "Contraseña Nueva", espacio_disco AS "Espacio Disco", ram AS "RAM", notas AS "Notas" FROM servidores')

    if not df_srv.empty:
        df_srv_editada = st.data_editor(df_srv, hide_index=True, use_container_width=True, disabled=["id"], key="editor_srv")

        if st.button("💾 Guardar Cambios en Base de Datos", key="btn_srv"):
            datos = [(row["Servidor"], row["IP"], row["Usuario"], row["Contraseña"], row["Contraseña Nueva"], row["Espacio Disco"], row["RAM"], row["Notas"], row["id"]) for _, row in df_srv_editada.iterrows()]
            try:
                execute_many_db("UPDATE servidores SET servidor = ?, ip = ?, usuario = ?, password = ?, password_nueva = ?, espacio_disco = ?, ram = ?, notas = ? WHERE id = ?", datos)
                st.session_state.msg_exito = "¡Servidores actualizados correctamente!"
                st.rerun()
            except: pass
    else:
        st.info("No hay servidores cargados.")

# ------------------------------------------------------------------------------
# ACCESO A CÁMARAS / DVRS
# ------------------------------------------------------------------------------
elif mod == "Acceso a Cámaras":
    st.title("📹 Acceso a Cámaras / DVRs")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar. Para **agregar un nuevo registro**, desplázate hasta la última fila vacía (símbolo '+').*")

    # --- INICIALIZACIÓN SILENCIOSA DE TABLA CREDENCIALES ---
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS credenciales_camaras_default (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, password TEXT)""")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM credenciales_camaras_default")
        if cursor.fetchone()[0] == 0:
            conn.executemany("INSERT INTO credenciales_camaras_default (usuario, password) VALUES (?, ?)", 
                             [("admin", "saerx2015"), ("admin", "saerx2015."), ("admin", "sae_2024@")])

    # --- SECCIÓN DE CREDENCIALES FRECUENTES (EDITABLE) ---
    with st.expander("🔑 Credenciales Frecuentes / Por Defecto", expanded=True):
        st.markdown("💡 *Edita o agrega nuevas credenciales base aquí. Se guardarán en la base de datos.*")
        
        df_cred = run_query('SELECT id, usuario AS "Usuario", password AS "Contraseña" FROM credenciales_camaras_default')
        
        df_cred_editada = st.data_editor(
            df_cred,
            hide_index=True,
            use_container_width=False,  # <--- Ajusta la tabla a sus columnas (alineada a la izquierda)
            num_rows="dynamic",
            column_config={
                "id": None  # <--- Oculta visualmente la columna ID de la interfaz
            },
            key="editor_cred_cam"
        )
        
        if st.button("💾 Guardar Credenciales Frecuentes", key="btn_cred_cam"):
            cambios_cred = st.session_state.get("editor_cred_cam", {})
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    # Modificar existentes
                    for row_idx, updates in cambios_cred.get("edited_rows", {}).items():
                        real_id = int(df_cred.iloc[int(row_idx)]["id"])
                        usr = updates.get("Usuario", df_cred.iloc[int(row_idx)]["Usuario"])
                        pwd = updates.get("Contraseña", df_cred.iloc[int(row_idx)]["Contraseña"])
                        conn.execute("UPDATE credenciales_camaras_default SET usuario=?, password=? WHERE id=?", (usr, pwd, real_id))
                    
                    # Agregar nuevas
                    for new_row in cambios_cred.get("added_rows", []):
                        usr = new_row.get("Usuario", "")
                        pwd = new_row.get("Contraseña", "")
                        conn.execute("INSERT INTO credenciales_camaras_default (usuario, password) VALUES (?, ?)", (usr, pwd))
                    
                    # Eliminar
                    for row_idx in cambios_cred.get("deleted_rows", []):
                        real_id = int(df_cred.iloc[int(row_idx)]["id"])
                        conn.execute("DELETE FROM credenciales_camaras_default WHERE id=?", (real_id,))
                
                st.session_state.msg_exito = "¡Credenciales frecuentes actualizadas!"
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar credenciales: {e}")

    st.divider()

    # --- TABLA PRINCIPAL DE CÁMARAS ---
    st.subheader("📍 Detalle de Cámaras por Sucursal")
    df_cam = run_query('SELECT id, sucursal AS "Sucursal", ip_sn AS "IP / SN", nombre AS "Nombre", usuario AS "Usuario", password AS "Contraseña", notas AS "Notas" FROM acceso_camaras')

    if df_cam.empty:
        df_cam = pd.DataFrame(columns=["id", "Sucursal", "IP / SN", "Nombre", "Usuario", "Contraseña", "Notas"])

    df_cam_editada = st.data_editor(
        df_cam, 
        hide_index=True, 
        use_container_width=True, 
        num_rows="dynamic", 
        disabled=["id"], 
        key="editor_cam"
    )

    if st.button("💾 Guardar Cambios en Base de Datos de Cámaras", key="btn_cam"):
        cambios = st.session_state.get("editor_cam", {})
        try:
            with sqlite3.connect(DB_NAME) as conn:
                for row_idx, updates in cambios.get("edited_rows", {}).items():
                    real_id = int(df_cam.iloc[int(row_idx)]["id"])
                    suc = updates.get("Sucursal", df_cam.iloc[int(row_idx)]["Sucursal"])
                    ip = updates.get("IP / SN", df_cam.iloc[int(row_idx)]["IP / SN"])
                    nom = updates.get("Nombre", df_cam.iloc[int(row_idx)]["Nombre"])
                    usr = updates.get("Usuario", df_cam.iloc[int(row_idx)]["Usuario"])
                    pwd = updates.get("Contraseña", df_cam.iloc[int(row_idx)]["Contraseña"])
                    nota = updates.get("Notas", df_cam.iloc[int(row_idx)]["Notas"])
                    
                    conn.execute("UPDATE acceso_camaras SET sucursal=?, ip_sn=?, nombre=?, usuario=?, password=?, notas=? WHERE id=?", 
                                 (suc, ip, nom, usr, pwd, nota, real_id))
                
                for new_row in cambios.get("added_rows", []):
                    suc = new_row.get("Sucursal", "")
                    ip = new_row.get("IP / SN", "")
                    nom = new_row.get("Nombre", "")
                    usr = new_row.get("Usuario", "")
                    pwd = new_row.get("Contraseña", "")
                    nota = new_row.get("Notas", "")
                    
                    conn.execute("INSERT INTO acceso_camaras (sucursal, ip_sn, nombre, usuario, password, notas) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (suc, ip, nom, usr, pwd, nota))
                    
                for row_idx in cambios.get("deleted_rows", []):
                    real_id = int(df_cam.iloc[int(row_idx)]["id"])
                    conn.execute("DELETE FROM acceso_camaras WHERE id=?", (real_id,))
                    
            st.session_state.msg_exito = "¡Cámaras y DVRs actualizados correctamente!"
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

# ------------------------------------------------------------------------------
# ENLACES ENTEL
# ------------------------------------------------------------------------------
elif mod == "Enlaces Entel":
    st.title("📡 Cuentas & Redes - Enlaces Entel y Telecomunicaciones")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar Proveedor, Sucursal, Código Servicio, LAN, Firewall, WAN, Banda Ancha o Notas y presionar 'Guardar Cambios'.*")

    df_enl = run_query('SELECT id, proveedor AS "Proveedor", sucursal AS "Sucursal", codigo_servicio AS "Código Servicio", segmento_lan AS "Segmento LAN", firewall AS "Firewall", wan AS "WAN", banda_ancha AS "Banda Ancha", notas AS "Notas" FROM enlaces_telecom')

    if not df_enl.empty:
        df_enl_editada = st.data_editor(df_enl, hide_index=True, use_container_width=True, disabled=["id"], key="editor_enl")

        if st.button("💾 Guardar Cambios en Base de Datos", key="btn_enl"):
            datos = [(row["Proveedor"], row["Sucursal"], row["Código Servicio"], row["Segmento LAN"], row["Firewall"], row["WAN"], row["Banda Ancha"], row["Notas"], row["id"]) for _, row in df_enl_editada.iterrows()]
            try:
                execute_many_db("UPDATE enlaces_telecom SET proveedor = ?, sucursal = ?, codigo_servicio = ?, segmento_lan = ?, firewall = ?, wan = ?, banda_ancha = ?, notas = ? WHERE id = ?", datos)
                st.session_state.msg_exito = "¡Enlaces de Telecomunicaciones actualizados correctamente!"
                st.rerun()
            except: pass
    else:
        st.info("No hay enlaces cargados.")

# ------------------------------------------------------------------------------
# IMPRESORAS
# ------------------------------------------------------------------------------
elif mod == "Impresoras":
    st.title("🖨️ Impresoras y Multifuncionales")
    st.markdown("💡 *Puedes hacer doble clic en cualquier celda para editar los datos de las impresoras y presionar 'Guardar Cambios'.*")

    df_imp = run_query('SELECT id, sucursal AS "Sucursal", ip AS "IP", marca AS "Marca", modelo AS "Modelo", serial_number AS "Serial Number", mac AS "MAC", fecha_compra AS "Fecha Compra", area AS "Área", ubicacion AS "Ubicación", persona_asignada AS "Persona Asignada", estado AS "Estado", toner AS "Tóner", admin AS "Admin", observacion AS "Observación" FROM impresoras')

    if not df_imp.empty:
        st.metric("Total Impresoras Registradas", len(df_imp))
        df_imp_editada = st.data_editor(df_imp, hide_index=True, use_container_width=True, disabled=["id"], key="editor_imp")

        if st.button("💾 Guardar Cambios en Base de Datos", key="btn_imp"):
            datos = [(row["Sucursal"], row["IP"], row["Marca"], row["Modelo"], row["Serial Number"], row["MAC"], row["Fecha Compra"], row["Área"], row["Ubicación"], row["Persona Asignada"], row["Estado"], row["Tóner"], row["Admin"], row["Observación"], row["id"]) for _, row in df_imp_editada.iterrows()]
            try:
                execute_many_db("UPDATE impresoras SET sucursal = ?, ip = ?, marca = ?, modelo = ?, serial_number = ?, mac = ?, fecha_compra = ?, area = ?, ubicacion = ?, persona_asignada = ?, estado = ?, toner = ?, admin = ?, observacion = ? WHERE id = ?", datos)
                st.session_state.msg_exito = "¡Impresoras actualizadas correctamente!"
                st.rerun()
            except: pass
    else:
        st.info("No hay impresoras cargadas.")

# ------------------------------------------------------------------------------
# HISTORIAL DE TICKETS ENTEL Y GOTRUCK
# ------------------------------------------------------------------------------
elif mod == "Historial de Tickets Entel":
    st.title("🎫 Historial de Tickets Entel")
    df_tkt = run_query("SELECT num_ticket, fecha_apertura, sucursal, motivo, estado, fecha_cierre, demora, observacion FROM tickets_red")
    if not df_tkt.empty:
        st.metric("Total Tickets Entel Registrados", len(df_tkt))
        st.dataframe(df_tkt, use_container_width=True, hide_index=True)
    else:
        st.info("No hay tickets Entel registrados.")

elif mod == "Historial de Tickets Gotruck":
    st.title("🚛 Historial de Tickets Gotruck")
    df_gotruck = run_query("SELECT num_ticket, fecha_apertura, sucursal, motivo, estado, fecha_cierre, demora, observacion FROM tickets_gotruck")
    if not df_gotruck.empty:
        st.metric("Total Tickets Gotruck Registrados", len(df_gotruck))
        st.dataframe(df_gotruck, use_container_width=True, hide_index=True)
    else:
        st.info("No hay tickets Gotruck registrados.")

# ------------------------------------------------------------------------------
# CARGA MASIVA
# ------------------------------------------------------------------------------
elif mod == "Carga Masiva (Excel Completo)":
    st.title("🚀 Carga de Datos - Carga Masiva")
    st.write("Sube tu archivo Excel (soporta cualquier formato: 'Consolidado_Equipos_Completo.xlsx', 'Detalle - Equipos', etc.).")

    uploaded_file = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])
    limpiar_bd = st.checkbox("⚠️ **Limpiar y sobreescribir las secciones presentes en el Excel antes de importar**", value=False)

    if uploaded_file:
        xls = pd.ExcelFile(uploaded_file)
        st.write("Pestañas detectadas en este archivo:", xls.sheet_names)

        if st.button("⚡ Procesar e Importar Excel"):
            resumen = []
            import re

            def normalize_key(text):
                if not text or pd.isna(text): return ""
                s = str(text).strip().upper()
                s = s.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
                return re.sub(r"[^A-Z0-9]", "", s)

            field_aliases = {
                "sucursal": ["SUCURSAL"], "estado": ["ESTADO"], "tipo_equipo": ["TIPOEQUIPO", "TIPO"],
                "nombre_equipo": ["NOMBREEQUIPO", "NOMREEQUIPO", "EQUIPO"],
                "serial_number": ["SERIALNUMBER", "NSERIE", "SERIAL", "SERIE", "NOSERIE"],
                "mac_ethernet": ["MACETHERNET", "ETHERNETMAC", "MACLAN", "DIRECCIONMAC"],
                "mac_wifi": ["MACWIFI", "WIFIMAC", "MACWLAN"], "fecha_inicio": ["FECHAINICIO", "FECHAASIGNACION", "FECHA"],
                "usuario": ["USUARIO", "USUARIOASIGNADO", "PERSONAASIGNADA", "USR"],
                "marca_modelo": ["MARCAMODELO", "MARCA", "MODELO"], "procesador": ["PROCESADOR", "CPU"],
                "ram": ["RAM", "MEMORIARAM", "MEMORIA"], "version_windows": ["VERSIONWINDOWS", "WINDOWSVERSION", "WINDOWS", "SO", "SISTEMAOPERATIVO"],
                "version_antivirus": ["VERSIONANTIVIRUS", "ANTIVIRUSVERSION", "ANTIVIRUS"], "dominio_tsae": ["DOMINIOTSAE", "DOMINIO"],
                "act_automatica": ["ACTAUTOMATICA", "ACTUALIZACIONAUTOMATICA"], "office": ["OFFICE", "VERSIONOFFICE"],
                "cuenta_office_365": ["CUENTAOFFICE365", "CUENTA365", "LICENCIA365", "CORREO365"],
                "anydesk": ["ANYDESK", "ANYDESKID", "IDANYDESK"], "pass_any": ["PASSANY", "PASS-ANY", "TEAMVIEWER", "TEAMVIEWERID", "IDTEAMVIEWER"],
                "observacion": ["OBSERVACION", "OBSERVACIONES", "NOTAS"], "email": ["EMAIL", "CORREO", "EMAILUSUARIO", "MAIL"],
                "acceso_sap": ["ACCESOSAP", "ACCESOASAP", "SAP"], "ultima_mantencion": ["ULTIMAMANTENCION", "MANTENCION"],
                "ultima_actualizacion_planilla": ["ULTIMAACTPLANILLA", "ULTIMAACTUALIZACIONPLANILLA", "ACTPLANILLA"],
                "ex_usuario": ["EXUSUARIO"], "proveedor": ["PROVEEDOR", "PROVEEDORCOMPRA", "PROV"], "num_factura": ["NUMFACTURA", "NFACTURA", "NOFACTURA", "FACTURA", "NUMEROFACTURA"],
            }

            try:
                with sqlite3.connect(DB_NAME) as conn:
                    # 1. EQUIPOS
                    sheet_eq = None
                    if "Detalle - Equipos" in xls.sheet_names: sheet_eq = "Detalle - Equipos"
                    elif "Inventario Equipos" in xls.sheet_names: sheet_eq = "Inventario Equipos"
                    else:
                        for s in xls.sheet_names:
                            df_test = pd.read_excel(uploaded_file, sheet_name=s)
                            cols_norm = [normalize_key(col) for col in df_test.columns]
                            if any(k in cn for cn in cols_norm for k in ["NOMBREEQUIPO", "NOMREEQUIPO", "EQUIPO"]) and not any(cn in ["SOCIEDAD", "PERSONAASIGNADA", "ALMACENAMIENTOGB"] for cn in cols_norm) and not any(cn in ["POWERBI", "POWERBIGATEWAY", "TENANT"] for cn in cols_norm):
                                sheet_eq = s; break

                    if sheet_eq:
                        df_eq = pd.read_excel(uploaded_file, sheet_name=sheet_eq)
                        if limpiar_bd: conn.execute("DELETE FROM computadores")
                        col_map = {normalize_key(col): col for col in df_eq.columns}

                        def get_val(row, f_key):
                            for alias in field_aliases.get(f_key, [normalize_key(f_key)]):
                                if alias in col_map:
                                    val = row.get(col_map[alias], "")
                                    if pd.isna(val): return ""
                                    val_s = str(val).strip()
                                    return "" if val_s.lower() in ["nan", "none"] else val_s.replace(" 00:00:00", "")
                            return ""

                        datos_eq = []
                        for _, row in df_eq.iterrows():
                            nom = get_val(row, "nombre_equipo")
                            if nom: datos_eq.append((
                                get_val(row, "sucursal"), get_val(row, "estado"), get_val(row, "tipo_equipo"), nom, get_val(row, "serial_number"),
                                get_val(row, "mac_ethernet"), get_val(row, "mac_wifi"), get_val(row, "fecha_inicio"), get_val(row, "usuario"),
                                get_val(row, "marca_modelo"), get_val(row, "procesador"), get_val(row, "ram"), get_val(row, "version_windows"),
                                get_val(row, "version_antivirus"), get_val(row, "dominio_tsae"), get_val(row, "act_automatica"), get_val(row, "office"),
                                get_val(row, "cuenta_office_365"), get_val(row, "anydesk"), get_val(row, "pass_any"), get_val(row, "observacion"),
                                get_val(row, "email"), get_val(row, "acceso_sap"), get_val(row, "ultima_mantencion"), get_val(row, "ultima_actualizacion_planilla"),
                                get_val(row, "ex_usuario"), get_val(row, "proveedor"), get_val(row, "num_factura")
                            ))
                        if datos_eq:
                            conn.executemany("INSERT OR REPLACE INTO computadores (sucursal, estado, tipo_equipo, nombre_equipo, serial_number, mac_ethernet, mac_wifi, fecha_inicio, usuario, marca_modelo, procesador, ram, version_windows, version_antivirus, dominio_tsae, act_automatica, office, cuenta_office_365, anydesk, pass_any, observacion, email, acceso_sap, ultima_mantencion, ultima_actualizacion_planilla, ex_usuario, proveedor, num_factura) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", datos_eq)
                        resumen.append(f"💻 Equipos: {len(datos_eq)}")

                    # 2. O365
                    sheet_365 = "CTAS 365" if "CTAS 365" in xls.sheet_names else next((s for s in xls.sheet_names if any("CUENTA" in str(c).strip().upper() for c in pd.read_excel(uploaded_file, sheet_name=s).columns) and any("POWER" in str(c).strip().upper() or "CONTRASEÑA" in str(c).strip().upper() for c in pd.read_excel(uploaded_file, sheet_name=s).columns)), None)
                    if sheet_365:
                        df_3 = pd.read_excel(uploaded_file, sheet_name=sheet_365)
                        if not any("CUENTA" in str(c).strip().upper() for c in df_3.columns): df_3 = pd.read_excel(uploaded_file, sheet_name=sheet_365, header=1)
                        if limpiar_bd: conn.execute("DELETE FROM credenciales_o365")

                        def v_3(row, k_list):
                            for col in df_3.columns:
                                if any(k.upper() in str(col).strip().upper() for k in k_list):
                                    val = row.get(col, "")
                                    return "" if pd.isna(val) else str(val).strip()
                            return ""

                        datos_o365 = [(v_3(row, ["CORREO CUENTA", "CUENTA"]), v_3(row, ["POWER BI", "POWE BI"]), v_3(row, ["CONTRASEÑA", "PASSWORD"]), v_3(row, ["POWER BI GATEWAY", "GATEWAY"]), v_3(row, ["CLAVE DE RECUPERACION", "CLAVE RECUPERACION"])) for _, row in df_3.iterrows() if "@" in v_3(row, ["CORREO CUENTA", "CUENTA"])]
                        if datos_o365:
                            conn.executemany("INSERT OR REPLACE INTO credenciales_o365 (cuenta, power_bi, password, power_bi_gateway, clave_recuperacion) VALUES (?, ?, ?, ?, ?)", datos_o365)
                        resumen.append(f"🔐 Licencias O365: {len(datos_o365)}")

                    # 3. WIFI
                    if "WIFI" in xls.sheet_names:
                        df_w = pd.read_excel(uploaded_file, sheet_name="WIFI", header=1)
                        if limpiar_bd: conn.execute("DELETE FROM credenciales_wifi")
                        datos_wifi = [(str(row.get("Sucursal", "")), str(row.get("Nombre SSID", "")).strip(), str(row.get("Contraseña", "")), str(row.get("IP", ""))) for _, row in df_w.iterrows() if str(row.get("Nombre SSID", "")).strip() and not pd.isna(row.get("Nombre SSID"))]
                        if datos_wifi:
                            conn.executemany("INSERT INTO credenciales_wifi (sucursal, ssid, password, ip) VALUES (?, ?, ?, ?)", datos_wifi)
                        resumen.append(f"🛜 Redes WiFi: {len(datos_wifi)}")

                    # 4. ENTEL NUEVA (Asignaciones IP - Hasta fila 143)
                    sheet_entel = "Entel_Nueva" if "Entel_Nueva" in xls.sheet_names else "Entel Nueva" if "Entel Nueva" in xls.sheet_names else None
                    if sheet_entel:
                        # Leemos hasta la fila 143 como requeriste
                        df_e = pd.read_excel(uploaded_file, sheet_name=sheet_entel, nrows=143)
                        if limpiar_bd: conn.execute("DELETE FROM asignacion_ip_entel")
                        
                        current_category = "General"
                        datos_e = []
                        for _, row in df_e.iterrows():
                            # Asegurar columnas exactas o índices
                            c_name_col = "Client Name" if "Client Name" in df_e.columns else df_e.columns[0]
                            mac_col = "MAC Address" if "MAC Address" in df_e.columns else df_e.columns[1]
                            ip_col = "LAN IP" if "LAN IP" in df_e.columns else df_e.columns[2]

                            c_name = str(row.get(c_name_col, "")).strip()
                            mac = str(row.get(mac_col, "")).strip()
                            ip = str(row.get(ip_col, "")).strip()
                            
                            # Ignorar si toda la fila está vacía
                            if (not c_name or c_name.lower() == "nan") and (not mac or mac.lower() == "nan") and (not ip or ip.lower() == "nan"):
                                continue
                                
                            # Si no hay MAC ni IP, asumimos que es el Título de una Categoría (Ej: "DISPOSITIVOS")
                            if (mac.lower() == "nan" or not mac) and (ip.lower() == "nan" or not ip):
                                current_category = c_name
                            else:
                                datos_e.append((
                                    current_category, 
                                    c_name if c_name.lower() != "nan" else "", 
                                    mac if mac.lower() != "nan" else "", 
                                    ip if ip.lower() != "nan" else ""
                                ))
                        
                        if datos_e:
                            conn.executemany("INSERT INTO asignacion_ip_entel (categoria, client_name, mac_address, lan_ip) VALUES (?, ?, ?, ?)", datos_e)
                        resumen.append(f"🌐 Asignaciones IP: {len(datos_e)}")

                    # 5. IP LIBRES
                    sheet_libres = "IP_Libres" if "IP_Libres" in xls.sheet_names else "IP Libres" if "IP Libres" in xls.sheet_names else None
                    if sheet_libres:
                        df_l = pd.read_excel(uploaded_file, sheet_name=sheet_libres)
                        if limpiar_bd: conn.execute("DELETE FROM ip_libres")
                        
                        current_category = "General"
                        datos_l = []
                        for _, row in df_l.iterrows():
                            col_name = df_l.columns[0] if len(df_l.columns)>0 else ""
                            ip_val = str(row.get(col_name, "")).strip()
                            
                            if not ip_val or ip_val.lower() == "nan":
                                continue
                                
                            # Si tiene punto ".", es IP, sino, es una categoría combinada
                            if "." in ip_val:
                                datos_l.append((current_category, ip_val))
                            else:
                                current_category = ip_val
                                
                        if datos_l:
                            conn.executemany("INSERT INTO ip_libres (categoria, ip_disponible) VALUES (?, ?)", datos_l)
                        resumen.append(f"🆓 IP Libres: {len(datos_l)}")

                if resumen:
                    st.session_state.msg_exito = "¡Importación completada! | " + " | ".join(resumen)
                else:
                    st.warning("⚠️ No se detectaron hojas o datos válidos.")
                st.rerun()

            except Exception as e:
                st.error(f"Error crítico en la importación: {e}")

# ------------------------------------------------------------------------------
# USUARIOS - SERVIDORES GCP
# ------------------------------------------------------------------------------
elif mod == "Usuarios - Servidores GCP":
    st.title("☁️ Servidores GCP")
    
    # Función limpiadora para evitar errores de celdas vacías (Nulos/NaN)
    def clean_val(v):
        return "" if pd.isna(v) or v is None else str(v).strip()

    # Crear las dos pestañas
    tab_usuarios, tab_resumen = st.tabs(["👥 Usuarios AD/SAP", "📋 Resumen de Accesos"])
    
    # PESTAÑA 1: Tabla Original
    with tab_usuarios:
        st.markdown("💡 *Haz doble clic en las celdas para editar. Para **agregar un registro**, desliza hasta la última fila (+).*")
        df_gcp = run_query('SELECT id, empresa AS "Empresa", sucursal AS "Sucursal", usuario_ad_cloud AS "Usuario AD Cloud", name_domain_user AS "Name domain user", password_ad_cloud AS "Contraseña AD Cloud", usuario_sap AS "Usuario SAP", status AS "Status", cliente AS "Cliente", acceso_sap_31_01 AS "Acceso a SAP 31-01" FROM usuarios_gcp')

        if df_gcp.empty:
            df_gcp = pd.DataFrame(columns=["id", "Empresa", "Sucursal", "Usuario AD Cloud", "Name domain user", "Contraseña AD Cloud", "Usuario SAP", "Status", "Cliente", "Acceso a SAP 31-01"])

        st.data_editor(df_gcp, hide_index=True, use_container_width=True, num_rows="dynamic", disabled=["id"], key="editor_gcp")

        if st.button("💾 Guardar Cambios en Usuarios", key="btn_save_gcp"):
            cambios = st.session_state.get("editor_gcp", {})
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    # 1. Actualizar registros modificados
                    for row_idx, updates in cambios.get("edited_rows", {}).items():
                        real_id = int(df_gcp.iloc[int(row_idx)]["id"])
                        emp = clean_val(updates.get("Empresa", df_gcp.iloc[int(row_idx)]["Empresa"]))
                        suc = clean_val(updates.get("Sucursal", df_gcp.iloc[int(row_idx)]["Sucursal"]))
                        usr_ad = clean_val(updates.get("Usuario AD Cloud", df_gcp.iloc[int(row_idx)]["Usuario AD Cloud"]))
                        name = clean_val(updates.get("Name domain user", df_gcp.iloc[int(row_idx)]["Name domain user"]))
                        pwd = clean_val(updates.get("Contraseña AD Cloud", df_gcp.iloc[int(row_idx)]["Contraseña AD Cloud"]))
                        usr_sap = clean_val(updates.get("Usuario SAP", df_gcp.iloc[int(row_idx)]["Usuario SAP"]))
                        stat = clean_val(updates.get("Status", df_gcp.iloc[int(row_idx)]["Status"]))
                        cli = clean_val(updates.get("Cliente", df_gcp.iloc[int(row_idx)]["Cliente"]))
                        acc_sap = clean_val(updates.get("Acceso a SAP 31-01", df_gcp.iloc[int(row_idx)]["Acceso a SAP 31-01"]))
                        
                        conn.execute("UPDATE usuarios_gcp SET empresa=?, sucursal=?, usuario_ad_cloud=?, name_domain_user=?, password_ad_cloud=?, usuario_sap=?, status=?, cliente=?, acceso_sap_31_01=? WHERE id=?", (emp, suc, usr_ad, name, pwd, usr_sap, stat, cli, acc_sap, real_id))
                    
                    # 2. Insertar registros nuevos
                    for new_row in cambios.get("added_rows", []):
                        emp = clean_val(new_row.get("Empresa"))
                        suc = clean_val(new_row.get("Sucursal"))
                        usr_ad = clean_val(new_row.get("Usuario AD Cloud"))
                        name = clean_val(new_row.get("Name domain user"))
                        pwd = clean_val(new_row.get("Contraseña AD Cloud"))
                        usr_sap = clean_val(new_row.get("Usuario SAP"))
                        stat = clean_val(new_row.get("Status"))
                        cli = clean_val(new_row.get("Cliente"))
                        acc_sap = clean_val(new_row.get("Acceso a SAP 31-01"))
                        
                        conn.execute("INSERT INTO usuarios_gcp (empresa, sucursal, usuario_ad_cloud, name_domain_user, password_ad_cloud, usuario_sap, status, cliente, acceso_sap_31_01) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (emp, suc, usr_ad, name, pwd, usr_sap, stat, cli, acc_sap))
                        
                    # 3. Eliminar registros
                    for row_idx in cambios.get("deleted_rows", []):
                        real_id = int(df_gcp.iloc[int(row_idx)]["id"])
                        conn.execute("DELETE FROM usuarios_gcp WHERE id=?", (real_id,))
                        
                st.session_state.msg_exito = "¡Usuarios de GCP actualizados correctamente!"
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar los datos de GCP: {e}")

    # PESTAÑA 2: Tabla Resumen
    with tab_resumen:
        st.markdown("💡 *Administra los accesos generales. Agrega filas al final (+) y presiona guardar.*")
        df_res = run_query('SELECT id, correo AS "Correo", usuario AS "Usuario", password AS "Contraseña", acceso_maquina AS "Acceso maquina" FROM gcp_resumen')

        if df_res.empty:
            df_res = pd.DataFrame(columns=["id", "Correo", "Usuario", "Contraseña", "Acceso maquina"])

        st.data_editor(df_res, hide_index=True, use_container_width=True, num_rows="dynamic", disabled=["id"], key="editor_gcp_res")

        if st.button("💾 Guardar Resumen en BD", key="btn_save_gcp_res"):
            cambios_res = st.session_state.get("editor_gcp_res", {})
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    for row_idx, updates in cambios_res.get("edited_rows", {}).items():
                        real_id = int(df_res.iloc[int(row_idx)]["id"])
                        corr = clean_val(updates.get("Correo", df_res.iloc[int(row_idx)]["Correo"]))
                        usr = clean_val(updates.get("Usuario", df_res.iloc[int(row_idx)]["Usuario"]))
                        pwd = clean_val(updates.get("Contraseña", df_res.iloc[int(row_idx)]["Contraseña"]))
                        acc = clean_val(updates.get("Acceso maquina", df_res.iloc[int(row_idx)]["Acceso maquina"]))
                        
                        conn.execute("UPDATE gcp_resumen SET correo=?, usuario=?, password=?, acceso_maquina=? WHERE id=?", (corr, usr, pwd, acc, real_id))
                    
                    for new_row in cambios_res.get("added_rows", []):
                        corr = clean_val(new_row.get("Correo"))
                        usr = clean_val(new_row.get("Usuario"))
                        pwd = clean_val(new_row.get("Contraseña"))
                        acc = clean_val(new_row.get("Acceso maquina"))
                        
                        conn.execute("INSERT INTO gcp_resumen (correo, usuario, password, acceso_maquina) VALUES (?, ?, ?, ?)", (corr, usr, pwd, acc))
                        
                    for row_idx in cambios_res.get("deleted_rows", []):
                        real_id = int(df_res.iloc[int(row_idx)]["id"])
                        conn.execute("DELETE FROM gcp_resumen WHERE id=?", (real_id,))
                        
                st.session_state.msg_exito = "¡Resumen de accesos GCP actualizado correctamente!"
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar resumen: {e}")

# ------------------------------------------------------------------------------
# GESTION USUARIOS
# ------------------------------------------------------------------------------

elif mod == "Gestion Usuarios":
    st.title("⚙️ Gestión de Usuarios")
    
    if st.session_state.rol != "Administrador":
        st.error("No tienes permisos para ver esta sección.")
        st.stop()

    st.markdown("💡 *Edita roles y estados directamente en la tabla. Para crear usuarios, añade una fila al final (+). Selecciona filas y presiona 'Suprimir' o 'Delete' para borrarlas.*")
    
    df_users = run_query("SELECT id, username AS 'Usuario', rol AS 'Rol', estado AS 'Estado' FROM usuarios")
    
    # Si la tabla está vacía (por seguridad), creamos la estructura base
    if df_users.empty:
        df_users = pd.DataFrame(columns=["id", "Usuario", "Rol", "Estado"])
    
    # Editor de usuarios con menús desplegables (Selectbox) para evitar errores de tipeo
    df_users_edit = st.data_editor(
        df_users, 
        hide_index=True, 
        use_container_width=True, 
        num_rows="dynamic", 
        disabled=["id"], 
        key="edit_users",
        column_config={
            "Rol": st.column_config.SelectboxColumn("Rol", options=["Administrador", "Técnico", "Lector"], required=True),
            "Estado": st.column_config.SelectboxColumn("Estado", options=["ACTIVO", "INACTIVO"], required=True),
            "Usuario": st.column_config.TextColumn("Usuario", required=True)
        }
    )
    
    if st.button("💾 Guardar Cambios en Usuarios", key="btn_save_users"):
        cambios = st.session_state.get("edit_users", {})
        try:
            with sqlite3.connect(DB_NAME) as conn:
                # 1. Modificar existentes
                for row_idx, updates in cambios.get("edited_rows", {}).items():
                    real_id = int(df_users.iloc[int(row_idx)]["id"])
                    usr = updates.get("Usuario", df_users.iloc[int(row_idx)]["Usuario"])
                    rol = updates.get("Rol", df_users.iloc[int(row_idx)]["Rol"])
                    est = updates.get("Estado", df_users.iloc[int(row_idx)]["Estado"])
                    conn.execute("UPDATE usuarios SET username=?, rol=?, estado=? WHERE id=?", (usr, rol, est, real_id))
                
                # 2. Agregar nuevos
                for new_row in cambios.get("added_rows", []):
                    usr = str(new_row.get("Usuario", "")).strip()
                    rol = new_row.get("Rol", "Técnico")
                    est = new_row.get("Estado", "ACTIVO")
                    
                    if usr: # Solo guarda si escribieron un nombre de usuario
                        # Contraseña por defecto temporal (temporal123)
                        tmp_hash = hashlib.sha256("temporal123".encode()).hexdigest()
                        conn.execute("INSERT INTO usuarios (username, password_hash, rol, estado) VALUES (?, ?, ?, ?)", (usr, tmp_hash, rol, est))
                
                # 3. Eliminar borrados
                for row_idx in cambios.get("deleted_rows", []):
                    real_id = int(df_users.iloc[int(row_idx)]["id"])
                    conn.execute("DELETE FROM usuarios WHERE id=?", (real_id,))
            
            st.session_state.msg_exito = "¡Usuarios actualizados correctamente!"
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ Error al guardar: Verifica que el nombre de usuario no esté duplicado. Detalle técnico: {e}")

    # Campo para generar contraseñas nuevas a usuarios creados/editados
    st.divider()
    st.subheader("🔑 Asignar o Cambiar Contraseña")
    col_u, col_p, col_b = st.columns([2, 2, 1])
    
    usr_sel = col_u.selectbox("Seleccionar Usuario:", df_users["Usuario"].tolist() if not df_users.empty else [])
    new_pass = col_p.text_input("Nueva Contraseña:", type="password")
    
    with col_b:
        st.write("") # Espaciador para alinear el botón con las cajas de texto
        st.write("")
        if st.button("Cambiar Contraseña", use_container_width=True):
            if usr_sel and new_pass:
                try:
                    new_hash = hashlib.sha256(new_pass.encode()).hexdigest()
                    execute_db("UPDATE usuarios SET password_hash=? WHERE username=?", (new_hash, usr_sel))
                    st.session_state.msg_exito = f"¡Contraseña actualizada con éxito para {usr_sel}!"
                    st.rerun()
                except Exception as e:
                    st.error("Error al actualizar la contraseña.")
            else:
                st.warning("⚠️ Selecciona un usuario y escribe una contraseña nueva.")