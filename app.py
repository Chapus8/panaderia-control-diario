import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Panadería Judith - Control", page_icon="🍞", layout="wide")

# Título y encabezado
st.title("🍞 Control Diario - Panadería Judith")
st.markdown("---")

# Conexión a la base de datos de Neon
# Streamlit maneja esto automáticamente si configuramos bien los secrets
try:
    conn = st.connection("postgresql", type="sql")
    st.sidebar.success("🟢 Conectado a la base de datos", icon="✅")
except Exception as e:
    st.sidebar.error("🔴 Error de conexión. Revisa los secrets.")
    st.stop()

# Crear pestañas para navegar
tab1, tab2, tab3 = st.tabs(["📝 Ingreso de Corte", "📊 Estadísticas", "💳 Créditos y Pagos"])

with tab1:
    st.header("Corte Diario")
    
    # Obtener datos de los catálogos desde la BD
    df_rutas = conn.query("SELECT id, nombre FROM rutas_locales")
    df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Registrar Ingreso")
        with st.form("form_ingresos", clear_on_submit=True):
            ruta = st.selectbox("Ruta o Local", df_rutas['nombre'])
            venta = st.number_input("Venta Total (Q)", min_value=0.00, step=10.00)
            efectivo = st.number_input("Efectivo Entregado (Q)", min_value=0.00, step=10.00)
            
            btn_ingreso = st.form_submit_button("Guardar Ingreso")
            if btn_ingreso:
                # Aquí irá la lógica de inserción (INSERT INTO)
                st.success(f"Ingreso de {ruta} registrado por Q{venta}.")
                
    with col2:
        st.subheader("📉 Registrar Gasto")
        with st.form("form_gastos", clear_on_submit=True):
            categoria = st.selectbox("Tipo de Gasto", df_categorias['nombre'])
            detalle = st.text_input("Detalle (Ej. Pago Stephanie, Gasolina moto)")
            monto = st.number_input("Monto (Q)", min_value=0.00, step=10.00)
            
            btn_gasto = st.form_submit_button("Guardar Gasto")
            if btn_gasto:
                # Aquí irá la lógica de inserción (INSERT INTO)
                st.success(f"Gasto guardado: {categoria} - Q{monto}")

with tab2:
    st.header("Estadísticas Mensuales")
    st.info("Aquí colocaremos gráficas de pastel y barras cuando tengamos los primeros datos guardados.")
    # Ejemplo de dónde irá la gráfica de en qué se gasta más.

with tab3:
    st.header("Control de Proveedores (Harina, Gas, etc.)")
    st.info("Aquí verás las alertas de cuándo toca pagar.")
