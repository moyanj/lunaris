# lunaris-go

Experimental Go guest SDK for Lunaris WASM modules.

This package targets `GOOS=wasip1` and `GOARCH=wasm` and wraps:

- task context reads from Lunaris environment variables
- capability checks
- `simd` host imports via `//go:wasmimport`

## Files

- `lunaris.go`: SDK package
- `example/main.go`: minimal `wmain` module
- `go.mod`: standalone module metadata

## Quick Start

```go
package main

import (
    "fmt"

    lunaris "github.com/moyan/lunaris/sdk/go/lunaris"
)

//go:wasmexport wmain
func wmain(a, b int32) int32 {
    if ctx, err := lunaris.CurrentContext(); err == nil {
        fmt.Printf("task=%d worker=%s\n", ctx.TaskID, ctx.WorkerVersion)
    }

    if value, err := lunaris.SIMDAddChecked(a, b); err == nil {
        return value
    }
    return a + b
}
```

## Build

```bash
cd sdk/go
GOOS=wasip1 GOARCH=wasm go build -o guest.wasm ./example
```
