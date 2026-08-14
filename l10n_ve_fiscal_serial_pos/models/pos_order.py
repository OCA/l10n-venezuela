# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def l10n_ve_fiscal_serial_pos_fiscal_action_payload(self):
        self.ensure_one()
        move = self.account_move
        if not move:
            raise UserError(_("La orden POS no tiene una factura contable asociada."))
        if move.country_code != "VE":
            raise UserError(_("La impresión fiscal POS solo aplica para documentos VE."))
        if move.l10n_ve_journal_emission_medium != "fiscal_machine":
            raise UserError(_("El diario del documento no está configurado como máquina fiscal."))

        fiscal_number = move.l10n_ve_invoice_number or self.l10n_ve_pos_fiscal_invoice_number
        if fiscal_number:
            if move.l10n_ve_invoice_number:
                data = move.check_reprint()
            else:
                move._l10n_ve_fiscal_serial_validate_print_base()
                data = {
                    "type": move.move_type,
                    "reprint_document_type": move._l10n_ve_fiscal_serial_reprint_document_type(),
                    "mf_number": move._l10n_ve_fiscal_serial_normalize_reprint_number(
                        fiscal_number
                    ),
                    "move_id": move.id,
                    "fiscal_machine": move._l10n_ve_fiscal_serial_journal_machine_payload(),
                }
            data["l10n_ve_print_action"] = "reprint"
            return data

        return self.l10n_ve_fiscal_serial_check_print_move()

    def l10n_ve_fiscal_serial_check_print_move(self):
        self.ensure_one()
        move = self.account_move
        if not move:
            raise UserError(_("La orden POS no tiene una factura contable asociada."))
        if move.country_code != "VE":
            raise UserError(_("La impresión fiscal POS solo aplica para documentos VE."))
        if move.l10n_ve_journal_emission_medium != "fiscal_machine":
            raise UserError(_("El diario del documento no está configurado como máquina fiscal."))
        if move.l10n_ve_invoice_number:
            raise UserError(_("El documento ya tiene número fiscal registrado."))

        if move.move_type == "out_invoice":
            data = move.check_print_out_invoice()
            data["l10n_ve_print_action"] = "print_out_invoice"
            return data
        if move.move_type == "out_refund":
            data = move.check_print_out_refund()
            data["l10n_ve_print_action"] = "print_out_refund"
            return data

        raise UserError(
            _("Tipo de documento %(move_type)s no soportado para impresión fiscal desde POS.")
            % {"move_type": move.move_type or ""}
        )

    def l10n_ve_fiscal_serial_register_print_result(self, values):
        self.ensure_one()
        data = values.get("data") if isinstance(values, dict) and values.get("data") else values
        if not isinstance(data, dict):
            raise UserError(_("Respuesta fiscal inválida."))

        order_vals = {}
        if data.get("sequence") is not None:
            order_vals["l10n_ve_pos_fiscal_invoice_number"] = str(data.get("sequence"))
        if data.get("serial_machine"):
            order_vals["l10n_ve_pos_fiscal_serial"] = str(data.get("serial_machine"))
        report_z = data.get("mf_reportz") or data.get("report_z")
        if report_z is not None:
            order_vals["l10n_ve_pos_fiscal_report_z"] = str(report_z)
        if order_vals:
            self.write(order_vals)

        move = self.account_move
        if not move:
            return True

        if move.move_type == "out_invoice":
            return move.print_out_invoice(values)
        if move.move_type == "out_refund":
            return move.print_out_refund(values)

        raise UserError(
            _(
                "Tipo de documento %(move_type)s no soportado para registrar "
                "impresión fiscal desde POS."
            )
            % {"move_type": move.move_type or ""}
        )
