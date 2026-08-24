# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nVeInvoiceCancelReason(models.Model):
    _name = "l10n_ve.invoice.cancel.reason"
    _description = "Motivo de anulación de documento fiscal (Venezuela)"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
