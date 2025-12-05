/**
 * Vote Signing Module
 * Handles wallet-based vote signing for blockchain-verified elections
 */

const VoteSigning = {
    /**
     * Check if MetaMask is available
     */
    isMetaMaskAvailable() {
        return typeof window.ethereum !== 'undefined' && window.ethereum.isMetaMask;
    },

    /**
     * Get current connected wallet address
     */
    async getWalletAddress() {
        if (!this.isMetaMaskAvailable()) {
            throw new Error('MetaMask is not installed');
        }

        const accounts = await window.ethereum.request({ method: 'eth_accounts' });
        if (accounts.length === 0) {
            // Request connection
            const newAccounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            return newAccounts[0];
        }
        return accounts[0];
    },

    /**
     * Generate vote message to be signed
     * @param {string} electionType - 'party_president', 'country_president', or 'congress'
     * @param {number} electionId - The election ID
     * @param {number} candidateId - The candidate being voted for
     * @param {number} timestamp - Unix timestamp
     */
    generateVoteMessage(electionType, electionId, candidateId, timestamp) {
        return `TACTIZEN_VOTE|${electionType}|${electionId}|${candidateId}|${timestamp}`;
    },

    /**
     * Sign a vote with MetaMask
     * @param {string} electionType - Type of election
     * @param {number} electionId - Election ID
     * @param {number} candidateId - Candidate ID
     * @returns {Object} - {walletAddress, message, signature, timestamp}
     */
    async signVote(electionType, electionId, candidateId) {
        if (!this.isMetaMaskAvailable()) {
            throw new Error('MetaMask is required to vote. Please install MetaMask browser extension.');
        }

        try {
            // Get wallet address
            const walletAddress = await this.getWalletAddress();

            // Generate timestamp and message
            const timestamp = Math.floor(Date.now() / 1000);
            const message = this.generateVoteMessage(electionType, electionId, candidateId, timestamp);

            // Request signature from MetaMask
            const signature = await window.ethereum.request({
                method: 'personal_sign',
                params: [message, walletAddress]
            });

            return {
                walletAddress: walletAddress,
                message: message,
                signature: signature,
                timestamp: timestamp
            };
        } catch (error) {
            if (error.code === 4001) {
                throw new Error('Vote signature was rejected. You must sign the vote to submit it.');
            }
            throw error;
        }
    },

    /**
     * Submit a signed vote to the server
     * @param {string} voteUrl - The URL to submit the vote to
     * @param {Object} signedVote - The signed vote object
     * @param {string} csrfToken - CSRF token for the request
     */
    async submitSignedVote(voteUrl, signedVote, csrfToken) {
        const response = await fetch(voteUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                wallet_address: signedVote.walletAddress,
                vote_message: signedVote.message,
                vote_signature: signedVote.signature
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to submit vote');
        }

        return data;
    },

    /**
     * Complete vote flow: sign and submit
     * @param {string} electionType - Type of election
     * @param {number} electionId - Election ID
     * @param {number} candidateId - Candidate ID
     * @param {string} voteUrl - URL to submit vote
     * @param {string} csrfToken - CSRF token
     */
    async castVote(electionType, electionId, candidateId, voteUrl, csrfToken) {
        // Sign the vote
        const signedVote = await this.signVote(electionType, electionId, candidateId);

        // Submit to server
        const result = await this.submitSignedVote(voteUrl, signedVote, csrfToken);

        return result;
    },

    /**
     * Initialize vote buttons on the page
     * Call this after DOM is loaded
     */
    initVoteButtons() {
        document.querySelectorAll('.vote-btn-blockchain').forEach(button => {
            button.addEventListener('click', async (e) => {
                e.preventDefault();

                const btn = e.currentTarget;
                const electionType = btn.dataset.electionType;
                const electionId = parseInt(btn.dataset.electionId);
                const candidateId = parseInt(btn.dataset.candidateId);
                const voteUrl = btn.dataset.voteUrl;
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ||
                                 document.querySelector('input[name="csrf_token"]')?.value;

                // Disable button and show loading
                btn.disabled = true;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing...';

                try {
                    // Check MetaMask
                    if (!VoteSigning.isMetaMaskAvailable()) {
                        throw new Error('MetaMask is required to vote. Please install MetaMask.');
                    }

                    // Cast the vote
                    const result = await VoteSigning.castVote(
                        electionType, electionId, candidateId, voteUrl, csrfToken
                    );

                    // Success - show message and update UI
                    btn.innerHTML = '<i class="fas fa-check"></i> Vote Cast!';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-success');

                    // Show success message
                    if (result.message) {
                        showAlert('success', result.message);
                    }

                    // Reload page after short delay to show updated vote counts
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);

                } catch (error) {
                    // Error - restore button and show error
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                    showAlert('danger', error.message || 'Failed to cast vote');
                }
            });
        });
    }
};

/**
 * Show alert message (uses Bootstrap alert if available)
 */
function showAlert(type, message) {
    // Try to find existing alert container
    let alertContainer = document.getElementById('vote-alert-container');

    if (!alertContainer) {
        // Create container if not exists
        alertContainer = document.createElement('div');
        alertContainer.id = 'vote-alert-container';
        alertContainer.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 9999; max-width: 400px;';
        document.body.appendChild(alertContainer);
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    alertContainer.appendChild(alert);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    VoteSigning.initVoteButtons();
});
