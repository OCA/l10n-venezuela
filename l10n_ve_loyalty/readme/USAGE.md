# Usage

## Descuento en borrador

En facturas en borrador (VE), use el botón **Descuento** junto a los totales
para aplicar un descuento global con motivo, porcentaje o monto fijo.

En **monto fijo** elija la base:
- **Subtotal**: el monto reduce la base imponible (sin IVA).
- **Total**: el monto reduce el total con impuestos. Ejemplo: `100 + 16%`
  y descuento `10` sobre total deja el documento en `106`.

La máquina fiscal (TFHKA) aplica el descuento global (`q-`) sobre el subtotal.
Por eso, si eligió base **Total**, Odoo convierte el monto a base imponible
antes de enviarlo a la impresora (p. ej. `10` con IVA 16% → `~8,62`), para que
el ticket fiscal coincida con los totales del documento.

## Descuento post-factura

En facturas de cliente confirmadas (VE), use el botón **Descuento** del
header para generar una nota de crédito de descuento:

1. Seleccione el motivo (Pronto pago, Pago en divisas, Descuento comercial, etc.).
2. Indique porcentaje o monto sobre el subtotal sin IVA disponible.
3. Confirme; se crea la nota de crédito en borrador.

## Loyalty

Configure programas en **Ventas ? Productos ? Descuentos & Loyalty**. Las
recompensas de descuento en compañías venezolanas se aplican como descuento
global, no como línea de producto.
