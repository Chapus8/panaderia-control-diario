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
import streamlit.components.v1 as components 

# ==========================================
# 1. CONFIGURACIÓN PRINCIPAL
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
# 3. CEREBRO CLASIFICADOR Y PDF
# ==========================================
def obtener_o_crear_corte(fecha_corte):
    with conn.session as s:
        result = s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()
        if result: return result[0]
        else:
            s.execute(text("INSERT INTO cortes_diarios (fecha) VALUES (:fecha)"), {"fecha": fecha_corte}); s.commit()
            return s.execute(text("SELECT id FROM cortes_diarios WHERE fecha = :fecha"), {"fecha": fecha_corte}).fetchone()[0]

def autocompletar_categoria(d):
    """Cerebro Clasificador Ultra Detallado entrenado con los datos de Panadería Judith"""
    d = str(d).lower()
    
    if re.search(r'\b(alquiler|arrendamiento|local|mensualidad|renta|parqueo|bodega)\b', d): return 'ALQUILERES'
    if re.search(r'\b(luz|agua|telefono|internet|basura|celular|energuate|claro|tigo|cable|recarga|eegsa|municipalidad|saldo|alarma|seguridad)\b', d): return 'PAGO DE SERVICIOS'
    if re.search(r'\b(resma|hoja|hojas|lapicero|cuaderno|libreta|marcador|clip|grapa|impresion|tinta|toner|papel bond|folder|papeleria)\b', d): return 'UTILES DE OFICINA'
    if re.search(r'\b(sellador|bolsa|bolsas|bandeja|calcomania|etiqueta|nylon|plastico|vaso|plato|desechable|domo|tapadera|tape|cinta|pita|rollo|caja|carton)\b', d): return 'EMPAQUES Y DESECHABLES'
    if re.search(r'\b(escoba|jabon|cloro|desinfectante|trapeador|esponja|basurero|papel higienico|servilleta|aromatizante|fabuloso|rinso|magia|detergente|cepillo|limpia vidrio)\b', d): return 'PRODUCTOS DE LIMPIEZA'
    if re.search(r'\b(harina|azucar|azúcar|manteca|levadura|leche|huevo|huevos|sal|esencia|colorante|polvo|margarina|aceite|vainilla|canela|chocolate|cocoa|jalea|manjar|queso|crema|ajonjoli|mermelada|pasa|maicena|royal|bicarbonato|premezcla|chantilly|fondant|cobertura|mayonesa|consome|mostaza|verdura|apio|cebolla|chile)\b', d): return 'MATERIA PRIMA'
    if re.search(r'\b(compra pasta|compras pasta|compra pollo|compras pollo|pasta de pollo)\b', d): return 'COMPRAS DE PASTA DE POLLO'
    if re.search(r'\b(bolsa de agua|agua pura|gaseosa|coca|bebida|tostada|marquesote|jugo|tampico|gatorade|botella|galleta|helado|ricito|dorito|golosina|toti|dulce|chicle|salvavidas|garrafon|frijol|tortilla)\b', d): return 'OTRAS MERCADERIAS'
    if re.search(r'\b(bono|sueldo|salario|anticipo|almuerzo|planilla|turno|quincena|panadero|pago a|wendy|dania|jorge|roberto|pasaje|comision|igss|viatico|colaboradora|prestacion|honorario|profesional|portillo)\b', d): return 'SUELDOS Y SALARIOS'
    if re.search(r'\b(gasolina|combustible|moto|vehiculo|repuesto|llanta|aceite motor|mecanico|pinchazo|bateria|freno|pastilla|servicio moto|carwash|lavado|bujia|cadena|candela)\b', d): return 'REPUESTOS Y REPARACIONES'
    if re.search(r'\b(prestamo|tarjeta|interes|abono|banco|cuota|visacuota|credito|banrural|industrial|ficohsa|bam|micoope|cooperativa|coosajo|bantrab|cmj|genesis|mami)\b', d): return 'PRESTAMOS E INTERESES'
    if re.search(r'\b(impuesto|sat|contador|patente|boleto de ornato|multa|isr|iva|declaracion|tramite|abogado|notario)\b', d): return 'IMPUESTOS Y LEGALES'
    if re.search(r'\b(gas|propano|cilindro|tambito|horno|batidora|lata|molde|espatula|raspa|cuchillo|rodillo|manga|boquilla|lata de horneo|afilado|plomero|electricista|foco|tubo|cableado|pintura|herramienta|edificio|mobiliario|equipo)\b', d): return 'MANTENIMIENTO Y EQUIPO'
    if re.search(r'\b(publicidad|anuncio|volante|facebook|radio)\b', d): return 'PUBLICIDAD'
    
    return 'OTROS GASTOS'

def add_pdf_header(elements, title_text, subtitle_text=""):
    logo_file = get_logo_path()
    if logo_file:
        try:
            img = RLImage(logo_file, width=120, height=120, kind='proportional')
            img.hAlign = 'CENTER'
            elements.append(img); elements.append(Spacer(1, 10))
        except: pass
    title_style = ParagraphStyle('Title', fontName="Helvetica-Bold", fontSize=18, alignment=1, textColor=colors.HexColor("#2C3E50"), spaceAfter=10, leading=22)
    sub_style = ParagraphStyle('Sub', fontName="Helvetica", fontSize=12, alignment=1, textColor=colors.gray, spaceAfter=20, leading=16)
    elements.append(Paragraph(title_text, title_style))
    if subtitle_text: elements.append(Paragraph(subtitle_text, sub_style))

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
    add_pdf_header(elements, "PANADERÍA Y REPOSTERÍA JUDITH", f"REPORTE COMPARATIVO DIARIO (INCLUYE RUTAS Y EXTRAS): {f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}")
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
            f"{row['Sueldo Quincenal']:.2f}" if row['Sueldo Quincenal'] else "-", 
            f"{row['Días Laborados']:.2f}", 
            f"{row['Sueldo Prop.']:.2f}", 
            f"{row['Comisiones']:.2f}" if row['Comisiones'] else "-", 
            f"{row['Total Devengado']:.2f}", 
            f"{row['Anticipos']:.2f}" if row['Anticipos'] else "-", 
            f"{row['IGSS']:.2f}" if row['IGSS'] else "-", 
            f"{row['Tienda']:.2f}" if row['Tienda'] else "-", 
            f"{row['Total Descuentos']:.2f}" if row['Total Descuentos'] else "-", 
            f"{row['Líquido a Recibir']:.2f}"
        ])
        sum_sueldo += row['Sueldo Quincenal']; sum_total_prop += row['Sueldo Prop.']; sum_comis += row['Comisiones']; sum_dev += row['Total Devengado']; sum_ant += row['Anticipos']; sum_igss += row['IGSS']; sum_tienda += row['Tienda']; sum_desc += row['Total Descuentos']; sum_liq += row['Líquido a Recibir']
    data.append(["", "TOTALES", f"{sum_sueldo:.2f}", "", f"{sum_total_prop:.2f}", f"{sum_comis:.2f}", f"{sum_dev:.2f}", f"{sum_ant:.2f}", f"{sum_igss:.2f}", f"{sum_tienda:.2f}", f"{sum_desc:.2f}", f"{sum_liq:.2f}"])
    t = Table(data, colWidths=[25, 140, 65, 45, 55, 75, 75, 55, 50, 50, 75, 75])
    t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTNAME', (0,0), (-1,1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#2980B9")), ('SPAN', (0,0), (0,1)), ('SPAN', (1,0), (1,1)), ('SPAN', (2,0), (2,1)), ('SPAN', (3,0), (3,1)), ('SPAN', (4,0), (4,1)), ('SPAN', (5,0), (5,1)), ('SPAN', (6,0), (6,1)), ('SPAN', (7,0), (9,0)), ('SPAN', (10,0), (10,1)), ('SPAN', (11,0), (11,1)), ('TEXTCOLOR', (0,0), (-1,1), colors.HexColor("#1A5276")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), ('SPAN', (0,-1), (1,-1))]))
    elements.append(t); elements.append(Spacer(1, 40)); sig_data = [["___________________________", "___________________________"], ["Elaborado Por", "Revisado / Autorizado"]]; t_sig = Table(sig_data, colWidths=[250, 250]); t_sig.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')])); elements.append(t_sig)
    doc.build(elements); buffer.seek(0); return buffer

