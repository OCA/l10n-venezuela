from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    force_currency_id = fields.Many2one(
        "res.currency",
        "Product Currency",
        default=lambda self: self._default_force_currency_id(),
        help="If empty, the company currency is used.",
    )
    company_currency_id = fields.Many2one(
        string="Company Currency",
        related="company_id.currency_id",
    )

    def _default_force_currency_id(self):
        currency_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ve_product_currency.default_force_currency_id")
        )
        try:
            return self.env["res.currency"].browse(int(currency_id)).exists().id
        except (TypeError, ValueError):
            return False

    @api.depends("force_currency_id", "company_id", "company_id.currency_id")
    def _compute_currency_id(self):
        forced_products = self.filtered("force_currency_id")
        for rec in forced_products:
            rec.currency_id = rec.force_currency_id
        return super(ProductTemplate, self - forced_products)._compute_currency_id()

    @api.depends("force_currency_id", "company_id", "company_id.currency_id")
    def _compute_cost_currency_id(self):
        forced_products = self.filtered("force_currency_id")
        for rec in forced_products:
            rec.cost_currency_id = rec.force_currency_id
        return super(
            ProductTemplate, self - forced_products
        )._compute_cost_currency_id()
