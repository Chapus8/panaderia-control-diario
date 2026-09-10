import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import pytz
import plotly.express as px

# ==========================================
# 1. CONFIGURACIÓN PRINCIPAL
# ==========================================
st.set_page_config(page_title="Panadería Judith - Sistema", page_icon="🍞", layout="wide")

USUARIOS = {
    "roberto": "esquipulas123", 
    "admin": "admin2026"
}

# Función para obtener la fecha exacta en Guatemala
def get_fecha_guate():
    zona_guate = pytz.timezone('America/Guatemala')
    return datetime.now(zona_guate).date()

# ==========================================
# 2. SISTEMA DE SEGURIDAD (LOGIN)
# ==========================================
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

# ==========================================
# 3. BARRA LATERAL Y CONEXIÓN A BASE DE DATOS
# ==========================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['usuario'].capitalize()}")
    st.write(f"📅 Fecha actual: {get_fecha_guate().strftime('%d/%m/%Y')}")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['logueado'] = False
        st.rerun()

try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("🔴 Error de conexión con la base de datos.")
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

# ==========================================
# 4. INTERFAZ DE LA APLICACIÓN
# ==========================================
st.title("🍞 Sistema de Control - Panadería Judith")

tab1, tab2, tab3 = st.tabs(["📝 Ingreso de Corte (Formato Papel)", "📈 Estadísticas", "💳 Proveedores y Créditos"])

# ------------------------------------------
# PESTAÑA 1: INGRESO DE CORTE TIPO PAPEL
# ------------------------------------------
with tab1:
    st.markdown("### 📋 Datos del Corte")
    
    df_rutas = conn.query("SELECT id, nombre FROM rutas_locales", ttl=0)
    df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto", ttl=0)
    lista_categorias = df_categorias['nombre'].tolist()
    
    col_enc1, col_enc2, col_enc3 = st.columns(3)
    fecha_corte = col_enc1.date_input("Fecha del Corte", get_fecha_guate(), format="DD/MM/YYYY")
    local_ruta = col_enc2.selectbox("Local / Ruta", df_rutas['nombre'])
    responsable = col_enc3.selectbox("Responsable", ["Dania", "Ana Judith Ramirez", "Stephanie Roldan", "Wendy Perez", "Otro"])
    
    st.markdown("---")
    
    # --- TABLA DE GASTOS ---
    st.markdown("### 💸 Detalle de Gastos")
    st.caption("Anota aquí todos los gastos que salieron de la caja hoy (salarios, bonos, insumos, etc.)")
    
    if 'gastos_df' not in st.session_state:
        st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(5): 
            st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]

    gastos_editados = st.data_editor(
        st.session_state.gastos_df,
        column_config={
            "Categoría": st.column_config.SelectboxColumn("Tipo de Gasto", options=lista_categorias, required=True),
            "Detalle": st.column_config.TextColumn("Detalle (Ej. Bono Dania, Huevos)"),
            "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")
        },
        num_rows="dynamic",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # --- NUEVA SECCIÓN DE INGRESOS ---
    st.markdown("### 💰 Resumen de Ingresos")
    col_ing1, col_ing2, col_ing3 = st.columns(3)
    
    venta_mostrador = col_ing1.number_input("🍞 Venta de Pan (Mostrador)", min_value=0.00, step=50.00)
    pago_pedidos = col_ing2.number_input("🎂 Pago de Pedidos / Abonos", min_value=0.00, step=50.00)
    
    total_ingresos = venta_mostrador + pago_pedidos
    total_gastos_calc = gastos_editados["Monto (Q)"].sum()
    
    st.markdown("---")
    
    # --- CUADRE FINAL ---
    st.markdown("### 📊 Cuadre Final")
    col_tot1, col_tot2, col_tot3 = st.columns(3)
    
    col_tot1.metric("💵 Total Ingresos (Venta + Pedidos)", f"Q {total_ingresos:.2f}")
    col_tot2.metric("📉 Suma Total de Gastos", f"Q {total_gastos_calc:.2f}")
    col_tot3.metric("⚖️ Total Neto Entregado", f"Q {total_ingresos - total_gastos_calc:.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("💾 Guardar Corte Completo", type="primary", use_container_width=True):
        if total_ingresos > 0 or total_gastos_calc > 0:
            corte_id = obtener_o_crear_corte(fecha_corte)
            ruta_id = df_rutas.loc[df_rutas['nombre'] == local_ruta, 'id'].values[0]
            
            with conn.session as s:
                # Guardamos los ingresos separados en la base de datos (venta normal y el abono a créditos/pedidos)
                if total_ingresos > 0:
                    s.execute(text("INSERT INTO ingresos (corte_id, ruta_id, venta_total, credito_pagado) VALUES (:c, :r, :v, :cp)"), 
                              {"c": corte_id, "r": int(ruta_id), "v": venta_mostrador, "cp": pago_pedidos})
                
                # Guardamos la tabla de gastos
                for index, row in gastos_editados.iterrows():
                    if pd.notna(row["Categoría"]) and row["Monto (Q)"] > 0:
                        cat_id = df_categorias.loc[df_categorias['nombre'] == row["Categoría"], 'id'].values[0]
                        s.execute(text("INSERT INTO gastos (corte_id, categoria_id, detalle, monto) VALUES (:c, :cat, :d, :m)"), 
                                  {"c": corte_id, "cat": int(cat_id), "d": row["Detalle"], "m": row["Monto (Q)"]})
                
                s.commit()
            
            st.success("✅ ¡Corte guardado exitosamente en la base de datos!")
            st.balloons()
            
            # Limpiamos la tabla de gastos
            st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
            for _ in range(5):
                st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]
        else:
            st.warning("⚠️ Debes ingresar al menos una venta o un gasto para guardar.")

