/**
 * Client-side credential backup encryption.
 *
 * New archives (version 2) derive an AES-256-GCM key with Argon2id through
 * hash-wasm, because a memory-hard function raises the cost of offline guessing.
 * Version 1 archives (PBKDF2-HMAC-SHA256, 600 000 iterations) can still be read.
 * The header is bound as additional authenticated data, so changed KDF settings,
 * salt, nonce or backup id make decryption fail. The passphrase is never sent,
 * stored or logged. A KDF slows guessing; it cannot prevent it.
 */

import { argon2id } from "hash-wasm";

export const ARCHIVE_FORMAT = "secure-ssi-wallet-backup-archive";
export const ARCHIVE_VERSION = 2;
export const LEGACY_ARCHIVE_VERSION = 1;
/** Above the OWASP minimum of 19 MiB, 2 passes, 1 lane. */
export const ARGON2 = { memoryKiB: 65_536, passes: 3, lanes: 1 };
/** Bounds stop a crafted file from exhausting the browser. */
const ARGON2_LIMITS = { minMemoryKiB: 19_456, maxMemoryKiB: 262_144, minPasses: 2, maxPasses: 10 };
export const PBKDF2_ITERATIONS = 600_000;
/** Upper bound protects the browser from a crafted, very slow archive. */
const MAX_ITERATIONS = 5_000_000;
export const MIN_PASSPHRASE_LENGTH = 12;
export const MAX_ARCHIVE_BYTES = 2 * 1024 * 1024;

export interface ArchiveHeader {
  format: typeof ARCHIVE_FORMAT;
  version: number;
  backupId: string;
  walletId: string;
  createdAt: string;
  itemCount: number;
  kdf:
    | { name: "PBKDF2"; hash: "SHA-256"; iterations: number; salt: string }
    | { name: "Argon2id"; memoryKiB: number; passes: number; lanes: number; salt: string };
  cipher: { name: "AES-GCM"; nonce: string };
}

export interface EncryptedArchive extends ArchiveHeader {
  ciphertext: string;
}

export type ArchiveErrorCode =
  | "TOO_LARGE"
  | "NOT_JSON"
  | "UNSUPPORTED_FORMAT"
  | "WEAK_OR_INVALID_KDF"
  | "DECRYPTION_FAILED"
  | "WEAK_PASSPHRASE";

export class ArchiveError extends Error {
  readonly code: ArchiveErrorCode;

  constructor(code: ArchiveErrorCode, message: string) {
    super(message);
    this.code = code;
    this.name = "ArchiveError";
  }
}

const encoder = new TextEncoder();

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function fromBase64(value: string, expectedLength?: number): Uint8Array {
  let binary: string;
  try {
    binary = atob(value);
  } catch {
    throw new ArchiveError("UNSUPPORTED_FORMAT", "The backup file is damaged.");
  }
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  if (expectedLength !== undefined && bytes.length !== expectedLength) {
    throw new ArchiveError("UNSUPPORTED_FORMAT", "The backup file is damaged.");
  }
  return bytes;
}

/** Fixed field order: the same bytes are produced when encrypting and decrypting. */
function headerAad(header: ArchiveHeader): Uint8Array {
  const kdf = header.kdf.name === "PBKDF2"
    ? [header.kdf.name, header.kdf.hash, header.kdf.iterations, header.kdf.salt]
    : [header.kdf.name, header.kdf.memoryKiB, header.kdf.passes, header.kdf.lanes, header.kdf.salt];
  return encoder.encode(JSON.stringify([
    header.format, header.version, header.backupId, header.walletId, header.createdAt, header.itemCount,
    ...kdf,
    header.cipher.name, header.cipher.nonce,
  ]));
}

async function argon2Key(passphrase: string, salt: Uint8Array, kdf: { memoryKiB: number; passes: number; lanes: number }): Promise<CryptoKey> {
  const raw = await argon2id({
    password: passphrase,
    salt,
    parallelism: kdf.lanes,
    iterations: kdf.passes,
    memorySize: kdf.memoryKiB,
    hashLength: 32,
    outputType: "binary",
  });
  return crypto.subtle.importKey("raw", raw as BufferSource, "AES-GCM", false, ["encrypt", "decrypt"]);
}

function keyFor(passphrase: string, kdf: ArchiveHeader["kdf"]): Promise<CryptoKey> {
  const salt = fromBase64(kdf.salt, 16);
  return kdf.name === "PBKDF2" ? deriveKey(passphrase, salt, kdf.iterations) : argon2Key(passphrase, salt, kdf);
}

