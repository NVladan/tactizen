/**
 * Simple HTTP server for Poseidon hash computation
 * Keeps circomlibjs loaded in memory for fast hashing
 */

const http = require('http');
const { buildPoseidon } = require('circomlibjs');

const PORT = 3999;
let poseidon = null;

async function init() {
    console.log('Building Poseidon...');
    poseidon = await buildPoseidon();
    console.log('Poseidon ready!');
}

const server = http.createServer(async (req, res) => {
    if (req.method === 'POST' && req.url === '/hash') {
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', () => {
            try {
                const { inputs } = JSON.parse(body);
                const bigIntInputs = inputs.map(x => BigInt(x));
                const hash = poseidon(bigIntInputs);
                const result = poseidon.F.toString(hash);

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ hash: result }));
            } catch (err) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: err.message }));
            }
        });
    } else {
        res.writeHead(404);
        res.end('Not found');
    }
});

init().then(() => {
    server.listen(PORT, '127.0.0.1', () => {
        console.log(`Poseidon server running on http://127.0.0.1:${PORT}`);
    });
});
