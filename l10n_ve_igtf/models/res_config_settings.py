from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_igtf_settings_eligible = fields.Boolean(
        compute="_compute_l10n_ve_igtf_settings_eligible",
        string="Show IGTF settings (Venezuela, special taxpayer)",
    )

    l10n_ve_igtf_account_id = fields.Many2one(
        related="company_id.l10n_ve_igtf_account_id",
        readonly=False,
        domain=(
            "[('account_type', 'in', "
            "('liability_current', 'liability_non_current'))]"
        ),
    )
    l10n_ve_igtf_percent = fields.Float(
        related="company_id.l10n_ve_igtf_percent",
        readonly=False,
    )

    l10n_ve_igtf_currency_ids = fields.Many2many(
        related="company_id.l10n_ve_igtf_currency_ids",
        readonly=False,
    )
    l10n_ve_igtf_allow_invoice_accrual = fields.Boolean(
        related="company_id.l10n_ve_igtf_allow_invoice_accrual",
        readonly=False,
    )

    l10n_ve_is_ve_country = fields.Boolean(
        compute="_compute_l10n_ve_is_ve_country",
        store=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super(
            ResConfigSettings,
            self.with_context(l10n_ve_skip_igtf_account_check=True),
        ).create(vals_list)

    def write(self, vals):
        return super(
            ResConfigSettings,
            self.with_context(l10n_ve_skip_igtf_account_check=True),
        ).write(vals)

    @api.depends(
        "company_id.account_fiscal_country_id",
        "company_id.taxpayer_type",
        "taxpayer_type",
    )
    def _compute_l10n_ve_igtf_settings_eligible(self):
        for record in self:
            company = record.company_id
            taxpayer_type = record.taxpayer_type or company.taxpayer_type
            record.l10n_ve_igtf_settings_eligible = (
                bool(company.account_fiscal_country_id)
                and company.account_fiscal_country_id.code == "VE"
                and taxpayer_type == "special"
            )

    def _l10n_ve_validate_igtf_account_for_special(self):
        for settings in self:
            if not settings.l10n_ve_igtf_settings_eligible:
                continue
            if not settings.l10n_ve_igtf_account_id:
                raise ValidationError(
                    _(
                        "La cuenta de IGTF es obligatoria para compañías "
                        "con tipo de contribuyente Especial."
                    )
                )

    def execute(self):
        self.ensure_one()
        res = super(
            ResConfigSettings,
            self.with_context(l10n_ve_skip_igtf_account_check=True),
        ).execute()
        self.company_id.invalidate_recordset(
            ["l10n_ve_igtf_account_id", "taxpayer_type", "partner_id"]
        )
        self.invalidate_recordset(["l10n_ve_igtf_settings_eligible"])
        self._l10n_ve_validate_igtf_account_for_special()
        return res

    @api.depends("company_id.account_fiscal_country_id")
    def _compute_l10n_ve_is_ve_country(self):
        for record in self:
            record.l10n_ve_is_ve_country = (
                record.company_id.account_fiscal_country_id
                and record.company_id.account_fiscal_country_id.code == "VE"
            )
