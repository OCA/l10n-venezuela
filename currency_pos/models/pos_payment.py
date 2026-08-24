from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero


class PosPayment(models.Model):
    _name = "pos.payment"
    _inherit = ["pos.payment", "mail.thread"]
    _description = "Point of Sale Payments"

    payment_currency_id = fields.Many2one(
        "res.currency",
        string="Payment Currency",
        tracking=True,
    )
    payment_currency_amount = fields.Monetary(
        string="Amount in Payment Currency",
        currency_field="payment_currency_id",
        tracking=True,
    )
    payment_currency_rate = fields.Float(
        string="Applied Exchange Rate",
        digits=(16, 6),
        tracking=True,
        help="Conversion rate from payment currency to order currency.",
    )
    is_foreign_currency_payment = fields.Boolean(
        string="Foreign Currency Payment",
        compute="_compute_is_foreign_currency_payment",
        store=True,
        index=True,
    )

    @api.depends("payment_currency_id", "currency_id")
    def _compute_is_foreign_currency_payment(self):
        for payment in self:
            payment.is_foreign_currency_payment = bool(
                payment.payment_currency_id
                and payment.currency_id
                and payment.payment_currency_id != payment.currency_id
            )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = list(super()._load_pos_data_fields(config_id))
        if not fields_list:
            fields_list = [
                "id",
                "uuid",
                "amount",
                "payment_method_id",
                "payment_date",
                "payment_status",
                "ticket",
                "is_change",
                "pos_order_id",
            ]
        for field_name in (
            "payment_currency_id",
            "payment_currency_amount",
            "payment_currency_rate",
            "payment_ref_no",
        ):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    @api.model
    def _oca_get_conversion_rate(self, from_currency, to_currency, company, payment_date):
        if from_currency == to_currency:
            return 1.0
        return self.env["res.currency"]._get_conversion_rate(
            from_currency,
            to_currency,
            company,
            payment_date,
        )

    @api.model
    def _oca_convert_amount(self, amount, from_currency, to_currency, company, payment_date):
        if from_currency == to_currency:
            return from_currency.round(amount)
        return from_currency._convert(
            amount,
            to_currency,
            company,
            payment_date,
        )

    def _oca_fill_multicurrency_values(self):
        for payment in self:
            order_currency = payment.currency_id
            payment_currency = (
                payment.payment_currency_id
                or payment.payment_method_id.payment_currency_id
                or order_currency
            )
            payment_date = (
                payment.payment_date.date()
                if payment.payment_date
                else fields.Date.context_today(payment)
            )
            values = {}

            if not payment.payment_currency_id:
                values["payment_currency_id"] = payment_currency.id

            rate = payment.payment_currency_rate
            if not rate:
                rate = payment._oca_get_conversion_rate(
                    payment_currency,
                    order_currency,
                    payment.company_id,
                    payment_date,
                )
                values["payment_currency_rate"] = rate

            if payment.payment_currency_amount in (False, None) and payment.amount is not False:
                if payment_currency == order_currency:
                    values["payment_currency_amount"] = payment.amount
                else:
                    values["payment_currency_amount"] = payment._oca_convert_amount(
                        payment.amount,
                        order_currency,
                        payment_currency,
                        payment.company_id,
                        payment_date,
                    )
            elif (
                payment.payment_currency_amount not in (False, None)
                and payment_currency != order_currency
                and float_is_zero(payment.amount, precision_rounding=order_currency.rounding)
            ):
                values["amount"] = payment._oca_convert_amount(
                    payment.payment_currency_amount,
                    payment_currency,
                    order_currency,
                    payment.company_id,
                    payment_date,
                )

            if values:
                super(PosPayment, payment).write(values)

    @api.model
    def _oca_prepare_multicurrency_vals(self, vals):
        vals = dict(vals)
        payment_method = self.env["pos.payment.method"].browse(vals.get("payment_method_id"))
        if not payment_method:
            return vals
        order = (
            self.env["pos.order"].browse(vals["pos_order_id"])
            if vals.get("pos_order_id")
            else self.env["pos.order"]
        )
        if not order:
            payment_currency = (
                self.env["res.currency"].browse(vals["payment_currency_id"])
                if vals.get("payment_currency_id")
                else payment_method.payment_currency_id
            )
            if payment_currency:
                vals.setdefault("payment_currency_id", payment_currency.id)
            return vals
        order_currency = order.currency_id
        payment_currency = (
            self.env["res.currency"].browse(vals["payment_currency_id"])
            if vals.get("payment_currency_id")
            else payment_method.payment_currency_id or order_currency
        )
        payment_date = vals.get("payment_date") or fields.Datetime.now()
        if isinstance(payment_date, str):
            payment_date = fields.Datetime.from_string(payment_date)
        payment_date_value = payment_date.date() if payment_date else fields.Date.today()

        vals.setdefault("payment_currency_id", payment_currency.id)
        rate = vals.get("payment_currency_rate") or self._oca_get_conversion_rate(
            payment_currency,
            order_currency,
            order.company_id,
            payment_date_value,
        )
        vals["payment_currency_rate"] = rate

        if payment_currency == order_currency:
            amount = vals.get("amount", vals.get("payment_currency_amount", 0.0))
            vals["amount"] = amount
            vals["payment_currency_amount"] = amount
        elif vals.get("payment_currency_amount") not in (False, None):
            ui_amount = vals.get("amount")
            if ui_amount not in (False, None) and not float_is_zero(
                ui_amount, precision_rounding=order_currency.rounding
            ):
                vals["amount"] = order_currency.round(ui_amount)
            else:
                vals["amount"] = self._oca_convert_amount(
                    vals["payment_currency_amount"],
                    payment_currency,
                    order_currency,
                    order.company_id,
                    payment_date_value,
                )
        elif vals.get("amount") not in (False, None):
            vals["payment_currency_amount"] = self._oca_convert_amount(
                vals["amount"],
                order_currency,
                payment_currency,
                order.company_id,
                payment_date_value,
            )
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._oca_prepare_multicurrency_vals(vals) for vals in vals_list]
        payments = super().create(vals_list)
        payments._oca_fill_multicurrency_values()
        payments._oca_post_multicurrency_message()
        return payments

    def write(self, vals):
        res = super().write(vals)
        if {"amount", "payment_currency_amount", "payment_currency_id", "payment_method_id"} & set(vals):
            self._oca_fill_multicurrency_values()
            self._oca_post_multicurrency_message()
        return res

    def _oca_post_multicurrency_message(self):
        for payment in self:
            if not payment.payment_currency_id or payment.payment_currency_id == payment.currency_id:
                continue
            payment.message_post(
                body=_(
                    "Multi-currency payment: %(payment_amount)s %(payment_currency)s "
                    "@ %(rate)s = %(order_amount)s %(order_currency)s",
                    payment_amount=payment.payment_currency_amount,
                    payment_currency=payment.payment_currency_id.name,
                    rate=payment.payment_currency_rate,
                    order_amount=payment.amount,
                    order_currency=payment.currency_id.name,
                ),
                message_type="notification",
            )

    @api.constrains(
        "amount",
        "payment_currency_amount",
        "payment_currency_id",
        "currency_id",
        "payment_method_id",
        "pos_order_id",
    )
    def _check_multicurrency_payment(self):
        for payment in self:
            config = payment.pos_order_id.config_id
            order_currency = payment.currency_id
            payment_currency = (
                payment.payment_currency_id
                or payment.payment_method_id.payment_currency_id
                or order_currency
            )
            if payment_currency != order_currency:
                if not config.allow_multi_currency_payment:
                    raise ValidationError(
                        _(
                            "Payment method %(method)s uses %(currency)s but multi-currency "
                            "payments are disabled on POS %(config)s.",
                            method=payment.payment_method_id.name,
                            currency=payment_currency.name,
                            config=config.name,
                        )
                    )
                if float_is_zero(
                    payment.payment_currency_amount,
                    precision_rounding=payment_currency.rounding,
                ):
                    raise ValidationError(
                        _(
                            "The amount in payment currency must be non-zero "
                            "for foreign currency payments."
                        )
                    )
                if float_compare(
                    payment.payment_currency_rate,
                    0.0,
                    precision_digits=6,
                ) <= 0:
                    raise ValidationError(_("The exchange rate must be positive."))
            elif payment.payment_currency_amount not in (False, None):
                if float_compare(
                    payment.payment_currency_amount,
                    payment.amount,
                    precision_rounding=order_currency.rounding,
                ) != 0:
                    raise ValidationError(
                        _(
                            "When payment currency matches order currency, both amounts must be equal."
                        )
                    )

    def _create_payment_moves(self, is_reverse=False):
        payments = self
        for payment in self:
            payment._oca_fill_multicurrency_values()
        return super(PosPayment, payments)._create_payment_moves(is_reverse=is_reverse)
