from setuptools import find_packages, setup

setup(
    name='py-eodms-rapi',
    version='1.0.0',
    author='Kevin Ballantyne (Natural Resources Canada)',
    author_email='kevin.ballantyne@nrcan-rncan.gc.ca',
    # packages=['package_name', 'package_name.test'],
    packages=find_packages(),
    # scripts=['bin/script1','bin/script2'],
    include_package_data=True, 
    url='https://github.com/nrcan-eodms-sgdot-rncan/py-eodms-rapi',
    license='LICENSE',
    description='A Python package for accessing the EODMS RAPI.',
    long_description=open('README.md').read(),
    install_requires=[
        "dateparser", 
        "requests",
        "tqdm",
        "geomet",
    ],
    python_requires='>=3.6',
)
