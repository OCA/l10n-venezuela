# © 2016 ADHOC SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_group_id = fields.Many2one(
        "account.payment.group",
        "Payment Group",
        ondelete="cascade",
        readonly=True,
    )
    # we add this field so company can be send in context when adding payments
    # before payment group is saved
    payment_group_company_id = fields.Many2one(
        related="payment_group_id.company_id",
        string="Payment Group Company",
    )
    # we make a copy without transfer option, we try with related but it
    # does not works
    payment_type_copy = fields.Selection(
        selection=[("outbound", "Send Money"), ("inbound", "Receive Money")],
        compute="_compute_payment_type_copy",
        inverse="_inverse_payment_type_copy",
        string="Payment Type (without transfer)",
    )
    signed_amount = fields.Monetary(
        compute="_compute_signed_amount",
    )
    signed_amount_company_currency = fields.Monetary(
        string="Payment Amount on Company Currency",
        compute="_compute_signed_amount",
        currency_field="company_currency_id",
    )
    amount_company_currency = fields.Monetary(
        string="Amount on Company Currency",
        compute="_compute_amount_company_currency",
        inverse="_inverse_amount_company_currency",
        currency_field="company_currency_id",
    )
    other_currency = fields.Boolean(
        compute="_compute_other_currency",
    )
    force_amount_company_currency = fields.Monetary(
        string="Forced Amount on Company Currency",
        currency_field="company_currency_id",
        copy=False,
    )
    exchange_rate = fields.Float(
        string="Exchange Rate",
        compute="_compute_exchange_rate",
        # readonly=False,
        # inverse='_inverse_exchange_rate',
        digits=(16, 4),
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company currency",
    )

    @api.depends("amount", "payment_type", "partner_type", "amount_company_currency")
    def _compute_signed_amount(self):
        for rec in self:
            sign = 1.0
            if (rec.partner_type == "supplier" and rec.payment_type == "inbound") or (
                rec.partner_type == "customer" and rec.payment_type == "outbound"
            ):
                sign = -1.0
            rec.signed_amount = rec.amount and rec.amount * sign
            rec.signed_amount_company_currency = (
                rec.amount_company_currency and rec.amount_company_currency * sign
            )

    # TODO check why we get error with depend on company_id and fix it
    # (recursive dependency?). The error is on payments tree/form view
    # @api.depends('currency_id', 'company_id')
    @api.depends("currency_id")
    def _compute_other_currency(self):
        for rec in self:
            rec.other_currency = False
            if (
                rec.company_currency_id
                and rec.currency_id
                and rec.company_currency_id != rec.currency_id
            ):
                rec.other_currency = True

    @api.onchange("payment_group_id")
    def onchange_payment_group_id(self):
        if self.payment_group_id.payment_difference:
            self.amount = self.payment_group_id.payment_difference

    @api.depends("amount", "other_currency", "amount_company_currency")
    def _compute_exchange_rate(self):
        for rec in self:
            if rec.other_currency:
                rec.exchange_rate = (
                    rec.amount and (rec.amount_company_currency / rec.amount) or 0.0
                )
            else:
                rec.exchange_rate = False

    # this onchange is necessary because Odoo, sometimes, re-compute
    # and overwrites amount_company_currency. That happens due to an issue
    # with rounding of amount field (amount field is not change but due to
    # rouding Odoo believes amount has changed)
    @api.onchange("amount_company_currency")
    def _inverse_amount_company_currency(self):
        for rec in self.with_context(skip_account_move_synchronization=True):
            if (
                rec.other_currency
                and rec.amount_company_currency
                != rec.currency_id._convert(
                    rec.amount, rec.company_id.currency_id, rec.company_id, rec.date
                )
            ):
                force_amount_company_currency = rec.amount_company_currency
            else:
                force_amount_company_currency = False
            rec.force_amount_company_currency = force_amount_company_currency

    @api.depends("amount", "other_currency", "force_amount_company_currency")
    def _compute_amount_company_currency(self):
        """
        * Si las monedas son iguales devuelve 1
        * si no, si hay force_amount_company_currency, devuelve ese valor
        * sino, devuelve el amount convertido a la moneda de la cia
        """
        for rec in self.with_context(skip_account_move_synchronization=True):
            if not rec.other_currency:
                amount_company_currency = rec.amount
            elif rec.force_amount_company_currency:
                amount_company_currency = rec.force_amount_company_currency
            else:
                amount_company_currency = rec.currency_id._convert(
                    rec.amount, rec.company_id.currency_id, rec.company_id, rec.date
                )
            rec.amount_company_currency = amount_company_currency

    @api.onchange("payment_type_copy")
    def _inverse_payment_type_copy(self):
        for rec in self:
            # if false, then it is a transfer
            rec.payment_type = rec.payment_type_copy and rec.payment_type_copy
            # rec.payment_type_copy and rec.payment_type_copy or 'transfer')

    @api.depends("payment_type")
    def _compute_payment_type_copy(self):
        for rec in self.with_context(skip_account_move_synchronization=True):
            if rec.payment_type == "transfer":
                rec.payment_type_copy = False
            else:
                rec.payment_type_copy = rec.payment_type

    def get_journals_domain(self):
        domain = super(AccountPayment, self).get_journals_domain()
        if self.payment_group_company_id:
            domain.append(("company_id", "=", self.payment_group_company_id.id))
        return domain

    @api.onchange("payment_type")
    def _onchange_payment_type(self):
        """
        we disable change of partner_type if we came from a payment_group
        but we still reset the journal
        """
        if not self._context.get("payment_group"):
            return super(AccountPayment, self)._onchange_payment_type()
        self.journal_id = False

    @api.constrains("payment_group_id", "payment_type")
    def check_payment_group(self):
        # Odoo tests don't create payments with payment groups
        if self.env.registry.in_test_mode():
            return True
        counterpart_aml_dicts = self._context.get("counterpart_aml_dicts")
        counterpart_aml_dicts = counterpart_aml_dicts or [{}]
        for rec in self:
            receivable_payable = all(
                [
                    x.get("move_line")
                    and x.get("move_line").account_id.internal_type
                    in ["receivable", "payable"]
                    for x in counterpart_aml_dicts
                ]
            )
            if (
                rec.partner_type
                and rec.partner_id
                and receivable_payable
                and not rec.payment_group_id
            ):
                raise ValidationError(
                    _("Payments with partners must be created from " "payments groups")
                )
            # transfers or payments from bank reconciliation without partners
            elif not rec.partner_type and rec.payment_group_id:
                raise ValidationError(
                    _(
                        "Payments without partners (usually transfers) cant't "
                        "have a related payment group"
                    )
                )

    @api.model
    def get_amls(self):
        """Review parameters of process_reconciliation() method and transform
        them to amls recordset. this one is return to recompute the payment
        values
         context keys(
            'counterpart_aml_dicts', 'new_aml_dicts', 'payment_aml_rec')
         :return: account move line recordset
        """
        counterpart_aml_dicts = self._context.get("counterpart_aml_dicts")
        counterpart_aml_data = counterpart_aml_dicts or [{}]
        new_aml_data = self._context.get("new_aml_dicts", [])
        amls = self.env["account.move.line"]
        if counterpart_aml_data:
            for item in counterpart_aml_data:
                amls |= item.get("move_line", self.env["account.move.line"])
        if new_aml_data:
            for aml_values in new_aml_data:
                amls |= amls.new(aml_values)
        return amls

    @api.model
    def infer_partner_info(self, vals):
        """Odoo way to to interpret the partner_id, partner_type is not
        useful for us because in some time they leave this ones empty and
        we need them in order to create the payment group.

        In this method will try to improve infer when it has a debt related
        taking into account the account type of the line to concile, and
        computing the partner if this ones is not setted when concile
        operation.

        return dictionary with keys (partner_id, partner_type)
        """
        res = {}
        # Get related amls
        amls = self.get_amls()
        if not amls:
            return res

        # Odoo manda partner type según si el pago es positivo o no, nosotros
        # mejoramos infiriendo a partir de que tipo de deuda se esta pagando
        partner_type = False
        internal_type = amls.mapped("account_id.internal_type")
        if len(internal_type) == 1:
            if internal_type == ["payable"]:
                partner_type = "supplier"
            elif internal_type == ["receivable"]:
                partner_type = "customer"
            if partner_type:
                res.update({"partner_type": partner_type})

        # por mas que el usuario no haya seleccionado partner, si esta pagando
        # deuda usamos el partner de esa deuda
        partner_id = vals.get("partner_id", False)
        if not partner_id and len(amls.mapped("partner_id")) == 1:
            partner_id = amls.mapped("partner_id").id
            res.update({"partner_id": partner_id})

        return res

    @api.model
    def create(self, vals):
        """When payments are created from bank reconciliation create the
        Payment group before creating payment to avoid raising error, only
        apply when the all the counterpart account are receivable/payable"""
        # Si viene counterpart_aml entonces estamos viniendo de una
        # conciliación desde el wizard
        new_aml_dicts = self._context.get("new_aml_dicts", [])
        counterpart_aml_dicts = self._context.get("counterpart_aml_dicts")
        counterpart_aml_data = counterpart_aml_dicts or [{}]
        if counterpart_aml_data or new_aml_dicts:
            vals.update(self.infer_partner_info(vals))

        create_from_statement = (
            self._context.get("create_from_statement", False)
            and vals.get("partner_type")
            and vals.get("partner_id")
            and all(
                [
                    x.get("move_line")
                    and x.get("move_line").account_id.internal_type
                    in ["receivable", "payable"]
                    for x in counterpart_aml_data
                ]
            )
        )
        create_from_expense = self._context.get("create_from_expense", False)
        create_from_website = self._context.get("create_from_website", False)
        # NOTE: This is required at least from POS when we do not have
        # partner_id and we do not want a payment group in tha case.
        create_payment_group = (
            create_from_statement or create_from_website or create_from_expense
        )
        if create_payment_group:
            company_id = (
                self.env["account.journal"].browse(vals.get("journal_id")).company_id.id
            )
            payment_group = self.env["account.payment.group"].create(
                {
                    "company_id": company_id,
                    "partner_type": vals.get("partner_type"),
                    "partner_id": vals.get("partner_id"),
                    "date": vals.get("date", fields.Date.context_today(self)),
                    "communication": vals.get("communication"),
                }
            )
            vals["payment_group_id"] = payment_group.id
        payment = super(AccountPayment, self).create(vals)
        if create_payment_group:
            payment.payment_group_id.post()
        return payment

    @api.depends("invoice_line_ids", "payment_type", "partner_type", "partner_id")
    def _compute_destination_account_id(self):
        """
        If we are paying a payment group with paylines, we use account
        of lines that are going to be paid
        """
        for rec in self.with_context(skip_account_move_synchronization=True):
            to_pay_account = rec.payment_group_id.to_pay_move_line_ids.mapped(
                "account_id"
            )
            if len(to_pay_account) > 1:
                raise ValidationError(_("To Pay Lines must be of the same account!"))
            elif len(to_pay_account) == 1:
                rec.destination_account_id = to_pay_account[0]
            else:
                super(AccountPayment, rec)._compute_destination_account_id()

    def show_details(self):
        """
        Método para mostrar form editable de payment, principalmente para ser
        usado cuando hacemos ajustes y el payment group esta confirmado pero
        queremos editar una linea
        """
        return {
            "name": _("Payment Lines"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "account.payment",
            "target": "new",
            "res_id": self.id,
            "context": self._context,
        }

    def _prepare_payment_moves(self):
        all_move_vals = []
        for rec in self:
            move_vals = super(AccountPayment, rec)._prepare_payment_moves()
            # If we have a communication on payment group append it
            # before payment communication
            if rec.payment_group_id.communication:
                move_vals[0]["ref"] = "%s%s" % (
                    self.payment_group_id.communication,
                    move_vals[0]["ref"] or "",
                )

            # Si se esta forzando importe en moneda de cia, usamos este
            # importe para débito/crédito
            if rec.force_amount_company_currency:
                for line in move_vals[0]["line_ids"]:
                    if line[2].get("debit"):
                        line[2]["debit"] = rec.force_amount_company_currency
                    if line[2].get("credit"):
                        line[2]["credit"] = rec.force_amount_company_currency
            all_move_vals += move_vals
        return all_move_vals

    # @api.depends('is_internal_transfer')
    # def _compute_partner_id(self):
    #     for pay in self:
    #         _logger.warning('ESTA ENTRANDO EN EL IFFFF')
    #         if pay.is_internal_transfer:
    #             pay.partner_id = pay.journal_id.company_id.partner_id

    @api.depends("partner_id")
    def _compute_partner_bank_id(self):
        """The default partner_bank_id will be the first available on the partner."""
        for pay in self:
            available_partner_bank_accounts = pay.partner_id.bank_ids.filtered(
                lambda x: x.company_id in (False, pay.company_id)
            )
            if available_partner_bank_accounts:
                if not pay.is_internal_transfer:
                    pay.partner_bank_id = available_partner_bank_accounts[0]._origin

            else:
                pay.partner_bank_id = False

    @api.depends("partner_id", "destination_account_id", "journal_id")
    def _onchange_is_internal_transfer(self):
        for payment in self:
            if payment.is_internal_transfer:
                payment.partner_id = payment.journal_id.company_id.partner_id
                is_partner_ok = (
                    payment.partner_id == payment.journal_id.company_id.partner_id
                )
                is_account_ok = (
                    payment.destination_account_id
                    and payment.destination_account_id
                    == payment.journal_id.company_id.transfer_account_id
                )
                payment.is_internal_transfer = is_partner_ok and is_account_ok
