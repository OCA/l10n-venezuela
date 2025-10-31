from odoo import api, Command, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    default_account_id = fields.Many2one(
        domain=(
            "[('deprecated', '=', False), ('company_id', '=', company_id),"
            "'|',('account_type', '=', default_account_type),"
            "('account_type', 'in', ('income', 'income_other') if type == 'sale' else ('expense', 'expense_depreciation', 'expense_direct_cost') if type == 'purchase' else ('asset_current', 'liability_current'))]"
        )
    )

    @api.depends("type", "currency_id")
    def _compute_inbound_payment_method_line_ids(self):
        journal_ids = self.env["account.journal"]
        for journal in self:
            pay_method_line_ids_commands = [Command.clear()]

            if self.env.company.chart_template != "ve_seniat":
                continue

            if journal.code in ("RIP", "RIC", "ISLRP", "ISLRC"):
                pay_method = self.env.ref("account.account_payment_method_manual_in")
                pay_method_line_ids_commands += [
                    Command.create(
                        {
                            "name": pay_method.name,
                            "payment_method_id": pay_method.id,
                            "payment_account_id": journal.default_account_id.id,
                        }
                    )
                ]
                journal_ids |= journal
                journal.inbound_payment_method_line_ids = pay_method_line_ids_commands

        return super(AccountJournal, self - journal_ids)._compute_inbound_payment_method_line_ids()

    @api.depends("type", "currency_id")
    def _compute_outbound_payment_method_line_ids(self):
        journal_ids = self.env["account.journal"]
        for journal in self:
            pay_method_line_ids_commands = [Command.clear()]

            if self.env.company.chart_template != "ve_seniat":
                continue

            if journal.code in ("RIP", "RIC", "ISLRP", "ISLRC"):
                pay_method = self.env.ref("account.account_payment_method_manual_out")
                pay_method_line_ids_commands += [
                    Command.create(
                        {
                            "name": pay_method.name,
                            "payment_method_id": pay_method.id,
                            "payment_account_id": journal.default_account_id.id,
                        }
                    )
                ]
                journal_ids |= journal
                journal.outbound_payment_method_line_ids = pay_method_line_ids_commands

        return super(AccountJournal, self - journal_ids)._compute_outbound_payment_method_line_ids()
