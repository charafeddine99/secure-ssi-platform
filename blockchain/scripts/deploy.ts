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

  // 2. Deploy RevocationRegistry (W3C Bitstring Status List & Credential Revocation)
  console.log("2. Deploying RevocationRegistry...");
  const RevocationRegistryFactory = await ethers.getContractFactory("RevocationRegistry");
  const revocationRegistry = await RevocationRegistryFactory.deploy();
  await revocationRegistry.waitForDeployment();
  const revocationRegistryAddress = await revocationRegistry.getAddress();
  console.log(`   RevocationRegistry deployed at: ${revocationRegistryAddress}`);

  // 3. Deploy EmergencyRecovery (2-out-of-3 Multi-Sig Guardian Recovery & AI Quarantine)
  console.log("3. Deploying EmergencyRecovery...");
  const EmergencyRecoveryFactory = await ethers.getContractFactory("EmergencyRecovery");
  const emergencyRecovery = await EmergencyRecoveryFactory.deploy();
  await emergencyRecovery.waitForDeployment();
  const emergencyRecoveryAddress = await emergencyRecovery.getAddress();
  console.log(`   EmergencyRecovery deployed at: ${emergencyRecoveryAddress}`);

  // 4. Deploy AuditLogger (Tamper-evident Security & Audit Event Hashes)
  console.log("4. Deploying AuditLogger...");
  const AuditLoggerFactory = await ethers.getContractFactory("AuditLogger");
  const auditLogger = await AuditLoggerFactory.deploy();
  await auditLogger.waitForDeployment();
  const auditLoggerAddress = await auditLogger.getAddress();
  console.log(`   AuditLogger deployed at: ${auditLoggerAddress}`);

  // Deployment Summary & Local JSON Artifact
  const deploymentInfo = {
    network: (await ethers.provider.getNetwork()).name,
    chainId: (await ethers.provider.getNetwork()).chainId.toString(),
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contracts: {
      DIDRegistry: didRegistryAddress,
      RevocationRegistry: revocationRegistryAddress,
      EmergencyRecovery: emergencyRecoveryAddress,
      AuditLogger: auditLoggerAddress,
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
