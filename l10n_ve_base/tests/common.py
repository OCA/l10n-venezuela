# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


class L10nVeSetupMixin:
    """VE company, RIF, UT and withholding journals/accounts. Not a TestCase."""

    @classmethod
    def _l10n_ve_setup(cls):
        cls.ve_country = cls.env.ref("base.ve")
        cls.company = cls.company_data["company"]
        partner_vals = {
            "name": "Empresa Prueba CA",
            "vat": "J000000000",
            "person_type": "pjdo",
        }
        rif = cls.env.ref(
            "l10n_ve_base.it_rif", raise_if_not_found=False
        ) or cls.env.ref("l10n_latam_base.it_vat", raise_if_not_found=False)
        if rif:
            partner_vals["l10n_latam_identification_type_id"] = rif.id
        cls.company.partner_id.write(partner_vals)
        cls.company.write(
            {
                "country_id": cls.ve_country.id,
                "account_fiscal_country_id": cls.ve_country.id,
            }
        )
        if not cls.env["l10n.ut"].search([("date", "<=", "2025-09-01")], limit=1):
            cls.env["l10n.ut"].create(
                {
                    "name": "UT test",
                    "date": "2025-06-02",
                    "amount": 43.0,
                }
            )
        cls._l10n_ve_ensure_ves_rate()
        expense = cls.company_data["default_account_expense"]
        journal = cls.company_data["default_journal_misc"]
        vals = {}
        for fname in (
            "wh_iva_account_id",
            "wh_iva_received_account_id",
            "wh_islr_account_id",
            "wh_muni_account_id",
            "wh_src_account_id",
            "l10n_ve_igtf_expense_account_id",
            "l10n_ve_igtf_perception_account_id",
        ):
            if fname in cls.company._fields:
                vals[fname] = expense.id
        for fname in (
            "wh_iva_journal_id",
            "wh_islr_journal_id",
            "wh_muni_journal_id",
            "wh_src_journal_id",
        ):
            if fname in cls.company._fields:
                vals[fname] = journal.id
        if vals:
            cls.company.write(vals)

    @classmethod
    def _l10n_ve_ensure_ves_rate(cls):
        ves = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not ves or ves == cls.company.currency_id:
            return
        ves.active = True
        existing = cls.env["res.currency.rate"].search(
            [
                ("currency_id", "=", ves.id),
                "|",
                ("company_id", "=", cls.company.id),
                ("company_id", "=", False),
            ],
            limit=1,
        )
        if existing:
            return
        cls.env["res.currency.rate"].create(
            {
                "name": "2025-01-01",
                "currency_id": ves.id,
                "company_id": cls.company.id,
                "rate": 36.0,
            }
        )

    @classmethod
    def _person_type_from_vat(cls, vat):
        letter = "".join(ch for ch in (vat or "") if ch.isalnum()).upper()
        if letter.startswith("VE") and len(letter) > 2 and letter[2] in "VEJPGC":
            letter = letter[2:]
        return {
            "V": "pnre",
            "E": "pnnr",
            "J": "pjdo",
            "C": "pjdo",
            "G": "pjdo",
            "P": "pjnd",
        }.get(letter[:1], "pjdo")

    @classmethod
    def _create_ve_partner(cls, name, vat, person_type=None, **extra):
        values = {
            "name": name,
            "country_id": cls.ve_country.id,
            "vat": vat,
            "person_type": person_type or cls._person_type_from_vat(vat),
            "company_id": cls.company.id,
        }
        rif = cls.env.ref(
            "l10n_ve_base.it_rif", raise_if_not_found=False
        ) or cls.env.ref("l10n_latam_base.it_vat", raise_if_not_found=False)
        if rif and "l10n_latam_identification_type_id" not in extra:
            values["l10n_latam_identification_type_id"] = rif.id
        values.update(extra)
        return cls.env["res.partner"].create(values)

    def _create_vendor_bill(
        self,
        partner,
        amount=10000.0,
        taxes=None,
        nro_ctrl="00-12345678",
        ref="FAC-001",
    ):
        line = {
            "name": "Servicio de prueba",
            "quantity": 1,
            "price_unit": amount,
            "account_id": self.company_data["default_account_expense"].id,
            "tax_ids": [(6, 0, taxes.ids)] if taxes else [(6, 0, [])],
        }
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": "2025-09-01",
                "invoice_date_due": "2025-09-15",
                "date": "2025-09-01",
                "nro_ctrl": nro_ctrl,
                "supplier_invoice_number": ref,
                "invoice_line_ids": [(0, 0, line)],
            }
        )
        move.action_post()
        return move
