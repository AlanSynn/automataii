cmake_minimum_required(VERSION 3.15)
project(automataii_native LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Find Python and pybind11
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

# Find Eigen (header-only)
find_package(Eigen3 3.3 REQUIRED NO_MODULE)

# Optimization flags
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG -march=native -ffast-math")
endif()

# ARAP native module
pybind11_add_module(arap_native
    arap_native.cpp
)

target_link_libraries(arap_native PRIVATE
    Eigen3::Eigen
)

# Install the module to the package directory
install(TARGETS arap_native
    LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}
)

# Print configuration summary
message(STATUS "Python executable: ${Python_EXECUTABLE}")
message(STATUS "pybind11 version: ${pybind11_VERSION}")
message(STATUS "Eigen3 version: ${Eigen3_VERSION}")
