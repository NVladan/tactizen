pragma circom 2.0.0;

include "node_modules/circomlib/circuits/poseidon.circom";

// Generates a commitment from voter's secret and nullifier secret
// commitment = Poseidon(secret, nullifierSecret)
template VoterCommitment() {
    // Private inputs - only the voter knows these
    signal input secret;           // Voter's private secret (random 256-bit)
    signal input nullifierSecret;  // Used to derive nullifier per election

    // Public output - stored in Merkle tree
    signal output commitment;      // Public commitment

    // Hash the secrets to create commitment
    component hasher = Poseidon(2);
    hasher.inputs[0] <== secret;
    hasher.inputs[1] <== nullifierSecret;

    commitment <== hasher.out;
}

component main = VoterCommitment();
