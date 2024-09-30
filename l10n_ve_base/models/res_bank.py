###############################################################################
# Author: SINAPSYS GLOBAL SA || MASTERCORE SAS
# Copyleft: 2020-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
#
###############################################################################

from odoo import _, api, exceptions, models


class ResBank(models.Model):
    """inherit for res_bank"""

    _inherit = "res.bank"

    @api.model
    def create(self, vals):
        if not vals["name"]:
            raise exceptions.UserError(
                _("Debe indicar el Nombre de la Entidad Bancaria.")
            )
        # if not vals['bic']:
        #     raise exceptions.UserError(
        #         _(u'Debe indicar el Código de la Entidad Bancaria.')
        #     )
        res = super(ResBank, self).create(vals)
        return res

    def write(self, vals):
        if "name" in vals:
            if not vals.get("name", False):
                raise exceptions.UserError(
                    _("Debe indicar el Nombre de la Entidad Bancaria.")
                )
        # if 'bic' in vals:
        #     if not vals.get('bic', False):
        #         raise exceptions.UserError(
        #             _(u'Debe indicar el Código de la Entidad Bancaria.')
        #         )
        res = super(ResBank, self).write(vals)
        return res
