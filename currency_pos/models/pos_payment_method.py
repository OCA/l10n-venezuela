from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    payment_currency_id = fields.Many2one(
        "res.currency",
        string="Payment Currency",
        compute="_compute_payment_currency_id",
        store=True,
        readonly=True,
    )
    inbound_payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Incoming Payment Method",
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'inbound')]",
        check_company=True,
        help="Accounting payment method line used for cash in / incoming receipts on this journal.",
    )
    outbound_payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Outgoing Payment Method",
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'outbound')]",
        check_company=True,
        help="Accounting payment method line used for cash out / outgoing payments on this journal.",
    )
    inbound_payment_account_id = fields.Many2one(
        related="inbound_payment_method_line_id.payment_account_id",
        string="Outstanding Receipts Account",
        readonly=True,
    )
    outbound_payment_account_id = fields.Many2one(
        related="outbound_payment_method_line_id.payment_account_id",
        string="Outstanding Payments Account",
        readonly=True,
    )

    @api.depends("journal_id", "journal_id.currency_id", "company_id", "company_id.currency_id")
    def _compute_payment_currency_id(self):
        for method in self:
            if method.journal_id and method.journal_id.currency_id:
                method.payment_currency_id = method.journal_id.currency_id
            else:
                method.payment_currency_id = method.company_id.currency_id

    @api.onchange("journal_id")
    def _onchange_journal_id_payment_method_lines(self):
        for method in self:
            method._oca_sync_payment_method_lines_from_journal()

    def _oca_sync_payment_method_lines_from_journal(self):
        for method in self:
            journal = method.journal_id
            if not journal:
                method.inbound_payment_method_line_id = False
                method.outbound_payment_method_line_id = False
                continue
            inbound_lines = journal.inbound_payment_method_line_ids
            outbound_lines = journal.outbound_payment_method_line_ids
            if (
                not method.inbound_payment_method_line_id
                or method.inbound_payment_method_line_id.journal_id != journal
            ):
                method.inbound_payment_method_line_id = inbound_lines[:1]
            if (
                not method.outbound_payment_method_line_id
                or method.outbound_payment_method_line_id.journal_id != journal
            ):
                method.outbound_payment_method_line_id = outbound_lines[:1]

    @api.model_create_multi
    def create(self, vals_list):
        methods = super().create(vals_list)
        methods._oca_sync_payment_method_lines_from_journal()
        return methods

    def write(self, vals):
        result = super().write(vals)
        if "journal_id" in vals:
            self._oca_sync_payment_method_lines_from_journal()
        return result

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in (
            "payment_currency_id",
            "inbound_payment_method_line_id",
            "outbound_payment_method_line_id",
        ):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    def is_foreign_currency_for_config(self, config):
        self.ensure_one()
        if not config or not config.allow_multi_currency_payment:
            return False
        return self.payment_currency_id != config.currency_id

    def _oca_get_cash_move_payment_method_line(self, move_type):
        self.ensure_one()
        journal = self.journal_id
        if move_type == "in":
            return (
                self.inbound_payment_method_line_id
                or journal.inbound_payment_method_line_ids[:1]
            )
        return (
            self.outbound_payment_method_line_id
            or journal.outbound_payment_method_line_ids[:1]
        )

    def _oca_get_default_outstanding_account(self, payment_type):
        self.ensure_one()
        account_ref = (
            "account_journal_payment_debit_account_id"
            if payment_type == "inbound"
            else "account_journal_payment_credit_account_id"
        )
        chart_template = self.with_context(
            allowed_company_ids=self.company_id.root_id.ids
        ).env["account.chart.template"]
        return (
            chart_template.ref(account_ref, raise_if_not_found=False)
            or self.company_id.transfer_account_id
        )

    def _oca_get_cash_move_counterpart_account(self, move_type):
        self.ensure_one()
        line = self._oca_get_cash_move_payment_method_line(move_type)
        if line.payment_account_id:
            return line.payment_account_id
        if not line:
            return self.env["account.account"]
        payment_type = "inbound" if move_type == "in" else "outbound"
        return self._oca_get_default_outstanding_account(payment_type)

    def _oca_get_payment_outstanding_account_for_amount(self, amount):
        self.ensure_one()
        move_type = "in" if amount >= 0 else "out"
        return (
            self._oca_get_cash_move_counterpart_account(move_type)
            or self.outstanding_account_id
        )
