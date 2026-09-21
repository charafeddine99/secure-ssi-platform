import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-toolbox/network-helpers";

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

      const [controller, storedHash, , active] = await didRegistry.getDID(did);
      expect(controller).to.equal(user.address);
      expect(storedHash).to.equal(docHash);
      expect(active).to.be.true;
    });

    it("should prevent unauthorized updates to a DID", async function () {
      const did = "did:key:z6MkuUserTestDID456";
      const docHash = ethers.keccak256(ethers.toUtf8Bytes("Initial-Doc"));
      await didRegistry.connect(user).registerDID(did, docHash);

      const attacker = guardians[0];
      const newHash = ethers.keccak256(ethers.toUtf8Bytes("Malicious-Update"));

      await expect(
        didRegistry.connect(attacker).updateDID(did, newHash)
      ).to.be.revertedWith("DIDRegistry: Yalnizca controller guncelleyebilir");
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

  describe("EmergencyRecovery (3/5 Guardian Social Recovery & Time-Lock)", function () {
    const timeLockSeconds = 3600; // 1 saatlik time-lock

    beforeEach(async function () {
      const guardianAddresses = guardians.map((g) => g.address);
      // Kullanıcı 5 guardian ile 3 onay eşiği ve 1 saatlik time-lock tanımlıyor
      await emergencyRecovery.connect(user).configureRecovery(guardianAddresses, 3, timeLockSeconds);
    });

    it("should successfully execute recovery only after 3/5 guardian approvals and time-lock expiry", async function () {
      const newKey = ethers.Wallet.createRandom().address;

      // 1. Guardian 1 recovery başlatır (otomatik 1. onay verilir)
      await emergencyRecovery.connect(guardians[0]).initiateRecovery(user.address, newKey);

      let req = await emergencyRecovery.activeRequests(user.address);
      expect(req.approvalCount).to.equal(1);

      // 2. Guardian 2 onay verir (toplam 2 onay)
      await emergencyRecovery.connect(guardians[1]).approveRecovery(user.address);
      req = await emergencyRecovery.activeRequests(user.address);
      expect(req.approvalCount).to.equal(2);

      // 2 onay varken execute çağrılırsa eşik yetersizliğinden revert olmalı
      await expect(
        emergencyRecovery.executeRecovery(user.address)
      ).to.be.revertedWith("EmergencyRecovery: Yetersiz guardian onayi (M-of-N saglanmadi)");

      // 3. Guardian 3 onay verir (toplam 3/5 onay tamamlandı!)
      await emergencyRecovery.connect(guardians[2]).approveRecovery(user.address);
      req = await emergencyRecovery.activeRequests(user.address);
      expect(req.approvalCount).to.equal(3);

      // 3 onay var ancak Time-Lock henüz dolmadıysa revert olmalı
      await expect(
        emergencyRecovery.executeRecovery(user.address)
      ).to.be.revertedWith("EmergencyRecovery: Time-lock suresi henuz dolmadi");

      // 4. Zamanı 3601 saniye ileri sar (Time-lock biter)
      await time.increase(timeLockSeconds + 1);

      // 5. Artık başarıyla icra edilebilir
      const tx = await emergencyRecovery.executeRecovery(user.address);
      const receipt = await tx.wait();
      expect(receipt.status).to.equal(1);

      req = await emergencyRecovery.activeRequests(user.address);
      expect(req.executed).to.be.true;
    });

    it("should allow wallet owner to cancel an unauthorized recovery attempt", async function () {
      const newKey = ethers.Wallet.createRandom().address;
      await emergencyRecovery.connect(guardians[0]).initiateRecovery(user.address, newKey);

      // Cüzdan sahibi anında iptal eder
      await emergencyRecovery.connect(user).cancelRecovery(user.address);

      const req = await emergencyRecovery.activeRequests(user.address);
      expect(req.cancelled).to.be.true;
    });
  });

  describe("AuditLogger & Gas Efficiency Benchmark", function () {
    it("should log security events and confirm gas efficiency", async function () {
      const eventHash = ethers.keccak256(ethers.toUtf8Bytes("AI_FRAUD_DETECTED_IP_185.220.101.5"));
      const category = 3; // FRAUD_DETECTED

      const tx = await auditLogger.connect(owner).logEvent(eventHash, category);
      const receipt = await tx.wait();

      expect(receipt.status).to.equal(1);
      expect(await auditLogger.totalRecords()).to.equal(1);

      // Gas kullanımı rapor hedefiyle (< 150,000 gas, ~0.00036 ETH L2/Testnet) uyumlu mu?
      const gasUsed = receipt.gasUsed;
      expect(gasUsed).to.be.lessThan(150000n);
    });
  });
});
