import sqlite3
import psycopg2

# 1. Configura tus conexiones
SQLITE_DB = "control_ti.db"
NEON_URL = "postgresql://neondb_owner:npg_J8ACdm1rOWhl@ep-billowing-sound-bb0xzny2-pooler.c-15.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" # <-- PEGA TU ENLACE AQUÍ (entre las comillas)


tablas = [
    "computadores", "cuentas_correo", "credenciales_o365", "impresoras", 
    "credenciales_wifi", "servidores", "enlaces_telecom", "acceso_camaras", 
    "tickets_red", "tickets_gotruck", "historial_asignaciones", 
    "asignacion_ip_entel", "ip_libres", "gps_flota", "usuarios", 
    "usuarios_gcp", "gcp_resumen", "equipos_moviles", "credenciales_camaras_default"
]

print("Iniciando migración de datos a Neon...")

try:
    conn_sl = sqlite3.connect(SQLITE_DB)
    conn_pg = psycopg2.connect(NEON_URL)
    cur_sl = conn_sl.cursor()
    cur_pg = conn_pg.cursor()

    # Agregar la columna faltante a Neon antes de migrar
    cur_pg.execute("ALTER TABLE gps_flota ADD COLUMN IF NOT EXISTS categoria_gps TEXT;")
    conn_pg.commit()

    for tabla in tablas:
        # Intentar extraer de SQLite, saltar si la tabla no existe
        try:
            cur_sl.execute(f"SELECT * FROM {tabla}")
            filas = cur_sl.fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                print(f"⏭️ Tabla '{tabla}' no existe en SQLite local. Saltando...")
                continue
            else:
                raise e
        
        if not filas:
            continue
            
        # Preparar la consulta para PostgreSQL
        cols = [desc[0] for desc in cur_sl.description]
        cols_str = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        
        # Insertar evitando duplicados por ID
        insert_query = f"INSERT INTO {tabla} ({cols_str}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING;"
        cur_pg.executemany(insert_query, filas)
        
        # Sincronizar el contador automático de IDs en PostgreSQL
        cur_pg.execute(f"SELECT setval('{tabla}_id_seq', COALESCE((SELECT MAX(id)+1 FROM {tabla}), 1), false);")
        
        print(f"✅ Tabla '{tabla}' migrada ({len(filas)} registros).")
        
    conn_pg.commit()
    conn_sl.close()
    conn_pg.close()
    print("🚀 ¡Migración completada con éxito! Revisa tu aplicación en Streamlit.")

except Exception as e:
    print(f"⚠️ Error durante la migración: {e}")