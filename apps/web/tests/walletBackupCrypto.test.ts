import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ArchiveError,
  MAX_ARCHIVE_BYTES,
  ARGON2,
  decryptBackup,
  encryptBackup,
  parseArchive,
} from "../src/lib/walletBackupCrypto.ts";

const META = {
  backupId: "wbk_wp28TestBackup000001",
  walletId: "wallet_wp28_holder_a_000001",
  createdAt: "2026-11-03T10:00:00Z",
  itemCount: 1,
};
const PAYLOAD = JSON.stringify({ format: "secure-ssi-wallet-backup", items: [{ credentialId: "urn:uuid:1", credential: { gpa: 4.0 } }] })
  .replace("4", "4.0"); // the exact server string, float formatting included
const PASSPHRASE = "correct horse battery staple";

async function rejects(promise: Promise<unknown>, code: string): Promise<void> {
  await assert.rejects(promise, (error: unknown) => error instanceof ArchiveError && error.code === code);
}

test("round trip returns the exact payload and stores no plaintext or passphrase", async () => {
  const archive = await encryptBackup(PAYLOAD, META, PASSPHRASE);
  const serialized = JSON.stringify(archive);
  assert.equal(archive.kdf.name, "Argon2id");
  assert.ok(archive.kdf.name === "Argon2id" && archive.kdf.memoryKiB === ARGON2.memoryKiB);
  assert.ok(!serialized.includes("urn:uuid:1"));
  assert.ok(!serialized.includes(PASSPHRASE));
  const parsed = parseArchive(serialized);
  assert.equal(await decryptBackup(parsed, PASSPHRASE), PAYLOAD);
});

test("wrong passphrase and tampered ciphertext both fail closed", async () => {
  const archive = await encryptBackup(PAYLOAD, META, PASSPHRASE);
  await rejects(decryptBackup(archive, "wrong passphrase 123"), "DECRYPTION_FAILED");
  const bytes = Uint8Array.from(atob(archive.ciphertext), (c) => c.charCodeAt(0));
  bytes[3] ^= 1;
  const tampered = { ...archive, ciphertext: btoa(String.fromCharCode(...bytes)) };
  await rejects(decryptBackup(tampered, PASSPHRASE), "DECRYPTION_FAILED");
});

test("authenticated header: swapping the wallet or backup id breaks decryption", async () => {
  const archive = await encryptBackup(PAYLOAD, META, PASSPHRASE);
  await rejects(decryptBackup({ ...archive, walletId: "wallet_wp28_holder_b_000001" }, PASSPHRASE), "DECRYPTION_FAILED");
  await rejects(decryptBackup({ ...archive, backupId: "wbk_wp28TestBackup000002" }, PASSPHRASE), "DECRYPTION_FAILED");
});

test("KDF downgrade, excessive cost and unknown formats are refused before decryption", async () => {
  const archive = await encryptBackup(PAYLOAD, META, PASSPHRASE);
  const variant = (change: Record<string, unknown>) => JSON.stringify({ ...archive, ...change });
  const weak = (e: unknown) => (e as ArchiveError).code === "WEAK_OR_INVALID_KDF";
  assert.throws(() => parseArchive(variant({ kdf: { ...archive.kdf, memoryKiB: 1024 } })), weak);
  assert.throws(() => parseArchive(variant({ kdf: { ...archive.kdf, memoryKiB: 8_000_000 } })), weak);
  assert.throws(() => parseArchive(variant({ kdf: { ...archive.kdf, passes: 1 } })), weak);
  assert.throws(() => parseArchive(variant({ kdf: { ...archive.kdf, passes: 1000 } })), weak);
  assert.throws(() => parseArchive(variant({ kdf: { ...archive.kdf, lanes: 64 } })), weak);
  assert.throws(() => parseArchive(variant({ kdf: { name: "PBKDF2", hash: "SHA-256", iterations: 600_000, salt: archive.kdf.salt } })), weak);
  assert.throws(() => parseArchive(variant({ version: 3 })), (e: unknown) => (e as ArchiveError).code === "UNSUPPORTED_FORMAT");
  assert.throws(() => parseArchive(variant({ injected: true })), (e: unknown) => (e as ArchiveError).code === "UNSUPPORTED_FORMAT");
  assert.throws(() => parseArchive(variant({ cipher: { name: "AES-CBC", nonce: archive.cipher.nonce } })), (e: unknown) => (e as ArchiveError).code === "UNSUPPORTED_FORMAT");
  assert.throws(() => parseArchive(variant({ backupId: "../../etc/passwd" })), (e: unknown) => (e as ArchiveError).code === "UNSUPPORTED_FORMAT");
  assert.throws(() => parseArchive("PK\u0003\u0004 not a json archive"), (e: unknown) => (e as ArchiveError).code === "NOT_JSON");
  assert.throws(() => parseArchive("x".repeat(MAX_ARCHIVE_BYTES + 1)), (e: unknown) => (e as ArchiveError).code === "TOO_LARGE");
});

test("a short passphrase is refused", async () => {
  await rejects(encryptBackup(PAYLOAD, META, "short"), "WEAK_PASSPHRASE");
});

test("changing Argon2id settings in the header breaks decryption", async () => {
  const archive = await encryptBackup(PAYLOAD, META, PASSPHRASE);
  assert.ok(archive.kdf.name === "Argon2id");
  await rejects(decryptBackup({ ...archive, kdf: { ...archive.kdf, passes: archive.kdf.passes + 1 } }, PASSPHRASE), "DECRYPTION_FAILED");
});

test("a version 1 archive can still be opened", async () => {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const b64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes));
  const header = {
    format: "secure-ssi-wallet-backup-archive", version: 1, ...META,
    kdf: { name: "PBKDF2" as const, hash: "SHA-256" as const, iterations: 600_000, salt: b64(salt) },
    cipher: { name: "AES-GCM" as const, nonce: b64(nonce) },
  };
  const aad = new TextEncoder().encode(JSON.stringify([
    header.format, header.version, header.backupId, header.walletId, header.createdAt, header.itemCount,
    header.kdf.name, header.kdf.hash, header.kdf.iterations, header.kdf.salt, header.cipher.name, header.cipher.nonce,
  ]));
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(PASSPHRASE), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt, iterations: 600_000 }, material, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, additionalData: aad }, key, new TextEncoder().encode(PAYLOAD));
  const legacy = JSON.stringify({ ...header, ciphertext: b64(new Uint8Array(ciphertext)) });
  assert.equal(await decryptBackup(parseArchive(legacy), PASSPHRASE), PAYLOAD);
});

