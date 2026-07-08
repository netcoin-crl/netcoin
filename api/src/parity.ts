/** Executable parity status schemas for the Rust/TypeScript migration bridge. */
import { z } from 'zod';

export const ParityLaneSchema = z.object({
  lane: z.string(),
  status: z.enum(['green', 'red']),
  total: z.number().int().nonnegative(),
  passed: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative()
});

export const ParityStatusSchema = z.object({
  ok: z.boolean(),
  schema_version: z.number().int().positive(),
  vector_fingerprint: z.string().length(64),
  total: z.number().int().nonnegative(),
  passed: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  lanes: z.array(ParityLaneSchema)
});

export type ParityLane = z.infer<typeof ParityLaneSchema>;
export type ParityStatus = z.infer<typeof ParityStatusSchema>;

export function summarizeParity(status: ParityStatus) {
  const green = status.lanes.filter((lane) => lane.status === 'green').length;
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
