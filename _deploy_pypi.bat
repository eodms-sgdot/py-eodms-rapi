echo on

python -m pip install --upgrade twine
python -m twine upload dist/*

pause