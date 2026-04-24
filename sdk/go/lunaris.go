//go:build wasip1 && wasm

package lunaris

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strconv"
)

const (
	TaskIDEnv           = "LUNARIS_TASK_ID"
	WorkerVersionEnv    = "LUNARIS_WORKER_VERSION"
	HostCapabilitiesEnv = "LUNARIS_HOST_CAPABILITIES"
)

var ErrMissingCapability = errors.New("missing Lunaris capability")

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

type TaskContext struct {
	TaskID           uint64
	WorkerVersion    string
	HostCapabilities []string
}

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

func WorkerVersion() (string, error) {
	value, ok := os.LookupEnv(WorkerVersionEnv)
	if !ok {
		return "", fmt.Errorf("%s: %w", WorkerVersionEnv, os.ErrNotExist)
	}
	return value, nil
}

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

func SIMDAvailable() bool {
	return HasCapability("simd")
}

func SIMDPingChecked() (int32, error) {
	if !SIMDAvailable() {
		return 0, fmt.Errorf("simd: %w", ErrMissingCapability)
	}
	return simdPingImport(), nil
}

func SIMDAddChecked(a int32, b int32) (int32, error) {
	if !SIMDAvailable() {
		return 0, fmt.Errorf("simd: %w", ErrMissingCapability)
	}
	return simdAddImport(a, b), nil
}
