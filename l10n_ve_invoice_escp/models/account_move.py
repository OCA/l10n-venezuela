import base64

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..report.invoice_escp import build_move_escp_bytes


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_escp_is_continuous_eligible(self):
        self.ensure_one()
        return (
            self.company_id.account_fiscal_country_id.code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium == "free"
            and self.journal_id.l10n_ve_free_form_print_medium == "continuous"
        )

    def _l10n_ve_get_free_form_continuous_print_action(self):
        res = super()._l10n_ve_get_free_form_continuous_print_action()
        if res:
            return res
        self.ensure_one()
        if not self._l10n_ve_escp_is_continuous_eligible():
            return False
        return {
            "type": "ir.actions.client",
            "tag": "l10n_ve_invoice_escp_print",
            "name": _("Imprimir factura (ESC/P USB)"),
            "target": "new",
            "context": {"dialog_size": "small"},
            "params": {"move_id": self.id},
        }

    def l10n_ve_invoice_escp_get_payload(self):
        self.ensure_one()
        self.check_access("read")
        if self.state not in ("posted", "cancel"):
            raise UserError(_("Solo documentos confirmados pueden imprimirse por USB."))
        if not self._l10n_ve_escp_is_continuous_eligible():
            raise UserError(
                _(
                    "Este documento no está en un diario con forma "
                    "libre y papel continuo."
                )
            )
        self.env[
            "ir.actions.report"
        ]._l10n_ve_check_block_invoice_pdf_before_digital_sent(
            "account.report_invoice_with_payments",
            self.ids,
            {},
        )
        raw = build_move_escp_bytes(self)
        return {"payload_b64": base64.b64encode(raw).decode("ascii")}

    def l10n_ve_invoice_escp_confirm_printed(self):
        self.ensure_one()
        self.check_access("read")
        if self.state not in ("posted", "cancel"):
            raise UserError(_("Solo documentos confirmados."))
        if not self._l10n_ve_escp_is_continuous_eligible():
            raise UserError(_("Operación no aplicable a este documento."))
        self.env[
            "ir.actions.report"
        ]._l10n_ve_check_block_invoice_pdf_before_digital_sent(
            "account.report_invoice_with_payments",
            self.ids,
            {},
        )
        if not self.l10n_ve_invoice_original_printed:
            write_vals = {"l10n_ve_invoice_original_printed": True}
            if (
                self.l10n_ve_journal_emission_medium == "fiscal_machine"
                and not self.l10n_ve_invoice_date
            ):
                write_vals["l10n_ve_invoice_date"] = fields.Datetime.now()
            self.sudo().write(write_vals)
        return True
