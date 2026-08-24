from odoo import api, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.depends("pos_use_pricelist", "pos_config_id", "pos_journal_id")
    def _compute_pos_pricelist_id(self):
        super()._compute_pos_pricelist_id()
        for res_config in self:
            if not res_config.pos_use_pricelist or not res_config.pos_config_id:
                continue
            # Keep multi-currency pricelists configured on the POS. Standard Odoo
            # drops any pricelist whose currency differs from the journal/company.
            res_config.pos_available_pricelist_ids = (
                res_config.pos_config_id.available_pricelist_ids
            )
            res_config.pos_pricelist_id = res_config.pos_config_id.pricelist_id
