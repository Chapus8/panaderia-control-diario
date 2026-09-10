import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import pytz
import plotly.express as px

# Librerías para generar el PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

# ==========================================
# 1. CONFIGURACIÓN PRINCIPAL
# ==========================================
st.set_page_config(page_title="Panadería Judith - Sistema", page_icon="🍞", layout="wide")

USUARIOS = {
    "roberto": "esquipulas123", 
    "admin": "admin2026"
}

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
# 3. CONEXIÓN A BASE DE DATOS Y FUNCIONES
# ==========================================
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

# --- FUNCIÓN PARA GENERAR EL PDF TAMAÑO CARTA ---
def generar_pdf_corte(fecha_str, local_str, responsable_str, df_gastos, venta_mostrador, pago_pedidos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50"))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray)
    bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=10, fontName="Helvetica-Bold")
    
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style))
    elements.append(Paragraph("INTEGRACIÓN DE INGRESOS Y EGRESOS - CORTE DE CAJA", subtitle_style))
    elements.append(Spacer(1, 15))
    
    info_data = [
        [Paragraph(f"<b>Fecha:</b> {fecha_str}", bold_style), Paragraph(f"<b>Local / Ruta:</b> {local_str}", bold_style), Paragraph(f"<b>Responsable:</b> {responsable_str}", bold_style)]
    ]
    info_table = Table(info_data, colWidths=[150, 200, 190])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAFAF1")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#27AE60")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))
    
    gastos_table_data = [["TIPO DE GASTO", "DETALLE", "TOTAL (Q)"]]
    total_gastos = 0.0
    
    for index, row in df_gastos.iterrows():
        if pd.notna(row["Categoría"]) and row["Monto (Q)"] > 0:
            gastos_table_data.append([str(row["Categoría"]), str(row["Detalle"]), f"Q {row['Monto (Q)']:.2f}"])
            total_gastos += float(row["Monto (Q)"])
            
    while len(gastos_table_data) < 10:
        gastos_table_data.append(["", "", ""])
        
    gastos_table_data.append(["", "TOTAL GASTOS", f"Q {total_gastos:.2f}"])
    
    t_gastos = Table(gastos_table_data, colWidths=[180, 240, 120])
    t_gastos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#27AE60")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#D4EFDF")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    elements.append(t_gastos)
    elements.append(Spacer(1, 15))
    
    total_ingresos = venta_mostrador + pago_pedidos
    neto = total_ingresos - total_gastos
    
    resumen_data = [
        ["RESUMEN FINANCIERO", "MONTO"],
        ["Venta de Pan (Mostrador)", f"Q {venta_mostrador:.2f}"],
        ["Pago de Pedidos / Abonos", f"Q {pago_pedidos:.2f}"],
        ["TOTAL INGRESOS", f"Q {total_ingresos:.2f}"],
        ["TOTAL GASTOS", f"Q {total_gastos:.2f}"],
        ["SALDO NETO ENTREGADO", f"Q {neto:.2f}"]
    ]
    
    t_resumen = Table(resumen_data, colWidths=[340, 200])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#EAECEE")),
        ('BACKGROUND', (0,5), (-1,5), colors.HexColor("#D4EFDF")),
        ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
        ('FONTNAME', (0,5), (-1,5), 'Helvetica-Bold'),
    ]))
    elements.append(t_resumen)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# 4. MENÚ LATERAL (SIDEBAR)
