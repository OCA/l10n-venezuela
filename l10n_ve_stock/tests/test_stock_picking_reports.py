# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_stock_picking_dispatch_guide import TestL10nVeStockDispatchGuide


@tagged("post_install", "-at_install")
class TestL10nVeStockPickingReports(TestL10nVeStockDispatchGuide):
    def test_dispatch_guide_bound_to_stock_picking(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        self.assertEqual(dispatch_report.binding_model_id, picking_model)
        self.assertEqual(dispatch_report.binding_type, "report")

    def test_ve_outgoing_picking_allows_dispatch_guide_report(self):
        product = self._create_product(
            name="Prod reportes",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        valid_ids = dispatch_report.get_valid_action_reports(
            "stock.picking", picking.ids
        )
        self.assertIn(dispatch_report.id, valid_ids)

    def test_dispatch_guide_not_in_print_actions_before_delivery_done(self):
        product = self._create_product(
            name="Prod acciones print",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        valid_ids = dispatch_report.get_valid_action_reports(
            "stock.picking", picking.ids
        )
        self.assertNotIn(dispatch_report.id, valid_ids)
        self.assertFalse(picking._l10n_ve_dispatch_guide_print_available())

    def test_do_print_picking_prints_dispatch_guide_for_ve_outgoing(self):
        product = self._create_product(
            name="Prod print btn",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        self.assertEqual(picking.state, "done")
        action = picking.action_l10n_ve_print_dispatch_guide()
        self.assertEqual(
            action.get("report_name"),
            "l10n_ve_stock.report_dispatch_guide",
        )

    def test_do_print_picking_uses_standard_report_when_dispatch_disabled(self):
        self.env.company.l10n_ve_dispatch_guide_enabled = False
        product = self._create_product(
            name="Prod print estándar",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        picking.move_ids.quantity = picking.move_ids.product_uom_qty
        picking.move_ids.picked = True
        picking.button_validate()
        action = picking.with_context(discard_logo_check=True).do_print_picking()
        self.assertEqual(action.get("report_name"), "stock.report_picking")

    def test_delivery_report_does_not_duplicate_recipient_data(self):
        combined_arch = self.env.ref(
            "stock.report_delivery_document"
        )._get_combined_arch()
        arch_text = etree.tostring(combined_arch, encoding="unicode")

        self.assertNotIn("div_partner_name", arch_text)
        self.assertNotIn("div_partner_rif", arch_text)

    def test_delivery_report_uses_contact_or_parent_vat(self):
        combined_arch = self.env.ref(
            "stock.report_delivery_document"
        )._get_combined_arch()
        arch_text = etree.tostring(combined_arch, encoding="unicode")

        self.assertIn("outgoing_delivery_vat", arch_text)
        self.assertIn("delivery_contact.commercial_partner_id.vat", arch_text)

    def test_delivery_report_uses_dispatch_guide_title(self):
        combined_arch = self.env.ref(
            "stock.report_delivery_document"
        )._get_combined_arch()
        arch_text = etree.tostring(combined_arch, encoding="unicode")

        self.assertIn("GUIA DE DESPACHO - ", arch_text)
        self.assertNotIn("Guía de Despacho: ", arch_text)

    def test_portal_picking_control_number_display(self):
        product = self._create_product(
            name="Prod portal label",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        self.assertTrue(picking.l10n_ve_control_number)
        self.assertEqual(
            picking.l10n_ve_portal_control_number_display(),
            picking.l10n_ve_control_number,
        )

    def test_portal_template_shows_control_number(self):
        product = self._create_product(
            name="Prod portal qweb",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        order = self._prepare_outgoing_sale_picking(product, 1).sale_id
        picking = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing"
        )[:1]
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        combined_arch = self.env.ref(
            "sale.sale_order_portal_content"
        )._get_combined_arch()
        arch_text = etree.tostring(combined_arch, encoding="unicode")
        self.assertIn("l10n_ve_portal_control_number_display", arch_text)
        self.assertNotIn("l10n_ve_portal_dispatch_guides", arch_text)
        from odoo.tools import is_html_empty

        html = self.env["ir.qweb"]._render(
            "sale.sale_order_portal_content",
            {
                "sale_order": order,
                "report_type": "html",
                "product_documents": order._get_product_documents(),
                "is_html_empty": is_html_empty,
            },
        )
        html_text = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn(picking.l10n_ve_control_number, html_text)
        self.assertIn("N° de control:", html_text)
        self.assertIn("Last Delivery Orders", html_text)

    def test_portal_invoice_control_number_on_invoices_only(self):
        product = self._create_product(
            name="Prod portal facturado",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        product.invoice_policy = "order"
        picking = self._prepare_outgoing_sale_picking(product, 1)
        invoice = picking.sale_id._create_invoices()
        invoice.action_post()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        self.assertFalse((picking.l10n_ve_control_number or "").strip())
        self.assertFalse(picking.l10n_ve_portal_control_number_display())
        self.assertEqual(
            invoice.l10n_ve_portal_control_number_display(),
            (invoice.l10n_ve_control_number or "").strip(),
        )
        from odoo.tools import is_html_empty

        html = self.env["ir.qweb"]._render(
            "sale.sale_order_portal_content",
            {
                "sale_order": picking.sale_id,
                "report_type": "html",
                "product_documents": picking.sale_id._get_product_documents(),
                "is_html_empty": is_html_empty,
            },
        )
        html_text = html.decode() if isinstance(html, bytes) else str(html)
        invoice_display = invoice.l10n_ve_portal_control_number_display()
        invoice_idx = html_text.find("Last Invoices")
        delivery_idx = html_text.find("Last Delivery Orders")
        self.assertGreater(invoice_idx, -1)
        self.assertGreater(delivery_idx, -1)
        self.assertLess(invoice_idx, delivery_idx)
        invoice_block = html_text[invoice_idx:delivery_idx]
        delivery_block = html_text[delivery_idx : delivery_idx + 1000]
        if invoice_display:
            self.assertIn(invoice_display, html_text)
            self.assertIn(invoice_display, invoice_block)
        self.assertNotIn("N° de control", delivery_block)

    def test_dispatch_guide_print_blocked_before_delivery_done(self):
        product = self._create_product(
            name="Prod print bloqueado",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        with self.assertRaises(UserError):
            picking.action_l10n_ve_print_dispatch_guide()

    def test_internal_picking_has_no_print_reports(self):
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if not picking_type:
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.env.company.id)], limit=1
            )
            self.assertTrue(warehouse)
            picking_type = self.env["stock.picking.type"].create(
                {
                    "name": "Internal Transfers Test",
                    "code": "internal",
                    "sequence_code": "INTT",
                    "company_id": self.env.company.id,
                    "warehouse_id": warehouse.id,
                    "default_location_src_id": warehouse.lot_stock_id.id,
                    "default_location_dest_id": warehouse.lot_stock_id.id,
                }
            )
        self.assertTrue(picking_type)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
        )
        report_model = self.env["ir.actions.report"]
        domain_reports = report_model.search(
            [
                ("model", "=", "stock.picking"),
                ("report_type", "=", "qweb-pdf"),
                ("binding_model_id.model", "=", "stock.picking"),
                ("domain", "!=", False),
            ]
        )
        valid_ids = domain_reports.get_valid_action_reports(
            "stock.picking", picking.ids
        )
        self.assertEqual(valid_ids, [])

    def test_extra_picking_report_keeps_binding_on_create(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        extra_report = self.env["ir.actions.report"].create(
            {
                "name": "Reporte extra test",
                "model": "stock.picking",
                "report_type": "qweb-pdf",
                "report_name": "l10n_ve_stock.report_extra_test",
                "binding_model_id": picking_model.id,
                "binding_type": "report",
            }
        )
        self.assertEqual(extra_report.binding_model_id, picking_model)
        self.assertEqual(extra_report.binding_type, "report")

    def test_dispatch_guide_shows_company_header_without_control_number(self):
        product = self._create_product(name="Prod header guía", is_storable=True)
        product.invoice_policy = "order"
        picking = self._prepare_outgoing_sale_picking(product, 1)
        invoice = picking.sale_id._create_invoices()
        invoice.action_post()
        self.assertFalse((picking.l10n_ve_control_number or "").strip())
        self.assertTrue(picking._l10n_ve_dispatch_guide_shows_company_header())

    def test_dispatch_guide_hides_company_header_with_control_number(self):
        picking = self._create_ve_sale_and_validate_delivery()
        self.assertTrue(picking.l10n_ve_control_number)
        self.assertFalse(picking._l10n_ve_dispatch_guide_shows_company_header())

    def test_dispatch_guide_paperformat_letter_when_no_talonario(self):
        product = self._create_product(
            name="Prod formato guía",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        product.invoice_policy = "order"
        picking = self._prepare_outgoing_sale_picking(product, 1)
        invoice = picking.sale_id._create_invoices()
        invoice.action_post()
        paperformat = picking._l10n_ve_dispatch_guide_paperformat()
        letter_format = self.env.ref(
            "l10n_ve_stock.paperformat_l10n_ve_dispatch_guide_letter"
        )
        self.assertEqual(paperformat, letter_format)
        self.assertEqual(paperformat.format, "Letter")
        self.assertEqual(paperformat.margin_top, 7)

    def test_dispatch_guide_paperformat_uses_book_when_has_talonario(self):
        picking = self._create_ve_sale_and_validate_delivery()
        section = picking._l10n_ve_dispatch_guide_section()
        self.assertTrue(section)
        book = section.book_id
        book._l10n_ve_ensure_paperformat()
        self.assertTrue(book.paperformat_id)
        paperformat = picking._l10n_ve_dispatch_guide_paperformat()
        self.assertEqual(paperformat, book.paperformat_id)
        self.assertNotEqual(
            paperformat,
            self.env.ref("l10n_ve_stock.paperformat_l10n_ve_dispatch_guide_letter"),
        )

    def _ensure_product_stock(self, product, qty=10.0):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        self.env["stock.quant"]._update_available_quantity(
            product, warehouse.lot_stock_id, qty
        )

    def test_dispatch_guide_shows_sale_global_discount(self):
        if "l10n.ve.sale.order.discount" not in self.env:
            self.skipTest("requires l10n_ve_sale_loyalty")
        journal = self.company_data["default_journal_sale"]
        if "l10n_ve_emission_medium" in journal._fields:
            self._l10n_ve_configure_journal_digital(journal)
        product = self._create_product(
            name="Prod desc global guía",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        self._ensure_product_stock(product)
        picking = self._prepare_outgoing_sale_picking(product, 1)
        order = picking.sale_id
        reason = self.env["l10n.ve.discount.reason"]._l10n_ve_get_default()
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": "Descuento"})
        subtotal = sum(
            line.price_subtotal for line in order.order_line if not line.display_type
        )
        self.env["l10n.ve.sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "reason_id": reason.id,
                "amount": subtotal * 0.1,
                "discount_type": "percentage",
                "discount_percentage": 0.1,
            }
        )
        self.assertTrue(order.l10n_ve_global_discount_ids)
        self.assertGreater(picking.l10n_ve_dispatch_display_discount, 0.0)
        amount, currency, lines = picking._l10n_ve_dispatch_guide_discount_display()
        self.assertAlmostEqual(amount, picking.l10n_ve_dispatch_display_discount)
        self.assertEqual(currency, order.currency_id)
        self.assertTrue(lines)
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_stock.report_dispatch_guide", picking.ids
        )[0]
        html = report_html.decode() if isinstance(report_html, bytes) else report_html
        self.assertIn("Subtotal:", html)
        self.assertIn("Descuento", html)

    def test_dispatch_guide_shows_product_line_discount(self):
        if "sale_discount_product_id" not in self.env["res.company"]._fields:
            self.skipTest("sale_discount_product_id requires sale module")
        journal = self.company_data["default_journal_sale"]
        if "l10n_ve_emission_medium" in journal._fields:
            self._l10n_ve_configure_journal_digital(journal)
        product = self._create_product(
            name="Prod desc línea guía",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        self._ensure_product_stock(product)
        picking = self._prepare_outgoing_sale_picking(product, 1)
        order = picking.sale_id
        product_subtotal = sum(
            line.price_subtotal for line in order.order_line if not line.display_type
        )
        discount_amount = product_subtotal * 0.1
        discount_product = self.env["product.product"].create(
            {
                "name": "Descuento producto guía",
                "type": "service",
                "list_price": 1.0,
                "company_id": self.env.company.id,
            }
        )
        self.env.company.sale_discount_product_id = discount_product
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": discount_product.id,
                "name": "Descuento promocional",
                "product_uom_qty": 1.0,
                "price_unit": -discount_amount,
            }
        )
        if "l10n_ve_global_discount_ids" in order._fields:
            self.assertFalse(order.l10n_ve_global_discount_ids)
        self.assertGreater(picking.l10n_ve_dispatch_display_discount, 0.0)
        self.assertGreater(picking.l10n_ve_dispatch_display_subtotal, 0.0)
        report_html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_stock.report_dispatch_guide", picking.ids
        )[0]
        html = report_html.decode() if isinstance(report_html, bytes) else report_html
        self.assertIn("Subtotal:", html)
        self.assertIn("Descuento", html)
