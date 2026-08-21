# Usage

Medios de emisión
-----------------

En **SENIAT → Empresas** el kanban muestra los medios de emisión asignados
a cada compañía. La selección se realiza en los ajustes de Contabilidad
(véase la sección de configuración).

Notas de crédito y débito
-------------------------

1. Abra una factura de cliente o de proveedor publicada.
2. Use **Nota de crédito** (reversión) o **Nota de Debito** según corresponda.
3. En **ventas**, aplican las reglas SENIAT de emisión, montos y productos.
4. En **proveedor**, el registro es más libre: puede cambiar moneda, impuestos y
   montos distintos a la factura origen (sin tope SENIAT de NC ni forzar bolívares).
5. Si tras una nota de crédito total de cliente queda una ND sin revertir,
   use el asistente **Nota de crédito por ND**.

Las notas reutilizan el mismo diario y contacto de la factura origen.

Fecha de recepción y vencimientos
---------------------------------

1. En **Contabilidad → Configuración → Ajustes**, bloque **Venezuela**, active
   **Usar fecha de recepción en facturas de cliente** y/o **Usar fecha de
   recepción en facturas de proveedor**.
2. Tras confirmar la factura, indique la **Fecha de recepción**. Esa fecha es
   el inicio de los plazos de pago:
   - Sin plazo de pago (contado): el vencimiento pasa a la fecha de recepción.
   - Con plazo (por ejemplo, 30 días): el vencimiento y cada cuota se calculan
     desde la recepción, no desde la fecha de la factura.
   La fecha de vencimiento se muestra en el encabezado y en **Fecha de
   vencimiento** de los apuntes contables.

Ejemplo: factura del 1 de enero, recepción el 5 de enero y pago a 30 días →
vencimiento el 4 de febrero.



