# Usage

1. Instale `l10n_ve_loyalty_pos` (auto-install con POS + loyalty VE).
2. Configure programas loyalty habilitados para el TPV.
3. En el POS:
   - **Recarga de monedero**: se vende el producto de recarga (producto normal).
   - **Consumo de monedero / gift card / promociones**: no aparece como producto
     en el carrito; se refleja en totales como descuento global.
   - **Descuento global manual**: en Acciones use *Descuento global* para agregar
     monto o porcentaje (con motivo) o para quitar uno existente. En monto fijo
     elija la base (**Subtotal** o **Total**, igual que en factura) y puede
     capturar el valor en BS o en USD ($); si elige dólares, se convierte
     a la moneda del pedido con la tasa vigente. No usa producto en el carrito;
     solo afecta totales, la factura y la impresión fiscal (`q-` sobre subtotal).
4. En el resumen del pedido verá Subtotal, Descuentos, Impuestos y Total.
5. Al facturar, esos descuentos se registran en `l10n_ve_global_discount_ids`.
   Si la base fue **Total**, el monto guardado ya es la base imponible equivalente
   (la máquina fiscal recibe ese valor, no el bruto con IVA).
6. **Reembolso a monedero**: en un reembolso, si paga con un método **sin diario**
   (crédito / `pay_later`), el monto se abona al monedero electrónico del cliente
   (debe tener cliente seleccionado y un programa eWallet activo en el TPV).
   Solo se abona la parte del pedido original pagada con métodos con diario
   (efectivo/banco). Lo pagado a crédito en el original solo cancela la CxC:
   - Original 100% crédito → reembolso a crédito **no** genera monedero.
   - Original mixto (p. ej. 50 efectivo + 50 crédito) → el reembolso a crédito
     abona como máximo 50 al monedero (y reparte ese tope entre reembolsos).
7. **Monedas distintas**: si el pedido está en bolívares y el monedero en dólares
   (o viceversa), la recarga, el abono por reembolso y el consumo convierten el
   monto con la tasa de cambio vigente de la compañía.
8. **Pago con monedero**: el consumo del monedero aparece en el ticket y en la
   factura fiscal como forma de pago **Monedero D** (no como descuento del 100%).

