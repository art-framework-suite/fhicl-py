cmake_minimum_required(VERSION 3.18.2 FATAL_ERROR)

find_package(cetmodules 2.13.00 REQUIRED)
project(fhiclpy VERSION 4.01.01 LANGUAGES CXX C)

include(CetCMakeEnv)
cet_cmake_env()

cet_set_compiler_flags(DIAGS VIGILANT
  WERROR
  NO_UNDEFINED
  EXTRA_FLAGS -pedantic
)

cet_report_compiler_flags(REPORT_THRESHOLD VERBOSE)

add_subdirectory(python)

####################################
# Generate CMake (and UPS, if appropriate) configuration files and
# packaging.
cet_cmake_config()
