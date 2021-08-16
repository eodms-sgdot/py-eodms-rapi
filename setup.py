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
    description='EODMS RAPI Client is a Python3 package used to access the REST API service provided by the Earth Observation Data Management System (EODMS) from Natural Resources Canada.',
    long_description=open('README.md').read(),
    install_requires=[
        "dateparser", 
        "requests",
        "tqdm",
        "geomet",
    ],
    project_urls={
        "Bug Tracker": "https://github.com/pypa/sampleproject/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
