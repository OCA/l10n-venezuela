# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

RECEIVED_VOUCHER_RE = re.compile(r"^\d{4}(0[1-9]|1[0-2])\d{8}$")


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_ve_company_is_spe = fields.Boolean(related="company_id.l10n_ve_is_spe")
    l10n_ve_iva_wh_received_amount = fields.Monetary(
        string="IVA Retenido por el Cliente",
        currency_field="currency_id",
        default=0.0,
        help="Monto de IVA que el cliente (agente de retención) retuvo según "
        "el comprobante entregado. Se descuenta del cobro y se registra "
        "en la cuenta de Retenciones de IVA Recibidas de Clientes.",
    )
    l10n_ve_iva_wh_voucher_number = fields.Char(
        string="Número de Comprobante Recibido",
        size=14,
        help="Numeración de 14 caracteres del comprobante de retención del "
        "cliente: AAAAMM + secuencial de 8 dígitos.",
    )
    l10n_ve_iva_wh_amount = fields.Monetary(
        string="IVA a Retener al Proveedor",
        currency_field="currency_id",
        compute="_compute_l10n_ve_iva_wh_amount",
        store=True,
        readonly=False,
        help="Retención de IVA (PA SNAT/2025/000054) calculada sobre el IVA "
        "de las facturas publicadas según el porcentaje del proveedor. "
        "Se prorratea en pagos parciales y descuenta lo ya retenido en "
        "comprobantes previos de los mismos documentos. Editable.",
    )

    @api.constrains("l10n_ve_iva_wh_voucher_number")
    def _check_l10n_ve_iva_wh_voucher_number(self):
        for wizard in self:
            number = wizard.l10n_ve_iva_wh_voucher_number
            if number and not RECEIVED_VOUCHER_RE.match(number):
                raise ValidationError(
                    self.env._(
                        "El número de comprobante de retención debe tener 14 "
                        "dígitos: AAAAMM + secuencial de 8 dígitos "
                        "(ej. 20260700000001)."
                    )
                )

    @api.depends(
        "line_ids",
        "amount",
        "currency_id",
        "payment_date",
        "partner_id",
        "company_id",
        "can_edit_wizard",
        "group_payment",
    )
    def _compute_l10n_ve_iva_wh_amount(self):
        for wizard in self:
            wizard.l10n_ve_iva_wh_amount = wizard._l10n_ve_get_iva_wh_agent_amount()

    def _l10n_ve_get_iva_wh_agent_amount(self):
        """Return VAT to withhold in the payment wizard currency."""
        self.ensure_one()
        company = self.company_id
        partner = self.partner_id.commercial_partner_id
        if (
            self.payment_type != "outbound"
            or self.partner_type != "supplier"
            or not self.can_edit_wizard
            or not partner
            or not company.l10n_ve_is_spe
        ):
            return 0.0
        batches = self.batches
        if not batches or (len(batches[0]["lines"]) > 1 and not self.group_payment):
            return 0.0
        if (
            company.l10n_ve_spe_date
            and self.payment_date
            and self.payment_date < company.l10n_ve_spe_date
        ):
            return 0.0
        if partner.l10n_ve_taxpayer_type == "especial":
            return 0.0
        if not partner.vat:
            return 0.0
        rate = float(partner.l10n_ve_wh_iva_rate or "0")
        if not rate:
            return 0.0
        moves = self.line_ids.move_id.filtered(
            lambda move: move.is_invoice(include_receipts=True)
            and move.state == "posted"
        )
        if not moves or not self.currency_id:
            return 0.0
        company_currency = company.currency_id
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        tax_total = 0.0
        pending_total = 0.0
        for move in moves:
            tax = voucher_model._l10n_ve_move_iva_amounts(move)["tax"]
            if company_currency.is_zero(tax):
                continue
            if move.move_type in ("in_refund", "out_refund"):
                tax_total -= tax
                continue
            tax_total += tax
            theoretical = company_currency.round(tax * rate / 100.0)
            previous_vouchers = voucher_model.search(
                [
                    ("company_id", "=", company.id),
                    ("state", "=", "posted"),
                    ("move_ids", "in", move.id),
                ]
            )
            already_withheld = sum(
                voucher._l10n_ve_get_amount_for_move(move)
                for voucher in previous_vouchers
            )
            pending_total += max(0.0, theoretical - already_withheld)
        if company_currency.compare_amounts(tax_total, 0.0) <= 0:
            return 0.0
        date = self.payment_date or fields.Date.context_today(self)
        tax_total_wc = company_currency._convert(
            tax_total, self.currency_id, company, date
        )
        pending_wc = company_currency._convert(
            pending_total, self.currency_id, company, date
        )
        total_docs_wc = self._l10n_ve_get_docs_total_in_wizard_currency(moves, date)
        if not total_docs_wc:
            return 0.0
        factor = min(1.0, max(0.0, self.amount / total_docs_wc))
        withholding = min(tax_total_wc * rate / 100.0 * factor, pending_wc)
        return max(0.0, self.currency_id.round(withholding))

    def _l10n_ve_get_docs_total_in_wizard_currency(self, moves, date):
        """Return the original document total net of credit notes."""
        self.ensure_one()
        total_cc = abs(sum(moves.mapped("amount_total_signed")))
        if self.currency_id == self.company_currency_id:
            return total_cc
        return self.company_currency_id._convert(
            total_cc, self.currency_id, self.company_id, date
        )

    def _l10n_ve_iva_wh_get_values(self):
        """Return validated withholding values without side effects."""
        self.ensure_one()
        received = self.l10n_ve_iva_wh_received_amount
        agent_wh = self.l10n_ve_iva_wh_amount
        is_received_case = (
            self.payment_type == "inbound"
            and self.partner_type == "customer"
            and received
        )
        is_agent_case = (
            self.payment_type == "outbound"
            and self.partner_type == "supplier"
            and agent_wh
        )
        if not is_received_case and not is_agent_case:
            return {}

        edit_mode = self.can_edit_wizard and (
            len(self.batches[0]["lines"]) == 1 or self.group_payment
        )
        if not edit_mode:
            raise UserError(
                self.env._(
                    "Para aplicar retención de IVA registre un solo pago agrupado "
                    "(active «Agrupar pagos» o pague las facturas una a una)."
                )
            )
        if self.is_register_payment_on_draft:
            raise UserError(
                self.env._(
                    "No se puede aplicar retención de IVA sobre documentos en "
                    "borrador: publique las facturas antes de registrar el pago."
                )
            )

        if is_received_case:
            if received < 0:
                raise UserError(
                    self.env._("El IVA retenido por el cliente no puede ser negativo.")
                )
            if not self.l10n_ve_iva_wh_voucher_number:
                raise UserError(
                    self.env._(
                        "Indique el número del comprobante de retención recibido "
                        "(14 dígitos: AAAAMM + 8)."
                    )
                )
            account = self.company_id.l10n_ve_iva_wh_received_account_id
            if not account:
                raise UserError(
                    self.env._(
                        "Configure la cuenta de Retenciones de IVA Recibidas de "
                        "Clientes en Ajustes > Contabilidad > Localización Venezuela."
                    )
                )
            withholding = self.currency_id.round(received)
            label = self.env._(
                "Ret. IVA recibida comprobante %s",
                self.l10n_ve_iva_wh_voucher_number,
            )
            direction = "received"
        else:
            if agent_wh < 0:
                raise UserError(
                    self.env._(
                        "La retención de IVA al proveedor no puede ser negativa."
                    )
                )
            account = self.company_id.l10n_ve_iva_wh_agent_account_id
            if not account:
                raise UserError(
                    self.env._(
                        "Configure la cuenta de Retenciones de IVA por Enterar "
                        "(Agente) en Ajustes > Contabilidad > Localización Venezuela."
                    )
                )
            partner = self.partner_id.commercial_partner_id
            if not partner.vat:
                raise UserError(
                    self.env._(
                        "El proveedor %s no tiene RIF configurado (campo NIF): "
                        "no puede practicarse la retención de IVA ni emitirse el "
                        "comprobante (Forma 99035).",
                        partner.display_name,
                    )
                )
            withholding = self.currency_id.round(agent_wh)
            label = self.env._(
                "Ret. IVA %(rate)s%% %(partner)s",
                rate=partner.l10n_ve_wh_iva_rate or "0",
                partner=partner.name,
            )
            direction = "agent"

        if self.currency_id.compare_amounts(withholding, self.amount) >= 0:
            raise UserError(
                self.env._(
                    "La retención de IVA (%(wh)s) no puede ser mayor o igual al "
                    "monto del pago (%(amount)s).",
                    wh=withholding,
                    amount=self.amount,
                )
            )
        if self.currency_id.is_zero(withholding):
            return {}
        return {
            "direction": direction,
            "wh": withholding,
            "account": account,
            "label": label,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        """Add a dedicated withholding write-off line to the payment."""
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        wh_values = self._l10n_ve_iva_wh_get_values()
        if not wh_values:
            return payment_vals
        withholding = wh_values["wh"]
        payment_vals["amount"] -= withholding
        if self.currency_id.compare_amounts(payment_vals["amount"], 0.0) <= 0:
            raise UserError(
                self.env._(
                    "Las retenciones combinadas del pago agotan o exceden su monto "
                    "(monto restante: %(amount)s). Revise los montos de retención "
                    "editados manualmente.",
                    amount=payment_vals["amount"],
                )
            )
        if self.payment_type == "inbound":
            write_off_amount_currency = withholding
        else:
            write_off_amount_currency = -withholding
        payment_vals.setdefault("write_off_line_vals", []).append(
            {
                "name": wh_values["label"],
                "account_id": wh_values["account"].id,
                "partner_id": self.partner_id.commercial_partner_id.id,
                "currency_id": self.currency_id.id,
                "amount_currency": write_off_amount_currency,
                "balance": self.currency_id._convert(
                    write_off_amount_currency,
                    self.company_id.currency_id,
                    self.company_id,
                    self.payment_date,
                ),
            }
        )
        if wh_values["direction"] == "received":
            payment_vals["l10n_ve_iva_wh_received_amount"] = withholding
            payment_vals["l10n_ve_iva_wh_received_number"] = (
                self.l10n_ve_iva_wh_voucher_number
            )
        return payment_vals

    def _create_payments(self):
        self.ensure_one()
        wh_values = self._l10n_ve_iva_wh_get_values()
        payments = super()._create_payments()
        if wh_values and wh_values["direction"] == "agent":
            self._l10n_ve_create_iva_wh_voucher(payments, wh_values)
        return payments

    def _l10n_ve_create_iva_wh_voucher(self, payments, wh_values):
        self.ensure_one()
        company = self.company_id
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        moves = self.line_ids.move_id.filtered(
            lambda move: move.is_invoice(include_receipts=True)
            and move.state == "posted"
        )
        base = exempt = tax = 0.0
        for move in moves:
            amounts = voucher_model._l10n_ve_move_iva_amounts(move)
            sign = -1.0 if move.move_type in ("in_refund", "out_refund") else 1.0
            base += sign * amounts["base"]
            exempt += sign * amounts["exempt"]
            tax += sign * amounts["tax"]
        withheld_company = self.currency_id._convert(
            wh_values["wh"], company.currency_id, company, self.payment_date
        )
        partner = self.partner_id.commercial_partner_id
        number = voucher_model._l10n_ve_next_voucher_number(
            self.payment_date, company=company
        )
        return voucher_model.create(
            {
                "number": number,
                "date": self.payment_date,
                "company_id": company.id,
                "partner_id": partner.id,
                "payment_id": payments[:1].id,
                "move_ids": [Command.set(moves.ids)],
                "base_amount": base,
                "tax_amount": tax,
                "withheld_amount": withheld_company,
                "exempt_amount": exempt,
                "wh_rate": float(partner.l10n_ve_wh_iva_rate or "0"),
                "state": "posted",
            }
        )
