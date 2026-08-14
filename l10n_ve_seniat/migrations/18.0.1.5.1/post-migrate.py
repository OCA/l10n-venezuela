import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_MEDIUMS = (
    (
        "l10n_ve_seniat.emission_medium_free_form",
        {
            "name": "Forma libre",
            "code": "free_form",
            "sequence": 10,
            "description": (
                "Emisión sobre formas libres elaboradas por imprentas autorizadas."
            ),
            "active": True,
        },
    ),
    (
        "l10n_ve_seniat.emission_medium_fiscal_machine",
        {
            "name": "Máquina Fiscal",
            "code": "fiscal_machine",
            "sequence": 20,
            "description": (
                "Emisión mediante máquinas fiscales autorizadas por el SENIAT."
            ),
            "active": True,
        },
    ),
    (
        "l10n_ve_seniat.emission_medium_digital_billing",
        {
            "name": "Facturación Digital",
            "code": "digital_billing",
            "sequence": 30,
            "description": "Emisión mediante facturación digital.",
            "active": True,
        },
    ),
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Medium = env["l10n.ve.emission.medium"]

    for xmlid, values in _MEDIUMS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if not record:
            record = Medium.search([("code", "=", values["code"])], limit=1)
        if record:
            record.write(values)
        else:
            record = Medium.create(values)
        env["ir.model.data"]._update_xmlids(
            [
                {
                    "xml_id": xmlid,
                    "record": record,
                    "noupdate": True,
                }
            ]
        )

    obsolete = env.ref(
        "l10n_ve_seniat.emission_medium_authorized_format",
        raise_if_not_found=False,
    )
    if obsolete:
        obsolete.write({"active": False})
        _logger.info("Archived obsolete emission medium: authorized_format")
