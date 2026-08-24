# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tools import is_html_empty

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderPortalNoteVe(L10nVeSeniatCommon):
    def test_l10n_ve_seniat_note_includes_igtf_when_taxpayer_not_ordinary(self):
        company_vals = {"taxpayer_type": "special"}
        if "l10n_ve_igtf_account_id" in self.env.company._fields:
            igtf_account = False
            if hasattr(self.env.company, "_l10n_ve_get_default_igtf_account"):
                igtf_account = self.env.company._l10n_ve_get_default_igtf_account()
            if not igtf_account:
                igtf_account = self.env["account.account"].create(
                    {
                        "name": "IGTF Test Payable",
                        "code": "2102098",
                        "account_type": "liability_current",
                        "company_ids": [(6, 0, self.env.company.ids)],
                    }
                )
            company_vals["l10n_ve_igtf_account_id"] = igtf_account.id
        self.env.company.with_context(l10n_ve_skip_igtf_account_check=True).write(
            company_vals
        )
        self.assertEqual(self.env.company.taxpayer_type, "special")
        self.assertTrue(self.env.company._l10n_ve_invoice_tag_include_igtf_notice())
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente portal VE",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345681",
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Prod portal",
                "list_price": 10.0,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        self.assertEqual(order.country_code, "VE")
        self.assertTrue(order.l10n_ve_seniat_note)
        self.assertIn("IGTF", order.l10n_ve_seniat_note)

    def test_l10n_ve_seniat_note_false_when_ordinary_taxpayer_only_igtf_branch(self):
        self.env.company.with_context(l10n_ve_skip_igtf_account_check=True).write(
            {"taxpayer_type": "ordinary"}
        )
        self.assertEqual(self.env.company.taxpayer_type, "ordinary")
        self.assertFalse(self.env.company._l10n_ve_invoice_tag_include_igtf_notice())
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente ordinario",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345682",
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Prod ord",
                "list_price": 5.0,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )
        self.assertFalse(order.l10n_ve_seniat_note)

    def test_l10n_ve_portal_preview_shows_no_fiscal_markers(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente portal VE",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345683",
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Prod portal",
                "list_price": 10.0,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        html = self.env["ir.qweb"]._render(
            order._get_name_portal_content_view(),
            {
                "sale_order": order,
                "report_type": "html",
                "is_html_empty": is_html_empty,
            },
        )
        html_text = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn("Sin derecho a crédito fiscal", html_text)
        self.assertIn("NO FISCAL", html_text)
