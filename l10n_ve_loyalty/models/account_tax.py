# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.tools import float_is_zero


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _l10n_ve_get_document_currency_rate(self, document):
        if document._name == "account.move":
            return document.invoice_currency_rate or 1.0
        if document._name == "sale.order":
            return document.currency_rate or 1.0
        return 1.0

    @api.model
    def _l10n_ve_get_document_conversion_date(self, document):
        if document._name == "account.move":
            return document.invoice_date or document.date
        if document._name == "sale.order":
            return (document.date_order or fields.Datetime.now()).date()
        return fields.Date.context_today(self.env)

    @api.model
    def _l10n_ve_amount_currency_to_company(self, document, amount_currency):
        """Convert an amount in document currency to company currency."""
        currency = document.currency_id
        company = document.company_id
        if not currency or currency == company.currency_id:
            return amount_currency
        inverse_rate = getattr(document, "l10n_ve_inverse_rate", None) or 0.0
        if inverse_rate:
            return company.currency_id.round(amount_currency * inverse_rate)
        rate = self._l10n_ve_get_document_currency_rate(document) or 0.0
        if rate:
            return company.currency_id.round(amount_currency / rate)
        conversion_date = self._l10n_ve_get_document_conversion_date(document)
        return currency._convert(
            amount_currency,
            company.currency_id,
            company,
            conversion_date,
        )

    @api.model
    def _l10n_ve_build_discount_totals_result(
        self, document, tax_totals, global_discount_amount_currency, global_discount_lines
    ):
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0)
        base_amount = tax_totals.get("base_amount", 0.0)
        base_amount_foreign = tax_totals.get("base_amount_foreign_currency")
        currency = document.currency_id
        if float_is_zero(
            global_discount_amount_currency,
            precision_rounding=currency.rounding,
        ):
            return {
                "show_global_discount": False,
                "global_discount_amount_currency": 0.0,
                "global_discount_amount": 0.0,
                "global_discount_amount_foreign": 0.0,
                "global_discount_percentage": False,
                "subtotal_gross_currency": base_amount_currency,
                "subtotal_gross": base_amount,
                "subtotal_gross_foreign": base_amount_foreign or 0.0,
                "global_discount_lines": [],
            }

        company = document.company_id
        global_discount_amount = self._l10n_ve_amount_currency_to_company(
            document, global_discount_amount_currency
        )

        global_discount_amount_foreign = 0.0
        if document._name == "account.move":
            foreign_currency = getattr(document, "foreign_currency_id", False) or getattr(
                company, "foreign_currency_id", False
            )
        else:
            foreign_currency = getattr(company, "foreign_currency_id", False)
        conversion_date = self._l10n_ve_get_document_conversion_date(document)
        if foreign_currency and base_amount_foreign is not None:
            global_discount_amount_foreign = currency._convert(
                global_discount_amount_currency,
                foreign_currency,
                company,
                conversion_date,
            )

        subtotal_gross_currency = base_amount_currency + global_discount_amount_currency
        subtotal_gross = company.currency_id.round(base_amount + global_discount_amount)
        overall_percentage = False
        percentage_lines = [
            line
            for line in global_discount_lines
            if line.get("discount_type") == "percentage" and line.get("discount_percentage")
        ]
        if (
            percentage_lines
            and len(percentage_lines) == len(global_discount_lines)
            and not float_is_zero(
                subtotal_gross_currency, precision_rounding=currency.rounding
            )
        ):
            if len(percentage_lines) == 1:
                overall_percentage = percentage_lines[0]["discount_percentage"]
            else:
                overall_percentage = (
                    global_discount_amount_currency / subtotal_gross_currency
                )
        return {
            "show_global_discount": True,
            "global_discount_amount_currency": global_discount_amount_currency,
            "global_discount_amount": global_discount_amount,
            "global_discount_amount_foreign": global_discount_amount_foreign,
            "global_discount_percentage": overall_percentage,
            "subtotal_gross_currency": subtotal_gross_currency,
            "subtotal_gross": subtotal_gross,
            "subtotal_gross_foreign": (base_amount_foreign or 0.0)
            + global_discount_amount_foreign,
            "global_discount_lines": global_discount_lines,
        }

    @api.model
    def _l10n_ve_apply_global_discount_to_tax_totals(self, document, tax_totals):
        """Return a new tax_totals dict with VE global discount display fields."""
        if not tax_totals:
            return tax_totals
        totals = dict(tax_totals)
        discount_totals = self._l10n_ve_get_global_discount_totals(document, totals)
        totals["l10n_ve_show_global_discount"] = discount_totals["show_global_discount"]
        totals["l10n_ve_subtotal_gross_currency"] = discount_totals[
            "subtotal_gross_currency"
        ]
        totals["l10n_ve_subtotal_gross"] = discount_totals["subtotal_gross"]
        totals["l10n_ve_global_discount_amount_currency"] = discount_totals[
            "global_discount_amount_currency"
        ]
        totals["l10n_ve_global_discount_amount"] = discount_totals[
            "global_discount_amount"
        ]
        totals["l10n_ve_global_discount_amount_foreign"] = discount_totals[
            "global_discount_amount_foreign"
        ]
        totals["l10n_ve_subtotal_gross_foreign"] = discount_totals[
            "subtotal_gross_foreign"
        ]
        totals["l10n_ve_global_discount_lines"] = discount_totals[
            "global_discount_lines"
        ]
        totals["l10n_ve_global_discount_percentage"] = discount_totals[
            "global_discount_percentage"
        ]
        totals["l10n_ve_can_manage_global_discount"] = self.env.user.has_group(
            "l10n_ve_loyalty.group_l10n_ve_global_discount"
        )
        company_currency = document.company_id.currency_id
        totals["display_in_company_currency"] = bool(
            document.currency_id and document.currency_id != company_currency
        )
        if not totals.get("company_currency_id") and company_currency:
            totals["company_currency_id"] = company_currency.id
        return totals

    @api.model
    def _l10n_ve_get_product_line_discount_totals(self, document, tax_totals):
        """Build tax-totals discount data from sale_discount_product lines."""
        if not hasattr(document, "_l10n_ve_get_product_discount_lines"):
            return None
        lines = document._l10n_ve_get_product_discount_lines()
        if not lines:
            return None
        currency = document.currency_id
        global_discount_lines = []
        total_amount = 0.0
        line_amounts = []
        for line in lines:
            line_amount = abs(line.price_subtotal or 0.0)
            if float_is_zero(line_amount, precision_rounding=currency.rounding):
                continue
            total_amount += line_amount
            line_amounts.append((line, currency.round(line_amount)))
        if not line_amounts:
            return None
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0) or 0.0
        gross = base_amount_currency + total_amount
        for line, line_amount in line_amounts:
            discount_percentage = False
            discount_type = "fixed"
            if not float_is_zero(gross, precision_rounding=currency.rounding):
                discount_percentage = line_amount / gross
                discount_type = "percentage"
            global_discount_lines.append(
                {
                    "id": line.id,
                    "name": _("Descuento"),
                    "amount": line_amount,
                    "discount_type": discount_type,
                    "discount_percentage": discount_percentage,
                    "source": "product_line",
                }
            )
        return self._l10n_ve_build_discount_totals_result(
            document,
            tax_totals,
            currency.round(total_amount),
            global_discount_lines,
        )

    @api.model
    def _l10n_ve_get_global_discount_totals(self, document, tax_totals):
        """Compute grouped global discount amounts for VE tax totals display.

        Prefers SENIAT global discount records; if none, falls back to product
        discount lines (sale_discount_product_id) so both modes share tax totals UI.
        """
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0)
        base_amount = tax_totals.get("base_amount", 0.0)
        base_amount_foreign = tax_totals.get("base_amount_foreign_currency")
        empty_result = {
            "show_global_discount": False,
            "global_discount_amount_currency": 0.0,
            "global_discount_amount": 0.0,
            "global_discount_amount_foreign": 0.0,
            "global_discount_percentage": False,
            "subtotal_gross_currency": base_amount_currency,
            "subtotal_gross": base_amount,
            "subtotal_gross_foreign": base_amount_foreign or 0.0,
            "global_discount_lines": [],
        }
        discounts = document.l10n_ve_global_discount_ids
        if discounts:
            subtotal_by_taxes = document._l10n_ve_global_discount_subtotal_by_taxes()
            global_discount_lines = document._l10n_ve_get_global_discount_lines_data(
                subtotal_by_taxes
            )
            global_discount_amount_currency = sum(
                line["amount"] for line in global_discount_lines
            )
            return self._l10n_ve_build_discount_totals_result(
                document,
                tax_totals,
                global_discount_amount_currency,
                global_discount_lines,
            )

        product_line_totals = self._l10n_ve_get_product_line_discount_totals(
            document, tax_totals
        )
        if product_line_totals:
            return product_line_totals
        return empty_result

    @api.model
    def _l10n_ve_get_line_discount_amounts(self, base_lines, company):
        """Return untaxed line discount amounts in company currency by move line id."""
        if not base_lines:
            return {}

        discounted_lines = [
            base_line
            for base_line in base_lines
            if (base_line.get("discount") or 0.0) > 0.0
            and base_line.get("special_type") != "global_discount"
        ]
        if not discounted_lines:
            return {}

        for in_foreign_currency in (True, False):
            self._add_and_round_raw_gross_total_excluded_and_discount(
                base_lines,
                company,
                in_foreign_currency=in_foreign_currency,
            )

        amounts = {}
        for base_line in discounted_lines:
            record = base_line.get("record")
            line_id = record.id if getattr(record, "id", False) else base_line.get("id")
            if not line_id:
                continue
            amount = base_line["tax_details"].get("raw_discount_amount", 0.0)
            if amount:
                amounts[line_id] = amount
        return amounts

