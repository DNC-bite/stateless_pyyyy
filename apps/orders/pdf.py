"""Factura en PDF (mismo diseño que la de Spring: encabezado, cliente/entrega, ítems, IVA y total)."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.utils import desglose_iva

NEGRO = colors.black
GRIS_TEXTO = colors.HexColor("#444444")
GRIS_SUBTITULO = colors.HexColor("#646464")
FONDO_CELDA = colors.HexColor("#F8F8F8")
BORDE_CELDA = colors.HexColor("#E1E1E1")
VERDE = colors.HexColor("#009650")
NARANJA = colors.HexColor("#C77700")
ROJO = colors.HexColor("#CC0000")


def _estilo(nombre, **kw):
    base = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=GRIS_TEXTO)
    base.update(kw)
    return ParagraphStyle(nombre, **base)


TITULO = _estilo("titulo", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=NEGRO)
SUBTITULO = _estilo("subtitulo", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=GRIS_SUBTITULO)
TEXTO = _estilo("texto")
NEGRITA = _estilo("negrita", fontName="Helvetica-Bold", textColor=NEGRO)
ENCABEZADO = _estilo("enc", fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
DERECHA = _estilo("der", alignment=TA_RIGHT)
DERECHA_NEGRITA = _estilo("dern", fontName="Helvetica-Bold", alignment=TA_RIGHT, textColor=NEGRO)
PIE = _estilo("pie", fontSize=7, leading=9, textColor=colors.gray, alignment=TA_CENTER)


def _p(texto, estilo):
    return Paragraph(escape(str(texto)), estilo)


def _dinero(valor) -> str:
    return f"$ {int(valor):,}"


def generar_factura_pdf(venta) -> bytes:
    envio = venta.envio
    usuario = venta.usuario
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
                            title=f"Factura {venta.numero_factura}", author=settings.EMPRESA_NOMBRE, pageCompression=0)
    ancho = A4[0] - 72
    elementos = []

    # --- Encabezado: empresa (izquierda) y número / fecha / estado (derecha)
    color_estado = {"CANCELADO": ROJO, "PAGO PENDIENTE": NARANJA}.get(venta.estado_factura, VERDE)
    fecha = timezone.localtime(venta.created_at).strftime("%d/%m/%Y %H:%M") if venta.created_at else "Fecha actual"
    izquierda = [
        _p("STATELESS", TITULO),
        _p(f"{settings.EMPRESA_NOMBRE} | NIT: {settings.EMPRESA_NIT}", SUBTITULO),
        _p(f"Régimen Común • {settings.FACTURA_SUBTITULO}", TEXTO),
        _p(settings.EMPRESA_CIUDAD, TEXTO),
    ]
    derecha = [
        Paragraph(f"FACTURA N° {escape(venta.numero_factura)}", _estilo("n", fontName="Helvetica-Bold", fontSize=14,
                                                                        leading=18, textColor=NEGRO, alignment=TA_RIGHT)),
        _p(f"Fecha de Emisión: {fecha}", DERECHA),
        Paragraph(f"Estado: {escape(venta.estado_factura)}", _estilo("e", fontName="Helvetica-Bold", textColor=color_estado,
                                                                      alignment=TA_RIGHT)),
    ]
    encabezado = Table([[izquierda, derecha]], colWidths=[ancho * 0.6, ancho * 0.4])
    encabezado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    elementos += [encabezado, Spacer(1, 14)]

    # --- Cliente y entrega/pago
    entrega = ", ".join(x for x in (envio.direccion, envio.apartamento) if x)
    ubicacion = ", ".join(x for x in (envio.ciudad, envio.departamento) if x)
    cliente = [
        _p("ADQUIRIENTE / CLIENTE", SUBTITULO),
        _p(f"Nombre: {usuario.name or 'Cliente'}", NEGRITA),
        _p(f"Email: {usuario.email}", TEXTO),
    ]
    destino = [
        _p("DATOS DE ENTREGA & PAGO", SUBTITULO),
        _p(f"Destino: {entrega}, {ubicacion}", TEXTO),
        _p(f"Método de Pago: {venta.get_metodo_pago_display().upper()}", TEXTO),
    ]
    if envio.destinatario:
        destino.insert(2, _p(f"Recibe: {envio.destinatario}", TEXTO))
    tabla_cliente = Table([[cliente, destino]], colWidths=[ancho / 2, ancho / 2])
    tabla_cliente.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FONDO_CELDA), ("BOX", (0, 0), (-1, -1), 0.5, BORDE_CELDA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDE_CELDA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elementos += [tabla_cliente, Spacer(1, 14)]

    # --- Ítems
    filas = [[_p(t, ENCABEZADO) for t in ("Descripción de Prenda", "Cant.", "Precio Unit.", "IVA (19%)", "Subtotal")]]
    for item in venta.items.select_related("producto", "variante").all():
        descripcion = item.producto.nombre
        if item.variante:
            descripcion += f" ({item.variante.color})"
        if item.talla:
            descripcion += f" · Talla {item.talla}"
        subtotal = item.precio_unitario * item.cantidad
        filas.append([
            _p(descripcion, TEXTO),
            Paragraph(str(item.cantidad), _estilo("c", alignment=TA_CENTER)),
            _p(_dinero(item.precio_unitario), DERECHA),
            _p(_dinero(desglose_iva(subtotal)[1]), DERECHA),
            _p(_dinero(subtotal), DERECHA_NEGRITA),
        ])
    items = Table(filas, colWidths=[ancho * 0.40] + [ancho * 0.15] * 4, repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, BORDE_CELDA), ("BOX", (0, 0), (-1, -1), 0.5, BORDE_CELDA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos += [items, Spacer(1, 14)]

    # --- Totales (la misma función de IVA que usan la pantalla, el Excel y los reportes)
    base, iva = desglose_iva(venta.total)
    totales = Table([
        [_p("Subtotal Base Imponible:", TEXTO), _p(_dinero(base), DERECHA)],
        [_p("IVA Discriminado (19%):", TEXTO), _p(_dinero(iva), DERECHA)],
        [_p("Despacho Express Nacional:", TEXTO), _p("GRATIS ($ 0)", DERECHA)],
        [Paragraph("TOTAL FACTURA COP:", _estilo("t", fontName="Helvetica-Bold", fontSize=10, textColor=colors.white)),
         Paragraph(escape(_dinero(venta.total)), _estilo("tv", fontName="Helvetica-Bold", fontSize=11, textColor=colors.white,
                                                         alignment=TA_RIGHT))],
    ], colWidths=[ancho * 0.30, ancho * 0.20], hAlign="RIGHT")
    totales.setStyle(TableStyle([
        ("BACKGROUND", (0, 3), (-1, 3), NEGRO), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 3), (-1, 3), 8), ("BOTTOMPADDING", (0, 3), (-1, 3), 8),
    ]))
    elementos += [totales, Spacer(1, 18)]

    elementos.append(_p(
        "Esta factura es un título valor según el Artículo 774 del Código de Comercio colombiano. "
        f"Para soporte o devoluciones escribe a {settings.EMPRESA_CORREO_SOPORTE}", PIE))

    doc.build(elementos)
    return buffer.getvalue()
