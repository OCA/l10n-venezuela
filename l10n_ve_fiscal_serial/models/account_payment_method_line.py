# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    l10n_ve_fiscal_payment_method_id = fields.Many2one(
        comodel_name="l10n.ve.fiscal.payment.method",
        string="Método de pago fiscal",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help=(
            "Código de forma de pago TFHKA (01-24) usado al imprimir "
            "fiscalmente pagos registrados con esta línea."
        ),
    )
