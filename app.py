import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import pytz
import plotly.express as px
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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

# --- FUNCIÓN PARA CONVERTIR NÚMEROS A LETRAS ---
def numero_a_letras(numero):
    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    dieces = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    veintes = ["VEINTE", "VEINTIUN", "VEINTIDOS", "VEINTITRES", "VEINTICUATRO", "VEINTICINCO", "VEINTISEIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def convertir_grupo(n):
        output = ""
        c = n // 100
        r = n % 100
        if c == 1 and r == 0: return "CIEN"
        elif c > 0: output += centenas[c] + " "
        d = r // 10
        u = r % 10
        if d == 1: output += dieces[u]
        elif d == 2: output += veintes[u]
        elif d > 2:
            output += decenas[d]
            if u > 0: output += " Y " + unidades[u]
        else:
            if u > 0: output += unidades[u]
        return output.strip()

    entero = int(numero)
    decimal = int(round((numero - entero) * 100))
    if entero == 0: letras = "CERO"
    elif entero < 1000: letras = convertir_grupo(entero)
    else:
        miles = entero // 1000
        resto = entero % 1000
        letras_miles = "UN MIL" if miles == 1 else convertir_grupo(miles) + " MIL"
        letras_resto = convertir_grupo(resto)
        letras = letras_miles + " " + letras_resto

    return f"{letras.strip()} CON {decimal:02d}/100"

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
        if result: return result[0]
        else:
            s.execute(text("INSERT INTO cortes_diarios (fecha) VALUES (:fecha)"), {"fecha": fecha_corte})
            s.commit()
            return s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()[0]

def autocompletar_categoria(detalle):
    d = str(detalle).lower()
    if 'pasta' in d or 'pollo' in d: return 'COMPRAS DE PASTA DE POLLO'
    if 'bolsa de agua' in d or 'agua' in d or 'gaseosa' in d or 'coca' in d or 'bebida' in d or 'tostada' in d or 'marquesote' in d: return 'OTRAS MERCADERIAS'
    if 'luz' in d or 'internet' in d or 'telefono' in d or 'basura' in d or 'alquiler' in d or 'impuesto' in d or 'gas ' in d or 'propano' in d: return 'OTROS GASTOS' 
    if re.search(r'\b(harina|azucar|azúcar|manteca|levadura|leche|huevo|huevos|sal)\b', d): return 'MATERIA PRIMA'
    if re.search(r'\b(bono|sueldo|sueldos|salario|salarios|anticipo|almuerzo|planilla|turno|quincena|panadero)\b', d): return 'SUELDOS Y SALARIOS'
    if re.search(r'\b(gasolina|moto|vehiculo|repuesto|llanta|aceite|mecanico|pinchazo)\b', d): return 'REPUESTOS Y REPARACIONES'
    if re.search(r'\b(bolsa|bandeja|calcomania|papel|limpieza|empaque|escoba|jabon|cloro)\b', d): return 'UTILES Y EMPAQUES'
    if re.search(r'\b(prestamo|tarjeta|interes|abono|banco|cuota)\b', d): return 'PRESTAMOS E INTERESES'
    return 'OTROS GASTOS' 

# -- FUNCIONES PDF ACTUALIZADAS --
def generar_pdf_corte(fecha_str, local_str, responsable_str, df_gastos, venta_efectivo, pago_pedidos, transferencias):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=10, fontName="Helvetica-Bold")
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style)); elements.append(Paragraph("INTEGRACIÓN DE INGRESOS Y EGRESOS - CORTE DE CAJA", subtitle_style)); elements.append(Spacer(1, 15))
    info_data = [[Paragraph(f"<b>Fecha:</b> {fecha_str}", bold_style), Paragraph(f"<b>Local / Ruta:</b> {local_str}", bold_style), Paragraph(f"<b>Responsable:</b> {responsable_str}", bold_style)]]
    info_table = Table(info_data, colWidths=[150, 200, 190])
    info_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAFAF1")), ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#27AE60")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 6)]))
    elements.append(info_table); elements.append(Spacer(1, 15))
    gastos_table_data = [["TIPO DE GASTO", "DETALLE", "TOTAL (Q)"]]; total_gastos = 0.0
    for index, row in df_gastos.iterrows():
        if row["Monto (Q)"] > 0:
            categoria_mostrar = row["Categoría"] if pd.notna(row["Categoría"]) else "OTROS GASTOS"
            gastos_table_data.append([str(categoria_mostrar), str(row["Detalle"]), f"Q {row['Monto (Q)']:.2f}"]); total_gastos += float(row["Monto (Q)"])
    while len(gastos_table_data) < 10: gastos_table_data.append(["", "", ""])
    gastos_table_data.append(["", "TOTAL GASTOS", f"Q {total_gastos:.2f}"])
    t_gastos = Table(gastos_table_data, colWidths=[180, 240, 120])
    t_gastos.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#27AE60")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('ALIGN', (2,0), (2,-1), 'RIGHT'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 6), ('GRID', (0,0), (-1,-2), 0.5, colors.grey), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')]))
    elements.append(t_gastos); elements.append(Spacer(1, 15))
    efectivo_ingresado = venta_efectivo + pago_pedidos; total_ingresos_brutos = efectivo_ingresado + transferencias; neto_efectivo = efectivo_ingresado - total_gastos
    resumen_data = [["RESUMEN FINANCIERO", "MONTO"], ["Venta de Pan (Efectivo)", f"Q {venta_efectivo:.2f}"], ["Pago de Pedidos (Efectivo)", f"Q {pago_pedidos:.2f}"], ["Transferencias / Fri / Depósitos", f"Q {transferencias:.2f}"], ["TOTAL INGRESOS BRUTOS", f"Q {total_ingresos_brutos:.2f}"], ["TOTAL GASTOS (En efectivo)", f"Q {total_gastos:.2f}"], ["EFECTIVO NETO A ENTREGAR", f"Q {neto_efectivo:.2f}"]]
    t_resumen = Table(resumen_data, colWidths=[340, 200])
    t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#EAECEE")), ('BACKGROUND', (0,6), (-1,6), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'), ('FONTNAME', (0,6), (-1,6), 'Helvetica-Bold')]))
    elements.append(t_resumen); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_reporte_mensual(f_inicio, f_fin, ingresos_df, gastos_cat_df, gastos_det_df, v_abonos_jeny, v_otras_rutas):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet(); title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style)); elements.append(Paragraph(f"REPORTE GERENCIAL DE RESULTADOS: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}", subtitle_style)); elements.append(Spacer(1, 20))
    v_efectivo = ingresos_df['efectivo'].sum() if not ingresos_df.empty else 0
    v_pedidos_trans = (ingresos_df['pedidos'].sum() + ingresos_df['transferencias'].sum()) if not ingresos_df.empty else 0
    t_ingresos = v_efectivo + v_pedidos_trans + v_abonos_jeny + v_otras_rutas
    t_gastos = gastos_cat_df['total'].sum() if not gastos_cat_df.empty else 0
    utilidad = t_ingresos - t_gastos
    resumen_data = [
        ["RESUMEN DE INGRESOS", "MONTO (Q)", "RESUMEN DE EGRESOS Y UTILIDAD", "MONTO (Q)"],
        ["Ventas Mostrador (Efectivo)", f"Q {v_efectivo:,.2f}", "Total Gastos Generales", f"Q {t_gastos:,.2f}"],
        ["Transferencias / Pedidos", f"Q {v_pedidos_trans:,.2f}", "", ""],
        ["Abonos Ruta Oasis (Jeny)", f"Q {v_abonos_jeny:,.2f}", "UTILIDAD BRUTA DEL PERIODO", f"Q {utilidad:,.2f}"],
        ["Rutas Contado (Shell/XML)", f"Q {v_otras_rutas:,.2f}", "", ""],
        ["TOTAL INGRESOS", f"Q {t_ingresos:,.2f}", "", ""]
    ]
    t_resumen = Table(resumen_data, colWidths=[140, 90, 190, 100])
    t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (1,0), colors.HexColor("#27AE60")), ('BACKGROUND', (2,0), (3,0), colors.HexColor("#E74C3C")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('ALIGN', (3,0), (3,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,-1), (1,-1), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,-1), (1,-1), 'Helvetica-Bold'), ('BACKGROUND', (2,3), (3,3), colors.HexColor("#FADBD8")), ('FONTNAME', (2,3), (3,3), 'Helvetica-Bold')]))
    elements.append(t_resumen); elements.append(Spacer(1, 20))
    if not gastos_cat_df.empty and t_gastos > 0:
        elements.append(Paragraph("<b>Distribución de Gastos por Categoría</b>", h2_style)); d = Drawing(400, 160); pc = Pie(); pc.x = 20; pc.y = 10; pc.width = 140; pc.height = 140; pc.data = gastos_cat_df['total'].tolist(); pc.labels = [f"{row['categoria']} ({(row['total']/t_gastos)*100:.1f}%)" for _, row in gastos_cat_df.iterrows()]; pc.sideLabels = 1; colores_hex = ["#3498DB", "#E74C3C", "#2ECC71", "#F1C40F", "#9B59B6", "#E67E22", "#1ABC9C", "#34495E", "#95A5A6"]
        for i in range(len(pc.data)): pc.slices[i].fillColor = colors.HexColor(colores_hex[i % len(colores_hex)]); pc.slices[i].strokeColor = colors.white
        d.add(pc); elements.append(d); elements.append(Spacer(1, 10))
    gastos_data = [["CATEGORÍA DE GASTO", "MONTO GASTADO", "PORCENTAJE"]]
    for index, row in gastos_cat_df.iterrows(): pct = (row['total'] / t_gastos) * 100 if t_gastos > 0 else 0; gastos_data.append([str(row["categoria"]), f"Q {row['total']:,.2f}", f"{pct:.1f}%"])
    t_cat = Table(gastos_data, colWidths=[250, 150, 120]); t_cat.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_cat); elements.append(Spacer(1, 25))
    elements.append(Paragraph("<b>Anexo: Detalle Específico de Artículos/Servicios Pagados</b>", h2_style)); det_data = [["CATEGORÍA", "DESCRIPCIÓN DEL GASTO", "TOTAL INVERTIDO"]]
    for index, row in gastos_det_df.iterrows(): det_data.append([str(row["categoria"]), str(row["detalle"]).title(), f"Q {row['total']:,.2f}"])
    t_det = Table(det_data, colWidths=[150, 250, 120]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#BDC3C7")), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (2,0), (2,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), ('FONTSIZE', (0,0), (-1,-1), 9)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_comparativa_diaria(f_inicio, f_fin, df_resumen, t_ing, t_gas, t_uti):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet(); title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style)); elements.append(Paragraph(f"REPORTE COMPARATIVO DIARIO (INCLUYE RUTAS Y ABONOS): {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}", subtitle_style)); elements.append(Spacer(1, 15))
    resumen_data = [["TOTAL INGRESOS GLOBAL", "TOTAL GASTOS", "UTILIDAD NETA"], [f"Q {t_ing:,.2f}", f"Q {t_gas:,.2f}", f"Q {t_uti:,.2f}"]]; t_resumen = Table(resumen_data, colWidths=[150, 150, 150]); t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_resumen); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Gráfica Comparativa: Ingresos vs Gastos</b>", h2_style)); d = Drawing(480, 200); bc = VerticalBarChart(); bc.x = 40; bc.y = 40; bc.height = 140; bc.width = 420; bc.data = [df_resumen['ingresos'].tolist(), df_resumen['gastos'].tolist()]; bc.strokeColor = colors.white; bc.valueAxis.valueMin = 0; bc.categoryAxis.categoryNames = [fecha.strftime('%d/%m') for fecha in df_resumen['fecha']]; bc.categoryAxis.labels.angle = 45; bc.categoryAxis.labels.dy = -10; bc.categoryAxis.labels.fontSize = 8; bc.bars[0].fillColor = colors.HexColor("#27AE60") ; bc.bars[1].fillColor = colors.HexColor("#E74C3C") 
    leg = Legend(); leg.x = 350; leg.y = 180; leg.alignment = 'right'; leg.colorNamePairs = [(colors.HexColor("#27AE60"), 'Total Ingresos'), (colors.HexColor("#E74C3C"), 'Total Gastos')]; leg.fontSize = 8; leg.boxAnchor = 'nw'; d.add(bc); d.add(leg); elements.append(d); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Detalle Diario de Movimientos</b>", h2_style)); det_data = [["FECHA", "TOTAL INGRESOS", "TOTAL GASTOS", "UTILIDAD NETA"]]
    for index, row in df_resumen.iterrows(): det_data.append([row['fecha'].strftime('%d/%m/%Y'), f"Q {row['ingresos']:,.2f}", f"Q {row['gastos']:,.2f}", f"Q {row['utilidad']:,.2f}"])
    t_det = Table(det_data, colWidths=[120, 120, 120, 120]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_dias_estrella(f_inicio, f_fin, df_agrupado, mejor_dia, peor_dia, prom_gral, dia_record):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet(); title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style)); elements.append(Paragraph(f"REPORTE DE DÍAS ESTRELLA: {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}", subtitle_style)); elements.append(Spacer(1, 15))
    metricas_data = [["MEJOR DÍA", "DÍA MÁS FLOJO", "PROMEDIO DIARIO", "DÍA RÉCORD"], [str(mejor_dia), str(peor_dia), f"Q {prom_gral:,.2f}", f"{dia_record['fecha'].strftime('%d/%m/%Y')} (Q {dia_record['ingresos']:,.2f})"]]; t_metricas = Table(metricas_data, colWidths=[120, 120, 130, 150]); t_metricas.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_metricas); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Gráfica de Rendimiento por Día de la Semana</b>", h2_style)); d = Drawing(480, 200); bc = VerticalBarChart(); bc.x = 40; bc.y = 40; bc.height = 140; bc.width = 420; bc.data = [df_agrupado['promedio_ventas'].tolist()]; bc.strokeColor = colors.white; bc.valueAxis.valueMin = 0; bc.categoryAxis.categoryNames = df_agrupado['nombre_dia'].tolist(); bc.categoryAxis.labels.dy = -10; bc.categoryAxis.labels.fontSize = 9; bc.bars[0].fillColor = colors.HexColor("#27AE60"); d.add(bc); elements.append(d); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Tabla de Promedios Diarios</b>", h2_style)); det_data = [["DÍA DE LA SEMANA", "PROMEDIO DE INGRESOS"]]
    for index, row in df_agrupado.iterrows(): det_data.append([str(row['nombre_dia']), f"Q {row['promedio_ventas']:,.2f}"])
    t_det = Table(det_data, colWidths=[200, 200]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

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
        ["📝 Registro de Corte", "📅 Historial de Cortes", "📈 Estadísticas", "📆 Comparativa Diaria", "🏆 Días Estrella", "🚚 Ruta y Pedidos (XML)", "💳 Proveedores", "👨‍🍳 Planilla Panaderos", "📊 Reporte PDF Mensual"],
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
# MÓDULO: 🚚 RUTA Y PEDIDOS (XML)
# ------------------------------------------
if opcion_menu == "🚚 Ruta y Pedidos (XML)":
    st.title("🚚 Control de Ruta y Pedidos (Lector SAT)")
    
    tab_xml, tab_cuenta, tab_historial_rutas = st.tabs(["📥 1. Lector de Facturas (XML)", "📓 2. Cuenta de Jeny (Oasis/Qualy)", "🗄️ 3. Historial General"])
    
    # --- PESTAÑA 1: SUBIR XML ---
    with tab_xml:
        st.markdown("Sube tu archivo `.xml` generado por la SAT para extraer automáticamente los productos.")
        
        archivo_xml = st.file_uploader("📂 Subir XML de Factura Electrónica (FEL)", type=["xml"])
        
        if archivo_xml is not None:
            try:
                xml_str = archivo_xml.getvalue().decode('utf-8', errors='ignore')
                xml_str = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_str) 
                xml_str = re.sub(r'<\w+:', '<', xml_str) 
                xml_str = re.sub(r'</\w+:', '</', xml_str) 
                
                root = ET.fromstring(xml_str)
                
                fecha_emision_elem = root.find('.//FechaHoraEmision')
                fecha_factura = fecha_emision_elem.text[:10] if fecha_emision_elem is not None else str(get_fecha_guate())
                
                receptor_elem = root.find('.//Receptor')
                cliente_nombre = receptor_elem.attrib.get('NombreReceptor', 'Cliente Generico') if receptor_elem is not None else "Cliente Generico"
                nit_cliente = receptor_elem.attrib.get('IDReceptor', 'CF') if receptor_elem is not None else "CF"
                
                st.markdown("---")
                st.markdown(f"### 🏢 Cliente: **{cliente_nombre}** (NIT: {nit_cliente})")
                st.markdown(f"📅 **Fecha de Emisión:** {pd.to_datetime(fecha_factura).strftime('%d/%m/%Y')}")
                
                lista_items = []
                for item in root.findall('.//Item'):
                    cantidad_elem = item.find('Cantidad')
                    desc_elem = item.find('Descripcion')
                    total_elem = item.find('Total')
                    
                    cant = float(cantidad_elem.text) if cantidad_elem is not None else 0.0
                    desc = desc_elem.text if desc_elem is not None else "Sin descripción"
                    tot = float(total_elem.text) if total_elem is not None else 0.0
                    
                    desc_low = desc.lower()
                    if 'pasta' in desc_low or 'pollo' in desc_low or 'taco' in desc_low:
                        categoria = "Pasta / Salado"
                    else:
                        categoria = "Pan / Repostería"
                        
                    lista_items.append({
                        "Cantidad": cant,
                        "Descripción": desc,
                        "Categoría": categoria,
                        "Total (Q)": tot
                    })
                    
                df_xml = pd.DataFrame(lista_items)
                
                if not df_xml.empty:
                    df_pan = df_xml[df_xml['Categoría'] == 'Pan / Repostería']
                    df_pasta = df_xml[df_xml['Categoría'] == 'Pasta / Salado']
                    
                    tot_pan = df_pan['Total (Q)'].sum()
                    tot_pasta = df_pasta['Total (Q)'].sum()
                    gran_total = df_xml['Total (Q)'].sum()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.success(f"🥐 **Total Pan/Repostería:** Q {tot_pan:,.2f}")
                        if not df_pan.empty:
                            st.dataframe(df_pan[['Cantidad', 'Descripción', 'Total (Q)']], use_container_width=True, hide_index=True)
                        else:
                            st.info("No se encontró pan en esta factura.")
                            
                    with col2:
                        st.warning(f"🍗 **Total Pasta/Salados:** Q {tot_pasta:,.2f}")
                        if not df_pasta.empty:
                            st.dataframe(df_pasta[['Cantidad', 'Descripción', 'Total (Q)']], use_container_width=True, hide_index=True)
                        else:
                            st.info("No se encontró pasta en esta factura.")
                    
                    st.markdown("---")
                    st.markdown(f"<h3 style='text-align: center; color: #2C3E50;'>Gran Total Facturado: Q {gran_total:,.2f}</h3>", unsafe_allow_html=True)
                    
                    if nit_cliente.replace("-", "") == "98133136" or "TIENDAS DE ORIENTE" in cliente_nombre or "OASIS" in cliente_nombre:
                        st.info("💡 **Sistema inteligente:** Se detectó la ruta de Tiendas de Oriente / Oasis. Al guardar, el total de Panadería (Q " + str(tot_pan) + ") se cargará automáticamente como deuda a la cuenta de Jeny.")
                    else:
                        st.success("⛽ **Venta al Contado:** Al guardar esta factura (Shell/Texaco/Otros), el total sumará automáticamente a tus ingresos en las Estadísticas.")
                        
                    if st.button("💾 Guardar Control de Ruta", type="primary", use_container_width=True):
                        try:
                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO control_rutas (fecha_factura, cliente, total_pan, total_pasta, gran_total)
                                    VALUES (:f, :c, :tpan, :tpasta, :gt)
                                """), {"f": fecha_factura, "c": cliente_nombre, "tpan": tot_pan, "tpasta": tot_pasta, "gt": gran_total})
                                
                                if nit_cliente.replace("-", "") == "98133136" or "TIENDAS DE ORIENTE" in cliente_nombre or "OASIS" in cliente_nombre:
                                    s.execute(text("""
                                        INSERT INTO cuenta_ruta_jeny (fecha, tipo, monto, detalle)
                                        VALUES (:f, 'CARGO', :m, :d)
                                    """), {"f": fecha_factura, "m": tot_pan, "d": f"Facturación de Pan - {cliente_nombre}"})
                                
                                s.commit()
                            st.success(f"✅ ¡Ruta de {cliente_nombre} guardada exitosamente!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"⚠️ Error al guardar. Revisa que creaste las tablas en Neon. Detalle: {e}")
                else:
                    st.warning("El XML parece estar vacío o no tiene el formato estándar de la SAT.")
                    
            except Exception as e:
                st.error(f"❌ Ocurrió un error al leer el XML. Detalles técnicos: {e}")

    # --- PESTAÑA 2: CUENTA CORRIENTE JENY ---
    with tab_cuenta:
        st.markdown("### 📓 Estado de Cuenta: Jeny (Oasis / Qualy / Tiendas de Oriente)")
        st.write("Aquí controlas las facturas acumuladas (Cargos) y los depósitos parciales que ella te hace (Abonos).")
        
        try:
            df_cuenta = conn.query("SELECT * FROM cuenta_ruta_jeny ORDER BY fecha ASC, id ASC", ttl=0)
            
            total_cargos = df_cuenta[df_cuenta['tipo'] == 'CARGO']['monto'].sum() if not df_cuenta.empty else 0.0
            total_abonos = df_cuenta[df_cuenta['tipo'] == 'ABONO']['monto'].sum() if not df_cuenta.empty else 0.0
            saldo_pendiente = total_cargos - total_abonos
            
            c1, c2, c3 = st.columns(3)
            c1.metric("📉 Total Facturado (Deuda)", f"Q {total_cargos:,.2f}")
            c2.metric("💵 Total Pagado (Abonos)", f"Q {total_abonos:,.2f}")
            c3.metric("⚖️ Saldo Pendiente por Cobrar", f"Q {saldo_pendiente:,.2f}")
            
            st.markdown("---")
            with st.expander("➕ Registrar un Nuevo Abono (Depósito de Jeny)"):
                with st.form("form_abono_jeny", clear_on_submit=True):
                    col_a1, col_a2, col_a3 = st.columns(3)
                    fecha_abono = col_a1.date_input("Fecha del Depósito", get_fecha_guate(), format="DD/MM/YYYY")
                    monto_abono = col_a2.number_input("Monto Recibido (Q)", min_value=0.00, step=100.00)
                    detalle_abono = col_a3.text_input("Nota / Ref. Depósito", placeholder="Ej. Depósito Banco Industrial")
                    
                    if st.form_submit_button("Guardar Abono"):
                        if monto_abono > 0:
                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO cuenta_ruta_jeny (fecha, tipo, monto, detalle)
                                    VALUES (:f, 'ABONO', :m, :d)
                                """), {"f": fecha_abono, "m": monto_abono, "d": detalle_abono})
                                s.commit()
                            st.success("✅ ¡Abono guardado! El dinero sumará automáticamente a tus estadísticas.")
                            st.rerun()
                        else:
                            st.warning("El monto debe ser mayor a cero.")
            
            st.markdown("#### 📜 Movimientos de la Cuenta")
            if not df_cuenta.empty:
                df_mostrar_cta = df_cuenta.copy()
                df_mostrar_cta['fecha'] = pd.to_datetime(df_mostrar_cta['fecha']).dt.strftime('%d/%m/%Y')
                
                st.dataframe(
                    df_mostrar_cta[['fecha', 'detalle', 'tipo', 'monto']],
                    column_config={
                        "fecha": "Fecha",
                        "detalle": "Concepto",
                        "tipo": "Tipo",
                        "monto": st.column_config.NumberColumn("Monto (Q)", format="Q %.2f")
                    },
                    hide_index=True, use_container_width=True
                )
            else:
                st.info("Aún no hay movimientos registrados en la cuenta de Jeny.")
                
        except Exception as e:
            st.error(f"⚠️ Esperando a que crees la tabla 'cuenta_ruta_jeny' en Neon. Detalle: {e}")

    # --- PESTAÑA 3: HISTORIAL RUTAS (NUEVA FUNCIÓN DE BORRADO) ---
    with tab_historial_rutas:
        st.markdown("### 🗄️ Historial de Rutas (Todos los clientes)")
        try:
            df_rutas_hist = conn.query("SELECT * FROM control_rutas ORDER BY fecha_factura DESC, id DESC LIMIT 50", ttl=0)
            if not df_rutas_hist.empty:
                df_mostrar_rutas = df_rutas_hist.copy()
                df_mostrar_rutas['fecha_factura'] = pd.to_datetime(df_mostrar_rutas['fecha_factura']).dt.strftime('%d/%m/%Y')
                
                st.dataframe(
                    df_mostrar_rutas[['fecha_factura', 'cliente', 'total_pan', 'total_pasta', 'gran_total']],
                    column_config={
                        "fecha_factura": "Fecha",
                        "cliente": "Cliente de Ruta",
                        "total_pan": st.column_config.NumberColumn("Total Pan (Q)", format="Q %.2f"),
                        "total_pasta": st.column_config.NumberColumn("Total Pasta (Q)", format="Q %.2f"),
                        "gran_total": st.column_config.NumberColumn("Total General (Q)", format="Q %.2f")
                    },
                    hide_index=True, use_container_width=True
                )
                
                # --- NUEVA FUNCIÓN PARA BORRAR FACTURAS EQUIVOCADAS ---
                st.markdown("---")
                st.markdown("#### 🗑️ Eliminar Factura Subida por Error")
                st.warning("⚠️ **Atención:** Si eliminas una factura de 'Tiendas de Oriente / Oasis', también se borrará automáticamente la deuda (cargo) que se había sumado a la cuenta de Jeny.")
                
                # Crear una lista legible para el selector
                opciones_borrar = df_rutas_hist.apply(
                    lambda row: f"ID: {row['id']} | Fecha: {pd.to_datetime(row['fecha_factura']).strftime('%d/%m/%Y')} | Cliente: {row['cliente']} | Total: Q {row['gran_total']}", 
                    axis=1
                ).tolist()
                
                ruta_a_borrar = st.selectbox("Selecciona la factura que deseas eliminar del sistema:", opciones_borrar)
                
                if st.button("🗑️ Eliminar Factura Seleccionada", type="secondary"):
                    # Extraer los datos reales del dataframe original basados en la selección
                    idx_seleccion = opciones_borrar.index(ruta_a_borrar)
                    datos_ruta = df_rutas_hist.iloc[idx_seleccion]
                    
                    ruta_id = int(datos_ruta['id'])
                    fecha_ruta = datos_ruta['fecha_factura']
                    monto_pan = float(datos_ruta['total_pan'])
                    cliente_ruta = datos_ruta['cliente']
                    
                    with conn.session as s:
                        # 1. Borrar de la tabla general de control de rutas
                        s.execute(text("DELETE FROM control_rutas WHERE id = :id"), {"id": ruta_id})
                        
                        # 2. Si es de Jeny/Oasis, buscar el CARGO exacto y borrarlo también
                        if "ORIENTE" in cliente_ruta.upper() or "OASIS" in cliente_ruta.upper() or "QUALY" in cliente_ruta.upper():
                            s.execute(text("""
                                DELETE FROM cuenta_ruta_jeny
                                WHERE tipo = 'CARGO'
                                  AND fecha = :f
                                  AND monto = :m
                                  AND detalle = :d
                            """), {"f": fecha_ruta, "m": monto_pan, "d": f"Facturación de Pan - {cliente_ruta}"})
                            
                        s.commit()
                        
                    st.success("✅ ¡Factura (y su deuda, si aplicaba) eliminada correctamente del sistema!")
                    st.rerun()
                    
            else:
                st.info("No hay rutas guardadas todavía.")
        except Exception as e:
            st.caption(f"Crea la tabla 'control_rutas' en Neon para ver el historial. Detalle: {e}")

