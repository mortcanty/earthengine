# Change Detection with Google Earth Engine Imagery
A simple Flask web application for performing change detection tasks with 
<a href="https://developers.google.com/earth-engine/">Google Earth Engine</a> imagery *. 

The AppEngine version (web version) is for demonstration only and has very limited functionality.
Exporting results in particular is not possible.

The local version runs in a docker container serving the Flask web application on localhost.

On the localhost, assuming you have been granted access to the Earth Engine, you can carry out the following tasks:

 1. Run the iMAD (iteratively re-weighted MAD) algorithm on LANDAT-5 TM bitemporal imagery. CCA is done on the client side 
 until Cholesky decomposition becomes available on the GEE API. This means that only small image subsets can be processed and iterations
 cannot exceed about 10. The code will later be extended to run LANDSAT-7, LANDSAT-8, ASTER 
 and Sentinel-2 optical/infrared imagery.
 
    <a href="http://www2.imm.dtu.dk/pubdb/views/publication_details.php?id=4695"> 
	A. A. Nielsen (2007). The Regularized Iteratively Reweighted MAD Method for Change Detection in Multi- and Hyperspectral Data.</a>

	<a href="http://www.amazon.com/Analysis-Classification-Change-Detection-Sensing/dp/1466570377/ref=dp_ob_title_bk"> M. J.Canty (2014). 
	Image Analysis, Classification and Change Detection in Remote Sensing, 3rd Ed., CRC Press 2014</a>; 
	
 2. Run the complex Wishart algorithm on polarimetric SAR bitemporal data (presently only Sentinel-1 dual pol, diagonal only, and single pol images).
 
	 <a href = "http://www2.imm.dtu.dk/pubdb/views/publication_details.php?id=1219"> 
	K. Conradsen et al. (2003). A test statistic in the complex Wishart distribution and its 
	application to change detection in polarimetric SAR data IEEE TGRS 41 (1) 4-19.</a>
	
	
 3. Run the (sequential) omnibus algorithm on polarimetric SAR multitemporal data (presently only Sentinel-1 dual pol, diagonal only, and single pol images).
 
	 <a href = "http://www2.imm.dtu.dk/pubdb/views/publication_details.php?id=6825"> 
	K. Conradsen et al. (2016). Determining the points of
	change in time series of polarimetric SAR data. IEEE TGRS 54 (5) 3007-3024.</a>

 3. Export imagery to your Earth Engine assets folder or to Google Drive for off-line local processing.
 
\* Special thanks to Charles G. Morton for making available his implementation of the incomplete gamma function on the  GEE API.

### Installation 

 1. Install <a href="https://docs.docker.com/">Docker</a>
 
 2. In a command window execute the command
 
 		docker run -it -p 5000:5000 --name=ee mort/eedocker 
 		
 3. At the container prompt execute the command
 
 		earthengine authenticate
 	
 	and follow the instructions. You will have to copy the given URL and paste it into your local browser
 	
 4. After successful authentification, run the command
 
 		python app.py
 	
 	and point your browser to 
 	
 		localhost:5000
 
 