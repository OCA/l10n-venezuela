import { describe, expect, test } from "@odoo/hoot";
import { applyInheritance } from "@web/core/template_inheritance";

const parser = new DOMParser();
const serializer = new XMLSerializer();

function applyTemplateInheritance(arch, operations) {
    const archXmlDoc = parser.parseFromString(arch, "text/xml");
    const inheritsDoc = parser.parseFromString(operations, "text/xml");
    const modifiedTemplate = applyInheritance(
        archXmlDoc.documentElement,
        inheritsDoc.documentElement,
        "currency_pos/test"
    );
    return serializer.serializeToString(modifiedTemplate);
}

const PAYMENT_AMOUNT_REPLACEMENT = `<div class="payment-amount px-3 text-end">
    <t t-if="line.isForeignCurrencyPayment and line.isForeignCurrencyPayment()">
        <div class="lh-sm">
            <t t-esc="getPaymentLineForeignAmountDisplay(line)"/>
        </div>
        <div class="small text-muted lh-sm">
            <t t-esc="getPaymentLineOrderAmountDisplay(line)"/>
        </div>
    </t>
    <t t-else="">
        <t t-esc="getPaymentLineOrderAmountDisplay(line)"/>
    </t>
</div>`;

const PAYMENT_SCREEN_PAYMENT_LINES_ARCH = `<t t-name="point_of_sale.PaymentScreenPaymentLines">
    <div class="paymentlines d-flex flex-column overflow-y-auto gap-1">
        <t t-foreach="props.paymentLines" t-as="line" t-key="line.uuid">
            <t t-if="line.isSelected()">
                <div t-attf-class="paymentline selected d-flex align-items-center bg-200 border rounded-3">
                    <div class="payment-infos d-flex align-items-center justify-content-between flex-grow-1 px-3 py-3 text-truncate cursor-pointer fs-2">
                        <span class="payment-name"><t t-esc="line.payment_method_id.name"/></span>
                        <div class="payment-amount px-3">
                            <t t-esc="env.utils.formatCurrency(line.get_amount())" />
                        </div>
                    </div>
                </div>
            </t>
            <t t-else="">
                <div class="paymentline d-flex align-items-center bg-view border rounded-3">
                    <div class="payment-infos d-flex align-items-center justify-content-between flex-grow-1 px-3 py-3 text-truncate cursor-pointer fs-2">
                        <t t-esc="line.payment_method_id.name" />
                        <div class="payment-amount px-3">
                            <t t-esc="env.utils.formatCurrency(line.get_amount())" />
                        </div>
                    </div>
                </div>
            </t>
        </t>
    </div>
</t>`;

const PAYMENT_SCREEN_STATUS_ARCH = `<t t-name="point_of_sale.PaymentScreenStatus">
    <div t-if="props.order.payment_ids.length == 0" class="text-center py-4 fs-4 my-auto">
        Please select a payment method
    </div>
    <section t-else="" t-attf-class="paymentlines-container p-3 rounded-3 border">
        <div class="payment-status-container d-flex flex-column-reverse flex-lg-row justify-content-between fs-2 pe-4 me-2">
            <div class="payment-status-remaining d-flex justify-content-between flex-grow-1">
                <span class="label pe-2">Remaining</span>
                <span class="amount align-self-end pe-5">
                    <t t-esc="remainingText" />
                </span>
            </div>
        </div>
    </section>
</t>`;

const PAYMENT_SCREEN_PAYMENT_LINES_OPERATIONS = `<t t-inherit="point_of_sale.PaymentScreenPaymentLines" t-inherit-mode="extension">
    <xpath expr="//span[hasclass('payment-name')]/following-sibling::div[hasclass('payment-amount')]" position="replace">
        ${PAYMENT_AMOUNT_REPLACEMENT}
    </xpath>
    <xpath expr="//div[hasclass('bg-view')]//div[hasclass('payment-amount')]" position="replace">
        ${PAYMENT_AMOUNT_REPLACEMENT}
    </xpath>
</t>`;

const PAYMENT_SCREEN_STATUS_OPERATIONS = `<t t-inherit="point_of_sale.PaymentScreenStatus" t-inherit-mode="extension">
    <xpath expr="//div[hasclass('payment-status-container')]" position="before">
        <div t-if="getPaymentStatusCurrencyLabel()" class="text-muted small pb-2">
            Entering amount in <t t-esc="getPaymentStatusCurrencyLabel()"/>
        </div>
    </xpath>
</t>`;

