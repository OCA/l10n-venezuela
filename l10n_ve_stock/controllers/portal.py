from werkzeug.exceptions import NotFound

from odoo import exceptions
from odoo.http import request, route

from odoo.addons.sale_stock.controllers.portal import SaleStockPortal


class L10nVeStockPortal(SaleStockPortal):
    @route(
        ["/my/picking/pdf/<int:picking_id>"], type="http", auth="public", website=True
    )
    def portal_my_picking_report(self, picking_id, access_token=None, **kw):
        try:
            picking_sudo = self._stock_picking_check_access(
                picking_id, access_token=access_token
            )
        except (exceptions.AccessError, exceptions.MissingError):
            return NotFound()

        if not picking_sudo._l10n_ve_is_ve_outgoing_dispatch_guide_picking():
            return super().portal_my_picking_report(
                picking_id, access_token=access_token, **kw
            )

        report_xmlid = picking_sudo._l10n_ve_get_portal_pdf_report_xmlid()
        pdf = (
            request.env["ir.actions.report"]
            .sudo()
            ._render_qweb_pdf(report_xmlid, [picking_sudo.id])[0]
        )
        pdfhttpheaders = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf)),
        ]
        return request.make_response(pdf, headers=pdfhttpheaders)
