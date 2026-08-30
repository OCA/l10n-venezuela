1. Set the sales journal's **Emission Medium** to **Fiscal machine** before
   posting documents that will be printed through the bridge.
2. Open Point of Sale settings and set the bridge URL, shared token, fiscal
   machine serial, and default backend payment code.
3. Set each POS payment method's HKA payment code.

Only one POS bridge can be configured per company for backend printing. Since
the usual URL points to `localhost`, the backend invoice form cannot safely
choose between multiple physical machines. POS printing is not subject to this
restriction because each register uses its own loaded configuration.

## Bridge contract

All endpoints use `POST`, JSON bodies, `Content-Type: application/json`, and an
`X-Bridge-Token` header. The token must be a random shared secret configured on
both sides and must never be embedded in source code.

Required endpoints are:

* `/claim-terminal`: accepts `{ "uuid": "<order uuid>" }`.
* `/release-terminal`: accepts `{ "uuid": "<order uuid>" }`.
* `/print-invoice`: accepts the fiscal payload described below.
* `/print-credit-note`: accepts the fiscal payload plus
  `numero_factura_afectada`, `serial_afectada`, and `fecha_afectada` in
  `DDMMYYYY` format.
* `/check-last-invoice`: accepts `{}` and returns the last invoice UUID, fiscal
  number, total, and serial.
* `/report-x`: accepts `{}`.
* `/report-z`: accepts `{}` and returns `numero_reporte_z`.

The invoice payload contains `uuid`, `cliente_nombre`, `cliente_rif`,
`serial_impresora`, `tasa_dolar`, `monto_total`, `monto_igtf`, `items`, and
`pagos`. Each item contains `descripcion`, `precio`, `cantidad`, and
`iva_porcentaje`. Each payment contains `metodo`, `monto`, and, from the POS,
the optional `divisa` flag.

A successful response must include `estado: "exito"`. Print responses also
include `numero_factura_fiscal` and preferably the real `serial` returned by the
machine. Error responses use a non-success `estado` and may provide `mensaje`.

The bridge must remember the last successfully printed invoice UUID and echo it
from `/check-last-invoice`; this is the primary anti-duplicate proof after a
browser timeout.

## Browser and network requirements

Calls originate in the cashier's or accounting user's browser. A bridge bound
to loopback should expose only the required endpoints and validate the shared
token on every request.

The bridge must answer CORS and Private Network Access preflights for the exact
Odoo origin. At minimum, its `OPTIONS` response must allow `POST`,
`Content-Type`, and `X-Bridge-Token`. Browsers requiring Private Network Access
also expect `Access-Control-Allow-Private-Network: true`. Do not use a wildcard
origin together with credentials. HTTPS Odoo deployments must be tested with
the chosen browser's loopback and mixed-content policy.

Automated tests mock the bridge. They do not open a serial port, ship the
Windows/HKA bridge, or certify a physical printer model.
