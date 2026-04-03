from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        pdf, report_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )

        if self.env.context.get("l10n_ve_ve_free_form"):
            return pdf, report_type

        report = self._get_report(report_ref)
        if report.report_name != "l10n_ve_seniat.report_invoice_document_ve":
            return pdf, report_type

        moves = (
            self.env["account.move"]
            .browse(res_ids or [])
            .filtered(
                lambda m: m.company_id.account_fiscal_country_id.code == "VE"
                and m.move_type in ("out_invoice", "out_refund")
            )
        )
        to_mark = moves.filtered(lambda m: not m.l10n_ve_ve_invoice_original_printed)
        if to_mark:
            to_mark.sudo().write({"l10n_ve_ve_invoice_original_printed": True})

        return pdf, report_type
