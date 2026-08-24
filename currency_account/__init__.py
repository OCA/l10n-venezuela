from . import models
from . import wizard


def post_init_hook(env):
    env["res.currency"]._sync_currency_groups_for_existing_fields()
