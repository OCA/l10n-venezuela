# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_DISCOUNT_XMLID_NAMES = (
    "l10n_ve_discount_reason_default",
    "l10n_ve_discount_reason_early_payment",
    "l10n_ve_discount_reason_foreign_currency",
    "l10n_ve_discount_reason_commercial",
    "l10n_ve_discount_reason_commercial_adjustment",
    "l10n_ve_discount_reason_view_list",
    "l10n_ve_discount_reason_view_form",
    "l10n_ve_discount_reason_action",
    "menu_l10n_ve_discount_reason",
    "l10n_ve_account_move_discount_wizard_view_form",
    "l10n_ve_account_move_post_discount_wizard_view_form",
    "access_l10n_ve_discount_reason_readonly",
    "access_l10n_ve_discount_reason_invoice",
    "access_l10n_ve_discount_reason_manager",
    "access_l10n_ve_account_move_discount",
    "access_l10n_ve_account_move_discount_wizard",
    "access_l10n_ve_account_move_post_discount_wizard",
    "model_l10n_ve_discount_reason",
    "model_l10n_ve_account_move_discount",
    "model_l10n_ve_account_move_discount_wizard",
    "model_l10n_ve_account_move_post_discount_wizard",
    "model_l10n_ve_global_discount_mixin",
)


def _mark_module_to_install(cr, module_name):
    cr.execute(
        """
        SELECT state
          FROM ir_module_module
         WHERE name = %s
        """,
        (module_name,),
    )
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "Module %s not found in ir_module_module; run update apps list.",
            module_name,
        )
        return
    if row[0] == "installed":
        return
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'to install'
         WHERE name = %s
           AND state NOT IN ('installed', 'uninstallable')
        """,
        (module_name,),
    )
    _logger.info(
        "Marked module %s as 'to install' (previous state=%s)", module_name, row[0]
    )


def _module_is_installed(cr, module_name):
    cr.execute(
        """
        SELECT 1
          FROM ir_module_module
         WHERE name = %s
           AND state IN ('installed', 'to upgrade', 'to install')
        """,
        (module_name,),
    )
    return bool(cr.fetchone())


def _reassign_discount_xmlids(cr):
    # Drop seniat xmlids that already exist under l10n_ve_loyalty
    cr.execute(
        """
        DELETE FROM ir_model_data AS seniat
         WHERE seniat.module = 'l10n_ve_seniat'
           AND seniat.name = ANY(%s)
           AND EXISTS (
                SELECT 1
                  FROM ir_model_data AS loyalty
                 WHERE loyalty.module = 'l10n_ve_loyalty'
                   AND loyalty.name = seniat.name
           )
        """,
        (list(_DISCOUNT_XMLID_NAMES),),
    )
    if cr.rowcount:
        _logger.info(
            "Deleted %s duplicate seniat discount xmlids already owned by loyalty",
            cr.rowcount,
        )

    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'l10n_ve_loyalty'
         WHERE module = 'l10n_ve_seniat'
           AND name = ANY(%s)
        """,
        (list(_DISCOUNT_XMLID_NAMES),),
    )
    _logger.info(
        "Reassigned %s discount xmlids from l10n_ve_seniat to l10n_ve_loyalty",
        cr.rowcount,
    )

    cr.execute(
        """
        DELETE FROM ir_model_data AS seniat
         WHERE seniat.module = 'l10n_ve_seniat'
           AND (
                seniat.name LIKE '%%discount_reason%%'
                OR seniat.name LIKE '%%account_move_discount%%'
                OR seniat.name LIKE '%%post_discount%%'
                OR seniat.name LIKE '%%global_discount%%'
           )
           AND EXISTS (
                SELECT 1
                  FROM ir_model_data AS loyalty
                 WHERE loyalty.module = 'l10n_ve_loyalty'
                   AND loyalty.name = seniat.name
           )
        """
    )
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'l10n_ve_loyalty'
         WHERE module = 'l10n_ve_seniat'
           AND (
                name LIKE '%%discount_reason%%'
                OR name LIKE '%%account_move_discount%%'
                OR name LIKE '%%post_discount%%'
                OR name LIKE '%%global_discount%%'
           )
        """
    )
    if cr.rowcount:
        _logger.info(
            "Reassigned %s extra discount-related xmlids to l10n_ve_loyalty",
            cr.rowcount,
        )


def migrate(cr, version):
    if not version:
        return
    _mark_module_to_install(cr, "l10n_ve_loyalty")
    _mark_module_to_install(cr, "loyalty")
    # Only pull the POS bridge when pos_loyalty is already present. Do not force
    # install pos_loyalty here: its auto-install can fail on DBs without website.
    if _module_is_installed(cr, "pos_loyalty") and _module_is_installed(
        cr, "l10n_ve_pos"
    ):
        _mark_module_to_install(cr, "l10n_ve_loyalty_pos")
    _reassign_discount_xmlids(cr)
