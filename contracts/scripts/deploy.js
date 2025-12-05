const hre = require("hardhat");

async function main() {
  console.log("Deploying GameNFT V3 contract to Base Sepolia...");

  // Get the contract factory
  const GameNFT = await hre.ethers.getContractFactory("GameNFT");

  // Deploy parameters
  const zenTokenAddress = process.env.ZEN_TOKEN_ADDRESS;
  const treasuryAddress = process.env.TREASURY_ADDRESS;

  if (!zenTokenAddress || !treasuryAddress) {
    throw new Error("Missing ZEN_TOKEN_ADDRESS or TREASURY_ADDRESS in environment");
  }

  console.log(`ZEN Token: ${zenTokenAddress}`);
  console.log(`Treasury: ${treasuryAddress}`);

  // Deploy the contract
  const gameNFT = await GameNFT.deploy(zenTokenAddress, treasuryAddress);

  await gameNFT.waitForDeployment();

  const contractAddress = await gameNFT.getAddress();

  console.log("\n✅ GameNFT V3 deployed successfully!");
  console.log(`📝 Contract Address: ${contractAddress}`);
  console.log(`🔗 View on BaseScan: https://sepolia.basescan.org/address/${contractAddress}`);
  console.log(`\n⚙️  Update your .env file:`);
  console.log(`NFT_CONTRACT_ADDRESS=${contractAddress}`);

  // Wait for block confirmations
  console.log("\nWaiting for block confirmations...");
  await gameNFT.deploymentTransaction().wait(5);

  console.log("\n✅ Contract confirmed on blockchain!");
  console.log("\nV3 Changes:");
  console.log("- Requires all 3 NFTs to be same tier");
  console.log("- Requires all 3 NFTs to be same type (player/company)");
  console.log("- Requires all 3 NFTs to be same category");
  console.log("- Preserves type and category in upgraded NFT");
  console.log("\nExample: 3× Comfort Cushion Q1 → 1× Comfort Cushion Q2");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
