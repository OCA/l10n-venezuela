from collections import OrderedDict

from odoo import _, fields, models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _l10n_ve_is_original_invoice_report(self, report):
        """True solo para el PDF fiscal oficial (botón Imprimir / is_invoice_report)."""
        if report.model != "account.move":
            return False
        report_name = report.report_name or ""
        if report_name == "l10n_ve_seniat.report_invoice_document":
            return True
        return bool(getattr(report, "is_invoice_report", False))

    def _l10n_ve_is_ve_blockable_invoice_report(self, report_ref):
        report = self._get_report(report_ref)
        return self._l10n_ve_is_original_invoice_report(report)

    def _l10n_ve_should_apply_book_paperformat(self, report_ref, res_ids):
        if not res_ids or not self._l10n_ve_is_ve_blockable_invoice_report(report_ref):
            return False
        moves = self.env["account.move"].browse(res_ids)
        return bool(moves) and all(
            move.country_code == "VE"
            and move.move_type in ("out_invoice", "out_refund")
            and move.l10n_ve_journal_emission_medium
            for move in moves
        )

    def get_paperformat(self):
        paperformat_id = self.env.context.get("l10n_ve_book_paperformat_id")
        if paperformat_id:
            return self.env["report.paperformat"].browse(paperformat_id)
        return super().get_paperformat()

    def _l10n_ve_validate_invoice_report(self, res_ids, data=None):
        """Valida permisos de impresión PDF de facturas venezolanas.

        Notes
        -----
        Art. 28 PA SNAT/2011/0071: validaciones mínimas.
        Art. 7 y Art. 21 PA SNAT/2024/000102: emisión digital y control de ejemplares.
        """

        data = data or {}
        if not res_ids:
            return
        moves = self.env["account.move"].browse(res_ids)
        moves._l10n_ve_check_invoice_print_allowed()
        for move in moves:
            if move._l10n_ve_block_invoice_pdf_contingency():
                raise UserError(
                    _(
                        "En contingencia no esta permitido imprimir ni descargar el PDF "
                        "de la factura (ni en borrador ni confirmada)."
                    )
                )
        if data.get("proforma"):
            return
        for move in moves:
            if move._l10n_ve_blocking_invoice_report_before_digital_sent():
                raise UserError(
                    _(
                        "No puede imprimir ni descargar la factura hasta que el envio a la "
                        "imprenta digital finalice correctamente (estado EDI: enviado)."
                    )
                )

    def _l10n_ve_check_block_invoice_pdf_before_digital_sent(self, report_ref, res_ids, data):
        data = data or {}
        if not res_ids:
            return
        if not self._l10n_ve_is_ve_blockable_invoice_report(report_ref):
            return
        self._l10n_ve_validate_invoice_report(res_ids, data)

    def get_valid_action_reports(self, model, record_ids):
        valid_ids = super().get_valid_action_reports(model, record_ids)
        if model != "account.move" or not valid_ids:
            return valid_ids
        moves = self.env["account.move"].browse(record_ids)
        blocked_moves = moves.filtered(
            lambda move: move.country_code == "VE"
            and move.move_type in ("out_invoice", "out_refund")
            and not move._l10n_ve_show_download_pdf_action()
        )
        if not blocked_moves:
            return valid_ids
        blocked_report_ids = {
            report.id
            for report in self
            if report.id in valid_ids
            and self._l10n_ve_is_ve_blockable_invoice_report(report)
        }
        if not blocked_report_ids:
            return valid_ids
        return [report_id for report_id in valid_ids if report_id not in blocked_report_ids]

    def report_action(self, docids, data=None, config=True):
        if self.model == "account.move" and self._l10n_ve_is_original_invoice_report(
            self
        ):
            if isinstance(docids, models.Model):
                res_ids = docids.ids
            elif isinstance(docids, int):
                res_ids = [docids]
            elif isinstance(docids, list):
                res_ids = docids
            else:
                res_ids = []
            self._l10n_ve_validate_invoice_report(res_ids, data)
        return super().report_action(docids, data=data, config=config)

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        return super()._pre_render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        if not self._l10n_ve_should_apply_book_paperformat(report_ref, res_ids):
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )

        moves = self.env["account.move"].browse(res_ids)
        paperformat_by_move = {
            move.id: move._l10n_ve_get_invoice_paperformat().id
            for move in moves
        }
        paperformat_ids = {
            paperformat_id
            for paperformat_id in paperformat_by_move.values()
            if paperformat_id
        }
        if not paperformat_ids:
            return super()._render_qweb_pdf_prepare_streams(
                report_ref, data, res_ids=res_ids
            )

        if len(paperformat_ids) == 1 and len(paperformat_ids) == len(paperformat_by_move):
            return super(
                IrActionsReport,
                self.with_context(
                    l10n_ve_book_paperformat_id=next(iter(paperformat_ids))
                ),
            )._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        collected_streams = OrderedDict()
        for res_id in res_ids:
            paperformat_id = paperformat_by_move.get(res_id)
            ctx = (
                {"l10n_ve_book_paperformat_id": paperformat_id}
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

    def _l10n_ve_mark_ve_invoice_printed(self, moves):
        to_mark = moves.filtered(lambda move: not move.l10n_ve_invoice_original_printed)
        for move in to_mark:
            write_vals = {"l10n_ve_invoice_original_printed": True}
            if (
                move.l10n_ve_journal_emission_medium == "fiscal_machine"
                and not move.l10n_ve_invoice_date
            ):
                write_vals["l10n_ve_invoice_date"] = fields.Datetime.now()
            move.sudo().write(write_vals)

    def _l10n_ve_attach_first_free_form_print_pdf(self, report_ref, res_ids, data=None):
        data = data or {}
        if data.get("proforma"):
            return
        moves = self.env["account.move"].browse(res_ids).filtered(
            lambda move: move._l10n_ve_should_attach_first_free_form_print_pdf()
        )
        if not moves:
            return
        self._l10n_ve_mark_ve_invoice_printed(moves)
        moves.invalidate_recordset(["l10n_ve_invoice_original_printed"])
        for move in moves:
            faithful_pdf, _report_type = super(IrActionsReport, self)._render_qweb_pdf(
                report_ref, res_ids=[move.id], data=data
            )
            move._l10n_ve_attach_invoice_pdf_report(faithful_pdf)

    def _l10n_ve_mark_ve_invoice_printed_after_render(self, res_ids):
        if not self.env.context.get("l10n_ve_invoice"):
            return
        moves = (
            self.env["account.move"]
            .browse(res_ids or [])
            .filtered(
                lambda m: m._l10n_ve_applies_fiscal_print_rules()
                and m.state == "posted"
            )
        )
        self._l10n_ve_mark_ve_invoice_printed(moves)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        data = data or {}
        pdf, report_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
        if self.env.context.get("l10n_ve_invoice") and res_ids:
            self._l10n_ve_attach_first_free_form_print_pdf(
                report_ref, res_ids, data=data
            )
        self._l10n_ve_mark_ve_invoice_printed_after_render(res_ids)
        return pdf, report_type
