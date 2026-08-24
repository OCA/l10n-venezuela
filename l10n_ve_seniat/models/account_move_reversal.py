# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_ve_fiscal_country_code = fields.Char(
        related="company_id.account_fiscal_country_id.code",
        string="Fiscal Country Code",
    )

    @api.model
    def _l10n_ve_moves_from_create_vals(self, vals):
        if not vals.get("move_ids"):
            return self.env["account.move"]
        ids = []
        for command in vals["move_ids"]:
            if command[0] == 6:
                ids.extend(command[2])
            elif command[0] == 4:
                ids.append(command[1])
        return self.env["account.move"].browse(ids) if ids else self.env["account.move"]

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            moves = self._l10n_ve_moves_from_create_vals(vals)
            if (
                not moves
                and self.env.context.get("active_model") == "account.move"
                and self.env.context.get("active_ids")
            ):
                moves = self.env["account.move"].browse(self.env.context["active_ids"])
                vals["move_ids"] = [(6, 0, moves.ids)]
            company = None
            if vals.get("company_id"):
                company = self.env["res.company"].browse(vals["company_id"])
            elif moves:
                company = moves[0].company_id
            if moves and not vals.get("journal_id"):
                journals = moves.journal_id.filtered(lambda j: j.active)
                if journals:
                    vals["journal_id"] = journals[0].id
            if company and company.account_fiscal_country_id.code == "VE":
                vals["date"] = fields.Date.context_today(self)
            cleaned.append(vals)
        return super().create(cleaned)

    def write(self, vals):
        if self.env.context.get("l10n_ve_skip_reversal_wizard_lock"):
            return super().write(vals)
        if {"journal_id", "date"} & set(vals):
            for rec in self:
                if rec.company_id.account_fiscal_country_id.code == "VE":
                    raise UserError(
                        _(
                            "No puede modificar el diario ni la fecha de "
                            "reversión en notas de crédito para empresas con "
                            "fiscalidad venezolana."
                        )
                    )
        return super().write(vals)

    def reverse_moves(self, is_modify=False):
        """Reversa asientos aplicando validaciones de NC venezolanas.

        Notes
        -----
        Art. 22-24 PA SNAT/2011/0071: notas de crédito.
        Art. 8 PA SNAT/2024/000102: NC digitales.
        """

        for rec in self:
            if rec.move_type != "entry" and not (rec.reason or "").strip():
                raise UserError(
                    _("Debe indicar el motivo de reversión antes de continuar.")
                )
        self.move_ids._l10n_ve_check_credit_note_creation_allowed()
        self.move_ids._l10n_ve_check_credit_debit_allowed()
        action = super().reverse_moves(is_modify=is_modify)
        self.new_move_ids._l10n_ve_force_refund_to_company_currency()
        return action
