import base64
import binascii
import copy
import json
import logging
import re
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_ve_edi.models.edi_mixin import STATE_SENT

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_edi_tfhka_show_sent_link_buttons = fields.Boolean(
        compute="_compute_l10n_ve_edi_tfhka_sent_links",
        string="TFHKA: documento EDI enviado",
    )
    l10n_ve_edi_tfhka_sent_pdf_url = fields.Char(
        compute="_compute_l10n_ve_edi_tfhka_sent_links",
        string="URL PDF (TFHKA)",
    )
    l10n_ve_edi_tfhka_sent_invoice_url = fields.Char(
        compute="_compute_l10n_ve_edi_tfhka_sent_links",
        string="URL documento fiscal (TFHKA)",
    )
    l10n_ve_edi_tfhka_pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        copy=False,
        readonly=True,
        string="PDF TFHKA (DescargaArchivo)",
    )
    l10n_ve_edi_tfhka_portal_iframe_report_type = fields.Char(
        compute="_compute_l10n_ve_edi_tfhka_portal_iframe_report_type",
        string="Portal: tipo de informe embebido (pdf/html)",
    )

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "journal_id.l10n_ve_emission_medium",
        "journal_id.l10n_ve_edi_provider",
        "l10n_ve_edi_send_state",
        "invoice_pdf_report_file",
    )
    def _compute_l10n_ve_edi_tfhka_portal_iframe_report_type(self):
        for move in self:
            if (
                move._l10n_ve_edi_tfhka_replace_invoice_report_with_digital_pdf()
                and move.invoice_pdf_report_file
            ):
                move.l10n_ve_edi_tfhka_portal_iframe_report_type = "pdf"
            else:
                move.l10n_ve_edi_tfhka_portal_iframe_report_type = "html"

    @api.depends(
        "l10n_ve_edi_response_json",
        "journal_id.l10n_ve_edi_provider",
        "l10n_ve_edi_send_state",
        "state",
        "move_type",
    )
    def _compute_l10n_ve_edi_tfhka_sent_links(self):
        for move in self:
            move.l10n_ve_edi_tfhka_show_sent_link_buttons = (
                move.state == "posted"
                and move.move_type in ("out_invoice", "out_refund")
                and move.l10n_ve_edi_send_state == "sent"
                and move.journal_id.l10n_ve_edi_provider == "tfhka"
            )
            move.l10n_ve_edi_tfhka_sent_pdf_url = False
            move.l10n_ve_edi_tfhka_sent_invoice_url = False
            if (
                move.journal_id.l10n_ve_edi_provider != "tfhka"
                or not move.l10n_ve_edi_response_json
            ):
                continue
            pdf_u, doc_u = move._tfhka_extract_public_urls_from_stored_response()
            move.l10n_ve_edi_tfhka_sent_pdf_url = pdf_u
            move.l10n_ve_edi_tfhka_sent_invoice_url = doc_u

    def _l10n_ve_edi_get_portal_digital_printer_url(self):
        self.ensure_one()
        url = super()._l10n_ve_edi_get_portal_digital_printer_url()
        if url:
            return url
        if self.journal_id.l10n_ve_edi_provider != "tfhka":
            return False
        return (
            self.l10n_ve_edi_tfhka_sent_invoice_url
            or self.l10n_ve_edi_tfhka_sent_pdf_url
            or False
        )

    def _tfhka_normalize_http_url(self, value):
        if not value or not isinstance(value, str):
            return False
        u = value.strip()
        if u.lower().startswith(("http://", "https://")):
            return u
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
                u = self._tfhka_normalize_http_url(blob.get(key))
                if u and u != pdf_url:
                    doc_url = u
            if not doc_url:
                u = self._tfhka_normalize_http_url(blob.get("url"))
                if u and u != pdf_url:
                    doc_url = u
        if doc_url == pdf_url:
            doc_url = False
        return pdf_url, doc_url

    def _tfhka_require_sent_tfhka_for_pdf_action(self):
        self.ensure_one()
        if self.state != "posted" or self.move_type not in (
            "out_invoice",
            "out_refund",
        ):
            raise UserError(_("Solo aplica a facturas o notas de cliente confirmadas."))
        if self.l10n_ve_edi_send_state != "sent":
            raise UserError(
                _(
                    "El documento debe estar enviado a facturacion digital "
                    "(estado: enviado)."
                )
            )
        if self.journal_id.l10n_ve_edi_provider != "tfhka":
            raise UserError(_("El diario debe usar el proveedor TFHKA."))

    def _tfhka_get_descarga_archivo_payload(self):
        self.ensure_one()
        return {
            "serie": self._tfhka_get_serie() or "",
            "tipoDocumento": self._tfhka_get_document_type(),
            "numeroDocumento": self._tfhka_get_document_number(),
        }

    def _tfhka_get_annulment_date(self):
        self.ensure_one()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return now.strftime("%d/%m/%Y")

    def _tfhka_get_annulment_hour(self):
        self.ensure_one()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return f"{now.strftime('%I:%M:%S')} {now.strftime('%p').lower()}"

    def _tfhka_get_annulment_reason(self):
        self.ensure_one()
        if "l10n_ve_cancel_reason_id" in self._fields and self.l10n_ve_cancel_reason_id:
            reason = (self.l10n_ve_cancel_reason_id.name or "").strip()
            if reason:
                return reason[:255]
        return _("Anulación desde Odoo")[:255]

    def _tfhka_should_cancel_digital_document(self):
        self.ensure_one()
        return (
            self.journal_id.l10n_ve_edi_provider == "tfhka"
            and self.l10n_ve_edi_send_state == STATE_SENT
        )

    def _tfhka_build_anular_payload(self):
        self.ensure_one()
        return {
            "serie": self._tfhka_get_serie() or "",
            "tipoDocumento": self._tfhka_get_document_type(),
            "numeroDocumento": self._tfhka_get_document_number(),
            "motivoAnulacion": self._tfhka_get_annulment_reason(),
            "fechaAnulacion": self._tfhka_get_annulment_date(),
            "horaAnulacion": self._tfhka_get_annulment_hour(),
        }

    def _tfhka_store_annulment_response(self, response):
        self.ensure_one()
        combined = {}
        if self.l10n_ve_edi_response_json:
            try:
                combined = json.loads(self.l10n_ve_edi_response_json)
            except (ValueError, TypeError):
                combined = {"emission_response_raw": self.l10n_ve_edi_response_json}
        if not isinstance(combined, dict):
            combined = {"emission": combined}
        combined["annulment"] = response
        self.write(
            {"l10n_ve_edi_response_json": json.dumps(combined, ensure_ascii=False)}
        )

    def _tfhka_cancel_digital_document(self):
        self.ensure_one()
        if self.env.context.get("skip_l10n_ve_edi_tfhka_digital_cancel"):
            return
        if not self._tfhka_should_cancel_digital_document():
            return
        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            raise UserError(_("Configure usuario y clave TFHKA en Ajustes."))
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        payload = self._tfhka_build_anular_payload()
        try:
            auth = client.authenticate(username, password)
            token = auth.get("token")
            if not token:
                raise UserError(_("La API TFHKA no devolvió token JWT."))
            response = client.cancel_document(payload, token)
        except UserError:
            raise
        except Exception as exc:
            _logger.exception(
                "TFHKA anulación fallida move_id=%s name=%s payload=%s",
                self.id,
                self.name,
                self._tfhka_safe_json_for_log(payload, 4000),
            )
            raise UserError(
                _("No fue posible anular el documento digital en TFHKA: %s") % exc
            ) from exc
        self._tfhka_store_annulment_response(response)
        _logger.info(
            "TFHKA documento anulado move_id=%s tipo=%s numero=%s respuesta=%s",
            self.id,
            payload.get("tipoDocumento"),
            payload.get("numeroDocumento"),
            self._tfhka_safe_json_for_log(response, 4000),
        )

    def _tfhka_extract_pdf_bytes_from_download_response(self, data):
        if not isinstance(data, dict):
            return None

        def _decode_b64_to_pdf(s):
            if not isinstance(s, str) or len(s) < 50:
                return None
            raw = s.strip().replace("\n", "").replace("\r", "").replace(" ", "")
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

        res = data.get("resultado")
        if isinstance(res, str):
            b = _decode_b64_to_pdf(res)
            if b:
                return b
        blobs = [data]
        if isinstance(res, dict):
            blobs.append(res)
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
                b = _decode_b64_to_pdf(blob.get(key))
                if b:
                    return b
        return None

    def _tfhka_get_invoice_pdf_bytes_via_descarga_archivo(self):
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
            payload = self._tfhka_get_descarga_archivo_payload()
            resp = client.download_file(payload, token)
        except UserError as exc:
            return None, str(exc)
        except Exception as exc:
            _logger.exception("TFHKA DescargaArchivo move_id=%s", self.id)
            return None, str(exc)
        pdf_bytes = self._tfhka_extract_pdf_bytes_from_download_response(resp)
        if pdf_bytes:
            return pdf_bytes, None
        _logger.warning(
            "TFHKA DescargaArchivo sin PDF reconocible move_id=%s claves=%s",
            self.id,
            list(resp.keys()) if isinstance(resp, dict) else type(resp),
        )
        return None, _(
            "La respuesta de DescargaArchivo no incluye un PDF en base64 reconocible."
        )

    def _tfhka_return_pdf_attachment_download_action(self, pdf_bytes):
        self.ensure_one()
        b64 = base64.b64encode(pdf_bytes)
        safe_name = (self.name or "factura").replace("/", "_")
        fname = f"TFHKA_{safe_name}.pdf"
        vals = {
            "name": fname,
            "type": "binary",
            "datas": b64,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
        }
        att = self.l10n_ve_edi_tfhka_pdf_attachment_id
        if att:
            att.sudo().write(vals)
        else:
            att = self.env["ir.attachment"].sudo().create(vals)
            self.sudo().write({"l10n_ve_edi_tfhka_pdf_attachment_id": att.id})
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "self",
        }

    def action_l10n_ve_edi_tfhka_open_sent_pdf(self):
        self.ensure_one()
        self._tfhka_require_sent_tfhka_for_pdf_action()
        pdf_bytes, api_err = self._tfhka_get_invoice_pdf_bytes_via_descarga_archivo()
        if pdf_bytes:
            return self._tfhka_return_pdf_attachment_download_action(pdf_bytes)
        pdf_url, _doc = self._tfhka_extract_public_urls_from_stored_response()
        pdf_url = pdf_url or self.l10n_ve_edi_tfhka_sent_pdf_url
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
        _pdf, doc_url = self._tfhka_extract_public_urls_from_stored_response()
        doc_url = doc_url or self.l10n_ve_edi_tfhka_sent_invoice_url
        if not doc_url:
            raise UserError(
                _(
                    "No hay URL de consulta del documento en la respuesta "
                    "guardada de TFHKA. "
                    "Revise el JSON de respuesta."
                )
            )
        return {"type": "ir.actions.act_url", "url": doc_url, "target": "new"}

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        if provider == "tfhka":
            return self._tfhka_build_documento_electronico_payload()
        return super()._l10n_ve_edi_build_payload_for_provider(provider)

    def _tfhka_build_documento_electronico_payload(self):
        """Assemble the TFHKA JSON tree; monetary totals mirror ``tax_totals``."""
        self.ensure_one()
        totals_payload = self._tfhka_get_totals_for_payload()
        encabezado = {
            "identificacionDocumento": self._tfhka_build_identificacion_documento(),
            "comprador": self._tfhka_build_comprador(),
            "totales": self._tfhka_build_totales(totals_payload),
        }
        vendedor = self._tfhka_build_vendedor()
        if vendedor:
            encabezado["vendedor"] = vendedor
        factura_guia = self._tfhka_build_factura_guia()
        if factura_guia:
            encabezado["facturaGuia"] = factura_guia
        totales_otra = self._tfhka_build_totales_otra_moneda(totals_payload)
        if totales_otra:
            encabezado["totalesOtraMoneda"] = totales_otra
        payload = {
            "documentoElectronico": {
                "encabezado": encabezado,
                "detallesItems": self._tfhka_build_detalles_items(),
            }
        }
        info_adicional = self._tfhka_build_info_adicional()
        if info_adicional:
            payload["documentoElectronico"]["infoAdicional"] = info_adicional
        return payload

    def _tfhka_get_line_items(self):
        self.ensure_one()
        line_items = self.invoice_line_ids.filtered(
            lambda line: line.display_type in (False, "product")
        )
        if line_items:
            return line_items
        return self.line_ids.filtered(
            lambda line: line.display_type in (False, "product")
            and not line.exclude_from_invoice_tab
        )

    def _tfhka_get_issue_date(self):
        self.ensure_one()
        return (self.invoice_date or fields.Date.context_today(self)).strftime(
            "%d/%m/%Y"
        )

    def _tfhka_get_due_date(self):
        self.ensure_one()
        return (
            self.invoice_date_due
            or self.invoice_date
            or fields.Date.context_today(self)
        ).strftime("%d/%m/%Y")

    def _tfhka_get_issue_hour(self):
        self.ensure_one()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return f"{now.strftime('%I:%M:%S')} {now.strftime('%p').lower()}"

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

    def _tfhka_get_serie(self):
        self.ensure_one()
        return self._tfhka_serie_from_journal(self.journal_id)

    def _tfhka_get_sucursal(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal or "l10n_ve_edi_tfhka_sucursal" not in journal._fields:
            return ""
        raw = (journal.l10n_ve_edi_tfhka_sucursal or "").strip()
        return re.sub(r"[^0-9A-Za-z]", "", raw)[:6]

    def _tfhka_secuencia_for_numero_documento(self):
        self.ensure_one()
        ref_date = self.invoice_date or self.date
        env_digit = self.journal_id._tfhka_get_numero_documento_environment_digit()
        return self.env[
            "l10n_ve.edi.tfhka.document.mixin"
        ]._tfhka_build_secuencia_yyyy_mm_seq(
            ref_date, self.name, self.id, environment_digit=env_digit
        )

    def _tfhka_get_document_number(self):
        self.ensure_one()
        return (
            f"{self._tfhka_get_document_type()}"
            f"{self._tfhka_secuencia_for_numero_documento()}"
        )

    def _tfhka_get_document_type(self):
        self.ensure_one()
        if self.move_type == "out_refund":
            return "02"
        if self.debit_origin_id:
            return "03"
        return "01"

    def _tfhka_is_adjustment_document(self):
        self.ensure_one()
        return self._tfhka_get_document_type() in ("02", "03")

    def _tfhka_get_sale_type(self):
        self.ensure_one()
        return "Interna"

    def _tfhka_get_tipo_de_pago(self):
        self.ensure_one()
        term = self.invoice_payment_term_id
        if term and term.line_ids and any(line.nb_days > 0 for line in term.line_ids):
            return "Crédito"
        return "Inmediato"

    def _tfhka_get_tipo_transaccion(self):
        self.ensure_one()
        if self._tfhka_get_document_type() == "01":
            return "01"
        return "02"

    def _tfhka_get_currency_code(self):
        self.ensure_one()
        currency = re.sub(r"[^0-9A-Za-z]", "", self.currency_id.name or "VES").upper()
        return (currency or "VES")[:3]

    def _tfhka_get_seller_name(self):
        self.ensure_one()
        raw_name = (
            self.invoice_user_id.name or self.user_id.name or self.create_uid.name or ""
        )
        normalized_name = re.sub(r"[^0-9A-Za-z ]", "", raw_name).strip()
        return normalized_name[:255]

    def _tfhka_validate_identificacion_documento(self):
        self.ensure_one()
        document_type = self._tfhka_get_document_type()
        if len(document_type or "") != 2:
            raise UserError(_("TipoDocumento debe tener exactamente 2 digitos."))
        number = self._tfhka_get_document_number()
        digits_only = re.sub(r"\D", "", number)
        if not digits_only or not digits_only.isdigit() or len(digits_only) > 19:
            raise UserError(
                _(
                    "NumeroDocumento debe tener entre 1 y 19 digitos "
                    "(formato tipo+anio+correlativo)."
                )
            )
        if len(self._tfhka_get_currency_code() or "") > 3:
            raise UserError(_("Moneda debe tener maximo 3 caracteres alfanumericos."))
        if len(self._tfhka_get_serie() or "") > 20:
            raise UserError(_("Serie debe tener maximo 20 caracteres alfanumericos."))
        if len(self._tfhka_get_sucursal() or "") > 6:
            raise UserError(_("Sucursal debe tener maximo 6 caracteres alfanumericos."))

    def _tfhka_format_amount_8_2(self, amount):
        value = f"{abs(amount or 0.0):.2f}"
        integer_part = value.split(".")[0]
        if len(integer_part) > 8:
            raise UserError(_("MontoFacturaAfectada excede el formato 8.2."))
        return value

    def _tfhka_format_tipo_cambio(self, rate):
        return f"{abs(float(rate or 0.0)):.4f}"

    def _tfhka_format_tasa_iva(self, rate):
        r = float(rate or 0.0)
        if abs(r - round(r)) < 0.001:
            return str(int(round(r)))
        return self._l10n_ve_edi_format_decimal(r)

    def _tfhka_get_monto_en_letras(self):
        self.ensure_one()
        words = (self.amount_total_words or "").strip()
        return words[:255] if words else ""

    def _tfhka_camel_key_to_pascal(self, key):
        if not key or not isinstance(key, str):
            return key
        return key[0].upper() + key[1:]

    def _tfhka_dict_keys_to_pascal(self, obj):
        if isinstance(obj, dict):
            return {
                self._tfhka_camel_key_to_pascal(k): self._tfhka_dict_keys_to_pascal(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._tfhka_dict_keys_to_pascal(i) for i in obj]
        return obj

    def _tfhka_strip_none(self, obj):
        if isinstance(obj, dict):
            return {
                k: self._tfhka_strip_none(v) for k, v in obj.items() if v is not None
            }
        if isinstance(obj, list):
            return [self._tfhka_strip_none(i) for i in obj]
        return obj

    def _tfhka_prepare_api_payload(self, payload):
        self.ensure_one()
        prepared = copy.deepcopy(payload)
        if self._tfhka_get_document_type() in ("02", "03"):
            prepared = self._tfhka_dict_keys_to_pascal(prepared)
        return self._tfhka_strip_none(prepared)

    def _tfhka_validate_affected_invoice_required(self):
        self.ensure_one()
        if not self._tfhka_is_adjustment_document():
            return
        affected_move = self._tfhka_get_affected_move()
        if not affected_move:
            raise UserError(
                _(
                    "La nota de credito/debito requiere una factura origen "
                    "(factura afectada)."
                )
            )
        required_values = {
            "NumeroFacturaAfectada": self._tfhka_get_affected_invoice_number(),
            "FechaFacturaAfectada": self._tfhka_get_affected_invoice_date(),
            "MontoFacturaAfectada": self._tfhka_get_affected_invoice_amount(),
        }
        missing = [
            field_name for field_name, value in required_values.items() if not value
        ]
        if missing:
            raise UserError(
                _(
                    "Faltan datos obligatorios de la factura afectada para "
                    "nota de credito/debito: %s"
                )
                % ", ".join(missing)
            )

    def _tfhka_get_affected_move(self):
        self.ensure_one()
        if self.reversed_entry_id:
            return self.reversed_entry_id
        if self.debit_origin_id:
            return self.debit_origin_id
        return self.env["account.move"]

    def _tfhka_get_affected_invoice_serie(self):
        self.ensure_one()
        affected_move = self._tfhka_get_affected_move()
        if not affected_move:
            return ""
        return self._tfhka_serie_from_journal(affected_move.journal_id)

    def _tfhka_get_affected_invoice_number(self):
        self.ensure_one()
        affected_move = self._tfhka_get_affected_move()
        if not affected_move:
            return ""
        return affected_move._tfhka_get_document_number()

    def _tfhka_get_affected_invoice_date(self):
        self.ensure_one()
        affected_move = self._tfhka_get_affected_move()
        if not affected_move:
            return ""
        affected_date = affected_move.invoice_date or affected_move.date
        return affected_date.strftime("%d/%m/%Y") if affected_date else ""

    def _tfhka_get_affected_invoice_amount(self):
        self.ensure_one()
        affected_move = self._tfhka_get_affected_move()
        if not affected_move:
            return ""
        return self._tfhka_format_amount_8_2(affected_move.amount_total)

    def _tfhka_get_affected_invoice_comment(self):
        self.ensure_one()
        if not self._tfhka_is_adjustment_document():
            return ""
        affected_move = self._tfhka_get_affected_move()
        if not affected_move:
            return ""
        comment = (self.ref or "").strip() or (affected_move.ref or "").strip()
        if not comment:
            comment = "Ajuste sobre factura %s" % (affected_move.name or "")
        return comment[:500]

    def _tfhka_get_line_tax_rate(self, line):
        tax = line.tax_ids[:1]
        return abs(tax.amount) if tax and tax.amount_type == "percent" else 0.0

    def _tfhka_get_line_tax_code_for_rate(self, rate):
        r = round(float(rate or 0.0), 2)
        if r == 0:
            return "E"
        if abs(r - 8.0) < 0.01:
            return "R"
        if abs(r - 16.0) < 0.01:
            return "G"
        if abs(r - 31.0) < 0.01:
            return "A"
        return "G" if r > 0 else "E"

    def _tfhka_get_line_tax_code(self, line):
        return self._tfhka_get_line_tax_code_for_rate(
            self._tfhka_get_line_tax_rate(line)
        )

    def _tfhka_get_line_iva_value(self, line):
        return line.price_total - line.price_subtotal

    def _tfhka_tax_group_to_codigo(self, tax_group_dict):
        self.ensure_one()
        tids = tax_group_dict.get("involved_tax_ids") or []
        if not tids:
            return "E"
        tax = self.env["account.tax"].browse(tids[0])
        if tax.amount_type == "percent":
            return self._tfhka_get_line_tax_code_for_rate(tax.amount)
        return "E"

    def _tfhka_tax_group_rate(self, tax_group_dict):
        tids = tax_group_dict.get("involved_tax_ids") or []
        if not tids:
            return 0.0
        tax = self.env["account.tax"].browse(tids[0])
        return abs(tax.amount) if tax.amount_type == "percent" else 0.0

    def _tfhka_is_igtf_tax_group(self, tax_group_dict):
        if not isinstance(tax_group_dict, dict):
            return False
        if tax_group_dict.get("id") == -1:
            return True
        group_name = (tax_group_dict.get("group_name") or "").upper()
        if "IGTF" in group_name:
            return True
        tids = tax_group_dict.get("involved_tax_ids") or []
        return (
            not tids and abs(float(tax_group_dict.get("tax_amount", 0.0) or 0.0)) > 0.0
        )

    def _tfhka_line_discount_and_count(self):
        self.ensure_one()
        cur = self.currency_id
        line_items = self._tfhka_get_line_items()
        total_desc = 0.0
        subtotal_antes = 0.0
        for line in line_items:
            brutto = cur.round(line.price_unit * line.quantity)
            ps = cur.round(line.price_subtotal)
            total_desc = cur.round(total_desc + cur.round(brutto - ps))
            subtotal_antes = cur.round(subtotal_antes + brutto)
        return len(line_items), total_desc, subtotal_antes

    def _tfhka_sum_buckets_base_tax(self, buckets, cur):
        if not buckets:
            return 0.0, 0.0
        sum_b = cur.round(sum(v.get("base", 0.0) for v in buckets.values()))
        sum_t = cur.round(sum(v.get("tax", 0.0) for v in buckets.values()))
        return sum_b, sum_t

    def _tfhka_reconcile_buckets_to_targets(
        self, buckets, target_base, target_tax, cur
    ):
        self.ensure_one()
        if not buckets:
            return buckets
        out = {
            k: {"base": cur.round(v["base"]), "tax": cur.round(v["tax"])}
            for k, v in buckets.items()
        }
        sum_b, sum_t = self._tfhka_sum_buckets_base_tax(out, cur)
        db = cur.round(target_base - sum_b)
        dt = cur.round(target_tax - sum_t)
        if cur.is_zero(db) and cur.is_zero(dt):
            return out
        _logger.info(
            "l10n_ve_edi_tfhka: buckets reconciliados move_id=%s moneda=%s "
            "base_delta=%s tax_delta=%s",
            self.id,
            cur.name,
            db,
            dt,
        )
        key_max = max(out.keys(), key=lambda k: (out[k]["base"], k))
        out[key_max]["base"] = cur.round(out[key_max]["base"] + db)
        out[key_max]["tax"] = cur.round(out[key_max]["tax"] + dt)
        return out

    def _tfhka_gravado_exento_from_buckets(self, buckets, cur, subtotal_target=None):
        gravado_raw = sum(
            vals.get("base", 0.0)
            for (code, _r), vals in buckets.items()
            if code in ("G", "R", "A")
        )
        exento_raw = sum(
            vals.get("base", 0.0)
            for (code, _r), vals in buckets.items()
            if code not in ("G", "R", "A")
        )
        gravado = cur.round(gravado_raw)
        if subtotal_target is not None:
            exento = cur.round(cur.round(subtotal_target) - gravado)
        else:
            exento = cur.round(exento_raw)
        return gravado, exento

    def _tfhka_log_totales_tfhka_debug(
        self, payload, igtf, monto_total_iva_oti, has_igtf
    ):
        if not _logger.isEnabledFor(logging.DEBUG):
            return
        bs = payload["comp"]
        inv = payload["inv"]
        comp_cur = self.company_id.currency_id
        inv_cur = self.currency_id
        cb, ct = self._tfhka_sum_buckets_base_tax(bs.get("buckets") or {}, comp_cur)
        ib, it = self._tfhka_sum_buckets_base_tax(inv.get("buckets") or {}, inv_cur)
        sub_iva_comp = comp_cur.round(bs["subtotal"] + bs["total_iva"])
        sub_iva_inv = inv_cur.round(inv["subtotal"] + inv["total_iva"])
        ap_igtf_comp = (
            comp_cur.round(bs["total_apagar"] - igtf["comp"]) if has_igtf else None
        )
        ap_igtf_inv = (
            inv_cur.round(inv["total_apagar"] - igtf["inv"]) if has_igtf else None
        )
        _logger.debug(
            "TFHKA totales move_id=%s name=%s comp subtotal+iva=%s buckets_b+t=%s "
            "total_apagar-igtf=%s montoTotalIVAyOTI=%s | inv "
            "subtotal+iva=%s buckets_b+t=%s "
            "total_apagar-igtf=%s",
            self.id,
            self.name,
            sub_iva_comp,
            comp_cur.round(cb + ct),
            ap_igtf_comp,
            monto_total_iva_oti,
            sub_iva_inv,
            inv_cur.round(ib + it),
            ap_igtf_inv,
        )

    def _tfhka_parse_amount_string(self, value):
        if value is None:
            return 0.0
        if isinstance(value, int | float):
            return float(value)
        s = str(value).strip().replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _tfhka_safe_json_for_log(self, obj, limit=8000):
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except TypeError:
            s = str(obj)
        if len(s) <= limit:
            return s
        return s[:limit] + "…(truncado)"

    def _tfhka_log_impuestos_subtotal_audit(self, label, imp_rows):
        if not imp_rows:
            _logger.error("TFHKA %s sin filas en impuestosSubtotal", label)
            return
        sum_b = 0.0
        sum_t = 0.0
        parts = []
        for row in imp_rows:
            if not isinstance(row, dict):
                continue
            code = row.get("codigoTotalImp")
            alic = row.get("alicuotaImp")
            bi = self._tfhka_parse_amount_string(row.get("baseImponibleImp"))
            vi = self._tfhka_parse_amount_string(row.get("valorTotalImp"))
            sum_b += bi
            sum_t += vi
            parts.append(f"{code}/{alic} base={bi} imp={vi}")
        _logger.error(
            "TFHKA %s impuestosSubtotal n=%s suma_bases=%.4f suma_impuestos=%.4f "
            "suma_b+imp=%.4f | %s",
            label,
            len(imp_rows),
            sum_b,
            sum_t,
            sum_b + sum_t,
            " | ".join(parts),
        )

    def _tfhka_log_emision_failure_analysis(self, odoo_payload, prepared, error_msg):
        self.ensure_one()
        _logger.error(
            "TFHKA EMISION FALLIDA move_id=%s name=%s tipo=%s estado=%s error=%s",
            self.id,
            self.name,
            self.move_type,
            self.state,
            error_msg,
        )
        _logger.error(
            "TFHKA contexto journal_id=%s moneda_doc=%s moneda_comp=%s "
            "amount_total=%s amount_untaxed=%s amount_tax=%s inverse_rate=%s",
            self.journal_id.id,
            self.currency_id.name,
            self.company_id.currency_id.name,
            self.amount_total,
            self.amount_untaxed,
            self.amount_tax,
            getattr(self, "l10n_ve_inverse_rate", None),
        )
        try:
            doc = (odoo_payload or {}).get("documentoElectronico") or {}
            enc = doc.get("encabezado") or {}
            ident = enc.get("identificacionDocumento") or {}
            _logger.error(
                "TFHKA payload ident tipoDocumento=%s numeroDocumento=%s moneda=%s "
                "tipoDePago=%s fechaEmision=%s",
                ident.get("tipoDocumento"),
                ident.get("numeroDocumento"),
                ident.get("moneda"),
                ident.get("tipoDePago"),
                ident.get("fechaEmision"),
            )
            tot = enc.get("totales") or {}
            st = self._tfhka_parse_amount_string(tot.get("subtotal"))
            iv = self._tfhka_parse_amount_string(tot.get("totalIVA"))
            mioti = self._tfhka_parse_amount_string(tot.get("montoTotalIVAyOTI"))
            sum_st_iv = st + iv
            gv = self._tfhka_parse_amount_string(tot.get("montoGravadoTotal"))
            exc = self._tfhka_parse_amount_string(tot.get("montoExentoTotal"))
            sum_grav_exc_iva = gv + exc + iv
            _logger.error(
                "TFHKA totales encabezado subtotal=%s totalIVA=%s montoGravadoTotal=%s "
                "montoExentoTotal=%s montoTotalConIVA=%s montoTotalIVAyOTI=%s "
                "totalAPagar=%s totalIGTF=%s montoTotalOTI=%s | float "
                "subtotal+IVA=%.4f float grav+exc+IVA=%.4f "
                "delta_montoTotalIVAyOTI_vs_grav_exc_iva=%.4f",
                tot.get("subtotal"),
                tot.get("totalIVA"),
                tot.get("montoGravadoTotal"),
                tot.get("montoExentoTotal"),
                tot.get("montoTotalConIVA"),
                tot.get("montoTotalIVAyOTI"),
                tot.get("totalAPagar"),
                tot.get("totalIGTF"),
                tot.get("montoTotalOTI"),
                sum_st_iv,
                sum_grav_exc_iva,
                mioti - sum_grav_exc_iva,
            )
            self._tfhka_log_impuestos_subtotal_audit(
                "compania_VES", tot.get("impuestosSubtotal") or []
            )
            imps = tot.get("impuestosSubtotal") or []
            if imps and tot.get("montoTotalIVAyOTI") is not None:
                sb = sum(
                    self._tfhka_parse_amount_string(r.get("baseImponibleImp"))
                    for r in imps
                    if isinstance(r, dict)
                )
                stx = sum(
                    self._tfhka_parse_amount_string(r.get("valorTotalImp"))
                    for r in imps
                    if isinstance(r, dict)
                )
                bucket_total = sb + stx
                _logger.error(
                    "TFHKA coherencia 1079 candidato suma_impuestosSubtotal=%.4f vs "
                    "montoTotalIVAyOTI=%.4f diff=%.4f",
                    bucket_total,
                    mioti,
                    mioti - bucket_total,
                )

            otm = enc.get("totalesOtraMoneda")
            if otm:
                st2 = self._tfhka_parse_amount_string(otm.get("subtotal"))
                iv2 = self._tfhka_parse_amount_string(otm.get("totalIVA"))
                mci2 = self._tfhka_parse_amount_string(otm.get("montoTotalConIVA"))
                mioti2 = self._tfhka_parse_amount_string(otm.get("montoTotalIVAyOTI"))
                sum2 = st2 + iv2
                _logger.error(
                    "TFHKA totalesOtraMoneda moneda=%s subtotal=%s totalIVA=%s "
                    "montoTotalConIVA=%s montoTotalIVAyOTI=%s totalAPagar=%s | "
                    "float_sub+IVA=%.4f "
                    "delta_montoTotalConIVA=%.4f delta_montoTotalIVAyOTI=%.4f",
                    otm.get("moneda"),
                    otm.get("subtotal"),
                    otm.get("totalIVA"),
                    otm.get("montoTotalConIVA"),
                    otm.get("montoTotalIVAyOTI"),
                    otm.get("totalAPagar"),
                    sum2,
                    mci2 - sum2,
                    mioti2 - sum2,
                )
                self._tfhka_log_impuestos_subtotal_audit(
                    "otra_moneda", otm.get("impuestosSubtotal") or []
                )
                imps2 = otm.get("impuestosSubtotal") or []
                if imps2 and otm.get("montoTotalIVAyOTI") is not None:
                    sb2 = sum(
                        self._tfhka_parse_amount_string(r.get("baseImponibleImp"))
                        for r in imps2
                        if isinstance(r, dict)
                    )
                    stx2 = sum(
                        self._tfhka_parse_amount_string(r.get("valorTotalImp"))
                        for r in imps2
                        if isinstance(r, dict)
                    )
                    bt2 = sb2 + stx2
                    _logger.error(
                        "TFHKA coherencia 1079 (otra moneda) "
                        "suma_impuestosSubtotal=%.4f "
                        "vs montoTotalIVAyOTI=%.4f diff=%.4f",
                        bt2,
                        mioti2,
                        mioti2 - bt2,
                    )

            items = doc.get("detallesItems") or []
            sum_lines = 0.0
            for it in items:
                if isinstance(it, dict):
                    sum_lines += self._tfhka_parse_amount_string(
                        it.get("valorTotalItem")
                    )
            _logger.error(
                "TFHKA detallesItems lineas=%s suma_valorTotalItem=%.4f",
                len(items),
                sum_lines,
            )
            if self._tfhka_get_document_type() in ("02", "03") and prepared:
                _logger.error(
                    "TFHKA payload_API_Pascal=%s",
                    self._tfhka_safe_json_for_log(prepared, 8000),
                )
        except Exception:
            _logger.exception("TFHKA error al analizar payload para log de fallo")

        tt = self.tax_totals
        if isinstance(tt, dict):
            _logger.error(
                "TFHKA tax_totals base_amount=%s tax_amount=%s total_amount=%s "
                "base_amount_currency=%s tax_amount_currency=%s "
                "total_amount_currency=%s l10n_ve_igtf_collected_amount=%s "
                "l10n_ve_igtf_collected_amount_currency=%s",
                tt.get("base_amount"),
                tt.get("tax_amount"),
                tt.get("total_amount"),
                tt.get("base_amount_currency"),
                tt.get("tax_amount_currency"),
                tt.get("total_amount_currency"),
                tt.get("l10n_ve_igtf_collected_amount"),
                tt.get("l10n_ve_igtf_collected_amount_currency"),
            )

        try:
            tp = self._tfhka_get_totals_for_payload()
            bs = tp["comp"]
            inv = tp["inv"]
            comp_cur = self.company_id.currency_id
            inv_cur = self.currency_id
            cb, ct = self._tfhka_sum_buckets_base_tax(bs.get("buckets") or {}, comp_cur)
            ib, itx = self._tfhka_sum_buckets_base_tax(
                inv.get("buckets") or {}, inv_cur
            )
            siva_c = comp_cur.round(bs["subtotal"] + bs["total_iva"])
            siva_i = inv_cur.round(inv["subtotal"] + inv["total_iva"])
            btc = comp_cur.round(cb + ct)
            bti = inv_cur.round(ib + itx)
            _logger.error(
                "TFHKA agregado_interno comp subtotal=%s total_iva=%s subtotal+iva=%s "
                "buckets_b=%s buckets_t=%s buckets_b+t=%s | inv "
                "subtotal+iva=%s buckets_b+t=%s",
                bs["subtotal"],
                bs["total_iva"],
                siva_c,
                cb,
                ct,
                btc,
                siva_i,
                bti,
            )
            _logger.error(
                "TFHKA deltas_internos comp subtotal+iva_vs_buckets=%s | "
                "inv subtotal+iva_vs_buckets=%s",
                comp_cur.round(siva_c - btc),
                inv_cur.round(siva_i - bti),
            )
        except Exception:
            _logger.exception("TFHKA agregado interno no disponible para log de fallo")

    def _tfhka_aggregate_from_tax_totals(self):
        """Fold Odoo ``tax_totals`` into TFHKA buckets and per-currency totals.

        Uses the same ``tax_totals`` structure as the invoice UI (including
        ``l10n_ve_igtf`` injection on ``total_amount``). IGTF tax groups are
        excluded from VAT buckets but reflected in ``total_apagar`` via the
        root ``total_amount`` / ``total_amount_currency`` fields.
        """
        self.ensure_one()
        tt = self.tax_totals
        if not isinstance(tt, dict):
            return None
        subtotals = tt.get("subtotals") or []
        if not subtotals:
            return None
        cur_inv = self.currency_id
        cur_comp = self.company_id.currency_id

        def fold_buckets(use_invoice_currency):
            buckets = defaultdict(lambda: {"base": 0.0, "tax": 0.0})
            gravado = 0.0
            exento = 0.0
            total_iva = 0.0
            cur = cur_inv if use_invoice_currency else cur_comp
            for sub in subtotals:
                for tg in sub.get("tax_groups", []):
                    if self._tfhka_is_igtf_tax_group(tg):
                        continue
                    code = self._tfhka_tax_group_to_codigo(tg)
                    rate = self._tfhka_tax_group_rate(tg)
                    rkey = round(float(rate), 4)
                    key = (code, rkey)
                    if use_invoice_currency:
                        b = tg.get("base_amount_currency", 0.0)
                        t = tg.get("tax_amount_currency", 0.0)
                    else:
                        b = tg.get("base_amount", 0.0)
                        t = tg.get("tax_amount", 0.0)
                    b = cur.round(b)
                    t = cur.round(t)
                    buckets[key]["base"] = cur.round(buckets[key]["base"] + b)
                    buckets[key]["tax"] = cur.round(buckets[key]["tax"] + t)
                    if code in ("G", "R", "A"):
                        gravado = cur.round(gravado + b)
                    else:
                        exento = cur.round(exento + b)
                    total_iva = cur.round(total_iva + t)
            return buckets, gravado, exento, total_iva

        inv_buckets, inv_gravado, inv_exento, _ = fold_buckets(True)
        comp_buckets, comp_gravado, comp_exento, _ = fold_buckets(False)

        inv_base = cur_inv.round(tt.get("base_amount_currency", 0.0))
        inv_tax = cur_inv.round(tt.get("tax_amount_currency", 0.0))
        inv_total = cur_inv.round(tt.get("total_amount_currency", 0.0))
        comp_base = cur_comp.round(tt.get("base_amount", 0.0))
        comp_tax = cur_comp.round(tt.get("tax_amount", 0.0))
        comp_total = cur_comp.round(tt.get("total_amount", 0.0))

        nro, total_desc, sub_antes = self._tfhka_line_discount_and_count()

        if not inv_buckets and inv_base:
            inv_exento = inv_base
            inv_gravado = 0.0
        if not comp_buckets and comp_base:
            comp_exento = comp_base
            comp_gravado = 0.0

        inv_sub = inv_base
        comp_sub = comp_base

        if inv_buckets:
            inv_buckets = self._tfhka_reconcile_buckets_to_targets(
                dict(inv_buckets), inv_base, inv_tax, cur_inv
            )
            inv_gravado, inv_exento = self._tfhka_gravado_exento_from_buckets(
                inv_buckets, cur_inv, subtotal_target=inv_sub
            )
        if comp_buckets:
            comp_buckets = self._tfhka_reconcile_buckets_to_targets(
                dict(comp_buckets), comp_base, comp_tax, cur_comp
            )
            comp_gravado, comp_exento = self._tfhka_gravado_exento_from_buckets(
                comp_buckets, cur_comp, subtotal_target=comp_sub
            )

        inv_iva_out = inv_tax
        comp_iva_out = comp_tax

        inv_total_con_iva = cur_inv.round(inv_sub + inv_iva_out)
        comp_total_con_iva = cur_comp.round(comp_sub + comp_iva_out)

        return {
            "inv": {
                "gravado": inv_gravado,
                "exento": inv_exento,
                "total_iva": inv_iva_out,
                "subtotal": inv_sub,
                "total_apagar": inv_total,
                "monto_total_con_iva": inv_total_con_iva,
                "buckets": dict(inv_buckets),
            },
            "comp": {
                "gravado": comp_gravado,
                "exento": comp_exento,
                "total_iva": comp_iva_out,
                "subtotal": comp_sub,
                "total_apagar": comp_total,
                "monto_total_con_iva": comp_total_con_iva,
                "buckets": dict(comp_buckets),
            },
            "total_descuento": total_desc,
            "subtotal_antes_descuento": sub_antes,
            "nro_items": nro,
        }

    def _tfhka_get_totals_for_payload(self):
        """Build internal totals dict for TFHKA mapping.

        Prefer :meth:`_tfhka_aggregate_from_tax_totals` so amounts match
        ``move.tax_totals``. If that is unavailable (empty structure), fall back
        to line-based aggregates.
        """
        self.ensure_one()
        tt_agg = self._tfhka_aggregate_from_tax_totals()
        if tt_agg:
            return tt_agg
        la = self._tfhka_get_line_aggregates()
        inv = {
            "gravado": la["gravado"],
            "exento": la["exento"],
            "total_iva": la["total_iva"],
            "subtotal": la["subtotal"],
            "total_apagar": la["total_apagar"],
            "monto_total_con_iva": la["monto_total_con_iva"],
            "buckets": la["buckets"],
        }
        if self.currency_id == self.company_id.currency_id:
            comp = dict(inv)
        else:
            comp = self._tfhka_convert_inv_totals_to_company(inv)
        return {
            "inv": inv,
            "comp": comp,
            "total_descuento": la["total_descuento"],
            "subtotal_antes_descuento": la["subtotal_antes_descuento"],
            "nro_items": la["nro_items"],
        }

    def _tfhka_get_line_aggregates(self):
        self.ensure_one()
        cur = self.currency_id
        line_items = self._tfhka_get_line_items()
        gravado = 0.0
        exento = 0.0
        total_iva = 0.0
        total_desc = 0.0
        subtotal_antes = 0.0
        buckets = defaultdict(lambda: {"base": 0.0, "tax": 0.0})
        sum_price_total = 0.0

        for line in line_items:
            ps = cur.round(line.price_subtotal)
            pt = cur.round(line.price_total)
            iva = cur.round(pt - ps)
            brutto = cur.round(line.price_unit * line.quantity)
            total_desc = cur.round(total_desc + cur.round(brutto - ps))
            subtotal_antes = cur.round(subtotal_antes + brutto)
            sum_price_total = cur.round(sum_price_total + pt)

            code = self._tfhka_get_line_tax_code(line)
            rate = self._tfhka_get_line_tax_rate(line)
            rkey = round(float(rate), 4)
            key = (code, rkey)
            buckets[key]["base"] = cur.round(buckets[key]["base"] + ps)
            buckets[key]["tax"] = cur.round(buckets[key]["tax"] + iva)

            if code in ("G", "R", "A"):
                gravado = cur.round(gravado + ps)
            else:
                exento = cur.round(exento + ps)
            total_iva = cur.round(total_iva + iva)

        subtotal = cur.round(gravado + exento)
        total_apagar = sum_price_total
        monto_total_con_iva = sum_price_total

        return {
            "gravado": gravado,
            "exento": exento,
            "total_iva": total_iva,
            "subtotal": subtotal,
            "total_descuento": total_desc,
            "subtotal_antes_descuento": subtotal_antes,
            "total_apagar": total_apagar,
            "monto_total_con_iva": monto_total_con_iva,
            "buckets": dict(buckets),
            "nro_items": len(line_items),
        }

    def _tfhka_build_identificacion_documento(self):
        self._tfhka_validate_identificacion_documento()
        self._tfhka_validate_affected_invoice_required()
        is_adjustment_document = self._tfhka_is_adjustment_document()
        data = {
            "tipoDocumento": self._tfhka_get_document_type(),
            "tipoTransaccion": self._tfhka_get_tipo_transaccion(),
            "numeroDocumento": self._tfhka_get_document_number(),
            "numeroPlanillaImportacion": "",
            "numeroExpedienteImportacion": "",
            "serieFacturaAfectada": "",
            "numeroFacturaAfectada": "",
            "fechaFacturaAfectada": "",
            "montoFacturaAfectada": "",
            "comentarioFacturaAfectada": "",
            "regimenEspTributacion": "",
            "fechaEmision": self._tfhka_get_issue_date(),
            "fechaVencimiento": self._tfhka_get_due_date(),
            "horaEmision": self._tfhka_get_issue_hour(),
            "tipoDePago": self._tfhka_get_tipo_de_pago(),
            "serie": self._tfhka_get_serie(),
            "sucursal": self._tfhka_get_sucursal(),
            "tipoDeVenta": self._tfhka_get_sale_type(),
            "moneda": self._tfhka_get_currency_code(),
            "transaccionId": "",
            "urlPdf": "",
        }
        if is_adjustment_document:
            data["serieFacturaAfectada"] = (
                self._tfhka_get_affected_invoice_serie() or ""
            )
            data["numeroFacturaAfectada"] = (
                self._tfhka_get_affected_invoice_number() or ""
            )
            data["fechaFacturaAfectada"] = self._tfhka_get_affected_invoice_date() or ""
            data["montoFacturaAfectada"] = (
                self._tfhka_get_affected_invoice_amount() or ""
            )
            data["comentarioFacturaAfectada"] = (
                self._tfhka_get_affected_invoice_comment() or ""
            )
        return data

    def _tfhka_build_vendedor(self):
        seller_name = self._tfhka_get_seller_name()
        if not seller_name:
            return None
        return {"nombre": seller_name, "codigo": "", "numCajero": ""}

    def _tfhka_get_dispatch_pickings_for_factura_guia(self):
        self.ensure_one()
        pickings = self.picking_ids
        if not pickings and self.invoice_origin:
            sale = self.env["sale.order"].search(
                [
                    ("name", "=", self.invoice_origin),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if sale:
                pickings = sale.picking_ids
        return pickings.filtered(
            lambda picking: picking.state == "done"
            and picking._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
            and picking._l10n_ve_edi_dispatch_guide_qualifies_for_factura_guia()
            and picking.sale_id
            and picking.sale_id.journal_id == self.journal_id
        ).sorted("id")

    def _tfhka_build_factura_guia(self):
        self.ensure_one()
        if self.move_type != "out_invoice":
            return None
        rows = []
        for picking in self._tfhka_get_dispatch_pickings_for_factura_guia()[:5]:
            if hasattr(picking, "_tfhka_get_document_number_for_reference"):
                numero = picking._tfhka_get_document_number_for_reference()
                serie = (
                    picking._tfhka_get_serie()
                    if hasattr(picking, "_tfhka_get_serie")
                    else ""
                )
            elif hasattr(picking, "_tfhka_get_document_number"):
                numero = picking._tfhka_get_document_number()
                serie = picking._tfhka_get_serie() or ""
            else:
                serie = ""
                numero = re.sub(r"\D", "", picking.name or str(picking.id or ""))
            numero = (numero or "").strip()
            if not numero:
                continue
            rows.append(
                {
                    "tipoDocumento": "04",
                    "serie": re.sub(r"[^0-9A-Za-z]", "", serie)[:20],
                    "numeroDocumento": numero[:19],
                }
            )
        return rows or None

    def _tfhka_build_comprador(self):
        buyer = self._l10n_ve_edi_get_buyer_partner()
        buyer_prefix, buyer_number = self._l10n_ve_edi_get_buyer_identification()
        phone = buyer.mobile or buyer.phone or ""
        email_list = [buyer.email] if buyer.email else []
        phone_list = [phone] if phone else []
        if email_list and not phone_list:
            raise UserError(
                _(
                    "La API TFHKA exige telefono en comprador cuando hay "
                    "correo. Indique telefono o movil del contacto."
                )
            )
        notificar = "Si" if (buyer.email or phone) else "No"
        return {
            "tipoIdentificacion": buyer_prefix,
            "numeroIdentificacion": buyer_number,
            "razonSocial": (buyer.name or "")[:100],
            "direccion": (buyer.street or buyer.contact_address_inline or "N/A")[:255],
            "pais": (buyer.country_id.code or "VE")[:2],
            "telefono": phone_list,
            "notificar": notificar,
            "correo": email_list,
        }

    def _tfhka_map_forma_pago_from_payment(self, payment):
        self.ensure_one()
        line = payment.payment_method_line_id
        if not line:
            return "99"
        name = (line.name or "").lower()
        code = (line.code or "").lower()
        if "transfer" in name or code in ("electronic", "sepa_ct", "sepa_dd"):
            return "03"
        if "tarjeta" in name or "card" in name or code in ("card", "credit_card"):
            return "05"
        if "efectivo" in name or "cash" in name or code == "cash":
            cur = payment.currency_id.name or "VES"
            return "08" if cur == "VES" else "09"
        if code == "manual" or "manual" in name:
            return "99"
        return "99"

    def _tfhka_collect_amounts_by_payment(self):
        self.ensure_one()
        raw = self._get_all_reconciled_invoice_partials()
        if not raw:
            return {}
        partials_list = raw if isinstance(raw, list) else []
        by_payment = {}
        for part in partials_list:
            if part.get("is_exchange"):
                continue
            aml = part.get("aml")
            if not aml:
                continue
            payment = aml.move_id.origin_payment_id
            if not payment:
                continue
            if getattr(payment, "is_retention", False):
                continue
            amt = abs(part.get("amount") or 0.0)
            if self.currency_id.is_zero(amt):
                continue
            by_payment[payment.id] = by_payment.get(payment.id, 0.0) + amt
        return by_payment

    def _tfhka_net_reconciled_from_payment_invoice_currency(self, payment):
        self.ensure_one()
        if getattr(payment, "is_retention", False):
            return 0.0
        raw = self._get_all_reconciled_invoice_partials()
        partials_list = raw if isinstance(raw, list) else []
        if not partials_list:
            return 0.0
        inv_cur = self.currency_id
        total = 0.0
        for part in partials_list:
            if part.get("is_exchange"):
                continue
            aml = part.get("aml")
            if not aml or aml.move_id.origin_payment_id != payment:
                continue
            amt = abs(part.get("amount") or 0.0)
            if inv_cur.is_zero(amt):
                continue
            total = inv_cur.round(total + amt)
        return total

    def _tfhka_convert_net_allocation_to_payment_currency(self, inv, payment, net_inv):
        inv.ensure_one()
        inv_cur = inv.currency_id
        pay_cur = payment.currency_id
        date = payment.date or inv.invoice_date or fields.Date.context_today(inv)
        if inv_cur == pay_cur:
            return pay_cur.round(net_inv)
        return pay_cur.round(inv_cur._convert(net_inv, pay_cur, inv.company_id, date))

    def _tfhka_is_single_customer_invoice_payment(self, payment):
        self.ensure_one()
        if getattr(payment, "is_retention", False):
            return False
        invs = payment.reconciled_invoice_ids.filtered(
            lambda m: m.is_sale_document(include_receipts=True)
        )
        return len(invs) == 1 and invs.id == self.id

    def _tfhka_forma_pago_amount_payment_currency(self, payment, norm_opts=None):
        self.ensure_one()
        pay_cur = payment.currency_id
        inv_cur = self.currency_id
        net_inv = self._tfhka_net_reconciled_from_payment_invoice_currency(payment)

        def _net_as_payment_currency():
            if inv_cur == pay_cur:
                return pay_cur.round(net_inv)
            return pay_cur.round(
                inv_cur._convert(
                    net_inv,
                    pay_cur,
                    self.company_id,
                    payment.date
                    or self.invoice_date
                    or fields.Date.context_today(self),
                )
            )

        if (
            not getattr(payment, "l10n_ve_apply_igtf", False)
            or self.country_code != "VE"
            or pay_cur.is_zero(payment.amount)
        ):
            result = _net_as_payment_currency()
        else:
            reconciled = payment.reconciled_invoice_ids.filtered(
                lambda m: m.is_sale_document(include_receipts=True)
            )
            if not reconciled:
                result = _net_as_payment_currency()
            else:
                nets_pay = {}
                for inv in reconciled:
                    n = inv._tfhka_net_reconciled_from_payment_invoice_currency(payment)
                    nets_pay[inv] = (
                        inv._tfhka_convert_net_allocation_to_payment_currency(
                            inv, payment, n
                        )
                    )
                total_net_pay = pay_cur.round(sum(nets_pay.values()))
                self_net_pay = nets_pay.get(self, 0.0)
                if pay_cur.is_zero(total_net_pay):
                    result = _net_as_payment_currency()
                else:
                    igtf_amt = pay_cur.round(
                        float(
                            getattr(payment, "l10n_ve_igtf_amount_currency", 0.0) or 0.0
                        )
                    )
                    if pay_cur.is_zero(igtf_amt):
                        remainder = pay_cur.round(payment.amount - total_net_pay)
                        if not pay_cur.is_zero(remainder):
                            igtf_amt = remainder
                    igtf_share = pay_cur.round(
                        igtf_amt * (self_net_pay / total_net_pay)
                    )
                    result = pay_cur.round(self_net_pay + igtf_share)

        if getattr(payment, "is_retention", False):
            return result
        if self._tfhka_is_single_customer_invoice_payment(
            payment
        ) and not pay_cur.is_zero(payment.amount):
            paid = pay_cur.round(payment.amount)
            if paid > result and not pay_cur.is_zero(paid - result):
                if norm_opts is not None:
                    norm_opts["skip_trim_excess"] = True
                return paid
        return result

    def _tfhka_get_reconciled_retention_totals(self):
        self.ensure_one()
        raw = self._get_all_reconciled_invoice_partials()
        if not raw:
            return {"inv": 0.0, "comp": 0.0}
        inv_cur = self.currency_id
        comp_cur = self.company_id.currency_id
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        inv_amount = 0.0
        for part in raw if isinstance(raw, list) else []:
            if part.get("is_exchange"):
                continue
            aml = part.get("aml")
            if not aml:
                continue
            payment = aml.move_id.origin_payment_id
            if not payment or not getattr(payment, "is_retention", False):
                continue
            amt = abs(part.get("amount") or 0.0)
            if inv_cur.is_zero(amt):
                continue
            inv_amount = inv_cur.round(inv_amount + amt)
        comp_amount = inv_amount
        if inv_cur != comp_cur:
            comp_amount = comp_cur.round(
                inv_cur._convert(inv_amount, comp_cur, self.company_id, date)
            )
        return {"inv": inv_amount, "comp": comp_amount}

    def _tfhka_get_igtf_totals(self):
        self.ensure_one()
        tt = self.tax_totals if isinstance(self.tax_totals, dict) else {}
        inv_cur = self.currency_id
        comp_cur = self.company_id.currency_id
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        inv = inv_cur.round(
            float(tt.get("l10n_ve_igtf_collected_amount_currency", 0.0) or 0.0)
        )
        comp = comp_cur.round(
            float(tt.get("l10n_ve_igtf_collected_amount", 0.0) or 0.0)
        )
        if inv_cur == comp_cur:
            return {"inv": inv, "comp": inv}
        if inv_cur.is_zero(inv) and not comp_cur.is_zero(comp):
            inv = inv_cur.round(comp_cur._convert(comp, inv_cur, self.company_id, date))
        if comp_cur.is_zero(comp) and not inv_cur.is_zero(inv):
            comp = comp_cur.round(
                inv_cur._convert(inv, comp_cur, self.company_id, date)
            )
        return {"inv": inv, "comp": comp}

    def _tfhka_format_igtf_impuesto_row(self, base, tax_amount, percent):
        pct = float(percent or 0.0)
        return {
            "codigoTotalImp": "IGTF",
            "alicuotaImp": self._l10n_ve_edi_format_decimal(pct),
            "baseImponibleImp": self._l10n_ve_edi_format_decimal(base),
            "valorTotalImp": self._l10n_ve_edi_format_decimal(tax_amount),
        }

    def _tfhka_build_impuestos_subtotal_list(
        self, buckets, igtf_base=None, igtf_tax=None, zero_currency=None
    ):
        self.ensure_one()
        rows = self._tfhka_build_impuestos_subtotal_from_buckets(buckets) or []
        cur = zero_currency or self.company_id.currency_id
        if (
            igtf_base is not None
            and igtf_tax is not None
            and (not cur.is_zero(igtf_base) or not cur.is_zero(igtf_tax))
        ):
            pct = self.company_id.l10n_ve_igtf_percent or 0.0
            rows.append(self._tfhka_format_igtf_impuesto_row(igtf_base, igtf_tax, pct))
        return rows if rows else None

    def _tfhka_get_igtf_bases_for_impuestos_row(self):
        self.ensure_one()
        if hasattr(self, "_l10n_ve_igtf_get_collected_amounts"):
            (
                base_inv,
                base_comp,
                tax_inv,
                tax_comp,
            ) = self._l10n_ve_igtf_get_collected_amounts(include_base=True)
            inv_cur = self.currency_id
            comp_cur = self.company_id.currency_id
            return (
                inv_cur.round(abs(base_inv or 0.0)),
                comp_cur.round(abs(base_comp or 0.0)),
                inv_cur.round(abs(tax_inv or 0.0)),
                comp_cur.round(abs(tax_comp or 0.0)),
            )
        igtf = self._tfhka_get_igtf_totals()
        z = self.currency_id
        c = self.company_id.currency_id
        return z.round(0.0), c.round(0.0), abs(igtf["inv"]), abs(igtf["comp"])

    def _tfhka_total_apagar_for_payload(self, payload):
        """Total to pay in (company currency, invoice currency).

        Taken from :meth:`_tfhka_get_totals_for_payload`, which is driven by
        ``tax_totals`` when possible, so ``total_amount`` / ``total_amount_currency``
        already include IGTF after ``l10n_ve_igtf`` injection.
        """
        self.ensure_one()
        return payload["comp"]["total_apagar"], payload["inv"]["total_apagar"]

    def _tfhka_formas_pago_line_amount_company_currency(self, line):
        self.ensure_one()
        comp_cur = self.company_id.currency_id
        m = float(line.get("monto") or 0.0)
        moneda = (line.get("moneda") or "VES")[:3]
        if moneda in ("VES", "VEF", "BSD"):
            return comp_cur.round(m)
        rate = float(line.get("tipoCambio") or 0.0)
        if rate <= 0:
            rate = float(getattr(self, "l10n_ve_inverse_rate", 0.0) or 0.0) or 1.0
        return comp_cur.round(m * rate)

    def _tfhka_formas_pago_sum_company_currency(self, lines):
        self.ensure_one()
        comp_cur = self.company_id.currency_id
        total = 0.0
        for line in lines:
            total = comp_cur.round(
                total + self._tfhka_formas_pago_line_amount_company_currency(line)
            )
        return total

    def _tfhka_formas_pago_apply_delta_company_currency(self, lines, delta):
        self.ensure_one()
        comp_cur = self.company_id.currency_id
        if comp_cur.is_zero(delta):
            return
        for i, line in enumerate(lines):
            moneda = (line.get("moneda") or "VES")[:3]
            m = float(line.get("monto") or 0.0)
            if moneda in ("VES", "VEF", "BSD"):
                lines[i]["monto"] = self._l10n_ve_edi_format_decimal(
                    comp_cur.round(m + delta)
                )
                return
        line0 = lines[0]
        m0 = float(line0.get("monto") or 0.0)
        rate = float(line0.get("tipoCambio") or 0.0)
        if rate <= 0:
            rate = float(getattr(self, "l10n_ve_inverse_rate", 0.0) or 0.0) or 1.0
        adj = (Decimal(str(delta)) / Decimal(str(rate))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        lines[0]["monto"] = self._l10n_ve_edi_format_decimal(
            float(Decimal(str(m0)) + adj)
        )

    def _tfhka_build_formas_pago_line(self, payment, amount):
        self.ensure_one()
        fecha = (
            payment.date.strftime("%d/%m/%Y")
            if payment.date
            else self._tfhka_get_issue_date()
        )
        desc = (payment.memo or payment.ref or payment.name or "Pago")[:120]
        cur = payment.currency_id
        cur_name = (cur.name or "VES")[:3]
        line = {
            "descripcion": desc,
            "fecha": fecha,
            "forma": self._tfhka_map_forma_pago_from_payment(payment),
            "monto": self._l10n_ve_edi_format_decimal(amount),
            "moneda": cur_name,
        }
        if cur_name not in ("VES", "BSD", "VEF"):
            rate = getattr(payment, "foreign_rate", None)
            if rate in (None, 0.0):
                rate = getattr(self, "l10n_ve_inverse_rate", 0.0) or 1.0
            line["tipoCambio"] = self._tfhka_format_tipo_cambio(rate)
        else:
            line["tipoCambio"] = "0.0000"
        return line

    def _tfhka_build_formas_pago_fallback(self, payload):
        self.ensure_one()
        comp_cur = self.company_id.currency_id
        cur = (comp_cur.name or "VES")[:3]
        ap_comp, _ap_inv = self._tfhka_total_apagar_for_payload(payload)
        line = {
            "descripcion": "Documento sin pagos conciliados a la fecha de envio",
            "fecha": self._tfhka_get_issue_date(),
            "forma": "99",
            "monto": self._l10n_ve_edi_format_decimal(ap_comp),
            "moneda": cur,
        }
        line["tipoCambio"] = "0.0000"
        return line

    def _tfhka_normalize_formas_pago_lines(self, lines, payload, norm_opts=None):
        self.ensure_one()
        if not lines:
            return lines
        comp_cur = self.company_id.currency_id
        target_bs, _target_inv = self._tfhka_total_apagar_for_payload(payload)
        skip_trim = bool(norm_opts and norm_opts.get("skip_trim_excess"))
        for _unused in range(12):
            sum_ves = self._tfhka_formas_pago_sum_company_currency(lines)
            delta = comp_cur.round(target_bs - sum_ves)
            if comp_cur.is_zero(delta):
                return lines
            if delta < 0 and skip_trim:
                return lines
            self._tfhka_formas_pago_apply_delta_company_currency(lines, delta)
        sum_ves = self._tfhka_formas_pago_sum_company_currency(lines)
        delta = comp_cur.round(target_bs - sum_ves)
        if comp_cur.is_zero(delta):
            return lines
        if delta < 0 and skip_trim:
            return lines
        if delta < 0:
            self._tfhka_formas_pago_apply_delta_company_currency(lines, delta)
            sum_ves = self._tfhka_formas_pago_sum_company_currency(lines)
            delta = comp_cur.round(target_bs - sum_ves)
        if not comp_cur.is_zero(delta):
            raise UserError(
                _(
                    "La suma de las formas de pago (en moneda de la compania "
                    "usando tipo de cambio de cada linea) no coincide con el "
                    "Total a Pagar fiscal. Suma formas VES: %(sum)s, "
                    "TotalAPagar: %(target)s, delta: %(d)s. Revise "
                    "conciliaciones, IGTF y moneda de los pagos."
                )
                % {"sum": sum_ves, "target": target_bs, "d": delta}
            )
        return lines

    def _tfhka_build_formas_pago(self, payload=None):
        self.ensure_one()
        if payload is None:
            payload = self._tfhka_get_totals_for_payload()
        norm_opts = {"skip_trim_excess": False}
        by_payment = self._tfhka_collect_amounts_by_payment()
        lines = []
        Payment = self.env["account.payment"]
        for pay_id in sorted(
            by_payment.keys(),
            key=lambda pid: Payment.browse(pid).date
            or fields.Date.context_today(Payment.browse(pid)),
        ):
            payment = Payment.browse(pay_id)
            if not payment.exists():
                continue
            amount = self._tfhka_forma_pago_amount_payment_currency(
                payment, norm_opts=norm_opts
            )
            if payment.currency_id.is_zero(amount):
                continue
            lines.append(self._tfhka_build_formas_pago_line(payment, amount))
        if not lines:
            lines = [self._tfhka_build_formas_pago_fallback(payload)]
        if len(lines) > 5:
            raise UserError(
                _(
                    "El maximo de formas de pago permitido es 5. Registre "
                    "menos pagos o agrupe antes de enviar."
                )
            )
        return self._tfhka_normalize_formas_pago_lines(
            lines, payload, norm_opts=norm_opts
        )

    def _tfhka_build_impuestos_subtotal_from_buckets(self, buckets):
        self.ensure_one()
        if not buckets:
            return None
        impuestos_subtotal = []
        for (code, rate), vals in sorted(
            buckets.items(), key=lambda x: (x[0][0], x[0][1])
        ):
            impuestos_subtotal.append(
                {
                    "codigoTotalImp": code,
                    "alicuotaImp": self._l10n_ve_edi_format_decimal(rate),
                    "baseImponibleImp": self._l10n_ve_edi_format_decimal(vals["base"]),
                    "valorTotalImp": self._l10n_ve_edi_format_decimal(vals["tax"]),
                }
            )
        return impuestos_subtotal

    def _tfhka_descuentos_a_bolivares(self, payload):
        self.ensure_one()
        comp_cur = self.company_id.currency_id
        inv_cur = self.currency_id
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        td = payload["total_descuento"]
        sa = payload["subtotal_antes_descuento"]
        if inv_cur == comp_cur:
            return td, sa
        return (
            comp_cur.round(inv_cur._convert(td, comp_cur, self.company_id, date)),
            comp_cur.round(inv_cur._convert(sa, comp_cur, self.company_id, date)),
        )

    def _tfhka_convert_inv_totals_to_company(self, inv):
        self.ensure_one()
        comp = self.company_id.currency_id
        inv_cur = self.currency_id
        date = self.invoice_date or self.date or fields.Date.context_today(self)

        def cnv(x):
            return comp.round(inv_cur._convert(x, comp, self.company_id, date))

        buckets = {}
        for key, vals in (inv.get("buckets") or {}).items():
            buckets[key] = {
                "base": cnv(vals["base"]),
                "tax": cnv(vals["tax"]),
            }
        return {
            "gravado": cnv(inv["gravado"]),
            "exento": cnv(inv["exento"]),
            "total_iva": cnv(inv["total_iva"]),
            "subtotal": cnv(inv["subtotal"]),
            "total_apagar": cnv(inv["total_apagar"]),
            "monto_total_con_iva": cnv(inv["monto_total_con_iva"]),
            "buckets": buckets,
        }

    def _tfhka_build_lista_desc_bonificacion(self):
        return None

    def _tfhka_build_otros_impuestos_subtotal(self):
        return None

    def _tfhka_build_totales(self, payload=None):
        """Build TFHKA header ``totales`` in company currency (e.g. VES).

        Numeric fields follow ``move.tax_totals`` via ``payload['comp']`` from
        :meth:`_tfhka_get_totals_for_payload` (gravado/exento/subtotal/IVA/total).
        """
        self.ensure_one()
        if payload is None:
            payload = self._tfhka_get_totals_for_payload()
        bs = payload["comp"]
        td_bs, sa_bs = self._tfhka_descuentos_a_bolivares(payload)
        igtf = self._tfhka_get_igtf_totals()
        retention = self._tfhka_get_reconciled_retention_totals()
        comp_cur = self.company_id.currency_id
        has_igtf = not comp_cur.is_zero(igtf["comp"])
        gravado = bs["gravado"]
        exento = bs["exento"]
        subtotal = bs["subtotal"]
        total_iva = bs["total_iva"]
        monto_total_con_iva_bs = bs["monto_total_con_iva"]
        total_apagar = bs["total_apagar"]
        igtf_base_inv, igtf_base_comp, igtf_tax_inv, igtf_tax_comp = (
            self._tfhka_get_igtf_bases_for_impuestos_row()
        )
        if has_igtf:
            imp_rows = self._tfhka_build_impuestos_subtotal_list(
                bs["buckets"], igtf_base_comp, igtf_tax_comp
            )
            total_igtf_key = None
            total_igtf_ves_key = None
            monto_total_oti_key = None
            monto_total_ivayoti_key = None
            _logger.info(
                "TFHKA totales VES (IGTF) move_id=%s grav=%s exc=%s sub=%s iva=%s "
                "montoTotalConIVA=%s igtf_row_base=%s igtf_row_tax=%s",
                self.id,
                gravado,
                exento,
                subtotal,
                total_iva,
                monto_total_con_iva_bs,
                igtf_base_comp,
                igtf_tax_comp,
            )
        else:
            imp_rows = self._tfhka_build_impuestos_subtotal_from_buckets(bs["buckets"])
            total_igtf_key = self._l10n_ve_edi_format_decimal(igtf["comp"])
            total_igtf_ves_key = self._l10n_ve_edi_format_decimal(igtf["comp"])
            monto_total_oti_key = None
            monto_total_ivayoti_key = None
        data = {
            "nroItems": str(payload["nro_items"]),
            "montoGravadoTotal": self._l10n_ve_edi_format_decimal(gravado),
            "montoExentoTotal": self._l10n_ve_edi_format_decimal(exento),
            "montoPercibidoTotal": self._l10n_ve_edi_format_decimal(retention["comp"]),
            "subtotalAntesDescuento": self._l10n_ve_edi_format_decimal(sa_bs),
            "totalDescuento": self._l10n_ve_edi_format_decimal(td_bs),
            "totalRecargos": None,
            "subtotal": self._l10n_ve_edi_format_decimal(subtotal),
            "totalIVA": self._l10n_ve_edi_format_decimal(total_iva),
            "montoTotalConIVA": self._l10n_ve_edi_format_decimal(
                monto_total_con_iva_bs
            ),
            "totalAPagar": self._l10n_ve_edi_format_decimal(total_apagar),
            "montoEnLetras": self._tfhka_get_monto_en_letras() or None,
            "listaRecargo": None,
            "listaDescBonificacion": self._tfhka_build_lista_desc_bonificacion(),
            "impuestosSubtotal": imp_rows,
            "otrosImpuestosSubtotal": self._tfhka_build_otros_impuestos_subtotal(),
            "totalIGTF": total_igtf_key,
            "totalIGTF_VES": total_igtf_ves_key,
            "montoTotalOTI": monto_total_oti_key,
            "montoTotalIVAyOTI": monto_total_ivayoti_key,
        }
        self._tfhka_log_totales_tfhka_debug(
            payload, igtf, monto_total_ivayoti_key, has_igtf
        )
        formas_pago = self._tfhka_build_formas_pago(payload)
        if formas_pago:
            data["formasPago"] = formas_pago
        return data

    def _tfhka_convert_bs_to_foreign(self, amount_bs, rate):
        self.ensure_one()
        if not rate:
            return 0.0
        amount_dec = Decimal(str(amount_bs or 0.0))
        rate_dec = Decimal(str(rate))
        result = (amount_dec / rate_dec).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return float(result)

    def _tfhka_build_totales_otra_moneda(self, payload=None):
        """Build TFHKA ``totalesOtraMoneda`` when the invoice currency is not VES.

        Amounts follow ``move.tax_totals`` via ``payload['inv']`` from
        :meth:`_tfhka_get_totals_for_payload`.
        """
        self.ensure_one()
        if self.currency_id == self.company_id.currency_id:
            return None
        rate = getattr(self, "l10n_ve_inverse_rate", 0.0) or 0.0
        if not rate:
            raise UserError(
                _(
                    "Para facturas en moneda extranjera debe existir tasa de "
                    "cambio a bolivares (fecha de factura y tasa de la moneda "
                    "en la empresa)."
                )
            )
        if payload is None:
            payload = self._tfhka_get_totals_for_payload()
        inv = payload["inv"]
        td_inv = payload["total_descuento"]
        sa_inv = payload["subtotal_antes_descuento"]
        igtf = self._tfhka_get_igtf_totals()
        retention = self._tfhka_get_reconciled_retention_totals()
        inv_cur = self.currency_id
        comp_cur = self.company_id.currency_id
        has_igtf = not comp_cur.is_zero(igtf["comp"])
        gravado = inv["gravado"]
        exento = inv["exento"]
        subtotal = inv["subtotal"]
        total_iva = inv["total_iva"]
        monto_total_con_iva_inv = inv["monto_total_con_iva"]
        total_apagar = inv["total_apagar"]
        (
            igtf_base_inv,
            _igtf_base_comp,
            igtf_tax_inv,
            _igtf_tax_comp,
        ) = self._tfhka_get_igtf_bases_for_impuestos_row()
        if has_igtf:
            imp_rows_inv = self._tfhka_build_impuestos_subtotal_list(
                inv["buckets"], igtf_base_inv, igtf_tax_inv, zero_currency=inv_cur
            )
            total_igtf_key = None
            total_igtf_ves_key = None
            monto_total_oti_key = None
            monto_total_ivayoti_key = None
            _logger.info(
                "TFHKA totales otra moneda (IGTF) move_id=%s grav=%s exc=%s "
                "sub=%s iva=%s "
                "montoTotalConIVA=%s igtf_row_base=%s igtf_row_tax=%s",
                self.id,
                gravado,
                exento,
                subtotal,
                total_iva,
                monto_total_con_iva_inv,
                igtf_base_inv,
                igtf_tax_inv,
            )
        else:
            imp_rows_inv = self._tfhka_build_impuestos_subtotal_from_buckets(
                inv["buckets"]
            )
            total_igtf_key = self._l10n_ve_edi_format_decimal(igtf["inv"])
            total_igtf_ves_key = self._l10n_ve_edi_format_decimal(igtf["comp"])
            monto_total_oti_key = None
            monto_total_ivayoti_key = None
        inv_code = (self.currency_id.name or "USD")[:3]

        data = {
            "moneda": inv_code,
            "tipoCambio": self._tfhka_format_tipo_cambio(rate),
            "montoGravadoTotal": self._l10n_ve_edi_format_decimal(gravado),
            "montoExentoTotal": self._l10n_ve_edi_format_decimal(exento),
            "montoPercibidoTotal": self._l10n_ve_edi_format_decimal(retention["inv"]),
            "subtotalAntesDescuento": self._l10n_ve_edi_format_decimal(sa_inv),
            "totalDescuento": self._l10n_ve_edi_format_decimal(td_inv),
            "totalRecargos": None,
            "subtotal": self._l10n_ve_edi_format_decimal(subtotal),
            "totalIVA": self._l10n_ve_edi_format_decimal(total_iva),
            "montoTotalConIVA": self._l10n_ve_edi_format_decimal(
                monto_total_con_iva_inv
            ),
            "totalAPagar": self._l10n_ve_edi_format_decimal(total_apagar),
            "montoEnLetras": None,
            "listaRecargo": None,
            "listaDescBonificacion": None,
            "impuestosSubtotal": imp_rows_inv,
            "otrosImpuestosSubtotal": None,
            "totalIGTF": total_igtf_key,
            "totalIGTF_VES": total_igtf_ves_key,
            "montoTotalOTI": monto_total_oti_key,
            "montoTotalIVAyOTI": monto_total_ivayoti_key,
        }
        return data

    def _tfhka_build_info_adicional(self):
        return []

    def _tfhka_build_info_adicional_item(self, line):
        return []

    def _tfhka_build_item_detail(self, index, line, tax_code, tax_rate, line_iva):
        product = line.product_id
        plu = ""
        if product:
            plu = (product.barcode or product.default_code or "")[:60]
        qty = line.quantity
        pu = line.price_unit
        brutto = pu * qty
        discount_monto = brutto - line.price_subtotal
        pu_con_desc = pu * (1 - (line.discount or 0) / 100.0) if line.discount else pu
        return {
            "numeroLinea": str(index),
            "codigoCIIU": "",
            "codigoPLU": plu,
            "indicadorBienoServicio": "2"
            if product and product.type == "service"
            else "1",
            "descripcion": (line.name or product.display_name or "")[:500],
            "cantidad": self._l10n_ve_edi_format_decimal(qty),
            "unidadMedida": (line.product_uom_id.name or "UND")[:3],
            "precioUnitario": self._l10n_ve_edi_format_decimal(pu),
            "precioUnitarioDescuento": self._l10n_ve_edi_format_decimal(pu_con_desc)
            if line.discount
            else None,
            "montoBonificacion": None,
            "descripcionBonificacion": None,
            "descuentoMonto": self._l10n_ve_edi_format_decimal(discount_monto),
            "recargoMonto": self._l10n_ve_edi_format_decimal(0.0),
            "precioItem": self._l10n_ve_edi_format_decimal(line.price_subtotal),
            "precioAntesDescuento": self._l10n_ve_edi_format_decimal(brutto),
            "codigoImpuesto": tax_code,
            "tasaIVA": self._tfhka_format_tasa_iva(tax_rate),
            "valorIVA": self._l10n_ve_edi_format_decimal(line_iva),
            "valorTotalItem": self._l10n_ve_edi_format_decimal(line.price_total),
            "infoAdicionalItem": self._tfhka_build_info_adicional_item(line),
            "listaItemOTI": None,
        }

    def _tfhka_build_detalles_items(self):
        details = []
        line_items = self._tfhka_get_line_items()
        if not line_items:
            raise UserError(
                _("No se encontraron lineas facturables para generar DetallesItems.")
            )
        for index, line in enumerate(line_items, start=1):
            tax_rate = self._tfhka_get_line_tax_rate(line)
            tax_code = self._tfhka_get_line_tax_code(line)
            line_iva = self._tfhka_get_line_iva_value(line)
            details.append(
                self._tfhka_build_item_detail(index, line, tax_code, tax_rate, line_iva)
            )
        return details

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        if self.journal_id.l10n_ve_edi_provider != "tfhka":
            return super()._l10n_ve_edi_dispatch_payload(payload)
        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            _logger.error(
                "TFHKA envio omitido move_id=%s name=%s: credenciales no configuradas",
                self.id,
                self.name,
            )
            return {"success": False, "error": "Credenciales TFHKA no configuradas."}
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        prepared = {}
        try:
            auth = client.authenticate(username, password)
            token = auth.get("token")
            if not token:
                _logger.error(
                    "TFHKA envio fallido move_id=%s auth sin token respuesta=%s",
                    self.id,
                    self._tfhka_safe_json_for_log(auth, 4000),
                )
                return {
                    "success": False,
                    "error": "La API TFHKA no devolvio token JWT.",
                }
            prepared = self._tfhka_prepare_api_payload(payload)
            response = client.issue_document(prepared, token)
            return {"success": True, "response": response}
        except UserError as exc:
            msg = str(exc)
            self._tfhka_log_emision_failure_analysis(payload, prepared, msg)
            if "TFHKA codigo 201" in msg or (
                "TFHKA codigo 203" in msg and "MontoTotalIVAyOTI" in msg
            ):
                try:
                    fallback = self._tfhka_fetch_existing_document_data(
                        client, token, prepared
                    )
                except UserError as fetch_exc:
                    return {"success": False, "error": str(fetch_exc)}
                if fallback:
                    return {"success": True, "response": fallback}
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            self._tfhka_log_emision_failure_analysis(payload, prepared, str(exc))
            return {"success": False, "error": str(exc)}

    def _tfhka_normalize_numero_documento_digits(self, value):
        return re.sub(r"\D", "", value or "")

    def _tfhka_document_status_matches_invoice(self, prepared_payload, status_response):
        if not isinstance(status_response, dict):
            return False
        estado = status_response.get("estado")
        if not isinstance(estado, dict):
            return False
        ident = (
            (prepared_payload or {})
            .get("documentoElectronico", {})
            .get("encabezado", {})
            .get("identificacionDocumento", {})
        )
        payload_fecha = (ident.get("fechaEmision") or "").strip()
        tfhka_fecha = (
            estado.get("fechaAsignacion")
            or estado.get("fechaAsignacionNumeroControl")
            or ""
        ).strip()
        if payload_fecha and tfhka_fecha and payload_fecha != tfhka_fecha:
            return False
        payload_num = self._tfhka_normalize_numero_documento_digits(
            ident.get("numeroDocumento")
        )
        tfhka_num = self._tfhka_normalize_numero_documento_digits(
            estado.get("numeroDocumento")
        )
        if payload_num and tfhka_num and payload_num != tfhka_num:
            payload_tail = payload_num.lstrip("0")
            tfhka_tail = tfhka_num.lstrip("0")
            if payload_tail != tfhka_tail and not (
                payload_tail.endswith(tfhka_tail) or tfhka_tail.endswith(payload_tail)
            ):
                return False
        return True

    def _tfhka_raise_duplicate_document_collision(
        self, prepared_payload, status_response
    ):
        self.ensure_one()
        ident = (
            (prepared_payload or {})
            .get("documentoElectronico", {})
            .get("encabezado", {})
            .get("identificacionDocumento", {})
        )
        estado = (status_response or {}).get("estado") or {}
        numero = ident.get("numeroDocumento") or self._tfhka_get_document_number()
        env_digit = self.journal_id._tfhka_get_numero_documento_environment_digit()
        raise UserError(
            _(
                "TFHKA indica documento duplicado: el numeroDocumento %(num)s ya "
                "existe (numero de control %(ctrl)s, asignado el %(tfhka_fecha)s), "
                "pero ese registro no corresponde a esta factura "
                "(fecha de emision %(inv_fecha)s). Avance la secuencia del diario "
                "a un correlativo cuyo numeroDocumento aun no este "
                "registrado en TFHKA, "
                "o configure en el diario un digito de ambiente TFHKA distinto al "
                "actual (%(env)s) si emite en otro entorno HKA."
            )
            % {
                "num": numero,
                "ctrl": self._tfhka_extract_numero_control(status_response) or "?",
                "tfhka_fecha": estado.get("fechaAsignacion") or "?",
                "inv_fecha": ident.get("fechaEmision") or "?",
                "env": env_digit,
            }
        )

    def _tfhka_fetch_existing_document_data(self, client, token, prepared_payload):
        self.ensure_one()
        ident = {}
        try:
            ident = (
                (prepared_payload or {})
                .get("documentoElectronico", {})
                .get("encabezado", {})
                .get("identificacionDocumento", {})
            )
        except Exception:
            ident = {}
        numero = ident.get("numeroDocumento") or self._tfhka_get_document_number()
        serie = ident.get("serie") or self._tfhka_get_serie()
        tipo = ident.get("tipoDocumento") or self._tfhka_get_document_type()
        consultas = [
            (
                client.get_document_status,
                {
                    "tipoDocumento": tipo,
                    "numeroDocumento": numero,
                    "serie": serie,
                },
            ),
            (
                client.get_last_document,
                {
                    "tipoDocumento": tipo,
                    "serie": serie,
                },
            ),
            (
                client.get_last_document,
                {
                    "serie": serie,
                },
            ),
        ]
        collision_response = False
        for idx, (call, query) in enumerate(consultas):
            try:
                resp = call(query, token)
            except Exception:
                continue
            control = self._tfhka_extract_numero_control(resp)
            if not control:
                continue
            if self._tfhka_document_status_matches_invoice(prepared_payload, resp):
                return resp
            if idx == 0:
                collision_response = resp
        if collision_response:
            self._tfhka_raise_duplicate_document_collision(
                prepared_payload, collision_response
            )
        return {}

    def _l10n_ve_edi_tfhka_replace_invoice_report_with_digital_pdf(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.state == "posted"
            and self.journal_id.l10n_ve_emission_medium == "digital"
            and self.journal_id.l10n_ve_edi_provider == "tfhka"
            and self.l10n_ve_edi_send_state == "sent"
        )

    def _l10n_ve_edi_tfhka_try_attach_official_pdf(self):
        self.ensure_one()
        if self.invoice_pdf_report_file:
            return True
        pdf_bytes, err = self._tfhka_get_invoice_pdf_bytes_via_descarga_archivo()
        if not pdf_bytes:
            _logger.warning(
                "TFHKA: PDF oficial no disponible (DescargaArchivo) move_id=%s err=%s",
                self.id,
                err,
            )
            return False
        vals = {
            "invoice_pdf_report_file": base64.b64encode(pdf_bytes).decode("ascii"),
        }
        if (
            self.company_id.account_fiscal_country_id.code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
        ):
            vals["l10n_ve_invoice_original_printed"] = True
        self.write(vals)
        return True

    def _l10n_ve_edi_tfhka_ensure_invoice_pdf_report(self):
        self.ensure_one()
        if self.invoice_pdf_report_file:
            return True
        return self._l10n_ve_edi_tfhka_try_attach_official_pdf()

    def _tfhka_refresh_invoice_payload_factura_guia_before_send(self):
        self.ensure_one()
        if self.move_type != "out_invoice":
            return
        attachment = self.l10n_ve_edi_payload_attachment_id
        if not attachment or not attachment.datas:
            return
        try:
            payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
        except (json.JSONDecodeError, TypeError, ValueError, binascii.Error):
            return
        factura_guia = self._tfhka_build_factura_guia()
        if not factura_guia:
            return
        encabezado = payload.setdefault("documentoElectronico", {}).setdefault(
            "encabezado", {}
        )
        if encabezado.get("facturaGuia") == factura_guia:
            return
        encabezado["facturaGuia"] = factura_guia
        new_attachment = self._l10n_ve_edi_create_payload_attachment(payload)
        self.write({"l10n_ve_edi_payload_attachment_id": new_attachment.id})

    def _run_job(self):
        self.ensure_one()
        if self.journal_id.l10n_ve_edi_provider == "tfhka":
            self._tfhka_refresh_invoice_payload_factura_guia_before_send()
        result = super()._run_job()
        if (
            result
            and self.move_type == "out_invoice"
            and self.journal_id.l10n_ve_edi_provider == "tfhka"
            and self.l10n_ve_edi_send_state == STATE_SENT
        ):
            self._l10n_ve_edi_tfhka_sync_dispatch_guides_with_invoice()
        return result

    def _l10n_ve_edi_on_dispatch_success(self, response):
        super()._l10n_ve_edi_on_dispatch_success(response)
        self.ensure_one()
        if self.journal_id.l10n_ve_edi_provider != "tfhka":
            return
        vals = {}
        numero = self._tfhka_extract_numero_control(response)
        if numero:
            vals["l10n_ve_control_number"] = numero
        if vals:
            self.write(vals)
        self._l10n_ve_edi_tfhka_try_attach_official_pdf()

    def _l10n_ve_edi_tfhka_sync_dispatch_guides_with_invoice(self):
        self.ensure_one()
        if (
            self.move_type != "out_invoice"
            or self.state != "posted"
            or self.journal_id.l10n_ve_edi_provider != "tfhka"
            or self.l10n_ve_edi_send_state != "sent"
        ):
            return
        pickings = self._tfhka_get_dispatch_pickings_for_factura_guia().filtered(
            lambda picking: picking.l10n_ve_edi_send_state == "sent"
        )
        for picking in pickings:
            picking._l10n_ve_edi_tfhka_resend_with_invoice_links(self)

    def _tfhka_extract_numero_control(self, response):
        if not isinstance(response, dict):
            return ""
        estado = response.get("estado")
        if isinstance(estado, dict):
            num = estado.get("numeroControl") or estado.get("numero_control")
            if num:
                return str(num).strip()
        resultado = response.get("resultado")
        if isinstance(resultado, dict):
            num = resultado.get("numeroControl") or resultado.get("numero_control")
            if num:
                return str(num).strip()
            ident = (
                resultado.get("documentoElectronico", {})
                .get("encabezado", {})
                .get("identificacionDocumento", {})
            )
            if isinstance(ident, dict):
                num = ident.get("numeroControl") or ident.get("numero_control")
                if num:
                    return str(num).strip()
        ident = (
            response.get("documentoElectronico", {})
            .get("encabezado", {})
            .get("identificacionDocumento", {})
        )
        if isinstance(ident, dict):
            num = ident.get("numeroControl") or ident.get("numero_control")
            if num:
                return str(num).strip()
        num = response.get("numeroControl") or response.get("numero_control")
        return str(num).strip() if num else ""

    def button_cancel(self):
        for move in self:
            move._tfhka_cancel_digital_document()
        return super().button_cancel()
