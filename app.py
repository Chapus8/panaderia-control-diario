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

# -- FUNCIONES PDF --
def generar_pdf_corte(fecha_str, local_str, responsable_str, df_gastos, venta_efectivo, pago_pedidos, transferencias):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); bold_style = ParagraphStyle('BoldStyle', parent=styles['Normal'], fontSize=10, fontName="Helvetica-Bold")
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style)); elements.append(Paragraph("INTEGRACIÓN DE INGRESOS Y EGRESOS - CORTE DE CAJA", subtitle_style)); elements.append(Spacer(1, 15))
    info_data = [[Paragraph(f"<b>Fecha:</b> {fecha_str}", bold_style), Paragraph(f"<b>Local / Ruta:</b> {local_str}", bold_style), Paragraph(f"<b>Responsable:</b> {responsable_str}", bold_style)]]
    info_table = Table(info_data, colWidths=[150, 200, 190]); info_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EAFAF1")), ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#27AE60")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 6)])); elements.append(info_table); elements.append(Spacer(1, 15))
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

def generar_pdf_reporte_mensual(f_inicio, f_fin, ingresos_df, gastos_cat_df, gastos_det_df, v_abonos_jeny, v_otras_rutas):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
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
    t_resumen = Table(resumen_data, colWidths=[140, 90, 190, 100]); t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (1,0), colors.HexColor("#27AE60")), ('BACKGROUND', (2,0), (3,0), colors.HexColor("#E74C3C")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('ALIGN', (3,0), (3,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,-1), (1,-1), colors.HexColor("#D4EFDF")), ('FONTNAME', (0,-1), (1,-1), 'Helvetica-Bold'), ('BACKGROUND', (2,3), (3,3), colors.HexColor("#FADBD8")), ('FONTNAME', (2,3), (3,3), 'Helvetica-Bold')])); elements.append(t_resumen); elements.append(Spacer(1, 20))
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
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
    elements.append(Paragraph("<b>PANADERÍA Y REPOSTERÍA JUDITH</b>", title_style)); elements.append(Paragraph(f"REPORTE COMPARATIVO DIARIO (INCLUYE RUTAS Y ABONOS): {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}", subtitle_style)); elements.append(Spacer(1, 15))
    resumen_data = [["TOTAL INGRESOS GLOBAL", "TOTAL GASTOS", "UTILIDAD NETA"], [f"Q {t_ing:,.2f}", f"Q {t_gas:,.2f}", f"Q {t_uti:,.2f}"]]; t_resumen = Table(resumen_data, colWidths=[150, 150, 150]); t_resumen.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0,0), (-1,0), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_resumen); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Gráfica Comparativa: Ingresos vs Gastos</b>", h2_style)); d = Drawing(480, 200); bc = VerticalBarChart(); bc.x = 40; bc.y = 40; bc.height = 140; bc.width = 420; bc.data = [df_resumen['ingresos'].tolist(), df_resumen['gastos'].tolist()]; bc.strokeColor = colors.white; bc.valueAxis.valueMin = 0; bc.categoryAxis.categoryNames = [fecha.strftime('%d/%m') for fecha in df_resumen['fecha']]; bc.categoryAxis.labels.angle = 45; bc.categoryAxis.labels.dy = -10; bc.categoryAxis.labels.fontSize = 8; bc.bars[0].fillColor = colors.HexColor("#27AE60"); bc.bars[1].fillColor = colors.HexColor("#E74C3C")
    leg = Legend(); leg.x = 350; leg.y = 180; leg.alignment = 'right'; leg.colorNamePairs = [(colors.HexColor("#27AE60"), 'Total Ingresos'), (colors.HexColor("#E74C3C"), 'Total Gastos')]; leg.fontSize = 8; leg.boxAnchor = 'nw'; d.add(bc); d.add(leg); elements.append(d); elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>Detalle Diario de Movimientos</b>", h2_style)); det_data = [["FECHA", "TOTAL INGRESOS", "TOTAL GASTOS", "UTILIDAD NETA"]]
    for index, row in df_resumen.iterrows(): det_data.append([row['fecha'].strftime('%d/%m/%Y'), f"Q {row['ingresos']:,.2f}", f"Q {row['gastos']:,.2f}", f"Q {row['utilidad']:,.2f}"])
    t_det = Table(det_data, colWidths=[120, 120, 120, 120]); t_det.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#34495E")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('ALIGN', (0,0), (0,-1), 'CENTER'), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey)])); elements.append(t_det); doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_dias_estrella(f_inicio, f_fin, df_agrupado, mejor_dia, peor_dia, prom_gral, dia_record):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36); elements = []; styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor("#2C3E50")); subtitle_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, alignment=1, textColor=colors.gray); h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#2980B9"), spaceAfter=10)
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
# MÓDULO: 🚚 RUTA Y PEDIDOS (XML) CON SELECCIÓN DE SUCURSAL
# ------------------------------------------
if opcion_menu == "🚚 Ruta y Pedidos (XML)":
    st.title("🚚 Control de Ruta y Pedidos (Lector SAT)")
    
    tab_xml, tab_cuenta, tab_historial_rutas, tab_estadisticas_rutas = st.tabs([
        "📥 1. Lector de Facturas (XML)", 
        "📓 2. Cuenta de Jeny (Oasis/Qualy)", 
        "🗄️ 3. Historial General",
        "📊 4. Estadísticas por Sucursal"
    ])
    
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
                cliente_nombre_sat = receptor_elem.attrib.get('NombreReceptor', 'Cliente Generico') if receptor_elem is not None else "Cliente Generico"
                nit_cliente = receptor_elem.attrib.get('IDReceptor', 'CF') if receptor_elem is not None else "CF"
                
                st.markdown("---")
                st.markdown(f"### 🏢 Facturado a: **{cliente_nombre_sat}** (NIT: {nit_cliente})")
                st.markdown(f"📅 **Fecha de Emisión:** {pd.to_datetime(fecha_factura).strftime('%d/%m/%Y')}")
                
                # --- ASIGNACIÓN DE SUCURSAL INTELIGENTE ---
                st.markdown("#### 📍 Identificación de Sucursal / Destino")
                es_oasis = (nit_cliente.replace("-", "") == "98133136" or "TIENDAS DE ORIENTE" in cliente_nombre_sat.upper() or "OASIS" in cliente_nombre_sat.upper())
                
                col_suc1, col_suc2 = st.columns(2)
                if es_oasis:
                    opciones_sucursal = [
                        "Oasis Chiquimula", "Oasis Esquipulas", "Oasis Quezaltepeque", 
                        "Oasis Ipala", "Oasis Zacapa", "Qualy Central", "Otra Sucursal Oasis"
                    ]
                    sucursal_seleccionada = col_suc1.selectbox("Selecciona la Sucursal de Oasis:", opciones_sucursal)
                    if sucursal_seleccionada == "Otra Sucursal Oasis":
                        sucursal_final = col_suc2.text_input("Escribe el nombre de la sucursal:", value="Oasis Sucursal")
                    else:
                        sucursal_final = sucursal_seleccionada
                else:
                    opciones_comunes = ["Gasolinera Shell", "Gasolinera Texaco", "Tienda La Blanquita", "Cliente Particular / Otro"]
                    sucursal_seleccionada = col_suc1.selectbox("Tipo de Cliente / Destino:", opciones_comunes)
                    if sucursal_seleccionada == "Cliente Particular / Otro":
                        sucursal_final = col_suc2.text_input("Escribe el nombre del negocio:", value=cliente_nombre_sat)
                    else:
                        sucursal_final = sucursal_seleccionada
                
                # Extraer productos
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
                        
                    lista_items.append({"Cantidad": cant, "Descripción": desc, "Categoría": categoria, "Total (Q)": tot})
                    
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
                        if not df_pan.empty: st.dataframe(df_pan[['Cantidad', 'Descripción', 'Total (Q)']], use_container_width=True, hide_index=True)
                        else: st.info("No se encontró pan en esta factura.")
                            
                    with col2:
                        st.warning(f"🍗 **Total Pasta/Salados:** Q {tot_pasta:,.2f}")
                        if not df_pasta.empty: st.dataframe(df_pasta[['Cantidad', 'Descripción', 'Total (Q)']], use_container_width=True, hide_index=True)
                        else: st.info("No se encontró pasta en esta factura.")
                    
                    st.markdown("---")
                    st.markdown(f"<h3 style='text-align: center; color: #2C3E50;'>Gran Total Facturado: Q {gran_total:,.2f}</h3>", unsafe_allow_html=True)
                    
                    if es_oasis:
                        st.info(f"💡 **Cuenta Corriente Jeny:** Al guardar, el Pan (Q {tot_pan:,.2f}) se sumará a su deuda bajo la sucursal **{sucursal_final}**.")
                    else:
                        st.success(f"⛽ **Ingreso al Contado:** Al guardar esta venta para **{sucursal_final}**, sumará a tus ingresos globales.")
                        
                    if st.button("💾 Guardar Control de Ruta", type="primary", use_container_width=True):
                        try:
                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO control_rutas (fecha_factura, cliente, sucursal, total_pan, total_pasta, gran_total)
                                    VALUES (:f, :c, :suc, :tpan, :tpasta, :gt)
                                """), {
                                    "f": fecha_factura, "c": cliente_nombre_sat, "suc": sucursal_final,
                                    "tpan": tot_pan, "tpasta": tot_pasta, "gt": gran_total
                                })
                                
                                if es_oasis:
                                    s.execute(text("""
                                        INSERT INTO cuenta_ruta_jeny (fecha, tipo, monto, detalle)
                                        VALUES (:f, 'CARGO', :m, :d)
                                    """), {"f": fecha_factura, "m": tot_pan, "d": f"Pan - {sucursal_final}"})
                                
                                s.commit()
                            st.success(f"✅ ¡Ruta guardada para {sucursal_final} exitosamente!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"⚠️ Error al guardar. Asegúrate de ejecutar el SQL para agregar la columna sucursal. Detalle: {e}")
                else:
                    st.warning("El XML parece estar vacío o no tiene el formato estándar de la SAT.")
            except Exception as e:
                st.error(f"❌ Ocurrió un error al leer el XML. Detalles técnicos: {e}")

    # --- PESTAÑA 2: CUENTA CORRIENTE JENY ---
    with tab_cuenta:
        st.markdown("### 📓 Estado de Cuenta: Jeny (Oasis / Qualy / Tiendas de Oriente)")
        st.write("Control de facturas acumuladas (Cargos) y depósitos parciales recibidos (Abonos).")
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
                            st.success("✅ ¡Abono guardado!")
                            st.rerun()
                        else: st.warning("El monto debe ser mayor a cero.")
            
            st.markdown("#### 📜 Movimientos de la Cuenta")
            if not df_cuenta.empty:
                df_mostrar_cta = df_cuenta.copy()
                df_mostrar_cta['fecha'] = pd.to_datetime(df_mostrar_cta['fecha']).dt.strftime('%d/%m/%Y')
                st.dataframe(df_mostrar_cta[['fecha', 'detalle', 'tipo', 'monto']], column_config={"fecha": "Fecha", "detalle": "Concepto / Sucursal", "tipo": "Tipo", "monto": st.column_config.NumberColumn("Monto (Q)", format="Q %.2f")}, hide_index=True, use_container_width=True)
            else: st.info("Aún no hay movimientos registrados en la cuenta de Jeny.")
        except Exception as e: st.error(f"⚠️ Error: {e}")

    # --- PESTAÑA 3: HISTORIAL GENERAL Y ELIMINACIÓN ---
    with tab_historial_rutas:
        st.markdown("### 🗄️ Historial de Facturas Subidas")
        try:
            df_rutas_hist = conn.query("SELECT * FROM control_rutas ORDER BY fecha_factura DESC, id DESC LIMIT 50", ttl=0)
            if not df_rutas_hist.empty:
                df_mostrar_rutas = df_rutas_hist.copy()
                df_mostrar_rutas['fecha_factura'] = pd.to_datetime(df_mostrar_rutas['fecha_factura']).dt.strftime('%d/%m/%Y')
                if 'sucursal' not in df_mostrar_rutas.columns:
                    df_mostrar_rutas['sucursal'] = df_mostrar_rutas['cliente']
                
                st.dataframe(
                    df_mostrar_rutas[['fecha_factura', 'sucursal', 'cliente', 'total_pan', 'total_pasta', 'gran_total']],
                    column_config={
                        "fecha_factura": "Fecha",
                        "sucursal": "Sucursal / Destino",
                        "cliente": "Razón Social SAT",
                        "total_pan": st.column_config.NumberColumn("Total Pan (Q)", format="Q %.2f"),
                        "total_pasta": st.column_config.NumberColumn("Total Pasta (Q)", format="Q %.2f"),
                        "gran_total": st.column_config.NumberColumn("Total Factura (Q)", format="Q %.2f")
                    },
                    hide_index=True, use_container_width=True
                )
                
                st.markdown("---")
                st.markdown("#### 🗑️ Eliminar Factura Subida por Error")
                opciones_borrar = df_rutas_hist.apply(
                    lambda row: f"ID: {row['id']} | Fecha: {pd.to_datetime(row['fecha_factura']).strftime('%d/%m/%Y')} | Sucursal: {row.get('sucursal', row['cliente'])} | Total: Q {row['gran_total']}", 
                    axis=1
                ).tolist()
                
                ruta_a_borrar = st.selectbox("Selecciona la factura a eliminar:", opciones_borrar)
                
                if st.button("🗑️ Eliminar Factura Seleccionada", type="secondary"):
                    idx_seleccion = opciones_borrar.index(ruta_a_borrar)
                    datos_ruta = df_rutas_hist.iloc[idx_seleccion]
                    ruta_id = int(datos_ruta['id'])
                    fecha_ruta = datos_ruta['fecha_factura']
                    monto_pan = float(datos_ruta['total_pan'])
                    suc_nombre = datos_ruta.get('sucursal', datos_ruta['cliente'])
                    cli_nombre = datos_ruta['cliente']
                    
                    with conn.session as s:
                        s.execute(text("DELETE FROM control_rutas WHERE id = :id"), {"id": ruta_id})
                        if "ORIENTE" in cli_nombre.upper() or "OASIS" in cli_nombre.upper() or "QUALY" in cli_nombre.upper():
                            s.execute(text("""
                                DELETE FROM cuenta_ruta_jeny
                                WHERE tipo = 'CARGO' AND fecha = :f AND monto = :m
                            """), {"f": fecha_ruta, "m": monto_pan})
                        s.commit()
                        
                    st.success("✅ ¡Factura y deuda eliminadas correctamente!")
                    st.rerun()
            else: st.info("No hay rutas guardadas todavía.")
        except Exception as e: st.caption(f"Error al cargar historial: {e}")

    # --- PESTAÑA 4: ESTADÍSTICAS POR SUCURSAL (NUEVO) ---
    with tab_estadisticas_rutas:
        st.markdown("### 📊 Comparativa de Compras por Sucursal")
        st.write("Analiza qué tienda o sucursal de Oasis / Ruta te genera mayor movimiento.")
        
        try:
            df_analisis = conn.query("SELECT * FROM control_rutas", ttl=0)
            if not df_analisis.empty:
                if 'sucursal' not in df_analisis.columns:
                    df_analisis['sucursal'] = df_analisis['cliente']
                else:
                    df_analisis['sucursal'] = df_analisis['sucursal'].fillna(df_analisis['cliente'])
                
                # Agrupar por sucursal
                resumen_sucursal = df_analisis.groupby('sucursal', as_index=False).agg({
                    'total_pan': 'sum',
                    'total_pasta': 'sum',
                    'gran_total': 'sum'
                }).sort_values('gran_total', ascending=False)
                
                sucursal_top = resumen_sucursal.iloc[0]['sucursal']
                total_top = resumen_sucursal.iloc[0]['gran_total']
                
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("👑 Sucursal Estrella (Mayor Compra)", f"{sucursal_top}", f"Q {total_top:,.2f}")
                col_m2.metric("📦 Total Facturado en Todas las Rutas", f"Q {resumen_sucursal['gran_total'].sum():,.2f}")
                
                st.markdown("---")
                st.subheader("📈 Gráfica: Pan vs Pasta de Pollo por Sucursal")
                df_graf_suc = resumen_sucursal.melt(
                    id_vars='sucursal', 
                    value_vars=['total_pan', 'total_pasta'],
                    var_name='Producto', 
                    value_name='Total_Q'
                )
                df_graf_suc['Producto'] = df_graf_suc['Producto'].map({'total_pan': 'Panadería', 'total_pasta': 'Pasta de Pollo'})
                
                fig_suc = px.bar(
                    df_graf_suc, 
                    x='sucursal', 
                    y='Total_Q', 
                    color='Producto', 
                    barmode='group',
                    labels={'sucursal': 'Sucursal / Cliente', 'Total_Q': 'Total Comprado (Q)'},
                    color_discrete_map={'Panadería': '#F39C12', 'Pasta de Pollo': '#E74C3C'}
                )
                st.plotly_chart(fig_suc, use_container_width=True)
                
                st.subheader("📋 Tabla Consolidada por Sucursal")
                st.dataframe(
                    resumen_sucursal,
                    column_config={
                        "sucursal": "Sucursal",
                        "total_pan": st.column_config.NumberColumn("Total Pan (Q)", format="Q %.2f"),
                        "total_pasta": st.column_config.NumberColumn("Total Pasta (Q)", format="Q %.2f"),
                        "gran_total": st.column_config.NumberColumn("Gran Total Vendido", format="Q %.2f")
                    },
                    hide_index=True, use_container_width=True
                )
            else:
                st.info("Sube facturas en la pestaña 1 para ver las estadísticas de tus sucursales.")
        except Exception as e:
            st.error(f"Error al calcular estadísticas: {e}")

# (El resto de módulos de la aplicación quedan disponibles igual que antes)
elif opcion_menu == "📝 Registro de Corte":
    st.title("🍞 Ingreso Diario de Corte")
    st.info("Usa el menú lateral para navegar entre módulos.")
