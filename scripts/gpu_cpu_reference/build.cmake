cmake_minimum_required(VERSION 3.20)

# This script is one owned preparation command. Its child configure/build processes inherit the
# qualifier's closed environment and process group; failures stop before any later build phase.
foreach(name IN ITEMS ALIGNC ENTRY GGML_SOURCE SHIM_SOURCE PROJECT_SOURCE PARENT_DRIVER
                      CC CXX AR RANLIB LINKER NINJA SDK OUTPUT)
    if(NOT DEFINED ${name} OR NOT IS_ABSOLUTE "${${name}}" OR NOT EXISTS "${${name}}")
        message(FATAL_ERROR "CPU reference requires an existing absolute ${name}")
    endif()
    if("${${name}}" MATCHES "[;\\\n\r]")
        message(FATAL_ERROR "CPU reference ${name} cannot contain a list separator or escape")
    endif()
endforeach()
if(NOT DEFINED GGML_COMMIT OR NOT GGML_COMMIT MATCHES "^[0-9a-f]+$"
   OR NOT DEFINED HOST_PLATFORM OR NOT HOST_PLATFORM MATCHES "^(macos|linux|wsl2)$")
    message(FATAL_ERROR "CPU reference source or platform identity is invalid")
endif()
string(LENGTH "${GGML_COMMIT}" commit_length)
if(NOT commit_length EQUAL 40)
    message(FATAL_ERROR "CPU reference source revision must have 40 hex digits")
endif()
if(EXISTS "${OUTPUT}/build")
    message(FATAL_ERROR "CPU reference build output is occupied")
endif()

set(sdk_flag "-DCMAKE_SYSROOT:PATH=${SDK}")
if(HOST_PLATFORM STREQUAL "macos")
    set(sdk_flag "-DCMAKE_OSX_SYSROOT:PATH=${SDK}")
endif()
execute_process(
    COMMAND "${CMAKE_COMMAND}" -S "${PROJECT_SOURCE}" -B "${OUTPUT}/build" -G Ninja
            "-DCMAKE_MAKE_PROGRAM:FILEPATH=${NINJA}"
            "-DCMAKE_C_COMPILER:FILEPATH=${CC}" "-DCMAKE_CXX_COMPILER:FILEPATH=${CXX}"
            "-DCMAKE_ASM_COMPILER:FILEPATH=${CC}" "-DCMAKE_AR:FILEPATH=${AR}"
            "-DCMAKE_RANLIB:FILEPATH=${RANLIB}" "-DCMAKE_LINKER:FILEPATH=${LINKER}"
            "${sdk_flag}" -DCMAKE_BUILD_TYPE=Release
            -DCMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH=FALSE
            "-DREFERENCE_ALIGNC:FILEPATH=${ALIGNC}" "-DREFERENCE_ENTRY:FILEPATH=${ENTRY}"
            "-DREFERENCE_GGML_SOURCE:PATH=${GGML_SOURCE}"
            "-DREFERENCE_SHIM_SOURCE:FILEPATH=${SHIM_SOURCE}"
            "-DREFERENCE_PARENT_DRIVER:FILEPATH=${PARENT_DRIVER}"
            "-DREFERENCE_OUTPUT:PATH=${OUTPUT}" "-DGGML_BUILD_COMMIT=${GGML_COMMIT}"
    RESULT_VARIABLE configured
)
if(NOT configured EQUAL 0)
    message(FATAL_ERROR "CPU reference configure failed: ${configured}")
endif()
execute_process(
    COMMAND "${CMAKE_COMMAND}" --build "${OUTPUT}/build" --target cpu-reference --parallel 2
    RESULT_VARIABLE built
)
if(NOT built EQUAL 0)
    message(FATAL_ERROR "CPU reference build failed: ${built}")
endif()
