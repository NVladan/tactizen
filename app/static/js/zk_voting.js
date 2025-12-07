/**
 * ZK Voting - Client-side proof generation
 *
 * Uses snarkjs to generate Groth16 proofs for anonymous voting.
 * Proofs are verified on zkVerify blockchain for trustless verification.
 */

// Circuit files (loaded after compilation)
const CIRCUIT_WASM = '/static/circuits/anonymous_vote.wasm';
const CIRCUIT_ZKEY = '/static/circuits/anonymous_vote.zkey';

// Storage keys for voter secrets
const STORAGE_PREFIX = 'zkVote_';

/**
 * Generate cryptographically secure random field element
 * Uses Web Crypto API for randomness
 */
function generateRandomFieldElement() {
    const FIELD_PRIME = BigInt('21888242871839275222246405745257275088548364400416034343698204186575808495617');

    // Generate 32 random bytes
    const randomBytes = new Uint8Array(32);
    crypto.getRandomValues(randomBytes);

    // Convert to BigInt and reduce mod field prime
    let value = BigInt(0);
    for (let i = 0; i < 32; i++) {
        value = (value << BigInt(8)) + BigInt(randomBytes[i]);
    }

    return (value % FIELD_PRIME).toString();
}

/**
 * Poseidon hash - calls server-side API for circomlib-compatible Poseidon
 * This ensures hash compatibility between frontend, backend, and Circom circuits
 */
async function poseidonHash(inputs) {
    const response = await fetch('/api/zk/poseidon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inputs: inputs.map(x => x.toString()) })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Poseidon hash failed');
    }

    const result = await response.json();
    return result.hash;
}

/**
 * Load external script dynamically
 */
function loadScript(src) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) {
            resolve();
            return;
        }
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

/**
 * Generate voter secrets and commitment
 * Called once during voter registration
 */
async function generateVoterCommitment(electionType, scopeId) {
    // Generate random secrets
    const secret = generateRandomFieldElement();
    const nullifierSecret = generateRandomFieldElement();

    // Compute commitment = Poseidon(secret, nullifierSecret)
    const commitment = await poseidonHash([secret, nullifierSecret]);

    // Store secrets in localStorage (browser-only storage)
    const storageKey = `${STORAGE_PREFIX}${electionType}_${scopeId}`;
    const voterData = {
        secret,
        nullifierSecret,
        commitment: '0x' + BigInt(commitment).toString(16).padStart(64, '0'),
        registeredAt: new Date().toISOString()
    };
    localStorage.setItem(storageKey, JSON.stringify(voterData));

    return voterData.commitment;
}

/**
 * Get stored voter data
 */
function getVoterData(electionType, scopeId) {
    const storageKey = `${STORAGE_PREFIX}${electionType}_${scopeId}`;
    const data = localStorage.getItem(storageKey);
    return data ? JSON.parse(data) : null;
}

/**
 * Register for anonymous voting
 */
async function registerForZKVoting(electionType, scopeId = null) {
    try {
        // Check if already registered
        const existing = getVoterData(electionType, scopeId);
        if (existing) {
            // Check if server has our registration
            const statusResp = await fetch(`/api/zk/registration-status?election_type=${electionType}${scopeId ? '&scope_id=' + scopeId : ''}`);
            const status = await statusResp.json();

            if (status.registered) {
                return {
                    success: true,
                    alreadyRegistered: true,
                    leafIndex: status.leaf_index,
                    merkleRoot: status.merkle_root
                };
            }
        }

        // Generate new commitment
        const commitment = await generateVoterCommitment(electionType, scopeId);

        // Register with server
        const response = await fetch('/api/zk/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                election_type: electionType,
                scope_id: scopeId,
                commitment: commitment
            })
        });

        const result = await response.json();

        if (result.success) {
            // Update stored data with leaf index
            const voterData = getVoterData(electionType, scopeId);
            voterData.leafIndex = result.leaf_index;
            voterData.merkleRoot = result.merkle_root;
            localStorage.setItem(`${STORAGE_PREFIX}${electionType}_${scopeId}`, JSON.stringify(voterData));
        }

        return result;

    } catch (error) {
        console.error('Registration error:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Compute nullifier for an election
 * Nullifier = Poseidon(secret, nullifierSecret, electionId)
 */
async function computeNullifier(secret, nullifierSecret, electionId) {
    const hash = await poseidonHash([secret, nullifierSecret, electionId.toString()]);
    return '0x' + BigInt(hash).toString(16).padStart(64, '0');
}

/**
 * Generate ZK proof for anonymous vote
 */
async function generateVoteProof(electionType, electionId, scopeId, candidateId, numCandidates) {
    // Load snarkjs if not available
    if (typeof snarkjs === 'undefined') {
        await loadScript('https://cdn.jsdelivr.net/npm/snarkjs@0.7.0/build/snarkjs.min.js');
    }

    // Get voter data
    const voterData = getVoterData(electionType, scopeId);
    if (!voterData) {
        throw new Error('Not registered for anonymous voting. Please register first.');
    }

    // Get Merkle proof from server
    const proofResp = await fetch('/api/zk/merkle-proof', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            election_type: electionType,
            scope_id: scopeId
        })
    });

    const merkleProof = await proofResp.json();
    if (!merkleProof.success) {
        throw new Error(merkleProof.error || 'Failed to get Merkle proof');
    }

    // Compute nullifier
    const nullifier = await computeNullifier(voterData.secret, voterData.nullifierSecret, electionId);

    // Prepare circuit inputs
    const circuitInputs = {
        // Private inputs (voter's secrets)
        secret: voterData.secret,
        nullifierSecret: voterData.nullifierSecret,
        pathElements: merkleProof.pathElements.map(h => BigInt(h).toString()),
        pathIndices: merkleProof.pathIndices,

        // Public inputs
        merkleRoot: BigInt(merkleProof.merkleRoot).toString(),
        electionId: electionId.toString(),
        candidateId: candidateId.toString(),
        numCandidates: numCandidates.toString(),
        nullifier: BigInt(nullifier).toString()
    };

    console.log('Generating ZK proof...');
    const startTime = Date.now();

    // Generate the proof
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(
        circuitInputs,
        CIRCUIT_WASM,
        CIRCUIT_ZKEY
    );

    console.log(`Proof generated in ${Date.now() - startTime}ms`);

    return {
        proof: proof,
        publicSignals: {
            merkle_root: merkleProof.merkleRoot,
            election_id: electionId,
            candidate_id: candidateId,
            num_candidates: numCandidates,
            nullifier: nullifier
        }
    };
}

