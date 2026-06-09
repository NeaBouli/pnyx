export const SEMAPHORE_NATIVE_MODULES = ["Identity", "Group", "Proof"] as const;

export type SemaphoreNativeModuleName = (typeof SEMAPHORE_NATIVE_MODULES)[number];

export interface SemaphoreNativeStatus {
  ready: boolean;
  present: SemaphoreNativeModuleName[];
  missing: SemaphoreNativeModuleName[];
}

export type RequireNativeModule = (moduleName: string) => unknown;

export function getNativeSemaphoreStatus(
  loadModule: RequireNativeModule,
): SemaphoreNativeStatus {
  const present: SemaphoreNativeModuleName[] = [];
  const missing: SemaphoreNativeModuleName[] = [];

  for (const moduleName of SEMAPHORE_NATIVE_MODULES) {
    try {
      const mod = loadModule(moduleName);
      if (mod) present.push(moduleName);
      else missing.push(moduleName);
    } catch {
      missing.push(moduleName);
    }
  }

  return {
    ready: missing.length === 0,
    present,
    missing,
  };
}
