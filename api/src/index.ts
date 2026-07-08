export type NetCoinService =
  | 'wallet'
  | 'explorer'
  | 'markets'
  | 'community'
  | 'faucet'
  | 'operator'
  | 'exchange'
  | 'release';

export interface ServiceStatus {
  service: NetCoinService;
  status: 'reference-python' | 'migrating' | 'live-typescript';
  routeCount: number;
}

export const serviceStatuses: ServiceStatus[] = [
  { service: 'wallet', status: 'reference-python', routeCount: 3 },
  { service: 'explorer', status: 'reference-python', routeCount: 6 },
  { service: 'markets', status: 'reference-python', routeCount: 8 },
  { service: 'community', status: 'reference-python', routeCount: 7 },
  { service: 'faucet', status: 'reference-python', routeCount: 3 },
  { service: 'operator', status: 'reference-python', routeCount: 2 },
  { service: 'exchange', status: 'reference-python', routeCount: 1 },
  { service: 'release', status: 'reference-python', routeCount: 1 }
];

export * from './schemas.js';
export * from './client.js';
export * from './migration-status.js';
export * from './parity.js';

export * from './parity-executor.js';
