import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("=================================================");
  console.log("Deploying Layer 1: Blockchain Layer Smart Contracts");
  console.log(`Deployer address: ${deployer.address}`);
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Deployer balance: ${ethers.formatEther(balance)} ETH`);
  console.log("=================================================");

  // 1. Deploy DIDRegistry
  console.log("1. Deploying DIDRegistry...");
  const DIDRegistryFactory = await ethers.getContractFactory("DIDRegistry");
  const didRegistry = await DIDRegistryFactory.deploy();
  await didRegistry.waitForDeployment();
  const didRegistryAddress = await didRegistry.getAddress();
  console.log(`   DIDRegistry deployed at: ${didRegistryAddress}`);

  // 2. Deploy EmergencyRecovery (2-out-of-3 Multi-Sig Guardian Recovery)
  console.log("2. Deploying EmergencyRecovery...");
  const EmergencyRecoveryFactory = await ethers.getContractFactory("EmergencyRecovery");
  const emergencyRecovery = await EmergencyRecoveryFactory.deploy();
  await emergencyRecovery.waitForDeployment();
  const emergencyRecoveryAddress = await emergencyRecovery.getAddress();
  console.log(`   EmergencyRecovery deployed at: ${emergencyRecoveryAddress}`);

  // Deployment Summary & Local JSON Artifact
  const deploymentInfo = {
    network: (await ethers.provider.getNetwork()).name,
    chainId: (await ethers.provider.getNetwork()).chainId.toString(),
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contracts: {
      DIDRegistry: didRegistryAddress,
      EmergencyRecovery: emergencyRecoveryAddress,
    },
  };

  const outputPath = path.join(__dirname, "../deployed-contracts.json");
  fs.writeFileSync(outputPath, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\nDeployment metadata saved to: ${outputPath}`);

  console.log("=================================================");
  console.log("Layer 1 Contracts Successfully Deployed!");
  console.log("=================================================");
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
