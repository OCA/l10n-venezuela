from odoo.tests import TransactionCase, tagged

EXPECTED_MODULES = (
    "l10n_ve_seniat",
    "l10n_ve_exchange_rates",
    "l10n_ve_product_currency",
    "l10n_ve_payment_advance",
    "l10n_ve_bank_statement_import",
    "l10n_ve_igtf",
    "l10n_ve_withholding",
    "l10n_ve_loyalty",
    "l10n_ve_seniat_sale",
    "l10n_ve_invoice_escp",
    "l10n_ve_fiscal_serial",
    "l10n_ve_stock",
    "l10n_ve_payment_advance_igtf",
    "l10n_ve_payment_advance_withholding",
    "l10n_ve_sale_loyalty",
    "l10n_ve_vat_seniat",
    "l10n_ve_pos",
    "l10n_ve_edi",
    "l10n_ve_pos_igtf",
    "l10n_ve_fiscal_serial_pos",
    "l10n_ve_edi_tfhka",
    "l10n_ve_edi_queue_job",
    "l10n_ve_loyalty_pos",
    "l10n_ve_reports",
    "l10n_ve_reports_stock",
    "l10n_ve_auditlog",
    "l10n_ve_audit",
    "l10n_ve_test",
)

MOVE_FIELDS = (
    "l10n_ve_control_number",
    "l10n_ve_invoice_number",
    "l10n_ve_igtf_collected_amount_company_currency",
    "generate_iva_retention",
    "apply_islr_retention",
    "l10n_ve_global_discount_ids",
)

REGISTER_FIELDS = (
    "l10n_ve_apply_igtf",
    "l10n_ve_apply_advance",
)

MODELS = (
    "account.book",
    "account.retention",
    "account.withholding.type",
    "l10n.ve.fiscal.machine",
    "l10n.ve.emission.medium",
    "pos.order",
    "stock.picking",
    "sale.order",
    "account.report",
)


@tagged("post_install", "-at_install", "l10n_ve_integration")
class TestL10nVeModulesInstalled(TransactionCase):
    def test_all_localization_modules_are_installed(self):
        installed = self.env["ir.module.module"].search(
            [("name", "in", list(EXPECTED_MODULES)), ("state", "=", "installed")]
        )
        missing = set(EXPECTED_MODULES) - set(installed.mapped("name"))
        self.assertFalse(missing, f"Missing installed modules: {sorted(missing)}")

    def test_account_move_exposes_cross_module_fields(self):
        fields_map = self.env["account.move"]._fields
        missing = [name for name in MOVE_FIELDS if name not in fields_map]
        self.assertFalse(missing, f"account.move missing fields: {missing}")

    def test_payment_register_exposes_igtf_and_advance(self):
        fields_map = self.env["account.payment.register"]._fields
        missing = [name for name in REGISTER_FIELDS if name not in fields_map]
        self.assertFalse(missing, f"account.payment.register missing fields: {missing}")

    def test_cross_module_models_exist(self):
        missing = [name for name in MODELS if name not in self.env]
        self.assertFalse(missing, f"Missing models: {missing}")

    def test_report_actions_are_available(self):
        for xmlid in (
            "l10n_ve_reports.action_account_report_pl",
            "l10n_ve_reports.action_account_report_bs",
        ):
            self.env.ref(xmlid)

    def test_form_views_load_together(self):
        for model_name in (
            "account.move",
            "account.payment",
            "sale.order",
            "stock.picking",
            "res.partner",
            "account.journal",
        ):
            self.env[model_name].get_views([[False, "form"], [False, "list"]])
