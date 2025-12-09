const hre = require("hardhat");
require('dotenv').config();

async function main() {
  const [deployer] = await hre.ethers.getSigners();

  console.log("=====================================");
  console.log("Deploying NFTMarketplace Contract");
  console.log("=====================================");
  console.log("Deploying with account:", deployer.address);
  console.log("");

  // Get contract addresses from environment
  const zenTokenAddress = process.env.ZEN_TOKEN_ADDRESS;
  const nftContractAddress = process.env.NFT_CONTRACT_ADDRESS || '0x57e277b2d887C3C749757e36F0B6CFad32E00e8A';
  const treasuryAddress = process.env.TREASURY_ADDRESS;

  if (!zenTokenAddress) {
    throw new Error("ZEN_TOKEN_ADDRESS not set in .env file");
  }

  if (!treasuryAddress) {
    throw new Error("TREASURY_ADDRESS not set in .env file");
  }

  console.log("Configuration:");
  console.log("- ZEN Token Address:", zenTokenAddress);
  console.log("- NFT Contract Address:", nftContractAddress);
  console.log("- Treasury Address:", treasuryAddress);
  console.log("- Marketplace Fee: 5% (500 basis points)");
  console.log("");

  // Deploy NFTMarketplace
  console.log("Deploying NFTMarketplace contract...");
  const NFTMarketplace = await hre.ethers.getContractFactory("NFTMarketplace");

  const marketplaceFee = 500; // 5% (in basis points: 500/10000 = 5%)

  const marketplace = await NFTMarketplace.deploy(
    zenTokenAddress,
    nftContractAddress,
    treasuryAddress,
    marketplaceFee
  );

  await marketplace.waitForDeployment();

  const marketplaceAddress = await marketplace.getAddress();

  console.log("");
  console.log("✅ NFTMarketplace deployed successfully!");
  console.log("=====================================");
  console.log("Contract Address:", marketplaceAddress);
  console.log("=====================================");
  console.log("");
  console.log("IMPORTANT: Add this to your .env file:");
  console.log(`MARKETPLACE_CONTRACT_ADDRESS=${marketplaceAddress}`);
  console.log("");
  console.log("Also update the contract address in:");
  console.log("- app/static/js/marketplace.js");
  console.log("");

  console.log("");
  console.log("Deployment complete!");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Deployment failed:");
    console.error(error);
    process.exit(1);
  });
