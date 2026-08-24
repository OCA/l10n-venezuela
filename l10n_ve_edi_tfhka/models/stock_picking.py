import base64
import binascii
import json
import logging
import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DISPATCH_GUIDE_DOCUMENT_TYPE = "04"


class StockPicking(models.Model):
    _inherit = "stock.picking"

    l10n_ve_edi_tfhka_show_sent_actions = fields.Boolean(
        compute="_compute_l10n_ve_edi_tfhka_sent_actions",
        string="TFHKA: guia EDI enviada",
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
        "picking_type_code",
        "company_id",
    )
    def _compute_l10n_ve_edi_tfhka_sent_actions(self):
        for picking in self:
            picking.l10n_ve_edi_tfhka_show_sent_actions = (
                picking._l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf()
            )
            picking.l10n_ve_edi_tfhka_sent_pdf_url = False
            picking.l10n_ve_edi_tfhka_sent_document_url = False
            if (
                picking._l10n_ve_edi_get_dispatch_edi_provider() != "tfhka"
                or not picking.l10n_ve_edi_response_json
            ):
                continue
            pdf_url, doc_url = picking._tfhka_extract_public_urls_from_stored_response()
            picking.l10n_ve_edi_tfhka_sent_pdf_url = pdf_url
            picking.l10n_ve_edi_tfhka_sent_document_url = doc_url

    def _l10n_ve_edi_tfhka_dispatch_guide_was_sent_to_tfhka(self):
        self.ensure_one()
        return (
            self.state == "done"
            and self._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
            and self._l10n_ve_edi_get_dispatch_edi_provider() == "tfhka"
            and self.l10n_ve_edi_send_state == "sent"
        )

    def _l10n_ve_edi_tfhka_dispatch_guide_has_edi_history(self):
        self.ensure_one()
        return (
            self._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
            and self.l10n_ve_edi_send_state in ("sent", "failed", "queued")
            and self._l10n_ve_edi_get_dispatch_edi_provider() == "tfhka"
        )

    @api.depends(
        "state",
        "picking_type_code",
        "l10n_ve_edi_send_state",
        "company_id",
        "sale_id",
        "sale_id.journal_id",
        "sale_id.journal_id.l10n_ve_emission_medium",
        "sale_id.journal_id.l10n_ve_edi_provider",
        "move_ids",
        "move_ids.state",
        "move_ids.quantity",
        "move_ids.product_uom_qty",
        "move_ids.sale_line_id",
        "move_ids.product_id",
        "invoice_ids",
    )
    def _compute_l10n_ve_edi_show_tab(self):
        for picking in self:
            picking.l10n_ve_edi_show_tab = (
                picking._l10n_ve_edi_dispatch_guide_uses_digital()
                or picking._l10n_ve_edi_tfhka_dispatch_guide_has_edi_history()
            )

    def _l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf(self):
        self.ensure_one()
        return self._l10n_ve_edi_tfhka_dispatch_guide_was_sent_to_tfhka()

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

    def _tfhka_get_reference_journal(self):
        self.ensure_one()
        return self._l10n_ve_edi_get_edi_journal()

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

    def _tfhka_get_serie(self):
        self.ensure_one()
        return self._tfhka_serie_from_journal(self._tfhka_get_reference_journal())

    def _tfhka_get_sucursal(self):
        self.ensure_one()
        return self._tfhka_sucursal_from_journal(self._tfhka_get_reference_journal())

    def _tfhka_format_date(self, value):
        if not value:
            value = fields.Date.context_today(self)
        if isinstance(value, str):
            return value
        return value.strftime("%d/%m/%Y")

    def _tfhka_get_issue_date(self):
        self.ensure_one()
        if self.l10n_ve_dispatch_guide_date:
            return self._tfhka_format_date(self.l10n_ve_dispatch_guide_date)
        if self.date_done:
            localized = fields.Datetime.context_timestamp(self, self.date_done)
            return localized.strftime("%d/%m/%Y")
        return self._tfhka_format_date(fields.Date.context_today(self))

    def _tfhka_get_issue_hour(self):
        self.ensure_one()
        if self.date_done:
            localized = fields.Datetime.context_timestamp(self, self.date_done)
            return (
                f"{localized.strftime('%I:%M:%S')} {localized.strftime('%p').lower()}"
            )
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return f"{now.strftime('%I:%M:%S')} {now.strftime('%p').lower()}"

    def _tfhka_get_document_currency(self):
        self.ensure_one()
        if self.sale_id:
            return self.sale_id.currency_id
        return self.l10n_ve_dispatch_currency_id or self.company_id.currency_id

    def _tfhka_get_conversion_date(self):
        self.ensure_one()
        if self.date_done:
            return fields.Datetime.to_datetime(self.date_done).date()
        if self.sale_id and self.sale_id.date_order:
            return fields.Datetime.to_datetime(self.sale_id.date_order).date()
        return fields.Date.context_today(self)

    def _tfhka_get_inverse_rate(self):
        self.ensure_one()
        doc_cur = self._tfhka_get_document_currency()
        comp_cur = self.company_id.currency_id
        if doc_cur == comp_cur:
            return 1.0
        if self.sale_id and self.sale_id.l10n_ve_inverse_rate:
            return self.sale_id.l10n_ve_inverse_rate
        rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", doc_cur.id),
                ("company_id", "=", self.company_id.id),
                ("name", "<=", self._tfhka_get_conversion_date()),
            ],
            order="name desc",
            limit=1,
        )
        if rate and rate.rate:
            return 1.0 / rate.rate
        return 0.0

    def _tfhka_get_currency_code(self):
        self.ensure_one()
        currency = re.sub(
            r"[^0-9A-Za-z]", "", self._tfhka_get_document_currency().name or "VES"
        ).upper()
        return (currency or "VES")[:3]

    def _tfhka_format_tipo_cambio(self, rate):
        return f"{abs(float(rate or 0.0)):.4f}"

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
            key: {"base": cur.round(vals["base"]), "tax": cur.round(vals["tax"])}
            for key, vals in buckets.items()
        }
        sum_b, sum_t = self._tfhka_sum_buckets_base_tax(out, cur)
        db = cur.round(target_base - sum_b)
        dt = cur.round(target_tax - sum_t)
        if cur.is_zero(db) and cur.is_zero(dt):
            return out
        key_max = max(out.keys(), key=lambda key: (out[key]["base"], key))
        out[key_max]["base"] = cur.round(out[key_max]["base"] + db)
        out[key_max]["tax"] = cur.round(out[key_max]["tax"] + dt)
        return out

    def _tfhka_gravado_exento_from_buckets(self, buckets, cur, subtotal_target=None):
        gravado_raw = sum(
            vals.get("base", 0.0)
            for (code, _rate), vals in buckets.items()
            if code in ("G", "R", "A")
        )
        exento_raw = sum(
            vals.get("base", 0.0)
            for (code, _rate), vals in buckets.items()
            if code not in ("G", "R", "A")
        )
        gravado = cur.round(gravado_raw)
        if subtotal_target is not None:
            exento = cur.round(cur.round(subtotal_target) - gravado)
        else:
            exento = cur.round(exento_raw)
        return gravado, exento

    def _tfhka_build_impuestos_subtotal_from_buckets(self, buckets):
        self.ensure_one()
        if not buckets:
            return None
        rows = []
        for (code, rate), vals in sorted(
            buckets.items(), key=lambda item: (item[0][0], item[0][1])
        ):
            rows.append(
                {
                    "codigoTotalImp": code,
                    "alicuotaImp": self._tfhka_format_tasa_iva(rate),
                    "baseImponibleImp": self._l10n_ve_edi_format_decimal(vals["base"]),
                    "valorTotalImp": self._l10n_ve_edi_format_decimal(vals["tax"]),
                }
            )
        return rows

    def _tfhka_convert_inv_totals_to_company(self, inv):
        self.ensure_one()
        comp = self.company_id.currency_id
        inv_cur = self._tfhka_get_document_currency()
        date = self._tfhka_get_conversion_date()

        def cnv(amount):
            return comp.round(inv_cur._convert(amount, comp, self.company_id, date))

        buckets = {}
        for key, vals in (inv.get("buckets") or {}).items():
            buckets[key] = {"base": cnv(vals["base"]), "tax": cnv(vals["tax"])}
        return {
            "gravado": cnv(inv["gravado"]),
            "exento": cnv(inv["exento"]),
            "total_iva": cnv(inv["total_iva"]),
            "subtotal": cnv(inv["subtotal"]),
            "total_apagar": cnv(inv["total_apagar"]),
            "monto_total_con_iva": cnv(inv["monto_total_con_iva"]),
            "buckets": buckets,
        }

    def _tfhka_secuencia_for_numero_documento(self):
        self.ensure_one()
        ref_date = self.date_done or self.scheduled_date
        journal = self._tfhka_get_reference_journal()
        env_digit = (
            journal._tfhka_get_numero_documento_environment_digit() if journal else "0"
        )
        return self.env[
            "l10n_ve.edi.tfhka.document.mixin"
        ]._tfhka_build_secuencia_yyyy_mm_seq(
            ref_date, self.name, self.id, environment_digit=env_digit
        )

    def _tfhka_get_document_number(self):
        self.ensure_one()
        return (
            f"{DISPATCH_GUIDE_DOCUMENT_TYPE}"
            f"{self._tfhka_secuencia_for_numero_documento()}"
        )

    def _tfhka_get_document_number_for_reference(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id
        if attachment and attachment.datas:
            try:
                payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
                ident = (
                    payload.get("documentoElectronico", {})
                    .get("encabezado", {})
                    .get("identificacionDocumento", {})
                )
                numero = (ident.get("numeroDocumento") or "").strip()
                if numero:
                    return numero
            except (json.JSONDecodeError, TypeError, ValueError, binascii.Error):
                _logger.debug(
                    "TFHKA: could not read stored payload for document number "
                    "picking_id=%s",
                    self.id,
                    exc_info=True,
                )
        return self._tfhka_get_document_number()

    def _tfhka_get_document_number_for_emission(self):
        self.ensure_one()
        if self.l10n_ve_edi_send_state == "sent":
            return self._tfhka_get_document_number_for_reference()
        return self._tfhka_get_document_number()

    def _tfhka_get_line_tax_rate(self, taxes):
        tax = taxes[:1]
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

    def _tfhka_format_tasa_iva(self, rate):
        r = float(rate or 0.0)
        if abs(r - round(r)) < 0.001:
            return str(int(round(r)))
        return self._l10n_ve_edi_format_decimal(r)

    def _tfhka_get_dispatch_moves(self):
        self.ensure_one()
        return self.move_ids.filtered(
            lambda move: move.product_id and move.state == "done"
        )

    def _tfhka_get_line_aggregates(self):
        self.ensure_one()
        cur = self._tfhka_get_document_currency()
        date = self._tfhka_get_conversion_date()
        gravado = exento = total_iva = total_desc = subtotal_antes = sum_price_total = (
            0.0
        )
        buckets = defaultdict(lambda: {"base": 0.0, "tax": 0.0})
        for move in self._tfhka_get_dispatch_moves():
            pricing = move._l10n_ve_dispatch_line_pricing_values()
            line_cur = pricing["currency"]
            qty = move.quantity if move.state == "done" else move.product_uom_qty
            pu = cur.round(
                line_cur._convert(pricing["price_unit"], cur, self.company_id, date)
            )
            ps = cur.round(
                line_cur._convert(pricing["subtotal"], cur, self.company_id, date)
            )
            pt = cur.round(
                line_cur._convert(pricing["total_included"], cur, self.company_id, date)
            )
            iva = cur.round(pt - ps)
            brutto = cur.round(pu * qty)
            total_desc = cur.round(total_desc + cur.round(brutto - ps))
            subtotal_antes = cur.round(subtotal_antes + brutto)
            sum_price_total = cur.round(sum_price_total + pt)
            taxes = pricing["taxes"]
            rate = self._tfhka_get_line_tax_rate(taxes)
            code = self._tfhka_get_line_tax_code_for_rate(rate)
            key = (code, round(float(rate), 4))
            buckets[key]["base"] = cur.round(buckets[key]["base"] + ps)
            buckets[key]["tax"] = cur.round(buckets[key]["tax"] + iva)
            if code in ("G", "R", "A"):
                gravado = cur.round(gravado + ps)
            else:
                exento = cur.round(exento + ps)
            total_iva = cur.round(total_iva + iva)
        subtotal = cur.round(gravado + exento)
        return {
            "gravado": gravado,
            "exento": exento,
            "total_iva": total_iva,
            "subtotal": subtotal,
            "total_descuento": total_desc,
            "subtotal_antes_descuento": subtotal_antes,
            "total_apagar": sum_price_total,
            "monto_total_con_iva": sum_price_total,
            "buckets": dict(buckets),
            "nro_items": len(self._tfhka_get_dispatch_moves()),
        }

    def _tfhka_get_totals_for_payload(self):
        self.ensure_one()
        inv = self._tfhka_get_line_aggregates()
        doc_cur = self._tfhka_get_document_currency()
        comp_cur = self.company_id.currency_id
        inv_buckets = self._tfhka_reconcile_buckets_to_targets(
            dict(inv["buckets"]), inv["subtotal"], inv["total_iva"], doc_cur
        )
        inv_gravado, inv_exento = self._tfhka_gravado_exento_from_buckets(
            inv_buckets, doc_cur, subtotal_target=inv["subtotal"]
        )
        inv = {
            **inv,
            "buckets": inv_buckets,
            "gravado": inv_gravado,
            "exento": inv_exento,
            "monto_total_con_iva": doc_cur.round(inv["subtotal"] + inv["total_iva"]),
            "total_apagar": doc_cur.round(inv["subtotal"] + inv["total_iva"]),
        }
        if doc_cur == comp_cur:
            comp = dict(inv)
        else:
            comp = self._tfhka_convert_inv_totals_to_company(inv)
            comp_buckets = self._tfhka_reconcile_buckets_to_targets(
                dict(comp["buckets"]), comp["subtotal"], comp["total_iva"], comp_cur
            )
            comp_gravado, comp_exento = self._tfhka_gravado_exento_from_buckets(
                comp_buckets, comp_cur, subtotal_target=comp["subtotal"]
            )
            comp = {
                **comp,
                "buckets": comp_buckets,
                "gravado": comp_gravado,
                "exento": comp_exento,
                "monto_total_con_iva": comp_cur.round(
                    comp["subtotal"] + comp["total_iva"]
                ),
                "total_apagar": comp_cur.round(comp["subtotal"] + comp["total_iva"]),
            }
        return {
            "inv": inv,
            "comp": comp,
            "total_descuento": inv["total_descuento"],
            "subtotal_antes_descuento": inv["subtotal_antes_descuento"],
            "nro_items": inv["nro_items"],
        }

    def _tfhka_build_identificacion_documento(self):
        self.ensure_one()
        issue_date = self._tfhka_get_issue_date()
        document_number = self._tfhka_get_document_number_for_emission()
        return {
            "tipoDocumento": DISPATCH_GUIDE_DOCUMENT_TYPE,
            "numeroDocumento": document_number,
            "tipoTransaccion": DISPATCH_GUIDE_DOCUMENT_TYPE,
            "numeroPlanillaImportacion": "",
            "numeroExpedienteImportacion": "",
            "serieFacturaAfectada": "",
            "numeroFacturaAfectada": "",
            "fechaFacturaAfectada": "",
            "montoFacturaAfectada": "",
            "comentarioFacturaAfectada": "",
            "regimenEspTributacion": "",
            "fechaEmision": issue_date,
            "fechaVencimiento": issue_date,
            "horaEmision": self._tfhka_get_issue_hour(),
            "anulado": False,
            "tipoDePago": "Inmediato",
            "serie": self._tfhka_get_serie() or "",
            "sucursal": self._tfhka_get_sucursal() or "",
            "tipoDeVenta": "Interna",
            "moneda": self._tfhka_get_currency_code(),
            "transaccionId": document_number,
            "urlPdf": "",
        }

    def _tfhka_build_comprador(self):
        self.ensure_one()
        buyer = self._l10n_ve_edi_get_buyer_partner()
        buyer_prefix, buyer_number = self._l10n_ve_edi_get_buyer_identification()
        phone = buyer.mobile or buyer.phone or ""
        email_list = [buyer.email] if buyer.email else []
        phone_list = [phone] if phone else []
        if email_list and not phone_list:
            raise UserError(
                _(
                    "La API TFHKA exige telefono en comprador cuando hay correo. "
                    "Indique telefono o movil del contacto."
                )
            )
        return {
            "tipoIdentificacion": buyer_prefix,
            "numeroIdentificacion": buyer_number,
            "razonSocial": (buyer.name or "")[:100],
            "direccion": (
                buyer.street or self._l10n_ve_dispatch_address_inline(buyer) or "N/A"
            )[:255],
            "pais": (buyer.country_id.code or "VE")[:2],
            "telefono": phone_list or None,
            "notificar": "Si" if (buyer.email or phone) else "No",
            "correo": email_list or None,
        }

    def _tfhka_build_vendedor(self):
        self.ensure_one()
        seller = self.l10n_ve_sales_user_id or self.user_id
        seller_name = seller.name if seller else ""
        normalized = re.sub(r"[^0-9A-Za-z ]", "", seller_name or "").strip()
        if not normalized:
            return None
        return {"nombre": normalized[:255], "codigo": "", "numCajero": ""}

    def _tfhka_build_invoice_factura_guia_row(self, invoice):
        journal = invoice.journal_id
        serie = ""
        if journal and "l10n_ve_edi_tfhka_serie" in journal._fields:
            serie = journal.l10n_ve_edi_tfhka_serie or ""
        if hasattr(invoice, "_tfhka_get_document_number"):
            numero = invoice._tfhka_get_document_number()
        else:
            numero = re.sub(
                r"\D", "", invoice.l10n_ve_invoice_number or invoice.name or ""
            )
        numero = (numero or "").strip()
        if not numero:
            return None
        return {
            "tipoDocumento": "01",
            "serie": re.sub(r"[^0-9A-Za-z]", "", serie)[:20],
            "numeroDocumento": numero[:19],
        }

    def _tfhka_build_factura_guia(self, invoices=None):
        self.ensure_one()
        rows = []
        if invoices is None:
            invoices = self.invoice_ids.filtered(
                lambda move: move.state == "posted"
                and move.move_type == "out_invoice"
                and move.l10n_ve_edi_send_state == "sent"
                and move.journal_id.l10n_ve_edi_provider == "tfhka"
            )
        else:
            invoices = invoices.filtered(
                lambda move: move.state == "posted"
                and move.move_type == "out_invoice"
                and move.journal_id.l10n_ve_edi_provider == "tfhka"
            )
        seen = set()
        for invoice in invoices[:5]:
            row = self._tfhka_build_invoice_factura_guia_row(invoice)
            if not row:
                continue
            key = (row["tipoDocumento"], row["numeroDocumento"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
        return rows or None

    def _tfhka_urls_from_response_dict(self, data):
        if not isinstance(data, dict):
            return False, False
        pdf_url = False
        doc_url = False
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

    def _tfhka_format_guide_response_json(self, previous_raw, new_response):
        if new_response is None:
            return previous_raw or False
        new_text = json.dumps(new_response, ensure_ascii=False, indent=2)
        if not previous_raw:
            return new_text
        code = self.env["l10n_ve_edi_tfhka.api.service"]._normalize_api_code(
            new_response
        )
        if code != 201:
            return new_text
        try:
            old_data = json.loads(previous_raw)
        except (json.JSONDecodeError, TypeError):
            return new_text
        old_pdf, old_doc = self._tfhka_urls_from_response_dict(old_data)
        new_pdf, new_doc = self._tfhka_urls_from_response_dict(new_response)
        if (old_doc or old_pdf) and not (new_doc or new_pdf):
            return previous_raw
        return new_text

    def _tfhka_persist_guide_payload_with_factura_guia(self, payload):
        self.ensure_one()
        attachment = self._l10n_ve_edi_create_payload_attachment(payload)
        self.write({"l10n_ve_edi_payload_attachment_id": attachment.id})

    def _tfhka_merge_factura_guia_into_payload(self, payload, invoice):
        rows = self._tfhka_build_factura_guia(invoices=invoice)
        if not rows:
            return payload
        encabezado = payload.setdefault("documentoElectronico", {}).setdefault(
            "encabezado", {}
        )
        existing = list(encabezado.get("facturaGuia") or [])
        existing_keys = {
            (row.get("tipoDocumento"), row.get("numeroDocumento"))
            for row in existing
            if isinstance(row, dict)
        }
        for row in rows:
            key = (row.get("tipoDocumento"), row.get("numeroDocumento"))
            if key not in existing_keys:
                existing.append(row)
                existing_keys.add(key)
        encabezado["facturaGuia"] = existing
        return payload

    def _tfhka_payload_factura_guia_has_invoice(self, payload, invoice):
        if not isinstance(payload, dict) or not invoice:
            return False
        rows = (
            payload.get("documentoElectronico", {})
            .get("encabezado", {})
            .get("facturaGuia")
            or []
        )
        if not hasattr(invoice, "_tfhka_get_document_number"):
            return False
        invoice_num = invoice._tfhka_get_document_number()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (
                row.get("tipoDocumento") == "01"
                and row.get("numeroDocumento") == invoice_num
            ):
                return True
        return False

    def _tfhka_stored_payload_has_invoice_link(self, invoice):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id
        if not attachment or not attachment.datas:
            return False
        try:
            payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
        except (json.JSONDecodeError, TypeError, ValueError, binascii.Error):
            return False
        return self._tfhka_payload_factura_guia_has_invoice(payload, invoice)

    def _l10n_ve_edi_tfhka_resend_with_invoice_links(self, invoice):
        self.ensure_one()
        if (
            self.state != "done"
            or self.l10n_ve_edi_send_state != "sent"
            or self._l10n_ve_edi_get_dispatch_edi_provider() != "tfhka"
            or not invoice
        ):
            return False
        factura_guia = self._tfhka_build_factura_guia(invoices=invoice)
        if not factura_guia:
            return False
        if self._tfhka_stored_payload_has_invoice_link(invoice):
            return True
        payload = self._tfhka_build_dispatch_documento_electronico_payload()
        payload = self._tfhka_merge_factura_guia_into_payload(payload, invoice)
        if not self._tfhka_payload_factura_guia_has_invoice(payload, invoice):
            return False
        payload["reenvio"] = True
        previous_response_json = self.l10n_ve_edi_response_json
        dispatch = self._l10n_ve_edi_dispatch_payload(payload)
        if dispatch.get("success"):
            self._tfhka_persist_guide_payload_with_factura_guia(payload)
            response = dispatch.get("response")
            response_json = self._tfhka_format_guide_response_json(
                previous_response_json, response
            )
            if response_json:
                self.write({"l10n_ve_edi_response_json": response_json})
            self.message_post(
                body=_(
                    "Guia de despacho actualizada en TFHKA con la factura %(invoice)s."
                )
                % {"invoice": invoice.display_name}
            )
            return True
        error = dispatch.get("error") or _("No se pudo actualizar la guia en TFHKA.")
        self.message_post(
            body=_(
                "No se pudo vincular la factura %(invoice)s en la guia TFHKA. "
                "Motivo: %(error)s"
            )
            % {"invoice": invoice.display_name, "error": error}
        )
        return False

    def _tfhka_build_totales(self, payload=None):
        self.ensure_one()
        if payload is None:
            payload = self._tfhka_get_totals_for_payload()
        bs = payload["comp"]
        comp_cur = self.company_id.currency_id
        doc_cur = self._tfhka_get_document_currency()
        td_inv = payload["total_descuento"]
        sa_inv = payload["subtotal_antes_descuento"]
        if doc_cur == comp_cur:
            td_bs, sa_bs = td_inv, sa_inv
        else:
            date = self._tfhka_get_conversion_date()
            td_bs = comp_cur.round(
                doc_cur._convert(td_inv, comp_cur, self.company_id, date)
            )
            sa_bs = comp_cur.round(
                doc_cur._convert(sa_inv, comp_cur, self.company_id, date)
            )
        return {
            "nroItems": str(payload["nro_items"] or 0),
            "montoGravadoTotal": self._l10n_ve_edi_format_decimal(bs["gravado"]),
            "montoExentoTotal": self._l10n_ve_edi_format_decimal(bs["exento"]),
            "montoPercibidoTotal": None,
            "subtotalAntesDescuento": self._l10n_ve_edi_format_decimal(sa_bs),
            "totalDescuento": self._l10n_ve_edi_format_decimal(td_bs),
            "totalRecargos": None,
            "subtotal": self._l10n_ve_edi_format_decimal(bs["subtotal"]),
            "totalIVA": self._l10n_ve_edi_format_decimal(bs["total_iva"]),
            "montoTotalConIVA": self._l10n_ve_edi_format_decimal(
                bs["monto_total_con_iva"]
            ),
            "totalAPagar": self._l10n_ve_edi_format_decimal(bs["total_apagar"]),
            "montoEnLetras": "n/a",
            "listaRecargo": None,
            "listaDescBonificacion": None,
            "impuestosSubtotal": self._tfhka_build_impuestos_subtotal_from_buckets(
                bs["buckets"]
            ),
            "otrosImpuestosSubtotal": None,
            "formasPago": None,
            "totalIGTF": None,
            "totalIGTF_VES": None,
            "montoTotalOTI": None,
            "montoTotalIVAyOTI": None,
        }

    def _tfhka_build_totales_otra_moneda(self, payload=None):
        self.ensure_one()
        doc_cur = self._tfhka_get_document_currency()
        comp_cur = self.company_id.currency_id
        if doc_cur == comp_cur:
            return None
        rate = self._tfhka_get_inverse_rate()
        if not rate:
            raise UserError(
                _(
                    "Para guias en moneda extranjera debe existir tasa de "
                    "cambio a bolivares "
                    "en el pedido de venta o en la moneda de la empresa."
                )
            )
        if payload is None:
            payload = self._tfhka_get_totals_for_payload()
        inv = payload["inv"]
        return {
            "moneda": self._tfhka_get_currency_code(),
            "tipoCambio": self._tfhka_format_tipo_cambio(rate),
            "montoGravadoTotal": self._l10n_ve_edi_format_decimal(inv["gravado"]),
            "montoExentoTotal": self._l10n_ve_edi_format_decimal(inv["exento"]),
            "montoPercibidoTotal": None,
            "subtotalAntesDescuento": self._l10n_ve_edi_format_decimal(
                payload["subtotal_antes_descuento"]
            ),
            "totalDescuento": self._l10n_ve_edi_format_decimal(
                payload["total_descuento"]
            ),
            "totalRecargos": None,
            "subtotal": self._l10n_ve_edi_format_decimal(inv["subtotal"]),
            "totalIVA": self._l10n_ve_edi_format_decimal(inv["total_iva"]),
            "montoTotalConIVA": self._l10n_ve_edi_format_decimal(
                inv["monto_total_con_iva"]
            ),
            "totalAPagar": self._l10n_ve_edi_format_decimal(inv["total_apagar"]),
            "montoEnLetras": None,
            "listaRecargo": None,
            "listaDescBonificacion": None,
            "impuestosSubtotal": self._tfhka_build_impuestos_subtotal_from_buckets(
                inv["buckets"]
            ),
            "otrosImpuestosSubtotal": None,
            "totalIGTF": None,
            "totalIGTF_VES": None,
            "montoTotalOTI": None,
            "montoTotalIVAyOTI": None,
        }

    def _tfhka_build_item_detail(self, index, move):
        self.ensure_one()
        product = move.product_id
        cur = self._tfhka_get_document_currency()
        date = self._tfhka_get_conversion_date()
        pricing = move._l10n_ve_dispatch_line_pricing_values()
        line_cur = pricing["currency"]
        qty = move.quantity if move.state == "done" else move.product_uom_qty
        pu = cur.round(
            line_cur._convert(pricing["price_unit"], cur, self.company_id, date)
        )
        subtotal = cur.round(
            line_cur._convert(pricing["subtotal"], cur, self.company_id, date)
        )
        total_included = cur.round(
            line_cur._convert(pricing["total_included"], cur, self.company_id, date)
        )
        line_iva = cur.round(total_included - subtotal)
        taxes = pricing["taxes"]
        tax_rate = self._tfhka_get_line_tax_rate(taxes)
        tax_code = self._tfhka_get_line_tax_code_for_rate(tax_rate)
        plu = (product.barcode or product.default_code or "")[:60] if product else ""
        brutto = cur.round(pu * qty)
        return {
            "numeroLinea": str(index),
            "codigoCIIU": "",
            "codigoPLU": plu,
            "indicadorBienoServicio": "2"
            if product and product.type == "service"
            else "1",
            "descripcion": (product.display_name or move.name or "")[:500],
            "cantidad": self._l10n_ve_edi_format_decimal(qty),
            "unidadMedida": (move.product_uom.name or "UND")[:3],
            "precioUnitario": self._l10n_ve_edi_format_decimal(pu),
            "precioUnitarioDescuento": None,
            "montoBonificacion": None,
            "descripcionBonificacion": None,
            "descuentoMonto": self._l10n_ve_edi_format_decimal(
                cur.round(brutto - subtotal)
            ),
            "recargoMonto": self._l10n_ve_edi_format_decimal(0.0),
            "precioItem": self._l10n_ve_edi_format_decimal(subtotal),
            "precioAntesDescuento": self._l10n_ve_edi_format_decimal(brutto),
            "codigoImpuesto": tax_code,
            "tasaIVA": self._tfhka_format_tasa_iva(tax_rate),
            "valorIVA": self._l10n_ve_edi_format_decimal(line_iva),
            "valorTotalItem": self._l10n_ve_edi_format_decimal(total_included),
            "infoAdicionalItem": [],
            "listaItemOTI": None,
        }

    def _tfhka_build_detalles_items(self):
        self.ensure_one()
        details = []
        moves = self._tfhka_get_dispatch_moves()
        if not moves:
            raise UserError(_("No hay lineas de producto para la guia de despacho."))
        for index, move in enumerate(moves, start=1):
            details.append(self._tfhka_build_item_detail(index, move))
        return details

    def _tfhka_build_guia_despacho(self):
        self.ensure_one()
        origin = self._l10n_ve_dispatch_origin_partner()
        dest = self._l10n_ve_dispatch_delivery_address_partner()
        transport = self.l10n_ve_transport_partner_id
        vehicle = self.l10n_ve_fleet_vehicle_id
        reason = self.l10n_ve_internal_transfer_reason_id
        motivo = reason.name if reason else "Entrega de mercancia"
        total_weight = sum(
            (move.quantity or 0.0) * (move.product_id.weight or 0.0)
            for move in self._tfhka_get_dispatch_moves()
        )
        data = {
            "esGuiaDespacho": "1",
            "motivoTraslado": motivo[:255],
            "descripcionServicio": (self.origin or self.sale_id.name or "")[:255],
            "tipoProducto": "",
            "origenProducto": self._l10n_ve_dispatch_address_inline(origin)[:255],
            "pesoOVolumenTotal": f"{total_weight:.2f}" if total_weight else "",
            "destinoProducto": self._l10n_ve_dispatch_address_inline(dest)[:255],
        }
        if transport:
            prefix, number = self._l10n_ve_edi_parse_ve_vat(transport.vat)
            data["transportista"] = {
                "razonSocial": (transport.name or "")[:255],
                "numeroIdentificacion": number or "",
                "domicilioFiscal": self._l10n_ve_dispatch_address_inline(transport)[
                    :255
                ],
            }
        if vehicle:
            data["vehiculo"] = {
                "tipoVehiculo": self._l10n_ve_dispatch_fleet_vehicle_model_name()[:100],
                "numeroTransporte": (vehicle.name or "")[:50],
                "numeroPlaca": (vehicle.license_plate or "")[:20],
            }
        return data

    def _tfhka_build_transporte(self):
        self.ensure_one()
        origin = self._l10n_ve_dispatch_origin_partner()
        dest = self._l10n_ve_dispatch_delivery_address_partner()
        vehicle = self.l10n_ve_fleet_vehicle_id
        issue_date = self._tfhka_get_issue_date()
        carrier = getattr(self, "carrier_id", False)
        return {
            "tipo": "Terrestre",
            "descripcion": ((carrier.name if carrier else "") or "")[:255],
            "codigo": "",
            "origen": self._l10n_ve_dispatch_address_inline(origin)[:255],
            "destino": self._l10n_ve_dispatch_address_inline(dest)[:255],
            "fechaEntrada": issue_date,
            "fechaSalida": issue_date,
            "lugarEntrega": self._l10n_ve_dispatch_address_inline(dest)[:255],
            "lugarRecepcion": self._l10n_ve_dispatch_address_inline(origin)[:255],
            "placa": (vehicle.license_plate if vehicle else "")[:20],
        }

    def _tfhka_build_dispatch_documento_electronico_payload(self):
        self.ensure_one()
        totals_payload = self._tfhka_get_totals_for_payload()
        encabezado = {
            "identificacionDocumento": self._tfhka_build_identificacion_documento(),
            "comprador": self._tfhka_build_comprador(),
            "totales": self._tfhka_build_totales(totals_payload),
        }
        totales_otra = self._tfhka_build_totales_otra_moneda(totals_payload)
        if totales_otra:
            encabezado["totalesOtraMoneda"] = totales_otra
        vendedor = self._tfhka_build_vendedor()
        if vendedor:
            encabezado["vendedor"] = vendedor
        factura_guia = self._tfhka_build_factura_guia()
        if factura_guia:
            encabezado["facturaGuia"] = factura_guia
        payload = {
            "documentoElectronico": {
                "encabezado": encabezado,
                "detallesItems": self._tfhka_build_detalles_items(),
                "guiaDespacho": self._tfhka_build_guia_despacho(),
                "transporte": self._tfhka_build_transporte(),
                "infoAdicional": [],
                "esLote": False,
                "esMinimo": False,
            }
        }
        _logger.info(
            "TFHKA dispatch guide payload picking_id=%s json=%s",
            self.id,
            json.dumps(payload, ensure_ascii=False)[:4000],
        )
        return payload

    def _tfhka_get_descarga_archivo_payload(self):
        self.ensure_one()
        return {
            "serie": self._tfhka_get_serie() or "",
            "tipoDocumento": DISPATCH_GUIDE_DOCUMENT_TYPE,
            "numeroDocumento": self._tfhka_get_document_number_for_emission(),
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

    def _tfhka_get_dispatch_pdf_bytes_via_descarga_archivo(self):
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
            _logger.exception("TFHKA DescargaArchivo picking_id=%s", self.id)
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
        safe_name = (self.name or f"picking_{self.id}").replace("/", "_")
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
        pdf_bytes, err = self._tfhka_get_dispatch_pdf_bytes_via_descarga_archivo()
        if not pdf_bytes:
            _logger.warning(
                "TFHKA: PDF oficial no disponible (DescargaArchivo) "
                "picking_id=%s err=%s",
                self.id,
                err,
            )
            return False
        self._tfhka_return_pdf_attachment_download_action(pdf_bytes)
        return True

    def _l10n_ve_edi_dispatch_guide_sent_document_available(self):
        self.ensure_one()
        return self._l10n_ve_edi_tfhka_dispatch_guide_was_sent_to_tfhka()

    def action_l10n_ve_edi_download_sent_document(self):
        self.ensure_one()
        if not self._l10n_ve_edi_dispatch_guide_sent_document_available():
            return super().action_l10n_ve_edi_download_sent_document()
        return self.action_l10n_ve_edi_tfhka_print_dispatch_guide()

    def action_l10n_ve_edi_open_sent_document_url(self):
        self.ensure_one()
        if not self._l10n_ve_edi_dispatch_guide_sent_document_available():
            return super().action_l10n_ve_edi_open_sent_document_url()
        return self.action_l10n_ve_edi_tfhka_open_sent_document_url()

    def l10n_ve_edi_tfhka_get_public_document_url(self):
        self.ensure_one()
        if not self._l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf():
            return False
        url = self.l10n_ve_edi_tfhka_sent_document_url
        if not url:
            _pdf_url, url = self._tfhka_extract_public_urls_from_stored_response()
        return url or False

    def action_l10n_ve_edi_tfhka_open_sent_document_url(self):
        self.ensure_one()
        doc_url = self.l10n_ve_edi_tfhka_get_public_document_url()
        if not doc_url:
            raise UserError(
                _(
                    "No hay URL de consulta de la guia en la respuesta "
                    "guardada de TFHKA. "
                    "Use Descargar documento digital o revise el JSON de respuesta."
                )
            )
        return {"type": "ir.actions.act_url", "url": doc_url, "target": "new"}

    def _l10n_ve_edi_tfhka_ensure_dispatch_pdf_report(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_tfhka_pdf_attachment_id
        if attachment and attachment.datas:
            return True
        return self._l10n_ve_edi_tfhka_try_attach_official_pdf()

    def action_l10n_ve_edi_tfhka_print_dispatch_guide(self):
        self.ensure_one()
        if not self._l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf():
            raise UserError(
                _("Solo puede imprimir la guia digital cuando fue enviada a TFHKA.")
            )
        pdf_bytes, api_err = self._tfhka_get_dispatch_pdf_bytes_via_descarga_archivo()
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
            _unused_pdf, pdf_url = (
                self._tfhka_extract_public_urls_from_stored_response()
            )
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
        num = response.get("numeroControl") or response.get("numero_control")
        return str(num).strip() if num else ""

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        if provider == "tfhka":
            return self._tfhka_build_dispatch_documento_electronico_payload()
        return super()._l10n_ve_edi_build_payload_for_provider(provider)

    def _tfhka_resend_response_matches_picking(self, response):
        self.ensure_one()
        if not isinstance(response, dict):
            return False
        control = self._tfhka_extract_numero_control(response)
        if not control or not self.l10n_ve_control_number:
            return False
        return control.strip() == self.l10n_ve_control_number.strip()

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        if self._l10n_ve_edi_get_dispatch_edi_provider() != "tfhka":
            return super()._l10n_ve_edi_dispatch_payload(payload)
        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            return {"success": False, "error": _("Credenciales TFHKA no configuradas.")}
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        is_resend = bool(payload.get("reenvio"))
        try:
            auth = client.authenticate(username, password)
            token = auth.get("token")
            if not token:
                return {
                    "success": False,
                    "error": _("La API TFHKA no devolvio token JWT."),
                }
            extra_codes = {201} if is_resend else None
            response = client.issue_document(
                payload, token, extra_success_codes=extra_codes
            )
            if is_resend and client._normalize_api_code(response) == 201:
                if not self._tfhka_resend_response_matches_picking(response):
                    return {
                        "success": False,
                        "error": _(
                            "TFHKA rechazo el reenvio de la guia: el "
                            "documento duplicado "
                            "no coincide con el numero de control de este albaran."
                        ),
                    }
            return {"success": True, "response": response}
        except UserError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            _logger.exception("TFHKA dispatch guide send picking_id=%s", self.id)
            return {"success": False, "error": str(exc)}

    def _l10n_ve_edi_on_dispatch_success(self, response):
        super()._l10n_ve_edi_on_dispatch_success(response)
        self.ensure_one()
        if self._l10n_ve_edi_get_dispatch_edi_provider() != "tfhka":
            return
        numero = self._tfhka_extract_numero_control(response)
        if numero:
            self.write({"l10n_ve_control_number": numero})
        self._l10n_ve_edi_tfhka_try_attach_official_pdf()
