from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    taxpayer_type = fields.Selection(
        related="company_id.taxpayer_type",
        readonly=False,
    )

    l10n_ve_emission_medium_ids = fields.Many2many(
        related="company_id.l10n_ve_emission_medium_ids",
        readonly=False,
    )

    l10n_ve_on_behalf_of_third_party_enabled = fields.Boolean(
        related="company_id.l10n_ve_on_behalf_of_third_party_enabled",
        readonly=False,
    )
    l10n_ve_validate_partner_vat_format = fields.Boolean(
        related="company_id.l10n_ve_validate_partner_vat_format",
        readonly=False,
    )
    l10n_ve_lock_partner_fiscal_data = fields.Boolean(
        related="company_id.l10n_ve_lock_partner_fiscal_data",
        readonly=False,
    )
    l10n_ve_reception_date_payment_term_customer = fields.Boolean(
        related="company_id.l10n_ve_reception_date_payment_term_customer",
        readonly=False,
    )
    l10n_ve_reception_date_payment_term_vendor = fields.Boolean(
        related="company_id.l10n_ve_reception_date_payment_term_vendor",
        readonly=False,
    )

    def action_open_l10n_ve_tax_groups(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Grupos de impuestos"),
            "res_model": "account.tax.group",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("country_id.code", "=", "VE"),
            ],
            "context": {
                "default_company_id": self.company_id.id,
                "default_country_id": self.company_id.account_fiscal_country_id.id,
            },
        }
