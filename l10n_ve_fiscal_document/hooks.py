# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).


def post_init_hook(env):
    historical_documents = env["account.move"].search(
        [
            ("state", "in", ("posted", "cancel")),
            ("move_type", "in", ("out_invoice", "out_refund", "out_receipt")),
            ("company_id.account_fiscal_country_id.code", "=", "VE"),
            ("l10n_ve_fiscal_data_locked", "=", False),
        ]
    )
    historical_documents._l10n_ve_lock_fiscal_data()
