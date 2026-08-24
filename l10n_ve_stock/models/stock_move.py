from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    l10n_ve_dispatch_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_l10n_ve_dispatch_line_prices",
    )
    l10n_ve_dispatch_price_unit = fields.Monetary(
        string="Precio unitario (guía)",
        currency_field="l10n_ve_dispatch_currency_id",
        compute="_compute_l10n_ve_dispatch_line_prices",
    )
    l10n_ve_dispatch_subtotal = fields.Monetary(
        string="Total línea (guía, s/ imp.)",
        currency_field="l10n_ve_dispatch_currency_id",
        compute="_compute_l10n_ve_dispatch_line_prices",
    )
    l10n_ve_dispatch_tax_ids = fields.Many2many(
        comodel_name="account.tax",
        compute="_compute_l10n_ve_dispatch_line_prices",
        string="Impuestos (guía)",
    )
    l10n_ve_dispatch_price_total = fields.Monetary(
        string="Total línea c/ imp. (guía)",
        currency_field="l10n_ve_dispatch_currency_id",
        compute="_compute_l10n_ve_dispatch_line_prices",
    )

    def _l10n_ve_dispatch_line_pricing_values(self):
        self.ensure_one()
        company = self.company_id
        product = self.product_id
        empty_tax = self.env["account.tax"]
        if not product:
            return {
                "price_unit": 0.0,
                "currency": company.currency_id,
                "subtotal": 0.0,
                "taxes": empty_tax,
                "total_included": 0.0,
            }
        picking = self.picking_id
        qty = self.quantity if self.state == "done" else self.product_uom_qty
        partner = picking.partner_id if picking else self.env["res.partner"].browse()
        price_unit = 0.0
        price_currency = company.currency_id
        if self.sale_line_id:
            sol = self.sale_line_id
            price_unit = sol.price_unit * (1.0 - (sol.discount or 0.0) / 100.0)
            price_currency = sol.currency_id
            taxes = sol.tax_id
            move_qty_sol_uom = self.product_uom._compute_quantity(
                qty,
                sol.product_uom,
                rounding_method="HALF-UP",
            )
            if sol.product_uom_qty:
                ratio = move_qty_sol_uom / sol.product_uom_qty
            else:
                ratio = 0.0
            subtotal_excl = sol.price_subtotal * ratio
            total_incl = sol.price_total * ratio
            return {
                "price_unit": price_unit,
                "currency": price_currency,
                "subtotal": subtotal_excl,
                "taxes": taxes,
                "total_included": total_incl,
            }
        if picking and picking.l10n_ve_dispatch_pricelist_id:
            pl = picking.l10n_ve_dispatch_pricelist_id
            price_unit = pl._get_product_price(
                product,
                qty,
                uom=self.product_uom,
                date=picking.scheduled_date or fields.Date.context_today(self),
            )
            price_currency = pl.currency_id or company.currency_id
        else:
            price_unit = product.lst_price
            price_currency = company.currency_id
        base_taxes = product.taxes_id._filter_taxes_by_company(company)
        if partner:
            fpos = self.env["account.fiscal.position"]._get_fiscal_position(partner)
            if fpos:
                base_taxes = fpos.map_tax(base_taxes)
        taxes = base_taxes
        subtotal_excl = price_unit * qty
        total_incl = subtotal_excl
        if taxes:
            res = taxes.compute_all(
                price_unit,
                price_currency,
                qty,
                product=product,
                partner=partner,
                is_refund=False,
            )
            subtotal_excl = res["total_excluded"]
            total_incl = res["total_included"]
        return {
            "price_unit": price_unit,
            "currency": price_currency,
            "subtotal": subtotal_excl,
            "taxes": taxes,
            "total_included": total_incl,
        }

    @api.depends(
        "product_id",
        "product_id.lst_price",
        "product_id.taxes_id",
        "product_uom",
        "product_uom_qty",
        "quantity",
        "state",
        "sale_line_id",
        "sale_line_id.price_unit",
        "sale_line_id.discount",
        "sale_line_id.currency_id",
        "sale_line_id.tax_id",
        "sale_line_id.price_subtotal",
        "sale_line_id.price_total",
        "sale_line_id.product_uom_qty",
        "sale_line_id.product_uom",
        "picking_id",
        "picking_id.picking_type_id",
        "picking_id.partner_id",
        "picking_id.company_id",
        "picking_id.company_id.account_fiscal_country_id",
        "picking_id.l10n_ve_dispatch_pricelist_id",
        "picking_id.scheduled_date",
    )
    def _compute_l10n_ve_dispatch_line_prices(self):
        for move in self:
            move.l10n_ve_dispatch_currency_id = move.company_id.currency_id
            move.l10n_ve_dispatch_price_unit = 0.0
            move.l10n_ve_dispatch_subtotal = 0.0
            move.l10n_ve_dispatch_tax_ids = self.env["account.tax"]
            move.l10n_ve_dispatch_price_total = 0.0
            picking = move.picking_id
            if not picking or picking.picking_type_id.code != "outgoing":
                continue
            if (
                not picking.company_id.account_fiscal_country_id
                or picking.company_id.account_fiscal_country_id.code != "VE"
            ):
                continue
            if not move.product_id:
                continue
            vals = move._l10n_ve_dispatch_line_pricing_values()
            move.l10n_ve_dispatch_currency_id = vals["currency"]
            move.l10n_ve_dispatch_price_unit = vals["price_unit"]
            move.l10n_ve_dispatch_subtotal = vals["subtotal"]
            move.l10n_ve_dispatch_tax_ids = vals["taxes"]
            move.l10n_ve_dispatch_price_total = vals["total_included"]
