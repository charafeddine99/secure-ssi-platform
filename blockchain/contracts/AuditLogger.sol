// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title AuditLogger
 * @dev SSI, AI Fraud Detection ve Kurtarma olaylarının SHA-256 özetlerini zincir üzerinde değiştirilemez şekilde saklar.
 */
contract AuditLogger {
    enum EventCategory {
        IDENTITY_ACTION,
        CREDENTIAL_ISSUED,
        CREDENTIAL_VERIFIED,
        FRAUD_DETECTED,
        ACCOUNT_QUARANTINED,
        RECOVERY_TRIGGERED,
        KEY_ROTATED
    }

    struct AuditRecord {
        bytes32 eventHash;
        EventCategory category;
        uint256 timestamp;
        address recorder;
    }

    AuditRecord[] public records;

    event SecurityEventLogged(
        uint256 indexed recordId,
        bytes32 indexed eventHash,
        EventCategory indexed category,
        address recorder,
        uint256 timestamp
    );

    /**
     * @notice Güvenlik veya kimlik olayının özetini zincirde kayıt altına alır.
     */
    function logEvent(bytes32 eventHash, EventCategory category) external returns (uint256 recordId) {
        require(eventHash != bytes32(0), "AuditLogger: Gecersiz event hash");

        recordId = records.length;
        records.push(AuditRecord({
            eventHash: eventHash,
            category: category,
            timestamp: block.timestamp,
            recorder: msg.sender
        }));

        emit SecurityEventLogged(recordId, eventHash, category, msg.sender, block.timestamp);
    }

    /**
     * @notice Toplam denetim kaydı sayısını döner.
     */
    function totalRecords() external view returns (uint256) {
        return records.length;
    }
}
