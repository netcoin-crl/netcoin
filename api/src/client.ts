/** Minimal typed client helpers for the future TypeScript API layer. */
import {
  ExplorerAddressSchema,
  MigrationStatusSchema,
  ParityStatusSchema,
  ParityVectorSchema,
  type ExplorerAddress,
  type MigrationStatus,
  type ParityStatus,
  type ParityVector
} from './schemas.js';

export interface NetCoinClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export class NetCoinClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: NetCoinClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? '';
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  async migrationStatus(): Promise<MigrationStatus> {
    const data = await this.getJson('/api/migration-status');
    return MigrationStatusSchema.parse(data);
  }

  async explorerAddress(address: string): Promise<ExplorerAddress> {
    const data = await this.getJson(`/api/explorer/address/${encodeURIComponent(address)}`);
    return ExplorerAddressSchema.parse(data);
  }

  async parityStatus(): Promise<ParityStatus> {
    const data = await this.getJson('/api/parity-status');
    return ParityStatusSchema.parse(data);
  }

  async parityVectors(): Promise<ParityVector> {
    const data = await this.getJson('/api/parity-vectors');
    return ParityVectorSchema.parse(data);
  }

  async migrationReadiness(): Promise<unknown> {
    return this.getJson('/api/migration-readiness');
  }

  private async getJson(path: string): Promise<unknown> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`);
    if (!response.ok) {
      throw new Error(`NetCoin API request failed: ${response.status} ${path}`);
    }
    return response.json();
  }
}
