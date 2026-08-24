# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    company_id = fields.Many2one(
        "res.company",
        compute="_compute_company_id",
    )
    l10n_ve_fiscal_country_code = fields.Char(
        related="company_id.account_fiscal_country_id.code",
        string="Fiscal Country Code",
    )

    @api.depends("move_ids", "move_ids.company_id")
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.move_ids[:1].company_id if rec.move_ids else False

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

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        moves = self.env["account.move"]
        if res.get("move_ids"):
            for command in res["move_ids"]:
                if command[0] == 6 and command[2]:
                    moves = self.env["account.move"].browse(command[2])
                    break
        if (
            not moves
            and self.env.context.get("active_model") == "account.move"
            and self.env.context.get("active_ids")
        ):
            moves = self.env["account.move"].browse(self.env.context["active_ids"])
        if not moves:
            return res
        company = moves[0].company_id
        if company.account_fiscal_country_id.code != "VE":
            return res
        if "journal_id" in fields_list and moves[0].journal_id:
            res["journal_id"] = moves[0].journal_id.id
        if "date" in fields_list:
            res["date"] = fields.Date.context_today(self)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            moves = self._l10n_ve_moves_from_create_vals(vals)
            company = None
            if moves:
                company = moves[0].company_id
            if company and company.account_fiscal_country_id.code == "VE":
                if moves[0].journal_id:
                    vals["journal_id"] = moves[0].journal_id.id
                vals["date"] = fields.Date.context_today(self)
            cleaned.append(vals)
        return super().create(cleaned)

    def write(self, vals):
        if self.env.context.get("l10n_ve_skip_debit_note_wizard_lock"):
            return super().write(vals)
        if {"journal_id", "date"} & set(vals):
            for rec in self:
                if rec.company_id.account_fiscal_country_id.code == "VE":
                    raise UserError(
                        _(
                            "No puede modificar el diario ni la fecha de la nota "
                            "de débito para empresas con fiscalidad venezolana."
                        )
                    )
        return super().write(vals)

    def create_debit(self):
        """Crea nota de débito validando reglas fiscales venezolanas.

        Notes
        -----
        Art. 22-24 PA SNAT/2011/0071: ND vinculada a factura origen.
        Art. 8 PA SNAT/2024/000102: ND en medios digitales.
        """

        self.move_ids._l10n_ve_check_debit_note_creation_allowed()
        self.move_ids._l10n_ve_check_credit_debit_allowed()
        return super().create_debit()
