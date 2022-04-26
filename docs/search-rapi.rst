
Submit an Image Search
======================

You can perform a search on the RAPI using the ``search`` method of the EODMSRAPI.

However, before submitting a search, you'll have to create the items used to filter the results. The ``search`` function requires a **Collection** name and optional **filters**\ , **geometry features**\ , **dates**\ , **result fields** and **maximum results** values.

Collection
----------

The Collection ID has to be specified when submitting a search.

To get a list of Collection IDs, use:

.. code-block:: python

   >>> print(rapi.get_collections(as_list=True))
   | EODMSRAPI | Getting Collection information, please wait...
   ['NAPL', 'SGBAirPhotos', 'RCMImageProducts', 'COSMO-SkyMed1', 'Radarsat1', 'Radarsat1RawProducts', 'Radarsat2', 'Radarsat2RawProducts', 'RCMScienceData', 'TerraSarX', 'DMC', 'Gaofen-1', 'GeoEye-1', 'IKONOS', 'IRS', 'PlanetScope', 'QuickBird-2', 'RapidEye', 'SPOT', 'WorldView-1', 'WorldView-2', 'WorldView-3', 'VASP']

Geometry Features
-----------------

The **geometry features** are a list of tuples with each tuple containing an operator and a specified geometry (\ ``[(<operator>, <geometry>), ...]``\ ).

The *operator* can be **contains**\ , **contained by**\ , **crosses**\ , **disjoint with**\ , **intersects**\ , **overlaps**\ , **touches**\ , and **within**\ .

.. note::
    The *operator* is not case sensitive. However, the *geometry* value(s) should follow the proper formatting and cases for their type (i.e. follow the proper formatting for GeoJSON, WKT, etc.).

The *geometry* can be:

+-------------+-------------------------------------------+----------------------------------------------------------------------------------+
| Type        | Info                                      | Example                                                                          |
+=============+===========================================+==================================================================================+
| A filename  | - | Can be a ESRI Shapefile, KML, GML or  | .. code-block:: python                                                           |
|             |   | GeoJSON                               |                                                                                  |
|             | - | Can contain points, lines or          |     feats = [('contains', 'C:\\TEMP\\test.geojson')]                             |
|             |   | polygons and have multiple features   |                                                                                  |
+-------------+-------------------------------------------+----------------------------------------------------------------------------------+
| WKT format  | - Can be a point, line or polygon.        | .. code-block:: python                                                           |
|             |                                           |                                                                                  |
|             |                                           |     feats = [                                                                    |
|             |                                           |            ('intersects', 'POINT (-75.92790414335645721 45.63414106580390239)'), |
|             |                                           |            ('intersects', 'POINT (-76.04462125987681986 46.23234274318053849)')  |
|             |                                           |     ]                                                                            |
+-------------+-------------------------------------------+----------------------------------------------------------------------------------+
| GeoJSON     | - | The 'geometry' entry from a GeoJSON   | .. code-block:: python                                                           |
|             |   | Feature.                              |                                                                                  |
|             | - | Can be a point, line or polygon.      |     ('within', {                                                                 |
|             |                                           |         "type":"Polygon",                                                        |
|             |                                           |         "coordinates":[                                                          |
|             |                                           |             [                                                                    |
|             |                                           |                 [-75.71484393257714,45.407703298380106],                         |
|             |                                           |                 [-75.6962772564671,45.40738537380734],                           |
|             |                                           |                 [-75.69343667852566,45.39264326981817],                          |
|             |                                           |                 [-75.71826085966613,45.390764097853655],                         |
|             |                                           |                 [-75.71484393257714,45.407703298380106]                          |
|             |                                           |             ]                                                                    |
|             |                                           |         ]                                                                        |
|             |                                           |     })                                                                           |
+-------------+-------------------------------------------+----------------------------------------------------------------------------------+
| Coordinates | - | A list of coordinates of a polygon    | .. code-block:: python                                                           |
|             |   | (ex: ```[(x1, y1), (x2, y2), ...]```) |                                                                                  |
|             | - | A single point (ex: ```[(x1, y1)]```) |     feats = [                                                                    |
|             |                                           |            ('contains', [                                                        |
|             |                                           |                (-75.71, 45.41),                                                  |
|             |                                           |                (-75.70, 45.41),                                                  |
|             |                                           |                (-75.69, 45.39),                                                  |
|             |                                           |                (-75.72, 45.39),                                                  |
|             |                                           |                (-75.71, 45.41)                                                   |
|             |                                           |            ]                                                                     |
|             |                                           |        )                                                                         |
|             |                                           |     ]                                                                            |
+-------------+-------------------------------------------+----------------------------------------------------------------------------------+ 

