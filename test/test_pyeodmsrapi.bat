SET EODMS_USER=kballan_test
SET EODMS_PASSWORD=wtLotiD3#

cd ..

python setup.py install

cd test

python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_search
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_orderparameters
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_deleteorder
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_availablefields
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_multiple_searches

pause