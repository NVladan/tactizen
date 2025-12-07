pragma circom 2.0.0;

include "node_modules/circomlib/circuits/poseidon.circom";

// Computes a nullifier for a specific election
// nullifier = Poseidon(secret, nullifierSecret, electionId)
// This ensures each voter can only vote once per election
template Nullifier() {
    // Private inputs
    signal input secret;
    signal input nullifierSecret;

    // Public inputs
    signal input electionId;

    // Public output
    signal output nullifier;

    // Hash to create election-specific nullifier
    component hasher = Poseidon(3);
    hasher.inputs[0] <== secret;
    hasher.inputs[1] <== nullifierSecret;
    hasher.inputs[2] <== electionId;

    nullifier <== hasher.out;
}

component main {public [electionId]} = Nullifier();
