#!/usr/bin/env python3
# ruff: noqa: E501
"""Genera articulos.md con texto íntegro de cada providencia (un archivo por norma)."""

import logging
import re
import shutil
import urllib.request
from pathlib import Path

_logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
AGENT = Path("/home/odoo/.cursor/projects/workspace/agent-tools")

FOOTERS = (
    "#### PODCAST",
    "#### SUSCRIPCIÓN",
    "Comuníquese y publíquese.",
    "Comuníquese y publíquese",
    "IVECOFI- ©",
)

PA71_ART08 = """Artículo 8. Los contribuyentes ordinarios del impuesto al valor agregado, los sujetos que realicen operaciones en Almacenes Libres de Impuestos (Duty Free Shops); y los sujetos que no califiquen como contribuyentes ordinarios del impuesto al valor agregado, deben utilizar exclusivamente Máquinas Fiscales para la emisión de facturas, cuando concurran las siguientes circunstancias:

1. Obtengan ingresos brutos anuales superiores a un mil quinientas unidades tributarias (1.500 U.T.).

2. Realicen mayor número de operaciones de ventas o prestaciones de servicios con sujetos que no utilicen la factura como prueba del desembolso o del crédito fiscal según corresponda.

3. Desarrollen conjunta o separadamente alguna de las actividades que se indican a continuación:

a. Venta de alimentos, bebidas, cigarrillos y demás manufacturas de tabaco, golosinas, confiterías, bombonerías y otros similares.

b. Venta de productos de limpieza de uso doméstico e industrial.

c. Ventas de partes, piezas, accesorios, lubricantes, refrigerantes y productos de limpieza de vehículos automotores, así como el servicio de mantenimiento y reparación de vehículos automotores, siempre que estas operaciones se efectúen independientemente de la venta de los vehículos. A los efectos de este numeral se entenderá por vehículo automotor cualquier medio de transporte de tracción mecánica.

d. Venta de materiales de construcción, artículos de ferretería, herramientas, equipos y materiales de fontanería, plomería y repuestos, partes y piezas de aire acondicionado, así como la venta de pinturas, barnices y lacas, vidrios y objetos de vidrio, vidrios y el servicio de instalación, cuando corresponda

e. Venta de artículos de perfumería, cosméticos y de tocador.

f. Venta de relojes y artículos de joyería, así como su reparación y servicio técnico.

g. Venta de juguetes para niños y adultos, muñecos que representan personas o criaturas, modelos a escalas, sus accesorios, así como la venta o alquiler de películas y juegos.

h. Venta de artículos de cuero, textiles, calzados, prendas de vestir, accesorios para prendas de vestir, artículos deportivos, maletas, bolsos y carteras, accesorios de viaje y artículos similares, y sus servicios de reparación.

i. Venta de flores, plantas, semillas, abonos, así como los servicios de floristería.

j. Servicio de comida y bebidas para su consumo dentro o fuera de establecimiento tales como: restaurantes, bares, cantinas, panaderías, cafés o similares; incluyendo los servicios de comidas y bebidas a domicilio.

k. Venta de productos farmacéuticos, medicinales, nutricionales, ortopédicos, lentes y sus accesorios.

l. Venta de equipos de computación, sus partes, piezas, accesorios y consumibles, así como la venta de equipos de impresión y fotocopiado, sus partes, piezas y accesorios.

m. Servicios de belleza, estética y acondicionamiento físico, tales como peluquerías, barberías, gimnasios, centro de masajes corporales y servicios conexos.

n. Servicio de lavado y pulitura de vehículos automotores.

o. Servicio de estacionamiento de vehículos automotores.

p. Servicio de fotocopiado, impresión, encuadernación y revelado fotográfico.

q.- Servicios de alojamiento y hospedaje, prestados en hoteles, moteles, posadas y casa de huéspedes.

r.- Servicios de alquiler de cajas de correo o apartados postales (P.O. BOX).

s.- Venta de electrodomésticos o sus accesorios y repuestos.

t.- Ventas de libros, papelerías y artículos de oficina.

u.- Venta de muebles para el hogar y oficinas.

Los sujetos pasivos dedicados a las actividades económicas previstas en el literal j del numeral 3 del presente artículo, deben emplear como medio de facturación obligatoria máquinas fiscales, independientemente que hayan obtenido o no la cantidad de ingresos establecidos en el numeral 1 de este artículo.

El Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), mediante Providencia Administrativa de carácter general, podrá incluir o excluir determinadas actividades, a los fines de la aplicación, del presente artículo.

A los fines del cálculo de los ingresos brutos y del número de operaciones a que se refieren los numerales 1 y 2 de este artículo, se deben considerar las operaciones realizadas durante el año calendario inmediato anterior al que esté en curso. Una vez nacida la obligación de utilizar máquinas fiscales, el sujeto no podrá utilizar otro medio de facturación, salvo en los casos previstos en el Artículo 11 de esta Providencia Administrativa."""


