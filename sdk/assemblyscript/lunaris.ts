/**
 * Lunaris AssemblyScript Guest SDK
 *
 * 用于编译到 WASM 的 AssemblyScript 模块。
 * 提供任务上下文读取和宿主能力访问功能。
 *
 * 主要组件：
 *   - TaskContext: 任务上下文类
 *   - context 命名空间: 环境变量读取函数
 *   - simd 命名空间: SIMD 能力封装
 *
 * 使用示例：
 *   ```ts
 *   import { TaskContext, context, simd } from "./lunaris";
 *
 *   export function wmain(a: i32, b: i32): i32 {
 *     let taskId: u64 = 0;
 *     const ctx = TaskContext.current();
 *     if (ctx != null) {
 *       taskId = ctx.taskId;
 *     }
 *
 *     if (simd.available()) {
 *       const value = simd.addChecked(a, b);
 *       if (value != null) return value;
 *     }
 *
 *     return a + b + <i32>(taskId % 2);
 *   }
 *   ```
 */

/** 任务 ID 环境变量名称 */
export const TASK_ID_ENV = "LUNARIS_TASK_ID";

/** Worker 版本环境变量名称 */
export const WORKER_VERSION_ENV = "LUNARIS_WORKER_VERSION";

/** 宿主能力环境变量名称 */
export const HOST_CAPABILITIES_ENV = "LUNARIS_HOST_CAPABILITIES";

/**
 * 状态枚举
 *
 * 表示操作的执行结果。
 */
export enum Status {
  Ok = 0,
  MissingEnv = 1,
  InvalidTaskId = 2,
  MissingCapability = 3,
}

/**
 * 任务上下文类
 *
 * 包含当前任务的元数据。
 */
export class TaskContext {
  constructor(
    /** 任务 ID */
    public readonly taskId: u64,
    /** Worker 版本号 */
    public readonly workerVersion: string,
    /** 宿主能力列表 */
    public readonly hostCapabilities: Array<string>,
  ) {}

  /**
   * 获取当前任务上下文
   *
   * 从环境变量读取任务上下文信息。
   *
   * Returns:
   *   - 成功：TaskContext
   *   - 失败：null
   */
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

/**
 * 读取环境变量
 */
function envGet(name: string): string | null {
  return process.env.has(name) ? process.env.get(name) : null;
}

/**
 * 解析能力 JSON 字符串
 */
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

/**
 * 上下文读取函数
 */
export namespace context {
  /**
   * 读取任务 ID
   */
  export function taskId(): u64 | null {
    const raw = envGet(TASK_ID_ENV);
    if (raw == null || raw.length == 0) {
      return null;
    }
    return U64.parseInt(raw, 10);
  }

  /**
   * 读取 Worker 版本
   */
  export function workerVersion(): string | null {
    return envGet(WORKER_VERSION_ENV);
  }

  /**
   * 读取宿主能力 JSON
   */
  export function hostCapabilitiesJson(): string | null {
    return envGet(HOST_CAPABILITIES_ENV);
  }

  /**
   * 读取宿主能力列表
   */
  export function hostCapabilities(): Array<string> | null {
    const raw = hostCapabilitiesJson();
    if (raw == null) {
      return null;
    }
    return parseCapabilities(raw);
  }

  /**
   * 检查是否具有指定能力
   */
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

/**
 * SIMD 能力模块
 */
export namespace simd {
  /**
   * 检查 SIMD 能力是否可用
   */
  export function available(): bool {
    return context.hasCapability("simd");
  }

  /**
   * 安全地调用 ping 函数
   */
  export function pingChecked(): i32 | null {
    if (!available()) {
      return null;
    }
    return simdPingImport();
  }

  /**
   * 安全地调用 add 函数
   */
  export function addChecked(a: i32, b: i32): i32 | null {
    if (!available()) {
      return null;
    }
    return simdAddImport(a, b);
  }
}

