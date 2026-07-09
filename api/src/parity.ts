/** Executable parity status helpers for the Rust/TypeScript migration bridge.
 * The Parity* schemas live in ./schemas.ts (single source of truth); this module
 * only adds derived helpers so it can be re-exported without name clashes. */
import { ParityStatusSchema, type ParityStatus } from './schemas.js';

export { ParityStatusSchema };

export function summarizeParity(status: ParityStatus) {
  const green = status.lanes.filter((lane: { status: string }) => lane.status === 'green').length;
  return {
    ok: status.ok,
    total: status.total,
    passed: status.passed,
    failed: status.failed,
    greenLanes: green,
    laneCount: status.lanes.length,
    fingerprintShort: status.vector_fingerprint.slice(0, 16)
  };
}
