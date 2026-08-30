# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.exceptions import UserError

SUPPORTED_RATES = (0, 8, 16, 31)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_fiscal_number = fields.Char(
        string="Fiscal Document Number", copy=False, readonly=True
    )
    l10n_ve_fiscal_machine_serial = fields.Char(
        string="Fiscal Machine Serial", copy=False, readonly=True
    )
    l10n_ve_fiscal_date = fields.Char(
        string="Fiscal Date and Time", copy=False, readonly=True
    )
    l10n_ve_fiscal_doc_type = fields.Selection(
        [("invoice", "Invoice"), ("credit_note", "Credit Note")],
        string="Fiscal Document Type",
        copy=False,
        readonly=True,
    )

    @staticmethod
    def _l10n_ve_rate_pct(taxes):
        amount = sum(taxes.mapped("amount")) if taxes else 0.0
        return min(SUPPORTED_RATES, key=lambda rate: abs(rate - amount))

    def _l10n_ve_get_bridge_config(self):
        self.ensure_one()
        configs = self.env["pos.config"].search(
            [
                ("l10n_ve_bridge_url", "!=", False),
                ("company_id", "=", self.company_id.id),
            ]
        )
        if not configs:
            raise UserError(
                self.env._(
                    "No point of sale for this company has a fiscal printer "
                    "bridge configured."
                )
            )
        if len(configs) > 1:
            raise UserError(
                self.env._(
                    "More than one point of sale has a fiscal printer bridge "
                    "configured (%(configs)s). Print from the corresponding point "
                    "of sale or leave only one bridge configured.",
                    configs=", ".join(configs.mapped("name")),
                )
            )
        return configs

    def _l10n_ve_build_payload(self, config):
        self.ensure_one()
        ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not ves:
            raise UserError(self.env._("The VES currency does not exist."))
        rate = config.l10n_ve_get_ves_rate()
        if rate <= 0:
            raise UserError(
                self.env._(
                    "No VES exchange rate is available for today. Fiscal "
                    "printing is blocked to prevent incorrect amounts."
                )
            )
        company = self.company_id
        today = fields.Date.context_today(self)

        def to_ves(amount):
            return round(self.currency_id._convert(amount, ves, company, today), 2)

        items = []
        for line in self.invoice_line_ids.filtered(
            lambda invoice_line: invoice_line.display_type == "product"
            and invoice_line.quantity
        ):
            if line.price_total < 0:
                raise UserError(
                    self.env._(
                        "Fiscal machines do not accept negative lines (%(line)s). "
                        "Apply discounts to the line price instead.",
                        line=line.name or line.product_id.name,
                    )
                )
            items.append(
                {
                    "descripcion": (line.product_id.name or line.name or "")[:40],
                    "precio": round(to_ves(line.price_total) / line.quantity, 2),
                    "cantidad": line.quantity,
                    "iva_porcentaje": self._l10n_ve_rate_pct(line.tax_ids),
                }
            )
        if not items:
            raise UserError(self.env._("The document has no product lines."))
        total = round(sum(item["precio"] * item["cantidad"] for item in items), 2)
        expected = to_ves(self.amount_total)
        if abs(total - expected) > 0.01 * len(items) + 0.02:
            raise UserError(
                self.env._(
                    "The fiscal machine total (VES %(machine)s) differs from the "
                    "invoice total (VES %(odoo)s). Review discounts and fractional "
                    "quantities.",
                    machine=total,
                    odoo=expected,
                )
            )
        payload = {
            "uuid": f"move-{self.id}",
            "cliente_nombre": (self.partner_id.name or "CONSUMIDOR FINAL")[:38],
            "cliente_rif": (self.partner_id.vat or "").replace("-", "").upper(),
            "serial_impresora": config.l10n_ve_machine_serial or "",
            "tasa_dolar": rate,
            "monto_total": total,
            "monto_igtf": 0,
            "items": items,
            "pagos": [
                {
                    "metodo": config.l10n_ve_default_payment_code or "01",
                    "monto": total,
                }
            ],
        }
        if self.move_type == "out_refund":
            origin = self.reversed_entry_id
            if not origin or not origin.l10n_ve_fiscal_number:
                raise UserError(
                    self.env._(
                        "The original invoice has no fiscal number. Issue the "
                        "credit note manually on the fiscal machine."
                    )
                )
            raw_date = (origin.l10n_ve_fiscal_date or "")[:10]
            origin_date = (
                fields.Date.to_date(raw_date) if raw_date else origin.invoice_date
            )
            payload.update(
                {
                    "numero_factura_afectada": origin.l10n_ve_fiscal_number,
                    "serial_afectada": (origin.l10n_ve_fiscal_machine_serial or ""),
                    "fecha_afectada": (
                        origin_date.strftime("%d%m%Y") if origin_date else ""
                    ),
                }
            )
        return payload

    def action_l10n_ve_print_fiscal(self):
        self.ensure_one()
        if (
            self.move_type not in ("out_invoice", "out_refund")
            or self.state != "posted"
        ):
            raise UserError(
                self.env._("Only posted customer invoices and credit notes can print.")
            )
        if self.l10n_ve_emission_medium != "fiscal_machine":
            raise UserError(
                self.env._(
                    "This document was not posted with the Fiscal machine emission "
                    "medium. Printing it would leave the fiscal result unregistered."
                )
            )
        if self.l10n_ve_fiscal_number or self.l10n_ve_control_number:
            raise UserError(
                self.env._(
                    "This document already has fiscal identification (%(number)s).",
                    number=(self.l10n_ve_fiscal_number or self.l10n_ve_control_number),
                )
            )
        config = self._l10n_ve_get_bridge_config()
        doc_type = "credit_note" if self.move_type == "out_refund" else "invoice"
        return {
            "type": "ir.actions.client",
            "tag": "l10n_ve_fiscal_printer.print_fiscal",
            "params": {
                "move_id": self.id,
                "doc_type": doc_type,
                "endpoint": (
                    "/print-credit-note"
                    if doc_type == "credit_note"
                    else "/print-invoice"
                ),
                "bridge_url": config.l10n_ve_bridge_url,
                "bridge_token": config.l10n_ve_bridge_token or "",
                "machine_serial": config.l10n_ve_machine_serial or "",
                "payload": self._l10n_ve_build_payload(config),
            },
        }

    def l10n_ve_set_fiscal_result(self, number, serial, doc_type):
        """Store the result returned to the browser by the local bridge."""
        self.ensure_one()
        if doc_type not in {"invoice", "credit_note"}:
            raise UserError(self.env._("Invalid fiscal document type."))
        if self.l10n_ve_fiscal_number and self.l10n_ve_fiscal_number != number:
            raise UserError(
                self.env._(
                    "Fiscal number %(current)s is already registered; %(new)s was "
                    "not stored. Verify the physical machine output.",
                    current=self.l10n_ve_fiscal_number,
                    new=number,
                )
            )
        stamp = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        fiscal_date = stamp.strftime("%Y-%m-%d %H:%M:%S")
        self._l10n_ve_assign_control_data(number, stamp.date())
        self.write(
            {
                "l10n_ve_fiscal_number": number,
                "l10n_ve_fiscal_machine_serial": serial,
                "l10n_ve_fiscal_date": fiscal_date,
                "l10n_ve_fiscal_doc_type": doc_type,
            }
        )
        self.message_post(
            body=self.env._(
                "Fiscal document printed: number %(number)s, machine %(serial)s.",
                number=number,
                serial=serial,
            )
        )
        return True

    def _post(self, soft=True):
        posted_moves = super()._post(soft)
        for move in posted_moves.filtered(
            lambda candidate: len(candidate.pos_order_ids) == 1
            and candidate.pos_order_ids.l10n_ve_fiscal_number
            and not candidate.l10n_ve_control_number
        ):
            order = move.pos_order_ids
            raw_date = (order.l10n_ve_fiscal_date or "")[:10]
            control_date = (
                fields.Date.to_date(raw_date)
                if raw_date
                else fields.Date.context_today(move)
            )
            move._l10n_ve_assign_control_data(order.l10n_ve_fiscal_number, control_date)
        return posted_moves
