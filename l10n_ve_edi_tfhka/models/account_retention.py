import base64
import binascii
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _inherit = "account.retention"

    l10n_ve_edi_tfhka_show_sent_actions = fields.Boolean(
        compute="_compute_l10n_ve_edi_tfhka_sent_actions",
        string="TFHKA: retencion EDI enviada",
    )
    l10n_ve_edi_tfhka_sent_pdf_url = fields.Char(
        compute="_compute_l10n_ve_edi_tfhka_sent_actions",
        string="URL PDF (TFHKA)",
    )
    l10n_ve_edi_tfhka_sent_document_url = fields.Char(
        compute="_compute_l10n_ve_edi_tfhka_sent_actions",
        string="URL documento fiscal (TFHKA)",
    )
    l10n_ve_edi_tfhka_pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        copy=False,
        readonly=True,
        string="PDF TFHKA (DescargaArchivo)",
    )

    @api.depends(
        "l10n_ve_edi_response_json",
        "l10n_ve_edi_send_state",
        "state",
        "type",
        "type_retention",
        "company_id",
    )
    def _compute_l10n_ve_edi_tfhka_sent_actions(self):
        for retention in self:
            retention.l10n_ve_edi_tfhka_show_sent_actions = (
                retention._l10n_ve_edi_tfhka_replace_retention_report_with_digital_pdf()
            )
            retention.l10n_ve_edi_tfhka_sent_pdf_url = False
            retention.l10n_ve_edi_tfhka_sent_document_url = False
            if (
                retention._l10n_ve_edi_get_retention_edi_provider() != "tfhka"
                or not retention.l10n_ve_edi_response_json
            ):
                continue
            pdf_url, doc_url = (
                retention._tfhka_extract_public_urls_from_stored_response()
            )
            retention.l10n_ve_edi_tfhka_sent_pdf_url = pdf_url
            retention.l10n_ve_edi_tfhka_sent_document_url = doc_url

    def _l10n_ve_edi_tfhka_replace_retention_report_with_digital_pdf(self):
        self.ensure_one()
        return (
            self.state == "emitted"
            and self.type == "in_invoice"
            and self.type_retention in ("iva", "islr")
            and self._l10n_ve_edi_retention_uses_digital()
            and self._l10n_ve_edi_get_retention_edi_provider() == "tfhka"
            and self.l10n_ve_edi_send_state == "sent"
        )

    def _tfhka_normalize_http_url(self, value):
        if not value or not isinstance(value, str):
            return False
        url = value.strip()
        if url.lower().startswith(("http://", "https://")):
            return url
        return False

    def _tfhka_extract_public_urls_from_stored_response(self):
        self.ensure_one()
        pdf_url = False
        doc_url = False
        raw = self.l10n_ve_edi_response_json
        if not raw:
            return pdf_url, doc_url
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return pdf_url, doc_url
        blobs = [data]
        resultado = data.get("resultado")
        if isinstance(resultado, dict):
            blobs.append(resultado)
        pdf_keys = ("urlPdf", "urlPDF", "pdfUrl", "PdfUrl", "URLPdf", "enlacePdf")
        doc_keys = (
            "urlDocumento",
            "urlConsulta",
            "enlaceDocumento",
            "urlVerificacion",
            "linkDocumento",
        )
        for blob in blobs:
            if not isinstance(blob, dict):
                continue
            for key in pdf_keys:
                if not pdf_url:
                    pdf_url = self._tfhka_normalize_http_url(blob.get(key))
            for key in doc_keys:
                url = self._tfhka_normalize_http_url(blob.get(key))
                if url and url != pdf_url:
                    doc_url = url
            if not doc_url:
                url = self._tfhka_normalize_http_url(blob.get("url"))
                if url and url != pdf_url:
                    doc_url = url
        if doc_url == pdf_url:
            doc_url = False
        return pdf_url, doc_url

    def _tfhka_get_descarga_archivo_payload(self):
        self.ensure_one()
        return {
            "serie": self._tfhka_get_retention_serie() or "",
            "tipoDocumento": self._tfhka_get_retention_document_type(),
            "numeroDocumento": self._tfhka_get_retention_numero_documento(),
        }

    def _tfhka_extract_pdf_bytes_from_download_response(self, data):
        if not isinstance(data, dict):
            return None

        def _decode_b64_to_pdf(value):
            if not isinstance(value, str) or len(value) < 50:
                return None
            raw = value.strip().replace("\n", "").replace("\r", "").replace(" ", "")
            pad = len(raw) % 4
            if pad:
                raw += "=" * (4 - pad)
            try:
                decoded = base64.b64decode(raw, validate=False)
            except (binascii.Error, TypeError):
                return None
            if len(decoded) >= 5 and decoded[:4] == b"%PDF":
                return decoded
            return None

        resultado = data.get("resultado")
        if isinstance(resultado, str):
            pdf_bytes = _decode_b64_to_pdf(resultado)
            if pdf_bytes:
                return pdf_bytes
        blobs = [data]
        if isinstance(resultado, dict):
            blobs.append(resultado)
        keys = (
            "archivo",
            "archivoBase64",
            "archivoPdf",
            "pdfBase64",
            "pdf",
            "base64",
            "datos",
            "contenido",
            "documento",
            "data",
        )
        for blob in blobs:
            if not isinstance(blob, dict):
                continue
            for key in keys:
                pdf_bytes = _decode_b64_to_pdf(blob.get(key))
                if pdf_bytes:
                    return pdf_bytes
        return None

    def _tfhka_get_retention_pdf_bytes_via_descarga_archivo(self):
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            return None, _("Configure usuario y clave TFHKA en Ajustes.")
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        try:
            auth = client.authenticate(username, password)
            token = auth.get("token")
            if not token:
                return None, _("La API TFHKA no devolvio token JWT.")
            response = client.download_file(
                self._tfhka_get_descarga_archivo_payload(), token
            )
        except UserError as exc:
            return None, str(exc)
        except Exception as exc:
            _logger.exception("TFHKA DescargaArchivo retention_id=%s", self.id)
            return None, str(exc)
        pdf_bytes = self._tfhka_extract_pdf_bytes_from_download_response(response)
        if pdf_bytes:
            return pdf_bytes, None
        return None, _(
            "La respuesta de DescargaArchivo no incluye un PDF en base64 reconocible."
        )

    def _tfhka_return_pdf_attachment_download_action(self, pdf_bytes):
        self.ensure_one()
        datas = base64.b64encode(pdf_bytes)
        safe_name = (self.number or f"retention_{self.id}").replace("/", "_")
        filename = f"TFHKA_{safe_name}.pdf"
        vals = {
            "name": filename,
            "type": "binary",
            "datas": datas,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
        }
        attachment = self.l10n_ve_edi_tfhka_pdf_attachment_id
        if attachment:
            attachment.sudo().write(vals)
        else:
            attachment = self.env["ir.attachment"].sudo().create(vals)
            self.sudo().write({"l10n_ve_edi_tfhka_pdf_attachment_id": attachment.id})
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _l10n_ve_edi_tfhka_try_attach_official_pdf(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_tfhka_pdf_attachment_id
        if attachment and attachment.datas:
            return True
        pdf_bytes, err = self._tfhka_get_retention_pdf_bytes_via_descarga_archivo()
        if not pdf_bytes:
            _logger.warning(
                "TFHKA: PDF oficial no disponible (DescargaArchivo) "
                "retention_id=%s err=%s",
                self.id,
                err,
            )
            return False
        self._tfhka_return_pdf_attachment_download_action(pdf_bytes)
        return True

    def _l10n_ve_edi_tfhka_ensure_retention_pdf_report(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_tfhka_pdf_attachment_id
        if attachment and attachment.datas:
            return True
        return self._l10n_ve_edi_tfhka_try_attach_official_pdf()

    def action_l10n_ve_edi_tfhka_print_retention(self):
        self.ensure_one()
        if not self._l10n_ve_edi_tfhka_replace_retention_report_with_digital_pdf():
            raise UserError(
                _(
                    "Solo puede imprimir el comprobante digital cuando la retencion "
                    "fue enviada a TFHKA."
                )
            )
        pdf_bytes, api_err = self._tfhka_get_retention_pdf_bytes_via_descarga_archivo()
        if pdf_bytes:
            return self._tfhka_return_pdf_attachment_download_action(pdf_bytes)
        attachment = self.l10n_ve_edi_tfhka_pdf_attachment_id
        if attachment and attachment.datas:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}?download=true",
                "target": "self",
            }
        pdf_url = self.l10n_ve_edi_tfhka_sent_pdf_url
        if not pdf_url:
            _pdf_url, pdf_url = self._tfhka_extract_public_urls_from_stored_response()
        if pdf_url:
            return {"type": "ir.actions.act_url", "url": pdf_url, "target": "new"}
        msg = api_err or _("No se pudo obtener el PDF.")
        raise UserError(
            _(
                "Descarga por API (/api/DescargaArchivo) no disponible: %(err)s "
                "Tampoco hay urlPdf en la respuesta guardada."
            )
            % {"err": msg}
        )

    def action_l10n_ve_edi_tfhka_open_sent_document_url(self):
        self.ensure_one()
        doc_url = self.l10n_ve_edi_tfhka_sent_document_url
        if not doc_url:
            _, doc_url = self._tfhka_extract_public_urls_from_stored_response()
        if not doc_url:
            raise UserError(
                _(
                    "No hay URL de consulta del documento en la respuesta "
                    "guardada de TFHKA."
                )
            )
        return {"type": "ir.actions.act_url", "url": doc_url, "target": "new"}

    def _l10n_ve_edi_on_dispatch_success(self, response):
        super()._l10n_ve_edi_on_dispatch_success(response)
        self.ensure_one()
        if self._l10n_ve_edi_get_retention_edi_provider() != "tfhka":
            return
        self._l10n_ve_edi_tfhka_try_attach_official_pdf()

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        if provider == "tfhka":
            return self._tfhka_build_retention_documento_electronico_payload()
        return super()._l10n_ve_edi_build_payload_for_provider(provider)

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        if self._l10n_ve_edi_get_retention_edi_provider() != "tfhka":
            return super()._l10n_ve_edi_dispatch_payload(payload)
        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            return {"success": False, "error": _("Credenciales TFHKA no configuradas.")}
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        try:
            auth = client.authenticate(username, password)
            token = auth.get("token")
            if not token:
                return {
                    "success": False,
                    "error": _("La API TFHKA no devolvio token JWT."),
                }
            response = client.issue_document(payload, token)
            return {"success": True, "response": response}
        except UserError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            _logger.exception("TFHKA retention send retention_id=%s", self.id)
            return {"success": False, "error": str(exc)}

    def _tfhka_get_retention_document_type(self):
        self.ensure_one()
        mapping = {"iva": "05", "islr": "06"}
        doc_type = mapping.get(self.type_retention)
        if not doc_type:
            raise UserError(_("Tipo de retencion no soportado para EDI TFHKA."))
        return doc_type

    def _tfhka_get_retention_journal(self):
        self.ensure_one()
        return self._l10n_ve_edi_get_tfhka_reference_journal()

    def _tfhka_serie_from_journal(self, journal):
        if not journal:
            return ""
        raw = ""
        if "l10n_ve_edi_tfhka_serie" in journal._fields:
            raw = journal.l10n_ve_edi_tfhka_serie or ""
        if not (raw or "").strip() and "series_correlative" in journal._fields:
            raw = journal.series_correlative or ""
        serie = re.sub(r"[^0-9A-Za-z]", "", (raw or "").strip())
        return serie[:20]

    def _tfhka_sucursal_from_journal(self, journal):
        if not journal or "l10n_ve_edi_tfhka_sucursal" not in journal._fields:
            return ""
        raw = (journal.l10n_ve_edi_tfhka_sucursal or "").strip()
        return re.sub(r"[^0-9A-Za-z]", "", raw)[:6]

    def _tfhka_get_retention_serie(self):
        self.ensure_one()
        return self._tfhka_serie_from_journal(self._tfhka_get_retention_journal())

    def _tfhka_get_retention_sucursal(self):
        self.ensure_one()
        return self._tfhka_sucursal_from_journal(self._tfhka_get_retention_journal())

    def _tfhka_format_date(self, value):
        if not value:
            value = fields.Date.context_today(self)
        if isinstance(value, str):
            return value
        return value.strftime("%d/%m/%Y")

    def _tfhka_get_issue_hour(self):
        self.ensure_one()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return f"{now.strftime('%I:%M:%S')} {now.strftime('%p').lower()}"

    def _tfhka_format_rate(self, percent_value):
        return f"{(percent_value or 0.0) / 100.0:.2f}"

    def _tfhka_get_retention_numero_documento(self):
        self.ensure_one()
        digits = re.sub(r"\D", "", self.number or "")
        if digits:
            return digits[:19]
        return str(self.id or 0).zfill(14)[:19]

    def _tfhka_get_numero_comp_retencion(self):
        self.ensure_one()
        if self.type_retention == "islr":
            return self._tfhka_get_retention_numero_documento()
        digits = re.sub(r"\D", "", self.number or "")
        if len(digits) >= 14:
            sequence = digits[6:].lstrip("0")
            return sequence or "0"
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", self.number or "")
        return cleaned[:50] if cleaned else str(self.id or 0)

    def _tfhka_get_retention_transaccion_id(self):
        self.ensure_one()
        if self.type_retention == "islr":
            return self._tfhka_get_retention_numero_documento()
        prefix = {"iva": "RIVA", "islr": "RISLR"}.get(self.type_retention, "RET")
        return f"{prefix}{self._tfhka_get_retention_numero_documento()}"[:50]

    def _tfhka_format_codigo_concepto(self, code):
        digits = re.sub(r"\D", "", code or "")
        if not digits:
            return None
        padded = digits.zfill(3)
        return padded[-4:] if len(padded) > 4 else padded

    def _tfhka_get_currency_code(self):
        self.ensure_one()
        currency = re.sub(
            r"[^0-9A-Za-z]", "", self.company_currency_id.name or "VES"
        ).upper()
        return (currency or "VES")[:3]

    def _tfhka_build_sujeto_retenido(self):
        self.ensure_one()
        partner = self._l10n_ve_edi_get_subject_partner()
        prefix, number = self._l10n_ve_edi_get_subject_identification()
        phone = partner.mobile or partner.phone or ""
        email_list = [partner.email] if partner.email else []
        phone_list = [phone] if phone else []
        return {
            "tipoIdentificacion": prefix,
            "numeroIdentificacion": number,
            "razonSocial": (partner.name or "")[:255],
            "direccion": (partner.street or partner.contact_address_inline or "N/A")[
                :255
            ],
            "pais": (partner.country_id.code or "VE")[:2],
            "telefono": phone_list or None,
            "correo": email_list or None,
            "notificar": "Si" if (partner.email or phone) else "No",
        }

    def _tfhka_build_retention_identificacion_documento(self):
        self.ensure_one()
        issue_date = self._tfhka_format_date(self.date)
        ident = {
            "tipoDocumento": self._tfhka_get_retention_document_type(),
            "numeroDocumento": self._tfhka_get_retention_numero_documento(),
            "tipoTransaccion": None,
            "fechaEmision": issue_date,
            "horaEmision": self._tfhka_get_issue_hour(),
            "anulado": False,
            "tipoDePago": "Inmediato",
            "serie": self._tfhka_get_retention_serie() or "",
            "sucursal": None,
            "tipoDeVenta": "interna",
            "moneda": self._tfhka_get_currency_code(),
            "transaccionId": self._tfhka_get_retention_transaccion_id(),
            "urlPdf": None,
        }
        if self.type_retention == "iva":
            ident["fechaVencimiento"] = issue_date
            ident["tipoDeVenta"] = "Interna"
            ident["sucursal"] = self._tfhka_get_retention_sucursal() or ""
        return ident

    def _tfhka_build_encabezado_totales(self):
        self.ensure_one()
        if self.type_retention == "islr":
            invoice_total = sum(
                line.invoice_total
                or (line.move_id.amount_total if line.move_id else 0.0)
                for line in self.retention_line_ids
            )
            return {
                "nroItems": str(len(self.retention_line_ids) or 1),
                "montoGravadoTotal": "0.00",
                "montoExentoTotal": "0.00",
                "totalDescuento": "0.00",
                "subtotal": "0.00",
                "totalIVA": "0.00",
                "montoTotalConIVA": self._l10n_ve_edi_format_decimal(invoice_total),
                "totalAPagar": "0.00",
                "montoEnLetras": "n/a",
            }
        return {
            "nroItems": "0",
            "montoGravadoTotal": "0",
            "montoExentoTotal": "0",
            "totalDescuento": "0.00",
            "subtotal": "0.00",
            "totalIVA": "0.00",
            "montoTotalConIVA": "0",
            "totalAPagar": "0.00",
            "montoEnLetras": "N/A",
        }

    def _tfhka_build_totales_retencion(self):
        self.ensure_one()
        totals = {
            "totalBaseImponible": self._l10n_ve_edi_format_decimal(
                self.total_invoice_amount
            ),
            "numeroCompRetencion": self._tfhka_get_numero_comp_retencion(),
            "fechaEmisionCR": self._tfhka_format_date(self.date),
        }
        if self.type_retention == "iva":
            totals["totalRetenido"] = self._l10n_ve_edi_format_decimal(
                self.total_retention_amount
            )
            totals["esNegativo"] = False
            totals["totalIVA"] = self._l10n_ve_edi_format_decimal(self.amount_tax)
            totals["totalISRL"] = ""
            totals["totalIGTF"] = ""
        if self.type_retention == "islr":
            totals["totalIVA"] = None
            totals["totalRetenido"] = None
            totals["totalISRL"] = self._l10n_ve_edi_format_decimal(
                self.total_retention_amount
            )
            totals["totalIGTF"] = None
            totals["tipoComprobante"] = "1"
        return totals

    def _tfhka_normalize_control_number(self, move):
        control = (move.l10n_ve_control_number or "").strip()
        if not control:
            return None
        normalized = re.sub(r"[^A-Za-z0-9]", "", control)
        return normalized[:15] if normalized else None

    def _tfhka_get_move_control_number(self, move):
        control = self._tfhka_normalize_control_number(move)
        if not control:
            raise UserError(
                _(
                    "La factura de proveedor «%(invoice)s» no tiene numero de control "
                    "fiscal valido para TFHKA."
                )
                % {"invoice": move.display_name}
            )
        if not re.match(r"^[A-Za-z0-9]{1,15}$", control):
            raise UserError(
                _(
                    "El numero de control «%(control)s» de la factura «%(invoice)s» no "
                    "cumple el formato TFHKA (alfanumerico, maximo 15 caracteres)."
                )
                % {"control": control, "invoice": move.display_name}
            )
        return control

    def _tfhka_invoice_document_number_from_move(self, move):
        fiscal_number = self._l10n_ve_edi_get_vendor_invoice_fiscal_number(move)
        if not fiscal_number:
            raise UserError(
                _(
                    "La factura de proveedor «%(invoice)s» no tiene numero de factura "
                    "fiscal para TFHKA."
                )
                % {"invoice": move.display_name}
            )
        digits = re.sub(r"\D", "", fiscal_number)
        if not digits:
            raise UserError(
                _(
                    "El numero de factura «%(number)s» de «%(invoice)s» no es valido "
                    "para TFHKA."
                )
                % {"number": fiscal_number, "invoice": move.display_name}
            )
        return digits.zfill(11)[:19]

    def _tfhka_invoice_document_type_from_move(self, move):
        if move.move_type == "in_refund":
            return "02"
        return "01"

    def _tfhka_line_monto_iva(self, line):
        if line.iva_amount:
            return line.iva_amount
        base = line.invoice_amount or 0.0
        rate = (line.aliquot or 0.0) / 100.0
        return base * rate

    def _tfhka_get_invoice_exempt_amount(self, move):
        exempt = 0.0
        for inv_line in move.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ):
            if not inv_line.tax_ids or all(
                float_compare(t.amount, 0.0, precision_digits=2) == 0
                for t in inv_line.tax_ids
            ):
                exempt += abs(inv_line.price_subtotal)
        return exempt

    def _tfhka_line_monto_total(self, line, move, monto_exento=0.0):
        base = line.invoice_amount or 0.0
        monto_iva = self._tfhka_line_monto_iva(line)
        return base + monto_exento + monto_iva

    def _tfhka_line_retenido(self, line):
        iva_amount = self._tfhka_line_monto_iva(line)
        retention_rate = (line.related_percentage_tax_base or 0.0) / 100.0
        computed = iva_amount * retention_rate
        if line.retention_amount and abs(line.retention_amount - computed) < 0.05:
            return line.retention_amount
        return computed

    def _tfhka_line_retenido_islr(self, line):
        base = line.invoice_amount or 0.0
        tax_base_rate = (line.related_percentage_tax_base or 100.0) / 100.0
        fee_rate = (line.related_percentage_fees or 0.0) / 100.0
        subtract = line.related_amount_subtract_fees or 0.0
        computed = max(0.0, (base * tax_base_rate * fee_rate) - subtract)
        if (
            line.retention_amount is not None
            and abs(line.retention_amount - computed) < 0.05
        ):
            return line.retention_amount
        return computed

    def _tfhka_get_line_codigo_concepto(self, line):
        self.ensure_one()
        code = line.code
        if not code and line.payment_concept_id:
            concept_lines = line.payment_concept_id.line_payment_concept_ids
            partner = (
                line.move_id._l10n_ve_withholding_partner() if line.move_id else None
            )
            if partner and partner.type_person_id:
                matched = concept_lines.filtered(
                    lambda cl: cl.type_person_id.id == partner.type_person_id.id
                )
                if matched:
                    code = matched[0].code
            if not code and concept_lines:
                code = concept_lines[0].code
        formatted = self._tfhka_format_codigo_concepto(code)
        if not formatted:
            raise UserError(
                _(
                    "La linea de retencion ISLR «%(line)s» no tiene codigo de concepto "
                    "valido para TFHKA."
                )
                % {"line": line.display_name}
            )
        return formatted

    def _tfhka_build_detalles_retencion(self):
        self.ensure_one()
        details = []
        currency = self._tfhka_get_currency_code()
        moves_with_exempt = set()
        for index, line in enumerate(self.retention_line_ids, start=1):
            move = line.move_id
            if not move:
                raise UserError(_("Hay lineas de retencion sin factura asociada."))
            if self.type_retention == "islr":
                retenido = self._tfhka_line_retenido_islr(line)
                detail = {
                    "numeroLinea": str(index),
                    "fechaDocumento": self._tfhka_format_date(
                        move.invoice_date or move.date
                    ),
                    "serieDocumento": "",
                    "tipoDocumento": self._tfhka_invoice_document_type_from_move(move),
                    "numeroDocumento": self._tfhka_invoice_document_number_from_move(
                        move
                    ),
                    "numeroControl": self._tfhka_get_move_control_number(move),
                    "tipoTransaccion": None,
                    "montoTotal": None,
                    "montoExento": None,
                    "baseImponible": self._l10n_ve_edi_format_decimal(
                        line.invoice_amount
                    ),
                    "porcentaje": self._tfhka_format_rate(line.related_percentage_fees),
                    "porcentajeRetencion": self._tfhka_format_rate(
                        line.related_percentage_fees
                    ),
                    "sustraendo": self._l10n_ve_edi_format_decimal(
                        line.related_amount_subtract_fees
                    ),
                    "montoIVA": None,
                    "retenido": self._l10n_ve_edi_format_decimal(retenido),
                    "percibido": None,
                    "codigoConcepto": self._tfhka_get_line_codigo_concepto(line),
                    "moneda": currency,
                    "infoAdicionalItem": None,
                }
                details.append(detail)
                continue
            monto_iva = self._tfhka_line_monto_iva(line)
            retenido = self._tfhka_line_retenido(line)
            assign_exempt = move.id not in moves_with_exempt
            if assign_exempt:
                moves_with_exempt.add(move.id)
            monto_exento = (
                self._tfhka_get_invoice_exempt_amount(move) if assign_exempt else 0.0
            )
            monto_total = self._tfhka_line_monto_total(
                line, move, monto_exento=monto_exento
            )
            detail = {
                "numeroLinea": str(index),
                "fechaDocumento": self._tfhka_format_date(
                    move.invoice_date or move.date
                ),
                "tipoDocumento": self._tfhka_invoice_document_type_from_move(move),
                "numeroDocumento": self._tfhka_invoice_document_number_from_move(move),
                "tipoTransaccion": None,
                "montoTotal": self._l10n_ve_edi_format_decimal(monto_total),
                "montoExento": self._l10n_ve_edi_format_decimal(monto_exento),
                "baseImponible": self._l10n_ve_edi_format_decimal(line.invoice_amount),
                "retenido": self._l10n_ve_edi_format_decimal(retenido),
                "percibido": "0",
                "moneda": currency,
                "infoAdicionalItem": [],
            }
            detail["numeroControl"] = self._tfhka_get_move_control_number(move)
            detail["montoIVA"] = self._l10n_ve_edi_format_decimal(monto_iva)
            detail["porcentaje"] = self._tfhka_format_rate(line.aliquot)
            detail["porcentajeRetencion"] = self._tfhka_format_rate(
                line.related_percentage_tax_base
            )
            details.append(detail)
        return details

    def _tfhka_build_retention_documento_electronico_payload(self):
        self.ensure_one()
        payload = {
            "documentoElectronico": {
                "encabezado": {
                    "identificacionDocumento": (
                        self._tfhka_build_retention_identificacion_documento()
                    ),
                    "sujetoRetenido": self._tfhka_build_sujeto_retenido(),
                    "totales": self._tfhka_build_encabezado_totales(),
                    "totalesRetencion": self._tfhka_build_totales_retencion(),
                },
                "detallesRetencion": self._tfhka_build_detalles_retencion(),
                "infoAdicional": [],
                "esLote": False,
                "esMinimo": False,
            }
        }
        _logger.info(
            "TFHKA retention payload retention_id=%s type=%s json=%s",
            self.id,
            self.type_retention,
            json.dumps(payload, ensure_ascii=False)[:4000],
        )
        return payload
