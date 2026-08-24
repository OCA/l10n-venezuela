# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import timedelta

from odoo import fields, models
from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero

QTY_FIELDS = (
    "inv_initial_qty",
    "entradas_qty",
    "salidas_qty",
    "retiros_qty",
    "autoconsumos_qty",
    "inv_final_qty",
)
CONVERTED_VAL_MAP = {
    "cost": "cost",
    "inv_initial_val": "inv_initial",
    "entradas_val": "entradas",
    "salidas_val": "salidas",
    "retiros_val": "retiros",
    "autoconsumos_val": "autoconsumos",
    "inv_final_val": "inv_final",
}


class StockInventoryBookReportHandler(models.AbstractModel):
    _name = "stock.inventory.book.report.handler.oca"
    _inherit = "account.report.custom.handler.oca"
    _description = "Stock Inventory Book Report Handler"

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "inventory_book_report",
            "components": {
                "AccountReportFilters": (
                    "l10n_ve_reports_stock.InventoryBookReportFilters"
                ),
            },
        }

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        options["multi_currency"] = report.env.user.has_group(
            "base.group_multi_currency"
        )
        options["warehouse_ids"] = (previous_options or {}).get("warehouse_ids", [])
        options["hide_zero_quantity_products"] = (previous_options or {}).get(
            "hide_zero_quantity_products", False
        )
        return result

    def _get_warehouses(self, options):
        warehouse_ids = options.get("warehouse_ids", [])
        warehouses = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)]
        )
        if warehouse_ids:
            warehouses = warehouses.filtered(lambda w: w.id in warehouse_ids)
        return warehouses

    def _get_product_cost_currency(self, product):
        if hasattr(product, "cost_currency_id") and product.cost_currency_id:
            return product.cost_currency_id
        if hasattr(product, "product_tmpl_id") and hasattr(
            product.product_tmpl_id, "cost_currency_id"
        ):
            if product.product_tmpl_id.cost_currency_id:
                return product.product_tmpl_id.cost_currency_id
        return self.env.company.currency_id

    def _convert_to_display_currency(self, value, source_currency, options, date=None):
        display_currency_id = options.get("display_currency_id")
        if not display_currency_id or source_currency.id == display_currency_id:
            return value, source_currency
        display_currency = self.env["res.currency"].browse(display_currency_id)
        if not date:
            currency_rate_date_type = options.get("currency_rate_date_type", "current")
            if currency_rate_date_type == "manual":
                date = options.get("currency_rate_date") or fields.Date.today()
            elif currency_rate_date_type == "document":
                date = options.get("date", {}).get("date_to") or fields.Date.today()
            else:
                date = fields.Date.today()
        if isinstance(date, str):
            date = fields.Date.from_string(date)
        try:
            converted = source_currency._convert(
                value, display_currency, self.env.company, date
            )
            return converted, display_currency
        except Exception:
            return value, source_currency

    def _get_child_location_ids(self, location):
        if not location:
            return []
        if location.parent_path:
            locations = self.env["stock.location"].search(
                [
                    "|",
                    ("id", "=", location.id),
                    ("parent_path", "like", location.parent_path + "%"),
                ]
            )
            return locations.ids
        return [location.id]

    def _get_stock_location_ids(self, warehouses):
        location_ids = []
        for warehouse in warehouses:
            location_ids.extend(self._get_child_location_ids(warehouse.lot_stock_id))
        return location_ids

    def _get_special_location_ids(self, warehouses):
        retiros_location_ids = []
        autoconsumos_location_ids = []
        for warehouse in warehouses:
            retiros_location_ids.extend(
                self._get_child_location_ids(warehouse.l10n_ve_location_retiros_id)
            )
            autoconsumos_location_ids.extend(
                self._get_child_location_ids(warehouse.l10n_ve_location_autoconsumos_id)
            )
        return retiros_location_ids, autoconsumos_location_ids

    def _get_empty_product_data(self):
        return {
            "inv_initial_qty": 0.0,
            "inv_initial_val": 0.0,
            "entradas_qty": 0.0,
            "entradas_val": 0.0,
            "salidas_qty": 0.0,
            "salidas_val": 0.0,
            "retiros_qty": 0.0,
            "retiros_val": 0.0,
            "autoconsumos_qty": 0.0,
            "autoconsumos_val": 0.0,
            "inv_final_qty": 0.0,
            "inv_final_val": 0.0,
            "cost": 0.0,
        }

    def _get_move_date(self, move):
        move_date = move.date
        if hasattr(move_date, "date"):
            return move_date.date()
        if isinstance(move_date, str):
            return fields.Date.from_string(move_date)
        return move_date

    def _apply_opening_move(self, data, qty, val, from_stock, to_stock):
        if to_stock and not from_stock:
            data["inv_initial_qty"] += qty
            data["inv_initial_val"] += val
        elif from_stock and not to_stock:
            data["inv_initial_qty"] -= qty
            data["inv_initial_val"] -= val

    def _apply_period_move(
        self, data, qty, val, from_stock, to_stock, to_retiros, to_autoconsumos
    ):
        if to_stock and not from_stock:
            data["entradas_qty"] += qty
            data["entradas_val"] += val
        elif from_stock and not to_stock:
            if to_retiros:
                data["retiros_qty"] += qty
                data["retiros_val"] += val
            elif to_autoconsumos:
                data["autoconsumos_qty"] += qty
                data["autoconsumos_val"] += val
            else:
                data["salidas_qty"] += qty
                data["salidas_val"] += val

    def _apply_move_to_product_data(
        self,
        result,
        move,
        date_from,
        date_to,
        stock_location_ids,
        retiros_location_ids,
        autoconsumos_location_ids,
    ):
        product = move.product_id
        if not product.is_storable:
            return
        qty = move.product_qty
        cost = product.standard_price or 0.0
        val = qty * cost
        from_stock = move.location_id.id in stock_location_ids
        to_stock = move.location_dest_id.id in stock_location_ids
        to_retiros = move.location_dest_id.id in retiros_location_ids
        to_autoconsumos = move.location_dest_id.id in autoconsumos_location_ids
        move_date = self._get_move_date(move)
        data = result[product.id]
        if move_date < date_from:
            self._apply_opening_move(data, qty, val, from_stock, to_stock)
        elif date_from <= move_date <= date_to:
            self._apply_period_move(
                data, qty, val, from_stock, to_stock, to_retiros, to_autoconsumos
            )

    def _finalize_product_data(self, result, products):
        for product in products:
            data = result[product.id]
            cost = product.standard_price or 0.0
            data["inv_initial_val"] = data["inv_initial_qty"] * cost
            inv_final = data["inv_initial_qty"] + data["entradas_qty"]
            inv_final -= data["salidas_qty"]
            inv_final -= data["retiros_qty"]
            inv_final -= data["autoconsumos_qty"]
            data["inv_final_qty"] = inv_final
            data["inv_final_val"] = inv_final * cost

    def _get_done_moves(self, stock_location_ids, date_to):
        date_to_end = date_to + timedelta(days=1)
        move_domain = [
            ("state", "=", "done"),
            ("product_id.is_storable", "=", True),
            ("date", "<", fields.Datetime.to_string(date_to_end)),
        ]
        if stock_location_ids:
            move_domain = expression.AND(
                [
                    move_domain,
                    [
                        "|",
                        ("location_id", "in", stock_location_ids),
                        ("location_dest_id", "in", stock_location_ids),
                    ],
                ]
            )
        return (
            self.env["stock.move"].with_context(active_test=False).search(move_domain)
        )

    def _get_product_data(self, warehouses, date_from, date_to, company_currency):
        del company_currency
        stock_location_ids = self._get_stock_location_ids(warehouses)
        retiros_location_ids, autoconsumos_location_ids = (
            self._get_special_location_ids(warehouses)
        )
        moves = self._get_done_moves(stock_location_ids, date_to)
        products = (
            self.env["product.product"]
            .browse(sorted(set(moves.mapped("product_id").ids)))
            .filtered("is_storable")
        )
        result = defaultdict(self._get_empty_product_data)
        for product in products:
            result[product.id]["cost"] = product.standard_price or 0.0
        for move in moves:
            self._apply_move_to_product_data(
                result,
                move,
                date_from,
                date_to,
                stock_location_ids,
                retiros_location_ids,
                autoconsumos_location_ids,
            )
        self._finalize_product_data(result, products)
        return result

    def _get_display_currency(self, options, company_currency):
        display_currency_id = options.get("display_currency_id")
        if display_currency_id:
            return self.env["res.currency"].browse(display_currency_id)
        return company_currency

    def _get_conversion_date(self, options):
        date_to_conv = options.get("date", {}).get("date_to") or fields.Date.today()
        if isinstance(date_to_conv, str):
            return fields.Date.from_string(date_to_conv)
        return date_to_conv

    def _is_zero_quantity_product(self, product, data):
        return all(
            float_is_zero(
                data[field_name],
                precision_rounding=product.uom_id.rounding or 0.01,
            )
            for field_name in QTY_FIELDS
        )

    def _convert_product_amounts(self, data, cost_currency, options, date_to_conv):
        converted = {}
        for field_name, converted_key in (
            ("cost", "cost"),
            ("inv_initial_val", "inv_initial"),
            ("entradas_val", "entradas"),
            ("salidas_val", "salidas"),
            ("retiros_val", "retiros"),
            ("autoconsumos_val", "autoconsumos"),
            ("inv_final_val", "inv_final"),
        ):
            converted[converted_key], _unused = self._convert_to_display_currency(
                data[field_name], cost_currency, options, date_to_conv
            )
        return converted

    def _build_product_column(
        self, report, options, column, product, data, converted, display_currency
    ):
        col_expr_label = column.get("expression_label", "")
        if col_expr_label == "code":
            return report._build_column_dict(
                product.default_code or str(product.id), column, options=options
            )
        if col_expr_label == "product":
            return report._build_column_dict(
                product.display_name, column, options=options
            )
        if col_expr_label in QTY_FIELDS:
            return report._build_column_dict(
                data[col_expr_label], column, options=options
            )
        if col_expr_label in CONVERTED_VAL_MAP:
            return report._build_column_dict(
                converted[CONVERTED_VAL_MAP[col_expr_label]],
                column,
                options=options,
                currency=display_currency,
            )
        return report._build_column_dict(None, column, options=options)

    def _accumulate_totals(self, totals, data, converted):
        totals["inv_initial_qty"] += data["inv_initial_qty"]
        totals["inv_initial_val"] += converted["inv_initial"]
        totals["entradas_qty"] += data["entradas_qty"]
        totals["entradas_val"] += converted["entradas"]
        totals["salidas_qty"] += data["salidas_qty"]
        totals["salidas_val"] += converted["salidas"]
        totals["retiros_qty"] += data["retiros_qty"]
        totals["retiros_val"] += converted["retiros"]
        totals["autoconsumos_qty"] += data["autoconsumos_qty"]
        totals["autoconsumos_val"] += converted["autoconsumos"]
        totals["inv_final_qty"] += data["inv_final_qty"]
        totals["inv_final_val"] += converted["inv_final"]

    def _build_total_column(self, report, options, column, totals, display_currency):
        col_expr_label = column.get("expression_label", "")
        if col_expr_label == "code":
            return report._build_column_dict("", column, options=options)
        if col_expr_label == "product":
            return report._build_column_dict(
                "TOTALES DEL PERIODO", column, options=options
            )
        if col_expr_label == "cost":
            return report._build_column_dict(None, column, options=options)
        if "val" in col_expr_label and col_expr_label in totals:
            return report._build_column_dict(
                totals[col_expr_label],
                column,
                options=options,
                currency=display_currency,
            )
        if col_expr_label in totals:
            return report._build_column_dict(
                totals[col_expr_label], column, options=options
            )
        return report._build_column_dict(None, column, options=options)

    def _append_product_line(
        self, report, options, lines, totals, product, data, display_currency, date_to
    ):
        cost_currency = self._get_product_cost_currency(product)
        converted = self._convert_product_amounts(data, cost_currency, options, date_to)
        line_columns = [
            self._build_product_column(
                report, options, column, product, data, converted, display_currency
            )
            for column in options["columns"]
        ]
        self._accumulate_totals(totals, data, converted)
        lines.append(
            (
                0,
                {
                    "id": report._get_generic_line_id(
                        None, "product.product", product.id
                    ),
                    "name": product.display_name,
                    "columns": line_columns,
                    "level": 2,
                    "unfoldable": False,
                    "caret_options": None,
                },
            )
        )

    def _append_total_line(self, report, options, lines, totals, display_currency):
        total_columns = [
            self._build_total_column(report, options, column, totals, display_currency)
            for column in options["columns"]
        ]
        lines.append(
            (
                0,
                {
                    "id": report._get_generic_line_id(None, "inventory_book_totals", 0),
                    "name": "TOTALES DEL PERIODO",
                    "columns": total_columns,
                    "level": 2,
                    "unfoldable": False,
                    "caret_options": None,
                },
            )
        )

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        del all_column_groups_expression_totals, warnings
        lines = []
        date_from = options.get("date", {}).get("date_from")
        date_to = options.get("date", {}).get("date_to")
        if not date_from or not date_to:
            return lines
        date_from = fields.Date.from_string(date_from)
        date_to = fields.Date.from_string(date_to)
        warehouses = self._get_warehouses(options)
        if not warehouses:
            return lines
        company_currency = self.env.company.currency_id
        product_data = self._get_product_data(
            warehouses, date_from, date_to, company_currency
        )
        totals = self._get_empty_product_data()
        totals.pop("cost", None)
        display_currency = self._get_display_currency(options, company_currency)
        date_to_conv = self._get_conversion_date(options)
        hide_zero = options.get("hide_zero_quantity_products")
        for product_id, data in sorted(product_data.items()):
            product = self.env["product.product"].browse(product_id)
            if not product.exists() or not product.active:
                continue
            if hide_zero and self._is_zero_quantity_product(product, data):
                continue
            self._append_product_line(
                report,
                options,
                lines,
                totals,
                product,
                data,
                display_currency,
                date_to_conv,
            )
        if product_data:
            self._append_total_line(report, options, lines, totals, display_currency)
        return lines
