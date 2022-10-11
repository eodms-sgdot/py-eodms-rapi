__title__ = 'py-eodms-rapi'
__name__ = 'eodms_rapi'
__author__ = 'Kevin Ballantyne'
__copyright__ = 'Copyright 2020-2022 Her Majesty the Queen in Right of Canada'
__license__ = 'MIT License'
__description__ = 'A Python package to access the EODMS RAPI service.'
__version__ = '1.5.2'
__maintainer__ = 'Kevin Ballantyne'
__email__ = 'eodms-sgdot@nrcan-rncan.gc.ca'

from .eodms import EODMSRAPI
from .eodms import QueryError
from .geo import EODMSGeo