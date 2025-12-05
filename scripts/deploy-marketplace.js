const hre = require("hardhat");

async function main() {
  const networkName = hre.network.name;
  console.log(`Deploying NFTMarketplace to ${networkName}...`);

  // Get addresses - hardcoded to ensure correctness
  const [deployer] = await hre.ethers.getSigners();
  const zenTokenAddress = "0x070040A826B586b58569750ED43cb5979b171e8d";
  const nftContractAddress = "0x57e277b2d887C3C749757e36F0B6CFad32E00e8A";
  const treasuryAddress = "0xe928a273C83c80445adF89a880D0c7cc8Ee089b0";

  if (!zenTokenAddress) {
    throw new Error("ZEN_TOKEN_ADDRESS not set in .env file!");
  }
  if (!nftContractAddress) {
    throw new Error("NFT_CONTRACT_ADDRESS not set in .env file!");
  }

  console.log("ZEN Token address:", zenTokenAddress);
  console.log("NFT Contract address:", nftContractAddress);
  console.log("Treasury address:", treasuryAddress);

  // Marketplace fee: 500 = 5%
  const marketplaceFee = 500;
  console.log("Marketplace fee:", marketplaceFee, "basis points (5%)");

  // Get the contract factory
  const NFTMarketplace = await hre.ethers.getContractFactory("NFTMarketplace");

  // Deploy the contract
  const marketplace = await NFTMarketplace.deploy(
    zenTokenAddress,
    nftContractAddress,
    treasuryAddress,
    marketplaceFee
  );

  await marketplace.waitForDeployment();

  const address = await marketplace.getAddress();

  console.log("NFTMarketplace deployed to:", address);
  console.log("\nAdd this to your .env file:");
  console.log(`MARKETPLACE_CONTRACT_ADDRESS=${address}`);

  console.log("\nWaiting for block confirmations...");
  await marketplace.deploymentTransaction().wait(5);

  console.log("\nDeployment complete!");
  console.log("\nTo verify on block explorer, run:");
  console.log(`npx hardhat verify --network ${networkName} ${address} ${zenTokenAddress} ${nftContractAddress} ${treasuryAddress} ${marketplaceFee}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
