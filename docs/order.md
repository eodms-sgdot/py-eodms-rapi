Order Images
============

To order images using the RAPI, a POST request is submitted containing the following JSON (as an example):

```json
{
	"destinations": [],
	"items": [
		{
			"collectionId": "RCMImageProducts", 
			"recordId": "7822244", 
			"parameters": [
				{
					"packagingFormat": "TAR"
				}, 
				{
					"NOTIFICATION_EMAIL_ADDRESS": "example@email.com"
				}
			]
		}
	]
}
```

So, ordering images using the EODMSRAPI requires a list of **results** (items) and optional **priority**, **parameters** and **destinations** values.

### Results

The **results** parameter can be a list of results returned from a search session or a list of items. The **results** is required.

Each item must have: ```recordId``` ```collectionId```

### Priority

The **priority** can be a single string entry ("Low", "Medium", "High", or "Urgent") which will be applied to all images or a list of dictionaries containing ```recordId``` and ```priority``` value for each individual image. The **priority** is optional and the default is "Medium".

### Parameters

The **parameters** can be a list of parameter dictionaries which will be applied to all images or a list of dictionaries containing the ```recordId``` and ```parameters```.

Each item in the ```parameters``` list should be the same as how it appears in the POST request (ex: ```{"packagingFormat": "TAR"}```)

You can get a list of available parameters by calling the ```get_orderParameters``` method of the EODMSRAPI, submitting arguments **collection** and **recordId**. The **parameters** is optional.

### Destinations
	
The **destinations** is a list of destination dictionaries containing a set of items. There are 2 types of destinations, "FTP" and "Physical".

The "FTP" dictionary would look something like this:
	
```json
{
	"type": "FTP", 
	"name": "FTP Name", 
	"hostname": "ftp://ftpsite.com", 
	"username": "username", 
	"password": "password", 
	"stringValue": "ftp://username@ftpsite.com/downloads", 
	"path": "downloads", 
	"canEdit": "false"
}
```
	
The "Physical" dictionary would look like this:
	
```json
{
	"type": "Physical", 
	"name": "Destination Name", 
	"customerName": "John Doe", 
	"contactEmail": "example@email.com", 
	"organization": "Organization Name", 
	"phone": "555-555-5555", 
	"addr1": "123 Fake Street", 
	"addr2": "Optional", 
	"addr3": "Optional", 
	"city": "Ottawa", 
	"stateProv": "Ontario", 
	"country": "Canada", 
	"postalCode": "A1A 1A1", 
	"classification": "Optional"
}
```
	
For more information on the destination items, visit [Directly Accessing the EODMS REST API](https://github.com/nrcan-eodms-sgdot-rncan/eodms-rapi-orderdownload/wiki/Directly-Accessing-the-EODMS-REST-API#order-destination-json).

### Example

Here's an example of how to submit an order to the EODMSRAPI using the previous search session:

```python
params = [{"packagingFormat": "TAR"}]

order_res = rapi.order(res, priority="low", parameters=params)
```
