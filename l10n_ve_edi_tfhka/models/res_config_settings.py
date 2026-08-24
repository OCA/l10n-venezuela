from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .client import (
    ICP_API_ENVIRONMENT,
    ICP_BASE_URL,
    ICP_PRODUCTION_URL,
    TFHKA_API_URL_TEST,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    TFHKA_TEST_INVOICE_PAYLOAD = {
        "documentoElectronico": {
            "encabezado": {
                "identificacionDocumento": {
                    "tipoDocumento": "01",
                    "numeroDocumento": "50370",
                    "numeroPlanillaImportacion": "",
                    "numeroExpedienteImportacion": "",
                    "serieFacturaAfectada": "",
                    "numeroFacturaAfectada": "",
                    "fechaFacturaAfectada": "",
                    "montoFacturaAfectada": "",
                    "comentarioFacturaAfectada": "",
                    "regimenEspTributacion": "",
                    "fechaEmision": "23/01/2026",
                    "fechaVencimiento": "23/01/2026",
                    "horaEmision": "10:52:00 am",
                    "tipoDePago": "Inmediato",
                    "serie": "",
                    "sucursal": "",
                    "tipoDeVenta": "Interna",
                    "moneda": "VES",
                    "transaccionId": "",
                    "urlPdf": "",
                },
                "comprador": {
                    "tipoIdentificacion": "J",
                    "numeroIdentificacion": "59858589-9",
                    "razonSocial": "PRUEBA DE EMPRESA",
                    "direccion": "CARACAS",
                    "pais": "VE",
                    "notificar": "Si",
                    "telefono": ["212-202-0811"],
                    "correo": ["prueba@yopmail.com"],
                },
                "totales": {
                    "nroItems": "2",
                    "montoGravadoTotal": "100.00",
                    "montoExentoTotal": "200.00",
                    "montoPercibidoTotal": "0.00",
                    "subtotalAntesDescuento": "300.00",
                    "totalDescuento": None,
                    "totalRecargos": None,
                    "subtotal": "300.00",
                    "totalIVA": "16.00",
                    "montoTotalConIVA": "316.00",
                    "totalAPagar": "316.00",
                    "montoEnLetras": (
                        "trescientos dieciséis bolivares con cero centimos"
                    ),
                    "listaRecargo": None,
                    "listaDescBonificacion": None,
                    "impuestosSubtotal": [
                        {
                            "codigoTotalImp": "E",
                            "alicuotaImp": "00.00",
                            "baseImponibleImp": "200.00",
                            "valorTotalImp": "00.00",
                        },
                        {
                            "codigoTotalImp": "G",
                            "alicuotaImp": "16.00",
                            "baseImponibleImp": "100.00",
                            "valorTotalImp": "16.00",
                        },
                    ],
                    "otrosImpuestosSubtotal": None,
                    "formasPago": [
                        {
                            "descripcion": "Tarjeta de débito",
                            "fecha": "23/01/2026",
                            "forma": "05",
                            "monto": "316.00",
                            "moneda": "BSD",
                            "tipoCambio": "0.0000",
                        }
                    ],
                    "totalIGTF": "0.00",
                    "totalIGTF_VES": "0.00",
                    "montoTotalOTI": None,
                    "montoTotalIVAyOTI": None,
                },
                "totalesOtraMoneda": {
                    "moneda": "USD",
                    "tipoCambio": "352.7063",
                    "montoGravadoTotal": "0.28",
                    "montoPercibidoTotal": "0.00",
                    "montoExentoTotal": "0.57",
                    "subtotal": "0.85",
                    "totalAPagar": "0.90",
                    "totalIVA": "0.05",
                    "montoTotalConIVA": "0.90",
                    "montoEnLetras": "cero dolares con noventa centimos",
                    "subtotalAntesDescuento": "0.85",
                    "totalDescuento": None,
                    "totalRecargos": None,
                    "listaRecargo": None,
                    "listaDescBonificacion": None,
                    "impuestosSubtotal": [
                        {
                            "codigoTotalImp": "E",
                            "alicuotaImp": "00.00",
                            "baseImponibleImp": "0.57",
                            "valorTotalImp": "00.00",
                        },
                        {
                            "codigoTotalImp": "G",
                            "alicuotaImp": "16.00",
                            "baseImponibleImp": "0.28",
                            "valorTotalImp": "0.05",
                        },
                    ],
                    "otrosImpuestosSubtotal": None,
                    "montoTotalOTI": None,
                    "montoTotalIVAyOTI": None,
                },
            },
            "detallesItems": [
                {
                    "numeroLinea": "1",
                    "codigoCIIU": "0198",
                    "codigoPLU": "0198599",
                    "indicadorBienoServicio": "1",
                    "descripcion": "PRODUCTO O SERVICIO A FACTURAR 1",
                    "cantidad": "1",
                    "unidadMedida": "4L",
                    "precioUnitario": "100.00",
                    "precioUnitarioDescuento": None,
                    "montoBonificacion": None,
                    "descripcionBonificacion": None,
                    "descuentoMonto": "0.00",
                    "recargoMonto": "0",
                    "precioItem": "100.00",
                    "precioAntesDescuento": "100.00",
                    "codigoImpuesto": "G",
                    "tasaIVA": "16",
                    "valorIVA": "16.00",
                    "valorTotalItem": "116",
                    "infoAdicionalItem": [],
                    "listaItemOTI": None,
                },
                {
                    "numeroLinea": "2",
                    "codigoCIIU": "0198",
                    "codigoPLU": "0198598",
                    "indicadorBienoServicio": "2",
                    "descripcion": "PRODUCTO O SERVICIO A FACTURAR 2",
                    "cantidad": "1",
                    "unidadMedida": "4L",
                    "precioUnitario": "200.00",
                    "precioUnitarioDescuento": None,
                    "montoBonificacion": None,
                    "descripcionBonificacion": None,
                    "descuentoMonto": "0.00",
                    "recargoMonto": "0",
                    "precioItem": "200.00",
                    "precioAntesDescuento": "200.00",
                    "codigoImpuesto": "E",
                    "tasaIVA": "0",
                    "valorIVA": "0.00",
                    "valorTotalItem": "200",
                    "infoAdicionalItem": [],
                    "listaItemOTI": None,
                },
            ],
        }
    }

    tfhka_api_environment = fields.Selection(
        [
            ("test", "Pruebas"),
            ("production", "Producción"),
        ],
        string="Ambiente HKA",
        default="test",
        config_parameter=ICP_API_ENVIRONMENT,
    )
    tfhka_base_url = fields.Char(
        string="URL API HKA",
        compute="_compute_tfhka_base_url",
        inverse="_inverse_tfhka_base_url",
        readonly=False,
    )
    tfhka_production_url = fields.Char(
        string="URL producción HKA",
        config_parameter=ICP_PRODUCTION_URL,
        help="URL del ambiente de producción de The Factory HKA.",
    )
    tfhka_username = fields.Char(
        string="TFHKA Username",
        config_parameter="l10n_ve_edi_tfhka.username",
    )
    tfhka_password = fields.Char(
        string="TFHKA Password",
        config_parameter="l10n_ve_edi_tfhka.password",
    )
    tfhka_iva_supplier_retention_edi_serie = fields.Char(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_tfhka_serie",
        readonly=False,
    )
    tfhka_iva_supplier_retention_edi_sucursal = fields.Char(
        related=(
            "company_id.iva_supplier_retention_journal_id.l10n_ve_edi_tfhka_sucursal"
        ),
        readonly=False,
    )
    tfhka_islr_supplier_retention_edi_serie = fields.Char(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_tfhka_serie",
        readonly=False,
    )
    tfhka_islr_supplier_retention_edi_sucursal = fields.Char(
        related=(
            "company_id.islr_supplier_retention_journal_id.l10n_ve_edi_tfhka_sucursal"
        ),
        readonly=False,
    )

    @api.depends("tfhka_api_environment", "tfhka_production_url")
    def _compute_tfhka_base_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        configured_url = icp.get_param(ICP_BASE_URL, default=TFHKA_API_URL_TEST)
        for settings in self:
            if settings.tfhka_api_environment == "production":
                production_url = (
                    (settings.tfhka_production_url or "").strip().rstrip("/")
                )
                settings.tfhka_base_url = production_url or configured_url
            else:
                settings.tfhka_base_url = TFHKA_API_URL_TEST

    def _inverse_tfhka_base_url(self):
        for settings in self:
            url = (settings.tfhka_base_url or "").strip().rstrip("/")
            if not url:
                continue
            if settings.tfhka_api_environment == "production":
                settings.tfhka_production_url = url

    def set_values(self):
        res = super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        if self.tfhka_api_environment == "production":
            production_url = (self.tfhka_production_url or "").strip().rstrip("/")
            if not production_url:
                raise UserError(
                    _(
                        "Indique la URL de producción de The Factory HKA o seleccione "
                        "el ambiente Pruebas."
                    )
                )
            icp.set_param(ICP_BASE_URL, production_url)
        else:
            icp.set_param(ICP_BASE_URL, TFHKA_API_URL_TEST)
        return res

    def action_test_tfhka_connection(self):
        self.ensure_one()
        if not self.tfhka_username or not self.tfhka_password:
            raise UserError(_("TFHKA username and password are required."))
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        client.authenticate(self.tfhka_username, self.tfhka_password)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Connection with The Factory HKA was successful."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_test_tfhka_invoice_send(self):
        self.ensure_one()
        if not self.tfhka_username or not self.tfhka_password:
            raise UserError(_("TFHKA username and password are required."))
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        auth = client.authenticate(self.tfhka_username, self.tfhka_password)
        token = auth.get("token")
        if not token:
            raise UserError(_("TFHKA token was not returned."))
        response = client.issue_document(self.TFHKA_TEST_INVOICE_PAYLOAD, token)
        message = response.get("mensaje") or _(
            "Test invoice payload sent successfully."
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }
