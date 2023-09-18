__title__ = 'py-eodms-rapi'
__name__ = 'eodms_rapi'
__author__ = 'Kevin Ballantyne'
__copyright__ = 'Copyright (c) His Majesty the King in Right of Canada, ' \
                'as represented by the Minister of Natural Resources, 2023'
__license__ = 'MIT License'
__description__ = 'A Python package to access the EODMS RAPI service.'
__maintainer__ = 'Kevin Ballantyne'
__email__ = 'eodms-sgdot@nrcan-rncan.gc.ca'

from .__version__ import __version__
from .eodms import EODMSRAPI
from .eodms import QueryError
from .geo import EODMSGeo