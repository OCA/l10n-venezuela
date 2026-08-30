# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, models
from odoo.exceptions import UserError


class L10nVeEdocProvider(models.AbstractModel):
    """Contract with the digital printing house. FOUR methods, not one more.

    All the fiscal logic lives outside of this, in
    ``account.move._l10n_ve_edoc_document_vals()``, which produces a neutral
    dict. The adapter only translates that dict into the provider's dialect
    and returns the result in the shape below. Switching providers is
    writing one file, without touching anything fiscal.

    The two providers shipped with this addon differ in exactly what this
    contract abstracts away: The Factory HKA returns the control number
    SYNCHRONOUSLY in the emission response, while an asynchronous provider
    would assign it later and require a follow-up query. That is why
    ``_edoc_send`` may return an empty control number and ``_edoc_fetch``
    exists at all.
    """

    _name = "l10n.ve.edoc.provider"
    _description = "Digital printing house contract (Venezuela)"

    def _edoc_send(self, move, vals):
        """Issue the document. Returns:

        {'external_id': str,            # the provider's own identifier
         'control_number': str | None,  # None if the provider is async
         'control_date': date | None}
        """
        raise UserError(_(
            "The digital printing house provider does not implement "
            "emission."))

    def _edoc_fetch(self, move):
        """Query the control number of a document already sent.

        Only asynchronous providers call this. Same return shape as
        ``_edoc_send``; a control number of None means "not assigned yet".
        """
        raise UserError(_(
            "The digital printing house provider does not implement "
            "querying."))

    def _edoc_cancel(self, move, reason):
        """Cancel the document with the provider. Returns True if cancelled."""
        raise UserError(_(
            "The digital printing house provider does not implement "
            "cancellation."))

    def _edoc_test_connection(self):
        """Authenticate against the provider without issuing anything.
        Returns a human-readable message."""
        raise UserError(_(
            "The digital printing house provider does not implement the "
            "connection test."))
