Download Images
===============

The *download* method of the EODMSRAPI requires:
	
- Either the **order results** from the *order* method or a list of **Order Item IDs**.
- A **local destination path** where the images will be downloaded.

```python
dest = "C:\\TEMP"
dn_res = rapi.download(order_res, dest)
```