"""
zkVerify Integration Service

This service handles communication with the zkVerify blockchain
for verifying zero-knowledge proofs used in anonymous voting.

zkVerify is a Substrate-based chain optimized for ZK proof verification,
offering ~91% cost savings compared to Ethereum verification.
"""

import os
import json
import subprocess
import tempfile
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class ZKVerifyService:
    """
    Service for verifying ZK proofs via zkVerify testnet.

    Uses zkverifyjs Node.js package for blockchain interaction.
    """

    def __init__(self):
        self.rpc_ws = os.getenv('ZKVERIFY_RPC_WS', 'wss://zkverify-rpc.zkverify.io')
        self.explorer = os.getenv('ZKVERIFY_EXPLORER', 'https://zkverify.subscan.io/')
        self.use_mainnet = os.getenv('ZKVERIFY_MAINNET', 'true').lower() == 'true'
        self.seed_phrase = os.getenv('ZKVERIFY_SEED_PHRASE')

        # Project root (where node_modules is located)
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # Paths to verification keys
        self.vk_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'static', 'circuits', 'anonymous_vote_verification_key.json'
        )

    def _create_verification_script(
        self,
        proof: Dict[str, Any],
        public_signals: list,
        verification_key: Dict[str, Any]
    ) -> str:
        """
        Create Node.js script for proof verification on zkVerify.
        """
        # Add node_modules path for when script runs from temp directory
        node_modules_path = os.path.join(self.project_root, 'node_modules').replace('\\', '\\\\')

        return f'''
// Add project's node_modules to module search path
module.paths.unshift('{node_modules_path}');

const {{ zkVerifySession, Library, CurveType, ZkVerifyEvents }} = require('zkverifyjs');

async function verifyProof() {{
    let session;
    try {{
        // Start session with zkVerify {'mainnet' if self.use_mainnet else 'testnet'}
        session = await zkVerifySession.start()
            .{'zkVerify' if self.use_mainnet else 'Volta'}()
            .withAccount('{self.seed_phrase}');

        console.log(JSON.stringify({{ status: 'connected' }}));

        // Submit proof for verification
        const {{ events, transactionResult }} = await session.verify()
            .groth16({{
                library: Library.snarkjs,
                curve: CurveType.bn128
            }})
            .execute({{
                proofData: {{
                    vk: {json.dumps(verification_key)},
                    proof: {json.dumps(proof)},
                    publicSignals: {json.dumps(public_signals)}
                }}
            }});

        // Handle transactionResult which is a Promise
        try {{
            const result = await transactionResult;
            console.log(JSON.stringify({{
                success: true,
                txHash: result.txHash || result.blockHash,
                blockNumber: result.blockNumber,
                status: 'verified'
            }}));
        }} catch (txError) {{
            console.log(JSON.stringify({{
                success: false,
                error: txError.message || String(txError)
            }}));
        }}

    }} catch (error) {{
        console.log(JSON.stringify({{
            success: false,
            error: error.message || String(error)
        }}));
    }} finally {{
        if (session) {{
            try {{
                await session.close();
            }} catch (e) {{
                // Ignore close errors
            }}
        }}
    }}
}}

// Handle unhandled rejections
process.on('unhandledRejection', (reason, promise) => {{
    console.log(JSON.stringify({{ success: false, error: String(reason) }}));
    process.exit(1);
}});

verifyProof();
'''

    async def verify_proof(
        self,
        proof: Dict[str, Any],
        public_signals: list,
        verification_key: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
        """
        Verify a Groth16 proof on zkVerify blockchain.

        Args:
            proof: The Groth16 proof object from snarkjs
            public_signals: List of public inputs
            verification_key: Verification key (loads from file if not provided)

        Returns:
            Tuple of (success, tx_hash, block_number, error_message)
        """
        # Load verification key if not provided
        if verification_key is None:
            try:
                with open(self.vk_path, 'r') as f:
                    verification_key = json.load(f)
            except FileNotFoundError:
                return (False, None, None, 'Verification key not found. Compile circuits first.')

        if not self.seed_phrase:
            return (False, None, None, 'ZKVERIFY_SEED_PHRASE not configured')

        # Create verification script
        script = self._create_verification_script(proof, public_signals, verification_key)

        # Execute via Node.js
        result = await self._run_node_script(script)
        return result

    async def _run_node_script(self, script: str) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
        """
        Execute Node.js verification script.

        Returns:
            Tuple of (success, tx_hash, block_number, error_message)
        """
        import asyncio

        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            # Run Node.js script from project root (where node_modules is)
            process = await asyncio.create_subprocess_exec(
                'node', script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=90  # 90 second timeout
            )

            output = stdout.decode().strip()
            errors = stderr.decode().strip()

            # Check for real errors (not just API warnings which go to stderr)
            # Real errors usually have "Error:" or "ERR_" patterns
            has_real_error = errors and (
                'ERR_UNHANDLED_REJECTION' in errors or
                'Error:' in errors or
                'throw err' in errors
            )

            # Parse the last JSON line from output first
            lines = [l for l in output.split('\n') if l.strip().startswith('{')]

            # If no JSON output and there was a real error, report it
            if not lines:
                if has_real_error:
                    # Extract just the error message, not the full stack trace
                    error_lines = [l for l in errors.split('\n') if 'Error' in l or 'error' in l.lower()]
                    error_msg = error_lines[0] if error_lines else errors[:500]
                    return (False, None, None, error_msg)
                return (False, None, None, f'No JSON output: {output[:500]}')

            result = json.loads(lines[-1])

            if result.get('success'):
                return (
                    True,
                    result.get('txHash'),
                    result.get('blockNumber'),
                    None
                )
            else:
                # Include stderr context if there was a real error
                error_msg = result.get('error', 'Unknown error')
                if has_real_error and error_msg == 'Unknown error':
                    error_lines = [l for l in errors.split('\n') if 'Error' in l]
                    if error_lines:
                        error_msg = error_lines[0]
                return (False, None, None, error_msg)

        except asyncio.TimeoutError:
            return (False, None, None, 'Verification timed out')
        except json.JSONDecodeError as e:
            return (False, None, None, f'Invalid JSON response: {e}')
        except Exception as e:
            return (False, None, None, str(e))
        finally:
            # Clean up temp file
            try:
                os.unlink(script_path)
            except:
                pass

    def verify_proof_sync(
        self,
        proof: Dict[str, Any],
        public_signals: list,
        verification_key: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
        """
        Synchronous wrapper for verify_proof.

        Use this from Flask routes that don't support async.
        """
        import asyncio

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.verify_proof(proof, public_signals, verification_key)
        )

    def get_explorer_url(self, tx_hash: str) -> str:
        """Get block explorer URL for a transaction."""
        return f"{self.explorer}extrinsic/{tx_hash}"

    def verify_proof_local(
        self,
        proof: Dict[str, Any],
        public_signals: list,
        verification_key: Dict[str, Any]
    ) -> bool:
        """
        Verify proof locally without blockchain submission.

        Useful for quick validation before submitting to zkVerify.
        Uses snarkjs for local verification.
        """
        # Add node_modules path for when script runs from temp directory
        node_modules_path = os.path.join(self.project_root, 'node_modules').replace('\\', '\\\\')

        script = f'''
// Add project's node_modules to module search path
module.paths.unshift('{node_modules_path}');

const snarkjs = require('snarkjs');

async function verify() {{
    const result = await snarkjs.groth16.verify(
        {json.dumps(verification_key)},
        {json.dumps(public_signals)},
        {json.dumps(proof)}
    );
    console.log(JSON.stringify({{ valid: result }}));
}}

verify().catch(err => console.log(JSON.stringify({{ error: err.message }})));
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                ['node', script_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )

            if result.returncode == 0:
                output = json.loads(result.stdout.strip())
                return output.get('valid', False)
            return False
        except:
            return False
        finally:
            try:
                os.unlink(script_path)
            except:
                pass


# Singleton instance
zkverify_service = ZKVerifyService()


def verify_vote_proof(
    proof: Dict[str, Any],
    merkle_root: str,
    election_id: int,
    candidate_id: int,
    num_candidates: int,
    nullifier: str
) -> Tuple[bool, Optional[str], Optional[int], Optional[str]]:
    """
    Convenience function to verify an anonymous vote proof.

    Args:
        proof: Groth16 proof from snarkjs
        merkle_root: Current Merkle root of voter registry
        election_id: Unique election identifier
        candidate_id: Vote choice (1-N for candidate, 0 for abstain)
        num_candidates: Total number of candidates
        nullifier: Unique nullifier to prevent double voting

    Returns:
        Tuple of (success, tx_hash, block_number, error_message)
    """
    # Construct public signals array matching circuit definition
    # Order must match: [merkleRoot, electionId, candidateId, numCandidates, nullifier]
    public_signals = [
        merkle_root if merkle_root.startswith('0x') else f'0x{merkle_root}',
        str(election_id),
        str(candidate_id),
        str(num_candidates),
        nullifier if nullifier.startswith('0x') else f'0x{nullifier}'
    ]

    return zkverify_service.verify_proof_sync(proof, public_signals)
