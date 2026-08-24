import logging

from lxml import etree

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT v.id, v.name, d.module, d.name
        FROM ir_ui_view v
        LEFT JOIN ir_model_data d
            ON d.model = 'ir.ui.view'
           AND d.res_id = v.id
        WHERE v.model = 'account.move'
          AND v.active = TRUE
          AND v.arch_db::text ILIKE '%audit_log_ids%'
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
                "Desactivada vista huerfana de account.move con "
                "audit_log_ids: id=%s name=%s",
                view_id,
                view_name,
            )
            continue
        cr.execute("SELECT arch_db FROM ir_ui_view WHERE id = %s", (view_id,))
        row = cr.fetchone()
        if not row or not row[0]:
            continue
        arch_value = row[0]
        if isinstance(arch_value, dict):
            arch_text = arch_value.get("en_US")
            if not arch_text:
                arch_text = next(
                    (
                        val
                        for val in arch_value.values()
                        if isinstance(val, str) and val
                    ),
                    None,
                )
        elif isinstance(arch_value, str):
            arch_text = arch_value
        else:
            arch_text = None
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
        for node in arch.xpath(".//field[@name='audit_log_ids']"):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                changed = True
        if changed:
            new_arch = etree.tostring(arch, encoding="unicode")
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
            _logger.warning(
                "Removido audit_log_ids de vista account.move: %s (%s)",
                view_name,
                xmlid,
            )
