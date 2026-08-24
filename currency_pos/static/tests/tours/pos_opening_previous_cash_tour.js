import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import { registry } from "@web/core/registry";

function checkSuggestedOpeningAmounts(expectedValues) {
    return {
        content: `Opening cash inputs suggest previous balances: ${expectedValues.join(", ")}`,
        trigger: ".opening-cash-section .cash-input-sub-section input",
        run() {
            const inputs = [
                ...document.querySelectorAll(".opening-cash-section .cash-input-sub-section input"),
            ];
            if (inputs.length !== expectedValues.length) {
                throw new Error(
                    `Expected ${expectedValues.length} opening cash inputs, got ${inputs.length}`
                );
            }
            for (let index = 0; index < expectedValues.length; index++) {
                const actual = (inputs[index].value || "").replace(/\s/g, "");
                const expected = String(expectedValues[index]).replace(/\s/g, "");
                if (actual !== expected) {
                    throw new Error(
                        `Opening cash input #${index} expected "${expected}", got "${actual}"`
                    );
                }
            }
        },
    };
}

registry.category("web_tour.tours").add("PosOpeningSuggestsPreviousCashBalancesTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            checkSuggestedOpeningAmounts(["5.00", "20.00"]),
            Dialog.confirm("Open Register"),
            Chrome.endTour(),
        ].flat(),
});
