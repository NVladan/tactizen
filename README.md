# Tactizen

A blockchain-powered nation simulation game built with Flask, featuring Web3 wallet authentication, NFT items, economic systems, political parties, resource management, and player-driven governance.

## Features

### Core Gameplay
- **Economic System**: Multi-currency support with resource markets and trading
- **Political System**: Political parties, elections, and democratic governance
- **Resource Management**: Production, trading, and consumption of various resources
- **Military System**: Training, battles, wars, and military units
- **Company Management**: Create and manage production companies
- **Travel System**: Move between countries and regions on a world map

### Web3 Integration
- **MetaMask Authentication**: Sign in with your Ethereum wallet
- **NFT Items**: Collectible items with gameplay bonuses
- **ZEN Token**: In-game currency on Horizen L3 blockchain
- **On-Chain Verification**: Transparent ownership and transactions

### Social Features
- **Friendships**: Connect with other players
- **Newspapers**: Create publications and write articles
- **Military Units**: Form and join military organizations
- **Alliances**: Country-level diplomatic alliances

## Tech Stack

- **Backend**: Flask (Python 3.8+)
- **Database**: MySQL with SQLAlchemy ORM
- **Authentication**: Web3 wallet integration (MetaMask)
- **Blockchain**: Horizen L3 Testnet (EVM-compatible)
- **Smart Contracts**: Solidity (ERC-721 NFTs, ERC-20 tokens)
- **Caching**: Flask-Caching (in-memory or Redis)
- **Rate Limiting**: Flask-Limiter
- **Migrations**: Alembic
- **Scheduler**: APScheduler for background tasks
- **Frontend**: Bootstrap 5, Three.js (world map)

## Prerequisites

- Python 3.8+
- MySQL 5.7+
- Node.js 16+ (for smart contract development)
- pip package manager
- MetaMask browser extension

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tactizen.git
cd tactizen
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install Node.js dependencies (for blockchain development):
```bash
npm install
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. Initialize the database:
```bash
flask db upgrade
```

7. Seed initial game data:
```bash
python seed_countries.py
python seed_neighbors.py
python seed_resources.py
python seed_currency_markets.py
python seed_achievements.py
```

## Running the Application

### Development Mode

```bash
python run.py
```

The application will be available at `http://localhost:5000`

### Production Deployment

For production deployment:
- Use a production WSGI server (Gunicorn recommended)
- Set up Nginx as reverse proxy
- Configure SSL certificates
- Use Redis for caching and rate limiting
- Set `SESSION_COOKIE_SECURE = True`
- Configure proper database backups

See `OPTIMIZATION_ROADMAP.md` for detailed production configuration.

## Project Structure

```
tactizen/
├── app/
│   ├── __init__.py          # App factory
│   ├── models/              # Database models
│   ├── services/            # Business logic services
│   ├── main/                # Main game routes
│   ├── auth/                # Authentication (Web3)
│   ├── admin/               # Admin panel
│   ├── party/               # Political party system
│   ├── government/          # Government & elections
│   ├── military_unit/       # Military units
│   ├── blockchain/          # Web3 & smart contracts
│   ├── routes/              # NFT & marketplace routes
│   ├── static/              # CSS, JS, images
│   └── templates/           # HTML templates
├── contracts/               # Solidity smart contracts
├── migrations/              # Database migrations
├── logs/                    # Application logs
├── config.py                # Configuration
├── run.py                   # Application entry point
└── requirements.txt         # Python dependencies
```

## Smart Contracts

The game uses three main smart contracts on Horizen L3 Testnet:

- **GameNFT.sol**: ERC-721 NFT contract for game items
- **ZENToken.sol**: ERC-20 token for in-game currency (TestZEN)
- **NFTMarketplace.sol**: P2P marketplace for NFT trading

To deploy contracts:
```bash
npx hardhat run contracts/scripts/deploy.js --network horizen
```

## Configuration

Key configuration options in `config.py`:

| Setting | Description |
|---------|-------------|
| `SECRET_KEY` | Flask secret key for sessions |
| `DATABASE_*` | MySQL connection settings |
| `BLOCKCHAIN_RPC_URL` | Horizen L3 RPC endpoint |
| `ZEN_TOKEN_ADDRESS` | Deployed ZEN token contract |
| `NFT_CONTRACT_ADDRESS` | Deployed NFT contract |

## API

The game includes an optional REST API for third-party integrations.
See `API_README.md` for documentation.

## Contributing

Contributions are welcome! Please ensure:
- Code follows existing style conventions
- All tests pass
- Commit messages are clear and descriptive

## Community

- **Twitter/X**: [@TactizenMMO](https://x.com/TactizenMMO)
- **Discord**: [Join our server](https://discord.gg/F4uS9zA53d)

## License

[MIT License](LICENSE)

## Support

For issues or questions, please open an issue on GitHub.
