# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import logging

_logger = logging.getLogger(__name__)

CONTINGENCY_CODE = "CONT"


def create_contingency_journals(env):
    """Create one unhashed contingency sales journal per Venezuelan company."""
    journal_model = env["account.journal"]
    companies = env["res.company"].search(
        [("account_fiscal_country_id.code", "=", "VE")]
    )
    if not companies:
        _logger.info(
            "l10n_ve_fiscal_books: no company has Venezuela as fiscal country; "
            "no contingency journal was created."
        )
        return
    for company in companies:
        existing = journal_model.search(
            [
                ("company_id", "=", company.id),
                ("l10n_ve_emission_medium", "=", "contingency"),
            ],
            limit=1,
        )
        if existing:
            continue
        model = journal_model.search(
            [("company_id", "=", company.id), ("type", "=", "sale")],
            order="id",
            limit=1,
        )
        if not model:
            _logger.warning(
                "l10n_ve_fiscal_books: company %s has no sales journal whose "
                "account can be copied; create the contingency journal manually.",
                company.display_name,
            )
            continue
        code = CONTINGENCY_CODE
        if journal_model.search_count(
            [("company_id", "=", company.id), ("code", "=", code)]
        ):
            code = "CONTG"
        journal = journal_model.create(
            {
                "name": "Ventas en Contingencia",
                "code": code,
                "type": "sale",
                "company_id": company.id,
                "default_account_id": model.default_account_id.id,
                "currency_id": model.currency_id.id,
                "l10n_ve_emission_medium": "contingency",
            }
        )
        _logger.info(
            "l10n_ve_fiscal_books: contingency journal %s created for %s",
            journal.code,
            company.display_name,
        )


def post_init_hook(env):
    create_contingency_journals(env)
