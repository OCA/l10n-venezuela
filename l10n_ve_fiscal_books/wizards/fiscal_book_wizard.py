# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
import io
from datetime import datetime, time

import pytz
import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

AMOUNT_KEYS = (
    "total",
    "base_16",
    "tax_16",
    "base_8",
    "tax_8",
    "base_31",
    "tax_31",
    "exempt",
    "wh_iva",
)

CHANNEL_LABELS = (
    ("fiscal_machine", "Emitidas por máquina fiscal"),
    ("digital", "Emitidas por imprenta digital (medios electrónicos)"),
    ("free", "Emitidas sobre forma libre de imprenta autorizada"),
    ("contingency", "Emitidas en contingencia (talonario)"),
    (False, "Sin canal de emisión declarado"),
)


class L10nVeFiscalBookWizard(models.TransientModel):
    _name = "l10n.ve.fiscal.book.wizard"
    _description = "Venezuelan Fiscal Books Wizard"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string="From",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="To", required=True, default=lambda self: fields.Date.context_today(self)
    )
    book_type = fields.Selection(
        [("sale", "Sales Book"), ("purchase", "Purchase Book")],
        required=True,
        default="sale",
    )
    file = fields.Binary(string="Generated File", readonly=True)
    filename = fields.Char()

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise ValidationError(
                    self.env._(
                        "The start date must be before or equal to the end date."
                    )
                )

    def action_generate(self):
        self.ensure_one()
        ves = self._get_ves_currency()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        try:
            if self.book_type == "sale":
                self._write_sale_book(workbook, ves)
            else:
                self._write_purchase_book(workbook, ves)
        finally:
            workbook.close()
        label = "ventas" if self.book_type == "sale" else "compras"
        self.write(
            {
                "file": base64.b64encode(output.getvalue()),
                "filename": (
                    f"libro_{label}_{self.date_from.strftime('%Y%m%d')}"
                    f"_{self.date_to.strftime('%Y%m%d')}.xlsx"
                ),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Venezuelan Fiscal Books"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_ves_currency(self):
        ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not ves:
            raise UserError(
                self.env._(
                    "The VES currency is required to express fiscal books in "
                    "bolivars at the applicable exchange rate."
                )
            )
        return ves

    def _to_ves(self, amount, ves, date, currency=None):
        currency = currency or self.company_id.currency_id
        if not amount:
            return 0.0
        return currency._convert(amount, ves, self.company_id, date)

    @staticmethod
    def _rate_key(rate):
        for key, value in (("16", 16.0), ("8", 8.0), ("31", 31.0)):
            if abs(rate - value) < 0.011:
                return key
        return "16"

    @staticmethod
    def _get_doc_type(move):
        if move.move_type in ("out_refund", "in_refund"):
            return "03", move.reversed_entry_id.name or ""
        if "debit_origin_id" in move._fields and move.debit_origin_id:
            return "02", move.debit_origin_id.name or ""
        return "01", ""

    def _get_sale_moves(self):
        return self.env["account.move"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
            ],
            order="date, name",
        )

    def _get_purchase_moves(self):
        return self.env["account.move"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
            ],
            order="date, name",
        )

    def _prepare_move_row(self, move, ves):
        sign = -1.0 if move.move_type in ("out_refund", "in_refund") else 1.0
        factor = -1.0 if move.is_sale_document(include_receipts=True) else 1.0
        vals = dict.fromkeys(AMOUNT_KEYS, 0.0)
        tax_keys = {}
        exempt = 0.0
        for line in move.invoice_line_ids.filtered(
            lambda invoice_line: invoice_line.display_type == "product"
        ):
            amount = factor * line.balance
            leaf_taxes = line.tax_ids
            group_taxes = leaf_taxes.filtered(lambda tax: tax.amount_type == "group")
            leaf_taxes = (leaf_taxes - group_taxes) | group_taxes.children_tax_ids
            rate = round(sum(tax.amount for tax in leaf_taxes), 2)
            if not rate:
                exempt += amount
                continue
            key = self._rate_key(rate)
            vals[f"base_{key}"] += self._to_ves(amount, ves, move.date)
            for tax in leaf_taxes:
                if tax.amount:
                    shares = tax_keys.setdefault(tax.id, {})
                    shares[key] = shares.get(key, 0.0) + amount
        for line in move.line_ids.filtered("tax_line_id"):
            if not line.tax_line_id.amount:
                continue
            amount = factor * line.balance
            shares = tax_keys.get(line.tax_line_id.id) or {
                self._rate_key(line.tax_line_id.amount): 1.0
            }
            total_share = sum(shares.values())
            for key, share in shares.items():
                part = amount * share / total_share if total_share else 0.0
                vals[f"tax_{key}"] += self._to_ves(part, ves, move.date)
        vals["exempt"] = self._to_ves(exempt, ves, move.date)
        vals["total"] = sign * self._to_ves(
            abs(move.amount_total_signed), ves, move.date
        )
        doc_type, affected = self._get_doc_type(move)
        if move.move_type in ("in_invoice", "in_refund"):
            number = move.ref or move.name
            vals["wh_iva"], vals["wh_voucher"] = self._get_wh_iva_data(move, ves)
        else:
            number = move.l10n_ve_paper_number or move.name
            vals["wh_iva"], vals["wh_voucher"] = self._get_wh_iva_received_data(
                move, ves
            )
        partner = move.commercial_partner_id
        vals.update(
            {
                "date": move.invoice_date or move.date,
                "number": number,
                "control": move.l10n_ve_control_number or "",
                "partner": partner.name or "",
                "vat": partner.vat or "",
                "doc_type": doc_type,
                "affected": affected,
            }
        )
        return vals

    def _get_wh_iva_data(self, move, ves):
        """Return optional supplier VAT withholding data through its public API."""
        voucher_model = self.env.get("l10n.ve.iva.wh.voucher")
        if voucher_model is None or not hasattr(
            voucher_model, "_l10n_ve_get_amount_for_move"
        ):
            return 0.0, ""
        required_fields = {"company_id", "move_ids", "state", "number"}
        if not required_fields <= set(voucher_model._fields):
            return 0.0, ""
        vouchers = voucher_model.sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("move_ids", "in", move.id),
                ("state", "=", "posted"),
            ]
        )
        if not vouchers:
            return 0.0, ""
        amount = sum(voucher._l10n_ve_get_amount_for_move(move) for voucher in vouchers)
        numbers = ", ".join(number for number in vouchers.mapped("number") if number)
        return self._to_ves(amount, ves, move.date), numbers

    def _get_wh_iva_received_data(self, move, ves):
        """Return optional customer VAT withholding data from reconciled payments."""
        payment_model = self.env["account.payment"]
        if "l10n_ve_iva_wh_received_amount" not in payment_model._fields:
            return 0.0, ""
        amount = 0.0
        numbers = []
        payments = move.matched_payment_ids.filtered(
            lambda payment: payment.state not in ("draft", "canceled", "rejected")
        )
        for payment in payments:
            withholding = getattr(payment, "l10n_ve_iva_wh_received_amount", 0.0)
            if not withholding:
                continue
            sale_documents = payment.invoice_ids.filtered(
                lambda document: document.is_sale_document(include_receipts=True)
            )
            total = sum(
                abs(document.amount_total_signed) for document in sale_documents
            )
            share = abs(move.amount_total_signed) / total if total else 1.0
            amount += self._to_ves(
                withholding * share,
                ves,
                payment.date,
                currency=payment.currency_id,
            )
            number = getattr(payment, "l10n_ve_iva_wh_received_number", "") or ""
            if number and number not in numbers:
                numbers.append(number)
        return amount, ", ".join(numbers)

    def _period_utc_bounds(self):
        timezone_name = self.env.context.get("tz") or self.env.user.tz
        timezone = pytz.timezone(timezone_name) if timezone_name else pytz.utc
        start = (
            timezone.localize(datetime.combine(self.date_from, time.min))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        stop = (
            timezone.localize(datetime.combine(self.date_to, time.max))
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )
        return start, stop

    def _get_pos_day_rows(self, ves):
        start, stop = self._period_utc_bounds()
        orders = (
            self.env["pos.order"]
            .sudo()
            .search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("date_order", ">=", start),
                    ("date_order", "<=", stop),
                    ("state", "in", ("paid", "done")),
                    ("account_move", "=", False),
                    ("session_id.state", "=", "closed"),
                    ("l10n_ve_contingency_control", "=", False),
                ],
                order="date_order, name",
            )
        )
        groups = {}
        for order in orders:
            day = fields.Datetime.context_timestamp(self, order.date_order).date()
            key = (order.session_id.id, day)
            groups.setdefault(
                key, {"session": order.session_id, "day": day, "orders": []}
            )["orders"].append(order)
        rows = []
        for group in sorted(
            groups.values(), key=lambda value: (value["day"], value["session"].id)
        ):
            vals = dict.fromkeys(AMOUNT_KEYS, 0.0)
            day = group["day"]
            for order in group["orders"]:
                self._add_pos_order_amounts(vals, order, day, ves)
            vals["total"] = sum(
                vals[key] for key in AMOUNT_KEYS if key not in ("total", "wh_iva")
            )
            names = sorted(order.name or "" for order in group["orders"])
            config = group["session"].config_id
            vals.update(
                {
                    "date": day,
                    "machine": config.l10n_ve_machine_serial or config.name or "",
                    "session": group["session"].name or "",
                    "first_order": names[0],
                    "last_order": names[-1],
                }
            )
            rows.append(vals)
        return rows

    def _add_pos_order_amounts(self, vals, order, day, ves):
        currency = order.currency_id
        for line in order.lines:
            base = self._to_ves(line.price_subtotal, ves, day, currency=currency)
            tax_amount = self._to_ves(
                line.price_subtotal_incl - line.price_subtotal,
                ves,
                day,
                currency=currency,
            )
            taxes = line.tax_ids
            group_taxes = taxes.filtered(lambda tax: tax.amount_type == "group")
            taxes = (taxes - group_taxes) | group_taxes.children_tax_ids
            rate = round(sum(tax.amount for tax in taxes), 2)
            if rate:
                key = self._rate_key(rate)
                vals[f"base_{key}"] += base
                vals[f"tax_{key}"] += tax_amount
            else:
                vals["exempt"] += base + tax_amount

    def _get_pos_contingency_rows(self, ves):
        start, stop = self._period_utc_bounds()
        orders = (
            self.env["pos.order"]
            .sudo()
            .search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("date_order", ">=", start),
                    ("date_order", "<=", stop),
                    ("state", "in", ("paid", "done")),
                    ("account_move", "=", False),
                    ("session_id.state", "=", "closed"),
                    ("l10n_ve_contingency_control", "!=", False),
                ],
                order="date_order, name",
            )
        )
        rows = []
        for order in orders:
            day = fields.Datetime.context_timestamp(self, order.date_order).date()
            vals = dict.fromkeys(AMOUNT_KEYS, 0.0)
            self._add_pos_order_amounts(vals, order, day, ves)
            vals["total"] = sum(
                vals[key] for key in AMOUNT_KEYS if key not in ("total", "wh_iva")
            )
            partner = order.partner_id
            vals.update(
                {
                    "date": day,
                    "number": order.l10n_ve_contingency_invoice_number
                    or order.name
                    or "",
                    "control": order.l10n_ve_contingency_control or "",
                    "partner": partner.name or "CONSUMIDOR FINAL",
                    "vat": partner.vat or "",
                    "doc_type": "01",
                    "affected": "",
                    "wh_voucher": "",
                }
            )
            rows.append(vals)
        return rows

    @staticmethod
    def _get_formats(workbook):
        return {
            "title": workbook.add_format({"bold": True, "font_size": 13}),
            "bold": workbook.add_format({"bold": True}),
            "section": workbook.add_format(
                {"bold": True, "font_size": 11, "font_color": "#1F4E78"}
            ),
            "header": workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#D9E1F2",
                    "border": 1,
                    "text_wrap": True,
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "text": workbook.add_format({"border": 1}),
            "num": workbook.add_format({"border": 1, "num_format": "#,##0.00"}),
            "total_label": workbook.add_format(
                {"bold": True, "border": 1, "bg_color": "#F2F2F2"}
            ),
            "total_num": workbook.add_format(
                {
                    "bold": True,
                    "border": 1,
                    "bg_color": "#F2F2F2",
                    "num_format": "#,##0.00",
                }
            ),
        }

    def _write_book_header(self, sheet, formats, title):
        company = self.company_id
        sheet.write(0, 0, company.name or "", formats["title"])
        sheet.write(1, 0, f"RIF: {company.vat or ''}", formats["bold"])
        sheet.write(2, 0, title, formats["title"])
        sheet.write(
            3,
            0,
            "Período: "
            f"{self.date_from.strftime('%d/%m/%Y')} al "
            f"{self.date_to.strftime('%d/%m/%Y')} - montos expresados en Bs",
            formats["bold"],
        )
        return 5

    def _write_sale_detail_by_channel(self, sheet, formats, row, headers, ves):
        by_channel = {}
        for move in self._get_sale_moves():
            by_channel.setdefault(move.l10n_ve_emission_medium, []).append(move)
        totals = dict.fromkeys(AMOUNT_KEYS, 0.0)
        split = len(by_channel) > 1
        for channel, label in CHANNEL_LABELS:
            moves = by_channel.get(channel)
            if not moves:
                continue
            if split:
                sheet.write(row, 0, f"  {label}", formats["section"])
                row += 1
            move_rows = [self._prepare_move_row(move, ves) for move in moves]
            row, block = self._write_detail_table(
                sheet, formats, row, headers, move_rows, with_voucher=True
            )
            for key in AMOUNT_KEYS:
                totals[key] += block[key]
        return row, totals

    @staticmethod
    def _write_detail_table(
        sheet, formats, row, headers, move_rows, with_voucher=False
    ):
        for column, header in enumerate(headers):
            sheet.write(row, column, header, formats["header"])
        row += 1
        totals = dict.fromkeys(AMOUNT_KEYS, 0.0)
        for vals in move_rows:
            sheet.write(row, 0, vals["date"].strftime("%d/%m/%Y"), formats["text"])
            sheet.write(row, 1, vals["number"] or "", formats["text"])
            sheet.write(row, 2, vals["control"], formats["text"])
            sheet.write(row, 3, vals["partner"], formats["text"])
            sheet.write(row, 4, vals["vat"], formats["text"])
            sheet.write(row, 5, vals["doc_type"], formats["text"])
            sheet.write(row, 6, vals["affected"], formats["text"])
            for offset, key in enumerate(AMOUNT_KEYS):
                sheet.write_number(row, 7 + offset, round(vals[key], 2), formats["num"])
                totals[key] += vals[key]
            if with_voucher:
                sheet.write(
                    row,
                    7 + len(AMOUNT_KEYS),
                    vals["wh_voucher"],
                    formats["text"],
                )
            row += 1
        sheet.write(row, 0, "TOTALES", formats["total_label"])
        for column in range(1, 7):
            sheet.write(row, column, "", formats["total_label"])
        for offset, key in enumerate(AMOUNT_KEYS):
            sheet.write_number(
                row, 7 + offset, round(totals[key], 2), formats["total_num"]
            )
        if with_voucher:
            sheet.write(row, 7 + len(AMOUNT_KEYS), "", formats["total_label"])
        return row + 2, totals

    @staticmethod
    def _write_summary(sheet, formats, row, totals, tax_label, wh_label):
        sheet.write(row, 0, "RESUMEN DEL PERÍODO (Art. 72)", formats["section"])
        row += 1
        for column, header in enumerate(["Concepto", "Base Imponible", tax_label]):
            sheet.write(row, column, header, formats["header"])
        row += 1
        lines = [
            (
                "Operaciones gravadas - alícuota general 16%",
                totals["base_16"],
                totals["tax_16"],
            ),
            (
                "Operaciones gravadas - alícuota reducida 8%",
                totals["base_8"],
                totals["tax_8"],
            ),
            (
                "Operaciones gravadas - alícuota general + adicional 31%",
                totals["base_31"],
                totals["tax_31"],
            ),
            (
                "Operaciones exentas, exoneradas o no sujetas",
                totals["exempt"],
                0.0,
            ),
        ]
        for label, base, tax in lines:
            sheet.write(row, 0, label, formats["text"])
            sheet.write_number(row, 1, round(base, 2), formats["num"])
            sheet.write_number(row, 2, round(tax, 2), formats["num"])
            row += 1
        total_base = (
            totals["base_16"] + totals["base_8"] + totals["base_31"] + totals["exempt"]
        )
        total_tax = totals["tax_16"] + totals["tax_8"] + totals["tax_31"]
        sheet.write(row, 0, "TOTALES", formats["total_label"])
        sheet.write_number(row, 1, round(total_base, 2), formats["total_num"])
        sheet.write_number(row, 2, round(total_tax, 2), formats["total_num"])
        row += 1
        sheet.write(row, 0, wh_label, formats["total_label"])
        sheet.write(row, 1, "", formats["total_label"])
        sheet.write_number(row, 2, round(totals["wh_iva"], 2), formats["total_num"])
        return row + 1

    def _write_sale_book(self, workbook, ves):
        formats = self._get_formats(workbook)
        sheet = workbook.add_worksheet("Libro de Ventas")
        sheet.set_column(0, 0, 11)
        sheet.set_column(1, 2, 18)
        sheet.set_column(3, 3, 40)
        sheet.set_column(4, 4, 14)
        sheet.set_column(5, 5, 9)
        sheet.set_column(6, 6, 18)
        sheet.set_column(7, 15, 15)
        sheet.set_column(16, 16, 22)
        row = self._write_book_header(sheet, formats, "LIBRO DE VENTAS")

        sheet.write(
            row,
            0,
            "I. VENTAS A CONTRIBUYENTES - una fila por documento (Art. 76)",
            formats["section"],
        )
        row += 1
        headers = [
            "Fecha",
            "Nº de Documento",
            "Nº de Control",
            "Razón Social",
            "RIF",
            "Tipo Doc.",
            "Nº Doc. Afectado",
            "Total Documento",
            "Base Gravada 16%",
            "IVA 16%",
            "Base Gravada 8%",
            "IVA 8%",
            "Base Gravada 31%",
            "IVA 31%",
            "Exento/No Gravado",
            "IVA Retenido",
            "Nº Comprobante de Retención",
        ]
        row, block1 = self._write_sale_detail_by_channel(
            sheet, formats, row, headers, ves
        )

        sheet.write(
            row,
            0,
            "II. VENTAS A NO CONTRIBUYENTES - resumen diario por máquina/"
            "sesión POS (Art. 77)",
            formats["section"],
        )
        row += 1
        headers2 = [
            "Fecha",
            "Nº Registro de Máquina",
            "Sesión",
            "Primera Orden del Día",
            "Última Orden del Día",
            "Total Gravado",
            "IVA",
            "Exento/No Gravado",
        ]
        for column, header in enumerate(headers2):
            sheet.write(row, column, header, formats["header"])
        row += 1
        pos_rows = self._get_pos_day_rows(ves)
        block2 = dict.fromkeys(AMOUNT_KEYS, 0.0)
        for vals in pos_rows:
            taxable = vals["base_16"] + vals["base_8"] + vals["base_31"]
            tax = vals["tax_16"] + vals["tax_8"] + vals["tax_31"]
            sheet.write(row, 0, vals["date"].strftime("%d/%m/%Y"), formats["text"])
            sheet.write(row, 1, vals["machine"], formats["text"])
            sheet.write(row, 2, vals["session"], formats["text"])
            sheet.write(row, 3, vals["first_order"], formats["text"])
            sheet.write(row, 4, vals["last_order"], formats["text"])
            sheet.write_number(row, 5, round(taxable, 2), formats["num"])
            sheet.write_number(row, 6, round(tax, 2), formats["num"])
            sheet.write_number(row, 7, round(vals["exempt"], 2), formats["num"])
            for key in AMOUNT_KEYS:
                block2[key] += vals[key]
            row += 1
        sheet.write(row, 0, "TOTALES", formats["total_label"])
        for column in range(1, 5):
            sheet.write(row, column, "", formats["total_label"])
        sheet.write_number(
            row,
            5,
            round(block2["base_16"] + block2["base_8"] + block2["base_31"], 2),
            formats["total_num"],
        )
        sheet.write_number(
            row,
            6,
            round(block2["tax_16"] + block2["tax_8"] + block2["tax_31"], 2),
            formats["total_num"],
        )
        sheet.write_number(row, 7, round(block2["exempt"], 2), formats["total_num"])
        row += 2

        contingency_rows = self._get_pos_contingency_rows(ves)
        block3 = dict.fromkeys(AMOUNT_KEYS, 0.0)
        if contingency_rows:
            sheet.write(
                row,
                0,
                "III. VENTAS EN CONTINGENCIA - facturadas en talonario "
                "autorizado (PA 0071 Art. 11)",
                formats["section"],
            )
            row += 1
            row, block3 = self._write_detail_table(
                sheet,
                formats,
                row,
                headers,
                contingency_rows,
                with_voucher=True,
            )

        combined = {key: block1[key] + block2[key] + block3[key] for key in AMOUNT_KEYS}
        self._write_summary(
            sheet,
            formats,
            row,
            combined,
            tax_label="Débito Fiscal",
            wh_label="IVA retenido por agentes de retención",
        )

    def _write_purchase_book(self, workbook, ves):
        formats = self._get_formats(workbook)
        sheet = workbook.add_worksheet("Libro de Compras")
        sheet.set_column(0, 0, 11)
        sheet.set_column(1, 2, 18)
        sheet.set_column(3, 3, 40)
        sheet.set_column(4, 4, 14)
        sheet.set_column(5, 5, 9)
        sheet.set_column(6, 6, 18)
        sheet.set_column(7, 15, 15)
        sheet.set_column(16, 16, 22)
        row = self._write_book_header(sheet, formats, "LIBRO DE COMPRAS")

        sheet.write(
            row,
            0,
            "COMPRAS NACIONALES E IMPORTACIONES - una fila por documento (Art. 75)",
            formats["section"],
        )
        row += 1
        headers = [
            "Fecha",
            "Nº de Factura",
            "Nº de Control",
            "Proveedor",
            "RIF",
            "Tipo Doc.",
            "Nº Doc. Afectado",
            "Total Documento",
            "Base Gravada 16%",
            "Crédito Fiscal 16%",
            "Base Gravada 8%",
            "Crédito Fiscal 8%",
            "Base Gravada 31%",
            "Crédito Fiscal 31%",
            "Exento/Sin Derecho a Crédito",
            "IVA Retenido al Proveedor",
            "Nº Comprobante de Retención",
        ]
        move_rows = [
            self._prepare_move_row(move, ves) for move in self._get_purchase_moves()
        ]
        row, totals = self._write_detail_table(
            sheet, formats, row, headers, move_rows, with_voucher=True
        )
        self._write_summary(
            sheet,
            formats,
            row,
            totals,
            tax_label="Crédito Fiscal",
            wh_label="IVA retenido a proveedores (como agente de retención)",
        )
