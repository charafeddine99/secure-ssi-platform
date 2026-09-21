import { expect } from "chai";
import { ethers } from "hardhat";

describe("Layer 1: Blockchain Layer - DIDRegistry & EmergencyRecovery", function () {
  let didRegistry: any;
  let emergencyRecovery: any;
  let deployer: any;
  let alice: any;
  let bob: any;
  let guardianA: any;
  let guardianB: any;
  let guardianC: any;
  let attacker: any;

  beforeEach(async function () {
    const signers = await ethers.getSigners();
    deployer = signers[0];
    alice = signers[1];
    bob = signers[2];
    guardianA = signers[3];
    guardianB = signers[4];
    guardianC = signers[5];
    attacker = signers[6];

    // Deploy DIDRegistry
    const DIDRegistryFactory = await ethers.getContractFactory("DIDRegistry");
    didRegistry = await DIDRegistryFactory.deploy();
    await didRegistry.waitForDeployment();

    // Deploy EmergencyRecovery
    const EmergencyRecoveryFactory = await ethers.getContractFactory("EmergencyRecovery");
    emergencyRecovery = await EmergencyRecoveryFactory.deploy();
    await emergencyRecovery.waitForDeployment();
  });

  describe("DIDRegistry Contract", function () {
    const did = "did:ssi:alice:001";
    const initialVcHash = ethers.keccak256(ethers.toUtf8Bytes("VerifiableCredential_Alice_Degree_v1"));
    const updatedVcHash = ethers.keccak256(ethers.toUtf8Bytes("VerifiableCredential_Alice_Degree_v2"));

    it("should allow a user to register a DID with initial VC hash", async function () {
      const tx = await didRegistry.connect(alice).registerDID(did, initialVcHash);
      await tx.wait();

      expect(await didRegistry.isDIDRegistered(did)).to.be.true;

      const [owner, vcHash, updatedAt] = await didRegistry.getDIDRecord(did);
      expect(owner).to.equal(alice.address);
      expect(vcHash).to.equal(initialVcHash);
      expect(updatedAt).to.be.gt(0);

      const [retrievedDid, retHash] = await didRegistry.getDIDByOwner(alice.address);
      expect(retrievedDid).to.equal(did);
      expect(retHash).to.equal(initialVcHash);
    });

    it("should prevent duplicate DID registration", async function () {
      await didRegistry.connect(alice).registerDID(did, initialVcHash);

      await expect(
        didRegistry.connect(alice).registerDID(did, initialVcHash)
      ).to.be.revertedWith("DIDRegistry: DID is already registered");
    });

    it("should allow ONLY the identity owner to update their VC hash", async function () {
      await didRegistry.connect(alice).registerDID(did, initialVcHash);

      // Non-owner attacker tries to update VC hash
      await expect(
        didRegistry.connect(attacker).updateVCHash(did, updatedVcHash)
      ).to.be.revertedWith("DIDRegistry: Only the identity owner can perform this action");

      // Identity owner Alice updates VC hash
      await didRegistry.connect(alice).updateVCHash(did, updatedVcHash);
      const [, newHash] = await didRegistry.getDIDRecord(did);
      expect(newHash).to.equal(updatedVcHash);
    });

    it("should allow transferring DID ownership to a new address", async function () {
      await didRegistry.connect(alice).registerDID(did, initialVcHash);

      // Alice transfers ownership to Bob
      await didRegistry.connect(alice).transferDIDOwnership(did, bob.address);

      const [newOwner] = await didRegistry.getDIDRecord(did);
      expect(newOwner).to.equal(bob.address);

      // Alice cannot update anymore
      await expect(
        didRegistry.connect(alice).updateVCHash(did, updatedVcHash)
      ).to.be.revertedWith("DIDRegistry: Only the identity owner can perform this action");

      // Bob (new owner) can now update
      await didRegistry.connect(bob).updateVCHash(did, updatedVcHash);
      const [, verifiedHash] = await didRegistry.getDIDRecord(did);
      expect(verifiedHash).to.equal(updatedVcHash);
    });
  });

  describe("EmergencyRecovery Contract - 2-out-of-3 Multi-Sig Guardian Recovery", function () {
    let aliceGuardians: [string, string, string];

    beforeEach(async function () {
      aliceGuardians = [guardianA.address, guardianB.address, guardianC.address];
      // Alice configures her 3 guardians
      await emergencyRecovery.connect(alice).configureGuardians(aliceGuardians);
    });

    it("should properly configure 3 guardians for the wallet", async function () {
      expect(await emergencyRecovery.isWalletConfigured(alice.address)).to.be.true;
      expect(await emergencyRecovery.getWalletOwner(alice.address)).to.equal(alice.address);

      const storedGuardians = await emergencyRecovery.getGuardians(alice.address);
      expect(storedGuardians[0]).to.equal(guardianA.address);
      expect(storedGuardians[1]).to.equal(guardianB.address);
      expect(storedGuardians[2]).to.equal(guardianC.address);

      expect(await emergencyRecovery.isGuardianOf(alice.address, guardianA.address)).to.be.true;
      expect(await emergencyRecovery.isGuardianOf(alice.address, attacker.address)).to.be.false;
    });

    it("should reject re-configuration of guardians", async function () {
      await expect(
        emergencyRecovery.connect(alice).configureGuardians(aliceGuardians)
      ).to.be.revertedWith("EmergencyRecovery: Wallet guardians already configured");
    });

    it("should prevent non-guardians from initiating recovery", async function () {
      await expect(
        emergencyRecovery.connect(attacker).initiateRecovery(alice.address, bob.address)
      ).to.be.revertedWith("EmergencyRecovery: Caller is not an authorized guardian");
    });

    it("should initiate recovery with 1 approval from initiator guardian", async function () {
      await emergencyRecovery.connect(guardianA).initiateRecovery(alice.address, bob.address);

      const [proposedOwner, approvalCount, executed, active] =
        await emergencyRecovery.getRecoveryStatus(alice.address);

      expect(proposedOwner).to.equal(bob.address);
      expect(approvalCount).to.equal(1);
      expect(executed).to.be.false;
      expect(active).to.be.true;
      expect(await emergencyRecovery.hasGuardianApproved(alice.address, guardianA.address)).to.be.true;
      expect(await emergencyRecovery.hasGuardianApproved(alice.address, guardianB.address)).to.be.false;
    });

    it("should reject duplicate approval from the same guardian", async function () {
      await emergencyRecovery.connect(guardianA).initiateRecovery(alice.address, bob.address);

      await expect(
        emergencyRecovery.connect(guardianA).approveRecovery(alice.address)
      ).to.be.revertedWith("EmergencyRecovery: Guardian has already approved this request");
    });

    it("should transfer ownership when 2-out-of-3 guardians approve (multi-sig threshold met)", async function () {
      // 1. Guardian A initiates recovery to Bob (Approval 1 of 3)
      await emergencyRecovery.connect(guardianA).initiateRecovery(alice.address, bob.address);

      // Ownership not yet transferred
      expect(await emergencyRecovery.getWalletOwner(alice.address)).to.equal(alice.address);

      // 2. Guardian B approves recovery (Approval 2 of 3 -> REACHES 2-OF-3 THRESHOLD!)
      const approveTx = await emergencyRecovery.connect(guardianB).approveRecovery(alice.address);
      const receipt = await approveTx.wait();
      expect(receipt.status).to.equal(1);

      // Verify wallet ownership is now successfully transferred to Bob!
      expect(await emergencyRecovery.getWalletOwner(alice.address)).to.equal(bob.address);

      const [proposedOwner, approvalCount, executed, active] =
        await emergencyRecovery.getRecoveryStatus(alice.address);
      expect(proposedOwner).to.equal(bob.address);
      expect(approvalCount).to.equal(2);
      expect(executed).to.be.true;
      expect(active).to.be.false;
    });

    it("should allow wallet owner to cancel an unauthorized recovery attempt before threshold is met", async function () {
      // Guardian A initiates recovery maliciously or prematurely
      await emergencyRecovery.connect(guardianA).initiateRecovery(alice.address, attacker.address);

      // Alice detects unauthorized attempt and cancels it
      await emergencyRecovery.connect(alice).cancelRecovery(alice.address);

      const [, , executed, active] = await emergencyRecovery.getRecoveryStatus(alice.address);
      expect(active).to.be.false;
      expect(executed).to.be.false;

      // Ownership remains with Alice
      expect(await emergencyRecovery.getWalletOwner(alice.address)).to.equal(alice.address);

      // Other guardians cannot approve an inactive request
      await expect(
        emergencyRecovery.connect(guardianB).approveRecovery(alice.address)
      ).to.be.revertedWith("EmergencyRecovery: No active recovery request found");
    });

    it("should support AI-driven quarantine trigger on high fraud risk", async function () {
      // Contract owner (platform admin) quarantines Alice's wallet due to AI risk > 70
      await emergencyRecovery.connect(deployer).quarantineWallet(alice.address, "AI Risk Score 88 - Suspicious IP");
      expect(await emergencyRecovery.isWalletQuarantined(alice.address)).to.be.true;

      // Lift quarantine after verification
      await emergencyRecovery.connect(deployer).unquarantineWallet(alice.address);
      expect(await emergencyRecovery.isWalletQuarantined(alice.address)).to.be.false;

      // Attacker cannot trigger quarantine
      await expect(
        emergencyRecovery.connect(attacker).quarantineWallet(alice.address, "Malicious quarantine")
      ).to.be.revertedWithCustomError(emergencyRecovery, "OwnableUnauthorizedAccount");
    });
  });
});
