# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_loyalty.tests.common import L10nVeLoyaltyCommon


@tagged("post_install", "-at_install")
class TestAccountMoveTaxTotalsGlobalDiscount(L10nVeLoyaltyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE global discount",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )

    def _create_invoice(self, price_unit=100.0, quantity=1.0, discount=0.0):
        product = self._create_product(
            name="Product line",
            list_price=price_unit,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "discount": discount,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )

    def _get_discount_reason(self, name):
        Reason = self.env["l10n.ve.discount.reason"]
        reason = Reason.search([("name", "=", name)], limit=1)
        if not reason:
            reason = Reason.create({"name": name})
        return reason

    def _add_global_discount(
        self,
        move,
        name,
        amount,
        discount_type="fixed",
        discount_percentage=0.0,
    ):
        return self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self._get_discount_reason(name).id,
                "amount": amount,
                "discount_type": discount_type,
                "discount_percentage": discount_percentage,
            }
        )

    def _invoice_subtotal(self, move):
        return sum(move._l10n_ve_global_discount_subtotal_by_taxes().values())

    def test_sequential_percentage_then_fixed_discount(self):
        move = self._create_invoice(price_unit=1000.0)
        subtotal = self._invoice_subtotal(move)
        self._add_global_discount(
            move,
            "Descuento 50%",
            subtotal * 0.5,
            discount_type="percentage",
            discount_percentage=0.5,
        )
        self._add_global_discount(move, "Descuento fijo", 10.0)
        self.assertAlmostEqual(
            move.amount_untaxed, subtotal - (subtotal * 0.5) - 10.0, places=2
        )
        tax_totals = move.tax_totals
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"],
            (subtotal * 0.5) + 10.0,
            places=2,
        )
        lines = tax_totals["l10n_ve_global_discount_lines"]
        self.assertEqual(lines[0]["discount_type"], "percentage")
        self.assertAlmostEqual(lines[0]["discount_percentage"], 0.5, places=4)
        self.assertAlmostEqual(lines[0]["amount"], subtotal * 0.5, places=2)
        self.assertAlmostEqual(lines[1]["amount"], 10.0, places=2)

    def test_fixed_discount_wizard_on_total_reduces_amount_total(self):
        move = self._create_invoice(price_unit=100.0)
        tax = self.company_data["default_tax_sale"]
        self.assertAlmostEqual(tax.amount, 16.0, places=2)
        self.assertAlmostEqual(move.amount_untaxed, 100.0, places=2)
        self.assertAlmostEqual(move.amount_total, 116.0, places=2)
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": move.id,
                "discount_mode": "amount",
                "amount_base": "total",
                "amount": 10.0,
                "reason_id": self._get_discount_reason("Desc total").id,
            }
        )
        wizard.action_apply_discount()
        self.assertAlmostEqual(move.amount_total, 106.0, places=2)
        discount = move.l10n_ve_global_discount_ids
        self.assertEqual(len(discount), 1)
        self.assertEqual(discount.amount_base, "total")
        expected_untaxed = move.currency_id.round(10.0 / 1.16)
        self.assertAlmostEqual(discount.amount, expected_untaxed, places=2)

    def test_fixed_discount_wizard_on_untaxed_keeps_subtotal_base(self):
        move = self._create_invoice(price_unit=100.0)
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": move.id,
                "discount_mode": "amount",
                "amount_base": "untaxed",
                "amount": 10.0,
                "reason_id": self._get_discount_reason("Desc subtotal").id,
            }
        )
        wizard.action_apply_discount()
        self.assertAlmostEqual(move.amount_untaxed, 90.0, places=2)
        self.assertAlmostEqual(move.amount_total, 104.4, places=2)
        self.assertEqual(move.l10n_ve_global_discount_ids.amount_base, "untaxed")
        self.assertAlmostEqual(move.l10n_ve_global_discount_ids.amount, 10.0, places=2)

    def test_only_one_percentage_global_discount_allowed(self):
        move = self._create_invoice()
        self._add_global_discount(
            move,
            "Descuento 10%",
            10.0,
            discount_type="percentage",
            discount_percentage=0.1,
        )
        with self.assertRaises(ValidationError):
            self._add_global_discount(
                move,
                "Descuento 20%",
                20.0,
                discount_type="percentage",
                discount_percentage=0.2,
            )

    def test_percentage_discount_updates_when_invoice_changes(self):
        move = self._create_invoice(price_unit=1000.0)
        subtotal = self._invoice_subtotal(move)
        discount = self._add_global_discount(
            move,
            "Descuento 50%",
            subtotal * 0.5,
            discount_type="percentage",
            discount_percentage=0.5,
        )
        move.invoice_line_ids[0].write({"price_unit": 2000.0})
        new_subtotal = self._invoice_subtotal(move)
        self.assertAlmostEqual(discount.amount, new_subtotal * 0.5, places=2)
        self.assertAlmostEqual(
            move.amount_untaxed, new_subtotal - discount.amount, places=2
        )

    def test_tax_totals_shows_grouped_global_discount(self):
        move = self._create_invoice()
        self._add_global_discount(move, "Promoción", 10.0)
        tax_totals = move.tax_totals

        self.assertTrue(tax_totals["l10n_ve_show_global_discount"])
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 10.0
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"]
            - tax_totals["l10n_ve_global_discount_amount_currency"],
            tax_totals["base_amount_currency"],
            places=2,
        )
        self.assertEqual(len(tax_totals["l10n_ve_global_discount_lines"]), 1)
        self.assertAlmostEqual(
            move.amount_untaxed, tax_totals["base_amount_currency"], places=2
        )

    def test_original_tax_totals_template_shows_global_discount(self):
        move = self._create_invoice()
        self._add_global_discount(move, "Promoción", 10.0)
        rendered = self.env["ir.ui.view"]._render_template(
            "account.document_tax_totals",
            {
                "currency": move.currency_id,
                "tax_totals": move.tax_totals,
            },
        )
        self.assertIn("o_l10n_ve_global_discount", rendered)
        self.assertIn("Descuento", rendered)
        self.assertLess(
            rendered.index("o_subtotal"),
            rendered.index("o_l10n_ve_global_discount"),
        )

    def test_tax_totals_groups_multiple_global_discounts(self):
        move = self._create_invoice(price_unit=200.0)
        self._add_global_discount(move, "Promo A", 10.0)
        self._add_global_discount(move, "Promo B", 20.0)
        tax_totals = move.tax_totals

        self.assertTrue(tax_totals["l10n_ve_show_global_discount"])
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 30.0
        )
        self.assertEqual(len(tax_totals["l10n_ve_global_discount_lines"]), 2)
        self.assertAlmostEqual(
            move.amount_untaxed, tax_totals["base_amount_currency"], places=2
        )

    def test_tax_totals_without_global_discount(self):
        move = self._create_invoice()
        tax_totals = move.tax_totals

        self.assertFalse(tax_totals.get("l10n_ve_show_global_discount"))
        self.assertAlmostEqual(
            tax_totals.get("l10n_ve_global_discount_amount_currency", 0.0),
            0.0,
            places=2,
        )

    def test_line_discount_not_exposed_in_tax_totals(self):
        move = self._create_invoice(discount=10.0)
        tax_totals = move.tax_totals

        self.assertFalse(tax_totals.get("l10n_ve_show_global_discount"))
        self.assertFalse(tax_totals.get("l10n_ve_show_line_discount"))

    def _ensure_sale_discount_product(self, name):
        if "sale_discount_product_id" not in self.env["res.company"]._fields:
            self.skipTest("sale_discount_product_id requires sale module")
        discount_product = self.env["product.product"].create(
            {
                "name": name,
                "type": "service",
                "list_price": 1.0,
                "company_id": self.env.company.id,
            }
        )
        self.env.company.sale_discount_product_id = discount_product
        return discount_product

    def test_product_discount_line_exposed_in_tax_totals(self):
        discount_product = self._ensure_sale_discount_product(
            "Producto descuento global"
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": discount_product.id,
                            "name": "Descuento promocional",
                            "quantity": 1.0,
                            "price_unit": -15.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        discount_line = move._l10n_ve_get_product_discount_lines()
        tax_totals = move.tax_totals
        discount_amount = abs(discount_line.price_subtotal)
        self.assertTrue(tax_totals["l10n_ve_show_global_discount"])
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"],
            discount_amount,
            places=2,
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"]
            - tax_totals["l10n_ve_global_discount_amount_currency"],
            tax_totals["base_amount_currency"],
            places=2,
        )
        self.assertEqual(len(tax_totals["l10n_ve_global_discount_lines"]), 1)
        self.assertEqual(
            tax_totals["l10n_ve_global_discount_lines"][0]["source"], "product_line"
        )
        self.assertEqual(
            tax_totals["l10n_ve_global_discount_lines"][0]["discount_type"],
            "percentage",
        )
        self.assertTrue(
            tax_totals["l10n_ve_global_discount_lines"][0]["discount_percentage"]
        )
        self.assertTrue(tax_totals.get("l10n_ve_global_discount_percentage"))

    def test_remove_product_discount_line_from_tax_totals_action(self):
        discount_product = self._ensure_sale_discount_product(
            "Producto descuento a remover"
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": discount_product.id,
                            "name": "Descuento",
                            "quantity": 1.0,
                            "price_unit": -10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        discount_line = move._l10n_ve_get_product_discount_lines()
        self.assertTrue(discount_line)
        move.action_l10n_ve_remove_global_discount(discount_line.id)
        self.assertFalse(move._l10n_ve_get_product_discount_lines())
        self.assertFalse(move.tax_totals.get("l10n_ve_show_global_discount"))

    def test_remove_global_discount_updates_totals(self):
        move = self._create_invoice()
        subtotal = self._invoice_subtotal(move)
        discount = self._add_global_discount(move, "Temporal", 15.0)
        self.assertAlmostEqual(move.amount_untaxed, subtotal - 15.0, places=2)
        discount.unlink()
        self.assertAlmostEqual(move.amount_untaxed, subtotal, places=2)
        self.assertFalse(move.tax_totals.get("l10n_ve_show_global_discount"))

    def test_global_discount_cannot_exceed_subtotal(self):
        move = self._create_invoice()
        with self.assertRaises(UserError):
            self._add_global_discount(move, "Exceso", 150.0)

    def test_global_discount_with_mixed_tax_and_untaxed_lines(self):
        company = self.env.company
        sale_tax = company.account_sale_tax_id
        exempt_tax = self.env["product.template"]._l10n_ve_get_exent_sale_tax(company)
        product_taxed = self._create_product(
            name="Gravada",
            list_price=100.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exenta",
            list_price=50.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Gravada",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(sale_tax.ids)],
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exenta",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    ),
                ],
            }
        )
        subtotal = self._invoice_subtotal(move)
        self._add_global_discount(move, "Descuento", 15.0)
        self.assertAlmostEqual(move.amount_untaxed, subtotal - 15.0, places=2)
        move.invoice_line_ids[0].write({"price_unit": 110.0})
        self.assertAlmostEqual(
            move.amount_untaxed,
            self._invoice_subtotal(move) - 15.0,
            places=2,
        )


