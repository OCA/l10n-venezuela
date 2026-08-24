from odoo import _, api, exceptions, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if "currency_id" not in fields_list:
            fields_list.append("currency_id")
        return fields_list

    def get_product_info_pos(self, price, quantity, pos_config_id, pricelist_id=None):
        """Return financial info with amounts expressed in the POS currency.

        The POS UI formats every amount with ``formatCurrency`` (POS currency), but
        standard Odoo keeps pricelist/supplier/optional amounts in their own
        currency. The unit ``price`` coming from the browser can also still be in
        the product currency when conversion was skipped client-side.
        """
        self.ensure_one()
        config = self.env["pos.config"].browse(pos_config_id)
        pos_currency = config.currency_id
        company = config.company_id
        date = fields.Date.context_today(self)

        pricelist = self.env["product.pricelist"].browse(pricelist_id or False).exists()
        if not pricelist:
            pricelist = config.pricelist_id
        if pricelist:
            price = pricelist._get_product_price(
                self,
                quantity,
                currency=pos_currency,
            )

        result = super().get_product_info_pos(price, quantity, pos_config_id)

        available_pricelists = (
            config.available_pricelist_ids if config.use_pricelist else config.pricelist_id
        )
        pricelists = {pricelist_rec.id: pricelist_rec for pricelist_rec in available_pricelists}
        for pricelist_data in result.get("pricelists", []):
            pricelist_rec = pricelists.get(pricelist_data["id"])
            if not pricelist_rec:
                continue
            price_pos = pricelist_rec._get_product_price(
                self,
                quantity,
                currency=pos_currency,
            )
            price_pl = pricelist_rec._get_product_price(
                self,
                quantity,
                currency=pricelist_rec.currency_id,
            )
            pricelist_data["price"] = price_pos
            pricelist_data["price_pos_currency"] = price_pos
            pricelist_data["price_pricelist_currency"] = price_pl
            pricelist_data["currency_id"] = pos_currency.id
            pricelist_data["pricelist_currency_id"] = pricelist_rec.currency_id.id
            pricelist_data["pricelist_currency_name"] = pricelist_rec.currency_id.name
            pricelist_data["pricelist_currency_symbol"] = (
                pricelist_rec.currency_id.symbol or pricelist_rec.currency_id.name
            )

        supplier_ids = [row["id"] for row in result.get("suppliers", [])]
        suppliers = {
            supplier.id: supplier
            for supplier in self.env["product.supplierinfo"].browse(supplier_ids)
        }
        for supplier_data in result.get("suppliers", []):
            supplier = suppliers.get(supplier_data["id"])
            if not supplier or not supplier.currency_id:
                continue
            if supplier.currency_id == pos_currency:
                continue
            supplier_data["price"] = supplier.currency_id._convert(
                supplier_data["price"],
                pos_currency,
                company,
                date,
            )

        optional_rows = result.get("optional_products") or []
        if optional_rows and hasattr(self, "_optional_product_pos_domain"):
            optional_templates = self.optional_product_ids.filtered_domain(
                self._optional_product_pos_domain()
            )
            for optional, template in zip(optional_rows, optional_templates):
                variant = template.product_variant_id
                if pricelist:
                    optional["price"] = pricelist._get_product_price(
                        variant,
                        quantity,
                        currency=pos_currency,
                    )
                else:
                    optional["price"] = variant.currency_id._convert(
                        variant.lst_price,
                        pos_currency,
                        company,
                        date,
                    )

        return result

    def _process_pos_ui_product_product(self, products, config_id):
        if not products:
            return super()._process_pos_ui_product_product(products, config_id)

        company = self.env.company
        pos_currency = config_id.currency_id
        date = fields.Date.today()
        products_by_id = {product["id"]: product for product in products}
        product_records = self.browse(list(products_by_id.keys()))
        source_prices = {}

        for product_record in product_records:
            product_data = products_by_id[product_record.id]
            if product_data.get("_currency_pos_price_currency_id") == pos_currency.id:
                source_prices[product_record.id] = {
                    "lst_price": product_data.get("lst_price"),
                    "standard_price": product_data.get("standard_price"),
                    "currency_pos_lst_price": product_data.get("currency_pos_lst_price"),
                    "currency_pos_standard_price": product_data.get(
                        "currency_pos_standard_price"
                    ),
                    "list_currency": pos_currency,
                    "cost_currency": pos_currency,
                    "already_converted": True,
                }
            else:
                source_prices[product_record.id] = {
                    "lst_price": product_data.get("lst_price"),
                    "standard_price": product_data.get("standard_price"),
                    "list_currency": product_record.currency_id or company.currency_id,
                    "cost_currency": (
                        product_record.cost_currency_id or company.currency_id
                    ),
                    "already_converted": False,
                }

        super()._process_pos_ui_product_product(products, config_id)

        for product_id, source in source_prices.items():
            product_data = products_by_id[product_id]
            if source["already_converted"]:
                if source.get("lst_price") is not None:
                    product_data["lst_price"] = source["lst_price"]
                if source.get("standard_price") is not None:
                    product_data["standard_price"] = source["standard_price"]
                if source.get("currency_pos_lst_price") is not None:
                    product_data["currency_pos_lst_price"] = source[
                        "currency_pos_lst_price"
                    ]
                if source.get("currency_pos_standard_price") is not None:
                    product_data["currency_pos_standard_price"] = source[
                        "currency_pos_standard_price"
                    ]
            else:
                raw_lst = source.get("lst_price")
                raw_std = source.get("standard_price")
                product_data["currency_pos_lst_price"] = raw_lst
                product_data["currency_pos_standard_price"] = raw_std
                if raw_lst is not None:
                    product_data["lst_price"] = source["list_currency"]._convert(
                        raw_lst,
                        pos_currency,
                        company,
                        date,
                    )
                if raw_std is not None:
                    product_data["standard_price"] = source["cost_currency"]._convert(
                        raw_std,
                        pos_currency,
                        company,
                        date,
                    )
            product_data["_currency_pos_price_currency_id"] = pos_currency.id

    @api.model
    def currency_pos_get_product_prices(self, product_ids, config_id):
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise exceptions.AccessError(
                _("You are not allowed to load POS product prices.")
            )
        config = self.env["pos.config"].browse(config_id).exists()
        if not config:
            raise exceptions.UserError(_("POS configuration not found."))
        config.check_access("read")
        product_ids = list(dict.fromkeys(product_ids or []))[:50]
        if not product_ids:
            return {}
        products = self._load_product_with_domain(
            [
                ("id", "in", product_ids),
                ("available_in_pos", "=", True),
                ("sale_ok", "=", True),
            ],
            config.id,
        )
        self._process_pos_ui_product_product(products, config)
        return {
            product["id"]: {
                "lst_price": product["lst_price"],
                "standard_price": product["standard_price"],
                "currency_pos_lst_price": product.get("currency_pos_lst_price"),
                "currency_pos_standard_price": product.get("currency_pos_standard_price"),
                "_currency_pos_price_currency_id": product.get(
                    "_currency_pos_price_currency_id"
                ),
            }
            for product in products
        }
