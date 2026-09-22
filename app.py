import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import pytz
import plotly.express as px
import os
import zipfile
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
import io
import re
import xml.etree.ElementTree as ET 
import streamlit.components.v1 as components 

# ==========================================
# 1. CONFIGURACIÓN PRINCIPAL Y ESCUDO DE TECLADO
# ==========================================
st.set_page_config(page_title="Panadería Judith - Sistema", page_icon="🍞", layout="wide")

components.html(
    """<script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if ((e.key.toLowerCase() === 'c' || e.key.toLowerCase() === 'r') && e.target.nodeName !== 'INPUT' && e.target.nodeName !== 'TEXTAREA') {
            e.stopPropagation(); e.preventDefault();
        }
    }, true);
    </script>""", height=0, width=0
)

def get_fecha_guate():
    zona_guate = pytz.timezone('America/Guatemala')
    return datetime.now(zona_guate).date()

def numero_a_letras(numero):
    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    dieces = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    veintes = ["VEINTE", "VEINTIUN", "VEINTIDOS", "VEINTITRES", "VEINTICUATRO", "VEINTICINCO", "VEINTISEIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
    def convertir_grupo(n):
        c = n // 100; r = n % 100
        if c == 1 and r == 0: return "CIEN"
        out = centenas[c] + " " if c > 0 else ""
        d = r // 10; u = r % 10
        if d == 1: out += dieces[u]
        elif d == 2: out += veintes[u]
        elif d > 2: out += decenas[d] + (" Y " + unidades[u] if u > 0 else "")
        else: out += unidades[u] if u > 0 else ""
        return out.strip()
    entero = int(numero); decimal = int(round((numero - entero) * 100))
    if entero == 0: letras = "CERO"
    elif entero < 1000: letras = convertir_grupo(entero)
    else:
        miles = entero // 1000; resto = entero % 1000
        letras = ("UN MIL" if miles == 1 else convertir_grupo(miles) + " MIL") + " " + convertir_grupo(resto)
    return f"{letras.strip()} CON {decimal:02d}/100"

def get_logo_path():
    for ext in ['png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG']:
        if os.path.exists(f"logo.{ext}"):
            return f"logo.{ext}"
    return None

# ==========================================
# 2. SISTEMA DE SEGURIDAD (LOGIN DINÁMICO)
# ==========================================
try:
    conn = st.connection("postgresql", type="sql", pool_pre_ping=True)
except Exception as e:
    st.error("🔴 Error de conexión con la base de datos."); st.stop()

if 'logueado' not in st.session_state: st.session_state['logueado'] = False

if not st.session_state['logueado']:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        logo_file = get_logo_path()
        if logo_file:
            st.image(logo_file, use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center;'>🍞 Panadería Judith</h1>", unsafe_allow_html=True)
            
        st.markdown("<h3 style='text-align: center; color: gray;'>Acceso Seguro</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            usuario = st.text_input("👤 Usuario").lower()
            password = st.text_input("🔒 Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                login_valido = False
                try:
                    res = conn.query(f"SELECT * FROM usuarios_app WHERE usuario='{usuario}' AND password='{password}'", ttl=0)
                    if not res.empty: login_valido = True
                except Exception:
                    fallback = {"roberto": "esquipulas123", "admin": "admin2026", "jefa": "pana2027"}
                    if fallback.get(usuario) == password: login_valido = True
                if login_valido:
                    st.session_state['logueado'] = True; st.session_state['usuario'] = usuario; st.rerun()
                else: st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

# ==========================================
# 3. CONEXIÓN A BASE DE DATOS Y FUNCIONES
# ==========================================
def obtener_o_crear_corte(fecha_corte):
    with conn.session as s:
        result = s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()
        if result: return result[0]
        else:
            s.execute(text("INSERT INTO cortes_diarios (fecha) VALUES (:fecha)"), {"fecha": fecha_corte}); s.commit()
            return s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()[0]

def autocompletar_categoria(d):
    d = str(d).lower()
    if 'pasta' in d or 'pollo' in d: return 'COMPRAS DE PASTA DE POLLO'
    if 'bolsa de agua' in d or 'agua' in d or 'gaseosa' in d or 'coca' in d or 'bebida' in d or 'tostada' in d or 'marquesote' in d: return 'OTRAS MERCADERIAS'
    if 'luz' in d or 'internet' in d or 'telefono' in d or 'basura' in d or 'alquiler' in d or 'impuesto' in d or 'gas ' in d or 'propano' in d: return 'OTROS GASTOS' 
    if re.search(r'\b(harina|azucar|azúcar|manteca|levadura|leche|huevo|huevos|sal)\b', d): return 'MATERIA PRIMA'
    if re.search(r'\b(bono|sueldo|sueldos|salario|salarios|anticipo|almuerzo|planilla|turno|quincena|panadero)\b', d): return 'SUELDOS Y SALARIOS'
    if re.search(r'\b(gasolina|moto|vehiculo|repuesto|llanta|aceite|mecanico|pinchazo)\b', d): return 'REPUESTOS Y REPARACIONES'
    if re.search(r'\b(bolsa|bandeja|calcomania|papel|limpieza|empaque|escoba|jabon|cloro)\b', d): return 'UTILES Y EMPAQUES'
    if re.search(r'\b(prestamo|tarjeta|interes|abono|banco|cuota)\b', d): return 'PRESTAMOS E INTERESES'
    return 'OTROS GASTOS' 

def add_pdf_header(elements, title_text, subtitle_text=""):
    logo_file = get_logo_path()
    if logo_file:
        try:
            img = RLImage(logo_file, width=120, height=120, kind='proportional')
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 10))
        except: pass

    title_style = ParagraphStyle('Title', fontName="Helvetica-Bold", fontSize=18, alignment=1, textColor=colors.HexColor("#2C3E50"), spaceAfter=10, leading=22)
    sub_style = ParagraphStyle('Sub', fontName="Helvetica", fontSize=12, alignment=1, textColor=colors.gray, spaceAfter=20, leading=16)
    
    elements.append(Paragraph(title_text, title_style))
    if subtitle_text:
        elements.append(Paragraph(subtitle_text, sub_style))

# -- FUNCIONES PDF DE REPORTES --
def generar_pdf_corte(fecha_str, local_str, responsable_str, df_gastos, venta_efectivo, pago_pedidos, transferencias):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", "INTEGRACIÓN DE INGRESOS Y EGRESOS - CORTE DE CAJA")
    
    bold_style = ParagraphStyle('BoldStyle', fontName="Helvetica-Bold", fontSize=10)
    info_data = [[Paragraph(f"<b>Fecha:</b> {fecha_str}", bold_style), Paragraph(f"<b>Local / Ruta:</b> {local_str}", bold_style), Paragraph(f"<b>Responsable:</b> {responsable_str}", bold_style)]]; info_table = Table(info_data, colWidths=[150, 200, 190]); info_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAFAF1")), ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#27AE60")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 6)])); elements.append(info_table); elements.append(Spacer(1, 15))
    gastos_table_data = [["TIPO DE GASTO", "DETALLE", "TOTAL (Q)"]]; total_gastos = 0.0
    for index, row in df_gastos.iterrows():
        if row["Monto (Q)"] > 0:
            categoria_mostrar = row["Categoría"] if pd.notna(row["Categoría"]) else "OTROS GASTOS"
            gastos_table_data.append([str(categoria_mostrar), str(row["Detalle"]), f"Q {row['Monto (Q)']:.2f}"]); total_gastos += float(row["Monto (Q)"])
    while len(gastos_table_data) < 10: gastos_table_data.append(["", "", ""])
    gastos_table_data.append(["", "TOTAL GASTOS", f"Q {total_gastos:.2f}"])
    t_gastos = Table(gastos_table_data, colWidths=[180, 240, 120]); t_gastos.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#27AE60")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('ALIGN', (2,0), (2,-1), 'RIGHT'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 6), ('GRID', (0,0), (-1,-2), 0.5, colors.grey), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')])); elements.append(t_gastos); elements.append(Spacer(1, 15))
    efectivo_ingresado = venta_efectivo + pago_pedidos; total_ingresos_brutos = efectivo_ingresado + transferencias; neto_efectivo = efectivo_ingresado - total_gastos
    resumen_data = [["RESUMEN FINANCIERO", "MONTO"], ["Venta de Pan (Efectivo)", f"Q {venta_efectivo:.2f}"], ["Pago de Pedidos (Efectivo)", f"Q {pago_pedidos:.2f}"], ["Transferencias / Fri / Depósitos", f"Q {transferencias:.2f}"], ["TOTAL INGRESOS BRUTOS", f"Q {total_ingresos_brutos:.2f}"], ["TOTAL GASTOS (En efectivo)", f"Q {total_gastos:.2f}"], ["EFECTIVO NETO A ENTREGAR", f"Q {neto_efectivo:.2f}"]]
    t_resumen = Table(resumen_data, colWidths=[340, 200]); t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#EAECEE")), ('BACKGROUND', (0,6), (-1,6), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'), ('FONTNAME', (0,6), (-1,6), 'Helvetica-Bold')])); elements.append(t_resumen); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_reporte_mensual(f_inicio, f_fin, ingresos_df, gastos_cat_df, gastos_det_df, v_abonos_jeny, v_otras_rutas, v_ventas_extra):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", f"REPORTE GERENCIAL DE RESULTADOS: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}")
    
    v_efectivo = ingresos_df['efectivo'].sum() if not ingresos_df.empty else 0; v_pedidos_trans = (ingresos_df['pedidos'].sum() + ingresos_df['transferencias'].sum()) if not ingresos_df.empty else 0
    t_ingresos = v_efectivo + v_pedidos_trans + v_abonos_jeny + v_otras_rutas + v_ventas_extra; t_gastos = gastos_cat_df['total'].sum() if not gastos_cat_df.empty else 0; utilidad = t_ingresos - t_gastos
    resumen_data = [
        ["RESUMEN DE INGRESOS", "MONTO (Q)", "RESUMEN DE EGRESOS Y UTILIDAD", "MONTO (Q)"],
        ["Ventas Mostrador (Efectivo)", f"Q {v_efectivo:,.2f}", "Total Gastos Generales", f"Q {t_gastos:,.2f}"],
        ["Transferencias / Pedidos", f"Q {v_pedidos_trans:,.2f}", "", ""],
        ["Abonos Ruta Oasis (Jeny)", f"Q {v_abonos_jeny:,.2f}", "UTILIDAD BRUTA DEL PERIODO", f"Q {utilidad:,.2f}"],
        ["Rutas Contado (Shell/XML)", f"Q {v_otras_rutas:,.2f}", "", ""],
        ["Ventas Extra / Mayoristas", f"Q {v_ventas_extra:,.2f}", "", ""],
        ["TOTAL INGRESOS", f"Q {t_ingresos:,.2f}", "", ""]
    ]
    t_resumen = Table(resumen_data, colWidths=[140, 90, 190, 100]); t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (1,0), colors.HexColor("#27AE60")), ('BACKGROUND', (2,0), (3,0), colors.HexColor("#E74C3C")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('ALIGN', (3,0), (3,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,-1), (1,-1), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,-1), (1,-1), 'Helvetica-Bold'), ('BACKGROUND', (2,3), (3,3), colors.HexColor("#FADBD8")), ('FONTNAME', (2,3), (3,3), 'Helvetica-Bold')])); elements.append(t_resumen); elements.append(Spacer(1, 20))
    if not gastos_cat_df.empty and t_gastos > 0:
        h2_style = ParagraphStyle('H2', fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
        elements.append(Paragraph("<b>Distribución de Gastos por Categoría</b>", h2_style)); d = Drawing(400, 160); pc = Pie(); pc.x = 20; pc.y = 10; pc.width = 140; pc.height = 140; pc.data = gastos_cat_df['total'].tolist(); pc.labels = [f"{row['categoria']} ({(row['total']/t_gastos)*100:.1f}%)" for _, row in gastos_cat_df.iterrows()]; pc.sideLabels = 1; colores_hex = ["#3498DB", "#E74C3C", "#2ECC71", "#F1C40F", "#9B59B6", "#E67E22", "#1ABC9C", "#34495E", "#95A5A6"]
        for i in range(len(pc.data)): pc.slices[i].fillColor = colors.HexColor(colores_hex[i % len(colores_hex)]); pc.slices[i].strokeColor = colors.white
        d.add(pc); elements.append(d); elements.append(Spacer(1, 10))
    gastos_data = [["CATEGORÍA DE GASTO", "MONTO GASTADO", "PORCENTAJE"]]
    for index, row in gastos_cat_df.iterrows(): pct = (row['total'] / t_gastos) * 100 if t_gastos > 0 else 0; gastos_data.append([str(row["categoria"]), f"Q {row['total']:,.2f}", f"{pct:.1f}%"])
    t_cat = Table(gastos_data, colWidths=[250, 150, 120]); t_cat.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_cat); elements.append(Spacer(1, 25))
    h2_style = ParagraphStyle('H2', fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>Anexo: Detalle Específico de Artículos/Servicios Pagados</b>", h2_style)); det_data = [["CATEGORÍA", "DESCRIPCIÓN DEL GASTO", "TOTAL INVERTIDO"]]
    for index, row in gastos_det_df.iterrows(): det_data.append([str(row["categoria"]), str(row["detalle"]).title(), f"Q {row['total']:,.2f}"])
    t_det = Table(det_data, colWidths=[150, 250, 120]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#BDC3C7")), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (2,0), (2,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), ('FONTSIZE', (0,0), (-1,-1), 9)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_comparativa_diaria(f_inicio, f_fin, df_resumen, t_ing, t_gas, t_uti):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", f"REPORTE COMPARATIVO DIARIO (INCLUYE RUTAS, ABONOS Y VENTAS EXTRA): {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}")
    
    resumen_data = [["TOTAL INGRESOS GLOBAL", "TOTAL GASTOS", "UTILIDAD NETA"], [f"Q {t_ing:,.2f}", f"Q {t_gas:,.2f}", f"Q {t_uti:,.2f}"]]; t_resumen = Table(resumen_data, colWidths=[150, 150, 150]); t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_resumen); elements.append(Spacer(1, 20))
    h2_style = ParagraphStyle('H2', fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>Gráfica Comparativa: Ingresos vs Gastos</b>", h2_style)); d = Drawing(480, 200); bc = VerticalBarChart(); bc.x = 40; bc.y = 40; bc.height = 140; bc.width = 420; bc.data = [df_resumen['ingresos'].tolist(), df_resumen['gastos'].tolist()]; bc.strokeColor = colors.white; bc.valueAxis.valueMin = 0; bc.categoryAxis.categoryNames = [fecha.strftime('%d/%m') for fecha in df_resumen['fecha']]; bc.categoryAxis.labels.angle = 45; bc.categoryAxis.labels.dy = -10; bc.categoryAxis.labels.fontSize = 8; bc.bars[0].fillColor = colors.HexColor("#27AE60") ; bc.bars[1].fillColor = colors.HexColor("#E74C3C") 
    leg = Legend(); leg.x = 350; leg.y = 180; leg.alignment = 'right'; leg.colorNamePairs = [(colors.HexColor("#27AE60"), 'Total Ingresos'), (colors.HexColor("#E74C3C"), 'Total Gastos')]; leg.fontSize = 8; leg.boxAnchor = 'nw'; d.add(bc); d.add(leg); elements.append(d); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Detalle Diario de Movimientos</b>", h2_style)); det_data = [["FECHA", "TOTAL INGRESOS", "TOTAL GASTOS", "UTILIDAD NETA"]]
    for index, row in df_resumen.iterrows(): det_data.append([row['fecha'].strftime('%d/%m/%Y'), f"Q {row['ingresos']:,.2f}", f"Q {row['gastos']:,.2f}", f"Q {row['utilidad']:,.2f}"])
    t_det = Table(det_data, colWidths=[120, 120, 120, 120]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_dias_estrella(f_inicio, f_fin, df_agrupado, mejor_dia, peor_dia, prom_gral, dia_record):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", f"REPORTE DE DÍAS ESTRELLA: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}")
    
    metricas_data = [["MEJOR DÍA", "DÍA MÁS FLOJO", "PROMEDIO DIARIO", "DÍA RÉCORD"], [str(mejor_dia), str(peor_dia), f"Q {prom_gral:,.2f}", f"{dia_record['fecha'].strftime('%d/%m/%Y')} (Q {dia_record['ingresos']:,.2f})"]]; t_metricas = Table(metricas_data, colWidths=[120, 120, 130, 150]); t_metricas.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_metricas); elements.append(Spacer(1, 20))
    h2_style = ParagraphStyle('H2', fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>Gráfica de Rendimiento por Día de la Semana</b>", h2_style)); d = Drawing(480, 200); bc = VerticalBarChart(); bc.x = 40; bc.y = 40; bc.height = 140; bc.width = 420; bc.data = [df_agrupado['promedio_ventas'].tolist()]; bc.strokeColor = colors.white; bc.valueAxis.valueMin = 0; bc.categoryAxis.categoryNames = df_agrupado['nombre_dia'].tolist(); bc.categoryAxis.labels.dy = -10; bc.categoryAxis.labels.fontSize = 9; bc.bars[0].fillColor = colors.HexColor("#27AE60"); d.add(bc); elements.append(d); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Tabla de Promedios Diarios</b>", h2_style)); det_data = [["DÍA DE LA SEMANA", "PROMEDIO DE INGRESOS"]]
    for index, row in df_agrupado.iterrows(): det_data.append([str(row['nombre_dia']), f"Q {row['promedio_ventas']:,.2f}"])
    t_det = Table(det_data, colWidths=[200, 200]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_recibo_venta_extra(fecha_emision, cliente, df_items, total):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", "RECIBO DE VENTA / NOTA DE ENVÍO")
    
    info_data = [["Fecha:", fecha_emision.strftime('%d/%m/%Y')], ["Cliente / Destino:", cliente]]
    t_info = Table(info_data, colWidths=[120, 380]); t_info.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)])); elements.append(t_info); elements.append(Spacer(1, 15))
    table_data = [["CANTIDAD", "DESCRIPCIÓN", "PRECIO UNIT.", "SUBTOTAL"]]
    for index, row in df_items.iterrows():
        if row['Subtotal (Q)'] > 0: table_data.append([str(row['Cantidad']), str(row['Descripción']), f"Q {row['Precio Unitario (Q)']:.2f}", f"Q {row['Subtotal (Q)']:.2f}"])
    table_data.append(["", "", "TOTAL:", f"Q {total:.2f}"])
    t_items = Table(table_data, colWidths=[80, 260, 80, 80])
    t_items.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (1,-1), 'LEFT'), ('ALIGN', (3,1), (3,-1), 'RIGHT'), ('GRID', (0,0), (-1,-2), 0.5, colors.lightgrey), ('FONTNAME', (2,-1), (3,-1), 'Helvetica-Bold'), ('BACKGROUND', (3,-1), (3,-1), colors.HexColor("#EAFAF1"))]))
    elements.append(t_items); elements.append(Spacer(1, 60))
    elements.append(Paragraph("__________________________________________", ParagraphStyle('firma', alignment=1))); elements.append(Paragraph("Firma de Entregado / Recibido", ParagraphStyle('firma', alignment=1)))
    doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_planilla_panaderos(panadero, f_inicio, f_fin, df_planilla, tot_lb_masa, tot_qq_masa, tot_lb_pasta, tot_qq_pasta, gran_total_qq, pago_qq, total_pagar):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", "PLANILLA DE PRODUCCIÓN DE PAN")
    
    header_data = [[f"PANADERO: {panadero.upper()}", f"SEMANA DEL: {f_inicio.strftime('%d/%m/%Y')} AL {f_fin.strftime('%d/%m/%Y')}", f"PAGO POR QQ: Q {pago_qq:.2f}"]]; t_header = Table(header_data, colWidths=[250, 250, 200]); t_header.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAECEE")), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('BOX', (0,0), (-1,-1), 1, colors.grey), ('PADDING', (0,0), (-1,-1), 5)])); elements.append(t_header); elements.append(Spacer(1, 10))
    df_imprimir = df_planilla[(df_planilla.iloc[:, 1:9].sum(axis=1) > 0)]; tabla_data = [["PRODUCTO", "LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO", "LIBRAS PASTA", "TOTAL LIBRAS"]]
    for index, row in df_imprimir.iterrows():
        total_fila = row['Lunes'] + row['Martes'] + row['Miércoles'] + row['Jueves'] + row['Viernes'] + row['Sábado'] + row['Domingo']
        tabla_data.append([row['Producto'], "" if row['Lunes']==0 else f"{row['Lunes']:.2f}", "" if row['Martes']==0 else f"{row['Martes']:.2f}", "" if row['Miércoles']==0 else f"{row['Miércoles']:.2f}", "" if row['Jueves']==0 else f"{row['Jueves']:.2f}", "" if row['Viernes']==0 else f"{row['Viernes']:.2f}", "" if row['Sábado']==0 else f"{row['Sábado']:.2f}", "" if row['Domingo']==0 else f"{row['Domingo']:.2f}", "" if row['Libras Pasta']==0 else f"{row['Libras Pasta']:.2f}", f"{total_fila:.2f}"])
    sumas = df_imprimir.sum(numeric_only=True); tabla_data.append(["TOTAL", f"{sumas['Lunes']:.2f}", f"{sumas['Martes']:.2f}", f"{sumas['Miércoles']:.2f}", f"{sumas['Jueves']:.2f}", f"{sumas['Viernes']:.2f}", f"{sumas['Sábado']:.2f}", f"{sumas['Domingo']:.2f}", f"{sumas['Libras Pasta']:.2f}", f"{tot_lb_masa:.2f}"])
    t_main = Table(tabla_data, colWidths=[150, 60, 60, 65, 60, 60, 60, 60, 80, 80]); t_main.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (0,-1), 'LEFT'), ('ALIGN', (1,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTSIZE', (0,0), (-1,-1), 8), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')])); elements.append(t_main); elements.append(Spacer(1, 15))
    liq_data = [["TOTAL LIBRAS MASA:", f"{tot_lb_masa:.2f}", "TOTAL QUINTALES MASA:", f"{tot_qq_masa:.2f}"], ["TOTAL LIBRAS PASTA:", f"{tot_lb_pasta:.2f}", "TOTAL QUINTALES PASTA:", f"{tot_qq_pasta:.2f}"], ["", "", "GRAN TOTAL QUINTALES:", f"{gran_total_qq:.2f}"], ["", "", "SUBTOTAL QUINCENA:", f"Q {pago_total_quincena:,.2f}"]]; t_liq = Table(liq_data, colWidths=[130, 100, 160, 100]); t_liq.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'RIGHT'), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('BACKGROUND', (2,2), (3,2), colors.HexColor("#F9E79F")), ('BACKGROUND', (2,3), (3,3), colors.lightgrey), ('GRID', (0,0), (1,1), 0.5, colors.grey), ('GRID', (2,0), (3,3), 0.5, colors.grey)])); t_liq.hAlign = 'RIGHT'; elements.append(t_liq); elements.append(Spacer(1, 30)); elements.append(Paragraph("___________________________________", ParagraphStyle('firma', alignment=1))); elements.append(Paragraph(f"Firma de Aprobación", ParagraphStyle('firma', alignment=1))); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_recibo_panadero(num_recibo, fecha_emision, panadero, f_inicio, f_fin, qq_total, precio_qq, subtotal, septimo, tortas, tienda, total_pagar):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", "RECIBO NO. " + str(num_recibo))
    
    label_style = ParagraphStyle('Lbl', fontName="Helvetica-Bold", fontSize=11, alignment=2, textColor=colors.HexColor("#34495E"))
    val_style = ParagraphStyle('Val', fontName="Helvetica", fontSize=11, alignment=0)
    center_bold = ParagraphStyle('CBold', fontName="Helvetica-Bold", fontSize=14, alignment=1, textColor=colors.HexColor("#2C3E50"))
    
    cantidad_letras = numero_a_letras(total_pagar); info_data = [[Paragraph("Fecha de Emisión:", label_style), Paragraph(fecha_emision.strftime('%A, %d de %B de %Y'), val_style)], [Paragraph("Recibí de:", label_style), Paragraph("PANADERÍA Y REPOSTERÍA JUDITH", val_style)], [Paragraph("La Cantidad de:", label_style), Paragraph(cantidad_letras, val_style)]]; t_info = Table(info_data, colWidths=[150, 380]); t_info.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOX', (0,0), (-1,-1), 1.5, colors.black), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('TOPPADDING', (0,0), (-1,-1), 6)])); elements.append(t_info)
    concept_data = [[Paragraph("Por Concepto De:", center_bold)], [Paragraph(f"Salario correspondiente del {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')} a favor de {panadero.upper()}", ParagraphStyle('C', alignment=1, fontSize=12))]]; t_concept = Table(concept_data, colWidths=[530]); t_concept.setStyle(TableStyle([('BACKGROUND', (0,0), (0,0), colors.lightgrey), ('BOX', (0,0), (-1,-1), 1.5, colors.black), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BOTTOMPADDING', (0,0), (-1,-1), 8), ('TOPPADDING', (0,0), (-1,-1), 8)])); elements.append(t_concept)
    calc_data = [[f"{qq_total:.2f}", "", ""], ["Quintalaje", f"Q {precio_qq:.2f}", f"Q {subtotal:,.2f}"], ["Septimo", "", f"{septimo:,.2f}"], ["tortas", "", f"{tortas:,.2f}"], ["(-) Tienda", "", f"{tienda:,.2f}"], ["Total A Pagar", "Q", f"{total_pagar:,.2f}"]]; t_calc = Table(calc_data, colWidths=[330, 80, 120]); t_calc.setStyle(TableStyle([('ALIGN', (0,0), (0,-1), 'RIGHT'), ('ALIGN', (1,0), (1,-1), 'CENTER'), ('ALIGN', (2,0), (2,-1), 'RIGHT'), ('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold'), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), ('BOX', (0,0), (0,0), 1, colors.black), ('BOX', (1,1), (1,1), 1, colors.black), ('BOX', (2,1), (2,-1), 1, colors.black), ('GRID', (2,1), (2,-1), 0.5, colors.black), ('BOX', (0,0), (-1,-1), 1.5, colors.black)])); elements.append(t_calc); elements.append(Spacer(1, 60)); elements.append(Paragraph("__________________________________________", ParagraphStyle('firma', alignment=1))); elements.append(Paragraph(f"Firma de Recibido - {panadero.upper()}", ParagraphStyle('firma', alignment=1))); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_planilla_empleados_resumen(f_inicio, f_fin, df_calc):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20); elements = []
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", f"Planilla correspondiente del: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}")
    
    data = [
        ["No.", "NOMBRES Y APELLIDOS", "SUELDO", "DÍAS", "TOTAL", "COMISIONES", "TOTAL", "DESCUENTOS", "", "", "TOTAL DE", "LÍQUIDO A"],
        ["", "DE LOS TRABAJADORES", "QUINCENAL", "LAB.", "PROP.", "S/ VENTAS", "DEVENGADO", "ANTICIPOS", "IGSS", "TIENDA", "DESCUENTOS", "RECIBIR"]
    ]
    sum_sueldo = 0; sum_total_prop = 0; sum_comis = 0; sum_dev = 0; sum_ant = 0; sum_igss = 0; sum_tienda = 0; sum_desc = 0; sum_liq = 0
    for i, row in df_calc.iterrows():
        data.append([
            str(i+1), str(row['Empleado']), 
            f"{row['Sueldo Quincenal']:.2f}", f"{row['Días Laborados']:.2f}", f"{row['Sueldo Prop.']:.2f}", 
            f"{row['Comisiones']:.2f}", f"{row['Total Devengado']:.2f}", 
            f"{row['Anticipos']:.2f}", f"{row['IGSS']:.2f}", f"{row['Tienda']:.2f}", 
            f"{row['Total Descuentos']:.2f}", f"{row['Líquido a Recibir']:.2f}"
        ])
        sum_sueldo += row['Sueldo Quincenal']; sum_total_prop += row['Sueldo Prop.']; sum_comis += row['Comisiones']; sum_dev += row['Total Devengado']; sum_ant += row['Anticipos']; sum_igss += row['IGSS']; sum_tienda += row['Tienda']; sum_desc += row['Total Descuentos']; sum_liq += row['Líquido a Recibir']
    
    data.append(["", "TOTALES", f"{sum_sueldo:.2f}", "", f"{sum_total_prop:.2f}", f"{sum_comis:.2f}", f"{sum_dev:.2f}", f"{sum_ant:.2f}", f"{sum_igss:.2f}", f"{sum_tienda:.2f}", f"{sum_desc:.2f}", f"{sum_liq:.2f}"])
    
    t = Table(data, colWidths=[25, 140, 65, 45, 55, 75, 75, 55, 50, 50, 75, 75])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTNAME', (0,0), (-1,1), 'Helvetica-Bold'), 
        ('FONTSIZE', (0,0), (-1,-1), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#2980B9")), 
        ('SPAN', (0,0), (0,1)), ('SPAN', (1,0), (1,1)), ('SPAN', (2,0), (2,1)), ('SPAN', (3,0), (3,1)), 
        ('SPAN', (4,0), (4,1)), ('SPAN', (5,0), (5,1)), ('SPAN', (6,0), (6,1)), 
        ('SPAN', (7,0), (9,0)), ('SPAN', (10,0), (10,1)), ('SPAN', (11,0), (11,1)), 
        ('TEXTCOLOR', (0,0), (-1,1), colors.HexColor("#1A5276")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), ('SPAN', (0,-1), (1,-1))
    ]))
    
    elements.append(t); elements.append(Spacer(1, 40)); sig_data = [["___________________________", "___________________________"], ["Elaborado Por", "Revisado / Autorizado"]]; t_sig = Table(sig_data, colWidths=[250, 250]); t_sig.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_sig)
    doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_recibos_quincenales(f_inicio, f_fin, df_calc):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40); elements = []
    
    lbl_style = ParagraphStyle('Lbl', fontName="Helvetica-Bold", fontSize=11)
    val_style = ParagraphStyle('Val', fontName="Helvetica", fontSize=11)

    for index, row in df_calc.iterrows():
        emp = str(row['Empleado']).strip()
        if not emp or emp.lower() == 'nan': continue
        
        add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", "BOLETA DE PAGO DE SALARIO")
        
        info_data = [[Paragraph("<b>Empleado:</b>", lbl_style), Paragraph(emp.upper(), val_style)], [Paragraph("<b>Período:</b>", lbl_style), Paragraph(f"Del {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}", val_style)]]
        t_info = Table(info_data, colWidths=[80, 400]); t_info.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'LEFT'), ('BOTTOMPADDING', (0,0), (-1,-1), 8)])); elements.append(t_info); elements.append(Spacer(1, 15))
        
        calc_data = [
            ["INGRESOS", "", "DESCUENTOS", ""],
            ["Sueldo Base", f"Q {row['Sueldo Quincenal']:.2f}", "Anticipos", f"Q {row['Anticipos']:.2f}"],
            [f"Días Laborados ({row['Días Laborados']} d)", "", "IGSS", f"Q {row['IGSS']:.2f}"],
            ["Sueldo Proporcional", f"Q {row['Sueldo Prop.']:.2f}", "Tienda", f"Q {row['Tienda']:.2f}"],
            ["Comisiones", f"Q {row['Comisiones']:.2f}", "", ""],
            ["TOTAL DEVENGADO", f"Q {row['Total Devengado']:.2f}", "TOTAL DESCUENTOS", f"Q {row['Total Descuentos']:.2f}"]
        ]
        
        t_calc = Table(calc_data, colWidths=[150, 100, 150, 100])
        t_calc.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('ALIGN', (1,1), (1,-1), 'RIGHT'), ('ALIGN', (3,1), (3,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#EAFAF1"))]))
        elements.append(t_calc); elements.append(Spacer(1, 15))
        
        liquido = float(row['Líquido a Recibir']); liq_letras = numero_a_letras(liquido)
        net_data = [[Paragraph("<b>LÍQUIDO A RECIBIR:</b>", lbl_style), Paragraph(f"<b>Q {liquido:,.2f}</b>", ParagraphStyle('N', fontSize=14, fontName="Helvetica-Bold", alignment=2, textColor=colors.HexColor("#27AE60")))], [Paragraph("<b>Cantidad en letras:</b>", lbl_style), Paragraph(liq_letras, val_style)]]
        t_net = Table(net_data, colWidths=[120, 380]); t_net.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1.5, colors.black), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 10)])); elements.append(t_net)
        
        elements.append(Spacer(1, 60)); elements.append(Paragraph("__________________________________________", ParagraphStyle('firma', alignment=1))); elements.append(Paragraph(f"Firma de Recibido - {emp.upper()}", ParagraphStyle('firma', alignment=1)))
        elements.append(PageBreak())
        
    doc.build(elements); buffer.seek(0); return buffer

