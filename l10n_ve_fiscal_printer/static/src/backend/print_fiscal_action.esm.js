// Copyright 2026 BWEALTHICS LLC
// License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {callBridge} from "@l10n_ve_fiscal_printer/app/utils/fiscal_bridge.esm";

registry
    .category("actions")
    .add("l10n_ve_fiscal_printer.print_fiscal", async (env, action) => {
        const params = action.params || {};
        try {
            const result = await callBridge(
                {
                    l10n_ve_bridge_url: params.bridge_url,
                    l10n_ve_bridge_token: params.bridge_token,
                },
                params.endpoint,
                params.payload
            );
            await env.services.orm.call("account.move", "l10n_ve_set_fiscal_result", [
                [params.move_id],
                result.numero_factura_fiscal,
                result.serial || params.machine_serial,
                params.doc_type,
            ]);
            env.services.notification.add(
                _t("Fiscal document %s printed.", result.numero_factura_fiscal),
                {type: "success"}
            );
            await env.services.action.doAction({
                type: "ir.actions.client",
                tag: "soft_reload",
            });
        } catch (error) {
            env.services.notification.add(error.message || String(error), {
                title: _t("Fiscal printer"),
                type: "danger",
                sticky: true,
            });
        }
    });
