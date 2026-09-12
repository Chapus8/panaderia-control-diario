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
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
import io
import re
import streamlit.components.v1 as components 

# ==========================================
# 1. CONFIGURACIÓN PRINCIPAL Y ESCUDO DE TECLADO
# ==========================================
st.set_page_config(page_title="Panadería Judith - Sistema", page_icon="🍞", layout="wide")

components.html(
    """
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if ((e.key.toLowerCase() === 'c' || e.key.toLowerCase() === 'r') && 
            e.target.nodeName !== 'INPUT' && 
            e.target.nodeName !== 'TEXTAREA') {
            e.stopPropagation();
            e.preventDefault();
        }
    }, true);
    </script>
    """,
    height=0, width=0
)

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
    if 'pasta' in d or 'pollo' in d:
        return 'COMPRAS DE PASTA DE POLLO'
    if 'bolsa de agua' in d or 'agua' in d or 'gaseosa' in d or 'coca' in d or 'bebida' in d or 'tostada' in d or 'marquesote' in d:
        return 'OTRAS MERCADERIAS'
    if 'luz' in d or 'internet' in d or 'telefono' in d or 'basura' in d or 'alquiler' in d or 'impuesto' in d or 'gas ' in d or 'propano' in d:
        return 'OTROS GASTOS' 
    if re.search(r'\b(harina|azucar|azúcar|manteca|levadura|leche|huevo|huevos|sal)\b', d):
        return 'MATERIA PRIMA'
    if re.search(r'\b(bono|sueldo|sueldos|salario|salarios|anticipo|almuerzo|planilla|turno|quincena|panadero)\b', d):
        return 'SUELDOS Y SALARIOS'
    if re.search(r'\b(gasolina|moto|vehiculo|repuesto|llanta|aceite|mecanico|pinchazo)\b', d):
        return 'REPUESTOS Y REPARACIONES'
    if re.search(r'\b(bolsa|bandeja|calcomania|papel|limpieza|empaque|escoba|jabon|cloro)\b', d):
        return 'UTILES Y EMPAQUES'
    if re.search(r'\b(prestamo|tarjeta|interes|abono|banco|cuota)\b', d):
        return 'PRESTAMOS E INTERESES'
    return 'OTROS GASTOS' 

