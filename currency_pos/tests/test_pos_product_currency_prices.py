from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPosProductCurrencyPrices(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company_currency = cls.company.currency_id
        cls.eur_currency = cls.env.ref("base.EUR")
        cls.eur_currency.active = True
        cls.env["res.currency.rate"].search(
            [
                ("currency_id", "=", cls.eur_currency.id),
                ("company_id", "in", [False, cls.company.id]),
            ]
        ).unlink()
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "rate": 2.0,
                "currency_id": cls.eur_currency.id,
                "company_id": cls.company.id,
            }
        )
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "POS Currency Prices",
                "company_id": cls.company.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "EUR Forced Product",
                "available_in_pos": True,
                "list_price": 10.0,
                "standard_price": 8.0,
                "force_currency_id": cls.eur_currency.id,
            }
        )

    def test_process_converts_forced_currency_to_pos_currency(self):
        products = self.env["product.product"]._load_product_with_domain(
            [("id", "=", self.product.id)],
            self.pos_config.id,
        )
        self.assertEqual(products[0]["lst_price"], 10.0)

        self.env["product.product"]._process_pos_ui_product_product(
            products,
            self.pos_config,
        )
        # Company/POS currency rate: 1 company = 2 EUR => 10 EUR -> 5 company
        self.assertAlmostEqual(products[0]["lst_price"], 5.0)
        self.assertAlmostEqual(products[0]["standard_price"], 4.0)
        self.assertAlmostEqual(products[0]["currency_pos_lst_price"], 10.0)
        self.assertAlmostEqual(products[0]["currency_pos_standard_price"], 8.0)
        self.assertEqual(
            products[0]["_currency_pos_price_currency_id"],
            self.pos_config.currency_id.id,
        )

    def test_process_is_idempotent(self):
        products = self.env["product.product"]._load_product_with_domain(
            [("id", "=", self.product.id)],
            self.pos_config.id,
        )
        Product = self.env["product.product"]
        Product._process_pos_ui_product_product(products, self.pos_config)
        first_lst = products[0]["lst_price"]
        first_std = products[0]["standard_price"]

        Product._process_pos_ui_product_product(products, self.pos_config)
        self.assertAlmostEqual(products[0]["lst_price"], first_lst)
        self.assertAlmostEqual(products[0]["standard_price"], first_std)

    def test_currency_pos_get_product_prices(self):
        prices = self.env["product.product"].currency_pos_get_product_prices(
            [self.product.id],
            self.pos_config.id,
        )
        self.assertIn(self.product.id, prices)
        self.assertAlmostEqual(prices[self.product.id]["lst_price"], 5.0)
        self.assertAlmostEqual(prices[self.product.id]["standard_price"], 4.0)
        self.assertAlmostEqual(prices[self.product.id]["currency_pos_lst_price"], 10.0)

    def test_get_product_info_pos_pricelists_in_pos_currency(self):
        eur_pricelist = self.env["product.pricelist"].create(
            {
                "name": "EUR Test PL",
                "currency_id": self.eur_currency.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "list_price",
                        },
                    )
                ],
            }
        )
        self.pos_config.write(
            {
                "use_pricelist": True,
                "pricelist_id": eur_pricelist.id,
                "available_pricelist_ids": [(6, 0, [eur_pricelist.id])],
            }
        )
        # Even if the client sends an unconverted product-currency price, the
        # server must recompute financials/pricelists in the POS currency.
        info = self.product.get_product_info_pos(
            10.0,
            1,
            self.pos_config.id,
            eur_pricelist.id,
        )
        self.assertEqual(len(info["pricelists"]), 1)
        self.assertAlmostEqual(info["all_prices"]["price_without_tax"], 5.0)
        self.assertAlmostEqual(info["pricelists"][0]["price"], 5.0)
        self.assertAlmostEqual(info["pricelists"][0]["price_pricelist_currency"], 10.0)
        self.assertEqual(
            info["pricelists"][0]["currency_id"],
            self.pos_config.currency_id.id,
        )
