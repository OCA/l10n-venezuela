Configuración del diario
------------------------

En **Contabilidad → Configuración → Diarios**, pestaña **SENIAT**, seleccione **Máquina fiscal**
como medio de emisión y asigne la **Máquina fiscal** registrada. Al imprimir, el sistema verifica
que el puerto seleccionado corresponda a esa máquina (por serial fiscal); en **modo entrenamiento**
se omite esa verificación. El diario no aplica límite de
líneas por factura ni por guía de despacho; la impresión usa baudios, paridad y FLAG_21 de esa máquina.

Métodos de pago fiscales en cobros y pagos
------------------------------------------

En diarios de banco, caja o crédito (país VE), en las pestañas **Incoming Payments** /
**Outgoing Payments**, asigne el **Método pago fiscal** (01-24) a cada línea de cobro o
pago pendiente. Ese código se envía a la máquina fiscal al imprimir el pago correspondiente.

En la ficha de la máquina fiscal, pestaña **Configuración**, defina el **Método de pago por
defecto** usado cuando la factura no tiene pagos conciliados.

Consola de depuración
---------------------

Abra **SENIAT → Máquinas Fiscales → Máquinas**, entre en la ficha de una máquina y use la pestaña
**Consola de depuración**. La consola toma baudios, paridad y FLAG_21 del registro y asocia la
auditoría a esa máquina.

1. Pulse **Abrir conexión** y seleccione el puerto COM en el diálogo del navegador (Chrome/Edge, HTTPS).
2. Envíe comandos manuales, la secuencia de factura de prueba, reportes X/Z o configure FLAG_21.
3. Pulse **Cerrar conexión** al terminar; al salir del formulario el puerto se cierra automáticamente.

Para más detalle técnico abra la consola del navegador (F12). Los eventos quedan en la auditoría
fiscal serial de la máquina.

Auditoría fiscal serial
-----------------------

La auditoría se genera automáticamente al usar:

* Impresión fiscal desde facturas y notas.
* Reportes X/Z.
* Detección de máquinas en el asistente de configuración.
* Consola de depuración en el formulario de cada máquina fiscal.

Consulte los eventos en **SENIAT → Máquinas Fiscales → Auditoría fiscal serial**. Cada sesión agrupa los
eventos por `session_id` y permite filtrar por usuario, tipo de evento, máquina o factura.

Desde la ficha de una máquina fiscal puede abrir su historial con el botón **Auditoría**.
