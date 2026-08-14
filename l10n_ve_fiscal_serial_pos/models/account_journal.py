from odoo import api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        for field_name in ("l10n_ve_fiscal_machine_id", "l10n_ve_fiscal_payment_code"):
            if field_name not in fields:
                fields.append(field_name)
        return fields
