##############################################################################
# MIT License
#
# Copyright (c) 2020-2022 Her Majesty the Queen in Right of Canada, as
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

__title__ = 'py-eodms-rapi Tester'
__author__ = 'Kevin Ballantyne'
__copyright__ = 'Copyright 2020-2022 Her Majesty the Queen in Right of Canada'
__license__ = 'MIT License'
__description__ = 'Performs various tests of the py-eodms-rapi Python package.'
__email__ = 'eodms-sgdot@nrcan-rncan.gc.ca'

import os
import sys
import eodms_rapi

import unittest

class TestEodmsRapi(unittest.TestCase):

    def test_search(self):
        """
        Tests the search, order and download of the py-eodms-rapi
        """
        
        username = os.getenv('EODMS_USER')
        password = os.environ.get('EODMS_PASSWORD')
        
        print(f"username: {username}")
        print(f"password: {password}")

        rapi = eodms_rapi.EODMSRAPI(username, password)

        # Set a polygon of geographic centre of Canada using GeoJSON
        feat = [
            ('INTERSECTS', {"type": "Polygon", "coordinates": [[[-95.47, 61.4], \
                                                                [-97.47, 61.4],
                                                                [-97.47, 63.4],
                                                                [-95.47, 63.4],
                                                                [-95.47,
                                                                 61.4]]]})]

        # Set date ranges
        dates = [{"start": "20190101_000000", "end": "20210621_000000"}]

        # Set search filters
        filters = {'Beam Mode Type': ('LIKE', ['%50m%']),
                   'Polarization': ('=', 'HH HV'),
                   'Incidence Angle': ('>=', 17)}

        # Set the results fields
        result_fields = ['ARCHIVE_RCM.PROCESSING_FACILITY',
                         'RCM.ANTENNA_ORIENTATION']

        # Submit search
        rapi.search("RCMImageProducts", filters, feat, dates, result_fields, 2)

        # Get results
        rapi.set_field_convention('upper')
        res = rapi.get_results('full')

        # Now order the images
        order_res = rapi.order(res)

        # Download images to a specific destination
        dest = "files/downloads"
        dn_res = rapi.download(order_res, dest, max_attempts=10)

        # Print results
        rapi.print_results(dn_res)

        assert dn_res is not None and not dn_res == ''

    def test_orderparameters(self):
        """
        Tests getting the order parameters using py-eodms-rapi
        """

        rapi = eodms_rapi.EODMSRAPI(os.getenv('EODMS_USER'),
                                    os.environ.get('EODMS_PASSWORD'))

        # Get the order parameters for RCM image with Record ID 7627902
        param_res = rapi.get_order_parameters('RCMImageProducts', '7627902')

        # Print the parameters
        print(f"param_res: {param_res}")

        assert param_res is not None and not param_res == ''

    def test_deleteorder(self):
        """
        Tests deleting an order using py-eodms-rapi
        """

        rapi = eodms_rapi.EODMSRAPI(os.getenv('EODMS_USER'),
                                    os.environ.get('EODMS_PASSWORD'))

        orders = rapi.get_orders()

        order_id = None
        item_id = None
        for o in orders:
            if o['status'] == 'AVAILABLE_FOR_DOWNLOAD':
                order_id = o['orderId']
                item_id = o['itemId']
                break

        # Delete the order item
        if order_id is not None and item_id is not None:
            delete_res = rapi.cancel_order_item(order_id, item_id)

            assert delete_res is not None and not delete_res == ''

    def test_availablefields(self):
        """
        Tests getting available fields for a collection using py-eodms-rapi
        """

        rapi = eodms_rapi.EODMSRAPI(os.getenv('EODMS_USER'),
                                    os.environ.get('EODMS_PASSWORD'))

        # Get the available field information for RCMImageProducts collection
        fields = rapi.get_available_fields('RCMImageProducts')
        print(fields)

        # Get a list of available field IDs for RCMImageProducts collection
        field_ids = rapi.get_available_fields('RCMImageProducts',
                                              name_type='id')
        print(field_ids)

        # Get a list of available field names used to submit searches (rapi.search())
        field_titles = rapi.get_available_fields('RCMImageProducts',
                                                 name_type='title')
        print(field_titles)

if __name__ == '__main__':
    unittest.main()