# ==========================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['usuario'].capitalize()}")
    st.write(f"📅 Fecha actual: {get_fecha_guate().strftime('%d/%m/%Y')}")
    st.markdown("---")
    
    st.subheader("📍 Menú Principal")
    opcion_menu = st.radio(
        "Selecciona un módulo:",
        ["📝 Registro de Corte", "📅 Historial de Cortes", "📈 Estadísticas", "💳 Proveedores"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['logueado'] = False
        st.rerun()

# ==========================================
# 5. MÓDULOS DE LA APLICACIÓN
# ==========================================

# ------------------------------------------
# MÓDULO 1: REGISTRO DE CORTE
# ------------------------------------------
if opcion_menu == "📝 Registro de Corte":
    st.title("🍞 Ingreso Diario de Corte")
    st.markdown("### 📋 Datos del Corte")
    
    df_rutas = conn.query("SELECT id, nombre FROM rutas_locales", ttl=0)
    df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto", ttl=0)
    lista_categorias = df_categorias['nombre'].tolist()
    
    col_enc1, col_enc2, col_enc3 = st.columns(3)
    fecha_corte = col_enc1.date_input("Fecha del Corte", get_fecha_guate(), format="DD/MM/YYYY")
    local_ruta = col_enc2.selectbox("Local / Ruta", df_rutas['nombre'])
    responsable = col_enc3.selectbox("Responsable", ["Dania", "Ana Judith Ramirez", "Stephanie Roldan", "Wendy Perez", "Otro"])
    
    st.markdown("---")
    st.markdown("### 💸 Detalle de Gastos")
    
    if 'gastos_df' not in st.session_state:
        st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11): 
            st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]

    gastos_editados = st.data_editor(
        st.session_state.gastos_df,
        column_config={
            "Categoría": st.column_config.SelectboxColumn("Tipo de Gasto", options=lista_categorias, required=True),
            "Detalle": st.column_config.TextColumn("Detalle (Ej. Almuerzo, Bono, Harina)"),
            "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")
        },
        num_rows="dynamic",
        use_container_width=True
    )
    
    st.markdown("---")
    st.markdown("### 💰 Resumen de Ingresos")
    col_ing1, col_ing2, col_ing3 = st.columns(3)
    
    venta_mostrador = col_ing1.number_input("🍞 Venta de Pan (Mostrador)", min_value=0.00, step=50.00)
    pago_pedidos = col_ing2.number_input("🎂 Pago de Pedidos / Abonos", min_value=0.00, step=50.00)
    
    total_ingresos = venta_mostrador + pago_pedidos
    total_gastos_calc = gastos_editados["Monto (Q)"].sum()
    
    st.markdown("---")
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
                if total_ingresos > 0:
                    s.execute(text("INSERT INTO ingresos (corte_id, ruta_id, venta_total, credito_pagado) VALUES (:c, :r, :v, :cp)"), 
                              {"c": corte_id, "r": int(ruta_id), "v": venta_mostrador, "cp": pago_pedidos})
                
                for index, row in gastos_editados.iterrows():
                    if pd.notna(row["Categoría"]) and row["Monto (Q)"] > 0:
                        cat_id = df_categorias.loc[df_categorias['nombre'] == row["Categoría"], 'id'].values[0]
                        s.execute(text("INSERT INTO gastos (corte_id, categoria_id, detalle, monto) VALUES (:c, :cat, :d, :m)"), 
                                  {"c": corte_id, "cat": int(cat_id), "d": row["Detalle"], "m": row["Monto (Q)"]})
                s.commit()
            
            st.success("✅ ¡Corte guardado y listo para imprimir!")
            st.balloons()
            
            pdf_buffer = generar_pdf_corte(fecha_corte.strftime('%d/%m/%Y'), local_ruta, responsable, gastos_editados, venta_mostrador, pago_pedidos)
            st.session_state['pdf_generado'] = pdf_buffer
            st.session_state['pdf_nombre'] = f"Corte_{fecha_corte.strftime('%d-%m-%Y')}.pdf"
            
            st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
            for _ in range(11):
                st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]
        else:
            st.warning("⚠️ Debes ingresar al menos una venta o un gasto para guardar.")
            
    if 'pdf_generado' in st.session_state:
        st.markdown("---")
        st.download_button(
            label="📥 Descargar PDF del Corte para Imprimir",
            data=st.session_state['pdf_generado'],
            file_name=st.session_state['pdf_nombre'],
            mime="application/pdf",
            type="secondary",
            use_container_width=True
        )

