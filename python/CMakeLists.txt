# Python convention.
set(PYTHON_MODULE_PREFIX "")
set(PYTHON_MODULE_SUFFIX ".so")

cet_find_package(PythonInterp PRIVATE REQUIRED)
cet_find_package(PythonLibs PUBLIC REQUIRED)
cet_find_package(pybind11 PRIVATE REQUIRED CONFIG)

cet_make_library(
  LIBRARY_NAME fhicl
  SOURCE fhiclmodule.cc
  LIBRARIES PRIVATE
    fhiclcpp::fhiclcpp
    pybind11::module
    pybind11::embed
  )

set_target_properties(fhicl PROPERTIES PREFIX "${PYTHON_MODULE_PREFIX}"
  SUFFIX "${PYTHON_MODULE_SUFFIX}")
