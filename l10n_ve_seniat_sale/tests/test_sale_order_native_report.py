# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderNativeReport(L10nVeSeniatCommon):
    def _create_ve_sale_order(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente informe nativo",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345682",
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Producto informe",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            }
        )
        return self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

    def _render_native_sale_report(self, order):
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder", order.ids
        )[0]
        return report_html.decode() if isinstance(report_html, bytes) else report_html

    def test_native_sale_report_is_bound(self):
        reports = self.env["ir.actions.report"].search(
            [
                ("model", "=", "sale.order"),
                ("report_type", "=", "qweb-pdf"),
                ("binding_model_id.model", "=", "sale.order"),
            ]
        )
        report_names = set(reports.mapped("report_name"))
        self.assertIn("sale.report_saleorder", report_names)

    def test_native_sale_report_shows_no_fiscal_markers(self):
        order = self._create_ve_sale_order()
        html = self._render_native_sale_report(order)
        self.assertIn("NO FISCAL", html)
        self.assertIn("Sin derecho a cr\u00e9dito fiscal", html)

    def test_native_sale_report_places_code_before_description(self):
        order = self._create_ve_sale_order()
        html = self._render_native_sale_report(order)
        self.assertLess(
            html.index('name="th_line_number"'),
            html.index('name="th_default_code"'),
        )
        self.assertLess(
            html.index('name="th_default_code"'),
            html.index('name="th_description"'),
        )
        self.assertLess(
            html.index('name="td_line_number"'),
            html.index('name="td_default_code"'),
        )
        self.assertLess(
            html.index('name="td_default_code"'),
            html.index('name="td_name"'),
        )

    def test_native_sale_report_uses_product_name_as_description(self):
        order = self._create_ve_sale_order()
        order.order_line.name = "Custom line description"
        html = self._render_native_sale_report(order)
        self.assertIn("Producto informe", html)
        self.assertNotIn("Custom line description", html)

    def test_ve_quote_native_report_shows_totals(self):
        order = self._create_ve_sale_order()
        self.assertIn(order.state, ("draft", "sent"))
        html = self._render_native_sale_report(order)
        self.assertIn("Presupuesto -", html)
        self.assertIn('name="so_total_summary"', html)

    def test_ve_sent_quote_native_report_shows_totals(self):
        order = self._create_ve_sale_order()
        order.state = "sent"
        html = self._render_native_sale_report(order)
        self.assertIn('name="so_total_summary"', html)

    def test_ve_confirmed_sale_order_native_report_hides_totals(self):
        order = self._create_ve_sale_order()
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        html = self._render_native_sale_report(order)
        self.assertIn("Pedido de venta -", html)
        self.assertNotIn('name="so_total_summary"', html)

    def test_ve_sale_report_uses_native_fiscal_markers_without_pba_layout(self):
        order = self._create_ve_sale_order()
        standard_layout = self.env.ref(
            "web.external_layout_standard", raise_if_not_found=False
        )
        if standard_layout:
            self.env.company.external_report_layout_id = standard_layout
        html = self._render_native_sale_report(order)
        self.assertIn("NO FISCAL", html)
        self.assertNotIn("o_pba_presupuesto_pdf_header", html)