# ------------------------------------------
# MÓDULO 2: HISTORIAL DE CORTES
# ------------------------------------------
elif opcion_menu == "📅 Historial de Cortes":
    st.title("📅 Consulta de Historial e Impresión")
    st.write("Selecciona un día para consultar el movimiento o reimprimir su PDF.")
    
    fecha_consulta = st.date_input("Consultar fecha:", get_fecha_guate(), format="DD/MM/YYYY")
    
    try:
        corte_data = conn.query(f"SELECT id FROM cortes_diarios WHERE fecha = '{fecha_consulta}'", ttl=0)
        
        if not corte_data.empty:
            corte_id = corte_data.iloc[0]['id']
            
            ingresos_hist = conn.query(f"SELECT r.nombre as Ruta, i.venta_total as Venta_Mostrador, i.credito_pagado as Pedidos FROM ingresos i JOIN rutas_locales r ON i.ruta_id = r.id WHERE i.corte_id = {corte_id}", ttl=0)
            gastos_hist = conn.query(f"SELECT c.nombre as Categoria, g.detalle as Detalle, g.monto as Monto FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id WHERE g.corte_id = {corte_id}", ttl=0)
            
            sum_venta = ingresos_hist['venta_mostrador'].sum() if not ingresos_hist.empty else 0.0
            sum_pedidos = ingresos_hist['pedidos'].sum() if not ingresos_hist.empty else 0.0
            sum_ingresos = sum_venta + sum_pedidos
            sum_gastos = gastos_hist['monto'].sum() if not gastos_hist.empty else 0.0
            
            st.markdown(f"### Resumen del {fecha_consulta.strftime('%d/%m/%Y')}")
            col_h1, col_h2, col_h3 = st.columns(3)
            col_h1.metric("💵 Total Ingresado", f"Q {sum_ingresos:.2f}")
            col_h2.metric("📉 Total Gastado", f"Q {sum_gastos:.2f}")
            col_h3.metric("⚖️ Saldo Neto", f"Q {sum_ingresos - sum_gastos:.2f}")
            
            st.markdown("---")
            
            ruta_nombre = ingresos_hist.iloc[0]['ruta'] if not ingresos_hist.empty else "LOCAL MERCADO"
            df_para_pdf = pd.DataFrame({
                "Categoría": gastos_hist['categoria'] if not gastos_hist.empty else [],
                "Detalle": gastos_hist['detalle'] if not gastos_hist.empty else [],
                "Monto (Q)": gastos_hist['monto'] if not gastos_hist.empty else []
            })
            
            pdf_historico = generar_pdf_corte(fecha_consulta.strftime('%d/%m/%Y'), ruta_nombre, "Histórico", df_para_pdf, sum_venta, sum_pedidos)
            
            st.download_button(
                label=f"📥 Descargar PDF del {fecha_consulta.strftime('%d/%m/%Y')} para Imprimir",
                data=pdf_historico,
                file_name=f"Corte_{fecha_consulta.strftime('%d-%m-%Y')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
            st.markdown("---")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.subheader("💰 Desglose de Ingresos")
                if not ingresos_hist.empty:
                    st.dataframe(ingresos_hist, use_container_width=True, hide_index=True)
                else:
                    st.info("No se registraron ingresos este día.")
            
            with col_t2:
                st.subheader("💸 Desglose de Gastos")
                if not gastos_hist.empty:
                    st.dataframe(gastos_hist, use_container_width=True, hide_index=True)
                else:
                    st.info("No se registraron gastos este día.")
        else:
            st.warning(f"No hay ningún corte guardado en el sistema para la fecha {fecha_consulta.strftime('%d/%m/%Y')}.")
            
    except Exception as e:
        st.error("Error al consultar el historial.")

# ------------------------------------------
# MÓDULO 3: ESTADÍSTICAS
# ------------------------------------------
elif opcion_menu == "📈 Estadísticas":
    st.title("📈 Visualización de Finanzas")
    st.write("Mira en qué se está yendo el dinero.")
    try:
        gastos_totales = conn.query("SELECT c.nombre as categoria, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id GROUP BY c.nombre", ttl=0)
        if not gastos_totales.empty and gastos_totales['total'].sum() > 0:
            fig = px.pie(gastos_totales, values='total', names='categoria', hole=0.4, title="Distribución Histórica de Gastos")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 Aún no hay suficientes datos para generar la gráfica.")
    except Exception as e:
        st.info("📊 Esperando datos...")

# ------------------------------------------
# MÓDULO 4: PROVEEDORES (Con opción para agregar nuevos)
# ------------------------------------------
elif opcion_menu == "💳 Proveedores":
    st.title("💳 Control de Créditos y Proveedores")
    
    try:
        # 1. EXPANDER PARA AGREGAR NUEVO PROVEEDOR
        with st.expander("🏢 Agregar un Nuevo Proveedor a la lista"):
            with st.form("form_nuevo_proveedor", clear_on_submit=True):
                nuevo_prov_nombre = st.text_input("Nombre del Proveedor (Ej. Zeta Gas, Molino Nuevo)")
                nuevo_prov_producto = st.text_input("¿Qué producto o servicio vende? (Ej. Gas Propano, Harina)")
                
                if st.form_submit_button("Guardar Proveedor"):
                    if nuevo_prov_nombre:
                        with conn.session as s:
                            s.execute(text("INSERT INTO proveedores (nombre, producto_servicio) VALUES (:n, :p)"), 
                                      {"n": nuevo_prov_nombre, "p": nuevo_prov_producto})
                            s.commit()
                        st.success(f"✅ ¡Proveedor '{nuevo_prov_nombre}' agregado con éxito! Ya puedes seleccionarlo abajo.")
                        st.rerun()
                    else:
                        st.warning("⚠️ Debes escribir al menos el nombre del proveedor.")

        st.markdown("---")

        # 2. EXPANDER PARA REGISTRAR CUENTA POR PAGAR
        df_proveedores = conn.query("SELECT id, nombre, producto_servicio FROM proveedores", ttl=0)
        
        with st.expander("➕ Registrar nueva cuenta por pagar (Deuda)"):
            with st.form("form_credito", clear_on_submit=True):
                prov = st.selectbox("Seleccionar Proveedor", df_proveedores['nombre'])
                num_factura = st.text_input("📄 No. de Factura o Documento (Ej. FAC-12345)")
                monto_credito = st.number_input("Monto total de la deuda (Q)", min_value=0.00, step=100.00)
                fecha_vencimiento = st.date_input("¿Cuándo toca pagar?", get_fecha_guate(), format="DD/MM/YYYY")
                
                if st.form_submit_button("Guardar Deuda"):
                    prov_id = df_proveedores.loc[df_proveedores['nombre'] == prov, 'id'].values[0]
                    with conn.session as s:
                        s.execute(text("""
                            INSERT INTO cuentas_por_pagar (proveedor_id, num_documento, fecha_compra, fecha_vencimiento, monto_total, saldo_pendiente) 
                            VALUES (:p, :doc, :f_compra, :f_vence, :monto, :saldo)
                        """), {
                            "p": int(prov_id), 
                            "doc": num_factura, 
                            "f_compra": get_fecha_guate(), 
                            "f_vence": fecha_vencimiento, 
                            "monto": monto_credito, 
                            "saldo": monto_credito
                        })
                        s.commit()
                    st.success("✅ Deuda registrada correctamente.")
        
        st.subheader("🚨 Deudas Activas")
        deudas_activas = conn.query("""
            SELECT p.nombre as Proveedor, c.num_documento as Documento, p.producto_servicio as Insumo, 
                   c.fecha_vencimiento as Vencimiento, c.saldo_pendiente as Saldo 
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
        st.error("Error al cargar el módulo de proveedores.")
