Configuración contable SENIAT para Venezuela.

Incluye facturación fiscal, numeración, validaciones de RIF y el flujo de
notas de crédito y notas de débito tanto para facturas de cliente como de
proveedor (`out_invoice` / `in_invoice`).

Los descuentos globales y post-factura están en el módulo opcional `l10n_ve_loyalty`.

Permite configurar por compañía los medios de emisión de facturas y otros
documentos (forma libre, máquina fiscal y facturación digital).

Los reportes nativos de facturas omiten el encabezado del diseño seleccionado.
El título muestra únicamente el nombre del documento y los totales omiten el
IGTF cuando el diario no tiene medio de emisión.
Los grupos de impuestos con una tasa de 0% no aparecen en los totales.

La fecha de recepción de la factura es el inicio de los plazos de pago y de
las cuotas de vencimiento.
