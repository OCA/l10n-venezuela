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

    @api.depends(
        "journal_id",
        "journal_id.currency_id",
        "company_id",
        "company_id.currency_id",
    )
    def _compute_payment_currency_id(self):
        for method in self:
            if method.journal_id and method.journal_id.currency_id:
                method.payment_currency_id = method.journal_id.currency_id
            else:
                method.payment_currency_id = method.company_id.currency_id

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = list(super()._load_pos_data_fields(config_id) or [])
        if "payment_currency_id" not in fields_list:
            fields_list.append("payment_currency_id")
        return fields_list