def generar_pdf_recibos_quincenales(f_inicio, f_fin, df_calc):
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40); elements = []
    lbl_style = ParagraphStyle('Lbl', fontName="Helvetica-Bold", fontSize=11); val_style = ParagraphStyle('Val', fontName="Helvetica", fontSize=11)
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
        elements.append(Spacer(1, 60)); elements.append(Paragraph("__________________________________________", ParagraphStyle('firma', alignment=1))); elements.append(Paragraph(f"Firma de Recibido - {emp.upper()}", ParagraphStyle('firma', alignment=1))); elements.append(PageBreak())
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

# ------------------------------------------
# MÓDULO 2: HISTORIAL DE CORTES
# ------------------------------------------
elif opcion_menu == "📅 Historial de Cortes":
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
                    st.subheader("💰 Desglose de Ingresos"); st.dataframe(ingresos_hist, use_container_width=True, hide_index=True) if not ingresos_hist.empty else st.info("No se registraron ingresos este día.")
                with col_t2:
                    st.subheader("💸 Desglose de Gastos"); st.dataframe(gastos_hist, use_container_width=True, hide_index=True) if not gastos_hist.empty else st.info("No se registraron gastos este día.")
            else: st.warning(f"No hay ningún corte guardado en el sistema para la fecha {fecha_consulta.strftime('%d/%m/%Y')}.")
        except Exception as e: st.error("Error al consultar el historial.")
        
    with tab_lote:
        st.markdown("### 📦 Descargar Múltiples Cortes")
        col_l1, col_l2 = st.columns(2)
        f_ini_lote = col_l1.date_input("Desde:", get_fecha_guate().replace(day=1), format="DD/MM/YYYY", key="lote_ini")
        f_fin_lote = col_l2.date_input("Hasta:", get_fecha_guate(), format="DD/MM/YYYY", key="lote_fin")
        if st.button("📦 Generar Archivo ZIP", type="primary", use_container_width=True):
            with st.spinner("Generando PDFs y comprimiendo..."):
                try:
                    q_cortes = f"SELECT id, fecha FROM cortes_diarios WHERE fecha BETWEEN '{f_ini_lote}' AND '{f_fin_lote}'"
                    df_cortes = conn.query(q_cortes, ttl=0)
                    if df_cortes.empty: st.warning("No hay cortes registrados en este rango de fechas.")
                    else:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for _, c_row in df_cortes.iterrows():
                                c_id = c_row['id']; c_fecha = pd.to_datetime(c_row['fecha']).date()
                                ingresos_hist = conn.query(f"SELECT r.nombre as Ruta, i.venta_total as Venta_Mostrador, i.credito_pagado as Pedidos, i.transferencias as transferencias FROM ingresos i JOIN rutas_locales r ON i.ruta_id = r.id WHERE i.corte_id = {c_id}", ttl=0)
                                gastos_hist = conn.query(f"SELECT c.nombre as Categoria, g.detalle as Detalle, g.monto as Monto FROM gastos g JOIN categorias_gasto c ON g.categoria_id = c.id WHERE g.corte_id = {c_id}", ttl=0)
                                sum_venta = ingresos_hist['venta_mostrador'].sum() if not ingresos_hist.empty else 0.0; sum_pedidos = ingresos_hist['pedidos'].sum() if not ingresos_hist.empty else 0.0; sum_transferencias = ingresos_hist['transferencias'].sum() if not ingresos_hist.empty and 'transferencias' in ingresos_hist.columns else 0.0
                                ruta_nombre = ingresos_hist.iloc[0]['ruta'] if not ingresos_hist.empty else "LOCAL MERCADO"
                                df_para_pdf = pd.DataFrame({"Categoría": gastos_hist['categoria'] if not gastos_hist.empty else [], "Detalle": gastos_hist['detalle'] if not gastos_hist.empty else [], "Monto (Q)": gastos_hist['monto'] if not gastos_hist.empty else []})
                                pdf_bytes = generar_pdf_corte(c_fecha.strftime('%d/%m/%Y'), ruta_nombre, "Histórico", df_para_pdf, sum_venta, sum_pedidos, sum_transferencias)
                                zip_file.writestr(f"Corte_{c_fecha.strftime('%d-%m-%Y')}.pdf", pdf_bytes.getvalue())
                        st.success(f"✅ ¡ZIP generado con {len(df_cortes)} cortes!")
                        st.download_button(label="📥 Descargar Archivo ZIP", data=zip_buffer.getvalue(), file_name=f"Cortes_{f_ini_lote.strftime('%d-%m-%Y')}_al_{f_fin_lote.strftime('%d-%m-%Y')}.zip", mime="application/zip", type="secondary", use_container_width=True)
                except Exception as e: st.error(f"Error al generar el lote: {e}")

# ------------------------------------------
# MÓDULO 3: ESTADÍSTICAS
# ------------------------------------------
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

# ------------------------------------------
# MÓDULO 4: COMPARATIVA DIARIA
# ------------------------------------------
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

# ------------------------------------------
# MÓDULO 5: DÍAS ESTRELLA
# ------------------------------------------
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

