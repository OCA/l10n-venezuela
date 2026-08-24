from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_fiscal_machine_id = fields.Many2one(
        comodel_name="l10n.ve.fiscal.machine",
        string="Máquina fiscal",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Máquina fiscal TFHKA asociada a este diario de ventas.",
    )
    l10n_ve_show_fiscal_payment_method = fields.Boolean(
        compute="_compute_l10n_ve_show_fiscal_payment_method",
    )

    @api.depends("company_id", "company_id.account_fiscal_country_id.code")
    def _compute_l10n_ve_show_fiscal_payment_method(self):
        FiscalMachine = self.env["l10n.ve.fiscal.machine"].sudo()
        companies = self.mapped("company_id")
        companies_with_machine = set(
            FiscalMachine.search(
                [("company_id", "in", companies.ids), ("active", "=", True)]
            )
            .mapped("company_id")
            .ids
        )
        for journal in self:
            journal.l10n_ve_show_fiscal_payment_method = bool(
                journal.company_id
                and journal.company_id.account_fiscal_country_id.code == "VE"
                and journal.company_id.id in companies_with_machine
            )

    @api.onchange("l10n_ve_emission_medium")
    def _onchange_l10n_ve_emission_medium_fiscal_machine(self):
        if self.l10n_ve_emission_medium != "fiscal_machine":
            self.l10n_ve_fiscal_machine_id = False

    def write(self, vals):
        if (
            "l10n_ve_emission_medium" in vals
            and vals["l10n_ve_emission_medium"] != "fiscal_machine"
        ):
            vals["l10n_ve_fiscal_machine_id"] = False
        return super().write(vals)

    @api.constrains(
        "l10n_ve_emission_medium",
        "l10n_ve_fiscal_machine_id",
        "company_id",
    )
    def _check_l10n_ve_fiscal_machine_id(self):
        for journal in self:
            machine = journal.l10n_ve_fiscal_machine_id
            if journal.l10n_ve_emission_medium == "fiscal_machine":
                if not machine:
                    raise ValidationError(
                        _(
                            "Debe seleccionar la máquina fiscal para el diario "
                            "«%(journal)s»."
                        )
                        % {"journal": journal.display_name}
                    )
            elif machine:
                raise ValidationError(
                    _(
                        "La máquina fiscal solo puede asignarse cuando el medio de "
                        "emisión del diario «%(journal)s» es «Máquina fiscal»."
                    )
                    % {"journal": journal.display_name}
                )
            if machine and machine.company_id != journal.company_id:
                raise ValidationError(
                    _(
                        "La máquina fiscal «%(machine)s» pertenece a otra compañía "
                        "que el diario «%(journal)s»."
                    )
                    % {
                        "machine": machine.display_name,
                        "journal": journal.display_name,
                    }
                )
