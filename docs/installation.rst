
Installation & Quick Guide
==================================================

Installation
------------

The package is installed using the pip command 

.. code-block:: bash

   pip install pg-eodms-rapi

The installation will also add the following packages:


* `dateparser <https://dateparser.readthedocs.io/en/latest/>`_
* `Requests <https://docs.python-requests.org/en/master/>`_
* `tqdm <https://tqdm.github.io/>`_
* `geomet <https://pypi.org/project/geomet/>`_

The package does not require the installation of the GDAL package. However, GDAL has to be installed if you wish to use ESRI Shapefiles.

Initializing the EODMSRAPI
--------------------------

The EODMSRAPI class is the object which contains the methods and functions used to access the EODMS REST API service.

.. code-block:: python

   from eodms_rapi import EODMSRAPI

Initialization of the EODMSRAPI requires entry of a password from a valid EODMS account. 

.. note::
	If you do not have an EODMS account, please visit https://www.eodms-sgdot.nrcan-rncan.gc.ca/index-en.html and click the **Register (Required to Order)** link under **Account**.

.. code-block:: python

   rapi = EODMSRAPI('eodms-username', 'eodms-password')

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
