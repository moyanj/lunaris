#include "../lunaris.h"

#include <stdio.h>

int wmain(int a, int b) {
    lunaris_context_t ctx;
    lunaris_status_t status = lunaris_context_load(&ctx);

    if (status == LUNARIS_STATUS_OK) {
        printf(
            "task=%llu worker=%s caps=%s\n",
            (unsigned long long)ctx.task_id,
            ctx.worker_version,
            ctx.host_capabilities_json
        );
        lunaris_context_free(&ctx);
    }

    if (lunaris_has_capability("simd")) {
        return lunaris_simd_add_checked(a, b, NULL);
    }
    return a + b;
}
