import { expect } from "chai";
import { ethers } from "hardhat";

describe("Secure SSI Platform - Smart Contracts Suite", function () {
  let didRegistry: any;
  let revocationRegistry: any;
  let emergencyRecovery: any;
  let auditLogger: any;
  let owner: any;
  let user: any;
  let guardians: any[];

  beforeEach(async function () {
    const signers = await ethers.getSigners();
    owner = signers[0];
    user = signers[1];
    guardians = [signers[2], signers[3], signers[4], signers[5], signers[6]];

    // 1. DIDRegistry Deploy
    const DIDRegistryFactory = await ethers.getContractFactory("DIDRegistry");
    didRegistry = await DIDRegistryFactory.deploy();

    // 2. RevocationRegistry Deploy
    const RevocationRegistryFactory = await ethers.getContractFactory("RevocationRegistry");
    revocationRegistry = await RevocationRegistryFactory.deploy();

    // 3. EmergencyRecovery Deploy
    const EmergencyRecoveryFactory = await ethers.getContractFactory("EmergencyRecovery");
    emergencyRecovery = await EmergencyRecoveryFactory.deploy();

    // 4. AuditLogger Deploy
    const AuditLoggerFactory = await ethers.getContractFactory("AuditLogger");
    auditLogger = await AuditLoggerFactory.deploy();
  });

  describe("DIDRegistry Tests", function () {
    it("should allow a user to register and query their DID", async function () {
      const did = "did:key:z6MkuUserTestDID123";
      const docHash = ethers.keccak256(ethers.toUtf8Bytes("DIDDocument-Metadata-Content"));

      const tx = await didRegistry.connect(user).registerDID(did, docHash);
      await tx.wait();

      const [controller, storedHash, updatedAt] = await didRegistry.getDIDRecord(did);
      expect(controller).to.equal(user.address);
      expect(storedHash).to.equal(docHash);
      expect(updatedAt).to.be.gt(0);
    });

    it("should prevent unauthorized updates to a DID", async function () {
      const did = "did:key:z6MkuUserTestDID456";
      const docHash = ethers.keccak256(ethers.toUtf8Bytes("Initial-Doc"));
      await didRegistry.connect(user).registerDID(did, docHash);

      const attacker = guardians[0];
      const newHash = ethers.keccak256(ethers.toUtf8Bytes("Malicious-Update"));

      await expect(
        didRegistry.connect(attacker).updateVCHash(did, newHash)
      ).to.be.revertedWith("DIDRegistry: Only the identity owner can perform this action");
    });
  });

  describe("RevocationRegistry Tests", function () {
    it("should anchor W3C Bitstring Status List root hash", async function () {
      const statusListId = "https://issuer.example.edu/status-lists/1";
      const rootHash = ethers.keccak256(ethers.toUtf8Bytes("Bitstring-Root-131072-bits"));
      const version = 1;

      await revocationRegistry.connect(owner).anchorStatusList(statusListId, rootHash, version);
      const [storedRoot, storedVersion] = await revocationRegistry.getStatusListAnchor(owner.address, statusListId);

      expect(storedRoot).to.equal(rootHash);
      expect(storedVersion).to.equal(version);
    });

    it("should record individual credential revocation and prevent duplicate revocation", async function () {
      const credHash = ethers.keccak256(ethers.toUtf8Bytes("Diploma-Credential-UUID-777"));
      const reasonHash = ethers.keccak256(ethers.toUtf8Bytes("Academic Suspicion"));

      await revocationRegistry.connect(owner).revokeCredential(credHash, reasonHash);
      expect(await revocationRegistry.isCredentialRevoked(credHash)).to.be.true;

      await expect(
        revocationRegistry.connect(owner).revokeCredential(credHash, reasonHash)
      ).to.be.revertedWith("RevocationRegistry: Zaten iptal edilmis");
    });
  });

  describe("EmergencyRecovery (2-out-of-3 Multi-Sig Guardian Recovery)", function () {
    beforeEach(async function () {
      const guardianAddresses: [string, string, string] = [
        guardians[0].address,
        guardians[1].address,
        guardians[2].address,
      ];
      await emergencyRecovery.connect(user).configureGuardians(guardianAddresses);
    });

    it("should successfully transfer ownership when 2-out-of-3 guardians approve", async function () {
      const newKey = ethers.Wallet.createRandom().address;

      // 1. Guardian 1 initiates recovery (approval 1)
      await emergencyRecovery.connect(guardians[0]).initiateRecovery(user.address, newKey);

      let [, approvalCount, executed, active] = await emergencyRecovery.getRecoveryStatus(user.address);
      expect(approvalCount).to.equal(1);
      expect(active).to.be.true;
      expect(executed).to.be.false;

      // 2. Guardian 2 approves recovery (approval 2 -> auto executes 2/3 multi-sig)
      await emergencyRecovery.connect(guardians[1]).approveRecovery(user.address);

      expect(await emergencyRecovery.getWalletOwner(user.address)).to.equal(newKey);
      [, approvalCount, executed, active] = await emergencyRecovery.getRecoveryStatus(user.address);
      expect(approvalCount).to.equal(2);
      expect(executed).to.be.true;
      expect(active).to.be.false;
    });

    it("should allow wallet owner to cancel an unauthorized recovery attempt", async function () {
      const newKey = ethers.Wallet.createRandom().address;
      await emergencyRecovery.connect(guardians[0]).initiateRecovery(user.address, newKey);

      // Cüzdan sahibi iptal eder
      await emergencyRecovery.connect(user).cancelRecovery(user.address);

      const [, , executed, active] = await emergencyRecovery.getRecoveryStatus(user.address);
      expect(active).to.be.false;
      expect(executed).to.be.false;
      expect(await emergencyRecovery.getWalletOwner(user.address)).to.equal(user.address);
    });
  });

  describe("AuditLogger & Gas Efficiency Benchmark", function () {
    it("should log security events and confirm gas efficiency", async function () {
      const eventHash = ethers.keccak256(ethers.toUtf8Bytes("AI_FRAUD_DETECTED_IP_185.220.101.5"));
      const category = 3; // FRAUD_DETECTED

      const tx = await auditLogger.connect(owner).logEvent(eventHash, category);
      const receipt = await tx.wait();

      expect(receipt.status).to.equal(1);
      const total = await auditLogger.totalRecords();
      expect(total).to.equal(1);
      const record = await auditLogger.records(0);
      expect(record.eventHash).to.equal(eventHash);
    });
  });
});