.. note::
    The `GDAL Python package <https://pypi.org/project/GDAL/>`_ is required if you wish to use shapefiles.

WKT example to get results for the easternmost and westernmost points of Canada:

.. code-block:: python

   >>> feats = [('intersects', 'POINT (-141.001944 60.306389)'), ('intersects', 'POINT (-52.619444 47.523611)')]

Date Range(s)
-------------

The **date range** is either:

- A list of date range dictionaries containing a *start* and *end* key. The date values should be in format *YYYYMMDD_HHMMSS*.
- A date of a previous time interval (ex: '24 hours', '7 days'). Available intervals are 'hour', 'day', 'week', 'month' or 'year' (plural is permitted).

For example, to search for images between January 1, 2019 at midnight to September 15, 2019 at 3:35:55 PM and in the last 3 days, use:

.. code-block:: python

   >>> dates = [{"start": "20190101_000000", "end": "20190915_153555"}, "3 days"]

Query Filter(s)
---------------

The **query** variable is a dictionary containing filter titles as keys and tuples with the operator and filter value such as: ``{<field>: (<operator>, <value(s)>), ...}``

Example of beam mnemonic filter: ``{'Beam Mnemonic': ('like', ['16M%', '3M11'])}``

The *operator* can be one of the following: **=**\ , **<**\ , **>**\ , **<>**\ , **<=**\ , **>=**\ , **like**\ , **starts with**\ , **ends with**\ , or **contains**.

.. note::
    The *operator* is not case sensitive. However, *fields* and *values* are case sensitive.

The following example will search for images with **Beam Mnemonic** that equals '3M11' or contains '16M' and with **Incidence Angle** greater than or equal to 45 degrees:

.. code-block:: python

   >>> filters = {'Beam Mnemonic': ('like', 'SC50%'), 'Incidence Angle': ('<=', '45')}

Get Available Fields
--------------------

You can get a list of available query fields using the ``get_available_fields`` and passing the **Collection ID**.

There are 3 ways to get the available fields for a Collection using the **\ *name_type*\ ** argument of the ``get_available_fields`` function:

+-------------+-------------------------------------------+-----------------------------------------------------------------------------+
| Value       | Description                               | Results                                                                     |
+=============+===========================================+=============================================================================+
| empty       | | Gets the raw field information from the | .. code-block:: python                                                      |
|             | | RAPI.                                   |                                                                             |
|             |                                           |     print(rapi.get_available_fields('RCMImageProducts'))                    |
|             |                                           |         {'search': {                                                        |
|             |                                           |             'Special Handling Required': {                                  |
|             |                                           |                 'id': 'RCM.SPECIAL_HANDLING_REQUIRED',                      |
|             |                                           |                 'datatype': 'String'},                                      |
|             |                                           |             'Client Order Number': {                                        |
|             |                                           |                 'id': 'ARCHIVE_IMAGE.CLIENT_ORDER_NUMBER',                  |
|             |                                           |                 'datatype': 'String'},                                      |
|             |                                           |             ...},                                                           |
|             |                                           |         'results': {                                                        |
|             |                                           |             'Buyer Id': {                                                   |
|             |                                           |                 'id': 'ARCHIVE_IMAGE.AGENCY_BUYER',                         |
|             |                                           |                 'datatype': 'Integer'},                                     |
|             |                                           |             'Archive Visibility Start Date': {                              |
|             |                                           |                 'id': 'ARCHIVE_IMAGE.ARCH_VISIBILITY_START',                |
|             |                                           |                 'datatype': 'Date'},                                        |
|             |                                           |             ...}                                                            |
|             |                                           |         }                                                                   |
+-------------+-------------------------------------------+-----------------------------------------------------------------------------+
| **id**      | Gets a list of field IDs.                 | .. code-block:: python                                                      |
|             |                                           |                                                                             |
|             |                                           |     print(rapi.get_available_fields('RCMImageProducts', name_type='id'))    |
|             |                                           |         {'search': [                                                        |
|             |                                           |             'RCM.SPECIAL_HANDLING_REQUIRED',                                |
|             |                                           |             'ARCHIVE_IMAGE.CLIENT_ORDER_NUMBER',                            |
|             |                                           |             ...],                                                           |
|             |                                           |         'results': [                                                        |
|             |                                           |             'ARCHIVE_IMAGE.AGENCY_BUYER',                                   |
|             |                                           |             'ARCHIVE_IMAGE.ARCH_VISIBILITY_START',                          |
|             |                                           |             ...]                                                            |
|             |                                           |         }                                                                   |
+-------------+-------------------------------------------+-----------------------------------------------------------------------------+
| **title**   | | Gets a list of field names (these are   | .. code-block:: python                                                      |
|             | | used when performing a search using the |                                                                             |
|             | | EODMSRAPI).                             |     print(rapi.get_available_fields('RCMImageProducts', name_type='title')) |
|             |                                           |         {'search': [                                                        |
|             |                                           |             'Special Handling Required',                                    |
|             |                                           |             'Client Order Number',                                          |
|             |                                           |             ...],                                                           |
|             |                                           |         'results': [                                                        |
|             |                                           |             'Buyer Id', 'Archive Visibility Start Date',                    |
|             |                                           |             ...]                                                            |
|             |                                           |         }                                                                   |
+-------------+-------------------------------------------+-----------------------------------------------------------------------------+

