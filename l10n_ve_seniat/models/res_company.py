from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    def _l10n_ve_invoice_tag_include_igtf_notice(self):
        """Indica si la factura debe mostrar aviso de IGTF.

        Returns
        -------
        bool

        Notes
        -----
        Providencia SNAT/2022/000013: IGTF 3% en operaciones en divisas.
        """

        self.ensure_one()
        return bool(self.taxpayer_type and self.taxpayer_type != "ordinary")

    def _l10n_ve_emission_medium_codes(self):
        """Return emission medium codes configured on the company settings."""
        self.ensure_one()
        return tuple(self.l10n_ve_emission_medium_ids.mapped("code"))

    def _l10n_ve_has_emission_medium(self, code):
        """Return True if the company uses the given emission medium code."""
        self.ensure_one()
        return code in self._l10n_ve_emission_medium_codes()

    taxpayer_type = fields.Selection(
        related="partner_id.taxpayer_type",
        readonly=False,
    )
    l10n_ve_emission_medium_ids = fields.Many2many(
        comodel_name="l10n.ve.emission.medium",
        relation="res_company_l10n_ve_emission_medium_rel",
        column1="company_id",
        column2="emission_medium_id",
        string="Medios de emisión",
        help="Medios de emisión de facturas y otros documentos utilizados por la "
        "empresa: forma libre, máquina fiscal y/o facturación digital. "
        "Forma libre no puede combinarse con máquina fiscal ni con "
        "facturación digital.",
    )
    l10n_ve_has_free_form = fields.Boolean(
        string="Tiene forma libre",
        compute="_compute_l10n_ve_emission_medium_flags",
    )
    l10n_ve_has_fiscal_machine = fields.Boolean(
        string="Tiene máquina fiscal",
        compute="_compute_l10n_ve_emission_medium_flags",
    )
    l10n_ve_has_digital_billing = fields.Boolean(
        string="Tiene facturación digital",
        compute="_compute_l10n_ve_emission_medium_flags",
    )

    @api.depends("l10n_ve_emission_medium_ids", "l10n_ve_emission_medium_ids.code")
    def _compute_l10n_ve_emission_medium_flags(self):
        for company in self:
            codes = set(company._l10n_ve_emission_medium_codes())
            company.l10n_ve_has_free_form = "free_form" in codes
            company.l10n_ve_has_fiscal_machine = "fiscal_machine" in codes
            company.l10n_ve_has_digital_billing = "digital_billing" in codes

    @api.constrains("l10n_ve_emission_medium_ids")
    def _check_l10n_ve_emission_medium_ids(self):
        for company in self:
            codes = set(company.l10n_ve_emission_medium_ids.mapped("code"))
            if "free_form" not in codes:
                continue
            if "fiscal_machine" in codes:
                raise ValidationError(
                    _(
                        "No se puede tener Forma libre y Máquina Fiscal "
                        "al mismo tiempo."
                    )
                )
            if "digital_billing" in codes:
                raise ValidationError(
                    _(
                        "No se puede tener Forma libre y Facturación Digital "
                        "al mismo tiempo."
                    )
                )

    l10n_ve_on_behalf_of_third_party_enabled = fields.Boolean(
        string="Facturación por cuenta de terceros habilitada",
        default=False,
    )
    l10n_ve_validate_partner_vat_format = fields.Boolean(
        string="Validar formato de RIF/CI",
        default=True,
    )
    l10n_ve_lock_partner_fiscal_data = fields.Boolean(
        string="Bloquear datos fiscales con movimientos",
        default=True,
    )
    l10n_ve_enforce_sale_price_ge_cost = fields.Boolean(
        string="Exigir precio de venta mayor o igual al coste",
        default=False,
    )