def trim_footer(text):
    for marker in FOOTERS:
        if marker in text:
            text = text.split(marker)[0]
    return text.rstrip()


def trim_header(text):
    m = re.search(
        r"(Capítulo I|DISPOSICIONES TRANSITORIAS|Disposiciones Transitorias|"
        r"Artículo 1\.|Articulo 1\.|Artículo 1°|Artículo 1\.)",
        text,
        re.IGNORECASE,
    )
    if m:
        text = text[m.start() :]
    return text


def fix_pa71_art08(text):
    pattern = re.compile(
        r"(?m)^Artículo 8\.?.*?(?=^Artículo 9)",
        re.DOTALL | re.IGNORECASE,
    )
    return pattern.sub(PA71_ART08 + "\n\n", text, count=1)


def write_providencia(
    folder, code, gaceta, source_text, fix_art08=False, skip_trim=False
):
    folder_path = BASE / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    articulos_dir = folder_path / "articulos"
    if articulos_dir.exists():
        shutil.rmtree(articulos_dir)

    body = trim_footer(source_text)
    if not skip_trim:
        body = trim_header(body)
    if fix_art08:
        body = fix_pa71_art08(body)

    content = (
        f"# {code}\n\n"
        f"**Gaceta Oficial:** {gaceta}\n\n"
        f"Texto íntegro transcrito de la Gaceta Oficial.\n\n"
        f"---\n\n"
        f"{body}\n"
    )
    (folder_path / "articulos.md").write_text(content, encoding="utf-8")

    readme = (
        f"# {code}\n\n"
        f"| Campo | Valor |\n"
        f"|-------|-------|\n"
        f"| **Código** | {code} |\n"
        f"| **Gaceta Oficial** | {gaceta} |\n\n"
        f"Texto íntegro en [articulos.md](./articulos.md).\n"
    )
    (folder_path / "README.md").write_text(readme, encoding="utf-8")
    _logger.info("%s: articulos.md (%s caracteres)", folder, len(body))


