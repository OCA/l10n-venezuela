import base64

from odoo import _, models
from odoo.exceptions import UserError

RETENTION_VOUCHER_REPORT = "l10n_ve_withholding.retention_voucher_template"
DISPATCH_GUIDE_REPORT = "l10n_ve_stock.report_dispatch_guide"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _l10n_ve_is_retention_voucher_report(self, report):
        return (report.report_name or "") == RETENTION_VOUCHER_REPORT

    def _l10n_ve_is_dispatch_guide_report(self, report):
        return (report.report_name or "") == DISPATCH_GUIDE_REPORT

    def _l10n_ve_check_block_dispatch_pdf_before_digital_sent(
        self, report_ref, res_ids, data=None
    ):
        if not res_ids:
            return
        report = self._get_report(report_ref)
        if not self._l10n_ve_is_dispatch_guide_report(report):
            return
        for picking in self.env["stock.picking"].browse(res_ids):
            if picking._l10n_ve_edi_dispatch_guide_blocking_print_before_digital_sent():
                raise UserError(
                    _(
                        "No puede imprimir la guia hasta que el envio a "
                        "facturacion digital finalice correctamente "
                        "(estado EDI: enviado)."
                    )
                )

    def _l10n_ve_check_block_retention_pdf_before_digital_sent(
        self, report_ref, res_ids, data=None
    ):
        if not res_ids:
            return
        report = self._get_report(report_ref)
        if not self._l10n_ve_is_retention_voucher_report(report):
            return
        for retention in self.env["account.retention"].browse(res_ids):
            if retention._l10n_ve_edi_retention_blocking_print_before_digital_sent():
                raise UserError(
                    _(
                        "No puede imprimir el comprobante hasta que el envio a "
                        "facturacion digital finalice correctamente "
                        "(estado EDI: enviado)."
                    )
                )

    def get_valid_action_reports(self, model, record_ids):
        valid_ids = super().get_valid_action_reports(model, record_ids)
        if model != "account.retention" or not valid_ids:
            return valid_ids
        retentions = self.env["account.retention"].browse(record_ids)
        if not retentions.filtered(
            lambda retention: (
                retention._l10n_ve_edi_retention_blocking_print_before_digital_sent()
            )
        ):
            return valid_ids
        reports = self.env["ir.actions.report"].browse(valid_ids)
        blocked_report_ids = {
            report.id
            for report in reports
            if self._l10n_ve_is_retention_voucher_report(report)
        }
        if not blocked_report_ids:
            return valid_ids
        return [
            report_id for report_id in valid_ids if report_id not in blocked_report_ids
        ]

    def report_action(self, docids, data=None, config=True):
        if (
            self.model == "account.retention"
            and self._l10n_ve_is_retention_voucher_report(self)
        ):
            if isinstance(docids, models.Model):
                res_ids = docids.ids
            elif isinstance(docids, int):
                res_ids = [docids]
            elif isinstance(docids, list):
                res_ids = docids
            else:
                res_ids = []
            self._l10n_ve_check_block_retention_pdf_before_digital_sent(
                self.id, res_ids, data
            )
        return super().report_action(docids, data=data, config=config)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self._l10n_ve_check_block_invoice_pdf_before_digital_sent(
            report_ref, res_ids, data
        )
        self._l10n_ve_check_block_retention_pdf_before_digital_sent(
            report_ref, res_ids, data
        )
        self._l10n_ve_check_block_dispatch_pdf_before_digital_sent(
            report_ref, res_ids, data
        )
        report = self._get_report(report_ref)
        if report.model == "account.move" and res_ids and len(res_ids) == 1:
            move = self.env["account.move"].browse(res_ids[0])
            if move._l10n_ve_edi_tfhka_replace_invoice_report_with_digital_pdf():
                if not move._l10n_ve_edi_tfhka_ensure_invoice_pdf_report():
                    raise UserError(
                        _(
                            "No hay PDF de facturacion digital para imprimir. "
                            "Verifique credenciales TFHKA en Ajustes y que la "
                            "emision en TFHKA haya generado el documento."
                        )
                    )
                att = move.invoice_pdf_report_id
                if att and att.datas:
                    return base64.b64decode(att.datas), "pdf"
                raise UserError(
                    _("El adjunto PDF de facturacion digital no esta disponible.")
                )
        if report.model == "account.retention" and res_ids and len(res_ids) == 1:
            retention = self.env["account.retention"].browse(res_ids[0])
            if retention._l10n_ve_edi_tfhka_replace_retention_report_with_digital_pdf():
                if not retention._l10n_ve_edi_tfhka_ensure_retention_pdf_report():
                    raise UserError(
                        _(
                            "No hay PDF de facturacion digital para imprimir. "
                            "Verifique credenciales TFHKA en Ajustes y que la "
                            "emision en TFHKA haya generado el comprobante."
                        )
                    )
                attachment = retention.l10n_ve_edi_tfhka_pdf_attachment_id
                if attachment and attachment.datas:
                    return base64.b64decode(attachment.datas), "pdf"
                raise UserError(
                    _("El adjunto PDF de facturacion digital no esta disponible.")
                )
        if report.model == "stock.picking" and res_ids and len(res_ids) == 1:
            picking = self.env["stock.picking"].browse(res_ids[0])
            if picking._l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf():
                if not picking._l10n_ve_edi_tfhka_ensure_dispatch_pdf_report():
                    raise UserError(
                        _(
                            "No hay PDF de facturacion digital para imprimir. "
                            "Verifique credenciales TFHKA en Ajustes y que la "
                            "emision en TFHKA haya generado el documento."
                        )
                    )
                attachment = picking.l10n_ve_edi_tfhka_pdf_attachment_id
                if attachment and attachment.datas:
                    return base64.b64decode(attachment.datas), "pdf"
                raise UserError(
                    _("El adjunto PDF de facturacion digital no esta disponible.")
                )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
