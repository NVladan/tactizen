const hre = require("hardhat");

async function main() {
  console.log("Deploying Tactizen GameNFT V3 to BASE Sepolia...");

  // Get ZEN token and treasury addresses from environment
  const zenTokenAddress = process.env.ZEN_TOKEN_ADDRESS;
  const treasuryAddress = process.env.TREASURY_ADDRESS;

  if (!zenTokenAddress) {
    throw new Error("ZEN_TOKEN_ADDRESS not set in .env file");
  }

  if (!treasuryAddress) {
    throw new Error("TREASURY_ADDRESS not set in .env file");
  }

  console.log("ZEN Token address:", zenTokenAddress);
  console.log("Treasury address:", treasuryAddress);

  // Get the contract factory
  const GameNFT = await hre.ethers.getContractFactory("GameNFT");

  // Deploy the contract with ZEN token and treasury addresses
  console.log("\nDeploying contract...");
  const gameNFT = await GameNFT.deploy(zenTokenAddress, treasuryAddress);

  await gameNFT.waitForDeployment();

  const address = await gameNFT.getAddress();

  console.log("\n✅ Tactizen GameNFT V3 deployed to:", address);
  console.log("\n📝 Add this to your .env file:");
  console.log(`NFT_CONTRACT_ADDRESS=${address}`);

  console.log("\nWaiting for block confirmations...");
  await gameNFT.deploymentTransaction().wait(5);

  console.log("\n✅ Deployment complete!");
  console.log("\n🔍 To verify on BaseScan, run:");
  console.log(`npx hardhat verify --network baseSepolia ${address} ${zenTokenAddress} ${treasuryAddress}`);

  console.log("\n📊 Contract Details:");
  console.log("- Mint Price: 1 ZEN");
  console.log("- Users can mint by paying ZEN directly");
  console.log("- Owner can adminMintNFT for free (airdrops/rewards)");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
