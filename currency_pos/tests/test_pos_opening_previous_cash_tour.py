from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon
from odoo.addons.point_of_sale.tests.common import archive_products


@tagged("post_install", "-at_install", "currency_pos_tour")
class TestPosOpeningPreviousCashTour(AccountTestInvoicingHttpCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        archive_products(cls.env)
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
        cash_journal = cls.company_data["default_journal_cash"]
        profit_account = (
            cash_journal.profit_account_id
            or cls.company.default_cash_difference_income_account_id
        )
        loss_account = (
            cash_journal.loss_account_id
            or cls.company.default_cash_difference_expense_account_id
        )
        if profit_account and not cash_journal.profit_account_id:
            cash_journal.profit_account_id = profit_account
        if loss_account and not cash_journal.loss_account_id:
            cash_journal.loss_account_id = loss_account
        cls.eur_cash_journal = cls.env["account.journal"].create(
            {
                "name": "Cash EUR Tour",
                "type": "cash",
                "code": "CEUR",
                "currency_id": cls.eur_currency.id,
                "profit_account_id": profit_account.id if profit_account else False,
                "loss_account_id": loss_account.id if loss_account else False,
            }
        )
        cls.eur_cash_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Cash EUR",
                "journal_id": cls.eur_cash_journal.id,
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
            }
        )
        cls.main_pos_config = cls.env["pos.config"].create(
            {
                "name": "Tour POS Opening Cash",
                "journal_id": cls.company_data["default_journal_sale"].id,
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
                "allow_multi_currency_payment": True,
                "payment_method_ids": [
                    (4, cls.cash_payment_method.id),
                    (4, cls.eur_cash_payment_method.id),
                ],
            }
        )
        cls.tour_product = cls.env["product.product"].create(
            {
                "name": "Tour Opening Product",
                "available_in_pos": True,
                "list_price": 10.0,
                "taxes_id": [(6, 0, [])],
            }
        )
        cls.pos_user = cls.env["res.users"].create(
            {
                "name": "POS Opening MC User",
                "login": "pos_opening_mc_user",
                "password": "pos_opening_mc_user",
                "groups_id": [
                    (6, 0, cls.env.ref("point_of_sale.group_pos_user").ids),
                ],
            }
        )

    def test_pos_opening_suggests_previous_cash_balances_tour(self):
        self.main_pos_config.with_user(self.pos_user).open_ui()
        first_session = self.main_pos_config.current_session_id
        first_session.oca_set_opening_control(
            {
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 20.0,
            },
            False,
        )
        first_session.post_closing_cash_details(
            5.0,
            counted_cash_by_method={
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 20.0,
            },
        )
        first_session.close_session_from_ui()
        self.assertEqual(first_session.state, "closed")

        self.main_pos_config.with_user(self.pos_user).open_ui()
        second_session = self.main_pos_config.current_session_id
        loaded = second_session._load_pos_data({})
        self.assertAlmostEqual(
            loaded["data"][0]["_oca_cash_box_openings"][self.cash_payment_method.id],
            5.0,
            places=2,
        )
        self.assertAlmostEqual(
            loaded["data"][0]["_oca_cash_box_openings"][self.eur_cash_payment_method.id],
            20.0,
            places=2,
        )

        self.start_tour(
            f"/pos/ui?config_id={self.main_pos_config.id}",
            "PosOpeningSuggestsPreviousCashBalancesTour",
            login="pos_opening_mc_user",
        )
