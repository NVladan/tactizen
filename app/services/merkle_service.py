"""
Merkle Tree Service for Anonymous Voting

This service manages Merkle trees used for voter registration in ZK voting.
Each voter's commitment is added as a leaf, and they can later prove
membership without revealing which leaf is theirs.

Uses Poseidon hash function (SNARK-friendly) for compatibility with Circom circuits.
"""

from typing import List, Dict, Tuple, Optional
import json
import subprocess
import os


class PoseidonHash:
    """
    Wrapper for circomlib-compatible Poseidon hash.
    Calls Node.js with circomlibjs via subprocess for exact circuit compatibility.
    """

    def __init__(self):
        # Path to the poseidon_node.js script
        self.script_path = os.path.join(
            os.path.dirname(__file__), 'poseidon_node.js'
        )
        # Project root for cwd
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(self.script_path)))
        # Cache for computed hashes to avoid repeated subprocess calls
        self._cache = {}

    def hash(self, inputs: List[int]) -> int:
        """
        Compute Poseidon hash of inputs using circomlibjs via Node.js subprocess.
        """
        # Create cache key
        cache_key = tuple(inputs)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Convert inputs to strings for command line
        str_inputs = [str(x) for x in inputs]

        try:
            result = subprocess.run(
                ['node', self.script_path] + str_inputs,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_root
            )

            if result.returncode != 0:
                raise RuntimeError(f"Poseidon hash failed: {result.stderr}")

            hash_value = int(result.stdout.strip())
            self._cache[cache_key] = hash_value
            return hash_value

        except FileNotFoundError:
            raise RuntimeError(
                "Node.js not found. Please install Node.js to use ZK voting features."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Poseidon hash computation timed out.")

    def hash_batch(self, inputs_list: List[List[int]]) -> List[int]:
        """
        Compute multiple Poseidon hashes in a single subprocess call.
        Much faster than calling hash() multiple times.
        """
        # Check cache for all inputs
        results = []
        uncached_indices = []
        uncached_inputs = []

        for i, inputs in enumerate(inputs_list):
            cache_key = tuple(inputs)
            if cache_key in self._cache:
                results.append(self._cache[cache_key])
            else:
                results.append(None)
                uncached_indices.append(i)
                uncached_inputs.append([str(x) for x in inputs])

        # If all cached, return early
        if not uncached_inputs:
            return results

        # Batch compute uncached hashes
        try:
            batch_input = json.dumps({'hashes': uncached_inputs})
            result = subprocess.run(
                ['node', self.script_path, '--batch'],
                input=batch_input,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )

            if result.returncode != 0:
                raise RuntimeError(f"Poseidon batch hash failed: {result.stderr}")

            batch_result = json.loads(result.stdout)
            hash_values = [int(h) for h in batch_result['results']]

            # Update cache and results
            for idx, hash_val in zip(uncached_indices, hash_values):
                cache_key = tuple(inputs_list[idx])
                self._cache[cache_key] = hash_val
                results[idx] = hash_val

            return results

        except FileNotFoundError:
            raise RuntimeError(
                "Node.js not found. Please install Node.js to use ZK voting features."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Poseidon batch hash computation timed out.")


# Global Poseidon hasher instance
poseidon = PoseidonHash()


class MerkleTreeService:
    """
    Manages Merkle trees for voter registries.

    Each election type + scope (country/party) has its own Merkle tree.
    Voters register by adding their commitment as a leaf.

    Uses a sparse tree approach - only stores actual commitments,
    computes intermediate hashes on-demand.
    """

    # Tree depth - supports up to 2^14 = 16,384 voters per election
    TREE_DEPTH = 14

    def __init__(self):
        # Precompute zero values for empty tree nodes
        self.zero_values = self._compute_zero_values()

    def _compute_zero_values(self) -> List[int]:
        """
        Precompute hash values for empty subtrees at each level.

        Level 0: zero_values[0] = 0 (empty leaf)
        Level 1: zero_values[1] = Poseidon(0, 0)
        Level 2: zero_values[2] = Poseidon(zero_values[1], zero_values[1])
        ...
        """
        zeros = [0]  # Empty leaf value
        for i in range(self.TREE_DEPTH):
            zeros.append(poseidon.hash([zeros[i], zeros[i]]))
        return zeros

    def _hash_pair(self, left: int, right: int) -> int:
        """Hash two child nodes to get parent node."""
        return poseidon.hash([left, right])

    def build_tree(self, commitments: List[int]) -> Dict:
        """
        Build a Merkle tree from voter commitments.

        Uses sparse representation - only stores actual leaves and
        computes the minimum needed intermediate nodes.

        Args:
            commitments: List of voter commitment hashes (leaf values)

        Returns:
            Dictionary containing:
            - root: The Merkle root
            - leaves: Original commitments (not padded)
        """
        if not commitments:
            # Empty tree - return precomputed empty root
            return {
                'root': self.zero_values[self.TREE_DEPTH],
                'leaves': []
            }

        # Compute root by building tree bottom-up
        # Only compute hashes for the path we need
        root = self._compute_root(commitments)

        return {
            'root': root,
            'leaves': commitments
        }

    def _compute_root(self, commitments: List[int]) -> int:
        """Compute Merkle root from commitments."""
        # Start with actual leaves
        current_layer = list(commitments)

        for depth in range(self.TREE_DEPTH):
            # At depth d, we need to produce nodes at level d+1
            # The layer size at level d is 2^(TREE_DEPTH - d)
            # We need to iterate through pairs to produce 2^(TREE_DEPTH - d - 1) nodes
            layer_size = 2 ** (self.TREE_DEPTH - depth)
            next_layer = []

            for i in range(0, layer_size, 2):
                if i < len(current_layer):
                    left = current_layer[i]
                else:
                    left = self.zero_values[depth]

                if i + 1 < len(current_layer):
                    right = current_layer[i + 1]
                else:
                    right = self.zero_values[depth]

                next_layer.append(self._hash_pair(left, right))

            current_layer = next_layer

        return current_layer[0] if current_layer else self.zero_values[self.TREE_DEPTH]

    def get_proof(self, tree_data: Dict, leaf_index: int) -> Tuple[List[int], List[int]]:
        """
        Generate a Merkle proof for a specific leaf.

        Computes the proof on-the-fly from stored leaves (sparse representation).
        Uses precomputed zero subtree hashes for efficiency.

        Args:
            tree_data: Tree data from build_tree()
            leaf_index: Index of the leaf to prove

        Returns:
            Tuple of (pathElements, pathIndices):
            - pathElements: Sibling hashes along the path to root
            - pathIndices: 0 if leaf is on left, 1 if on right at each level
        """
        leaves = tree_data.get('leaves', [])
        path_elements = []
        path_indices = []

        current_index = leaf_index

        for depth in range(self.TREE_DEPTH):
            # Determine if current node is left (0) or right (1) child
            is_right = current_index % 2
            sibling_index = current_index - 1 if is_right else current_index + 1

            # Compute sibling value
            sibling = self._get_node_at(leaves, depth, sibling_index)
            path_elements.append(sibling)
            path_indices.append(is_right)

            current_index //= 2

        return path_elements, path_indices

    def _get_node_at(self, leaves: List[int], depth: int, index: int) -> int:
        """
        Get the value of a node at a specific depth and index.

        The tree structure:
        - depth 0 = leaf level (16384 nodes for TREE_DEPTH=14)
        - depth 13 = root level (1 node)

        For efficiency, computes only the needed path from leaves.
        Uses precomputed zero subtree hashes when possible.

        Note: zero_values[d] = the root of an empty subtree of height d.
        A node at depth d in our tree corresponds to a subtree of height d.
        """
        if depth == 0:
            # Leaf level
            if index < len(leaves):
                return leaves[index]
            else:
                return 0  # Empty leaf = zero_values[0]

        # Check if this entire subtree is empty (beyond actual leaves)
        # At depth d, index i covers leaf indices [i * 2^d, (i+1) * 2^d)
        subtree_start = index * (2 ** depth)

        if subtree_start >= len(leaves):
            # Entire subtree is empty
            # A node at depth d is the root of a subtree of height d
            # So an empty node at depth d = zero_values[d]
            return self.zero_values[depth]

        # Otherwise compute from children
        left_child_idx = index * 2
        right_child_idx = index * 2 + 1

        left = self._get_node_at(leaves, depth - 1, left_child_idx)
        right = self._get_node_at(leaves, depth - 1, right_child_idx)

        return self._hash_pair(left, right)

    def verify_proof(
        self,
        leaf: int,
        root: int,
        path_elements: List[int],
        path_indices: List[int]
    ) -> bool:
        """
        Verify a Merkle proof.

        Args:
            leaf: The leaf value being proved
            root: The expected Merkle root
            path_elements: Sibling hashes from get_proof()
            path_indices: Path direction from get_proof()

        Returns:
            True if proof is valid, False otherwise
        """
        current = leaf

        for i in range(len(path_elements)):
            if path_indices[i]:
                # Current node is right child
                current = self._hash_pair(path_elements[i], current)
            else:
                # Current node is left child
                current = self._hash_pair(current, path_elements[i])

        return current == root

    def add_leaf(self, tree_data: Dict, commitment: int) -> Dict:
        """
        Add a new leaf to an existing tree.

        This rebuilds the tree with the new leaf added.

        Args:
            tree_data: Existing tree data
            commitment: New voter commitment to add

        Returns:
            Updated tree data
        """
        leaves = list(tree_data.get('leaves', []))
        leaves.append(commitment)
        return self.build_tree(leaves)

    def serialize_tree(self, tree_data: Dict) -> Dict:
        """
        Serialize tree data for database storage.

        Uses sparse representation - only stores root and leaves.
        Converts integers to hex strings for JSON compatibility.
        """
        return {
            'root': hex(tree_data['root']),
            'leaves': [hex(l) for l in tree_data['leaves']]
        }

    def deserialize_tree(self, serialized: Dict) -> Dict:
        """
        Deserialize tree data from database.

        Converts hex strings back to integers.
        """
        return {
            'root': int(serialized['root'], 16),
            'leaves': [int(l, 16) for l in serialized['leaves']]
        }

    def serialize_proof(self, path_elements: List[int], path_indices: List[int]) -> Dict:
        """Serialize Merkle proof for frontend."""
        return {
            'pathElements': [hex(e) for e in path_elements],
            'pathIndices': path_indices
        }


# Singleton instance
merkle_service = MerkleTreeService()


def get_or_create_tree(election_type: str, scope_id: int):
    """
    Get existing Merkle tree or create a new empty one.

    Args:
        election_type: 'presidential', 'congressional', or 'party'
        scope_id: country_id or party_id

    Returns:
        MerkleTree database model instance
    """
    from app.models import MerkleTree, db

    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree:
        # Create empty tree
        empty_tree = merkle_service.build_tree([])
        tree = MerkleTree(
            election_type=election_type,
            scope_id=scope_id,
            root=hex(empty_tree['root']),
            num_leaves=0,
            tree_data=merkle_service.serialize_tree(empty_tree)
        )
        db.session.add(tree)
        db.session.commit()

    return tree


def add_voter_to_tree(election_type: str, scope_id: int, commitment: str) -> Tuple[int, str]:
    """
    Add a voter's commitment to the Merkle tree.

    Args:
        election_type: 'presidential', 'congressional', or 'party'
        scope_id: country_id or party_id
        commitment: Hex string of voter's commitment hash

    Returns:
        Tuple of (leaf_index, new_merkle_root)
    """
    from app.models import MerkleTree, db

    tree = get_or_create_tree(election_type, scope_id)

    # Deserialize existing tree
    tree_data = merkle_service.deserialize_tree(tree.tree_data)

    # Add new commitment
    commitment_int = int(commitment, 16)
    leaf_index = len(tree_data['leaves'])
    new_tree_data = merkle_service.add_leaf(tree_data, commitment_int)

    # Update database
    tree.root = hex(new_tree_data['root'])
    tree.num_leaves = len(new_tree_data['leaves'])
    tree.tree_data = merkle_service.serialize_tree(new_tree_data)

    db.session.commit()

    return leaf_index, tree.root


def get_merkle_proof(election_type: str, scope_id: int, leaf_index: int) -> Optional[Dict]:
    """
    Get Merkle proof for a voter's commitment.

    Args:
        election_type: 'presidential', 'congressional', or 'party'
        scope_id: country_id or party_id
        leaf_index: Voter's leaf index in the tree

    Returns:
        Dictionary with pathElements and pathIndices, or None if not found
    """
    from app.models import MerkleTree

    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree or leaf_index >= tree.num_leaves:
        return None

    tree_data = merkle_service.deserialize_tree(tree.tree_data)
    path_elements, path_indices = merkle_service.get_proof(tree_data, leaf_index)

    return {
        'merkleRoot': tree.root,
        'pathElements': [hex(e) for e in path_elements],
        'pathIndices': path_indices,
        'leafIndex': leaf_index
    }
