# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2.errors import UniqueViolation

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountTaxGroupL10nVe(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tax_group_model = cls.env["account.tax.group"]
        cls.ve_country = cls.env.ref("base.ve")
        cls.exempt_group = cls._configure_tax_group(
            "IVA Exento Test",
            exclude=True,
            sequence=10,
        )
        cls.general_group = cls._configure_tax_group(
            "IVA General Test",
            aliquot_type="general",
            sequence=20,
        )
        cls.reduced_group = cls._configure_tax_group(
            "IVA Reducido Test",
            aliquot_type="reduced",
            sequence=30,
        )
        cls.extend_group = cls._configure_tax_group(
            "IVA Extendido Test",
            aliquot_type="extend",
            sequence=40,
        )

    @classmethod
    def _configure_tax_group(cls, name, aliquot_type=None, exclude=False, sequence=10):
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
            "name": name,
            "sequence": sequence,
            "l10n_ve_exclude_from_reports": exclude,
            "l10n_ve_aliquot_type": False if exclude else aliquot_type,
        }
        if group:
            group.write(values)
            return group
        return cls.tax_group_model.create(
            {
                "company_id": cls.env.company.id,
                "country_id": cls.ve_country.id,
                **values,
            }
        )

    def _create_ve_tax_group(self, name, **values):
        return self.tax_group_model.create(
            {
                "name": name,
                "company_id": self.env.company.id,
                "country_id": self.ve_country.id,
                **values,
            }
        )

    def test_aliquot_type_and_exclude_are_mutually_exclusive(self):
        group = self._create_ve_tax_group(
            "Grupo temporal",
            l10n_ve_exclude_from_reports=True,
        )
        with self.assertRaises(ValidationError):
            group.write({"l10n_ve_aliquot_type": "general"})

    def test_aliquot_type_unique_per_company(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            with self.cr.savepoint():
                self._create_ve_tax_group(
                    "General duplicado",
                    l10n_ve_aliquot_type="general",
                    sequence=25,
                )

    def test_report_tax_groups_ordered_by_sequence(self):
        self.general_group.sequence = 5
        self.exempt_group.sequence = 50
        ordered_groups = self.tax_group_model._l10n_ve_get_report_tax_groups(
            self.env.company
        )
        ordered_ids = ordered_groups.ids
        self.assertLess(
            ordered_ids.index(self.general_group.id),
            ordered_ids.index(self.exempt_group.id),
        )

    def test_build_tax_config_from_tax_groups(self):
        tax_config = self.tax_group_model._l10n_ve_build_tax_config(self.env.company)
        self.assertEqual(tax_config.get("general"), self.general_group.id)
        self.assertEqual(tax_config.get("exempt"), self.exempt_group.id)
