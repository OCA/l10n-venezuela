# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models


class AccountMove(models.Model):
    _inherit = ["account.move", "l10n.ve.fiscal.event.mixin"]
    _name = "account.move"

    def _l10n_ve_audit_is_fiscal_document(self):
        self.ensure_one()
        return self.country_code == "VE" and self.move_type in (
            "out_invoice",
            "out_refund",
            "in_invoice",
            "in_refund",
        )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves.filtered(
            lambda record: record._l10n_ve_audit_is_fiscal_document()
            and record.state == "draft"
            and not record.invoice_origin
            and record.move_type == "out_invoice"
            and not record.debit_origin_id
        ):
            move._l10n_ve_audit_log_fiscal_event(
                "draft_invoice",
                _("Creación de factura borrador %(document)s")
                % {"document": move.display_name},
            )
        return moves

    def _l10n_ve_audit_log_posted_fiscal_event(self):
        self.ensure_one()
        control = self.l10n_ve_control_number or ""
        if self.move_type == "out_refund":
            origin = self.reversed_entry_id.display_name or ""
            self._l10n_ve_audit_log_fiscal_event(
                "credit_note_posted",
                _("Emisión de nota de crédito %(document)s de la factura %(origin)s")
                % {"document": self.display_name, "origin": origin},
            )
            return
        if self.move_type == "out_invoice" and self.debit_origin_id:
            origin = self.debit_origin_id.display_name or ""
            self._l10n_ve_audit_log_fiscal_event(
                "debit_note_posted",
                _("Emisión de nota de débito %(document)s de la factura %(origin)s")
                % {"document": self.display_name, "origin": origin},
            )
            return
        if self.move_type == "out_invoice":
            description = _("Emisión de factura %(document)s") % {
                "document": self.display_name
            }
            if control:
                description = _(
                    "Emisión de factura %(document)s (N° control: %(control)s)"
                ) % {"document": self.display_name, "control": control}
            self._l10n_ve_audit_log_fiscal_event("invoice_posted", description)
            return
        if self.move_type in ("in_invoice", "in_refund"):
            self._l10n_ve_audit_log_fiscal_event(
                "invoice_posted",
                _("Confirmación de documento de compra %(document)s")
                % {"document": self.display_name},
            )

    def _post(self, soft=True):
        to_log = self.filtered(
            lambda move: move._l10n_ve_audit_is_fiscal_document()
            and move.state != "posted"
        )
        res = super()._post(soft=soft)
        for move in to_log:
            if move.state == "posted":
                move._l10n_ve_audit_log_posted_fiscal_event()
        return res

    def button_cancel(self):
        to_log = self.filtered(lambda move: move._l10n_ve_audit_is_fiscal_document())
        res = super().button_cancel()
        for move in to_log.filtered(lambda record: record.state == "cancel"):
            reason = move.l10n_ve_cancel_reason_id.display_name or ""
            description = _("Anulación del documento fiscal %(document)s") % {
                "document": move.display_name
            }
            if reason:
                description = _(
                    "Anulación del documento fiscal %(document)s (Motivo: %(reason)s)"
                ) % {"document": move.display_name, "reason": reason}
            move._l10n_ve_audit_log_fiscal_event("document_cancelled", description)
        return res

    def _l10n_ve_audit_log_fiscal_print_event(self):
        self.ensure_one()
        fiscal_number = self.l10n_ve_invoice_number or ""
        if self.move_type == "out_refund":
            event_type = "fiscal_print"
            description = _(
                "Impresión fiscal de nota de crédito %(document)s (N° %(number)s)"
            ) % {"document": self.display_name, "number": fiscal_number}
        elif self.debit_origin_id:
            event_type = "fiscal_print"
            description = _(
                "Impresión fiscal de nota de débito %(document)s (N° %(number)s)"
            ) % {"document": self.display_name, "number": fiscal_number}
        else:
            event_type = "fiscal_print"
            description = _(
                "Impresión fiscal de factura %(document)s (N° %(number)s)"
            ) % {"document": self.display_name, "number": fiscal_number}
        self._l10n_ve_audit_log_fiscal_event(event_type, description)

    def print_out_invoice(self, values):
        res = super().print_out_invoice(values)
        for move in self.filtered(
            lambda record: record._l10n_ve_audit_is_fiscal_document()
        ):
            move._l10n_ve_audit_log_fiscal_print_event()
        return res

    def print_out_refund(self, values):
        res = super().print_out_refund(values)
        for move in self.filtered(
            lambda record: record._l10n_ve_audit_is_fiscal_document()
        ):
            move._l10n_ve_audit_log_fiscal_print_event()
        return res

    def print_debit_note(self, values):
        res = super().print_debit_note(values)
        for move in self.filtered(
            lambda record: record._l10n_ve_audit_is_fiscal_document()
        ):
            move._l10n_ve_audit_log_fiscal_print_event()
        return res

    def _l10n_ve_audit_log_edi_dispatch_event(self):
        self.ensure_one()
        control = self.l10n_ve_control_number or ""
        if self.move_type == "out_refund":
            origin = self.reversed_entry_id.display_name or ""
            description = _(
                "Envío digital de nota de crédito %(document)s de la factura %(origin)s"
            ) % {"document": self.display_name, "origin": origin}
        elif self.debit_origin_id:
            origin = self.debit_origin_id.display_name or ""
            description = _(
                "Envío digital de nota de débito %(document)s de la factura %(origin)s"
            ) % {"document": self.display_name, "origin": origin}
        else:
            description = _("Envío digital de factura %(document)s") % {
                "document": self.display_name
            }
        if control:
            description = _("%(description)s (N° control: %(control)s)") % {
                "description": description,
                "control": control,
            }
        self._l10n_ve_audit_log_fiscal_event("edi_dispatch", description)

    def _l10n_ve_edi_on_dispatch_success(self, response):
        res = super()._l10n_ve_edi_on_dispatch_success(response)
        for move in self.filtered(
            lambda record: record._l10n_ve_audit_is_fiscal_document()
        ):
            move._l10n_ve_audit_log_edi_dispatch_event()
        return res
