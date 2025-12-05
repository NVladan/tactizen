// NFT Marketplace JavaScript
// Handles listing, buying, and canceling NFT marketplace listings

let web3;
let marketplaceContract;
let nftContract;
let userAccount;
let currentUserId = null;

const MARKETPLACE_CONTRACT_ADDRESS = '0x8668466ae57Fc64799B1321eA592Cd8ae24c3Ee9';
const NFT_CONTRACT_ADDRESS = '0x57e277b2d887C3C749757e36F0B6CFad32E00e8A';  // Tactizen Game NFT
const ZEN_TOKEN_ADDRESS = '0x070040A826B586b58569750ED43cb5979b171e8d';

// Category names mapping
const CATEGORY_NAMES = {
    'combat_boost': 'Combat Boost',
    'energy_regen': 'Energy Regen',
    'wellness_regen': 'Wellness Regen',
    'military_tutor': 'Military Tutor',
    'travel_discount': 'Travel Discount',
    'storage_increase': 'Storage Increase',
    'production_boost': 'Production Boost',
    'material_efficiency': 'Material Efficiency',
    'upgrade_discount': 'Upgrade Discount',
    'speed_boost': 'Speed Boost',
    'android_worker': 'Android Worker',
    'tax_breaks': 'Tax Breaks'
};

const TIER_NAMES = {
    1: 'Q1 Common',
    2: 'Q2 Uncommon',
    3: 'Q3 Rare',
    4: 'Q4 Epic',
    5: 'Q5 Legendary'
};

// Helper function to clean up modal backdrops
function cleanupModalBackdrops() {
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => backdrop.remove());
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
    document.body.style.removeProperty('pointer-events');
    document.body.style.removeProperty('position');
    document.body.style.removeProperty('top');
    document.body.style.removeProperty('width');
    document.body.style.overflow = '';
    document.body.style.pointerEvents = 'auto';
    document.documentElement.style.overflow = '';
    document.documentElement.style.overflowY = 'auto';
}

// Modal helper functions
function showSuccess(message) {
    const modalEl = document.getElementById('successModal');
    document.getElementById('successMessage').textContent = message;

    // Clean up any existing modal
    const existingModal = bootstrap.Modal.getInstance(modalEl);
    if (existingModal) {
        existingModal.dispose();
    }
    cleanupModalBackdrops();

    const modal = new bootstrap.Modal(modalEl);
    modal.show();

    // Add cleanup handler
    modalEl.addEventListener('hidden.bs.modal', function() {
        cleanupModalBackdrops();
        const instance = bootstrap.Modal.getInstance(modalEl);
        if (instance) instance.dispose();
        setTimeout(() => cleanupModalBackdrops(), 100);
        setTimeout(() => cleanupModalBackdrops(), 300);
    }, { once: true });
}

function showError(message) {
    const modalEl = document.getElementById('errorModal');
    document.getElementById('errorMessage').textContent = message;

    // Clean up any existing modal
    const existingModal = bootstrap.Modal.getInstance(modalEl);
    if (existingModal) {
        existingModal.dispose();
    }
    cleanupModalBackdrops();

    const modal = new bootstrap.Modal(modalEl);
    modal.show();

    // Add cleanup handler
    modalEl.addEventListener('hidden.bs.modal', function() {
        cleanupModalBackdrops();
        const instance = bootstrap.Modal.getInstance(modalEl);
        if (instance) instance.dispose();
        setTimeout(() => cleanupModalBackdrops(), 100);
        setTimeout(() => cleanupModalBackdrops(), 300);
    }, { once: true });
}

function showInfo(message) {
    const modalEl = document.getElementById('infoModal');
    document.getElementById('infoMessage').textContent = message;

    // Clean up any existing modal
    const existingModal = bootstrap.Modal.getInstance(modalEl);
    if (existingModal) {
        existingModal.dispose();
    }
    cleanupModalBackdrops();

    const modal = new bootstrap.Modal(modalEl);
    modal.show();

    // Add cleanup handler
    modalEl.addEventListener('hidden.bs.modal', function() {
        cleanupModalBackdrops();
        const instance = bootstrap.Modal.getInstance(modalEl);
        if (instance) instance.dispose();
        setTimeout(() => cleanupModalBackdrops(), 100);
        setTimeout(() => cleanupModalBackdrops(), 300);
    }, { once: true });
}

