pragma circom 2.0.0;

include "node_modules/circomlib/circuits/poseidon.circom";
include "node_modules/circomlib/circuits/mux1.circom";
include "node_modules/circomlib/circuits/comparators.circom";
include "node_modules/circomlib/circuits/bitify.circom";

// Merkle tree inclusion proof using Poseidon hash
template MerkleProof(levels) {
    signal input leaf;
    signal input pathElements[levels];
    signal input pathIndices[levels];
    signal output root;

    component hashers[levels];
    component mux[levels][2];

    signal levelHashes[levels + 1];
    levelHashes[0] <== leaf;

    for (var i = 0; i < levels; i++) {
        // Determine left and right inputs based on path index
        mux[i][0] = Mux1();
        mux[i][0].c[0] <== levelHashes[i];
        mux[i][0].c[1] <== pathElements[i];
        mux[i][0].s <== pathIndices[i];

        mux[i][1] = Mux1();
        mux[i][1].c[0] <== pathElements[i];
        mux[i][1].c[1] <== levelHashes[i];
        mux[i][1].s <== pathIndices[i];

        // Hash the pair
        hashers[i] = Poseidon(2);
        hashers[i].inputs[0] <== mux[i][0].out;
        hashers[i].inputs[1] <== mux[i][1].out;

        levelHashes[i + 1] <== hashers[i].out;
    }

    root <== levelHashes[levels];
}

// Main anonymous voting circuit for multi-candidate elections
// Proves: "I am a registered voter and I'm voting for candidate X"
// Without revealing: "Which registered voter I am"
template AnonymousVote(merkleDepth, maxCandidates) {
    // ========== Private Inputs (only voter knows) ==========
    signal input secret;                          // Voter's secret
    signal input nullifierSecret;                 // Nullifier derivation secret
    signal input pathElements[merkleDepth];       // Merkle proof path
    signal input pathIndices[merkleDepth];        // Merkle proof indices (0 or 1)

    // ========== Public Inputs (visible to everyone) ==========
    signal input merkleRoot;          // Current voter registry root
    signal input electionId;          // Unique election identifier
    signal input candidateId;         // Which candidate (1 to maxCandidates), 0 = abstain
    signal input numCandidates;       // Total candidates in this election
    signal input nullifier;           // Prevents double voting

    // ========== Verify candidateId is valid ==========
    // candidateId must be >= 0 and <= numCandidates
    component gteMinus1 = GreaterEqThan(8);
    gteMinus1.in[0] <== candidateId;
    gteMinus1.in[1] <== 0;
    gteMinus1.out === 1;

    component lteMax = LessEqThan(8);
    lteMax.in[0] <== candidateId;
    lteMax.in[1] <== numCandidates;
    lteMax.out === 1;

    // ========== Compute voter's commitment ==========
    component commitmentHasher = Poseidon(2);
    commitmentHasher.inputs[0] <== secret;
    commitmentHasher.inputs[1] <== nullifierSecret;

    // ========== Verify Merkle proof (voter is registered) ==========
    component merkleProof = MerkleProof(merkleDepth);
    merkleProof.leaf <== commitmentHasher.out;
    for (var i = 0; i < merkleDepth; i++) {
        merkleProof.pathElements[i] <== pathElements[i];
        merkleProof.pathIndices[i] <== pathIndices[i];
    }

    // Verify the computed root matches the public root
    merkleRoot === merkleProof.root;

    // ========== Compute and verify nullifier ==========
    // nullifier = Poseidon(secret, nullifierSecret, electionId)
    component nullifierHasher = Poseidon(3);
    nullifierHasher.inputs[0] <== secret;
    nullifierHasher.inputs[1] <== nullifierSecret;
    nullifierHasher.inputs[2] <== electionId;

    // Verify the provided nullifier matches
    nullifier === nullifierHasher.out;
}

// Merkle tree depth of 14 supports up to 16,384 voters per election
// Max 50 candidates per election
component main {public [merkleRoot, electionId, candidateId, numCandidates, nullifier]} = AnonymousVote(14, 50);
