/** Minimal typed client helpers for the future TypeScript API layer. */
import {
  ExplorerAddressSchema,
  ExplorerTransactionSchema,
  IndexerSnapshotSchema,
  MigrationReadinessSchema,
  MigrationStatusSchema,
  ParityStatusSchema,
  ParityVectorSchema,
  OperatorDiagnosticsSchema,
  ReleaseVerifySchema,
  type ExplorerAddress,
  type ExplorerTransaction,
  type IndexerSnapshot,
  type MigrationReadiness,
  type OperatorDiagnostics,
  type MigrationStatus,
  type ParityStatus,
  type ParityVector,
  type ReleaseVerify
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

  async migrationReadiness(): Promise<MigrationReadiness> {
    const data = await this.getJson('/api/migration-readiness');
    return MigrationReadinessSchema.parse(data);
  }

  async explorerTransaction(txid: string): Promise<ExplorerTransaction> {
    const data = await this.getJson(`/api/explorer/tx/${encodeURIComponent(txid)}`);
    return ExplorerTransactionSchema.parse(data);
  }

  async explorerBlock(id: string): Promise<IndexerSnapshot> {
    const data = await this.getJson(`/api/explorer/block/${encodeURIComponent(id)}`);
    return IndexerSnapshotSchema.parse(data);
  }

  async explorerMempool(): Promise<unknown> {
    return this.getJson('/api/explorer/mempool');
  }

  async operatorDiagnosticsBundle(): Promise<OperatorDiagnostics> {
    const data = await this.getJson('/api/operator/diagnostics/bundle');
    return OperatorDiagnosticsSchema.parse(data);
  }

  async releaseVerify(): Promise<ReleaseVerify> {
    const data = await this.getJson('/api/release/verify');
    return ReleaseVerifySchema.parse(data);
  }

  private async getJson(path: string): Promise<unknown> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`);
    if (!response.ok) {
      throw new Error(`NetCoin API request failed: ${response.status} ${path}`);
    }
    return response.json();
  }
}
