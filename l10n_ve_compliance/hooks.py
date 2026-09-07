# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Audit rules over the fiscal models, created AND confirmed.

Creating a rule does not audit anything: OCA auditlog only hooks the models
whose rules are in state 'confirmed' (auditlog_rule.py:241 and :269). That
step is always forgotten, so it lives here and not in the documentation.

The models are resolved by NAME and not by XML-ID on purpose: the ir.model
records of inherited models live in the module that defines them (account,
base...) and guessing those identifiers is a source of installation failures.

To re-run it from odoo-bin shell:

    from odoo.addons.l10n_ve_compliance.hooks import ensure_audit_rules
    ensure_audit_rules(env)
"""

import logging

_logger = logging.getLogger(__name__)

# Models with fiscal audit relevance. account.move.line is left out on
# purpose: it is the highest-volume model by far (every POS session closing
# generates hundreds of lines) and its amounts are already protected by the
# journal hash chain, which detects any later alteration. If it is ever
# needed, add it here and re-run.
AUDITED_MODELS = (
    "account.move",
    "account.journal",
    "account.tax",
    "res.company",
    "res.partner",
    "l10n.ve.islr.voucher",
    "l10n.ve.iva.wh.voucher",
)


def ensure_audit_rules(env):
    Rule = env["auditlog.rule"]
    IrModel = env["ir.model"]
    for model_name in AUDITED_MODELS:
        model = IrModel.sudo().search([("model", "=", model_name)], limit=1)
        if not model:
            _logger.warning(
                "l10n_ve_compliance: model %s does not exist; no audit rule.",
                model_name,
            )
            continue
        rule = Rule.search([("model_id", "=", model.id)], limit=1)
        if not rule:
            rule = Rule.create(
                {
                    "name": f"VE Compliance - {model_name}",
                    "model_id": model.id,
                    "log_create": True,
                    "log_write": True,
                    "log_unlink": True,
                    # OCA auditlog itself declares that READ logging does not
                    # work on every model and "needs research": enabling it
                    # would give a false sense of coverage.
                    "log_read": False,
                    # 'full' keeps the PREVIOUS value of every field, which
                    # is exactly what an auditor wants to see. Upstream
                    # incompatibility that motivated the CI exclusion:
                    # https://github.com/OCA/server-tools/issues/3720
                    "log_type": "full",
                }
            )
        if rule.state != "confirmed":
            rule.set_to_confirmed()
    _logger.info(
        "l10n_ve_compliance: %s audit rules active.",
        Rule.search_count([("state", "=", "confirmed")]),
    )


def post_init_hook(env):
    ensure_audit_rules(env)
