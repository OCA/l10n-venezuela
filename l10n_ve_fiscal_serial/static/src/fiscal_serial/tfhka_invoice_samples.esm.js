/** @odoo-module **/

import {TfhkaFiscalMachine} from "./tfhka_fiscal_machine";

const SAMPLE_PARTNER = {
    vat: "J123456789",
    name: "Cliente Prueba Fiscal",
    address: "Av. Principal de la Urbina, Caracas",
    phone: "(0212) 555-55-55",
};

const SAMPLE_LINE_DISCOUNT_AMOUNT = 100;

const SAMPLE_INVOICE_LINES = [
    {
        tax: "0",
        price_unit: 1000,
        quantity: 1,
        name: "PRODUCTO EXENTO IVA",
        discount_amount: SAMPLE_LINE_DISCOUNT_AMOUNT,
    },
    {
        tax: "1",
        price_unit: 1000,
        quantity: 1,
        name: "PRODUCTO TASA GRAL 16%",
        discount_amount: SAMPLE_LINE_DISCOUNT_AMOUNT,
    },
    {
        tax: "2",
        price_unit: 1000,
        quantity: 1,
        name: "PRODUCTO TASA REDU 8%",
        discount_amount: SAMPLE_LINE_DISCOUNT_AMOUNT,
    },
    {
        tax: "3",
        price_unit: 1000,
        quantity: 1,
        name: "PRODUCTO TASA ADICIONAL",
        discount_amount: SAMPLE_LINE_DISCOUNT_AMOUNT,
    },
];

function _sampleGlobalDiscountAmount() {
    const grossSubtotal = SAMPLE_INVOICE_LINES.reduce(
        (sum, line) => sum + line.price_unit * line.quantity,
        0
    );
    const lineDiscountTotal = SAMPLE_INVOICE_LINES.reduce(
        (sum, line) => sum + (line.discount_amount || 0),
        0
    );
    const afterLineDiscount = grossSubtotal - lineDiscountTotal;
    return Math.round(afterLineDiscount * 0.1 * 100) / 100;
}

export function getSampleHkaInvoiceLines(flag21 = "30") {
    const machine = new TfhkaFiscalMachine(null);
    const result = machine.prepareInvoiceData({
        data: {
            flag_21: flag21,
            partner_id: SAMPLE_PARTNER,
            invoice_lines: SAMPLE_INVOICE_LINES,
            payment_lines: [{payment_method: "01", amount: 0}],
            info: ["FACTURA DE PRUEBA - ALICUOTAS Y DESCUENTOS"],
            aditional_lines: [],
            has_cashbox: false,
            global_discount_amount: _sampleGlobalDiscountAmount(),
        },
    });
    if (!result.valid || !result.cmd?.length) {
        return [
            "iR*J123456789",
            "iS*Cliente Prueba Fiscal",
            "i00Direccion: Av. Principal de la Urbina",
            "i01Telefono: (0212) 555-55-55",
        ];
    }
    return result.cmd;
}
