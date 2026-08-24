from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon
from odoo.addons.point_of_sale.tests.common import archive_products


@tagged("post_install", "-at_install", "currency_pos_tour")
class TestPosPaymentCurrencyTour(AccountTestInvoicingHttpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        archive_products(cls.env)
        cls.main_pos_config = cls.env["pos.config"].create(
            {
                "name": "Tour POS MC",
                "journal_id": cls.company_data["default_journal_sale"].id,
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
                "allow_multi_currency_payment": True,
            }
        )
        cls.company_data["default_journal_cash"].pos_payment_method_ids.unlink()
        cls.cash_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Cash",
                "journal_id": cls.company_data["default_journal_cash"].id,
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
            }
        )
        cls.eur_currency = cls.env.ref("base.EUR")
        cls.eur_currency.active = True
        cls.env["res.currency.rate"].search([("currency_id", "=", cls.eur_currency.id)]).unlink()
        cls.env["res.currency.rate"].create(
            {
                "name": "2026-01-01",
                "rate": 2.0,
                "currency_id": cls.eur_currency.id,
            }
        )
        cls.eur_bank_journal = cls.env["account.journal"].create(
            {
                "name": "Bank EUR Tour",
                "type": "bank",
                "code": "BEUR",
                "currency_id": cls.eur_currency.id,
            }
        )
        cls.eur_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Bank EUR",
                "journal_id": cls.eur_bank_journal.id,
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
            }
        )
        cls.main_pos_config.write(
            {
                "payment_method_ids": [
                    (4, cls.cash_payment_method.id),
                    (4, cls.eur_payment_method.id),
                ],
            }
        )
        cls.tour_product = cls.env["product.product"].create(
            {
                "name": "Tour MC Product",
                "is_storable": True,
                "available_in_pos": True,
                "list_price": 10.0,
                "taxes_id": [(6, 0, [])],
            }
        )
        cls.env["stock.quant"].with_context(inventory_mode=True).create(
            {
                "product_id": cls.tour_product.id,
                "inventory_quantity": 100,
                "location_id": cls.main_pos_config.picking_type_id.default_location_src_id.id,
            }
        ).action_apply_inventory()

        cls.pos_user = cls.env["res.users"].create(
            {
                "name": "POS MC User",
                "login": "pos_mc_user",
                "password": "pos_mc_user",
                "groups_id": [
                    (6, 0, cls.env.ref("point_of_sale.group_pos_user").ids),
                ],
            }
        )

    def test_pos_payment_currency_tour(self):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_tour(
            f"/pos/ui?config_id={self.main_pos_config.id}",
            "PosPaymentCurrencyTour",
            login="pos_mc_user",
        )
