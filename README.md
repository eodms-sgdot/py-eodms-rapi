EODMS RAPI Client
=================

## Overview

EODMS RAPI Client is a Python3 package used to access the REST API service provided by the [Earth Observation Data Management System (EODMS)](https://www.eodms-sgdot.nrcan-rncan.gc.ca/index-en.html) from Natural Resources Canada.

## Installation

The package can be installed using pip:

```pip install pg-eodms-rapi```

## Basic Usage

Here are a few examples on how to use the EODMS RAPI Client (```EODMSRAPI```). For full documentation, visit ...

### Search for Images

```python
from eodms_rapi import EODMSRAPI

# Create the EODMSRAPI object
rapi = EODMSRAPI('eodms-username', 'eodms-password')

# Add a point to the search
feat = [('intersects', "POINT (-96.47 62.4)")]

# Create a dictionary of query filters for the search
filters = {'Beam Mnemonic': ('=', ['16M11', '16M13']), 
            'Incidence Angle': ('>=', '35')}

# Set a date range for the search
dates = [{"start": "20200513_120000", "end": "20200613_150000"}]

# Submit the search to the EODMSRAPI, specifying the Collection
rapi.search("RCMImageProducts", filters=filters, features=feat, dates=dates)

# Get the results from the search
res = rapi.get_results('full')

# Print results
rapi.print_results()
```

### Order and Download Images

Using the results from the previous example:

```python
# Submit an order using results
order_res = rapi.order(res)

# Specify a folder location to download the images
dest = "C:\\temp\\py_eodms_rapi"

# Download the images from the order
dn_res = rapi.download(order_res, dest)
```

## Acknowledgements

Some code in this package is based off the [EODMS API Client](https://pypi.org/project/eodms-api-client/) designed by Mike Brady.

## Contact

If you have any questions or require support, please contact the EODMS Support Team at nrcan.eodms-sgdot.rncan@canada.ca.

## License

MIT License