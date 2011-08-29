test_pass: fhiclpy.py
	@echo "*************************START OF EXPECTED SUCCESSES********************************"
	@echo "Test1: "
	python fhiclpy.py < testFiles/pass/assoc_pass.fcl
	@echo "Test2: "
	python fhiclpy.py < testFiles/pass/hname_pass.fcl
	@echo "Test3: "
	python fhiclpy.py < testFiles/pass/comments_pass.fcl
	@echo "Test4: "
	python fhiclpy.py < testFiles/pass/include_pass.fcl
	@echo "Test5: "
	python fhiclpy.py < testFiles/pass/leading_zero_pass.fcl
	@echo "Test6: "
	python fhiclpy.py < testFiles/pass/names_pass.fcl
	@echo "Test7: "
	python fhiclpy.py < testFiles/pass/prolog_pass.fcl
	@echo "Test8: "
	python fhiclpy.py < testFiles/pass/recursion_pass.fcl
	@echo "Test9: "
	python fhiclpy.py < testFiles/pass/ref_pass.fcl
	@echo "Test10: "
	python fhiclpy.py < testFiles/pass/seq_pass.fcl
	@echo "Test11: "
	python fhiclpy.py < testFiles/pass/string_pass.fcl
	@echo "Test12: "
	python fhiclpy.py < testFiles/pass/table_pass.fcl
	@echo "Test13: "
	python fhiclpy.py < testFiles/pass/hname_pro_pass.fcl
	@echo "Test14: "
	python fhiclpy.py < testFiles/pass/hname2_pass.fcl  
	@echo "Test15: "    
	python fhiclpy.py < testFiles/pass/override_pass.fcl
	@echo "Test16: "
	python fhiclpy.py < testFiles/pass/override2_pass.fcl
	@echo "Test17: "
	python fhiclpy.py < testFiles/pass/combo_exist_pass.fcl
	@echo "Test18: "
	python fhiclpy.py < testFiles/pass/combo_new_pass.fcl
	@echo "Test19: "
	python fhiclpy.py < testFiles/pass/adv_num_pass.fcl
	@echo "Test20: "
	python fhiclpy.py < testFiles/pass/adv_string_pass.fcl
	@echo "Test21: "
	python fhiclpy.py < testFiles/pass/adv_ref2_pass.fcl
	@echo "Test22: "
	python fhiclpy.py < testFiles/pass/adv_ref3_pass.fcl
	@echo "Test23: "
	python fhiclpy.py < testFiles/pass/adv_ref4_pass.fcl
	@echo "Test24: "
	python fhiclpy.py < testFiles/pass/adv_ref5_pass.fcl
	@echo "Test25: "
	python fhiclpy.py < testFiles/pass/adv_test_pass.fcl
	@echo "Test26: "
	python fhiclpy.py < testFiles/pass/bool_pass.fcl
	@echo "Test27: "
	python fhiclpy.py < testFiles/pass/leading_zero_pass.fcl
	@echo "**************************END OF EXPECTED SUCCESSES*********************************"
test_fail: fhiclpy.py
	@echo "*************************START OF EXPECTED FAILURES********************************"
	@echo "Test1: "
	python fhiclpy.py < testFiles/fail/assoc_fail.fcl
	@echo "Test2: "
	python fhiclpy.py < testFiles/fail/assoc2_fail.fcl
	@echo "Test3: "
	python fhiclpy.py < testFiles/fail/hname_fail.fcl
	@echo "Test4: "
	python fhiclpy.py < testFiles/fail/include_fail.fcl
	@echo "Test5: "
	python fhiclpy.py < testFiles/fail/include2_fail.fcl
	@echo "Test6: "
	python fhiclpy.py < testFiles/fail/include3_fail.fcl
	@echo "Test7: "
	python fhiclpy.py < testFiles/fail/name_fail.fcl
	@echo "Test8: "
	python fhiclpy.py < testFiles/fail/prolog2_fail.fcl
	@echo "Test9: "
	python fhiclpy.py < testFiles/fail/prolog_fail.fcl
	@echo "Test10: "
	python fhiclpy.py < testFiles/fail/ref_fail.fcl
	@echo "Test11: "
	python fhiclpy.py < testFiles/fail/seq_fail.fcl
	@echo "Test12: "
	python fhiclpy.py < testFiles/fail/table_fail.fcl
	@echo "Test13: "
	python fhiclpy.py < testFiles/fail/adv_string_fail.fcl
	@echo "Test14: "
	python fhiclpy.py < testFiles/fail/adv_ref_fail.fcl
	@echo "**************************END OF EXPECTED FAILURES*********************************"
