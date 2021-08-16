##############################################################################
# MIT License
# 
# Copyright (c) 2021 Her Majesty the Queen in Right of Canada, as 
# represented by the President of the Treasury Board
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
import sys
import requests
import logging
import logging.config
import traceback
import urllib
import json
import csv
import datetime
import pytz
import time
import pprint
import re
import dateutil.parser
from dateutil.tz import tzlocal
from urllib.parse import urlencode
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree

from tqdm.auto import tqdm

from .geo import EODMSGeo

OTHER_FORMAT = '| %(name)s | %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'
              
logger = logging.getLogger('EODMSRAPI')

# Set handler for output to terminal
logger.setLevel(logging.DEBUG)
ch = logging.NullHandler()
formatter = logging.Formatter('| %(name)s | %(asctime)s | %(levelname)s: ' \
                                '%(message)s', '%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)

RECORD_KEYS = ["recordId", "overviewUrl", "collectionId", "metadata2", \
            "rapiOrderUrl", "geometry", "title", "orderExecuteUrl", \
            "thumbnailUrl", "metadataUrl", "isGeorectified", \
            "collectionTitle", "isOrderable", "thisRecordUrl", \
            "metadata"]

class QueryError:
    """
    The QueryError class is used to store error information for a query.
    """
    
    def __init__(self, msgs):
        """
        Initializer for QueryError object which stores an error message.
        
        :param msgs: The error message to print.
        :type msgs: str
        """
        
        self.msgs = msgs
        
    def _get_msgs(self, as_str=False):
        """
        Gets the messages stored with the QueryError.
        
        :param as_str: Determines whether to return a string or a list of messages.
        :type  as_str: boolean
        
        :return: Either a string or a list of messages.
        :rtype: str or list
        """
        
        if isinstance(self.msgs, list):
            if as_str:
                return ' '.join(self.msgs)
        
        return self.msgs
        
    def _set_msgs(self, msgs):
        """
        Sets the messages stored with the QueryError.
        
        :param msgs: Can either be a string or a list of messages.
        :type  msgs: str or list
        
        """
        self.msgs = msgs

class EODMSRAPI():
    
    def __init__(self, username, password):
        """
        Initializer for EODMSRAPI.
        
        :param username: The username of an EODMS account.
        :type  username: str
        :param password: The password of an EODMS account.
        :type  password: str
        """
    
        # print("\nInitializing EODMSRAPI, please wait...")
        
        # Create session
        self._session = requests.Session()
        self._session.auth = (username, password)
        
        self.rapi_root = "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi"
        
        self.rapi_collections = {}
        self.unsupport_collections = {}
        self.download_size = 0
        self.size_limit = None
        self.results = []
        self.res_mdata = None
        #self.default_queryLimit = 1000
        self.limit_interval = 1000
        self.name_conv = 'camel'
        self.res_format = 'raw'
        self.stdout_enabled = True
        self.timeout_query = 120.0
        self.timeout_order = 180.0
        self.attempts = 4
        self.indent = 3
        self.aoi = None
        self.dates = None
        self.feats = None
        self.start = datetime.datetime.now()
        
        self.geo = EODMSGeo(self)
        
        self._map_fields()
        
        self._header = '| EODMSRAPI | '
        
        self.failed_status = ['CANCELLED', 'FAILED', 'EXPIRED', \
                            'DELIVERED', 'MEDIA_ORDER_SUBMITTED', \
                            'AWAITING_PAYMENT']
        
        return None
        
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
        
    def _check_auth(self, in_err):
        """
        Checks if the error results from the RAPI are unauthorized.
        
        :param in_err: The QueryError containing the error from the RAPI.
        :type  in_err: QueryError
        
        :return: True if unauthorized, False if not.
        :rtype: boolean
        """
        
        err_msg = in_err._get_msgs(True)
        if err_msg.find('401 - Unauthorized') > -1 or \
            (err_msg.find('HTTP Error: 401 Client Error') > -1 and \
            err_msg.find('Unauthorized') > -1):
            # Inform the user if the error was caused by an authentication 
            #   issue.
            err_msg = "An authentication error has occurred while " \
                        "trying to access the EODMS RAPI. Please try " \
                        "again with your EODMS username and password."
            self._log_msg(err_msg, 'error')
            return True
            
        return False
        
    def _convert_date(self, date, in_forms=['%Y-%m-%d %H:%M:%S.%f'], 
                out='string', out_form="%Y%m%d_%H%M%S"):
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
                    msg = "%s. Date will not be included in query." % \
                        str(e).capitalize()
                    self._log_msg(msg, 'warning')
                    pass
                except:
                    msg = traceback.format_exc()
                    self._log_msg(msg, 'warning')
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
        
        fields = self.get_availableFields(collection, 'all')[field_type]
        
        for k, v in fields.items():
            if field == k:
                return v['id']
            elif field == v['id']:
                return k
        
    def _get_conv(self, field):
        """
        Converts a field name into the set naming convention (self.name_conv).
        
        :param field: The field name.
        :type  field: str
        
        :return: The field name with the proper naming convention 
                ('words', 'upper' or 'camel').
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
                words = re.findall('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=' \
                        '[A-Z])(?=[A-Z][a-z])|$)', field)
                words = [w[0].upper() + w[1:] for w in words]
            
            if self.name_conv == 'words':
                return ' '.join(words)
            elif self.name_conv == 'upper':
                return '_'.join([w.upper() for w in words])
        else:
            return self._to_camelCase(field)
            
    def _download_image(self, url, dest_fn, fsize):
        """
        Given a list of remote and local items, download the remote data 
            if it is not already found locally.
            
        (Adapted from the eodms-api-client (https://pypi.org/project/eodms-api-client/) developed by Mike Brady)
        
        :param url: The download URL of the image.
        :type  url: str
        :param dest_fn: The local destination filename for the download.
        :type  dest_fn: str
        :param fsize: The total filesize of the image.
        :type  fsize: int
        """
        
        # If we have an existing local file, check the filesize against the manifest
        if os.path.exists(dest_fn):
            # if all-good, continue to next file
            if os.stat(dest_fn).st_size == fsize:
                msg = "No download necessary. " \
                    "Local file already exists: %s" % dest_fn
                self._log_msg(msg)
                return None
            # Otherwise, delete the incomplete/malformed local file and redownload
            else:
                msg = 'Filesize mismatch with %s. Re-downloading...' % \
                    os.path.basename(dest_fn)
                self._log_msg(msg, 'warning')
                os.remove(dest_fn)
                
        # Use streamed download so we can wrap nicely with tqdm
        with self._session.get(url, stream=True) as stream:
            with open(dest_fn, 'wb') as pipe:
                with tqdm.wrapattr(
                    pipe,
                    method='write',
                    miniters=1,
                    total=fsize,
                    desc="%s%s" % (self._header, os.path.basename(dest_fn))
                ) as file_out:
                    for chunk in stream.iter_content(chunk_size=1024):
                        file_out.write(chunk)
                        
        msg = '%s has been downloaded.' % dest_fn
        self._log_msg(msg)
            
    def _fetch_metadata(self, max_workers=4, len_timeout=20.0):
        """
        Fetches all metadata for a given record
        
        (Adapted from: eodms-api-client (https://pypi.org/project/eodms-api-client/)
            developed by Mike Brady)
            
        :param max_workers: The number of threads used for retrieving the metadata.
        :type  max_workers: int
        :param len_timeout: The length of time in seconds before the thread returns
                            a timeout warning.
        :type  len_timeout: float
        
        :return: A list containing the metadata for all items in the self.results        
        :rtype:  list
        """
        
        metadata_fields = self._get_metaKeys()
        
        if isinstance(metadata_fields, QueryError):
            msg = "Could not generate metadata for the results."
            # print("\n%sWARNING: %s" % (self._header, msg))
            self._log_msg(msg, 'warning')
            return None
        
        n_urls = len(self.results)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            res = list(
                tqdm(
                    executor.map(
                        self._fetch_single_record_metadata,
                        self.results,
                        [metadata_fields] * n_urls,
                        [len_timeout] * n_urls, 
                    ),
                    desc='%sFetching result metadata' % self._header,
                    total=n_urls,
                    miniters=1,
                    unit='item'
                )
            )
        
        return res
        
    def _fetch_single_record_metadata(self, record, keys, timeout):
        """
        Fetches a single image's metadata.
        
        (Adapted from: eodms-api-client (https://pypi.org/project/eodms-api-client/)
            developed by Mike Brady)
        
        :param record: A dictionary of an image record.
        :type  record: dict
        :param keys: A list of metadata keys.
        :type  keys: list
        :param timeout: The time in seconds to wait before timing out.
        :type  timeout: float
            
        :return: Dictionary containing the keys and geometry metadata for 
                    the given image.
        :rtype: dict
        """
        
        metadata = {}
        r = self._submit(record['thisRecordUrl'], timeout, as_json=False)
        
        if r is None: return None
        
        if isinstance(r, QueryError):
            err_msg = "Could not retrieve full metadata due to: %s" % \
                    r._get_msgs(True)
            self._log_msg(err_msg, 'warning')
            record['issue'] = err_msg
            image_res = record
        elif r.ok:
            image_res = r.json()
        else:
            err_msg = "Could not retrieve metadata."
            self._log_msg(err_msg, 'warning')
            image_res = record
        
        # Add all record info
        record_info = {}
        
        # Add metadata at start
        metadata[self._get_conv('recordId')] = \
            image_res['recordId']
        metadata[self._get_conv('collectionId')] = \
            image_res['collectionId']
        metadata[self._get_conv('geometry')] = \
            image_res['geometry']
        
        exclude = [self._get_conv('recordId'), \
                    self._get_conv('collectionId'), \
                    self._get_conv('geometry'), \
                    self._get_conv('metadata2'), \
                    self._get_conv('metadata')]
                    
        for k in image_res.keys():
            if self._get_conv(k) not in exclude:
                metadata[self._get_conv(k)] = image_res[k]
        
        # Add remaining metadata
        for k in keys:
            mdata_key = res_key = k
            if isinstance(k, list):
                mdata_key = k[0]
                res_key = k[1]
            
            mdata_key = self._get_conv(mdata_key)
            
            if mdata_key in exclude: continue
            
            if res_key in image_res.keys():
                metadata[mdata_key] = image_res[res_key]
            else:
                vals = [f[1] for f in image_res['metadata'] \
                        if f[0] == res_key]
                if len(vals) > 0:
                    metadata[mdata_key] = vals[0]
        
        if self.res_format == 'full':
            wkt_field = self._get_conv('WKT Geometry')
            metadata[wkt_field] = self.geo.convert_imageGeom(\
                                image_res['geometry'], 'wkt')
            
        return metadata
        
    def _get_dateRange(self, items):
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
            
            if 'dateRapiOrdered' in i.keys():
                rapi_str = i['dateRapiOrdered']
            else:
                rapi_str = i['dateSubmitted']
                
            rapi_date = dateutil.parser.parse(rapi_str)
                
            # Convert UTC to Eastern
            rapi_date = rapi_date.astimezone(eastern)
            
            dates.append(rapi_date)
        
        dates.sort()
        
        start = dates[0]
        start = start - datetime.timedelta(hours=0, minutes=1)
        
        end = dates[len(dates) - 1]
        end = end + datetime.timedelta(hours=0, minutes=1)
        
        return (start, end)
        
    def _get_metaKeys(self):
        """
        Gets a list of metadata (fields) keys for a given collection
        
        :return: A list of metadata keys
        :rtype:  list
        """
        
        if not self.rapi_collections:
            self.get_collections()
            
        if self.rapi_collections is None: return None
            
        fields = self.rapi_collections[self.collection]['fields']\
                    ['results'].keys()
        sorted_lst = sorted(fields)
        
        return sorted_lst
        
    def _get_exception(self, res, output='str'):
        """
        Gets the Exception text (or XML) from an request result.
        
        :param in_xml: The XML which will be checked for an exception.
        :type  in_xml: xml.etree.ElementTree.Element
        :param output: Determines what type of output should be returned 
                        (default='str').
                       Options:
                       - 'str': returns the XML Exception as a string
                       - 'tree': returns the XML Exception as a 
                                    xml.etree.ElementTree.Element
        :type  output: str
        
        :return:       The Exception XML text or element depending on 
                        the output variable.
        :rtype:        str or xml.etree.ElementTree.Element
        """
        
        in_str = res.text

        # If the input XML is None, return None
        if in_str is None: return None
        
        if self._is_json(in_str): return None
        
        # If the input is a string, convert it to a xml.etree.ElementTree.Element
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
        
    def _get_fieldId(self, name, collection=None, field_type='search'):
        """
        Gets the field ID for a given field name.
        
        :param name: The field name.
        :type  name: str
        :param collection: The collection ID.
        :type  collection: str
        :param field_type: The field type, either 'search' or 'result'.
        :type  field_type: str
        
        :return: The proper field ID for the given name.
        :rtype: str
        """
        
        if collection is None: collection = self.collection
        
        field_id = None
        if field_type == 'search':
            fields = self.get_availableFields(name_type='all')[field_type]
            
            if not name in fields.keys():
                # Check field in field_map
                coll_fields = self.field_map[self.collection]
                ui_fields = [f['uiField'] for f in coll_fields]
                # print("coll_fields: %s" % coll_fields)
                # print([f['uiField'] for f in coll_fields])
                
                for f in coll_fields:
                    if f['uiField'].find(name) > -1 or \
                        f['uiField'].upper().replace(' ', '_')\
                            .find(name) > -1 or \
                        f['fieldId'].find(name) > -1:
                        field_id = f['fieldId']
                        break
            else:
                # Check in available fields
                for k, v in fields.items():
                    if name == k:
                        field_id = v['id']
            
            # If field_id is still None, check to make sure the
            #   name entry is an ID
            if field_id is None:
                if name in [f['id'] for f in fields.values()]:
                    return name
            
            return field_id
            
        elif field_type == 'results':
            fields = self.get_availableFields(name_type='all')[field_type]
            
            # Check if results fields
            for k, v in fields.items():
                if name == k:
                    field_id = v['id']
            
            # If field_id is still None, check to make sure the
            #   name entry is an ID
            if field_id is None:
                if name in [f['id'] for f in fields.values()]:
                    return name
                    
            return field_id
        
    def _get_fieldType(self, coll_id, field_id):
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
            
        if self.rapi_collections is None: return None
        
        for k, v in self.rapi_collections[coll_id]['fields']['search'].items():
            if v['id'] == field_id:
                return v['datatype']
                
    def _get_itemFromOrders(self, item_id, orders):
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
                
    def _is_json(self, my_json):
        """
        Checks to see in the input item is in JSON format.
        
        :param my_json: A string value from the requests results.
        :type  my_json: str
        
        :return: True if a valid JSON format, False if not.
        :rtype: boolean
        """
        
        try:
            json_object = json.loads(my_json)
        except (ValueError, TypeError) as e:
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
            or_query = '%s' % ' OR '.join(["%s%s'%s'" % \
                        (field_id, op, v) for v in values])
        else:
            or_query = '%s' % ' OR '.join(["%s%s%s" % \
                        (field_id, op, v) for v in values])
                        
        return or_query
        
    def _log_msg(self, messages, msg_type='info', log_indent='', 
                out_indent=''):
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
            print("EODMSRAPI._log_msg: 'messages' parameter not valid.")
            return None
        
        # Log the message
        log_msg = "%s%s" % (log_indent, log_msg)
        log_msg = log_msg.replace('\n', '\\n')
        log_msg = log_msg.replace('\t', '\\t')
        log_msg = log_msg.replace("'", "\\'")
        eval_str = "logger.%s('%s')" % (msg_type, log_msg)
        eval("logger.%s('%s')" % (msg_type, log_msg))
        
        # If stdout is disabled, don't print message to terminal
        if not self.stdout_enabled: return None
        
        # Print message to terminal
        if msg_type == 'info':
            msg = "%s%s%s" % (out_indent, self._header, out_msg)
        else:
            msg = "%s%s %s: %s" % (out_indent, self._header, \
                msg_type.upper(), out_msg)
                
        print(msg)
    
    def _map_fields(self):
        """
        Sets the mapping of the fields to the labels used on the EODMS UI.
        """
        
        self.field_map = {'COSMO-SkyMed1': 
                [{'collectionId': 'COSMO-SkyMed1', 
                    'fieldId': 'csmed.ORBIT_ABS', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Absolute Orbit'}, 
                 {'collectionId': 'COSMO-SkyMed1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing', 
                    'rapiField': 'Spatial Resolution'}], 
            'DMC': 
                [{'collectionId': 'DMC', 
                    'fieldId': 'DMC.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover (Not all ' \
                            'vendors supply cloud cover data)', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'DMC', 
                    'fieldId': 'Spatial Resolution', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'DMC', 
                    'fieldId': 'DMC.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'Gaofen-1': 
                [{'collectionId': 'Gaofen-1', 
                    'fieldId': 'SATOPT.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'Gaofen-1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Gaofen-1', 
                    'fieldId': 'SATOPT.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'GeoEye-1': 
                [{'collectionId': 'GeoEye-1', 
                    'fieldId': 'GE1.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'GeoEye-1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'GeoEye-1', 
                    'fieldId': 'GE1.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'GeoEye-1', 
                    'fieldId': 'GE1.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'IKONOS': 
                [{'collectionId': 'IKONOS', 
                    'fieldId': 'IKONOS.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'IKONOS', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'IKONOS', 
                    'fieldId': 'IKONOS.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'IKONOS', 
                    'fieldId': 'IKONOS.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'IRS': 
                [{'collectionId': 'IRS', 
                    'fieldId': 'IRS.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'IRS', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'IRS', 
                    'fieldId': 'IRS.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'IRS', 
                    'fieldId': 'IRS.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'PlanetScope': 
                [{'collectionId': 'PlanetScope', 
                    'fieldId': 'SATOPT.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'PlanetScope', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'PlanetScope', 
                    'fieldId': 'SATOPT.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'QuickBird-2': 
                [{'collectionId': 'QuickBird-2', 
                    'fieldId': 'QB2.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'QuickBird-2', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'QuickBird-2', 
                    'fieldId': 'QB2.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'QuickBird-2', 
                    'fieldId': 'QB2.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'Radarsat1': [{'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.ORBIT_ABS', 
                    'uiField': 'Orbit', 
                    'rapiField': 'Absolute Orbit'}], 
            'Radarsat1RawProducts': [{'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.DATASET_ID', 
                    'uiField': 'Dataset Id', 
                    'rapiField': 'Dataset Id'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'ARCHIVE_CUF.ARCHIVE_FACILITY', 
                    'uiField': 'Archive Facility', 
                    'rapiField': 'Reception Facility'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'ARCHIVE_CUF.RECEPTION_FACILITY', 
                    'uiField': 'Reception Facility', 
                    'rapiField': 'Reception Facility'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.ORBIT_ABS', 
                    'uiField': 'Orbit', 
                    'rapiField': 'Absolute Orbit'}], 
            'Radarsat2': [{'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'CATALOG_IMAGE.SEQUENCE_ID', 
                    'uiField': 'Sequence Id', 
                    'rapiField': 'Sequence Id'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.ANTENNA_ORIENTATION', 
                    'uiField': 'Look Direction', 
                    'rapiField': 'Look Direction'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.TR_POL', 
                    'uiField': 'Transmit Polarization', 
                    'rapiField': 'Transmit Polarization'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.REC_POL', 
                    'uiField': 'Receive Polarization', 
                    'rapiField': 'Receive Polarization'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.IMAGE_ID', 
                    'uiField': 'Image Identification', 
                    'rapiField': 'Image Id'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.ORBIT_REL', 
                    'uiField': 'Relative Orbit', 
                    'rapiField': 'Relative Orbit'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'ARCHIVE_IMAGE.ORDER_KEY', 
                    'uiField': 'Order Key', 
                    'rapiField': 'Order Key'}], 
            'Radarsat2RawProducts': [{'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.ANTENNA_ORIENTATION', 
                    'uiField': 'Look Orientation', 
                    'rapiField': 'Look Orientation'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.TR_POL', 
                    'uiField': 'Transmit Polarization', 
                    'rapiField': 'Transmit Polarization'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.REC_POL', 
                    'uiField': 'Receive Polarization', 
                    'rapiField': 'Receive Polarization'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.IMAGE_ID', 
                    'uiField': 'Image Identification', 
                    'rapiField': 'Image Id'}], 
            'RapidEye': [{'collectionId': 'RapidEye', 
                    'fieldId': 'RE.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'RapidEye', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'RapidEye', 
                    'fieldId': 'RE.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'RapidEye', 
                    'fieldId': 'RE.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'RCMImageProducts': [{'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Beam Mnemonic'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'SENSOR_BEAM_CONFIG.BEAM_MODE_QUALIFIER', 
                    'uiField': 'Beam Mode Qualifier', 
                    'rapiField': 'Beam Mode Qualifier'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.SBEAM', 
                    'uiField': 'Beam Mode Type', 
                    'rapiField': 'Beam Mode Type'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.DOWNLINK_SEGMENT_ID', 
                    'uiField': 'Downlink segment ID', 
                    'rapiField': 'Downlink segment ID'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'LUTApplied', 
                    'uiField': 'LUT Applied', 
                    'rapiField': 'LUT Applied'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'CATALOG_IMAGE.OPEN_DATA', 
                    'uiField': 'Open Data', 
                    'rapiField': 'Open Data'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.POLARIZATION', 
                    'uiField': 'Polarization', 
                    'rapiField': 'Polarization'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'PRODUCT_FORMAT.FORMAT_NAME_E', 
                    'uiField': 'Product Format', 
                    'rapiField': 'Product Format'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'ARCHIVE_IMAGE.PRODUCT_TYPE', 
                    'uiField': 'Product Type', 
                    'rapiField': 'Product Type'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.ORBIT_REL', 
                    'uiField': 'Relative Orbit', 
                    'rapiField': 'Relative Orbit'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.WITHIN_ORBIT_TUBE', 
                    'uiField': 'Within Orbital Tube', 
                    'rapiField': 'Within Orbital Tube'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'ARCHIVE_IMAGE.ORDER_KEY', 
                    'uiField': 'Order Key', 
                    'rapiField': 'Order Key'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'CATALOG_IMAGE.SEQUENCE_ID', 
                    'uiField': 'Sequence Id', 
                    'rapiField': 'Sequence Id'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.SPECIAL_HANDLING_REQUIRED', 
                    'uiField': 'Special Handling Required', 
                    'rapiField': 'Special Handling Required'}], 
            'RCMScienceData': [{'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Beam Mode Type'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Beam Mnemonic'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'CUF_RCM.TR_POL', 
                    'uiField': 'Transmit Polarization', 
                    'rapiField': 'Transmit Polarization'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'CUF_RCM.REC_POL', 
                    'uiField': 'Receive Polarization', 
                    'rapiField': 'Receive Polarization'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.DOWNLINK_SEGMENT_ID', 
                    'uiField': 'Downlink Segment ID', 
                    'rapiField': 'Downlink Segment ID'}], 
            'SPOT': [{'collectionId': 'SPOT', 
                    'fieldId': 'SPOT.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover (Not all vendors supply cloud cover data)', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'SPOT', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'SPOT', 
                    'fieldId': 'SPOT.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'TerraSarX': [{'collectionId': 'TerraSarX', 
                    'fieldId': 'TSX1.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'TerraSarX', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'TerraSarX', 
                    'fieldId': 'INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}], 
            'VASP': [{'collectionId': 'VASP', 
                    'fieldId': 'CATALOG_SERIES.CEOID', 
                    'uiField': 'Value-added Satellite Product Options', 
                    'rapiField': 'Sequence Id'}], 
            'WorldView-1': [{'collectionId': 'WorldView-1', 
                    'fieldId': 'WV1.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'WorldView-1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'WorldView-1', 
                    'fieldId': 'WV1.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'WorldView-1', 
                    'fieldId': 'WV1.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'WorldView-2': [{'collectionId': 'WorldView-2', 
                    'fieldId': 'WV2.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'WorldView-2', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'WorldView-2', 
                    'fieldId': 'WV2.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'WorldView-2', 
                    'fieldId': 'WV2.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'WorldView-3': [{'collectionId': 'WorldView-3', 
                    'fieldId': 'WV3.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'WorldView-3', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId', 'WorldView-3', 
                    'fieldId', 'WV3.SENS_INC', 
                    'uiField', 'Incidence Angle (Decimal Degrees)', 
                    'rapiField', 'Sensor Incidence Angle'}, 
                 {'collectionId', 'WorldView-3', 
                    'fieldId', 'WV3.SBEAM', 
                    'uiField', 'Sensor Mode', 
                    'rapiField', 'Sensor Mode'}]}
        
                
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
        
        return '(%s>=%s AND %s<=%s)' % (field, start, field, end)
        
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
            
        if self.rapi_collections is None: return None
        
        # Build the query for the date range
        if dates is not None and not str(dates).strip() == '':
            self.dates = dates
        
        if self.dates is not None:
            
            field_id = self._get_fieldId('Acquisition Start Date')
            
            if field_id is None:
                field_id = self._get_fieldId('Start Date')
            
            date_queries = []
            for rng in self.dates:
                if 'start' not in rng.keys():
                    break
                
                start = self._convert_date(rng.get('start'), \
                                "%Y%m%d_%H%M%S", \
                                out_form="%Y-%m-%dT%H:%M:%SZ")
                end = self._convert_date(rng.get('end'), "%Y%m%d_%H%M%S", \
                                out_form="%Y-%m-%dT%H:%M:%SZ")
                                
                if start is None or end is None:
                    continue
                
                date_queries.append("%s>='%s' AND %s<='%s'" % \
                    (field_id, start, field_id, end))
            
            if len(date_queries) > 0:
                query_lst.append("(%s)" % ' OR '.join(date_queries))
        
        # Build the query for the geometry features
        if feats is None: feats = self.feats
        
        if feats is not None:
            
            geom_lst = []
            
            for idx, f in enumerate(feats):
                op = f[0].upper()
                src = f[1]
                
                self.geoms = self.geo.add_geom(src)
                
                if self.geoms is None or isinstance(self.geoms, SyntaxError):
                    msg = "Geometry feature #%s could not be determined. " \
                            "Excluding it from search." % str(idx + 1)
                    self._log_msg(msg, 'warning')
                else:
                    field_id = self._get_fieldId('Footprint')

                    self.geoms = [self.geoms] \
                        if not isinstance(self.geoms, list) else self.geoms
                    
                    for g in self.geoms:
                        geom_lst.append('%s %s %s' % (field_id, op, g))
            
            if len(geom_lst) > 0:
                query_lst.append("(%s)" % ' OR '.join(geom_lst))
        
        # Build the query containing the filters
        if filters is not None:
            for field, values in filters.items():
                    
                field_id = self._get_fieldId(field)
                
                if field_id is None:
                    msg = "No available field named '%s'." % field
                    self._log_msg(msg, 'warning')
                    continue
                    
                d_type = self._get_fieldType(self.collection, field_id)
                
                op = values[0]
                val = values[1]
                
                if not any(c in op for c in '=><'):
                    op = ' %s ' % op
                
                if field == 'Incidence Angle' or field == 'Scale' or \
                    field == 'Spacial Resolution' or field == 'Absolute Orbit':
                    if isinstance(val, list) or isinstance(val, tuple):
                        for v in val:
                            if v.find('-') > -1:
                                start, end = v.split('-')
                                val_query = self._parse_range(field_id, start, end)
                            else:
                                val_query = "%s%s%s" % (field_id, op, v)
                            query_lst.append(val_query)
                        continue
                    else:
                        if str(val).find('-') > -1:
                            start, end = str(val).split('-')
                            val_query = self._parse_range(field_id, start, end)
                        else:
                            val_query = "%s%s%s" % (field_id, op, val)
                else:
                    if isinstance(val, list) or isinstance(val, tuple):
                        val_query = self._build_or(field_id, op, val, d_type)
                    else:
                        if d_type == 'String':
                            val_query = "%s%s'%s'" % (field_id, op, val)
                        else:
                            val_query = "%s%s%s" % (field_id, op, val)
                
                query_lst.append(val_query)
        
        if len(query_lst) > 1:
            query_lst = ['(%s)' % q if q.find(' OR ') > -1 else q \
                        for q in query_lst]
            
        full_query = ' AND '.join(query_lst)
        
        return full_query
            
    def _submit_search(self):
        """
        Submit a search query to the desired EODMS collection

        Since there may be instances where the default maxResults is greater 
        than 150, this method should recursively call itself until the 
        correct number of results is retrieved.
        
        (Adapted from: eodms-api-client (https://pypi.org/project/eodms-api-client/)
            developed by Mike Brady)
        
        :return: The search-query response JSON from the EODMS REST API.
        :rtype:  json
        """
        
        if self.max_results is not None:
            if len(self.results) >= self.max_results:
                self.results = self.results[:self.max_results]
                return self.results
        
        # Print status of search
        start = len(self.results) + 1
        end = len(self.results) + self.limit_interval
        
        msg = "Querying records within %s to %s..." % (start, end)
        self._log_msg(msg)
        
        logger.debug("RAPI Query URL: %s" % self._search_url)
        r = self._submit(self._search_url, as_json=False)
        
        if r is None: return None
        
        if isinstance(r, QueryError):
            msg = 'Retrying in 3 seconds...'
            self._log_msg(msg, 'warning')
            time.sleep(3)
            return self._submit_search()
            
        if r.ok:
            data = r.json()
                
            
            tot_results = int(data['totalResults'])
            if tot_results == 0:
                return self.results
            elif tot_results < self.limit_interval:
                self.results += data['results']
                return self.results
            
            self.results += data['results']
            first_result = len(self.results) + 1
            if self._search_url.find('&firstResult') > -1:
                old_firstResult = int(re.search(
                                        r'&firstResult=([\d*]+)', \
                                        self._search_url
                                    ).group(1))
                self._search_url = self._search_url.replace(
                                    '&firstResult=%d' % old_firstResult, 
                                    '&firstResult=%d' % first_result
                                   )
            else:
                self._search_url += '&firstResult=%s' % first_result
            return self._submit_search()
            
    def _submit(self, query_url, timeout=None, 
                record_name=None, quiet=True, as_json=True):
        """
        Send a query to the RAPI.
        
        :param query_url: The query URL.
        :type  query_url: str
        :param timeout: The length of the timeout in seconds.
        :type  timeout: float
        :param record_name: A string used to supply information for the record 
                            in a print statement.
        :type  record_name: str
        
        :return: The response returned from the RAPI.
        :rtype: request.Response
        """
        
        if timeout is None:
            timeout = self.timeout_query
        
        verify = True
        
        logger.debug("RAPI Query URL: %s" % query_url)
        
        res = None
        attempt = 1
        err = None
        # Get the entry records from the RAPI using the downlink segment ID
        while res is None and attempt <= self.attempts:
            # Continue to attempt if timeout occurs
            try:
                if record_name is None:
                    msg = "Sending request to the RAPI (attempt %s)..." \
                            % attempt
                    if not quiet and attempt > 1:
                        logger.debug("\n%s%s" % (self._header, msg))
                else:
                    msg = "Sending request to the RAPI for '%s' " \
                                "(attempt %s)..." % (record_name, attempt)
                    if not quiet and attempt > 1:
                        logger.debug("\n%s%s" % (self._header, msg))
                if self._session is None:
                    res = requests.get(query_url, timeout=timeout, verify=verify)
                else:
                    res = self._session.get(query_url, timeout=timeout, verify=verify)
                res.raise_for_status()
            except requests.exceptions.HTTPError as errh:
                msg = "HTTP Error: %s" % errh
                
                if msg.find('Unauthorized') > -1 or \
                    msg.find('404 Client Error: Not Found for url') > -1:
                    err = msg
                    attempt = self.attempts
                
                if attempt < self.attempts:
                    msg = "%s; attempting to connect again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
            except (requests.exceptions.Timeout, 
                    requests.exceptions.ReadTimeout) as errt:
                msg = "Timeout Error: %s" % errt
                if attempt < self.attempts:
                    msg = "%s; increasing timeout by a minute and trying " \
                            "again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                    timeout += 60.0
                    self.timeout_query = timeout
                else:
                    err = msg
                attempt += 1
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.RequestException) as req_err:
                msg = "%s Error: %s" % (req_err.__class__.__name__, req_err)
                self._log_msg(msg, 'error')
                attempt = self.attempts
                return None
            except KeyboardInterrupt as key_err:
                msg = "Process ended by user."
                err = msg
                attempt = self.attempts
                self._log_msg(msg, out_indent='\n')
                return None
            except:
                msg = "Unexpected error: %s" % traceback.format_exc()
                if attempt < self.attempts:
                    msg = "%s; attempting to connect again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
                
        if err is not None:
            query_err = QueryError(err)
            
            if self._check_auth(query_err): return None
            
            return query_err
                
        # If no results from RAPI, return None
        if res is None: return None
        
        # Check for exceptions that weren't already caught
        except_err = self._get_exception(res)
        
        if isinstance(except_err, QueryError):
            if self._check_auth(except_err): return None
                
            self._log_msg(msg, 'warning')
            return except_err
        
        if as_json:
            return res.json()
        else:
            return res
            
    def _to_camelCase(self, in_str):
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
        
        return '%s%s' % (first_word, other_words)
        
    def _update_conv(self):
        """
        Updates all fields in the set of results to the proper naming 
            convention.
        """
        
        if self.res_mdata is not None:
            for m in self.res_mdata:
                for k, v in m.items():
                    new_k = self._get_conv(k)
                    m[new_k] = m.pop(k)
            
    def _get_fullCollId(self, coll, unsupported=False):
        """
        Gets the full collection ID using the input collection ID which can be a 
            substring of the collection ID.
        
        :param coll_id: The collection ID to check.
        :type  coll_id: str
        :param unsupported: Determines whether to check in the supported or 
                                unsupported collection lists.
        :type  unsupported: boolean
        
        :return: The full collection ID.
        :rtype: str
        """
                
        if not self.rapi_collections:
            self.get_collections()
            
        if self.rapi_collections is None: return None
                
        for k, v in self.rapi_collections.items():
            if coll.lower() == k.lower():
                return k
            elif coll.lower() in v['aliases']:
                return k
        
    def set_queryTimeout(self, timeout):
        """
        Sets the timeout limit for a query to the RAPI.
        
        :param timeout: The value of the timeout in seconds.
        :type  timeout: float
        
        """
        self.timeout_query = float(timeout)
        
    def set_orderTimeout(self, timeout):
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
        
    def set_fieldConvention(self, convention):
        """
        Sets the naming convention of the output fields.
        
        :param convention: The type of naming convention for the fields.
            
            - ``words``: The label with spaces and words will be returned.
            - ``camel`` (default): The format will be lower camel case like 'camelCase'.
            - ``upper``: The format will be all uppercase with underscore for spaces.
            
        :type  convention: str

        """
        
        self.name_conv = convention
        
        self._update_conv()
        
    def download(self, items, dest, wait=10.0):
        """
        Downloads a list of order items from the EODMS RAPI.
        
        :param items: A list of order items returned from the RAPI.
            
            Example:
                
                ``{'items': [{'recordId': '8023427', 'status': 'SUBMITTED', 'collectionId': 'RCMImageProducts', 'itemId': '346204', 'orderId': '50975'}, ...]}``
            or
                ``[{'recordId': '8023427', 'status': 'SUBMITTED', 'collectionId': 'RCMImageProducts', 'itemId': '346204', 'orderId': '50975'}, ...]``
                
        :type  items: list or dict
        :param dest: The local download folder location.
        :type  dest: str
        :param wait: Sets the time to wait before checking the status of all orders.
        :type  wait: float or int
        
        :return: A list of the download (completed) items.
        :rtype: list
        """
        
        msg = "Downloading images..."
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        if items is None:
            msg = "No images to download."
            self._log_msg(msg)
            return []
            
        if isinstance(items, dict):
            if 'items' in items.keys():
                items = items['items']
                
        if len(items) == 0:
            msg = "No images to download."
            self._log_msg(msg)
            return []
            
        complete_items = []
        while len(items) > len(complete_items):
            time.sleep(wait)
            
            start, end = self._get_dateRange(items)
            
            orders = self.get_orders(dtstart=start, dtend=end)
            
            if len(orders) == 0:
                msg = "No orders could be found."
                self._log_msg(msg)
                return []
            
            new_count = len(complete_items)
            
            for itm in items:
                item_id = itm['itemId']
                cur_item = self._get_itemFromOrders(item_id, orders)
                status = cur_item['status']
                record_id = cur_item['recordId']
                
                # Check record is already complete
                if self._check_complete(complete_items, record_id):
                    continue
                
                if status in self.failed_status:
                    if status == 'FAILED':
                        # If the order has failed, inform user
                        status_mess = cur_item.get('statusMessage')
                        msg = "\n  The following Order Item has failed:"
                        if status_mess is None:
                            msg += "\n    Order Item Id: %s\n" \
                                    "    Record Id: %s" % \
                                    "    Collection: %s\n" \
                                    (cur_item['itemId'], \
                                    cur_item['recordId'], \
                                    cur_item['collectionId'])
                        else:
                            msg += "\n    Order Item Id: %s\n" \
                                    "    Record Id: %s\n" \
                                    "    Collection: %s\n" \
                                    "    Reason for Failure: %s" % \
                                    (cur_item['itemId'], cur_item['recordId'], \
                                    cur_item['collectionId'], \
                                    cur_item['statusMessage'])
                    else:
                        # If the order was unsuccessful with another status, 
                        #   inform user
                        msg = "\n  The following Order Item has status " \
                                "'%s' and will not be downloaded:" % status
                        msg += "\n    Order Item Id: %s\n" \
                                "    Record Id: %s\n" \
                                "    Collection: %s\n" % \
                                (cur_item['itemId'], \
                                cur_item['recordId'], \
                                cur_item['collectionId'])
                    
                    self._log_msg(msg)
                    
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
                        
                        # Parse the HTML text of the destination string
                        root = ElementTree.fromstring(str_val)
                        url = root.text
                        fn = os.path.basename(url)
                        
                        # Download the image
                        msg = "Downloading image with " \
                                "Record Id %s (%s)." % (record_id, \
                                os.path.basename(url))
                        self._log_msg(msg)
                        
                        # Save the image contents to the 'downloads' folder
                        out_fn = os.path.join(dest, fn)
                        full_path = os.path.realpath(out_fn)
                        
                        if not os.path.exists(dest):
                            os.mkdir(dest)
                        
                        self._download_image(url, out_fn, fsize)
                        print('')
                        
                        # Record the URL and downloaded file to a dictionary
                        dest_info = {}
                        dest_info['url'] = url
                        dest_info['local_destination'] = full_path
                        download_paths.append(dest_info)
                        
                    cur_item['downloadPaths'] = download_paths
                    
                    complete_items.append(cur_item)
            
            if new_count == 0 and len(complete_items) == 0:
                msg = "No items are ready for download yet."
                self._log_msg(msg)
            elif new_count == len(complete_items):
                msg = "No new items are ready for download yet."
                self._log_msg(msg)
        
        return complete_items
        
    def get_availableFields(self, collection=None, name_type='all'):
        """
        Gets a dictionary of available fields for a collection from the RAPI.
        
        :param collection: The Collection ID.
        :type  collection: str
        
        :return: A dictionary containing the available fields for the given 
                collection.
        :rtype:  dict
        """
        
        if collection is None:
            if self.collection is None:
                self._log_msg('No collection can be determined.', 'warning')
                return None
            collection = self.collection
        
        query_url = '%s/collections/%s' % (self.rapi_root, collection)
        
        coll_res = self._submit(query_url, timeout=20.0)
        
        if coll_res is None: return None
        
        # If an error occurred
        if isinstance(coll_res, QueryError):
            self._log_msg(coll_res._get_msgs(True), 'warning')
            return None
        
        # Get a list of the searchFields
        fields = {}
        if name_type == 'title' or name_type == 'id':
            
            srch_fields = []
            for r in coll_res['searchFields']:
                srch_fields.append(r[name_type])
        
            fields['search'] = srch_fields
        
            res_fields = []
            for r in coll_res['resultFields']:
                res_fields.append(r[name_type])
                
            fields['results'] = res_fields
                
        else:
            srch_fields = {}
            for r in coll_res['searchFields']:
                srch_fields[r['title']] = {'id': r['id'], \
                                    'datatype': r['datatype'], \
                                    'choices': r.get('choices')}
        
            fields['search'] = srch_fields
        
            res_fields = {}
            for r in coll_res['resultFields']:
                    res_fields[r['title']] = {'id': r['id'], \
                                    'datatype': r['datatype']}
            
            fields['results'] = res_fields
            
        return fields
        
    def get_fieldChoices(self, collection, field=None):
        """
        Gets the avaiable choices for a specified field. If no choices exist,
            then the data type is returned.
            
        :param collection: The collection containing the field.
        :type  collection: str
        :param field: The field name or field ID.
        :type  field: str
        
        :return: Either a list of choices or a string containing the 
                data type.
        :rtype: list or str
        """
        
        fields = self.get_availableFields(collection)
        
        all_fields = {}
        for f, v in fields['search'].items():
            choices = []
            if field is None:
                field_choices = v.get('choices')
                if field_choices is not None:
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
                        for c in field_choices:
                            value = c['value']
                            if not value == '':
                                choices.append(value)
                        return choices
                    else:
                        return 'Data type: %s' % v.get('datatype')
        
        return all_fields
        
    def get_collections(self, as_list=False, titles=False, redo=False):
        """
        Gets a list of available collections for the current user.
        
        :param as_list: Determines the type of return. If False, a dictionary
                        will be returned. If True, only a list of collection
                        IDs will be returned.
        :type  as_list: bool
        
        :return: Either a dictionary of collections or a list of collection IDs 
                depending on the value of as_list.
        :rtype:  dict
        """
        
        if self.rapi_collections and not redo:
            if as_list:
                if titles:
                    collections = [i['title'] for i in \
                                self.rapi_collections.values()]
                else:
                    collections = list(self.rapi_collections.keys())
                return collections
            return self.rapi_collections
        
        # Create the query to get available collections for the current user
        query_url = "%s/collections" % self.rapi_root
        
        msg = "Getting Collection information, please wait..."
        self._log_msg(msg)
        logger.debug("RAPI URL: %s" % query_url)
        
        # Send the query URL
        coll_res = self._submit(query_url, timeout=20.0)
        
        if coll_res is None: return None
        
        # If an error occurred
        if isinstance(coll_res, QueryError):
            msg = "Could not get a list of collections due to '%s'." % \
                coll_res._get_msgs(True)
            self._log_msg(msg, 'error')
            return None
        
        # Create the collections dictionary
        for coll in coll_res:
            for child in coll['children']:                
                for c in child['children']:
                    coll_id = c['collectionId']
                    # Add aliases for specific collections allowing easier access for users
                    aliases = []
                    if coll_id == 'RCMImageProducts':
                        aliases = ['rcm']
                    elif coll_id == 'Radarsat1':
                        aliases = ['r1', 'rs1', 'radarsat', 'radarsat-1']
                    elif coll_id == 'Radarsat2':
                        aliases = ['r2', 'rs2', 'radarsat-2']
                    elif coll_id == 'PlanetScope':
                        aliases = ['planet']
                    fields = self.get_availableFields(coll_id, 'all')
                    if fields is None: continue
                    self.rapi_collections[c['collectionId']] = {
                        'title': c['title'], 
                        'aliases': aliases, 
                        'fields': fields}
        
        # If as_list is True, convert dictionary to list of collection IDs
        if as_list:
            if titles:
                collections = [i['title'] for i in \
                            self.rapi_collections.values()]
            else:
                collections = list(self.rapi_collections.keys())
            return collections
        
        return self.rapi_collections
                
    def get_orderItem(self, itemId):
        """
        Submits a query to the EODMS RAPI to get a specific order item.
        
        :param itemId: The Order Item ID of the image to retrieve from the RAPI.
        :type  itemId: str or int
        
        :return: A dictionary containing the JSON format of the results from the RAPI. 
        :rtype:  dict
        """
        
        query = "%s/order?itemId=%s" % (self.rapi_root, itemId)
        log_msg = "Getting order item %s (RAPI query): %s" % (itemId, query)
        msg = "Getting order item %s..." % itemId
        
        messages = (log_msg, msg)
        self._log_msg(messages, log_indent='\n\n\t', out_indent='\n')
        
        res = self._submit(query, timeout=self.timeout_order)
        
        if res is None: return None
                
        return res
        
    def get_order(self, orderId):
        """
        Gets an specified order from the EODMS RAPI.
        
        :param orderId: The Order ID of the specific order.
        :type  orderId: str or int
        
        :return: A JSON dictionary of the specific order.
        :rtype:  dict
        """
        
        orders = self.get_orders()
        
        order = []
        for item in order:
            if item['orderId'] == orderId:
                order.append(item)
                
        return order
                
    def get_orders(self, dtstart=None, dtend=None, maxOrders=10000, 
                    outFormat='json'):
        """
        Sends a query to retrieve orders from the RAPI.
        
        :param dtstart: The start date for the date range of the query.
        :type  dtstart: datetime.datetime
        :param dtend: The end date for the date range of the query.
        :type  dtend: datetime.datetime
        :param maxOrders: The maximum number of orders to retrieve.
        :type  maxOrders: int
        :param outFormat: The format of the results.
        :type  outFormat: str
        
        :return: A JSON dictionary of the query results containing the orders.
        :rtype:  dict
        """
        
        msg = "Getting list of current orders..."
        self._log_msg(msg)
        
        tm_frm = '%Y-%m-%dT%H:%M:%SZ'
        params = {}
        if dtstart is not None:
            params['dtstart'] = dtstart.strftime(tm_frm)
            params['dtend'] = dtend.strftime(tm_frm)
        params['maxOrders'] = maxOrders
        param_str = urlencode(params)
        
        query_url = "%s/order?%s" % (self.rapi_root, param_str)
        
        logger.debug("RAPI URL:\n\n%s\n" % query_url)
        
        # Send the query to the RAPI
        res = self._submit(query_url, self.timeout_query, quiet=False)
        
        if res is None or isinstance(res, QueryError):
            if isinstance(res, QueryError):
                msg = "Order submission was unsuccessful due to: %s." % \
                        res._get_msgs(True)
            else:
                msg = "Order submission was unsuccessful."
            self._log_msg(msg, 'warning')
            return None
            
        if 'items' in res.keys():
            return res['items']
        else:
            return res
            
    def get_ordersByRecords(self, records):
        """
        Gets a list of orders from the RAPI based on a list of records.
        
        :param records: A list of records used to get the list of orders.
        :type  records: list
            
        :return: A list of results from the RAPI.
        :rtype:  list
        """
        
        if records is None or len(records) == 0:
            msg = "Cannot get orders as no image items provided."
            self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
            return None
        
        start, end = self._get_dateRange(records)
        
        orders = self.get_orders(dtstart=start, dtend=end)
        
        msg = "Getting a list of order items..."
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
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
            order_item = max([r for r in rec_orders \
                        if r['recordId'] == rec_id], \
                        key=lambda x:x['dateSubmitted'])
                        
            found_orders.append(order_item)
        
        msg = "Found %s order items for the following records: %s" % \
                (len(found_orders), ', '.join([r['recordId'] \
                for r in found_orders]))
        self._log_msg(msg)
                    
        if len(unfound) > 0:
            msg = "No order items found for the following " \
                    "records: %s" % ', '.join(unfound)
            self._log_msg(msg)
        
        return found_orders
        
    def get_orderParameters(self, collection, recordId):
        """
        Gets the list of available Order parameters for a given image record.
        
        :param collection: The Collection ID for the query.
        :type  collection: str
        :param recordId: The Record ID for the image.
        :type  recordId: int or str
            
        :return: A JSON dictionary of the order parameters.
        :rtype:  dict
        
        """
        
        # Get the proper Collection ID for the RAPI
        collection = self._get_fullCollId(collection)
        
        msg = "\n\n\tGetting order parameters for image in " \
                "Collection %s with Record ID %s..." % \
                (collection, recordId)
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # Set the RAPI URL
        query_url = "%s/order/params/%s/%s" % (self.rapi_root, \
                    collection, recordId)
        
        # Send the JSON request to the RAPI
        try:
            param_res = self._session.get(url=query_url)
            param_res.raise_for_status()
        except (requests.exceptions.HTTPError, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as req_err:
            msg = "%s Error: %s" % (req_err.__class__.__name__, req_err)
            self._log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt as err:
            msg = "Process ended by user."
            self._log_msg(msg, out_indent='\n')
            print()
            return None
        
        if not param_res.ok:
            err = self._get_exception(param_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self._log_msg(msg, 'warning')
                return msg
                
        msg = "Order removed successfully."
        self._log_msg(msg)
                
        return param_res.json()
        
    def search(self, collection, filters=None, features=None, dates=None, 
                resultFields=[], maxResults=None):
        """
        Sends a search to the RAPI to search for image results.
        
        :param collection: The Collection ID for the query.
        :type  collection: str
        :param filters: A dictionary of query filters and values in 
                    the following format:
                    
                ``{"|filter title|": ("|operator|", ["value1", "value2", ...]), ...}``
                
                Example: ``{"Beam Mnemonic": {'=': []}}``
        
        :type  filters: dict
        :param features: A list of tuples containing the operator and filenames or coordinates of features to use in the search. The features can be:
                
                - a filename (ESRI Shapefile, KML, GML or GeoJSON)
                - a WKT format string
                - the 'geometry' entry from a GeoJSON Feature
                - a list of coordinates (ex: ``[(x1, y1), (x2, y2), ...]``)
        :type  features: list
        :param dates: A list of date range dictionaries with keys ``start`` and ``end``.
                The values of the ``start`` and ``end`` can either be a string in format
                ``yyyymmdd_hhmmss`` or a datetime.datetime object.
                
                Example:
                    ``[{"start": "20201013_120000", "end": "20201013_150000"}]``
                    
        :type  dates: list
        :param resultFields: A name of a field to include in the query results.
        :type  resultFields: str
        :param maxResults: The maximum number of results to return from the query.
        :type  maxResults: str or int
        
        """
        
        # Get the proper Collection ID for the RAPI
        self.collection = self._get_fullCollId(collection)
        
        if self.collection is None: return None
        
        params = {'collection': self.collection}
        
        if filters is not None or features is not None or dates is not None:
            params['query'] = self._parse_query(filters, features, dates)
        
        if isinstance(resultFields, str):
            resultFields = [resultFields]
        
        result_field = []
        for field in resultFields:
            field_id = self._get_fieldId(field, field_type='results')
            if field_id is None:
                msg = "Field '%s' does not exist for collection '%s'. "\
                        "Excluding it from resultField entry." % (field, \
                        self.collection)
                self._log_msg(msg, 'warning')
            else:
                result_field.append(field_id)
        
        # Get the geometry field and add it to resultField
        footprint_id = self._get_fieldId('Footprint', collection)
        if footprint_id is not None:
            result_field.append(footprint_id)
                
        # Get the pixel spacing field and add it to resultField
        pixspace_id = self._get_fieldId('Spatial Resolution', \
                        collection)
        if pixspace_id is not None:
            result_field.append(pixspace_id)
        
        params['resultField'] = ','.join(result_field)
        
        params['maxResults'] = self.limit_interval
        if maxResults is None or maxResults == '':
            self.max_results = None
        else:
            self.max_results = int(maxResults)
            
            if self.max_results is not None:
                params['maxResults'] = self.max_results \
                        if int(self.max_results) < int(self.limit_interval) \
                        else self.limit_interval
        
        params['format'] = "json"
        
        query_str = urlencode(params)
        self._search_url = "%s/search?%s" % (self.rapi_root, query_str)
        
        print()
        print(self._search_url)
        
        # Clear self.results
        self.results = []
        
        msg = "Searching for %s images on RAPI" % self.collection
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        logger.debug("RAPI URL:\n\n%s\n" % self._search_url)
        # Send the query to the RAPI
        self._submit_search()
        
        self.res_mdata = None
        
        msg = "Number of %s images returned from RAPI: %s" % \
                (self.collection, len(self.results))
        self._log_msg(msg)
        
    def get_results(self, form='raw'):
        """
        Gets the self.results in a given format
        
        :param form: The type of format to return.
            
            Available options:
            
            - ``raw``: Returns the JSON results straight from the RAPI.
            - ``full``: Returns a JSON with full metadata information.
            - ``geojson``: Returns a FeatureCollection of the results
                        (requires geojson package).
                            
        :type  form: str
        
        :return: A dictionary of the results from self.results variable.
        :rtype:  dict
        
        """
        
        if self.results is None or \
            isinstance(self.results, QueryError):
            msg = "No results exist. Please use search() to run a search " \
                    "on the RAPI."
            self._log_msg(msg, 'warning')
            return None
            
        if len(self.results) == 0: return self.results
            
        self.res_format = form
            
        if self.res_format == 'full':
            if self.res_mdata is None:
                self.res_mdata = self._fetch_metadata()
            return self.res_mdata
        elif self.res_format == 'geojson':
            if self.res_mdata is None:
                self.res_mdata = self._fetch_metadata()
            return self.geo.convert_toGeoJSON(self.res_mdata)
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
        
    def order(self, results, priority="Medium", parameters=None, 
                destinations=[]):
        """
        Sends an order to EODMS using the RAPI.
        
        :param results: A list of JSON results from the RAPI.
                            
                The results list must contain a ``collectionId`` key and 
                a ``recordId`` key for each image.
                
        :type  results: list
        :param priority: Determines the priority of the order.
                
            If you'd like to specify a separate priority for each image,
            pass a list of dictionaries containing the ``recordId`` (matching 
            the IDs in results) and ``priority``, such as:
            
            ``[{"recordId": 7627902, "priority": "Low"}, ...]``
                    
            Priority options: "Low", "Medium", "High" or "Urgent"
        
        :type  priority: str or list
        :param parameter: Either a list of parameters or a list of record items.
                
                Use the get_orderParameters method to get a list of available parameters.
                
                **Parameter list**: ``[{"|internalName|": "|value|"}, ...]``
                
                    Example: ``[{"packagingFormat": "TARGZ"}, {"NOTIFICATION_EMAIL_ADDRESS": "kevin.ballantyne@canada.ca"}, ...]``
                
                **Parameters for each record**: ``[{"recordId": |recordId|, "parameters": [{"|internalName|": "|value|"}, ...]}]``
                  
                    Example: ``[{"recordId": 7627902, "parameters": [{"packagingFormat": "TARGZ"}, ...]}]``
        
        :type parameter: list
        """
        
        msg = "Submitting order items..."
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # Add the 'Content-Type' option to the header
        self._session.headers.update({'Content-Type': 'application/json'})
        
        # Create the items from the list of results
        coll_key = self._get_conv('collectionId')
        recid_key = self._get_conv('recordId')
        
        items = [{'collectionId': item[coll_key], \
                'recordId': item[recid_key]} \
                for item in results]
        
        items = []
        for r in results:
            # Set the Collection ID and Record ID
            item = {'collectionId': r[coll_key], \
                    'recordId': r[recid_key]}
            
            # Set the priority
            if priority is not None and not priority.lower() == 'medium':
                item['priority'] = priority
            if 'priority' in r.keys():
                item['priority'] == r[self._get_conv('priority')]
            
            # Set parameters
            if parameters is not None:
                item['parameters'] = parameters
            if 'parameters' in r.keys():
                item['parameters'] = r[self._get_conv('parameters')]
                
            if item['collectionId'] == 'NAPL':
                params = item.get('parameters')
                if params is None: params = []
                params.append({"MediaType": "DIGITAL"})
                params.append({"FreeMode": "true"})
                item['parameters'] = params
                
            items.append(item)
        
        # Create the dictionary for the POST request JSON
        post_dict = {"destinations": destinations, 
                    "items": items}
                    
        # Dump the dictionary into a JSON object
        post_json = json.dumps(post_dict)
        
        # Set the RAPI URL
        order_url = "%s/order" % self.rapi_root
        
        logger.debug("RAPI URL:\n\n%s\n" % order_url)
        logger.debug("RAPI POST:\n\n%s\n" % post_json)
        
        # Send the JSON request to the RAPI
        time_submitted = datetime.datetime.now(tzlocal()).isoformat()
        try:
            order_res = self._session.post(url=order_url, data=post_json)
            order_res.raise_for_status()
        except (requests.exceptions.HTTPError, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as req_err:
            msg = "%s Error: %s" % (req_err.__class__.__name__, req_err)
            self._log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt as err:
            msg = "Process ended by user."
            self._log_msg(msg, out_indent='\n')
            print()
            return None
        
        if not order_res.ok:
            err = self._get_exception(order_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self._log_msg(msg, 'warning')
                return msg
        
        # Add the time the order was submitted
        items = order_res.json()['items']
        
        for i in items:
            i['dateRapiOrdered'] = time_submitted
            
        order_res = {'items': items}
                
        msg = "Order submitted successfully."
        self._log_msg(msg)
                
        return order_res
        
    def cancel_orderItem(self, orderId, itemId):
        
        """
        Removes an Order Item from the EODMS using the RAPI.
        
        :param orderId: The Order ID of the Order Item to remove.
        :type  orderId: int or str
        :param itemId: The Order Item ID of the Order Item to remove.
        :type  itemId: int or str
            
        :return: Returns the contents of the Delete request (always empty).
        :rtype:  byte str
        """
        
        msg = "Removing order item %s..." % itemId
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # Set the RAPI URL
        order_url = "%s/order/%s/%s" % (self.rapi_root, orderId, itemId)
        
        # Send the JSON request to the RAPI
        try:
            cancel_res = self._session.delete(url=order_url)
            cancel_res.raise_for_status()
        except (requests.exceptions.HTTPError, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as req_err:
            err = self._get_exception(cancel_res)._get_msgs()
            msg = "%s Error: %s - %s" % (req_err.__class__.__name__, \
                    req_err, err[1])
            self._log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt as err:
            msg = "Process ended by user."
            self._log_msg(msg, out_indent='\n')
            print()
            return None
        
        if not cancel_res.ok:
            err = self._get_exception(cancel_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self._log_msg(msg, 'warning')
                return msg
                
        msg = "Order removed successfully."
        self._log_msg(msg)
                
        return cancel_res.content
