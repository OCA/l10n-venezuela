from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_ve_igtf_feature_active = fields.Boolean(
        related="company_id.l10n_ve_igtf_feature_active",
    )

    l10n_ve_apply_igtf = fields.Boolean(string="Apply IGTF", default=False)
    l10n_ve_igtf_included = fields.Boolean(
        string="Include IGTF in amount",
        default=False,
        help=(
            "If enabled, the payment amount already includes IGTF. "
            "Example: Invoice 100, IGTF 3% => pay 103 to settle the "
            "invoice and record 3 as IGTF."
        ),
    )
    l10n_ve_igtf_currency_ids = fields.Many2many(
        related="company_id.l10n_ve_igtf_currency_ids",
        readonly=True,
    )
    l10n_ve_show_apply_igtf = fields.Boolean(
        string="Show Apply IGTF",
        compute="_compute_l10n_ve_show_apply_igtf",
        store=False,
    )
    l10n_ve_igtf_amount_company_currency = fields.Monetary(
        string="IGTF (Company currency)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_igtf_amount_company_currency",
        store=False,
        readonly=True,
        help="Computed IGTF amount expressed in the company currency.",
    )
    l10n_ve_igtf_amount_currency = fields.Monetary(
        string="IGTF (Payment currency)",
        currency_field="currency_id",
        compute="_compute_l10n_ve_igtf_amount_currency",
        store=False,
        readonly=True,
        help="Computed IGTF amount expressed in the payment currency.",
    )
    l10n_ve_igtf_cap_amount_company_currency = fields.Monetary(
        string="IGTF Cap (Company currency)",
        currency_field="company_currency_id",
        help="Maximum IGTF allowed for this payment from invoice residual IGTF.",
    )

    def _l10n_ve_igtf_block_manual_activation(self, vals):
        """
        Prevent enabling IGTF directly on payments.

        Parameters
        ----------
        vals : dict
            Values being written/created.

        Returns
        -------
        None

        Raises
        ------
        UserError
            If IGTF flags are being enabled outside the invoice payment register wizard.
        """
        if self.env.context.get("l10n_ve_igtf_from_register_payment"):
            return
        enable_apply = vals.get("l10n_ve_apply_igtf") is True
        enable_included = vals.get("l10n_ve_igtf_included") is True
        if enable_apply or enable_included:
            raise UserError(
                _(
                    "You cannot enable IGTF directly on the payment. "
                    "Please register the payment from the invoice wizard "
                    "(Register Payment)."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create payments enforcing IGTF activation rules.

        Parameters
        ----------
        vals_list : list[dict]
            Create values.

        Returns
        -------
        recordset
            Created payments.
        """
        for vals in vals_list:
            self._l10n_ve_igtf_block_manual_activation(vals)
        return super().create(vals_list)

    def write(self, vals):
        """
        Write payments enforcing IGTF activation rules.

        Parameters
        ----------
        vals : dict
            Write values.

        Returns
        -------
        bool
        """
        self._l10n_ve_igtf_block_manual_activation(vals)
        return super().write(vals)

    def _l10n_ve_igtf_payment_applies(self):
        self.ensure_one()
        return self.country_code == "VE" and self.company_id.l10n_ve_igtf_feature_active

    def _get_igtf_currency_ids(self):
        """
        Return the currencies that should trigger IGTF for the current company.

        Parameters
        ----------
        None

        Returns
        -------
        recordset
            `res.currency` recordset.
        """
        self.ensure_one()
        return self.company_id.l10n_ve_igtf_currency_ids

    @api.depends(
        "currency_id",
        "company_id",
        "company_id.l10n_ve_igtf_currency_ids",
        "company_id.l10n_ve_igtf_feature_active",
        "country_code",
        "reconciled_invoice_ids",
        "invoice_ids",
    )
    def _compute_l10n_ve_show_apply_igtf(self):
        for payment in self:
            if not payment._l10n_ve_igtf_payment_applies():
                payment.l10n_ve_show_apply_igtf = False
                continue
            allowed = payment.company_id.l10n_ve_igtf_currency_ids
            if not (payment.currency_id and payment.currency_id in allowed):
                payment.l10n_ve_show_apply_igtf = False
                continue
            invs = payment.reconciled_invoice_ids | payment.invoice_ids
            if any(m.l10n_ve_igtf_invoice_has_igtf_accrual() for m in invs):
                payment.l10n_ve_show_apply_igtf = False
                continue
            payment.l10n_ve_show_apply_igtf = True

    @api.depends(
        "l10n_ve_apply_igtf",
        "l10n_ve_igtf_included",
        "amount",
        "currency_id",
        "date",
        "company_id",
        "company_currency_id",
        "company_id.l10n_ve_igtf_percent",
    )
    def _compute_l10n_ve_igtf_amount_currency(self):
        """
        Compute IGTF amount in the payment currency.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        for payment in self:
            payment.l10n_ve_igtf_amount_currency = payment._l10n_ve_get_igtf_amounts()[
                0
            ]

    def _l10n_ve_get_igtf_amounts(self):
        self.ensure_one()
        if not self._l10n_ve_igtf_payment_applies():
            return 0.0, 0.0
        if any(
            m.l10n_ve_igtf_invoice_has_igtf_accrual()
            for m in (self.reconciled_invoice_ids | self.invoice_ids)
        ):
            return 0.0, 0.0
        percent = self.company_id.l10n_ve_igtf_percent or 0.0
        if not self.l10n_ve_apply_igtf or percent <= 0.0 or not self.currency_id:
            return 0.0, 0.0
        if self.currency_id not in self._get_igtf_currency_ids():
            return 0.0, 0.0
        p = percent / 100.0
        if self.l10n_ve_igtf_included:
            base_amount_currency = self.amount / (1.0 + p)
        else:
            base_amount_currency = self.amount
        base_amount_company = self.company_currency_id.round(
            self.currency_id._convert(
                base_amount_currency,
                self.company_currency_id,
                self.company_id,
                self.date,
            )
        )
        raw_igtf_company = self.company_currency_id.round(base_amount_company * p)
        igtf_company = raw_igtf_company
        if self.l10n_ve_igtf_cap_amount_company_currency:
            igtf_company = min(
                raw_igtf_company,
                self.company_currency_id.round(
                    self.l10n_ve_igtf_cap_amount_company_currency
                ),
            )
        if self.company_currency_id.is_zero(igtf_company):
            return 0.0, 0.0
        igtf_currency = self.currency_id.round(
            self.company_currency_id._convert(
                igtf_company,
                self.currency_id,
                self.company_id,
                self.date,
            )
        )
        return igtf_currency, igtf_company

    def _compute_l10n_ve_igtf_amount_company_currency(self):
        """
        Compute IGTF amount expressed in company currency.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        for payment in self:
            payment.l10n_ve_igtf_amount_company_currency = (
                payment._l10n_ve_get_igtf_amounts()[1]
            )

    def _prepare_move_line_default_vals(
        self, write_off_line_vals=None, force_balance=None
    ):
        """
        Split IGTF from receivable and post it to the IGTF payable account.

        Parameters
        ----------
        write_off_line_vals : dict | None
            Optional write-off line values.
        force_balance : float | None
            Optional forced balance.

        Returns
        -------
        list[dict]
            Journal item values for the payment entry.

        Raises
        ------
        UserError
            If computed IGTF exceeds the receivable counterpart amount.
        """
        self.ensure_one()

        line_vals_list = super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )

        if not self._l10n_ve_igtf_payment_applies():
            return line_vals_list

        if any(
            m.l10n_ve_igtf_invoice_has_igtf_accrual()
            for m in (self.reconciled_invoice_ids | self.invoice_ids)
        ):
            return line_vals_list

        company = self.company_id
        igtf_account = company.l10n_ve_igtf_account_id
        igtf_percent = company.l10n_ve_igtf_percent or 0.0

        if (
            not igtf_account
            or not self.l10n_ve_apply_igtf
            or igtf_percent <= 0.0
            or self.payment_type != "inbound"
            or self.destination_account_id.account_type != "asset_receivable"
            or self.currency_id not in self._get_igtf_currency_ids()
        ):
            return line_vals_list

        counterpart_line = next(
            (
                line
                for line in line_vals_list
                if line.get("account_id") == self.destination_account_id.id
            ),
            None,
        )
        if not counterpart_line:
            return line_vals_list

        p = igtf_percent / 100.0
        if self.l10n_ve_igtf_included:
            base_amount_currency = self.amount / (1.0 + p)
        else:
            base_amount_currency = self.amount

        base_amount_company_abs = company.currency_id.round(
            self.currency_id._convert(
                base_amount_currency,
                company.currency_id,
                company,
                self.date,
            )
        )
        raw_igtf_balance_abs = company.currency_id.round(base_amount_company_abs * p)
        if company.currency_id.is_zero(raw_igtf_balance_abs):
            return line_vals_list
        igtf_balance_abs = raw_igtf_balance_abs
        if self.l10n_ve_igtf_cap_amount_company_currency:
            igtf_balance_abs = min(
                igtf_balance_abs,
                company.currency_id.round(
                    self.l10n_ve_igtf_cap_amount_company_currency
                ),
            )
        if company.currency_id.is_zero(igtf_balance_abs):
            return line_vals_list

        igtf_amount_currency_abs = self.currency_id.round(
            company.currency_id._convert(
                igtf_balance_abs,
                self.currency_id,
                company,
                self.date,
            )
        )
        igtf_amount_currency = -igtf_amount_currency_abs

        counterpart_balance = counterpart_line.get("balance", 0.0)
        if counterpart_balance >= 0.0:
            return line_vals_list

        if abs(counterpart_balance) < igtf_balance_abs:
            raise UserError(
                _(
                    "Computed IGTF exceeds the payment amount. "
                    "Please review the IGTF percentage."
                )
            )

        counterpart_line["balance"] = company.currency_id.round(
            counterpart_balance + igtf_balance_abs
        )
        counterpart_line["amount_currency"] = self.currency_id.round(
            counterpart_line["amount_currency"] - igtf_amount_currency
        )

        igtf_line_vals = {
            "name": _("IGTF (%s%%)") % (igtf_percent,),
            "date_maturity": self.date,
            "amount_currency": igtf_amount_currency,
            "currency_id": self.currency_id.id,
            "balance": -igtf_balance_abs,
            "partner_id": False,
            "account_id": igtf_account.id,
        }

        idx = line_vals_list.index(counterpart_line)
        line_vals_list.insert(idx + 1, igtf_line_vals)
        return line_vals_list
