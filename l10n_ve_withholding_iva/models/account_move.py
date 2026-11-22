# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

# Purchase receipts are not subject to VAT withholding: only vendor bills
# issue a voucher; vendor credit notes adjust the voucher of their bill.
L10N_VE_IVA_WH_MOVE_TYPES = ("in_invoice",)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_iva_wh_excluded = fields.Boolean(
        string="Excluido de Retención de IVA",
        copy=False,
        help="Marque cuando la operación esté expresamente excluida de la "
        "retención de IVA (art. 3, PA SNAT/2025/000054). Al contabilizar el "
        "documento no se emitirá comprobante de retención.",
    )
    l10n_ve_iva_wh_voucher_id = fields.Many2one(
        comodel_name="l10n.ve.iva.wh.voucher",
        string="Comprobante de Retención de IVA",
        copy=False,
        readonly=True,
        index="btree_not_null",
        help="Comprobante emitido al contabilizar este documento (abono en "
        "cuenta, art. 13, PA SNAT/2025/000054) o al que se agregó esta nota "
        "de crédito.",
    )

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        ve_posted = posted.filtered(
            lambda move: move.state == "posted" and move.country_code == "VE"
        )
        ve_posted.filtered(
            lambda move: move.move_type in L10N_VE_IVA_WH_MOVE_TYPES
        )._l10n_ve_iva_wh_create()
        ve_posted.filtered(
            lambda move: move.move_type == "in_refund"
        )._l10n_ve_iva_wh_apply_refund()
        return posted

    # ------------------------------------------------------------------
    # Protection of the withholding entries
    # ------------------------------------------------------------------

    def _l10n_ve_iva_wh_protecting_vouchers(self):
        """Return the posted vouchers whose withholding entries are in self.

        Resolved from the voucher side with sudo: the pointers stored on
        the moves are writable over RPC and must not decide anything.
        """
        voucher_model = self.env["l10n.ve.iva.wh.voucher"].sudo()
        ids = [move_id for move_id in self.ids if move_id]
        if not ids:
            return voucher_model
        return voucher_model.search(
            [
                ("state", "=", "posted"),
                ("company_id", "in", self.company_id.ids),
                "|",
                ("wh_move_id", "in", ids),
                ("adjustment_ids.move_id", "in", ids),
            ]
        )

    def _l10n_ve_iva_wh_check_protected(self):
        """Block any change to the entries of an issued voucher.

        State based on purpose: the voucher is cancelled (or the credit
        note adjustment detached from it) before its entries are undone,
        so no context key, which RPC clients control, is needed to let the
        module's own transitions through.
        """
        vouchers = self._l10n_ve_iva_wh_protecting_vouchers()
        if vouchers:
            raise UserError(
                self.env._(
                    "Este asiento pertenece al comprobante de retención de IVA "
                    "emitido %s: no puede pasarse a borrador, anularse, "
                    "reversarse, eliminarse ni desconciliarse. Pase a borrador "
                    "o anule el documento del proveedor, o anule el "
                    "comprobante.",
                    ", ".join(vouchers.mapped("number")),
                )
            )

    def _l10n_ve_iva_wh_cancelled_vouchers(self):
        """Return the vouchers cancelled by posting these credit notes."""
        voucher_model = self.env["l10n.ve.iva.wh.voucher"].sudo()
        ids = [move_id for move_id in self.ids if move_id]
        if not ids:
            return voucher_model
        return voucher_model.search(
            [
                ("cancel_refund_id", "in", ids),
                ("company_id", "in", self.company_id.ids),
            ]
        )

    def _l10n_ve_iva_wh_check_cancelling_refund(self):
        vouchers = self._l10n_ve_iva_wh_cancelled_vouchers()
        if vouchers:
            raise UserError(
                self.env._(
                    "Esta nota de crédito anuló el comprobante de retención de "
                    "IVA %s, cuyo correlativo no puede reutilizarse, por lo que "
                    "no puede pasarse a borrador, anularse ni reversarse. "
                    "Registre una nueva factura del proveedor si corresponde.",
                    ", ".join(vouchers.mapped("number")),
                )
            )

    def button_draft(self):
        self._l10n_ve_iva_wh_check_protected()
        self._l10n_ve_iva_wh_check_cancelling_refund()
        refunds = self.filtered(lambda move: move.move_type == "in_refund")
        refunds._l10n_ve_iva_wh_remove_refund()
        (self - refunds)._l10n_ve_iva_wh_posted_vouchers()._l10n_ve_cancel()
        return super().button_draft()

    def button_cancel(self):
        # button_cancel resets posted moves through button_draft; checked
        # here too so draft-time changes cannot bypass it.
        self._l10n_ve_iva_wh_check_protected()
        return super().button_cancel()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_l10n_ve_iva_wh(self):
        self._l10n_ve_iva_wh_check_protected()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        self._l10n_ve_iva_wh_check_protected()
        if not cancel:
            return super()._reverse_moves(default_values_list, cancel=cancel)
        # Reversing with cancel unreconciles the document from its
        # withholding entry, so the withholding must be settled first.
        self._l10n_ve_iva_wh_check_cancelling_refund()
        default_values_list = default_values_list or [{} for _move in self]
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        to_cancel = []
        for move, values in zip(self, default_values_list, strict=True):
            if move.move_type == "in_refund":
                move._l10n_ve_iva_wh_remove_refund()
                continue
            vouchers = move._l10n_ve_iva_wh_posted_vouchers()
            if not vouchers:
                continue
            reversal_date = values.get("date") or move.date
            if not all(
                voucher_model._l10n_ve_same_wh_period(voucher.date, reversal_date)
                for voucher in vouchers
            ):
                raise UserError(
                    self.env._(
                        "La factura %s tiene un comprobante de retención de IVA "
                        "de un período anterior: no puede reversarse "
                        "anulándola. Emita una nota de crédito (sin retención) "
                        "en su lugar.",
                        move.display_name,
                    )
                )
            # Full credit note in the same period: the voucher is cancelled.
            to_cancel.append((move, vouchers))
        for _move, vouchers in to_cancel:
            vouchers._l10n_ve_cancel()
        reverse_moves = super()._reverse_moves(default_values_list, cancel=cancel)
        reverse_by_origin = {
            reverse.reversed_entry_id.id: reverse for reverse in reverse_moves
        }
        for move, vouchers in to_cancel:
            reverse = reverse_by_origin.get(move.id)
            if reverse:
                vouchers.sudo()._l10n_ve_write_unlocked(
                    {"cancel_refund_id": reverse.id}
                )
        return reverse_moves

    # ------------------------------------------------------------------
    # Vendor bills
    # ------------------------------------------------------------------

    def _l10n_ve_iva_wh_posted_vouchers(self):
        """Return the issued vouchers that withhold on these documents.

        Resolved from the voucher side on purpose: the pointer stored on the
        document is informative and writable over RPC, so it must not decide
        which voucher gets cancelled.
        """
        if not self.ids:
            return self.env["l10n.ve.iva.wh.voucher"]
        return (
            self.env["l10n.ve.iva.wh.voucher"]
            .sudo()
            .search(
                [
                    ("move_ids", "in", self.ids),
                    ("company_id", "in", self.company_id.ids),
                    ("wh_move_id", "!=", False),
                    ("state", "=", "posted"),
                ]
            )
            .sudo(False)
        )

    def action_l10n_ve_create_iva_wh(self):
        """Issue the withholding of bills posted before configuration."""
        eligible = self.filtered(lambda move: move._l10n_ve_iva_wh_is_eligible())
        if not eligible:
            raise UserError(
                self.env._(
                    "No corresponde retención de IVA: verifique que el documento "
                    "sea una factura de proveedor contabilizada, que la compañía "
                    "sea Sujeto Pasivo Especial a la fecha contable, que el "
                    "proveedor tenga RIF y porcentaje de retención, que el "
                    "documento tenga IVA, que no esté excluido y que no tenga ya "
                    "un comprobante."
                )
            )
        eligible._l10n_ve_iva_wh_create()
        return True

    def _l10n_ve_iva_wh_is_eligible(self):
        """Return whether the agent must withhold VAT on this document.

        Art. 13 PA SNAT/2025/000054: the withholding arises on payment or
        "abono en cuenta", whichever happens first; posting the vendor bill
        is the abono en cuenta. Art. 3 does not exclude vendors that are
        special taxpayers themselves, so they are withheld too.
        """
        self.ensure_one()
        company = self.company_id
        partner = self.commercial_partner_id
        if (
            self.state != "posted"
            or self.move_type not in L10N_VE_IVA_WH_MOVE_TYPES
            or self.country_code != "VE"
            or not company.l10n_ve_is_spe
            or self.l10n_ve_iva_wh_excluded
            or self._l10n_ve_iva_wh_posted_vouchers()
            or not partner.vat
            or not float(partner.l10n_ve_wh_iva_rate or "0")
        ):
            return False
        if company.l10n_ve_spe_date and self.date < company.l10n_ve_spe_date:
            return False
        tax = self.env["l10n.ve.iva.wh.voucher"]._l10n_ve_move_iva_amounts(self)["tax"]
        return company.currency_id.compare_amounts(tax, 0.0) > 0

    def _l10n_ve_iva_wh_payable_lines(self):
        """Return the payable lines of the document's first payable account."""
        self.ensure_one()
        payable_lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        return payable_lines.filtered(
            lambda line: line.account_id == payable_lines[:1].account_id
        )

    def _l10n_ve_iva_wh_to_document_currency(self, amount):
        """Convert a company-currency amount at the document's own rate.

        The withholding is computed and rounded in company currency
        (bolivars); the document currency amount is derived from it with
        the rate the document was posted with, so no exchange difference
        arises when it is reconciled with the document. A one-cent residual
        left in the document currency is settled by the standard exchange
        difference mechanism on full reconciliation.
        """
        self.ensure_one()
        if self.currency_id == self.company_id.currency_id:
            return amount
        if self.invoice_currency_rate:
            return self.currency_id.round(amount * self.invoice_currency_rate)
        return self.company_id.currency_id._convert(
            amount, self.currency_id, self.company_id, self.date
        )

    def _l10n_ve_iva_wh_create_entry(self, amount, label, sign):
        """Create and post a withholding entry for this document.

        :param sign: 1 moves the VAT from the vendor payable to the
            withholding account (bill); -1 returns it (credit note).
        """
        self.ensure_one()
        company = self.company_id
        partner = self.commercial_partner_id
        payable_account = self._l10n_ve_iva_wh_payable_lines()[:1].account_id
        amount_currency = self._l10n_ve_iva_wh_to_document_currency(amount)
        line_common = {
            "name": label,
            "partner_id": partner.id,
            "currency_id": self.currency_id.id,
        }
        wh_move = (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": company.l10n_ve_iva_wh_journal_id.id,
                    "date": self.date,
                    "ref": label,
                    "partner_id": partner.id,
                    "line_ids": [
                        Command.create(
                            {
                                **line_common,
                                "account_id": payable_account.id,
                                "amount_currency": sign * amount_currency,
                                "balance": sign * amount,
                            }
                        ),
                        Command.create(
                            {
                                **line_common,
                                "account_id": (
                                    company.l10n_ve_iva_wh_agent_account_id.id
                                ),
                                "amount_currency": -sign * amount_currency,
                                "balance": -sign * amount,
                            }
                        ),
                    ],
                }
            )
        )
        wh_move.action_post()
        return wh_move

    def _l10n_ve_iva_wh_check_configuration(self):
        self.ensure_one()
        company = self.company_id
        if (
            not company.l10n_ve_iva_wh_journal_id
            or not company.l10n_ve_iva_wh_agent_account_id
        ):
            raise UserError(
                self.env._(
                    "El documento %s está sujeto a retención de IVA: "
                    "configure el diario y la cuenta de Retenciones de IVA "
                    "por Enterar en Ajustes > Contabilidad > Localización "
                    "Venezuela.",
                    self.display_name,
                )
            )

    def _l10n_ve_iva_wh_create(self):
        """Issue voucher and withholding entry for each eligible document."""
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        vouchers = voucher_model
        for move in self:
            if not move._l10n_ve_iva_wh_is_eligible():
                continue
            move._l10n_ve_iva_wh_check_configuration()
            payable_lines = move._l10n_ve_iva_wh_payable_lines()
            if not payable_lines:
                continue
            company = move.company_id
            partner = move.commercial_partner_id
            rate = float(partner.l10n_ve_wh_iva_rate)
            amounts = voucher_model._l10n_ve_move_iva_amounts(move)
            withheld = voucher_model._l10n_ve_move_withheld(move, rate)
            # Invoicing users have read-only access to vouchers: issuing
            # one is a side effect of posting the bill, not a direct edit.
            voucher = voucher_model.sudo()._l10n_ve_create_unlocked(
                [
                    {
                        "date": move.date,
                        "company_id": company.id,
                        "partner_id": partner.id,
                        "move_ids": [Command.set(move.ids)],
                        "base_amount": amounts["base"],
                        "tax_amount": amounts["tax"],
                        "withheld_amount": withheld,
                        "exempt_amount": amounts["exempt"],
                        "wh_rate": rate,
                        "state": "posted",
                    }
                ]
            )
            label = self.env._(
                "Ret. IVA %(rate)s%% comprobante %(number)s - %(doc)s",
                rate=partner.l10n_ve_wh_iva_rate,
                number=voucher.number,
                doc=move.ref or move.name,
            )
            wh_move = move._l10n_ve_iva_wh_create_entry(withheld, label, 1.0)
            voucher._l10n_ve_write_unlocked({"wh_move_id": wh_move.id})
            voucher = voucher.sudo(False)
            move.l10n_ve_iva_wh_voucher_id = voucher
            # A document already settled (e.g. re-posted after payment) keeps
            # the withholding open on the vendor instead of failing.
            open_lines = payable_lines.filtered(lambda line: not line.reconciled)
            if open_lines:
                (
                    open_lines
                    + wh_move.line_ids.filtered(
                        lambda line, acc=payable_lines.account_id: line.account_id
                        == acc
                    )
                ).reconcile()
            vouchers |= voucher
        return vouchers

    # ------------------------------------------------------------------
    # Vendor credit notes (art. 11 PA SNAT/2025/000054; art. 58 Ley IVA)
    # ------------------------------------------------------------------

    def _l10n_ve_iva_wh_refund_voucher(self):
        """Return the posted voucher of the bill this credit note corrects.

        Only when the credit note falls in the same withholding period as
        that voucher: a credit note of a later period is not withheld and
        leaves the declared voucher untouched.
        """
        self.ensure_one()
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        bill = self.reversed_entry_id
        if (
            self.move_type != "in_refund"
            or self.state != "posted"
            or self.country_code != "VE"
            or not bill
            or bill.move_type not in L10N_VE_IVA_WH_MOVE_TYPES
            # The link is writable over RPC: a credit note of another
            # vendor or company must never touch this bill's voucher.
            or bill.company_id != self.company_id
            or bill.commercial_partner_id != self.commercial_partner_id
        ):
            return voucher_model
        voucher = bill._l10n_ve_iva_wh_posted_vouchers()
        if len(voucher) != 1 or self in voucher.move_ids:
            return voucher_model
        if not voucher_model._l10n_ve_same_wh_period(voucher.date, self.date):
            return voucher_model
        return voucher

    def _l10n_ve_iva_wh_apply_refund(self):
        """Apply posted vendor credit notes to the voucher of their bill.

        A credit note that brings the net VAT of the bill to zero cancels
        the voucher; a partial one is added to it and the withholding on
        its VAT is returned to the vendor payable.
        """
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        for refund in self:
            voucher = refund._l10n_ve_iva_wh_refund_voucher()
            if not voucher:
                continue
            refund_tax = voucher_model._l10n_ve_move_iva_amounts(refund)["tax"]
            currency = refund.company_id.currency_id
            if currency.compare_amounts(refund_tax, 0.0) <= 0:
                continue
            net_tax = voucher.tax_amount - refund_tax
            if currency.compare_amounts(net_tax, 0.0) <= 0:
                refund._l10n_ve_iva_wh_cancel_voucher(voucher)
            else:
                refund._l10n_ve_iva_wh_add_to_voucher(voucher)

    def _l10n_ve_iva_wh_cancel_voucher(self, voucher):
        """Total credit note: cancel the voucher and settle the documents."""
        self.ensure_one()
        voucher._l10n_ve_cancel()
        voucher.sudo()._l10n_ve_write_unlocked({"cancel_refund_id": self.id})
        # The withheld VAT is back on the bill: match it with the credit
        # note the standard reversal reconciliation could not fully use.
        lines = self._l10n_ve_iva_wh_payable_lines()
        open_lines = (voucher.move_ids - self).line_ids | lines
        open_lines = open_lines.filtered(
            lambda line: line.account_id == lines.account_id and not line.reconciled
        )
        if any(line.balance > 0 for line in open_lines) and any(
            line.balance < 0 for line in open_lines
        ):
            open_lines.reconcile()

    def _l10n_ve_iva_wh_add_to_voucher(self, voucher):
        """Partial credit note: add it to the voucher and adjust the entry."""
        self.ensure_one()
        self._l10n_ve_iva_wh_check_configuration()
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        withheld = voucher_model._l10n_ve_move_withheld(self, voucher.wh_rate)
        voucher_sudo = voucher.sudo()
        voucher_sudo._l10n_ve_write_unlocked({"move_ids": [Command.link(self.id)]})
        voucher_sudo._l10n_ve_write_unlocked(voucher_sudo._l10n_ve_compute_totals())
        self.l10n_ve_iva_wh_voucher_id = voucher
        if self.company_id.currency_id.is_zero(withheld):
            return
        lines = self._l10n_ve_iva_wh_payable_lines()
        # The standard reversal reconciliation already matched the credit
        # note with its bill. Undo it so the adjustment is matched with the
        # credit note first, then match what is left with the bill again.
        bill_partials = (lines.matched_debit_ids | lines.matched_credit_ids).filtered(
            lambda partial: (
                partial.debit_move_id.move_id | partial.credit_move_id.move_id
            )
            & (voucher.move_ids - self)
        )
        bill_partials.unlink()
        label = self.env._(
            "Ajuste Ret. IVA comprobante %(number)s - %(doc)s",
            number=voucher.number,
            doc=self.ref or self.name,
        )
        adjust_move = self._l10n_ve_iva_wh_create_entry(withheld, label, -1.0)
        self.env["l10n.ve.iva.wh.voucher.adjustment"].sudo().create(
            {
                "voucher_id": voucher.id,
                "refund_id": self.id,
                "move_id": adjust_move.id,
                "withheld_amount": withheld,
            }
        )
        (
            lines.filtered(lambda line: not line.reconciled)
            + adjust_move.line_ids.filtered(
                lambda line: line.account_id == lines.account_id
            )
        ).reconcile()
        if bill_partials:
            to_match = (
                (voucher.move_ids - self).line_ids.filtered(
                    lambda line: line.account_id == lines.account_id
                )
                | lines
            ).filtered(lambda line: not line.reconciled)
            if any(line.balance > 0 for line in to_match) and any(
                line.balance < 0 for line in to_match
            ):
                to_match.reconcile()

    def _l10n_ve_iva_wh_remove_refund(self):
        """Undo what posting these credit notes did to a posted voucher."""
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        for voucher in self._l10n_ve_iva_wh_posted_vouchers().sudo():
            refunds = self & voucher.move_ids
            adjustments = voucher.adjustment_ids.filtered(
                lambda adjustment, refunds=refunds: adjustment.refund_id in refunds
            )
            adjust_moves = adjustments.move_id
            # Detach first: the entries stop being protected once they no
            # longer belong to the posted voucher.
            adjustments.unlink()
            voucher._l10n_ve_write_unlocked(
                {"move_ids": [Command.unlink(refund.id) for refund in refunds]}
            )
            voucher._l10n_ve_write_unlocked(voucher._l10n_ve_compute_totals())
            for adjust_move in adjust_moves:
                voucher_model._l10n_ve_undo_move(adjust_move.sudo(False))
            refunds.sudo(False).l10n_ve_iva_wh_voucher_id = False
