// Copyright 2026 BWEALTHICS LLC
// License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import {
    FiscalBridgeError,
    buildInvoicePayload,
    callBridge,
} from "@l10n_ve_fiscal_printer/app/utils/fiscal_bridge.esm";
import {expect, test} from "@odoo/hoot";
import {mockFetch} from "@odoo/hoot-mock";

test("callBridge sends the token and returns a successful mocked response", async () => {
    mockFetch((url, options) => {
        expect(url).toBe("http://localhost:5001/print-invoice");
        expect(options.method).toBe("POST");
        expect(new Headers(options.headers).get("X-Bridge-Token")).toBe("test-token");
        expect(JSON.parse(options.body).uuid).toBe("order-1");
        return JSON.stringify({
            estado: "exito",
            numero_factura_fiscal: "00000123",
            serial: "TEST123",
        });
    });
    const result = await callBridge(
        {
            l10n_ve_bridge_url: "http://localhost:5001/",
            l10n_ve_bridge_token: "test-token",
        },
        "/print-invoice",
        {uuid: "order-1"}
    );
    expect(result.numero_factura_fiscal).toBe("00000123");
});

test("callBridge exposes mocked bridge failures", async () => {
    mockFetch(() => JSON.stringify({estado: "error", mensaje: "printer offline"}));
    let error = null;
    try {
        await callBridge(
            {l10n_ve_bridge_url: "http://localhost:5001"},
            "/report-x",
            {}
        );
    } catch (caught) {
        error = caught;
    }
    expect(error).toBeInstanceOf(FiscalBridgeError);
    expect(error.message).toBe("printer offline");
    expect(error.ambiguous).toBe(false);
});

test("buildInvoicePayload preserves machine arithmetic and optional IGTF", () => {
    const paymentMethod = {
        l10n_ve_fiscal_payment_code: "02",
        l10n_ve_igtf_applies: true,
    };
    const order = {
        uuid: "order-2",
        lines: [
            {
                qty: 2,
                prices: {total_included: 23.21},
                tax_ids: [{amount: 16}],
                getFullProductName: () =>
                    "A product with a deliberately long fiscal description",
            },
        ],
        payment_ids: [{amount: 23.21, payment_method_id: paymentMethod}],
        getPartner: () => ({name: "Customer", vat: "J-123-4"}),
    };
    const payload = buildInvoicePayload(
        {
            config: {l10n_ve_machine_serial: "TEST123"},
            company: {l10n_ve_is_spe: true, l10n_ve_igtf_pct: 3},
        },
        order,
        10
    );
    expect(payload.items[0].descripcion.length <= 40).toBe(true);
    expect(payload.items[0].iva_porcentaje).toBe(16);
    expect(payload.monto_total).toBe(payload.items[0].precio * 2);
    expect(payload.pagos[0].monto).toBe(payload.monto_total);
    expect(payload.monto_igtf).toBe(6.96);
});
