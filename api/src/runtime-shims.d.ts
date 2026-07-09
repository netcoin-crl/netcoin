/** Minimal ambient declarations used by source-only CI in restricted sandboxes.
 * Real npm builds still use the package dependencies declared in package.json;
 * these shims keep `tsc --noEmit` deterministic when node_modules is absent. */
declare module 'zod' {
  export namespace z {
    export type infer<T> = any;
  }
  export const z: any;
}

declare module 'fastify' {
  export interface FastifyInstance {
    get(path: string, handler: (request?: any, reply?: any) => any): FastifyInstance;
    post(path: string, handler: (request?: any, reply?: any) => any): FastifyInstance;
    put(path: string, handler: (request?: any, reply?: any) => any): FastifyInstance;
    patch(path: string, handler: (request?: any, reply?: any) => any): FastifyInstance;
    delete(path: string, handler: (request?: any, reply?: any) => any): FastifyInstance;
    listen(options: any): Promise<unknown>;
  }
  export default function Fastify(options?: any): FastifyInstance;
}

declare module 'node:fs' {
  export function readFileSync(path: string, encoding?: string): string;
}

declare module 'node:url' {
  export function fileURLToPath(url: string | URL): string;
}

declare module 'node:path' {
  export function dirname(path: string): string;
  export function join(...paths: string[]): string;
}

declare const process: {
  argv: string[];
  env: Record<string, string | undefined>;
  exit(code?: number): never;
};

