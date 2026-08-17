from collections import OrderedDict

from odoo import models

_L10N_VE_DISPATCH_GUIDE_REPORT_NAME = "l10n_ve_stock.report_dispatch_guide"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def get_paperformat(self):
        paperformat_id = self.env.context.get("l10n_ve_dispatch_guide_paperformat_id")
        if paperformat_id:
            return self.env["report.paperformat"].browse(paperformat_id)
        return super().get_paperformat()

    def _l10n_ve_should_apply_dispatch_guide_paperformat(self, report_ref, res_ids):
        if not res_ids:
            return False
        report = self._get_report(report_ref)
        return report.report_name == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        if not self._l10n_ve_should_apply_dispatch_guide_paperformat(report_ref, res_ids):
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )
        pickings = self.env["stock.picking"].browse(res_ids)
        paperformat_by_picking = {
            picking.id: picking._l10n_ve_dispatch_guide_paperformat().id
            for picking in pickings
        }
        paperformat_ids = set(paperformat_by_picking.values())
        if not paperformat_ids:
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )
        if len(paperformat_ids) == 1 and len(paperformat_by_picking) == len(res_ids):
            return super(
                IrActionsReport,
                self.with_context(
                    l10n_ve_dispatch_guide_paperformat_id=next(iter(paperformat_ids))
                ),
            )._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)
        collected_streams = OrderedDict()
        for res_id in res_ids:
            paperformat_id = paperformat_by_picking.get(res_id)
            ctx = (
                {"l10n_ve_dispatch_guide_paperformat_id": paperformat_id}
                if paperformat_id
                else {}
            )
            sub_streams = super(
                IrActionsReport, self.with_context(**ctx)
            )._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=[res_id]
            )
            collected_streams[res_id] = sub_streams[res_id]
        return collected_streams

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME:
            pickings = self.env["stock.picking"].browse(res_ids or [])
            pickings.l10n_ve_dispatch_guide_report_check()
        pdf, rep_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
        if report.report_name == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME:
            pickings = self.env["stock.picking"].browse(res_ids or [])
            to_mark = pickings.filtered(
                lambda p: p.company_id.account_fiscal_country_id.code == "VE"
                and not p.l10n_ve_dispatch_guide_original_printed
            )
            if to_mark:
                to_mark.sudo().write({"l10n_ve_dispatch_guide_original_printed": True})
        return pdf, rep_type
