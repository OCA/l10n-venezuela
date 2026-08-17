import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_fiscal_serial_number_placeholder = fields.Char(
        string="Próximo serial fiscal",
        compute="_compute_l10n_ve_fiscal_placeholders",
    )
    l10n_ve_fiscal_invoice_number_placeholder = fields.Char(
        string="Próximo N° fiscal",
        compute="_compute_l10n_ve_fiscal_placeholders",
    )
    l10n_ve_fiscal_report_z_placeholder = fields.Char(
        string="Próximo reporte Z",
        compute="_compute_l10n_ve_fiscal_placeholders",
    )

    @api.model
    def _l10n_ve_fiscal_serial_increment_counter(self, value, min_width=8):
        digits = re.sub(r"\D", "", str(value or ""))
        if not digits:
            return False
        width = max(len(digits), min_width)
        return str(int(digits) + 1).zfill(width)

    def _l10n_ve_fiscal_serial_machine_for_placeholders(self):
        self.ensure_one()
        if self.country_code != "VE":
            return self.env["l10n.ve.fiscal.machine"]
        if self.move_type not in ("out_invoice", "out_refund"):
            return self.env["l10n.ve.fiscal.machine"]
        if self.l10n_ve_journal_emission_medium != "fiscal_machine":
            return self.env["l10n.ve.fiscal.machine"]
        if self.l10n_ve_on_behalf_of_third_party:
            return self.env["l10n.ve.fiscal.machine"]
        return self.journal_id.l10n_ve_fiscal_machine_id

    def _l10n_ve_fiscal_serial_last_number_for_placeholders(self, machine):
        self.ensure_one()
        if self.move_type == "out_refund":
            return machine.last_credit_note_number
        if self.move_type == "out_invoice" and self.debit_origin_id:
            return machine.last_debit_note_number
        return machine.last_invoice_number

    @api.depends(
        "l10n_ve_serial_number",
        "l10n_ve_invoice_number",
        "l10n_ve_report_z",
        "move_type",
        "debit_origin_id",
        "country_code",
        "l10n_ve_journal_emission_medium",
        "l10n_ve_on_behalf_of_third_party",
        "journal_id.l10n_ve_fiscal_machine_id",
        "journal_id.l10n_ve_fiscal_machine_id.registered_serial",
        "journal_id.l10n_ve_fiscal_machine_id.last_invoice_number",
        "journal_id.l10n_ve_fiscal_machine_id.last_credit_note_number",
        "journal_id.l10n_ve_fiscal_machine_id.last_debit_note_number",
        "journal_id.l10n_ve_fiscal_machine_id.daily_closure_counter",
    )
    def _compute_l10n_ve_fiscal_placeholders(self):
        for move in self:
            serial_placeholder = False
            invoice_placeholder = False
            report_z_placeholder = False
            machine = move._l10n_ve_fiscal_serial_machine_for_placeholders()
            if machine:
                if not (move.l10n_ve_serial_number or "").strip():
                    serial_placeholder = (machine.registered_serial or "").strip() or False
                if not (move.l10n_ve_invoice_number or "").strip():
                    invoice_placeholder = move._l10n_ve_fiscal_serial_increment_counter(
                        move._l10n_ve_fiscal_serial_last_number_for_placeholders(machine),
                        min_width=8,
                    )
                if not (move.l10n_ve_report_z or "").strip():
                    report_z_placeholder = move._l10n_ve_fiscal_serial_increment_counter(
                        machine.daily_closure_counter,
                        min_width=4,
                    )
            move.l10n_ve_fiscal_serial_number_placeholder = serial_placeholder
            move.l10n_ve_fiscal_invoice_number_placeholder = invoice_placeholder
            move.l10n_ve_fiscal_report_z_placeholder = report_z_placeholder

    def _l10n_ve_fiscal_serial_reprint_document_type(self):
        self.ensure_one()
        if self.move_type == "out_refund":
            return "out_refund"
        if self.move_type == "out_invoice" and self.debit_origin_id:
            return "debit_note"
        return "out_invoice"

    def _l10n_ve_fiscal_serial_normalize_reprint_number(self, number):
        digits = re.sub(r"\D", "", str(number or ""))
        if not digits:
            return "0000000"
        return digits[-7:].zfill(7)

    def _l10n_ve_fiscal_serial_prepare_line_name_and_code(self, line):
        self.ensure_one()
        if line.product_id:
            base_name = line.product_id.name or line.name or ""
            default_code = line.product_id.default_code or ""
        else:
            base_name = line.name or ""
            default_code = ""

        machine = self.journal_id.l10n_ve_fiscal_machine_id
        if machine and machine.send_default_code_in_name and default_code:
            return f"[{default_code}] {base_name}".strip(), ""
        return base_name, default_code

    def _l10n_ve_fiscal_serial_date_ddmmyyyy(self, value):
        date_value = fields.Date.to_date(value) if value else False
        if not date_value:
            return ""
        return date_value.strftime("%d/%m/%Y")

    def _l10n_ve_fiscal_serial_validate_print_base(self):
        self.ensure_one()
        if self.country_code != "VE":
            raise ValidationError(_("Esta acción solo aplica para compañías VE."))
        if self.l10n_ve_journal_emission_medium != "fiscal_machine":
            raise ValidationError(_("El diario no está configurado como máquina fiscal."))
        if not self.journal_id.l10n_ve_fiscal_machine_id:
            raise ValidationError(
                _("Configure la máquina fiscal en el diario de ventas.")
            )
        if self.state != "posted":
            raise ValidationError(_("Debe confirmar la factura antes de imprimirla fiscalmente."))

    def _l10n_ve_fiscal_serial_journal_machine_payload(self):
        self.ensure_one()
        if self.l10n_ve_journal_emission_medium != "fiscal_machine":
            return {}
        machine = self.journal_id.l10n_ve_fiscal_machine_id
        if not machine:
            raise ValidationError(
                _("Configure la máquina fiscal en el diario de ventas.")
            )
        baud = machine.baudrate or "9600"
        shared = machine.company_id.l10n_ve_fiscal_get_shared_config()
        return {
            "machine_id": machine.id,
            "name": machine.name or "",
            "registered_serial": machine.registered_serial or "",
            "baudrate": int(baud) if str(baud).isdigit() else 9600,
            "parity": machine.parity
            if machine.parity in ("none", "even", "odd")
            else "even",
            "flag_21": shared.get("flag_21") or "30",
            "flag_50": shared.get("flag_50") or "01",
            "use_barcode": bool(shared.get("use_barcode")),
            "footer_lines": shared.get("footer_lines") or [],
            "payment_methods": shared.get("payment_methods") or [],
            "use_emulator": bool(machine.use_emulator),
            "send_default_code_in_name": bool(machine.send_default_code_in_name),
            "serial_port": machine.serial_port or "",
            "webserial_usb_vendor_id": machine.webserial_usb_vendor_id or 0,
            "webserial_usb_product_id": machine.webserial_usb_product_id or 0,
            "webserial_usb_serial_number": machine.webserial_usb_serial_number or "",
        }

    def _l10n_ve_fiscal_serial_map_tax_code(self, line):
        tax = line.tax_ids[:1]
        if not tax:
            return "0"
        amount = abs(tax.amount)
        if amount <= 0:
            return "0"
        if amount <= 8:
            return "2"
        if amount <= 16:
            return "1"
        return "3"

    def _l10n_ve_fiscal_serial_line_price_unit_for_print(self, line):
        self.ensure_one()
        price = line.price_unit or 0.0
        if self.currency_id == self.company_currency_id:
            return price
        rate = line.currency_rate or self.invoice_currency_rate or 0.0
        if not float_is_zero(rate, precision_rounding=1e-9):
            return self.company_currency_id.round(price / rate)
        return price

    def _l10n_ve_fiscal_serial_global_discount_amount(self):
        self.ensure_one()
        tax_totals = self.tax_totals or {}
        amount = tax_totals.get("l10n_ve_global_discount_amount", 0.0)
        if float_is_zero(amount, precision_rounding=self.company_currency_id.rounding):
            return 0.0
        return amount

    def _l10n_ve_fiscal_serial_line_discount_amounts(self):
        self.ensure_one()
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        Tax = self.env["account.tax"]
        if hasattr(Tax, "_l10n_ve_get_line_discount_amounts"):
            return Tax._l10n_ve_get_line_discount_amounts(base_lines, self.company_id)
        return self._l10n_ve_fiscal_serial_line_discount_amounts_fallback(base_lines)

    def _l10n_ve_fiscal_serial_line_discount_amounts_fallback(self, base_lines):
        """Untaxed line discounts when l10n_ve_loyalty is not installed."""
        if not base_lines:
            return {}
        Tax = self.env["account.tax"]
        discounted_lines = [
            base_line
            for base_line in base_lines
            if (base_line.get("discount") or 0.0) > 0.0
            and base_line.get("special_type") != "global_discount"
        ]
        if not discounted_lines:
            return {}
        for in_foreign_currency in (True, False):
            Tax._add_and_round_raw_gross_total_excluded_and_discount(
                base_lines,
                self.company_id,
                in_foreign_currency=in_foreign_currency,
            )
        amounts = {}
        for base_line in discounted_lines:
            record = base_line.get("record")
            line_id = record.id if getattr(record, "id", False) else base_line.get("id")
            if not line_id:
                continue
            amount = base_line["tax_details"].get("raw_discount_amount", 0.0)
            if amount:
                amounts[line_id] = amount
        return amounts

    def _l10n_ve_fiscal_serial_invoice_lines_payload(self):
        self.ensure_one()
        discount_amounts = self._l10n_ve_fiscal_serial_line_discount_amounts()
        lines = []
        for line in self.invoice_line_ids.filtered(
            lambda line_item: line_item.display_type in (False, "product")
        ):
            display_name, default_code = self._l10n_ve_fiscal_serial_prepare_line_name_and_code(line)
            lines.append(
                {
                    "tax": self._l10n_ve_fiscal_serial_map_tax_code(line),
                    "tax_percent": line.tax_ids[:1].amount if line.tax_ids[:1] else 0.0,
                    "price_unit": self._l10n_ve_fiscal_serial_line_price_unit_for_print(line),
                    "quantity": line.quantity,
                    "default_code": default_code,
                    "name": display_name,
                    "discount": line.discount or 0.0,
                    "discount_amount": discount_amounts.get(line.id, 0.0),
                }
            )
        return lines

    def _l10n_ve_fiscal_serial_default_payment_code(self):
        self.ensure_one()
        method = self.company_id.l10n_ve_fiscal_default_payment_method_id
        if method and method.code:
            return str(method.code).strip().zfill(2)
        if self.l10n_ve_igtf_document_has_igtf():
            return "21"
        return "01"

    def _l10n_ve_fiscal_serial_payment_method_line_code(self, payment_method_line):
        if not payment_method_line:
            return False
        method = payment_method_line.l10n_ve_fiscal_payment_method_id
        if method and method.code:
            return str(method.code).strip().zfill(2)
        return False

    def _l10n_ve_fiscal_serial_journal_fiscal_payment_code(self, journal):
        if not journal:
            return self._l10n_ve_fiscal_serial_default_payment_code()
        journal_code = getattr(journal, "l10n_ve_fiscal_payment_code", False)
        if journal_code:
            code = str(journal_code).strip()
            if code:
                return code.zfill(2)
        fallback = getattr(journal, "payment_method", False) or getattr(
            journal, "l10n_ve_payment_method", False
        )
        if fallback:
            return str(fallback).strip().zfill(2)
        for line in journal.inbound_payment_method_line_ids:
            code = self._l10n_ve_fiscal_serial_payment_method_line_code(line)
            if code:
                return code
        for line in journal.outbound_payment_method_line_ids:
            code = self._l10n_ve_fiscal_serial_payment_method_line_code(line)
            if code:
                return code
        return self._l10n_ve_fiscal_serial_default_payment_code()

    def _l10n_ve_fiscal_serial_resolve_payment_code(self, payment=None, journal=None):
        self.ensure_one()
        if payment:
            code = self._l10n_ve_fiscal_serial_payment_method_line_code(
                payment.payment_method_line_id
            )
            if code:
                return code
            journal = journal or payment.journal_id
        return self._l10n_ve_fiscal_serial_journal_fiscal_payment_code(journal)

    def _l10n_ve_fiscal_serial_payment_lines_from_pos_orders(self):
        self.ensure_one()
        lines = []
        for order in self.pos_order_ids:
            conv_date = (
                fields.Date.to_date(order.date_order)
                if order.date_order
                else (self.invoice_date or self.date)
            )
            order_currency = order.currency_id
            for pay in order.payment_ids.sorted("id"):
                if pay.is_change:
                    continue
                if pay.payment_method_id.type == "pay_later":
                    continue
                amount = abs(float(pay.amount))
                if float_is_zero(amount, precision_rounding=order_currency.rounding):
                    continue
                amount_company = order_currency._convert(
                    amount,
                    self.company_currency_id,
                    self.company_id,
                    conv_date,
                )
                if float_is_zero(
                    amount_company,
                    precision_rounding=self.company_currency_id.rounding,
                ):
                    continue
                journal = pay.payment_method_id.journal_id
                lines.append(
                    {
                        "amount": amount_company,
                        "payment_method": self._l10n_ve_fiscal_serial_resolve_payment_code(
                            journal=journal
                        ),
                    }
                )
        return lines

    def _l10n_ve_fiscal_serial_payment_lines_from_invoice_widget(self):
        self.ensure_one()
        lines = []
        payments_widget = self.invoice_payments_widget or {}
        if isinstance(payments_widget, bytes):
            try:
                payments_widget = json.loads(payments_widget.decode("utf-8"))
            except Exception:
                payments_widget = {}
        elif isinstance(payments_widget, str):
            try:
                payments_widget = json.loads(payments_widget)
            except Exception:
                payments_widget = {}

        reconciled = payments_widget.get("content", []) if isinstance(payments_widget, dict) else []

        for item in reconciled:
            if item.get("is_exchange"):
                continue
            amount = item.get("amount")
            if amount is None:
                continue
            amount = abs(float(amount))
            item_currency_id = item.get("currency_id")
            from_currency = self.currency_id
            if item_currency_id and item_currency_id != self.currency_id.id:
                from_currency = self.env["res.currency"].browse(item_currency_id)
            if float_is_zero(amount, precision_rounding=from_currency.rounding):
                continue
            conv_date = item.get("date")
            conv_date = fields.Date.to_date(conv_date) if conv_date else False
            if not conv_date:
                conv_date = self.invoice_date or self.date
            amount_company = from_currency._convert(
                amount,
                self.company_currency_id,
                self.company_id,
                conv_date,
            )
            if float_is_zero(
                amount_company,
                precision_rounding=self.company_currency_id.rounding,
            ):
                continue
            journal = False
            payment = False
            payment_id = item.get("account_payment_id")
            if payment_id:
                payment = self.env["account.payment"].browse(payment_id)
                journal = payment.journal_id
            else:
                counterpart_move = self.env["account.move"].browse(item.get("move_id"))
                journal = counterpart_move.journal_id
            payment_method = self._l10n_ve_fiscal_serial_resolve_payment_code(
                payment=payment,
                journal=journal,
            )
            lines.append(
                {
                    "amount": amount_company,
                    "payment_method": payment_method,
                }
            )
        return lines

    def _l10n_ve_fiscal_serial_fallback_payment_line(self):
        self.ensure_one()
        return {
            "amount": 0,
            "payment_method": self._l10n_ve_fiscal_serial_default_payment_code(),
        }

    def _l10n_ve_fiscal_serial_payment_lines_payload(self):
        self.ensure_one()
        lines = []
        if "pos_order_ids" in self._fields and self.pos_order_ids:
            lines = self._l10n_ve_fiscal_serial_payment_lines_from_pos_orders()
        if not lines:
            lines = self._l10n_ve_fiscal_serial_payment_lines_from_invoice_widget()
        if not lines:
            lines.append(self._l10n_ve_fiscal_serial_fallback_payment_line())
        return lines

    def _l10n_ve_fiscal_serial_partner_payload(self):
        self.ensure_one()
        partner = self.partner_id
        return {
            "name": partner.name or "",
            "vat": partner.vat or "",
            "address": partner.street or "",
            "phone": partner.phone or partner.mobile or "",
        }

    def _l10n_ve_fiscal_serial_base_payload(self):
        self.ensure_one()
        machine_cfg = self._l10n_ve_fiscal_serial_journal_machine_payload()
        machine = self.journal_id.l10n_ve_fiscal_machine_id
        use_barcode = bool(machine_cfg.get("use_barcode"))
        barcode = False
        if use_barcode:
            digits = re.sub(r"\D", "", self.name or "")
            if digits:
                barcode = [digits]
        return {
            "company_id": self.company_id.id,
            "partner_id": self._l10n_ve_fiscal_serial_partner_payload(),
            "invoice_lines": self._l10n_ve_fiscal_serial_invoice_lines_payload(),
            "payment_lines": self._l10n_ve_fiscal_serial_payment_lines_payload(),
            "global_discount_amount": self._l10n_ve_fiscal_serial_global_discount_amount(),
            "flag_21": machine_cfg.get("flag_21") or "30",
            "flag_50": machine_cfg.get("flag_50") or "01",
            "use_barcode": use_barcode,
            "barcode": barcode,
            "fiscal_machine": machine_cfg or False,
            "aditional_lines": [],
            "has_cashbox": False,
            "use_emulator": bool(machine.use_emulator) if machine else False,
        }

    def check_print_out_invoice(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if self.move_type != "out_invoice":
            raise ValidationError(_("Solo puede imprimir facturas de cliente."))
        if self.l10n_ve_invoice_number:
            raise ValidationError(_("La factura ya fue impresa en máquina fiscal."))
        payload = self._l10n_ve_fiscal_serial_base_payload()
        payload.update({"move_type": self.move_type, "move_id": self.id})
        return payload

    def check_print_out_refund(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if self.move_type != "out_refund":
            raise ValidationError(_("Solo puede imprimir notas de crédito de cliente."))
        if self.l10n_ve_invoice_number:
            raise ValidationError(_("La nota de crédito ya fue impresa en máquina fiscal."))
        if not self.reversed_entry_id:
            raise ValidationError(_("La nota de crédito debe tener factura afectada."))
        if not self.reversed_entry_id.l10n_ve_invoice_number:
            raise ValidationError(
                _(
                    "La factura afectada no tiene número fiscal. "
                    "No se puede imprimir la nota de crédito."
                )
            )
        payload = self._l10n_ve_fiscal_serial_base_payload()
        payload.update(
            {
                "move_type": self.move_type,
                "move_id": self.id,
                "invoice_affected": {
                    "number": self.reversed_entry_id.l10n_ve_invoice_number,
                    "serial_machine": self.reversed_entry_id.l10n_ve_serial_number,
                    "date": self._l10n_ve_fiscal_serial_date_ddmmyyyy(
                        self.reversed_entry_id.invoice_date or self.reversed_entry_id.date
                    ),
                },
            }
        )
        return payload

    def check_print_debit_note(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if self.move_type != "out_invoice" or not self.debit_origin_id:
            raise ValidationError(_("Solo puede imprimir notas de débito de cliente."))
        if self.l10n_ve_invoice_number:
            raise ValidationError(_("La nota de débito ya fue impresa en máquina fiscal."))
        if not self.debit_origin_id.l10n_ve_invoice_number:
            raise ValidationError(
                _(
                    "La factura origen no tiene número fiscal. "
                    "No se puede imprimir la nota de débito."
                )
            )
        payload = self._l10n_ve_fiscal_serial_base_payload()
        payload.update(
            {
                "move_type": self.move_type,
                "move_id": self.id,
                "invoice_affected": {
                    "number": self.debit_origin_id.l10n_ve_invoice_number,
                    "serial_machine": self.debit_origin_id.l10n_ve_serial_number,
                    "date": self._l10n_ve_fiscal_serial_date_ddmmyyyy(
                        self.debit_origin_id.invoice_date or self.debit_origin_id.date
                    ),
                },
            }
        )
        return payload

    def check_reprint(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if not self.l10n_ve_invoice_number:
            raise ValidationError(_("El documento no tiene número fiscal para reimprimir."))
        return {
            "type": self.move_type,
            "reprint_document_type": self._l10n_ve_fiscal_serial_reprint_document_type(),
            "mf_number": self._l10n_ve_fiscal_serial_normalize_reprint_number(
                self.l10n_ve_invoice_number
            ),
            "move_id": self.id,
            "fiscal_machine": self._l10n_ve_fiscal_serial_journal_machine_payload(),
        }

    def _l10n_ve_fiscal_serial_machine_counter_vals(self, data):
        self.ensure_one()
        machine_vals = {}
        parsed = data.get("parsed_post") if isinstance(data, dict) else None
        if isinstance(parsed, dict):
            if parsed.get("LastInvoiceNumber"):
                machine_vals["last_invoice_number"] = str(parsed["LastInvoiceNumber"])
            if parsed.get("LastCreditNoteNumber"):
                machine_vals["last_credit_note_number"] = str(
                    parsed["LastCreditNoteNumber"]
                )
            if parsed.get("LastDebitNoteNumber"):
                machine_vals["last_debit_note_number"] = str(
                    parsed["LastDebitNoteNumber"]
                )
            if parsed.get("DailyClosureCounter") not in (None, False, ""):
                machine_vals["daily_closure_counter"] = str(
                    parsed["DailyClosureCounter"]
                )
        sequence = data.get("sequence") if isinstance(data, dict) else None
        if sequence:
            sequence = str(sequence)
            if self.move_type == "out_refund":
                machine_vals.setdefault("last_credit_note_number", sequence)
            elif self.move_type == "out_invoice" and self.debit_origin_id:
                machine_vals.setdefault("last_debit_note_number", sequence)
            elif self.move_type == "out_invoice":
                machine_vals.setdefault("last_invoice_number", sequence)
        return machine_vals

    def _l10n_ve_fiscal_serial_update_machine_counters(self, data):
        self.ensure_one()
        machine = self.journal_id.l10n_ve_fiscal_machine_id
        if not machine:
            return
        machine_vals = self._l10n_ve_fiscal_serial_machine_counter_vals(data)
        if machine_vals:
            machine.write(machine_vals)

    def _l10n_ve_fiscal_serial_write_print_result(self, values):
        self.ensure_one()
        data = values.get("data") if isinstance(values, dict) and values.get("data") else values
        if not isinstance(data, dict):
            raise ValidationError(_("Respuesta fiscal inválida."))
        vals = {}
        sequence = data.get("sequence")
        serial = data.get("serial_machine")
        report_z = data.get("mf_reportz") or data.get("report_z")
        if sequence:
            vals["l10n_ve_invoice_number"] = str(sequence)
        if serial:
            vals["l10n_ve_serial_number"] = str(serial)
        if report_z:
            vals["l10n_ve_report_z"] = str(report_z)
        vals["l10n_ve_invoice_date"] = fields.Datetime.now()
        if not self.l10n_ve_invoice_original_printed:
            vals["l10n_ve_invoice_original_printed"] = True
        self.write(vals)
        self._l10n_ve_fiscal_serial_update_machine_counters(data)
        return True

    def print_out_invoice(self, values):
        self.ensure_one()
        return self._l10n_ve_fiscal_serial_write_print_result(values)

    def print_out_refund(self, values):
        self.ensure_one()
        return self._l10n_ve_fiscal_serial_write_print_result(values)

    def print_debit_note(self, values):
        self.ensure_one()
        return self._l10n_ve_fiscal_serial_write_print_result(values)
