##############################################################################
# MIT License
# 
# Copyright (c) His Majesty the King in Right of Canada, as
# represented by the Minister of Natural Resources, 2023
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
import requests
import traceback

from tqdm.auto import tqdm

# from .geo import EODMSGeo
from .query_error import QueryError

# OTHER_FORMAT = '| %(name)s | %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'

# logger = logging.getLogger('EODMSRAPI')

# # Set handler for output to terminal
# logger.setLevel(logging.DEBUG)
# ch = logging.NullHandler()
# formatter = logging.Formatter('| %(name)s | %(asctime)s | %(levelname)s: '
#                               '%(message)s', '%Y-%m-%d %H:%M:%S')
# ch.setFormatter(formatter)
# logger.addHandler(ch)

class RAPIRequests:
    """
    The RAPIRequests Class containing the methods which sends requests to the 
    RAPI.
    """

    def __init__(self, eodms_obj, username, password, timeout_query=120.0, 
                 timeout_order=180.0, attempts=4, verify=True):
        """
        Initializer for RAPIRequests.
        
        
        """

        self.eodms = eodms_obj

        # Create session
        self._session = requests.Session()
        self._session.auth = (username, password)

        self.rapi_root = "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi"

        self.timeout_query = timeout_query
        self.timeout_order = timeout_order
        self.attempts = attempts
        self.verify = verify

        # self.geo = EODMSGeo(self)

        self.logger = eodms_obj.logger

        self._headers = {}

        # print(f"version: {eodms_obj.__version__()}")

        # self._map_fields()

        # self._header = '| EODMSRAPI | '

    def close_session(self):

        self.eodms.log_msg("Logging out of EODMS", log_indent='\n\n\t', 
                           out_indent='\n')
        
        self._session.get('https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/logout.jsp')

    def check_http(self, err_msg):
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

    def add_header(self, key, value, append=False, top=True):
        """
        Add a value to either existing key or add new key.

        :param key: The key in the header to change.
        :type  key: str
        :param value: The value to add to the header.
        :type  key: str
        :param append: Determines whether to add the value to the header or 
                    replace the existing header with value.
        :type  append: boolean
        """

        entry = {key: value}
        if append:
            if self._session:
                exist_entry = self._session.headers.get(key)
            else:
                exist_entry = self._headers.get(key)

            if top:
                entry = {key: f"{value} {exist_entry}"}
            else:
                entry = {key: f"{exist_entry} {value}"}

        if self._session:
            self._session.headers.update(entry)
        else:
            self._headers.update(entry)

        # print(f"Session headers: {self._session.headers}")
        # print(f"headers: {self._headers}")

    def submit(self, query_url, request_type='get', post_data=None,
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

        self.logger.debug(f"RAPI Query URL: {query_url}")

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
                else:
                    msg = f"Sending request to the RAPI for '{record_name}' " \
                              f"(attempt {attempt})..."
                if not quiet and attempt > 1:
                    self.logger.debug(f"\n{self.eodms.header}{msg}")
                if self._session is None:
                    if request_type.lower() == 'post':
                        res = requests.post(query_url, post_data,
                                            headers=self._headers,
                                            timeout=timeout, 
                                            verify=self.verify)
                    elif request_type.lower() == 'put':
                        res = requests.put(url=query_url,
                                           headers=self._headers,
                                           timeout=timeout,
                                           verify=self.verify)
                    elif request_type.lower() == 'delete':
                        res = requests.delete(url=query_url,
                                              headers=self._headers,
                                              timeout=timeout,
                                              verify=self.verify)
                    else:
                        res = requests.get(query_url, headers=self._headers, 
                                           timeout=timeout,
                                           verify=self.verify)
                elif request_type.lower() == 'post':
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

                out_msg = self.check_http(msg)

                if out_msg is not None:
                    err = out_msg
                    query_err = QueryError(err)

                    return query_err if self._check_auth(query_err) \
                        else query_err

                if attempt < self.attempts:
                    msg = f"{msg}; attempting to connect again..."
                    self.eodms.log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
            except requests.exceptions.SSLError as ssl_err:
                msg = f"SSL Error: {ssl_err}"
                if attempt < self.attempts:
                    msg = f"{msg}; removing SSL verification and attempting " \
                              f"to connect again..."
                    self.eodms.log_msg(msg, 'warning')
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
                    self.eodms.log_msg(msg, 'warning')
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
                self.eodms.log_msg(self.err_msg, 'error')
                # attempt = self.attempts
                return None
            except KeyboardInterrupt:
                self.err_msg = "Process ended by user."
                self.eodms.log_msg(self.err_msg, out_indent='\n')
                self.err_occurred = True
                return None
            except Exception:
                msg = f"Unexpected error: {traceback.format_exc()}"
                if attempt < self.attempts:
                    msg = f"{msg}; attempting to connect again..."
                    self.eodms.log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1

        if err is not None:
            query_err = QueryError(err)

            return None if self._check_auth(query_err) else query_err
        # If no results from RAPI, return None
        if res is None:
            return None

        # Check for exceptions that weren't already caught
        if not res.ok:
            except_err = self._get_exception(res)

            if isinstance(except_err, QueryError):
                if self._check_auth(except_err):
                    return None

                self.eodms.log_msg(msg, 'warning')
                return except_err

        if res.text == '':
            return res

        if res.text.find('BRB!') > -1:
            self.err_msg = f"There was a problem while attempting to access the " \
                      f"EODMS RAPI server. If the problem persists, please " \
                      f"contact the EODMS Support Team at {self._email}."
            self.eodms.log_msg(self.err_msg, 'error')
            self.err_occurred = True
            query_err = QueryError(self.err_msg)
            return query_err

        return res.json() if as_json else res

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

    def download(self, url, dest_fn, fsize, show_progress=True):
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

        # Use streamed download so we can wrap nicely with tqdm
        if show_progress:
            with self._session.get(url, stream=True, verify=self.verify) as stream:
                with open(dest_fn, 'wb') as pipe:
                    with tqdm.wrapattr(
                            pipe,
                            method='write',
                            miniters=1,
                            total=fsize,
                            desc=f"{self.eodms.header}{os.path.basename(dest_fn)}"
                    ) as file_out:
                        for chunk in stream.iter_content(chunk_size=1024):
                            file_out.write(chunk)
        else:
            response = self._session.get(url, stream=True, verify=self.verify)
            open(dest_fn, "wb").write(response.content)

        return dest_fn
