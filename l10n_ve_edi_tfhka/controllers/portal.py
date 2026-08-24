import base64

from werkzeug.exceptions import NotFound
from werkzeug.utils import redirect

from odoo import exceptions
from odoo.http import request, route

from odoo.addons.l10n_ve_stock.controllers.portal import L10nVeStockPortal


class L10nVeEdiTfhkaPortal(L10nVeStockPortal):
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

        if picking_sudo._l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf():
            doc_url = picking_sudo.l10n_ve_edi_tfhka_get_public_document_url()
            if doc_url and kw.get("tfhka") != "pdf":
                return redirect(doc_url, code=302)
            pdf_bytes, _err = (
                picking_sudo._tfhka_get_dispatch_pdf_bytes_via_descarga_archivo()
            )
            if not pdf_bytes:
                attachment = picking_sudo.l10n_ve_edi_tfhka_pdf_attachment_id
                if attachment and attachment.datas:
                    pdf_bytes = base64.b64decode(attachment.datas)
            if pdf_bytes:
                headers = [
                    ("Content-Type", "application/pdf"),
                    ("Content-Length", len(pdf_bytes)),
                    (
                        "Content-Disposition",
                        'inline; filename="{}.pdf"'.format(
                            (picking_sudo.name or "guia").replace("/", "_")
                        ),
                    ),
                ]
                return request.make_response(pdf_bytes, headers=headers)
            if doc_url:
                return redirect(doc_url, code=302)

        return super().portal_my_picking_report(
            picking_id, access_token=access_token, **kw
        )
