# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

from .islr_concept import PERSON_TYPES, tarifa2_tax

# Documents whose posting issues a voucher (abono en cuenta). Credit notes
# never issue one: they only adjust the voucher of the bill they refund.
L10N_VE_ISLR_MOVE_TYPES = ("in_invoice", "in_receipt")
# Decree 1,808 art. 9 second paragraph: tax units of the subtrahend.
L10N_VE_ISLR_SUBTRAHEND_FACTOR = 83.3334


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_islr_voucher_ids = fields.One2many(
        "l10n.ve.islr.voucher",
        "source_move_id",
        string="Comprobantes de Retención ISLR",
        readonly=True,
        copy=False,
        help="Comprobantes emitidos al contabilizar esta factura (abono en "
        "cuenta, art. 1 del Decreto 1.808): uno por concepto de retención.",
    )
    l10n_ve_islr_wh_pending = fields.Boolean(
        string="Retención ISLR Pendiente",
        compute="_compute_l10n_ve_islr_wh_pending",
        help="Factura contabilizada sujeta a retención de ISLR sin "
        "comprobante emitido (p. ej. contabilizada antes de configurar la "
        "retención o cuyo comprobante fue anulado).",
    )

    @api.depends(
        "state",
        "move_type",
        "country_code",
        "l10n_ve_islr_voucher_ids.state",
        "invoice_line_ids.l10n_ve_islr_concept_id",
        "reversal_move_ids.state",
    )
    def _compute_l10n_ve_islr_wh_pending(self):
        for move in self:
            move.l10n_ve_islr_wh_pending = move._l10n_ve_islr_wh_is_eligible()

    def _post(self, soft=True):
        self._l10n_ve_islr_check_vendor_rif()
        self._l10n_ve_islr_check_concepts_apply()
        posted = super()._post(soft=soft)
        ve_posted = posted.filtered(
            lambda move: move.state == "posted" and move.country_code == "VE"
        )
        ve_posted.filtered(
            lambda move: move.move_type in L10N_VE_ISLR_MOVE_TYPES
        )._l10n_ve_islr_wh_create()
        ve_posted.filtered(
            lambda move: move.move_type == "in_refund"
        )._l10n_ve_islr_apply_credit_notes()
        return posted

    def _l10n_ve_islr_check_vendor_rif(self):
        """Block bills subject to withholding of vendors without a valid RIF.

        The voucher and the SENIAT XML identify the withheld subject by its
        RIF (art. 24, Decree 1,808), so it must exist and pass the SENIAT
        check digit before the withholding is issued.
        """
        for move in self.filtered(
            lambda m: m.move_type in L10N_VE_ISLR_MOVE_TYPES
            and m.country_code == "VE"
            and m._l10n_ve_islr_get_wh_lines()
        ):
            partner = move.commercial_partner_id
            if not partner._l10n_ve_islr_get_valid_rif():
                raise UserError(
                    self.env._(
                        "La factura %(move)s está sujeta a retención de ISLR y "
                        "el proveedor %(partner)s no tiene un RIF válido (una "
                        "letra V/E/J/P/G, 8 dígitos y dígito verificador "
                        "correcto, ej. J-12345678-4). Corrija el RIF antes de "
                        "contabilizar.",
                        move=move.display_name,
                        partner=partner.display_name,
                    )
                )

    def _l10n_ve_islr_check_concepts_apply(self):
        """Block bills with a concept that does not apply to the vendor."""
        for move in self.filtered(
            lambda m: m.move_type in L10N_VE_ISLR_MOVE_TYPES and m.country_code == "VE"
        ):
            partner = move.commercial_partner_id
            person_type = partner.l10n_ve_person_type or "pj_dom"
            for concept in move._l10n_ve_islr_get_wh_lines().l10n_ve_islr_concept_id:
                move._l10n_ve_islr_check_concept_applies(concept, person_type)

    def _l10n_ve_islr_check_concept_applies(self, concept, person_type):
        """Raise when the concept has no SENIAT code for the person type.

        Such a concept cannot be declared (the XML would carry '000'), so
        the withholding stops instead of issuing a zero voucher or using the
        code of another concept.
        """
        self.ensure_one()
        if not concept._l10n_ve_islr_applies_to(person_type):
            raise UserError(
                self.env._(
                    "El concepto de retención ISLR %(concept)s no aplica al "
                    "proveedor %(partner)s, de tipo %(person_type)s: el "
                    "concepto no tiene código SENIAT para ese tipo de "
                    "persona. Cambie el concepto de la línea o el tipo de "
                    "persona del proveedor.",
                    concept=concept.name,
                    partner=self.commercial_partner_id.display_name,
                    person_type=dict(PERSON_TYPES)[person_type],
                )
            )

    # Protection of the withholding entries and of the credit notes that
    # adjusted a voucher. Vouchers are looked up from the voucher side, with
    # sudo and the company of the moves, never through a writable pointer.

    def _l10n_ve_islr_check_wh_move_unlocked(self):
        """Block any change to the entry of an issued voucher.

        The only way to undo it is cancelling the voucher, which changes
        its state before undoing the entry (state-based protection).
        """
        if not self.ids:
            return
        protected = (
            self.env["l10n.ve.islr.voucher"]
            .sudo()
            .search_count(
                [
                    ("wh_move_id", "in", self.ids),
                    ("state", "=", "issued"),
                    ("company_id", "in", self.company_id.ids),
                ],
                limit=1,
            )
        )
        if protected:
            raise UserError(
                self.env._(
                    "Este asiento corresponde a un comprobante de retención de "
                    "ISLR emitido: no puede pasarse a borrador, anularse, "
                    "revertirse, eliminarse ni desconciliarse de la factura. "
                    "Pase a borrador o anule la factura del proveedor, o anule "
                    "el comprobante."
                )
            )

    def _l10n_ve_islr_check_credit_note_unlocked(self):
        """Block undoing a credit note that adjusted a voucher.

        A same-month credit note cancelled or replaced the voucher of its
        bill. Restoring the previous voucher automatically could reopen a
        period already declared to SENIAT, so the credit note stays posted;
        a new vendor bill corrects it if needed.
        """
        # The adjusted vouchers are found through the link stored when the
        # credit note cancelled them, never re-derived from its current
        # lines or from the writable reversed_entry_id.
        for credit_note in self.filtered(
            lambda move: move.move_type == "in_refund" and move.state == "posted"
        ):
            adjusted = (
                self.env["l10n.ve.islr.voucher"]
                .sudo()
                .search(
                    [
                        ("credit_note_id", "=", credit_note.id),
                        ("company_id", "=", credit_note.company_id.id),
                    ],
                    limit=1,
                )
            )
            if adjusted:
                raise UserError(
                    self.env._(
                        "La nota de crédito %(credit_note)s ajustó la retención "
                        "de ISLR de la factura %(bill)s en el mismo período: no "
                        "puede pasarse a borrador ni anularse. Para revertir su "
                        "efecto registre una nueva factura del proveedor.",
                        credit_note=credit_note.display_name,
                        bill=adjusted.source_move_id.display_name,
                    )
                )

    def button_draft(self):
        self._l10n_ve_islr_check_wh_move_unlocked()
        self._l10n_ve_islr_check_credit_note_unlocked()
        # Invoicing users only read vouchers: cancel them with sudo; the
        # entry itself is undone with the caller's rights.
        self.sudo().l10n_ve_islr_voucher_ids.filtered(
            lambda voucher: voucher.state == "issued"
        ).action_cancel()
        return super().button_draft()

    def button_cancel(self):
        self._l10n_ve_islr_check_wh_move_unlocked()
        self._l10n_ve_islr_check_credit_note_unlocked()
        return super().button_cancel()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_l10n_ve_islr_wh_move(self):
        self._l10n_ve_islr_check_wh_move_unlocked()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        self._l10n_ve_islr_check_wh_move_unlocked()
        if not cancel:
            return super()._reverse_moves(default_values_list, cancel=cancel)
        self._l10n_ve_islr_check_credit_note_unlocked()
        # A full refund breaks every reconciliation of the bill before
        # posting the credit note, the withholding entry included. Detach
        # it here through the trusted path; posting the credit note then
        # applies the ISLR rules (same month: the voucher is cancelled).
        vouchers = (
            self.env["l10n.ve.islr.voucher"]
            .sudo()
            .search(
                [
                    ("source_move_id", "in", self.ids),
                    ("state", "=", "issued"),
                    ("wh_move_id", "!=", False),
                    ("company_id", "in", self.company_id.ids),
                ]
            )
        )
        wh_lines = vouchers.wh_move_id.line_ids
        (wh_lines.matched_debit_ids | wh_lines.matched_credit_ids).sudo(
            False
        )._l10n_ve_unlink_unlocked()
        reverse_moves = super()._reverse_moves(default_values_list, cancel=cancel)
        # Vouchers still issued (credit note in a later month) keep their
        # entry reconciled with the bill; the credit note takes the rest.
        for voucher in vouchers.filtered(lambda v: v.state == "issued"):
            bill = voucher.source_move_id.sudo(False)
            bill_payable = bill._l10n_ve_islr_get_payable_lines()
            account = bill_payable.account_id[:1]
            wh_payable = voucher.wh_move_id.sudo(False).line_ids.filtered(
                lambda line, acc=account: line.account_id == acc
            )
            refund_payable = reverse_moves.filtered(
                lambda move, b=bill: move.reversed_entry_id == b
            ).line_ids.filtered(lambda line, acc=account: line.account_id == acc)
            (bill_payable + refund_payable).remove_move_reconcile()
            (bill_payable + wh_payable)._l10n_ve_islr_reconcile_open()
            (bill_payable + refund_payable)._l10n_ve_islr_reconcile_open()
        return reverse_moves

    # Withholding computation

    def action_l10n_ve_create_islr_wh(self):
        """Issue the withholding of bills posted before configuration."""
        eligible = self.filtered(lambda move: move._l10n_ve_islr_wh_is_eligible())
        if not eligible:
            raise UserError(
                self.env._(
                    "No corresponde retención de ISLR: verifique que el documento "
                    "sea una factura de proveedor contabilizada de una compañía "
                    "venezolana, que alguna línea tenga concepto de retención "
                    "ISLR y que no tenga ya comprobantes emitidos."
                )
            )
        eligible._l10n_ve_islr_wh_create()
        return True

    def _l10n_ve_islr_get_wh_lines(self):
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.l10n_ve_islr_concept_id
        )

    def _l10n_ve_islr_get_payable_lines(self):
        self.ensure_one()
        payable_lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        return payable_lines.filtered(
            lambda line, acc=payable_lines.account_id[:1]: line.account_id == acc
        )

    def _l10n_ve_islr_get_refunded_bill(self):
        """Return the bill this credit note refunds, if it is consistent.

        ``reversed_entry_id`` can be written over RPC: a credit note only
        adjusts the voucher of a bill of the same company and commercial
        partner, so a credit note of another vendor never cancels or nets
        it.
        """
        self.ensure_one()
        bill = self.reversed_entry_id
        if (
            bill
            and bill.company_id == self.company_id
            and bill.commercial_partner_id == self.commercial_partner_id
        ):
            return bill
        return self.browse()

    def _l10n_ve_islr_get_netting_credit_notes(self):
        """Return the posted credit notes netted against this bill.

        Only credit notes dated in the month of the voucher (the bill
        accounting date) reduce its base: the SENIAT XML has no document
        type and rejects negative amounts, so a later credit note does not
        touch a voucher already declared.
        """
        self.ensure_one()
        period = self.date.strftime("%Y%m")
        return self.reversal_move_ids.filtered(
            lambda move: move.state == "posted"
            and move.move_type == "in_refund"
            and move.date.strftime("%Y%m") == period
            and move._l10n_ve_islr_get_refunded_bill() == self
        )

    def _l10n_ve_islr_get_pending_concepts(self):
        """Return the concepts that still need an issued voucher.

        Evaluated on company currency balances so that it never needs an
        exchange rate (it backs a computed field).
        """
        self.ensure_one()
        concepts = self.env["l10n.ve.islr.concept"]
        if not (
            self.state == "posted"
            and self.move_type in L10N_VE_ISLR_MOVE_TYPES
            and self.country_code == "VE"
        ):
            return concepts
        lines = self._l10n_ve_islr_get_wh_lines()
        issued = self.l10n_ve_islr_voucher_ids.filtered(
            lambda voucher: voucher.state == "issued"
        ).concept_id
        credit_note_lines = (
            self._l10n_ve_islr_get_netting_credit_notes()._l10n_ve_islr_get_wh_lines()
        )
        currency = self.company_id.currency_id
        for concept in lines.l10n_ve_islr_concept_id - issued:
            # Bill lines are debits and credit note lines credits.
            net = sum(
                (lines + credit_note_lines)
                .filtered(lambda line, c=concept: line.l10n_ve_islr_concept_id == c)
                .mapped("balance")
            )
            if currency.compare_amounts(net, 0.0) > 0:
                concepts |= concept
        return concepts

    def _l10n_ve_islr_wh_is_eligible(self):
        """Return whether the agent must still withhold on this bill.

        Decree 1,808 art. 1: the withholding arises on payment or "abono en
        cuenta", whichever happens first; posting the vendor bill is the
        abono en cuenta.
        """
        self.ensure_one()
        return bool(self._l10n_ve_islr_get_pending_concepts())

    def _l10n_ve_islr_get_ves_base(self, lines):
        """Return the untaxed amount of the lines in bolivars, in cents.

        The withholding is a bolivar amount: it is computed on the amounts
        the bill booked in bolivars, never in another currency multiplied
        by the rate.
        """
        self.ensure_one()
        ut_model = self.env["l10n.ve.ut"]
        ves = ut_model._get_ves_currency()
        if self.currency_id == ves:
            return ves.round(sum(lines.mapped("price_subtotal")))
        sign = -1.0 if self.move_type == "in_refund" else 1.0
        base = sign * sum(lines.mapped("balance"))
        company_currency = self.company_id.currency_id
        if company_currency == ves:
            return ves.round(base)
        ut_model._require_ves_rate(self.company_id, self.date)
        return company_currency._convert(base, ves, self.company_id, self.date)

    def _l10n_ve_islr_from_ves(self, amount_ves):
        """Return (amount in document currency, balance) of a VES amount.

        The bolivar amount is final; the other currencies are derived from
        it. A cent of difference left in a foreign currency once the bill
        is fully paid is settled by the standard exchange difference.
        """
        self.ensure_one()
        ut_model = self.env["l10n.ve.ut"]
        ves = ut_model._get_ves_currency()
        company = self.company_id
        company_currency = company.currency_id
        currency = self.currency_id
        if company_currency == ves:
            balance = amount_ves
        elif currency == ves and self.invoice_currency_rate:
            balance = company_currency.round(amount_ves / self.invoice_currency_rate)
        else:
            ves = ut_model._require_ves_rate(company, self.date)
            balance = ves._convert(amount_ves, company_currency, company, self.date)
        if currency == ves:
            amount_currency = amount_ves
        elif currency == company_currency or not self.invoice_currency_rate:
            amount_currency = balance
        else:
            amount_currency = currency.round(balance * self.invoice_currency_rate)
        return amount_currency, balance

    def _l10n_ve_islr_get_subtrahend(self, concept, person_type):
        """Return the subtrahend in bolivars.

        Decree 1,808 art. 9 second paragraph: tax unit in force at the
        accounting date x rate x 83.3334, for resident individuals only.
        """
        self.ensure_one()
        if not concept.apply_subtrahend or person_type != "pn_res":
            return 0.0
        ut_model = self.env["l10n.ve.ut"]
        ut_value = ut_model.get_ut_value(self.date)
        return ut_model._get_ves_currency().round(
            ut_value * concept.rate_pn_res / 100.0 * L10N_VE_ISLR_SUBTRAHEND_FACTOR
        )

    def _l10n_ve_islr_get_tarifa2_prior_base(self, concept):
        """Return the Tarifa N° 2 taxable base of the vendor before a voucher.

        Sum of the taxable bases of the issued Tarifa N° 2 vouchers of the
        commercial partner and company in the calendar year of the bill that
        precede the voucher of this bill and concept, ordered by date, bill
        and concept. Cancelled vouchers do not count. Ordering by document
        instead of by issue time keeps the result independent of the order
        in which bills and credit notes are posted.
        """
        self.ensure_one()
        key = (self.date, self.id, concept.id)
        vouchers = (
            self.env["l10n.ve.islr.voucher"]
            .sudo()
            .search(
                [
                    ("partner_id", "=", self.commercial_partner_id.id),
                    ("company_id", "=", self.company_id.id),
                    ("state", "=", "issued"),
                    ("is_tarifa2", "=", True),
                    ("date", ">=", self.date.replace(month=1, day=1)),
                    ("date", "<=", self.date),
                ]
            )
        )
        return sum(
            voucher.taxable_base
            for voucher in vouchers
            if voucher._l10n_ve_islr_tarifa2_key() < key
        )

    def _l10n_ve_islr_get_wh_values(self, concepts=None, templates=None):
        """Return one withholding dict per concept, in bolivars.

        The base is the untaxed amount of the bill lines (VAT is not part of
        it) minus the same-month credit notes of the bill for that concept.
        ``templates`` maps a concept to the voucher being replaced, whose
        person type and treaty are kept.
        """
        self.ensure_one()
        ut_model = self.env["l10n.ve.ut"]
        ves = ut_model._get_ves_currency()
        partner = self.commercial_partner_id
        partner_person_type = partner.l10n_ve_person_type or "pj_dom"
        templates = templates or {}
        lines = self._l10n_ve_islr_get_wh_lines()
        credit_notes = self._l10n_ve_islr_get_netting_credit_notes()
        # Tarifa N° 2 base of the concepts computed earlier in this call.
        tarifa2_running = 0.0
        result = []
        # Sorted like the Tarifa N° 2 voucher key (date, bill, concept).
        for concept in lines.l10n_ve_islr_concept_id.sorted("id"):
            if concepts is not None and concept not in concepts:
                continue
            base = self._l10n_ve_islr_get_ves_base(
                lines.filtered(
                    lambda line, c=concept: line.l10n_ve_islr_concept_id == c
                )
            )
            for credit_note in credit_notes:
                cn_lines = credit_note._l10n_ve_islr_get_wh_lines().filtered(
                    lambda line, c=concept: line.l10n_ve_islr_concept_id == c
                )
                if cn_lines:
                    base -= credit_note._l10n_ve_islr_get_ves_base(cn_lines)
            base = ves.round(base)
            if ves.compare_amounts(base, 0.0) <= 0:
                continue
            template = templates.get(concept)
            if template:
                person_type = template.person_type
                treaty = template.treaty_applied
                treaty_rate = template.rate
                certificate = template.treaty_certificate
            else:
                person_type = partner_person_type
                treaty = partner._l10n_ve_islr_treaty_applies(person_type)
                treaty_rate = partner.l10n_ve_islr_treaty_rate
                certificate = partner.l10n_ve_islr_treaty_certificate
            self._l10n_ve_islr_check_concept_applies(concept, person_type)
            values = {
                "concept": concept,
                "person_type": person_type,
                "base": base,
                "subtrahend": 0.0,
                "is_tarifa2": False,
                "treaty_applied": bool(treaty),
                "treaty_certificate": (certificate or False) if treaty else False,
            }
            if treaty:
                # The treaty rate replaces the computed one, on the gross.
                values.update(
                    base_pct=100.0,
                    taxable_base=base,
                    rate=treaty_rate,
                    amount=ves.round(base * treaty_rate / 100.0),
                )
            elif concept._is_tarifa2(person_type):
                base_pct = concept._get_base_pct(person_type)
                taxable_base = ves.round(base * base_pct / 100.0)
                prior = (
                    self._l10n_ve_islr_get_tarifa2_prior_base(concept) + tarifa2_running
                )
                ut_value = ut_model.get_ut_value(self.date)
                amount = ves.round(
                    tarifa2_tax(prior + taxable_base, ut_value)
                    - tarifa2_tax(prior, ut_value)
                )
                tarifa2_running += taxable_base
                values.update(
                    base_pct=base_pct,
                    taxable_base=taxable_base,
                    is_tarifa2=True,
                    # Effective rate on the taxable base.
                    rate=float_round(
                        amount / taxable_base * 100.0 if taxable_base else 0.0,
                        precision_digits=2,
                    ),
                    amount=amount,
                )
            else:
                base_pct = concept._get_base_pct(person_type)
                taxable_base = ves.round(base * base_pct / 100.0)
                rate = concept._get_rate(person_type)
                subtrahend = self._l10n_ve_islr_get_subtrahend(concept, person_type)
                values.update(
                    base_pct=base_pct,
                    taxable_base=taxable_base,
                    rate=rate,
                    subtrahend=subtrahend,
                    amount=ves.round(taxable_base * rate / 100.0 - subtrahend),
                )
            values["amount"] = max(values["amount"], 0.0)
            result.append(values)
        return result

    def _l10n_ve_islr_wh_create(
        self, concepts=None, templates=None, reissue_later=True
    ):
        """Issue vouchers and withholding entries for pending concepts.

        One voucher per bill and withholding concept, in bolivars. Vouchers
        are created with sudo because invoicing users only read them. Bills
        are processed in Tarifa N° 2 order (date, then bill); unless
        ``reissue_later`` is False, the Tarifa N° 2 vouchers of the same
        vendor and month that follow the new ones are re-issued.
        """
        voucher_model = self.env["l10n.ve.islr.voucher"].sudo()
        vouchers = voucher_model
        ves = self.env["l10n.ve.ut"]._get_ves_currency()
        for move in self.sorted(lambda m: (m.date, m.id)):
            pending = move._l10n_ve_islr_get_pending_concepts()
            if concepts is not None:
                pending &= concepts
            if not pending:
                continue
            company = move.company_id
            journal = company.l10n_ve_islr_wh_journal_id
            account = company.l10n_ve_islr_wh_account_id
            if not journal or not account:
                raise UserError(
                    self.env._(
                        "El documento %s está sujeto a retención de ISLR: "
                        "configure el diario y la cuenta de Retenciones ISLR "
                        "por Enterar en Ajustes > Contabilidad > Localización "
                        "Venezuela - Retención ISLR.",
                        move.display_name,
                    )
                )
            payable_lines = move._l10n_ve_islr_get_payable_lines()
            if not payable_lines:
                continue
            payable_account = payable_lines.account_id
            partner = move.commercial_partner_id
            for values in move._l10n_ve_islr_get_wh_values(pending, templates):
                voucher = voucher_model._l10n_ve_create_unlocked(
                    {
                        "date": move.date,
                        "company_id": company.id,
                        "currency_id": ves.id,
                        "partner_id": partner.id,
                        "source_move_id": move.id,
                        "move_ids": [Command.set(move.ids)],
                        "concept_id": values["concept"].id,
                        "person_type": values["person_type"],
                        "seniat_code": values["concept"]._get_seniat_code(
                            values["person_type"]
                        ),
                        "base": values["base"],
                        "base_pct": values["base_pct"],
                        "taxable_base": values["taxable_base"],
                        "is_tarifa2": values["is_tarifa2"],
                        "treaty_applied": values["treaty_applied"],
                        "treaty_certificate": values["treaty_certificate"],
                        "rate": values["rate"],
                        "subtrahend": values["subtrahend"],
                        "amount": values["amount"],
                        "state": "issued",
                    }
                )
                vouchers |= voucher
                # A zero voucher is still issued (SENIAT completeness rule)
                # but moves no money.
                if ves.is_zero(values["amount"]):
                    continue
                amount_currency, balance = move._l10n_ve_islr_from_ves(values["amount"])
                label = self.env._(
                    "Ret. ISLR %(concept)s comprobante %(number)s - %(doc)s",
                    concept=values["concept"].name,
                    number=voucher.number,
                    doc=move.ref or move.name,
                )
                line_common = {
                    "name": label,
                    "partner_id": partner.id,
                    "currency_id": move.currency_id.id,
                }
                wh_move = (
                    self.env["account.move"]
                    .with_company(company)
                    .create(
                        {
                            "move_type": "entry",
                            "journal_id": journal.id,
                            "date": move.date,
                            "ref": label,
                            "partner_id": partner.id,
                            "line_ids": [
                                Command.create(
                                    {
                                        **line_common,
                                        "account_id": payable_account.id,
                                        "amount_currency": amount_currency,
                                        "balance": balance,
                                    }
                                ),
                                Command.create(
                                    {
                                        **line_common,
                                        "account_id": account.id,
                                        "amount_currency": -amount_currency,
                                        "balance": -balance,
                                    }
                                ),
                            ],
                        }
                    )
                )
                wh_move.action_post()
                voucher._l10n_ve_write_unlocked({"wh_move_id": wh_move.id})
                # A bill already settled (e.g. re-posted after payment)
                # keeps the withholding open on the vendor instead of failing.
                (
                    payable_lines
                    + wh_move.line_ids.filtered(
                        lambda line, acc=payable_account: line.account_id == acc
                    )
                )._l10n_ve_islr_reconcile_open()
        if reissue_later:
            self._l10n_ve_islr_tarifa2_reissue_later(vouchers)
        return vouchers

    def _l10n_ve_islr_tarifa2_reissue_later(self, vouchers):
        """Re-issue the Tarifa N° 2 vouchers that follow the given ones.

        A Tarifa N° 2 withholding depends on the taxable base of the vendor
        vouchers that precede it in the year. When a voucher is inserted
        before others (a backdated bill) or replaced on a different base (a
        same-month credit note), the issued vouchers of the same vendor,
        company and month that follow it are cancelled and re-issued in
        order. Vouchers of other months are never touched: they may already
        be declared to SENIAT.
        """
        voucher_model = self.env["l10n.ve.islr.voucher"].sudo()
        anchors = vouchers.filtered("is_tarifa2")
        later = voucher_model
        for anchor in anchors:
            candidates = voucher_model.search(
                [
                    ("partner_id", "=", anchor.partner_id.id),
                    ("company_id", "=", anchor.company_id.id),
                    ("period", "=", anchor.period),
                    ("state", "=", "issued"),
                    ("is_tarifa2", "=", True),
                    ("source_move_id", "!=", False),
                    ("id", "not in", anchors.ids),
                ]
            )
            key = anchor._l10n_ve_islr_tarifa2_key()
            later |= candidates.filtered(
                lambda voucher, k=key: voucher._l10n_ve_islr_tarifa2_key() > k
            )
        if not later:
            return
        later = later.sorted(lambda voucher: voucher._l10n_ve_islr_tarifa2_key())
        later.action_cancel()
        bills = self.browse()
        for voucher in later:
            if voucher.source_move_id not in bills:
                bills |= voucher.source_move_id
        for bill in bills:
            bill_vouchers = later.filtered(
                lambda voucher, b=bill: voucher.source_move_id == b
            )
            bill.sudo(False)._l10n_ve_islr_wh_create(
                concepts=bill_vouchers.concept_id,
                templates={v.concept_id: v for v in bill_vouchers},
                reissue_later=False,
            )

    def _l10n_ve_islr_apply_credit_notes(self):
        """Adjust the voucher of the bill refunded by each credit note.

        Decree 1,808 art. 1 and PA SNAT/2009/0095: the SENIAT XML rejects
        negative amounts and has no document type, so a credit note never
        issues a voucher. When it is dated in the month of the bill voucher,
        the voucher of each refunded concept is cancelled and, if a positive
        base remains, a new voucher is issued on the net base. A credit note
        of a later month leaves the declared voucher untouched.
        """
        for credit_note in self:
            bill = credit_note._l10n_ve_islr_get_refunded_bill()
            if (
                not bill
                or bill.state != "posted"
                or bill.move_type not in L10N_VE_ISLR_MOVE_TYPES
            ):
                continue
            concepts = credit_note._l10n_ve_islr_get_wh_lines().l10n_ve_islr_concept_id
            period = credit_note.date.strftime("%Y%m")
            vouchers = bill.sudo().l10n_ve_islr_voucher_ids.filtered(
                lambda voucher, p=period, c=concepts: voucher.state == "issued"
                and voucher.period == p
                and voucher.concept_id in c
            )
            if not vouchers:
                continue
            vouchers._l10n_ve_write_unlocked({"credit_note_id": credit_note.id})
            vouchers.action_cancel()
            # The net voucher keeps the person type and treaty snapshotted
            # on the voucher it replaces.
            new_vouchers = bill._l10n_ve_islr_wh_create(
                concepts=vouchers.concept_id,
                templates={v.concept_id: v for v in vouchers},
                reissue_later=False,
            )
            # The later Tarifa N° 2 vouchers of the vendor in the month are
            # recomputed on the net, whether or not a net voucher remains.
            bill._l10n_ve_islr_tarifa2_reissue_later(vouchers | new_vouchers)
            account = bill._l10n_ve_islr_get_payable_lines().account_id
            (bill.line_ids + credit_note.line_ids).filtered(
                lambda line, acc=account: line.account_id == acc
            )._l10n_ve_islr_reconcile_open()
