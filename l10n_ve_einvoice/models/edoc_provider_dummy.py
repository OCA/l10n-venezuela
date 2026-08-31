# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class L10nVeEdocProviderDummy(models.AbstractModel):
    """Provider used to validate synchronous and asynchronous flows."""

    _name = "l10n.ve.edoc.provider.dummy"
    _inherit = "l10n.ve.edoc.provider"
    _description = "Dummy Venezuelan Electronic Document Provider"

    _dummy_fetch_delay = 0

    def _edoc_send(self, move, vals):
        external_id = f"DUMMY-{move.id}"
        if self._dummy_fetch_delay:
            return {
                "external_id": external_id,
                "control_number": None,
                "control_date": None,
            }
        return {
            "external_id": external_id,
            "control_number": f"00-{move.id:08d}",
            "control_date": fields.Date.context_today(self),
        }

    def _edoc_fetch(self, move):
        return {
            "external_id": move.l10n_ve_edoc_external_id,
            "control_number": f"00-{move.id:08d}",
            "control_date": fields.Date.context_today(self),
        }

    def _edoc_cancel(self, move, reason):
        return True

    def _edoc_test_connection(self):
        return self.env._("Dummy provider: no external service was contacted.")
