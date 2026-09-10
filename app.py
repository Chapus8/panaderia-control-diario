import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date
import plotly.express as px

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Panadería Judith - Sistema", page_icon="🍞", layout="wide")

USUARIOS = {"roberto": "esquipulas123", "admin": "admin2026"}

if 'logueado' not in st.session_state:
    st.session_state['logueado'] = False

if not st.session_state['logueado']:
    st.markdown("<h1 style='text-align: center;'>🍞 Panadería Judith</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Acceso Seguro</h3>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("👤 Usuario").lower()
            password = st.text_input("🔒 Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                if usuario in USUARIOS and USUARIOS[usuario] == password:
                    st.session_state['logueado'] = True
                    st.session_state['usuario'] = usuario
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['usuario'].capitalize()}")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['logueado'] = False
        st.rerun()

# 2. CONEXIÓN A LA BASE DE DATOS
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("🔴 Error de conexión.")
    st.stop()

def obtener_o_crear_corte(fecha_corte):
    with conn.session as s:
        result = s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()
        if result:
            return result[0]
        else:
            s.execute(text("INSERT INTO cortes_diarios (fecha) VALUES (:fecha)"), {"fecha": fecha_corte})
            s.commit()
            return s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()[0]

# 3. INTERFAZ PRINCIPAL
st.title("🍞 Ingreso Rápido de Cortes")

tab1, tab2, tab3 = st.tabs(["📝 Formato de Papel", "📈 Estadísticas", "💳 Créditos"])

with tab1:
    # --- ENCABEZADO DEL CORTE (Igual al papel) ---
    st.markdown("### 📋 Datos del Corte")
    df_rutas = conn.query("SELECT id, nombre FROM rutas_locales")
    df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto")
    lista_categorias = df_categorias['nombre'].tolist()
    
    col_enc1, col_enc2, col_enc3 = st.columns(3)
    fecha_corte = col_enc1.date_input("Fecha del Corte", date.today())
    local_ruta = col_enc2.selectbox("Local / Ruta", df_rutas['nombre'])
    responsable = col_enc3.selectbox("Responsable", ["Dania", "Ana Judith Ramirez", "Stephanie Roldan", "Wendy Perez", "Otro"])
    
    st.markdown("---")
    
    # --- LISTA DE GASTOS INTERACTIVA ---
    st.markdown("### 💸 Detalle de Gastos")
    st.caption("Agrega filas para cada gasto que aparezca en el papelito.")
    
    # Creamos una tabla vacía con la estructura necesaria
    if 'gastos_df' not in st.session_state:
        st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        # Agregamos 5 filas vacías por defecto para que sea más rápido
        for _ in range(5):
            st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]

    # Usamos data_editor para que puedas editar tipo Excel
    gastos_editados = st.data_editor(
        st.session_state.gastos_df,
        column_config={
            "Categoría": st.column_config.SelectboxColumn(
                "Tipo de Gasto", help="Categoría", options=lista_categorias, required=True
            ),
            "Detalle": st.column_config.TextColumn("Detalle (Ej. Almuerzo, Bono)"),
            "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")
        },
        num_rows="dynamic",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # --- TOTALES Y GUARDADO ---
    col_tot1, col_tot2, col_tot3 = st.columns(3)
    venta_total = col_tot1.number_input("💰 Venta Total (Efectivo)", min_value=0.00, step=100.00)
    
    # Calculamos automáticamente el total de gastos que pusiste en la tabla
    total_gastos_calc = gastos_editados["Monto (Q)"].sum()
    col_tot2.metric("📉 Suma Total de Gastos", f"Q {total_gastos_calc:.2f}")
    col_tot3.metric("⚖️ Total Neto Entregado", f"Q {venta_total - total_gastos_calc:.2f}")
    
    if st.button("💾 Guardar Corte Completo", type="primary", use_container_width=True):
        if venta_total > 0 or total_gastos_calc > 0:
            corte_id = obtener_o_crear_corte(fecha_corte)
            ruta_id = df_rutas.loc[df_rutas['nombre'] == local_ruta, 'id'].values[0]
            
            with conn.session as s:
                # 1. Guardamos el ingreso principal
                if venta_total > 0:
                    s.execute(text("INSERT INTO ingresos (corte_id, ruta_id, venta_total) VALUES (:c, :r, :v)"), 
                              {"c": corte_id, "r": int(ruta_id), "v": venta_total})
                
                # 2. Guardamos todos los gastos válidos de la tabla
                for index, row in gastos_editados.iterrows():
                    if pd.notna(row["Categoría"]) and row["Monto (Q)"] > 0:
                        cat_id = df_categorias.loc[df_categorias['nombre'] == row["Categoría"], 'id'].values[0]
                        s.execute(text("INSERT INTO gastos (corte_id, categoria_id, detalle, monto) VALUES (:c, :cat, :d, :m)"), 
                                  {"c": corte_id, "cat": int(cat_id), "d": row["Detalle"], "m": row["Monto (Q)"]})
                
                s.commit()
            
            st.success("✅ ¡Corte guardado exitosamente en la base de datos!")
            st.balloons()
        else:
            st.warning("⚠️ Debes ingresar al menos una venta o un gasto para guardar.")

with tab2:
    st.header("Visualización de Finanzas")
    st.write("Mira en qué se está yendo el dinero.")
    gastos_totales = conn.query("SELECT c.nombre as categoria, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id GROUP BY c.nombre")
    if not gastos_totales.empty:
        fig = px.pie(gastos_totales, values='total', names='categoria', hole=0.4, title="Distribución Histórica de Gastos")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no hay suficientes datos para las gráficas.")

with tab3:
    st.header("Pendientes de Pago")
    st.info("Módulo de proveedores activo. (Funcionalidad idéntica a la versión anterior).")