# ==========================================
# 4. MENÚ LATERAL (SIDEBAR)
# ==========================================
with st.sidebar:
    logo_file = get_logo_path()
    if logo_file:
        st.image(logo_file, use_container_width=True)
    
    st.markdown(f"### 👤 {st.session_state['usuario'].capitalize()}")
    st.write(f"📅 Fecha actual: {get_fecha_guate().strftime('%d/%m/%Y')}")
    st.markdown("---")
    st.subheader("📍 Menú Principal")
    opcion_menu = st.radio("Selecciona un módulo:", [
        "📝 Registro de Corte", "📅 Historial de Cortes", "📈 Estadísticas", "📆 Comparativa Diaria", 
        "🏆 Días Estrella", "🚚 Ruta y Pedidos (XML)", "📝 Ventas Extra (Recibos)", "💳 Proveedores", 
        "👨‍🍳 Planilla Panaderos", "👩‍💼 Planilla Quincenal", "📊 Reporte PDF Mensual", "👥 Usuarios"
    ], label_visibility="collapsed")
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['logueado'] = False; st.rerun()

# ==========================================
# 5. MÓDULOS DE LA APLICACIÓN
# ==========================================

# ------------------------------------------
# MÓDULO 2: HISTORIAL DE CORTES CON DESCARGA EN LOTE (NUEVO)
# ------------------------------------------
if opcion_menu == "📅 Historial de Cortes":
    st.title("📅 Consulta de Historial e Impresión")
    
    tab_dia, tab_lote = st.tabs(["📅 Consulta por Día", "📦 Descargar Lote (ZIP)"])
    
    with tab_dia:
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
                with st.expander("✏️ Corregir Ingresos de este Día"):
                    with st.form("form_corregir_ingresos"):
                        st.warning("Usa esta opción si se te olvidó registrar alguna venta, efectivo o transferencia en este día.")
                        col_e1, col_e2, col_e3 = st.columns(3)
                        nuevo_efectivo = col_e1.number_input("🍞 Venta (Efectivo)", value=float(sum_venta), min_value=0.0, step=50.0)
                        nuevo_pedidos = col_e2.number_input("🎂 Pedidos (Efectivo)", value=float(sum_pedidos), min_value=0.0, step=50.0)
                        nuevo_trans = col_e3.number_input("📱 Transferencias (Fri/Depósitos)", value=float(sum_transferencias), min_value=0.0, step=50.0)
                        if st.form_submit_button("💾 Guardar Corrección"):
                            with conn.session as s:
                                existe = s.execute(text("SELECT id FROM ingresos WHERE corte_id = :cid"), {"cid": int(corte_id)}).fetchone()
                                if existe: s.execute(text("UPDATE ingresos SET venta_total = :v, credito_pagado = :p, transferencias = :t WHERE corte_id = :cid"), {"v": nuevo_efectivo, "p": nuevo_pedidos, "t": nuevo_trans, "cid": int(corte_id)})
                                else: ruta_default = s.execute(text("SELECT id FROM rutas_locales LIMIT 1")).fetchone()[0]; s.execute(text("INSERT INTO ingresos (corte_id, ruta_id, venta_total, credito_pagado, transferencias) VALUES (:c, :r, :v, :cp, :t)"), {"c": int(corte_id), "r": ruta_default, "v": nuevo_efectivo, "cp": nuevo_pedidos, "t": nuevo_trans})
                                s.commit()
                            st.success("✅ ¡Ingresos corregidos exitosamente!"); st.rerun()
                
                st.markdown("---")
                ruta_nombre = ingresos_hist.iloc[0]['ruta'] if not ingresos_hist.empty else "LOCAL MERCADO"
                df_para_pdf = pd.DataFrame({"Categoría": gastos_hist['categoria'] if not gastos_hist.empty else [], "Detalle": gastos_hist['detalle'] if not gastos_hist.empty else [], "Monto (Q)": gastos_hist['monto'] if not gastos_hist.empty else []})
                
                pdf_historico = generar_pdf_corte(fecha_consulta.strftime('%d/%m/%Y'), ruta_nombre, "Histórico", df_para_pdf, sum_venta, sum_pedidos, sum_transferencias)
                st.download_button(label=f"📥 Descargar PDF del {fecha_consulta.strftime('%d/%m/%Y')} para Imprimir", data=pdf_historico, file_name=f"Corte_{fecha_consulta.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
                
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
            else: st.warning(f"No hay ningún corte guardado en el sistema para la fecha {fecha_consulta.strftime('%d/%m/%Y')}.")
        except Exception as e: st.error("Error al consultar el historial.")

    with tab_lote:
        st.markdown("### 📦 Descargar Múltiples Cortes")
        st.write("Selecciona un rango de fechas para descargar todos los cortes en un solo archivo comprimido (.zip).")
        col_l1, col_l2 = st.columns(2)
        f_ini_lote = col_l1.date_input("Desde:", get_fecha_guate().replace(day=1), format="DD/MM/YYYY", key="lote_ini")
        f_fin_lote = col_l2.date_input("Hasta:", get_fecha_guate(), format="DD/MM/YYYY", key="lote_fin")
        
        if st.button("📦 Generar Archivo ZIP", type="primary", use_container_width=True):
            with st.spinner("Generando PDFs y comprimiendo..."):
                try:
                    q_cortes = f"SELECT id, fecha FROM cortes_diarios WHERE fecha BETWEEN '{f_ini_lote}' AND '{f_fin_lote}'"
                    df_cortes = conn.query(q_cortes, ttl=0)
                    
                    if df_cortes.empty:
                        st.warning("No hay cortes registrados en este rango de fechas.")
                    else:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for _, c_row in df_cortes.iterrows():
                                c_id = c_row['id']
                                c_fecha = pd.to_datetime(c_row['fecha']).date()
                                
                                ingresos_hist = conn.query(f"SELECT r.nombre as Ruta, i.venta_total as Venta_Mostrador, i.credito_pagado as Pedidos, i.transferencias as transferencias FROM ingresos i JOIN rutas_locales r ON i.ruta_id = r.id WHERE i.corte_id = {c_id}", ttl=0)
                                gastos_hist = conn.query(f"SELECT c.nombre as Categoria, g.detalle as Detalle, g.monto as Monto FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id WHERE g.corte_id = {c_id}", ttl=0)
                                
                                sum_venta = ingresos_hist['venta_mostrador'].sum() if not ingresos_hist.empty else 0.0
                                sum_pedidos = ingresos_hist['pedidos'].sum() if not ingresos_hist.empty else 0.0
                                sum_transferencias = ingresos_hist['transferencias'].sum() if not ingresos_hist.empty and 'transferencias' in ingresos_hist.columns else 0.0
                                
                                ruta_nombre = ingresos_hist.iloc[0]['ruta'] if not ingresos_hist.empty else "LOCAL MERCADO"
                                df_para_pdf = pd.DataFrame({"Categoría": gastos_hist['categoria'] if not gastos_hist.empty else [], "Detalle": gastos_hist['detalle'] if not gastos_hist.empty else [], "Monto (Q)": gastos_hist['monto'] if not gastos_hist.empty else []})
                                
                                pdf_bytes = generar_pdf_corte(c_fecha.strftime('%d/%m/%Y'), ruta_nombre, "Histórico", df_para_pdf, sum_venta, sum_pedidos, sum_transferencias)
                                zip_file.writestr(f"Corte_{c_fecha.strftime('%d-%m-%Y')}.pdf", pdf_bytes.getvalue())
                                
                        st.success(f"✅ ¡ZIP generado con {len(df_cortes)} cortes!")
                        st.download_button(label="📥 Descargar Archivo ZIP", data=zip_buffer.getvalue(), file_name=f"Cortes_{f_ini_lote.strftime('%d-%m-%Y')}_al_{f_fin_lote.strftime('%d-%m-%Y')}.zip", mime="application/zip", type="secondary", use_container_width=True)
                except Exception as e:
                    st.error(f"Error al generar el lote: {e}")

# ------------------------------------------
# EL RESTO DE MÓDULOS DE LA APLICACIÓN (MANTENIDOS INTACTOS)
# ------------------------------------------
elif opcion_menu == "📝 Registro de Corte":
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
    if 'reset_key' not in st.session_state: st.session_state.reset_key = 0

    if 'gastos_df' not in st.session_state:
        st.session_state.gastos_df = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11): st.session_state.gastos_df.loc[len(st.session_state.gastos_df)] = [None, "", 0.0]

    gastos_editados = st.data_editor(
        st.session_state.gastos_df,
        column_config={
            "Categoría": st.column_config.SelectboxColumn("Tipo de Gasto (Automático)", options=lista_categorias, required=False),
            "Detalle": st.column_config.TextColumn("Detalle del gasto"),
            "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")
        },
        num_rows="dynamic", use_container_width=True, key=f"tabla_gastos_{st.session_state.reset_key}" 
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
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1: btn_guardar = st.button("💾 Guardar Corte Completo", type="primary", use_container_width=True)
    with col_btn2: btn_limpiar = st.button("🧹 Limpiar / Nuevo Corte", type="secondary", use_container_width=True)

    if btn_limpiar:
        df_limpio = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11): df_limpio.loc[len(df_limpio)] = [None, "", 0.0]
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
            for _ in range(11): df_limpio.loc[len(df_limpio)] = [None, "", 0.0]
            st.session_state.gastos_df = df_limpio
            st.session_state.reset_key += 1
            st.rerun()
        else:
            st.warning("⚠️ Debes ingresar al menos una venta o un gasto para guardar.")
            
    if 'pdf_generado' in st.session_state:
        st.markdown("---")
        st.download_button(label="📥 Descargar PDF del Corte para Imprimir", data=st.session_state['pdf_generado'], file_name=st.session_state['pdf_nombre'], mime="application/pdf", type="secondary", use_container_width=True)

