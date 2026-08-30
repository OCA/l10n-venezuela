# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, fields, models


class L10nVeEdocProviderDummy(models.AbstractModel):
    """Test provider: talks to no one.

    Exists so the whole connector -- states, retries, log, synchronous and
    asynchronous flow -- can be written and tested before a contract with a
    real digital printing house exists. It must never be selected in
    production; the configuration screen labels it "simulation only".
    """

    _name = "l10n.ve.edoc.provider.dummy"
    _inherit = "l10n.ve.edoc.provider"
    _description = "Simulated digital printing house (test only)"

    # Number of calls to _edoc_fetch before "assigning" the control number,
    # to simulate an asynchronous provider's delay.
    _dummy_fetch_delay = 0

    def _edoc_send(self, move, vals):
        external_id = "DUMMY-%s" % move.id
        if self._dummy_fetch_delay:
            return {"external_id": external_id,
                    "control_number": None,
                    "control_date": None}
        return {
            "external_id": external_id,
            "control_number": "00-%08d" % move.id,
            "control_date": fields.Date.context_today(self),
        }

    def _edoc_fetch(self, move):
        return {
            "external_id": move.l10n_ve_edoc_external_id,
            "control_number": "00-%08d" % move.id,
            "control_date": fields.Date.context_today(self),
        }

    def _edoc_cancel(self, move, reason):
        return True

    def _edoc_test_connection(self):
        return _("Simulated provider: no real printing house was contacted.")