const PAYMENT_SCREEN_DUE_ARCH = `<t t-name="point_of_sale.PaymentScreenDue">
    <section class="paymentlines-container rounded-3 bg-view"
        t-att-class="{'paymentlines-empty': paymentLines.length === 0 }">
        <div class="total text-center py-2 py-lg-4 text-success">
            <t t-esc="this.env.utils.formatCurrency(currentOrder.getTotalDue())" />
        </div>
    </section>
</t>`;

const PAYMENT_SCREEN_DUE_OPERATIONS = `<t t-inherit="point_of_sale.PaymentScreenDue" t-inherit-mode="extension">
    <xpath expr="//section[hasclass('paymentlines-container')]" position="attributes">
        <attribute name="class" add="position-relative" separator=" "/>
    </xpath>
    <xpath expr="//div[hasclass('total')]" position="before">
        <div t-if="getPaymentCurrencyRateLabels().length"
            class="o_currency_pos_payment_rates position-absolute top-0 end-0 m-2 text-start text-muted fs-6 lh-sm">
            <div t-foreach="getPaymentCurrencyRateLabels()" t-as="rateLabel" t-key="rateLabel_index"
                t-esc="rateLabel"/>
        </div>
    </xpath>
</t>`;

const ORDER_RECEIPT_ARCH = `<t t-name="point_of_sale.OrderReceipt">
    <div class="pos-receipt p-2">
        <div class="paymentlines text-start" t-foreach="props.data.paymentlines" t-as="line" t-key="line_index">
            <t t-esc="line.name" />
            <span t-esc="props.formatCurrency(line.amount)" class="pos-receipt-right-align"/>
        </div>
    </div>
</t>`;

const ORDER_RECEIPT_OPERATIONS = `<t t-inherit="point_of_sale.OrderReceipt" t-inherit-mode="extension">
    <xpath expr="//div[hasclass('paymentlines')]" position="replace">
        <div
            class="paymentlines text-start d-flex justify-content-between"
            t-foreach="props.data.paymentlines"
            t-as="line"
            t-key="line_index"
        >
            <t t-esc="line.name" />
            <span class="pos-receipt-right-align text-end">
                <t t-if="line.is_foreign_currency_payment">
                    <div>
                        <t t-esc="formatReceiptPaymentForeignAmount(line)" />
                    </div>
                    <div>
                        (<t t-esc="props.formatCurrency(line.amount)" />)
                    </div>
                </t>
                <t t-else="">
                    <t t-esc="props.formatCurrency(line.amount)" />
                </t>
            </span>
        </div>
    </xpath>
</t>`;

describe("currency_pos payment screen templates", () => {
    test("PaymentScreenStatus inheritance applies without xpath errors", () => {
        const result = applyTemplateInheritance(
            PAYMENT_SCREEN_STATUS_ARCH,
            PAYMENT_SCREEN_STATUS_OPERATIONS
        );
        expect(result).toInclude("getPaymentStatusCurrencyLabel()");
        expect(result).toInclude("payment-status-container");
    });

    test("PaymentScreenDue inheritance shows rate labels without xpath errors", () => {
        const result = applyTemplateInheritance(
            PAYMENT_SCREEN_DUE_ARCH,
            PAYMENT_SCREEN_DUE_OPERATIONS
        );
        expect(result).toInclude("getPaymentCurrencyRateLabels()");
        expect(result).toInclude("o_currency_pos_payment_rates");
        expect(result).toInclude("position-relative");
    });

    test("PaymentScreenPaymentLines inheritance applies without xpath errors", () => {
        const result = applyTemplateInheritance(
            PAYMENT_SCREEN_PAYMENT_LINES_ARCH,
            PAYMENT_SCREEN_PAYMENT_LINES_OPERATIONS
        );
        expect(result).toInclude("getPaymentLineForeignAmountDisplay(line)");
        expect(result).toInclude("getPaymentLineOrderAmountDisplay(line)");
    });

    test("OrderReceipt inheritance applies without xpath errors", () => {
        const result = applyTemplateInheritance(ORDER_RECEIPT_ARCH, ORDER_RECEIPT_OPERATIONS);
        expect(result).toInclude("formatReceiptPaymentForeignAmount(line)");
        expect(result).toInclude("line.is_foreign_currency_payment");
    });
});
