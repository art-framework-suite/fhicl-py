find_package(PythonInterp EXPORT REQUIRED)
find_package(PythonLibs EXPORT REQUIRED)
find_package(fhiclcpp REQUIRED)
find_package(pybind11 REQUIRED CONFIG)

cet_make_library(
  LIBRARY_NAME fhicl
  SOURCE fhiclmodule.cc
  LIBRARIES PRIVATE
    fhiclcpp::fhiclcpp
    pybind11::module
    pybind11::embed
  )

set_target_properties(fhicl
  PROPERTIES
    PREFIX ""
    SUFFIX ".so"
)
