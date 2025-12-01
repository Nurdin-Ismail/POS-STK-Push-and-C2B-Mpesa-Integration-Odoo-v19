/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { NumberPopup } from "@point_of_sale/app/components/popups/number_popup/number_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { rpc } from "@web/core/network/rpc";
import { MpesaCallbackPopup } from "./mpesa_callback_popup";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.mpesaState = useState({
            stkEnabled: false,
            checkoutRequestId: null,
            isProcessing: false
        });
    },

    get hasMpesaPaymentMethod() {
        return this.payment_methods_from_config.some(
            method => method.name && method.name.toLowerCase().includes('mpesa')
        );
    },

    get mpesaPaymentMethod() {
        return this.payment_methods_from_config.find(
            method => method.name && method.name.toLowerCase().includes('mpesa')
        );
    },

    toggleMpesaStk() {
        console.log('╔════════════════════════════════════════════════════════════════');
        console.log('║ M-PESA STK TOGGLE');
        console.log('╠════════════════════════════════════════════════════════════════');
        console.log('║ Current State:', this.mpesaState.stkEnabled ? 'ENABLED' : 'DISABLED');
        console.log('║ New State:', !this.mpesaState.stkEnabled ? 'ENABLED' : 'DISABLED');
        console.log('╚════════════════════════════════════════════════════════════════');

        this.mpesaState.stkEnabled = !this.mpesaState.stkEnabled;

        if (this.mpesaState.stkEnabled && this.mpesaPaymentMethod && !this.hasMpesaPaymentLine()) {
            console.log('✓ Adding M-Pesa payment line automatically');
            this.addNewPaymentLine(this.mpesaPaymentMethod);
        }
    },

    get isMpesaStkEnabled() {
        return this.mpesaState.stkEnabled;
    },

    hasMpesaPaymentLine() {
        return this.paymentLines.some(
            line => line.payment_method_id.name &&
                line.payment_method_id.name.toLowerCase().includes('mpesa')
        );
    },

    isValidKenyanNumber(phoneNumber) {
        const cleaned = phoneNumber.replace(/[\s\-\(\)]/g, '');
        const pattern = /^(07|01)\d{8}$|^(2547|2541)\d{8}$|^\+?(2547|2541)\d{8}$/;
        return pattern.test(cleaned);
    },

    async initiateMpesaPayment(phoneNumber, amount, orderReference) {
        console.log('╔════════════════════════════════════════════════════════════════');
        console.log('║ INITIATING M-PESA STK PUSH');
        console.log('╠════════════════════════════════════════════════════════════════');
        console.log('║ Phone Number:', phoneNumber);
        console.log('║ Amount (raw):', amount);
        console.log('║ Amount (type):', typeof amount);
        console.log('║ Order Reference:', orderReference);
        console.log('╚════════════════════════════════════════════════════════════════');

        try {
            const response = await rpc('/mpesa/stk_push', {
                phone_number: phoneNumber,
                amount: amount,
                order_reference: orderReference
            });

            console.log('╔════════════════════════════════════════════════════════════════');
            console.log('║ STK PUSH RESPONSE');
            console.log('╠════════════════════════════════════════════════════════════════');
            console.log('║ Success:', response.success);
            console.log('║ Message:', response.message);
            if (response.checkout_request_id) {
                console.log('║ Checkout Request ID:', response.checkout_request_id);
            }
            if (response.merchant_request_id) {
                console.log('║ Merchant Request ID:', response.merchant_request_id);
            }
            console.log('║ Full Response:', JSON.stringify(response, null, 2));
            console.log('╚════════════════════════════════════════════════════════════════');

            return response;
        } catch (error) {
            console.error('╔════════════════════════════════════════════════════════════════');
            console.error('║ M-PESA STK PUSH ERROR');
            console.error('╠════════════════════════════════════════════════════════════════');
            console.error('║ Error:', error);
            console.error('║ Error Message:', error.message);
            console.error('║ Stack:', error.stack);
            console.error('╚════════════════════════════════════════════════════════════════');
            return {
                success: false,
                message: error.message || 'Failed to initiate payment'
            };
        }
    },

    async checkCallbackReceived(checkoutRequestId) {
        console.log('→ Checking if callback already received for:', checkoutRequestId);
        try {
            const result = await rpc('/mpesa/check_callback_received', {
                checkout_request_id: checkoutRequestId
            });

            if (result.callback_received) {
                console.log('✓ Callback already received!');
                console.log('  Receipt:', result.receipt_number);
                console.log('  Status:', result.status);
                return result;
            }
            return null;
        } catch (error) {
            console.log('⚠ Error checking callback:', error.message);
            return null;
        }
    },

    async checkMpesaPaymentStatus(checkoutRequestId, maxAttempts = 30) {
        console.log('╔════════════════════════════════════════════════════════════════');
        console.log('║ CHECKING M-PESA PAYMENT STATUS');
        console.log('╠════════════════════════════════════════════════════════════════');
        console.log('║ Checkout Request ID:', checkoutRequestId);
        console.log('║ Max Attempts:', maxAttempts);
        console.log('║ Callback checks: Every 2 seconds');
        console.log('║ API queries: Every 10 seconds');
        console.log('╚════════════════════════════════════════════════════════════════');

        let attempts = 0;
        let apiQueryCounter = 0;
        let skipApiUntilAttempt = 0; // Track when to resume API queries

        console.log('⏳ Starting status monitoring...');

        while (attempts < maxAttempts) {
            attempts++;
            console.log(`\n→ Attempt ${attempts}/${maxAttempts}`);

            // Check callback DB (fast, no API call)
            const callbackCheck = await this.checkCallbackReceived(checkoutRequestId);
            if (callbackCheck && callbackCheck.callback_received) {
                console.log('✓ Callback received!');
                if (callbackCheck.status === 'success') {
                    console.log('✓ Payment confirmed via callback!');
                    return {
                        success: true,
                        message: 'Payment successful',
                        receipt: callbackCheck.receipt_number
                    };
                } else if (callbackCheck.status === 'cancelled') {
                    console.log('✗ Payment cancelled (from callback)');
                    return { success: false, message: 'Payment cancelled by user', cancelled: true };
                } else if (callbackCheck.status === 'failed') {
                    console.log('✗ Payment failed (from callback)');
                    return { success: false, message: callbackCheck.result_desc || 'Payment failed' };
                }
            }

            // Query API only every 4 attempts AND if not rate limited
            if (attempts % 4 === 0 && attempts > skipApiUntilAttempt) {
                apiQueryCounter++;
                console.log(`→ API Query #${apiQueryCounter} (every 10 seconds)`);

                try {
                    const response = await rpc('/mpesa/check_status', {
                        checkout_request_id: checkoutRequestId
                    });

                    console.log('  Status:', response.status);
                    console.log('  Message:', response.message);

                    if (response.status === 'completed') {
                        console.log('✓ Payment completed (via API)!');
                        return { success: true, message: response.message };
                    } else if (response.status === 'cancelled') {
                        console.log('✗ Payment cancelled by user');
                        return { success: false, message: response.message, cancelled: true };
                    } else if (response.status === 'failed') {
                        console.log('✗ Payment failed (via API)');
                        return {
                            success: false,
                            message: response.message || response.error || 'Payment failed'
                        };
                    } else if (response.status === 'error') {
                        console.log('⚠ API error:', response.message);

                        if (response.message && response.message.toLowerCase().includes('rate')) {
                            console.log('⚠ Rate limit detected, pausing API queries for 30 seconds...');
                            skipApiUntilAttempt = attempts + 15; // Resume after 15 attempts (30 sec)
                        }
                    } else if (response.status === 'pending') {
                        console.log('⏳ Payment still pending (via API)');
                    }
                } catch (error) {
                    console.error('✗ API query error:', error);

                    if (error.message && error.message.toLowerCase().includes('rate')) {
                        console.log('⚠ Rate limit hit, pausing API queries for 30 seconds...');
                        skipApiUntilAttempt = attempts + 15;
                    }
                }
            } else if (attempts % 4 === 0) {
                console.log(`  API queries paused due to rate limit (resume at attempt ${skipApiUntilAttempt + 1})`);
            } else {
                console.log('  Callback check only (no API call)');
            }

            // Wait 2 seconds before next check
            await new Promise(resolve => setTimeout(resolve, 2000));
        }

        console.log('✗ Payment timeout after', maxAttempts * 2, 'seconds');
        return { success: false, message: 'Payment timeout. Customer may not have completed payment.' };
    },

    async validateOrder(isForceValidate = false) {
        console.log('╔════════════════════════════════════════════════════════════════');
        console.log('║ VALIDATE ORDER CALLED');
        console.log('╠════════════════════════════════════════════════════════════════');
        console.log('║ Has M-Pesa Payment Line:', this.hasMpesaPaymentLine());
        console.log('║ STK Enabled:', this.mpesaState.stkEnabled);
        console.log('║ Is Processing:', this.mpesaState.isProcessing);
        console.log('╚════════════════════════════════════════════════════════════════');

        // C2B FLOW
        if (this.hasMpesaPaymentLine() && !this.mpesaState.stkEnabled) {
            console.log('→ C2B FLOW: Searching for direct payments...');

            const mpesaLine = this.paymentLines.find(
                line => line.payment_method_id.name?.toLowerCase().includes('mpesa')
            );

            if (!mpesaLine) {
                console.log('✗ M-Pesa payment line not found');
                await super.validateOrder(isForceValidate);
                return;
            }

            const amount = mpesaLine.amount;
            console.log('║ Payment Amount:', amount);

            this.env.services.notification.add(_t("Searching for M-Pesa payment..."), { type: "info" });

            try {
                const searchResult = await rpc('/mpesa/search_unreconciled_callbacks', {
                    amount: amount,
                    max_age_minutes: 10
                });

                console.log('║ Search Result:', searchResult);

                if (!searchResult.success || searchResult.count === 0) {
                    console.log('✗ No matching payments found');

                    const confirmed = await new Promise((resolve) => {
                        this.env.services.dialog.add(ConfirmationDialog, {
                            title: _t("No M-Pesa Payment Found"),
                            body: _t("No matching M-Pesa payment found in the last 10 minutes.\n\nValidate order anyway?"),
                            confirm: () => resolve(true),
                            cancel: () => resolve(false),
                        });
                    });

                    if (!confirmed) {
                        console.log('✗ User cancelled validation');
                        return;
                    }

                    console.log('→ Validating without reconciliation');
                    await super.validateOrder(isForceValidate);
                    return;
                }

                console.log(`✓ Found ${searchResult.count} matching payment(s)`);

                const selectedCallback = await makeAwaitable(this.env.services.dialog, MpesaCallbackPopup, {
                    callbacks: searchResult.callbacks,
                    amount: amount
                });

                if (selectedCallback === 'skip') {
                    console.log('→ User chose to skip reconciliation');
                    await super.validateOrder(isForceValidate);
                    return;
                }

                if (!selectedCallback) {
                    console.log('✗ User cancelled selection');
                    return;
                }

                console.log('✓ Callback selected:', selectedCallback.id);

                // VALIDATE ORDER FIRST to get id
                await super.validateOrder(isForceValidate);

                // NOW reconcile with the id
                if (this.currentOrder.id) {
                    console.log('→ Reconciling callback to order:', this.currentOrder.id);

                    try {
                        const reconcileResult = await rpc('/mpesa/reconcile_callback', {
                            callback_id: selectedCallback.id,
                            order_id: this.currentOrder.id
                        });

                        if (reconcileResult.success) {
                            console.log('✓ Callback reconciled successfully');
                            this.env.services.notification.add(
                                _t("Payment matched! Receipt: %s", reconcileResult.receipt_number),
                                { type: "success" }
                            );
                        } else {
                            console.log('⚠ Reconciliation failed:', reconcileResult.message);
                        }
                    } catch (error) {
                        console.error('✗ Reconciliation error:', error);
                    }
                } else {
                    console.log('⚠ Order validation succeeded but no id available');
                }

                return;
            } catch (error) {
                console.error('✗ C2B Flow Error:', error);
                this.env.services.notification.add(
                    _t("Error searching for payments: %s", error.message || 'Unknown error'),
                    { type: "danger" }
                );
                return;
            }
        }

        // STK PUSH FLOW
        if (this.hasMpesaPaymentLine() && this.mpesaState.stkEnabled) {
            console.log('→ STK PUSH FLOW');

            if (this.mpesaState.isProcessing) {
                console.log('⚠ Payment already in progress');
                this.notification.add(_t("Payment is already being processed"), { type: "warning" });
                return;
            }

            const phoneNumber = await makeAwaitable(this.dialog, NumberPopup, {
                title: _t("Enter M-Pesa Phone Number"),
                startingValue: "",
                placeholder: "07XXXXXXXX or 01XXXXXXXX"
            });

            if (phoneNumber === undefined) {
                console.log('✗ Phone number entry cancelled');
                return;
            }

            console.log('→ Phone number entered:', phoneNumber);

            if (!this.isValidKenyanNumber(phoneNumber)) {
                console.log('✗ Invalid phone number format');
                this.dialog.add(AlertDialog, {
                    title: _t("Invalid Phone Number"),
                    body: _t("Please enter a valid Kenyan phone number starting with 07 or 01.")
                });
                return;
            }

            console.log('✓ Phone number valid');

            this.mpesaState.phoneNumber = phoneNumber;
            this.mpesaState.isProcessing = true;

            const mpesaPaymentLine = this.paymentLines.find(
                line => line.payment_method_id.name &&
                    line.payment_method_id.name.toLowerCase().includes('mpesa')
            );

            const amount = mpesaPaymentLine ? mpesaPaymentLine.amount : this.currentOrder.get_due();
            const orderReference = this.currentOrder.name || `ORDER-${Date.now()}`;

            console.log('╔════════════════════════════════════════════════════════════════');
            console.log('║ ORDER DETAILS');
            console.log('╠════════════════════════════════════════════════════════════════');
            console.log('║ M-Pesa Payment Line Amount:', mpesaPaymentLine?.amount);
            console.log('║ Amount to Charge:', amount);
            console.log('║ Order Reference:', orderReference);
            console.log('║ Order Name:', this.currentOrder.name);
            console.log('╚════════════════════════════════════════════════════════════════');

            this.notification.add(_t("Sending STK Push to %s...", phoneNumber), { type: "info" });

            const stkResponse = await this.initiateMpesaPayment(phoneNumber, amount, orderReference);

            if (!stkResponse.success) {
                console.log('✗ STK Push failed');
                this.mpesaState.isProcessing = false;
                this.dialog.add(AlertDialog, {
                    title: _t("Payment Failed"),
                    body: _t("STK Push failed:\n\n%s", stkResponse.message)
                });
                return;
            }

            console.log('✓ STK Push sent successfully');

            this.mpesaState.checkoutRequestId = stkResponse.checkout_request_id;
            this.notification.add(_t("Please check your phone and enter M-Pesa PIN"), { type: "success" });

            const statusResult = await this.checkMpesaPaymentStatus(stkResponse.checkout_request_id);
            this.mpesaState.isProcessing = false;

            if (statusResult.success) {
                console.log('✓ Payment successful! Validating order...');
                this.notification.add(_t("Payment successful!"), { type: "success" });

                await super.validateOrder(isForceValidate);

                // Reconcile STK callback to order
                if (this.currentOrder.id && statusResult.callback_id) {
                    console.log('→ Reconciling STK callback to order:', this.currentOrder.id);

                    try {
                        const reconcileResult = await rpc('/mpesa/reconcile_callback', {
                            callback_id: statusResult.callback_id,
                            order_id: this.currentOrder.id
                        });

                        if (reconcileResult.success) {
                            console.log('✓ STK callback reconciled successfully');
                            this.env.services.notification.add(
                                _t("Payment matched! Receipt: %s", reconcileResult.receipt_number),
                                { type: "success" }
                            );
                        }
                    } catch (error) {
                        console.error('✗ STK callback reconciliation error:', error);
                    }
                }
            } else {
                console.log('✗ Payment not successful');
                const title = statusResult.cancelled ? _t("Payment Cancelled") : _t("Payment Failed");
                const errorDetails = statusResult.message || 'Unknown error occurred';

                this.dialog.add(AlertDialog, {
                    title: title,
                    body: _t("Payment Error:\n\n%s\n\nPlease try again or use a different payment method.", errorDetails)
                });
            }
            return;
        }

        console.log('→ Normal validation (no M-Pesa)');
        await super.validateOrder(isForceValidate);
    }
});