elif opcion_menu == "📈 Estadísticas":
    st.title("📈 Estadísticas y Finanzas")
    meses_dict = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
    hoy = get_fecha_guate(); nombre_mes_actual = list(meses_dict.keys())[list(meses_dict.values()).index(hoy.month)]
    col_f1, col_f2 = st.columns(2); mes_seleccionado = col_f1.selectbox("Selecciona el Mes", list(meses_dict.keys()), index=list(meses_dict.keys()).index(nombre_mes_actual)); anio_seleccionado = col_f2.selectbox("Selecciona el Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1); mes_num = meses_dict[mes_seleccionado]
    try:
        query_gastos = """SELECT c.nombre as categoria, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id JOIN cortes_diarios cd ON g.corte_id = cd.id WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio GROUP BY c.nombre"""
        gastos_totales = conn.query(query_gastos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_ingresos = """SELECT SUM(i.venta_total + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as total_ingresos FROM ingresos i JOIN cortes_diarios cd ON i.corte_id = cd.id WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio"""
        ingresos_totales = conn.query(query_ingresos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_jeny = """SELECT SUM(monto) as abonos FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND EXTRACT(MONTH FROM fecha) = :mes AND EXTRACT(YEAR FROM fecha) = :anio"""
        jeny_totales = conn.query(query_jeny, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_rutas = """SELECT SUM(gran_total) as rutas_contado FROM control_rutas WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND EXTRACT(MONTH FROM fecha_factura) = :mes AND EXTRACT(YEAR FROM fecha_factura) = :anio"""
        rutas_totales = conn.query(query_rutas, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_ve = "SELECT SUM(total) as ve FROM ventas_extra WHERE EXTRACT(MONTH FROM fecha) = :mes AND EXTRACT(YEAR FROM fecha) = :anio"
        try: ve_totales = conn.query(query_ve, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        except: ve_totales = pd.DataFrame() 

        total_g = gastos_totales['total'].sum() if not gastos_totales.empty else 0.0
        ing_caja = float(ingresos_totales.iloc[0]['total_ingresos']) if not ingresos_totales.empty and pd.notna(ingresos_totales.iloc[0]['total_ingresos']) else 0.0
        ing_jeny = float(jeny_totales.iloc[0]['abonos']) if not jeny_totales.empty and pd.notna(jeny_totales.iloc[0]['abonos']) else 0.0
        ing_rutas = float(rutas_totales.iloc[0]['rutas_contado']) if not rutas_totales.empty and pd.notna(rutas_totales.iloc[0]['rutas_contado']) else 0.0
        ing_ve = float(ve_totales.iloc[0]['ve']) if not ve_totales.empty and pd.notna(ve_totales.iloc[0]['ve']) else 0.0
        total_i = ing_caja + ing_jeny + ing_rutas + ing_ve; utilidad = total_i - total_g
        
        st.markdown("---"); col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric(f"💵 Ingresos Globales ({mes_seleccionado})", f"Q {total_i:,.2f}"); col_s2.metric(f"📉 Gastos Globales ({mes_seleccionado})", f"Q {total_g:,.2f}"); col_s3.metric(f"⚖️ Utilidad Bruta", f"Q {utilidad:,.2f}")
        st.caption(f"**Desglose Ingresos:** Caja Diaria (Q {ing_caja:,.2f}) + Abonos Jeny (Q {ing_jeny:,.2f}) + Rutas Contado (Q {ing_rutas:,.2f}) + Ventas Extra (Q {ing_ve:,.2f})"); st.markdown("---")
        if not gastos_totales.empty and total_g > 0: fig = px.pie(gastos_totales, values='total', names='categoria', hole=0.4, title=f"Distribución de Gastos - {mes_seleccionado} {anio_seleccionado}"); st.plotly_chart(fig, use_container_width=True)
        else: st.info(f"📊 No hay gastos registrados para el mes de {mes_seleccionado} {anio_seleccionado}.")
    except Exception as e: st.error(f"Error al cargar las estadísticas: {e}")

elif opcion_menu == "📆 Comparativa Diaria":
    st.title("📆 Comparativa de Ingresos vs Gastos por Día")
    hoy = get_fecha_guate(); primer_dia_mes = hoy.replace(day=1)
    col_d1, col_d2 = st.columns(2); fecha_inicio_comp = col_d1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY"); fecha_fin_comp = col_d2.date_input("Hasta:", hoy, format="DD/MM/YYYY")
    if st.button("🔍 Consultar Días", type="primary"):
        with st.spinner("Cargando los datos..."):
            try:
                q_ing_full = """
                    SELECT fecha, SUM(monto) as ingresos FROM (
                        SELECT cd.fecha, (COALESCE(i.venta_total, 0) + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as monto FROM cortes_diarios cd LEFT JOIN ingresos i ON cd.id = i.corte_id WHERE cd.fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha, monto FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha_factura as fecha, gran_total as monto FROM control_rutas WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND fecha_factura BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha, total as monto FROM ventas_extra WHERE fecha BETWEEN :inicio AND :fin
                    ) sub GROUP BY fecha
                """
                df_ing = conn.query(q_ing_full, params={"inicio": fecha_inicio_comp, "fin": fecha_fin_comp}, ttl=0)
                q_gas = """SELECT cd.fecha, SUM(COALESCE(g.monto, 0)) as gastos FROM cortes_diarios cd LEFT JOIN gastos g ON cd.id = g.corte_id WHERE cd.fecha BETWEEN :inicio AND :fin GROUP BY cd.fecha"""
                df_gas = conn.query(q_gas, params={"inicio": fecha_inicio_comp, "fin": fecha_fin_comp}, ttl=0)
                if df_ing.empty and df_gas.empty: st.warning("No hay registros en esas fechas.")
                else:
                    df_resumen = pd.merge(df_ing, df_gas, on='fecha', how='outer').fillna(0); df_resumen['fecha'] = pd.to_datetime(df_resumen['fecha']).dt.date; df_resumen = df_resumen.sort_values('fecha'); df_resumen['utilidad'] = df_resumen['ingresos'] - df_resumen['gastos']
                    t_ing = df_resumen['ingresos'].sum(); t_gas = df_resumen['gastos'].sum(); t_uti = df_resumen['utilidad'].sum()
                    st.markdown("---"); c1, c2, c3 = st.columns(3); c1.metric("💰 Total Ingresos del Rango", f"Q {t_ing:,.2f}"); c2.metric("📉 Total Gastos del Rango", f"Q {t_gas:,.2f}"); c3.metric("⚖️ Utilidad del Rango", f"Q {t_uti:,.2f}"); st.markdown("---")
                    df_graf = df_resumen[['fecha', 'ingresos', 'gastos']].melt(id_vars='fecha', var_name='Tipo', value_name='Monto')
                    fig = px.bar(df_graf, x='fecha', y='Monto', color='Tipo', barmode='group', color_discrete_map={'ingresos': '#27AE60', 'gastos': '#E74C3C'}); st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df_resumen, column_config={"fecha": st.column_config.DateColumn("Fecha del Corte", format="DD/MM/YYYY"), "ingresos": st.column_config.NumberColumn("Total Ingresos (Global)", format="Q %.2f"), "gastos": st.column_config.NumberColumn("Total Gastos", format="Q %.2f"), "utilidad": st.column_config.NumberColumn("Utilidad Neta", format="Q %.2f")}, hide_index=True, use_container_width=True)
                    pdf_comparativa = generar_pdf_comparativa_diaria(fecha_inicio_comp, fecha_fin_comp, df_resumen, t_ing, t_gas, t_uti)
                    st.download_button(label="📥 Descargar Comparativa en PDF", data=pdf_comparativa, file_name=f"Comparativa_Diaria_{fecha_inicio_comp.strftime('%d-%m-%Y')}_al_{fecha_fin_comp.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
            except Exception as e: st.error(f"Error al cargar la comparativa: {e}")

elif opcion_menu == "🏆 Días Estrella":
    st.title("🏆 Días Estrella (Rendimiento Semanal)")
    hoy = get_fecha_guate(); primer_dia_mes = hoy.replace(day=1)
    col_d1, col_d2 = st.columns(2); fecha_inicio_est = col_d1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY", key="fecha_est_1"); fecha_fin_est = col_d2.date_input("Hasta:", hoy, format="DD/MM/YYYY", key="fecha_est_2")
    if st.button("📊 Analizar Días", type="primary"):
        with st.spinner("Buscando el mejor día..."):
            try:
                q_ing_full = """
                    SELECT fecha, SUM(monto) as ingresos FROM (
                        SELECT cd.fecha, (COALESCE(i.venta_total, 0) + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as monto FROM cortes_diarios cd LEFT JOIN ingresos i ON cd.id = i.corte_id WHERE cd.fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha, monto FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha_factura as fecha, gran_total as monto FROM control_rutas WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND fecha_factura BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha, total as monto FROM ventas_extra WHERE fecha BETWEEN :inicio AND :fin
                    ) sub GROUP BY fecha
                """
                df_ing_dias = conn.query(q_ing_full, params={"inicio": fecha_inicio_est, "fin": fecha_fin_est}, ttl=0)
                if df_ing_dias.empty or df_ing_dias['ingresos'].sum() == 0: st.warning("No hay ventas registradas en ese rango.")
                else:
                    dias_espanol = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
                    df_ing_dias['fecha'] = pd.to_datetime(df_ing_dias['fecha']); df_ing_dias['nombre_dia'] = df_ing_dias['fecha'].dt.day_name().map(dias_espanol)
                    df_agrupado = df_ing_dias.groupby('nombre_dia', as_index=False)['ingresos'].mean(); df_agrupado = df_agrupado.rename(columns={'ingresos': 'promedio_ventas'})
                    orden_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']; df_agrupado['nombre_dia'] = pd.Categorical(df_agrupado['nombre_dia'], categories=orden_dias, ordered=True); df_agrupado = df_agrupado.sort_values('nombre_dia')
                    mejor_dia_nombre = df_agrupado.loc[df_agrupado['promedio_ventas'].idxmax()]['nombre_dia']; peor_dia_nombre = df_agrupado.loc[df_agrupado['promedio_ventas'].idxmin()]['nombre_dia']; promedio_general = df_ing_dias['ingresos'].mean(); dia_record = df_ing_dias.loc[df_ing_dias['ingresos'].idxmax()]
                    st.markdown("---"); col1, col2, col3, col4 = st.columns(4)
                    col1.metric("🔥 Mejor Día de la Semana", str(mejor_dia_nombre)); col2.metric("💤 Día más Flojo", str(peor_dia_nombre)); col3.metric("📊 Venta Promedio Diaria", f"Q {promedio_general:,.2f}"); col4.metric("👑 Día Récord (Fecha Exacta)", f"{dia_record['fecha'].strftime('%d/%m/%Y')}", f"Q {dia_record['ingresos']:,.2f}")
                    fig = px.bar(df_agrupado, x='nombre_dia', y='promedio_ventas', labels={'nombre_dia': 'Día de la Semana', 'promedio_ventas': 'Promedio Vendido (Q)'}, color='promedio_ventas', color_continuous_scale=px.colors.sequential.Viridis); st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df_agrupado, column_config={"nombre_dia": "Día de la Semana", "promedio_ventas": st.column_config.NumberColumn("Promedio de Ingresos", format="Q %.2f")}, hide_index=True, use_container_width=True)
                    pdf_estrellas = generar_pdf_dias_estrella(fecha_inicio_est, fecha_fin_est, df_agrupado, mejor_dia_nombre, peor_dia_nombre, promedio_general, dia_record); st.download_button(label="📥 Descargar Análisis en PDF", data=pdf_estrellas, file_name=f"Dias_Estrella_{fecha_inicio_est.strftime('%d-%m-%Y')}_al_{fecha_fin_est.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
            except Exception as e: st.error(f"Error al cargar el análisis: {e}")

elif opcion_menu == "📊 Reporte PDF Mensual":
    st.title("📊 Generador de Reporte Financiero (PDF)")
    st.write("Selecciona las fechas para crear un reporte gerencial con gráfica de pastel y resumen de gastos consolidados.")
    hoy = get_fecha_guate(); primer_dia_mes = hoy.replace(day=1)
    col_f1, col_f2 = st.columns(2); fecha_inicio = col_f1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY"); fecha_fin = col_f2.date_input("Hasta:", hoy, format="DD/MM/YYYY")
    if st.button("📑 Generar Reporte PDF", type="primary"):
        with st.spinner("Calculando agrupaciones y dibujando gráficas..."):
            try:
                query_ing = """SELECT SUM(i.venta_total) as efectivo, SUM(COALESCE(i.credito_pagado, 0)) as pedidos, SUM(COALESCE(i.transferencias, 0)) as transferencias FROM ingresos i JOIN cortes_diarios cd ON i.corte_id = cd.id WHERE cd.fecha BETWEEN :inicio AND :fin"""
                ingresos_df = conn.query(query_ing, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                query_cat = """SELECT c.nombre as categoria, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id JOIN cortes_diarios cd ON g.corte_id = cd.id WHERE cd.fecha BETWEEN :inicio AND :fin GROUP BY c.nombre ORDER BY total DESC"""
                gastos_cat_df = conn.query(query_cat, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                query_det = """SELECT c.nombre as categoria, LOWER(g.detalle) as detalle, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id JOIN cortes_diarios cd ON g.corte_id = cd.id WHERE cd.fecha BETWEEN :inicio AND :fin GROUP BY c.nombre, LOWER(g.detalle) ORDER BY c.nombre, total DESC"""
                gastos_det_df = conn.query(query_det, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                query_jeny = """SELECT SUM(monto) as abonos FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND fecha BETWEEN :inicio AND :fin"""
                jeny_totales = conn.query(query_jeny, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                ing_jeny = float(jeny_totales.iloc[0]['abonos']) if not jeny_totales.empty and pd.notna(jeny_totales.iloc[0]['abonos']) else 0.0
                query_rutas = """SELECT SUM(gran_total) as rutas_contado FROM control_rutas WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND fecha_factura BETWEEN :inicio AND :fin"""
                rutas_totales = conn.query(query_rutas, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                ing_rutas = float(rutas_totales.iloc[0]['rutas_contado']) if not rutas_totales.empty and pd.notna(rutas_totales.iloc[0]['rutas_contado']) else 0.0
                try: 
                    query_ve = "SELECT SUM(total) as ve FROM ventas_extra WHERE fecha BETWEEN :inicio AND :fin"
                    ve_totales = conn.query(query_ve, params={"inicio": fecha_inicio, "fin": fecha_fin}, ttl=0)
                    ing_ve = float(ve_totales.iloc[0]['ve']) if not ve_totales.empty and pd.notna(ve_totales.iloc[0]['ve']) else 0.0
                except: ing_ve = 0.0

                if (not ingresos_df.empty and ingresos_df['efectivo'].sum() > 0) or not gastos_cat_df.empty or ing_jeny > 0 or ing_rutas > 0 or ing_ve > 0:
                    buffer_pdf = generar_pdf_reporte_mensual(fecha_inicio, fecha_fin, ingresos_df, gastos_cat_df, gastos_det_df, ing_jeny, ing_rutas, ing_ve)
                    st.success("✅ ¡Tu Reporte Gerencial ha sido generado con éxito!")
                    st.download_button(label="📥 Descargar Reporte PDF", data=buffer_pdf, file_name=f"Reporte_Panaderia_{fecha_inicio.strftime('%d-%m-%Y')}_al_{fecha_fin.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
                else: st.warning(f"⚠️ No se encontraron registros de ventas ni gastos entre el {fecha_inicio.strftime('%d/%m/%Y')} y el {fecha_fin.strftime('%d/%m/%Y')}.")
            except Exception as e: st.error(f"Error al generar el reporte: {e}")
