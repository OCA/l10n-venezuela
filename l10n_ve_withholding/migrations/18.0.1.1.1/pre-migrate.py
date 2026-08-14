import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'res_company'
           AND column_name = 'condition_withholding_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE res_partner partner
           SET withholding_type_id = company.condition_withholding_id
          FROM res_company company
         WHERE company.partner_id = partner.id
           AND company.condition_withholding_id IS NOT NULL
        """
    )
    _logger.info(
        "Sincronizado condition_withholding_id de empresa hacia "
        "withholding_type_id del contacto de la compañía."
    )
