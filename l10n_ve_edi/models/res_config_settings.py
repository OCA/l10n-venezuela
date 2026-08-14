from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_has_digital_billing_emission = fields.Boolean(
        compute="_compute_l10n_ve_has_digital_billing_emission",
    )

    @api.depends("l10n_ve_emission_medium_ids", "l10n_ve_emission_medium_ids.code")
    def _compute_l10n_ve_has_digital_billing_emission(self):
        for settings in self:
            codes = set(settings.l10n_ve_emission_medium_ids.mapped("code"))
            settings.l10n_ve_has_digital_billing_emission = "digital_billing" in codes

    l10n_ve_edi_iva_supplier_retention_provider = fields.Selection(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_provider",
        readonly=False,
    )
    l10n_ve_edi_islr_supplier_retention_provider = fields.Selection(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_provider",
        readonly=False,
    )
