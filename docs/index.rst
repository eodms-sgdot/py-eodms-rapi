=======================================
EODMS RAPI Python Package Documentation
=======================================

EODMS RAPI Client is a Python3 package used to access the REST API service provided by the `Earth Observation Data Management System (EODMS) <https://www.eodms-sgdot.nrcan-rncan.gc.ca/index-en.html>`_ from Natural Resources Canada.

This package requires Python 3.6 or higher (it was designed using Python 3.7).

Installation
------------

The package is installed using the pip command 

.. code-block:: bash

   pip install py-eodms-rapi -U

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
   rapi.set_field_convention('upper')
   res = rapi.get_results('full')

   # Now order the images
   order_res = rapi.order(res)

   # Download images to a specific destination
   dest = "C:\\TEMP"
   dn_res = rapi.download(order_res, dest)

   # Print results
   rapi.print_results(dn_res)
   
   # Clear search results
   rapi.clear_results()

Contents
--------

.. toctree::
	:maxdepth: 3
	:caption: User Guide
   
	initialization
	search-rapi
	order
	download
	examples
	
.. toctree::
	:maxdepth: 4
	:caption: API
   
	eodms_rapi.rst

Support
-------

If you have any issues or questions, please contact the EODMS Support Team at `eodms-sgdot@nrcan-rncan.gc.ca <mailto:eodms-sgdot@nrcan-rncan.gc.ca?subject=EODMS RAPI Client>`_.

Acknowledgements
----------------

Some code in this package is based off the `EODMS API Client <https://pypi.org/project/eodms-api-client/>`_ designed by Mike Brady.

License
-------

Copyright (c) His Majesty the King in Right of Canada, as
represented by the Minister of Natural Resources, 2024.

Licensed under the MIT license
(see LICENSE or <http://opensource.org/licenses/MIT>) All files in the 
project carrying such notice may not be copied, modified, or distributed 
except according to those terms.
