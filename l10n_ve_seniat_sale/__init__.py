# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard


def post_init_hook(env):
    env["res.company"]._l10n_ve_seniat_sale_fix_discount_products()