Get Available Field Choices
---------------------------

Some fields have specific choices that the user can enter. These values are included in the ``get_available_fields`` *empty* results, however the function ``get_field_choices`` in the EODMSRAPI offers results easier to manipulate.

The ``get_field_choices`` function requires a **Collection ID** and an optional **field** name or ID. If no field is specified, all fields and choices for the specified Collection will be returned.

Example of choices for the Polarization field in RCM:

.. code-block:: python

   >>> rapi.get_field_choices('RCMImageProducts', 'Polarization')
   ['CH CV', 'HH', 'HH HV', 'HH HV VH VV', 'HH VV', 'HV', 'VH', 'VH VV', 'VV']

Result Fields
-------------

The next value to set is the **result fields**. The raw JSON results from the RAPI returns only a select few fields. For example, when searching RCM images, the RAPI only returns metadata for these Field IDs:

.. code-block::

   RCM.ORBIT_REL
   ARCHIVE_IMAGE.PROCESSING_DATETIME
   ARCHIVE_IMAGE.PRODUCT_TYPE
   IDX_SENSOR.SENSOR_NAME
   RCM.SBEAMFULL
   RCM.POLARIZATION
   RCM.SPECIAL_HANDLING_REQUIRED_R
   CATALOG_IMAGE.START_DATETIME
   RELATED_PRODUCTS
   RCM.SPECIAL_HANDLING_INSTRUCTIONS
   Metadata
   RCM.DOWNLINK_SEGMENT_ID

If you want more fields returned, you can create a list and add Field IDs (found in the 'results' entry of the ``get_available_fields`` method results, in bold below) of fields you'd like included in the results JSON.


.. code-block:: python

	>>> print(rapi.get_available_fields('RCMImageProducts'))
       {'search': 
           {
               [...]
           }, 
       'results': 
           {
               'Buyer Id': {'id': ' \*ARCHIVE_IMAGE.AGENCY_BUYER*\ ', 'datatype': 'Integer'}, 
               [...]
           }
       }


.. note::
    The **result fields** parameter is not necessary if you use the 'full' option when getting the results after the search; see `Get Results <#get-results>`_ for more information.

For example, the following will include the Processing Facility and Look Orientation of the images:

.. code-block:: python

   >>> result_fields = ['ARCHIVE_RCM.PROCESSING_FACILITY', 'RCM.ANTENNA_ORIENTATION']

Submit Search
-------------

Now submit the search, in this example, setting the **Collection ID** to 'RCMImageProducts' and **max results** to 100:

.. code-block:: python

   >>> rapi.search("RCMImageProducts", filters=filters, features=feats, dates=dates, result_fields=result_fields, maxResults=100)

Get Results
-----------

Before getting the results, set the field type to return:

*
  **camel** (default): All field names will be in lower camelcase (ex: fieldName)
*
  **upper**\ : Field names will be in upper case with underscore for spaces (ex: FIELD_NAME)
*
  **words**\ : Field names will be English words (ex: Field Name)

.. code-block:: python

   >>> rapi.set_field_convention('upper')

.. note::
    Changing the field name convention does not apply when using the 'raw' parameter for the ``get_results`` method.

Now to get the results of your search using the ``get_results`` method.

There are three options for getting results:

