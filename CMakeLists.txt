# Required to keep CMake happy.
cmake_minimum_required(VERSION 3.18.2 FATAL_ERROR)

# Find cetmodules macros and functions.

# Project information, including version and required languages.
find_package(cetmodules 2.03.00 REQUIRED)
project(fhiclpy VERSION 4.00.02 LANGUAGES CXX C)

####################################
# Set any project configuration variables here.
set(${PROJECT_NAME}_OLD_STYLE_CONFIG_VARS TRUE)

# Initialize the cetmodules build environment.
include(CetCMakeEnv)
cet_cmake_env()

# Compiler flag settings.
cet_set_compiler_flags(DIAGS VIGILANT
  WERROR
  NO_UNDEFINED
  EXTRA_FLAGS -pedantic)

# Compiler flag settings.
cet_report_compiler_flags(REPORT_THRESHOLD VERBOSE)

####################################
# Dependencies.

find_ups_product(cetlib_except) ### MIGRATE-ACTION-RECOMMENDED: use cet_find_package() with target semantics for linking
find_ups_product(cetlib) ### MIGRATE-ACTION-RECOMMENDED: use cet_find_package() with target semantics for linking
find_ups_product(fhiclcpp v4_11_01) ### MIGRATE-ACTION-RECOMMENDED: use cet_find_package() with target semantics for linking

add_subdirectory(python)

####################################
# Generate CMake (and UPS, if appropriate) configuration files and
# packaging.
cet_cmake_config(COMPATIBILITY SameMajorVersion)
