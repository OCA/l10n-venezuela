# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, Command, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ve_sale_taxes_readonly = fields.Boolean(
        compute="_compute_l10n_ve_sale_taxes_readonly",
    )
    l10n_ve_sale_tax_id = fields.Many2one(
        "account.tax",
        string="Sales Tax",
        compute="_compute_l10n_ve_tax_ids",
        inverse="_inverse_l10n_ve_sale_tax_id",
        domain=[("type_tax_use", "=", "sale")],
        help="Updates the original sales taxes field with a single tax.",
    )
    l10n_ve_purchase_tax_id = fields.Many2one(
        "account.tax",
        string="Purchase Tax",
        compute="_compute_l10n_ve_tax_ids",
        inverse="_inverse_l10n_ve_purchase_tax_id",
        domain=[("type_tax_use", "=", "purchase")],
        help="Updates the original purchase taxes field with a single tax.",
    )

    @api.depends("product_variant_ids")
    def _compute_l10n_ve_sale_taxes_readonly(self):
        locked = self.env["product.template"]._l10n_ve_locked_sale_tax_template_id_set(
            self
        )
        for tmpl in self:
            tmpl.l10n_ve_sale_taxes_readonly = tmpl.id in locked

    @api.depends("taxes_id", "supplier_taxes_id")
    def _compute_l10n_ve_tax_ids(self):
        for tmpl in self:
            tmpl.l10n_ve_sale_tax_id = tmpl.taxes_id[:1]
            tmpl.l10n_ve_purchase_tax_id = tmpl.supplier_taxes_id[:1]

    def _inverse_l10n_ve_sale_tax_id(self):
        for tmpl in self:
            tmpl.taxes_id = [Command.set(tmpl.l10n_ve_sale_tax_id.ids)]

    def _inverse_l10n_ve_purchase_tax_id(self):
        for tmpl in self:
            tmpl.supplier_taxes_id = [Command.set(tmpl.l10n_ve_purchase_tax_id.ids)]

    @api.model
    def _l10n_ve_locked_sale_tax_template_id_set(self, templates):
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve or not templates:
            return set()
        candidates = templates.filtered(
            lambda t: (t.company_id or self.env.company).account_fiscal_country_id
            == ve
        )
        if not candidates:
            return set()
        variant_ids = candidates.mapped("product_variant_ids").ids
        if not variant_ids:
            return set()
        self.env.cr.execute(
            """
            SELECT DISTINCT pp.product_tmpl_id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN product_product pp ON pp.id = aml.product_id
            WHERE aml.product_id = ANY(%s)
              AND COALESCE(aml.display_type, '') NOT IN ('line_section', 'line_note')
              AND am.state = 'posted'
              AND am.move_type IN ('out_invoice', 'out_refund')
            """,
            (variant_ids,),
        )
        invoiced = {row[0] for row in self.env.cr.fetchall()}
        return invoiced & set(candidates.ids)

    def _l10n_ve_user_can_override_sale_tax_lock(self):
        return self.env.user.has_group(
            "l10n_ve_seniat.group_l10n_ve_override_locked_master_data"
        )

    @api.model
    def _l10n_ve_sync_tax_utility_vals(self, vals):
        vals = dict(vals)
        if "l10n_ve_sale_tax_id" in vals:
            tax_id = vals.pop("l10n_ve_sale_tax_id")
            vals["taxes_id"] = [Command.set([tax_id])] if tax_id else [Command.clear()]
        if "l10n_ve_purchase_tax_id" in vals:
            tax_id = vals.pop("l10n_ve_purchase_tax_id")
            vals["supplier_taxes_id"] = (
                [Command.set([tax_id])] if tax_id else [Command.clear()]
            )
        return vals

    def write(self, vals):
        vals = self._l10n_ve_sync_tax_utility_vals(vals)
        if (
            "taxes_id" in vals
            and not self._l10n_ve_user_can_override_sale_tax_lock()
        ):
            locked = self.env["product.template"]._l10n_ve_locked_sale_tax_template_id_set(
                self
            )
            if set(self.ids) & locked:
                raise ValidationError(
                    _(
                        "No puede modificar el impuesto de ventas de un producto que "
                        "ya figura en facturas de cliente o notas de crédito "
                        "confirmadas."
                    )
                )
        vals = dict(vals)
        if "list_price" in vals:
            ve_country = self.env.ref("base.ve", raise_if_not_found=False)
            if ve_country:
                ve_templates = self.filtered(
                    lambda t: (t.company_id or self.env.company).account_fiscal_country_id
                    == ve_country
                )
                if ve_templates:
                    self._l10n_ve_normalize_list_price_in_vals(vals, templates=ve_templates)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._l10n_ve_sync_tax_utility_vals(vals) for vals in vals_list]
        for vals in vals_list:
            self._l10n_ve_normalize_list_price_in_vals(vals)
            self._l10n_ve_inject_default_exent_taxes_in_vals(vals)
        return super().create(vals_list)

    def _force_default_sale_tax(self, companies):
        return super(
            ProductTemplate,
            self.with_context(l10n_ve_skip_product_tax_constraint=True),
        )._force_default_sale_tax(companies)

    def _force_default_purchase_tax(self, companies):
        return super(
            ProductTemplate,
            self.with_context(l10n_ve_skip_product_tax_constraint=True),
        )._force_default_purchase_tax(companies)

    @api.model
    def _l10n_ve_vals_get_company(self, vals):
        if "company_id" not in vals or vals["company_id"] is False:
            return self.env.company
        cid = vals["company_id"]
        if isinstance(cid, int):
            return self.env["res.company"].browse(cid)
        if isinstance(cid, models.Model):
            return cid
        if isinstance(cid, (list, tuple)) and len(cid) >= 2:
            if cid[0] == 4:
                return self.env["res.company"].browse(cid[1])
            if cid[0] == 1 and len(cid) >= 2:
                return self.env["res.company"].browse(cid[1])
        return self.env.company

    @api.model
    def _l10n_ve_m2m_commands_have_tax_ids(self, field_name, vals):
        if field_name not in vals:
            return False
        cmds = vals[field_name]
        if not cmds:
            return False
        for c in cmds:
            if c[0] == 6 and c[2]:
                return True
            if c[0] == 4:
                return True
            if c[0] == 3:
                return True
            if c[0] == 0:
                return True
        return False

    @api.model
    def _l10n_ve_get_exent_sale_tax(self, company):
        tax = self.env["account.tax.group"]._l10n_ve_get_exempt_tax(
            company, "sale"
        )
        if tax:
            return tax
        return self.env["account.tax"].search(
            [
                ("company_id", "parent_of", company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )

    @api.model
    def _l10n_ve_get_exent_purchase_tax(self, company):
        tax = self.env["account.tax.group"]._l10n_ve_get_exempt_tax(
            company, "purchase"
        )
        if tax:
            return tax
        return self.env["account.tax"].search(
            [
                ("company_id", "parent_of", company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )

    @api.model
    def _l10n_ve_normalize_list_price_in_vals(self, vals, templates=None):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")

        if templates is not None:
            costs = [float(c or 0.0) for c in templates.mapped("standard_price")]
            if "standard_price" in vals:
                costs.append(float(vals.get("standard_price") or 0.0))
            cost_max = max(costs) if costs else 0.0
            if "list_price" in vals and float_compare(
                vals["list_price"], 0.0, precision_digits=prec
            ) <= 0:
                vals["list_price"] = max(1.0, cost_max)
            return

        company = self._l10n_ve_vals_get_company(vals)
        if company.account_fiscal_country_id != ve_country:
            return
        cost = float(vals.get("standard_price", 0.0) or 0.0)
        if "list_price" in vals and float_compare(
            vals["list_price"], 0.0, precision_digits=prec
        ) <= 0:
            vals["list_price"] = max(1.0, cost)

    @api.model
    def _l10n_ve_inject_default_exent_taxes_in_vals(self, vals):
        if self.env.context.get("l10n_ve_skip_auto_exent_taxes"):
            return
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve:
            return
        company = self._l10n_ve_vals_get_company(vals)
        if company.account_fiscal_country_id != ve:
            return
        if not self.env["account.tax.group"]._l10n_ve_get_report_tax_groups(company):
            return
        if not self._l10n_ve_m2m_commands_have_tax_ids("taxes_id", vals):
            sale_tax = self._l10n_ve_get_exent_sale_tax(company)
            if sale_tax:
                vals["taxes_id"] = [(6, 0, [sale_tax.id])]
        if not self._l10n_ve_m2m_commands_have_tax_ids("supplier_taxes_id", vals):
            purchase_tax = self._l10n_ve_get_exent_purchase_tax(company)
            if purchase_tax:
                vals["supplier_taxes_id"] = [(6, 0, [purchase_tax.id])]

    def _l10n_ve_check_sale_price_vs_cost(self):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for tmpl in self:
            if tmpl._l10n_ve_is_sale_discount_template():
                continue
            company = tmpl.company_id or self.env.company
            if company.account_fiscal_country_id != ve_country:
                continue
            enforce_ge_cost = company.l10n_ve_enforce_sale_price_ge_cost
            for variant in tmpl.product_variant_ids:
                self._l10n_ve_check_sale_price_values(
                    tmpl.display_name,
                    variant.display_name,
                    variant.lst_price,
                    variant.standard_price,
                    enforce_ge_cost,
                    prec,
                )

    @api.constrains("list_price", "standard_price")
    def _l10n_ve_check_list_price_and_cost(self):
        self._l10n_ve_check_sale_price_vs_cost()

    @api.model
    def _l10n_ve_check_sale_price_values(
        self,
        product_name,
        variant_name,
        sale_price,
        cost,
        enforce_ge_cost,
        precision_digits,
    ):
        if float_compare(sale_price, 0.0, precision_digits=precision_digits) <= 0:
            raise ValidationError(
                _(
                    'El precio de venta del producto "%(name)s" debe ser '
                    "mayor que cero (variante: %(variant)s)."
                )
                % {
                    "name": product_name,
                    "variant": variant_name,
                }
            )
        if enforce_ge_cost and float_compare(
            sale_price, cost, precision_digits=precision_digits
        ) < 0:
            raise ValidationError(
                _(
                    'El precio de venta del producto "%(name)s" no puede ser '
                    "inferior al coste (variante: %(variant)s)."
                )
                % {
                    "name": product_name,
                    "variant": variant_name,
                }
            )

    @api.onchange("list_price", "standard_price", "company_id")
    def _onchange_l10n_ve_check_list_price_and_cost(self):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for tmpl in self:
            if tmpl._l10n_ve_is_sale_discount_template():
                continue
            company = tmpl.company_id or self.env.company
            if company.account_fiscal_country_id != ve_country:
                continue
            tmpl._l10n_ve_check_sale_price_values(
                tmpl.display_name,
                tmpl.display_name,
                tmpl.list_price,
                tmpl.standard_price,
                company.l10n_ve_enforce_sale_price_ge_cost,
                prec,
            )

    def _l10n_ve_companies_for_tax_count(self):
        """Companies whose tax counts must be validated for this product."""
        self.ensure_one()
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return self.env["res.company"]
        if self.company_id:
            if self.company_id.account_fiscal_country_id == ve_country:
                return self.company_id
            return self.env["res.company"]
        companies = (self.taxes_id | self.supplier_taxes_id).company_id
        if self.env.company.account_fiscal_country_id == ve_country:
            companies |= self.env.company
        return companies.filtered(
            lambda company: company.account_fiscal_country_id == ve_country
        )

    def _l10n_ve_taxes_for_company(self, taxes, company):
        return taxes.filtered(lambda tax: tax.company_id == company)

    @api.constrains("taxes_id", "supplier_taxes_id")
    def _l10n_ve_check_exactly_one_tax_per_use(self):
        """Exige exactamente un impuesto de venta y uno de compra por compañía VE.

        Notes
        -----
        Art. 13 num. 9-11 PA SNAT/2011/0071: alícuota aplicable por operación.
        En multi-compañía un producto compartido puede tener un impuesto por
        compañía; el conteo se hace por compañía, no sobre el total.
        """

        if self.env.context.get(
            "install_mode"
        ) or self.env.context.get("l10n_ve_skip_product_tax_constraint"):
            return
        for tmpl in self:
            if tmpl._l10n_ve_is_sale_discount_template():
                continue
            if (
                hasattr(tmpl, "_l10n_ve_is_loyalty_reward_discount_template")
                and tmpl._l10n_ve_is_loyalty_reward_discount_template()
            ):
                continue
            for company in tmpl._l10n_ve_companies_for_tax_count():
                n_sale = len(tmpl._l10n_ve_taxes_for_company(tmpl.taxes_id, company))
                if n_sale != 1:
                    raise ValidationError(
                        _(
                            'El producto "%(name)s" debe tener exactamente un '
                            "impuesto de ventas en la compañía “%(company)s” "
                            "(tiene %(n)d)."
                        )
                        % {
                            "name": tmpl.display_name,
                            "company": company.display_name,
                            "n": n_sale,
                        }
                    )
                n_purchase = len(
                    tmpl._l10n_ve_taxes_for_company(tmpl.supplier_taxes_id, company)
                )
                if n_purchase != 1:
                    raise ValidationError(
                        _(
                            'El producto "%(name)s" debe tener exactamente un '
                            "impuesto de compras en la compañía “%(company)s” "
                            "(tiene %(n)d)."
                        )
                        % {
                            "name": tmpl.display_name,
                            "company": company.display_name,
                            "n": n_purchase,
                        }
                    )

    @api.onchange("l10n_ve_sale_tax_id")
    def _onchange_l10n_ve_sale_tax_id(self):
        for tmpl in self:
            tmpl.taxes_id = [Command.set(tmpl.l10n_ve_sale_tax_id.ids)]

    @api.onchange("l10n_ve_purchase_tax_id")
    def _onchange_l10n_ve_purchase_tax_id(self):
        for tmpl in self:
            tmpl.supplier_taxes_id = [Command.set(tmpl.l10n_ve_purchase_tax_id.ids)]

    @api.onchange("taxes_id", "supplier_taxes_id")
    def _onchange_l10n_ve_check_exactly_one_tax_per_use(self):
        for tmpl in self:
            tmpl.l10n_ve_sale_tax_id = tmpl.taxes_id[:1]
            tmpl.l10n_ve_purchase_tax_id = tmpl.supplier_taxes_id[:1]
        self._l10n_ve_check_exactly_one_tax_per_use()


class ProductProduct(models.Model):
    _inherit = "product.product"

    l10n_ve_sale_taxes_readonly = fields.Boolean(
        related="product_tmpl_id.l10n_ve_sale_taxes_readonly",
    )

    @api.onchange("l10n_ve_sale_tax_id")
    def _onchange_l10n_ve_sale_tax_id(self):
        for product in self:
            product.taxes_id = [Command.set(product.l10n_ve_sale_tax_id.ids)]

    @api.onchange("l10n_ve_purchase_tax_id")
    def _onchange_l10n_ve_purchase_tax_id(self):
        for product in self:
            product.supplier_taxes_id = [
                Command.set(product.l10n_ve_purchase_tax_id.ids)
            ]

    @api.onchange("taxes_id", "supplier_taxes_id")
    def _onchange_l10n_ve_check_exactly_one_tax_per_use(self):
        for product in self:
            product.l10n_ve_sale_tax_id = product.taxes_id[:1]
            product.l10n_ve_purchase_tax_id = product.supplier_taxes_id[:1]
        self.mapped("product_tmpl_id")._l10n_ve_check_exactly_one_tax_per_use()

    def _l10n_ve_check_product_price_onchange(self, price_field):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")
        Template = self.env["product.template"]
        for product in self:
            template = product.product_tmpl_id
            if template and template._l10n_ve_is_sale_discount_template():
                continue
            company = template.company_id or product.company_id or self.env.company
            if company.account_fiscal_country_id != ve_country:
                continue
            Template._l10n_ve_check_sale_price_values(
                template.display_name or product.display_name,
                product.display_name,
                product[price_field],
                product.standard_price,
                company.l10n_ve_enforce_sale_price_ge_cost,
                prec,
            )

    @api.onchange("list_price", "standard_price", "company_id")
    def _onchange_l10n_ve_check_list_price_and_cost(self):
        self._l10n_ve_check_product_price_onchange("list_price")

    @api.onchange("lst_price")
    def _onchange_l10n_ve_check_lst_price_and_cost(self):
        self._l10n_ve_check_product_price_onchange("lst_price")

    @api.model_create_multi
    def create(self, vals_list):
        Template = self.env["product.template"]
        vals_list = [
            Template._l10n_ve_sync_tax_utility_vals(vals) for vals in vals_list
        ]
        for vals in vals_list:
            Template._l10n_ve_normalize_list_price_in_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = self.env["product.template"]._l10n_ve_sync_tax_utility_vals(vals)
        if "list_price" in vals:
            ve_country = self.env.ref("base.ve", raise_if_not_found=False)
            if ve_country:
                ve_products = self.filtered(
                    lambda p: (
                        p.product_tmpl_id.company_id or self.env.company
                    ).account_fiscal_country_id
                    == ve_country
                )
                if ve_products:
                    self.env["product.template"]._l10n_ve_normalize_list_price_in_vals(
                        vals, templates=ve_products.product_tmpl_id
                    )
        return super().write(vals)
