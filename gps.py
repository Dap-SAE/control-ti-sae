import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

DB_NAME = "control_ti.db"

def run_query(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(query, conn, params=params)

def execute_db(query, params=()):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(query, params)

def execute_many_db(query, params_list):
    with sqlite3.connect(DB_NAME) as conn:
        conn.executemany(query, params_list)

def upgrade_gps_table():
    """Añade la columna de categoría a la tabla si no existe, asignando 'Camión' por defecto a lo antiguo."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("ALTER TABLE gps_flota ADD COLUMN categoria_gps TEXT DEFAULT 'Camión'")
    except sqlite3.OperationalError:
        pass # La columna ya existe

def render_gps_module():
    # Actualizar esquema de BD silenciosamente
    upgrade_gps_table()

    st.title("🛰️ Centralizado de GPS y Flota")
    st.markdown("Dashboard interactivo, gestión de dispositivos GPS y análisis de proveedores para Camiones y Equipos.")

    # Cargar datos base de GPS incluyendo la nueva categoría
    df_gps = run_query("""
        SELECT id, categoria_gps, patente AS "Patente", vin AS "VIN", tipo AS "Tipo", marca AS "Marca", 
               modelo AS "Modelo", anio AS "Año", imei AS "IMEI", ultimo_reporte AS "Último Reporte", 
               proveedor_gps AS "Proveedor GPS", sucursal AS "Sucursal", estado AS "Estado" 
        FROM gps_flota
    """)

    # Crear pestañas organizadas
    tab_resumen, tab_gest_camiones, tab_gest_equipos, tab_alertas, tab_carga = st.tabs([
        "📊 Resumen", 
        "🚛 Gestión Camiones",
        "🚜 Gestión Equipos", 
        "⚠️ Alertas", 
        "🚀 Carga Masiva GPS"
    ])

    # ---------------------------------------------------------
    # PESTAÑA 1: RESUMEN / DASHBOARD PROFESIONAL
    # ---------------------------------------------------------
    with tab_resumen:
        if not df_gps.empty:
            st.subheader("📈 Dashboard Analítico de Flota")
            
            # Filtro Maestro
            filtro_cat = st.radio("📌 Filtrar Dashboard por tipo de activo:", ["Todos", "Camiones", "Equipos"], horizontal=True)
            
            if filtro_cat == "Camiones":
                df_resumen = df_gps[df_gps["categoria_gps"] == "Camión"].copy()
            elif filtro_cat == "Equipos":
                df_resumen = df_gps[df_gps["categoria_gps"] == "Equipo"].copy()
            else:
                df_resumen = df_gps.copy()

            if not df_resumen.empty:
                # --- CÁLCULOS PRINCIPALES ---
                df_resumen["Patente_Std"] = df_resumen["Patente"].astype(str).str.strip().str.upper()
                total_flota = len(df_resumen)
                total_camiones = len(df_resumen[df_resumen["categoria_gps"] == "Camión"])
                total_equipos = len(df_resumen[df_resumen["categoria_gps"] == "Equipo"])
                total_unicas = df_resumen["Patente_Std"].nunique()
                duplicadas = total_flota - total_unicas
                
                df_resumen["Estado_Std"] = df_resumen["Estado"].fillna("SIN ESTADO").astype(str).str.strip().str.upper()
                df_resumen["Proveedor_Std"] = df_resumen["Proveedor GPS"].fillna("SIN PROVEEDOR").astype(str).str.strip().str.upper()
                df_resumen["Sucursal_Std"] = df_resumen["Sucursal"].fillna("SIN SUCURSAL").astype(str).str.strip().str.upper()
                
                sin_replica = len(df_resumen[df_resumen["Estado_Std"].isin(["NO REPLICA", "INACTIVO", "OFFLINE", "SIN SEÑAL"])])

                # --- FILA 1: KPIs GLOBALES ---
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric(label=f"Total Flota", value=total_flota)
                c2.metric(label="🚛 Camiones", value=total_camiones)
                c3.metric(label="🚜 Equipos", value=total_equipos)
                c4.metric(label="🚨 Duplicados", value=duplicadas, delta="- Revisar" if duplicadas > 0 else "OK", delta_color="inverse")
                c5.metric(label="📡 Sin Réplica", value=sin_replica, delta="- Crítico" if sin_replica > 0 else "OK", delta_color="inverse")
                c6.metric(label="🏢 Proveedores", value=df_resumen["Proveedor_Std"].nunique())
                
                st.markdown("---")

                # --- SECCIÓN: PROVEEDORES ---
                st.markdown(f"#### 🏢 Distribución por Proveedor GPS ({filtro_cat})")
                col_g1, col_t1 = st.columns([2, 1])
                df_prov = df_resumen["Proveedor_Std"].value_counts().reset_index()
                df_prov.columns = ["Proveedor", "Cantidad"]
                
                with col_g1:
                    st.bar_chart(df_prov, x="Proveedor", y="Cantidad", use_container_width=True)
                with col_t1:
                    st.dataframe(df_prov, hide_index=True, use_container_width=True)

                st.markdown("---")

                # --- SECCIÓN: ESTADO DE CONEXIÓN ---
                st.markdown(f"#### 🚦 Estado General de Conexión ({filtro_cat})")
                col_g2, col_t2 = st.columns([2, 1])
                df_est = df_resumen["Estado_Std"].value_counts().reset_index()
                df_est.columns = ["Estado", "Cantidad"]
                
                with col_g2:
                    st.bar_chart(df_est, x="Estado", y="Cantidad", use_container_width=True)
                with col_t2:
                    st.dataframe(df_est, hide_index=True, use_container_width=True)

                st.markdown("---")

                # --- SECCIÓN: SUCURSALES ---
                st.markdown(f"#### 📍 Distribución por Sucursal/Base ({filtro_cat})")
                col_g3, col_t3 = st.columns([2, 1])
                df_suc = df_resumen["Sucursal_Std"].value_counts().reset_index()
                df_suc.columns = ["Sucursal", "Cantidad"]
                
                with col_g3:
                    st.bar_chart(df_suc, x="Sucursal", y="Cantidad", use_container_width=True)
                with col_t3:
                    st.dataframe(df_suc, hide_index=True, use_container_width=True)
            else:
                st.info(f"No hay datos registrados en la categoría: {filtro_cat}.")
        else:
            st.info("No hay datos suficientes para generar el Dashboard. Ve a la pestaña 'Carga Masiva GPS' para comenzar.")

    # ---------------------------------------------------------
    # FUNCIONES DE GESTIÓN (Reutilizables para Camiones y Equipos)
    # ---------------------------------------------------------
    def render_gestion_tab(categoria_filtrar, key_prefix):
        df_cat = df_gps[df_gps["categoria_gps"] == categoria_filtrar].copy()
        
        st.subheader(f"📝 Tabla Editable - {categoria_filtrar}s")
        st.markdown(f"Filtra, edita celdas directamente o agrega nuevos **{categoria_filtrar}s** al final de la tabla.")
        
        if df_cat.empty:
            st.info(f"No hay {categoria_filtrar}s registrados.")
            df_cat = pd.DataFrame(columns=["id", "Patente", "VIN", "Tipo", "Marca", "Modelo", "Año", "IMEI", "Último Reporte", "Proveedor GPS", "Sucursal", "Estado"])
        
        # --- NUEVA SECCIÓN DE FILTROS (BÚSQUEDA Y PROVEEDOR) ---
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            busqueda_pat = st.text_input(f"🔍 Buscar por Patente ({categoria_filtrar}):", key=f"search_{key_prefix}")
            
        with col_f2:
            proveedores = ["Todos"] + sorted([p for p in df_cat["Proveedor GPS"].dropna().unique() if p])
            prov_sel = st.selectbox(f"🏢 Filtrar por Proveedor:", proveedores, key=f"sel_{key_prefix}")
        
        columnas_vista = [col for col in df_cat.columns if not col.endswith("_Std") and col != "categoria_gps"]
        df_view = df_cat[columnas_vista]
        
        # Aplicar filtro de Proveedor
        if prov_sel != "Todos":
            df_view = df_view[df_view["Proveedor GPS"] == prov_sel]
            
        # Aplicar filtro de Búsqueda por Patente
        if busqueda_pat:
            df_view = df_view[df_view["Patente"].astype(str).str.contains(busqueda_pat, case=False, na=False)]

        df_editado = st.data_editor(
            df_view,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            disabled=["id"],
            key=f"editor_{key_prefix}"
        )

        if st.button(f"💾 Guardar Cambios en {categoria_filtrar}s", key=f"btn_save_{key_prefix}"):
            cambios = st.session_state.get(f"editor_{key_prefix}", {})
            try:
                for row_idx, updates in cambios.get("edited_rows", {}).items():
                    real_id = int(df_view.iloc[int(row_idx)]["id"])
                    cols = []
                    vals = []
                    for col_name, new_val in updates.items():
                        db_col = col_name.lower().replace(" ", "_").replace("último", "ultimo").replace("año", "anio")
                        cols.append(f"{db_col}=?")
                        vals.append(str(new_val).strip() if pd.notna(new_val) else "")
                    if cols:
                        vals.append(real_id)
                        execute_db(f"UPDATE gps_flota SET {', '.join(cols)} WHERE id=?", vals)
                
                for new_row in cambios.get("added_rows", []):
                    cols = ["categoria_gps", "patente", "vin", "tipo", "marca", "modelo", "anio", "imei", "ultimo_reporte", "proveedor_gps", "sucursal", "estado"]
                    vals = [categoria_filtrar] + [str(new_row.get(c.replace("_", " ").title().replace("Anio", "Año").replace("Ultimo Reporte", "Último Reporte").replace("Imei", "IMEI").replace("Vin", "VIN"), "")).strip() for c in cols[1:]]
                    execute_db(f"INSERT INTO gps_flota ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)

                for row_idx in cambios.get("deleted_rows", []):
                    real_id = int(df_view.iloc[int(row_idx)]["id"])
                    execute_db("DELETE FROM gps_flota WHERE id=?", (real_id,))

                st.success(f"¡Datos de {categoria_filtrar} actualizados correctamente!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    # ---------------------------------------------------------
    # PESTAÑA 2: GESTIÓN CAMIONES
    # ---------------------------------------------------------
    with tab_gest_camiones:
        render_gestion_tab("Camión", "camiones")

    # ---------------------------------------------------------
    # PESTAÑA 3: GESTIÓN EQUIPOS
    # ---------------------------------------------------------
    with tab_gest_equipos:
        render_gestion_tab("Equipo", "equipos")

    # ---------------------------------------------------------
    # PESTAÑA 4: ALERTAS (DUPLICADOS Y RÉPLICAS)
    # ---------------------------------------------------------
    with tab_alertas:
        st.subheader("🔍 Análisis y Auditoría de Flota")
        if not df_gps.empty:
            col_dup, col_rep = st.columns(2)
            
            with col_dup:
                st.markdown("### 🚨 Patentes Duplicadas")
                st.write("Vehículos/Equipos que aparecen más de una vez (posible cobro doble de proveedores).")
                
                df_gps["pat_upper"] = df_gps["Patente"].astype(str).str.strip().str.upper()
                dups = df_gps[df_gps.duplicated(subset=["pat_upper"], keep=False)].sort_values("pat_upper")
                
                if not dups.empty:
                    cols_mostrar = ["Patente", "categoria_gps", "Proveedor GPS", "Sucursal", "Estado"]
                    st.dataframe(dups[cols_mostrar].rename(columns={"categoria_gps": "Clasificación"}), use_container_width=True, hide_index=True)
                else:
                    st.success("✅ No se encontraron patentes duplicadas.")

            with col_rep:
                st.markdown("### 📡 GPS Sin Réplica / Inactivos")
                st.write("Vehículos/Equipos marcados como sin conexión o con fallas.")
                
                df_sin_rep = df_gps[
                    (df_gps["Estado"].astype(str).str.upper().isin(["NO REPLICA", "INACTIVO", "OFFLINE", "SIN SEÑAL"])) |
                    (df_gps["Último Reporte"].isna()) | 
                    (df_gps["Último Reporte"].astype(str).str.strip() == "")
                ]
                if not df_sin_rep.empty:
                    cols_mostrar = ["Patente", "categoria_gps", "Proveedor GPS", "Último Reporte", "Estado"]
                    st.dataframe(df_sin_rep[cols_mostrar].rename(columns={"categoria_gps": "Clasificación"}), use_container_width=True, hide_index=True)
                else:
                    st.success("✅ Toda la flota parece estar comunicando.")
        else:
            st.info("Sin datos para analizar.")

    # ---------------------------------------------------------
    # PESTAÑA 5: CARGA MASIVA (Con Selección de Destino)
    # ---------------------------------------------------------
    with tab_carga:
        st.subheader("🚀 Carga Masiva de GPS / Flota")
        st.write("Sube el Excel con el consolidado de tus proveedores GPS. El sistema detectará las columnas automáticamente.")
        
        destino_carga = st.radio("🎯 ¿Dónde deseas cargar esta información?", ["Camiones", "Equipos"], horizontal=True)
        categoria_insertar = "Camión" if destino_carga == "Camiones" else "Equipo"
        
        uploaded_gps = st.file_uploader("Selecciona tu archivo Excel de Flota", type=["xlsx", "xls"], key="up_gps")
        limpiar_gps = st.checkbox(f"⚠️ Borrar SOLO la tabla actual de **{destino_carga}** antes de cargar", value=False)

        if uploaded_gps:
            if st.button(f"⚡ Procesar e Importar como {destino_carga}"):
                try:
                    df_up = pd.read_excel(uploaded_gps)
                    
                    def get_col(df, aliases):
                        for c in df.columns:
                            c_norm = str(c).strip().upper().replace(" ", "")
                            if any(a in c_norm for a in aliases):
                                return c
                        return None

                    map_cols = {
                        "patente": get_col(df_up, ["PATENTE", "PLACA", "PPU", "EQUIPO"]),
                        "vin": get_col(df_up, ["VIN", "CHASIS", "SERIE"]),
                        "tipo": get_col(df_up, ["TIPO", "VEHICULO", "CLASIFICACION"]),
                        "marca": get_col(df_up, ["MARCA"]),
                        "modelo": get_col(df_up, ["MODELO"]),
                        "anio": get_col(df_up, ["AÑO", "ANO", "YEAR"]),
                        "imei": get_col(df_up, ["IMEI", "DISPOSITIVO", "IDGPS"]),
                        "ultimo_reporte": get_col(df_up, ["ULTIMOREPORTE", "FECHA", "REPORTE", "ULTIMACONEXION"]),
                        "proveedor_gps": get_col(df_up, ["PROVEEDOR", "EMPRESA", "PLATAFORMA"]),
                        "sucursal": get_col(df_up, ["SUCURSAL", "BASE", "OPERACION", "ZONA"]),
                        "estado": get_col(df_up, ["ESTADO", "STATUS", "REPLICA"])
                    }

                    if limpiar_gps:
                        execute_db("DELETE FROM gps_flota WHERE categoria_gps=?", (categoria_insertar,))

                    datos_insert = []
                    for _, row in df_up.iterrows():
                        pat = str(row[map_cols["patente"]]).strip() if map_cols["patente"] else ""
                        if not pat or pat.lower() == "nan": 
                            continue 
                        
                        datos_insert.append((
                            categoria_insertar,
                            pat,
                            str(row[map_cols["vin"]]).strip() if map_cols["vin"] else "",
                            str(row[map_cols["tipo"]]).strip() if map_cols["tipo"] else "",
                            str(row[map_cols["marca"]]).strip() if map_cols["marca"] else "",
                            str(row[map_cols["modelo"]]).strip() if map_cols["modelo"] else "",
                            str(row[map_cols["anio"]]).strip() if map_cols["anio"] else "",
                            str(row[map_cols["imei"]]).strip() if map_cols["imei"] else "",
                            str(row[map_cols["ultimo_reporte"]]).strip() if map_cols["ultimo_reporte"] else "",
                            str(row[map_cols["proveedor_gps"]]).strip() if map_cols["proveedor_gps"] else "",
                            str(row[map_cols["sucursal"]]).strip() if map_cols["sucursal"] else "",
                            str(row[map_cols["estado"]]).strip() if map_cols["estado"] else "ACTIVO",
                        ))
                    
                    if datos_insert:
                        execute_many_db("""
                            INSERT INTO gps_flota (categoria_gps, patente, vin, tipo, marca, modelo, anio, imei, ultimo_reporte, proveedor_gps, sucursal, estado)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, datos_insert)
                        
                        st.success(f"¡Importación exitosa! Se cargaron {len(datos_insert)} registros a la sección de {destino_carga}.")
                        st.rerun()
                    else:
                        st.warning("No se encontraron patentes válidas en el archivo para importar.")

                except Exception as e:
                    st.error(f"Error al leer el Excel: {e}")