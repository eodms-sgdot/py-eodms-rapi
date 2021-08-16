# eodms_rapi package

## eodms_rapi.eodms module

### class eodms_rapi.eodms.EODMSRAPI(username, password)

Bases: `object`


#### download(items, dest, wait=10.0)
Downloads a list of order items from the EODMS RAPI.


* **Parameters**

    
    * **items** (*list** or **dict*) – A list of order items returned from the RAPI.

    Example:

		{'items': 
			[
				{'recordId': '8023427', 
				'status': 'SUBMITTED', 
				'collectionId': 'RCMImageProducts', 
				'itemId': '346204', 
				'orderId': '50975'}, 
				...
			]
		}

    or

		[
			{'recordId': '8023427', 
			'status': 'SUBMITTED', 
			'collectionId': 'RCMImageProducts', 
			'itemId': '346204', 
			'orderId': '50975'}, 
			...
		]



    * **dest** (*str*) – The local download folder location.


    * **wait** (*float** or **int*) – Sets the time to wait before checking the status of all orders.



#### get_availableFields(collection=None, name_type='title')
Gets a dictionary of available fields for a collection from the RAPI.


* **Parameters**

    **collection** (*str*) – The Collection ID.



* **Returns**

    A dictionary containing the available fields for the given
    collection.



* **Return type**

    dict



#### get_collections(as_list=False, titles=False, redo=False)
Gets a list of available collections for the current user.


* **Parameters**

    **as_list** (*bool*) – Determines the type of return. If False, a dictionary
    will be returned. If True, only a list of collection
    IDs will be returned.



* **Returns**

    Either a dictionary of collections or a list of collection IDs
    depending on the value of as_list.



* **Return type**

    dict



#### get_order(orderId)
Gets an specified order from the EODMS RAPI.


* **Parameters**

    **orderId** (*str** or **int*) – The Order ID of the specific order.



* **Returns**

    A JSON dictionary of the specific order.



* **Return type**

    dict



#### get_orderItem(itemId)
Submits a query to the EODMS RAPI to get a specific order item.


* **Parameters**

    **itemId** (*str** or **int*) – The Order Item ID of the image to retrieve from the RAPI.



* **Returns**

    A dictionary containing the JSON format of the results from the RAPI.



* **Return type**

    dict



#### get_orderParameters(collection, recordId)
Gets the list of available Order parameters for a given image record.


* **Parameters**

    
    * **collection** (*str*) – The Collection ID for the query.


    * **recordId** (*int** or **str*) – The Record ID for the image.



* **Returns**

    A JSON dictionary of the order parameters.



* **Return type**

    dict



#### get_orders(dtstart=None, dtend=None, maxOrders=10000, format='json')
Sends a query to retrieve orders from the RAPI.


* **Parameters**

    
    * **dtstart** (*datetime.datetime*) – The start date for the date range of the query.


    * **dtend** (*datetime.datetime*) – The end date for the date range of the query.


    * **maxOrders** (*int*) – The maximum number of orders to retrieve.


    * **format** (*str*) – The format of the results.



* **Returns**

    A JSON dictionary of the query results containing the orders.



* **Return type**

    dict



#### get_ordersByRecords(records)
Gets a list of orders from the RAPI based on a list of records.


* **Parameters**

    **records** (*list*) – A list of records used to get the list of orders.



* **Returns**

    A list of results from the RAPI.



* **Return type**

    list



#### get_results(form='raw')
Gets the self.results in a given format


* **Parameters**

    **form** (*str*) – The type of format to return.

    Available options:


    * `raw`: Returns the JSON results straight from the RAPI.


    * `full`: Returns a JSON with full metadata information.


    * `geojson`: Returns a FeatureCollection of the results

        (requires geojson package).




* **Returns**

    A dictionary of the results from self.results variable.



* **Return type**

    dict



#### order(results, priority='Medium', parameters=None, destinations=[])
Sends an order to EODMS using the RAPI.


* **Parameters**

    
    * **results** (*list*) – A list of JSON results from the RAPI.

    The results list must contain a `collectionId` key and
    a `recordId` key for each image.



    * **priority** (*str** or **list*) – Determines the priority of the order.

    If you’d like to specify a separate priority for each image,
    pass a list of dictionaries containing the `recordId` (matching
    the IDs in results) and `priority`, such as:

    `[{"recordId": 7627902, "priority": "Low"}, ...]`

    Priority options: “Low”, “Medium”, “High” or “Urgent”



    * **parameter** (*list*) – Either a list of parameters or a list of record items.

    Use the get_orderParameters method to get a list of available parameters.

    **Parameter list**: `[{"|internalName|": "|value|"}, ...]`

    > Example: `[{"packagingFormat": "TARGZ"}, {"NOTIFICATION_EMAIL_ADDRESS": "kevin.ballantyne@canada.ca"}, ...]`

    **Parameters for each record**: `[{"recordId": |recordId|, "parameters": [{"|internalName|": "|value|"}, ...]}]`

    > Example: `[{"recordId": 7627902, "parameters": [{"packagingFormat": "TARGZ"}, ...]}]`




#### remove_orderItem(orderId, itemId)
Removes an Order Item from the EODMS using the RAPI.