def generar_pdf_corte(fecha_str, local_str, responsable_str, df_gastos, venta_efectivo, pago_pedidos, transferencias):
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
    
    efectivo_ingresado = venta_efectivo + pago_pedidos
    total_ingresos_brutos = efectivo_ingresado + transferencias
    neto_efectivo = efectivo_ingresado - total_gastos
    
    resumen_data = [
        ["RESUMEN FINANCIERO", "MONTO"],
        ["Venta de Pan (Efectivo)", f"Q {venta_efectivo:.2f}"],
        ["Pago de Pedidos (Efectivo)", f"Q {pago_pedidos:.2f}"],
        ["Transferencias / Fri / Depósitos", f"Q {transferencias:.2f}"],
        ["TOTAL INGRESOS BRUTOS", f"Q {total_ingresos_brutos:.2f}"],
        ["TOTAL GASTOS (En efectivo)", f"Q {total_gastos:.2f}"],
        ["EFECTIVO NETO A ENTREGAR", f"Q {neto_efectivo:.2f}"]
    ]
    
    t_resumen = Table(resumen_data, colWidths=[340, 200])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#EAECEE")),
        ('BACKGROUND', (0,6), (-1,6), colors.HexColor("#D4EFDF")),
        ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'),
        ('FONTNAME', (0,6), (-1,6), 'Helvetica-Bold'),
    ]))
    elements.append(t_resumen)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generar_pdf_reporte_mensual(f_inicio, f_fin, ingresos_df, gastos_cat_df, gastos_det_df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50"))
    subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style))
    elements.append(Paragraph(f"REPORTE GERENCIAL DE RESULTADOS: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}", subtitle_style))
    elements.append(Spacer(1, 20))
    
    v_efectivo = ingresos_df['efectivo'].sum() if not ingresos_df.empty else 0
    v_pedidos = ingresos_df['pedidos'].sum() if not ingresos_df.empty else 0
    v_trans = ingresos_df['transferencias'].sum() if not ingresos_df.empty else 0
    t_ingresos = v_efectivo + v_pedidos + v_trans
    t_gastos = gastos_cat_df['total'].sum() if not gastos_cat_df.empty else 0
    utilidad = t_ingresos - t_gastos
    
    resumen_data = [
        ["RESUMEN DE INGRESOS", "MONTO (Q)", "RESUMEN DE EGRESOS Y UTILIDAD", "MONTO (Q)"],
        ["Ventas Mostrador (Efec)", f"Q {v_efectivo:,.2f}", "Total Gastos Generales", f"Q {t_gastos:,.2f}"],
        ["Pago Pedidos (Efec)", f"Q {v_pedidos:,.2f}", "", ""],
        ["Transferencias / Fri", f"Q {v_trans:,.2f}", "UTILIDAD BRUTA DEL PERIODO", f"Q {utilidad:,.2f}"],
        ["TOTAL INGRESOS", f"Q {t_ingresos:,.2f}", "", ""]
    ]
    t_resumen = Table(resumen_data, colWidths=[140, 90, 190, 100])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#27AE60")), 
        ('BACKGROUND', (2,0), (3,0), colors.HexColor("#E74C3C")), 
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,-1), (1,-1), colors.HexColor("#D4EFDF")),
        ('FONTNAME', (0,-1), (1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (2,3), (3,3), colors.HexColor("#FADBD8")), 
        ('FONTNAME', (2,3), (3,3), 'Helvetica-Bold'),
    ]))
    elements.append(t_resumen)
    elements.append(Spacer(1, 20))
    
    if not gastos_cat_df.empty and t_gastos > 0:
        elements.append(Paragraph("<b>Distribución de Gastos por Categoría</b>", h2_style))
        d = Drawing(400, 160)
        pc = Pie()
        pc.x = 20
        pc.y = 10
        pc.width = 140
        pc.height = 140
        pc.data = gastos_cat_df['total'].tolist()
        
        labels = []
        for i, row in gastos_cat_df.iterrows():
            pct = (row['total'] / t_gastos) * 100
            labels.append(f"{row['categoria']} ({pct:.1f}%)")
        pc.labels = labels
        pc.sideLabels = 1 
        
        colores_hex = ["#3498DB", "#E74C3C", "#2ECC71", "#F1C40F", "#9B59B6", "#E67E22", "#1ABC9C", "#34495E", "#95A5A6"]
        for i in range(len(pc.data)):
            pc.slices[i].fillColor = colors.HexColor(colores_hex[i % len(colores_hex)])
            pc.slices[i].strokeColor = colors.white
            
        d.add(pc)
        elements.append(d)
        elements.append(Spacer(1, 10))
        
    gastos_data = [["CATEGORÍA DE GASTO", "MONTO GASTADO", "PORCENTAJE"]]
    for index, row in gastos_cat_df.iterrows():
        pct = (row['total'] / t_gastos) * 100 if t_gastos > 0 else 0
        gastos_data.append([str(row["categoria"]), f"Q {row['total']:,.2f}", f"{pct:.1f}%"])
        
    t_cat = Table(gastos_data, colWidths=[250, 150, 120])
    t_cat.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    elements.append(t_cat)
    elements.append(Spacer(1, 25))
    
    elements.append(Paragraph("<b>Anexo: Detalle Específico de Artículos/Servicios Pagados</b>", h2_style))
    det_data = [["CATEGORÍA", "DESCRIPCIÓN DEL GASTO", "TOTAL INVERTIDO"]]
    for index, row in gastos_det_df.iterrows():
        det_data.append([str(row["categoria"]), str(row["detalle"]).title(), f"Q {row['total']:,.2f}"])
        
    t_det = Table(det_data, colWidths=[150, 250, 120])
    t_det.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#BDC3C7")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    elements.append(t_det)
    
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
    # AGREGADA LA NUEVA OPCIÓN "📆 Comparativa Diaria"
    opcion_menu = st.radio(
        "Selecciona un módulo:",
        ["📝 Registro de Corte", "📅 Historial de Cortes", "📈 Estadísticas", "📆 Comparativa Diaria", "💳 Proveedores", "📊 Reporte PDF Mensual"],
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
    
    try:
        df_rutas = conn.query("SELECT id, nombre FROM rutas_locales", ttl=600)
        df_categorias = conn.query("SELECT id, nombre FROM categorias_gasto", ttl=600)
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
    st.caption("✨ **Escribe todo rápido usando el teclado (Tab y Enter).** Cuando termines, presiona el botón Mágico de abajo.")
    
    if 'reset_key' not in st.session_state:
        st.session_state.reset_key = 0

    if 'gastos_df' not in st.session_state:
        st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11): 
            st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]

    gastos_editados = st.data_editor(
        st.session_state.gastos_df,
        column_config={
            "Categoría": st.column_config.SelectboxColumn("Tipo de Gasto (Automático)", options=lista_categorias, required=False),
            "Detalle": st.column_config.TextColumn("Detalle del gasto"),
            "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")
        },
        num_rows="dynamic",
        use_container_width=True,
        key=f"tabla_gastos_{st.session_state.reset_key}" 
    )

    if st.button("✨ Autocompletar Categorías Vacías", type="secondary"):
        df_temp = gastos_editados.copy()
        hubo_cambios = False
        
        for i, row in df_temp.iterrows():
            detalle = str(row["Detalle"]).strip() if pd.notna(row["Detalle"]) else ""
            categoria = row["Categoría"]
            
            if detalle != "" and (pd.isna(categoria) or categoria is None or str(categoria).strip() == ""):
                df_temp.at[i, "Categoría"] = autocompletar_categoria(detalle)
                hubo_cambios = True
        
        if hubo_cambios:
            st.session_state.gastos_df = df_temp
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 💰 Resumen de Ingresos")
    col_ing1, col_ing2, col_ing3 = st.columns(3)
    
    venta_mostrador = col_ing1.number_input("🍞 Venta (Efectivo)", min_value=0.00, step=50.00, key=f"venta_input_{st.session_state.reset_key}")
    pago_pedidos = col_ing2.number_input("🎂 Pedidos (Efectivo)", min_value=0.00, step=50.00, key=f"pedidos_input_{st.session_state.reset_key}")
    transferencias = col_ing3.number_input("📱 Transferencias (Fri/Depósitos)", min_value=0.00, step=50.00, key=f"trans_input_{st.session_state.reset_key}")
    
    total_ingresos_efectivo = venta_mostrador + pago_pedidos
    total_ingresos_bruto = total_ingresos_efectivo + transferencias
    total_gastos_calc = gastos_editados["Monto (Q)"].sum()
    efectivo_a_entregar = total_ingresos_efectivo - total_gastos_calc
    
    st.markdown("---")
    st.markdown("### 📊 Cuadre Final")
    col_tot1, col_tot2, col_tot_bruto, col_tot3, col_tot4 = st.columns(5)
    
    col_tot1.metric("💵 Ingresos (Efectivo)", f"Q {total_ingresos_efectivo:.2f}")
    col_tot2.metric("📱 Fri / Depósitos", f"Q {transferencias:.2f}")
    col_tot_bruto.metric("💰 Total Ingresos", f"Q {total_ingresos_bruto:.2f}")
    col_tot3.metric("📉 Gastos (Efectivo)", f"Q {total_gastos_calc:.2f}")
    col_tot4.metric("⚖️ Efectivo a Entregar", f"Q {efectivo_a_entregar:.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        btn_guardar = st.button("💾 Guardar Corte Completo", type="primary", use_container_width=True)
    with col_btn2:
        btn_limpiar = st.button("🧹 Limpiar / Nuevo Corte", type="secondary", use_container_width=True)

    if btn_limpiar:
        df_limpio = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11):
            df_limpio.loc[len(df_limpio)] = [None, "", 0.0]
        st.session_state.gastos_df = df_limpio
        st.session_state.reset_key += 1
        if 'pdf_generado' in st.session_state:
            del st.session_state['pdf_generado']
            del st.session_state['pdf_nombre']
        st.rerun()

    if btn_guardar:
        if total_ingresos_bruto > 0 or total_gastos_calc > 0:
            corte_id = obtener_o_crear_corte(fecha_corte)
            ruta_id = df_rutas.loc[df_rutas['nombre'] == local_ruta, 'id'].values[0]
            
            with conn.session as s:
                if total_ingresos_bruto > 0:
                    s.execute(text("INSERT INTO ingresos (corte_id, ruta_id, venta_total, credito_pagado, transferencias) VALUES (:c, :r, :v, :cp, :t)"), 
                              {"c": corte_id, "r": int(ruta_id), "v": venta_mostrador, "cp": pago_pedidos, "t": transferencias})
                
                for index, row in gastos_editados.iterrows():
                    monto = row["Monto (Q)"]
                    if monto > 0:
                        detalle = str(row["Detalle"]).strip() if pd.notna(row["Detalle"]) else "Gasto sin detalle"
                        categoria = row["Categoría"]
                        
                        if pd.isna(categoria) or categoria is None or str(categoria).strip() == "":
                            categoria = autocompletar_categoria(detalle)
                            gastos_editados.at[index, "Categoría"] = categoria
                            
                        if categoria in lista_categorias:
                            cat_id = df_categorias.loc[df_categorias['nombre'] == categoria, 'id'].values[0]
                            s.execute(text("INSERT INTO gastos (corte_id, categoria_id, detalle, monto) VALUES (:c, :cat, :d, :m)"), 
                                      {"c": corte_id, "cat": int(cat_id), "d": detalle, "m": monto})
                s.commit()
            
            st.success("✅ ¡Corte guardado y listo para imprimir!")
            st.balloons()
            
            pdf_buffer = generar_pdf_corte(fecha_corte.strftime('%d/%m/%Y'), local_ruta, responsable, gastos_editados, venta_mostrador, pago_pedidos, transferencias)
            st.session_state['pdf_generado'] = pdf_buffer
            st.session_state['pdf_nombre'] = f"Corte_{fecha_corte.strftime('%d-%m-%Y')}.pdf"
            
            df_limpio = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
            for _ in range(11):
                df_limpio.loc[len(df_limpio)] = [None, "", 0.0]
            st.session_state.gastos_df = df_limpio
            st.session_state.reset_key += 1
            st.rerun()
            
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
            
            ingresos_hist = conn.query(f"SELECT r.nombre as Ruta, i.venta_total as Venta_Mostrador, i.credito_pagado as Pedidos, i.transferencias as transferencias FROM ingresos i JOIN rutas_locales r ON i.ruta_id = r.id WHERE i.corte_id = {corte_id}", ttl=0)
            gastos_hist = conn.query(f"SELECT c.nombre as Categoria, g.detalle as Detalle, g.monto as Monto FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id WHERE g.corte_id = {corte_id}", ttl=0)
            
            sum_venta = ingresos_hist['venta_mostrador'].sum() if not ingresos_hist.empty else 0.0
            sum_pedidos = ingresos_hist['pedidos'].sum() if not ingresos_hist.empty else 0.0
            sum_transferencias = ingresos_hist['transferencias'].sum() if not ingresos_hist.empty and 'transferencias' in ingresos_hist.columns else 0.0
            
            sum_efectivo = sum_venta + sum_pedidos
            total_ingresos_bruto_hist = sum_efectivo + sum_transferencias
            sum_gastos = gastos_hist['monto'].sum() if not gastos_hist.empty else 0.0
            neto_efectivo = sum_efectivo - sum_gastos
            
            st.markdown(f"### Resumen del {fecha_consulta.strftime('%d/%m/%Y')}")
            col_h1, col_h2, col_h_bruto, col_h3, col_h4 = st.columns(5)
            col_h1.metric("💵 Ingresos Efectivo", f"Q {sum_efectivo:.2f}")
            col_h2.metric("📱 Transferencias/Fri", f"Q {sum_transferencias:.2f}")
            col_h_bruto.metric("💰 Total Ingresos", f"Q {total_ingresos_bruto_hist:.2f}")
            col_h3.metric("📉 Gastos", f"Q {sum_gastos:.2f}")
            col_h4.metric("⚖️ Efectivo Entregado", f"Q {neto_efectivo:.2f}")
            
            st.markdown("---")
            ruta_nombre = ingresos_hist.iloc[0]['ruta'] if not ingresos_hist.empty else "LOCAL MERCADO"
            df_para_pdf = pd.DataFrame({
                "Categoría": gastos_hist['categoria'] if not gastos_hist.empty else [],
                "Detalle": gastos_hist['detalle'] if not gastos_hist.empty else [],
                "Monto (Q)": gastos_hist['monto'] if not gastos_hist.empty else []
            })
            
            pdf_historico = generar_pdf_corte(fecha_consulta.strftime('%d/%m/%Y'), ruta_nombre, "Histórico", df_para_pdf, sum_venta, sum_pedidos, sum_transferencias)
            st.download_button(
                label=f"📥 Descargar PDF del {fecha_consulta.strftime('%d/%m/%Y')} para Imprimir",
                data=pdf_historico, file_name=f"Corte_{fecha_consulta.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
            
            st.markdown("---")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.subheader("💰 Desglose de Ingresos")
                if not ingresos_hist.empty: st.dataframe(ingresos_hist, use_container_width=True, hide_index=True)
                else: st.info("No se registraron ingresos este día.")
            with col_t2:
                st.subheader("💸 Desglose de Gastos")
                if not gastos_hist.empty: st.dataframe(gastos_hist, use_container_width=True, hide_index=True)
                else: st.info("No se registraron gastos este día.")
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
            FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id JOIN cortes_diarios cd ON g.corte_id = cd.id
            WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio
            GROUP BY c.nombre
        """
        gastos_totales = conn.query(query_gastos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        
        query_ingresos = """
            SELECT SUM(i.venta_total + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as total_ingresos
            FROM ingresos i JOIN cortes_diarios cd ON i.corte_id = cd.id
            WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio
        """
        ingresos_totales = conn.query(query_ingresos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        
        total_g = gastos_totales['total'].sum() if not gastos_totales.empty else 0.0
        total_i = float(ingresos_totales.iloc[0]['total_ingresos']) if not ingresos_totales.empty and pd.notna(ingresos_totales.iloc[0]['total_ingresos']) else 0.0
        utilidad = total_i - total_g
        
        st.markdown("---")
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric(f"💵 Ingresos Brutos ({mes_seleccionado})", f"Q {total_i:.2f}")
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
# MÓDULO 3.5: COMPARATIVA DIARIA (NUEVO)
# ------------------------------------------
elif opcion_menu == "📆 Comparativa Diaria":
    st.title("📆 Comparativa de Ingresos vs Gastos por Día")
    st.write("Mira cuánto entró y cuánto salió exactamente cada día en el rango que elijas.")
    
    hoy = get_fecha_guate()
    primer_dia_mes = hoy.replace(day=1)
    
    col_d1, col_d2 = st.columns(2)
    fecha_inicio_comp = col_d1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY")
    fecha_fin_comp = col_d2.date_input("Hasta:", hoy, format="DD/MM/YYYY")
    
    if st.button("🔍 Consultar Días", type="primary"):
        with st.spinner("Cargando los datos día por día..."):
            try:
                # 1. Traer Ingresos por día
                q_ing = """
                    SELECT cd.fecha, 
                           SUM(COALESCE(i.venta_total, 0) + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as ingresos
                    FROM cortes_diarios cd
                    LEFT JOIN ingresos i ON cd.id = i.corte_id
                    WHERE cd.fecha BETWEEN :inicio AND :fin
                    GROUP BY cd.fecha
                """
                df_ing = conn.query(q_ing, params={"inicio": fecha_inicio_comp, "fin": fecha_fin_comp}, ttl=0)
                
                # 2. Traer Gastos por día
                q_gas = """
                    SELECT cd.fecha, SUM(COALESCE(g.monto, 0)) as gastos
                    FROM cortes_diarios cd
                    LEFT JOIN gastos g ON cd.id = g.corte_id
                    WHERE cd.fecha BETWEEN :inicio AND :fin
                    GROUP BY cd.fecha
                """
                df_gas = conn.query(q_gas, params={"inicio": fecha_inicio_comp, "fin": fecha_fin_comp}, ttl=0)
                
                if df_ing.empty and df_gas.empty:
                    st.warning("No hay registros en esas fechas.")
                else:
                    # Unir las dos tablas para tener todo en una sola vista
                    df_resumen = pd.merge(df_ing, df_gas, on='fecha', how='outer').fillna(0)
                    df_resumen['fecha'] = pd.to_datetime(df_resumen['fecha']).dt.date
                    df_resumen = df_resumen.sort_values('fecha')
                    df_resumen['utilidad'] = df_resumen['ingresos'] - df_resumen['gastos']
                    
                    # Calcular sumas totales
                    t_ing = df_resumen['ingresos'].sum()
                    t_gas = df_resumen['gastos'].sum()
                    t_uti = df_resumen['utilidad'].sum()
                    
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("💰 Total Ingresos del Rango", f"Q {t_ing:,.2f}")
                    c2.metric("📉 Total Gastos del Rango", f"Q {t_gas:,.2f}")
                    c3.metric("⚖️ Utilidad del Rango", f"Q {t_uti:,.2f}")
                    st.markdown("---")
                    
                    # Gráfica de barras comparativa
                    st.subheader("📊 Gráfica de Movimientos Diarios")
                    df_graf = df_resumen[['fecha', 'ingresos', 'gastos']].melt(id_vars='fecha', var_name='Tipo', value_name='Monto')
                    fig = px.bar(
                        df_graf, 
                        x='fecha', 
                        y='Monto', 
                        color='Tipo', 
                        barmode='group', 
                        color_discrete_map={'ingresos': '#27AE60', 'gastos': '#E74C3C'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Tabla final
                    st.subheader("📋 Detalle de cada día")
                    st.dataframe(
                        df_resumen,
                        column_config={
                            "fecha": st.column_config.DateColumn("Fecha del Corte", format="DD/MM/YYYY"),
                            "ingresos": st.column_config.NumberColumn("Total Ingresos (Efec + Fri)", format="Q %.2f"),
                            "gastos": st.column_config.NumberColumn("Total Gastos", format="Q %.2f"),
                            "utilidad": st.column_config.NumberColumn("Utilidad Neta", format="Q %.2f")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
            except Exception as e:
                st.error(f"Error al cargar la comparativa: {e}")

# ------------------------------------------
# MÓDULO 4: PROVEEDORES
# ------------------------------------------
elif opcion_menu == "💳 Proveedores":
    st.title("💳 Control de Créditos y Proveedores")
    try:
        tab_prov1, tab_prov2, tab_prov3 = st.tabs(["📋 Gestionar Proveedores", "➕ Registrar Deuda", "🚨 Deudas Activas"])
        with tab_prov1:
            with st.expander("➕ Agregar un Nuevo Proveedor"):
                with st.form("form_nuevo_proveedor", clear_on_submit=True):
                    nuevo_nombre = st.text_input("Nombre del Proveedor")
                    nuevo_producto = st.text_input("Producto o Servicio")
                    if st.form_submit_button("Guardar Proveedor") and nuevo_nombre:
                        with conn.session as s:
                            s.execute(text("INSERT INTO proveedores (nombre, producto_servicio) VALUES (:n, :p)"), {"n": nuevo_nombre, "p": nuevo_producto})
                            s.commit()
                        st.success(f"✅ ¡Proveedor agregado!")
                        st.rerun()
            df_prov_edit = conn.query("SELECT id, nombre, producto_servicio FROM proveedores ORDER BY id", ttl=0)
            if not df_prov_edit.empty:
                proveedores_editados = st.data_editor(df_prov_edit, column_config={"id": st.column_config.NumberColumn("ID", disabled=True)}, hide_index=True, use_container_width=True)
                if st.button("💾 Guardar Cambios en Proveedores", type="primary"):
                    with conn.session as s:
                        for index, row in proveedores_editados.iterrows():
                            s.execute(text("UPDATE proveedores SET nombre = :nombre, producto_servicio = :prod WHERE id = :id"), {"nombre": row["nombre"], "prod": row["producto_servicio"], "id": int(row["id"])})
                        s.commit()
                    st.success("✅ ¡Proveedores actualizados!")
                    st.rerun()
                st.markdown("### 🗑️ Eliminar Proveedor")
                prov_a_borrar = st.selectbox("Selecciona para eliminar:", df_prov_edit['nombre'])
                if st.button("Eliminar Proveedor Seleccionado"):
                    id_borrar = df_prov_edit.loc[df_prov_edit['nombre'] == prov_a_borrar, 'id'].values[0]
                    with conn.session as s:
                        s.execute(text("DELETE FROM cuentas_por_pagar WHERE proveedor_id = :id"), {"id": int(id_borrar)})
                        s.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": int(id_borrar)})
                        s.commit()
                    st.success("🗑️ Proveedor eliminado.")
                    st.rerun()
        with tab_prov2:
            df_proveedores = conn.query("SELECT id, nombre FROM proveedores ORDER BY nombre", ttl=0)
            if not df_proveedores.empty:
                with st.form("form_credito", clear_on_submit=True):
                    prov = st.selectbox("Proveedor", df_proveedores['nombre'])
                    num_factura = st.text_input("📄 No. de Factura/Doc")
                    monto_credito = st.number_input("Monto total (Q)", min_value=0.00, step=100.00)
                    fecha_vencimiento = st.date_input("¿Cuándo toca pagar?", get_fecha_guate(), format="DD/MM/YYYY")
                    if st.form_submit_button("Guardar Deuda"):
                        prov_id = df_proveedores.loc[df_proveedores['nombre'] == prov, 'id'].values[0]
                        with conn.session as s:
                            s.execute(text("INSERT INTO cuentas_por_pagar (proveedor_id, num_documento, fecha_compra, fecha_vencimiento, monto_total, saldo_pendiente) VALUES (:p, :doc, :f_compra, :f_vence, :monto, :saldo)"), 
                                      {"p": int(prov_id), "doc": num_factura, "f_compra": get_fecha_guate(), "f_vence": fecha_vencimiento, "monto": monto_credito, "saldo": monto_credito})
                            s.commit()
                        st.success("✅ Deuda registrada.")
        with tab_prov3:
            deudas_activas = conn.query("SELECT c.id, p.nombre as proveedor, c.num_documento as documento, p.producto_servicio as insumo, c.fecha_vencimiento as vencimiento, c.saldo_pendiente as saldo FROM cuentas_por_pagar c JOIN proveedores p ON c.proveedor_id = p.id WHERE c.estado = 'Pendiente'", ttl=0)
            if not deudas_activas.empty:
                hoy = get_fecha_guate()
                deudas_activas['vencimiento'] = pd.to_datetime(deudas_activas['vencimiento']).dt.date
                def asignar_semaforo(fecha_vence):
                    if pd.isnull(fecha_vence): return "⚪ Sin Fecha"
                    dias_restantes = (fecha_vence - hoy).days
                    if dias_restantes < 0: return "🔴 Vencido"
                    elif 0 <= dias_restantes <= 3: return "🟡 Próximo"
                    else: return "🟢 A tiempo"
                deudas_activas.insert(0, 'Estado', deudas_activas['vencimiento'].apply(asignar_semaforo))
                st.dataframe(deudas_activas, column_config={"vencimiento": st.column_config.DateColumn("Vencimiento", format="DD/MM/YYYY"), "saldo": st.column_config.NumberColumn("Saldo Pendiente", format="Q %.2f")}, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error: {e}")

# ------------------------------------------
# MÓDULO 5: REPORTE PDF MENSUAL
# ------------------------------------------
elif opcion_menu == "📊 Reporte PDF Mensual":
    st.title("📊 Generador de Reporte Financiero (PDF)")
    st.write("Selecciona las fechas para crear un reporte gerencial con gráfica de pastel y resumen de gastos consolidados.")
    
    hoy = get_fecha_guate()
    primer_dia_mes = hoy.replace(day=1)
    
    col_f1, col_f2 = st.columns(2)
    fecha_inicio = col_f1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY")
    fecha_fin = col_f2.date_input("Hasta:", hoy, format="DD/MM/YYYY")
    
    if st.button("📑 Generar Reporte PDF", type="primary"):
        with st.spinner("Calculando agrupaciones y dibujando gráficas..."):
            try:
                query_ing = """
                    SELECT SUM(i.venta_total) as efectivo, SUM(COALESCE(i.credito_pagado, 0)) as pedidos, SUM(COALESCE(i.transferencias, 0)) as transferencias
                    FROM ingresos i
                    JOIN cortes_diarios cd ON i.corte_id = cd.id
                    WHERE cd.fecha BETWEEN :inicio AND :fin
                """
                ingresos_df = conn.query(query_ing, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                
                query_cat = """
                    SELECT c.nombre as categoria, SUM(g.monto) as total
                    FROM gastos g
                    JOIN categorias_gasto c ON g.categoria_id = c.id
                    JOIN cortes_diarios cd ON g.corte_id = cd.id
                    WHERE cd.fecha BETWEEN :inicio AND :fin
                    GROUP BY c.nombre
                    ORDER BY total DESC
                """
                gastos_cat_df = conn.query(query_cat, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                
                query_det = """
                    SELECT c.nombre as categoria, LOWER(g.detalle) as detalle, SUM(g.monto) as total
                    FROM gastos g
                    JOIN categorias_gasto c ON g.categoria_id = c.id
                    JOIN cortes_diarios cd ON g.corte_id = cd.id
                    WHERE cd.fecha BETWEEN :inicio AND :fin
                    GROUP BY c.nombre, LOWER(g.detalle)
                    ORDER BY c.nombre, total DESC
                """
                gastos_det_df = conn.query(query_det, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                
                if (not ingresos_df.empty and ingresos_df['efectivo'].sum() > 0) or not gastos_cat_df.empty:
                    buffer_pdf = generar_pdf_reporte_mensual(fecha_inicio, fecha_fin, ingresos_df, gastos_cat_df, gastos_det_df)
                    st.success("✅ ¡Tu Reporte Gerencial ha sido generado con éxito!")
                    st.download_button(
                        label="📥 Descargar Reporte PDF",
                        data=buffer_pdf,
                        file_name=f"Reporte_Panaderia_{fecha_inicio.strftime('%d-%m-%Y')}_al_{fecha_fin.strftime('%d-%m-%Y')}.pdf",
                        mime="application/pdf",
                        type="secondary",
                        use_container_width=True
                    )
                else:
                    st.warning(f"⚠️ No se encontraron registros de ventas ni gastos entre el {fecha_inicio.strftime('%d/%m/%Y')} y el {fecha_fin.strftime('%d/%m/%Y')}.")
                    
            except Exception as e:
                st.error(f"Error al generar el reporte: {e}")
