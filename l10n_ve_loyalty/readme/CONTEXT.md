En Venezuela los descuentos y recargos no deben manejarse como productos en
la factura. El módulo estándar `loyalty` crea líneas con
`discount_line_product_id`, incompatible con la práctica fiscal SENIAT.

Este módulo concentra la infraestructura de descuento global (antes en
`l10n_ve_seniat`) y la integra con programas de lealtad, cupones y wallet.