*
  **raw** (default): The raw JSON data results from the RAPI. Only the basic fields and the fields you specified in the result_fields will be returned.

	.. code-block:: python

		>>> print(rapi.get_results('raw'))
		[
		   {
			   "recordId": "7822244",
			   "overviewUrl": "http://was-eodms.compusult.net/wes/images/No_Data_Available.png",
			   "collectionId": "RCMImageProducts",
			   "metadata2": [
				   {
					   "id": "RCM.ANTENNA_ORIENTATION",
					   "value": "Right",
					   "label": "Look Orientation"
				   },
				   {
					   "id": "ARCHIVE_IMAGE.PROCESSING_DATETIME",
					   "value": "2020-11-09 13:49:14 GMT",
					   "label": "Processing Date"
				   },
				   {
					   "id": "ARCHIVE_IMAGE.PRODUCT_TYPE",
					   "value": "GRD",
					   "label": "Type"
				   },
				   [...]
			   ],
			   "rapiOrderUrl": "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi/order/direct?collection=RCMImageProducts&recordId=7822244&destination=fill_me_in",
			   "geometry": {
				   "type": "Polygon",
				   "coordinates": [
					   [
						   [
							   -111.2061013084167,
							   62.4209316874871
						   ],
						   [
							   -111.2710554014949,
							   62.22606212562155
						   ],
						   [
							   -110.6882156023417,
							   62.18309404584561
						   ],
						   [
							   -110.6194709629304,
							   62.3778734605923
						   ],
						   [
							   -111.2061013084167,
							   62.4209316874871
						   ]
					   ]
				   ]
			   },
			   "title": "RCM2_OK1370026_PK1375301_3_16M17_20201109_134014_HH_HV_GRD",
			   "orderExecuteUrl": "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/Client/?entryPoint=preview#?cseq=RCMImageProducts&record=7822244",
			   "thumbnailUrl": "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/getObject?FeatureID=62f0e816-8006-4768-8f32-6ef4008e6895-7822244&ObjectType=Thumbview&collectionId=RCMImageProducts",
			   "metadataUrl": "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/Client/?entryPoint=resultDetails&resultId=7822244&collectionId=RCMImageProducts",
			   "isGeorectified": "False",
			   "collectionTitle": "RCM Image Products",
			   "isOrderable": "True",
			   "thisRecordUrl": "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi/record/RCMImageProducts/7822244",
			   "metadata": [
				   [
					   "Look Orientation",
					   "Right"
				   ],
				   [...]
			   ]
		   },
		   [...]
		]


* 
  **full**\ : The full metadata for each image in the results from the RAPI.

    .. note::
       When running the ```get_results``` function for the first time, the 'full' option will require calls to the RAPI to fetch all the metadata for each image. This can take time depending on the number of images returned from the search.

    The following example is the output from the 'full' results returned from the RAPI when using the 'upper' field name convention:

	.. code-block:: python

	   >>> print(rapi.get_results('full'))
	   | EODMSRAPI | Fetching result metadata: 100%|████████████████████████████████████████| 29/29 [00:07<00:00,  3.81item/s]
	   [
		   {
			   "RECORD_ID": "8572605",
			   "COLLECTION_ID": "RCMImageProducts",
			   "GEOMETRY": {
				   "type": "Polygon",
				   "coordinates": [
					   [
						   [
							   -75.87136946742638,
							   45.53642826726489
						   ],
						   [
							   -75.88537895138599,
							   45.47880111111606
						   ],
						   [
							   -75.63233378406722,
							   45.44847937835439
						   ],
						   [
							   -75.61805821213746,
							   45.50610429149886
						   ],
						   [
							   -75.87136946742638,
							   45.53642826726489
						   ]
					   ]
				   ]
			   },
			   "TITLE": "rcm_20210407_N4549W07575",
			   "COLLECTION_TITLE": "RCM Image Products",
			   "IS_ORDERABLE": true,
			   "THIS_RECORD_URL": "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi/record/RCMImageProducts/8572605",
			   "ABSOLUTE_ORBIT": "9917.0",
			   "ACQUISITION_END_DATE": "2021-04-07 11:12:05 GMT",
			   "ACQUISITION_START_DATE": "2021-04-07 11:12:04 GMT",
			   "ARCHIVE_VISIBILITY_START_DATE": "2021-04-07 11:12:04 GMT",
			   "BEAM_MNEMONIC": "FSL22",
			   "BEAM_MODE_DEFINITION_ID": "422",
			   [...]
			   "VISIBILITY_RESTRICTION_EXPIRY_DATE": "2021-04-07 11:12:06 GMT",
			   "WITHIN_ORBIT_TUBE": "true",
			   "WKT_GEOMETRY": "POLYGON ((-75.8713694674264 45.5364282672649 0,-75.885378951386 45.4788011111161 0,-75.6323337840672 45.4484793783544 0,-75.6180582121375 45.5061042914989 0,-75.8713694674264 45.5364282672649 0))"
		   },
		   [...]
	   ]


