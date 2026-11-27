# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTaxApplType(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve = cls.env.ref("base.ve")
        cls.company = cls.env.company
        partner_vals = {
            "vat": "J000000000",
            "person_type": "pjdo",
        }
        rif = cls.env.ref(
            "l10n_ve_base.it_rif", raise_if_not_found=False
        ) or cls.env.ref("l10n_latam_base.it_vat", raise_if_not_found=False)
        if rif:
            partner_vals["l10n_latam_identification_type_id"] = rif.id
        cls.company.partner_id.write(partner_vals)
        cls.company.write(
            {
                "country_id": cls.ve.id,
                "account_fiscal_country_id": cls.ve.id,
            }
        )
        cls.tax_group = cls.env["account.tax.group"].create(
            {
                "name": "IVA VE appl_type test",
                "country_id": cls.ve.id,
            }
        )

    def _plain(self, value):
        return re.sub(r"<[^>]+>", "", str(value or "")).strip()

    def _create_tax(self, name, amount, type_tax_use="sale"):
        values = {
            "name": name,
            "amount": amount,
            "amount_type": "percent",
            "type_tax_use": type_tax_use,
            "country_id": self.ve.id,
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        }
        Tax = self.env["account.tax"]
        if "invoice_label" in Tax._fields:
            values["invoice_label"] = f"VAT ({amount:.1f}%) sales"
        if "description" in Tax._fields:
            values["description"] = f"VAT ({amount:.1f}%) sales"
        return Tax.create(values)

    def test_assigns_official_outdated_and_current_rates(self):
        tax12 = self._create_tax("12%", 12.0)
        tax8 = self._create_tax("8%", 8.0)
        tax0 = self._create_tax("0% EXEMPT", 0.0)
        tax22 = self._create_tax("22%", 22.0)
        tax16 = self._create_tax("16%", 16.0, type_tax_use="purchase")
        tax31 = self._create_tax("31%", 31.0, type_tax_use="purchase")
        sdcf = self._create_tax("SDCF", 0.0)
        sdcf.appl_type = "sdcf"
        igtf = self._create_tax("IGTF 3%", 3.0)

        self.env["account.tax"]._l10n_ve_assign_appl_type()

        self.assertEqual(tax12.appl_type, "general")
        self.assertAlmostEqual(tax12.amount, 16.0)
        self.assertEqual(tax12.name, "IVA 16%")
        if "description" in tax12._fields:
            self.assertEqual(self._plain(tax12.description), "IVA 16% (ventas)")
        if "invoice_label" in tax12._fields:
            self.assertEqual(tax12.invoice_label, "IVA 16% (ventas)")
        self.assertEqual(tax8.appl_type, "reducido")
        self.assertAlmostEqual(tax8.amount, 8.0)
        self.assertEqual(tax8.name, "IVA 8%")
        if "description" in tax8._fields:
            self.assertEqual(self._plain(tax8.description), "IVA 8% (ventas)")
        self.assertEqual(tax0.appl_type, "exento")
        self.assertEqual(tax0.name, "Exento")
        if "description" in tax0._fields:
            self.assertEqual(self._plain(tax0.description), "Exento (ventas)")
        self.assertEqual(tax22.appl_type, "adicional")
        self.assertAlmostEqual(tax22.amount, 31.0)
        self.assertEqual(tax22.name, "IVA 31%")
        if "description" in tax22._fields:
            self.assertEqual(self._plain(tax22.description), "IVA 31% (ventas)")
        self.assertEqual(tax16.appl_type, "general")
        self.assertEqual(tax16.name, "IVA 16%")
        self.assertEqual(tax31.appl_type, "adicional")
        self.assertEqual(sdcf.appl_type, "sdcf")
        self.assertFalse(igtf.appl_type)

    def test_sets_iva_16_as_company_default_sale_and_purchase(self):
        sale_12 = self._create_tax("12%", 12.0, type_tax_use="sale")
        sale_22 = self._create_tax("22%", 22.0, type_tax_use="sale")
        purchase_12 = self._create_tax("12%", 12.0, type_tax_use="purchase")
        purchase_22 = self._create_tax("22%", 22.0, type_tax_use="purchase")
        self.company.write(
            {
                "account_sale_tax_id": sale_22.id,
                "account_purchase_tax_id": purchase_22.id,
            }
        )

        self.env["account.tax"]._l10n_ve_assign_appl_type()

        self.assertEqual(self.company.account_sale_tax_id, sale_12)
        self.assertEqual(self.company.account_purchase_tax_id, purchase_12)
        self.assertEqual(sale_12.name, "IVA 16%")
        self.assertEqual(purchase_12.name, "IVA 16%")
        if "description" in purchase_12._fields:
            self.assertEqual(self._plain(purchase_12.description), "IVA 16% (compras)")
        self.assertAlmostEqual(sale_12.amount, 16.0)
        self.assertAlmostEqual(purchase_12.amount, 16.0)

    def test_does_not_overwrite_manual_appl_type(self):
        tax = self._create_tax("8% marked", 8.0)
        tax.appl_type = "general"
        self.env["account.tax"]._l10n_ve_assign_appl_type()
        self.assertEqual(tax.appl_type, "general")
        self.assertAlmostEqual(tax.amount, 8.0)
