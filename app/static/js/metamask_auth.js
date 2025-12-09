// app/static/js/metamask_auth.js

// GLOBAL flag to prevent multiple simultaneous connection attempts across all scripts
window.isWalletConnecting = window.isWalletConnecting || false;

    document.addEventListener('DOMContentLoaded', () => {
        // --- Moved Functions Inside DOMContentLoaded ---

        // Helper function to show ban modal
        function showBanModal(banMessage) {
            const modalMessageEl = document.getElementById('banModalMessage');
            if (modalMessageEl) {
                modalMessageEl.innerHTML = banMessage.replace(/\n/g, '<br>');
            }

            const banModalEl = document.getElementById('banModal');
            if (banModalEl && typeof bootstrap !== 'undefined') {
                const banModal = new bootstrap.Modal(banModalEl);
                banModal.show();
            }
        }

        // Helper function to update UI elements
        function updateWalletStatus(message, isError = false) {
            const statusEl = document.getElementById('walletStatus');
            if (statusEl) {
                // Clear all previous classes and styles
                statusEl.className = '';
                statusEl.style.cssText = 'font-size: 0.9rem; max-width: 400px; display: inline-block;';

                if (isError) {
                    // Style as Bootstrap alert-danger for errors
                    statusEl.className = 'alert alert-danger py-1 px-3 mb-0';
                    statusEl.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i>' + message;
                } else if (message === 'Success!') {
                    statusEl.className = 'alert alert-success py-1 px-3 mb-0';
                    statusEl.innerHTML = '<i class="fas fa-check-circle me-2"></i>' + message;
                } else if (message) {
                    // Normal status messages
                    statusEl.className = 'text-light';
                    statusEl.textContent = message;
                } else {
                    // Clear message
                    statusEl.textContent = '';
                }
            }
            // Update button state
            const connectBtn = document.getElementById('connectWalletBtn');
             if (connectBtn) {
                 // Disable button during critical phases, enable otherwise
                connectBtn.disabled = (message === 'Connecting...' || message === 'Fetching message...' || message === 'Waiting for signature...' || message === 'Verifying...');
            }
        }

        // Main function to handle wallet connection and signing
        async function connectAndSign() {
            // Prevent multiple simultaneous connection attempts (GLOBAL check)
            if (window.isWalletConnecting) {
                console.log('Connection already in progress, ignoring click');
                updateWalletStatus('Already connecting, please wait...', true);
                return;
            }

            // Check if MetaMask (or any Ethereum provider) is installed first
            if (typeof window.ethereum === 'undefined') {
                updateWalletStatus('MetaMask not detected!', true);
                if (typeof showWarning === 'function') {
                    showWarning('Please install MetaMask to connect your wallet.');
                } else {
                    // Show Bootstrap modal instead of alert
                    showBootstrapModal('MetaMask Required', 'Please install MetaMask to connect your wallet.', 'warning');
                }
                return; // Stop execution if no provider
            }

            // Check if ethers.js is loaded (check both global and window.ethers)
            const ethersLib = (typeof ethers !== 'undefined') ? ethers : window.ethers;
            if (typeof ethersLib === 'undefined') {
                 updateWalletStatus('Ethers.js library not loaded!', true);
                 if (typeof showError === 'function') {
                     showError('A required library (ethers.js) failed to load. Please refresh the page or check your connection.');
                 } else {
                     // Show Bootstrap modal instead of alert
                     showBootstrapModal('Library Error', 'A required library (ethers.js) failed to load. Please refresh the page or check your connection.', 'danger');
                 }
                 return; // Stop execution if library missing
            }

            // Set GLOBAL flag to prevent concurrent requests
            window.isWalletConnecting = true;

            updateWalletStatus('Connecting...');
            const provider = new ethersLib.providers.Web3Provider(window.ethereum, "any"); // Use "any" to allow network changes

            try {
                // 1. Request account access (triggers MetaMask prompt)
                // Use eth_requestAccounts for modern approach
                const accounts = await provider.send("eth_requestAccounts", []);
                if (!accounts || accounts.length === 0) {
                    updateWalletStatus('Connection refused by user.', true);
                    return;
                }
                const signerAddress = accounts[0];
                // Display truncated address immediately after connection
                updateWalletStatus(`Connected: ${signerAddress.substring(0, 6)}...${signerAddress.substring(signerAddress.length - 4)}`);
                console.log("Connected account:", signerAddress);

                updateWalletStatus('Fetching message...');

                // 2. Fetch the nonce/message to sign from the backend
                const messageResponse = await fetch('/auth/web3_message'); // Ensure URL is correct
                if (!messageResponse.ok) {
                    let errorMsg = `Failed to fetch message (${messageResponse.status})`;
                    try {
                        const errorData = await messageResponse.json();
                        errorMsg = errorData.error || errorMsg;
                    } catch(e) { /* Ignore if response not json */ }
                    throw new Error(errorMsg);
                }
                const messageData = await messageResponse.json();
                const messageToSign = messageData.message;
                if (!messageToSign) {
                     throw new Error("Received empty message from server.");
                }
                console.log("Message to sign:", messageToSign);


                updateWalletStatus('Waiting for signature...');

                // 3. Request signature from the user (triggers MetaMask prompt)
                const signer = provider.getSigner();
                let signature;
                try {
                    signature = await signer.signMessage(messageToSign);
                } catch (signError) {
                     // Handle specific signature rejection error
                    if (signError.code === 4001 || signError.code === 'ACTION_REJECTED') {
                         throw new Error('Signature request rejected by user.');
                     }
                     // Handle other potential signing errors
                     throw new Error(`Signing failed: ${signError.message}`);
                }
                console.log("Signature:", signature);


                updateWalletStatus('Verifying...');

                // Get CSRF token from meta tag
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

                // 4. Send address and signature to backend for verification
                const verifyResponse = await fetch('/auth/verify_signature', { // Ensure URL is correct
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        address: signerAddress,
                        signature: signature,
                    }),
                });

                const verifyData = await verifyResponse.json();

                if (verifyResponse.ok && verifyData.success) {
                    // Success! Redirect or reload page
                    console.log("Authentication successful!");
                    updateWalletStatus('Success!');
                    // Redirect to the URL provided by the backend, or just reload
                     window.location.href = verifyData.redirect_url || window.location.href; // Reload current page or redirect
                } else {
                    // Verification failed - Use error message from backend if available
                    const errorMessage = verifyData.error || `Verification failed (${verifyResponse.status})`;

                    // If it's a ban error (403 status), show modal notification
                    if (verifyResponse.status === 403) {
                        updateWalletStatus(''); // Clear status
                        showBanModal(errorMessage);
                        return; // Don't throw error, we're showing modal instead
                    }

                    throw new Error(errorMessage);
                }

            } catch (error) {
                console.error("Authentication error:", error);
                // Display specific error messages caught during the process
                updateWalletStatus(`Error: ${error.message}`, true);
                 // Re-enable button on error
                 const connectBtn = document.getElementById('connectWalletBtn');
                 if (connectBtn) connectBtn.disabled = false;
            } finally {
                // Always reset the GLOBAL connecting flag when done
                window.isWalletConnecting = false;
            }
        } // --- End connectAndSign ---


        // --- Event Listener Attachment ---
        const connectBtn = document.getElementById('connectWalletBtn');
        if (connectBtn) {
            connectBtn.addEventListener('click', connectAndSign);
        } else {
            // This might appear briefly if the user is logged in and the button isn't rendered
            // console.warn("Connect Wallet button not found (this might be normal if logged in).");
        }

         // Clear any previous wallet status on page load (optional)
         // updateWalletStatus('');

    }); // --- End DOMContentLoaded Listener ---


    // Optional: Add event listener for account changes in MetaMask (keep outside DOMContentLoaded)
    if (typeof window.ethereum !== 'undefined') {
        window.ethereum.on('accountsChanged', (accounts) => {
            console.log('MetaMask account changed:', accounts);
            // Could force logout or reload page depending on desired behavior
             if (accounts.length === 0) {
                console.log('MetaMask disconnected.');
                // Optionally redirect to logout or show message
                 // window.location.href = '/auth/logout'; // Example: Force logout
             } else {
                 console.log('Account changed, reloading for new state.');
                 window.location.reload(); // Reload to reflect new account
             }
        });
         window.ethereum.on('chainChanged', (chainId) => {
             console.log('MetaMask network changed:', chainId);
             // Often good to reload as contract addresses might change or app logic might depend on network
             window.location.reload();
         });
    }


    // --- Optional: Function to get CSRF token if needed (example) ---
    // function getCsrfToken() {
    //     const csrfInput = document.querySelector('input[name="csrf_token"]'); // Adjust selector if needed
    //     return csrfInput ? csrfInput.value : null;
    // }

    // Helper function to show Bootstrap modals instead of native alerts
    function showBootstrapModal(title, message, type = 'info') {
        const modalId = 'dynamicAlertModal';
        // Remove existing modal if present
        const existingModal = document.getElementById(modalId);
        if (existingModal) {
            existingModal.remove();
        }

        const iconClass = {
            'success': 'fa-check-circle text-success',
            'warning': 'fa-exclamation-triangle text-warning',
            'danger': 'fa-times-circle text-danger',
            'info': 'fa-info-circle text-info'
        }[type] || 'fa-info-circle text-info';

        const modalHtml = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content bg-dark text-light">
                        <div class="modal-header border-secondary">
                            <h5 class="modal-title"><i class="fas ${iconClass} me-2"></i>${title}</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">${message}</div>
                        <div class="modal-footer border-secondary">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">OK</button>
                        </div>
                    </div>
                </div>
            </div>`;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modalEl = document.getElementById(modalId);
        if (modalEl && typeof bootstrap !== 'undefined') {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
            // Clean up modal element after it's hidden
            modalEl.addEventListener('hidden.bs.modal', () => modalEl.remove());
        }
    }