/**
 * Node.js script for computing Poseidon hash using circomlibjs
 * Called from Python for hash compatibility with Circom circuits
 *
 * Usage:
 *   Single hash:  node poseidon_node.js 123 456
 *   Batch mode:   node poseidon_node.js --batch < input.json
 *                 Input JSON: {"hashes": [["0", "0"], ["1", "2"]]}
 *                 Output JSON: {"results": ["hash1", "hash2"]}
 */

const path = require('path');
const projectRoot = path.resolve(__dirname, '..', '..', '..');
module.paths.unshift(path.join(projectRoot, 'node_modules'));

const { buildPoseidon } = require('circomlibjs');

let poseidonInstance = null;

async function getPoseidon() {
    if (!poseidonInstance) {
        poseidonInstance = await buildPoseidon();
    }
    return poseidonInstance;
}

async function computeHash(poseidon, inputs) {
    const bigIntInputs = inputs.map(x => BigInt(x));
    const hash = poseidon(bigIntInputs);
    return poseidon.F.toString(hash);
}

async function main() {
    const args = process.argv.slice(2);

    if (args.length === 0) {
        console.error('Usage: node poseidon_node.js <input1> <input2> ...');
        console.error('       node poseidon_node.js --batch < input.json');
        process.exit(1);
    }

    const poseidon = await getPoseidon();

    // Batch mode - read JSON from stdin
    if (args[0] === '--batch') {
        let input = '';
        for await (const chunk of process.stdin) {
            input += chunk;
        }

        const data = JSON.parse(input);
        const results = [];

        for (const hashInputs of data.hashes) {
            results.push(await computeHash(poseidon, hashInputs));
        }

        console.log(JSON.stringify({ results }));
    } else {
        // Single hash mode
        const result = await computeHash(poseidon, args);
        console.log(result);
    }
}

main().catch(err => {
    console.error(err.message);
    process.exit(1);
});
