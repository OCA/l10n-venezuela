from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL


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
                    _("No se puede tener Forma libre y Máquina Fiscal al mismo tiempo.")
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
    l10n_ve_reception_date_payment_term_customer = fields.Boolean(
        string="Use reception date on customer invoices",
        help=(
            "When enabled, payment terms and installment due dates on customer "
            "invoices start from the reception date."
        ),
        default=False,
    )
    l10n_ve_reception_date_payment_term_vendor = fields.Boolean(
        string="Use reception date on vendor bills",
        help=(
            "When enabled, payment terms and installment due dates on vendor "
            "bills start from the reception date."
        ),
        default=False,
    )

    def init(self):
        result = super().init()
        self._l10n_ve_ensure_sql_defaults()
        return result

    @api.model
    def _l10n_ve_ensure_sql_defaults(self):
        cr = self.env.cr
        targets = (
            ("res_company", "res.company"),
            ("product_template", "product.template"),
            ("product_product", "product.product"),
        )
        fallbacks = {
            "boolean": "false",
            "integer": "0",
            "bigint": "0",
            "smallint": "0",
            "numeric": "0",
            "double precision": "0",
            "real": "0",
            "character varying": "''",
            "character": "''",
            "text": "''",
            "date": "'2026-01-01'",
            "timestamp without time zone": "'2026-01-01'",
            "timestamp with time zone": "'2026-01-01'",
        }
        for table_name, model_name in targets:
            cr.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND is_nullable = 'NO'
                  AND column_default IS NULL
                  AND column_name <> 'id'
                """,
                (table_name,),
            )
            model_fields = (
                self.env[model_name]._fields if model_name in self.env else {}
            )
            for column_name, data_type in cr.fetchall():
                sql_default = fallbacks.get(data_type)
                field = model_fields.get(column_name)
                if field is not None:
                    default = field.default
                    if callable(default):
                        default = None
                    if default is not None and default is not False:
                        if field.type == "boolean":
                            sql_default = "true" if default else "false"
                        elif field.type in ("char", "text", "selection", "html"):
                            escaped = str(default).replace("'", "''")
                            sql_default = f"'{escaped}'"
                        elif field.type in ("integer", "float", "monetary"):
                            sql_default = str(default)
                        elif field.type == "many2one":
                            sql_default = str(int(getattr(default, "id", default)))
                if not sql_default:
                    continue
                cr.execute(
                    SQL(
                        "ALTER TABLE %s ALTER COLUMN %s SET DEFAULT %s",
                        SQL.identifier(table_name),
                        SQL.identifier(column_name),
                        SQL(sql_default),
                    )
                )
