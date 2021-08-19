
Initializing the EODMSRAPI
==================================================

The EODMSRAPI class is the object which contains the methods and functions used to access the EODMS REST API service.

.. code-block:: python

   from eodms_rapi import EODMSRAPI

Initialization of the EODMSRAPI requires entry of a password from a valid EODMS account. 

.. note::
	If you do not have an EODMS account, please visit https://www.eodms-sgdot.nrcan-rncan.gc.ca/index-en.html and click the **Register (Required to Order)** link under **Account**.

.. code-block:: python

   rapi = EODMSRAPI('eodms-username', 'eodms-password')

