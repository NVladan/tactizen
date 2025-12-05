// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/**
 * @title CitizenshipNFT
 * @dev Soul-bound NFT representing citizenship in Tactizen countries
 * @notice These NFTs are non-transferable once minted
 */
contract CitizenshipNFT is ERC721, ERC721URIStorage, Ownable {
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIdCounter;

    // Mapping from token ID to country name
    mapping(uint256 => string) public tokenCountry;

    // Mapping from user address to token ID (one citizenship per address)
    mapping(address => uint256) public addressToTokenId;

    // Mapping to track if address has a citizenship NFT
    mapping(address => bool) public hasCitizenship;

    event CitizenshipMinted(address indexed citizen, uint256 indexed tokenId, string country);
    event CitizenshipBurned(address indexed citizen, uint256 indexed tokenId);

    constructor() ERC721("Tactizen Citizenship", "TACT-CIT") Ownable(msg.sender) {}

    /**
     * @dev Mints a citizenship NFT to a user
     * @param to Address of the citizen
     * @param country Name of the country
     * @param tokenURI Metadata URI for the NFT
     */
    function mintCitizenship(
        address to,
        string memory country,
        string memory tokenURI
    ) public onlyOwner {
        require(!hasCitizenship[to], "Address already has citizenship");

        _tokenIdCounter.increment();
        uint256 tokenId = _tokenIdCounter.current();

        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenURI);

        tokenCountry[tokenId] = country;
        addressToTokenId[to] = tokenId;
        hasCitizenship[to] = true;

        emit CitizenshipMinted(to, tokenId, country);
    }

    /**
     * @dev Burns a citizenship NFT (only owner can burn)
     * @param tokenId Token ID to burn
     */
    function burnCitizenship(uint256 tokenId) public onlyOwner {
        address owner = ownerOf(tokenId);
        hasCitizenship[owner] = false;
        delete addressToTokenId[owner];
        delete tokenCountry[tokenId];

        _burn(tokenId);

        emit CitizenshipBurned(owner, tokenId);
    }

    /**
     * @dev Override transfer functions to make NFT soul-bound (non-transferable)
     */
    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        address from = _ownerOf(tokenId);

        // Allow minting (from == address(0)) and burning (to == address(0))
        // But prevent transfers between addresses
        if (from != address(0) && to != address(0)) {
            revert("Citizenship NFTs are soul-bound and cannot be transferred");
        }

        return super._update(to, tokenId, auth);
    }

    /**
     * @dev Get citizenship country for a token
     */
    function getCitizenshipCountry(uint256 tokenId) public view returns (string memory) {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        return tokenCountry[tokenId];
    }

    /**
     * @dev Get token ID for an address
     */
    function getTokenIdForAddress(address citizen) public view returns (uint256) {
        require(hasCitizenship[citizen], "Address does not have citizenship");
        return addressToTokenId[citizen];
    }

    /**
     * @dev Get total number of citizenships minted
     */
    function totalSupply() public view returns (uint256) {
        return _tokenIdCounter.current();
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
