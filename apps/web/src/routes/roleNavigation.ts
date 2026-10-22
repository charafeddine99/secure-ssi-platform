import type { UserProfile } from "../context/AuthContext";

/** Return the single landing route assigned to an authenticated account role. */
export function roleHomePath(role: UserProfile["role"]): string {
  switch (role) {
    case "HOLDER": return "/wallet";
    case "ISSUER": return "/issuer";
    case "VERIFIER": return "/verifier";
    case "ADMIN": return "/admin";
  }
}
