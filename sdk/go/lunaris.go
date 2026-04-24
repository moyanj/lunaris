// Package lunaris 提供 Lunaris WASM 任务的 Go Guest SDK
//
// 用于编译到 GOOS=wasip1 GOARCH=wasm 目标的 WASM 模块。
// 提供任务上下文读取和宿主能力访问功能。
//
// 主要组件：
//   - TaskContext: 任务上下文结构体
//   - CurrentContext(): 获取当前任务上下文
//   - HasCapability(): 检查宿主能力
//   - SIMD 函数: SIMD 能力封装
//
// 使用示例：
//
//	package main
//
//	import (
//	    "fmt"
//	    lunaris "github.com/moyan/lunaris/sdk/go/lunaris"
//	)
//
//	//go:wasmexport wmain
//	func wmain(a, b int32) int32 {
//	    if ctx, err := lunaris.CurrentContext(); err == nil {
//	        fmt.Printf("task=%d worker=%s\n", ctx.TaskID, ctx.WorkerVersion)
//	    }
//
//	    if value, err := lunaris.SIMDAddChecked(a, b); err == nil {
//	        return value
//	    }
//	    return a + b
//	}
//go:build wasip1 && wasm

package lunaris

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strconv"
)

// 环境变量名称常量
const (
	TaskIDEnv           = "LUNARIS_TASK_ID"
	WorkerVersionEnv    = "LUNARIS_WORKER_VERSION"
	HostCapabilitiesEnv = "LUNARIS_HOST_CAPABILITIES"
)

// ErrMissingCapability 表示缺少宿主能力
var ErrMissingCapability = errors.New("missing Lunaris capability")

// ContextError 表示上下文读取错误
type ContextError struct {
	Field string
	Err   error
}

func (e *ContextError) Error() string {
	return fmt.Sprintf("invalid Lunaris context field %s: %v", e.Field, e.Err)
}

func (e *ContextError) Unwrap() error {
	return e.Err
}

// TaskContext 表示任务上下文
//
// 包含当前任务的元数据。
type TaskContext struct {
	TaskID           uint64
	WorkerVersion    string
	HostCapabilities []string
}

// CurrentContext 获取当前任务上下文
//
// 从环境变量读取任务上下文信息。
func CurrentContext() (*TaskContext, error) {
	taskID, err := TaskID()
	if err != nil {
		return nil, err
	}
	workerVersion, err := WorkerVersion()
	if err != nil {
		return nil, err
	}
	hostCapabilities, err := HostCapabilities()
	if err != nil {
		return nil, err
	}
	return &TaskContext{
		TaskID:           taskID,
		WorkerVersion:    workerVersion,
		HostCapabilities: hostCapabilities,
	}, nil
}

// TaskID 读取任务 ID
//
// 从 LUNARIS_TASK_ID 环境变量读取并解析为 uint64。
func TaskID() (uint64, error) {
	raw, err := os.LookupEnv(TaskIDEnv)
	if !err {
		return 0, fmt.Errorf("%s: %w", TaskIDEnv, os.ErrNotExist)
	}
	value, parseErr := strconv.ParseUint(raw, 10, 64)
	if parseErr != nil {
		return 0, &ContextError{Field: TaskIDEnv, Err: parseErr}
	}
	return value, nil
}

// WorkerVersion 读取 Worker 版本
func WorkerVersion() (string, error) {
	value, ok := os.LookupEnv(WorkerVersionEnv)
	if !ok {
		return "", fmt.Errorf("%s: %w", WorkerVersionEnv, os.ErrNotExist)
	}
	return value, nil
}

// HostCapabilities 读取宿主能力列表
//
// 从 LUNARIS_HOST_CAPABILITIES 环境变量读取并解析 JSON 数组。
func HostCapabilities() ([]string, error) {
	raw, ok := os.LookupEnv(HostCapabilitiesEnv)
	if !ok {
		return nil, fmt.Errorf("%s: %w", HostCapabilitiesEnv, os.ErrNotExist)
	}

	var items []string
	if err := json.Unmarshal([]byte(raw), &items); err != nil {
		return nil, &ContextError{Field: HostCapabilitiesEnv, Err: err}
	}
	return items, nil
}

// HasCapability 检查是否具有指定能力
func HasCapability(name string) bool {
	items, err := HostCapabilities()
	if err != nil {
		return false
	}
	for _, item := range items {
		if item == name {
			return true
		}
	}
	return false
}

//go:wasmimport lunaris:simd ping
func simdPingImport() int32

//go:wasmimport lunaris:simd add
func simdAddImport(a int32, b int32) int32

// SIMDAvailable 检查 SIMD 能力是否可用
func SIMDAvailable() bool {
	return HasCapability("simd")
}

// SIMDPingChecked 安全地调用 ping 函数
func SIMDPingChecked() (int32, error) {
	if !SIMDAvailable() {
		return 0, fmt.Errorf("simd: %w", ErrMissingCapability)
	}
	return simdPingImport(), nil
}

// SIMDAddChecked 安全地调用 add 函数
func SIMDAddChecked(a int32, b int32) (int32, error) {
	if !SIMDAvailable() {
		return 0, fmt.Errorf("simd: %w", ErrMissingCapability)
	}
	return simdAddImport(a, b), nil
}
