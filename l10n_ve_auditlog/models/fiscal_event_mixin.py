# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class L10nVeFiscalEventMixin(models.AbstractModel):
    _name = "l10n.ve.fiscal.event.mixin"
    _description = "Venezuela Fiscal Event Logger Mixin"

    def _l10n_ve_audit_log_fiscal_event(self, event_type, description):
        self.ensure_one()
        return self.env["auditlog.log"].log_fiscal_event(self, event_type, description)