// Initialize Web3
async function initWeb3() {
    if (typeof window.ethereum !== 'undefined') {
        web3 = new Web3(window.ethereum);
        try {
            const accounts = await ethereum.request({ method: 'eth_requestAccounts' });
            userAccount = accounts[0];
            console.log('Connected to MetaMask:', userAccount);
            return true;
        } catch (error) {
            console.error('User denied account access');
            return false;
        }
    } else {
        showError('Please install MetaMask to use the marketplace!');
        return false;
    }
}

// Load marketplace info
async function loadMarketplaceInfo() {
    try {
        const response = await fetch('/nft-marketplace/api/marketplace-info');
        const data = await response.json();

        if (data.success) {
            document.getElementById('marketplaceFee').textContent = `${data.marketplace_fee_percent}%`;
            document.getElementById('feePercent').textContent = data.marketplace_fee_percent;
        }
    } catch (error) {
        console.error('Error loading marketplace info:', error);
    }
}

// Load and display marketplace listings
async function loadListings() {
    try {
        document.getElementById('loadingSpinner').style.display = 'block';
        document.getElementById('listingsContainer').style.display = 'none';
        document.getElementById('noListings').style.display = 'none';

        // Build query params from filters
        const params = new URLSearchParams();

        const type = document.getElementById('filterType').value;
        const category = document.getElementById('filterCategory').value;
        const minTier = document.getElementById('filterMinTier').value;
        const maxTier = document.getElementById('filterMaxTier').value;
        const minPrice = document.getElementById('filterMinPrice').value;
        const maxPrice = document.getElementById('filterMaxPrice').value;
        const sortBy = document.getElementById('sortBy').value;

        if (type) params.append('nft_type', type);
        if (category) params.append('category', category);
        if (minTier) params.append('min_tier', minTier);
        if (maxTier) params.append('max_tier', maxTier);
        if (minPrice) params.append('min_price', minPrice);
        if (maxPrice) params.append('max_price', maxPrice);
        if (sortBy) params.append('sort_by', sortBy);

        const response = await fetch(`/nft-marketplace/api/listings?${params}`);
        const data = await response.json();

        document.getElementById('loadingSpinner').style.display = 'none';

        if (data.success && data.listings.length > 0) {
            currentUserId = data.current_user_id;
            displayListings(data.listings);
        } else {
            document.getElementById('noListings').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading listings:', error);
        document.getElementById('loadingSpinner').style.display = 'none';
        showError('Failed to load marketplace listings. Please try again.');
    }
}

// Display listings in the grid
function displayListings(listings) {
    const container = document.getElementById('listingsContainer');
    container.innerHTML = '';
    container.style.display = 'flex';

    listings.forEach(listing => {
        const nft = listing.nft;
        const card = createListingCard(listing, nft);
        container.appendChild(card);
    });
}

// Create a listing card
function createListingCard(listing, nft) {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6 mb-4';

    const tierClass = `tier-${nft.tier}`;
    const typeIcon = nft.nft_type === 'player' ? 'fa-user' : 'fa-building';
    const typeLabel = nft.nft_type === 'player' ? 'Player NFT' : 'Company NFT';
    const isOwnListing = listing.seller_id === currentUserId;

    col.innerHTML = `
        <div class="nft-card h-100" style="overflow: hidden;">
            <!-- NFT Image Header -->
            <div style="position: relative; background: linear-gradient(135deg, #0a0e1a 0%, #1a1f2e 100%); padding: 1.5rem; border-bottom: 1px solid rgba(34, 197, 94, 0.2);">
                <!-- Tier Badge - Absolute positioned -->
                <div class="nft-tier-badge ${tierClass}" style="position: absolute; top: 12px; right: 12px; padding: 0.4rem 0.8rem; font-size: 0.75rem; z-index: 10;">
                    <i class="fas fa-star me-1"></i>${TIER_NAMES[nft.tier]}
                </div>

                <!-- NFT Image - Centered -->
                ${nft.image_url ? `
                    <div style="text-align: center;">
                        <img src="${nft.image_url}"
                             alt="${nft.name}"
                             class="nft-card-image"
                             style="width: 140px; height: 240px; object-fit: cover; border-radius: 12px;
                                    border: 2px solid rgba(34, 197, 94, 0.3); background: #0a0e1a;
                                    transition: all 0.3s ease; cursor: pointer; display: inline-block;"
                             onerror="this.style.display='none'">
                    </div>
                ` : ''}
            </div>

            <!-- Card Content -->
            <div class="card-body" style="padding: 1.25rem;">
                <!-- Title -->
                <h5 class="text-white mb-2" style="font-size: 1.1rem; font-weight: 700; line-height: 1.3;">
                    ${nft.name}
                </h5>

                <!-- Type & Category Badges -->
                <div class="d-flex gap-2 mb-3 flex-wrap">
                    <span class="badge" style="background: rgba(100, 116, 139, 0.2); color: #94a3b8; font-size: 0.7rem; padding: 0.3rem 0.6rem;">
                        <i class="fas ${typeIcon} me-1"></i>${typeLabel}
                    </span>
                    <span class="badge" style="background: rgba(100, 116, 139, 0.15); color: #cbd5e1; font-size: 0.7rem; padding: 0.3rem 0.6rem;">
                        ${CATEGORY_NAMES[nft.category]}
                    </span>
                </div>

                <!-- Description -->
                <p class="text-muted mb-3" style="font-size: 0.85rem; line-height: 1.4; max-height: 60px; overflow: hidden; text-overflow: ellipsis;">
                    ${nft.description || 'A powerful NFT that enhances your gameplay.'}
                </p>

                <!-- Bonus -->
                <div class="d-flex align-items-center justify-content-center px-2 py-2 rounded mb-3" style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(34, 197, 94, 0.05)); border: 1.5px solid rgba(34, 197, 94, 0.4);">
                    <i class="fas fa-bolt text-success me-2"></i>
                    <span class="text-success" style="font-size: 0.95rem; font-weight: 700;">
                        +${nft.bonus_value}% Bonus
                    </span>
                </div>

                <!-- Divider -->
                <hr style="border-color: rgba(34, 197, 94, 0.2); margin: 1rem 0;">

                <!-- Seller -->
                <div class="mb-3">
                    <small class="text-muted d-block mb-1" style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px;">Seller</small>
                    <div class="text-white" style="font-size: 0.9rem; font-weight: 600;">
                        ${listing.seller_username}${isOwnListing ? ' <span class="badge bg-info ms-1">You</span>' : ''}
                    </div>
                </div>

                <!-- Price -->
                <div class="mb-3">
                    <small class="text-muted d-block mb-1" style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px;">Price</small>
                    <div class="text-warning" style="font-size: 1.6rem; font-weight: 800; line-height: 1;">
                        <i class="fas fa-coins me-1"></i>${parseFloat(listing.price_zen).toFixed(2)} <span style="font-size: 0.9rem;">ZEN</span>
                    </div>
                </div>

                <!-- Action Button - Buy or Cancel depending on ownership -->
                ${isOwnListing ? `
                    <button class="btn btn-cancel w-100" onclick="cancelListing(${listing.id}, ${nft.token_id})" style="padding: 0.75rem; font-size: 0.95rem; font-weight: 600;">
                        <i class="fas fa-times me-2"></i>Remove from Sale
                    </button>
                ` : `
                    <button class="btn btn-buy w-100" onclick="buyNFT(${listing.id}, ${nft.token_id}, ${listing.price_zen})" style="padding: 0.75rem; font-size: 0.95rem; font-weight: 600;">
                        <i class="fas fa-shopping-cart me-2"></i>Buy Now
                    </button>
                `}

                <!-- Token ID -->
                <div class="mt-2 text-center">
                    <small class="text-muted" style="font-size: 0.65rem; opacity: 0.5;">
                        Token #${nft.token_id}
                    </small>
                </div>
            </div>
        </div>
    `;

    return col;
}

// Buy NFT
async function buyNFT(listingId, tokenId, priceZen) {
    if (!web3) {
        const connected = await initWeb3();
        if (!connected) return;
    }

    try {
        // Show loading
        showInfo('Please approve the ZEN token spending, then confirm the purchase transaction in MetaMask.');

        // Convert price to wei
        const priceWei = web3.utils.toWei(priceZen.toString(), 'ether');

        // First approve ZEN spending
        const zenContract = new web3.eth.Contract([
            {
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ], ZEN_TOKEN_ADDRESS);

        console.log('Approving ZEN spending...');
        const approvalTx = await zenContract.methods.approve(MARKETPLACE_CONTRACT_ADDRESS, priceWei)
            .send({
                from: userAccount,
                gas: 100000  // Reasonable gas limit for ERC20 approve
            });

        console.log('ZEN approved, tx hash:', approvalTx.transactionHash);

        // Wait a moment for the approval to propagate
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Then call buyNFT on marketplace
        marketplaceContract = new web3.eth.Contract([
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "buyNFT",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ], MARKETPLACE_CONTRACT_ADDRESS);

        const tx = await marketplaceContract.methods.buyNFT(tokenId)
            .send({
                from: userAccount,
                gas: 400000  // Reasonable gas limit for buying (transfer NFT + ZEN)
            });

        // Send transaction hash to backend for verification
        const response = await fetch('/nft-marketplace/api/buy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                listing_id: listingId,
                tx_hash: tx.transactionHash
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('NFT purchased successfully! Check your NFT inventory.');
            loadListings(); // Refresh listings
        } else {
            showError('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error buying NFT:', error);

        // Handle user rejection
        if (error.message && error.message.includes('User denied')) {
            showInfo('Purchase cancelled. You need to approve both the ZEN spending and purchase transactions.');
        } else {
            showError('Failed to buy NFT: ' + error.message);
        }
    }
}

// Load user's NFTs for listing
async function loadMyNFTs() {
    try {
        document.getElementById('myNFTsLoading').style.display = 'block';
        document.getElementById('myNFTsContainer').style.display = 'none';

        const response = await fetch('/api/nft/inventory');
        const data = await response.json();

        document.getElementById('myNFTsLoading').style.display = 'none';
        document.getElementById('myNFTsContainer').style.display = 'block';

        if (data.success && data.nfts.length > 0) {
            displayMyNFTs(data.nfts.filter(nft => !nft.is_equipped));
        } else {
            document.getElementById('myNFTsList').innerHTML =
                '<div class="col-12 text-center"><p class="text-muted">No NFTs available to list</p></div>';
        }
    } catch (error) {
        console.error('Error loading NFTs:', error);
        showError('Failed to load your NFTs. Please try again.');
    }
}

// Display user's NFTs
function displayMyNFTs(nfts) {
    const container = document.getElementById('myNFTsList');
    const emptyState = document.getElementById('myNFTsEmpty');
    container.innerHTML = '';

    if (nfts.length === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    container.style.display = 'flex';
    emptyState.style.display = 'none';

    nfts.forEach(nft => {
        const col = document.createElement('div');
        col.className = 'col';

        const tierClass = `tier-${nft.tier}`;
        const typeIcon = nft.nft_type === 'player' ? 'fa-user' : 'fa-building';

        col.innerHTML = `
            <div class="nft-card h-100">
                <div class="card-body position-relative d-flex flex-column">
                    <i class="fas ${typeIcon} nft-type-icon"></i>
                    <div class="nft-tier-badge ${tierClass}">
                        ${TIER_NAMES[nft.tier]}
                    </div>
                    ${nft.image_url ? `
                        <img src="${nft.image_url}"
                             alt="${nft.name}"
                             class="nft-card-image"
                             style="width: 90px; height: 160px; object-fit: cover; border-radius: 8px;
                                    border: 2px solid rgba(34, 197, 94, 0.3); background: #0a0e1a;
                                    display: block; margin: 1rem auto 0; transition: all 0.3s ease; cursor: pointer;"
                             onerror="this.style.display='none'"
                             onclick="window.open('https://horizen-testnet.explorer.caldera.xyz/token/${nft.contract_address}?a=${nft.token_id}', '_blank'); event.stopPropagation();"
                             title="View on Horizen Explorer (click) or hover to zoom">
                    ` : ''}
                    <h6 class="card-title mt-3 mb-1">${nft.name}</h6>
                    <p class="text-muted small mb-2">${CATEGORY_NAMES[nft.category]}</p>
                    <p class="text-success mb-3">
                        <i class="fas fa-bolt"></i> +${nft.bonus_value}%
                    </p>
                    <button class="btn btn-primary w-100 mt-auto" onclick="showPriceModal(${nft.id}, ${nft.token_id})">
                        <i class="fas fa-tag me-1"></i> Set Price
                    </button>
                </div>
            </div>
        `;

        container.appendChild(col);
    });
}

// Show price setting modal
function showPriceModal(nftId, tokenId) {
    document.getElementById('selectedNFTId').value = nftId;
    document.getElementById('listingPrice').value = '';
    document.getElementById('feeCalculation').style.display = 'none';

    const listModal = bootstrap.Modal.getInstance(document.getElementById('listNFTModal'));
    listModal.hide();

    const priceModal = new bootstrap.Modal(document.getElementById('setPriceModal'));
    priceModal.show();
}

// Calculate and display fee
document.getElementById('listingPrice')?.addEventListener('input', async function() {
    const price = parseFloat(this.value);

    if (price > 0) {
        try {
            const response = await fetch('/nft-marketplace/api/calculate-fee', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ price_zen: price })
            });

            const data = await response.json();

            if (data.success) {
                document.getElementById('displayPrice').textContent = data.price_zen.toFixed(2);
                document.getElementById('displayFee').textContent = data.fee_zen.toFixed(2);
                document.getElementById('displaySellerAmount').textContent = data.seller_receives_zen.toFixed(2);
                document.getElementById('feeCalculation').style.display = 'block';
            }
        } catch (error) {
            console.error('Error calculating fee:', error);
        }
    } else {
        document.getElementById('feeCalculation').style.display = 'none';
    }
});

// List NFT on marketplace
document.getElementById('confirmListingBtn')?.addEventListener('click', async function() {
    const nftId = parseInt(document.getElementById('selectedNFTId').value);
    const price = parseFloat(document.getElementById('listingPrice').value);

    if (!price || price <= 0) {
        showError('Please enter a valid price greater than 0');
        return;
    }

    if (!web3) {
        const connected = await initWeb3();
        if (!connected) return;
    }

    try {
        // Show loading
        this.disabled = true;
        this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Listing...';

        // Get NFT details from backend
        const nftResponse = await fetch(`/api/nft/inventory`);
        const nftData = await nftResponse.json();
        const nft = nftData.nfts.find(n => n.id === nftId);

        if (!nft) {
            throw new Error('NFT not found');
        }

        // Convert price to wei
        const priceWei = web3.utils.toWei(price.toString(), 'ether');
        console.log(`Listing NFT ${nft.token_id} for ${price} ZEN (${priceWei} wei)`);

        // Check if NFT is already listed on blockchain and cancel if needed
        marketplaceContract = new web3.eth.Contract([
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "getListing",
                "outputs": [
                    {"name": "seller", "type": "address"},
                    {"name": "price", "type": "uint256"},
                    {"name": "active", "type": "bool"},
                    {"name": "listedAt", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "cancelListing",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ], MARKETPLACE_CONTRACT_ADDRESS);

        const existingListing = await marketplaceContract.methods.getListing(nft.token_id).call();

        if (existingListing.active && existingListing.seller.toLowerCase() === userAccount.toLowerCase()) {
            console.log('Found existing active listing, cancelling first...');
            showInfo('Cancelling previous listing first. Please confirm the transaction.');

            const cancelTx = await marketplaceContract.methods.cancelListing(nft.token_id)
                .send({
                    from: userAccount,
                    gas: 300000
                });

            console.log('Previous listing cancelled:', cancelTx.transactionHash);
            await new Promise(resolve => setTimeout(resolve, 2000));
        }

        // Check if marketplace is already approved to transfer NFTs
        nftContract = new web3.eth.Contract([
            {
                "inputs": [
                    {"name": "operator", "type": "address"},
                    {"name": "approved", "type": "bool"}
                ],
                "name": "setApprovalForAll",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "operator", "type": "address"}
                ],
                "name": "isApprovedForAll",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            }
        ], NFT_CONTRACT_ADDRESS);

        // Check if already approved
        const isApproved = await nftContract.methods.isApprovedForAll(userAccount, MARKETPLACE_CONTRACT_ADDRESS).call();

        if (!isApproved) {
            console.log('Setting approval for marketplace...');
            const approvalTx = await nftContract.methods.setApprovalForAll(MARKETPLACE_CONTRACT_ADDRESS, true)
                .send({
                    from: userAccount,
                    gas: 50000  // Gas limit for setApprovalForAll
                });

            console.log('Approval set, tx hash:', approvalTx.transactionHash);

            // Wait a moment for the approval to propagate
            await new Promise(resolve => setTimeout(resolve, 2000));
        } else {
            console.log('Marketplace already approved, skipping approval step');
        }

        // Then call listNFT on marketplace
        marketplaceContract = new web3.eth.Contract([
            {
                "inputs": [
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "price", "type": "uint256"}
                ],
                "name": "listNFT",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ], MARKETPLACE_CONTRACT_ADDRESS);

        const tx = await marketplaceContract.methods.listNFT(nft.token_id, priceWei)
            .send({
                from: userAccount,
                gas: 150000  // Gas limit for listing (transfer NFT to escrow)
            });

        // Send transaction hash to backend for verification
        const response = await fetch('/nft-marketplace/api/list', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                nft_id: nftId,
                price_zen: price,
                tx_hash: tx.transactionHash
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('NFT listed successfully! It is now available for purchase.');
            const modal = bootstrap.Modal.getInstance(document.getElementById('setPriceModal'));
            modal.hide();
            loadListings(); // Refresh listings
        } else {
            showError('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error listing NFT:', error);

        // Handle user rejection
        if (error.message && error.message.includes('User denied')) {
            showInfo('Transaction cancelled. You need to approve both transactions to list your NFT.');
        } else {
            showError('Failed to list NFT: ' + error.message);
        }
    } finally {
        this.disabled = false;
        this.innerHTML = '<i class="fas fa-check"></i> List NFT';
    }
});

// Load user's active listings
async function loadMyListings() {
    try {
        document.getElementById('myListingsLoading').style.display = 'block';
        document.getElementById('myListingsContainer').style.display = 'none';

        const response = await fetch('/nft-marketplace/api/my-listings');
        const data = await response.json();

        document.getElementById('myListingsLoading').style.display = 'none';
        document.getElementById('myListingsContainer').style.display = 'block';

        if (data.success && data.listings.length > 0) {
            displayMyListings(data.listings);
        } else {
            document.getElementById('myListingsContainer').innerHTML =
                '<div class="text-center"><p class="text-muted">You have no active listings</p></div>';
        }
    } catch (error) {
        console.error('Error loading my listings:', error);
        showError('Failed to load your listings. Please try again.');
    }
}

// Display user's listings
function displayMyListings(listings) {
    const container = document.getElementById('myListingsContainer');
    const emptyState = document.getElementById('myListingsEmpty');

    if (listings.length === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    container.style.display = 'block';
    emptyState.style.display = 'none';
    container.innerHTML = '<div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3"></div>';
    const row = container.querySelector('.row');

    listings.forEach(listing => {
        const nft = listing.nft;
        const col = document.createElement('div');
        col.className = 'col';

        const tierClass = `tier-${nft.tier}`;
        const typeIcon = nft.nft_type === 'player' ? 'fa-user' : 'fa-building';

        col.innerHTML = `
            <div class="nft-card h-100">
                <div class="card-body position-relative d-flex flex-column">
                    <i class="fas ${typeIcon} nft-type-icon"></i>
                    <div class="nft-tier-badge ${tierClass}">
                        ${TIER_NAMES[nft.tier]}
                    </div>
                    <h6 class="card-title mt-4 mb-1">${nft.name}</h6>
                    <p class="text-muted small mb-2">${CATEGORY_NAMES[nft.category]}</p>
                    <p class="text-success mb-2">
                        <i class="fas fa-bolt"></i> +${nft.bonus_value}%
                    </p>
                    <hr class="my-2">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <span class="text-muted small">Listed Price</span>
                        <h5 class="text-warning mb-0">
                            <i class="fas fa-coins"></i> ${parseFloat(listing.price_zen).toFixed(2)}
                        </h5>
                    </div>
                    <button class="btn btn-cancel w-100 mt-auto" onclick="cancelListing(${listing.id}, ${nft.token_id})">
                        <i class="fas fa-times me-1"></i> Cancel Listing
                    </button>
                </div>
            </div>
        `;

        row.appendChild(col);
    });
}

// Cancel listing
async function cancelListing(listingId, tokenId) {
    if (!web3) {
        const connected = await initWeb3();
        if (!connected) return;
    }

    try {
        // Show confirmation modal
        showInfo('Please confirm the transaction to cancel your listing. Your NFT will be returned to your wallet.');
        // Call cancelListing on marketplace contract
        marketplaceContract = new web3.eth.Contract([
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "cancelListing",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ], MARKETPLACE_CONTRACT_ADDRESS);

        const tx = await marketplaceContract.methods.cancelListing(tokenId)
            .send({
                from: userAccount,
                gas: 300000  // Reasonable gas limit for cancelling (return NFT from escrow)
            });

        // Send transaction hash to backend for verification
        const response = await fetch('/nft-marketplace/api/cancel', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                listing_id: listingId,
                tx_hash: tx.transactionHash
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess('Listing cancelled successfully! Your NFT has been returned.');
            loadMyListings();
            loadListings();
        } else {
            showError('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error cancelling listing:', error);

        // Handle user rejection
        if (error.message && error.message.includes('User denied')) {
            showInfo('Cancellation aborted. Your listing is still active.');
        } else {
            showError('Failed to cancel listing: ' + error.message);
        }
    }
}

// Update category filter based on type
document.getElementById('filterType')?.addEventListener('change', function() {
    const categorySelect = document.getElementById('filterCategory');
    categorySelect.innerHTML = '<option value="">All Categories</option>';

    const type = this.value;

    if (type === 'player') {
        categorySelect.innerHTML += `
            <option value="combat_boost">Combat Boost</option>
            <option value="energy_regen">Energy Regen</option>
            <option value="wellness_regen">Wellness Regen</option>
            <option value="military_tutor">Military Tutor</option>
            <option value="travel_discount">Travel Discount</option>
            <option value="storage_increase">Storage Increase</option>
        `;
    } else if (type === 'company') {
        categorySelect.innerHTML += `
            <option value="production_boost">Production Boost</option>
            <option value="material_efficiency">Material Efficiency</option>
            <option value="upgrade_discount">Upgrade Discount</option>
            <option value="speed_boost">Speed Boost</option>
            <option value="android_worker">Android Worker</option>
            <option value="tax_breaks">Tax Breaks</option>
        `;
    }
});

// Get CSRF token
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]').content;
}

// Event listeners
document.getElementById('applyFiltersBtn')?.addEventListener('click', loadListings);
document.getElementById('clearFiltersBtn')?.addEventListener('click', function() {
    document.getElementById('filterType').value = '';
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterMinTier').value = '';
    document.getElementById('filterMaxTier').value = '';
    document.getElementById('filterMinPrice').value = '';
    document.getElementById('filterMaxPrice').value = '';
    document.getElementById('sortBy').value = 'listed_at';
    loadListings();
});

document.getElementById('myNFTsBtn')?.addEventListener('click', function() {
    const modal = new bootstrap.Modal(document.getElementById('listNFTModal'));
    modal.show();
    loadMyNFTs();
});

document.getElementById('myListingsBtn')?.addEventListener('click', function() {
    const modal = new bootstrap.Modal(document.getElementById('myListingsModal'));
    modal.show();
    loadMyListings();
});

// Second clear filters button (in empty state)
document.getElementById('clearFiltersBtn2')?.addEventListener('click', function() {
    document.getElementById('filterType').value = '';
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterMinTier').value = '';
    document.getElementById('filterMaxTier').value = '';
    document.getElementById('filterMinPrice').value = '';
    document.getElementById('filterMaxPrice').value = '';
    document.getElementById('sortBy').value = 'listed_at';
    loadListings();
});

// List NFT from empty state in My Listings modal
document.getElementById('listNFTFromEmpty')?.addEventListener('click', function() {
    // Open the List NFT modal
    const modal = new bootstrap.Modal(document.getElementById('listNFTModal'));
    modal.show();
    loadMyNFTs();
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadMarketplaceInfo();
    loadListings();
    initWeb3(); // Try to connect wallet on load

    // Global handler for ALL modal hidden events - ensures scroll is always restored
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('hidden.bs.modal', function() {
            setTimeout(() => {
                cleanupModalBackdrops();
            }, 100);
        });
    });

    // Add click handlers to all modal OK/Close buttons
    document.querySelectorAll('.modal [data-bs-dismiss="modal"]').forEach(btn => {
        btn.addEventListener('click', function() {
            setTimeout(() => cleanupModalBackdrops(), 200);
        });
    });
});
