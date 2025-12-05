// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/**
 * @title GameNFT V2
 * @dev ERC-721 NFT with on-chain ZEN payment verification for Tactizen
 * @notice Users pay ZEN directly to the contract, which then mints NFT
 */
contract GameNFT is ERC721, ERC721URIStorage, Ownable {
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIdCounter;

    // ZEN Token contract
    IERC20 public zenToken;

    // Treasury address to receive ZEN payments
    address public treasury;

    // Mint price in ZEN (1 ZEN = 10^18 wei)
    uint256 public constant MINT_PRICE = 1 ether;

    // NFT Metadata Struct
    struct NFTMetadata {
        string nftType;      // "player" or "company"
        string category;     // "combat_boost", "energy_regen", "production_boost", etc.
        uint8 tier;          // 1-5 (Q1-Q5)
        uint16 bonusValue;   // Bonus percentage or value (e.g., 25 = 25%)
        bool exists;         // Track if NFT exists
    }

    // Mapping from token ID to metadata
    mapping(uint256 => NFTMetadata) public nftMetadata;

    // Mapping to track total supply per tier
    mapping(uint8 => uint256) public tierSupply;

    // Events
    event NFTMinted(address indexed to, uint256 indexed tokenId, string nftType, string category, uint8 tier, uint256 pricePaid);
    event NFTBurned(uint256 indexed tokenId, address indexed burner);
    event NFTUpgraded(address indexed owner, uint256[] burnedTokenIds, uint256 newTokenId, uint8 newTier);
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);

    constructor(address _zenToken, address _treasury) ERC721("Tactizen Game NFT", "TACTIZEN") Ownable(msg.sender) {
        require(_zenToken != address(0), "ZEN token cannot be zero address");
        require(_treasury != address(0), "Treasury cannot be zero address");
        zenToken = IERC20(_zenToken);
        treasury = _treasury;
    }

    /**
     * @dev Mint a new game NFT with ZEN payment
     * @param nftType "player" or "company"
     * @param category Category of bonus (e.g., "combat_boost")
     * @param tier Tier 1-5 (Q1-Q5)
     * @param bonusValue Bonus value (e.g., 25 for 25%)
     * @param tokenURI Metadata URI
     */
    function mintNFT(
        string memory nftType,
        string memory category,
        uint8 tier,
        uint16 bonusValue,
        string memory tokenURI
    ) public returns (uint256) {
        require(tier >= 1 && tier <= 5, "Tier must be 1-5");
        require(bytes(nftType).length > 0, "NFT type required");
        require(bytes(category).length > 0, "Category required");

        // CRITICAL: Verify ZEN payment on-chain
        require(
            zenToken.transferFrom(msg.sender, treasury, MINT_PRICE),
            "ZEN payment failed - ensure you approved the contract"
        );

        _tokenIdCounter.increment();
        uint256 tokenId = _tokenIdCounter.current();

        _safeMint(msg.sender, tokenId);
        _setTokenURI(tokenId, tokenURI);

        nftMetadata[tokenId] = NFTMetadata({
            nftType: nftType,
            category: category,
            tier: tier,
            bonusValue: bonusValue,
            exists: true
        });

        tierSupply[tier]++;

        emit NFTMinted(msg.sender, tokenId, nftType, category, tier, MINT_PRICE);

        return tokenId;
    }

    /**
     * @dev Admin mint function (for airdrops, rewards, etc.) - NO PAYMENT REQUIRED
     * @param to Address to mint to
     * @param nftType "player" or "company"
     * @param category Category of bonus
     * @param tier Tier 1-5
     * @param bonusValue Bonus value
     * @param tokenURI Metadata URI
     */
    function adminMintNFT(
        address to,
        string memory nftType,
        string memory category,
        uint8 tier,
        uint16 bonusValue,
        string memory tokenURI
    ) public onlyOwner returns (uint256) {
        require(tier >= 1 && tier <= 5, "Tier must be 1-5");
        require(bytes(nftType).length > 0, "NFT type required");
        require(bytes(category).length > 0, "Category required");

        _tokenIdCounter.increment();
        uint256 tokenId = _tokenIdCounter.current();

        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenURI);

        nftMetadata[tokenId] = NFTMetadata({
            nftType: nftType,
            category: category,
            tier: tier,
            bonusValue: bonusValue,
            exists: true
        });

        tierSupply[tier]++;

        emit NFTMinted(to, tokenId, nftType, category, tier, 0);

        return tokenId;
    }

    /**
     * @dev Burn NFT
     * @param tokenId Token ID to burn
     */
    function burnNFT(uint256 tokenId) public {
        require(_ownerOf(tokenId) == msg.sender || owner() == msg.sender, "Not owner or game admin");
        require(nftMetadata[tokenId].exists, "NFT does not exist");

        uint8 tier = nftMetadata[tokenId].tier;

        // Mark as non-existent before burning
        nftMetadata[tokenId].exists = false;
        tierSupply[tier]--;

        _burn(tokenId);

        emit NFTBurned(tokenId, msg.sender);
    }

    /**
     * @dev Upgrade NFT by burning 3 of same tier to create 1 of next tier
     * @param burnTokenIds Array of 3 token IDs to burn (must be same tier)
     * @param newNftType Type of new NFT
     * @param newCategory Category of new NFT
     * @param newBonusValue Bonus value for new NFT
     * @param newTokenURI Metadata URI for new NFT
     */
    function upgradeNFT(
        uint256[] memory burnTokenIds,
        string memory newNftType,
        string memory newCategory,
        uint16 newBonusValue,
        string memory newTokenURI
    ) public returns (uint256) {
        require(burnTokenIds.length == 3, "Must burn exactly 3 NFTs");

        // Verify all NFTs are owned by sender and same tier
        uint8 tier = nftMetadata[burnTokenIds[0]].tier;
        require(tier < 5, "Cannot upgrade Q5 NFTs");

        for (uint i = 0; i < 3; i++) {
            require(_ownerOf(burnTokenIds[i]) == msg.sender, "Must own all NFTs");
            require(nftMetadata[burnTokenIds[i]].tier == tier, "All NFTs must be same tier");
            require(nftMetadata[burnTokenIds[i]].exists, "NFT does not exist");
        }

        // Burn all 3 NFTs
        for (uint i = 0; i < 3; i++) {
            nftMetadata[burnTokenIds[i]].exists = false;
            tierSupply[tier]--;
            _burn(burnTokenIds[i]);
        }

        // Mint new NFT of next tier
        uint8 newTier = tier + 1;
        _tokenIdCounter.increment();
        uint256 newTokenId = _tokenIdCounter.current();

        _safeMint(msg.sender, newTokenId);
        _setTokenURI(newTokenId, newTokenURI);

        nftMetadata[newTokenId] = NFTMetadata({
            nftType: newNftType,
            category: newCategory,
            tier: newTier,
            bonusValue: newBonusValue,
            exists: true
        });

        tierSupply[newTier]++;

        emit NFTUpgraded(msg.sender, burnTokenIds, newTokenId, newTier);

        return newTokenId;
    }

    /**
     * @dev Update treasury address
     * @param newTreasury New treasury address
     */
    function updateTreasury(address newTreasury) public onlyOwner {
        require(newTreasury != address(0), "Treasury cannot be zero address");
        address oldTreasury = treasury;
        treasury = newTreasury;
        emit TreasuryUpdated(oldTreasury, newTreasury);
    }

    /**
     * @dev Get NFT metadata
     * @param tokenId Token ID
     */
    function getNFTMetadata(uint256 tokenId) public view returns (
        string memory nftType,
        string memory category,
        uint8 tier,
        uint16 bonusValue,
        bool exists
    ) {
        NFTMetadata memory metadata = nftMetadata[tokenId];
        return (
            metadata.nftType,
            metadata.category,
            metadata.tier,
            metadata.bonusValue,
            metadata.exists
        );
    }

    /**
     * @dev Get total supply
     */
    function totalSupply() public view returns (uint256) {
        return _tokenIdCounter.current();
    }

    /**
     * @dev Get supply by tier
     */
    function getSupplyByTier(uint8 tier) public view returns (uint256) {
        require(tier >= 1 && tier <= 5, "Invalid tier");
        return tierSupply[tier];
    }

    /**
     * @dev Get all NFTs owned by an address
     * @param owner Address to check
     * @return Array of token IDs
     */
    function getNFTsByOwner(address owner) public view returns (uint256[] memory) {
        uint256 totalTokens = _tokenIdCounter.current();
        uint256 ownedCount = 0;

        // Count owned NFTs
        for (uint256 i = 1; i <= totalTokens; i++) {
            if (_ownerOf(i) == owner && nftMetadata[i].exists) {
                ownedCount++;
            }
        }

        // Create array of owned token IDs
        uint256[] memory ownedTokens = new uint256[](ownedCount);
        uint256 index = 0;

        for (uint256 i = 1; i <= totalTokens; i++) {
            if (_ownerOf(i) == owner && nftMetadata[i].exists) {
                ownedTokens[index] = i;
                index++;
            }
        }

        return ownedTokens;
    }

    // Required overrides for ERC721URIStorage
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
