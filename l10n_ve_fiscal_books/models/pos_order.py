# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_ve_contingency_control = fields.Char(
        string="Contingency Control Number",
        copy=False,
        readonly=True,
        index="btree_not_null",
        help="Control number of the preprinted authorized booklet form used while "
        "the fiscal machine was unavailable.",
    )
    l10n_ve_contingency_invoice_number = fields.Char(
        string="Contingency Invoice Number",
        copy=False,
        readonly=True,
        index="btree_not_null",
        help="Preprinted invoice number of the authorized booklet form. The sales "
        "book uses it as the document number.",
    )

    @api.constrains("l10n_ve_contingency_control", "l10n_ve_contingency_invoice_number")
    def _check_l10n_ve_contingency_unique(self):
        for order in self:
            for field_name, label in (
                ("l10n_ve_contingency_control", self.env._("Control number")),
                (
                    "l10n_ve_contingency_invoice_number",
                    self.env._("Invoice number"),
                ),
            ):
                value = order[field_name]
                if not value:
                    continue
                duplicate = self.search(
                    [
                        ("id", "!=", order.id),
                        ("company_id", "=", order.company_id.id),
                        (field_name, "=", value),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(
                        self.env._(
                            "The booklet %(label)s '%(value)s' is already recorded "
                            "on order %(order)s.",
                            label=label,
                            value=value,
                            order=duplicate.display_name,
                        )
                    )
