# Python convention.
set(PYTHON_MODULE_PREFIX "")
set(PYTHON_MODULE_SUFFIX ".so")

cet_find_package(PythonInterp PRIVATE REQUIRED)
cet_find_package(PythonLibs PUBLIC REQUIRED)
cet_find_package(pybind11 PRIVATE REQUIRED CONFIG)

cet_make(LIBRARY_NAME fhicl ### MIGRATE-ACTION-RECOMMENDED: use cet_make_library(), build_dictionary(), basic_plugin() with explicit source lists
  LIB_MODULE
  LIBRARIES cetlib cetlib_except fhiclcpp ${PYTHON_LIBRARIES})

target_include_directories(fhicl PRIVATE ${pybind11_INCLUDE_DIRS} ${PYTHON_INCLUDE_DIRS})
set_target_properties(fhicl PROPERTIES PREFIX "${PYTHON_MODULE_PREFIX}"
  SUFFIX "${PYTHON_MODULE_SUFFIX}")
