// Copyright 2026 BWEALTHICS LLC
// License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import {
    AlertDialog,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {ControlButtons} from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import {callBridge} from "@l10n_ve_fiscal_printer/app/utils/fiscal_bridge.esm";

patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.l10nVeDialog = useService("dialog");
    },

    async clickL10nVeReportX() {
        try {
            await callBridge(this.pos.config, "/report-x", {});
            this.l10nVeDialog.add(AlertDialog, {
                title: _t("Fiscal printer"),
                body: _t("X report printed."),
            });
        } catch (error) {
            this.l10nVeDialog.add(AlertDialog, {
                title: _t("Fiscal printer"),
                body: error.message,
            });
        }
    },

    clickL10nVeReportZ() {
        this.l10nVeDialog.add(ConfirmationDialog, {
            title: _t("Z report"),
            body: _t(
                "The Z report closes the fiscal day and cannot be repeated. Continue?"
            ),
            confirm: async () => {
                try {
                    const result = await callBridge(this.pos.config, "/report-z", {});
                    await this.pos.data.call("pos.session", "write", [
                        [this.pos.session.id],
                        {l10n_ve_z_number: result.numero_reporte_z || ""},
                    ]);
                    this.l10nVeDialog.add(AlertDialog, {
                        title: _t("Fiscal printer"),
                        body: _t(
                            "Z report %s printed.",
                            result.numero_reporte_z || "-"
                        ),
                    });
                } catch (error) {
                    this.l10nVeDialog.add(AlertDialog, {
                        title: _t("Fiscal printer"),
                        body: error.message,
                    });
                }
            },
        });
    },
});
