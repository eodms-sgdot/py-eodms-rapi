
Examples
========

Search, Order and Download
--------------------------

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

Get Available Order Parameters for an Image
-------------------------------------------

.. code-block:: python

   from eodms_rapi import EODMSRAPI

   # Initialize EODMSRAPI using EODMS account credentials
   rapi = EODMSRAPI('username', 'password')

   # Get the order parameters for RCM image with Record ID 7627902
   param_res = rapi.get_order_parameters('RCMImageProducts', '7627902')

   # Print the parameters
   print("param_res: %s" % param_res)

Cancel an Existing Order Item
-----------------------------

.. code-block:: python

   from eodms_rapi import EODMSRAPI

   # Initialize EODMSRAPI using your EODMS account credentials
   rapi = EODMSRAPI('eodms-username', 'eodms-password')

   # Cancel the order item with Order ID 48188 and Order Item ID 289377
   delete_res = rapi.cancel_order_item('48188', '289377')

Get a List of Available Fields for a Collection
-----------------------------------------------

.. code-block:: python

   from eodms_rapi import EODMSRAPI

   # Initialize EODMSRAPI using your EODMS account credentials
   rapi = EODMSRAPI('eodms-username', 'eodms-password')

   # Get the available field information for RCMImageProducts collection
   fields = rapi.get_available_fields('RCMImageProducts')
   print(fields)

   >>> {'search': {'Special Handling Required': {'id': 'RCM.SPECIAL_HANDLING_REQUIRED', 'datatype': 'String'}, ...}, 
       'results': {'Buyer Id': {'id': 'ARCHIVE_IMAGE.AGENCY_BUYER', 'datatype': 'Integer'}, ...}
   }

   # Get a list of available field IDs for RCMImageProducts collection
   field_ids = rapi.get_available_fields('RCMImageProducts', name_type='id')
   print(field_ids)

   >>> {'search': ['RCM.SPECIAL_HANDLING_REQUIRED', 'ARCHIVE_IMAGE.CLIENT_ORDER_NUMBER', ...], 
       'results': ['ARCHIVE_IMAGE.AGENCY_BUYER', 'ARCHIVE_IMAGE.ARCH_VISIBILITY_START', ...]
   }

   # Get a list of available field names used to submit searches (rapi.search())
   field_titles = rapi.get_available_fields('RCMImageProducts', name_type='title')
   print(field_titles)

   >>> {'search': ['Special Handling Required', 'Client Order Number', 'Order Key', ...], 
       'results': ['Buyer Id', 'Archive Visibility Start Date', 'Client Order Item Number', ...]
   }
