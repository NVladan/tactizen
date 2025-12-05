// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TestZEN - Simple ERC20 Token
 * @dev Test version of ZEN token for BASE Sepolia testnet
 * @notice Simplified version without OpenZeppelin dependencies
 */
contract TestZEN {
    string public name = "Test Horizen";
    string public symbol = "testZEN";
    uint8 public decimals = 18;
    uint256 public totalSupply;

    address public owner;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    mapping(address => uint256) public lastClaim;

    uint256 public constant FAUCET_AMOUNT = 100 * 10**18; // 100 testZEN
    uint256 public constant CLAIM_COOLDOWN = 1 days;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event TokensClaimed(address indexed claimer, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    constructor() {
        owner = msg.sender;
        // Mint 1 million tokens to deployer
        uint256 initialSupply = 1_000_000 * 10**18;
        balanceOf[msg.sender] = initialSupply;
        totalSupply = initialSupply;
        emit Transfer(address(0), msg.sender, initialSupply);
    }

    function transfer(address to, uint256 value) public returns (bool) {
        require(to != address(0), "Cannot transfer to zero address");
        require(balanceOf[msg.sender] >= value, "Insufficient balance");

        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;

        emit Transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) public returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) public returns (bool) {
        require(to != address(0), "Cannot transfer to zero address");
        require(balanceOf[from] >= value, "Insufficient balance");
        require(allowance[from][msg.sender] >= value, "Insufficient allowance");

        balanceOf[from] -= value;
        balanceOf[to] += value;
        allowance[from][msg.sender] -= value;

        emit Transfer(from, to, value);
        return true;
    }

    /**
     * @dev Faucet function - allows anyone to claim test tokens
     */
    function claimTestTokens() public {
        require(
            block.timestamp >= lastClaim[msg.sender] + CLAIM_COOLDOWN,
            "You can only claim once per day"
        );

        lastClaim[msg.sender] = block.timestamp;
        balanceOf[msg.sender] += FAUCET_AMOUNT;
        totalSupply += FAUCET_AMOUNT;

        emit Transfer(address(0), msg.sender, FAUCET_AMOUNT);
        emit TokensClaimed(msg.sender, FAUCET_AMOUNT);
    }

    /**
     * @dev Allows owner to mint tokens for testing
     */
    function mint(address to, uint256 amount) public onlyOwner {
        require(to != address(0), "Cannot mint to zero address");

        balanceOf[to] += amount;
        totalSupply += amount;

        emit Transfer(address(0), to, amount);
    }

    /**
     * @dev Allows owner to burn tokens
     */
    function burn(address from, uint256 amount) public onlyOwner {
        require(balanceOf[from] >= amount, "Insufficient balance to burn");

        balanceOf[from] -= amount;
        totalSupply -= amount;

        emit Transfer(from, address(0), amount);
    }
}
