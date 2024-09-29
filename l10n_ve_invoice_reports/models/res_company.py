###############################################################################
# Author      : SINAPSYS GLOBAL SA || MASTERCORE SAS
# Copyright(c): 2021-Present.
# License URL : AGPL-3
###############################################################################

from odoo import api, models


class ResCompany(models.Model):
    """
    Modificación del registro de la Compañia default para la inclusión de
    la plantilla «boxed».
    """

    _inherit = "res.company"

    @api.model
    def set_report_layout(self):
        self.browse(1).write(
            {"external_report_layout_id": self.env.ref("web.external_layout_bold").id}
        )
