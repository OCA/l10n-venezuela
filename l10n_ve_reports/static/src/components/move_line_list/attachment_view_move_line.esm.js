import {AttachmentView} from "@mail/core/common/attachment_view";
import {onMounted} from "@odoo/owl";
import {useBus} from "@web/core/utils/hooks";

export class AttachmentViewMoveLine extends AttachmentView {
    static props = [...AttachmentView.props, "openInPopout"];
    static components = {AttachmentView};

    setup() {
        super.setup();
        if (this.props.openInPopout) {
            onMounted(this.onClickPopout);
        }
        useBus(this.uiService.bus, "resize", () => this.env.setPopout(false));
    }
}
