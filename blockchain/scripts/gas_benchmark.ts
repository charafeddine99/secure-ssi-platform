import { ethers } from "hardhat";

async function main() {
  const [owner, user, g1, g2, g3] = await ethers.getSigners();
  const gasResults: Record<string, any> = {};

  // 1. Deploy Contracts
  const DIDFactory = await ethers.getContractFactory("DIDRegistry");
  const didRegistry = await DIDFactory.deploy();
  await didRegistry.waitForDeployment();
  const didDeployReceipt = await didRegistry.deploymentTransaction()?.wait();
  gasResults["DIDRegistry_deployment"] = Number(didDeployReceipt?.gasUsed || 0);

  const RevFactory = await ethers.getContractFactory("RevocationRegistry");
  const revRegistry = await RevFactory.deploy();
  await revRegistry.waitForDeployment();
  const revDeployReceipt = await revRegistry.deploymentTransaction()?.wait();
  gasResults["RevocationRegistry_deployment"] = Number(revDeployReceipt?.gasUsed || 0);

  const RecFactory = await ethers.getContractFactory("EmergencyRecovery");
  const recRegistry = await RecFactory.deploy();
  await recRegistry.waitForDeployment();
  const recDeployReceipt = await recRegistry.deploymentTransaction()?.wait();
  gasResults["EmergencyRecovery_deployment"] = Number(recDeployReceipt?.gasUsed || 0);

  const AuditFactory = await ethers.getContractFactory("AuditLogger");
  const auditLogger = await AuditFactory.deploy();
  await auditLogger.waitForDeployment();
  const auditDeployReceipt = await auditLogger.deploymentTransaction()?.wait();
  gasResults["AuditLogger_deployment"] = Number(auditDeployReceipt?.gasUsed || 0);

  // 2. DID Operations
  const did = "did:key:z6MkhaXgBZDvotDkL5257faiz4898XETow1maK5tMTnSV6DG";
  const initHash = ethers.keccak256(ethers.toUtf8Bytes("genesis_vc_hash"));
  const tx1 = await didRegistry.connect(user).registerDID(did, initHash);
  const r1 = await tx1.wait();
  gasResults["registerDID"] = Number(r1?.gasUsed || 0);

  const updateHash = ethers.keccak256(ethers.toUtf8Bytes("updated_vc_hash"));
  const tx2 = await didRegistry.connect(user).updateVCHash(did, updateHash);
  const r2 = await tx2.wait();
  gasResults["updateVCHash"] = Number(r2?.gasUsed || 0);

  // 3. Revocation & Status Operations
  const statusRoot = ethers.keccak256(ethers.toUtf8Bytes("status_list_root_131072"));
  const tx3 = await revRegistry.connect(owner).anchorStatusList("status-list-2026-batch-1", statusRoot, 131072);
  const r3 = await tx3.wait();
  gasResults["anchorStatusList"] = Number(r3?.gasUsed || 0);

  const credHash = ethers.keccak256(ethers.toUtf8Bytes("revoked_credential_sample"));
  const reasonHash = ethers.keccak256(ethers.toUtf8Bytes("Security Compromise"));
  const tx4 = await revRegistry.connect(owner).revokeCredential(credHash, reasonHash);
  const r4 = await tx4.wait();
  gasResults["revokeCredential"] = Number(r4?.gasUsed || 0);

  // 4. Emergency Recovery Operations
  const tx5 = await recRegistry.connect(user).configureGuardians([g1.address, g2.address, g3.address]);
  const r5 = await tx5.wait();
  gasResults["configureGuardians"] = Number(r5?.gasUsed || 0);

  const newKey = ethers.Wallet.createRandom().address;
  const tx6 = await recRegistry.connect(g1).initiateRecovery(user.address, newKey);
  const r6 = await tx6.wait();
  gasResults["initiateRecovery"] = Number(r6?.gasUsed || 0);

  const tx7 = await recRegistry.connect(g2).approveRecovery(user.address);
  const r7 = await tx7.wait();
  gasResults["approveRecovery_execute"] = Number(r7?.gasUsed || 0);

  // 5. Audit Logging Operations
  const eventHash = ethers.keccak256(ethers.toUtf8Bytes("AI_FRAUD_DETECTED_IP_185.220.101.5"));
  const tx8 = await auditLogger.connect(owner).logEvent(eventHash, 3);
  const r8 = await tx8.wait();
  gasResults["logEvent"] = Number(r8?.gasUsed || 0);

  console.log(JSON.stringify(gasResults, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
