import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date

# Configuración de la página
st.set_page_config(page_title="Panadería Judith - Control", page_icon="🍞", layout="wide")

st.title("🍞 Control Diario - Panadería Judith")
st.markdown("---")

# Conexión a la base de datos
try:
    conn = st.connection("postgresql", type="sql")
    st.sidebar.success("🟢 Conectado a la base de datos", icon="✅")
except Exception as e:
    st.sidebar.error("🔴 Error de conexión.")
    st.stop()

# Función para obtener el corte de hoy (o crearlo si no existe)
def obtener_corte_hoy():
    hoy = date.today()
    with conn.session as s:
        # Buscar si ya hay un corte hoy
        result = s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": hoy}).fetchone()
        if result:
            return result[0]
        else:
            # Si no hay, crearlo
            s.execute(text("INSERT INTO cortes_diarios (fecha) VALUES (:fecha)"), {"fecha": hoy})
            s.commit()
            result = s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": hoy}).fetchone()
            return result[0]

# Pestañas
tab1, tab2, tab3 = st.tabs(["📝 Ingreso de Corte", "📊 Estadísticas", "💳 Créditos y Pagos"])

with tab1:
    st.header(f"Corte Diario - {date.today().strftime('%d/%m/%Y')}")
    
    # Obtener catálogos
    df_rutas = conn.query("SELECT id, nombre FROM rutas_locales")
    df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Registrar Ingreso")
        with st.form("form_ingresos", clear_on_submit=True):
            ruta = st.selectbox("Ruta o Local", df_rutas['nombre'])
            venta = st.number_input("Venta Total (Q)", min_value=0.00, step=10.00)
            efectivo = st.number_input("Efectivo Entregado (Q)", min_value=0.00, step=10.00)
            
            if st.form_submit_button("Guardar Ingreso"):
                corte_id = obtener_corte_hoy()
                ruta_id = df_rutas.loc[df_rutas['nombre'] == ruta, 'id'].values[0]
                
                with conn.session as s:
                    s.execute(text("""
                        INSERT INTO ingresos (corte_id, ruta_id, venta_total, efectivo) 
                        VALUES (:corte_id, :ruta_id, :venta, :efectivo)
                    """), {"corte_id": corte_id, "ruta_id": int(ruta_id), "venta": venta, "efectivo": efectivo})
                    s.commit()
                st.success(f"✅ Ingreso de {ruta} guardado en la base de datos.")
                
    with col2:
        st.subheader("📉 Registrar Gasto")
        with st.form("form_gastos", clear_on_submit=True):
            categoria = st.selectbox("Tipo de Gasto", df_categorias['nombre'])
            detalle = st.text_input("Detalle (Ej. Pago de turnos, Gasolina)")
            monto = st.number_input("Monto (Q)", min_value=0.00, step=10.00)
            
            if st.form_submit_button("Guardar Gasto"):
                corte_id = obtener_corte_hoy()
                cat_id = df_categorias.loc[df_categorias['nombre'] == categoria, 'id'].values[0]
                
                with conn.session as s:
                    s.execute(text("""
                        INSERT INTO gastos (corte_id, categoria_id, detalle, monto) 
                        VALUES (:corte_id, :cat_id, :detalle, :monto)
                    """), {"corte_id": corte_id, "cat_id": int(cat_id), "detalle": detalle, "monto": monto})
                    s.commit()
                st.success(f"✅ Gasto guardado: Q{monto} en {categoria}")

with tab2:
    st.header("Estadísticas Mensuales")
    st.info("Aquí colocaremos gráficas de pastel y barras cuando tengamos más datos guardados.")

with tab3:
    st.header("Control de Proveedores (Créditos)")
    st.info("Aquí verás las alertas de cuándo toca pagar la harina, gas, etc.")
