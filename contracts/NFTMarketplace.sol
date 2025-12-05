// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title NFTMarketplace
 * @dev P2P NFT marketplace with escrow for CyberRepublik
 * @notice Players can list NFTs for sale and buy from each other using ZEN tokens
 */
contract NFTMarketplace is Ownable, ReentrancyGuard {
    // ZEN Token contract
    IERC20 public zenToken;

    // GameNFT contract
    IERC721 public nftContract;

    // Marketplace fee (in basis points, e.g., 500 = 5%)
    uint256 public marketplaceFee;

    // Treasury address to receive fees
    address public treasury;

    // Listing structure
    struct Listing {
        uint256 tokenId;
        address seller;
        uint256 price;
        bool active;
        uint256 listedAt;
    }

    // Token ID => Listing
    mapping(uint256 => Listing) public listings;

    // Array to track all active listings
    uint256[] public activeListings;

    // Events
    event NFTListed(
        uint256 indexed tokenId,
        address indexed seller,
        uint256 price,
        uint256 timestamp
    );

    event NFTSold(
        uint256 indexed tokenId,
        address indexed seller,
        address indexed buyer,
        uint256 price,
        uint256 fee,
        uint256 timestamp
    );

    event ListingCancelled(
        uint256 indexed tokenId,
        address indexed seller,
        uint256 timestamp
    );

    event MarketplaceFeeUpdated(uint256 oldFee, uint256 newFee);
    event TreasuryUpdated(address oldTreasury, address newTreasury);

    constructor(
        address _zenToken,
        address _nftContract,
        address _treasury,
        uint256 _marketplaceFee
    ) Ownable(msg.sender) {
        require(_zenToken != address(0), "ZEN token cannot be zero address");
        require(_nftContract != address(0), "NFT contract cannot be zero address");
        require(_treasury != address(0), "Treasury cannot be zero address");
        require(_marketplaceFee <= 2000, "Fee cannot exceed 20%"); // Max 20%

        zenToken = IERC20(_zenToken);
        nftContract = IERC721(_nftContract);
        treasury = _treasury;
        marketplaceFee = _marketplaceFee;
    }

    /**
     * @dev List an NFT for sale with escrow
     * @param tokenId The NFT token ID to list
     * @param price The price in ZEN tokens (with 18 decimals)
     * @notice The NFT will be transferred to this contract as escrow
     */
    function listNFT(uint256 tokenId, uint256 price) external nonReentrant {
        require(price > 0, "Price must be greater than 0");
        require(nftContract.ownerOf(tokenId) == msg.sender, "You don't own this NFT");
        require(!listings[tokenId].active, "NFT already listed");

        // Transfer NFT to marketplace contract (escrow)
        nftContract.transferFrom(msg.sender, address(this), tokenId);

        // Create listing
        listings[tokenId] = Listing({
            tokenId: tokenId,
            seller: msg.sender,
            price: price,
            active: true,
            listedAt: block.timestamp
        });

        activeListings.push(tokenId);

        emit NFTListed(tokenId, msg.sender, price, block.timestamp);
    }

    /**
     * @dev Buy a listed NFT
     * @param tokenId The NFT token ID to purchase
     * @notice Buyer must have approved ZEN token spending before calling this
     */
    function buyNFT(uint256 tokenId) external nonReentrant {
        Listing storage listing = listings[tokenId];

        require(listing.active, "NFT not listed for sale");
        require(listing.seller != msg.sender, "Cannot buy your own NFT");

        uint256 price = listing.price;
        uint256 fee = (price * marketplaceFee) / 10000;
        uint256 sellerAmount = price - fee;

        // Mark as inactive before transfers (reentrancy protection)
        listing.active = false;
        _removeFromActiveListings(tokenId);

        // Transfer ZEN from buyer to seller
        require(
            zenToken.transferFrom(msg.sender, listing.seller, sellerAmount),
            "ZEN payment to seller failed"
        );

        // Transfer marketplace fee to treasury
        if (fee > 0) {
            require(
                zenToken.transferFrom(msg.sender, treasury, fee),
                "ZEN fee payment failed"
            );
        }

        // Transfer NFT from escrow to buyer
        nftContract.transferFrom(address(this), msg.sender, tokenId);

        emit NFTSold(
            tokenId,
            listing.seller,
            msg.sender,
            price,
            fee,
            block.timestamp
        );
    }

    /**
     * @dev Cancel a listing and return NFT to seller
     * @param tokenId The NFT token ID to cancel
     * @notice Free cancellation anytime
     */
    function cancelListing(uint256 tokenId) external nonReentrant {
        Listing storage listing = listings[tokenId];

        require(listing.active, "NFT not listed");
        require(listing.seller == msg.sender, "Not the seller");

        // Mark as inactive
        listing.active = false;
        _removeFromActiveListings(tokenId);

        // Return NFT to seller
        nftContract.transferFrom(address(this), listing.seller, tokenId);

        emit ListingCancelled(tokenId, msg.sender, block.timestamp);
    }

    /**
     * @dev Get listing details
     * @param tokenId The NFT token ID
     */
    function getListing(uint256 tokenId) external view returns (
        address seller,
        uint256 price,
        bool active,
        uint256 listedAt
    ) {
        Listing memory listing = listings[tokenId];
        return (
            listing.seller,
            listing.price,
            listing.active,
            listing.listedAt
        );
    }

    /**
     * @dev Get all active listings
     * @return Array of token IDs that are currently listed
     */
    function getActiveListings() external view returns (uint256[] memory) {
        return activeListings;
    }

    /**
     * @dev Get count of active listings
     */
    function getActiveListingCount() external view returns (uint256) {
        return activeListings.length;
    }

    /**
     * @dev Update marketplace fee (only owner)
     * @param newFee New fee in basis points (e.g., 500 = 5%)
     */
    function updateMarketplaceFee(uint256 newFee) external onlyOwner {
        require(newFee <= 2000, "Fee cannot exceed 20%");
        uint256 oldFee = marketplaceFee;
        marketplaceFee = newFee;
        emit MarketplaceFeeUpdated(oldFee, newFee);
    }

    /**
     * @dev Update treasury address (only owner)
     * @param newTreasury New treasury address
     */
    function updateTreasury(address newTreasury) external onlyOwner {
        require(newTreasury != address(0), "Treasury cannot be zero address");
        address oldTreasury = treasury;
        treasury = newTreasury;
        emit TreasuryUpdated(oldTreasury, newTreasury);
    }

    /**
     * @dev Emergency function to recover stuck NFTs (only owner)
     * @param tokenId Token ID to recover
     * @param to Address to send NFT to
     * @notice This should only be used if there's a bug or emergency
     */
    function emergencyWithdrawNFT(uint256 tokenId, address to) external onlyOwner {
        require(to != address(0), "Cannot send to zero address");
        nftContract.transferFrom(address(this), to, tokenId);
    }

    /**
     * @dev Internal function to remove token ID from active listings array
     * @param tokenId Token ID to remove
     */
    function _removeFromActiveListings(uint256 tokenId) internal {
        for (uint256 i = 0; i < activeListings.length; i++) {
            if (activeListings[i] == tokenId) {
                // Move last element to this position and pop
                activeListings[i] = activeListings[activeListings.length - 1];
                activeListings.pop();
                break;
            }
        }
    }
}
