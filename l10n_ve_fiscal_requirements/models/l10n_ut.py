# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class L10nUt(models.Model):
    _name = "l10n.ut"
    _description = "Tax Unit (Unidad Tributaria)"
    _order = "date desc"

    name = fields.Char(
        string="Reference number",
        required=True,
        help="Reference number under the law",
    )
    date = fields.Date(
        string="Date",
        required=True,
        help="Date on which goes into effect the new Tax Unit",
    )
    amount = fields.Float(
        string="Amount",
        digits="Account",
        required=True,
        help="Amount of the tax unit in Bs",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Salesman",
        default=lambda self: self.env.user,
        help="User who registered the record",
    )

    @api.model
    def get_amount_ut(self, date=False):
        """Return the value of the tax unit for the specified date or current date."""
        target_date = date or fields.Date.context_today(self)
        ut_record = self.search(
            [("date", "<=", target_date)], order="date desc", limit=1
        )
        return ut_record.amount if ut_record else 0.0

    @api.model
    def compute(self, from_amount, date=False):
        """Return the number of tributary units depending on an amount of money."""
        ut = self.get_amount_ut(date=date)
        return (from_amount / ut) if ut else 0.0

    @api.model
    def compute_ut_to_money(self, amount_ut, date=False):
        """Transforms from tax units into money."""
        ut = self.get_amount_ut(date=date)
        return (amount_ut * ut) if ut else 0.0
