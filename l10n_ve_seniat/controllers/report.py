# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

import werkzeug.exceptions

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.tools.misc import html_escape

from odoo.addons.web.controllers.report import ReportController as WebReportController

_logger = logging.getLogger(__name__)


class L10nVeReportController(WebReportController):
    def _l10n_ve_report_http_error_response(self, exception, reportname):
        _logger.warning("Error while generating report %s", reportname, exc_info=True)
        error = {
            "code": 200,
            "message": "Odoo Server Error",
            "data": http.serialize_exception(exception),
        }
        return request.make_response(html_escape(json.dumps(error)))

    @http.route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        try:
            return super().report_routes(
                reportname, docids=docids, converter=converter, **data
            )
        except (UserError, AccessError) as exc:
            raise werkzeug.exceptions.InternalServerError(
                response=self._l10n_ve_report_http_error_response(exc, reportname)
            ) from exc

    @http.route()
    def report_download(self, data, context=None, token=None, readonly=True):
        requestcontent = json.loads(data)
        url = requestcontent[0]
        type_ = requestcontent[1]
        pattern = "/report/pdf/" if type_ == "qweb-pdf" else "/report/text/"
        reportname = url.split(pattern)[1].split("?")[0] if pattern in url else "???"
        if "/" in reportname:
            reportname = reportname.split("/")[0]
        try:
            return super().report_download(
                data, context=context, token=token, readonly=readonly
            )
        except (UserError, AccessError) as exc:
            raise werkzeug.exceptions.InternalServerError(
                response=self._l10n_ve_report_http_error_response(exc, reportname)
            ) from exc
