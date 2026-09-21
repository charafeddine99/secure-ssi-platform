// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title DIDRegistry
 * @dev Securely maps users' Decentralized Identifiers (DIDs) and Verifiable Credential (VC) hashes.
 * Enforces that only the identity owner can update or manage their own credential records.
 */
contract DIDRegistry is Ownable, ReentrancyGuard {
    struct DIDRecord {
        address owner;
        bytes32 vcHash;
        uint256 updatedAt;
        bool exists;
    }

    // Mapping from DID string (e.g. "did:key:z6Mku...") to its corresponding record
    mapping(string => DIDRecord) private _didRecords;

    // Optional reverse lookup: wallet address => DID string
    mapping(address => string) private _ownerToDID;

    // Events
    event DIDRegistered(string indexed did, address indexed owner, bytes32 vcHash, uint256 timestamp);
    event VCHashUpdated(string indexed did, address indexed owner, bytes32 newVcHash, uint256 timestamp);
    event DIDTransferred(string indexed did, address indexed previousOwner, address indexed newOwner, uint256 timestamp);

    modifier onlyDIDOwner(string calldata did) {
        require(_didRecords[did].exists, "DIDRegistry: DID not registered");
        require(_didRecords[did].owner == msg.sender, "DIDRegistry: Only the identity owner can perform this action");
        _;
    }

    constructor() Ownable(msg.sender) {}

    /**
     * @notice Registers a new DID and binds an initial Verifiable Credential (VC) hash.
     * @param did The decentralized identifier string.
     * @param vcHash SHA-256 or Keccak-256 hash of the initial Verifiable Credential.
     */
    function registerDID(string calldata did, bytes32 vcHash) external nonReentrant {
        require(bytes(did).length > 0, "DIDRegistry: DID string cannot be empty");
        require(!_didRecords[did].exists, "DIDRegistry: DID is already registered");
        require(vcHash != bytes32(0), "DIDRegistry: Invalid VC hash");

        _didRecords[did] = DIDRecord({
            owner: msg.sender,
            vcHash: vcHash,
            updatedAt: block.timestamp,
            exists: true
        });

        _ownerToDID[msg.sender] = did;

        emit DIDRegistered(did, msg.sender, vcHash, block.timestamp);
    }

    /**
     * @notice Updates the Verifiable Credential hash associated with a DID.
     * Only the recorded owner of the DID is permitted to update.
     * @param did The decentralized identifier string.
     * @param newVcHash The new hash of the updated or newly issued Verifiable Credential.
     */
    function updateVCHash(string calldata did, bytes32 newVcHash) external onlyDIDOwner(did) nonReentrant {
        require(newVcHash != bytes32(0), "DIDRegistry: Invalid new VC hash");
        require(newVcHash != _didRecords[did].vcHash, "DIDRegistry: New VC hash must be different from current hash");

        _didRecords[did].vcHash = newVcHash;
        _didRecords[did].updatedAt = block.timestamp;

        emit VCHashUpdated(did, msg.sender, newVcHash, block.timestamp);
    }

    /**
     * @notice Transfers ownership of a DID record to a new address (e.g. after emergency recovery).
     * @param did The decentralized identifier string.
     * @param newOwner The address of the new identity owner.
     */
    function transferDIDOwnership(string calldata did, address newOwner) external onlyDIDOwner(did) nonReentrant {
        require(newOwner != address(0), "DIDRegistry: New owner cannot be zero address");
        require(newOwner != msg.sender, "DIDRegistry: New owner must be different from current owner");

        address previousOwner = _didRecords[did].owner;
        _didRecords[did].owner = newOwner;
        _didRecords[did].updatedAt = block.timestamp;

        delete _ownerToDID[previousOwner];
        _ownerToDID[newOwner] = did;

        emit DIDTransferred(did, previousOwner, newOwner, block.timestamp);
    }

    /**
     * @notice Returns the record for a given DID string.
     * @param did The decentralized identifier string.
     * @return owner The Ethereum address controlling the DID.
     * @return vcHash The stored Verifiable Credential hash.
     * @return updatedAt Unix timestamp of the last update.
     */
    function getDIDRecord(string calldata did) external view returns (address owner, bytes32 vcHash, uint256 updatedAt) {
        require(_didRecords[did].exists, "DIDRegistry: DID not found");
        DIDRecord memory rec = _didRecords[did];
        return (rec.owner, rec.vcHash, rec.updatedAt);
    }

    /**
     * @notice Reverse lookup to retrieve the DID associated with a wallet address.
     * @param owner The wallet address to query.
     */
    function getDIDByOwner(address owner) external view returns (string memory did, bytes32 vcHash, uint256 updatedAt) {
        did = _ownerToDID[owner];
        require(bytes(did).length > 0, "DIDRegistry: No DID found for this owner");
        DIDRecord memory rec = _didRecords[did];
        return (did, rec.vcHash, rec.updatedAt);
    }

    /**
     * @notice Checks if a DID is registered.
     */
    function isDIDRegistered(string calldata did) external view returns (bool) {
        return _didRecords[did].exists;
    }
}
