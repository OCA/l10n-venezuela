from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iva_supplier_retention_journal_id = fields.Many2one(
        related="company_id.iva_supplier_retention_journal_id", readonly=False
    )
    iva_customer_retention_journal_id = fields.Many2one(
        related="company_id.iva_customer_retention_journal_id", readonly=False
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        related="company_id.islr_supplier_retention_journal_id", readonly=False
    )
    islr_customer_retention_journal_id = fields.Many2one(
        related="company_id.islr_customer_retention_journal_id", readonly=False
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        related="company_id.municipal_supplier_retention_journal_id", readonly=False
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        related="company_id.municipal_customer_retention_journal_id", readonly=False
    )

    condition_withholding_id = fields.Many2one(
        related="company_id.condition_withholding_id", readonly=False
    )
    type_person_id = fields.Many2one(
        "type.person",
        related="company_id.type_person_id",
        readonly=False,
    )
    hide_patent_columns_extra = fields.Boolean(
        related="company_id.hide_patent_columns_extra", readonly=False
    )

    def action_open_tax_units(self):
        return self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_ve_withholding.action_tax_unit_l10n_ve_withholding"
        )

    def action_open_payment_concepts(self):
        return self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_ve_withholding.action_payment_concept_line_l10n_ve_withholding"
        )
