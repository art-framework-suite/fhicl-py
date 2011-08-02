# ======================================================================
#
# Testing
#
# ======================================================================

include(CetTest)

#File globs
FILE(GLOB testPass "testFiles/pass/*_pass.fcl")
FILE(GLOB testFail "testFiles/fail/*_fail.fcl")
FILE(GLOB test_cases "${testPass}" "${testFail}")


cet_test(test_suite USE_BOOST_UNIT NO_AUTO)

FOREACH(test_file ${testPass})
        GET_FILENAME_COMPONENT( test_file_stem ${test_file} NAME_WE)
        cet_test(${test_file_stem} HANDBUILT
                TEST_EXEC test_suite
                TEST_ARGS ${test_file}
                DATAFILES ${test_file}
)
ENDFOREACH()

FOREACH(test_file ${testFail})
        GET_FILENAME_COMPONENT( test_file_stem ${test_file} NAME_WE)
        cet_test(${test_file_stem} HANDBUILT
                TEST_EXEC test_suite
                TEST_ARGS ${test_file}
                DATAFILES ${test_file}
                TEST_PROPERTIES WILL_FAIL true
)
ENDFOREACH()

