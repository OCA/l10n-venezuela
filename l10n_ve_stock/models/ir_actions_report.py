from collections import OrderedDict

from odoo import models

_L10N_VE_DISPATCH_GUIDE_REPORT_NAME = "l10n_ve_stock.report_dispatch_guide"
_L10N_VE_DISPATCH_GUIDE_XMLID = "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _l10n_ve_is_dispatch_guide_report(self, report):
        return (report.report_name or "") == _L10N_VE_DISPATCH_GUIDE_REPORT_NAME

    def _l10n_ve_get_dispatch_guide_report(self):
        return self.env.ref(_L10N_VE_DISPATCH_GUIDE_XMLID, raise_if_not_found=False)

    def _l10n_ve_dispatch_guide_available_for_pickings(self, pickings):
        dispatch_report = self._l10n_ve_get_dispatch_guide_report()
        if not dispatch_report:
            return False
        ve_outgoing = pickings.filtered(
            lambda picking: picking._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
        )
        if not ve_outgoing:
            return False
        return all(
            picking._l10n_ve_dispatch_guide_print_available() for picking in ve_outgoing
        )

    def get_valid_action_reports(self, model, record_ids):
        valid_ids = super().get_valid_action_reports(model, record_ids)
        if model != "stock.picking" or not record_ids:
            return valid_ids
        pickings = self.env["stock.picking"].browse(record_ids)
        dispatch_report = self._l10n_ve_get_dispatch_guide_report()
        if not dispatch_report:
            return valid_ids
        available = self._l10n_ve_dispatch_guide_available_for_pickings(pickings)
        if dispatch_report.id in valid_ids and not available:
            return [
                report_id
                for report_id in valid_ids
                if report_id != dispatch_report.id
            ]
        return valid_ids

    def report_action(self, docids, data=None, config=True):
        if self._l10n_ve_is_dispatch_guide_report(self):
            if isinstance(docids, models.Model):
                pickings = docids
            elif isinstance(docids, int):
                pickings = self.env["stock.picking"].browse([docids])
            elif isinstance(docids, list):
                pickings = self.env["stock.picking"].browse(docids)
            else:
                pickings = self.env["stock.picking"]
            if pickings and not self._l10n_ve_dispatch_guide_available_for_pickings(
                pickings
            ):
                return {"type": "ir.actions.act_window_close"}
        return super().report_action(docids, data=data, config=config)

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
