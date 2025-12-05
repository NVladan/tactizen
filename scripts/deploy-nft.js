const hre = require("hardhat");

async function main() {
  const networkName = hre.network.name;
  console.log(`Deploying GameNFT to ${networkName}...`);

  // Get addresses from environment or use deployer
  const [deployer] = await hre.ethers.getSigners();
  const zenTokenAddress = process.env.ZEN_TOKEN_ADDRESS;
  const treasuryAddress = process.env.TREASURY_ADDRESS || deployer.address;

  if (!zenTokenAddress) {
    throw new Error("ZEN_TOKEN_ADDRESS not set in .env file. Deploy ZEN token first!");
  }

  console.log("ZEN Token address:", zenTokenAddress);
  console.log("Treasury address:", treasuryAddress);

  // Get the contract factory
  const GameNFT = await hre.ethers.getContractFactory("GameNFT");

  // Deploy the contract with both required arguments
  const gameNFT = await GameNFT.deploy(zenTokenAddress, treasuryAddress);

  await gameNFT.waitForDeployment();

  const address = await gameNFT.getAddress();

  console.log("✅ GameNFT deployed to:", address);
  console.log("\nAdd this to your .env file:");
  console.log(`NFT_CONTRACT_ADDRESS=${address}`);
  console.log(`CITIZENSHIP_NFT_ADDRESS=${address}`);

  console.log("\nWaiting for block confirmations...");
  await gameNFT.deploymentTransaction().wait(5);

  console.log("\n✅ Deployment complete!");
  console.log("\nTo verify on block explorer, run:");
  console.log(`npx hardhat verify --network ${networkName} ${address} ${zenTokenAddress} ${treasuryAddress}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
