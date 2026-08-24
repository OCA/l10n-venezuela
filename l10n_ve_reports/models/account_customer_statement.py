from odoo import _, models


class CustomerStatementCustomHandler(models.AbstractModel):
    _name = "account.customer.statement.report.handler.oca"
    _inherit = "account.partner.ledger.report.handler.oca"
    _description = "Customer Statement Custom Handler"

    def _get_custom_display_config(self):
        display_config = super()._get_custom_display_config()
        display_config["css_custom_class"] += " customer_statement"
        return display_config

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(report, options, previous_options)

        options["buttons"].append(
            {
                "name": _("Send"),
                "action": "action_send_statements",
                "sequence": 90,
                "always_show": True,
            }
        )
        return result
