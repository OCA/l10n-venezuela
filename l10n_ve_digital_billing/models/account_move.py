# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import re

from odoo import fields, models
from odoo.exceptions import UserError


def _split_vat(vat):
    """Split a RIF/cédula into (type, number): "J-98765432-1" -> ("J", "987654321").

    A digital printing house asks for the type and the number separately;
    Odoo's vat field carries them together. A value with no letter (happens
    on databases that mix cédulas without a prefix) returns an empty type and
    only the digits: picking the letter is for the user to decide, not the
    code.
    """
    vat = (vat or "").strip().upper()
    match = re.match(r"^([VEJGPC])-?(\d{1,9})-?(\d)?$", vat)
    if not match:
        return "", re.sub(r"\D", "", vat)
    letter, body, check = match.groups()
    return letter, body + (check or "")


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_edoc_state = fields.Selection(
        [
            ("to_send", "To send"),
            ("sent", "Sent, control number pending"),
            ("assigned", "Control number assigned"),
            ("error", "Error"),
            ("cancelled", "Cancelled at the digital printing house"),
        ],
        string="Digital printing house status",
        copy=False,
        readonly=True,
        tracking=True,
    )
    l10n_ve_edoc_external_id = fields.Char(
        string="Digital printing house identifier", copy=False, readonly=True
    )
    l10n_ve_edoc_error = fields.Text(
        string="Last digital printing house error", copy=False, readonly=True
    )

    # ------------------------------------------------------------------
    # Fiscal payload -- fully writable without knowing the provider
    # ------------------------------------------------------------------
    def _l10n_ve_edoc_document_vals(self):
        """The document as a NEUTRAL dict, independent of the provider.

        All the fiscal logic lives here: what counts as taxable base and
        what is exempt, how VAT splits by rate, what a credit note carries.
        The adapter only renames fields. Switching digital printing houses
        means writing one file, without touching this.
        """
        self.ensure_one()
        company = self.company_id
        partner = self.commercial_partner_id
        buyer_type, buyer_number = _split_vat(partner.vat)
        lines = []
        for line in self.invoice_line_ids.filtered(
            lambda ln: ln.display_type == "product"
        ):
            rate = next((tax.amount for tax in line.tax_ids if tax.amount), 0.0)
            lines.append(
                {
                    # The digital printing house requires a product code (PLU)
                    # and a unit of measure; the adapter cannot invent them, so
                    # they travel from here.
                    "code": line.product_id.default_code or "",
                    "description": line.name or "",
                    "quantity": line.quantity,
                    "uom": line.product_uom_id.name or "",
                    "unit_price": line.price_unit,
                    "discount_pct": line.discount,
                    # Odoo's discount is a percentage; the printing house wants
                    # it as an AMOUNT.
                    "discount_amount": self.currency_id.round(
                        line.quantity * line.price_unit * line.discount / 100.0
                    ),
                    "base": line.price_subtotal,
                    "rate": rate,
                    # price_total - price_subtotal = the line's taxes. Under the
                    # VE tax setup (only VAT on sales) that is the line's VAT.
                    "tax": line.price_total - line.price_subtotal,
                    "total": line.price_total,
                    "exempt": line._l10n_ve_edoc_is_exempt(),
                }
            )
        # The legal emission time is when the document is sent, not the
        # accounting date: it is fixed here so the log and the printing
        # house see the exact same value.
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        vals = {
            "doc_type": self._l10n_ve_edoc_doc_type(),
            "number": self.name,
            "date": self.invoice_date,
            "time": now.strftime("%H:%M:%S"),
            "currency": self.currency_id.name,
            # Cash or credit based on the due date: this is what the
            # printing house labels as the sale type, and what decides the
            # default payment when there is no reconciled collection yet.
            "sale_type": "credit"
            if (
                self.invoice_date_due
                and self.invoice_date
                and self.invoice_date_due > self.invoice_date
            )
            else "cash",
            "issuer": {
                "vat": company.vat or "",
                "name": company.name,
                "address": company.street or "",
            },
            "buyer": {
                "vat": partner.vat or "",
                "id_type": buyer_type,
                "id_number": buyer_number,
                "name": partner.name or "",
                "address": partner.street or "",
                "email": partner.email or "",
                "phone": partner.phone or "",
            },
            "lines": lines,
            "line_count": len(lines),
            "exempt_total": sum(ln["base"] for ln in lines if ln["exempt"]),
            "taxed_total": sum(ln["base"] for ln in lines if not ln["exempt"]),
            "untaxed_total": self.amount_untaxed,
            "tax_total": self.amount_tax,
            "total": self.amount_total,
            "payments": self._l10n_ve_edoc_payment_vals(),
        }
        # A credit or debit note must reference the date, number and amount
        # of the document it affects (PA 0071 art. 143 and PA 102). A debit
        # note is an out_invoice with debit_origin_id -- without this branch
        # it would travel without that reference.
        origin = None
        if self.move_type == "out_refund" and self.reversed_entry_id:
            origin = self.reversed_entry_id
        elif "debit_origin_id" in self._fields and self.debit_origin_id:
            origin = self.debit_origin_id
        if origin:
            vals["affected_document"] = {
                "number": origin.name,
                "control_number": origin.l10n_ve_control_number or "",
                "date": origin.invoice_date,
                "amount": origin.amount_total,
                "reason": self.ref or "",
            }
        return vals

    def _l10n_ve_edoc_doc_type(self):
        self.ensure_one()
        if self.move_type == "out_refund":
            return "credit_note"
        if "debit_origin_id" in self._fields and self.debit_origin_id:
            return "debit_note"
        return "invoice"

    def _l10n_ve_edoc_payment_vals(self):
        """Payments already reconciled with the document, in neutral form.

        Almost always empty -- the invoice is issued before it is collected
        -- and the adapter sends a single payment for the total based on the
        sale type. When there is a real collection (cash sales, deposits),
        the actual ones travel instead.
        """
        self.ensure_one()
        if not hasattr(self, "_get_reconciled_payments"):
            return []
        return [
            {
                "description": (
                    payment.payment_method_line_id.name or payment.journal_id.name or ""
                ),
                "date": payment.date,
                "amount": payment.amount,
                "currency": payment.currency_id.name,
            }
            for payment in self._get_reconciled_payments()
        ]

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        # Queue for the digital printing house: without this no document
        # ever reaches "to_send" and the cron's sending branch would be dead
        # code. Only when a provider is configured, so the cron does not
        # blow up. l10n_ve_emission_medium is read on the MOVE, not the
        # journal: l10n_ve_fiscal_document snapshots it there at posting
        # time, so a later change to the journal's configuration never
        # reclassifies an already-posted document.
        for move in posted:
            if (
                move.is_sale_document(include_receipts=True)
                and move.l10n_ve_emission_medium == "digital"
                and not move.l10n_ve_edoc_state
                and move.company_id.l10n_ve_edoc_provider
            ):
                move.l10n_ve_edoc_state = "to_send"
        return posted

    def _l10n_ve_edoc_provider(self):
        self.ensure_one()
        provider = self.company_id.l10n_ve_edoc_provider
        if not provider:
            raise UserError(
                self.env._(
                    "%(company)s has no digital printing house provider configured.",
                    company=self.company_id.display_name,
                )
            )
        return self.env[provider]

    def action_l10n_ve_edoc_send(self):
        for move in self:
            if move.l10n_ve_emission_medium != "digital":
                raise UserError(
                    self.env._(
                        "%(document)s is not on a digital billing journal.",
                        document=move.display_name,
                    )
                )
            if move.state != "posted":
                raise UserError(self.env._("Only posted documents can be sent."))
            if move.l10n_ve_edoc_state in ("sent", "assigned"):
                raise UserError(
                    self.env._(
                        "%(document)s was already sent to the digital printing house.",
                        document=move.display_name,
                    )
                )
            move._l10n_ve_edoc_do_send()
        return True

    def _l10n_ve_edoc_do_send(self):
        self.ensure_one()
        provider = self._l10n_ve_edoc_provider()
        vals = self._l10n_ve_edoc_document_vals()
        try:
            result = provider._edoc_send(self, vals)
        except Exception as error:  # noqa: BLE001 -- the provider's error is
            # logged and shown; it must never roll back the accounting entry.
            self._l10n_ve_edoc_log("send", vals, str(error), ok=False)
            self.write(
                {
                    "l10n_ve_edoc_state": "error",
                    "l10n_ve_edoc_error": str(error),
                }
            )
            return False
        self._l10n_ve_edoc_log("send", vals, result, ok=True)
        self._l10n_ve_edoc_apply(result)
        return True

    def _l10n_ve_edoc_apply(self, result):
        """Apply the provider's response through the control data assignment
        API that l10n_ve_fiscal_document exposes for exactly this: a digital
        printing house is a legitimate source for the control number of an
        already-posted document. Skips the call once a number is on file, so
        a retried fetch/cron cycle stays a harmless no-op.

        The date is normalised to None rather than False: the assignment API
        type-checks it and rejects anything that is not a date.
        """
        self.ensure_one()
        number = result.get("control_number")
        if number and not self.l10n_ve_control_number:
            self._l10n_ve_assign_control_data(
                number, result.get("control_date") or None
            )
        self.write(
            {
                "l10n_ve_edoc_external_id": result.get("external_id"),
                "l10n_ve_edoc_error": False,
                "l10n_ve_edoc_state": "assigned" if number else "sent",
            }
        )

    def action_l10n_ve_edoc_fetch(self):
        """Query the control number of documents already sent.

        Only needed for asynchronous providers. With a synchronous provider
        such as The Factory HKA, which returns the control number in the
        emission call itself, this never gets used.
        """
        for move in self.filtered(lambda m: m.l10n_ve_edoc_state == "sent"):
            provider = move._l10n_ve_edoc_provider()
            try:
                result = provider._edoc_fetch(move)
            except Exception as error:  # noqa: BLE001
                move._l10n_ve_edoc_log("fetch", {}, str(error), ok=False)
                continue
            move._l10n_ve_edoc_log("fetch", {}, result, ok=True)
            if result.get("control_number"):
                move._l10n_ve_edoc_apply(result)
        return True

    def action_l10n_ve_edoc_cancel(self):
        """Open the cancellation wizard: the provider requires a reason."""
        self.ensure_one()
        if self.l10n_ve_edoc_state not in ("sent", "assigned"):
            raise UserError(
                self.env._(
                    "%(document)s was not issued at the digital printing "
                    "house: there is nothing to cancel.",
                    document=self.display_name,
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Cancel at the digital printing house"),
            "res_model": "l10n.ve.edoc.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _l10n_ve_edoc_do_cancel(self, reason):
        """Cancel at the digital printing house. Returns True/False and
        NEVER raises: raising would roll back the log entry, which must
        survive above all when the call fails (same policy as
        ``_l10n_ve_edoc_do_send``)."""
        self.ensure_one()
        provider = self._l10n_ve_edoc_provider()
        request = {"reason": reason}
        try:
            result = provider._edoc_cancel(self, reason)
        except Exception as error:  # noqa: BLE001 -- see _l10n_ve_edoc_do_send
            self._l10n_ve_edoc_log("cancel", request, str(error), ok=False)
            self.l10n_ve_edoc_error = str(error)
            return False
        self._l10n_ve_edoc_log("cancel", request, result, ok=bool(result))
        if result:
            self.write(
                {
                    "l10n_ve_edoc_state": "cancelled",
                    "l10n_ve_edoc_error": False,
                }
            )
        return bool(result)

    def _l10n_ve_edoc_log(self, endpoint, request, response, ok):
        self.ensure_one()
        self.env["l10n.ve.edoc.log"].sudo().create(
            {
                "move_id": self.id,
                "endpoint": endpoint,
                "request": repr(request),
                "response": repr(response),
                "ok": ok,
            }
        )

    def _l10n_ve_edoc_cron(self):
        """Send pending documents and query asynchronous ones. ONE cron for
        both: half the code and no ordering issue between them."""
        moves = self.search([("l10n_ve_edoc_state", "in", ("to_send", "sent"))])
        for move in moves.filtered(
            lambda m: m.l10n_ve_edoc_state == "to_send"
            and m.company_id.l10n_ve_edoc_provider
        ):
            move._l10n_ve_edoc_do_send()
        moves.filtered(
            lambda m: m.l10n_ve_edoc_state == "sent"
        ).action_l10n_ve_edoc_fetch()