# ------------------------------------------
# PESTAÑA 2: ESTADÍSTICAS
# ------------------------------------------
with tab2:
    st.header("Visualización de Finanzas")
    st.write("Mira en qué se está yendo el dinero.")
    
    try:
        gastos_totales = conn.query("SELECT c.nombre as categoria, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id GROUP BY c.nombre", ttl=0)
        
        if not gastos_totales.empty and gastos_totales['total'].sum() > 0:
            fig = px.pie(gastos_totales, values='total', names='categoria', hole=0.4, title="Distribución Histórica de Gastos")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 Aún no hay gastos registrados para generar la gráfica. Guarda tu primer corte en la pestaña anterior.")
    except Exception as e:
        st.info("📊 Esperando que ingreses los primeros datos para mostrar las estadísticas...")

# ------------------------------------------
# PESTAÑA 3: CONTROL DE PROVEEDORES Y DEUDAS
# ------------------------------------------
with tab3:
    st.header("Control de Créditos (Harina, Gas, etc.)")
    
    try:
        df_proveedores = conn.query("SELECT id, nombre, producto_servicio FROM proveedores", ttl=0)
        
        with st.expander("➕ Registrar nueva cuenta por pagar"):
            with st.form("form_credito", clear_on_submit=True):
                prov = st.selectbox("Proveedor", df_proveedores['nombre'])
                monto_credito = st.number_input("Monto total de la deuda (Q)", min_value=0.00, step=100.00)
                fecha_vencimiento = st.date_input("¿Cuándo toca pagar?", get_fecha_guate(), format="DD/MM/YYYY")
                
                if st.form_submit_button("Guardar Deuda"):
                    prov_id = df_proveedores.loc[df_proveedores['nombre'] == prov, 'id'].values[0]
                    with conn.session as s:
                        s.execute(text("""
                            INSERT INTO cuentas_por_pagar (proveedor_id, fecha_compra, fecha_vencimiento, monto_total, saldo_pendiente)
                            VALUES (:p, :f_compra, :f_vence, :monto, :saldo)
                        """), {"p": int(prov_id), "f_compra": get_fecha_guate(), "f_vence": fecha_vencimiento, "monto": monto_credito, "saldo": monto_credito})
                        s.commit()
                    st.success("✅ Deuda registrada correctamente.")
        
        st.subheader("🚨 Deudas Activas")
        deudas_activas = conn.query("""
            SELECT p.nombre as Proveedor, p.producto_servicio as Insumo, c.fecha_vencimiento as Vencimiento, c.saldo_pendiente as Saldo
            FROM cuentas_por_pagar c
            JOIN proveedores p ON c.proveedor_id = p.id
            WHERE c.estado = 'Pendiente'
        """, ttl=0)
        
        if not deudas_activas.empty:
            deudas_activas['vencimiento'] = pd.to_datetime(deudas_activas['vencimiento']).dt.strftime('%d/%m/%Y')
            st.dataframe(deudas_activas, use_container_width=True, hide_index=True)
        else:
            st.success("🎉 ¡Felicidades! No tienes deudas pendientes registradas.")
            
    except Exception as e:
        st.error("Aún configurando la tabla de proveedores...")