# ------------------------------------------
# MÓDULO 6: RUTA Y PEDIDOS (XML) LECTOR POR REGEX PURO
# ------------------------------------------
elif opcion_menu == "🚚 Ruta y Pedidos (XML)":
    st.title("🚚 Control de Ruta y Pedidos (Lector SAT)")
    tab_xml, tab_cuenta, tab_historial_rutas, tab_estadisticas_rutas, tab_config_sucursales = st.tabs(["📥 1. Lector de Facturas", "📓 2. Cuenta de Jeny", "🗄️ 3. Historial General", "📊 4. Estadísticas", "⚙️ 5. Configurar Sucursales"])
    
    def obtener_lista_sucursales():
        try:
            df_suc = conn.query("SELECT nombre FROM sucursales_oasis ORDER BY nombre", ttl=0)
            if not df_suc.empty: return df_suc['nombre'].tolist() + ["Otra Sucursal Oasis"]
        except Exception: pass
        return ["Oasis Jocotan", "Oasis Zacapa", "Oasis Teculutan", "Quali Usumatlan", "Quali San Jorge Zacapa", "Oasis Chiquimula Octava", "Oasis Chiquimula Decima", "Quali El Molino Chiquimula", "Otra Sucursal Oasis"]
    
    def obtener_lista_comunes():
        try:
            df_suc = conn.query("SELECT nombre FROM sucursales_comunes ORDER BY nombre", ttl=0)
            if not df_suc.empty: return df_suc['nombre'].tolist() + ["Cliente Particular / Otro"]
        except Exception: pass
        return ["Gasolinera Shell", "Gasolinera Texaco", "Tienda La Blanquita", "Cliente Particular / Otro"]
    
    with tab_xml:
        st.markdown("Sube tu archivo `.xml` generado por la SAT para extraer automáticamente los productos.")
        archivo_xml = st.file_uploader("📂 Subir XML de Factura Electrónica (FEL)", type=["xml"])
        
        if archivo_xml is not None:
            try:
                xml_str = archivo_xml.getvalue().decode('utf-8', errors='ignore')
                f_emision_m = re.search(r'FechaHoraEmision="([^"]+)"', xml_str)
                fecha_factura = f_emision_m.group(1)[:10] if f_emision_m else str(get_fecha_guate())
                cliente_m = re.search(r'NombreReceptor="([^"]+)"', xml_str)
                cliente_nombre_sat = cliente_m.group(1) if cliente_m else "Cliente Generico"
                nit_m = re.search(r'IDReceptor="([^"]+)"', xml_str)
                nit_cliente = nit_m.group(1) if nit_m else "CF"
                
                st.markdown("---")
                st.markdown(f"### 🏢 Facturado a: **{cliente_nombre_sat}** (NIT: {nit_cliente})")
                st.markdown(f"📅 **Fecha de Emisión:** {pd.to_datetime(fecha_factura).strftime('%d/%m/%Y')}")
                
                st.markdown("#### 📍 Identificación de Sucursal / Destino")
                es_oasis_detectado = (nit_cliente.replace("-", "") == "98133136" or "TIENDAS DE ORIENTE" in cliente_nombre_sat.upper() or "OASIS" in cliente_nombre_sat.upper() or "QUALY" in cliente_nombre_sat.upper())
                
                forzar_contado = False
                if es_oasis_detectado:
                    forzar_contado = st.checkbox("✅ Forzar como Venta al Contado (No sumar a la cuenta de Jeny)")
                
                es_oasis_final = es_oasis_detectado and not forzar_contado
                col_suc1, col_suc2 = st.columns(2)
                if es_oasis_final:
                    sucursal_seleccionada = col_suc1.selectbox("Selecciona la Sucursal de Oasis:", obtener_lista_sucursales())
                    if sucursal_seleccionada == "Otra Sucursal Oasis": sucursal_final = col_suc2.text_input("Escribe el nombre de la sucursal:", value="Oasis Sucursal")
                    else: sucursal_final = sucursal_seleccionada
                else:
                    sucursal_seleccionada = col_suc1.selectbox("Tipo de Cliente / Destino:", obtener_lista_comunes())
                    if sucursal_seleccionada == "Cliente Particular / Otro": sucursal_final = col_suc2.text_input("Escribe el nombre del negocio:", value=cliente_nombre_sat)
                    else: sucursal_final = sucursal_seleccionada
                
                item_blocks = re.findall(r'<[^>]*?Item\b[^>]*>(.*?)</[^>]*?Item>', xml_str, re.DOTALL | re.IGNORECASE)
                lista_items = []
                for block in item_blocks:
                    cant_m = re.search(r'<[^>]*?Cantidad[^>]*>([\d\.]+)</', block, re.IGNORECASE)
                    desc_m = re.search(r'<[^>]*?Descripcion[^>]*>(.*?)</', block, re.IGNORECASE)
                    tot_m = re.search(r'<[^>]*?Total[^>]*>([\d\.]+)</', block, re.IGNORECASE)
                    
                    cant = float(cant_m.group(1)) if cant_m else 0.0
                    desc = desc_m.group(1).strip() if desc_m else "Sin descripción"
                    tot = float(tot_m.group(1)) if tot_m else 0.0
                    
                    desc_low = desc.lower()
                    if 'pasta' in desc_low or 'pollo' in desc_low or 'taco' in desc_low: categoria = "Pasta / Salado"
                    else: categoria = "Pan / Repostería"
                    lista_items.append({"Cantidad": cant, "Descripción": desc, "Categoría": categoria, "Total (Q)": tot})
                        
                df_xml = pd.DataFrame(lista_items)
                
                if not df_xml.empty:
                    df_pan = df_xml[df_xml['Categoría'] == 'Pan / Repostería']
                    df_pasta = df_xml[df_xml['Categoría'] == 'Pasta / Salado']
                    tot_pan = float(df_pan['Total (Q)'].sum()) if not df_pan.empty else 0.0
                    tot_pasta = float(df_pasta['Total (Q)'].sum()) if not df_pasta.empty else 0.0
                    gran_total = float(df_xml['Total (Q)'].sum()) if not df_xml.empty else 0.0
                    
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
                    
                    if es_oasis_final: st.info(f"💡 **Cuenta Corriente Jeny:** Al guardar, el Pan (Q {tot_pan:,.2f}) se sumará a su deuda bajo la sucursal **{sucursal_final}**.")
                    else: st.success(f"⛽ **Ingreso al Contado:** Al guardar esta venta para **{sucursal_final}**, sumará a tus ingresos globales.")
                        
                    if st.button("💾 Guardar Control de Ruta", type="primary", use_container_width=True):
                        try:
                            with conn.session as s:
                                s.execute(text("""
                                    INSERT INTO control_rutas (fecha_factura, cliente, sucursal, total_pan, total_pasta, gran_total)
                                    VALUES (:f, :c, :suc, :tpan, :tpasta, :gt)
                                """), {"f": fecha_factura, "c": cliente_nombre_sat, "suc": sucursal_final, "tpan": tot_pan, "tpasta": tot_pasta, "gt": gran_total})
                                
                                if es_oasis_final:
                                    s.execute(text("""
                                        INSERT INTO cuenta_ruta_jeny (fecha, tipo, monto, detalle)
                                        VALUES (:f, 'CARGO', :m, :d)
                                    """), {"f": fecha_factura, "m": tot_pan, "d": f"Pan - {sucursal_final}"})
                                s.commit()
                            st.success(f"✅ ¡Ruta guardada para {sucursal_final} exitosamente!"); st.balloons()
                        except Exception as e: st.error(f"⚠️ Error al guardar. Detalle: {e}")
                else: st.warning("No pude extraer productos de este XML. Verifica que sea una factura estándar de la SAT.")
            except Exception as e: st.error(f"❌ Ocurrió un error al procesar el XML. Detalles: {e}")
            
    with tab_cuenta:
        st.markdown("### 📓 Estado de Cuenta: Jeny (Oasis / Qualy / Tiendas de Oriente)")
        try:
            df_cuenta = conn.query("SELECT * FROM cuenta_ruta_jeny ORDER BY fecha ASC, id ASC", ttl=0)
            total_cargos = df_cuenta[df_cuenta['tipo'] == 'CARGO']['monto'].sum() if not df_cuenta.empty else 0.0; total_abonos = df_cuenta[df_cuenta['tipo'] == 'ABONO']['monto'].sum() if not df_cuenta.empty else 0.0; saldo_pendiente = total_cargos - total_abonos
            c1, c2, c3 = st.columns(3); c1.metric("📉 Total Facturado (Deuda)", f"Q {total_cargos:,.2f}"); c2.metric("💵 Total Pagado (Abonos)", f"Q {total_abonos:,.2f}"); c3.metric("⚖️ Saldo Pendiente por Cobrar", f"Q {saldo_pendiente:,.2f}")
            st.markdown("---")
            with st.expander("➕ Registrar un Nuevo Abono (Depósito de Jeny)"):
                with st.form("form_abono_jeny", clear_on_submit=True):
                    col_a1, col_a2, col_a3 = st.columns(3); fecha_abono = col_a1.date_input("Fecha del Depósito", get_fecha_guate(), format="DD/MM/YYYY"); monto_abono = col_a2.number_input("Monto Recibido (Q)", min_value=0.00, step=100.00); detalle_abono = col_a3.text_input("Nota / Ref. Depósito", placeholder="Ej. Depósito Banco Industrial")
                    if st.form_submit_button("Guardar Abono"):
                        if monto_abono > 0:
                            with conn.session as s: s.execute(text("INSERT INTO cuenta_ruta_jeny (fecha, tipo, monto, detalle) VALUES (:f, 'ABONO', :m, :d)"), {"f": fecha_abono, "m": monto_abono, "d": detalle_abono}); s.commit()
                            st.success("✅ ¡Abono guardado!"); st.rerun()
                        else: st.warning("El monto debe ser mayor a cero.")
            st.markdown("#### 📜 Movimientos de la Cuenta")
            if not df_cuenta.empty:
                df_mostrar_cta = df_cuenta.copy(); df_mostrar_cta['fecha'] = pd.to_datetime(df_mostrar_cta['fecha']).dt.strftime('%d/%m/%Y'); st.dataframe(df_mostrar_cta[['fecha', 'detalle', 'tipo', 'monto']], column_config={"fecha": "Fecha", "detalle": "Concepto / Sucursal", "tipo": "Tipo", "monto": st.column_config.NumberColumn("Monto (Q)", format="Q %.2f")}, hide_index=True, use_container_width=True)
            else: st.info("Aún no hay movimientos registrados en la cuenta de Jeny.")
        except Exception as e: st.error(f"⚠️ Error: {e}")

    with tab_historial_rutas:
        st.markdown("### 🗄️ Historial de Facturas Subidas")
        try:
            df_rutas_hist = conn.query("SELECT * FROM control_rutas ORDER BY fecha_factura DESC, id DESC LIMIT 50", ttl=0)
            if not df_rutas_hist.empty:
                df_mostrar_rutas = df_rutas_hist.copy(); df_mostrar_rutas['fecha_factura'] = pd.to_datetime(df_mostrar_rutas['fecha_factura']).dt.strftime('%d/%m/%Y')
                if 'sucursal' not in df_mostrar_rutas.columns: df_mostrar_rutas['sucursal'] = df_mostrar_rutas['cliente']
                st.dataframe(df_mostrar_rutas[['fecha_factura', 'sucursal', 'cliente', 'total_pan', 'total_pasta', 'gran_total']], column_config={"fecha_factura": "Fecha", "sucursal": "Sucursal / Destino", "cliente": "Razón Social SAT", "total_pan": st.column_config.NumberColumn("Total Pan (Q)", format="Q %.2f"), "total_pasta": st.column_config.NumberColumn("Total Pasta (Q)", format="Q %.2f"), "gran_total": st.column_config.NumberColumn("Total Factura (Q)", format="Q %.2f")}, hide_index=True, use_container_width=True)
                st.markdown("---"); col_edit, col_del = st.columns(2)
                with col_edit:
                    st.markdown("#### ✏️ Corregir Sucursal")
                    opciones_edit = df_rutas_hist.apply(lambda row: f"ID: {row['id']} | Fecha: {pd.to_datetime(row['fecha_factura']).strftime('%d/%m/%Y')} | Sucursal actual: {row.get('sucursal', row['cliente'])}", axis=1).tolist(); ruta_a_editar = st.selectbox("Selecciona la factura:", opciones_edit, key="sel_edit")
                    idx_edit_temp = opciones_edit.index(ruta_a_editar); datos_edit_temp = df_rutas_hist.iloc[idx_edit_temp]
                    es_oasis_edit = ("ORIENTE" in datos_edit_temp['cliente'].upper() or "OASIS" in datos_edit_temp['cliente'].upper() or "QUALY" in datos_edit_temp['cliente'].upper())
                    nueva_suc_correcta = st.selectbox("Nueva Sucursal Correcta:", obtener_lista_sucursales() if es_oasis_edit else obtener_lista_comunes())
                    if st.button("💾 Guardar Corrección", type="primary"):
                        idx_edit = opciones_edit.index(ruta_a_editar); datos_edit = df_rutas_hist.iloc[idx_edit]; id_edit = int(datos_edit['id']); f_edit = datos_edit['fecha_factura']; m_edit = float(datos_edit['total_pan']); suc_vieja = datos_edit.get('sucursal', datos_edit['cliente']); cli_nombre_edit = datos_edit['cliente']
                        with conn.session as s:
                            s.execute(text("UPDATE control_rutas SET sucursal = :ns WHERE id = :id"), {"ns": nueva_suc_correcta, "id": id_edit})
                            if "ORIENTE" in cli_nombre_edit.upper() or "OASIS" in cli_nombre_edit.upper() or "QUALY" in cli_nombre_edit.upper(): s.execute(text("UPDATE cuenta_ruta_jeny SET detalle = :nd WHERE tipo = 'CARGO' AND fecha = :f AND monto = :m AND detalle = :vd"), {"nd": f"Pan - {nueva_suc_correcta}", "f": f_edit, "m": m_edit, "vd": f"Pan - {suc_vieja}"})
                            s.commit()
                        st.success("✅ ¡Sucursal corregida con éxito!"); st.rerun()
                with col_del:
                    st.markdown("#### 🗑️ Eliminar Factura")
                    opciones_borrar = df_rutas_hist.apply(lambda row: f"ID: {row['id']} | Fecha: {pd.to_datetime(row['fecha_factura']).strftime('%d/%m/%Y')} | Total: Q {row['gran_total']}", axis=1).tolist(); ruta_a_borrar = st.selectbox("Selecciona para eliminar:", opciones_borrar, key="sel_del")
                    if st.button("🗑️ Eliminar Definitivamente", type="secondary"):
                        idx_del = opciones_borrar.index(ruta_a_borrar); datos_del = df_rutas_hist.iloc[idx_del]; id_del = int(datos_del['id']); f_del = datos_del['fecha_factura']; m_del = float(datos_del['total_pan']); cli_del = datos_del['cliente']
                        with conn.session as s:
                            s.execute(text("DELETE FROM control_rutas WHERE id = :id"), {"id": id_del})
                            if "ORIENTE" in cli_del.upper() or "OASIS" in cli_del.upper() or "QUALY" in cli_del.upper(): s.execute(text("DELETE FROM cuenta_ruta_jeny WHERE tipo = 'CARGO' AND fecha = :f AND monto = :m"), {"f": f_del, "m": m_del})
                            s.commit()
                        st.success("✅ ¡Factura (y deuda) eliminadas!"); st.rerun()
            else: st.info("No hay rutas guardadas todavía.")
        except Exception as e: st.caption(f"Error al cargar historial: {e}")

    with tab_estadisticas_rutas:
        st.markdown("### 📊 Comparativa de Compras por Sucursal")
        try:
            df_analisis = conn.query("SELECT * FROM control_rutas", ttl=0)
            if not df_analisis.empty:
                if 'sucursal' not in df_analisis.columns: df_analisis['sucursal'] = df_analisis['cliente']
                else: df_analisis['sucursal'] = df_analisis['sucursal'].fillna(df_analisis['cliente'])
                resumen_sucursal = df_analisis.groupby('sucursal', as_index=False).agg({'total_pan': 'sum', 'total_pasta': 'sum', 'gran_total': 'sum'}).sort_values('gran_total', ascending=False)
                sucursal_top = resumen_sucursal.iloc[0]['sucursal']; total_top = float(resumen_sucursal.iloc[0]['gran_total'])
                col_m1, col_m2 = st.columns(2); col_m1.metric("👑 Sucursal Estrella (Mayor Compra)", f"{sucursal_top}", f"Q {total_top:,.2f}"); col_m2.metric("📦 Total Facturado en Todas las Rutas", f"Q {float(resumen_sucursal['gran_total'].sum()):,.2f}")
                st.markdown("---"); st.subheader("📈 Gráfica: Pan vs Pasta de Pollo por Sucursal")
                df_graf_suc = resumen_sucursal.melt(id_vars='sucursal', value_vars=['total_pan', 'total_pasta'], var_name='Producto', value_name='Total_Q'); df_graf_suc['Producto'] = df_graf_suc['Producto'].map({'total_pan': 'Panadería', 'total_pasta': 'Pasta de Pollo'})
                fig_suc = px.bar(df_graf_suc, x='sucursal', y='Total_Q', color='Producto', barmode='group', labels={'sucursal': 'Sucursal / Cliente', 'Total_Q': 'Total Comprado (Q)'}, color_discrete_map={'Panadería': '#F39C12', 'Pasta de Pollo': '#E74C3C'}); st.plotly_chart(fig_suc, use_container_width=True)
                st.subheader("📋 Tabla Consolidada por Sucursal"); st.dataframe(resumen_sucursal, column_config={"sucursal": "Sucursal", "total_pan": st.column_config.NumberColumn("Total Pan (Q)", format="Q %.2f"), "total_pasta": st.column_config.NumberColumn("Total Pasta (Q)", format="Q %.2f"), "gran_total": st.column_config.NumberColumn("Gran Total Vendido", format="Q %.2f")}, hide_index=True, use_container_width=True)
            else: st.info("Sube facturas en la pestaña 1 para ver las estadísticas de tus sucursales.")
        except Exception as e: st.error(f"Error al calcular estadísticas: {e}")

    with tab_config_sucursales:
        st.markdown("### ⚙️ Administrar Sucursales y Clientes")
        col_oasis, col_comun = st.columns(2)
        with col_oasis:
            st.markdown("#### 🍞 Oasis / Qualy (Cuenta Jeny)")
            with st.expander("➕ Agregar Oasis"):
                with st.form("form_nuevo_oasis", clear_on_submit=True):
                    nueva_sucursal = st.text_input("Nombre (Ej. Oasis Zacapa 2)")
                    if st.form_submit_button("Guardar"):
                        if nueva_sucursal.strip() != "":
                            with conn.session as s: s.execute(text("INSERT INTO sucursales_oasis (nombre) VALUES (:n)"), {"n": nueva_sucursal.strip()}); s.commit()
                            st.success(f"✅ Agregado."); st.rerun()
            try:
                df_sucursales_edit = conn.query("SELECT id, nombre FROM sucursales_oasis ORDER BY id", ttl=0)
                if not df_sucursales_edit.empty:
                    st.caption("✏️ Editar Nombres"); sucursales_editadas = st.data_editor(df_sucursales_edit, column_config={"id": None, "nombre": st.column_config.TextColumn("Nombre", required=True)}, hide_index=True, use_container_width=True, key="edit_oasis")
                    if st.button("💾 Guardar Oasis", type="primary"):
                        with conn.session as s:
                            for index, row in sucursales_editadas.iterrows(): s.execute(text("UPDATE sucursales_oasis SET nombre = :n WHERE id = :id"), {"n": row["nombre"], "id": int(row["id"])})
                            s.commit()
                        st.success("✅ Nombres actualizados."); st.rerun()
                    st.caption("🗑️ Eliminar"); suc_a_borrar = st.selectbox("Quitar de la lista:", df_sucursales_edit['nombre'], key="del_oasis")
                    if st.button("Eliminar Oasis Seleccionado"):
                        id_borrar = df_sucursales_edit.loc[df_sucursales_edit['nombre'] == suc_a_borrar, 'id'].values[0]
                        with conn.session as s: s.execute(text("DELETE FROM sucursales_oasis WHERE id = :id"), {"id": int(id_borrar)}); s.commit()
                        st.success("🗑️ Eliminado."); st.rerun()
            except: pass
        with col_comun:
            st.markdown("#### ⛽ Clientes de Contado (XML)")
            with st.expander("➕ Agregar Cliente"):
                with st.form("form_nuevo_comun", clear_on_submit=True):
                    nuevo_comun = st.text_input("Nombre (Ej. Despensa Familiar)")
                    if st.form_submit_button("Guardar"):
                        if nuevo_comun.strip() != "":
                            try:
                                with conn.session as s: s.execute(text("INSERT INTO sucursales_comunes (nombre) VALUES (:n)"), {"n": nuevo_comun.strip()}); s.commit()
                                st.success(f"✅ Agregado."); st.rerun()
                            except: st.error("Falta la tabla sucursales_comunes en Neon.")
            try:
                df_comunes_edit = conn.query("SELECT id, nombre FROM sucursales_comunes ORDER BY id", ttl=0)
                if not df_comunes_edit.empty:
                    st.caption("✏️ Editar Nombres"); comunes_editadas = st.data_editor(df_comunes_edit, column_config={"id": None, "nombre": st.column_config.TextColumn("Nombre", required=True)}, hide_index=True, use_container_width=True, key="edit_comunes")
                    if st.button("💾 Guardar Clientes", type="primary"):
                        with conn.session as s:
                            for index, row in comunes_editadas.iterrows(): s.execute(text("UPDATE sucursales_comunes SET nombre = :n WHERE id = :id"), {"n": row["nombre"], "id": int(row["id"])})
                            s.commit()
                        st.success("✅ Nombres actualizados."); st.rerun()
                    st.caption("🗑️ Eliminar"); comun_a_borrar = st.selectbox("Quitar de la lista:", df_comunes_edit['nombre'], key="del_comunes")
                    if st.button("Eliminar Cliente Seleccionado"):
                        id_borrar = df_comunes_edit.loc[df_comunes_edit['nombre'] == comun_a_borrar, 'id'].values[0]
                        with conn.session as s: s.execute(text("DELETE FROM sucursales_comunes WHERE id = :id"), {"id": int(id_borrar)}); s.commit()
                        st.success("🗑️ Eliminado."); st.rerun()
            except: pass

