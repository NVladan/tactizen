// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title ZENToken
 * @dev ERC20 token for CyberRepublik in-game currency
 */
contract ZENToken is ERC20, Ownable {

    constructor() ERC20("Zenith Token", "ZEN") Ownable(msg.sender) {
        // Mint initial supply to deployer (1 million ZEN)
        _mint(msg.sender, 1000000 * 10**18);
    }

    /**
     * @dev Mint new tokens (only owner can mint)
     * @param to Address to receive tokens
     * @param amount Amount of tokens to mint (in wei, 18 decimals)
     */
    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }

    /**
     * @dev Burn tokens from caller's balance
     * @param amount Amount of tokens to burn
     */
    function burn(uint256 amount) public {
        _burn(msg.sender, amount);
    }

    /**
     * @dev Get decimals (18 for standard ERC20)
     */
    function decimals() public pure override returns (uint8) {
        return 18;
    }
}