/**
 * Cast anonymous vote with ZK proof
 */
async function castAnonymousVote(electionType, electionId, scopeId, candidateId, numCandidates) {
    try {
        // Show loading state
        const statusDiv = document.getElementById('zk-vote-status');
        if (statusDiv) {
            statusDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Generating zero-knowledge proof... This may take a moment.</div>';
        }

        // Generate proof
        const { proof, publicSignals } = await generateVoteProof(
            electionType, electionId, scopeId, candidateId, numCandidates
        );

        if (statusDiv) {
            statusDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Submitting vote to zkVerify blockchain...</div>';
        }

        // Submit vote to server
        const response = await fetch('/api/zk/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                election_type: electionType,
                election_id: electionId,
                proof: proof,
                public_signals: publicSignals
            })
        });

        const result = await response.json();

        if (statusDiv) {
            if (result.success) {
                statusDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle"></i> Vote cast anonymously!
                        <br><small>Your vote has been verified on zkVerify blockchain.</small>
                        ${result.explorer_url ? `<br><a href="${result.explorer_url}" target="_blank" class="text-white"><u>View proof on blockchain</u></a>` : ''}
                    </div>
                `;
            } else {
                statusDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> ${result.error}
                    </div>
                `;
            }
        }

        return result;

    } catch (error) {
        console.error('Vote error:', error);
        const statusDiv = document.getElementById('zk-vote-status');
        if (statusDiv) {
            statusDiv.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i> Error: ${error.message}
                </div>
            `;
        }
        return { success: false, error: error.message };
    }
}

/**
 * Check if user has already voted (via nullifier)
 */
async function checkVotingStatus(electionType, electionId, scopeId) {
    const voterData = getVoterData(electionType, scopeId);
    if (!voterData) {
        return { registered: false, voted: false };
    }

    // We can't check if voted without exposing identity
    // The nullifier prevents double voting on the server side
    return {
        registered: true,
        hasLocalSecrets: true,
        leafIndex: voterData.leafIndex
    };
}

/**
 * Export public key info for transparency
 * This doesn't reveal voter identity, just shows they registered
 */
function getPublicVoterInfo(electionType, scopeId) {
    const voterData = getVoterData(electionType, scopeId);
    if (!voterData) return null;

    return {
        commitment: voterData.commitment,
        registeredAt: voterData.registeredAt
        // Note: leafIndex is NOT included as it could be used to track votes
    };
}

/**
 * Clear voter data (careful - this means losing ability to vote!)
 */
function clearVoterData(electionType, scopeId) {
    const storageKey = `${STORAGE_PREFIX}${electionType}_${scopeId}`;
    localStorage.removeItem(storageKey);
}

// Initialize ZK voting UI
document.addEventListener('DOMContentLoaded', function() {
    // Check for ZK voting elements on page
    const zkVoteContainers = document.querySelectorAll('[data-zk-vote]');

    zkVoteContainers.forEach(container => {
        const electionType = container.dataset.electionType;
        const electionId = container.dataset.electionId;
        const scopeId = container.dataset.scopeId;

        // Add ZK voting status indicator
        const statusIndicator = document.createElement('div');
        statusIndicator.className = 'zk-status-indicator';
        statusIndicator.innerHTML = '<small class="text-muted"><i class="fas fa-shield-alt"></i> Anonymous voting enabled</small>';
        container.prepend(statusIndicator);
    });
});

// Export functions for use in templates
window.ZKVoting = {
    register: registerForZKVoting,
    castVote: castAnonymousVote,
    checkStatus: checkVotingStatus,
    getPublicInfo: getPublicVoterInfo,
    clearData: clearVoterData
};
