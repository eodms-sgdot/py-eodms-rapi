
EODMS RAPI Python Package Documentation
==================================================

EODMS RAPI Client is a Python3 package used to access the REST API service provided by the `Earth Observation Data Management System (EODMS) <https://www.eodms-sgdot.nrcan-rncan.gc.ca/index-en.html>`_ from Natural Resources Canada.

This package requires Python 3.6 or higher (it was designed using Python 3.7).

Installation
------------

The package is installed using the pip command 

.. code-block:: bash

   pip install py-eodms-rapi

The installation will also add the following packages:


* `dateparser <https://dateparser.readthedocs.io/en/latest/>`_
* `Requests <https://docs.python-requests.org/en/master/>`_
* `tqdm <https://tqdm.github.io/>`_
* `geomet <https://pypi.org/project/geomet/>`_

The package does not require the installation of the GDAL package. However, GDAL has to be installed if you wish to use ESRI Shapefiles.

Example Code
------------

An example to search, order and download RCM images:

.. code-block:: python

   from eodms_rapi import EODMSRAPI

   # Initialize EODMSRAPI using your EODMS account credentials
   rapi = EODMSRAPI('eodms-username', 'eodms-password')

   # Set a polygon of geographic centre of Canada using GeoJSON
   feat = [('INTERSECTS', {"type":"Polygon", "coordinates":[[[-95.47,61.4],\
           [-97.47,61.4],[-97.47,63.4],[-95.47,63.4],[-95.47,61.4]]]})]

   # Set date ranges
   dates = [{"start": "20190101_000000", "end": "20210621_000000"}]

   # Set search filters
   filters = {'Beam Mode Type': ('LIKE', ['%50m%']), 
               'Polarization': ('=', 'HH HV'), 
               'Incidence Angle': ('>=', 17)}

   # Set the results fields
   result_fields = ['ARCHIVE_RCM.PROCESSING_FACILITY', 'RCM.ANTENNA_ORIENTATION']

   # Submit search
   rapi.search("RCMImageProducts", filters, feat, dates, result_fields, 2)

   # Get results
   rapi.set_fieldConvention('upper')
   res = rapi.get_results('full')

   # Now order the images
   order_res = rapi.order(res)

   # Download images to a specific destination
   dest = "C:\\TEMP"
   dn_res = rapi.download(order_res, dest)

   # Print results
   rapi.print_results(dn_res)

Contents
--------

.. toctree::
	:maxdepth: 2
	:caption: User Guide
   
	initialization
	search-rapi
	order
	download
	examples
	
.. toctree::
	:maxdepth: 2
	:caption: API
   
	api/eodms_rapi.rst

Support
-------

If you have any issues or questions, please contact the EODMS Support Team at `nrcan.eodms-sgdot.rncan@canada.ca <mailto:nrcan.eodms-sgdot.rncan@canada.ca?subject=EODMS RAPI Client>`_.

Acknowledgements
----------------

Some code in this package is based off the `EODMS API Client <https://pypi.org/project/eodms-api-client/>`_ designed by Mike Brady.

License
-------

MIT License

Copyright (c) 2021 Her Majesty the Queen in Right of Canada, as 
represented by the President of the Treasury Board

Permission is hereby granted, free of charge, to any person obtaining a 
copy of this software and associated documentation files (the "Software"), 
to deal in the Software without restriction, including without limitation 
the rights to use, copy, modify, merge, publish, distribute, sublicense, 
and/or sell copies of the Software, and to permit persons to whom the 
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in 
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
DEALINGS IN THE SOFTWARE.
