// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title TestZEN
 * @dev Test version of ZEN token for BASE Sepolia testnet
 * @notice This is ONLY for testing purposes on testnet
 */
contract TestZEN is ERC20, Ownable {
    uint8 private constant _decimals = 18;

    // Initial supply: 1 million tokens
    uint256 private constant INITIAL_SUPPLY = 1_000_000 * 10**18;

    constructor() ERC20("Test Horizen", "testZEN") Ownable(msg.sender) {
        // Mint initial supply to deployer
        _mint(msg.sender, INITIAL_SUPPLY);
    }

    /**
     * @dev Allows owner to mint additional tokens for testing
     * @param to Address to receive tokens
     * @param amount Amount of tokens to mint (in wei)
     */
    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }

    /**
     * @dev Faucet function - allows anyone to claim test tokens
     * @notice Users can claim 100 testZEN once per day for testing
     */
    mapping(address => uint256) public lastClaim;
    uint256 public constant FAUCET_AMOUNT = 100 * 10**18; // 100 testZEN
    uint256 public constant CLAIM_COOLDOWN = 1 days;

    function claimTestTokens() public {
        require(
            block.timestamp >= lastClaim[msg.sender] + CLAIM_COOLDOWN,
            "You can only claim once per day"
        );

        lastClaim[msg.sender] = block.timestamp;
        _mint(msg.sender, FAUCET_AMOUNT);
    }

    /**
     * @dev Returns the number of decimals used by the token
     */
    function decimals() public pure override returns (uint8) {
        return _decimals;
    }

    /**
     * @dev Allows owner to burn tokens from any address (for testing cleanup)
     */
    function burn(address from, uint256 amount) public onlyOwner {
        _burn(from, amount);
    }
}
