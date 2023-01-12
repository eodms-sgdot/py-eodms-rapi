cd ..

python setup.py install

cd test

python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_search
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_orderparameters
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_deleteorder
python -m unittest test_pyeodmsrapi.TestEodmsRapi.test_availablefields

pause