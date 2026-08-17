# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest import SkipTest

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install", "l10n_ve_reports")
class TestL10nVeBookReportColumns(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reports_module = cls.env["ir.module.module"].search(
            [("name", "=", "l10n_ve_reports"), ("state", "=", "installed")]
        )
        if not reports_module:
            raise SkipTest("l10n_ve_reports is not installed")
        cls.handler = cls.env["account.sales.book.report.handler.oca"]
        cls.tax_group_model = cls.env["account.tax.group"]
        cls.ve_country = cls.env.ref("base.ve")
        cls.exempt_group = cls._configure_tax_group(
            exclude=True,
            sequence=20,
        )
        cls.general_group = cls._configure_tax_group(
            aliquot_type="general",
            sequence=10,
        )
        cls.reduced_group = cls._configure_tax_group(
            aliquot_type="reduced",
            sequence=30,
        )

    @classmethod
    def _configure_tax_group(cls, aliquot_type=None, exclude=False, sequence=10):
        domain = [
            ("company_id", "=", cls.env.company.id),
            ("country_id", "=", cls.ve_country.id),
        ]
        if exclude:
            domain.append(("l10n_ve_exclude_from_reports", "=", True))
        elif aliquot_type:
            domain.append(("l10n_ve_aliquot_type", "=", aliquot_type))
        group = cls.tax_group_model.search(domain, limit=1)
        values = {
            "sequence": sequence,
            "l10n_ve_exclude_from_reports": exclude,
            "l10n_ve_aliquot_type": False if exclude else aliquot_type,
        }
        if group:
            group.write(values)
            return group
        return cls.tax_group_model.create(
            {
                "name": f"Grupo {aliquot_type or 'exento'} reporte",
                "company_id": cls.env.company.id,
                "country_id": cls.ve_country.id,
                **values,
            }
        )

    def test_sales_book_columns_follow_tax_group_sequence(self):
        report = self.env.ref("l10n_ve_reports.sales_book_report")
        options = report.get_options({})
        labels = [
            column.get("expression_label")
            for column in options.get("columns", [])
        ]

        general_index = labels.index("tax_base_general_aliquot")
        exempt_index = labels.index("total_sales_not_iva")
        reduced_index = labels.index("tax_base_reduced_aliquot")
        self.assertLess(general_index, exempt_index)
        self.assertLess(exempt_index, reduced_index)
