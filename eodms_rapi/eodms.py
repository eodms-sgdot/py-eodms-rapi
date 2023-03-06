##############################################################################
# MIT License
# 
# Copyright (c) His Majesty the King in Right of Canada, as
# represented by the Minister of Natural Resources, 2022
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.
# 
##############################################################################



import os
# import sys
import requests
# import logging
import logging.config
import traceback
import urllib
import json
# import csv
import datetime
import pytz
import time
# import pprint
import dateparser
import re
import dateutil.parser
from dateutil.tz import tzlocal
from urllib.parse import urlencode
# from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree
from warnings import warn

from tqdm.auto import tqdm

from .geo import EODMSGeo

OTHER_FORMAT = '| %(name)s | %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'

logger = logging.getLogger('EODMSRAPI')

# Set handler for output to terminal
logger.setLevel(logging.DEBUG)
ch = logging.NullHandler()
formatter = logging.Formatter('| %(name)s | %(asctime)s | %(levelname)s: '
                              '%(message)s', '%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)

RECORD_KEYS = ["recordId", "overviewUrl", "collectionId", "metadata2",
               "rapiOrderUrl", "geometry", "title", "orderExecuteUrl",
               "thumbnailUrl", "metadataUrl", "isGeorectified",
               "collectionTitle", "isOrderable", "thisRecordUrl",
               "metadata"]


class QueryError:
    """
    The QueryError class is used to store error information for a query.
    """

    def __init__(self, msgs):
        """
        Initializer for QueryError object which stores an error message.
        
        :param msgs: The error message to print.
        :type  msgs: str
        """

        self.msgs = msgs

    def get_msgs(self, as_str=False):
        """
        Gets the messages stored with the QueryError.
        
        :param as_str: Determines whether to return a string or a list of
        messages.
        :type  as_str: boolean
        
        :return: Either a string or a list of messages.
        :rtype: str or list
        """

        if isinstance(self.msgs, list):
            if as_str:
                return ' '.join(filter(None, self.msgs))

        return self.msgs

    def _set_msgs(self, msgs):
        """
        Sets the messages stored with the QueryError.
        
        :param msgs: Can either be a string or a list of messages.
        :type  msgs: str or list
        
        """
        self.msgs = msgs


class EODMSRAPI:
    """
    The EODMSRAPI Class containing the methods for the eodms_rapi
    """

    def __init__(self, username, password, show_timestamp=True):
        """
        Initializer for EODMSRAPI.
        
        :param username: The username of an EODMS account.
        :type  username: str
        :param password: The password of an EODMS account.
        :type  password: str
        :param show_timestamp: Determines whether to show a timestamp
        :type  show_timestamp: bool
        """

        # Create session
        self.collection = None
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._email = 'eodms-sgdot@nrcan-rncan.gc.ca'

        self.rapi_root = "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi"

        self.rapi_collections = {}
        self.unsupport_collections = {}
        self.download_size = 0
        self.size_limit = None
        self.results = []
        self.search_results = None
        self.res_mdata = None
        self.limit_interval = 1000
        self.name_conv = 'camel'
        self.res_format = 'raw'
        self.stdout_enabled = True
        self.timeout_query = 120.0
        self.timeout_order = 180.0
        self.attempts = 4
        self.indent = 3
        self.aoi = None
        self.verify = True
        self.dates = None
        self.feats = None
        self.max_results = None
        self._rapi_url = None
        self.start = datetime.datetime.now()
        self.logger = logger
        self.err_occurred = False
        self.auth_err = False
        self.err_msg = None
        self.order_json = None
        self.show_timestamp = show_timestamp

        self.geo = EODMSGeo(self)

        # self._map_fields()

        self._header = '| EODMSRAPI | '

        self.failed_status = ['CANCELLED', 'FAILED', 'EXPIRED',
                              'DELIVERED', 'MEDIA_ORDER_SUBMITTED',
                              'AWAITING_PAYMENT']

        self.ui_field_map = {
            'ALOS-2': ['Look Direction',
                       'SENSOR_BEAM.SPATIAL_RESOLUTION',
                       'ARCHIVE_IMAGE.PRODUCT_TYPE',
                       'PRODUCT_FORMAT.FORMAT_NAME_E', 'sarsat.SBEAM',
                       'sarsat.REC_POL', 'sarsat.TR_POL',
                       'SENSOR_BEAM_CONFIG.INCIDENCE_HIGH',
                       'SENSOR_BEAM_CONFIG.INCIDENCE_LOW'],
            'COSMO-SkyMed1': ['ARCHIVE_IMAGE.ORDER_KEY',
                              'SENSOR_BEAM.SPATIAL_RESOLUTION',
                              'csmed.ORBIT_ABS'],
            'DMC': ['ARCHIVE_IMAGE.ORDER_KEY',
                    'SENSOR_BEAM.SPATIAL_RESOLUTION', 'DMC.CLOUD_PERCENT',
                    'DMC.INCIDENCE_ANGLE'],
            'Gaofen-1': ['ARCHIVE_IMAGE.ORDER_KEY',
                         'SENSOR_BEAM.SPATIAL_RESOLUTION',
                         'SATOPT.CLOUD_PERCENT', 'SATOPT.SENS_INC'],
            'GeoEye-1': ['ARCHIVE_IMAGE.ORDER_KEY',
                         'SENSOR_BEAM.SPATIAL_RESOLUTION',
                         'GE1.CLOUD_PERCENT', 'GE1.SENS_INC'],
            'IKONOS': ['ARCHIVE_IMAGE.ORDER_KEY',
                       'SENSOR_BEAM.SPATIAL_RESOLUTION',
                       'IKONOS.CLOUD_PERCENT', 'IKONOS.SENS_INC',
                       'IKONOS.SBEAM'],
            'IRS': ['ARCHIVE_IMAGE.ORDER_KEY',
                    'SENSOR_BEAM.SPATIAL_RESOLUTION',
                    'IRS.CLOUD_PERCENT', 'IRS.SENS_INC', 'IRS.SBEAM'],
            'NAPL': ['ARCHIVE_IMAGE.ORDER_KEY', 'PHOTO.SBEAM',
                     'FLIGHT_SEGMENT.SCALE', 'ROLL.ROLL_NUMBER',
                     'PHOTO.PHOTO_NUMBER', 'CATALOG_IMAGE.OPEN_DATA',
                     'PREVIEW_AVAILABLE'],
            'PlanetScope': ['ARCHIVE_IMAGE.ORDER_KEY',
                            'SENSOR_BEAM.SPATIAL_RESOLUTION',
                            'SATOPT.CLOUD_PERCENT', 'SATOPT.SENS_INC'],
            'QuickBird-2': ['ARCHIVE_IMAGE.ORDER_KEY',
                            'SENSOR_BEAM.SPATIAL_RESOLUTION',
                            'QB2.CLOUD_PERCENT', 'QB2.SENS_INC', 'QB2.SBEAM'],
            'Radarsat1': ['ARCHIVE_IMAGE.ORDER_KEY',
                          'SENSOR_BEAM.SPATIAL_RESOLUTION',
                          'RSAT1.ORBIT_DIRECTION', 'RSAT1.INCIDENCE_ANGLE',
                          'RSAT1.SBEAM', 'RSAT1.BEAM_MNEMONIC',
                          'RSAT1.ORBIT_ABS', 'ARCHIVE_IMAGE.PRODUCT_TYPE',
                          'ARCHIVE_IMAGE.PRODUCT_ID',
                          'PROCESSING_LEVEL_LUT.PROCESSING_LEVEL'],
            'Radarsat1RawProducts': ['SENSOR_BEAM.SPATIAL_RESOLUTION',
                                     'RSAT1.ORBIT_DIRECTION',
                                     'RSAT1.INCIDENCE_ANGLE',
                                     'RSAT1.DATASET_ID',
                                     'ARCHIVE_CUF.ARCHIVE_FACILITY',
                                     'ARCHIVE_CUF.RECEPTION_FACILITY',
                                     'RSAT1.SBEAM', 'RSAT1.BEAM_MNEMONIC',
                                     'RSAT1.ORBIT_ABS'],
            'Radarsat2': ['ARCHIVE_IMAGE.ORDER_KEY',
                          'SENSOR_BEAM.SPATIAL_RESOLUTION',
                          'RSAT2.ORBIT_DIRECTION', 'RSAT2.INCIDENCE_ANGLE',
                          'CATALOG_IMAGE.SEQUENCE_ID', 'RSAT2.SBEAM',
                          'RSAT2.BEAM_MNEMONIC', 'RSAT2.ANTENNA_ORIENTATION',
                          'RSAT2.TR_POL', 'RSAT2.REC_POL', 'RSAT2.IMAGE_ID',
                          'RSAT2.ORBIT_REL'],
            'Radarsat2RawProducts': ['SENSOR_BEAM.SPATIAL_RESOLUTION',
                                     'RSAT2.ORBIT_DIRECTION',
                                     'RSAT2.INCIDENCE_ANGLE',
                                     'RSAT2.ANTENNA_ORIENTATION',
                                     'RSAT2.SBEAM', 'RSAT2.BEAM_MNEMONIC',
                                     'RSAT2.TR_POL', 'RSAT2.REC_POL',
                                     'RSAT2.IMAGE_ID'],
            'RapidEye': ['ARCHIVE_IMAGE.ORDER_KEY',
                         'SENSOR_BEAM.SPATIAL_RESOLUTION',
                         'RE.CLOUD_PERCENT', 'RE.SENS_INC', 'RE.SBEAM'],
            'RCMImageProducts': ['ARCHIVE_IMAGE.ORDER_KEY',
                                 'SENSOR_BEAM.SPATIAL_RESOLUTION',
                                 'RCM.ORBIT_DIRECTION', 'RCM.INCIDENCE_ANGLE',
                                 'RCM.BEAM_MNEMONIC',
                                 'SENSOR_BEAM_CONFIG.BEAM_MODE_QUALIFIER',
                                 'RCM.SBEAM', 'RCM.DOWNLINK_SEGMENT_ID',
                                 'LUTApplied', 'CATALOG_IMAGE.OPEN_DATA',
                                 'RCM.POLARIZATION',
                                 'PRODUCT_FORMAT.FORMAT_NAME_E',
                                 'ARCHIVE_IMAGE.PRODUCT_TYPE', 'RCM.ORBIT_REL',
                                 'RCM.WITHIN_ORBIT_TUBE',
                                 'CATALOG_IMAGE.SEQUENCE_ID',
                                 'RCM.SPECIAL_HANDLING_REQUIRED',
                                 'RCM.ORBIT_DATA_SOURCE'],
            'RCMScienceData': ['SENSOR_BEAM.SPATIAL_RESOLUTION',
                               'RCM.ORBIT_DIRECTION', 'RCM.INCIDENCE_ANGLE',
                               'RCM.SBEAM', 'RCM.BEAM_MNEMONIC',
                               'CUF_RCM.TR_POL', 'CUF_RCM.REC_POL',
                               'RCM.DOWNLINK_SEGMENT_ID'],
            'SGBAirPhotos': ['ARCHIVE_IMAGE.ORDER_KEY',
                             'FLIGHT_SEGMENT.SCALE', 'ROLL.ROLL_NUMBER',
                             'PHOTO.PHOTO_NUMBER', 'Area'],
            'SPOT': ['ARCHIVE_IMAGE.ORDER_KEY',
                     'SENSOR_BEAM.SPATIAL_RESOLUTION',
                     'SPOT.CLOUD_PERCENT', 'SPOT.SENS_INC'],
            'TerraSarX': ['ARCHIVE_IMAGE.ORDER_KEY',
                          'SENSOR_BEAM.SPATIAL_RESOLUTION',
                          'TSX1.ORBIT_DIRECTION', 'INCIDENCE_ANGLE'],
            'VASP': ['CATALOG_SERIES.CEOID'],
            'WorldView-1': ['ARCHIVE_IMAGE.ORDER_KEY',
                            'SENSOR_BEAM.SPATIAL_RESOLUTION',
                            'WV1.CLOUD_PERCENT', 'WV1.SENS_INC', 'WV1.SBEAM'],
            'WorldView-2': ['ARCHIVE_IMAGE.ORDER_KEY',
                            'SENSOR_BEAM.SPATIAL_RESOLUTION',
                            'WV2.CLOUD_PERCENT', 'WV2.SENS_INC', 'WV2.SBEAM'],
            'WorldView-3': ['ARCHIVE_IMAGE.ORDER_KEY',
                            'SENSOR_BEAM.SPATIAL_RESOLUTION',
                            'WV3.CLOUD_PERCENT', 'WV3.SENS_INC', 'WV3.SBEAM'],
        }

    ###############################################################
    # Backwards compatibility methods
    ###############################################################

    def set_queryTimeout(self, timeout):
        warn("Method 'set_queryTimeout' is deprecated. Please use "
             "'set_query_timeout'.", DeprecationWarning, stacklevel=2)
        self.set_query_timeout(timeout)

    def set_orderTimeout(self, timeout):
        warn("Method 'set_orderTimeout' is deprecated. Please use "
             "'set_order_timeout'.", DeprecationWarning, stacklevel=2)
        self.set_order_timeout(timeout)

    def set_fieldConvention(self, convention):
        warn("Method 'set_fieldConvention' is deprecated. Please use "
             "'set_field_convention'.", DeprecationWarning, stacklevel=2)
        self.set_field_convention(convention)

    def get_availableFields(self, collection=None, name_type='all'):
        warn("Method 'get_availableFields' is deprecated. Please use "
             "'get_available_fields'.", DeprecationWarning, stacklevel=2)
        return self.get_available_fields(collection, name_type)

    def get_fieldChoices(self, collection, field=None):
        warn("Method 'get_fieldChoices' is deprecated. Please use "
             "'get_field_choices'.", DeprecationWarning, stacklevel=2)
        return self.get_field_choices(collection, field)

    def get_orderItem(self, itemId):
        warn("Method 'get_orderItem' is deprecated. Please use "
             "'get_order_item'.", DeprecationWarning, stacklevel=2)
        return self.get_order_item(itemId)

    def get_ordersByRecords(self, records):
        warn("Method 'get_ordersByRecords' is deprecated. Please use "
             "'get_orders_by_records'.", DeprecationWarning, stacklevel=2)
        return self.get_orders_by_records(records)

    def get_orderParameters(self, collection, recordId):
        warn("Method 'get_orderParameters' is deprecated. Please use "
             "'get_order_parameters'.", DeprecationWarning, stacklevel=2)
        return self.get_order_parameters(collection, recordId)

    def get_rapiUrl(self):
        warn("Method 'get_rapiUrl' is deprecated. Please use "
             "'get_rapi_url'.", DeprecationWarning, stacklevel=2)
        return self.get_rapi_url()

    def cancel_orderItem(self, orderId, itemId):
        warn("Method 'cancel_orderItem' is deprecated. Please use "
             "'cancel_order_item'.", DeprecationWarning, stacklevel=2)
        return self.cancel_order_item(orderId, itemId)

    ###############################################################

    def _check_complete(self, complete_items, record_id):
        """
        Checks if an order item has already been downloaded.

        :param complete_items: A list of completed order items.
        :type  complete_items: list
        :param record_id: The record ID of the image.
        :type  record_id: int

        :return: True if already downloaded, False if not.
        :rtype: boolean
        """

        for i in complete_items:
            if i['recordId'] == record_id:
                return True

        return False

    def _check_auth(self, in_err=None):
        """
        Checks if the error results from the RAPI are unauthorized.

        :param in_err: The QueryError containing the error from the RAPI.
        :type  in_err: QueryError

        :return: True if unauthorized, False if not.
        :rtype: boolean
        """

        if in_err is None:
            query_url = f"{self.rapi_root}/collections?format=json"
            coll_res = self._submit(query_url, timeout=20.0)

            # print(f"coll_res: {coll_res}")
            if isinstance(coll_res, QueryError):
                in_err = coll_res
            else:
                return False

        self.err_msg = in_err.get_msgs(True)
        if self.err_msg.find('401 - Unauthorized') > -1 or \
                self.err_msg.find('HTTP Error: 401 Client Error') > -1 or \
                self.err_msg.find('Unauthorized') > -1:
            # Inform the user if the error was caused by an authentication
            #   issue.
            self.err_msg = "An authentication error has occurred while " \
                      "trying to access the EODMS RAPI. Please ensure " \
                      "your account login is in good standing on the actual " \
                      "website, https://www.eodms-sgdot.nrcan-rncan.gc.ca/" \
                      "index-en.html."
            self.err_occurred = True
            self.auth_err = True
            self.log_msg(self.err_msg, 'error')
            return True

        return False

    def _convert_date(self, date, in_forms=None, out='string',
                      out_form="%Y%m%d_%H%M%S"):
        """
        Converts a date to a specified format.

        :param date: The input date to convert.
        :type  date: str or datetime.datetime
        :param in_forms: Specifies the input formats of the date.
        :type  in_forms: list
        :param out: The type of output date, either 'string' or 'date'
                    (i.e. datetime.datetime)
        :type  out: str
        :param out_form: Specifies the output format for the date.
        :type  out_form: str

        :return: The date in the specified format.
        :rtype: str or datetime.datetime
        """

        if in_forms is None:
            in_forms = ['%Y-%m-%d %H:%M:%S.%f']
        if isinstance(date, datetime.datetime):
            if out_form == 'iso':
                return date.isoformat()
            else:
                return date.strftime(out_form)

        elif isinstance(date, str):

            if isinstance(in_forms, str):
                in_forms = [in_forms]

            for form in in_forms:
                try:
                    out_date = datetime.datetime.strptime(date, form)
                    if out == 'date':
                        return out_date
                    else:
                        return out_date.strftime(out_form)
                except ValueError as e:
                    msg = f"{str(e).capitalize()}. Date will not be included " \
                          f"in query."

                    self.log_msg(msg, 'warning')
                    pass
                except Exception:
                    msg = traceback.format_exc()
                    self.log_msg(msg, 'warning')
                    pass

    def _convert_field(self, field, collection, field_type='search'):
        """
        Converts a field to either a field name or a field ID, depending on
            the input.

        :param field: The input field name or field ID.
        :type  field: str
        :param collection: The collection ID containing the fields.
        :type  collection: str
        :param field_type: Retrieves either the 'search' fields or the
                            'result' fields.
        :type  field_type: str

        :return: Either the field name or the field ID.
        :rtype: str
        """

        fields = self.get_available_fields(collection, 'all')[field_type]

        for k, v in fields.items():
            if field == k:
                return v['id']
            elif field == v['id']:
                return k

    def get_conv(self, field):
        """
        Converts a field name into the set naming convention (self.name_conv).

        :param field: The field name.
        :type  field: str

        :return: The field name with the proper naming convention ('words',
        'upper' or 'camel').
        :rtype: str
        """

        if self.name_conv == 'words' or self.name_conv == 'upper':
            # Remove bracketted string for 'upper'
            if self.name_conv == 'upper':
                field = re.sub(r"\([^()]*\)", "", field)
                field = field.strip()

            # Separate into words
            if field.find(' ') > -1:
                words = field.split(' ')
            else:
                words = re.findall('.+?(?:(?<=[a-z])(?=[A-Z])|(?<='
                                   '[A-Z])(?=[A-Z][a-z])|$)', field)
                words = [w[0].upper() + w[1:] for w in words]

            if self.name_conv == 'words':
                return ' '.join(words)
            elif self.name_conv == 'upper':
                return '_'.join([w.upper() for w in words])
        else:
            return self._to_camel_case(field)

    def _fetch_metadata(self, max_workers=4, len_timeout=20.0,
                        show_progress=True):
        """
        Fetches all metadata for a given record

        (Adapted from: eodms-api-client (
        https://pypi.org/project/eodms-api-client/) developed by Mike Brady)

        :param max_workers: The number of threads used for retrieving the
        metadata.
        :type  max_workers: int
        :param len_timeout: The length of time in seconds before the thread
        returns a timeout warning.
        :type len_timeout: float
        :param show_progress: Determines whether to show the progress
        (use tqdm) when fetching the metadata
        :type show_progress: bool

        :return: A list containing the metadata for all items in the
        self.results
        :rtype:  list
        """

        metadata_fields = self._get_meta_keys()

        if isinstance(metadata_fields, QueryError):
            msg = "Could not generate metadata for the results."
            self.log_msg(msg, 'warning')
            return None

        if isinstance(self.results, dict):
            self.results = [self.results]

        if show_progress:
            n_urls = len(self.results)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                out_results = list(
                    tqdm(
                        executor.map(
                            self._fetch_single_record_metadata,
                            self.results,
                            [len_timeout] * n_urls,
                        ),
                        desc=f'{self._header}Fetching result metadata',
                        total=n_urls,
                        miniters=1,
                        unit='item'
                    )
                )
        else:
            out_results = []
            for res in self.results:
                mdata = self._fetch_single_record_metadata(res, len_timeout)
                out_results.append(mdata)

        return out_results

    def _fetch_single_record_metadata(self, record, timeout):  # , keys):
        """
        Fetches a single image's metadata.

        (Adapted from: eodms-api-client (
        https://pypi.org/project/eodms-api-client/) developed by Mike Brady)

        :param record: A dictionary of an image record.
        :type  record: dict
        :param timeout: The time in seconds to wait before timing out.
        :type  timeout: float

        :return: Dictionary containing the keys and geometry metadata for the
        given image.
        :rtype: dict
        """

        record_url = f"{record['thisRecordUrl']}?format=json"
        r = self._submit(record_url, timeout=timeout, as_json=False)

        if r is None or self.err_occurred:
            return None

        if isinstance(r, QueryError):
            err_msg = f"Could not retrieve full metadata due to: " \
                      f"{r.get_msgs(True)}"
            self.log_msg(err_msg, 'warning')
            record['issue'] = err_msg
            image_res = record
        elif r.ok:
            image_res = r.json()
        else:
            err_msg = "Could not retrieve metadata."
            self.log_msg(err_msg, 'warning')
            image_res = record

        metadata = self.parse_metadata(image_res)  # , keys)

        return metadata

    def _get_date_range(self, items):
        """
        Gets the date range for a list of items (images).

        :param items: A list of items.
        :type  items: list

        :return: A tuple with the start and end date of the range.
        :rtype: tuple
        """

        eastern = pytz.timezone('US/Eastern')

        dates = []
        for i in items:

            rapi_str = i.get('dateRapiOrdered')
            if rapi_str is None:
                rapi_str = i.get('dateSubmitted')

            if rapi_str is None:
                return None

            rapi_date = dateutil.parser.parse(rapi_str)

            # Convert UTC to Eastern
            rapi_date = rapi_date.astimezone(eastern)

            dates.append(rapi_date)

        dates.sort()

        start = dates[0]
        start = start - datetime.timedelta(hours=0, minutes=1)

        end = dates[len(dates) - 1]
        end = end + datetime.timedelta(hours=0, minutes=1)

        return start, end

    def _get_meta_keys(self):
        """
        Gets a list of metadata (fields) keys for a given collection

        :return: A list of metadata keys
        :rtype:  list
        """

        if not self.rapi_collections:
            self.get_collections()

        if self.rapi_collections is None or self.err_occurred:
            return None

        fields = self.rapi_collections[self.collection]['fields']['results']. \
            keys()
        sorted_lst = sorted(fields)

        return sorted_lst

    def _get_exception(self, res, output='str'):
        """
        Gets the Exception text (or XML) from an request result.

        :param res: The XML which will be checked for an exception.
        :type  res: xml.etree.ElementTree.Element
        :param output: Determines what type of output should be returned
                        (default='str').
                       Options:
                       - 'str': returns the XML Exception as a string
                       - 'tree': returns the XML Exception as a
                                    xml.etree.ElementTree.Element
        :type  output: str

        :return:       The Exception XML text or element depending on
                        the output variable.
        :rtype:        QueryError or xml.etree.ElementTree.Element
        """

        in_str = res.text

        # If the input XML is None, return None
        if in_str is None:
            return None

        if self.is_json(in_str):
            return None

        # If the input is a string, convert it to a
        #   xml.etree.ElementTree.Element
        # print(f"in_str: {in_str}")
        if isinstance(in_str, str):
            root = ElementTree.fromstring(in_str)
        else:
            root = in_str

        # Cycle through the input XML and location the ExceptionText element
        out_except = []
        for child in root.iter('*'):
            if child.tag.find('ExceptionText') > -1:
                if output == 'tree':
                    return child
                else:
                    return child.text
            elif child.tag.find('p') > -1:
                out_except.append(child.text)

        query_err = QueryError(out_except)

        return query_err

    def _get_field_id(self, name, field_type='search'):
        """
        Gets the field ID for a given field name.

        :param name: The field name.
        :type  name: str
        :param field_type: The field type, either 'search' or 'result'.
        :type  field_type: str

        :return: The proper field ID for the given name.
        :rtype: str
        """

        field_id = None
        if field_type == 'search':
            fields = self.get_available_fields(name_type='all')

            if fields is None:
                return None

            fields = fields[field_type]

            # Check in available fields
            for k, v in fields.items():
                if name == k:
                    field_id = v['id']
                    break

            # If field_id is still None, check to make sure the
            #   name entry is an ID
            if field_id is None:
                if name in [f['id'] for f in fields.values()]:
                    return name

            return field_id

        elif field_type == 'results':
            fields = self.get_available_fields(name_type='all')

            if fields is None:
                return None

            fields = fields[field_type]

            # Check if results fields
            for k, v in fields.items():
                if k.find(name) > -1:
                    field_id = v['id']

            # If field_id is still None, check to make sure the
            #   name entry is an ID
            if field_id is None:
                if name in [f['id'] for f in fields.values()]:
                    return name

            return field_id

    def _get_field_type(self, coll_id, field_id):
        """
        Gets the field data type.

        :param coll_id: The collection ID.
        :type  coll_id: str
        :param field_id: The field ID.
        :type  field_id: str

        :return: The data type of the specified field.
        :rtype: str
        """

        if not self.rapi_collections:
            self.get_collections()

        if self.rapi_collections is None or self.err_occurred:
            return None

        for k, v in self.rapi_collections[coll_id]['fields']['search'].items():
            if v['id'] == field_id:
                return v['datatype']

    def _get_item_from_orders(self, item_id, orders):
        """
        Gets the order item ID from a list of order items (either from
            'itemId' or 'ParentItemId').

        :param item_id: The order item ID.
        :type  item_id: int
        :param orders: A list of order items.
        :type  orders: list

        :return: The specific order with the given order item ID.
        :rtype: dict
        """

        for o in orders:
            if 'parameters' in o.keys():
                if 'ParentItemId' in o['parameters'].keys():
                    if str(o['parameters']['ParentItemId']) == str(item_id):
                        return o
            if str(o['itemId']) == str(item_id):
                return o

    def is_json(self, my_json):
        """
        Checks to see in the input item is in JSON format.

        :param my_json: A string value from the requests results.
        :type  my_json: str

        :return: True if a valid JSON format, False if not.
        :rtype: boolean
        """

        try:
            json.loads(my_json)
        except (ValueError, TypeError):
            return False
        return True

    def _build_or(self, field_id, op, values, d_type):
        """
        Builds an 'OR' statement for the query to the RAPI.

        :param field_id: The field ID for the OR statements.
        :type  field_id: str
        :param op: The operator for the OR statements.
        :type  op: str
        :param values: A list of values for the OR statements.
        :type  values: list
        :param d_type: The data type of the values ('String' or something
                        else).
        :type  d_type: str

        :return: The complete OR statement for the list of values.
        :rtype: str
        """

        if d_type == 'String':
            or_query = '%s' % ' OR '.join([f"{field_id}{op}'{v}'"
                                           for v in values])
        elif d_type == 'Boolean':
            vals_str = []
            for v in values:
                if val[0].lower().find('t') > -1 \
                    or val[0].lower().find('y') > -1:
                    val_query = f"{field_id}{op}True"
                elif val[0].lower().find('f') > -1 \
                    or val[0].lower().find('n') > -1:
                    val_query = f"{field_id}{op}False"
                vals_str.append(val_query)
            or_query = '%s' % ' OR '.join(vals_str)
        elif d_type == 'DateTimeRange':
            date_vals = []
            for val in values:
                date = dateutil.parser.parse(val)
                iso_date = date.isoformat()
                date_vals.append(iso_date)
            or_query = '%s' % ' OR '.join([f"{field_id}{op}'{v}'"
                                           for v in date_vals])
        else:
            or_query = '%s' % ' OR '.join([f"{field_id}{op}{v}"
                                           for v in values])

        return or_query

    def log_msg(self, messages, msg_type='info', log_indent='', out_indent=''):
        """
        Logs a message to the logger.

        :param messages: Either a single message or a list of messages to log.
        :type  messages: str or list
        :param msg_type: The type of log ('debug', 'info', 'warning',
                        'error', etc.)
        :type  msg_type: str
        :param log_indent: The amount of indentation for the log.
                            (ex: '\t\t').
        :type  log_indent: str
        :param out_indent: The amount of indentation for the printout.
                            (ex: '\t\t').
        :type  out_indent: str
        """

        if isinstance(messages, list) or isinstance(messages, tuple):
            log_msg, out_msg = messages
        elif isinstance(messages, str):
            log_msg = out_msg = messages
        else:
            print("EODMSRAPI.log_msg: 'messages' parameter not valid.")
            return None

        # Log the message
        log_msg = f"{log_indent}{log_msg}"
        log_msg = log_msg.replace('\n', '\\n')
        log_msg = log_msg.replace('\t', '\\t')
        log_msg = log_msg.replace("'", "\\'")
        eval(f"logger.{msg_type}(r'{log_msg}')")

        # If stdout is disabled, don't print message to terminal
        if not self.stdout_enabled:
            return None

        # Set timestamp
        if self.show_timestamp:
            current_time = datetime.datetime.now()
            timestamp = f"{current_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        else:
            timestamp = ''

        # Print message to terminal
        if msg_type == 'info':
            msg = f"{out_indent}{self._header}{timestamp}{out_msg}"
        else:
            msg = f"{out_indent}{self._header}{timestamp} " \
                  f"{msg_type.upper()}: {out_msg}"

        print(msg)

    def _order_results(self, results, keys):
        """
        Orders the metadata keys of RAPI results.

        :param results:
        :type  results: list
        :param keys: A list of keys in the proper order (the list does not
                    have to contain all the keys, all remaining keys will
                    appear in their original order).
        :type  keys: list

        :return: The results in the specified order.
        :rtype: list
        """

        out_results = []
        for res in results:
            remain_keys = [k for k in res.keys() if k not in keys]

            keys += remain_keys

            new_res = {k: res[k] for k in keys}

            out_results.append(new_res)

        return out_results

    def parse_metadata(self, image_res):
        """
        Parses the metadata results from the RAPI for better JSON.

        :param image_res: A dictionary of a single record from the RAPI.
        :type  image_res: dict
        """

        if 'metadata' not in image_res.keys():
            # The image result has already been parsed
            return image_res

        metadata = {self.get_conv('recordId'): image_res['recordId'],
                    self.get_conv('collectionId'): image_res['collectionId']}

        # Add the following at the start of the metadata
        if 'geometry' in image_res.keys():
            metadata[self.get_conv('geometry')] = \
                image_res['geometry']

        # Exclude what's already been added and other metadata fields
        exclude = [self.get_conv('recordId'), self.get_conv('collectionId'),
                   self.get_conv('geometry')]

        for k, v in image_res.items():
            if self.get_conv(k) not in exclude:
                if k == 'metadata':
                    continue
                elif k == 'metadata2':
                    for mdata in v:
                        mdata_field = mdata['label']
                        mdata_field = self.get_conv(mdata_field)
                        if mdata_field not in exclude:
                            metadata[mdata_field] = mdata['value']
                else:
                    metadata[self.get_conv(k)] = v

        if self.res_format == 'full':
            if 'geometry' in image_res.keys():
                wkt_field = self.get_conv('WKT Geometry')
                metadata[wkt_field] = self.geo.convert_image_geom(
                    image_res['geometry'], 'wkt')

        return metadata

    def _parse_range(self, field, start, end):
        """
        Creates the date range string for the RAPI search URL.

        :param field: The field ID for the query.
        :type  field: str
        :param start: The start date in ISO format.
        :type  start: str
        :param end: The end date in ISO format.
        :type  end: str

        :return: The date range string for the RAPI search URL.
        :rtype: str
        """

        return f'({field}>={start} AND {field}<={end})'

    def _parse_query(self, filters=None, feats=None, dates=None):
        """
        Parses a search query for the RAPI.

        :param filters: A dictionary of filters and values for the RAPI.
        :type  filters: dict
        :param feats: A list of geometries for the query.
        :type  feats: list
        :param dates: A list of date range dictionaries containing keys
                        'start' and 'end'.
        :type  dates: list

        :return: The query for the RAPI search URL.
        :rtype: str
        """

        query_lst = []

        # Get the collection
        if not self.rapi_collections:
            self.get_collections()

        if self.rapi_collections is None:
            return None

        # Build the query for the date range
        if dates is not None and not str(dates).strip() == '':
            self.dates = dates

        if self.dates is not None:

            field_id = self._get_field_id('Acquisition Start Date')

            if self.err_occurred:
                return None

            if field_id is None:
                field_id = self._get_field_id('Start Date')

                if self.err_occurred:
                    return None

            date_queries = []
            for rng in self.dates:
                start = None
                end = None
                if isinstance(rng, str):
                    time_words = ['hour', 'day', 'week', 'month', 'year']

                    if any(word in rng for word in time_words):
                        start = dateparser.parse(rng).strftime("%Y%m%d_%H%M%S")
                        end = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                else:
                    if 'start' not in rng.keys():
                        break

                    start = self._convert_date(rng.get('start'),
                                               "%Y%m%d_%H%M%S",
                                               out_form="%Y-%m-%dT%H:%M:%SZ")
                    end = self._convert_date(rng.get('end'), "%Y%m%d_%H%M%S",
                                             out_form="%Y-%m-%dT%H:%M:%SZ")

                if start is None or end is None:
                    continue

                date_queries.append(f"{field_id}>='{start}' AND "
                                    f"{field_id}<='{end}'")

            if len(date_queries) > 0:
                query_lst.append(f"({' OR '.join(date_queries)})")

        # Build the query for the geometry features
        if feats is None:
            feats = self.feats

        if feats is not None:

            geom_lst = []

            for idx, f in enumerate(feats):
                op = f[0].upper()
                src = f[1]

                self.geoms = self.geo.add_geom(src)

                if self.geoms is None or isinstance(self.geoms, SyntaxError):
                    msg = f"Geometry feature #{str(idx + 1)} could not be " \
                          f"determined. Excluding it from search."
                    self.log_msg(msg, 'warning')
                else:
                    field_id = self._get_field_id('Footprint')

                    if self.err_occurred:
                        return None

                    self.geoms = [self.geoms] \
                        if not isinstance(self.geoms, list) else self.geoms

                    for g in self.geoms:
                        if op == '=':
                            geom_lst.append(f"{field_id}{op}'{g}'")
                        else:
                            geom_lst.append(f'{field_id} {op} {g}')

            if len(geom_lst) > 0:
                query_lst.append(f"({' OR '.join(geom_lst)})")

        # Build the query containing the filters
        if filters is not None:
            for field, values in filters.items():

                field_id = self._get_field_id(field)

                if self.err_occurred:
                    return None

                if field_id is None:
                    msg = f"No available field named '{field}'."
                    self.log_msg(msg, 'warning')
                    continue

                d_type = self._get_field_type(self.collection, field_id)

                # print("d_type: %s" % d_type)

                op = values[0]
                val = values[1]

                if not any(c in op for c in '=><'):
                    op = ' %s ' % op

                if not isinstance(val, list) and not isinstance(val, tuple):
                    val = [val]

                if field == 'Incidence Angle' or field == 'Scale' or \
                        field == 'Spacial Resolution' or \
                        field == 'Absolute Orbit':
                    for v in val:
                        if v.find('-') > -1:
                            start, end = v.split('-')
                            val_query = self._parse_range(field_id, start,
                                                            end)
                        else:
                            val_query = f"{field_id}{op}{v}"
                        query_lst.append(val_query)
                    continue
                    # else:
                    #     if str(val).find('-') > -1:
                    #         start, end = str(val).split('-')
                    #         val_query = self._parse_range(field_id, start, end)
                    #     else:
                    #         val_query = f"{field_id}{op}{val}"

                elif field_id == 'RCM.SPECIAL_HANDLING_REQUIRED':
                    val_query = f"{field_id}{op}{val[0]}"

                elif field == 'Footprint':

                    pnts = []
                    vals = val[0].split(' ')
                    for idx in range(0, len(vals), 2):
                        if vals[idx].strip() == '':
                            continue

                        pnts.append((float(vals[idx]), float(vals[idx + 1])))

                    self.geoms = self.geo.add_geom(pnts)

                    val_query = f"{field_id}{op}{self.geoms}"

                else:
                    # Convert choice to value
                    choices = self.get_field_choices(self.collection, 
                                                     field_id, True)
                    valid_vals = []
                    for v in val:
                        new_val = None
                        for c in choices:
                            if c.get('label') == v:
                                new_val = c.get('value')
                                valid_vals.append(new_val)
                                break
                        if not new_val:
                            valid_vals.append(v)

                    val = valid_vals

                    if len(val) > 1:
                        val_query = self._build_or(field_id, op, val, d_type)
                    else:
                        if d_type == 'String':
                            val_query = f"{field_id}{op}'{val[0]}'"
                        elif d_type == 'Boolean':
                            if val[0].lower().find('t') > -1 \
                                or val[0].lower().find('y') > -1:
                                val_query = f"{field_id}{op}True"
                            elif val[0].lower().find('f') > -1 \
                                or val[0].lower().find('n') > -1:
                                val_query = f"{field_id}{op}False"
                        elif d_type == 'DateTimeRange':
                            date = dateutil.parser.parse(val[0])
                            iso_date = date.isoformat()
                            val_query = f"{field_id}{op}'{iso_date}'"
                        else:
                            val_query = f"{field_id}{op}{val[0]}"

                query_lst.append(val_query)

        if len(query_lst) > 1:
            query_lst = ['(%s)' % q if q.find(' OR ') > -1 else q
                         for q in query_lst]

        full_query = ' AND '.join(query_lst)

        return full_query

    def _submit_search(self):
        """
        Submit a search query to the desired EODMS collection

        Since there may be instances where the default maxResults is greater
        than 150, this method should recursively call itself until the
        correct number of results is retrieved.

        (Adapted from: eodms-api-client (
        https://pypi.org/project/eodms-api-client/) developed by Mike Brady)

        :return: The search-query response JSON from the EODMS REST API.
        :rtype:  json
        """

        # If max_results is specified, reduce the number of records in
        #   search_results to max_results and then return the search_results
        if self.max_results is not None:
            if len(self.search_results) >= self.max_results:
                self.search_results = self.search_results[:self.max_results]
                return self.search_results

        # Print status of search
        start = len(self.search_results) + 1
        end = len(self.search_results) + self.limit_interval

        msg = f"Querying records within {start} to {end}..."
        self.log_msg(msg)

        logger.debug(f"RAPI Query URL: {self._rapi_url}")
        r = self._submit(self._rapi_url)

        # If a fatal error occurred
        if r is None or self.err_occurred:
            return None

        # If an QueryError occurred
        if isinstance(r, QueryError):
            err_msg = r.get_msgs(True)

            out_msg = self._check_http(err_msg)
            if out_msg is not None:
                self.log_msg(out_msg, 'warning')
                self.search_results = r
                return self.search_results

            msg = 'Retrying in 3 seconds...'
            self.log_msg(msg, 'warning')
            time.sleep(3)
            return self._submit_search()

        # If applicable, convert results to JSON
        if isinstance(r, requests.Response):
            data = r.json()
        else:
            data = r

        # Get the total number of results
        tot_results = int(data['totalResults'])

        # If there are no results, no need to go further
        if tot_results == 0:
            return self.search_results

        # If the number of results has hit the limit_interval, return results
        elif tot_results < self.limit_interval:
            self.search_results += data['results']
            return self.search_results

        # Append firstResult to the URL query and run _submit_search method
        #   again
        self.search_results += data['results']
        first_result = len(self.search_results) + 1
        if self._rapi_url.find('&firstResult') > -1:
            old_first_result = int(re.search(
                r'&firstResult=([\d*]+)',
                self._rapi_url
            ).group(1))
            self._rapi_url = self._rapi_url.replace(
                '&firstResult=%d' % old_first_result,
                '&firstResult=%d' % first_result
            )
        else:
            self._rapi_url += f'&firstResult={first_result}'

        return self._submit_search()

    def _check_http(self, err_msg):
        """
        Checks an error message for the HTTP code and returns a more
        appropriate message.

        :param err_msg: The error message from the response.
        :type  err_msg: str

        :return: The new error message (or None is no error).
        :rtype: str (or None)
        """

        if err_msg.find('404 Client Error') > -1 or \
            err_msg.find('404 for url') > -1:
            msg = f"404 Client Error: Could not find {self._rapi_url}."
        elif err_msg.find('400 Client Error') > -1:
            msg = f"400 Client Error: A Bad Request occurred while trying to " \
                  f"reach {self._rapi_url}"
        elif err_msg.find('500 Server Error') > -1:
            msg = f"500 Server Error: An internal server error has occurred " \
                  f"while to access {self._rapi_url}"
        elif err_msg.find('401 Client Error') > -1:
            return err_msg
        else:
            return None

        return msg

    def _submit(self, query_url, request_type='get', post_data=None,
                timeout=None, record_name=None, quiet=True, as_json=True):
        """
        Send a query to the RAPI.

        :param query_url: The query URL.
        :type  query_url: str
        :param timeout: The length of the timeout in seconds.
        :type  timeout: float
        :param record_name: A string used to supply information for the record
                            in a print statement.
        :type  record_name: str
        :param quiet: Determines whether to ignore log printing.
        :type  quiet: bool
        :param as_json: Determines whether to return results in JSON format.
        :type  as_json: bool

        :return: The response returned from the RAPI.
        :rtype: request.Response
        """

        if timeout is None:
            timeout = self.timeout_query

        logger.debug(f"RAPI Query URL: {query_url}")

        res = None
        attempt = 1
        err = None
        msg = ''
        # Get the entry records from the RAPI using the downlink segment ID
        while res is None and attempt <= self.attempts:
            # Continue to attempt if timeout occurs
            try:
                if record_name is None:
                    msg = f"Sending request to the RAPI (attempt {attempt})..."
                    if not quiet and attempt > 1:
                        logger.debug(f"\n{self._header}{msg}")
                else:
                    msg = f"Sending request to the RAPI for '{record_name}' " \
                          f"(attempt {attempt})..."
                    if not quiet and attempt > 1:
                        logger.debug(f"\n{self._header}{msg}")
                if self._session is None:
                    if request_type.lower() == 'post':
                        res = requests.post(query_url, post_data,
                                            timeout=timeout, verify=self.verify)
                    elif request_type.lower() == 'put':
                        res = requests.put(url=query_url,
                                           timeout=timeout,
                                           verify=self.verify)
                    elif request_type.lower() == 'delete':
                        res = requests.delete(url=query_url,
                                              timeout=timeout,
                                              verify=self.verify)
                    else:
                        res = requests.get(query_url, timeout=timeout,
                                           verify=self.verify)
                else:
                    if request_type.lower() == 'post':
                        res = self._session.post(query_url, post_data,
                                                 timeout=timeout,
                                                 verify=self.verify)
                    elif request_type.lower() == 'put':
                        res = self._session.put(url=query_url,
                                                timeout=timeout,
                                                verify=self.verify)
                    elif request_type.lower() == 'delete':
                        res = self._session.delete(url=query_url,
                                                   timeout=timeout,
                                                   verify=self.verify)
                    else:
                        res = self._session.get(query_url, timeout=timeout,
                                                verify=self.verify)
                res.raise_for_status()
            except requests.exceptions.HTTPError as errh:
                msg = f"HTTP Error: {errh}"

                out_msg = self._check_http(msg)

                if out_msg is not None:
                    err = out_msg
                    query_err = QueryError(err)

                    if self._check_auth(query_err):
                        return query_err

                    return query_err

                # elif msg.find('400 Client Error') > -1:
                #     query_err = self._get_exception(res)
                #
                #     if self._check_auth(query_err):
                #         return err
                #
                #     return query_err
                # elif msg.find('500 Server Error') > -1:
                #     query_err = self._get_exception(res)
                #     # err = msg
                #     # query_err = QueryError(err)
                #
                #     if self._check_auth(query_err):
                #         return err
                #
                #     return query_err

                if attempt < self.attempts:
                    msg = f"{msg}; attempting to connect again..."
                    self.log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
            except requests.exceptions.SSLError as ssl_err:
                msg = f"SSL Error: {ssl_err}"
                if attempt < self.attempts:
                    msg = f"{msg}; removing SSL verification and attempting " \
                          f"to connect again..."
                    self.log_msg(msg, 'warning')
                    res = None
                    self.verify = False
                else:
                    err = msg
                attempt += 1
            except (requests.exceptions.Timeout,
                    requests.exceptions.ReadTimeout) as errt:
                msg = f"Timeout Error: {errt}"
                if attempt < self.attempts:
                    msg = f"{msg}; increasing timeout by a minute and " \
                          f"trying again..."
                    self.log_msg(msg, 'warning')
                    res = None
                    timeout += 60.0
                    self.timeout_query = timeout
                else:
                    err = msg
                attempt += 1
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.RequestException) as req_err:
                # print(f"res: {res}")
                self.err_msg = f"{req_err.__class__.__name__} Error: {req_err}"
                self.err_occurred = True
                self.log_msg(self.err_msg, 'error')
                # attempt = self.attempts
                return None
            except KeyboardInterrupt:
                self.err_msg = "Process ended by user."
                self.log_msg(self.err_msg, out_indent='\n')
                self.err_occurred = True
                return None
            except Exception:
                msg = f"Unexpected error: {traceback.format_exc()}"
                if attempt < self.attempts:
                    msg = f"{msg}; attempting to connect again..."
                    self.log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1

        if err is not None:
            query_err = QueryError(err)

            if self._check_auth(query_err):
                return None

            return query_err

        # If no results from RAPI, return None
        if res is None:
            return None

        # Check for exceptions that weren't already caught
        if not res.ok:
            except_err = self._get_exception(res)

            if isinstance(except_err, QueryError):
                if self._check_auth(except_err):
                    return None

                self.log_msg(msg, 'warning')
                return except_err

        if res.text == '':
            return res

        if res.text.find('BRB!') > -1:
            self.err_msg = f"There was a problem while attempting to access the " \
                  f"EODMS RAPI server. If the problem persists, please " \
                  f"contact the EODMS Support Team at {self._email}."
            self.log_msg(self.err_msg, 'error')
            self.err_occurred = True
            query_err = QueryError(self.err_msg)
            return query_err

        if as_json:
            return res.json()
        else:
            return res

    def _to_camel_case(self, in_str):
        """
        Converts a string to lower camel case.

        :param in_str: The input string to convert.
        :type  in_str: str

        :return: The input string convert to lower camel case.
        :rtype: str
        """

        in_str = re.sub(r"\([^()]*\)", "", in_str)

        if in_str.find(' ') > -1:
            words = in_str.split(' ')
        elif in_str.find('_') > -1:
            words = in_str.split('_')
        else:
            return in_str[0].lower() + in_str[1:]

        first_word = words[0].lower()
        other_words = ''.join(w.title() for w in words[1:])

        return f'{first_word}{other_words}'

    def _update_conv(self):
        """
        Updates all fields in the set of results to the proper naming
            convention.
        """

        if self.res_mdata is not None:
            for m in self.res_mdata:
                for k, v in m.items():
                    new_k = self.get_conv(k)
                    m[new_k] = m.pop(k)

    def get_collection_id(self, coll):
        """
        Gets the full collection ID using the input collection ID which can be a
            substring of the collection ID.

        :param coll: The collection ID to check.
        :type  coll: str

        :return: The full collection ID.
        :rtype: str
        """

        if not self.rapi_collections:
            self.get_collections()

        # print(f"self.rapi_collections: {self.rapi_collections}")

        if self.rapi_collections is None or self.err_occurred:
            return None

        for k, v in self.rapi_collections.items():
            if coll.lower() == v['title'].lower():
                return k
            if coll.lower() == k.lower():
                return k
            elif coll.lower() in v['aliases']:
                return k

    def get_err_msg(self):
        """
        Gets the error message of this class after an error occurred.

        :return: The error message
        :rtype: str
        """

        return self.err_msg

    def set_query_timeout(self, timeout):
        """
        Sets the timeout limit for a query to the RAPI.

        :param timeout: The value of the timeout in seconds.
        :type  timeout: float

        """
        self.timeout_query = float(timeout)

    def set_order_timeout(self, timeout):
        """
        Sets the timeout limit for an order to the RAPI.

        :param timeout: The value of the timeout in seconds.
        :type  timeout: float

        """
        self.timeout_order = float(timeout)

    def set_attempts(self, number):
        """
        Sets number of attempts to be made to the RAPI before the script
        ends.

        :param number: The value for the number of attempts.
        :type  number: int

        """
        self.attempts = int(number)

    def set_field_convention(self, convention):
        """
        Sets the naming convention of the output fields.

        :param convention: The type of naming convention for the fields.

            - ``words``: The label with spaces and words will be returned.
            - ``camel`` (default): The format will be lower camel case like
            'camelCase'.
            - ``upper``: The format will be all uppercase with
            underscore for spaces.
        :type  convention: str

        """

        self.name_conv = convention

        self._update_conv()

    def set_root_url(self, url):
        """
        Sets the root URL of the RAPI.

        :param url: The new URL.
        :type  url: str
        """

        self.rapi_root = url

    def download_image(self, url, dest_fn, fsize, show_progress=True):
        """
        Given a list of remote and local items, download the remote data if
        it is not already found locally.

        (Adapted from the eodms-api-client (
        https://pypi.org/project/eodms-api-client/) developed by Mike Brady)

        :param url: The download URL of the image.
        :type  url: str
        :param dest_fn: The local destination filename for the download.
        :type  dest_fn: str
        :param fsize: The total filesize of the image.
        :type  fsize: int
        :param show_progress: Determines whether to show progress while
        downloading an image
        :type  show_progress: bool
        """

        # If we have an existing local file, check the filesize against the
        #   manifest
        if os.path.exists(dest_fn):
            # if all-good, continue to next file
            if os.stat(dest_fn).st_size == fsize:
                msg = f"No download necessary. Local file already exists: " \
                      f"{dest_fn}"
                self.log_msg(msg)
                return None
            # Otherwise, delete the incomplete/malformed local file and
            #   redownload
            else:
                msg = f'Filesize mismatch with {os.path.basename(dest_fn)}. ' \
                      f'Re-downloading...'
                self.log_msg(msg, 'warning')
                os.remove(dest_fn)

        if self._check_auth():
            return None

        # Use streamed download so we can wrap nicely with tqdm
        if show_progress:
            with self._session.get(url, stream=True, verify=self.verify) as stream:
                with open(dest_fn, 'wb') as pipe:
                    with tqdm.wrapattr(
                            pipe,
                            method='write',
                            miniters=1,
                            total=fsize,
                            desc=f"{self._header}{os.path.basename(dest_fn)}"
                    ) as file_out:
                        for chunk in stream.iter_content(chunk_size=1024):
                            file_out.write(chunk)
        else:
            response = self._session.get(url, stream=True, verify=self.verify)
            open(dest_fn, "wb").write(response.content)

        msg = f'{dest_fn} has been downloaded.'
        self.log_msg(msg)

    def download(self, items, dest, wait=10.0, max_attempts=None,
                 show_progress=True):
        """
        Downloads a list of order items from the EODMS RAPI.

        :param items: A list of order items returned from the RAPI.

            Example:

                .. code-block:: python

                    {'items': [
                        {'recordId': '8023427',
                         'status': 'SUBMITTED',
                         'collectionId': 'RCMImageProducts',
                         'itemId': '346204',
                         'orderId': '50975'},
                    ...]}
                or

                .. code-block:: python

                    [{
                        'recordId': '8023427',
                        'status': 'SUBMITTED',
                        'collectionId': 'RCMImageProducts',
                        'itemId': '346204',
                        'orderId': '50975'
                    }, ...]

        :type  items: list or dict
        :param dest: The local download folder
            location.
        :type  dest: str
        :param wait: Sets the time to wait before checking the status of
            all orders.
        :type  wait: float or int
        :param max_attempts: The number of download attempts before stopping
            downloads. If None, the script will continue to check and download
            orders until all orders have been downloaded.
        :type  max_attempts: int
        :param show_progress: Determines whether to show progress while
        downloading an image
        :type  show_progress: bool

        :return: A list of the download (completed) items.
        :rtype: list
        """

        msg = "Downloading images..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        if items is None:
            msg = "No images to download."
            self.log_msg(msg)
            return []

        if isinstance(items, dict):
            if 'items' in items.keys():
                items = items['items']

        if len(items) == 0:
            msg = "No images to download."
            self.log_msg(msg)
            return []

        unique_items = self.remove_duplicate_orders(items)

        attempt = 0
        complete_items = []
        while len(unique_items) > len(complete_items):
            time.sleep(wait)
            attempt += 1

            if max_attempts is not None and not max_attempts == '':
                if attempt > max_attempts:
                    msg = "Maximum number of attempts reached."
                    self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')
                    return complete_items

            # start, end = self._get_dateRange(unique_items)
            # orders = self.get_orders(dtstart=start, dtend=end)
            # print(f"max_downloads: {max_downloads}")
            # answer = input("Press enter...")
            # max_orders = max_downloads + int((max_downloads / 4))
            # orders = self.get_orders(max_orders=max_orders)
            orders = self.get_orders(unique_items)

            # for order in orders:
            #     print(f"itemId: {order.get('itemId')}")
            #     print(f"  orderId: {order.get('orderId')}")
            #     print(f"  recordId: {order.get('recordId')}")
            # answer = input("Press enter...")

            if self.err_occurred:
                return complete_items

            if orders is None:
                msg = "An error occurred while getting a list of orders. " \
                      "Downloads unsuccessful."
                self.log_msg(msg)
                return []

            if len(orders) == 0:
                msg = "No orders could be found."
                self.log_msg(msg)
                return []

            new_count = len(complete_items)

            for itm in unique_items:
                item_id = itm['itemId']
                cur_item = self._get_item_from_orders(item_id, orders)
                order_id = cur_item['orderId']
                status = cur_item['status']
                record_id = cur_item['recordId']
                coll_id = cur_item['collectionId']

                # Check record is already complete
                if self._check_complete(complete_items, record_id):
                    continue

                if status in self.failed_status:
                    if status == 'FAILED':
                        # If the order has failed, inform user
                        status_mess = cur_item.get('statusMessage')
                        msg = "\n  The following Order Item has failed:"
                        if status_mess is None:
                            msg += f"\n    Order Item Id: " \
                                   f"{cur_item['itemId']}\n" \
                                   f"    Order Id: {order_id}\n" \
                                   f"    Record Id: {cur_item['recordId']}" \
                                   f"    Collection: {coll_id}\n"

                        else:
                            msg += f"\n    Order Item Id: " \
                                   f"{cur_item['itemId']}\n" \
                                   f"    Order Id: {order_id}\n" \
                                   f"    Record Id: {cur_item['recordId']}\n" \
                                   f"    Collection: {coll_id}\n" \
                                   f"    Reason for Failure: " \
                                   f"{cur_item['statusMessage']}"
                    else:
                        # If the order was unsuccessful with another status,
                        #   inform user
                        msg = f"\n  The following Order Item has status " \
                              f"'{status}' and will not be downloaded:"
                        msg += f"\n    Order Item Id: {cur_item['itemId']}\n" \
                               f"    Record Id: {cur_item['recordId']}\n" \
                               f"    Collection: {coll_id}\n"

                    self.log_msg(msg)

                    cur_item['downloaded'] = 'False'

                    complete_items.append(cur_item)

                elif status == 'AVAILABLE_FOR_DOWNLOAD':
                    cur_item['downloaded'] = 'True'

                    dests = cur_item['destinations']
                    manifest_key = list(cur_item['manifest'].keys()).pop()
                    fsize = int(cur_item['manifest'][manifest_key])

                    download_paths = []
                    for d in dests:

                        # Get the string value of the destination
                        str_val = d['stringValue']
                        str_val = str_val.replace('</br>', '')

                        str_val = str_val.replace('&', '?')

                        # Parse the HTML text of the destination string
                        root = ElementTree.fromstring(str_val)
                        url = root.text
                        url = url.split("?")[0]

                        fn = os.path.basename(url)

                        # Download the image
                        msg = f"Downloading image from Collection {coll_id} " \
                              f"with Record Id {record_id} ({fn})."
                        self.log_msg(msg)

                        # Save the image contents to the 'downloads' folder
                        out_fn = os.path.join(dest, fn)
                        full_path = os.path.realpath(out_fn)

                        if not os.path.exists(dest):
                            os.makedirs(dest, exist_ok=True)

                        try:
                            self.download_image(url, out_fn, fsize,
                                                show_progress=show_progress)
                        except Exception as e:
                            self.log_msg(e, 'warning')
                            continue

                        print('')

                        # Record the URL and downloaded file to a dictionary
                        dest_info = {'url': url, 'local_destination': full_path}
                        download_paths.append(dest_info)

                    cur_item['downloadPaths'] = download_paths

                    complete_items.append(cur_item)

            if new_count == 0 and len(complete_items) == 0:
                msg = "No items are ready for download yet."
                self.log_msg(msg)
            elif new_count == len(complete_items):
                msg = "No new items are ready for download yet."
                self.log_msg(msg)

        return complete_items

    def get_available_fields(self, collection=None, name_type='all',
                             ui_fields=False):
        """
        Gets a dictionary of available fields for a collection from the RAPI.

        :param collection: The Collection ID.
        :type  collection: str
        :param name_type: The field name type to search for.
        :type  name_type: str
        :param ui_fields: Determines whether to return fields that the
        EODMS UI website uses.
        :type  ui_fields: bool

        :return: A dictionary containing the available fields for the given
                collection.
        :rtype:  dict
        """

        if collection is None:
            if self.collection is None:
                self.log_msg('No collection can be determined.', 'warning')
                return None
            collection = self.collection

        query_url = f"{self.rapi_root}/collections/{collection}?format=json"

        coll_res = self._submit(query_url, timeout=20.0)

        if coll_res is None or self.err_occurred:
            return None

        # If an error occurred
        if isinstance(coll_res, QueryError):
            self.log_msg(coll_res.get_msgs(True), 'warning')
            return None

        coll_ui_fields = self.ui_field_map.get(collection)

        # Get a list of the searchFields
        fields = {}
        if name_type == 'title' or name_type == 'id':

            srch_fields = []
            for r in coll_res['searchFields']:
                if coll_ui_fields is not None and ui_fields:
                    if r['id'] not in coll_ui_fields:
                        continue
                srch_fields.append(r[name_type])

            fields['search'] = srch_fields

            res_fields = []
            for r in coll_res['resultFields']:
                res_fields.append(r[name_type])

            fields['results'] = res_fields

        else:
            srch_fields = {}
            for r in coll_res['searchFields']:
                if coll_ui_fields is not None and ui_fields:
                    if r['id'] not in coll_ui_fields:
                        continue
                if r.get('choices') is None:
                    r['choices'] = None
                srch_fields[r['title']] = r

            fields['search'] = srch_fields

            res_fields = {}
            for r in coll_res['resultFields']:
                res_fields[r['title']] = r

            fields['results'] = res_fields

        return fields

    def get_field_choices(self, collection, field=None, full=False):
        """
        Gets the available choices for a specified field. If no choices exist,
        then the data type is returned.

        :param collection: The collection containing the field.
        :type  collection: str
        :param field: The field name or field ID.
        :type  field: str

        :return: Either a list of choices or a string containing the
                data type.
        :rtype: list or str
        """

        fields = self.get_available_fields(collection)

        if self.err_occurred:
            return None

        all_fields = {}
        for f, v in fields['search'].items():
            choices = []
            if field is None:
                field_choices = v.get('choices')
                if field_choices is not None:
                    if full:
                        choices = field_choices
                    else:
                        for c in field_choices:
                            value = c['value']
                            if not value == '':
                                choices.append(value)
                    all_fields[f] = choices
                else:
                    all_fields[f] = {'data_type': v.get('datatype')}
            else:
                if f == field or v['id'] == field:
                    field_choices = v.get('choices')
                    if field_choices is not None:
                        if full:
                            choices = field_choices
                        else:
                            for c in field_choices:
                                value = c['value']
                                if not value == '':
                                    choices.append(value)
                        return choices
                    else:
                        return {'data_type': v.get('datatype')}

        return all_fields

    def get_collections(self, as_list=False, opt='id', redo=False):
        """
        Gets a list of available collections for the current user.

        :param as_list: Determines the type of return. If False, a dictionary
                        will be returned. If True, only a list of collection
                        IDs will be returned.
        :type  as_list: bool
        :param opt: Determines whether the list of collections should be just
            titles or both titles and ids.
        :type  opt: str
        :param redo: Determines whether to get the list from the RAPI again.
        :type  redo: bool

        :return: Either a dictionary of collections or a list of collection IDs
                depending on the value of as_list.
        :rtype:  dict
        """

        if self.rapi_collections and not redo:
            if as_list:
                if opt == 'title':
                    collections = [i['title'] for i in
                                   self.rapi_collections.values()]
                elif opt == 'both':
                    collections = [{'id': k, 'title': v['title']}
                                   for k, v in self.rapi_collections.items()]
                else:
                    collections = list(self.rapi_collections.keys())
                return collections

            return self.rapi_collections

        # Create the query to get available collections for the current user
        query_url = f"{self.rapi_root}/collections?format=json"

        msg = "Getting Collection information, please wait..."
        self.log_msg(msg)
        logger.debug(f"RAPI URL: {query_url}")

        # Send the query URL
        coll_res = self._submit(query_url, timeout=20.0)

        if coll_res is None or self.err_occurred:
            return None

        # If an error occurred
        if isinstance(coll_res, QueryError):
            self.err_msg = f"Could not get a list of collections due to " \
                  f"'{coll_res.get_msgs(True)}'."
            self.err_occurred = True
            self.log_msg(self.err_msg, 'error')
            return coll_res

        # Create the collections dictionary
        for coll in coll_res:
            for child in coll['children']:
                for c in child['children']:
                    coll_id = c['collectionId']
                    # Add aliases for specific collections allowing easier
                    #   access for users
                    aliases = []
                    if coll_id == 'RCMImageProducts':
                        aliases = ['rcm']
                    elif coll_id == 'Radarsat1':
                        aliases = ['r1', 'rs1', 'radarsat', 'radarsat-1']
                    elif coll_id == 'Radarsat2':
                        aliases = ['r2', 'rs2', 'radarsat-2']
                    elif coll_id == 'PlanetScope':
                        aliases = ['planet']
                    fields = self.get_available_fields(coll_id, 'all')
                    if self.err_occurred:
                        return None
                    if fields is None:
                        continue
                    self.rapi_collections[c['collectionId']] = {
                        'title': c['title'],
                        'aliases': aliases,
                        'fields': fields}

        # If as_list is True, convert dictionary to list of collection IDs
        if as_list:
            if opt == 'title':
                collections = [i['title'] for i in
                               self.rapi_collections.values()]
            elif opt == 'both':
                collections = [{'id': k, 'title': v['title']}
                               for k, v in self.rapi_collections.items()]
            else:
                collections = list(self.rapi_collections.keys())
            return collections

        return self.rapi_collections

    def get_order_item(self, item_id):
        """
        Submits a query to the EODMS RAPI to get a specific order item.

        :param item_id: The Order Item ID of the image to retrieve from the
            RAPI.
        :type  item_id: str or int

        :return: A dictionary containing the JSON format of the results from
            the RAPI.
        :rtype:  dict
        """

        query = f"{self.rapi_root}/order?itemId={item_id}&format=json"
        log_msg = f"Getting order item {item_id} (RAPI query): {query}"
        msg = f"Getting order item {item_id}..."

        messages = (log_msg, msg)
        self.log_msg(messages, log_indent='\n\n\t', out_indent='\n')

        res = self._submit(query, timeout=self.timeout_order)

        if res is None or self.err_occurred:
            return None

        return res

    def get_order(self, order_id):
        """
        Gets an specified order from the EODMS RAPI.

        :param order_id: The Order ID of the specific order.
        :type  order_id: str or int

        :return: A JSON dictionary of the specific order.
        :rtype:  dict
        """

        query_url = f"{self.rapi_root}/order?orderId={order_id}&format=json"

        logger.debug(f"RAPI URL:\n\n{query_url}\n")

        # Send the query to the RAPI
        res = self._submit(query_url, timeout=self.timeout_query, quiet=False)

        if self.err_occurred:
            return None

        if res is None or isinstance(res, QueryError):
            if isinstance(res, QueryError):
                msg = f"Could not get order with Order ID {order_id} due " \
                      f"to {res.get_msgs(True)}."
            else:
                msg = f"Could not get order with Order ID {order_id}."
            self.log_msg(msg, 'warning')
            return None

        if 'items' in res.keys():
            return res['items']
        else:
            return res

    def get_orders(self, order_res=None, dtstart=None, dtend=None,
                   max_orders=100, status=None, out_format='json'):
        """
        Sends a query to retrieve orders from the RAPI.

        :param order_res: The results from an order submission. If this value
            is included, dtstart, dtend and max_orders will be ignored.
        :type  order_res: list
        :param dtstart: The start date for the date range of the query.
        :type  dtstart: datetime.datetime
        :param dtend: The end date for the date range of the query.
        :type  dtend: datetime.datetime
        :param max_orders: The maximum number of orders to retrieve.
        :type  max_orders: int
        :param status: The status of the orders to retrieve.
        :type  status: str
        :param out_format: The format of the results.
        :type  out_format: str

        :return: A JSON dictionary of the query results containing the orders.
        :rtype:  dict
        """

        msg = "Getting list of current orders..."
        self.log_msg(msg)

        tm_frm = '%Y-%m-%dT%H:%M:%SZ'

        if order_res is not None:

            # Get a list of unique orders
            if isinstance(order_res, dict) and 'items' in order_res.keys():
                order_res = order_res['items']

            unique_list = list(set([o['orderId'] for o in order_res]))

            all_orders = []
            for order_id in unique_list:
                # Submit query with order ID
                query_url = f"{self.rapi_root}/order?orderId={order_id}" \
                            f"&format={out_format}"

                logger.debug(f"RAPI URL:\n\n{query_url}\n")

                # Send the query to the RAPI
                res = self._submit(query_url, timeout=self.timeout_query,
                                   quiet=False)

                if self.err_occurred:
                    return None

                if res is None or isinstance(res, QueryError):
                    if isinstance(res, QueryError):
                        msg = f"Order submission was unsuccessful due to: " \
                              f"{res.get_msgs(True)}."

                    else:
                        msg = "Order submission was unsuccessful."
                    self.log_msg(msg, 'warning')
                    continue

                if 'items' in res.keys():
                    res = res['items']

                all_orders += res

            return all_orders

        params = {}
        if dtstart is not None:
            params['dtstart'] = dtstart.strftime(tm_frm)
            params['dtend'] = dtend.strftime(tm_frm)
        params['maxOrders'] = max_orders
        if status is not None:
            params['status'] = status.upper()
        param_str = urlencode(params)

        query_url = f"{self.rapi_root}/order?{param_str}&format={out_format}"

        logger.debug(f"RAPI URL:\n\n{query_url}\n")

        # Send the query to the RAPI
        res = self._submit(query_url, timeout=self.timeout_query, quiet=False)

        if self.err_occurred:
            return None

        if res is None or isinstance(res, QueryError):
            if isinstance(res, QueryError):
                msg = f"Order submission was unsuccessful due to: " \
                      f"{res.get_msgs(True)}."

            else:
                msg = "Order submission was unsuccessful."
            self.log_msg(msg, 'warning')
            return None

        if 'items' in res.keys():
            res = res['items']

        if status is not None:
            status_res = [r for r in res if r.get('status') == status.upper()]
            return status_res
        else:
            return res

    def get_orders_by_records(self, records):
        """
        Gets a list of orders from the RAPI based on a list of records.

        :param records: A list of records used to get the list of orders.
        :type  records: list

        :return: A list of results from the RAPI.
        :rtype:  list
        """

        if isinstance(records, dict):
            if 'items' in records.keys():
                records = records['items']

        if records is None or len(records) == 0:
            msg = "Cannot get orders as no image items provided."
            self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')
            return None

        if not all("orderId" in keys for keys in records):
            # msg = "Cannot get orders as no orderId is provided in the " \
            #       "results."
            orders = self.get_orders()
            # self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        else:

            # dates = self._get_date_range(records)
            #
            # if dates is None:
            #     msg = "Cannot get orders as no order dates are available."
            #     self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')
            #     return None
            #
            # start, end = dates

            orders = self.get_orders(records)

        if self.err_occurred:
            return None

        msg = "Getting a list of order items..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        found_orders = []
        unfound = []
        for idx, r in enumerate(records):

            # Go through each record
            rec_id = r['recordId']

            rec_orders = []

            for i in orders:
                # Go through each order item

                if i['recordId'] == r['recordId']:
                    # Check in filt_orders for an older order item
                    #   and replace it
                    rec_orders.append(i)

            if len(rec_orders) == 0:
                unfound.append(rec_id)
                continue

            # Get the most recent order item with the given recordId
            filt_recs = [r for r in rec_orders if r['recordId'] == rec_id]
            order_item = max(filt_recs, key=lambda x: x['dateSubmitted'])

            found_orders.append(order_item)

        msg = f"Found {len(found_orders)} order items for the following " \
              f"records: {', '.join([r['recordId'] for r in found_orders])}"
        self.log_msg(msg)

        if len(unfound) > 0:
            msg = f"No order items found for the following records: " \
                  f"{', '.join(unfound)}"
            self.log_msg(msg)

        return found_orders

    def get_order_parameters(self, collection, record_id):
        """
        Gets the list of available Order parameters for a given image record.

        :param collection: The Collection ID for the query.
        :type  collection: str
        :param record_id: The Record ID for the image.
        :type  record_id: int or str

        :return: A JSON dictionary of the order parameters.
        :rtype:  dict

        """

        # Get the proper Collection ID for the RAPI
        collection = self.get_collection_id(collection)

        if self.err_occurred:
            return None

        msg = f"\n\n\tGetting order parameters for image in Collection " \
              f"{collection} with Record ID {record_id}..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        # Set the RAPI URL
        query_url = f"{self.rapi_root}/order/params/{collection}/" \
                    f"{record_id}?format=json"

        # Send the JSON request to the RAPI
        try:
            param_res = self._session.get(url=query_url, verify=self.verify)
            param_res.raise_for_status()
        except (requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as req_err:
            msg = f"{req_err.__class__.__name__} Error: {req_err}"
            self.log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt:
            self.err_msg = "Process ended by user."
            self.log_msg(self.err_msg, out_indent='\n')
            self.err_occurred = True
            print()
            return None

        if not param_res.ok:
            err = self._get_exception(param_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self.log_msg(msg, 'warning')
                return msg

        # msg = "Order removed successfully."
        # self.log_msg(msg)

        return param_res.json()

    def get_rapi_url(self):
        """ Gets the previous URL used to query the RAPI.

        return: The RAPI URL.
        rtype: str
        """

        return self._rapi_url

    def get_record(self, collection, record_id, output='full'):
        """
        Gets an image record from the RAPI.

        :param collection: The Collection ID of the record.
        :type  collection: str
        :param record_id: The Record ID of the image.
        :type  record_id: str or int
        :param output: The format of the results (either 'full', 'raw'
                        or 'geojson').
        :type  output: str
        """

        # keys = self.get_meta_keys()

        self.collection = self.get_collection_id(collection)

        self._rapi_url = f"{self.rapi_root}/record/{self.collection}/" \
                         f"{record_id}?format=json"

        self.results = self._submit(self._rapi_url)

        if self.err_occurred:
            return None

        if isinstance(self.results, QueryError):
            msg = self.results.get_msgs()
            self.log_msg(msg, 'warning')
            return {'errors': msg}

        if output == 'geojson':
            feat = self.geo.convert_to_geojson(self.results, 'list')
            return feat
        elif output == 'raw':
            return self.results
        else:
            return self.parse_metadata(self.results)

    def cancel_order_item(self, order_id, item_id):

        """
        Removes an Order Item from the EODMS using the RAPI.

        :param order_id: The Order ID of the Order Item to remove.
        :type  order_id: int or str
        :param item_id: The Order Item ID of the Order Item to remove.
        :type  item_id: int or str

        :return: Returns the contents of the Delete request (always empty).
        :rtype:  byte str
        """

        msg = f"Removing order item {item_id}..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        # Set the RAPI URL
        self._rapi_url = f"{self.rapi_root}/order/{order_id}/{item_id}"

        # Send the JSON request to the RAPI
        cancel_res = self._submit(self._rapi_url, 'delete')

        if self.err_occurred:
            return None

        # try:
        #     cancel_res = self._session.delete(url=self._rapi_url)
        #     cancel_res.raise_for_status()
        # except (requests.exceptions.HTTPError,
        #         requests.exceptions.ConnectionError,
        #         requests.exceptions.Timeout,
        #         requests.exceptions.RequestException) as req_err:
        #     err = self._get_exception(cancel_res).get_msgs()
        #     msg = f"{req_err.__class__.__name__} Error: {req_err} - {err[1]}"
        #     self.log_msg(msg, 'warning')
        #     return msg
        # except KeyboardInterrupt:
        #     msg = "Process ended by user."
        #     self.log_msg(msg, out_indent='\n')
        #     self.err_occurred = True
        #     print()
        #     return None

        if not cancel_res.ok:
            err = self._get_exception(cancel_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self.log_msg(msg, 'warning')
                return msg

        msg = "Order removed successfully."
        self.log_msg(msg)

        return cancel_res.content

    def create_destination(self, dest_type, dest_name, **kwargs):
        """
        Create a new destination using the given dest_type and dest_name.

        :param dest_type: The destination type, either "FTP" or "Physical".
        :type  dest_type: str
        :param dest_name: The destination name
        :type  dest_name: str
        :param kwargs:
        Options for FTP:
            *hostname*: The fully qualified domain name of the target FTP
            server.
            *username*: The username used to log in to the target FTP server.
            *password*: The password used to log in to the target FTP server.
            *string_val*: A readable string representation of the whole object,
            typically "ftp://{user}@{host}/{path}"
            *path*: After logging in to the FTP server, change directory to
            this path (optional; default is the root directory)
            *can_edit*: "true" if the currently connected user is allowed
            to modify the properties of this Order Destination object
            (server to client only)
        Options for Physical:
            *customerName*: The name of the customer who will receive the
            order (required).
            *contactEmail*: An email address that can be used to contact
            the customer if necessary (required).
            *organization*: The names of any organization and organizational
            units necessary to identify the delivery location (optional).
            *phone*: A phone number that can be used to contact the customer
            if necessary (optional).
            *addrs*: A list of physical delivery addresses (1 address is
            required, a maximum of 3).
            *city*: The city or other community of the physical delivery
            address (required).
            *stateProv*: The name or code identifying the state or other
            administrative region required for the physical delivery
            address (required for most countries).
            *country*: The name of the country to which the product is to
            be delivered (required).
            *postalCode*: Any code that is necessary for the postal system
            to successfully deliver the product (required for many countries).
            *classification*: This is the security classification of the
            physical address (optional).
        """

        msg = "Creating destination..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        dest_info = {'type': dest_type,
                     'name': dest_name}

        if dest_type.lower() == 'ftp':
            hostname = kwargs.get('hostname')
            username = kwargs.get('username')
            password = kwargs.get('password')
            string_val = kwargs.get('string_val')
            path = kwargs.get('path')
            can_edit = kwargs.get('can_edit')

            dest_info['hostname'] = hostname
            dest_info['username'] = username
            dest_info['password'] = password
            dest_info['stringValue'] = string_val
            if path:
                dest_info['path'] = path
            dest_info['canEdit'] = can_edit
        else:
            customer_name = kwargs.get('customer_name')
            contact_email = kwargs.get('contact_email')
            organization = kwargs.get('organization')
            phone = kwargs.get('phone')
            addrs = kwargs.get('addrs')
            city = kwargs.get('city')
            state_prov = kwargs.get('state_prov')
            country = kwargs.get('country')
            postal_code = kwargs.get('postal_code')
            classification = kwargs.get('classification')

            dest_info['customerName'] = customer_name
            dest_info['contactEmail'] = contact_email
            if organization:
                dest_info['organization'] = organization
            if phone:
                dest_info['phone'] = phone
            dest_info['addr1'] = addrs[0]
            if len(addrs) > 1:
                for idx, a in enumerate(addrs[1:3]):
                    dest_info[f'addr{idx + 2}'] = a
            dest_info['city'] = city
            dest_info['stateProv'] = state_prov
            dest_info['country'] = country
            dest_info['postalCode'] = postal_code
            if classification:
                dest_info['classification'] = classification

        self._rapi_url = f"{self.rapi_root}/order/destinations"
        dest_json = json.dumps(dest_info)
        dest_res = self._submit(self._rapi_url, 'post', dest_json)

        if self.err_occurred:
            return None

        if isinstance(dest_res, QueryError):
            self.err_msg = f"Could not create destination due to " \
                  f"'{dest_res.get_msgs(True)}'."
            self.err_occurred = True
            self.log_msg(self.err_msg, 'error')
            return None

        return dest_res

    def delete_destination(self, dest_type, dest_name):
        """
        Deletes a specific destination using the dest_type and dest_name.

        :param dest_type: The destination type, either "FTP" or "Physical".
        :type  dest_type: str
        :param dest_name: The destination name
        :type  dest_name: str
        """

        msg = "Deleting destination..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        # Set the RAPI URL
        dest_url = f"{self.rapi_root}/order/destinations/{dest_type}/" \
                   f"{dest_name}"

        # Delete the given destination
        dest_res = self._submit(dest_url, 'delete')

        if self.err_occurred:
            return None

        if isinstance(dest_res, QueryError):
            self.err_msg = f"Could not delete destination due to " \
                  f"'{dest_res.get_msgs(True)}'."
            self.err_occurred = True
            self.log_msg(self.err_msg, 'error')
            return None

        return dest_res

    def edit_destination(self, dest_type, dest_name, **kwargs):
        """
        Edits an existing destination using the given dest_type and dest_name

        :param dest_type: The destination type, either "FTP" or "Physical".
        :type  dest_type: str
        :param dest_name: The destination name
        :type  dest_name: str
        :param kwargs:
        Options for FTP:
            *hostname*: The fully qualified domain name of the target FTP
            server.
            *username*: The username used to log in to the target FTP server.
            *password*: The password used to log in to the target FTP server.
            *string_val*: A readable string representation of the whole object,
            typically "ftp://{user}@{host}/{path}"
            *path*: After logging in to the FTP server, change directory to
            this path (optional; default is the root directory)
            *can_edit*: "true" if the currently connected user is allowed
            to modify the properties of this Order Destination object
            (server to client only)
        Options for Physical:
            *customerName*: The name of the customer who will receive the
            order (required).
            *contactEmail*: An email address that can be used to contact
            the customer if necessary (required).
            *organization*: The names of any organization and organizational
            units necessary to identify the delivery location (optional).
            *phone*: A phone number that can be used to contact the customer
            if necessary (optional).
            *addrs*: A list of physical delivery addresses (1 address is
            required, a maximum of 3).
            *city*: The city or other community of the physical delivery
            address (required).
            *stateProv*: The name or code identifying the state or other
            administrative region required for the physical delivery
            address (required for most countries).
            *country*: The name of the country to which the product is to
            be delivered (required).
            *postalCode*: Any code that is necessary for the postal system
            to successfully deliver the product (required for many countries).
            *classification*: This is the security classification of the
            physical address (optional).
        """

        msg = "Creating destination..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        dest_info = {'type': dest_type, 'name': dest_name}

        if dest_type.lower() == 'ftp':
            hostname = kwargs.get('hostname')
            username = kwargs.get('username')
            password = kwargs.get('password')
            string_val = kwargs.get('string_val')
            path = kwargs.get('path')
            can_edit = kwargs.get('can_edit')

            dest_info['hostname'] = hostname
            dest_info['username'] = username
            dest_info['password'] = password
            dest_info['stringValue'] = string_val
            if path:
                dest_info['path'] = path
            dest_info['canEdit'] = can_edit
        else:
            customer_name = kwargs.get('customer_name')
            contact_email = kwargs.get('contact_email')
            organization = kwargs.get('organization')
            phone = kwargs.get('phone')
            addrs = kwargs.get('addrs')
            city = kwargs.get('city')
            state_prov = kwargs.get('state_prov')
            country = kwargs.get('country')
            postal_code = kwargs.get('postal_code')
            classification = kwargs.get('classification')

            dest_info['customerName'] = customer_name
            dest_info['contactEmail'] = contact_email
            if organization:
                dest_info['organization'] = organization
            if phone:
                dest_info['phone'] = phone
            dest_info['addr1'] = addrs[0]
            if len(addrs) > 1:
                for idx, a in enumerate(addrs[1:3]):
                    dest_info[f'addr{idx + 2}'] = a
            dest_info['city'] = city
            dest_info['stateProv'] = state_prov
            dest_info['country'] = country
            dest_info['postalCode'] = postal_code
            if classification:
                dest_info['classification'] = classification

        # Set the RAPI URL
        dest_url = f"{self.rapi_root}/order/destinations/{dest_type}/" \
                   f"{dest_name}"
        dest_json = json.dumps(dest_info)
        dest_res = self._submit(dest_url, 'put', dest_json)

        if self.err_occurred:
            return None

        if isinstance(dest_res, QueryError):
            self.err_msg = f"Could not update destination due to " \
                  f"'{dest_res.get_msgs(True)}'."
            self.err_occurred = True
            self.log_msg(self.err_msg, 'error')
            return None

        return dest_res

    def retrieve_destinations(self, collection=None, record_id=None):
        """
        Retrieves a list of order destinations for the current profile.

        :param collection: The Collection Id. If this value is set, then the
            record_id must be set as well.
        :type  collection: str
        :param record_id: The Record Id for a specific image. If this value is
            set, then the collection must be set as well.
        """

        msg = "Retrieving list of destinations..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        if collection is not None:
            self._rapi_url = f"{self.rapi_root}/order/destinations?" \
                             f"collection={collection}&recordId={record_id}"
        else:
            self._rapi_url = f"{self.rapi_root}/order/destinations"

        self.results = self._submit(self._rapi_url)

        if self.err_occurred:
            return None

        if isinstance(self.results, QueryError):
            msg = self.results.get_msgs()
            self.log_msg(msg, 'warning')
            return {'errors': msg}

        return self.results

    def search_url(self, url, **kwargs):
        """
        Submits a URL to the RAPI.

        :param url: A valid RAPI URL (with or without the path)
        :type  url: str
        :param kwargs: Options include:<br>
                filters (dict): A dictionary of filters and values for the
                    RAPI.<br>
                features (list): A list of geometries for the query.<br>
                dates (list): A list of date range dictionaries containing keys
                        'start' and 'end'.<br>
        :type  kwargs: dict
        """

        if url.find("?") > -1:
            query_str = url.split('?')[1]
        else:
            query_str = url

        params = {p.split('=')[0]: urllib.parse.unquote_plus('='.join(
            p.split('=')[1:])) for p in query_str.split('&')}
        self.collection = params['collection']

        filters = kwargs.get('filters')
        features = kwargs.get('features')
        dates = kwargs.get('dates')

        if filters is not None or features is not None or dates is not None:
            query = params.get('query')
            if query is None:
                params['query'] = self._parse_query(filters, features,
                                                    dates)
            else:
                params['query'] = '%s AND %s' % (query, self._parse_query(
                    filters, features, dates))

        if 'maxResults' in params.keys():
            self.max_results = int(params['maxResults'])
        else:
            self.max_results = 20

        if 'format' not in params:
            params['format'] = 'json'

        result_field = params.get('resultField')
        if result_field is None:
            result_fields = []

            footprint_id = self._get_field_id('Footprint', self.collection)
            if self.err_occurred:
                return None
            if footprint_id is not None:
                result_fields.append(footprint_id)

            pixspace_id = self._get_field_id('Spatial Resolution',
                                             self.collection)
            if self.err_occurred:
                return None
            if pixspace_id is not None:
                result_fields.append(pixspace_id)
        else:
            result_fields = result_field.split(',')

            footprint_id = self._get_field_id('Footprint', self.collection)
            if self.err_occurred:
                return None
            if footprint_id is not None:
                if footprint_id not in result_fields:
                    result_fields.append(footprint_id)

            pixspace_id = self._get_field_id('Spatial Resolution',
                                             self.collection)
            if self.err_occurred:
                return None
            if pixspace_id is not None:
                if pixspace_id not in result_fields:
                    result_fields.append(pixspace_id)

        if result_field is not None and len(result_field) > 0:
            params['resultField'] = ','.join(result_fields)

        query_str = urlencode(params)
        self._rapi_url = f"{self.rapi_root}/search?{query_str}"

        # Clear self.search_results
        self.search_results = []

        msg = f"Searching for {self.collection} images on RAPI"
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        logger.debug(f"RAPI URL:\n\n{self._rapi_url}\n")
        print(f"RAPI URL:\n\n{self._rapi_url}\n")
        # Send the query to the RAPI
        self._submit_search()

        if self.err_occurred:
            return None

        self.res_mdata = None

        if isinstance(self.search_results, QueryError):
            msg = self.search_results.get_msgs()
            if isinstance(msgs, list):
                self.log_msg(': '.join(msgs), 'warning')
            else:
                self.log_msg(msgs, 'warning')
            return {'errors': msg}

        msg = f"Number of {self.collection} images returned from RAPI: " \
              f"{len(self.search_results)}"
        self.log_msg(msg)

        self.results += self.search_results

    def search(self, collection, filters=None, features=None, dates=None,
               result_fields=None, max_results=None):
        """
        Sends a search to the RAPI to search for image results.

        :param collection: The Collection ID for the query.
        :type  collection: str
        :param filters: A dictionary of query filters and values in the
            following format:

                ``{"|filter title|": ("|operator|", ["value1", "value2", ...]),
                ...}``

                Example:

                .. code-block:: python

                    {"Beam Mnemonic": {'=': []}}

        :type  filters: dict
        :param features: A list of tuples containing the operator and
            filenames or coordinates of features to use in the search.
            The features can be:

                - a filename (ESRI Shapefile, KML, GML or GeoJSON)
                - a WKT format string
                - the 'geometry' entry from a GeoJSON Feature
                - a list of coordinates (ex: ``[(x1, y1), (x2, y2), ...]``)

        :type  features: list
        :param dates: A list of date range dictionaries with keys ``start``
                and ``end``.
                The values of the ``start`` and ``end`` can either be a
                string in format
                ``yyyymmdd_hhmmss`` or a datetime.datetime object.

                Example:

                .. code-block:: python

                    [{"start": "20201013_120000", "end": "20201013_150000"}]

        :type  dates: list
        :param result_fields: A name of a field to include in the query results.
        :type  result_fields: str
        :param max_results: The maximum number of results to return from the
            query.
        :type  max_results: str or int

        """

        # Get the proper Collection ID for the RAPI
        if result_fields is None:
            result_fields = []
        self.collection = self.get_collection_id(collection)

        if self.collection is None or self.err_occurred:
            return None

        params = {'collection': self.collection}

        if filters is not None or features is not None or dates is not None:
            params['query'] = self._parse_query(filters, features, dates)
            if self.err_occurred:
                return None

        if isinstance(result_fields, str):
            result_fields = [result_fields]

        result_field = []
        for field in result_fields:
            field_id = self._get_field_id(field, field_type='results')
            if self.err_occurred:
                return None

            if field_id is None:
                msg = f"Field '{field}'' does not exist for collection " \
                      f"'{self.collection}'. Excluding it from resultField " \
                      f"entry."
                self.log_msg(msg, 'warning')
            else:
                result_field.append(field_id)

        # Get the geometry field and add it to resultField
        footprint_id = self._get_field_id('Footprint', field_type='results')
        if self.err_occurred:
            return None
        if footprint_id is not None:
            result_field.append(footprint_id)

        # Get the pixel spacing field and add it to resultField
        pixspace_id = self._get_field_id('Spatial Resolution',
                                         field_type='results')
        if self.err_occurred:
            return None
        if pixspace_id is not None:
            result_field.append(pixspace_id)

        # Get the pixel spacing field and add it to resultField
        dl_id = self._get_field_id('Download Link', field_type='results')
        if self.err_occurred:
            return None
        if dl_id is not None:
            result_field.append(dl_id)

        params['resultField'] = ','.join(result_field)

        params['maxResults'] = self.limit_interval
        if max_results is None or max_results == '':
            self.max_results = None
        else:
            self.max_results = int(max_results)

            if self.max_results is not None:
                params['maxResults'] = self.max_results \
                    if int(self.max_results) < int(self.limit_interval) \
                    else self.limit_interval

        params['format'] = "json"

        query_str = urlencode(params)
        self._rapi_url = f"{self.rapi_root}/search?{query_str}"

        # Clear self.search_results
        self.search_results = []

        msg = f"Searching for {self.collection} images on RAPI"
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        logger.debug(f"RAPI URL:\n\n{self._rapi_url}\n")
        # Send the query to the RAPI
        self._submit_search()

        self.res_mdata = None

        if isinstance(self.search_results, QueryError):
            msgs = self.search_results.get_msgs()
            if isinstance(msgs, list):
                self.log_msg(': '.join(msgs), 'warning')
            else:
                self.log_msg(msgs, 'warning')
            return {'errors': msgs}

        msg = f"Number of {self.collection} images returned from RAPI: " \
              f"{len(self.search_results)}"
        self.log_msg(msg)

        self.results += self.search_results

    def reset(self):
        """
        Resets specific values for the EODMSRAPI.

        :return: n/a
        """

        self.clear_results()
        self.err_msg = None
        self.err_occurred = False
        self.auth_err = False
        self.order_json = None
        self.search_results = None

    def clear_results(self):
        """
        Clears the cumulative results.

        :return: n/a
        """

        self.results = []

    def get_results(self, form='raw', show_progress=True):
        """
        Gets the self.results in a given format

        :param form: The type of format to return.

            Available options:

            - ``raw``: Returns the JSON results straight from the RAPI.
            - ``brief``: Returns the JSON results with the 'raw' metadata but
                in the field convention.
            - ``full``: Returns a JSON with full metadata information.
            - ``geojson``: Returns a FeatureCollection of the results
                (requires geojson package).

        :type  form: str
        :param show_progress: Determines whether to show progress while
        fetching metadata
        :type  show_progress: bool

        :return: A dictionary of the results from self.results variable.
        :rtype:  dict

        """

        if self.results is None:
            msg = "No results exist. Please use search() to run a search " \
                  "on the RAPI."
            self.log_msg(msg, 'warning')
            return None

        if isinstance(self.results, QueryError):
            return [{'errors': self.results.get_msgs()}]

        if len(self.results) == 0:
            return self.results

        self.res_format = form

        if self.res_format == 'full':
            if self.res_mdata is None:
                self.res_mdata = self._fetch_metadata(
                    show_progress=show_progress)
            if self.err_occurred:
                return None
            return self.res_mdata
        elif self.res_format == 'geojson':
            if self.res_mdata is None:
                self.res_mdata = self._fetch_metadata(
                    show_progress=show_progress)
            if self.err_occurred:
                return None
            return self.geo.convert_to_geojson(self.res_mdata)
        elif self.res_format == 'brief':
            conv_res = []
            for res in self.results:
                mdata = self.parse_metadata(res)
                conv_res.append(mdata)

            self.results = conv_res

            return self.results
        else:
            return self.results

    def print_results(self, results=None):
        """
        Pretty prints the specified results.

        :param results: A JSON of results from the RAPI.
        :type  results: dict
        """

        if results is None:
            results = self.get_results('full')

        print(json.dumps(results, indent=4, ensure_ascii=False))

    def remove_duplicate_orders(self, orders):
        """
        Removes any duplicate images from a list of orders

        :param orders: A list of orders.
        :type  orders: list

        :return: A unique list of orders
        :rtype:  list
        """

        # Get duplicate record IDs
        rec_ids = [o['recordId'] for o in orders]
        dup_ids = list(set([x for x in rec_ids if rec_ids.count(x) > 1]))

        unique_orders = []
        for o in orders:
            rec_id = o['recordId']
            if rec_id in dup_ids:
                # For the duplicate, get the latest order
                filt_ords = [order for order in orders
                             if order['recordId'] == rec_id]

                for order in filt_ords:
                    if 'dateRapiOrdered' in order.keys():
                        order['dateSubmitted'] = order['dateRapiOrdered']
                        del order['dateRapiOrdered']

                if 'dateSubmitted' in filt_ords[0]:
                    date_sort = sorted(filt_ords,
                                    key=lambda d: d['dateSubmitted'],
                                    reverse=True)
                else:
                    date_sort = filt_ords
                if rec_id not in [order['recordId'] for order in unique_orders]:
                    unique_orders.append(date_sort[0])
            else:
                unique_orders.append(o)

        return unique_orders

    def order(self, results, priority="Medium", parameters=None,
              destinations=None):
        """
        Sends an order to EODMS using the RAPI.

        :param results: A list of JSON results from the RAPI.

            The results list must contain a ``collectionId`` key and a
                ``recordId`` key for each image.

        :type  results: list
        :param priority: Determines the priority of the order.

            If you'd like to specify a separate priority for each image,
            pass a list of dictionaries containing the ``recordId`` (matching
            the IDs in results) and ``priority``, such as:

            .. code-block:: python

                [{"recordId": 7627902, "priority": "Low"}, ...]

            Priority options: "Low", "Medium", "High" or "Urgent"

        :type  priority: str or list
        :param parameters: Either a list of parameters or a list of record
                            items.

                Use the get_order_parameters method to get a list of available
                    parameters.

                **Parameter list**: ``[{"|internalName|": "|value|"}, ...]``

                    Example:

                        .. code-block:: python

                            [
                                {"packagingFormat": "TARGZ"},
                                {"NOTIFICATION_EMAIL_ADDRESS":
                                    "kevin.ballantyne@canada.ca"},
                            ...]

                **Parameters for each record**: ``[{"recordId": |recordId|,
                    "parameters": [{"|internalName|": "|value|"}, ...]}]``

                    Example:

                        .. code-block:: python

                            [
                                {"recordId": 7627902,
                                 "parameters": [{"packagingFormat": "TARGZ"},
                                    ...]}
                            ]

        :type parameters: list
        :param destinations: A JSON representation of an array of order
            destinations
        :type  destinations: list
        """

        if destinations is None:
            destinations = []
        msg = "Submitting order items..."
        self.log_msg(msg, log_indent='\n\n\t', out_indent='\n')

        # Add the 'Content-Type' option to the header
        self._session.headers.update({'Content-Type': 'application/json'})

        # Create the items from the list of results
        coll_key = self.get_conv('collectionId')
        recid_key = self.get_conv('recordId')

        items = []
        for r in results:
            # Set the Collection ID and Record ID
            item = {'collectionId': r[coll_key],
                    'recordId': r[recid_key]}

            # Set the priority
            if priority is not None and not priority.lower() == 'medium':
                item['priority'] = priority.title()
            if 'priority' in r.keys():
                item['priority'] = r[self.get_conv('priority')].title()

            # Set parameters
            if parameters is not None:
                item['parameters'] = parameters
            if 'parameters' in r.keys():
                item['parameters'] = r[self.get_conv('parameters')]

            if item['collectionId'] == 'NAPL':
                params = item.get('parameters')
                if params is None:
                    params = []
                params.append({"MediaType": "DIGITAL"})
                params.append({"FreeMode": "true"})
                item['parameters'] = params

            items.append(item)

        # Create the dictionary for the POST request JSON
        self.order_json = [{"destinations": destinations,
                        "items": items[i:i + 100]} for i in range(0, len(items),
                                                                  100)]
        # Set the RAPI URL for the POST
        self._rapi_url = f"{self.rapi_root}/order"

        logger.debug(f"RAPI URL:\n\n{self._rapi_url}\n")

        # Send the JSON request to the RAPI
        time_submitted = datetime.datetime.now(tzlocal()).isoformat()
        # order_res = None
        all_items = []
        for p in self.order_json:
            # Dump the dictionary into a JSON object
            post_json = json.dumps(p)
            logger.debug(f"RAPI POST:\n\n{post_json}\n")
            order_res = self._submit(self._rapi_url, 'POST', post_json)

            if self.err_occurred:
                return None

            if order_res is None:
                err = self._get_exception(order_res)
                if isinstance(err, list):
                    msg = '; '.join(err)
                    self.log_msg(msg, 'warning')
                    return msg

            if isinstance(order_res, requests.Response) and not order_res.ok:
                self.err_msg = "Order submission failed."
                self.log_msg(self.err_msg, 'error')
                self.err_occurred = True
                return self.err_msg

            # Add the time the order was submitted
            items = order_res['items']

            for i in items:
                i['dateRapiOrdered'] = time_submitted

            all_items += items

        final_res = {'items': all_items}

        msg = "Order submitted successfully."
        self.log_msg(msg)

        return final_res
