const hre = require("hardhat");

async function main() {
  const network = hre.network.name;
  console.log(`\n🚀 Deploying DAMNMemory to ${network}...`);

  const DAMNMemory = await hre.ethers.getContractFactory("DAMNMemory");
  const damn = await DAMNMemory.deploy();
  await damn.waitForDeployment();

  const address = await damn.getAddress();
  console.log(`✅ DAMNMemory deployed to: ${address}`);
  console.log(`🔗 Explorer: ${getExplorer(network)}/address/${address}`);
  console.log(`\n📝 Add to .env:`);
  console.log(`CONTRACT_ADDRESS_${network.toUpperCase()}=${address}`);
}

function getExplorer(network) {
  const explorers = {
    sepolia: "https://sepolia.etherscan.io",
    polygon: "https://polygonscan.com",
    base:    "https://basescan.org"
  };
  return explorers[network] || "https://etherscan.io";
}

main().catch((e) => { console.error(e); process.exit(1); });