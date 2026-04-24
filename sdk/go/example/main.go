package main

import (
	"fmt"

	lunaris "github.com/moyan/lunaris/sdk/go/lunaris"
)

//go:wasmexport wmain
func wmain(a, b int32) int32 {
	if ctx, err := lunaris.CurrentContext(); err == nil {
		fmt.Printf("task=%d worker=%s caps=%v\n", ctx.TaskID, ctx.WorkerVersion, ctx.HostCapabilities)
	}

	if value, err := lunaris.SIMDAddChecked(a, b); err == nil {
		return value
	}
	return a + b
}

func main() {}
