# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class StockPicking(models.Model):
    _inherit = ["stock.picking", "l10n.ve.fiscal.event.mixin"]
    _name = "stock.picking"

    def _l10n_ve_edi_on_dispatch_success(self, response):
        res = super()._l10n_ve_edi_on_dispatch_success(response)
        for picking in self.filtered(
            lambda record: record.company_id.account_fiscal_country_id.code == "VE"
        ):
            control = picking.l10n_ve_control_number or ""
            description = _("Envío digital de guía de despacho %(document)s") % {
                "document": picking.display_name
            }
            if control:
                description = _(
                    "Envío digital de guía de despacho %(document)s "
                    "(N° control: %(control)s)"
                ) % {"document": picking.display_name, "control": control}
            picking._l10n_ve_audit_log_fiscal_event("dispatch_guide", description)
        return res
