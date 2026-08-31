# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from odoo import fields, models
from odoo.exceptions import UserError

_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "passwd",
    "password",
    "secret",
    "token",
}
_SECRET_TEXT_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|authorization|credential|api[_-]?key)"
    r"\b(\s*[:=]\s*)([^\s,;}\]]+)"
)


def _split_vat(vat):
    """Split a Venezuelan identity number into its type and digits."""
    vat = (vat or "").strip().upper()
    match = re.match(r"^([VEJGPC])-?(\d{1,9})-?(\d)?$", vat)
    if not match:
        return "", re.sub(r"\D", "", vat)
    letter, body, check = match.groups()
    return letter, body + (check or "")


def _sanitize_log_value(value):
    """Redact common credential keys before a value reaches the audit log."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if str(key).lower() in _SECRET_KEYS
            else _sanitize_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitize_log_value(item) for item in value)
    if isinstance(value, str):
        return _SECRET_TEXT_RE.sub(r"\1\2[REDACTED]", value)
    return value


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_edoc_state = fields.Selection(
        selection=[
            ("to_send", "To Send"),
            ("sent", "Sent, Awaiting Control Number"),
            ("assigned", "Control Number Assigned"),
            ("error", "Error"),
            ("cancelled", "Cancelled by Provider"),
        ],
        string="Electronic Document Status",
        copy=False,
        readonly=True,
        tracking=True,
    )
    l10n_ve_edoc_external_id = fields.Char(
        string="Provider Document ID",
        copy=False,
        readonly=True,
    )
    l10n_ve_edoc_error = fields.Text(
        string="Last Provider Error",
        copy=False,
        readonly=True,
    )

    def _l10n_ve_edoc_document_vals(self):
        """Build the provider-neutral representation of this document."""
        self.ensure_one()
        company = self.company_id
        partner = self.commercial_partner_id
        buyer_type, buyer_number = _split_vat(partner.vat)
        lines = []
        for line in self.invoice_line_ids.filtered(
            lambda invoice_line: invoice_line.display_type == "product"
        ):
            rate = next((tax.amount for tax in line.tax_ids if tax.amount), 0.0)
            lines.append(
                {
                    "codigo": line.product_id.default_code or "",
                    "descripcion": line.name or "",
                    "cantidad": line.quantity,
                    "unidad": line.product_uom_id.name or "",
                    "precio_unitario": line.price_unit,
                    "descuento": line.discount,
                    "descuento_monto": self.currency_id.round(
                        line.quantity * line.price_unit * line.discount / 100.0
                    ),
                    "base": line.price_subtotal,
                    "alicuota": rate,
                    "iva": line.price_total - line.price_subtotal,
                    "total": line.price_total,
                    "exento": line._l10n_ve_edoc_is_exempt(),
                }
            )
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        vals = {
            "tipo_documento": self._l10n_ve_edoc_doc_type(),
            "numero": self.name,
            "fecha": self.invoice_date,
            "hora": now.strftime("%H:%M:%S"),
            "moneda": self.currency_id.name,
            "tipo_venta": (
                "credito"
                if self.invoice_date_due
                and self.invoice_date
                and self.invoice_date_due > self.invoice_date
                else "contado"
            ),
            "emisor": {
                "rif": company.vat or "",
                "razon_social": company.name,
                "domicilio": company.street or "",
            },
            "comprador": {
                "rif": partner.vat or "",
                "tipo_identificacion": buyer_type,
                "numero_identificacion": buyer_number,
                "razon_social": partner.name or "",
                "domicilio": partner.street or "",
                "correo": partner.email or "",
                "telefono": partner.phone or "",
            },
            "lineas": lines,
            "nro_items": len(lines),
            "total_exento": sum(line["base"] for line in lines if line["exento"]),
            "total_base": sum(line["base"] for line in lines if not line["exento"]),
            "subtotal": self.amount_untaxed,
            "total_iva": self.amount_tax,
            "total": self.amount_total,
            "formas_pago": self._l10n_ve_edoc_payment_vals(),
        }
        reference_currency = company.currency_id
        if reference_currency != self.currency_id:
            rate_date = self.invoice_date or fields.Date.context_today(self)
            reference_rate = self.env["res.currency"]._get_conversion_rate(
                self.currency_id,
                reference_currency,
                company,
                rate_date,
            )
            vals["tipo_cambio"] = reference_rate
            vals["totales_bs"] = {
                "moneda": reference_currency.name,
                "tipo_cambio": reference_rate,
                "total_exento": reference_currency.round(
                    vals["total_exento"] * reference_rate
                ),
                "total_base": reference_currency.round(
                    vals["total_base"] * reference_rate
                ),
                "total_iva": reference_currency.round(
                    vals["total_iva"] * reference_rate
                ),
                "total": reference_currency.round(vals["total"] * reference_rate),
            }
        origin = False
        if self.move_type == "out_refund" and self.reversed_entry_id:
            origin = self.reversed_entry_id
        elif "debit_origin_id" in self._fields and self.debit_origin_id:
            origin = self.debit_origin_id
        if origin:
            vals["documento_afectado"] = {
                "numero": origin.name,
                "numero_control": origin.l10n_ve_control_number or "",
                "fecha": origin.invoice_date,
                "monto": origin.amount_total,
                "comentario": self.ref or "",
            }
        return vals

    def _l10n_ve_edoc_payment_vals(self):
        """Return reconciled payments in provider-neutral form."""
        self.ensure_one()
        if not hasattr(self, "_get_reconciled_payments"):
            return []
        return [
            {
                "descripcion": payment.payment_method_line_id.name
                or payment.journal_id.name
                or "",
                "fecha": payment.date,
                "monto": payment.amount,
                "moneda": payment.currency_id.name,
            }
            for payment in self._get_reconciled_payments()
        ]

    def _l10n_ve_edoc_doc_type(self):
        self.ensure_one()
        if self.move_type == "out_refund":
            return "nota_credito"
        if "debit_origin_id" in self._fields and self.debit_origin_id:
            return "nota_debito"
        return "factura"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        for move in posted:
            if (
                move.is_sale_document(include_receipts=True)
                and move.l10n_ve_emission_medium == "digital"
                and not move.l10n_ve_edoc_state
                and move.company_id.l10n_ve_edoc_provider
            ):
                move.l10n_ve_edoc_state = "to_send"
        return posted

    def _l10n_ve_edoc_provider(self):
        self.ensure_one()
        provider = self.company_id.l10n_ve_edoc_provider
        if not provider:
            raise UserError(
                self.env._(
                    "Company %(company)s has no electronic document provider "
                    "configured.",
                    company=self.company_id.display_name,
                )
            )
        return self.env[provider]

    def action_l10n_ve_edoc_send(self):
        for move in self:
            if move.l10n_ve_emission_medium != "digital":
                raise UserError(
                    self.env._(
                        "%(document)s was not posted using digital billing.",
                        document=move.display_name,
                    )
                )
            if move.state != "posted":
                raise UserError(self.env._("Only posted documents can be sent."))
            if move.l10n_ve_edoc_state in ("sent", "assigned"):
                raise UserError(
                    self.env._(
                        "%(document)s was already sent to its provider.",
                        document=move.display_name,
                    )
                )
            move._l10n_ve_edoc_do_send()
        return True

    def _l10n_ve_edoc_do_send(self):
        self.ensure_one()
        provider = self._l10n_ve_edoc_provider()
        vals = self._l10n_ve_edoc_document_vals()
        try:
            result = provider._edoc_send(self, vals)
        except Exception as error:  # noqa: BLE001
            self._l10n_ve_edoc_log("send", vals, str(error), ok=False)
            self.write(
                {
                    "l10n_ve_edoc_state": "error",
                    "l10n_ve_edoc_error": str(error),
                }
            )
            return False
        self._l10n_ve_edoc_log("send", vals, result, ok=True)
        self._l10n_ve_edoc_apply(result)
        return True

    def _l10n_ve_edoc_apply(self, result):
        """Apply a provider result and assign fiscal control data safely."""
        self.ensure_one()
        control_number = result.get("control_number")
        if control_number:
            self._l10n_ve_assign_control_data(
                control_number,
                result.get("control_date") or fields.Date.context_today(self),
            )
        self.write(
            {
                "l10n_ve_edoc_external_id": result.get("external_id"),
                "l10n_ve_edoc_error": False,
                "l10n_ve_edoc_state": "assigned" if control_number else "sent",
            }
        )

    def action_l10n_ve_edoc_fetch(self):
        for move in self.filtered(
            lambda document: document.l10n_ve_edoc_state == "sent"
        ):
            provider = move._l10n_ve_edoc_provider()
            try:
                result = provider._edoc_fetch(move)
            except Exception as error:  # noqa: BLE001
                move._l10n_ve_edoc_log("fetch", {}, str(error), ok=False)
                continue
            move._l10n_ve_edoc_log("fetch", {}, result, ok=True)
            if result.get("control_number"):
                move._l10n_ve_edoc_apply(result)
        return True

    def action_l10n_ve_edoc_cancel(self):
        self.ensure_one()
        if self.l10n_ve_edoc_state not in ("sent", "assigned"):
            raise UserError(
                self.env._(
                    "%(document)s has not been issued by its provider.",
                    document=self.display_name,
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Cancel Electronic Document"),
            "res_model": "l10n.ve.edoc.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _l10n_ve_edoc_do_cancel(self, reason):
        self.ensure_one()
        provider = self._l10n_ve_edoc_provider()
        request = {"motivo": reason}
        try:
            result = provider._edoc_cancel(self, reason)
        except Exception as error:  # noqa: BLE001
            self._l10n_ve_edoc_log("cancel", request, str(error), ok=False)
            self.l10n_ve_edoc_error = str(error)
            return False
        self._l10n_ve_edoc_log("cancel", request, result, ok=bool(result))
        if result:
            self.write(
                {
                    "l10n_ve_edoc_state": "cancelled",
                    "l10n_ve_edoc_error": False,
                }
            )
        return bool(result)

    def _l10n_ve_edoc_log(self, endpoint, request, response, ok):
        self.ensure_one()
        self.env["l10n.ve.edoc.log"].sudo().create(
            {
                "move_id": self.id,
                "endpoint": endpoint,
                "request": repr(_sanitize_log_value(request)),
                "response": repr(_sanitize_log_value(response)),
                "ok": ok,
            }
        )

    def _l10n_ve_edoc_cron(self):
        moves = self.search([("l10n_ve_edoc_state", "in", ("to_send", "sent"))])
        for move in moves.filtered(
            lambda document: document.l10n_ve_edoc_state == "to_send"
            and document.company_id.l10n_ve_edoc_provider
        ):
            move._l10n_ve_edoc_do_send()
        moves.filtered(
            lambda document: document.l10n_ve_edoc_state == "sent"
        ).action_l10n_ve_edoc_fetch()
