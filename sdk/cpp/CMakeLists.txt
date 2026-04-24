cmake_minimum_required(VERSION 3.16)

project(lunaris_guest_sdk_cpp LANGUAGES CXX)

add_library(lunaris_guest_sdk_cpp INTERFACE)
target_include_directories(
    lunaris_guest_sdk_cpp
    INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/../c
)