async function deriveKey(passphrase: string, salt: Uint8Array, iterations: number): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey("raw", encoder.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

/** Length and variety only: a KDF slows offline guessing, it cannot prevent it. */
export function isAcceptablePassphrase(passphrase: string): boolean {
  return passphrase.length >= MIN_PASSPHRASE_LENGTH && new Set(passphrase).size >= 6;
}

const ARCHIVE_FIELDS = new Set([
  "format", "version", "backupId", "walletId", "createdAt", "itemCount", "kdf", "cipher", "ciphertext",
]);

export async function encryptBackup(
  payload: string,
  meta: { backupId: string; walletId: string; createdAt: string; itemCount: number },
  passphrase: string,
): Promise<EncryptedArchive> {
  if (!isAcceptablePassphrase(passphrase)) {
    throw new ArchiveError("WEAK_PASSPHRASE", `Use at least ${MIN_PASSPHRASE_LENGTH} characters, with real variety.`);
  }
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const header: ArchiveHeader = {
    format: ARCHIVE_FORMAT,
    version: ARCHIVE_VERSION,
    ...meta,
    kdf: { name: "Argon2id", ...ARGON2, salt: toBase64(salt) },
    cipher: { name: "AES-GCM", nonce: toBase64(nonce) },
  };
  const key = await keyFor(passphrase, header.kdf);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce, additionalData: headerAad(header) },
    key,
    encoder.encode(payload),
  );
  return { ...header, ciphertext: toBase64(new Uint8Array(ciphertext)) };
}

/** Strict parse of an untrusted file: size, JSON, format, version and KDF bounds. */
export function parseArchive(text: string): EncryptedArchive {
  if (encoder.encode(text).length > MAX_ARCHIVE_BYTES) {
    throw new ArchiveError("TOO_LARGE", "The file is larger than any wallet backup can be.");
  }
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new ArchiveError("NOT_JSON", "This is not a Secure SSI wallet backup file.");
  }
  const value = raw as Partial<EncryptedArchive> | null;
  if (value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).some((name) => !ARCHIVE_FIELDS.has(name))) {
    throw new ArchiveError("UNSUPPORTED_FORMAT", "The backup file format or version is not supported.");
  }
  const kdf = value?.kdf as (Record<string, unknown> & { salt?: string }) | undefined;
  const cipher = value?.cipher as Partial<ArchiveHeader["cipher"]> | undefined;
  const isText = (item: unknown, max: number): item is string => typeof item === "string" && item.length > 0 && item.length <= max;
  if (
    !value || typeof value !== "object" || Array.isArray(value)
    || value.format !== ARCHIVE_FORMAT || (value.version !== ARCHIVE_VERSION && value.version !== LEGACY_ARCHIVE_VERSION)
    || !isText(value.backupId, 80) || !/^wbk_[A-Za-z0-9_-]{16,64}$/.test(value.backupId)
    || !isText(value.walletId, 100) || !isText(value.createdAt, 40)
    || typeof value.itemCount !== "number" || !Number.isInteger(value.itemCount) || value.itemCount < 0
    || !cipher || cipher.name !== "AES-GCM" || !isText(cipher.nonce, 32)
    || !isText(value.ciphertext, MAX_ARCHIVE_BYTES)
  ) {
    throw new ArchiveError("UNSUPPORTED_FORMAT", "The backup file format or version is not supported.");
  }
  const legacy = value.version === LEGACY_ARCHIVE_VERSION;
  const whole = (item: unknown, low: number, high: number): boolean =>
    typeof item === "number" && Number.isInteger(item) && item >= low && item <= high;
  const pbkdf2Ok = kdf?.name === "PBKDF2" && kdf.hash === "SHA-256" && whole(kdf.iterations, PBKDF2_ITERATIONS, MAX_ITERATIONS);
  const argonOk = kdf?.name === "Argon2id" && kdf.lanes === 1
    && whole(kdf.memoryKiB, ARGON2_LIMITS.minMemoryKiB, ARGON2_LIMITS.maxMemoryKiB)
    && whole(kdf.passes, ARGON2_LIMITS.minPasses, ARGON2_LIMITS.maxPasses);
  if (!kdf || !isText(kdf.salt, 32) || !(legacy ? pbkdf2Ok : argonOk)) {
    throw new ArchiveError("WEAK_OR_INVALID_KDF", "The backup uses key-derivation settings this wallet does not accept.");
  }
  fromBase64(kdf.salt as string, 16);
  fromBase64(cipher.nonce, 12);
  return value as EncryptedArchive;
}

/**
 * Returns the exact server payload. A wrong passphrase and a modified file are
 * indistinguishable by design (AES-GCM authentication fails for both).
 */
export async function decryptBackup(archive: EncryptedArchive, passphrase: string): Promise<string> {
  const key = await keyFor(passphrase, archive.kdf);
  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: fromBase64(archive.cipher.nonce, 12), additionalData: headerAad(archive) },
      key,
      fromBase64(archive.ciphertext),
    );
    return new TextDecoder("utf-8", { fatal: true }).decode(plaintext);
  } catch {
    throw new ArchiveError("DECRYPTION_FAILED", "The passphrase is wrong or the backup file was modified.");
  }
}

export function archiveFileName(archive: ArchiveHeader): string {
  return `secure-ssi-wallet-backup-${archive.createdAt.slice(0, 10)}-${archive.backupId.slice(4, 12)}.json`;
}
