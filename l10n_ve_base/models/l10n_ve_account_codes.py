# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

"""7-digit VEN-NIF account codes for official l10n_ve on Odoo 19.

Official ``l10n_ve`` uses ``code_digits = 7``. The community proposal
(odoo/odoo#285425) keeps that width and shares 4-digit functional groups with
the 6-digit master chart. Localization modules must look up accounts by those
codes, never by a custom chart of accounts.

New VEN-NIF codes are tried first; current official codes are the fallback.
"""

ACCOUNT_CODE_DIGITS = 7

# semantic key -> (preferred 7-digit codes..., older official fallbacks...)
ACCOUNT_CODES = {
    "receivable": ("1101001", "1122001"),
    "payable": ("2101001", "2122001"),
    "vat_credit": ("1103001", "1151004"),
    "vat_wh_received": ("1103002", "1151003"),
    "islr_wh_received": ("1103003", "1151002"),
    "vat_debit": ("2103001", "2172003"),
    "vat_payable": ("2103002", "2175018"),
    "vat_wh_payable": ("2103003", "2172004"),
    "igtf_perception": ("2103004",),
    "islr_wh_payable": ("2104001", "2172002"),
    "islr_payable": ("2104002", "2191001"),
    "muni_payable": ("2104003", "2175018"),
    "other_tax_payable": ("2104004", "2175018"),
    "igtf_expense": ("6601001", "9114001"),
    "vat_nondeductible": ("6601003",),
}

# 4-digit groups shared by the 7-digit chart and the 6-digit master proposal
ACCOUNT_PREFIXES = {
    "tax_credits": "1103",
    "vat_igtf_liability": "2103",
    "income_other_tax": "2104",
    "tax_expense": "6601",
}

COMPANY_ACCOUNT_FIELDS = (
    ("wh_iva_account_id", "vat_wh_payable"),
    ("wh_iva_received_account_id", "vat_wh_received"),
    ("wh_islr_account_id", "islr_wh_payable"),
    ("wh_muni_account_id", "muni_payable"),
    ("wh_src_account_id", "other_tax_payable"),
    ("l10n_ve_igtf_expense_account_id", "igtf_expense"),
    ("l10n_ve_igtf_perception_account_id", "igtf_perception"),
)