# ------------------------------------------
# MÓDULO 7: VENTAS EXTRA (RECIBOS)
# ------------------------------------------
elif opcion_menu == "📝 Ventas Extra (Recibos)":
    st.title("📝 Control de Ventas Extra (Ingresos Aparte)")
    st.write("Registra ventas a clientes específicos e imprime su recibo. Esto sumará a los ingresos en tus estadísticas.")
    tab_crear, tab_hist_ve = st.tabs(["➕ Nueva Venta Extra", "🗄️ Historial de Ventas Extra"])
    with tab_crear:
        col_c1, col_c2 = st.columns(2); fecha_ve = col_c1.date_input("Fecha de Venta", get_fecha_guate(), format="DD/MM/YYYY"); cliente_ve = col_c2.text_input("Cliente / Negocio (Ej. Panadería Santa Lucía)")
        st.markdown("#### 🥖 Detalle de Productos")
        if 've_df' not in st.session_state: st.session_state.ve_df = pd.DataFrame({"Cantidad": [0]*10, "Descripción": [""]*10, "Precio Unitario (Q)": [0.0]*10})
        with st.form("form_ventas_extra"):
            ve_edit = st.data_editor(st.session_state.ve_df, column_config={"Cantidad": st.column_config.NumberColumn(min_value=0), "Precio Unitario (Q)": st.column_config.NumberColumn(format="%.2f")}, use_container_width=True, hide_index=True)
            if st.form_submit_button("✅ Calcular Total"): st.session_state.ve_df = ve_edit; st.rerun()
        df_calc_ve = st.session_state.ve_df.copy(); df_calc_ve['Subtotal (Q)'] = df_calc_ve['Cantidad'] * df_calc_ve['Precio Unitario (Q)']; total_ve = df_calc_ve['Subtotal (Q)'].sum()
        st.markdown(f"<h3 style='text-align: right; color: #27AE60;'>Total Venta: Q {total_ve:,.2f}</h3>", unsafe_allow_html=True)
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("🧹 Limpiar Datos", use_container_width=True): st.session_state.ve_df = pd.DataFrame({"Cantidad": [0]*10, "Descripción": [""]*10, "Precio Unitario (Q)": [0.0]*10}); st.rerun()
        if col_btn2.button("💾 Guardar y Generar Recibo PDF", type="primary", use_container_width=True):
            if total_ve > 0 and cliente_ve.strip() != "":
                try:
                    with conn.session as s: s.execute(text("INSERT INTO ventas_extra (fecha, cliente, detalle_json, total) VALUES (:f, :c, :j, :t)"), {"f": fecha_ve, "c": cliente_ve, "j": df_calc_ve.to_json(orient='records'), "t": total_ve}); s.commit()
                    st.success("✅ Venta extra guardada en la base de datos."); st.session_state.ve_df = pd.DataFrame({"Cantidad": [0]*10, "Descripción": [""]*10, "Precio Unitario (Q)": [0.0]*10})
                    pdf_ve = generar_pdf_recibo_venta_extra(fecha_ve, cliente_ve, df_calc_ve, total_ve); st.download_button("📥 Descargar Recibo PDF", data=pdf_ve, file_name=f"Recibo_{cliente_ve}_{fecha_ve.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
                except Exception as e: st.error(f"Error al guardar. ¿Creaste la tabla 'ventas_extra' en Neon? {e}")
            else: st.warning("Debes ingresar un cliente y al menos un producto con precio.")
    with tab_hist_ve:
        st.markdown("### 🗄️ Historial de Ventas Extra")
        try:
            df_hist_ve = conn.query("SELECT * FROM ventas_extra ORDER BY fecha DESC, id DESC LIMIT 100", ttl=0)
            if not df_hist_ve.empty:
                df_mostrar_ve = df_hist_ve.copy(); df_mostrar_ve['fecha'] = pd.to_datetime(df_mostrar_ve['fecha']).dt.strftime('%d/%m/%Y'); st.dataframe(df_mostrar_ve[['id', 'fecha', 'cliente', 'total']], hide_index=True, use_container_width=True)
                st.markdown("---"); opc_ve = df_hist_ve.apply(lambda row: f"ID: {row['id']} | {pd.to_datetime(row['fecha']).strftime('%d/%m/%Y')} | {row['cliente']} | Q {row['total']}", axis=1).tolist(); sel_ve = st.selectbox("Selecciona una venta para Reimprimir o Eliminar:", opc_ve)
                col_h1, col_h2 = st.columns(2)
                if col_h1.button("📥 Reimprimir Recibo"):
                    idx_ve = opc_ve.index(sel_ve); r_ve = df_hist_ve.iloc[idx_ve]; df_items_re = pd.read_json(io.StringIO(r_ve['detalle_json']), orient='records'); pdf_re = generar_pdf_recibo_venta_extra(pd.to_datetime(r_ve['fecha']).date(), r_ve['cliente'], df_items_re, r_ve['total']); st.download_button("Descargar Archivo", data=pdf_re, file_name=f"Reimpresion_{r_ve['cliente']}.pdf", mime="application/pdf", type="primary")
                if col_h2.button("🗑️ Eliminar Venta", type="secondary"):
                    idx_ve = opc_ve.index(sel_ve); id_borrar = int(df_hist_ve.iloc[idx_ve]['id'])
                    with conn.session as s: s.execute(text("DELETE FROM ventas_extra WHERE id=:id"), {"id": id_borrar}); s.commit()
                    st.success("Venta eliminada exitosamente."); st.rerun()
            else: st.info("No hay ventas registradas.")
        except Exception: st.error("Error al cargar historial.")

# ------------------------------------------
# MÓDULO 8: PROVEEDORES
# ------------------------------------------
elif opcion_menu == "💳 Proveedores":
    st.title("💳 Control de Créditos y Proveedores")
    try:
        tab_prov1, tab_prov2, tab_prov3, tab_prov4 = st.tabs(["📋 Gestionar Proveedores", "➕ Registrar Deuda", "🚨 Deudas Activas", "✅ Deudas Pagadas"])
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
                st.markdown("---"); prov_a_borrar = st.selectbox("Selecciona para eliminar:", df_prov_edit['nombre'])
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
                        with conn.session as s: s.execute(text("INSERT INTO cuentas_por_pagar (proveedor_id, num_documento, fecha_compra, fecha_vencimiento, monto_total, saldo_pendiente, estado) VALUES (:p, :doc, :f_compra, :f_vence, :monto, :saldo, 'Pendiente')"), {"p": int(prov_id), "doc": num_factura, "f_compra": get_fecha_guate(), "f_vence": fecha_vencimiento, "monto": monto_credito, "saldo": monto_credito}); s.commit()
                        st.success("✅ Deuda registrada.")
        with tab_prov3:
            st.markdown("### 🚨 Listado de Deudas Pendientes")
            deudas_activas = conn.query("SELECT c.id, p.nombre as proveedor, c.num_documento as documento, p.producto_servicio as insumo, c.fecha_vencimiento as vencimiento, c.saldo_pendiente as saldo FROM cuentas_por_pagar c JOIN proveedores p ON c.proveedor_id = p.id WHERE c.estado = 'Pendiente' OR c.estado IS NULL", ttl=0)
            if not deudas_activas.empty:
                hoy = get_fecha_guate(); deudas_activas['vencimiento'] = pd.to_datetime(deudas_activas['vencimiento']).dt.date
                def asignar_semaforo(fecha_vence):
                    if pd.isnull(fecha_vence): return "⚪ Sin Fecha"
                    dias_restantes = (fecha_vence - hoy).days
                    if dias_restantes < 0: return "🔴 Vencido"
                    elif 0 <= dias_restantes <= 3: return "🟡 Próximo"
                    else: return "🟢 A tiempo"
                deudas_activas.insert(0, 'Estado', deudas_activas['vencimiento'].apply(asignar_semaforo))
                st.dataframe(deudas_activas, column_config={"vencimiento": st.column_config.DateColumn("Vencimiento", format="DD/MM/YYYY"), "saldo": st.column_config.NumberColumn("Saldo Pendiente", format="Q %.2f")}, use_container_width=True, hide_index=True)
                st.markdown("---"); st.markdown("#### 💸 Registrar Pago o Abono")
                opciones_deuda = deudas_activas.apply(lambda row: f"ID: {row['id']} | {row['proveedor']} - Doc: {row['documento']} | Saldo: Q {row['saldo']}", axis=1).tolist(); deuda_sel = st.selectbox("Selecciona la deuda a abonar/pagar:", opciones_deuda)
                col_p1, col_p2 = st.columns(2); monto_abono = col_p1.number_input("Monto a Pagar/Abonar (Q)", min_value=0.01, step=50.00)
                if col_p2.button("✅ Aplicar Pago", use_container_width=True):
                    idx_deuda = opciones_deuda.index(deuda_sel); id_deuda = int(deudas_activas.iloc[idx_deuda]['id']); saldo_actual = float(deudas_activas.iloc[idx_deuda]['saldo'])
                    if monto_abono > saldo_actual: st.warning(f"⚠️ El monto a pagar (Q {monto_abono}) no puede ser mayor al saldo pendiente (Q {saldo_actual}).")
                    else:
                        nuevo_saldo = saldo_actual - monto_abono; estado_nuevo = 'Pagado' if nuevo_saldo <= 0 else 'Pendiente'
                        with conn.session as s: s.execute(text("UPDATE cuentas_por_pagar SET saldo_pendiente = :ns, estado = :est WHERE id = :id"), {"ns": nuevo_saldo, "est": estado_nuevo, "id": id_deuda}); s.commit()
                        st.success(f"✅ Pago aplicado correctamente. Nuevo saldo: Q {nuevo_saldo:.2f}"); st.rerun()
            else: st.info("No tienes deudas pendientes registradas en este momento. ¡Felicidades!")
        with tab_prov4:
            st.markdown("### ✅ Historial de Deudas Completamente Pagadas")
            deudas_pagadas = conn.query("SELECT c.id, p.nombre as proveedor, c.num_documento as documento, p.producto_servicio as insumo, c.fecha_vencimiento as vencimiento, c.monto_total as total FROM cuentas_por_pagar c JOIN proveedores p ON c.proveedor_id = p.id WHERE c.estado = 'Pagado'", ttl=0)
            if not deudas_pagadas.empty: st.dataframe(deudas_pagadas, column_config={"vencimiento": st.column_config.DateColumn("Vencimiento", format="DD/MM/YYYY"), "total": st.column_config.NumberColumn("Total Pagado", format="Q %.2f")}, use_container_width=True, hide_index=True)
            else: st.info("Aún no tienes deudas pagadas en el historial.")
    except Exception as e: st.error(f"Error: {e}")

# ------------------------------------------
# MÓDULO 9: PLANILLA PANADEROS
# ------------------------------------------
elif opcion_menu == "👨‍🍳 Planilla Panaderos":
    st.title("👨‍🍳 Control de Producción y Recibos")
    tab_planilla, tab_recibo, tab_historial_recibos = st.tabs(["📝 1. Calcular Planilla (Detalle)", "🧾 2. Emitir Recibo de Pago", "🗄️ 3. Historial de Recibos"])
    with tab_planilla:
        col_p1, col_p2, col_p3 = st.columns(3); panadero_nombre = col_p1.selectbox("Nombre del Panadero", ["Jorge", "Otro"]); fecha_inicio_plan = col_p2.date_input("Semana del:", get_fecha_guate() - pd.Timedelta(days=6), format="DD/MM/YYYY"); fecha_fin_plan = col_p3.date_input("Al:", get_fecha_guate(), format="DD/MM/YYYY")
        st.markdown("---")
        productos_base = ["MEXICANA", "CONCHA", "CORONA", "GUANABA", "PAN INDIO", "PAN AZUCARADO", "BESITO", "PITUFO", "GUSANITO", "SAN ANTONIO", "PIRUJO", "TOSTADO REDONDO", "TOSTADO LARGO", "PESCADITO", "HOJITA", "PASTELITO", "CORTADA BLANCA", "CORTADA ROJA", "ROSQUITA", "ROYALITO", "CHURRO", "LENGUA", "CORTADA CANELA", "CORTADA FRESA", "HARINADO OFERTA", "CHAMUCO", "TOSTADO OFERTA", "CUBILETE OFERTA", "CONCHA OFERTA", "MEXICANA OFERTA", "PIQUIADA", "CHAMPU 2 SABORES", "POLVOROSAS", "CHAMPURRADAS", "ROYAL", "PAN ANTONIO", "OTROS"]
        if 'planilla_pan_df' not in st.session_state:
            df_base = pd.DataFrame({"Producto": productos_base})
            for dia in ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']: df_base[dia] = 0.00
            df_base['Libras Pasta'] = 0.00; st.session_state.planilla_pan_df = df_base
        col_b1, col_b2 = st.columns(2)
        if col_b1.button("Guardar Avance (Borrador)", use_container_width=True):
            try:
                with conn.session as s: s.execute(text("INSERT INTO borrador_planilla (id, datos) VALUES (1, :d) ON CONFLICT (id) DO UPDATE SET datos = :d"), {"d": st.session_state.planilla_pan_df.to_json(orient='records')}); s.commit()
                st.success("¡Avance guardado a salvo en la base de datos!")
            except Exception as e: st.error("⚠️ Falta crear la tabla borrador_planilla.")
        if col_b2.button("Recuperar Avance Guardado", use_container_width=True):
            try:
                with conn.session as s:
                    resultado = s.execute(text("SELECT datos FROM borrador_planilla WHERE id = 1")).fetchone()
                    if resultado and resultado[0]: st.session_state.planilla_pan_df = pd.read_json(io.StringIO(resultado[0]), orient='records'); st.success("Avance recuperado con éxito."); st.rerun()
            except Exception as e: st.error("⚠️ Falta crear la tabla borrador_planilla.")
        config_columnas = {"Producto": st.column_config.TextColumn("🍞 Producto", disabled=True)}
        for d in ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo', 'Libras Pasta']: config_columnas[d] = st.column_config.NumberColumn(d, min_value=0.0, format="%.2f")
        with st.form("form_edicion_panaderos"):
            st.info("💡 **Seguro de Edición Activado:** Escribe las Libras con calma. No se borrará nada. Presiona el botón verde de abajo para calcular los totales.")
            planilla_editada = st.data_editor(st.session_state.planilla_pan_df, hide_index=True, column_config=config_columnas, use_container_width=True, height=600)
            if st.form_submit_button("✅ Aplicar Cambios y Calcular", type="primary"): st.session_state.planilla_pan_df = planilla_editada; st.rerun()
        st.markdown("### 🧮 Subtotal de Producción")
        col_pago, col_vacio = st.columns([1, 3]); precio_quintal = col_pago.number_input("Pago por Quintal (Q)", min_value=0.00, value=135.00, step=5.00)
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']; total_libras_masa = st.session_state.planilla_pan_df[dias_semana].sum().sum(); total_quintales_masa = total_libras_masa / 100; total_libras_pasta = st.session_state.planilla_pan_df['Libras Pasta'].sum(); total_quintales_pasta = total_libras_pasta / 100; gran_total_quintales = total_quintales_masa + total_quintales_pasta; pago_total_quincena = gran_total_quintales * precio_quintal
        c_res1, c_res2, c_res3, c_res4 = st.columns(4); c_res1.metric("⚖️ Libras Masa", f"{total_libras_masa:.2f}", f"{total_quintales_masa:.2f} QQ"); c_res2.metric("🧈 Libras Pasta", f"{total_libras_pasta:.2f}", f"{total_quintales_pasta:.2f} QQ"); c_res3.metric("📦 Gran Total", f"{gran_total_quintales:.2f} QQ"); c_res4.metric("💵 Subtotal Base", f"Q {pago_total_quincena:,.2f}")
        if st.button("📥 Descargar Detalle de Planilla PDF", type="secondary"):
            if gran_total_quintales > 0:
                pdf_planilla = generar_pdf_planilla_panaderos(panadero_nombre, fecha_inicio_plan, fecha_fin_plan, st.session_state.planilla_pan_df, total_libras_masa, total_quintales_masa, total_libras_pasta, total_quintales_pasta, gran_total_quintales, precio_quintal, pago_total_quincena)
                st.download_button(label="Descargar Reporte Horizontal", data=pdf_planilla, file_name=f"Detalle_Planilla_{panadero_nombre}_{fecha_fin_plan.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
            else: st.warning("⚠️ Ingresa libras para generar el reporte.")
    with tab_recibo:
        st.markdown("### 🧾 Generar Recibo de Pago")
        col_r1, col_r2 = st.columns(2); numero_recibo = col_r1.text_input("No. de Recibo", value="25"); fecha_emision_recibo = col_r2.date_input("Fecha de Emisión", get_fecha_guate(), format="DD/MM/YYYY")
        col_e1, col_e2, col_e3 = st.columns(3); septimo_val = col_e1.number_input("➕ Séptimo (Q)", min_value=0.00, value=0.00, step=10.00); tortas_val = col_e2.number_input("➕ Tortas (Q)", min_value=0.00, value=0.00, step=10.00); tienda_val = col_e3.number_input("➖ Deducción Tienda (Q)", min_value=0.00, value=0.00, step=10.00)
        total_final_pagar = pago_total_quincena + septimo_val + tortas_val - tienda_val; st.markdown(f"<h3 style='text-align: center; color: #27AE60;'>Total a Pagar: Q {total_final_pagar:,.2f}</h3>", unsafe_allow_html=True)
        if st.button("💾 Guardar y Emitir Recibo Oficial", type="primary", use_container_width=True):
            if total_final_pagar > 0:
                try:
                    with conn.session as s:
                        s.execute(text("INSERT INTO recibos_panaderos (panadero, fecha_inicio, fecha_fin, num_recibo, fecha_emision, gran_total_qq, precio_qq, subtotal, septimo, tortas, tienda, total_pagar) VALUES (:p, :fi, :ff, :nr, :fe, :gqq, :pqq, :sub, :sep, :tor, :tie, :tot)"), {"p": panadero_nombre, "fi": fecha_inicio_plan, "ff": fecha_fin_plan, "nr": numero_recibo, "fe": fecha_emision_recibo, "gqq": gran_total_quintales, "pqq": precio_quintal, "sub": pago_total_quincena, "sep": septimo_val, "tor": tortas_val, "tie": tienda_val, "tot": total_final_pagar}); s.commit()
                    pdf_recibo = generar_pdf_recibo_panadero(numero_recibo, fecha_emision_recibo, panadero_nombre, fecha_inicio_plan, fecha_fin_plan, gran_total_quintales, precio_quintal, pago_total_quincena, septimo_val, tortas_val, tienda_val, total_final_pagar)
                    st.success("✅ ¡Recibo guardado en el historial y listo para imprimir!"); st.download_button(label="📥 Descargar Recibo para Firma", data=pdf_recibo, file_name=f"Recibo_Pago_{panadero_nombre}_{numero_recibo}.pdf", mime="application/pdf", type="secondary", use_container_width=True)
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
                    pdf_reimpresion = generar_pdf_recibo_panadero(datos_recibo['num_recibo'], pd.to_datetime(datos_recibo['fecha_emision']).date(), datos_recibo['panadero'], pd.to_datetime(datos_recibo['fecha_inicio']).date(), pd.to_datetime(datos_recibo['fecha_fin']).date(), datos_recibo['gran_total_qq'], datos_recibo['precio_qq'], datos_recibo['subtotal'], datos_recibo['septimo'], datos_recibo['tortas'], datos_recibo['tienda'], datos_recibo['total_pagar'])
                    st.download_button(label="Descargar Archivo PDF", data=pdf_reimpresion, file_name=f"Reimpresion_Recibo_{datos_recibo['panadero']}_{datos_recibo['num_recibo']}.pdf", mime="application/pdf", type="primary", use_container_width=True)
        except Exception as e: st.error(f"⚠️ Error de base de datos: {e}")

# ------------------------------------------
# MÓDULO 10: 👩‍💼 PLANILLA QUINCENAL
# ------------------------------------------
elif opcion_menu == "👩‍💼 Planilla Quincenal":
    st.title("👩‍💼 Control de Planilla Quincenal (Empleados)")
    st.write("Calcula los sueldos y genera recibos individuales para firmar sin usar Excel.")
    tab_calc, tab_hist = st.tabs(["📝 1. Calcular Planilla", "🗄️ 2. Historial y Archivo"])
    empleados_base = ["Wendy Paola Pérez", "Dania Perez", "Roberto Sagastume"]; total_filas = 10
    lista_emp_inicial = empleados_base + [""] * (total_filas - len(empleados_base)); lista_sueldos_inicial = [1675.00, 1475.00, 2000.00] + [0.0] * (total_filas - 3)
    if 'quin_id_activa' not in st.session_state: st.session_state.quin_id_activa = None
    if 'quin_f_inicio' not in st.session_state: st.session_state.quin_f_inicio = get_fecha_guate().replace(day=1)
    if 'quin_f_fin' not in st.session_state: st.session_state.quin_f_fin = get_fecha_guate().replace(day=15)
    if 'planilla_quin_df' not in st.session_state: st.session_state.planilla_quin_df = pd.DataFrame({"Empleado": lista_emp_inicial, "Sueldo Quincenal": lista_sueldos_inicial, "Días Laborados": [15.0]*total_filas, "Comisiones": [0.0]*total_filas, "Anticipos": [0.0]*total_filas, "IGSS": [0.0]*total_filas, "Tienda": [0.0]*total_filas})

    with tab_calc:
        if st.session_state.quin_id_activa: st.info(f"✏️ **Modo Edición:** Estás editando la Planilla Guardada ID: {st.session_state.quin_id_activa}")
        col1, col2 = st.columns(2); f_inicio_quin = col1.date_input("Del:", st.session_state.quin_f_inicio, format="DD/MM/YYYY"); f_fin_quin = col2.date_input("Al:", st.session_state.quin_f_fin, format="DD/MM/YYYY")
        st.markdown("---")
        config_cols = {"Empleado": st.column_config.TextColumn("👤 Empleado"), "Sueldo Quincenal": st.column_config.NumberColumn("Sueldo Base", format="%.2f"), "Días Laborados": st.column_config.NumberColumn("Días Lab.", format="%.2f"), "Comisiones": st.column_config.NumberColumn("Comisiones", format="%.2f"), "Anticipos": st.column_config.NumberColumn("Anticipos", format="%.2f"), "IGSS": st.column_config.NumberColumn("IGSS", format="%.2f"), "Tienda": st.column_config.NumberColumn("Tienda", format="%.2f")}
        with st.form("form_edicion_quin"):
            st.info("💡 **Seguro de Edición Activado:** Llena las casillas tranquilamente. No se borrará nada. Al terminar, presiona el botón verde de abajo para calcular los totales.")
            df_edit_quin = st.data_editor(st.session_state.planilla_quin_df, column_config=config_cols, use_container_width=True, hide_index=True)
            if st.form_submit_button("✅ Aplicar Cambios y Calcular", type="primary"): st.session_state.planilla_quin_df = df_edit_quin; st.rerun()
        st.markdown("---"); st.markdown("### 🧮 Vista Previa: Planilla Calculada")
        df_calc = st.session_state.planilla_quin_df.copy()
        df_calc['Empleado'] = df_calc['Empleado'].astype(str).str.strip()
        df_calc = df_calc[(df_calc['Empleado'] != "") & (df_calc['Empleado'].str.lower() != "nan")] 
        df_calc['Sueldo Prop.'] = (df_calc['Sueldo Quincenal'] / 15 * df_calc['Días Laborados']).round(2)
        df_calc['Total Devengado'] = df_calc['Sueldo Prop.'] + df_calc['Comisiones']
        df_calc['Total Descuentos'] = df_calc['Anticipos'] + df_calc['IGSS'] + df_calc['Tienda']
        df_calc['Líquido a Recibir'] = df_calc['Total Devengado'] - df_calc['Total Descuentos']
        st.dataframe(df_calc, use_container_width=True, hide_index=True)
        st.markdown("<br>", unsafe_allow_html=True); col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("📥 Descargar Recibos Individuales", type="secondary", use_container_width=True):
                if not df_calc.empty:
                    pdf_recibos = generar_pdf_recibos_quincenales(f_inicio_quin, f_fin_quin, df_calc); st.download_button("Descargar Recibos (Para Firmar)", data=pdf_recibos, file_name=f"Boletas_Pago_{f_inicio_quin.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", use_container_width=True)
                else: st.warning("⚠️ La planilla está vacía.")
        with col_btn2:
            if st.button("📥 Descargar Tabla General", type="secondary", use_container_width=True):
                if not df_calc.empty:
                    pdf_resumen = generar_pdf_planilla_empleados_resumen(f_inicio_quin, f_fin_quin, df_calc); st.download_button("Descargar Tabla PDF", data=pdf_resumen, file_name=f"Resumen_Planilla_{f_inicio_quin.strftime('%d-%m-%Y')}.pdf", mime="application/pdf", use_container_width=True)
                else: st.warning("⚠️ La planilla está vacía.")
        with col_btn3:
            if st.button("💾 Guardar Oficialmente", type="primary", use_container_width=True):
                datos_json = st.session_state.planilla_quin_df.to_json(orient='records'); total_pagar_quin = float(df_calc['Líquido a Recibir'].sum())
                try:
                    with conn.session as s:
                        if st.session_state.quin_id_activa: s.execute(text("UPDATE planillas_quincenales SET fecha_inicio=:fi, fecha_fin=:ff, total_pagar=:tot, datos_json=:json WHERE id=:id"), {"fi": f_inicio_quin, "ff": f_fin_quin, "tot": total_pagar_quin, "json": datos_json, "id": st.session_state.quin_id_activa}); st.success("✅ Planilla actualizada exitosamente en el historial.")
                        else: s.execute(text("INSERT INTO planillas_quincenales (fecha_inicio, fecha_fin, total_pagar, datos_json) VALUES (:fi, :ff, :tot, :json)"), {"fi": f_inicio_quin, "ff": f_fin_quin, "tot": total_pagar_quin, "json": datos_json}); st.success("✅ ¡Planilla guardada como nueva en el historial!")
                        s.commit()
                except Exception as e: st.error(f"⚠️ Error al guardar. Detalle: {e}")

    with tab_hist:
        st.markdown("### 🗄️ Historial de Planillas Guardadas")
        st.write("Consulta, edita o elimina las planillas anteriores.")
        try:
            df_historial = conn.query("SELECT id, fecha_inicio, fecha_fin, total_pagar, datos_json FROM planillas_quincenales ORDER BY fecha_inicio DESC, id DESC", ttl=0)
            if not df_historial.empty:
                df_mostrar = df_historial[['id', 'fecha_inicio', 'fecha_fin', 'total_pagar']].copy()
                df_mostrar['fecha_inicio'] = pd.to_datetime(df_mostrar['fecha_inicio']).dt.strftime('%d/%m/%Y'); df_mostrar['fecha_fin'] = pd.to_datetime(df_mostrar['fecha_fin']).dt.strftime('%d/%m/%Y')
                st.dataframe(df_mostrar, column_config={"id": "ID Planilla", "fecha_inicio": "Inicio", "fecha_fin": "Fin", "total_pagar": st.column_config.NumberColumn("Total Pagado", format="Q %.2f")}, hide_index=True, use_container_width=True)
                st.markdown("---")
                opciones = df_historial.apply(lambda row: f"ID: {row['id']} | {pd.to_datetime(row['fecha_inicio']).strftime('%d/%m/%Y')} al {pd.to_datetime(row['fecha_fin']).strftime('%d/%m/%Y')} | Q {row['total_pagar']}", axis=1).tolist(); seleccion = st.selectbox("Seleccionar Planilla:", opciones)
                col_acc1, col_acc2, col_acc3 = st.columns(3)
                if col_acc1.button("📂 Cargar para Editar", type="primary", use_container_width=True):
                    idx = opciones.index(seleccion); fila = df_historial.iloc[idx]
                    st.session_state.quin_id_activa = int(fila['id']); st.session_state.quin_f_inicio = fila['fecha_inicio']; st.session_state.quin_f_fin = fila['fecha_fin']
                    df_cargado = pd.read_json(io.StringIO(fila['datos_json']), orient='records')
                    if 'Bono 14' in df_cargado.columns: df_cargado = df_cargado.drop(columns=['Bono 14'])
                    st.session_state.planilla_quin_df = df_cargado
                    st.success("Planilla cargada. Ve a la Pestaña 1 para verla/editarla."); st.rerun()
                if col_acc2.button("🗑️ Eliminar Planilla", type="secondary", use_container_width=True):
                    idx = opciones.index(seleccion); id_borrar = int(df_historial.iloc[idx]['id'])
                    with conn.session as s: s.execute(text("DELETE FROM planillas_quincenales WHERE id=:id"), {"id": id_borrar}); s.commit()
                    if st.session_state.quin_id_activa == id_borrar: st.session_state.quin_id_activa = None
                    st.success("Planilla eliminada definitivamente."); st.rerun()
                if col_acc3.button("✨ Limpiar Pantalla", use_container_width=True):
                    st.session_state.quin_id_activa = None; st.session_state.quin_f_inicio = get_fecha_guate().replace(day=1); st.session_state.quin_f_fin = get_fecha_guate().replace(day=15)
                    st.session_state.planilla_quin_df = pd.DataFrame({"Empleado": lista_emp_inicial, "Sueldo Quincenal": lista_sueldos_inicial, "Días Laborados": [15.0]*total_filas, "Comisiones": [0.0]*total_filas, "Anticipos": [0.0]*total_filas, "IGSS": [0.0]*total_filas, "Tienda": [0.0]*total_filas})
                    st.success("Listo para crear una nueva planilla."); st.rerun()
            else: st.info("Aún no tienes planillas guardadas en el historial.")
        except Exception as e: st.error(f"Esperando a que crees la tabla 'planillas_quincenales' en Neon. Detalle: {e}")

# ------------------------------------------
# MÓDULO 11: REPORTE PDF MENSUAL
# ------------------------------------------
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

# ------------------------------------------
# MÓDULO 12: USUARIOS
# ------------------------------------------
elif opcion_menu == "👥 Usuarios":
    st.title("👥 Gestión de Usuarios")
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Crear Nuevo Usuario"):
            with st.form("form_crear_usr"):
                n_usr = st.text_input("Nombre de Usuario").lower(); n_pwd = st.text_input("Contraseña")
                if st.form_submit_button("Guardar Usuario"):
                    if n_usr and n_pwd:
                        try:
                            with conn.session as s: s.execute(text("INSERT INTO usuarios_app (usuario, password) VALUES (:u, :p)"), {"u": n_usr, "p": n_pwd}); s.commit()
                            st.success(f"Usuario '{n_usr}' creado."); st.rerun()
                        except Exception as e: st.error("Error al crear (quizás el usuario ya existe).")
                    else: st.warning("Llena ambos campos.")
    try:
        df_usr = conn.query("SELECT id, usuario, password FROM usuarios_app ORDER BY id", ttl=0)
        if not df_usr.empty:
            st.markdown("#### ✏️ Editar / Ver Usuarios Actuales")
            df_edit_usr = st.data_editor(df_usr, column_config={"id": None, "usuario": "Usuario", "password": "Password"}, hide_index=True, use_container_width=True)
            if st.button("💾 Guardar Cambios"):
                with conn.session as s:
                    for i, r in df_edit_usr.iterrows(): s.execute(text("UPDATE usuarios_app SET usuario=:u, password=:p WHERE id=:id"), {"u": r['usuario'], "p": r['password'], "id": r['id']})
                    s.commit()
                st.success("Usuarios actualizados."); st.rerun()
            st.markdown("---"); usr_borrar = st.selectbox("Selecciona para ELIMINAR:", df_usr['usuario'])
            if st.button("🗑️ Eliminar Usuario"):
                if usr_borrar == 'admin' or usr_borrar == 'roberto': st.warning("No puedes eliminar a los administradores principales.")
                else:
                    with conn.session as s: s.execute(text("DELETE FROM usuarios_app WHERE usuario=:u"), {"u": usr_borrar}); s.commit()
                    st.success("Usuario eliminado."); st.rerun()
    except Exception as e: st.error("Error al cargar usuarios.")
