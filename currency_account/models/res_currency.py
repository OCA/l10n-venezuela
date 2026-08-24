from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _currency_group_xmlid_name(self):
        self.ensure_one()
        return f"group_currency_{self.id}"

    def _currency_group_xmlid(self):
        self.ensure_one()
        return f"currency_account.{self._currency_group_xmlid_name()}"

    def _ensure_currency_group(self):
        self.ensure_one()
        imd = self.env["ir.model.data"].sudo()
        existing = imd.search(
            [
                ("module", "=", "currency_account"),
                ("name", "=", self._currency_group_xmlid_name()),
            ],
            limit=1,
        )
        if existing:
            return self.env["res.groups"].browse(existing.res_id)
        category = self.env.ref(
            "currency_account.module_category_currency_account",
            raise_if_not_found=False,
        )
        group = self.env["res.groups"].sudo().create(
            {
                "name": f"Ver multimoneda: {self.display_name}",
                "category_id": category.id if category else False,
            }
        )
        imd.create(
            {
                "module": "currency_account",
                "name": self._currency_group_xmlid_name(),
                "model": "res.groups",
                "res_id": group.id,
                "noupdate": True,
            }
        )
        return group

    @api.model
    def _sync_currency_groups_for_existing_fields(self):
        field_model = self.env["ir.model.fields"].sudo()
        for currency in self.search([]):
            if field_model.search_count(
                [("name", "in", currency._dynamic_currency_field_names())],
                limit=1,
            ):
                currency._ensure_currency_group()

    def _dynamic_currency_field_names(self):
        self.ensure_one()
        return [
            f"x_currency_id_{self.id}",
            f"x_amount_currency_{self.id}",
            f"x_subtotal_currency_{self.id}",
            f"x_price_unit_currency_{self.id}",
            f"x_cost_currency_{self.id}",
        ]

    def _available_product_template_currency_models(self):
        return ["product.model_product_template"]

    def _available_fields_depends_on_product_template(self):
        return ["standard_price", "company_id"]

    def _prepare_product_cost_currency_field(self, model, field_name):
        model_record = self.env.ref(model)
        return {
            "name": field_name,
            "field_description": f"Costo (tasa compra) {self.name}",
            "model_id": model_record.id,
            "ttype": "monetary",
            "store": True,
            "depends": ", ".join(self._available_fields_depends_on_product_template()),
            "compute": f"""for record in self:
    record['{field_name}'] = record._compute_product_cost_currency_field({self.id})
            """,
        }

    def _available_models(self):
        return ["account.model_account_move_line", "account.model_account_move"]

    def _prepare_currency_field(self, model, field_name):
        return {
            "name": field_name,
            "field_description": f"Moneda {self.name}",
            "model_id": self.env.ref(model).id,
            "ttype": "many2one",
            "on_delete": "cascade",
            "relation": "res.currency",
            "store": True,
            "compute": f"""for record in self:
    record['{field_name}'] = {self.id}
            """,
        }

    @api.model
    def _available_fields_depends_on_account_move(self):
        return ["total_currencies", "amount_total", "amount_untaxed"]

    @api.model
    def _available_fields_depends_on(self, model):
        if model == "account.move":
            return self._available_fields_depends_on_account_move()
        if model == "account.move.line":
            return [
                "price_unit",
                "quantity",
                "discount",
                "price_subtotal",
                "price_total",
                "tax_ids",
            ]
        return []

    def _prepare_currency_amount_field(self, model, field_name):
        model_record = self.env.ref(model)
        return {
            "name": field_name,
            "field_description": f"Monto en {self.name}",
            "model_id": model_record.id,
            "ttype": "monetary",
            "store": True,
            "depends": ", ".join(
                self._available_fields_depends_on(model_record.model)
            ),
            "compute": f"""for record in self:
    record['{field_name}'] = record._compute_currency_field({self.id})
            """,
        }

    def _prepare_currency_subtotal_field(self, model, field_name):
        model_record = self.env.ref(model)
        return {
            "name": field_name,
            "field_description": f"Subtotal en {self.name}",
            "model_id": model_record.id,
            "ttype": "monetary",
            "store": True,
            "depends": ", ".join(
                self._available_fields_depends_on(model_record.model)
            ),
            "compute": f"""for record in self:
    record['{field_name}'] = record._compute_subtotal_currency_field({self.id})
            """,
        }

    def _available_line_models(self):
        return ["account.model_account_move_line"]

    def _prepare_price_unit_currency_field(self, model, field_name):
        model_record = self.env.ref(model)
        return {
            "name": field_name,
            "field_description": f"Precio Unit. en {self.name}",
            "model_id": model_record.id,
            "ttype": "monetary",
            "store": True,
            "depends": "price_unit",
            "compute": f"""for record in self:
    record['{field_name}'] = record._compute_price_unit_currency_field({self.id})
            """,
        }

    def _available_report_models(self):
        return ["account.model_account_invoice_report"]

    def _prepare_report_currency_field(self, model, field_name):
        return {
            "name": field_name,
            "field_description": f"Moneda {self.name}",
            "model_id": self.env.ref(model).id,
            "ttype": "many2one",
            "on_delete": "cascade",
            "relation": "res.currency",
            "store": True,
            "readonly": True,
        }

    def _prepare_report_amount_field(self, model, field_name):
        return {
            "name": field_name,
            "field_description": f"Monto en {self.name}",
            "model_id": self.env.ref(model).id,
            "ttype": "monetary",
            "store": True,
            "readonly": True,
        }

    def _prepare_report_subtotal_field(self, model, field_name):
        return {
            "name": field_name,
            "field_description": f"Subtotal en {self.name}",
            "model_id": self.env.ref(model).id,
            "ttype": "monetary",
            "store": True,
            "readonly": True,
        }

    def action_create_fields(self):
        self.ensure_one()
        self._ensure_currency_group()
        field_model = self.env["ir.model.fields"]
        currency_field_name = f"x_currency_id_{self.id}"
        currency_amount_field_name = f"x_amount_currency_{self.id}"
        currency_subtotal_field_name = f"x_subtotal_currency_{self.id}"
        fields_to_delete = self._dynamic_currency_field_names()
        for model in self._available_models():
            field_model.sudo().search(
                [
                    ("name", "in", fields_to_delete),
                    ("model_id", "=", self.env.ref(model).id),
                ]
            ).unlink()

            currency_field_vals = self._prepare_currency_field(
                model, currency_field_name
            )
            currency_amount_field_vals = self._prepare_currency_amount_field(
                model, currency_amount_field_name
            )
            currency_subtotal_field_vals = self._prepare_currency_subtotal_field(
                model, currency_subtotal_field_name
            )
            currency_amount_field_vals["currency_field"] = currency_field_vals["name"]
            currency_subtotal_field_vals["currency_field"] = currency_field_vals["name"]

            self.env["ir.model.fields"].create(currency_field_vals)
            self.env["ir.model.fields"].create(currency_amount_field_vals)
            self.env["ir.model.fields"].create(currency_subtotal_field_vals)

        price_unit_field_name = f"x_price_unit_currency_{self.id}"
        for model in self._available_line_models():
            field_model.sudo().search(
                [
                    ("name", "=", price_unit_field_name),
                    ("model_id", "=", self.env.ref(model).id),
                ]
            ).unlink()

            price_unit_vals = self._prepare_price_unit_currency_field(
                model, price_unit_field_name
            )
            price_unit_vals["currency_field"] = currency_field_name
            self.env["ir.model.fields"].create(price_unit_vals)

        for model in self._available_report_models():
            field_model.sudo().search(
                [
                    ("name", "in", fields_to_delete),
                    ("model_id", "=", self.env.ref(model).id),
                ]
            ).unlink()

            currency_field_vals = self._prepare_report_currency_field(
                model, currency_field_name
            )
            currency_amount_field_vals = self._prepare_report_amount_field(
                model, currency_amount_field_name
            )
            currency_subtotal_field_vals = self._prepare_report_subtotal_field(
                model, currency_subtotal_field_name
            )
            currency_amount_field_vals["currency_field"] = currency_field_vals["name"]
            currency_subtotal_field_vals["currency_field"] = currency_field_vals["name"]

            self.env["ir.model.fields"].create(currency_field_vals)
            self.env["ir.model.fields"].create(currency_amount_field_vals)
            self.env["ir.model.fields"].create(currency_subtotal_field_vals)

        product_cost_field_name = f"x_cost_currency_{self.id}"
        product_field_subset = [
            f"x_currency_id_{self.id}",
            product_cost_field_name,
        ]
        for model in self._available_product_template_currency_models():
            field_model.sudo().search(
                [
                    ("name", "in", product_field_subset),
                    ("model_id", "=", self.env.ref(model).id),
                ]
            ).unlink()

            currency_field_vals = self._prepare_currency_field(
                model, currency_field_name
            )
            cost_field_vals = self._prepare_product_cost_currency_field(
                model, product_cost_field_name
            )
            cost_field_vals["currency_field"] = currency_field_vals["name"]

            self.env["ir.model.fields"].create(currency_field_vals)
            self.env["ir.model.fields"].create(cost_field_vals)

    def action_delete_fields(self):
        self.ensure_one()
        self.env["ir.model.fields"].sudo().with_context(_force_unlink=True).search(
            [("name", "in", self._dynamic_currency_field_names())]
        ).unlink()