def main():
    write_providencia(
        "SNAT-2011-00071",
        "SNAT/2011/00071",
        "N° 39.795 (08/11/2011)",
        (AGENT / "c8ac8e17-0a65-4026-b5a7-4cca00fbacb7.txt").read_text(
            encoding="utf-8"
        ),
        fix_art08=True,
    )
    write_providencia(
        "SNAT-2024-000102",
        "SNAT/2024/000102",
        "N° 43.032 (19/12/2024)",
        (AGENT / "45b96864-6b93-43c0-b44b-ddb9c2631391.txt").read_text(
            encoding="utf-8"
        ),
    )
    write_providencia(
        "SNAT-2018-0141",
        "SNAT/2018/0141",
        "N° 41.518 (06/11/2018)",
        (AGENT / "aec9efcf-b6d4-4fe2-97c1-046af284c1ac.txt").read_text(
            encoding="utf-8"
        ),
    )
    pa121 = (
        (AGENT / "pa-2024-121.txt").read_text(encoding="utf-8")
        if (AGENT / "pa-2024-121.txt").exists()
        else None
    )
    if not pa121:
        pa121 = """Capítulo I Disposiciones Generales

Artículo 1.La presente Providencia Administrativa tiene por objeto regular las condiciones y requisitos que deben cumplir los proveedores de sistemas informáticos utilizados para la emisión de facturas y otros documentos fiscales, a los efectos de ser homologados y autorizados por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).

Artículo 2.Las personas naturales, las sociedades cooperativas y personas jurídicas domiciliadas en el país, que sean proveedores de sistemas informáticos utilizados para la emisión de facturas y otros documentos fiscales, deben estar previamente autorizados por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).

Capítulo II Requisitos y Condiciones de los Sistemas Informáticos

Artículo 3.Los sistemas informáticos deben cumplir con los siguientes requisitos:

1. Garantizar la integridad, continuidad, confiabilidad, conservación, accesibilidad, legibilidad, trazabilidad, inalterabilidad e inviolabilidad de los registros.
2. Remisión por medios electrónicos al Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), de forma continua, segura, correcta, íntegra, automática, consecutiva, inmediata y fehaciente de los registros de facturación o de interés fiscal que sean requeridos.
3. Llevar el registro de eventos que recopile automáticamente, en el momento en que se produzcan, determinadas interacciones con el sistema informático, operaciones realizadas con él o los sucesos ocurridos durante su uso.
4. Permitir la corrección o anulación de la factura únicamente mediante la emisión de notas de débito o crédito según corresponda, de forma que se conserven inalterables los datos originalmente registrados.
5. Garantizar funcionalidades que permitan el seguimiento de los datos registrados de forma clara y fiable. Todos los datos registrados deben encontrarse correctamente fechados, indicando la hora en que se efectúa el registro.
6. Garantizar la correcta aplicación dentro de su funcionalidad de las normas establecidas en la Ley del Impuesto al Valor Agregado y su reglamento, que regulan el hecho imponible, considerando este último el inicio de un proceso que finalice en la emisión de un documento fiscal válido.
7. Garantizar el cumplimiento de lo establecido en la normativa vigente que establece las normas generales para la emisión de facturas y otros documentos.
8. Otorgar una clave de consulta al Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT) que permita el acceso al sistema informático así como a la interfaz de programación de aplicaciones y al resto de las funcionalidades exigidas sobre la información de los registros fiscales y de eventos.

Capítulo III De los Proveedores de Sistemas Informáticos

Sección I De la Autorización

Artículo 4.Los proveedores de sistemas informáticos utilizados para emisión de facturas y otros documentos fiscales deberán presentar ante la Intendencia Nacional Tributos Internos del Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), una solicitud de autorización, la cual debe cumplir con lo siguiente:

Ficha técnica del Sistema Informático

1. Aplicativo.
2. Lenguaje.
3. Base de datos.
4. Monitoreo y auditoría.
5. Tipo de conexión con las plataformas.

En el caso de personas jurídicas:

1. Anexar copia del Acta Constitutiva y su última modificación, si la hubiere, con vista al original.
2. Copia de las cédulas de identidad del representante legal y de los socios principales.

Artículo 5.Consignados todos los recaudos, la Intendencia Nacional de Tributos Internos, deberá notificar al solicitante la fecha, lugar y hora en la que la Gerencia de Fiscalización conjuntamente con la Gerencia General de Tecnología de Información y Comunicaciones realizará la evaluación técnica del sistema informático.

Finalizada la evaluación técnica se emitirá un informe que indique si cumple o no con las características, condiciones y requerimientos técnicos exigidos en esta Providencia Administrativa para la homologación del sistema informático. Este informe tendrá carácter vinculante.

Artículo 6.Una vez emitido el informe indicado en artículo anterior, la Intendencia Nacional de Tributos Internos del Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), tendrá un plazo de quince (15) días hábiles para emitir el acto administrativo que acuerde o niegue la homologación y autorización del sistema informático para la emisión de facturas y otros documentos fiscales.

Artículo 7.La Intendencia Nacional de Tributos Internos del Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), negará la solicitud de homologación y autorización al proveedor del sistema informático, cuando:

Algunos de los socios, directores, gerentes o administradores del solicitante:

1. Sea o haya sido socio director, gerente o administrador de alguna empresa a la cual se le haya revocado la autorización como Proveedor de sistemas informáticos.
2. Sea empleado o funcionario al servicio de los órganos y entes públicos nacionales, estadales y municipales.
3. Sea cónyuge o pariente dentro del primer grado de consanguinidad o primero de afinidad, de funcionarios que ocupen cargos directivos en el Servido Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).
4. Haya sido condenado mediante sentencia firme por la comisión de delitos relacionados con delincuencia organizada, financiamiento al terrorismo, legitimación de capitales, contra el patrimonio público o por delitos de naturaleza aduanera o tributaria.

Sección II Obligaciones de los Proveedores de Sistemas Informáticos

Artículo 8.Los proveedores de sistemas informáticos para la emisión de facturas y otros documentos fiscales, están obligados a:

1. El solicitante se encuentre omiso en la presentación de declaraciones o en el pago de los tributos a los que esté obligado.
2. No comercializar sistemas informáticos que no estén homologados y autorizados por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).
3. No facilitar a sus clientes programas que permitan desviar de la contabilidad fiscal a una contabilidad alterna, registros de facturas y otros documentos fiscales que no se incluyan en las declaraciones tributarias que deben realizar los sujetos pasivos.
4. Garantizar la imposibilidad de conexión de cualquier equipo o dispositivo no fiscal o no homologado por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT) con el sistema informático.
5. Notificar de forma inmediata al Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), cualquier irregularidad o alteración en el sistema informático de facturación, efectuada por el sujeto pasivo que adquirió el sistema informático.

Artículo 9.En el caso de desarrollar una nueva versión del sistema informático para la emisión de facturas y otros documentos fiscales, el proveedor autorizado debe solicitar la homologación ante la Intendencia Nacional de Tributos Internos del Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).

Artículo 10.A efectos de lo previsto en el artículo 9 de esta Providencia Administrativa, el proveedor del sistema informático para la emisión de facturas y otros documentos fiscales, debe presentar un escrito ante la Intendencia Nacional de Tributos Internos del Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), la cual dispone de un lapso de quince (15) días hábiles para emitir el documento que acuerde o niegue la homologación de la nueva versión del sistema informático.

Artículo 11.Autorizada la nueva versión del sistema informático, el proveedor del sistema informático para la emisión de facturas y otros documentos fiscales, podrá efectuar de forma automática la instalación, sin afectar el funcionamiento del sistema ni la integridad de los datos.

Artículo 12.Son responsables tanto el desarrollador como el proveedor de sistemas informáticos para la emisión de facturas y otros documentos fiscales, si los usuarios realizan cualquier cambio, actualización o modificación de los sistemas informáticos que no hayan sido autorizados y homologados por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).

Sección III De la Revocatoria

Artículo 13.El Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), a través de la Intendencia Nacional Tributos Internos podrá revocar la autorización otorgada a los proveedores de sistemas informáticos utilizados para emisión de facturas y otros documentos fiscales, cuando:

1. Se incumplan las disposiciones establecidas en esta Providencia Administrativa y en la legislación tributaria.
2. Incurra en alguno de los supuestos establecidos en la Ley Especial contra los Delitos Informáticos.
3. Se produzcan alteraciones en los mecanismos de seguridad, violaciones de las bases de datos o de las memorias fiscales, o cualquier otro hecho que impida el normal funcionamiento del sistema informático emisor de facturas y otros documentos fiscales, debido a acciones u omisiones del proveedor autorizado.
4. Hubiere incumplido con la presentación de declaraciones o con el pago de los tributos nacionales a los que esté obligado.
5. Haya efectuado cambio de domicilio, sin informar al Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), conforme a la normativa vigente.
6. Haya sido condenado mediante sentencia firme por la comisión de delitos relacionados con delincuencia organizada, financiamiento al terrorismo, legitimación de capitales, contra el patrimonio público o por delitos de naturaleza aduanera o tributaria.

Parágrafo Único. Se entenderá por alteración de los registros fiscales, la ocultación o eliminación de cualquier registro originalmente generado, la ocultación o modificación, total o parcial de los datos, la adición de registros de facturación, simulados o falsos, distintos a los originalmente generados y registrados por el sistema informático.

Disposiciones Transitorias

Primera. Los sujetos pasivos tendrán noventa días (90) días continuos contados a partir de la fecha de publicación de esta Providencia Administrativa en la Gaceta Oficial de la República Bolivariana de Venezuela, para adaptar o adquirir los sistemas informáticos homologados y autorizados por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), para la emisión de facturas y otros documentos fiscales.

Segunda. En el caso de las Imprentas Digitales autorizadas, tendrán un plazo de treinta (30) días hábiles a partir de la entrada en vigencia de esta Providencia Administrativa para informar al Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), sobre los sistemas informáticos que están utilizando para su respectiva homologación, para lo cual deberán cumplir con los requisitos establecidos en el artículo 4 de la presente providencia.

Disposiciones Finales

Primera. La Intendencia Nacional de Tributos Internos, la Gerencia de Fiscalización y la Gerencia General de Control Aduanero y Tributario conjuntamente con la Gerencia General de Tecnología de Información y Comunicaciones, podrán acceder a los sistemas informáticos emisores de facturas y otros documentos fiscales, con el fin de verificar la correcta operación del sistema, realizar auditorías fiscales y solicitar reportes detallados de todas las transacciones realizadas.

Segunda. La Intendencia Nacional de Tributos Internos, la Gerencia de Fiscalización conjuntamente con la Gerencia General de Tecnología de Información y Comunicaciones, podrá hacer evaluaciones posteriores a los proveedores de los sistemas informáticos autorizados para constatar el cumplimiento de lo establecido en esta Providencia Administrativa.

Tercera. El incumplimiento de las normas previstas en esta Providencia Administrativa será sancionado de conformidad con las normas establecidas en el Decreto Constituyente que dicta el Código Orgánico Tributario.

Cuarta. Los sujetos pasivos estarán obligados a utilizar solo sistemas informáticos autorizados y homologados por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT) para la emisión de facturas y otros documentos fiscales.

Quinta. Los proveedores de sistemas informáticos para la emisión de facturas y otros documentos fiscales serán sancionados como coautores en los casos en que los sujetos pasivos que adquieran el sistema informático lo utilicen para realizar u omitir registros que conlleven a la defraudación tributaria de conformidad con lo establecido en el Título III, Capítulo IV del Decreto Constituyente mediante el cual se dicta el Código Orgánico Tributario.

Sexta. El Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), publicará en su Portal Fiscal, los datos de los proveedores de sistemas informáticos utilizados para emisión de facturas y otros documentos fiscales debidamente autorizados y de los que se les hubiere revocado la autorización.

Séptima. El Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT), a los efectos del cumplimiento de las disposiciones a que diere lugar la aplicación de esta Providencia Administrativa, publicará en el portal fiscal los instructivos y formatos con las especificaciones relativas a proveedores de sistemas informáticos utilizados para emisión de facturas y otros documentos fiscales.

Octava. A los efectos de esta Providencia Administrativa se entiende por portal fiscal la página Web, https://declaraciones.seniat.gob.ve, o cualquiera otra que sea creada para sustituirla por el Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT).

Novena. Esta Providencia Administrativa entrará en vigencia a partir de su publicación en la Gaceta Oficial de la República Bolivariana de Venezuela."""
    write_providencia(
        "SNAT-2024-000121",
        "SNAT/2024/000121",
        "N° 43.032 (19/12/2024)",
        pa121,
    )
    pa013 = """Artículo 1. Sin menoscabo de los supuestos de no sujeción establecidos en el artículo 5º del Decreto N" 4.647, de fecha 25 de febrero de 2022, publicado en la Gaceta Oficial de la República Bolivariana de Venezuela N° 6.689 Extraordinario, de la misma fecha, se designan como responsables del impuesto a las grandes transacciones financieras, en calidad de agentes de percepción, a los sujetos pasivos calificados como especiales, por los pagos recibidos en moneda distinta a la de curso legal en el país, o en criptomonedas o criptoactivos diferentes a los emitidos por la República Bolivariana de Venezuela, sin mediación de instituciones financieras, de las personas naturales, jurídicas y las entidades económicas sin personalidad jurídica.

Articulo 2. La percepción del impuesto debe practicarse el mismo día en el que se verifique el hecho imponible sujeto a ésta.

Articulo 3. Para proceder al enteramiento del impuesto percibido, los agentes de percepción deberán:

1. Realizar transmisión quincenal de conformidad con las especificaciones previstas en el Instructivo técnico que a tal efecto establezca el Servicio Nacional Integrado de Administración Aduanera y Tributaria.
2. Declarar a través del Portal Fiscal y pagar en las Oficinas Receptoras de Fondos Nacionales de manera quincenal, conforme al Calendario de Pagos de las Retenciones del Impuesto al Valor Agregado para Contribuyentes Especiales, las cantidades percibidas, de acuerdo con las especificaciones previstas en el Instructivo Técnico que a tal fin dicte el Servicio Nacional Integrado de Administración Aduanera y Tributaria.

Articulo 4. Cuando se practique una percepción indebida o se entere cantidades superiores a las efectivamente percibidas, y el monto sea transferido a la cuenta del Tesoro Nacional abierta para la recaudación de este impuesto, el agente de percepción deberá restituir al contribuyente el monto indebidamente percibido y solicitar posteriormente al Servicio Nacional Integrado de Administración Aduanera y Tributaria el reintegro de dicho monto, conforme al procedimiento establecido en el Decreto con Rango, Valor y Fuerza de Ley del Código Orgánico Tributario.

Articulo 5. Los sujetos pasivos especiales que utilicen máquina fiscal, deben ajustarla a los fines de reflejar en la factura la alícuota impositiva y el impuesto a las grandes transacciones financieras correspondiente, por las operaciones señaladas en el artículo 1° de esta Providencia Administrativa.

Articulo 6. Los sujetos pasivos especiales que emitan facturas en formato o forma libre, además de los requisitos previstos en la Providencia Administrativa que establece las normas Generales para la emisión de factura y otros documentos, deberán reflejar en la factura la alícuota impositiva y el monto del impuesto a las grandes transacciones financieras por las operaciones señaladas en el artículo 1° de esta Providencia Administrativa.

En los casos de las facturas en formato impreso podrá reflejar la alícuota impositiva y el monto del impuesto a las grandes transacciones financieras de manera manual, hasta agotar su existencia.

Articulo 7. Esta Providencia Administrativa entrará en vigencia el 28 de marzo de 2022."""
    write_providencia(
        "SNAT-2022-000013",
        "SNAT/2022/000013",
        "N° 42.339 (17/03/2022)",
        pa013,
    )
    build_ley_iva()


