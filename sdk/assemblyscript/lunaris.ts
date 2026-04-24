export const TASK_ID_ENV = "LUNARIS_TASK_ID";
export const WORKER_VERSION_ENV = "LUNARIS_WORKER_VERSION";
export const HOST_CAPABILITIES_ENV = "LUNARIS_HOST_CAPABILITIES";

export enum Status {
  Ok = 0,
  MissingEnv = 1,
  InvalidTaskId = 2,
  MissingCapability = 3,
}

export class TaskContext {
  constructor(
    public readonly taskId: u64,
    public readonly workerVersion: string,
    public readonly hostCapabilities: Array<string>,
  ) {}

  static current(): TaskContext | null {
    const taskId = context.taskId();
    const workerVersion = context.workerVersion();
    const hostCapabilities = context.hostCapabilities();
    if (taskId == null || workerVersion == null || hostCapabilities == null) {
      return null;
    }
    return new TaskContext(taskId, workerVersion, hostCapabilities);
  }
}

function envGet(name: string): string | null {
  return process.env.has(name) ? process.env.get(name) : null;
}

function parseCapabilities(raw: string): Array<string> {
  const items = new Array<string>();
  let cursor = 0;
  while (cursor < raw.length) {
    const start = raw.indexOf('"', cursor);
    if (start < 0) break;
    const end = raw.indexOf('"', start + 1);
    if (end < 0) break;
    items.push(raw.substring(start + 1, end));
    cursor = end + 1;
  }
  return items;
}

export namespace context {
  export function taskId(): u64 | null {
    const raw = envGet(TASK_ID_ENV);
    if (raw == null || raw.length == 0) {
      return null;
    }
    return U64.parseInt(raw, 10);
  }

  export function workerVersion(): string | null {
    return envGet(WORKER_VERSION_ENV);
  }

  export function hostCapabilitiesJson(): string | null {
    return envGet(HOST_CAPABILITIES_ENV);
  }

  export function hostCapabilities(): Array<string> | null {
    const raw = hostCapabilitiesJson();
    if (raw == null) {
      return null;
    }
    return parseCapabilities(raw);
  }

  export function hasCapability(name: string): bool {
    const raw = hostCapabilitiesJson();
    if (raw == null || name.length == 0) {
      return false;
    }
    return raw.indexOf('"' + name + '"') >= 0;
  }
}

@external("lunaris:simd", "ping")
declare function simdPingImport(): i32;

@external("lunaris:simd", "add")
declare function simdAddImport(a: i32, b: i32): i32;

export namespace simd {
  export function available(): bool {
    return context.hasCapability("simd");
  }

  export function pingChecked(): i32 | null {
    if (!available()) {
      return null;
    }
    return simdPingImport();
  }

  export function addChecked(a: i32, b: i32): i32 | null {
    if (!available()) {
      return null;
    }
    return simdAddImport(a, b);
  }
}

