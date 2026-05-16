/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║         JEDNYMKLIK.PL — Widget JS                           ║
 * ║         Embed na stronę sklepu — art. 11a Dyrektywy UE      ║
 * ║                                                             ║
 * ║  Użycie:                                                    ║
 * ║  <script src="http://localhost:8000/widget.js"              ║
 * ║          data-shop-id="TWOJ_SHOP_ID"                        ║
 * ║          data-shop-token="TWOJ_TOKEN"                       ║
 * ║          data-order-id="NUMER_ZAMOWIENIA"                   ║
 * ║          data-customer-email="email@klienta.pl"             ║
 * ║          data-order-date="2026-05-16"                       ║
 * ║          data-order-value="299.99">                         ║
 * ║  </script>                                                  ║
 * ╚══════════════════════════════════════════════════════════════╝
 */

(function() {
    'use strict';

    // ─────────────────────────────────────────────
    // KONFIGURACJA
    // ─────────────────────────────────────────────
    const API_BASE = 'https://jednymklik-production.up.railway.app';

    const script = document.currentScript;
    const CONFIG = {
        shopId:         script.getAttribute('data-shop-id') || '',
        shopToken:      script.getAttribute('data-shop-token') || '',
        orderId:        script.getAttribute('data-order-id') || '',
        customerEmail:  script.getAttribute('data-customer-email') || '',
        customerName:   script.getAttribute('data-customer-name') || '',
        orderDate:      script.getAttribute('data-order-date') || '',
        orderValue:     script.getAttribute('data-order-value') || '',
        containerId:    script.getAttribute('data-container-id') || 'jednymklik-widget',
        lang:           script.getAttribute('data-lang') || 'pl',
        primaryColor:   script.getAttribute('data-color') || '#dc2626',
    };

    // ─────────────────────────────────────────────
    // TEKSTY — dopracowane, bardziej ludzkie
    // ─────────────────────────────────────────────
    const TEXTS = {
        pl: {
            btnLabel:           'Odstąp od umowy',
            step1Title:         'Prawo do odstąpienia od umowy',
            step1Subtitle:      'Krok 1 z 2',
            step1Info:          'Zgodnie z prawem masz 14 dni na odstąpienie od umowy zawartej przez internet — bez podawania przyczyny i bez dodatkowych kosztów.',
            step1OrderLabel:    'Numer zamówienia:',
            step1ReasonLabel:   'Powód zwrotu (opcjonalnie)',
            step1ReasonPlaceholder: 'Np. produkt niezgodny z opisem, zmieniłem/am zdanie, wybrałem/am zły rozmiar...',
            step1BtnNext:       'Potwierdzam i przechodzę dalej →',
            step1BtnCancel:     'Anuluj',
            step2Title:         'Czy na pewno chcesz odstąpić?',
            step2Subtitle:      'Krok 2 z 2 — ostatni krok',
            step2Warning:       '⚠️ Po potwierdzeniu Twoje odstąpienie zostanie zarejestrowane, a na podany adres email wyślemy oficjalne potwierdzenie. Tego działania nie można cofnąć.',
            step2BtnConfirm:    '✅ Tak, odstępuję od umowy',
            step2BtnBack:       '← Wróć',
            successTitle:       'Dziękujemy! Sprawa załatwiona ✓',
            successSubtitle:    'Twoje odstąpienie zostało zarejestrowane w systemie.',
            successText:        'Oficjalne potwierdzenie wysłaliśmy na adres:',
            successRefund:      'Zwrot pieniędzy nastąpi w ciągu 14 dni roboczych od daty odstąpienia. Środki wrócą tą samą metodą płatności.',
            successDeadline:    'Termin zwrotu towaru:',
            successClose:       'Zamknij okno',
            successBackToOrders:'Wróć do listy zamówień',
            errorText:          'Coś poszło nie tak. Odśwież stronę i spróbuj ponownie lub skontaktuj się ze sklepem.',
            errorRetry:         'Spróbuj ponownie',
            poweredBy:          'Zgodność z art. 11a Dyrektywy UE 2023/2673',
        },
        en: {
            btnLabel:           'Withdraw from contract',
            step1Title:         'Right of Withdrawal',
            step1Subtitle:      'Step 1 of 2',
            step1Info:          'You have the right to withdraw from this contract within 14 days without giving any reason and without additional costs.',
            step1OrderLabel:    'Order number:',
            step1ReasonLabel:   'Reason for return (optional)',
            step1ReasonPlaceholder: 'E.g. item not as described, changed my mind, wrong size...',
            step1BtnNext:       'Confirm and proceed →',
            step1BtnCancel:     'Cancel',
            step2Title:         'Are you sure you want to withdraw?',
            step2Subtitle:      'Step 2 of 2 — final step',
            step2Warning:       '⚠️ After confirmation, your withdrawal will be registered and we will send official confirmation to your email address. This action cannot be undone.',
            step2BtnConfirm:    '✅ Yes, I withdraw from the contract',
            step2BtnBack:       '← Back',
            successTitle:       'Withdrawal accepted',
            successSubtitle:    'All done — we have taken care of your request.',
            successText:        'Official confirmation was sent to:',
            successRefund:      'Your refund will be processed within 14 business days from the withdrawal date.',
            successDeadline:    'Return item by:',
            successClose:       'Close',
            successBackToOrders:'Back to orders',
            errorText:          'Something went wrong. Please refresh the page and try again, or contact the shop.',
            errorRetry:         'Try again',
            poweredBy:          'Compliant with art. 11a EU Directive 2023/2673',
        }
    };

    const T = TEXTS[CONFIG.lang] || TEXTS.pl;

    // ─────────────────────────────────────────────
    // STYLE CSS
    // ─────────────────────────────────────────────
    const CSS = `
        #jk-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: ${CONFIG.primaryColor};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.1s;
            font-family: inherit;
        }
        #jk-btn:hover  { opacity: 0.88; }
        #jk-btn:active { transform: scale(0.97); }

        #jk-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.55);
            z-index: 99998;
            align-items: center;
            justify-content: center;
            padding: 16px;
            backdrop-filter: blur(2px);
        }
        #jk-overlay.jk-open { display: flex; }

        #jk-modal {
            background: white;
            border-radius: 16px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 24px 64px rgba(0,0,0,0.25);
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            animation: jk-slide-up 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        @keyframes jk-slide-up {
            from { opacity: 0; transform: translateY(24px) scale(0.97); }
            to   { opacity: 1; transform: translateY(0) scale(1); }
        }

        .jk-header {
            background: ${CONFIG.primaryColor};
            color: white;
            padding: 20px 24px;
        }
        .jk-header h2 { margin: 0 0 4px; font-size: 18px; font-weight: 600; }
        .jk-header p  { margin: 0; font-size: 13px; opacity: 0.8; }

        .jk-body { padding: 24px; }

        .jk-info-box {
            background: #fef3c7;
            border: 1px solid #fbbf24;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13px;
            color: #92400e;
            margin-bottom: 16px;
            line-height: 1.5;
        }

        .jk-order-box {
            background: #f3f4f6;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 16px;
            font-size: 14px;
        }

        .jk-label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: #374151;
            margin-bottom: 6px;
        }

        .jk-textarea {
            width: 100%;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
            min-height: 80px;
            box-sizing: border-box;
            margin-bottom: 16px;
            line-height: 1.5;
        }
        .jk-textarea:focus { outline: 2px solid ${CONFIG.primaryColor}; border-color: transparent; }

        .jk-warning {
            background: #fef2f2;
            border: 1px solid #fca5a5;
            border-radius: 8px;
            padding: 14px 16px;
            font-size: 13px;
            color: #991b1b;
            margin-bottom: 20px;
            line-height: 1.55;
        }

        .jk-btn-primary {
            width: 100%;
            background: ${CONFIG.primaryColor};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 14px;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            margin-bottom: 8px;
            font-family: inherit;
            transition: opacity 0.2s, transform 0.1s;
        }
        .jk-btn-primary:hover  { opacity: 0.88; }
        .jk-btn-primary:active { transform: scale(0.98); }
        .jk-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

        .jk-btn-secondary {
            width: 100%;
            background: white;
            color: #374151;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 12px;
            font-size: 14px;
            cursor: pointer;
            font-family: inherit;
            transition: background 0.15s;
        }
        .jk-btn-secondary:hover { background: #f9fafb; }

        /* ── SUKCES ── */
        .jk-success-header {
            background: linear-gradient(135deg, #065f46 0%, #059669 100%);
            color: white;
            padding: 32px 24px 24px;
            text-align: center;
        }
        .jk-success-icon {
            font-size: 56px;
            display: block;
            margin-bottom: 12px;
            animation: jk-pop 0.4s cubic-bezier(0.34,1.56,0.64,1) 0.1s both;
        }
        @keyframes jk-pop {
            from { transform: scale(0); opacity: 0; }
            to   { transform: scale(1); opacity: 1; }
        }
        .jk-success-header h2 {
            margin: 0 0 6px;
            font-size: 20px;
            font-weight: 700;
        }
        .jk-success-header p {
            margin: 0;
            font-size: 13px;
            opacity: 0.85;
        }

        .jk-success-body { padding: 24px; }

        .jk-success-email {
            text-align: center;
            margin-bottom: 16px;
        }
        .jk-success-email p {
            font-size: 13px;
            color: #6b7280;
            margin: 0 0 4px;
        }
        .jk-success-email strong {
            font-size: 15px;
            color: #111827;
        }

        .jk-info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 16px;
        }
        .jk-info-tile {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 12px 14px;
            text-align: center;
        }
        .jk-info-tile .tile-label {
            font-size: 11px;
            color: #9ca3af;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: block;
            margin-bottom: 4px;
        }
        .jk-info-tile .tile-value {
            font-size: 14px;
            font-weight: 600;
            color: #111827;
        }
        .jk-info-tile .tile-value.green { color: #059669; }

        .jk-refund-box {
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 13px;
            color: #166534;
            margin-bottom: 16px;
            text-align: center;
            line-height: 1.5;
        }
        .jk-refund-box strong { display: block; font-size: 14px; margin-bottom: 2px; }

        .jk-ref-row {
            text-align: center;
            margin-bottom: 20px;
        }
        .jk-ref-row span {
            font-size: 12px;
            color: #9ca3af;
            display: block;
            margin-bottom: 4px;
        }
        .jk-ref-id {
            font-family: monospace;
            background: #e5e7eb;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 12px;
            color: #374151;
            word-break: break-all;
        }

        .jk-success-btns { display: flex; gap: 8px; }
        .jk-success-btns .jk-btn-primary  { margin: 0; flex: 1; }
        .jk-success-btns .jk-btn-secondary { flex: 1; }

        /* ── BŁĄD ── */
        .jk-error-header {
            background: #7f1d1d;
            color: white;
            padding: 20px 24px;
        }
        .jk-error-header h2 { margin: 0 0 4px; font-size: 18px; }
        .jk-error-header p  { margin: 0; font-size: 13px; opacity: 0.8; }

        .jk-error-body {
            padding: 24px;
            text-align: center;
        }
        .jk-error-icon { font-size: 40px; margin-bottom: 12px; }
        .jk-error-msg  { font-size: 14px; color: #374151; margin-bottom: 20px; line-height: 1.5; }

        .jk-footer {
            padding: 10px 24px;
            background: #f9fafb;
            border-top: 1px solid #e5e7eb;
            text-align: center;
            font-size: 11px;
            color: #9ca3af;
        }

        .jk-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.4);
            border-top-color: white;
            border-radius: 50%;
            animation: jk-spin 0.7s linear infinite;
            vertical-align: middle;
            margin-right: 6px;
        }
        @keyframes jk-spin { to { transform: rotate(360deg); } }
    `;

    // ─────────────────────────────────────────────
    // HTML WIDGETU
    // ─────────────────────────────────────────────
    function buildHTML() {
        return `
        <button id="jk-btn" type="button" aria-label="${T.btnLabel}">
            ↩ ${T.btnLabel}
        </button>

        <div id="jk-overlay" role="dialog" aria-modal="true" aria-labelledby="jk-modal-title">
            <div id="jk-modal">

                <!-- KROK 1 -->
                <div id="jk-step-1">
                    <div class="jk-header">
                        <h2 id="jk-modal-title">${T.step1Title}</h2>
                        <p>${T.step1Subtitle}</p>
                    </div>
                    <div class="jk-body">
                        <div class="jk-info-box">${T.step1Info}</div>
                        <div class="jk-order-box">
                            <strong>${T.step1OrderLabel}</strong> ${CONFIG.orderId || '—'}
                        </div>
                        <label class="jk-label" for="jk-reason">${T.step1ReasonLabel}</label>
                        <textarea id="jk-reason" class="jk-textarea"
                                  placeholder="${T.step1ReasonPlaceholder}"></textarea>
                        <button class="jk-btn-primary" id="jk-btn-next">${T.step1BtnNext}</button>
                        <button class="jk-btn-secondary" id="jk-btn-cancel-1">${T.step1BtnCancel}</button>
                    </div>
                    <div class="jk-footer">${T.poweredBy}</div>
                </div>

                <!-- KROK 2 — potwierdzenie -->
                <div id="jk-step-2" style="display:none">
                    <div class="jk-header">
                        <h2>${T.step2Title}</h2>
                        <p>${T.step2Subtitle}</p>
                    </div>
                    <div class="jk-body">
                        <div class="jk-warning">${T.step2Warning}</div>
                        <button class="jk-btn-primary" id="jk-btn-confirm">${T.step2BtnConfirm}</button>
                        <button class="jk-btn-secondary" id="jk-btn-back">${T.step2BtnBack}</button>
                    </div>
                    <div class="jk-footer">${T.poweredBy}</div>
                </div>

                <!-- SUKCES -->
                <div id="jk-step-success" style="display:none">
                    <div class="jk-success-header">
                        <span class="jk-success-icon">✅</span>
                        <h2>${T.successTitle}</h2>
                        <p>${T.successSubtitle}</p>
                    </div>
                    <div class="jk-success-body">

                        <div class="jk-success-email">
                            <p>${T.successText}</p>
                            <strong id="jk-email-display"></strong>
                        </div>

                        <div class="jk-info-grid">
                            <div class="jk-info-tile">
                                <span class="tile-label">${T.successDeadline}</span>
                                <span class="tile-value" id="jk-deadline-display">—</span>
                            </div>
                            <div class="jk-info-tile">
                                <span class="tile-label">Status</span>
                                <span class="tile-value green">Zarejestrowane</span>
                            </div>
                        </div>

                        <div class="jk-refund-box">
                            <strong>💳 ${T.successRefund}</strong>
                        </div>

                        <div class="jk-ref-row">
                            <span>Numer referencyjny odstąpienia</span>
                            <span class="jk-ref-id" id="jk-ref-id"></span>
                        </div>

                        <div class="jk-success-btns">
                            <button class="jk-btn-primary" id="jk-btn-close-success">${T.successClose}</button>
                            <button class="jk-btn-secondary" id="jk-btn-back-orders">${T.successBackToOrders}</button>
                        </div>

                    </div>
                    <div class="jk-footer">${T.poweredBy}</div>
                </div>

                <!-- BŁĄD -->
                <div id="jk-step-error" style="display:none">
                    <div class="jk-error-header">
                        <h2>Wystąpił problem</h2>
                        <p>Nie udało się zarejestrować odstąpienia</p>
                    </div>
                    <div class="jk-error-body">
                        <div class="jk-error-icon">⚠️</div>
                        <p class="jk-error-msg" id="jk-error-msg">${T.errorText}</p>
                        <button class="jk-btn-primary" id="jk-btn-retry">${T.errorRetry}</button>
                    </div>
                    <div class="jk-footer">${T.poweredBy}</div>
                </div>

            </div>
        </div>
        `;
    }

    // ─────────────────────────────────────────────
    // LOGIKA WIDGETU
    // ─────────────────────────────────────────────
    let withdrawalId = null;

    function showStep(step) {
        ['jk-step-1', 'jk-step-2', 'jk-step-success', 'jk-step-error'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = id === step ? 'block' : 'none';
        });
        if (step === 'jk-step-success') launchConfetti();
    }

    function launchConfetti() {
        if (typeof confetti === 'undefined') {
            const s = document.createElement('script');
            s.src = 'https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js';
            s.onload = runConfetti;
            document.head.appendChild(s);
        } else {
            runConfetti();
        }
    }

    function runConfetti() {
        const colors = ['#22c55e', '#86efac', '#eab308', '#f97316'];
        const end    = Date.now() + 2500;
        (function frame() {
            confetti({ particleCount: 8, angle:  60, spread: 55, origin: { x: 0.1 }, colors });
            confetti({ particleCount: 8, angle: 120, spread: 55, origin: { x: 0.9 }, colors });
            if (Date.now() < end) requestAnimationFrame(frame);
        })();
    }



    function openModal() {
        const overlay = document.getElementById('jk-overlay');
        if (overlay) overlay.classList.add('jk-open');
        showStep('jk-step-1');
    }

    function closeModal() {
        const overlay = document.getElementById('jk-overlay');
        if (overlay) overlay.classList.remove('jk-open');
        withdrawalId = null;
    }

    function setLoading(btnId, loading) {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled = loading;
        if (loading) {
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = `<span class="jk-spinner"></span> Przetwarzanie...`;
        } else {
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
        }
    }

    async function initiateWithdrawal() {
        setLoading('jk-btn-next', true);
        try {
            const response = await fetch(`${API_BASE}/api/v1/withdrawal/initiate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Shop-Token': CONFIG.shopToken,
                },
                body: JSON.stringify({
                    shop_id:        CONFIG.shopId,
                    order_id:       CONFIG.orderId,
                    customer_email: CONFIG.customerEmail,
                    customer_name:  CONFIG.customerName,
                    order_date:     CONFIG.orderDate,
                    order_value:    parseFloat(CONFIG.orderValue) || null,
                })
            });

            if (!response.ok) throw new Error('API error: ' + response.status);
            const data = await response.json();
            withdrawalId = data.withdrawal_id;
            showStep('jk-step-2');

        } catch (err) {
            console.error('JednymKlik error:', err);
            document.getElementById('jk-error-msg').textContent = T.errorText;
            showStep('jk-step-error');
        } finally {
            setLoading('jk-btn-next', false);
        }
    }

    async function confirmWithdrawal() {
        if (!withdrawalId) return;
        setLoading('jk-btn-confirm', true);

        const reason = document.getElementById('jk-reason')?.value || '';

        try {
            const response = await fetch(`${API_BASE}/api/v1/withdrawal/confirm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Shop-Token': CONFIG.shopToken,
                },
                body: JSON.stringify({
                    withdrawal_id: withdrawalId,
                    reason: reason || null,
                })
            });

            if (!response.ok) throw new Error('API error: ' + response.status);
            const data = await response.json();

            // Wypełnij ekran sukcesu
            document.getElementById('jk-email-display').textContent    = CONFIG.customerEmail;
            document.getElementById('jk-deadline-display').textContent = data.deadline_return;
            document.getElementById('jk-ref-id').textContent           = withdrawalId;
            showStep('jk-step-success');

        } catch (err) {
            console.error('JednymKlik error:', err);
            document.getElementById('jk-error-msg').textContent = T.errorText;
            showStep('jk-step-error');
        } finally {
            setLoading('jk-btn-confirm', false);
        }
    }

    // ─────────────────────────────────────────────
    // INICJALIZACJA
    // ─────────────────────────────────────────────
    function init() {
        // Wstrzyknij CSS
        const style = document.createElement('style');
        style.textContent = CSS;
        document.head.appendChild(style);

        // Znajdź lub stwórz kontener
        let container = document.getElementById(CONFIG.containerId);
        if (!container) {
            container = document.createElement('div');
            container.id = CONFIG.containerId;
            document.body.appendChild(container);
        }

        // Wstrzyknij HTML
        container.innerHTML = buildHTML();

        // Event listenery
        document.getElementById('jk-btn')?.addEventListener('click', openModal);
        document.getElementById('jk-btn-cancel-1')?.addEventListener('click', closeModal);
        document.getElementById('jk-btn-next')?.addEventListener('click', initiateWithdrawal);
        document.getElementById('jk-btn-back')?.addEventListener('click', () => showStep('jk-step-1'));
        document.getElementById('jk-btn-confirm')?.addEventListener('click', confirmWithdrawal);
        document.getElementById('jk-btn-retry')?.addEventListener('click', () => showStep('jk-step-1'));

        // Przyciski na ekranie sukcesu
        document.getElementById('jk-btn-close-success')?.addEventListener('click', closeModal);
        document.getElementById('jk-btn-back-orders')?.addEventListener('click', function() {
            closeModal();
            // Opcjonalnie: przekieruj do listy zamówień
            // window.location.href = '/moje-zamowienia';
        });

        // Zamknij po kliknięciu tła
        document.getElementById('jk-overlay')?.addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });

        // Zamknij na Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeModal();
        });

        console.log('JednymKlik.pl widget załadowany ✅');
    }

    // Uruchom po załadowaniu DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
