cmake_minimum_required(VERSION 3.20)
project(align_cpu_reference C CXX)

foreach(name IN ITEMS REFERENCE_ALIGNC REFERENCE_ENTRY REFERENCE_GGML_SOURCE
                      REFERENCE_SHIM_SOURCE REFERENCE_PARENT_DRIVER REFERENCE_OUTPUT)
    if(NOT DEFINED ${name} OR NOT IS_ABSOLUTE "${${name}}" OR NOT EXISTS "${${name}}")
        message(FATAL_ERROR "CPU reference project requires ${name}")
    endif()
endforeach()

set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
set(GGML_CPU ON CACHE BOOL "" FORCE)
foreach(feature IN ITEMS NATIVE CCACHE LTO CPU_REPACK CPU_KLEIDIAI CPU_HBM CPU_ALL_VARIANTS
                         OPENMP ACCELERATE BLAS LLAMAFILE CUDA METAL HIP MUSA RPC VULKAN SYCL
                         OPENCL OPENVINO CANN ZENDNN VIRTGPU HEXAGON
                         SSE42 AVX AVX2 AVX_VNNI BMI2 AVX512 AVX512_VBMI AVX512_VNNI
                         AVX512_BF16 FMA F16C AMX_TILE AMX_INT8 AMX_BF16
                         BUILD_TESTS BUILD_EXAMPLES)
    set(GGML_${feature} OFF CACHE BOOL "" FORCE)
endforeach()
set(GIT_EXE OFF CACHE FILEPATH "" FORCE)
set(GGML_GIT_DIRTY 0)
add_compile_options(-ffp-contract=off)
add_subdirectory("${REFERENCE_GGML_SOURCE}/ggml" ggml)

add_library(align_ggml_shim STATIC "${REFERENCE_SHIM_SOURCE}")
target_compile_definitions(align_ggml_shim PRIVATE
    ALIGN_GGML_FP_CONTRACT_OFF=1 ALIGN_GGML_STATIC_CPU_ONLY=1)
target_compile_options(align_ggml_shim PRIVATE -Wall -Wextra -Werror)
target_include_directories(align_ggml_shim PRIVATE "${REFERENCE_GGML_SOURCE}/ggml/include")
target_link_libraries(align_ggml_shim PRIVATE ggml)

if(APPLE)
    set(REFERENCE_CXX_LIBRARY "-lc++")
else()
    set(REFERENCE_CXX_LIBRARY "-lstdc++")
endif()
configure_file(driver.c.in driver.c.configured @ONLY ESCAPE_QUOTES)
file(GENERATE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/driver.c"
     INPUT "${CMAKE_CURRENT_BINARY_DIR}/driver.c.configured")
add_executable(cpu-reference-driver "${CMAKE_CURRENT_BINARY_DIR}/driver.c")
target_compile_options(cpu-reference-driver PRIVATE -Wall -Wextra -Werror)
add_dependencies(cpu-reference-driver align_ggml_shim ggml ggml-cpu ggml-base)

get_filename_component(entry_name "${REFERENCE_ENTRY}" NAME_WE)
add_custom_command(
    OUTPUT "${REFERENCE_OUTPUT}/${entry_name}"
    COMMAND "$<TARGET_FILE:cpu-reference-driver>" --build-entry
            "${REFERENCE_ALIGNC}" "${REFERENCE_ENTRY}"
    WORKING_DIRECTORY "${REFERENCE_OUTPUT}"
    DEPENDS cpu-reference-driver align_ggml_shim ggml ggml-cpu ggml-base "${REFERENCE_ENTRY}"
    VERBATIM
)
add_custom_target(cpu-reference DEPENDS "${REFERENCE_OUTPUT}/${entry_name}")
