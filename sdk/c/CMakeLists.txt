cmake_minimum_required(VERSION 3.16)

project(lunaris_guest_sdk_c LANGUAGES C)

add_library(lunaris_guest_sdk_c INTERFACE)
target_include_directories(
    lunaris_guest_sdk_c
    INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}
)
