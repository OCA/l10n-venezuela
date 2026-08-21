# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


class L10nVeLoyaltyCommon(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id = [
            Command.link(cls.env.ref("l10n_ve_loyalty.group_l10n_ve_global_discount").id)
        ]
