// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title DIDRegistry
 * @dev W3C DID Core uyumlu merkeziyetsiz kimlik kayıt akıllı sözleşmesi.
 * Gizlilik ilkesi gereği ham kimlik verisi zincire yazılmaz, yalnızca SHA-256/keccak256 belge özeti saklanır.
 */
contract DIDRegistry {
    struct DIDRecord {
        address controller;
        bytes32 docHash;
        uint256 updatedAt;
        bool active;
    }

    // DID string => DIDRecord
    mapping(string => DIDRecord) private _dids;

    event DIDRegistered(string indexed did, address indexed controller, bytes32 docHash, uint256 timestamp);
    event DIDUpdated(string indexed did, address indexed controller, bytes32 newDocHash, uint256 timestamp);
    event DIDDeactivated(string indexed did, address indexed controller, uint256 timestamp);

    modifier onlyController(string memory did) {
        require(_dids[did].controller == msg.sender, "DIDRegistry: Yalnizca controller guncelleyebilir");
        _;
    }

    /**
     * @notice Yeni bir DID ve belge özetini zincirde tescil eder.
     */
    function registerDID(string calldata did, bytes32 docHash) external {
        require(_dids[did].controller == address(0), "DIDRegistry: DID zaten kayitli");
        require(docHash != bytes32(0), "DIDRegistry: Gecersiz belge ozeti");

        _dids[did] = DIDRecord({
            controller: msg.sender,
            docHash: docHash,
            updatedAt: block.timestamp,
            active: true
        });

        emit DIDRegistered(did, msg.sender, docHash, block.timestamp);
    }

    /**
     * @notice Mevcut bir DID'nin belge özetini günceller.
     */
    function updateDID(string calldata did, bytes32 newDocHash) external onlyController(did) {
        require(_dids[did].active, "DIDRegistry: DID pasif durumda");
        require(newDocHash != bytes32(0), "DIDRegistry: Gecersiz yeni belge ozeti");

        _dids[did].docHash = newDocHash;
        _dids[did].updatedAt = block.timestamp;

        emit DIDUpdated(did, msg.sender, newDocHash, block.timestamp);
    }

    /**
     * @notice Bir DID'yi pasif duruma getirir (deactivate).
     */
    function deactivateDID(string calldata did) external onlyController(did) {
        require(_dids[did].active, "DIDRegistry: DID zaten pasif");

        _dids[did].active = false;
        _dids[did].updatedAt = block.timestamp;

        emit DIDDeactivated(did, msg.sender, block.timestamp);
    }

    /**
     * @notice DID kaydını sorgular.
     */
    function getDID(string calldata did) external view returns (address controller, bytes32 docHash, uint256 updatedAt, bool active) {
        DIDRecord memory rec = _dids[did];
        require(rec.controller != address(0), "DIDRegistry: DID bulunamadi");
        return (rec.controller, rec.docHash, rec.updatedAt, rec.active);
    }

    /**
     * @notice DID'nin aktif olup olmadığını kontrol eder.
     */
    function isActive(string calldata did) external view returns (bool) {
        return _dids[did].active;
    }
}
