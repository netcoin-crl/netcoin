/** Static migration status for TypeScript tooling until the live API is moved. */
import type { ServiceStatus } from './index.js';

export interface MigrationLaneStatus {
  id: string;
  language: 'Rust' | 'TypeScript' | 'Python';
  owner: string;
  status: 'migration-space' | 'starter-parity-crate' | 'typed-schema-starter' | 'active-reference';
  liveReplacement: boolean;
}

export const migrationLanes: MigrationLaneStatus[] = [
  { id: 'rust-consensus-parity', language: 'Rust', owner: 'core-rs/crates/consensus', status: 'starter-parity-crate', liveReplacement: false },
  { id: 'rust-wallet-core', language: 'Rust', owner: 'core-rs/crates/wallet-core', status: 'starter-parity-crate', liveReplacement: false },
  { id: 'rust-markets-core', language: 'Rust', owner: 'core-rs/crates/markets-core', status: 'starter-parity-crate', liveReplacement: false },
  { id: 'typescript-api-contracts', language: 'TypeScript', owner: 'api/src', status: 'typed-schema-starter', liveReplacement: false },
  { id: 'python-reference', language: 'Python', owner: 'netcoin/', status: 'active-reference', liveReplacement: true }
];

export function summarizeMigration(statuses: ServiceStatus[]) {
  return {
    serviceCount: statuses.length,
    laneCount: migrationLanes.length,
    liveRuntime: 'python-reference-app',
    replacementRuntime: 'rust-core-typescript-app',
    liveReplacementCount: migrationLanes.filter((lane) => lane.liveReplacement).length
  };
}