@tagged("post_install", "-at_install")
class TestAccountMoveGlobalDiscountJournalLines(L10nVeLoyaltyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE discount journal",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J123456780",
            }
        )
        cls.discount_allocation_account = cls.env["account.account"].create(
            {
                "name": "VE Global discount allocation",
                "code": "VEDISCAL",
                "account_type": "expense",
                "company_ids": [(6, 0, cls.env.company.ids)],
            }
        )
        cls.env.company.account_discount_expense_allocation_id = (
            cls.discount_allocation_account
        )

    def _create_invoice(self, price_unit=100.0, quantity=1.0):
        product = self._create_product(
            name="Product line",
            list_price=price_unit,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )

    def _get_discount_reason(self, name):
        reason = self.env["l10n.ve.discount.reason"].search(
            [("name", "=", name)], limit=1
        )
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": name})
        return reason

    def _add_global_discount(self, move, name, amount):
        return self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self._get_discount_reason(name).id,
                "amount": amount,
            }
        )

    def test_global_discount_creates_accounting_discount_lines(self):
        revenue_account = self.company_data["default_account_revenue"]
        discount_account = self.discount_allocation_account

        move = self._create_invoice(price_unit=100.0)
        self._add_global_discount(move, "Promoción", 10.0)

        product_line = move.line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        global_discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        self.assertEqual(len(global_discount_lines), 1)
        self.assertEqual(product_line.account_id, revenue_account)
        self.assertAlmostEqual(
            product_line.amount_currency,
            -move.tax_totals["l10n_ve_subtotal_gross_currency"],
            places=2,
        )
        discount_line = global_discount_lines
        self.assertEqual(discount_line.account_id, discount_account)
        self.assertAlmostEqual(discount_line.amount_currency, 10.0, places=2)
        self.assertAlmostEqual(
            move.amount_untaxed,
            move.tax_totals["base_amount_currency"],
            places=2,
        )

    def test_global_discount_accounting_lines_per_tax_group(self):
        revenue_account = self.company_data["default_account_revenue"]
        sale_tax = self.company_data["default_tax_sale"]
        exempt_tax = self.env["product.template"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )

        product_taxed = self._create_product(
            name="Taxed product",
            list_price=100.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exempt product",
            list_price=50.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Taxed product",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exempt product",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                        }
                    ),
                ],
            }
        )
        self._add_global_discount(move, "Descuento mixto", 15.0)

        global_discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        subtotal_by_taxes = move._l10n_ve_global_discount_subtotal_by_taxes()
        self.assertEqual(len(global_discount_lines), len(subtotal_by_taxes))
        self.assertAlmostEqual(
            sum(line.amount_currency for line in global_discount_lines),
            15.0,
            places=2,
        )
        self.assertAlmostEqual(
            move.amount_untaxed,
            move.tax_totals["base_amount_currency"],
            places=2,
        )
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_global_discount_amount_currency"],
            15.0,
            places=2,
        )

    def test_duplicate_invoice_with_global_discount_is_balanced(self):
        move = self._create_invoice(price_unit=100.0)
        self._add_global_discount(move, "Promoción", 10.0)
        self.assertTrue(move.line_ids.filtered("l10n_ve_global_discount_line"))

        duplicate = move.copy()

        self.assertEqual(len(duplicate.l10n_ve_global_discount_ids), 1)
        self.assertAlmostEqual(
            duplicate.l10n_ve_global_discount_ids.amount, 10.0, places=2
        )
        self.assertAlmostEqual(
            duplicate.tax_totals["l10n_ve_global_discount_amount_currency"],
            10.0,
            places=2,
        )
        self.assertTrue(duplicate.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertAlmostEqual(sum(duplicate.line_ids.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(duplicate.amount_untaxed, move.amount_untaxed, places=2)
        self.assertAlmostEqual(duplicate.amount_total, move.amount_total, places=2)

    def test_remove_global_discount_rebalances_invoice(self):
        move = self._create_invoice(price_unit=100.0)
        self._add_global_discount(move, "Promoción", 10.0)
        self.assertTrue(move.line_ids.filtered("l10n_ve_global_discount_line"))

        move.l10n_ve_global_discount_ids.unlink()

        self.assertFalse(move.l10n_ve_global_discount_ids)
        self.assertFalse(move.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertAlmostEqual(
            move.tax_totals.get("l10n_ve_global_discount_amount_currency", 0.0),
            0.0,
            places=2,
        )
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_remove_global_discount_with_line_discount_rebalances_invoice(self):
        revenue_account = self.company_data["default_account_revenue"]
        sale_tax = self.company_data["default_tax_sale"]
        exempt_tax = self.env["product.template"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )

        product_taxed = self._create_product(
            name="Taxed product",
            list_price=1000.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exempt product",
            list_price=2000.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Taxed product",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "discount": 3.99,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exempt product",
                            "quantity": 1.0,
                            "price_unit": 2000.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                        }
                    ),
                ],
            }
        )
        self._add_global_discount(move, "Promoción", 1500.0)
        self.assertTrue(move.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertFalse(move.line_ids.filtered("l10n_ve_line_discount_line"))

        move.l10n_ve_global_discount_ids.unlink()

        self.assertFalse(move.l10n_ve_global_discount_ids)
        self.assertFalse(move.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertFalse(move.line_ids.filtered("l10n_ve_line_discount_line"))
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_line_and_global_discount_without_line_discount_journal_lines(self):
        revenue_account = self.company_data["default_account_revenue"]
        discount_account = self.discount_allocation_account
        sale_tax = self.company_data["default_tax_sale"]
        exempt_tax = self.env["product.template"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )

        product_taxed = self._create_product(
            name="Taxed product",
            list_price=1000.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exempt product",
            list_price=2000.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Taxed product",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "discount": 3.99,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exempt product",
                            "quantity": 1.0,
                            "price_unit": 2000.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                        }
                    ),
                ],
            }
        )
        self._add_global_discount(move, "Promoción", 1500.0)

        revenue_discount_lines = move.line_ids.filtered(
            lambda line: line.display_type == "discount"
            and line.account_id == revenue_account
        )
        line_discount_lines = move.line_ids.filtered("l10n_ve_line_discount_line")
        global_discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        taxed_product_line = move.line_ids.filtered(
            lambda line: line.display_type == "product" and line.name == "Taxed product"
        )

        self.assertFalse(revenue_discount_lines)
        self.assertFalse(line_discount_lines)
        self.assertTrue(global_discount_lines)
        self.assertAlmostEqual(taxed_product_line.amount_currency, -960.1, places=2)
        self.assertEqual(global_discount_lines.account_id, discount_account)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_global_discount_requires_permission(self):
        move = self._create_invoice(price_unit=100.0)
        invoice_user = self.env["res.users"].create(
            {
                "name": "Invoice user without discount",
                "login": "l10n_ve_invoice_no_discount",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("account.group_account_invoice").id,
                        ]
                    )
                ],
            }
        )
        env = self.env(user=invoice_user)
        move_as_user = move.with_env(env)
        with self.assertRaises(UserError):
            move_as_user.action_l10n_ve_open_global_discount_wizard()
        with self.assertRaises(UserError):
            self.env["l10n.ve.account.move.discount"].with_env(env).create(
                {
                    "move_id": move.id,
                    "reason_id": self._get_discount_reason("Blocked").id,
                    "amount": 10.0,
                }
            )
        self.assertFalse(move_as_user.l10n_ve_show_global_discount_action)
        self.assertFalse(
            move_as_user.tax_totals.get("l10n_ve_can_manage_global_discount")
        )
