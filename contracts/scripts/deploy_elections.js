// Deployment script for ElectionResults contract

const hre = require("hardhat");

async function main() {
    console.log("Deploying ElectionResults contract...");

    // Get the deployer account
    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying with account:", deployer.address);

    // Get balance
    const balance = await deployer.provider.getBalance(deployer.address);
    console.log("Account balance:", hre.ethers.formatEther(balance), "ETH");

    // Deploy the contract
    const ElectionResults = await hre.ethers.getContractFactory("ElectionResults");
    const electionResults = await ElectionResults.deploy();

    await electionResults.waitForDeployment();

    const contractAddress = await electionResults.getAddress();
    console.log("ElectionResults deployed to:", contractAddress);

    // Verify the owner
    const owner = await electionResults.owner();
    console.log("Contract owner:", owner);

    // Log deployment info for configuration
    console.log("\n=== Configuration ===");
    console.log("Add to your .env or config.py:");
    console.log(`ELECTION_RESULTS_CONTRACT_ADDRESS=${contractAddress}`);

    return contractAddress;
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