* 
  **geojson**\ : The results will be returned in GeoJSON format.

    .. note:
       When running the ```get_results``` function for the first time, the 'geojson' option will require calls to the RAPI to fetch all the metadata for each image. This can take time depending on the number of images returned from the search.

    The following example is the output from the 'geojson' results returned from the RAPI when using the 'upper' field name convention:

	.. code-block:: python

	   >>> print(rapi.get_results('geojson'))
	   | EODMSRAPI | Fetching result metadata: 100%|████████████████████████████████████████| 29/29 [00:07<00:00,  3.86item/s]
	   {
		   "type": "FeatureCollection",
		   "features": [
			   {
				   "type": "Feature",
				   "geometry": {
					   "type": "Polygon",
					   "coordinates": [
						   [
							   [
								   -75.87136946742638,
								   45.53642826726489
							   ],
							   [
								   -75.88537895138599,
								   45.47880111111606
							   ],
							   [
								   -75.63233378406722,
								   45.44847937835439
							   ],
							   [
								   -75.61805821213746,
								   45.50610429149886
							   ],
							   [
								   -75.87136946742638,
								   45.53642826726489
							   ]
						   ]
					   ]
				   },
				   "properties": {
					   "RECORD_ID": "8572605",
					   "COLLECTION_ID": "RCMImageProducts",
					   "GEOMETRY": {
						   "type": "Polygon",
						   "coordinates": [
							   [
								   [
									   -75.87136946742638,
									   45.53642826726489
								   ],
								   [
									   -75.88537895138599,
									   45.47880111111606
								   ],
								   [
									   -75.63233378406722,
									   45.44847937835439
								   ],
								   [
									   -75.61805821213746,
									   45.50610429149886
								   ],
								   [
									   -75.87136946742638,
									   45.53642826726489
								   ]
							   ]
						   ]
					   },
					   [...]
					   "VISIBILITY_RESTRICTION_EXPIRY_DATE": "2021-04-07 11:12:06 GMT",
					   "WITHIN_ORBIT_TUBE": "true",
					   "WKT_GEOMETRY": "POLYGON ((-75.8713694674264 45.5364282672649 0,-75.885378951386 45.4788011111161 0,-75.6323337840672 45.4484793783544 0,-75.6180582121375 45.5061042914989 0,-75.8713694674264 45.5364282672649 0))"
				   }
			   },
			   [...]
		   ]
	   }

.. code-block:: python

   >>> res = rapi.get_results('full')

Print Results
-------------

The EODMSRAPI has a ``print_results`` function which will print the results in pretty print. You can pass a specific results from the RAPI to the function. If not, the 'full' results will be printed. 

.. note::
    If you haven't run ``get_results`` prior to ``print_results``\ , the EODMSRAPI will first fetch the full metadata which can some time depending on the number of results.

.. code-block:: python

   >>> rapi.print_results()

.. note::
    In Linux, if you get the error ``UnicodeEncodeError: 'ascii' codec can't encode character...``\ , add ``export LC_CTYPE=en_US.UTF-8`` to the "~/.bashrc" file and run ``source ~/.bashrc``.

Full Search Code Example
------------------------

.. code-block:: python

   from eodms_rapi import EODMSRAPI

   # Initialize EODMSRAPI using your EODMS account credentials
   rapi = EODMSRAPI('eodms-username', 'eodms-password')

   # Set features using the easternmost and westernmost points of Canada in WKT format
   feats = [('intersects', 'POINT (-141.001944 60.306389)'), \
           ('intersects', 'POINT (-52.619444 47.523611)')]

   # Set date ranges
   dates = [{"start": "20190101_000000", "end": "20190915_153555"}, 
           {"start": "20201013_120000", "end": "20201113_150000"}]

   # Set search filters
   filters = {'Beam Mnemonic': ('like', 'SC50%'), \
               'Incidence Angle': ('<=', '45')}

   # Set the results fields
   result_fields = ['ARCHIVE_RCM.PROCESSING_FACILITY', 'RCM.ANTENNA_ORIENTATION']

   # Submit search
   rapi.search("RCMImageProducts", filters, feats, dates, result_fields, 100)

   # Get results
   rapi.set_field_convention('upper')
   res = rapi.get_results('full')

   rapi.print_results(res)
