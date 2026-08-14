from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_authorities_logo = fields.Image(max_width=128, max_height=128)
    tax_authorities_name = fields.Char()
    economic_activity_number = fields.Char()

    iva_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.V.A Retentions",
    )
    iva_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.V.A Retentions",
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.S.L.R Retentions",
    )
    islr_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.S.L.R Retentions",
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier Municipal Retentions",
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer Municipal Retentions",
    )

    condition_withholding_id = fields.Many2one(
        "account.withholding.type",
        string="The condition of this taxpayer requires the withholding of",
        related="partner_id.withholding_type_id",
        readonly=False,
    )

    type_person_id = fields.Many2one(
        "type.person",
        related="partner_id.type_person_id",
        readonly=False,
    )

    hide_patent_columns_extra = fields.Boolean(
        string="Hide extra columns in Patent Municipal Report related to advances",
        default=False,
    )