# ------------------------------------------
# (OTROS MÓDULOS SE MANTIENEN INTACTOS, RESUMIDOS AQUÍ POR ESPACIO)
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
    gastos_editados = st.data_editor(st.session_state.gastos_df, column_config={"Categoría": st.column_config.SelectboxColumn("Tipo de Gasto (Automático)", options=lista_categorias, required=False), "Detalle": st.column_config.TextColumn("Detalle del gasto"), "Monto (Q)": st.column_config.NumberColumn("Total (Q)", min_value=0.0, format="Q %.2f")}, num_rows="dynamic", use_container_width=True, key=f"tabla_gastos_{st.session_state.reset_key}")
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
    with col_btn1: btn_guardar = st.button("💾 Guardar Corte Completo", type="primary", use_container_width=True)
    with col_btn2: btn_limpiar = st.button("🧹 Limpiar / Nuevo Corte", type="secondary", use_container_width=True)
    if btn_limpiar:
        df_limpio = pd.DataFrame(columns=["Categoría", "Detalle", "Monto (Q)"])
        for _ in range(11): df_limpio.loc[len(df_limpio)] = [None, "", 0.0]
        st.session_state.gastos_df = df_limpio
        st.session_state.reset_key += 1
        st.rerun()
    if btn_guardar:
        if total_ingresos_bruto > 0 or total_gastos_calc > 0:
            corte_id = obtener_o_crear_corte(fecha_corte)
            ruta_id = df_rutas.loc[df_rutas['nombre'] == local_ruta, 'id'].values[0]
            with conn.session as s:
                if total_ingresos_bruto > 0:
                    s.execute(text("INSERT INTO ingresos (corte_id, ruta_id, venta_total, credito_pagado, transferencias) VALUES (:c, :r, :v, :cp, :t)"), {"c": corte_id, "r": int(ruta_id), "v": venta_mostrador, "cp": pago_pedidos, "t": transferencias})
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
                            s.execute(text("INSERT INTO gastos (corte_id, categoria_id, detalle, monto) VALUES (:c, :cat, :d, :m)"), {"c": corte_id, "cat": int(cat_id), "d": detalle, "m": monto})
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
        else: st.warning("⚠️ Debes ingresar al menos una venta o un gasto para guardar.")
    if 'pdf_generado' in st.session_state:
        st.markdown("---")
        st.download_button(label="📥 Descargar PDF del Corte para Imprimir", data=st.session_state['pdf_generado'], file_name=st.session_state['pdf_nombre'], mime="application/pdf", type="secondary", use_container_width=True)

