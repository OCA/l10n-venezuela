# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models


class AccountRetention(models.Model):
    _inherit = ["account.retention", "l10n.ve.fiscal.event.mixin"]
    _name = "account.retention"

    @api.model_create_multi
    def create(self, vals_list):
        retentions = super().create(vals_list)
        for retention in retentions:
            retention._l10n_ve_audit_log_fiscal_event(
                "retention_draft",
                _("Creación de retención borrador %(document)s")
                % {"document": retention.display_name},
            )
        return retentions

    def action_post(self):
        to_log = self.filtered(lambda record: record.state != "emitted")
        res = super().action_post()
        for retention in to_log.filtered(lambda record: record.state == "emitted"):
            number = retention.number or retention.display_name
            retention._l10n_ve_audit_log_fiscal_event(
                "retention_emitted",
                _("Emisión de retención %(document)s (N° %(number)s)")
                % {"document": retention.display_name, "number": number},
            )
        return res

    def _l10n_ve_edi_on_dispatch_success(self, response):
        res = super()._l10n_ve_edi_on_dispatch_success(response)
        for retention in self:
            number = retention.number or retention.display_name
            retention._l10n_ve_audit_log_fiscal_event(
                "retention_edi",
                _("Envío digital de retención %(document)s (N° %(number)s)")
                % {"document": retention.display_name, "number": number},
            )
        return res
