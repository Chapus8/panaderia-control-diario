import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import pytz
import plotly.express as px
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
    # EL ESCUDO: pool_pre_ping=True verifica que Neon esté despierto antes de consultarlo
    conn = st.connection("postgresql", type="sql", pool_pre_ping=True)
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

def autocompletar_categoria(detalle):
    d = str(detalle).lower()
    if any(x in d for x in ['harina', 'azucar', 'azúcar', 'manteca', 'levadura', 'leche', 'huevo', 'huevos', 'sal']):
        return 'MATERIA PRIMA'
    elif any(x in d for x in ['bono', 'sueldo', 'pago', 'salario', 'anticipo', 'almuerzo', 'planilla', 'turno', 'quincena']):
        return 'SUELDOS Y SALARIOS'
    elif any(x in d for x in ['gasolina', 'moto', 'vehiculo', 'repuesto', 'llanta', 'aceite', 'mecanico', 'pinchazo']):
        return 'REPUESTOS Y REPARACIONES'
    elif any(x in d for x in ['bolsa', 'bandeja', 'calcomania', 'papel', 'limpieza', 'empaque', 'escoba', 'jabon', 'cloro']):
        return 'UTILES Y EMPAQUES'
    elif any(x in d for x in ['prestamo', 'tarjeta', 'interes', 'abono', 'banco', 'cuota']):
        return 'PRESTAMOS E INTERESES'
    elif any(x in d for x in ['pasta', 'pollo']):
        return 'COMPRAS DE PASTA DE POLLO'
    elif any(x in d for x in ['bebida', 'dulce', 'tostada', 'marquesote', 'agua', 'gaseosa', 'coca']):
        return 'OTRAS MERCADERIAS'
    elif any(x in d for x in ['gas ', 'propano', 'luz', 'internet', 'telefono', 'alquiler', 'impuesto', 'basura']):
        return 'OTROS GASTOS'
    return 'OTROS GASTOS' 

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
        if row["Monto (Q)"] > 0:
            categoria_mostrar = row["Categoría"] if pd.notna(row["Categoría"]) else "OTROS GASTOS"
            gastos_table_data.append([str(categoria_mostrar), str(row["Detalle"]), f"Q {row['Monto (Q)']:.2f}"])
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
    
    # Intento seguro de leer las tablas
    try:
        df_rutas = conn.query("SELECT id, nombre FROM rutas_locales", ttl=0)
        df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto", ttl=0)
        lista_categorias = df_categorias['nombre'].tolist()
    except Exception as e:
        st.error("⚠️ La base de datos está inactiva o faltan las tablas principales. Refresca la página.")
        st.stop()
    
    col_enc1, col_enc2, col_enc3 = st.columns(3)
    fecha_corte = col_enc1.date_input("Fecha del Corte", get_fecha_guate(), format="DD/MM/YYYY")
    local_ruta = col_enc2.selectbox("Local / Ruta", df_rutas['nombre'])
    responsable = col_enc3.selectbox("Responsable", ["Dania", "Ana Judith Ramirez", "Stephanie Roldan", "Wendy Perez", "Otro"])
    
    st.markdown("---")
    st.markdown("### 💸 Detalle de Gastos")
    st.caption("✨ **Escribe el detalle y presiona 'Enter'.** ¡El sistema llenará la categoría por ti al instante!")
    
    if 'gastos_df' not in st.session_state:
        st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11): 
            st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]

    gastos_editados = st.data_editor(
        st.session_state.gastos_df,
        column_config={
            "Categoría": st.column_config.SelectboxColumn("Tipo de Gasto (Automático)", options=lista_categorias, required=False),
            "Detalle": st.column_config.TextColumn("Detalle (Escribe y presiona Enter)"),
            "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")
        },
        num_rows="dynamic",
        use_container_width=True
    )
    
    hubo_cambios = False
    for i, row in gastos_editados.iterrows():
        detalle = str(row["Detalle"]).strip() if pd.notna(row["Detalle"]) else ""
        categoria = row["Categoría"]
        
        if detalle != "" and (pd.isna(categoria) or categoria is None or str(categoria).strip() == ""):
            nueva_cat = autocompletar_categoria(detalle)
            gastos_editados.at[i, "Categoría"] = nueva_cat
            hubo_cambios = True

    if hubo_cambios:
        st.session_state.gastos_df = gastos_editados
        st.rerun()
    else:
        st.session_state.gastos_df = gastos_editados
    
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
                    monto = row["Monto (Q)"]
                    if monto > 0:
                        detalle = str(row["Detalle"]).strip() if pd.notna(row["Detalle"]) else "Gasto sin detalle"
                        categoria = row["Categoría"] if pd.notna(row["Categoría"]) else "OTROS GASTOS"
                        
                        if categoria in lista_categorias:
                            cat_id = df_categorias.loc[df_categorias['nombre'] == categoria, 'id'].values[0]
                            s.execute(text("INSERT INTO gastos (corte_id, categoria_id, detalle, monto) VALUES (:c, :cat, :d, :m)"), 
                                      {"c": corte_id, "cat": int(cat_id), "d": detalle, "m": monto})
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
    st.title("📈 Estadísticas y Finanzas")
    st.write("Filtra tus movimientos por mes para analizar el rendimiento del negocio.")
    
    meses_dict = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, 
        "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }
    
    hoy = get_fecha_guate()
    nombre_mes_actual = list(meses_dict.keys())[list(meses_dict.values()).index(hoy.month)]
    
    col_f1, col_f2 = st.columns(2)
    mes_seleccionado = col_f1.selectbox("Selecciona el Mes", list(meses_dict.keys()), index=list(meses_dict.keys()).index(nombre_mes_actual))
    anio_seleccionado = col_f2.selectbox("Selecciona el Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1)
    
    mes_num = meses_dict[mes_seleccionado]
    
    try:
        query_gastos = """
            SELECT c.nombre as categoria, SUM(g.monto) as total 
            FROM gastos g 
            JOIN categorias_gasto c ON g.categoria_id = c.id 
            JOIN cortes_diarios cd ON g.corte_id = cd.id
            WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio
            GROUP BY c.nombre
        """
        gastos_totales = conn.query(query_gastos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        
        query_ingresos = """
            SELECT SUM(i.venta_total + COALESCE(i.credito_pagado, 0)) as total_ingresos
            FROM ingresos i
            JOIN cortes_diarios cd ON i.corte_id = cd.id
            WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio
        """
        ingresos_totales = conn.query(query_ingresos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        
        total_g = gastos_totales['total'].sum() if not gastos_totales.empty else 0.0
        
        if not ingresos_totales.empty and pd.notna(ingresos_totales.iloc[0]['total_ingresos']):
            total_i = float(ingresos_totales.iloc[0]['total_ingresos'])
        else:
            total_i = 0.0
            
        utilidad = total_i - total_g
        
        st.markdown("---")
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric(f"💵 Ingresos ({mes_seleccionado})", f"Q {total_i:.2f}")
        col_s2.metric(f"📉 Gastos ({mes_seleccionado})", f"Q {total_g:.2f}")
        col_s3.metric(f"⚖️ Utilidad Bruta", f"Q {utilidad:.2f}")
        st.markdown("---")
        
        if not gastos_totales.empty and total_g > 0:
            fig = px.pie(gastos_totales, values='total', names='categoria', hole=0.4, title=f"Distribución de Gastos - {mes_seleccionado} {anio_seleccionado}")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"📊 No hay gastos registrados para el mes de {mes_seleccionado} {anio_seleccionado}.")
            
    except Exception as e:
        st.error(f"Error al cargar las estadísticas: {e}")

# ------------------------------------------
# MÓDULO 4: PROVEEDORES
# ------------------------------------------
elif opcion_menu == "💳 Proveedores":
    st.title("💳 Control de Créditos y Proveedores")
    
    try:
        tab_prov1, tab_prov2, tab_prov3 = st.tabs(["📋 Gestionar Proveedores", "➕ Registrar Deuda", "🚨 Deudas Activas"])
        
        with tab_prov1:
            st.subheader("Administrar Directorio de Proveedores")
            
            with st.expander("➕ Agregar un Nuevo Proveedor"):
                with st.form("form_nuevo_proveedor", clear_on_submit=True):
                    nuevo_nombre = st.text_input("Nombre del Proveedor (Ej. Molino Central)")
                    nuevo_producto = st.text_input("Producto o Servicio (Ej. Harina)")
                    if st.form_submit_button("Guardar Proveedor"):
                        if nuevo_nombre:
                            with conn.session as s:
                                s.execute(text("INSERT INTO proveedores (nombre, producto_servicio) VALUES (:n, :p)"), 
                                          {"n": nuevo_nombre, "p": nuevo_producto})
                                s.commit()
                            st.success(f"✅ ¡Proveedor '{nuevo_nombre}' agregado con éxito!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Escribe al menos el nombre del proveedor.")
            
            st.markdown("---")
            st.markdown("### Editar o Eliminar Proveedores Existentes")
            df_prov_edit = conn.query("SELECT id, nombre, producto_servicio FROM proveedores ORDER BY id", ttl=0)
            
            if not df_prov_edit.empty:
                proveedores_editados = st.data_editor(
                    df_prov_edit,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "nombre": st.column_config.TextColumn("Nombre del Proveedor", required=True),
                        "producto_servicio": st.column_config.TextColumn("Insumo / Producto")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_proveedores"
                )
                
                if st.button("💾 Guardar Cambios en Proveedores", type="primary"):
                    with conn.session as s:
                        for index, row in proveedores_editados.iterrows():
                            s.execute(text("""
                                UPDATE proveedores 
                                SET nombre = :nombre, producto_servicio = :prod 
                                WHERE id = :id
                            """), {
                                "nombre": row["nombre"],
                                "prod": row["producto_servicio"],
                                "id": int(row["id"])
                            })
                        s.commit()
                    st.success("✅ ¡Proveedores actualizados correctamente!")
                    st.rerun()
                
                st.markdown("---")
                st.markdown("### 🗑️ Eliminar Proveedor")
                prov_a_borrar = st.selectbox("Selecciona el proveedor que deseas eliminar:", df_prov_edit['nombre'])
                if st.button("Eliminar Proveedor Seleccionado", type="secondary"):
                    id_borrar = df_prov_edit.loc[df_prov_edit['nombre'] == prov_a_borrar, 'id'].values[0]
                    with conn.session as s:
                        s.execute(text("DELETE FROM cuentas_por_pagar WHERE proveedor_id = :id"), {"id": int(id_borrar)})
                        s.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": int(id_borrar)})
                        s.commit()
                    st.success(f"🗑️ Proveedor '{prov_a_borrar}' eliminado del sistema.")
                    st.rerun()
            else:
                st.info("No hay proveedores registrados todavía.")

        with tab_prov2:
            st.subheader("Registrar Factura o Crédito")
            df_proveedores = conn.query("SELECT id, nombre FROM proveedores ORDER BY nombre", ttl=0)
            
            if not df_proveedores.empty:
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
            else:
                st.warning("⚠️ Primero debes registrar al menos un proveedor en la pestaña 'Gestionar Proveedores'.")

        with tab_prov3:
            st.subheader("Listado de Cuentas por Pagar")
            deudas_activas = conn.query("""
                SELECT c.id, p.nombre as proveedor, c.num_documento as documento, p.producto_servicio as insumo, 
                       c.fecha_vencimiento as vencimiento, c.saldo_pendiente as saldo 
                FROM cuentas_por_pagar c 
                JOIN proveedores p ON c.proveedor_id = p.id 
                WHERE c.estado = 'Pendiente'
            """, ttl=0)
            
            if not deudas_activas.empty:
                hoy = get_fecha_guate()
                deudas_activas['vencimiento'] = pd.to_datetime(deudas_activas['vencimiento']).dt.date
                
                def asignar_semaforo(fecha_vence):
                    if pd.isnull(fecha_vence): 
                        return "⚪ Sin Fecha"
                    dias_restantes = (fecha_vence - hoy).days
                    if dias_restantes < 0: 
                        return "🔴 Vencido"
                    elif 0 <= dias_restantes <= 3: 
                        return "🟡 Próximo (0-3 días)"
                    else: 
                        return "🟢 A tiempo"
                
                deudas_activas.insert(0, 'Estado', deudas_activas['vencimiento'].apply(asignar_semaforo))
                
                st.dataframe(
                    deudas_activas, 
                    column_config={
                        "Estado": "Estatus",
                        "id": "ID",
                        "proveedor": "Proveedor",
                        "documento": "Documento",
                        "insumo": "Insumo",
                        "vencimiento": st.column_config.DateColumn("Vencimiento", format="DD/MM/YYYY"),
                        "saldo": st.column_config.NumberColumn("Saldo Pendiente", format="Q %.2f")
                    },
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.success("🎉 ¡Felicidades! No tienes deudas pendientes registradas.")
                
    except Exception as e:
        st.error(f"Error en el módulo de proveedores: {e}")
