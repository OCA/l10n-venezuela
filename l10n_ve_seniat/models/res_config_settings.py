from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .l10n_ve_dispatch_guide_email import _EMAIL_RE


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
    l10n_ve_has_dispatch_guide_emission = fields.Boolean(
        compute="_compute_l10n_ve_has_dispatch_guide_emission",
    )

    @api.depends("l10n_ve_emission_medium_ids", "l10n_ve_emission_medium_ids.code")
    def _compute_l10n_ve_has_dispatch_guide_emission(self):
        for settings in self:
            codes = set(settings.l10n_ve_emission_medium_ids.mapped("code"))
            settings.l10n_ve_has_dispatch_guide_emission = bool(
                codes & {"free_form", "digital_billing", "fiscal_machine"}
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
    l10n_ve_enforce_sale_price_ge_cost = fields.Boolean(
        related="company_id.l10n_ve_enforce_sale_price_ge_cost",
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

    l10n_ve_unfactured_dispatch_email_recipient = fields.Char(
        related="company_id.l10n_ve_unfactured_dispatch_email_recipient",
        readonly=False,
    )
    l10n_ve_unfactured_dispatch_email_interval_number = fields.Integer(
        related="company_id.l10n_ve_unfactured_dispatch_email_interval_number",
        readonly=False,
    )
    l10n_ve_unfactured_dispatch_email_interval_type = fields.Selection(
        related="company_id.l10n_ve_unfactured_dispatch_email_interval_type",
        readonly=False,
    )
    l10n_ve_unfactured_dispatch_email_schedule_enabled = fields.Boolean(
        related="company_id.l10n_ve_unfactured_dispatch_email_schedule_enabled",
        readonly=False,
    )
    l10n_ve_unfactured_dispatch_email_last_sent = fields.Datetime(
        related="company_id.l10n_ve_unfactured_dispatch_email_last_sent",
        readonly=True,
    )

    l10n_ve_implementer_name = fields.Char(
        string="Razón social del implementador",
        config_parameter="l10n_ve_seniat.implementer_name",
    )
    l10n_ve_implementer_vat = fields.Char(
        string="RIF del implementador",
        config_parameter="l10n_ve_seniat.implementer_vat",
    )
    l10n_ve_implementer_email = fields.Char(
        string="Correo del implementador",
        config_parameter="l10n_ve_seniat.implementer_email",
    )

    @api.constrains("l10n_ve_implementer_email")
    def _check_l10n_ve_implementer_email(self):
        for settings in self:
            email = (settings.l10n_ve_implementer_email or "").strip()
            if email and not _EMAIL_RE.match(email):
                raise ValidationError(
                    _("El correo del implementador “%(email)s” no tiene un formato válido.")
                    % {"email": email}
                )

    def set_values(self):
        res = super().set_values()
        self.env["res.company"]._l10n_ve_sync_unfactured_dispatch_cron()
        return res
