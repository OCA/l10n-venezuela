# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class L10nVeSeniatCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.partner_id.write(
            {"vat": "J770023598", "country_id": cls.env.ref("base.ve").id}
        )
        cls.change_company_country(cls.env.company, cls.env.ref("base.ve"))
        sale_tax = cls.company_data["default_tax_sale"]
        if sale_tax:
            sale_tax.sudo().write({"price_include": False})
            sale_tax.flatten_taxes_hierarchy().sudo().write({"price_include": False})
        cls._setup_l10n_ve_sale_journal_sections()
        cls._l10n_ve_set_company_emission_medium_codes("free_form")

    @classmethod
    def _l10n_ve_set_company_emission_medium_codes(cls, *codes):
        mediums = cls.env["l10n.ve.emission.medium"].search(
            [("code", "in", list(codes))]
        )
        cls.env.company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, mediums.ids)]}
        )

    @classmethod
    def _setup_l10n_ve_sale_journal_sections(cls):
        company = cls.env.company
        journal = cls.company_data["default_journal_sale"]
        book = cls.env["account.book"].create(
            {
                "name": "Talonario tests",
                "company_id": company.id,
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        sec = cls.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "Ventas",
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        journal.write(
            {
                "l10n_ve_invoice_section_id": sec.id,
                "l10n_ve_credit_note_section_id": sec.id,
            }
        )

    @classmethod
    def _l10n_ve_configure_journal_fiscal_machine(cls, journal, **extra):
        cls._l10n_ve_set_company_emission_medium_codes("fiscal_machine")
        vals = {"l10n_ve_emission_medium": "fiscal_machine"}
        if "l10n_ve_fiscal_machine_id" in journal._fields:
            machine_model = cls.env["l10n.ve.fiscal.machine"].sudo()
            machine = machine_model.search(
                [("company_id", "=", journal.company_id.id)], limit=1
            )
            if not machine:
                machine = machine_model.create(
                    {
                        "name": "Test Fiscal Machine",
                        "company_id": journal.company_id.id,
                        "registered_serial": "TESTSENIAT1",
                        "fiscal_rif": "J123456789",
                    }
                )
            vals["l10n_ve_fiscal_machine_id"] = machine.id
        vals.update(extra)
        journal.write(vals)

    @classmethod
    def _l10n_ve_configure_journal_digital(cls, journal, **extra):
        cls._l10n_ve_set_company_emission_medium_codes("digital_billing")
        vals = {
            "l10n_ve_emission_medium": "digital",
            "l10n_ve_invoice_section_id": False,
            "l10n_ve_credit_note_section_id": False,
            "l10n_ve_debit_note_section_id": False,
        }
        vals.update(extra)
        journal.write(vals)