def extract_ivecofi_html(html):
    """Extrae texto legal del bloque com-content de páginas IVECOFI."""
    match = re.search(
        r'class="[^"]*com-content[^"]*"[^>]*>(.*?)'
        r'(?:<div[^>]*class="[^"]*sidebar|SUSCRIPCIÓN)',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return ""
    chunk = match.group(1)
    text = re.sub(r"<br\s*/?>", "\n", chunk, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_ivecofi_markdown(text):
    """Limpia texto extraído de IVECOFI."""
    for marker in FOOTERS:
        if marker in text:
            text = text.split(marker)[0]
    lines = []
    skip_prefixes = (
        "Ley de IVA -",
        "Ley de Impuesto al Valor Agregado -",
        "Régimen Tributario",
        "IVECOFI",
        "Título I",
        "Título II",
        "Título III",
        "Título IV",
        "Título V",
        "Título VI",
        "Título VII",
        "Título VIII",
    )
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("Ley de Impuesto al Valor Agregado") and "Gaceta" in s:
            continue
        if any(s.startswith(p) for p in skip_prefixes) and len(s) < 80:
            continue
        if s in ("SUSCRÍBETE", "BOLETÍN", "WHATSAPP"):
            continue
        lines.append(s)
    body = "\n".join(lines)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body


def fetch_ivecofi_titulo(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    return clean_ivecofi_markdown(extract_ivecofi_html(html))


def build_ley_iva():
    base_url = (
        "https://tributos.ivecofi.net/informacion/legislacion/leyes/"
        "ley-impuesto-valor-agregado/titulo-"
    )
    roman = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii"]
    parts = []
    for i, r in enumerate(roman):
        text = fetch_ivecofi_titulo(f"{base_url}{r}")
        if i == 0:
            m = re.search(r"(TÍTULO I\b|Artículo 1\.)", text)
            if m:
                text = text[m.start() :]
        else:
            m = re.search(
                r"(TÍTULO [IVXLC]+.*|Capítulo I.*|Artículo \d+)",
                text,
                re.IGNORECASE,
            )
            if m:
                text = text[m.start() :]
        parts.append(trim_footer(text))
    body = "\n\n".join(parts)
    write_providencia(
        "LEY-IVA",
        "Decreto Constituyente — Ley del Impuesto al Valor Agregado",
        "N° 6.507 Extraordinario (29/01/2020)",
        body,
        skip_trim=True,
    )


if __name__ == "__main__":
    main()