* **Parameters**

    
    * **orderId** (*int** or **str*) – The Order ID of the Order Item to remove.


    * **itemId** (*int** or **str*) – The Order Item ID of the Order Item to remove.



* **Returns**

    Returns the contents of the Delete request (always empty).



* **Return type**

    byte str



#### search(collection, filters=None, feats=None, dates=None, resultField=[], maxResults=None)
Sends a search to the RAPI to search for image results.


* **Parameters**

    
    * **collection** (*str*) – The Collection ID for the query.


    * **filters** (*dict*) – A dictionary of query filters and values in

        the following format:

    `{"|filter title|": ("|operator|", ["value1", "value2", ...]), ...}`

    Example: `{"Beam Mnemonic": {'=': []}}`



    * **feats** (*list*) – A list of tuples containing the operator and filenames or coordinates of features to use in the search. The features can be:


        * a filename (ESRI Shapefile, KML, GML or GeoJSON)


        * a WKT format string


        * the ‘geometry’ entry from a GeoJSON Feature


        * a list of coordinates (ex: `[(x1, y1), (x2, y2), ...]`)



    * **dates** (*list*) – A list of date range dictionaries with keys `start` and `end`.
    The values of the `start` and `end` can either be a string in format
    `yyyymmdd_hhmmss` or a datetime.datetime object.

    Example:

        `[{"start": "20201013_120000", "end": "20201013_150000"}]`



    * **resultField** (*str*) – A name of a field to include in the query results.


    * **maxResults** (*str** or **int*) – The maximum number of results to return from the query.



#### set_attempts(number)
Sets number of attempts to be made to the RAPI before the script
ends.


* **Parameters**

    **number** (*int*) – The value for the number of attempts.



#### set_fieldConvention(convention)
Sets the naming convention of the output fields.


* **Parameters**

    **convention** (*str*) – The type of naming convention for the fields.


    * `words`: The label with spaces and words will be returned.


    * `camel` (default): The format will be lower camel case like ‘camelCase’.


    * `upper`: The format will be all uppercase with underscore for spaces.




#### set_orderTimeout(timeout)
Sets the timeout limit for an order to the RAPI.


* **Parameters**

    **timeout** (*float*) – The value of the timeout in seconds.



#### set_queryTimeout(timeout)
Sets the timeout limit for a query to the RAPI.


* **Parameters**

    **timeout** (*float*) – The value of the timeout in seconds.



### class eodms_rapi.eodms.QueryError(msg)
Bases: `object`

The QueryError class is used to store error information for a query.

## eodms_rapi.geo module


### class eodms_rapi.geo.EODMSGeo(eodmsrapi)
Bases: `object`

The Geo class contains all the methods and functions used to perform

    geographic processes mainly using OGR.


#### add_geom(in_src)
Processes the source and converts it for use in the RAPI.


* **Parameters**

    **in_src** (*str*) – The in_src can either be:


    * a filename (ESRI Shapefile, KML, GML or GeoJSON) of multiple features


    * a WKT format string of a single feature


    * the ‘geometry’ entry from a GeoJSON Feature


    * a list of coordinates (ex: `[(x1, y1), (x2, y2), ...]`)




* **Returns**

    A string of the WKT of the feature.



* **Return type**

    str



#### convert_coords(coord_lst, geom_type)
Converts a list of points to GeoJSON format.


* **Parameters**

    
    * **coord_lst** (*list*) – A list of points.


    * **geom_type** (*str*) – The type of geometry, either ‘Point’,
    ‘LineString’ or ‘Polygon’.



* **Returns**

    A dictionary in the GeoJSON format.



* **Return type**

    dict



#### convert_fromWKT(in_feat)
Converts a WKT to a GDAL geometry.


* **Parameters**

    **in_feat** (*str*) – The WKT of the feature.



* **Returns**

    The polygon geometry of the input WKT.



* **Return type**

    ogr.Geometry



#### convert_imageGeom(coords, output='array')
Converts a list of coordinates from the RAPI to a polygon geometry,

    array of points or as WKT.


* **Parameters**

    
    * **coords** (*list*) – A list of coordinates from the RAPI results.


    * **output** (*str*) – The type of return, can be ‘array’, ‘wkt’ or ‘geom’.



* **Returns**

    Either a polygon geometry, WKT or array of points.



* **Return type**

    multiple types



#### convert_toGeoJSON(results)
Converts a get of RAPI results to GeoJSON geometries.


* **Parameters**

    **results** (*list*) – A list of results from the RAPI.



* **Returns**

    A dictionary of a GeoJSON FeatureCollection.



* **Return type**

    dict



#### convert_toWKT(in_feat, in_type)
Converts a feature into WKT format.


* **Parameters**

    **in_feat** (*dict** or **list*) – The input feature, either as a GeoJSON
    dictionary or list of points.



* **Returns**

    The input feature converted to WKT.



* **Return type**

    str



#### get_features(in_src)
Extracts the features from an AOI file.


* **Parameters**

    **in_src** (*str*) – The input filename of the AOI file. Can either be
    a GML, KML, GeoJSON, or Shapefile.



* **Returns**

    The AOI in WKT format.



* **Return type**

    str


## Module contents
