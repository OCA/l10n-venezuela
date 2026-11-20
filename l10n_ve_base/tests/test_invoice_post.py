# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .common import L10nVeSetupMixin


@tagged("post_install", "-at_install")
class TestInvoicePost(L10nVeSetupMixin, AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._l10n_ve_setup()
        cls.partner = cls._create_ve_partner("Proveedor Fiscal", "J123456784")

    def test_vendor_bill_requires_control_number(self):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2025-09-01",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Servicio",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            move.action_post()

    def test_vendor_bill_posts_with_control_number(self):
        move = self._create_vendor_bill(self.partner, amount=100.0)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.nro_ctrl, "00-12345678")

    def test_customer_invoice_does_not_generate_control_number(self):
        customer = self._create_ve_partner("Cliente Fiscal", "V123456781")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": customer.id,
                "invoice_date": "2025-09-01",
                "invoice_date_due": "2025-09-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Servicio",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        # Assigned by the printing house or fiscal machine, never by Odoo.
        self.assertFalse(move.nro_ctrl)

    def test_ve_partner_without_vat_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Sin RIF",
                    "country_id": self.ve_country.id,
                }
            )

    def test_partner_without_rif_cannot_post(self):
        foreign = self.env["res.partner"].create(
            {
                "name": "Sin RIF",
                "country_id": self.env.ref("base.us").id,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": foreign.id,
                "invoice_date": "2025-09-01",
                "nro_ctrl": "00-00000001",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Servicio",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            move.action_post()

    def test_posted_invoice_locks_identification(self):
        self.assertFalse(self.partner.l10n_ve_identification_locked)
        self.partner.write({"vat": "J111111110"})
        self.assertEqual(self.partner.vat, "J111111110")
        self._create_vendor_bill(self.partner, amount=100.0)
        self.partner.invalidate_recordset(["l10n_ve_identification_locked"])
        self.assertTrue(self.partner.l10n_ve_identification_locked)
        with self.assertRaises(ValidationError):
            self.partner.write({"vat": "J123456784"})
        with self.assertRaises(ValidationError):
            self.partner.write(
                {
                    "l10n_latam_identification_type_id": self.env.ref(
                        "l10n_ve_base.it_cedula_v"
                    ).id,
                }
            )
        with self.assertRaises(ValidationError):
            self.partner.write({"person_type": "pjnd"})
        self.partner.write({"vat": self.partner.vat})
        self.partner.write({"person_type": self.partner.person_type})
