# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models
from odoo.exceptions import UserError


class L10nVeEdocProvider(models.AbstractModel):
    """Contract implemented by electronic-document provider addons."""

    _name = "l10n.ve.edoc.provider"
    _description = "Venezuelan Electronic Document Provider"

    def _edoc_send(self, move, vals):
        """Send a neutral document and return the provider-neutral result."""
        raise UserError(self.env._("The provider does not implement document sending."))

    def _edoc_fetch(self, move):
        """Fetch the control data of an asynchronously processed document."""
        raise UserError(
            self.env._("The provider does not implement document fetching.")
        )

    def _edoc_cancel(self, move, reason):
        """Cancel a provider document and return whether it was cancelled."""
        raise UserError(
            self.env._("The provider does not implement document cancellation.")
        )

    def _edoc_test_connection(self):
        """Test provider authentication without sending a document."""
        raise UserError(self.env._("The provider does not implement connection tests."))
