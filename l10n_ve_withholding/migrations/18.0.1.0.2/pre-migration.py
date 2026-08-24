import logging

from lxml import etree

_logger = logging.getLogger(__name__)


def _get_arch_text(arch_value):
    if isinstance(arch_value, dict):
        arch_text = arch_value.get("en_US")
        if not arch_text:
            arch_text = next(
                (val for val in arch_value.values() if isinstance(val, str) and val),
                None,
            )
        return arch_text
    if isinstance(arch_value, str):
        return arch_value
    return None


def _write_arch(cr, view_id, new_arch):
    cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = CASE
                WHEN jsonb_typeof(arch_db) = 'object'
                    THEN jsonb_set(
                        arch_db,
                        '{en_US}',
                        to_jsonb(%s::text),
                        true
                    )
                ELSE to_jsonb(%s::text)
            END
         WHERE id = %s
        """,
        (new_arch, new_arch, view_id),
    )


def _cleanup_res_config_settings(cr):
    cr.execute(
        """
        SELECT v.id, v.name, d.module, d.name
        FROM ir_ui_view v
        LEFT JOIN ir_model_data d
            ON d.model = 'ir.ui.view'
           AND d.res_id = v.id
        WHERE v.model = 'res.config.settings'
          AND v.active = TRUE
          AND (
                v.arch_db::text ILIKE '%account_tax_periodicity%'
                OR v.arch_db::text ILIKE '%totals_below_sections%'
          )
        """
    )
    for view_id, view_name, module_name, xmlid_name in cr.fetchall():
        xmlid = (
            f"{module_name}.{xmlid_name}" if module_name and xmlid_name else "no_xmlid"
        )
        if xmlid == "no_xmlid":
            cr.execute(
                """
                UPDATE ir_ui_view
                   SET active = FALSE
                 WHERE id = %s
                """,
                (view_id,),
            )
            _logger.warning(
                "Desactivada vista huerfana de res.config.settings "
                "con account_tax_periodicity: id=%s name=%s",
                view_id,
                view_name,
            )
            continue
        cr.execute("SELECT arch_db FROM ir_ui_view WHERE id = %s", (view_id,))
        row = cr.fetchone()
        if not row or not row[0]:
            continue
        arch_text = _get_arch_text(row[0])
        if not arch_text:
            continue
        try:
            arch = etree.fromstring(arch_text.encode("utf-8"))
        except Exception:
            _logger.warning(
                "No se pudo parsear vista %s (%s), se mantiene sin cambios",
                view_name,
                xmlid,
            )
            continue
        changed = False
        for node in arch.xpath(
            ".//field[starts-with(@name, 'account_tax_periodicity') "
            "or @name='totals_below_sections']"
        ):
            setting = node.xpath("ancestor::setting[1]")
            if setting:
                parent = setting[0].getparent()
                if parent is not None:
                    parent.remove(setting[0])
                    changed = True
                continue
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                changed = True
        if changed:
            new_arch = etree.tostring(arch, encoding="unicode")
            _write_arch(cr, view_id, new_arch)
            _logger.warning(
                "Removido account_tax_periodicity de vista "
                "res.config.settings: %s (%s)",
                view_name,
                xmlid,
            )


def _cleanup_res_company(cr):
    cr.execute(
        """
        SELECT v.id, v.name, d.module, d.name
        FROM ir_ui_view v
        LEFT JOIN ir_model_data d
            ON d.model = 'ir.ui.view'
           AND d.res_id = v.id
        WHERE v.model = 'res.company'
          AND v.active = TRUE
          AND (
                v.arch_db::text ILIKE '%account_display_representative_field%'
                OR v.arch_db::text ILIKE '%account_representative_id%'
          )
        """
    )
    for view_id, view_name, module_name, xmlid_name in cr.fetchall():
        xmlid = (
            f"{module_name}.{xmlid_name}" if module_name and xmlid_name else "no_xmlid"
        )
        if xmlid == "no_xmlid":
            cr.execute(
                """
                UPDATE ir_ui_view
                   SET active = FALSE
                 WHERE id = %s
                """,
                (view_id,),
            )
            _logger.warning(
                "Desactivada vista huerfana de res.company "
                "con account_display_representative_field: id=%s name=%s",
                view_id,
                view_name,
            )
            continue
        cr.execute("SELECT arch_db FROM ir_ui_view WHERE id = %s", (view_id,))
        row = cr.fetchone()
        if not row or not row[0]:
            continue
        arch_text = _get_arch_text(row[0])
        if not arch_text:
            continue
        try:
            arch = etree.fromstring(arch_text.encode("utf-8"))
        except Exception:
            _logger.warning(
                "No se pudo parsear vista %s (%s), se mantiene sin cambios",
                view_name,
                xmlid,
            )
            continue
        changed = False
        for node in arch.xpath(
            ".//field[starts-with(@name, 'account_representative') "
            "or starts-with(@name, 'account_display_representative')]"
        ):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                changed = True
        if changed:
            new_arch = etree.tostring(arch, encoding="unicode")
            _write_arch(cr, view_id, new_arch)
            _logger.warning(
                "Removido account_display_representative_field "
                "de vista res.company: %s (%s)",
                view_name,
                xmlid,
            )


def migrate(cr, version):
    _cleanup_res_config_settings(cr)
    _cleanup_res_company(cr)
