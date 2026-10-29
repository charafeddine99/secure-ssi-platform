import { getOrCreateHolderWallet, type HolderWallet } from "../../api/wallet.ts";
import { useAsync } from "../../lib/useAsync.ts";

/** Resolve the signed-in holder's wallet (listing first, creating only if none exists). */
export function useHolderWallet() {
  return useAsync<HolderWallet>(() => getOrCreateHolderWallet(), []);
}
