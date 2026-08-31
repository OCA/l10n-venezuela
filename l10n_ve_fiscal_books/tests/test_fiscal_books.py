# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
import io
from datetime import datetime, time, timedelta

import openpyxl
import pytz

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestFiscalBooks(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        country_ve = cls.env.ref("base.ve")
        cls.change_company_country(cls.company, country_ve)
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.sale_journal.l10n_ve_emission_medium = "free"
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager")
        partner_model = cls.env["res.partner"].with_context(no_vat_validation=True)
        cls.partner = partner_model.create(
            {
                "name": "Cliente de Prueba VE, C.A.",
                "vat": "J-12345678-9",
                "country_id": country_ve.id,
            }
        )
        cls.vendor = partner_model.create(
            {
                "name": "Proveedor de Prueba VE, C.A.",
                "vat": "J-98765432-1",
                "country_id": country_ve.id,
            }
        )
        cls.tax_group = cls.env["account.tax.group"].create(
            {"name": "IVA de prueba", "company_id": cls.company.id}
        )
        cls.sale_tax = cls.env["account.tax"].create(
            {
                "name": "IVA 16% (Ventas) - prueba",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        cls.purchase_tax = cls.env["account.tax"].create(
            {
                "name": "IVA 16% (Compras) - prueba",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": cls.company.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        today = fields.Date.today()
        cls.date_from = today.replace(day=1)
        cls.date_to = today
        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "invoice_date": today,
                "l10n_ve_control_number": "00-00000001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Servicio de prueba",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(cls.sale_tax.ids)],
                        }
                    )
                ],
            }
        )
        cls.invoice.action_post()
        cls.bill = cls.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": cls.vendor.id,
                "invoice_date": today,
                "ref": "FACT-PROV-0001",
                "l10n_ve_control_number": "00-00000002",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Insumo de prueba",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set(cls.purchase_tax.ids)],
                        }
                    )
                ],
            }
        )
        cls.bill.action_post()
        cls.pos_config = (
            cls.env["pos.config"]
            .sudo()
            .create(
                {
                    "name": "POS Libros VE",
                    "company_id": cls.company.id,
                    "l10n_ve_machine_serial": "Z1B1234567",
                }
            )
        )
        cls.pos_session = (
            cls.env["pos.session"]
            .sudo()
            .create({"config_id": cls.pos_config.id, "user_id": cls.env.uid})
        )

    def _make_wizard(self, book_type):
        return self.env["l10n.ve.fiscal.book.wizard"].create(
            {
                "date_from": self.date_from,
                "date_to": self.date_to,
                "book_type": book_type,
            }
        )

    def _generate(self, book_type):
        wizard = self._make_wizard(book_type)
        result = wizard.action_generate()
        self.assertEqual(result["res_id"], wizard.id)
        return wizard

    @staticmethod
    def _extract_cell_values(file_b64):
        workbook = openpyxl.load_workbook(
            io.BytesIO(base64.b64decode(file_b64)), read_only=True
        )
        return {
            str(cell.value)
            for sheet in workbook.worksheets
            for row in sheet.iter_rows()
            for cell in row
            if cell.value is not None
        }

    def _create_pos_order(self, name, date_order, price=100.0):
        tax_amount = round(price * self.sale_tax.amount / 100.0, 2)
        total = price + tax_amount
        return self.env["pos.order"].create(
            {
                "name": name,
                "session_id": self.pos_session.id,
                "company_id": self.company.id,
                "date_order": date_order,
                "pos_reference": name,
                "sequence_number": 1,
                "amount_tax": tax_amount,
                "amount_total": total,
                "amount_paid": total,
                "amount_return": 0.0,
                "state": "paid",
                "lines": [
                    Command.create(
                        {
                            "name": f"{name}-1",
                            "product_id": self.product_a.id,
                            "qty": 1.0,
                            "price_unit": price,
                            "price_subtotal": price,
                            "price_subtotal_incl": total,
                            "tax_ids": [Command.set(self.sale_tax.ids)],
                        }
                    )
                ],
            }
        )

    @staticmethod
    def _local_to_utc(local_datetime, timezone_name="America/Caracas"):
        timezone = pytz.timezone(timezone_name)
        return (
            timezone.localize(local_datetime).astimezone(pytz.utc).replace(tzinfo=None)
        )

    def _create_customer_invoice(self, journal=None, control_number=False, price=10.0):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.date_to,
                "journal_id": (journal or self.sale_journal).id,
                "l10n_ve_control_number": control_number,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Venta de prueba",
                            "quantity": 1.0,
                            "price_unit": price,
                            "tax_ids": [Command.set(self.sale_tax.ids)],
                        }
                    )
                ],
            }
        )

    def test_sale_book(self):
        wizard = self._generate("sale")
        self.assertTrue(wizard.file)
        self.assertTrue(wizard.filename.startswith("libro_ventas_"))
        self.assertTrue(wizard.filename.endswith(".xlsx"))
        self.assertEqual(base64.b64decode(wizard.file)[:2], b"PK")
        values = self._extract_cell_values(wizard.file)
        self.assertIn("LIBRO DE VENTAS", values)
        self.assertIn(self.invoice.name, values)
        self.assertIn("00-00000001", values)
        self.assertIn(self.partner.vat, values)

    def test_purchase_book(self):
        wizard = self._generate("purchase")
        self.assertTrue(wizard.file)
        self.assertTrue(wizard.filename.startswith("libro_compras_"))
        self.assertEqual(base64.b64decode(wizard.file)[:2], b"PK")
        values = self._extract_cell_values(wizard.file)
        self.assertIn("LIBRO DE COMPRAS", values)
        self.assertIn("FACT-PROV-0001", values)
        self.assertIn("00-00000002", values)
        self.assertIn(self.vendor.vat, values)

    def test_refund_referenced(self):
        reversal = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=self.invoice.ids)
            .create({"journal_id": self.invoice.journal_id.id, "reason": "Prueba NC"})
        )
        action = reversal.refund_moves()
        refund = self.env["account.move"].browse(action["res_id"])
        refund.action_post()
        values = self._extract_cell_values(self._generate("sale").file)
        self.assertIn(refund.name, values)
        self.assertIn("03", values)

    def test_date_constraint(self):
        with self.assertRaises(ValidationError):
            self.env["l10n.ve.fiscal.book.wizard"].create(
                {
                    "date_from": self.date_to,
                    "date_to": self.date_from - timedelta(days=1),
                    "book_type": "sale",
                }
            )

    def test_control_number_not_copied(self):
        self.assertFalse(self.invoice.copy().l10n_ve_control_number)

    def test_pos_daily_block_timezone(self):
        self.env.user.tz = "America/Caracas"
        order_late = self._create_pos_order(
            "POS/TZ-IN",
            self._local_to_utc(datetime.combine(self.date_to, time(21, 0))),
        )
        order_eve = self._create_pos_order(
            "POS/TZ-OUT", datetime.combine(self.date_from, time(2, 0))
        )
        self.pos_session.state = "closed"
        wizard = self._make_wizard("sale")
        rows = wizard._get_pos_day_rows(wizard._get_ves_currency())
        days = [row["date"] for row in rows]
        self.assertIn(self.date_to, days)
        self.assertTrue(all(self.date_from <= day <= self.date_to for day in days))
        names = {
            name for row in rows for name in (row["first_order"], row["last_order"])
        }
        self.assertIn(order_late.name, names)
        self.assertNotIn(order_eve.name, names)

    def test_pos_invoiced_order_split_blocks(self):
        self.env.user.tz = "America/Caracas"
        midday = self._local_to_utc(datetime.combine(self.date_to, time(10, 0)))
        plain_order = self._create_pos_order("POS/NOINV", midday)
        invoiced_order = self._create_pos_order("POS/INV", midday, price=200.0)
        pos_invoice = self._create_customer_invoice(
            control_number="00-00000099", price=200.0
        )
        pos_invoice.action_post()
        invoiced_order.account_move = pos_invoice
        self.pos_session.state = "closed"
        wizard = self._make_wizard("sale")
        self.assertIn(pos_invoice, wizard._get_sale_moves())
        rows = wizard._get_pos_day_rows(wizard._get_ves_currency())
        names = {
            name for row in rows for name in (row["first_order"], row["last_order"])
        }
        self.assertIn(plain_order.name, names)
        self.assertNotIn(invoiced_order.name, names)
        values = self._extract_cell_values(self._generate("sale").file)
        self.assertIn(pos_invoice.name, values)
        self.assertIn("00-00000099", values)

    def test_purchase_book_wh_iva_voucher(self):
        voucher_model = self.env.get("l10n.ve.iva.wh.voucher")
        if voucher_model is None or not hasattr(
            voucher_model, "_l10n_ve_get_amount_for_move"
        ):
            self.skipTest("No compatible VAT withholding voucher model is installed")
        voucher = voucher_model.create(
            {
                "number": "20260700000001",
                "date": self.date_to,
                "company_id": self.company.id,
                "partner_id": self.vendor.id,
                "move_ids": [Command.set(self.bill.ids)],
                "base_amount": 50.0,
                "tax_amount": 8.0,
                "withheld_amount": 6.0,
                "wh_rate": 75.0,
                "state": "posted",
            }
        )
        wizard = self._make_wizard("purchase")
        ves = wizard._get_ves_currency()
        amount, numbers = wizard._get_wh_iva_data(self.bill, ves)
        self.assertEqual(numbers, voucher.number)
        self.assertAlmostEqual(
            amount, wizard._to_ves(6.0, ves, self.bill.date), places=2
        )
        voucher.action_cancel()
        self.assertEqual(wizard._get_wh_iva_data(self.bill, ves), (0.0, ""))
        values = self._extract_cell_values(self._generate("purchase").file)
        self.assertIn("IVA Retenido al Proveedor", values)

    def test_sale_book_wh_iva_received(self):
        payment_model = self.env["account.payment"]
        if "l10n_ve_iva_wh_received_amount" not in payment_model._fields:
            self.skipTest("No compatible received VAT withholding fields are installed")
        payment_values = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 104.0,
            "date": self.date_to,
            "journal_id": self.company_data["default_journal_bank"].id,
            "l10n_ve_iva_wh_received_amount": 12.0,
        }
        has_number = "l10n_ve_iva_wh_received_number" in payment_model._fields
        if has_number:
            payment_values["l10n_ve_iva_wh_received_number"] = "20260700000077"
        payment = payment_model.create(payment_values)
        payment.state = "in_process"
        self.invoice.matched_payment_ids = [Command.link(payment.id)]
        wizard = self._make_wizard("sale")
        ves = wizard._get_ves_currency()
        amount, numbers = wizard._get_wh_iva_received_data(self.invoice, ves)
        expected = wizard._to_ves(12.0, ves, payment.date, currency=payment.currency_id)
        self.assertAlmostEqual(amount, expected, places=2)
        if has_number:
            self.assertEqual(numbers, "20260700000077")
        self.assertAlmostEqual(
            wizard._prepare_move_row(self.invoice, ves)["wh_iva"], expected, places=2
        )
        payment.state = "canceled"
        self.assertEqual(wizard._get_wh_iva_received_data(self.invoice, ves)[0], 0.0)

    def test_control_free_without_channel(self):
        self.assertFalse(self.bill.journal_id.l10n_ve_emission_medium)
        self.bill.l10n_ve_control_number = "00-00000099"
        self.assertEqual(self.bill.l10n_ve_control_number, "00-00000099")

    def test_control_locked_for_assigned_channels(self):
        for medium in ("fiscal_machine", "digital"):
            with self.subTest(medium=medium):
                self.sale_journal.l10n_ve_emission_medium = medium
                invoice = self._create_customer_invoice()
                invoice.action_post()
                invoice._l10n_ve_assign_control_data("00-00009999")
                with self.assertRaises(UserError):
                    invoice.l10n_ve_control_number = "00-00008888"

    def test_control_write_once_for_forma_libre(self):
        self.sale_journal.l10n_ve_emission_medium = "free"
        invoice = self._create_customer_invoice(control_number="00-00007777")
        invoice.action_post()
        self.assertEqual(invoice.l10n_ve_control_number, "00-00007777")
        with self.assertRaises(UserError):
            invoice.l10n_ve_control_number = "00-00006666"

    def test_control_editable_before_post_in_contingency(self):
        self.sale_journal.l10n_ve_emission_medium = "contingency"
        invoice = self._create_customer_invoice(control_number="00-00005555")
        invoice.l10n_ve_control_number = "00-00004444"
        invoice.action_post()
        self.assertEqual(invoice.l10n_ve_control_number, "00-00004444")
        with self.assertRaises(UserError):
            invoice.l10n_ve_control_number = "00-00003333"

    def test_control_writeback_context_bypasses_guard(self):
        self.sale_journal.l10n_ve_emission_medium = "fiscal_machine"
        invoice = self._create_customer_invoice()
        invoice.action_post()
        invoice._l10n_ve_assign_control_data("00-00001326")
        self.assertEqual(invoice.l10n_ve_control_number, "00-00001326")

    def test_control_locked_on_create_for_assigned_channel(self):
        self.sale_journal.l10n_ve_emission_medium = "digital"
        invoice = self._create_customer_invoice()
        invoice.action_post()
        self.assertFalse(invoice.l10n_ve_control_number)
        invoice._l10n_ve_assign_control_data("00-00012345")
        self.assertEqual(invoice.l10n_ve_control_number, "00-00012345")

    def _combo_invoice(self, taxes, lines=None):
        lines = lines or [(100.0, taxes)]
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.date_to,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": f"Línea de prueba {index}",
                            "quantity": 1.0,
                            "price_unit": price,
                            "tax_ids": [Command.set(line_taxes.ids)],
                        }
                    )
                    for index, (price, line_taxes) in enumerate(lines)
                ],
            }
        )
        move.action_post()
        return move

    def test_move_row_combined_rate_31(self):
        tax15 = self.env["account.tax"].create(
            {
                "name": "IVA adicional 15% - prueba",
                "amount": 15.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group.id,
            }
        )
        group = self.env["account.tax"].create(
            {
                "name": "IVA 31% (grupo) - prueba",
                "amount_type": "group",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group.id,
                "children_tax_ids": [Command.set((self.sale_tax | tax15).ids)],
            }
        )
        wizard = self._make_wizard("sale")
        ves = wizard._get_ves_currency()
        for label, taxes in (
            ("two taxes", self.sale_tax | tax15),
            ("tax group", group),
        ):
            with self.subTest(combo=label):
                move = self._combo_invoice(taxes)
                row = wizard._prepare_move_row(move, ves)
                self.assertAlmostEqual(
                    row["base_31"],
                    wizard._to_ves(100.0, ves, move.date),
                    delta=0.02,
                )
                self.assertAlmostEqual(
                    row["tax_31"],
                    wizard._to_ves(31.0, ves, move.date),
                    delta=0.02,
                )
                self.assertEqual(row["base_16"], 0.0)
                self.assertEqual(row["tax_16"], 0.0)
                self.assertEqual(row["exempt"], 0.0)

    def test_move_row_negative_line_netted(self):
        move = self._combo_invoice(
            None,
            lines=[(100.0, self.sale_tax), (-20.0, self.sale_tax)],
        )
        wizard = self._make_wizard("sale")
        ves = wizard._get_ves_currency()
        row = wizard._prepare_move_row(move, ves)
        self.assertAlmostEqual(
            row["base_16"], wizard._to_ves(80.0, ves, move.date), delta=0.02
        )
        self.assertAlmostEqual(
            row["tax_16"], wizard._to_ves(12.8, ves, move.date), delta=0.02
        )
        self.assertAlmostEqual(
            row["total"], wizard._to_ves(92.8, ves, move.date), delta=0.02
        )
        self.assertEqual(row["exempt"], 0.0)

    def test_contingency_journal_created_and_unhashed(self):
        from ..hooks import create_contingency_journals

        create_contingency_journals(self.env)
        journal = self.env["account.journal"].search(
            [
                ("company_id", "=", self.company.id),
                ("l10n_ve_emission_medium", "=", "contingency"),
            ]
        )
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal.type, "sale")
        self.assertFalse(journal.restrict_mode_hash_table)
        self.assertTrue(journal.default_account_id)
        create_contingency_journals(self.env)
        self.assertEqual(
            len(
                self.env["account.journal"].search(
                    [
                        ("company_id", "=", self.company.id),
                        ("l10n_ve_emission_medium", "=", "contingency"),
                    ]
                )
            ),
            1,
        )

    def test_sale_book_splits_by_channel(self):
        self.sale_journal.l10n_ve_emission_medium = "fiscal_machine"
        machine_invoice = self._create_customer_invoice()
        machine_invoice.action_post()
        contingency = self.env["account.journal"].create(
            {
                "name": "Contingencia de prueba",
                "code": "CONTT",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self.sale_journal.default_account_id.id,
                "l10n_ve_emission_medium": "contingency",
            }
        )
        manual = self._create_customer_invoice(
            journal=contingency, control_number="00-00003333", price=70.0
        )
        manual.action_post()
        contingency.l10n_ve_emission_medium = "digital"
        values = self._extract_cell_values(self._generate("sale").file)
        self.assertIn("  Emitidas por máquina fiscal", values)
        self.assertIn("  Emitidas en contingencia (talonario)", values)
        self.assertIn("00-00003333", values)
        self.assertEqual(manual.l10n_ve_emission_medium, "contingency")

    def _make_batch(self, **extra):
        values = {
            "type": "talonario",
            "company_id": self.company.id,
            "control_from": "000001",
            "control_to": "000050",
            "invoice_from": "000001",
            "invoice_to": "000050",
            "printer_name": "Imprenta de Prueba, C.A.",
        }
        values.update(extra)
        return self.env["l10n.ve.paper.batch"].create(values)

    def _contingency_journal(self):
        return self.env["account.journal"].create(
            {
                "name": "Contingencia Batch Test",
                "code": "CONTB",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self.sale_journal.default_account_id.id,
                "l10n_ve_emission_medium": "contingency",
            }
        )

    def test_paper_batch_range_constraints(self):
        with self.assertRaises(ValidationError):
            self._make_batch(control_from="NO-DIGITS-")
        with self.assertRaises(ValidationError):
            self._make_batch(control_from="000010", control_to="000005")
        with self.assertRaises(ValidationError):
            self._make_batch(control_from="A-000001", control_to="B-000050")
        with self.assertRaises(ValidationError):
            self._make_batch(invoice_from=False)
        self._make_batch(type="forma_libre", invoice_from=False, invoice_to=False)

    def test_paper_batch_next_numbers(self):
        batch = self._make_batch()
        result = batch.next_numbers()
        self.assertEqual(result["control"], "000001")
        self.assertEqual(result["invoice"], "000001")
        self.assertFalse(result.get("error"))
        journal = self._contingency_journal()
        move = self._create_customer_invoice(journal=journal, control_number="000007")
        move.l10n_ve_paper_number = "000003"
        move.action_post()
        result = batch.next_numbers()
        self.assertEqual(result["control"], "000008")
        self.assertEqual(result["invoice"], "000004")
        order = self._create_pos_order("ORD/BATCH/1", fields.Datetime.now())
        order.write(
            {
                "l10n_ve_contingency_control": "000012",
                "l10n_ve_contingency_invoice_number": "000011",
            }
        )
        result = batch.next_numbers()
        self.assertEqual(result["control"], "000013")
        self.assertEqual(result["invoice"], "000012")
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": self.date_to,
                "ref": "FACT-PROV-9999",
                "l10n_ve_control_number": "105704110713",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra con control del proveedor",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "tax_ids": [Command.set(self.purchase_tax.ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        open_batch = self._make_batch(control_to=False, invoice_to=False)
        result = open_batch.next_numbers()
        self.assertEqual(result["control"], "000013")
        self.assertEqual(result["invoice"], "000012")

    def test_paper_batch_exhaustion_and_warning(self):
        batch = self._make_batch(control_to="000002", invoice_to="000002")
        self.assertTrue(batch.next_numbers()["warning"])
        order = self._create_pos_order("ORD/BATCH/2", fields.Datetime.now())
        order.write(
            {
                "l10n_ve_contingency_control": "000002",
                "l10n_ve_contingency_invoice_number": "000002",
            }
        )
        self.assertTrue(batch.next_numbers().get("error"))

    def test_paper_batch_check_numbers(self):
        batch = self._make_batch()
        self.assertFalse(batch.check_numbers("000001", "000001"))
        self.assertTrue(batch.check_numbers("A-000001", "000001"))
        self.assertTrue(batch.check_numbers("000001", "000099"))
        order = self._create_pos_order("ORD/BATCH/3", fields.Datetime.now())
        order.write({"l10n_ve_contingency_control": "000020"})
        self.assertTrue(batch.check_numbers("000001", "000020"))

    def test_pos_contingency_numbers_unique(self):
        order1 = self._create_pos_order("ORD/DUP/1", fields.Datetime.now())
        order1.write(
            {
                "l10n_ve_contingency_control": "000040",
                "l10n_ve_contingency_invoice_number": "000041",
            }
        )
        order2 = self._create_pos_order("ORD/DUP/2", fields.Datetime.now())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order2.write({"l10n_ve_contingency_control": "000040"})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            order2.write({"l10n_ve_contingency_invoice_number": "000041"})
        order1.write({"l10n_ve_contingency_control": "000040"})

    def test_sale_book_uses_paper_number_as_document(self):
        journal = self._contingency_journal()
        move = self._create_customer_invoice(journal=journal, control_number="000021")
        move.l10n_ve_paper_number = "000009"
        move.action_post()
        wizard = self._make_wizard("sale")
        ves = wizard._get_ves_currency()
        row = wizard._prepare_move_row(move, ves)
        self.assertEqual(row["number"], "000009")
        self.assertEqual(row["control"], "000021")
        self.assertEqual(
            wizard._prepare_move_row(self.invoice, ves)["number"], self.invoice.name
        )

    def test_contingency_block_uses_invoice_number(self):
        order = self._create_pos_order(
            "ORD/CONT/9",
            self._local_to_utc(datetime.combine(self.date_to, time(12, 0))),
        )
        order.write(
            {
                "l10n_ve_contingency_control": "000030",
                "l10n_ve_contingency_invoice_number": "000031",
            }
        )
        self.pos_session.sudo().write({"state": "closed"})
        wizard = self._make_wizard("sale")
        rows = wizard._get_pos_contingency_rows(wizard._get_ves_currency())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["number"], "000031")
        self.assertEqual(rows[0]["control"], "000030")
