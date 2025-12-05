// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CitizenshipNFT
 * @dev Simplified soul-bound NFT for citizenship (without OpenZeppelin)
 */
contract CitizenshipNFT {
    string public name = "Tactizen Citizenship";
    string public symbol = "TACT-CIT";

    address public owner;
    uint256 private _tokenIdCounter;

    // Token data
    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;
    mapping(uint256 => string) public tokenURI;
    mapping(uint256 => string) public tokenCountry;

    // Soul-bound enforcement
    mapping(address => uint256) public addressToTokenId;
    mapping(address => bool) public hasCitizenship;

    // Events
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event CitizenshipMinted(address indexed citizen, uint256 indexed tokenId, string country);
    event CitizenshipBurned(address indexed citizen, uint256 indexed tokenId);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Returns the owner of a token
     */
    function ownerOf(uint256 tokenId) public view returns (address) {
        address tokenOwner = _owners[tokenId];
        require(tokenOwner != address(0), "Token does not exist");
        return tokenOwner;
    }

    /**
     * @dev Returns the balance of an address (max 1 for soul-bound)
     */
    function balanceOf(address tokenOwner) public view returns (uint256) {
        require(tokenOwner != address(0), "Invalid address");
        return _balances[tokenOwner];
    }

    /**
     * @dev Mint a citizenship NFT
     */
    function mintCitizenship(
        address to,
        string memory country,
        string memory uri
    ) public onlyOwner {
        require(to != address(0), "Cannot mint to zero address");
        require(!hasCitizenship[to], "Address already has citizenship");

        _tokenIdCounter++;
        uint256 tokenId = _tokenIdCounter;

        _owners[tokenId] = to;
        _balances[to] = 1;
        tokenURI[tokenId] = uri;
        tokenCountry[tokenId] = country;
        addressToTokenId[to] = tokenId;
        hasCitizenship[to] = true;

        emit Transfer(address(0), to, tokenId);
        emit CitizenshipMinted(to, tokenId, country);
    }

    /**
     * @dev Burn a citizenship NFT
     */
    function burnCitizenship(uint256 tokenId) public onlyOwner {
        address tokenOwner = ownerOf(tokenId);

        _balances[tokenOwner] = 0;
        delete _owners[tokenId];
        delete tokenURI[tokenId];
        delete tokenCountry[tokenId];
        delete addressToTokenId[tokenOwner];
        hasCitizenship[tokenOwner] = false;

        emit Transfer(tokenOwner, address(0), tokenId);
        emit CitizenshipBurned(tokenOwner, tokenId);
    }

    /**
     * @dev Override transfer to prevent transfers (soul-bound)
     */
    function transferFrom(address from, address to, uint256 tokenId) public pure {
        revert("Citizenship NFTs are soul-bound and cannot be transferred");
    }

    function safeTransferFrom(address from, address to, uint256 tokenId) public pure {
        revert("Citizenship NFTs are soul-bound and cannot be transferred");
    }

    function safeTransferFrom(address from, address to, uint256 tokenId, bytes memory data) public pure {
        revert("Citizenship NFTs are soul-bound and cannot be transferred");
    }

    /**
     * @dev Get citizenship country for a token
     */
    function getCitizenshipCountry(uint256 tokenId) public view returns (string memory) {
        require(_owners[tokenId] != address(0), "Token does not exist");
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
     * @dev Get total supply
     */
    function totalSupply() public view returns (uint256) {
        return _tokenIdCounter;
    }

    /**
     * @dev ERC165 support
     */
    function supportsInterface(bytes4 interfaceId) public pure returns (bool) {
        return
            interfaceId == 0x80ac58cd || // ERC721
            interfaceId == 0x01ffc9a7;   // ERC165
    }
}
