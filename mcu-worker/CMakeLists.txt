cmake_minimum_required(VERSION 3.16)

project(lunaris_mcu_worker VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(LUNARIS_MCU_NANOPB_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party/nanopb)
set(LUNARIS_MCU_WASM3_DIR ${CMAKE_CURRENT_SOURCE_DIR}/third_party/wasm3)

if(NOT EXISTS ${LUNARIS_MCU_NANOPB_DIR}/pb_common.c)
    message(FATAL_ERROR "Missing nanopb dependency. Run ./mcu-worker/scripts/fetch_deps.sh first.")
endif()

if(NOT EXISTS ${LUNARIS_MCU_WASM3_DIR}/source/m3_env.c)
    message(FATAL_ERROR "Missing wasm3 dependency. Run ./mcu-worker/scripts/fetch_deps.sh first.")
endif()

option(LUNARIS_MCU_BUILD_TESTS "Build MCU worker tests" ON)
set(LUNARIS_MCU_CORE_SRCS
    generated/common.pb.c
    generated/worker.pb.c
    src/engine.c
    src/proto.c
    src/websocket.c
    src/worker.c
    ${LUNARIS_MCU_NANOPB_DIR}/pb_common.c
    ${LUNARIS_MCU_NANOPB_DIR}/pb_decode.c
    ${LUNARIS_MCU_NANOPB_DIR}/pb_encode.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_api_libc.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_api_meta_wasi.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_api_tracer.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_bind.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_code.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_compile.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_core.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_env.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_exec.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_function.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_info.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_module.c
    ${LUNARIS_MCU_WASM3_DIR}/source/m3_parse.c
)

add_library(
    lunaris_mcu_worker_core
    ${LUNARIS_MCU_CORE_SRCS}
    src/platform_default.c
)

target_include_directories(
    lunaris_mcu_worker_core
    PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/generated
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${LUNARIS_MCU_NANOPB_DIR}
    ${LUNARIS_MCU_WASM3_DIR}/source
)
target_compile_definitions(lunaris_mcu_worker_core PUBLIC LUNARIS_MCU_USE_WASM3=1)

add_executable(lunaris-mcu-worker src/main.c)
target_link_libraries(lunaris-mcu-worker PRIVATE lunaris_mcu_worker_core)
target_link_libraries(lunaris_mcu_worker_core PUBLIC m)

if(LUNARIS_MCU_BUILD_TESTS)
    enable_testing()

    add_executable(
        lunaris_mcu_worker_tests
        tests/test_main.c
        tests/test_engine.c
        tests/test_proto.c
        tests/test_worker.c
    )
    target_link_libraries(lunaris_mcu_worker_tests PRIVATE lunaris_mcu_worker_core)

    add_test(NAME lunaris_mcu_worker_tests COMMAND lunaris_mcu_worker_tests)
endif()
