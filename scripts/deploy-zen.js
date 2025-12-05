const hre = require("hardhat");

async function main() {
  const networkName = hre.network.name;
  console.log(`Deploying ZEN Token to ${networkName}...`);

  // Get the contract factory
  const ZENToken = await hre.ethers.getContractFactory("ZENToken");

  // Deploy the contract
  const zenToken = await ZENToken.deploy();

  await zenToken.waitForDeployment();

  const address = await zenToken.getAddress();

  console.log("✅ ZEN Token deployed to:", address);
  console.log("\nAdd this to your .env file:");
  console.log(`ZEN_TOKEN_ADDRESS=${address}`);

  console.log("\nWaiting for block confirmations...");
  await zenToken.deploymentTransaction().wait(5);

  console.log("\n✅ Deployment complete!");
  console.log("\nTo verify on block explorer, run:");
  console.log(`npx hardhat verify --network ${networkName} ${address}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
