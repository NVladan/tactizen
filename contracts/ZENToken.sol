// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title ZENToken
 * @dev ERC20 token for Tactizen game economy on Horizen L3
 *
 * Token Details:
 * - Name: Horizen
 * - Symbol: ZEN
 * - Total Supply: 21,000,000 ZEN (fixed, no additional minting)
 * - Decimals: 18
 */
contract ZENToken is ERC20, Ownable {

    uint256 public constant MAX_SUPPLY = 21_000_000 * 10**18;

    constructor() ERC20("Horizen", "ZEN") Ownable(msg.sender) {
        // Mint entire max supply to deployer (treasury)
        _mint(msg.sender, MAX_SUPPLY);
    }

    /**
     * @dev Burn tokens from caller's balance
     * @param amount Amount of tokens to burn
     */
    function burn(uint256 amount) public {
        _burn(msg.sender, amount);
    }

    /**
     * @dev Burn tokens from a specific address (requires allowance)
     * @param account Address to burn from
     * @param amount Amount of tokens to burn
     */
    function burnFrom(address account, uint256 amount) public {
        _spendAllowance(account, msg.sender, amount);
        _burn(account, amount);
    }

    /**
     * @dev Get decimals (18 for standard ERC20)
     */
    function decimals() public pure override returns (uint8) {
        return 18;
    }
}
