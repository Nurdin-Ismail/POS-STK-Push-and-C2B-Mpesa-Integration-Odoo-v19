/** @odoo-module **/

import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class MpesaCallbackPopup extends Component {
    static template = "mpesa_integration.MpesaCallbackPopup";
    static components = { Dialog };
    static props = {
        callbacks: Array,
        amount: Number,
        close: Function,
        getPayload: { type: Function, optional: true },
    };

    setup() {
        console.log('MpesaCallbackPopup setup', this.props);
        this.dialog = useService("dialog");
        this.selectedCallback = null;
    }

    async onSelectCallback(callback) {
        console.log('→ Callback selection requested:', callback);

        // Show confirmation dialog
        const confirmed = await new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Confirm Payment Selection"),
                body: _t(
                    "Match this payment to the order?\n\n" +
                    "Receipt: %s\n" +
                    "Amount: KES %s\n" +
                    "Customer: %s\n" +
                    "Phone: %s",
                    callback.mpesa_receipt_number,
                    callback.amount.toFixed(2),
                    callback.customer_name || 'Unknown',
                    this.formatPhone(callback.phone_number)
                ),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
                confirmLabel: _t("Yes, Match Payment"),
                cancelLabel: _t("Cancel"),
            });
        });

        if (confirmed) {
            console.log('✓ Callback selected:', callback);
            this.selectedCallback = callback;
            this.props.getPayload(callback);
            this.props.close();
        } else {
            console.log('✗ Selection cancelled by user');
        }
    }

    async onSkipReconciliation() {
        console.log('→ Skip reconciliation requested');

        // Show confirmation dialog
        const confirmed = await new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Validate Without Payment Match"),
                body: _t(
                    "Are you sure you want to validate this order without matching an M-Pesa payment?\n\n" +
                    "This should only be done if:\n" +
                    "• The customer paid but payment is not shown\n" +
                    "• You will manually reconcile later\n" +
                    "• Customer is using a different payment method"
                ),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
                confirmLabel: _t("Yes, Validate Anyway"),
                cancelLabel: _t("Go Back"),
            });
        });

        if (confirmed) {
            console.log('→ Skipping reconciliation (confirmed)');
            this.props.getPayload('skip');
            this.props.close();
        } else {
            console.log('✗ Skip cancelled by user');
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        try {
            const date = new Date(dateStr);
            return date.toLocaleString('en-GB', {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateStr;
        }
    }

    formatPhone(phone) {
        if (!phone) return 'N/A';
        if (phone.startsWith('254')) {
            phone = '0' + phone.substring(3);
        }
        if (phone.length === 10) {
            return `${phone.substring(0, 4)} ${phone.substring(4, 7)} ${phone.substring(7)}`;
        }
        return phone;
    }
}