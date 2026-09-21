import { ethers, run, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("==================================================================");
  console.log("🚀 Starting Deployment to Ethereum Sepolia Testnet");
  console.log(`Network:          ${network.name} (Chain ID: ${network.config.chainId})`);
  console.log(`Deployer Address: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Deployer Balance: ${ethers.formatEther(balance)} ETH`);

  if (balance === 0n) {
    console.warn("⚠️  WARNING: Deployer account balance is 0 ETH. You need Sepolia testnet ETH to proceed!");
  }
  console.log("==================================================================\n");

  // -------------------------------------------------------------
  // 1. Deploy DIDRegistry.sol
  // -------------------------------------------------------------
  console.log("1️⃣  Deploying DIDRegistry.sol...");
  const DIDRegistryFactory = await ethers.getContractFactory("DIDRegistry");
  const didRegistry = await DIDRegistryFactory.deploy();
  await didRegistry.waitForDeployment();
  const didRegistryAddress = await didRegistry.getAddress();
  console.log(`   ✅ DIDRegistry deployed at: ${didRegistryAddress}`);

  // -------------------------------------------------------------
  // 2. Deploy EmergencyRecovery.sol
  // -------------------------------------------------------------
  console.log("\n2️⃣  Deploying EmergencyRecovery.sol (2-of-3 Multi-Sig Recovery)...");
  const EmergencyRecoveryFactory = await ethers.getContractFactory("EmergencyRecovery");
  const emergencyRecovery = await EmergencyRecoveryFactory.deploy();
  await emergencyRecovery.waitForDeployment();
  const emergencyRecoveryAddress = await emergencyRecovery.getAddress();
  console.log(`   ✅ EmergencyRecovery deployed at: ${emergencyRecoveryAddress}`);

  // -------------------------------------------------------------
  // 3. Save Deployment Artifacts to JSON
  // -------------------------------------------------------------
  const deploymentInfo = {
    network: network.name,
    chainId: network.config.chainId,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contracts: {
      DIDRegistry: {
        address: didRegistryAddress,
        etherscanUrl: `https://sepolia.etherscan.io/address/${didRegistryAddress}`
      },
      EmergencyRecovery: {
        address: emergencyRecoveryAddress,
        etherscanUrl: `https://sepolia.etherscan.io/address/${emergencyRecoveryAddress}`
      }
    }
  };

  const outputPath = path.join(__dirname, "../deployed-sepolia-contracts.json");
  fs.writeFileSync(outputPath, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\n💾 Saved Sepolia deployment metadata to:\n   ${outputPath}`);

  // -------------------------------------------------------------
  // 4. Automated Etherscan Verification
  // -------------------------------------------------------------
  if (network.name === "sepolia") {
    console.log("\n⏳ Waiting for 5 block confirmations to ensure bytecode is indexed by Etherscan...");

    const deployTx1 = didRegistry.deploymentTransaction();
    if (deployTx1) await deployTx1.wait(5);

    const deployTx2 = emergencyRecovery.deploymentTransaction();
    if (deployTx2) await deployTx2.wait(5);

    console.log("🔍 Verifying DIDRegistry on Etherscan...");
    try {
      await run("verify:verify", {
        address: didRegistryAddress,
        constructorArguments: [],
      });
      console.log("   ✅ DIDRegistry verified successfully on Etherscan!");
    } catch (err: any) {
      if (err.message.toLowerCase().includes("already verified")) {
        console.log("   ℹ️  DIDRegistry is already verified on Etherscan.");
      } else {
        console.error("   ❌ DIDRegistry verification error:", err.message);
      }
    }

    console.log("\n🔍 Verifying EmergencyRecovery on Etherscan...");
    try {
      await run("verify:verify", {
        address: emergencyRecoveryAddress,
        constructorArguments: [],
      });
      console.log("   ✅ EmergencyRecovery verified successfully on Etherscan!");
    } catch (err: any) {
      if (err.message.toLowerCase().includes("already verified")) {
        console.log("   ℹ️  EmergencyRecovery is already verified on Etherscan.");
      } else {
        console.error("   ❌ EmergencyRecovery verification error:", err.message);
      }
    }
  } else {
    console.log("\n💡 Skipping Etherscan verification (not on live Sepolia network).");
  }

  console.log("\n==================================================================");
  console.log("🎉 Sepolia Deployment Workflow Completed Successfully!");
  console.log(`🔗 DIDRegistry Etherscan:       https://sepolia.etherscan.io/address/${didRegistryAddress}`);
  console.log(`🔗 EmergencyRecovery Etherscan: https://sepolia.etherscan.io/address/${emergencyRecoveryAddress}`);
  console.log("==================================================================");
}

main().catch((error) => {
  console.error("❌ Sepolia Deployment failed:", error);
  process.exitCode = 1;
});
