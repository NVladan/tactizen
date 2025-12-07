#!/bin/bash

# zkVerify Anonymous Voting - Circuit Compilation Script
# Run this in WSL: bash compile_circuits.sh

set -e

echo "=========================================="
echo "zkVerify Anonymous Voting Circuit Compiler"
echo "=========================================="

# Check if circom is installed
if ! command -v circom &> /dev/null; then
    echo "Circom not found. Installing..."

    # Install Rust if not present
    if ! command -v cargo &> /dev/null; then
        echo "Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source $HOME/.cargo/env
    fi

    # Install Circom
    echo "Installing Circom..."
    cargo install --git https://github.com/iden3/circom.git
fi

# Check if snarkjs is installed
if ! command -v snarkjs &> /dev/null; then
    echo "Installing snarkjs globally..."
    npm install -g snarkjs
fi

# Install circomlib if not present
if [ ! -d "node_modules/circomlib" ]; then
    echo "Installing circomlib..."
    npm init -y 2>/dev/null || true
    npm install circomlib
fi

# Create output directory
mkdir -p build

echo ""
echo "Step 1: Compiling circuits..."
echo "------------------------------"

# Compile voter_commitment circuit
echo "Compiling voter_commitment.circom..."
circom voter_commitment.circom --r1cs --wasm --sym -o build/

# Compile nullifier circuit
echo "Compiling nullifier.circom..."
circom nullifier.circom --r1cs --wasm --sym -o build/

# Compile main anonymous_vote circuit
echo "Compiling anonymous_vote.circom..."
circom anonymous_vote.circom --r1cs --wasm --sym -o build/

echo ""
echo "Step 2: Generating trusted setup..."
echo "------------------------------------"

# Download powers of tau (if not exists)
if [ ! -f "build/powersOfTau28_hez_final_16.ptau" ]; then
    echo "Downloading powers of tau ceremony file..."
    # Try iden3 source first, then snarkjs backup
    wget -O build/powersOfTau28_hez_final_16.ptau https://storage.googleapis.com/zkevm/ptau/powersOfTau28_hez_final_16.ptau \
    || wget -O build/powersOfTau28_hez_final_16.ptau https://pse-trusted-setup-ppot.s3.eu-central-1.amazonaws.com/pot28_0080/ppot_0080_16.ptau
fi

echo ""
echo "Step 3: Generating proving keys..."
echo "-----------------------------------"

# Generate zkey for voter_commitment
echo "Generating zkey for voter_commitment..."
snarkjs groth16 setup build/voter_commitment.r1cs build/powersOfTau28_hez_final_16.ptau build/voter_commitment_0000.zkey
snarkjs zkey contribute build/voter_commitment_0000.zkey build/voter_commitment.zkey --name="Tactizen contribution" -v -e="random entropy for voter commitment"
snarkjs zkey export verificationkey build/voter_commitment.zkey build/voter_commitment_verification_key.json

# Generate zkey for nullifier
echo "Generating zkey for nullifier..."
snarkjs groth16 setup build/nullifier.r1cs build/powersOfTau28_hez_final_16.ptau build/nullifier_0000.zkey
snarkjs zkey contribute build/nullifier_0000.zkey build/nullifier.zkey --name="Tactizen contribution" -v -e="random entropy for nullifier"
snarkjs zkey export verificationkey build/nullifier.zkey build/nullifier_verification_key.json

# Generate zkey for anonymous_vote
echo "Generating zkey for anonymous_vote..."
snarkjs groth16 setup build/anonymous_vote.r1cs build/powersOfTau28_hez_final_16.ptau build/anonymous_vote_0000.zkey
snarkjs zkey contribute build/anonymous_vote_0000.zkey build/anonymous_vote.zkey --name="Tactizen contribution" -v -e="random entropy for anonymous vote"
snarkjs zkey export verificationkey build/anonymous_vote.zkey build/anonymous_vote_verification_key.json

echo ""
echo "Step 4: Copying artifacts to static folder..."
echo "----------------------------------------------"

# Create static circuits folder
mkdir -p ../app/static/circuits

# Copy WASM files (for browser proof generation)
cp build/voter_commitment_js/voter_commitment.wasm ../app/static/circuits/
cp build/nullifier_js/nullifier.wasm ../app/static/circuits/
cp build/anonymous_vote_js/anonymous_vote.wasm ../app/static/circuits/

# Copy zkey files (for browser proof generation)
cp build/voter_commitment.zkey ../app/static/circuits/
cp build/nullifier.zkey ../app/static/circuits/
cp build/anonymous_vote.zkey ../app/static/circuits/

# Copy verification keys (for backend verification)
cp build/voter_commitment_verification_key.json ../app/static/circuits/
cp build/nullifier_verification_key.json ../app/static/circuits/
cp build/anonymous_vote_verification_key.json ../app/static/circuits/

echo ""
echo "=========================================="
echo "Circuit compilation complete!"
echo "=========================================="
echo ""
echo "Generated files in app/static/circuits/:"
echo "  - voter_commitment.wasm"
echo "  - voter_commitment.zkey"
echo "  - voter_commitment_verification_key.json"
echo "  - nullifier.wasm"
echo "  - nullifier.zkey"
echo "  - nullifier_verification_key.json"
echo "  - anonymous_vote.wasm"
echo "  - anonymous_vote.zkey"
echo "  - anonymous_vote_verification_key.json"
echo ""
echo "You can now use these circuits for anonymous voting!"