elif opcion_menu == "📅 Historial de Cortes":
    st.title("📅 Consulta de Historial e Impresión")
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
            ruta_nombre = ingresos_hist.iloc[0]['ruta'] if not ingresos_hist.empty else "LOCAL MERCADO"
            df_para_pdf = pd.DataFrame({"Categoría": gastos_hist['categoria'] if not gastos_hist.empty else [], "Detalle": gastos_hist['detalle'] if not gastos_hist.empty else [], "Monto (Q)": gastos_hist['monto'] if not gastos_hist.empty else []})
            pdf_historico = generar_pdf_corte(fecha_consulta.strftime('%d/%m/%Y'), ruta_nombre, "Histórico", df_para_pdf, sum_venta, sum_pedidos, sum_transferencias)
            st.download_button(label=f"📥 Descargar PDF del {fecha_consulta.strftime('%d/%m/%Y')} para Imprimir", data=pdf_historico, file_name=f"Corte_{fecha_consulta.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
            col_t1, col_t2 = st.columns(2)
            with col_t1: st.subheader("💰 Desglose de Ingresos"); st.dataframe(ingresos_hist, use_container_width=True, hide_index=True) if not ingresos_hist.empty else st.info("No se registraron ingresos este día.")
            with col_t2: st.subheader("💸 Desglose de Gastos"); st.dataframe(gastos_hist, use_container_width=True, hide_index=True) if not gastos_hist.empty else st.info("No se registraron gastos este día.")
        else: st.warning(f"No hay ningún corte guardado en el sistema para la fecha {fecha_consulta.strftime('%d/%m/%Y')}.")
    except Exception as e: st.error("Error al consultar el historial.")

elif opcion_menu == "📈 Estadísticas":
    st.title("📈 Estadísticas y Finanzas")
    meses_dict = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
    hoy = get_fecha_guate()
    nombre_mes_actual = list(meses_dict.keys())[list(meses_dict.values()).index(hoy.month)]
    col_f1, col_f2 = st.columns(2)
    mes_seleccionado = col_f1.selectbox("Selecciona el Mes", list(meses_dict.keys()), index=list(meses_dict.keys()).index(nombre_mes_actual))
    anio_seleccionado = col_f2.selectbox("Selecciona el Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1)
    mes_num = meses_dict[mes_seleccionado]
    try:
        query_gastos = """SELECT c.nombre as categoria, SUM(g.monto) as total FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id JOIN cortes_diarios cd ON g.corte_id = cd.id WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio GROUP BY c.nombre"""
        gastos_totales = conn.query(query_gastos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_ingresos = """SELECT SUM(i.venta_total + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as total_ingresos FROM ingresos i JOIN cortes_diarios cd ON i.corte_id = cd.id WHERE EXTRACT(MONTH FROM cd.fecha) = :mes AND EXTRACT(YEAR FROM cd.fecha) = :anio"""
        ingresos_totales = conn.query(query_ingresos, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_jeny = """SELECT SUM(monto) as abonos FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND EXTRACT(MONTH FROM fecha) = :mes AND EXTRACT(YEAR FROM fecha) = :anio"""
        jeny_totales = conn.query(query_jeny, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)
        query_rutas = """SELECT SUM(gran_total) as rutas_contado FROM control_rutas WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND EXTRACT(MONTH FROM fecha_factura) = :mes AND EXTRACT(YEAR FROM fecha_factura) = :anio"""
        rutas_totales = conn.query(query_rutas, params={"mes": mes_num, "anio": anio_seleccionado}, ttl=0)

        total_g = gastos_totales['total'].sum() if not gastos_totales.empty else 0.0
        ing_caja = float(ingresos_totales.iloc[0]['total_ingresos']) if not ingresos_totales.empty and pd.notna(ingresos_totales.iloc[0]['total_ingresos']) else 0.0
        ing_jeny = float(jeny_totales.iloc[0]['abonos']) if not jeny_totales.empty and pd.notna(jeny_totales.iloc[0]['abonos']) else 0.0
        ing_rutas = float(rutas_totales.iloc[0]['rutas_contado']) if not rutas_totales.empty and pd.notna(rutas_totales.iloc[0]['rutas_contado']) else 0.0
        
        total_i = ing_caja + ing_jeny + ing_rutas
        utilidad = total_i - total_g
        
        st.markdown("---")
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric(f"💵 Ingresos Globales ({mes_seleccionado})", f"Q {total_i:,.2f}")
        col_s2.metric(f"📉 Gastos Globales ({mes_seleccionado})", f"Q {total_g:,.2f}")
        col_s3.metric(f"⚖️ Utilidad Bruta", f"Q {utilidad:,.2f}")
        st.caption(f"**Desglose Ingresos:** Caja Diaria (Q {ing_caja:,.2f}) + Abonos Jeny (Q {ing_jeny:,.2f}) + Rutas Contado (Q {ing_rutas:,.2f})")
        st.markdown("---")
        if not gastos_totales.empty and total_g > 0:
            fig = px.pie(gastos_totales, values='total', names='categoria', hole=0.4, title=f"Distribución de Gastos - {mes_seleccionado} {anio_seleccionado}"); st.plotly_chart(fig, use_container_width=True)
        else: st.info(f"📊 No hay gastos registrados para el mes de {mes_seleccionado} {anio_seleccionado}.")
    except Exception as e: st.error(f"Error al cargar las estadísticas: {e}")

elif opcion_menu == "📆 Comparativa Diaria":
    st.title("📆 Comparativa de Ingresos vs Gastos por Día")
    hoy = get_fecha_guate()
    primer_dia_mes = hoy.replace(day=1)
    col_d1, col_d2 = st.columns(2)
    fecha_inicio_comp = col_d1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY")
    fecha_fin_comp = col_d2.date_input("Hasta:", hoy, format="DD/MM/YYYY")
    if st.button("🔍 Consultar Días", type="primary"):
        with st.spinner("Cargando los datos día por día..."):
            try:
                q_ing_full = """
                    SELECT fecha, SUM(monto) as ingresos FROM (
                        SELECT cd.fecha, (COALESCE(i.venta_total, 0) + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as monto
                        FROM cortes_diarios cd LEFT JOIN ingresos i ON cd.id = i.corte_id
                        WHERE cd.fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha, monto FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha_factura as fecha, gran_total as monto FROM control_rutas
                        WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND fecha_factura BETWEEN :inicio AND :fin
                    ) sub GROUP BY fecha
                """
                df_ing = conn.query(q_ing_full, params={"inicio": fecha_inicio_comp, "fin": fecha_fin_comp}, ttl=0)
                q_gas = """SELECT cd.fecha, SUM(COALESCE(g.monto, 0)) as gastos FROM cortes_diarios cd LEFT JOIN gastos g ON cd.id = g.corte_id WHERE cd.fecha BETWEEN :inicio AND :fin GROUP BY cd.fecha"""
                df_gas = conn.query(q_gas, params={"inicio": fecha_inicio_comp, "fin": fecha_fin_comp}, ttl=0)
                
                if df_ing.empty and df_gas.empty: st.warning("No hay registros en esas fechas.")
                else:
                    df_resumen = pd.merge(df_ing, df_gas, on='fecha', how='outer').fillna(0)
                    df_resumen['fecha'] = pd.to_datetime(df_resumen['fecha']).dt.date
                    df_resumen = df_resumen.sort_values('fecha')
                    df_resumen['utilidad'] = df_resumen['ingresos'] - df_resumen['gastos']
                    t_ing = df_resumen['ingresos'].sum(); t_gas = df_resumen['gastos'].sum(); t_uti = df_resumen['utilidad'].sum()
                    
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("💰 Total Ingresos del Rango", f"Q {t_ing:,.2f}")
                    c2.metric("📉 Total Gastos del Rango", f"Q {t_gas:,.2f}")
                    c3.metric("⚖️ Utilidad del Rango", f"Q {t_uti:,.2f}")
                    st.markdown("---")
                    
                    df_graf = df_resumen[['fecha', 'ingresos', 'gastos']].melt(id_vars='fecha', var_name='Tipo', value_name='Monto')
                    fig = px.bar(df_graf, x='fecha', y='Monto', color='Tipo', barmode='group', color_discrete_map={'ingresos': '#27AE60', 'gastos': '#E74C3C'})
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df_resumen, column_config={"fecha": st.column_config.DateColumn("Fecha del Corte", format="DD/MM/YYYY"), "ingresos": st.column_config.NumberColumn("Total Ingresos (Global)", format="Q %.2f"), "gastos": st.column_config.NumberColumn("Total Gastos", format="Q %.2f"), "utilidad": st.column_config.NumberColumn("Utilidad Neta", format="Q %.2f")}, hide_index=True, use_container_width=True)
                    pdf_comparativa = generar_pdf_comparativa_diaria(fecha_inicio_comp, fecha_fin_comp, df_resumen, t_ing, t_gas, t_uti)
                    st.download_button(label="📥 Descargar Comparativa en PDF", data=pdf_comparativa, file_name=f"Comparativa_Diaria_{fecha_inicio_comp.strftime('%d-%m-%Y')}_al_{fecha_fin_comp.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
            except Exception as e: st.error(f"Error al cargar la comparativa: {e}")

elif opcion_menu == "🏆 Días Estrella":
    st.title("🏆 Días Estrella (Rendimiento Semanal)")
    hoy = get_fecha_guate()
    primer_dia_mes = hoy.replace(day=1)
    col_d1, col_d2 = st.columns(2)
    fecha_inicio_est = col_d1.date_input("Desde:", primer_dia_mes, format="DD/MM/YYYY", key="fecha_est_1")
    fecha_fin_est = col_d2.date_input("Hasta:", hoy, format="DD/MM/YYYY", key="fecha_est_2")

    if st.button("📊 Analizar Días", type="primary"):
        with st.spinner("Buscando el mejor día..."):
            try:
                q_ing_full = """
                    SELECT fecha, SUM(monto) as ingresos FROM (
                        SELECT cd.fecha, (COALESCE(i.venta_total, 0) + COALESCE(i.credito_pagado, 0) + COALESCE(i.transferencias, 0)) as monto
                        FROM cortes_diarios cd LEFT JOIN ingresos i ON cd.id = i.corte_id
                        WHERE cd.fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha, monto FROM cuenta_ruta_jeny WHERE tipo = 'ABONO' AND fecha BETWEEN :inicio AND :fin
                        UNION ALL
                        SELECT fecha_factura as fecha, gran_total as monto FROM control_rutas
                        WHERE cliente NOT ILIKE '%ORIENTE%' AND cliente NOT ILIKE '%OASIS%' AND cliente NOT ILIKE '%QUALY%' AND fecha_factura BETWEEN :inicio AND :fin
                    ) sub GROUP BY fecha
                """
                df_ing_dias = conn.query(q_ing_full, params={"inicio": fecha_inicio_est, "fin": fecha_fin_est}, ttl=0)

                if df_ing_dias.empty or df_ing_dias['ingresos'].sum() == 0: st.warning("No hay ventas registradas en ese rango para hacer el análisis.")
                else:
                    dias_espanol = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
                    df_ing_dias['fecha'] = pd.to_datetime(df_ing_dias['fecha'])
                    df_ing_dias['nombre_dia'] = df_ing_dias['fecha'].dt.day_name().map(dias_espanol)
                    df_agrupado = df_ing_dias.groupby('nombre_dia', as_index=False)['ingresos'].mean(); df_agrupado = df_agrupado.rename(columns={'ingresos': 'promedio_ventas'})
                    orden_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']; df_agrupado['nombre_dia'] = pd.Categorical(df_agrupado['nombre_dia'], categories=orden_dias, ordered=True); df_agrupado = df_agrupado.sort_values('nombre_dia')
                    mejor_dia_nombre = df_agrupado.loc[df_agrupado['promedio_ventas'].idxmax()]['nombre_dia']; peor_dia_nombre = df_agrupado.loc[df_agrupado['promedio_ventas'].idxmin()]['nombre_dia']; promedio_general = df_ing_dias['ingresos'].mean(); dia_record = df_ing_dias.loc[df_ing_dias['ingresos'].idxmax()]
                    st.markdown("---"); col1, col2, col3, col4 = st.columns(4)
                    col1.metric("🔥 Mejor Día de la Semana", str(mejor_dia_nombre)); col2.metric("💤 Día más Flojo", str(peor_dia_nombre)); col3.metric("📊 Venta Promedio Diaria", f"Q {promedio_general:,.2f}"); col4.metric("👑 Día Récord (Fecha Exacta)", f"{dia_record['fecha'].strftime('%d/%m/%Y')}", f"Q {dia_record['ingresos']:,.2f}")
                    fig = px.bar(df_agrupado, x='nombre_dia', y='promedio_ventas', labels={'nombre_dia': 'Día de la Semana', 'promedio_ventas': 'Promedio Vendido (Q)'}, color='promedio_ventas', color_continuous_scale=px.colors.sequential.Viridis); st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(df_agrupado, column_config={"nombre_dia": "Día de la Semana", "promedio_ventas": st.column_config.NumberColumn("Promedio de Ingresos", format="Q %.2f")}, hide_index=True, use_container_width=True)
                    pdf_estrellas = generar_pdf_dias_estrella(fecha_inicio_est, fecha_fin_est, df_agrupado, mejor_dia_nombre, peor_dia_nombre, promedio_general, dia_record)
                    st.download_button(label="📥 Descargar Análisis en PDF", data=pdf_estrellas, file_name=f"Dias_Estrella_{fecha_inicio_est.strftime('%d-%m-%Y')}_al_{fecha_fin_est.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
            except Exception as e: st.error(f"Error al cargar el análisis: {e}")

elif opcion_menu == "💳 Proveedores":
    st.title("💳 Control de Créditos y Proveedores")
    try:
        tab_prov1, tab_prov2, tab_prov3 = st.tabs(["📋 Gestionar Proveedores", "➕ Registrar Deuda", "🚨 Deudas Activas"])
        with tab_prov1:
            with st.expander("➕ Agregar un Nuevo Proveedor"):
                with st.form("form_nuevo_proveedor", clear_on_submit=True):
                    nuevo_nombre = st.text_input("Nombre del Proveedor"); nuevo_producto = st.text_input("Producto o Servicio")
                    if st.form_submit_button("Guardar Proveedor") and nuevo_nombre:
                        with conn.session as s: s.execute(text("INSERT INTO proveedores (nombre, producto_servicio) VALUES (:n, :p)"), {"n": nuevo_nombre, "p": nuevo_producto}); s.commit()
                        st.success(f"✅ ¡Proveedor agregado!"); st.rerun()
            df_prov_edit = conn.query("SELECT id, nombre, producto_servicio FROM proveedores ORDER BY id", ttl=0)
            if not df_prov_edit.empty:
                proveedores_editados = st.data_editor(df_prov_edit, column_config={"id": st.column_config.NumberColumn("ID", disabled=True)}, hide_index=True, use_container_width=True)
                if st.button("💾 Guardar Cambios en Proveedores", type="primary"):
                    with conn.session as s:
                        for index, row in proveedores_editados.iterrows(): s.execute(text("UPDATE proveedores SET nombre = :nombre, producto_servicio = :prod WHERE id = :id"), {"nombre": row["nombre"], "prod": row["producto_servicio"], "id": int(row["id"])})
                        s.commit()
                    st.success("✅ ¡Proveedores actualizados!"); st.rerun()
                prov_a_borrar = st.selectbox("Selecciona para eliminar:", df_prov_edit['nombre'])
                if st.button("Eliminar Proveedor Seleccionado"):
                    id_borrar = df_prov_edit.loc[df_prov_edit['nombre'] == prov_a_borrar, 'id'].values[0]
                    with conn.session as s: s.execute(text("DELETE FROM cuentas_por_pagar WHERE proveedor_id = :id"), {"id": int(id_borrar)}); s.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": int(id_borrar)}); s.commit()
                    st.success("🗑️ Proveedor eliminado."); st.rerun()
        with tab_prov2:
            df_proveedores = conn.query("SELECT id, nombre FROM proveedores ORDER BY nombre", ttl=0)
            if not df_proveedores.empty:
                with st.form("form_credito", clear_on_submit=True):
                    prov = st.selectbox("Proveedor", df_proveedores['nombre']); num_factura = st.text_input("📄 No. de Factura/Doc"); monto_credito = st.number_input("Monto total (Q)", min_value=0.00, step=100.00); fecha_vencimiento = st.date_input("¿Cuándo toca pagar?", get_fecha_guate(), format="DD/MM/YYYY")
                    if st.form_submit_button("Guardar Deuda"):
                        prov_id = df_proveedores.loc[df_proveedores['nombre'] == prov, 'id'].values[0]
                        with conn.session as s: s.execute(text("INSERT INTO cuentas_por_pagar (proveedor_id, num_documento, fecha_compra, fecha_vencimiento, monto_total, saldo_pendiente) VALUES (:p, :doc, :f_compra, :f_vence, :monto, :saldo)"), {"p": int(prov_id), "doc": num_factura, "f_compra": get_fecha_guate(), "f_vence": fecha_vencimiento, "monto": monto_credito, "saldo": monto_credito}); s.commit()
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
    except Exception as e: st.error(f"Error: {e}")

elif opcion_menu == "👨‍🍳 Planilla Panaderos":
    st.title("👨‍🍳 Control de Producción y Recibos")
    tab_planilla, tab_recibo, tab_historial_recibos = st.tabs(["📝 1. Calcular Planilla (Detalle)", "🧾 2. Emitir Recibo de Pago", "🗄️ 3. Historial de Recibos"])
    with tab_planilla:
        col_p1, col_p2, col_p3 = st.columns(3)
        panadero_nombre = col_p1.selectbox("Nombre del Panadero", ["Jorge", "Otro"])
        fecha_inicio_plan = col_p2.date_input("Semana del:", get_fecha_guate() - pd.Timedelta(days=6), format="DD/MM/YYYY")
        fecha_fin_plan = col_p3.date_input("Al:", get_fecha_guate(), format="DD/MM/YYYY")
        productos_base = ["MEXICANA", "CONCHA", "CORONA", "GUANABA", "PAN INDIO", "PAN AZUCARADO", "BESITO", "PITUFO", "GUSANITO", "SAN ANTONIO", "PIRUJO", "TOSTADO REDONDO", "TOSTADO LARGO", "PESCADITO", "HOJITA", "PASTELITO", "CORTADA BLANCA", "CORTADA ROJA", "ROSQUITA", "ROYALITO", "CHURRO", "LENGUA", "CORTADA CANELA", "CORTADA FRESA", "HARINADO OFERTA", "CHAMUCO", "TOSTADO OFERTA", "CUBILETE OFERTA", "CONCHA OFERTA", "MEXICANA OFERTA", "PIQUIADA", "CHAMPU 2 SABORES", "POLVOROSAS", "CHAMPURRADAS", "ROYAL", "PAN ANTONIO", "OTROS"]
        if 'planilla_df' not in st.session_state:
            df_base = pd.DataFrame({"Producto": productos_base})
            for dia in ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']: df_base[dia] = 0.00
            df_base['Libras Pasta'] = 0.00
            st.session_state.planilla_df = df_base
        col_b1, col_b2 = st.columns(2)
        if col_b1.button("Guardar Avance (Borrador)", use_container_width=True):
            try:
                with conn.session as s: s.execute(text("INSERT INTO borrador_planilla (id, datos) VALUES (1, :d) ON CONFLICT (id) DO UPDATE SET datos = :d"), {"d": st.session_state.planilla_df.to_json(orient='records')}); s.commit()
                st.success("¡Avance guardado a salvo en la base de datos!")
            except Exception as e: st.error("⚠️ Falta crear la tabla borrador_planilla.")
        if col_b2.button("Recuperar Avance Guardado", use_container_width=True):
            try:
                with conn.session as s:
                    resultado = s.execute(text("SELECT datos FROM borrador_planilla WHERE id = 1")).fetchone()
                    if resultado and resultado[0]: st.session_state.planilla_df = pd.read_json(io.StringIO(resultado[0]), orient='records'); st.success("Avance recuperado con éxito."); st.rerun()
            except Exception as e: st.error("⚠️ Falta crear la tabla borrador_planilla.")
        config_columnas = {"Producto": st.column_config.TextColumn("🍞 Producto", disabled=True)}
        for d in ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo', 'Libras Pasta']: config_columnas[d] = st.column_config.NumberColumn(d, min_value=0.0, format="%.2f")
        planilla_editada = st.data_editor(st.session_state.planilla_df, hide_index=True, column_config=config_columnas, use_container_width=True, height=600)
        st.session_state.planilla_df = planilla_editada
        st.markdown("### 🧮 Subtotal de Producción")
        col_pago, col_vacio = st.columns([1, 3])
        precio_quintal = col_pago.number_input("Pago por Quintal (Q)", min_value=0.00, value=135.00, step=5.00)
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        total_libras_masa = planilla_editada[dias_semana].sum().sum(); total_quintales_masa = total_libras_masa / 100; total_libras_pasta = planilla_editada['Libras Pasta'].sum(); total_quintales_pasta = total_libras_pasta / 100; gran_total_quintales = total_quintales_masa + total_quintales_pasta; pago_total_quincena = gran_total_quintales * precio_quintal
        c_res1, c_res2, c_res3, c_res4 = st.columns(4); c_res1.metric("⚖️ Libras Masa", f"{total_libras_masa:.2f}", f"{total_quintales_masa:.2f} QQ"); c_res2.metric("🧈 Libras Pasta", f"{total_libras_pasta:.2f}", f"{total_quintales_pasta:.2f} QQ"); c_res3.metric("📦 Gran Total", f"{gran_total_quintales:.2f} QQ"); c_res4.metric("💵 Subtotal Base", f"Q {pago_total_quincena:,.2f}")
        if st.button("📥 Descargar Detalle de Planilla PDF", type="primary"):
            if gran_total_quintales > 0:
                pdf_planilla = generar_pdf_planilla(panadero_nombre, fecha_inicio_plan, fecha_fin_plan, planilla_editada, total_libras_masa, total_quintales_masa, total_libras_pasta, total_quintales_pasta, gran_total_quintales, precio_quintal, pago_total_quincena)
                st.download_button(label="Descargar Reporte Horizontal", data=pdf_planilla, file_name=f"Detalle_Planilla_{panadero_nombre}_{fecha_fin_plan.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
    with tab_recibo:
        st.markdown("### 🧾 Generar Recibo de Pago")
        col_r1, col_r2 = st.columns(2)
        numero_recibo = col_r1.text_input("No. de Recibo", value="25"); fecha_emision_recibo = col_r2.date_input("Fecha de Emisión", get_fecha_guate(), format="DD/MM/YYYY")
        col_e1, col_e2, col_e3 = st.columns(3)
        septimo_val = col_e1.number_input("➕ Séptimo (Q)", min_value=0.00, value=0.00, step=10.00); tortas_val = col_e2.number_input("➕ Tortas (Q)", min_value=0.00, value=0.00, step=10.00); tienda_val = col_e3.number_input("➖ Deducción Tienda (Q)", min_value=0.00, value=0.00, step=10.00)
        total_final_pagar = pago_total_quincena + septimo_val + tortas_val - tienda_val
        st.markdown(f"<h3 style='text-align: center; color: #27AE60;'>Total a Pagar: Q {total_final_pagar:,.2f}</h3>", unsafe_allow_html=True)
        if st.button("💾 Guardar y Emitir Recibo Oficial", type="primary", use_container_width=True):
            if total_final_pagar > 0:
                try:
                    with conn.session as s:
                        s.execute(text("INSERT INTO recibos_panaderos (panadero, fecha_inicio, fecha_fin, num_recibo, fecha_emision, gran_total_qq, precio_qq, subtotal, septimo, tortas, tienda, total_pagar) VALUES (:p, :fi, :ff, :nr, :fe, :gqq, :pqq, :sub, :sep, :tor, :tie, :tot)"), {"p": panadero_nombre, "fi": fecha_inicio_plan, "ff": fecha_fin_plan, "nr": numero_recibo, "fe": fecha_emision_recibo, "gqq": gran_total_quintales, "pqq": precio_quintal, "sub": pago_total_quincena, "sep": septimo_val, "tor": tortas_val, "tie": tienda_val, "tot": total_final_pagar}); s.commit()
                    pdf_recibo = generar_pdf_recibo(numero_recibo, fecha_emision_recibo, panadero_nombre, fecha_inicio_plan, fecha_fin_plan, gran_total_quintales, precio_quintal, pago_total_quincena, septimo_val, tortas_val, tienda_val, total_final_pagar)
                    st.success("✅ ¡Recibo guardado en el historial y listo para imprimir!")
                    st.download_button(label="📥 Descargar Recibo para Firma", data=pdf_recibo, file_name=f"Recibo_Pago_{panadero_nombre}_{numero_recibo}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
                except Exception as e: st.error(f"⚠️ Error: {e}")
    with tab_historial_recibos:
        st.markdown("### 🗄️ Historial de Recibos Emitidos")
        try:
            df_recibos = conn.query("SELECT * FROM recibos_panaderos ORDER BY id DESC", ttl=0)
            if not df_recibos.empty:
                df_mostrar = df_recibos.copy(); df_mostrar['fecha_emision'] = pd.to_datetime(df_mostrar['fecha_emision']).dt.strftime('%d/%m/%Y')
                st.dataframe(df_mostrar[['num_recibo', 'panadero', 'fecha_emision', 'gran_total_qq', 'total_pagar']], column_config={"num_recibo": "No. Recibo", "panadero": "Panadero", "fecha_emision": "Emitido El", "gran_total_qq": "Total QQ", "total_pagar": st.column_config.NumberColumn("Total Pagado", format="Q %.2f")}, use_container_width=True, hide_index=True)
                opciones_recibo = df_recibos.apply(lambda row: f"Recibo {row['num_recibo']} - {row['panadero']} (Q {row['total_pagar']})", axis=1).tolist(); recibo_seleccionado = st.selectbox("Selecciona el recibo que deseas descargar de nuevo:", opciones_recibo)
                if st.button("📥 Reimprimir este Recibo", type="secondary"):
                    idx_seleccion = opciones_recibo.index(recibo_seleccionado); datos_recibo = df_recibos.iloc[idx_seleccion]
                    pdf_reimpresion = generar_pdf_recibo(datos_recibo['num_recibo'], pd.to_datetime(datos_recibo['fecha_emision']).date(), datos_recibo['panadero'], pd.to_datetime(datos_recibo['fecha_inicio']).date(), pd.to_datetime(datos_recibo['fecha_fin']).date(), datos_recibo['gran_total_qq'], datos_recibo['precio_qq'], datos_recibo['subtotal'], datos_recibo['septimo'], datos_recibo['tortas'], datos_recibo['tienda'], datos_recibo['total_pagar'])
                    st.download_button(label="Descargar Archivo PDF", data=pdf_reimpresion, file_name=f"Reimpresion_Recibo_{datos_recibo['panadero']}_{datos_recibo['num_recibo']}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        except Exception as e: st.error(f"⚠️ Error de base de datos: {e}")

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

                if (not ingresos_df.empty and ingresos_df['efectivo'].sum() > 0) or not gastos_cat_df.empty or ing_jeny > 0 or ing_rutas > 0:
                    buffer_pdf = generar_pdf_reporte_mensual(fecha_inicio, fecha_fin, ingresos_df, gastos_cat_df, gastos_det_df, ing_jeny, ing_rutas)
                    st.success("✅ ¡Tu Reporte Gerencial ha sido generado con éxito!")
                    st.download_button(label="📥 Descargar Reporte PDF", data=buffer_pdf, file_name=f"Reporte_Panaderia_{fecha_inicio.strftime('%d-%m-%Y')}_al_{fecha_fin.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
                else: st.warning(f"⚠️ No se encontraron registros de ventas ni gastos entre el {fecha_inicio.strftime('%d/%m/%Y')} y el {fecha_fin.strftime('%d/%m/%Y')}.")
            except Exception as e: st.error(f"Error al generar el reporte: {e}")
