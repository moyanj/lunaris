#include "../lunaris.hpp"

#include <iostream>

extern "C" int wmain(int a, int b) {
    if (auto ctx = lunaris::TaskContext::current()) {
        std::cout << "task=" << ctx->task_id
                  << " worker=" << ctx->worker_version
                  << " caps=" << ctx->host_capabilities_json
                  << "\n";
    }

    if (auto value = lunaris::simd::addChecked(a, b)) {
        return *value;
    }
    return a + b;
}
